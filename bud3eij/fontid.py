"""Font identification from images (Storia font-classify) for Bu D3eij — a Vanguard tool.

Classifies the lettering in an image against ~3,500 Google Fonts using the
open `storia/font-classify-onnx` model (EfficientNet-B3, MIT) on the
already-bundled `onnxruntime` — no PyTorch. Results are *closest matches*:
commercial fonts (Helvetica, …) are reported as their nearest Google
equivalent, never an exact ID. The model + config download once to
`~/.bud3eij/models/fontid/` and are cached thereafter, like the upscaler
models (SHA-256-verified, 30 s socket timeout).
"""
from __future__ import annotations

import re
import shutil
import sys
import urllib.request
from pathlib import Path

from .formats import ConversionError, IMAGE_EXTS

MODEL_NAME = "storia/font-classify-onnx (EfficientNet-B3, ~3,500 Google Fonts)"

_MODEL_DIR = Path.home() / ".bud3eij" / "models" / "fontid"
_BASE_URL = "https://huggingface.co/storia/font-classify-onnx/resolve/main/"
# filename -> (sha256, minimum sane size in bytes)
FONTID_FILES: dict[str, tuple[str, int]] = {
    "model.onnx": (
        "44aa3d46804aa55b7841a0eb6dcc9bb72badd6d01645e5c7448a70525655b7b6",
        64_057_660,  # exact size: a truncated download must NOT pass the cache check
    ),
    "model_config.yaml": (
        "eb33dd3ed758879cf555923ae1c5af08f067995eee4ebd54d269cfb4ed905f79",
        70_000,
    ),
}

# ImageNet normalisation (the model was trained on timm defaults).
_MEAN = (0.485, 0.456, 0.406)
_STD = (0.229, 0.224, 0.225)
_MAX_SIDE = 1024        # huge inputs are cropped to this before the model fit
                        # (CutMax in the upstream pipeline: crop, not resize)
_DOWNLOAD_TIMEOUT = 30  # socket timeout (s): a stalled download fails, not hangs

_SESSION = None         # onnxruntime session (loaded once)
_CONFIG: dict | None = None  # parsed model_config.yaml (classnames, input size)


def unload_models() -> None:
    """Drop the cached classifier session so its memory can be reclaimed."""
    global _SESSION, _CONFIG
    _SESSION = None
    _CONFIG = None


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _ensure_file(filename: str) -> Path:
    """Return the local path for a model file, downloading + caching on first use."""
    sha256, min_size = FONTID_FILES[filename]
    # Allow a bundled copy (frozen exe) to satisfy the requirement offline.
    base = getattr(sys, "_MEIPASS", None)
    if base:
        bundled = Path(base) / "bud3eij" / "models" / "fontid" / filename
        if bundled.exists():
            return bundled
    dest = _MODEL_DIR / filename
    if dest.exists() and dest.stat().st_size >= min_size:
        return dest
    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with urllib.request.urlopen(_BASE_URL + filename,
                                    timeout=_DOWNLOAD_TIMEOUT) as resp, \
                open(tmp, "wb") as fh:  # noqa: S310 - pinned HTTPS URL
            shutil.copyfileobj(resp, fh)
    except Exception as exc:  # noqa: BLE001
        tmp.unlink(missing_ok=True)
        raise ConversionError(f"Could not download the font model: {exc}") from exc
    if _sha256(tmp) != sha256:
        tmp.unlink(missing_ok=True)
        raise ConversionError(
            "Downloaded font model failed its integrity check (hash mismatch).")
    tmp.replace(dest)
    return dest


def _config() -> dict:
    global _CONFIG
    if _CONFIG is None:
        import yaml  # lazy (PyYAML, already a runtime dep)

        with open(_ensure_file("model_config.yaml"), encoding="utf-8") as fh:
            _CONFIG = yaml.safe_load(fh)
    return _CONFIG


def _session():
    global _SESSION
    if _SESSION is None:
        import onnxruntime as ort  # lazy: heavy

        path = _ensure_file("model.onnx")
        _SESSION = ort.InferenceSession(str(path),
                                        providers=["CPUExecutionProvider"])
    return _SESSION


def _display_name(classname: str) -> tuple[str, str]:
    """Split a model classname into (family, style) display strings.

    Classnames look like ``AbhayaLibre-Bold``, ``Abel-Regular`` or the
    variable-font form ``AdventPro[wdth,wght]`` — the family is CamelCase
    with the style after the last dash.
    """
    name = re.sub(r"\[.*?\]$", "", classname)  # drop variable-axis suffix
    family, _, style = name.partition("-")
    # CamelCase -> spaced words ("AbhayaLibre" -> "Abhaya Libre")
    family = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", family)
    return family, (style or "Variable")


def _preprocess(src: Path, size: int):
    """Load an image and letterbox it to the model's square input (NCHW f32).

    Mirrors the upstream inference pipeline exactly: CutMax (crop to 1024,
    not resize) -> ResizeWithPad with a WHITE pad -> ImageNet normalise.
    """
    import numpy as np
    from PIL import Image

    with Image.open(src) as im:
        im = im.convert("RGB")
        if im.width > _MAX_SIDE or im.height > _MAX_SIDE:
            im = im.crop((0, 0, min(im.width, _MAX_SIDE), min(im.height, _MAX_SIDE)))
        scale = size / max(im.size)
        im = im.resize((max(1, round(im.width * scale)),
                        max(1, round(im.height * scale))), Image.LANCZOS)
        canvas = Image.new("RGB", (size, size), (255, 255, 255))
        canvas.paste(im, ((size - im.width) // 2, (size - im.height) // 2))
    x = np.asarray(canvas, dtype=np.float32) / 255.0
    x = (x - np.asarray(_MEAN, dtype=np.float32)) / np.asarray(_STD, dtype=np.float32)
    return x.transpose(2, 0, 1)[None, ...]  # HWC -> 1CHW


def identify_font(src, top_k: int = 5) -> dict:
    """Identify the font in an image; return a GUI-agnostic result dict.

    Returns ``{"matches": [{"name", "family", "style", "prob"}], "model"}``,
    best match first. The matches are the closest of ~3,500 Google Fonts —
    an estimate, not an exact identification. Like the other Vanguard tools
    this lives outside `convert_file`/`CONVERSIONS`.
    """
    src = Path(src)
    ext = src.suffix.lower().lstrip(".")
    if ext not in IMAGE_EXTS:
        raise ConversionError(f"Font identification needs an image; got .{ext or '?'}")
    if not src.is_file():
        raise ConversionError(f"File not found: {src}")

    import numpy as np

    try:
        cfg = _config()
        session = _session()
        x = _preprocess(src, int(cfg.get("size", 320)))
        inp = session.get_inputs()[0].name
        logits = session.run(None, {inp: x})[0][0]
    except ConversionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ConversionError(f"Font identification failed: {exc}") from exc

    logits = logits.astype(np.float64)
    probs = np.exp(logits - logits.max())
    probs /= probs.sum()
    classnames = cfg["classnames"]
    order = np.argsort(probs)[::-1][:max(1, top_k)]
    matches = []
    for idx in order:
        family, style = _display_name(classnames[int(idx)])
        matches.append({
            "name": f"{family} {style}".strip(),
            "family": family,
            "style": style,
            "prob": float(probs[int(idx)]),
        })
    return {"matches": matches, "model": MODEL_NAME}
