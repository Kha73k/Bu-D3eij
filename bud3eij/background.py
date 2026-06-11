"""Image background removal for Bu D3eij — the first Marquee tool.

Flash/Mid ride on rembg (onnxruntime CPU). The Omega tier was upgraded in
v4.1 to the official **BiRefNet_HR** (MIT, ZhengPeng7/BiRefNet_HR) running on
**PyTorch CUDA** — the current open state of the art for matting-quality
cut-outs (best hair/edge fidelity; the stronger-still RMBG-2.0 is gated behind
a HuggingFace account, which violates the app's no-accounts rule). The
~444 MB weights + model code download once into the app cache
(`HF_HOME = ~/.bud3eij/models/hf`, revision pinned) and run at 2048x2048 in
fp16 on the GPU (fp32 on CPU fallback).
"""
from __future__ import annotations

import os
from pathlib import Path

from .formats import ConversionError, IMAGE_EXTS, unique_path

# Marquee background-removal tiers -> (model name, one-line blurb).
# Flash/Mid are rembg models (each downloads its own .onnx on first use);
# "birefnet-hr" is the v4.1 torch path below.
BG_MODELS = {
    "Flash": ("u2netp",            "Fastest · lightweight model for quick cut-outs"),
    "Mid":   ("isnet-general-use", "Balanced · cleaner edges at near-Flash speed"),
    "Omega": ("birefnet-hr",       "Max precision · BiRefNet-HR on the GPU — best "
                                   "hair & edges (~444 MB one-time download)"),
}
DEFAULT_BG_TIER = "Mid"

BIREFNET_HR_REPO = "ZhengPeng7/BiRefNet_HR"
BIREFNET_HR_REVISION = "a7a562f6fd16021180f2f4348f4de003a2d3d1e1"  # pinned
_BIREFNET_SIZE = (2048, 2048)  # the HR model's native working resolution

# Lazily-created sessions, cached per model name (each loaded once).
_REMBG_SESSIONS: dict = {}
_BIREFNET = None  # (model, device) once loaded


def unload_models() -> None:
    """Drop all cached background-removal models (CPU and GPU memory)."""
    global _BIREFNET
    _REMBG_SESSIONS.clear()
    _BIREFNET = None
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001 - freeing memory must never raise
        pass


def _birefnet_hr():
    """Load (once) the BiRefNet_HR model onto the GPU/CPU."""
    global _BIREFNET
    if _BIREFNET is None:
        os.environ.setdefault("HF_HOME", str(Path.home() / ".bud3eij" / "models" / "hf"))
        import torch
        from transformers import AutoModelForImageSegmentation  # lazy: heavy

        model = AutoModelForImageSegmentation.from_pretrained(
            BIREFNET_HR_REPO, trust_remote_code=True,
            revision=BIREFNET_HR_REVISION,
        )
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model.to(device)
        if device == "cuda":
            model = model.half()  # fp16: fits 2048x2048 comfortably in 8 GB
        model.eval()
        _BIREFNET = (model, device)
    return _BIREFNET


def _remove_birefnet_hr(im):
    """Run BiRefNet_HR on a PIL image; return the RGBA cut-out."""
    import torch
    from torchvision import transforms

    model, device = _birefnet_hr()
    prep = transforms.Compose([
        transforms.Resize(_BIREFNET_SIZE),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    rgb = im.convert("RGB")
    x = prep(rgb)[None].to(device)
    if device == "cuda":
        x = x.half()
    with torch.no_grad():
        pred = model(x)[-1].sigmoid().float().cpu()
    mask = transforms.ToPILImage()(pred[0].squeeze().clamp(0, 1))
    out = im.convert("RGBA")
    out.putalpha(mask.resize(out.size))
    return out


def remove_background(src, out_path=None, model: str = "isnet-general-use",
                      overwrite: bool = False) -> Path:
    """Remove an image's background and save a transparent PNG; return its path.

    `model` is a rembg model name (see `BG_MODELS` for the Marquee tiers:
    `u2netp` / `isnet-general-use` / `birefnet-general`). `src` must be an image;
    the output is always saved as PNG (the only supported image format that
    preserves transparency). With `overwrite` an explicitly chosen `out_path` is
    replaced (the GUI's save dialog already confirmed it); otherwise the path is
    de-duplicated with ` (n)`. Like `download_youtube`, this lives outside
    `convert_file`/`CONVERSIONS` — it has no target format to choose.
    """
    from PIL import Image
    from rembg import new_session, remove  # lazy: heavy (onnxruntime + model)

    src = Path(src)
    ext = src.suffix.lower().lstrip(".")
    if ext not in IMAGE_EXTS:
        raise ConversionError(f"Background removal needs an image; got .{ext or '?'}")

    try:
        if model == "birefnet-hr":  # v4.1 Omega: torch/CUDA path
            with Image.open(src) as im:
                result = _remove_birefnet_hr(im)
        else:
            session = _REMBG_SESSIONS.get(model)
            if session is None:
                # Downloads this model's .onnx on first use, then caches in ~/.u2net.
                session = new_session(model)
                _REMBG_SESSIONS[model] = session
            with Image.open(src) as im:
                result = remove(im.convert("RGBA"), session=session)
    except Exception as exc:  # noqa: BLE001
        raise ConversionError(f"Background removal failed: {exc}") from exc

    out = Path(out_path) if out_path else src.with_name(f"{src.stem}_no-bg.png")
    if out.suffix.lower() != ".png":
        out = out.with_suffix(".png")  # transparency requires PNG
    if not (overwrite and out_path):
        out = unique_path(out)  # auto-named output never clobbers a file
    result.save(out, "PNG")
    return out
