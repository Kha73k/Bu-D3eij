"""AI text detection (Vanguard) for Bu D3eij — the first tool of the Vanguard section.

Estimates how likely a piece of text is AI-generated using a local DeBERTa-v3-large
detector (`desklib/ai-text-detector-v1.01`, the #1 open model on the RAID robustness
benchmark) exported to ONNX and run on the already-bundled `onnxruntime` — *no PyTorch*.
The model + its fast tokenizer download once to `~/.bud3eij/models/vanguard/` and cache,
like the rembg/upscaler models. Tokenisation uses the light `tokenizers` library.

The document is split into sentence-group chunks, each scored independently (so passages
can be highlighted and so long documents stream through in bounded batches); the overall
score is a length-weighted mean. Returns a plain dict — GUI-agnostic — with a `progress`
callback mirroring `upscale_image`.

IMPORTANT: detection is probabilistic, NOT proof. False positives happen (especially on
non-native-English or heavily-edited human text) and accuracy drops on paraphrased / newer
text. Callers must present results as an estimate, never an accusation.
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

from .formats import ConversionError

# The detector files live next to the other models, in their own subfolder.
_MODEL_DIR = Path.home() / ".bud3eij" / "models" / "vanguard"
_DEV_DIR = Path(__file__).resolve().parent.parent / "vanguard_model"  # dev: local export

# The ONNX model + its fast tokenizer. The model is large (fp32, ~1.7 GB — fp16 won't
# load in onnxruntime for this graph and int8 hurts accuracy), so for this personal
# build it is NOT bundled in the exe or hosted online: it is produced once by
# `_export_vanguard.py` and lives in the local cache (`_MODEL_DIR`), where both the
# source app and the frozen exe load it. (A self-host download URL could be added here
# later if the app is ever distributed.)
VANGUARD_FILES = {"onnx": "model.onnx", "tokenizer": "tokenizer.json"}
DETECTOR_NAME = "desklib DeBERTa-v3-large"

_MAX_TOKENS = 768       # the detector's training context length
_MIN_WORDS = 40         # below this, results are unreliable -> caveat
_SENTS_PER_CHUNK = 3    # group ~3 sentences per scored chunk
_MAX_CHUNKS = 200       # cap chunks on huge docs (merge more sentences instead)
_BATCH = 8              # chunks per onnxruntime run

# Score (0-100) -> confidence tier. Ordered low→high; first match wins by upper bound.
CONFIDENCE_TIERS: list[tuple[int, str]] = [
    (20, "Human"),
    (40, "Likely Human"),
    (60, "Uncertain"),
    (80, "Likely AI"),
    (100, "AI"),
]
# A chunk at/above this P(AI) is flagged for highlighting in the UI.
FLAG_THRESHOLD = 0.60

_SESSION = None       # onnxruntime InferenceSession (loaded once)
_TOKENIZER = None     # tokenizers.Tokenizer (loaded once)
_INPUT_NAMES: set[str] = set()


def tier_for(score: int) -> str:
    """Map a 0-100 score to a CONFIDENCE_TIERS label."""
    for upper, label in CONFIDENCE_TIERS:
        if score < upper or upper == 100:
            return label
    return CONFIDENCE_TIERS[-1][1]


# --------------------------------------------------------------------------- #
# Text extraction (reuses the same engines as converters.py)
# --------------------------------------------------------------------------- #
def extract_document_text(path) -> str:
    """Return the plain text of a .txt / .docx / .pdf file."""
    path = Path(path)
    ext = path.suffix.lower().lstrip(".")
    if ext == "txt":
        return path.read_text(encoding="utf-8", errors="replace")
    if ext == "docx":
        import docx  # lazy

        document = docx.Document(str(path))
        return "\n".join(p.text for p in document.paragraphs)
    if ext == "pdf":
        import pdfplumber  # lazy

        parts: list[str] = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        return "\n\n".join(parts)
    raise ConversionError(f"AI text detection needs a .txt/.docx/.pdf; got .{ext or '?'}")


# --------------------------------------------------------------------------- #
# Model + tokenizer (download once, cache)
# --------------------------------------------------------------------------- #
def _ensure_file(kind: str) -> Path:
    """Locate a detector file: frozen-exe bundle, then dev export dir, then the cache."""
    filename = VANGUARD_FILES[kind]
    base = getattr(sys, "_MEIPASS", None)
    if base:
        bundled = Path(base) / "bud3eij" / "models" / "vanguard" / filename
        if bundled.exists():
            return bundled
    if (_DEV_DIR / filename).exists():
        return _DEV_DIR / filename
    dest = _MODEL_DIR / filename
    if dest.exists() and dest.stat().st_size > 10_000:
        return dest
    raise ConversionError(
        f"Detector file '{filename}' not found. Put the Vanguard model files "
        f"(model.onnx + tokenizer.json) in {_MODEL_DIR}.")


def _session():
    global _SESSION, _INPUT_NAMES
    if _SESSION is None:
        import onnxruntime as ort  # lazy: heavy

        path = _ensure_file("onnx")
        _SESSION = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        _INPUT_NAMES = {i.name for i in _SESSION.get_inputs()}
    return _SESSION


def _tokenizer():
    global _TOKENIZER
    if _TOKENIZER is None:
        from tokenizers import Tokenizer  # lazy

        tok = Tokenizer.from_file(str(_ensure_file("tokenizer")))
        tok.enable_truncation(max_length=_MAX_TOKENS)
        pad_id = tok.token_to_id("[PAD]")
        tok.enable_padding(pad_id=pad_id if pad_id is not None else 0, pad_token="[PAD]")
        _TOKENIZER = tok
    return _TOKENIZER


def _score_chunks(chunks: list[str], progress=None) -> list[float]:
    """Return P(AI) in [0,1] for each chunk, scored in bounded batches."""
    import numpy as np

    session = _session()
    tok = _tokenizer()
    probs: list[float] = []
    total = max(1, len(chunks))
    for start in range(0, len(chunks), _BATCH):
        batch = chunks[start:start + _BATCH]
        encs = tok.encode_batch(batch)
        ids = np.array([e.ids for e in encs], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encs], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mask,
                "token_type_ids": np.zeros_like(ids)}
        feed = {k: v for k, v in feed.items() if k in _INPUT_NAMES}
        logits = session.run(None, feed)[0].reshape(-1)
        probs.extend((1.0 / (1.0 + np.exp(-logits))).tolist())
        if progress:
            progress(min(1.0, (start + len(batch)) / total))
    return probs


# --------------------------------------------------------------------------- #
# Chunking + entry point
# --------------------------------------------------------------------------- #
_SENT_RE = re.compile(r".+?(?:[.!?]+(?=\s|$)|\n+|$)", re.DOTALL)


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) char spans of sentence-ish units, in order, covering the text."""
    spans = [(m.start(), m.end()) for m in _SENT_RE.finditer(text) if m.group().strip()]
    return spans or ([(0, len(text))] if text else [])


def _chunk_spans(text: str) -> list[tuple[int, int]]:
    """Group sentences into chunks of (start,end) char offsets, capped at _MAX_CHUNKS."""
    sents = _sentence_spans(text)
    if not sents:
        return []
    per = max(_SENTS_PER_CHUNK, math.ceil(len(sents) / _MAX_CHUNKS))
    chunks = []
    for i in range(0, len(sents), per):
        group = sents[i:i + per]
        chunks.append((group[0][0], group[-1][1]))
    return chunks


def detect_ai_text(source, *, is_file: bool = False, progress=None) -> dict:
    """Estimate AI-generated probability of `source` (text str, or a file if `is_file`).

    Returns a dict: `score` (0-100 int), `tier` (str), `spans` (list of
    {text, start, end, p_ai} per scored chunk, offsets into the analysed text),
    `text` (the analysed text), `too_short` (bool), `model` (str), `word_count` (int).

    `progress(frac)` (optional) is called with a float in [0,1] as chunks are scored
    (GUI-agnostic — marshal back to the UI thread yourself). Failures raise
    `ConversionError`. Detection is an estimate, not proof — present it as such.
    """
    text = extract_document_text(source) if is_file else str(source)
    text = (text or "").strip()
    if not text:
        raise ConversionError("There's no text to analyse.")

    word_count = len(text.split())
    spans = _chunk_spans(text)
    chunk_texts = [text[s:e] for s, e in spans]

    try:
        probs = _score_chunks(chunk_texts, progress=progress)
    except ConversionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ConversionError(f"AI text detection failed: {exc}") from exc

    # Length-weighted mean so long docs and short paragraphs both behave sensibly.
    weights = [max(1, e - s) for s, e in spans]
    overall = sum(p * w for p, w in zip(probs, weights)) / max(1, sum(weights))
    score = int(round(overall * 100))

    span_objs = [
        {"text": t, "start": s, "end": e, "p_ai": round(p, 4)}
        for (s, e), t, p in zip(spans, chunk_texts, probs)
    ]
    return {
        "score": score,
        "tier": tier_for(score),
        "spans": span_objs,
        "text": text,
        "too_short": word_count < _MIN_WORDS,
        "model": DETECTOR_NAME,
        "word_count": word_count,
    }
