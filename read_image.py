import stat
from pathlib import Path
from typing import Annotated

from mistralai import agents
from pydantic import Field

from config import WORKSPACE_DIR

MAX_IMAGE_BYTES = 5 * 1024 * 1024
TEMP_ROOT = Path("/tmp")

_IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def _sniff_media_type(data: bytes) -> str | None:
    for signature, media_type in _IMAGE_SIGNATURES:
        if data.startswith(signature):
            return media_type
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _resolve_path(requested: str) -> Path:
    if not requested.strip():
        raise agents.ToolError("Path cannot be empty.")
    workspace = WORKSPACE_DIR.resolve()
    supplied = Path(requested)
    candidate = supplied if supplied.is_absolute() else workspace / supplied
    resolved = candidate.resolve()
    roots = [workspace]
    try:
        temp_root = TEMP_ROOT.resolve(strict=True)
    except OSError:
        temp_root = None
    if temp_root is not None:
        roots.append(temp_root)
    if not any(resolved == root or resolved.is_relative_to(root) for root in roots):
        raise agents.ToolError(f"Path is outside the workspace: {requested}")
    return resolved


@agents.tool(model_access="direct")
def read_image(path: Annotated[str, Field(description="Path to the image file, relative to the workspace or absolute.")]) -> list[agents.TextContentBlock | agents.ImageContentBlock]:
    """Read an image file and view it. Supports PNG, JPEG, WebP and GIF files up to 5 MB. Relative paths resolve against the workspace."""
    resolved = _resolve_path(path)
    try:
        status = resolved.stat()
    except FileNotFoundError:
        raise agents.ToolError(f"File not found: {path}") from None
    except OSError as error:
        raise agents.ToolError(f"Could not read {path}: {error}") from None
    if not stat.S_ISREG(status.st_mode):
        raise agents.ToolError(f"Path is not a regular file: {path}")
    if status.st_size > MAX_IMAGE_BYTES:
        raise agents.ToolError(f"Image is too large: {status.st_size} bytes (the limit is {MAX_IMAGE_BYTES} bytes).")
    try:
        data = resolved.read_bytes()
    except OSError as error:
        raise agents.ToolError(f"Could not read {path}: {error}") from None
    media_type = _sniff_media_type(data)
    if media_type is None:
        raise agents.ToolError(f"Not a supported image file (PNG, JPEG, WebP or GIF): {path}")
    return [
        agents.TextContentBlock(text=f"Image file: {resolved.name} ({media_type}, {status.st_size} bytes)"),
        agents.ImageContentBlock.from_bytes(data, media_type),
    ]


READ_IMAGE_TOOLS = [read_image]
