#!/usr/bin/env python3
"""
INITIUM Video Generation Backend
Serves the static website + API endpoints for Seedance 2.0 video generation.

Run:
    cd /home/hermes/initium-website/backend
    python3 app.py

Or with gunicorn:
    gunicorn -w 2 -b 0.0.0.0:5000 app:app
"""

import os
import sys
import json
import uuid
import threading
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
from werkzeug.utils import secure_filename

from auth import (
    init_admin_key,
    require_api_key,
    require_admin_key,
    create_team_key,
    revoke_team_key,
    delete_team_key,
    list_team_keys,
    record_usage,
)
from seedance import (
    submit_task,
    get_task_status,
    extract_video_url,
    download_video,
    build_text_only_payload,
    build_multimodal_payload,
)

# ═══════════════════════════════════════════════════════════
app = Flask(__name__, static_folder="../", static_url_path="")
CORS(app, resources={r"/api/*": {"origins": "*"}})

ADMIN_KEY = init_admin_key()

# In-memory job tracker (for demo; use Redis in production)
jobs = {}
jobs_lock = threading.Lock()

VIDEO_DIR = Path("/home/hermes/initium-website/backend/static/videos")
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

UPLOAD_DIR = Path("/home/hermes/initium-website/backend/static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

UPLOAD_MAX_AGE = 86400 * 7  # Keep uploads for 7 days
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "mp3", "mp4", "wav"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

JOBS_FILE = Path(__file__).parent / "jobs.json"

# ═══════════════════════════════════════════════════════════
# PERSISTENCE
# ═══════════════════════════════════════════════════════════

def _load_jobs():
    global jobs
    if JOBS_FILE.exists():
        try:
            with open(JOBS_FILE) as f:
                jobs = json.load(f)
        except:
            jobs = {}


def _save_jobs():
    with open(JOBS_FILE, "w") as f:
        json.dump(jobs, f, indent=2, default=str)


_load_jobs()

# ═══════════════════════════════════════════════════════════
# STATIC SITE
# ═══════════════════════════════════════════════════════════

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(app.static_folder, path)


# ═══════════════════════════════════════════════════════════
# TEAM API (Protected by API Key)
# ═══════════════════════════════════════════════════════════

@app.route("/api/generate", methods=["POST"])
@require_api_key
def api_generate():
    """Submit a video generation task."""
    data = request.get_json(force=True) or {}
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    ratio = data.get("ratio", "9:16")
    duration = min(int(data.get("duration", 5)), 11)
    images = data.get("images", []) or []
    video = data.get("video")
    audio = data.get("audio")
    generate_audio = data.get("generate_audio", True)
    watermark = data.get("watermark", False)

    # Build payload
    kwargs = {"generate_audio": generate_audio, "watermark": watermark}
    if images or video or audio:
        payload = build_multimodal_payload(
            prompt, images=images or None, video=video, audio=audio,
            ratio=ratio, duration=duration, **kwargs
        )
    else:
        payload = build_text_only_payload(
            prompt, ratio=ratio, duration=duration, **kwargs
        )

    try:
        task_id = submit_task(payload)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    job_id = str(uuid.uuid4())[:8]
    job = {
        "id": job_id,
        "task_id": task_id,
        "prompt": prompt,
        "ratio": ratio,
        "duration": duration,
        "status": "submitted",
        "created_by": request.api_key_entry.get("name", "unknown"),
        "created_at": datetime.utcnow().isoformat(),
        "video_path": None,
        "video_url": None,
        "error": None,
    }

    with jobs_lock:
        jobs[job_id] = job
        _save_jobs()

    record_usage(request.headers.get("X-API-Key").strip())

    return jsonify({"job": job}), 202


@app.route("/api/jobs/<job_id>", methods=["GET"])
@require_api_key
def api_get_job(job_id):
    """Get job status + poll Seedance for updates."""
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    # If still running, poll upstream
    if job["status"] in ("submitted", "running", "pending"):
        try:
            status = get_task_status(job["task_id"])
            state = status.get("status", "unknown")

            if state in ("completed", "succeeded", "success"):
                job["status"] = "completed"
                try:
                    video_url = extract_video_url(status)
                    job["video_url"] = video_url

                    # Download locally
                    filename = f"{job_id}.mp4"
                    local_path = VIDEO_DIR / filename
                    download_video(video_url, str(local_path))
                    job["video_path"] = f"/videos/{filename}"
                except Exception as e:
                    job["status"] = "failed"
                    job["error"] = f"Download failed: {e}"

            elif state in ("failed", "error", "cancelled"):
                job["status"] = "failed"
                err = status.get("error", {})
                job["error"] = err.get("message", "Unknown error")

            else:
                job["status"] = state

            with jobs_lock:
                jobs[job_id] = job
                _save_jobs()

        except Exception as e:
            job["error"] = str(e)

    return jsonify({"job": job})


@app.route("/api/jobs", methods=["GET"])
@require_api_key
def api_list_jobs():
    """List all jobs for this API key's user."""
    name = request.api_key_entry.get("name", "")
    with jobs_lock:
        user_jobs = [j for j in jobs.values() if j.get("created_by") == name]
    return jsonify({"jobs": sorted(user_jobs, key=lambda x: x["created_at"], reverse=True)})


@app.route("/api/me", methods=["GET"])
@require_api_key
def api_me():
    """Return current key info."""
    return jsonify({"key": request.api_key_entry})


# ═══════════════════════════════════════════════════════════
# FILE UPLOAD
# ═══════════════════════════════════════════════════════════

def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _cleanup_old_uploads():
    """Delete upload files older than UPLOAD_MAX_AGE."""
    now = time.time()
    for f in UPLOAD_DIR.iterdir():
        if f.is_file() and now - f.stat().st_mtime > UPLOAD_MAX_AGE:
            try:
                f.unlink()
            except OSError:
                pass


@app.route("/api/upload", methods=["POST"])
@require_api_key
def api_upload():
    """Upload a file (image/video/audio). Returns public URL."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not _allowed_file(file.filename):
        return jsonify({"error": f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    # Check size by reading into memory (simple approach)
    file_data = file.read()
    if len(file_data) > MAX_FILE_SIZE:
        return jsonify({"error": f"File too large. Max {MAX_FILE_SIZE // 1024 // 1024}MB"}), 400

    # Save with UUID prefix to avoid collisions
    ext = secure_filename(file.filename).rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex[:16]}.{ext}"
    filepath = UPLOAD_DIR / filename

    with open(filepath, "wb") as f:
        f.write(file_data)

    # Lazy cleanup on each upload
    _cleanup_old_uploads()

    # Return absolute URL that Seedance can fetch
    base = request.host_url.rstrip("/")
    file_url = f"{base}/uploads/{filename}"
    return jsonify({
        "url": file_url,
        "filename": filename,
        "size": len(file_data),
    })


@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)


# ═══════════════════════════════════════════════════════════
# ADMIN API (Protected by Admin Key)
# ═══════════════════════════════════════════════════════════

@app.route("/admin/keys", methods=["GET"])
@require_admin_key
def admin_list_keys():
    return jsonify({"keys": list_team_keys()})


@app.route("/admin/keys", methods=["POST"])
@require_admin_key
def admin_create_key():
    data = request.get_json(force=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    entry = create_team_key(name)
    return jsonify({"key": entry}), 201


@app.route("/admin/keys/<key>/revoke", methods=["POST"])
@require_admin_key
def admin_revoke_key(key):
    if revoke_team_key(key):
        return jsonify({"message": "Key revoked"})
    return jsonify({"error": "Key not found"}), 404


@app.route("/admin/keys/<key>", methods=["DELETE"])
@require_admin_key
def admin_delete_key(key):
    if delete_team_key(key):
        return jsonify({"message": "Key deleted"})
    return jsonify({"error": "Key not found"}), 404


@app.route("/admin/jobs", methods=["GET"])
@require_admin_key
def admin_list_jobs():
    with jobs_lock:
        all_jobs = list(jobs.values())
    return jsonify({"jobs": sorted(all_jobs, key=lambda x: x["created_at"], reverse=True)})


@app.route("/admin/stats", methods=["GET"])
@require_admin_key
def admin_stats():
    with jobs_lock:
        total = len(jobs)
        completed = sum(1 for j in jobs.values() if j["status"] == "completed")
        failed = sum(1 for j in jobs.values() if j["status"] == "failed")
    return jsonify({
        "total_jobs": total,
        "completed": completed,
        "failed": failed,
        "keys_count": len(list_team_keys()),
    })


# ═══════════════════════════════════════════════════════════
# VIDEO SERVING
# ═══════════════════════════════════════════════════════════

@app.route("/videos/<path:filename>")
def serve_video(filename):
    return send_from_directory(VIDEO_DIR, filename)


# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"\n🚀 INITIUM Video Backend")
    print(f"   Admin key: {ADMIN_KEY[:20]}...")
    print(f"   Static folder: {app.static_folder}")
    print(f"   Listening on http://0.0.0.0:5000\n")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
