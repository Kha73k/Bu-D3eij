"""Format model, shared helpers, and the ConversionError type for Bu D3eij.

Pure, GUI-free logic — importable and testable without launching the app.
"""
from __future__ import annotations

from pathlib import Path


# --------------------------------------------------------------------------- #
# Format model
# --------------------------------------------------------------------------- #
IMAGE_EXTS = {"jpg", "jpeg", "png", "webp", "bmp", "gif", "tiff", "tif"}
DOC_EXTS = {"pdf", "docx", "txt", "md"}
PRESENTATION_EXTS = {"pptx"}
AV_EXTS = {"mp4", "mp3", "wav"}

# input extension -> list of compatible target extensions
CONVERSIONS: dict[str, list[str]] = {
    "pdf": ["docx", "txt", "md"],
    "docx": ["pdf", "txt", "md"],
    "txt": ["pdf", "docx", "md"],
    "pptx": ["pdf", "txt", "md"],
    "jpg": ["png", "webp", "bmp", "gif", "tiff"],
    "jpeg": ["png", "webp", "bmp", "gif", "tiff"],
    "png": ["jpg", "webp", "bmp", "gif", "tiff"],
    "webp": ["png", "jpg", "bmp", "gif", "tiff"],
    "bmp": ["png", "jpg", "webp", "gif", "tiff"],
    "gif": ["png", "jpg", "webp", "bmp", "tiff"],
    "tiff": ["png", "jpg", "webp", "bmp", "gif"],
    "tif": ["png", "jpg", "webp", "bmp", "gif", "tiff"],  # alias of tiff
    "mp4": ["mp3", "wav"],
    "mp3": ["wav"],
    "wav": ["mp3"],
}

# extension -> Pillow format name
PILLOW_FORMAT = {
    "jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP",
    "bmp": "BMP", "gif": "GIF", "tiff": "TIFF", "tif": "TIFF",
}


class ConversionError(Exception):
    """Raised when a conversion cannot be completed."""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def detect_format(path) -> str:
    """Return the lower-case extension (without dot) of a path."""
    return Path(path).suffix.lower().lstrip(".")


def compatible_targets(src_ext: str) -> list[str]:
    """Return the list of formats `src_ext` can be converted to."""
    return CONVERSIONS.get(src_ext.lower().lstrip("."), [])


def unique_path(path: Path) -> Path:
    """Return a non-existing path by appending ' (n)' before the suffix."""
    if not path.exists():
        return path
    stem, suffix, parent = path.stem, path.suffix, path.parent
    n = 1
    while True:
        candidate = parent / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def human_size(num: float) -> str:
    """Human-readable file size, e.g. '1.4 MB'."""
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{int(num)} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} GB"


def category_of(ext: str) -> str:
    """Human label for a file extension's category."""
    ext = ext.lower().lstrip(".")
    if ext in IMAGE_EXTS:
        return "Image"
    if ext in PRESENTATION_EXTS:
        return "Presentation"
    if ext in DOC_EXTS:
        return "Document"
    if ext in AV_EXTS:
        return "Audio / Video"
    return "File"
