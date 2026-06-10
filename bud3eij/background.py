"""Image background removal (rembg) for Bu D3eij — the first Marquee tool."""
from __future__ import annotations

from pathlib import Path

from .formats import ConversionError, IMAGE_EXTS, unique_path


# Marquee background-removal tiers -> (rembg model name, one-line blurb).
# All three ride on the bundled rembg; each downloads its own .onnx on first use.
BG_MODELS = {
    "Flash": ("u2netp",            "Fastest · lightweight model for quick cut-outs"),
    "Mid":   ("isnet-general-use", "Balanced · cleaner edges at near-Flash speed"),
    "Omega": ("birefnet-general",  "Max precision · best hair/edges, slower + larger download"),
}
DEFAULT_BG_TIER = "Mid"


# Lazily-created rembg sessions, cached per model name (model loaded once each).
_REMBG_SESSIONS: dict = {}


def unload_models() -> None:
    """Drop all cached rembg sessions so their memory can be reclaimed."""
    _REMBG_SESSIONS.clear()


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
