import base64
import json
import os
import sys
import zlib
import struct
from pathlib import Path

import httpx

BOT_DIR = Path(__file__).resolve().parent / ".bot"
CACHE_PATH = BOT_DIR / "cache.json"
PROBE_TIMEOUT_SECONDS = 10.0


def _probe_png() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\x00\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def _probe_data_uri() -> str:
    return "data:image/png;base64," + base64.b64encode(_probe_png()).decode("ascii")


def _load_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    try:
        CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")
    except OSError:
        pass


def detect_input_modalities(base_url: str, model: str, api_key_env_var: str) -> list[str]:
    key = f"{base_url.rstrip('/')}|{model}"
    cache = _load_cache()
    cached = cache.get(key)
    if cached in (["text"], ["text", "image"]):
        return cached
    api_key = os.environ.get(api_key_env_var, "").strip()
    if not api_key:
        return ["text"]
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Reply with: ok"},
                    {"type": "image_url", "image_url": {"url": _probe_data_uri()}},
                ],
            }
        ],
        "max_tokens": 1,
        "stream": False,
    }
    try:
        with httpx.Client(base_url=base_url.rstrip("/"), timeout=PROBE_TIMEOUT_SECONDS) as client:
            response = client.post("/chat/completions", json=payload, headers={"Authorization": f"Bearer {api_key}"})
    except Exception as error:
        print(f"warning: could not probe {model} for image support ({error}); assuming text-only", file=sys.stderr)
        return ["text"]
    if response.status_code == 200:
        modalities = ["text", "image"]
    else:
        if response.status_code != 400:
            print(f"warning: image-support probe for {model} returned HTTP {response.status_code}; assuming text-only", file=sys.stderr)
        modalities = ["text"]
    cache[key] = modalities
    _save_cache(cache)
    return modalities
