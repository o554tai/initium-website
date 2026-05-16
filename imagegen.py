#!/usr/bin/env python3
"""
fal.ai Image Generation Integration for INITIUM
Supports Flux Pro and Seedream V4 via fal.ai API.
"""

import os
import sys
import json
import time
import requests
from pathlib import Path

API_KEY = os.environ.get("FAL_API_KEY", "")
BASE_URL = "https://queue.fal.run"

HEADERS = lambda key: {
    "Content-Type": "application/json",
    "Authorization": f"Key {key}",
}

MODELS = {
    "flux-pro": "fal-ai/flux-pro/v1.1",
    "flux-ultra": "fal-ai/flux-pro/v1.1-ultra",
    "seedream-v4": "fal-ai/bytedance/seedream/v4/text-to-image",
}


def submit_image_task(model: str, prompt: str, ratio: str = "16:9", **kwargs) -> dict:
    """Submit an image generation task to fal.ai queue. Returns {request_id, response_url, status_url}."""
    if not API_KEY:
        raise RuntimeError("FAL_API_KEY not configured")

    endpoint = MODELS.get(model, MODELS["flux-pro"])
    url = f"{BASE_URL}/{endpoint}"

    # Map ratio to image_size
    size_map = {
        "16:9": {"width": 1344, "height": 768},
        "9:16": {"width": 768, "height": 1344},
        "1:1":  {"width": 1024, "height": 1024},
        "4:3":  {"width": 1024, "height": 768},
        "3:4":  {"width": 768, "height": 1024},
    }
    image_size = size_map.get(ratio, size_map["16:9"])

    payload = {
        "prompt": prompt,
        "image_size": image_size,
        "num_images": 1,
        "enable_safety_checker": kwargs.get("safety", True),
    }

    # Seedream uses slightly different param name
    if "seedream" in endpoint:
        payload["aspect_ratio"] = ratio
        del payload["image_size"]

    resp = requests.post(url, headers=HEADERS(API_KEY), json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def poll_image_result(status_url: str) -> dict:
    """Poll fal.ai queue for completed image."""
    if not API_KEY:
        raise RuntimeError("FAL_API_KEY not configured")

    resp = requests.get(status_url, headers=HEADERS(API_KEY), timeout=30)
    resp.raise_for_status()
    return resp.json()


def extract_image_url(result: dict) -> str:
    """Extract image URL from fal.ai response."""
    images = result.get("images", [])
    if images:
        return images[0].get("url", "")

    # Fallback shapes
    if "image" in result:
        return result["image"].get("url", "")
    if "url" in result:
        return result["url"]

    raise RuntimeError(f"No image URL in response: {json.dumps(result, indent=2)}")


def download_image(url: str, output_path: str):
    """Download image from URL to local file."""
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
