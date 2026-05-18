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
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

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
from imagegen import (
    generate_image,
    poll_image_result_fal,
    extract_image_url_fal,
    download_image,
    ALL_MODELS,
)

# ═══════════════════════════════════════════════════════════
app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app, resources={r"/api/*": {"origins": "*"}})

ADMIN_KEY = init_admin_key()

# In-memory job tracker (for demo; use Redis in production)
jobs = {}
jobs_lock = threading.Lock()

VIDEO_DIR = Path("static/videos")
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_DIR = Path("static/images")
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

UPLOAD_DIR = Path("static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

UPLOAD_MAX_AGE = 86400 * 7  # Keep uploads for 7 days
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "mp3", "mp4", "wav"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

JOBS_FILE = Path("jobs.json")
SUBMISSIONS_FILE = Path("submissions.json")
TOURS_FILE = Path("tours.json")

def _load_tours():
    if TOURS_FILE.exists():
        try:
            with open(TOURS_FILE) as f:
                return json.load(f)
        except:
            return []
    return []


def _save_tours(tours):
    with open(TOURS_FILE, "w") as f:
        json.dump(tours, f, indent=2, default=str)


def _detect_platform(url):
    url = url.lower()
    if "lumalabs.ai" in url or "luma.ai" in url:
        return "Luma AI"
    if "polycam.ai" in url or "polycam" in url:
        return "Polycam"
    if "sketchfab.com" in url:
        return "Sketchfab"
    if "playcanvas.com" in url:
        return "PlayCanvas"
    if "matterport.com" in url:
        return "Matterport"
    if "supersplat" in url:
        return "SuperSplat"
    return "Other"


def _build_embed_iframe(url):
    """Build an embed iframe src for known platforms."""
    url = url.strip()
    if "sketchfab.com" in url:
        # Convert viewer URL to embed URL
        if "/embed" not in url:
            url = url.rstrip("/") + "/embed"
        return url + "?autostart=0&ui_theme=dark"
    if "playcanvas.com" in url:
        if "/embed" not in url:
            url = url.rstrip("/") + "/embed"
        return url
    # Generic fallback: wrap in iframe
    return url

# Telegram notification config
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8838407168:AAEmuWjjoswhuOpi4a-85FfG3GlUhOY9vT8")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "328460225")

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


def _load_submissions():
    if SUBMISSIONS_FILE.exists():
        try:
            with open(SUBMISSIONS_FILE) as f:
                return json.load(f)
        except:
            return []
    return []


def _save_submissions(subs):
    with open(SUBMISSIONS_FILE, "w") as f:
        json.dump(subs, f, indent=2, default=str)


_load_jobs()

import stripe

# ═══════════════════════════════════════════════════════════
# STRIPE SETUP
# ═══════════════════════════════════════════════════════════

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")

PRICING = {
    5: {"amount_cents": 500, "label": "S$5.00", "duration": 5},
    10: {"amount_cents": 800, "label": "S$8.00", "duration": 10},
}

# Track used payments to prevent double-spending
PAYMENTS_FILE = Path("payments.json")
payments = {}
payments_lock = threading.Lock()


def _load_payments():
    global payments
    if PAYMENTS_FILE.exists():
        try:
            with open(PAYMENTS_FILE) as f:
                payments = json.load(f)
        except:
            payments = {}


def _save_payments():
    with open(PAYMENTS_FILE, "w") as f:
        json.dump(payments, f, indent=2, default=str)


_load_payments()


# ═══════════════════════════════════════════════════════════
# STATIC SITE
# ═══════════════════════════════════════════════════════════

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/<path:path>")
def static_files(path):
    if path.startswith("api/"):
        abort(404)
    return send_from_directory(app.static_folder, path)


# ═══════════════════════════════════════════════════════════
# TEAM API (Protected by API Key)
# ═══════════════════════════════════════════════════════════

@app.route("/api/generate", methods=["POST"])
@require_api_key
def api_generate():
    """Submit a video generation task. Requires verified payment."""
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
    payment_intent_id = data.get("payment_intent_id", "").strip()

    # Verify payment
    if not payment_intent_id:
        return jsonify({"error": "Payment required. Please pay before generating."}), 402

    with payments_lock:
        if payment_intent_id in payments:
            return jsonify({"error": "Payment already used. Please pay again."}), 402

    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        if intent.status != "succeeded":
            return jsonify({"error": f"Payment not completed. Status: {intent.status}"}), 402

        # Mark as used
        with payments_lock:
            payments[payment_intent_id] = {
                "used_at": datetime.utcnow().isoformat(),
                "user": request.api_key_entry.get("name", "unknown"),
                "amount": intent.amount,
                "duration": duration,
            }
            _save_payments()
    except Exception as e:
        return jsonify({"error": f"Payment verification failed: {e}"}), 402

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


@app.route("/api/generate-image", methods=["POST"])
@require_api_key
def api_generate_image():
    """Submit an image generation task via fal.ai. Free for team members."""
    data = request.get_json(force=True) or {}
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    ratio = data.get("ratio", "16:9")
    model = data.get("model", "seedream-4.5")
    if model not in ALL_MODELS:
        model = "seedream-4.5"

    try:
        result = generate_image(model, prompt, ratio=ratio)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    job_id = str(uuid.uuid4())[:8]

    # BytePlus is synchronous — complete immediately
    if result.get("provider") == "byteplus":
        try:
            filename = f"{job_id}.png"
            local_path = IMAGE_DIR / filename
            download_image(result["url"], str(local_path))
            job = {
                "id": job_id,
                "task_id": None,
                "status_url": None,
                "prompt": prompt,
                "ratio": ratio,
                "model": model,
                "status": "completed",
                "created_by": request.api_key_entry.get("name", "unknown"),
                "created_at": datetime.utcnow().isoformat(),
                "image_path": f"/images/{filename}",
                "image_url": result["url"],
                "error": None,
            }
        except Exception as e:
            job = {
                "id": job_id,
                "task_id": None,
                "status_url": None,
                "prompt": prompt,
                "ratio": ratio,
                "model": model,
                "status": "failed",
                "created_by": request.api_key_entry.get("name", "unknown"),
                "created_at": datetime.utcnow().isoformat(),
                "image_path": None,
                "image_url": None,
                "error": str(e),
            }
    else:
        # fal.ai async path
        job = {
            "id": job_id,
            "task_id": result.get("request_id", ""),
            "status_url": result.get("status_url", ""),
            "prompt": prompt,
            "ratio": ratio,
            "model": model,
            "status": "submitted",
            "created_by": request.api_key_entry.get("name", "unknown"),
            "created_at": datetime.utcnow().isoformat(),
            "image_path": None,
            "image_url": None,
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
            # ── Image jobs (fal.ai) ──
            if job.get("status_url"):
                status = poll_image_result_fal(job["status_url"])
                status_state = status.get("status", "unknown")

                if status_state in ("completed", "success") or "images" in status:
                    job["status"] = "completed"
                    try:
                        image_url = extract_image_url_fal(status)
                        job["image_url"] = image_url
                        filename = f"{job_id}.png"
                        local_path = IMAGE_DIR / filename
                        download_image(image_url, str(local_path))
                        job["image_path"] = f"/images/{filename}"
                    except Exception as e:
                        job["status"] = "failed"
                        job["error"] = f"Download failed: {e}"

                elif status_state in ("failed", "error", "cancelled"):
                    job["status"] = "failed"
                    job["error"] = status.get("error", "Unknown error")
                else:
                    job["status"] = status_state

            # ── Video jobs (Seedance) ──
            else:
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


@app.route("/api/projects", methods=["GET"])
def api_projects():
    """Return scraped EcoProp new launch projects. Public endpoint. Supports filtering."""
    try:
        with open("ecoprop_projects.json", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return jsonify({"error": "Project data not available yet"}), 404

    projects = data.get("projects", [])

    # Query params
    search = (request.args.get("search", "")).lower().strip()
    district = request.args.get("district", "").strip()
    property_type = request.args.get("property_type", "").lower().strip()
    tenure = request.args.get("tenure", "").lower().strip()
    min_price = request.args.get("min_price", type=int)
    max_price = request.args.get("max_price", type=int)
    sort = request.args.get("sort", "name")  # name, price_asc, price_desc, district

    def normalize_tenure(t):
        t = (t or "").lower()
        if "freehold" in t:
            return "freehold"
        if "999" in t:
            return "999"
        if "leasehold" in t and "99" not in t:
            return "leasehold"
        if "99" in t:
            return "99"
        return ""

    def get_category(pt):
        pt = (pt or "").lower()
        if "executive condominium" in pt or pt == "ec":
            return "ec"
        if any(x in pt for x in ["landed", "cluster", "villa", "low-rise residential"]):
            return "landed"
        if any(x in pt for x in ["commercial", "industrial", "mixed"]):
            return "commercial"
        return "condo"

    filtered = []
    for p in projects:
        if search:
            hay = " ".join([
                p.get("project_name", ""),
                p.get("district", ""),
                p.get("location", ""),
                p.get("address", ""),
                p.get("property_type", ""),
            ]).lower()
            if search not in hay:
                continue
        if district and p.get("district") != district:
            continue
        if property_type and get_category(p.get("property_type", "")) != property_type:
            continue
        if tenure and normalize_tenure(p.get("tenure", "")) != tenure:
            continue
        if min_price is not None and (p.get("min_price") or 0) < min_price:
            continue
        if max_price is not None and (p.get("min_price") or 0) > max_price:
            continue
        filtered.append(p)

    # Sorting
    if sort == "price_asc":
        filtered.sort(key=lambda x: x.get("min_price") or 999999999)
    elif sort == "price_desc":
        filtered.sort(key=lambda x: x.get("min_price") or 0, reverse=True)
    elif sort == "district":
        filtered.sort(key=lambda x: x.get("district", ""))
    else:
        filtered.sort(key=lambda x: x.get("project_name", "").lower())

    return jsonify({
        "source": data.get("source", "ecoprop.com"),
        "total": len(filtered),
        "filters_applied": {
            "search": search or None,
            "district": district or None,
            "property_type": property_type or None,
            "tenure": tenure or None,
            "min_price": min_price,
            "max_price": max_price,
            "sort": sort,
        },
        "projects": filtered,
    })


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
# PAYMENT API (Stripe)
# ═══════════════════════════════════════════════════════════

@app.route("/api/pricing", methods=["GET"])
def api_pricing():
    """Return pricing + Stripe publishable key."""
    return jsonify({
        "stripe_key": STRIPE_PUBLISHABLE_KEY,
        "pricing": PRICING,
        "currency": "sgd",
    })


@app.route("/api/create-payment-intent", methods=["POST"])
@require_api_key
def api_create_payment_intent():
    """Create a Stripe PaymentIntent for a video generation."""
    if not stripe.api_key:
        return jsonify({"error": "Stripe not configured"}), 500

    data = request.get_json(force=True) or {}
    duration = int(data.get("duration", 5))

    if duration not in PRICING:
        return jsonify({"error": "Invalid duration"}), 400

    price = PRICING[duration]

    try:
        intent = stripe.PaymentIntent.create(
            amount=price["amount_cents"],
            currency="sgd",
            metadata={
                "user": request.api_key_entry.get("name", "unknown"),
                "duration": str(duration),
                "api_key": request.headers.get("X-API-Key", "")[:12],
            },
            automatic_payment_methods={"enabled": True},
        )
        return jsonify({
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id,
            "amount": price["amount_cents"],
            "currency": "sgd",
            "label": price["label"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/api/shop/checkout", methods=["POST"])
def api_shop_checkout():
    """Create a Stripe Checkout Session for multi-item shop orders."""
    if not stripe.api_key:
        return jsonify({"error": "Stripe not configured"}), 500

    data = request.get_json(force=True) or {}
    items = data.get("items", [])

    if not items or not isinstance(items, list):
        return jsonify({"error": "Cart is empty"}), 400

    line_items = []
    for item in items:
        product_data = {"name": item.get("name", "Item")}
        desc = item.get("desc", "")
        if desc:
            product_data["description"] = desc
        line_items.append({
            "price_data": {
                "currency": "sgd",
                "product_data": product_data,
                "unit_amount": int(round(float(item.get("price", 0)) * 100)),
            },
            "quantity": int(item.get("qty", 1)),
        })

    try:
        session = stripe.checkout.Session.create(
            line_items=line_items,
            mode="payment",
            success_url="https://initium.sg/intm-shop.html?status=success",
            cancel_url="https://initium.sg/intm-shop.html?status=cancel",
            shipping_address_collection={"allowed_countries": ["SG"]},
        )
        return jsonify({"url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════════════════════
# TOUR API (3D Virtual Tours)
# ═══════════════════════════════════════════════════════════

@app.route("/api/tours", methods=["POST"])
@require_api_key
def api_create_tour():
    """Team member submits a new 3D tour for approval."""
    data = request.get_json(force=True) or {}
    url = data.get("url", "").strip()
    name = data.get("name", "").strip()
    district = data.get("district", "").strip()
    badge = data.get("badge", "3D Tour").strip()
    notes = data.get("notes", "").strip()

    if not url or not name:
        return jsonify({"error": "url and name are required"}), 400

    if not url.startswith(("http://", "https://")):
        return jsonify({"error": "url must start with http:// or https://"}), 400

    tours = _load_tours()
    tour = {
        "id": str(uuid.uuid4())[:8],
        "url": url,
        "embed_url": _build_embed_iframe(url),
        "platform": _detect_platform(url),
        "name": name,
        "district": district,
        "badge": badge,
        "notes": notes,
        "status": "pending",
        "submitted_by": request.api_key_entry.get("name", "unknown"),
        "api_key_prefix": request.headers.get("X-API-Key", "")[:12],
        "created_at": datetime.utcnow().isoformat() + "Z",
        "approved_at": None,
        "approved_by": None,
    }
    tours.insert(0, tour)
    _save_tours(tours)

    return jsonify({"tour": tour}), 201


@app.route("/api/tours", methods=["GET"])
@require_api_key
def api_list_tours():
    """List tours visible to this team member (all pending + their own + all approved)."""
    tours = _load_tours()
    user_key = request.headers.get("X-API-Key", "")
    user_name = request.api_key_entry.get("name", "")

    # Filter: everyone sees approved + their own submissions + pending (for transparency)
    visible = []
    for t in tours:
        if t.get("status") == "approved":
            visible.append(t)
        elif t.get("submitted_by") == user_name:
            visible.append(t)
        elif t.get("status") == "pending":
            visible.append(t)

    return jsonify({"tours": visible})


@app.route("/api/tours/public", methods=["GET"])
def api_public_tours():
    """Public endpoint: return only approved tours for embedding on virtual-tours.html."""
    tours = _load_tours()
    approved = [t for t in tours if t.get("status") == "approved"]
    return jsonify({"tours": approved})


@app.route("/api/tours/<tour_id>", methods=["DELETE"])
@require_api_key
def api_delete_tour(tour_id):
    """Allow submitter or admin to delete a tour."""
    tours = _load_tours()
    user_name = request.api_key_entry.get("name", "")
    user_key = request.headers.get("X-API-Key", "")

    idx = None
    for i, t in enumerate(tours):
        if t.get("id") == tour_id:
            idx = i
            break

    if idx is None:
        return jsonify({"error": "Tour not found"}), 404

    # Only submitter or admin can delete
    is_owner = tours[idx].get("submitted_by") == user_name
    is_admin = user_key == ADMIN_KEY
    if not (is_owner or is_admin):
        return jsonify({"error": "Not authorized"}), 403

    tours.pop(idx)
    _save_tours(tours)
    return jsonify({"message": "Tour deleted"})


@app.route("/admin/tours/<tour_id>/approve", methods=["POST"])
@require_admin_key
def admin_approve_tour(tour_id):
    tours = _load_tours()
    for t in tours:
        if t.get("id") == tour_id:
            t["status"] = "approved"
            t["approved_at"] = datetime.utcnow().isoformat() + "Z"
            t["approved_by"] = "admin"
            _save_tours(tours)
            return jsonify({"tour": t})
    return jsonify({"error": "Tour not found"}), 404


@app.route("/admin/tours/<tour_id>/reject", methods=["POST"])
@require_admin_key
def admin_reject_tour(tour_id):
    tours = _load_tours()
    for t in tours:
        if t.get("id") == tour_id:
            t["status"] = "rejected"
            _save_tours(tours)
            return jsonify({"tour": t})
    return jsonify({"error": "Tour not found"}), 404


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


def _send_telegram_notification(submission):
    """Send a Telegram message when a new enquiry comes in."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    enquiry_labels = {
        "buy": "Buy Property",
        "sell": "Sell Property",
        "rent": "Rent / Lease",
        "newlaunch": "New Launch",
        "join": "Join INITIUM",
        "general": "General Enquiry",
    }
    label = enquiry_labels.get(submission.get("enquiryType"), "Other")

    text = (
        f"🔔 <b>New INITIUM Enquiry</b>\n\n"
        f"<b>Name:</b> {submission.get('name', 'N/A')}\n"
        f"<b>Mobile:</b> {submission.get('mobile', 'N/A')}\n"
        f"<b>Email:</b> {submission.get('email', 'N/A')}\n"
        f"<b>Type:</b> {label}\n"
    )
    if submission.get("project"):
        text += f"<b>Project:</b> {submission['project']}\n"
    if submission.get("district"):
        text += f"<b>District:</b> {submission['district']}\n"
    if submission.get("message"):
        msg = submission["message"]
        if len(msg) > 200:
            msg = msg[:200] + "..."
        text += f"\n<b>Message:</b>\n{msg}\n"
    text += f"\n📅 {submission.get('timestamp', '')}"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass  # Fail silently so form submission still succeeds


# ═══════════════════════════════════════════════════════════
# CONTACT FORM
# ═══════════════════════════════════════════════════════════

@app.route("/api/contact", methods=["POST"])
def contact_submit():
    """Receive enquiry from the contact form."""
    data = request.get_json(silent=True) or {}
    
    required = ["name", "mobile", "email", "enquiryType"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
    
    submission = {
        "id": str(uuid.uuid4())[:8],
        "name": data.get("name", "").strip(),
        "mobile": data.get("mobile", "").strip(),
        "email": data.get("email", "").strip(),
        "enquiryType": data.get("enquiryType", ""),
        "district": data.get("district", "").strip(),
        "message": data.get("message", "").strip(),
        "project": data.get("project", "").strip(),  # Project of interest
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source": request.headers.get("Origin", "unknown"),
    }
    
    subs = _load_submissions()
    subs.insert(0, submission)
    _save_submissions(subs)
    
    _send_telegram_notification(submission)
    
    return jsonify({
        "success": True,
        "id": submission["id"],
        "message": "Enquiry received. We will reply within 2 hours."
    }), 201


@app.route("/admin/submissions", methods=["GET"])
@require_admin_key
def admin_list_submissions():
    """View all contact form submissions."""
    subs = _load_submissions()
    project = request.args.get("project", "").strip()
    if project:
        subs = [s for s in subs if project.lower() in (s.get("project") or "").lower()]
    return jsonify({
        "count": len(subs),
        "submissions": subs
    })


@app.route("/admin/submissions/stats", methods=["GET"])
@require_admin_key
def admin_submission_stats():
    """Summary stats of enquiries."""
    subs = _load_submissions()
    from collections import Counter
    by_type = Counter(s.get("enquiryType", "unknown") for s in subs)
    by_project = Counter(s.get("project", "General") for s in subs if s.get("project"))
    return jsonify({
        "total": len(subs),
        "by_type": dict(by_type),
        "by_project": dict(by_project.most_common(20)),
    })


# ═══════════════════════════════════════════════════════════
# VIDEO SERVING
# ═══════════════════════════════════════════════════════════

@app.route("/videos/<path:filename>")
def serve_video(filename):
    return send_from_directory(VIDEO_DIR, filename)


@app.route("/images/<path:filename>")
def serve_image(filename):
    return send_from_directory(IMAGE_DIR, filename)


# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"\n🚀 INITIUM Video Backend")
    print(f"   Admin key: {ADMIN_KEY[:20]}...")
    print(f"   Static folder: {app.static_folder}")
    print(f"   Listening on http://0.0.0.0:5000\n")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
