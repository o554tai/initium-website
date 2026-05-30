#!/usr/bin/env python3
"""
Image Generation for INITIUM Studio
Primary: BytePlus ModelArk Seedream 4.0/4.5 (direct)
Fallback: fal.ai (Flux Pro, Seedream V4)

Features:
- text-to-image, img2img, face/character reference
- negative_prompt, seed, quality, style
- base64 local file input, multiple reference images
"""

import os
import sys
import json
import time
import base64
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


def _encode_image_to_base64(image_path_or_url: str) -> str:
    """Convert a local image path to base64 data URI, or return URL as-is."""
    if image_path_or_url.startswith(("http://", "https://", "data:")):
        return image_path_or_url
    path = Path(image_path_or_url)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path_or_url}")
    ext = path.suffix.lower().replace(".", "")
    if ext == "jpg":
        ext = "jpeg"
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return f"data:image/{ext};base64,{data}"


def _resolve_images(images) -> list:
    """Normalize images input to a list of base64/URL strings."""
    if images is None:
        return []
    if isinstance(images, str):
        images = [images]
    return [_encode_image_to_base64(img) for img in images]


def generate_image_byteplus(
    prompt: str,
    model: str = "seedream-4.5",
    ratio: str = "16:9",
    images=None,
    negative_prompt: str = "",
    seed: int | None = None,
    quality: str = "",
    style: str = "",
    response_format: str = "",
    **extra
) -> dict:
    """
    Generate image via BytePlus Seedream.
    Synchronous — returns image URL or base64 immediately.

    Parameters:
        prompt:            Text prompt
        model:             "seedream-4.5" or "seedream-4.0"
        ratio:             "1:1", "16:9", "9:16", "4:3", "3:4"
        images:            Single path/URL or list — for img2img / character ref
        negative_prompt:   What to avoid
        seed:              Reproducibility seed (int)
        quality:           "standard" or "hd"
        style:             "natural" or "vivid"
        response_format:   "url" (default) or "b64_json"
    """
    model_id = BP_MODELS.get(model, BP_MODELS["seedream-4.5"])
    size = BP_SIZE_MAP.get(ratio, BP_SIZE_MAP["16:9"])

    payload = {
        "model": model_id,
        "prompt": prompt,
        "size": size,
    }

    # img2img / reference images
    img_list = _resolve_images(images)
    if img_list:
        if len(img_list) == 1:
            payload["image"] = img_list[0]
        else:
            payload["image"] = img_list  # type: ignore[assignment]

    # Optional params
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt
    if seed is not None:
        payload["seed"] = seed  # type: ignore[assignment]
    if quality:
        payload["quality"] = quality
    if style:
        payload["style"] = style
    if response_format:
        payload["response_format"] = response_format

    # Merge any extra API params
    payload.update(extra)

    resp = requests.post(
        f"{BP_BASE_URL}/images/generations",
        headers=BP_HEADERS,
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise RuntimeError(f"BytePlus API error: {data['error']}")

    result = data.get("data", [{}])[0]

    output = {
        "model": model,
        "provider": "byteplus",
        "size": result.get("size", ""),
    }

    if response_format == "b64_json":
        output["b64_json"] = result.get("b64_json", "")
    else:
        url = result.get("url", "")
        if not url:
            raise RuntimeError(f"No image URL in BytePlus response: {json.dumps(data)}")
        output["url"] = url

    return output


# ═══════════════════════════════════════════════════════════
# HIGH-LEVEL HELPERS
# ═══════════════════════════════════════════════════════════

def img2img_transform(
    image: str,
    prompt: str,
    model: str = "seedream-4.5",
    ratio: str = "16:9",
    negative_prompt: str = "blurry, low quality, watermark, deformed face, extra limbs",
    seed: int | None = None,
    quality: str = "hd",
    style: str = "natural",
    **kwargs
) -> dict:
    """Transform an existing image (style transfer, relighting, etc.)."""
    return generate_image_byteplus(
        prompt=prompt,
        model=model,
        ratio=ratio,
        images=image,
        negative_prompt=negative_prompt,
        seed=seed,
        quality=quality,
        style=style,
        **kwargs
    )


def generate_character_variations(
    character_image: str,
    scenes: list,
    model: str = "seedream-4.5",
    ratio: str = "3:4",
    negative_prompt: str = "blurry, low quality, watermark, deformed face, extra limbs, different person",
    seed: int | None = None,
    quality: str = "hd",
    style: str = "natural",
    output_dir: str = "./output",
) -> list:
    """
    Generate multiple scenes using the same character reference image.
    Returns list of result dicts with local file paths.
    """
    results = []
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for i, scene in enumerate(scenes):
        print(f"[{i+1}/{len(scenes)}] Generating: {scene[:60]}...")
        try:
            result = generate_image_byteplus(
                prompt=scene,
                model=model,
                ratio=ratio,
                images=character_image,
                negative_prompt=negative_prompt,
                seed=(seed + i) if seed else None,
                quality=quality,
                style=style,
            )
            filename = f"variation_{i+1:03d}.png"
            local_path = out / filename
            download_image(result["url"], str(local_path))
            result["local_path"] = str(local_path)
            results.append(result)
        except Exception as e:
            print(f"  FAILED: {e}")
            results.append({"error": str(e), "scene": scene})

    return results


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
        return generate_image_byteplus(prompt, model=model, ratio=ratio, **kwargs)

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


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate images with Seedream")
    parser.add_argument("prompt", help="Text prompt")
    parser.add_argument("-o", "--output", default="output.png", help="Output file path")
    parser.add_argument("--model", default="seedream-4.5", choices=list(BP_MODELS.keys()))
    parser.add_argument("--ratio", default="16:9", choices=list(BP_SIZE_MAP.keys()))
    parser.add_argument("--image", help="Reference image path or URL (img2img)")
    parser.add_argument("--negative", default="", help="Negative prompt")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--quality", default="", choices=["", "standard", "hd"])
    parser.add_argument("--style", default="", choices=["", "natural", "vivid"])
    parser.add_argument("--b64", action="store_true", help="Return base64 instead of URL")

    args = parser.parse_args()

    try:
        result = generate_image_byteplus(
            prompt=args.prompt,
            model=args.model,
            ratio=args.ratio,
            images=args.image,
            negative_prompt=args.negative,
            seed=args.seed,
            quality=args.quality,
            style=args.style,
            response_format="b64_json" if args.b64 else "url",
        )

        if args.b64:
            b64 = result.get("b64_json", "")
            if b64:
                data = base64.b64decode(b64)
                Path(args.output).parent.mkdir(parents=True, exist_ok=True)
                with open(args.output, "wb") as f:
                    f.write(data)
                print(f"Saved base64 image to {args.output}")
            else:
                print("No base64 data returned")
        else:
            url = result["url"]
            print(f"Image URL: {url}")
            download_image(url, args.output)
            print(f"Downloaded to {args.output}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
