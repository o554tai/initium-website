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
# REPLICATE FACE-SWAP (character identity lock)
# ═══════════════════════════════════════════════════════════

REPLICATE_BASE_URL = "https://api.replicate.com/v1"

REPLICATE_HEADERS = lambda: {
    "Authorization": f"Token {os.environ.get('REPLICATE_API_TOKEN', '')}",
    "Content-Type": "application/json",
    "Prefer": "wait",
}


def _resolve_image_for_replicate(image: str) -> str:
    """Return a URL or base64 data URI that Replicate can fetch."""
    if image.startswith(("http://", "https://", "data:")):
        return image
    path = Path(image)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image}")
    # Convert local file to base64 data URI — Replicate models accept these
    ext = path.suffix.lower().replace(".", "")
    if ext == "jpg":
        ext = "jpeg"
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return f"data:image/{ext};base64,{data}"


def face_swap(
    source_face: str,
    target_image: str,
    model: str = "cdingram/face-swap",
) -> dict:
    """
    Swap `source_face` onto `target_image` using Replicate.

    Parameters:
        source_face:   Path/URL to the face image (mugshot)
        target_image:  Path/URL to the generated image (body/scene)
        model:         Replicate model identifier

    Returns:
        {"url": <result URL>, "provider": "replicate"}
    """
    if not os.environ.get("REPLICATE_API_TOKEN"):
        raise RuntimeError("REPLICATE_API_TOKEN not configured. Get one at replicate.com/account/api-tokens")

    source_url = _resolve_image_for_replicate(source_face)
    target_url = _resolve_image_for_replicate(target_image)

    payload = {
        "version": "d1d6ea8c8be89d664a07a457526f7128109dee7030fdac424788d762c71ed111",
        "input": {
            "input_image": target_url,
            "swap_image": source_url,
        },
    }

    resp = requests.post(
        f"{REPLICATE_BASE_URL}/predictions",
        headers=REPLICATE_HEADERS(),
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    prediction = resp.json()

    # Poll if not completed immediately
    pred_id = prediction.get("id")
    status = prediction.get("status")
    output_url = None

    while status in ("starting", "processing"):
        time.sleep(1)
        poll = requests.get(
            f"{REPLICATE_BASE_URL}/predictions/{pred_id}",
            headers={"Authorization": f"Token {os.environ.get('REPLICATE_API_TOKEN', '')}"},
            timeout=30,
        )
        poll.raise_for_status()
        data = poll.json()
        status = data.get("status")
        if status == "succeeded":
            output = data.get("output", "")
            if isinstance(output, list):
                output_url = output[0]
            else:
                output_url = output
            break
        elif status == "failed":
            raise RuntimeError(f"Replicate face-swap failed: {data.get('error', 'unknown')}")

    if not output_url:
        raise RuntimeError("Replicate face-swap did not return an image URL")

    return {"url": output_url, "provider": "replicate", "model": model}


def character_avatar(
    source_face: str,
    prompt: str,
    model: str = "seedream-4.5",
    ratio: str = "3:4",
    seed: int | None = None,
    quality: str = "hd",
    style: str = "natural",
    negative_prompt: str = "blurry, low quality, watermark, deformed face, extra limbs, different person",
    output_dir: str = "./output",
    filename: str = "",
) -> dict:
    """
    Full pipeline: mugshot → Seedream full-body → face-swap exact identity.

    Returns dict with keys:
        seedream_url, seedream_local, face_swap_url, face_swap_local, final_path
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    base_name = filename or f"avatar_{int(time.time())}"

    # Step 1 — Seedream img2img with mugshot as reference
    print(f"[1/3] Seedream generating full-body from prompt...")
    gen = generate_image_byteplus(
        prompt=prompt,
        model=model,
        ratio=ratio,
        images=source_face,
        negative_prompt=negative_prompt,
        seed=seed,
        quality=quality,
        style=style,
    )
    seedream_url = gen["url"]
    seedream_local = out / f"{base_name}_raw.png"
    download_image(seedream_url, str(seedream_local))
    print(f"  → Raw saved: {seedream_local}")

    # Step 2 — Face-swap exact identity (use original mugshot as source)
    print(f"[2/3] Replicate face-swap for exact identity lock...")
    swapped = face_swap(source_face=source_face, target_image=str(seedream_local))
    face_swap_url = swapped["url"]
    face_swap_local = out / f"{base_name}_final.png"
    download_image(face_swap_url, str(face_swap_local))
    print(f"  → Final saved: {face_swap_local}")

    return {
        "seedream_url": seedream_url,
        "seedream_local": str(seedream_local),
        "face_swap_url": face_swap_url,
        "face_swap_local": str(face_swap_local),
        "final_path": str(face_swap_local),
        "provider": "byteplus+replicate",
    }


def video_face_swap(
    source_face: str,
    target_video: str,
    model: str = "okaris/roop",
    output_dir: str = "./output",
    filename: str = "",
) -> dict:
    """
    Swap `source_face` onto `target_video` using Replicate video face-swap (raw HTTP API).
    Avoids the Python client's file-upload path which requires broader token scope.
    Parameters:
        source_face:   Path/URL to the face image (mugshot)
        target_video:  Path/URL to the generated video (Seedance output)
        model:         Replicate model identifier (default: okaris/roop)
        output_dir:    Where to save the result
        filename:      Base filename (without ext); defaults to timestamp
    Returns:
        {"url": <result URL>, "local_path": <saved path>, "provider": "replicate"}
    """
    import base64

    if not os.environ.get("REPLICATE_API_TOKEN"):
        raise RuntimeError("REPLICATE_API_TOKEN not configured. Get one at replicate.com/account/api-tokens")

    token = os.environ["REPLICATE_API_TOKEN"]
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json",
        "Prefer": "wait",
    }

    def _resolve_for_replicate(path_or_url: str, media_type: str = "image") -> str:
        if path_or_url.startswith(("http://", "https://", "data:")):
            return path_or_url
        p = Path(path_or_url)
        if not p.exists():
            raise FileNotFoundError(f"Not found: {path_or_url}")
        ext = p.suffix.lower().replace(".", "")
        if ext == "jpg":
            ext = "jpeg"
        with open(p, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return f"data:{media_type}/{ext};base64,{data}"

    source_url = _resolve_for_replicate(source_face, media_type="image")
    target_url = _resolve_for_replicate(target_video, media_type="video")

    print(f"[Replicate] Starting video face-swap with {model}...")
    print(f"  Source face: {source_face}")
    print(f"  Target video: {target_video}")

    payload = {
        "input": {
            "source": source_url,
            "target": target_url,
        },
    }

    resp = requests.post(
        f"{REPLICATE_BASE_URL}/models/{model}/predictions",
        headers=headers,
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    prediction = resp.json()

    # Poll
    pred_id = prediction.get("id")
    status = prediction.get("status")
    output_url = None
    max_polls = 60
    polls = 0

    while polls < max_polls:
        if status == "succeeded" and prediction.get("output"):
            output = prediction["output"]
            output_url = output[0] if isinstance(output, list) else output
            break
        if status == "failed":
            raise RuntimeError(f"Replicate face-swap failed: {prediction.get('error', 'unknown')}")

        time.sleep(2)
        polls += 1
        poll = requests.get(
            f"{REPLICATE_BASE_URL}/predictions/{pred_id}",
            headers={"Authorization": f"Token {token}"},
            timeout=30,
        )
        poll.raise_for_status()
        prediction = poll.json()
        status = prediction.get("status")

    if not output_url:
        raise RuntimeError("Replicate face-swap did not return a video URL")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    base_name = filename or f"face_swap_{int(time.time())}"
    local_path = out / f"{base_name}.mp4"

    print(f"[Replicate] Downloading result...")
    download_image(output_url, str(local_path))
    print(f"  → Saved: {local_path}")

    return {
        "url": output_url,
        "local_path": str(local_path),
        "provider": "replicate",
        "model": model,
    }


def character_video(
    source_face: str,
    prompt: str,
    ratio: str = "9:16",
    duration: int = 5,
    output_dir: str = "./output",
    filename: str = "",
) -> dict:
    """
    Full video pipeline: text-only Seedance → Replicate video face-swap.
    Steps:
        1. Generate video via Seedance (text-only, no face ref to avoid filter)
        2. Face-swap the exact mugshot onto the video via Replicate
    Returns dict with keys:
        seedance_url, seedance_local, face_swap_url, face_swap_local, final_path
    """
    from seedance import (
        build_text_only_payload,
        submit_task,
        wait_for_completion,
        extract_video_url,
        download_video,
    )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    base_name = filename or f"char_vid_{int(time.time())}"

    print(f"[1/2] Seedance text-to-video: {prompt[:60]}...")
    payload = build_text_only_payload(
        prompt=prompt,
        ratio=ratio,
        duration=duration,
        generate_audio=False,
    )
    task_id = submit_task(payload)
    status = wait_for_completion(task_id)
    seedance_url = extract_video_url(status)
    seedance_local = out / f"{base_name}_raw.mp4"
    download_video(seedance_url, str(seedance_local))
    print(f"  → Raw video saved: {seedance_local}")

    print(f"[2/2] Replicate video face-swap...")
    swapped = video_face_swap(
        source_face=source_face,
        target_video=str(seedance_local),
        output_dir=output_dir,
        filename=base_name,
    )
    face_swap_local = swapped["local_path"]
    print(f"  → Final video saved: {face_swap_local}")

    return {
        "seedance_url": seedance_url,
        "seedance_local": str(seedance_local),
        "face_swap_url": swapped["url"],
        "face_swap_local": str(face_swap_local),
        "final_path": str(face_swap_local),
        "provider": "byteplus+replicate",
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

    parser = argparse.ArgumentParser(description="Generate images with Seedream + optional face-swap")
    parser.add_argument("prompt", nargs="?", default="", help="Text prompt")
    parser.add_argument("-o", "--output", default="output.png", help="Output file path")
    parser.add_argument("--model", default="seedream-4.5", choices=list(BP_MODELS.keys()))
    parser.add_argument("--ratio", default="16:9", choices=list(BP_SIZE_MAP.keys()))
    parser.add_argument("--image", help="Reference image path or URL (img2img)")
    parser.add_argument("--negative", default="", help="Negative prompt")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--quality", default="", choices=["", "standard", "hd"])
    parser.add_argument("--style", default="", choices=["", "natural", "vivid"])
    parser.add_argument("--b64", action="store_true", help="Return base64 instead of URL")

    # Face-swap / character avatar flags
    parser.add_argument("--face-swap", metavar="SOURCE_FACE", help="After generation, swap SOURCE_FACE onto the result (Replicate)")
    parser.add_argument("--character-avatar", metavar="SOURCE_FACE", help="Full pipeline: mugshot → Seedream full-body → face-swap exact identity")
    parser.add_argument("--output-dir", default="./output", help="Directory for character_avatar outputs")

    # Video face-swap / character video flags
    parser.add_argument("--video-face-swap", metavar="SOURCE_FACE", help="Swap SOURCE_FACE onto a target video (provide --target-video)")
    parser.add_argument("--target-video", help="Target video path/URL for --video-face-swap")
    parser.add_argument("--character-video", metavar="SOURCE_FACE", help="Full pipeline: text → Seedance video → face-swap exact identity")
    parser.add_argument("--duration", type=int, default=5, help="Video duration in seconds (for --character-video)")

    args = parser.parse_args()

    try:
        # Video face-swap only
        if args.video_face_swap:
            if not args.target_video:
                print("Error: --video-face-swap requires --target-video")
                sys.exit(1)
            result = video_face_swap(
                source_face=args.video_face_swap,
                target_video=args.target_video,
                output_dir=args.output_dir,
                filename=Path(args.output).stem,
            )
            print(f"\n✓ Face-swapped video: {result['local_path']}")
            sys.exit(0)

        # Character video full pipeline
        if args.character_video:
            if not args.prompt:
                print("Error: --character-video requires a prompt")
                sys.exit(1)
            result = character_video(
                source_face=args.character_video,
                prompt=args.prompt,
                ratio=args.ratio,
                duration=args.duration,
                output_dir=args.output_dir,
                filename=Path(args.output).stem,
            )
            print(f"\n✓ Final video: {result['final_path']}")
            sys.exit(0)

        # Character avatar full pipeline
        if args.character_avatar:
            if not args.prompt:
                print("Error: --character-avatar requires a prompt")
                sys.exit(1)
            result = character_avatar(
                source_face=args.character_avatar,
                prompt=args.prompt,
                model=args.model,
                ratio=args.ratio,
                seed=args.seed,
                quality=args.quality or "hd",
                style=args.style or "natural",
                negative_prompt=args.negative or "blurry, low quality, watermark, deformed face, extra limbs, different person",
                output_dir=args.output_dir,
                filename=Path(args.output).stem,
            )
            print(f"\n✓ Final avatar: {result['final_path']}")
            sys.exit(0)

        # Standard generation
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
                sys.exit(1)
        else:
            url = result["url"]
            print(f"Image URL: {url}")
            download_image(url, args.output)
            print(f"Downloaded to {args.output}")

            # Optional post-process face-swap
            if args.face_swap:
                print(f"\nRunning face-swap with {args.face_swap}...")
                swapped = face_swap(source_face=args.face_swap, target_image=args.output)
                swap_path = str(Path(args.output).with_suffix("")) + "_swapped.png"
                download_image(swapped["url"], swap_path)
                print(f"Face-swapped image: {swap_path}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
