#!/usr/bin/env python3
"""
Image Generation for INITIUM Studio
Primary: BytePlus ModelArk Seedream (direct)
Fallback: fal.ai (Flux Pro, Seedream V4)
"""

import os
import sys
import json
import time
import requests
from pathlib import Path

# ═══════════════════════════════════════════════════════════
# BYTEPLUS DIRECT (primary)
# ═══════════════════════════════════════════════════════════

BP_API_KEY = os.environ.get("SEEDANCE_API_KEY", "ark-3c1f1e49-47ce-4e5d-9a58-df85f5b52e3e-2ce11")
BP_BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"

BP_MODELS = {
    "seedream-4.5": "seedream-4-5-251128",
    "seedream-4.0": "seedream-4-0-250828",
}

# BytePlus requires min 3,686,400 pixels
BP_SIZE_MAP = {
    "1:1":  "2048x2048",
    "16:9": "2560x1440",
    "9:16": "1440x2560",
    "4:3":  "2304x1728",
    "3:4":  "1728x2304",
}

BP_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {BP_API_KEY}",
}


def generate_image_byteplus(prompt: str, model: str = "seedream-4.5", ratio: str = "16:9") -> dict:
    """Generate image via BytePlus Seedream. Synchronous — returns image URL immediately."""
    model_id = BP_MODELS.get(model, BP_MODELS["seedream-4.5"])
    size = BP_SIZE_MAP.get(ratio, BP_SIZE_MAP["16:9"])

    payload = {
        "model": model_id,
        "prompt": prompt,
        "size": size,
    }

    resp = requests.post(
        f"{BP_BASE_URL}/images/generations",
        headers=BP_HEADERS,
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    image_url = data.get("data", [{}])[0].get("url", "")
    if not image_url:
        raise RuntimeError(f"No image URL in BytePlus response: {json.dumps(data)}")

    return {
        "url": image_url,
        "size": data.get("data", [{}])[0].get("size", ""),
        "model": model,
        "provider": "byteplus",
    }


# ═══════════════════════════════════════════════════════════
# FAL.AI FALLBACK
# ═══════════════════════════════════════════════════════════

FAL_API_KEY = os.environ.get("FAL_API_KEY", "")
FAL_BASE_URL = "https://queue.fal.run"

FAL_MODELS = {
    "flux-pro": "fal-ai/flux-pro/v1.1",
    "flux-ultra": "fal-ai/flux-pro/v1.1-ultra",
    "seedream-v4": "fal-ai/bytedance/seedream/v4/text-to-image",
}

FAL_HEADERS = lambda key: {
    "Content-Type": "application/json",
    "Authorization": f"Key {key}",
}


def submit_image_task_fal(model: str, prompt: str, ratio: str = "16:9", **kwargs) -> dict:
    """Submit an image generation task to fal.ai queue. Returns {request_id, response_url, status_url}."""
    if not FAL_API_KEY:
        raise RuntimeError("FAL_API_KEY not configured")

    endpoint = FAL_MODELS.get(model, FAL_MODELS["flux-pro"])
    url = f"{FAL_BASE_URL}/{endpoint}"

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

    if "seedream" in endpoint:
        payload["aspect_ratio"] = ratio
        del payload["image_size"]

    resp = requests.post(url, headers=FAL_HEADERS(FAL_API_KEY), json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def poll_image_result_fal(status_url: str) -> dict:
    """Poll fal.ai queue for completed image."""
    if not FAL_API_KEY:
        raise RuntimeError("FAL_API_KEY not configured")

    resp = requests.get(status_url, headers=FAL_HEADERS(FAL_API_KEY), timeout=30)
    resp.raise_for_status()
    return resp.json()


def extract_image_url_fal(result: dict) -> str:
    """Extract image URL from fal.ai response."""
    images = result.get("images", [])
    if images:
        return images[0].get("url", "")
    if "image" in result:
        return result["image"].get("url", "")
    if "url" in result:
        return result["url"]
    raise RuntimeError(f"No image URL in fal.ai response: {json.dumps(result, indent=2)}")


# ═══════════════════════════════════════════════════════════
# UNIFIED INTERFACE
# ═══════════════════════════════════════════════════════════

ALL_MODELS = {
    "seedream-4.5": {"provider": "byteplus", "name": "Seedream 4.5 (BytePlus)"},
    "seedream-4.0": {"provider": "byteplus", "name": "Seedream 4.0 (BytePlus)"},
    "flux-pro":     {"provider": "fal",      "name": "Flux Pro (fal.ai)"},
    "flux-ultra":   {"provider": "fal",      "name": "Flux Ultra (fal.ai)"},
    "seedream-v4":  {"provider": "fal",      "name": "Seedream V4 (fal.ai)"},
}


def generate_image(model: str, prompt: str, ratio: str = "16:9", **kwargs) -> dict:
    """Unified image generation. Tries BytePlus first, falls back to fal.ai."""
    meta = ALL_MODELS.get(model, ALL_MODELS["seedream-4.5"])

    if meta["provider"] == "byteplus":
        return generate_image_byteplus(prompt, model=model, ratio=ratio)

    # fal.ai async path
    result = submit_image_task_fal(model, prompt, ratio=ratio, **kwargs)
    return {
        "request_id": result.get("request_id", ""),
        "status_url": result.get("status_url", ""),
        "provider": "fal",
    }


def download_image(url: str, output_path: str):
    """Download image from URL to local file."""
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
