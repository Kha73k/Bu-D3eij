"""Image upscaling (UltraSharp V2 via spandrel/PyTorch) for Bu D3eij — a Marquee tool.

Upscales a low-quality image to an exact target resolution (1080p / 2K / 4K)
using Kim2091's **UltraSharp V2** super-resolution models loaded through
**spandrel** (the model loader ComfyUI/chaiNNer use) on **PyTorch CUDA** —
GPU-fast on the RTX 3070 Ti, automatic CPU fallback elsewhere. v4.1 replaced
the 2021-era Real-ESRGAN ONNX models after a measured A/B (PSNR on degraded
test images): Fast = UltraSharp V2 **Lite** (RealPLKSR) beat even the old Max
tier by ~1.8 dB at a fraction of the time; Max = UltraSharp V2 (DAT-2) is the
overall quality winner (+2.6 dB over old Max). Models download once
(SHA-256-verified) into ~/.bud3eij/models. If the model can't be loaded, it
falls back to high-quality Lanczos resampling so the tool never hard-fails.

After upscaling, the image is fit to the exact target with letterboxing (the whole
image is preserved and padded with bars), so output is always exactly W x H.
"""
from __future__ import annotations

import math
import shutil
import sys
import urllib.request
from pathlib import Path

from .formats import ConversionError, IMAGE_EXTS, unique_path

# Target label -> exact output resolution (W, H).
TARGETS: dict[str, tuple[int, int]] = {
    "1080p": (1920, 1080),
    "2K": (2560, 1440),
    "4K": (3840, 2160),
}
DEFAULT_TARGET = "2K"

# Upscaler quality tiers -> (model filename, download URL, one-line blurb, sha256).
# Both are x4 models loaded via spandrel; they share one inference path. Each
# model downloads once to ~/.bud3eij/models and is cached thereafter.
_MODEL_DIR = Path.home() / ".bud3eij" / "models"
UPSCALE_MODELS: dict[str, tuple[str, str, str, str]] = {
    "Fast": (
        "4x-UltraSharpV2_Lite.safetensors",
        "https://huggingface.co/Kim2091/UltraSharpV2/resolve/main/4x-UltraSharpV2_Lite.safetensors",
        "Sharp + fast · UltraSharp V2 Lite on the GPU (~28 MB)",
        "7a330ef6b7c632477d311ac03499c91c350e35c5986d4a6c295f0628cb871a09",
    ),
    "Max": (
        "4x-UltraSharpV2.safetensors",
        "https://huggingface.co/Kim2091/UltraSharpV2/resolve/main/4x-UltraSharpV2.safetensors",
        "Max fidelity · UltraSharp V2 (DAT-2) — best detail (~133 MB)",
        "2b5db674aa8f3864a696dccd1d07d7cc0500fbf220f35044cd30eee9a7f971a7",
    ),
}
DEFAULT_UPSCALE_TIER = "Fast"

_SCALE = 4          # the models upscale x4 per pass
_MAX_PASSES = 2     # cap repeated passes (x16) for very small inputs
_TILE = 256         # input-pixel tile size (bounds memory on large inputs)
_OVERLAP = 16       # tile overlap (input px) to avoid seams
_SR_MIN_GAIN = 1.25  # below this fit scale a full x4 SR pass isn't worth the
                     # minutes of CPU + ~GB RAM it costs; plain Lanczos is enough
_DOWNLOAD_TIMEOUT = 30  # socket timeout (s): a stalled download fails, not hangs

_UPSCALE_SESSIONS: dict = {}  # tier -> loaded spandrel model (loaded once each)


def unload_models() -> None:
    """Drop all cached upscaler models so their (GPU) memory can be reclaimed."""
    _UPSCALE_SESSIONS.clear()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001 - freeing memory must never raise
        pass


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _ensure_model(tier: str) -> Path:
    """Return the local path for `tier`'s model, downloading + caching on first use."""
    filename, url, _, sha256 = UPSCALE_MODELS[tier]
    # Allow a bundled copy (frozen exe) to satisfy the requirement offline.
    base = getattr(sys, "_MEIPASS", None)
    if base:
        bundled = Path(base) / "bud3eij" / "models" / filename
        if bundled.exists():
            return bundled
    dest = _MODEL_DIR / filename
    if dest.exists() and dest.stat().st_size > 1_000_000:
        return dest
    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=_DOWNLOAD_TIMEOUT) as resp, \
                open(tmp, "wb") as fh:  # noqa: S310 - pinned HTTPS URL
            shutil.copyfileobj(resp, fh)
    except Exception as exc:  # noqa: BLE001
        tmp.unlink(missing_ok=True)
        raise ConversionError(f"Could not download the upscaler model: {exc}") from exc
    if _sha256(tmp) != sha256:
        tmp.unlink(missing_ok=True)
        raise ConversionError(
            "Downloaded upscaler model failed its integrity check (hash mismatch).")
    tmp.replace(dest)
    return dest


def _session(tier: str):
    """Return the loaded spandrel model for `tier` (cached; CUDA if available)."""
    sess = _UPSCALE_SESSIONS.get(tier)
    if sess is None:
        import torch  # lazy: heavy
        from spandrel import ModelLoader

        path = _ensure_model(tier)
        desc = ModelLoader().load_from_file(str(path))
        device = "cuda" if torch.cuda.is_available() else "cpu"
        sess = desc.model.eval().to(device)
        sess._bud3eij_device = device  # remembered for _run_tile
        _UPSCALE_SESSIONS[tier] = sess
    return sess


def _run_tile(session, tile):
    """Run the model on one HxWx3 float32[0,1] tile; return the x4 HxWx3 result."""
    import numpy as np
    import torch

    device = getattr(session, "_bud3eij_device", "cpu")
    x = torch.from_numpy(tile.transpose(2, 0, 1)[None, ...].copy()).to(device)
    with torch.no_grad():
        y = session(x)
    out = y[0].clamp(0.0, 1.0).permute(1, 2, 0).cpu().numpy()
    return np.ascontiguousarray(out)


def _sr_x4(session, img, on_tile=None):
    """Upscale a HxWx3 float32[0,1] image x4, tiling large inputs to bound memory.

    `on_tile` (if given) is called once per processed tile, so callers can report
    real fill progress (one call for the single-tile fast path too).
    """
    import numpy as np

    h, w, _ = img.shape
    if h <= _TILE and w <= _TILE:
        out = _run_tile(session, img)
        if on_tile:
            on_tile()
        return out
    out = np.zeros((h * _SCALE, w * _SCALE, 3), dtype=np.float32)
    for y in range(0, h, _TILE):
        for x in range(0, w, _TILE):
            y0, y1 = max(0, y - _OVERLAP), min(h, y + _TILE + _OVERLAP)
            x0, x1 = max(0, x - _OVERLAP), min(w, x + _TILE + _OVERLAP)
            up = _run_tile(session, img[y0:y1, x0:x1])
            # copy only the non-overlap core into the output canvas
            ky, kx = (y - y0) * _SCALE, (x - x0) * _SCALE
            hk = (min(h, y + _TILE) - y) * _SCALE
            wk = (min(w, x + _TILE) - x) * _SCALE
            out[y * _SCALE:y * _SCALE + hk, x * _SCALE:x * _SCALE + wk] = up[ky:ky + hk, kx:kx + wk]
            if on_tile:
                on_tile()
    return out


def _fit_letterbox(img, target_w: int, target_h: int):
    """Fit `img` (PIL) into target W x H preserving aspect ratio, padding with
    black bars (letterbox). Output is always exactly target_w x target_h."""
    from PIL import Image

    w, h = img.size
    scale = min(target_w / w, target_h / h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    resized = img.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), (0, 0, 0))
    canvas.paste(resized, ((target_w - nw) // 2, (target_h - nh) // 2))
    return canvas


def _fit_crop(img, target_w: int, target_h: int):
    """Fill target W x H preserving aspect ratio: scale to cover, center-crop.
    No bars — the overflowing edges are trimmed instead."""
    from PIL import Image

    w, h = img.size
    scale = max(target_w / w, target_h / h)
    nw, nh = max(target_w, round(w * scale)), max(target_h, round(h * scale))
    resized = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - target_w) // 2, (nh - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def upscale_image(src, out_path=None, target: str = DEFAULT_TARGET,
                  model: str = DEFAULT_UPSCALE_TIER, fit: str = "letterbox",
                  progress=None, overwrite: bool = False) -> Path:
    """Upscale `src` to an exact target resolution; return the output path.

    `target` is a key of `TARGETS` (1080p / 2K / 4K). `model` is an upscaler tier
    in `UPSCALE_MODELS` (Fast = UltraSharp V2 Lite, Max = UltraSharp V2). The
    image is super-resolved on the GPU when available (enough x4 passes to exceed
    the fitted size), then Lanczos-fit to exactly W x H — `fit="letterbox"` pads with bars,
    `fit="crop"` fills the frame and trims the overflow. Output defaults to PNG
    (lossless); a chosen .jpg/.webp extension is honoured. With `overwrite` an
    explicitly chosen `out_path` is replaced (the GUI's save dialog already
    confirmed it); auto-named outputs never clobber a file.

    `progress`, if given, is called with a float in [0, 1] as the work proceeds (one
    update per processed tile, ending at 1.0) so a GUI can show a real filling bar.
    It is invoked on the calling thread — marshal back to the UI thread yourself.
    """
    from PIL import Image
    import numpy as np

    src = Path(src)
    ext = src.suffix.lower().lstrip(".")
    if ext not in IMAGE_EXTS:
        raise ConversionError(f"Upscaling needs an image; got .{ext or '?'}")
    if target not in TARGETS:
        raise ConversionError(f"Unknown target resolution: {target}")
    if model not in UPSCALE_MODELS:
        model = DEFAULT_UPSCALE_TIER
    if fit not in ("letterbox", "crop"):
        fit = "letterbox"
    target_w, target_h = TARGETS[target]

    with Image.open(src) as im:
        img = im.convert("RGB")
        w, h = img.size
        # Crop must *cover* the target, letterbox must *fit inside* it.
        ratios = (target_w / w, target_h / h)
        fit_scale = max(ratios) if fit == "crop" else min(ratios)

        big = img
        # Below _SR_MIN_GAIN a full x4 SR pass (then a Lanczos *down*scale) costs
        # minutes of CPU and up to GBs of RAM for a near-identical result.
        if fit_scale > _SR_MIN_GAIN:  # input is meaningfully smaller -> super-resolve
            # Plan the passes up front so progress is a real fraction: each x4 pass
            # tiles the (4x-growing) image; sum every tile we'll process.
            total_tiles, pw, ph, factor, planned = 0, w, h, 1, 0
            while factor < fit_scale and planned < _MAX_PASSES:
                total_tiles += math.ceil(ph / _TILE) * math.ceil(pw / _TILE)
                pw, ph, factor, planned = pw * _SCALE, ph * _SCALE, factor * _SCALE, planned + 1
            total_tiles = max(1, total_tiles)
            done = 0

            def _tick():
                nonlocal done
                done += 1
                if progress:
                    progress(min(0.97, done / total_tiles * 0.97))  # reserve tail for fit/save

            try:
                session = _session(model)
                arr = np.asarray(img, dtype=np.float32) / 255.0
                factor = 1
                passes = 0
                while factor < fit_scale and passes < _MAX_PASSES:
                    arr = _sr_x4(session, arr, on_tile=_tick)
                    factor *= _SCALE
                    passes += 1
                big = Image.fromarray((np.clip(arr, 0.0, 1.0) * 255.0 + 0.5).astype("uint8"))
            except Exception as exc:  # noqa: BLE001 - degrade to Lanczos, never hard-fail
                print(f"[upscale] AI model unavailable, using Lanczos fallback: {exc!r}",
                      file=sys.stderr)
                big = img  # _fit_letterbox will Lanczos-enlarge to the fitted size

        fitter = _fit_crop if fit == "crop" else _fit_letterbox
        result = fitter(big, target_w, target_h)

    out = Path(out_path) if out_path else src.with_name(f"{src.stem}_{target}.png")
    suffix = out.suffix.lower()
    if suffix not in (".png", ".jpg", ".jpeg", ".webp"):
        out = out.with_suffix(".png")
        suffix = ".png"
    if not (overwrite and out_path):
        out = unique_path(out)  # auto-named output never clobbers a file
    fmt = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}[suffix]
    result.save(out, fmt)
    if progress:
        progress(1.0)
    return out
