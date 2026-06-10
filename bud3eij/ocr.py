"""Text extraction from images (RapidOCR) for Bu D3eij — a Vanguard tool."""
from __future__ import annotations

from pathlib import Path

from .formats import ConversionError, IMAGE_EXTS

# OCR quality tiers -> (config key, one-line blurb). Both run locally on the
# bundled onnxruntime — no APIs, no accounts, no usage limits.
# Fast = PP-OCRv4 mobile det/cls/rec, bundled inside the rapidocr wheel
#        (fully offline, instant; the ch models also read Chinese).
# Max  = the measured-best recipe for English screenshots/photos: the
#        English-dedicated recognizer (fixes the merged-words problem — the ch
#        recognizer drops English spaces) + a looser, wider detector
#        (box_thresh 0.4 / unclip_ratio 2.0 — recovers lines the defaults
#        skip) + a ~2x Lanczos pre-upscale of small images so the detector
#        sees more pixels. Just as fast as Fast; the en rec model (~10 MB)
#        downloads once (SHA-256-verified by rapidocr itself) into
#        ~/.bud3eij/models/rapidocr/. NOTE: the PP-OCRv4 *server* models were
#        tested and rejected — they fragment/skip lines on UI-style
#        screenshots (they're tuned for large natural photos) at 10x the time.
OCR_MODELS = {
    "Fast": ("bundled", "Instant · fully offline · also reads Chinese"),
    "Max":  ("english", "Best for English · proper spacing, catches faint/small "
                        "lines · tiny one-time download"),
}
DEFAULT_OCR_TIER = "Fast"

_MODEL_DIR = Path.home() / ".bud3eij" / "models" / "rapidocr"
_MAX_PRE_MIN = 1600   # Max tier: images smaller than this get pre-upscaled…
_MAX_PRE_CAP = 2000   # …toward this longest side (rapidocr's own max_side_len)

# Lazily-created RapidOCR engines, cached per tier (each loaded once).
_ENGINES: dict = {}


def unload_models() -> None:
    """Drop the cached OCR engines so their memory can be reclaimed."""
    _ENGINES.clear()


def _engine(tier: str):
    eng = _ENGINES.get(tier)
    if eng is None:
        from rapidocr import LangRec, RapidOCR  # lazy: heavy (onnxruntime + models)

        if OCR_MODELS[tier][0] == "english":
            # The en rec model downloads once into the app's model cache (NOT
            # the package dir — keeps the frozen exe's folder pristine).
            _MODEL_DIR.mkdir(parents=True, exist_ok=True)
            eng = RapidOCR(params={
                "Global.model_root_dir": str(_MODEL_DIR),
                "Rec.lang_type": LangRec.EN,
                "Det.box_thresh": 0.4,
                "Det.unclip_ratio": 2.0,
            })
        else:
            eng = RapidOCR()  # bundled mobile models
        _ENGINES[tier] = eng
    return eng


def _prepared_input(src: Path, tier: str):
    """Return the engine input for `src` — Max pre-upscales small images.

    Small/dense screenshots are the common failure case: at native size the
    detector misses faint or tiny lines and the recognizer fumbles spacing.
    A plain Lanczos ~2x upscale measurably fixes both. Returns a BGR ndarray
    (rapidocr's array convention) for Max, or the plain path for Fast.
    """
    if OCR_MODELS[tier][0] != "english":
        return str(src)
    import numpy as np
    from PIL import Image

    with Image.open(src) as im:
        im = im.convert("RGB")
        side = max(im.size)
        if side < _MAX_PRE_MIN:
            f = min(2.0, _MAX_PRE_CAP / side)
            im = im.resize((max(1, round(im.width * f)),
                            max(1, round(im.height * f))), Image.LANCZOS)
        return np.asarray(im)[:, :, ::-1].copy()  # RGB -> BGR


def extract_text(src, model: str = DEFAULT_OCR_TIER) -> dict:
    """OCR every text line out of an image; return a GUI-agnostic result dict.

    `model` is an `OCR_MODELS` tier ("Fast" bundled mobile / "Max" server,
    downloaded once). Returns ``{"text": str, "lines": [(text, confidence)],
    "count": int}`` — `text` is the detected lines joined with newlines in
    reading order. Like the other Vanguard/Marquee models this lives outside
    `convert_file`/`CONVERSIONS` (it produces text, not a converted file).
    """
    if model not in OCR_MODELS:
        raise ConversionError(
            f"Unknown OCR tier '{model}' — use one of: {', '.join(OCR_MODELS)}")
    src = Path(src)
    ext = src.suffix.lower().lstrip(".")
    if ext not in IMAGE_EXTS:
        raise ConversionError(f"Text extraction needs an image; got .{ext or '?'}")
    if not src.is_file():
        raise ConversionError(f"File not found: {src}")

    try:
        result = _engine(model)(_prepared_input(src, model))
    except Exception as exc:  # noqa: BLE001
        raise ConversionError(f"Text extraction failed: {exc}") from exc

    if result is None or not result.txts:
        return {"text": "", "lines": [], "count": 0}

    scores = result.scores or [0.0] * len(result.txts)
    lines = [(txt, float(score)) for txt, score in zip(result.txts, scores)]
    return {
        "text": "\n".join(txt for txt, _ in lines),
        "lines": lines,
        "count": len(lines),
    }
