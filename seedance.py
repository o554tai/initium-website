#!/usr/bin/env python3
"""
BytePlus ModelArk Seedance 2.0 Integration
Submit video generation tasks and poll for results.
"""

import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path

# ═══════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════

API_KEY = os.environ.get("SEEDANCE_API_KEY", "ark-3c1f1e49-47ce-4e5d-9a58-df85f5b52e3e-2ce11")
MODEL_ID = "dreamina-seedance-2-0-260128"
BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations"
POLL_INTERVAL = 10  # seconds between status checks
MAX_POLL_TIME = 600  # max 10 minutes

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}",
}


# ═══════════════════════════════════════════════════════════
# CORE FUNCTIONS
# ═══════════════════════════════════════════════════════════

def submit_task(payload: dict) -> str:
    """Submit a generation task. Returns task ID."""
    url = f"{BASE_URL}/tasks"
    resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if "id" not in data:
        raise RuntimeError(f"Unexpected response: {data}")

    return data["id"]


def get_task_status(task_id: str) -> dict:
    """Poll task status. Returns full response dict."""
    url = f"{BASE_URL}/tasks/{task_id}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def wait_for_completion(task_id: str, verbose: bool = True) -> dict:
    """Poll until task completes, fails, or times out."""
    start = time.time()

    while True:
        status = get_task_status(task_id)
        state = status.get("status", "unknown")

        if verbose:
            print(f"  [{int(time.time() - start)}s] Status: {state}")

        if state in ("completed", "succeeded", "success"):
            if verbose:
                print(f"\n✅ Task completed!")
            return status

        if state in ("failed", "error", "cancelled"):
            err = status.get("error", {})
            msg = err.get("message", "Unknown error")
            code = err.get("code", "N/A")
            raise RuntimeError(f"Task failed [{code}]: {msg}")

        if time.time() - start > MAX_POLL_TIME:
            raise TimeoutError(f"Task did not complete within {MAX_POLL_TIME}s")

        time.sleep(POLL_INTERVAL)


def download_video(url: str, output_path: str):
    """Download video from URL to local file."""
    print(f"\n⬇️  Downloading video...")
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"✅ Saved to: {output_path}")


def extract_video_url(status: dict) -> str:
    """Extract video URL from completed task response."""
    # Text-only responses return content as a dict: {"content": {"video_url": "..."}}
    # Multimodal responses return content as a list:
    #   [{"type": "video_url", "video_url": {"url": "..."}}]
    content = status.get("content")

    if isinstance(content, dict):
        if "video_url" in content:
            return content["video_url"]

    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "video_url":
                return item["video_url"]["url"]

    if "video_url" in status:
        return status["video_url"]

    if "url" in status:
        return status["url"]

    if "data" in status and "url" in status["data"]:
        return status["data"]["url"]

    raise RuntimeError(f"Could not find video URL in response: {json.dumps(status, indent=2)}")


# ═══════════════════════════════════════════════════════════
# PAYLOAD BUILDERS
# ═══════════════════════════════════════════════════════════

def build_text_only_payload(prompt: str, ratio: str = "16:9", duration: int = 5, **kwargs) -> dict:
    """Build a text-to-video payload."""
    return {
        "model": MODEL_ID,
        "content": [{"type": "text", "text": prompt}],
        "ratio": ratio,
        "duration": duration,
        "generate_audio": kwargs.get("generate_audio", True),
        "watermark": kwargs.get("watermark", False),
    }


def build_multimodal_payload(
    prompt: str,
    images: list = None,
    video: str = None,
    audio: str = None,
    ratio: str = "16:9",
    duration: int = 5,
    **kwargs
) -> dict:
    """Build a multimodal payload with images/video/audio references."""
    content = [{"type": "text", "text": prompt}]

    for img_url in (images or []):
        content.append({
            "type": "image_url",
            "image_url": {"url": img_url},
            "role": "reference_image"
        })

    if video:
        content.append({
            "type": "video_url",
            "video_url": {"url": video},
            "role": "reference_video"
        })

    if audio:
        content.append({
            "type": "audio_url",
            "audio_url": {"url": audio},
            "role": "reference_audio"
        })

    return {
        "model": MODEL_ID,
        "content": content,
        "ratio": ratio,
        "duration": duration,
        "generate_audio": kwargs.get("generate_audio", True),
        "watermark": kwargs.get("watermark", False),
    }


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Generate AI videos with BytePlus Seedance 2.0")
    parser.add_argument("prompt", help="Text prompt for video generation")
    parser.add_argument("-o", "--output", default="output.mp4", help="Output file path")
    parser.add_argument("--ratio", default="16:9", choices=["16:9", "9:16", "1:1"], help="Aspect ratio")
    parser.add_argument("--duration", type=int, default=5, help="Duration in seconds (max 11)")
    parser.add_argument("--image", action="append", help="Reference image URL (can use multiple)")
    parser.add_argument("--video", help="Reference video URL")
    parser.add_argument("--audio", help="Reference audio URL")
    parser.add_argument("--no-audio", action="store_true", help="Disable generated audio")
    parser.add_argument("--watermark", action="store_true", help="Add watermark")
    parser.add_argument("--submit-only", action="store_true", help="Only submit, don't poll")
    parser.add_argument("--task-id", help="Poll existing task ID instead of submitting")

    args = parser.parse_args()

    try:
        # ── Mode 1: Poll existing task ──
        if args.task_id:
            print(f"Polling task: {args.task_id}")
            status = wait_for_completion(args.task_id)
            video_url = extract_video_url(status)
            download_video(video_url, args.output)
            return

        # ── Mode 2: Submit new task ──
        kwargs = {
            "generate_audio": not args.no_audio,
            "watermark": args.watermark,
        }

        if args.image or args.video or args.audio:
            payload = build_multimodal_payload(
                args.prompt,
                images=args.image,
                video=args.video,
                audio=args.audio,
                ratio=args.ratio,
                duration=args.duration,
                **kwargs
            )
        else:
            payload = build_text_only_payload(
                args.prompt,
                ratio=args.ratio,
                duration=args.duration,
                **kwargs
            )

        print(f"Submitting task...")
        print(f"  Prompt: {args.prompt[:80]}...")
        print(f"  Ratio: {args.ratio} | Duration: {args.duration}s")

        task_id = submit_task(payload)
        print(f"✅ Task submitted: {task_id}")

        if args.submit_only:
            print(f"\nTask ID: {task_id}")
            print(f"Poll later with: python seedance.py --task-id {task_id} -o {args.output}")
            return

        # ── Poll and download ──
        status = wait_for_completion(task_id)
        video_url = extract_video_url(status)
        download_video(video_url, args.output)

        print(f"\n🎬 Done! Video saved to: {args.output}")

    except requests.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        try:
            print(json.dumps(e.response.json(), indent=2))
        except:
            print(e.response.text[:500])
        sys.exit(1)

    except RuntimeError as e:
        print(f"\n❌ {e}")
        sys.exit(1)

    except KeyboardInterrupt:
        print(f"\n\n⏹️  Interrupted by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
