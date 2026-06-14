"""Image -> Prompt for Bu D3eij — a Marquee tool that describes an image.

Given an image, produce a detailed natural-language prompt that could be used to
recreate it (subject, setting, style, lighting, colours, composition). Runs
**Qwen2-VL-2B-Instruct** (Apache-2.0, ungated, ~2.2B params, ~4.4 GB) on
**PyTorch CUDA** in bf16 — it fits comfortably in 8 GB and, being instructable,
can be asked directly for a text-to-image prompt. It is a first-class
transformers model (no `trust_remote_code`), so it stays compatible with the
project's `transformers>=5` pin (Microsoft's Florence-2, the obvious smaller
captioner, ships remote modeling code that breaks on transformers 5.x).

The weights download once into the app cache (`HF_HOME = ~/.bud3eij/models/hf`,
revision pinned) — fully offline afterwards. No Fast/Max tiers; instead a free
DETAIL mode swaps the instruction (Concise vs Detailed) — same model, same cost.
"""
from __future__ import annotations

import os
from pathlib import Path

from .formats import ConversionError, IMAGE_EXTS

QWEN_REPO = "Qwen/Qwen2-VL-2B-Instruct"
QWEN_REVISION = "895c3a49bc3fa70a340399125c650a463535e71c"  # pinned main

# DETAIL mode label -> the instruction handed to the model. Same model, no tier.
PROMPT_MODES = {
    "Concise": (
        "Describe this image in one or two sentences as a text-to-image prompt, "
        "covering the main subject, style, and setting. Output only the prompt."
    ),
    "Detailed": (
        "Write a single detailed text-to-image prompt that could recreate this "
        "image. Cover the main subject, setting, art style or medium, lighting, "
        "colour palette, mood, and composition. Write it as one flowing "
        "description and output only the prompt."
    ),
}
DEFAULT_PROMPT_MODE = "Detailed"

# Bound the vision tokens so a big image can't blow the 8 GB budget (28 = patch).
_MAX_PIXELS = 1024 * 28 * 28
_MIN_PIXELS = 256 * 28 * 28

# Loaded once and cached (model, processor, device).
_MODEL = None
_PROCESSOR = None
_DEVICE = None


def unload_models() -> None:
    """Drop the cached Qwen2-VL model/processor so its memory can be reclaimed."""
    global _MODEL, _PROCESSOR, _DEVICE
    _MODEL = None
    _PROCESSOR = None
    _DEVICE = None
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001 - freeing memory must never raise
        pass


def _load():
    """Load (once) Qwen2-VL-2B onto the GPU/CPU; return (model, processor, device)."""
    global _MODEL, _PROCESSOR, _DEVICE
    if _MODEL is None:
        os.environ.setdefault("HF_HOME", str(Path.home() / ".bud3eij" / "models" / "hf"))
        import torch
        from transformers import AutoProcessor, Qwen2VLForConditionalGeneration  # lazy

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if device == "cuda" else torch.float32
        model = Qwen2VLForConditionalGeneration.from_pretrained(
            QWEN_REPO, revision=QWEN_REVISION, torch_dtype=dtype,
            attn_implementation="sdpa",
        )
        processor = AutoProcessor.from_pretrained(
            QWEN_REPO, revision=QWEN_REVISION,
            min_pixels=_MIN_PIXELS, max_pixels=_MAX_PIXELS,
        )
        model = model.to(device).eval()
        _MODEL, _PROCESSOR, _DEVICE = model, processor, device
    return _MODEL, _PROCESSOR, _DEVICE


def image_to_prompt(src, mode: str = DEFAULT_PROMPT_MODE, progress=None) -> str:
    """Describe an image as a detailed text prompt; return the prompt string.

    `mode` is a key of `PROMPT_MODES` (Concise / Detailed). `src` must be an
    image. Like the other Marquee tools this lives outside `convert_file`; it
    produces text (copied to the clipboard), not a file.
    """
    from PIL import Image

    src = Path(src)
    ext = src.suffix.lower().lstrip(".")
    if ext not in IMAGE_EXTS:
        raise ConversionError(f"Image description needs an image; got .{ext or '?'}")

    instruction = PROMPT_MODES.get(mode, PROMPT_MODES[DEFAULT_PROMPT_MODE])
    if progress:
        progress(0.1)

    try:
        import torch

        model, processor, device = _load()
        with Image.open(src) as im:
            image = im.convert("RGB")
            messages = [{
                "role": "user",
                "content": [{"type": "image"}, {"type": "text", "text": instruction}],
            }]
            text = processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)
            inputs = processor(text=[text], images=[image], padding=True,
                               return_tensors="pt").to(device)
            with torch.no_grad():
                generated = model.generate(**inputs, max_new_tokens=512,
                                           do_sample=False)
            trimmed = [out[len(inp):] for inp, out in
                       zip(inputs.input_ids, generated)]
            decoded = processor.batch_decode(
                trimmed, skip_special_tokens=True,
                clean_up_tokenization_spaces=False)[0]
    except Exception as exc:  # noqa: BLE001
        raise ConversionError(f"Image description failed: {exc}") from exc

    if progress:
        progress(1.0)
    return decoded.strip()
