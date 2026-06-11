"""Audio stem separation (Demucs htdemucs_ft) for Bu D3eij — the Sonara tool.

Splits a song into four stems (vocals / drums / bass / other) with Meta's
**Demucs** `htdemucs_ft` model — a fine-tuned *bag of four* Hybrid Transformer
models, the highest-quality open stem separator. This is the app's first (and
only) PyTorch dependency; it runs on CUDA when available (seconds per song on
the RTX 3070 Ti) and falls back to CPU (slow but works). Everything is local —
no APIs, no accounts, no usage limits.

PyPI demucs (4.0.1) predates the `demucs.api` module, so this drives the
lower-level pieces directly: `pretrained.get_model` + per-submodel
`apply_model` calls (mirroring BagOfModels averaging) with a lazy *counting
pool* injected for real segment-level progress — apply_model submits every
segment up front and executes them lazily in `result()`, so counting
submissions/completions yields an accurate fraction. Pin demucs==4.0.1; these
internals are stable for that release.

The four checkpoints (~80 MB each) download once via torch.hub into
`TORCH_HOME` (pointed at ~/.bud3eij/models/torch, the app's cache convention).
"""
from __future__ import annotations

import os
from pathlib import Path

from .formats import ConversionError, unique_path

MODEL_NAME = "htdemucs_ft"
STEMS = ("vocals", "drums", "bass", "other")
# What the drop zone / CLI accept — anything ffmpeg can decode an audio
# stream from (mp4/webm video included: the audio track is used).
AUDIO_EXTS = {"mp3", "wav", "flac", "m4a", "aac", "ogg", "opus", "wma",
              "aiff", "mp4", "webm", "mkv"}

_TORCH_HOME = Path.home() / ".bud3eij" / "models" / "torch"
os.environ.setdefault("TORCH_HOME", str(_TORCH_HOME))

_MODEL = None  # cached BagOfModels (loaded once; ~1 GB RAM / VRAM while resident)


def model_is_cached() -> bool:
    """True once the htdemucs_ft checkpoints exist locally (first-run warning)."""
    ckpt = Path(os.environ.get("TORCH_HOME", str(_TORCH_HOME))) / "hub" / "checkpoints"
    return ckpt.is_dir() and len(list(ckpt.glob("*.th"))) >= 4


def unload_models() -> None:
    """Drop the cached Demucs model and free CUDA memory."""
    global _MODEL
    _MODEL = None
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001 - freeing memory must never raise
        pass


def _get_model():
    global _MODEL
    if _MODEL is None:
        from demucs.pretrained import get_model  # lazy: heavy (torch)

        _MODEL = get_model(MODEL_NAME)
        _MODEL.eval()
    return _MODEL


def _load_audio(src: Path, model):
    """Decode `src` to a (channels, samples) float32 tensor at the model rate.

    Mirrors demucs' own load_track (ffmpeg first, torchaudio fallback) but
    raises ConversionError instead of sys.exit'ing the process.
    """
    import subprocess

    from demucs.audio import AudioFile, convert_audio

    errors = []
    try:
        return AudioFile(src).read(streams=0, samplerate=model.samplerate,
                                   channels=model.audio_channels)
    except FileNotFoundError:
        errors.append("ffmpeg is not installed or not on PATH")
    except subprocess.CalledProcessError:
        errors.append("ffmpeg could not read the file")
    try:
        import torchaudio

        wav, sr = torchaudio.load(str(src))
        return convert_audio(wav, sr, model.samplerate, model.audio_channels)
    except Exception as exc:  # noqa: BLE001 - report both backends' failures
        errors.append(f"torchaudio: {exc}")
    raise ConversionError(
        f"Could not decode {src.name} ({'; '.join(errors)}).")


class _CountingPool:
    """Drop-in for demucs' DummyPoolExecutor that reports completion progress.

    apply_model submits one job per audio segment (all up front), then consumes
    the futures in order; executing lazily in result() keeps memory flat and
    lets done/submitted track real progress.
    """

    class _Job:
        # positional-only: the forwarded kwargs contain demucs' own
        # 'pool'/'progress' keys, which must not collide with our params
        def __init__(self, pool, func, /, *args, **kwargs):
            self._pool, self._func, self._args, self._kwargs = pool, func, args, kwargs

        def result(self):
            out = self._func(*self._args, **self._kwargs)
            self._pool.done += 1
            self._pool._report()
            return out

    def __init__(self, on_progress=None):
        self.submitted = 0
        self.done = 0
        self._on_progress = on_progress

    def submit(self, func, /, *args, **kwargs):
        self.submitted += 1
        return self._Job(self, func, *args, **kwargs)

    def _report(self):
        if self._on_progress and self.submitted:
            self._on_progress(min(1.0, self.done / self.submitted))


def split_stems(src, progress=None) -> dict:
    """Split an audio file into the four Demucs stems; return a result dict.

    Returns ``{"stems": {name: float32 ndarray (samples, 2)}, "samplerate":
    int, "duration": float (seconds), "model": MODEL_NAME, "device": str}``.
    `progress(frac)` (0..1) is called from the worker thread as segments
    finish. Like the other AI tools this sits outside `convert_file`/
    `CONVERSIONS` — the caller decides which stems to save via `save_stem`.
    """
    src = Path(src)
    ext = src.suffix.lower().lstrip(".")
    if ext not in AUDIO_EXTS:
        raise ConversionError(f"Stem splitting needs an audio file; got .{ext or '?'}")
    if not src.is_file():
        raise ConversionError(f"File not found: {src}")

    try:
        import torch
        from demucs.apply import apply_model

        model = _get_model()
        device = "cuda" if torch.cuda.is_available() else "cpu"

        wav = _load_audio(src, model)
        # demucs normalizes the mixture and de-normalizes the estimates.
        ref = wav.mean(0)
        norm = (wav - ref.mean()) / (ref.std() + 1e-8)

        # Drive the bag ourselves (instead of one apply_model(bag) call) so a
        # counting pool per submodel gives a real 0..1 progress fraction.
        submodels = list(zip(model.models, model.weights))
        estimates = None
        totals = [0.0] * len(model.sources)
        for idx, (sub, weights) in enumerate(submodels):
            def on_pool(frac, _idx=idx):
                if progress:
                    progress((_idx + frac) / len(submodels))

            pool = _CountingPool(on_pool)
            with torch.no_grad():
                out = apply_model(sub, norm[None], device=device, shifts=1,
                                  split=True, overlap=0.25, pool=pool)
            for k, w in enumerate(weights):
                out[:, k, :, :] *= w
                totals[k] += w
            estimates = out if estimates is None else estimates + out
            del out
        for k, total in enumerate(totals):
            estimates[:, k, :, :] /= total

        stems = {}
        for name, tensor in zip(model.sources, estimates[0]):
            denorm = tensor * ref.std() + ref.mean()
            stems[name] = denorm.cpu().numpy().T.astype("float32", copy=False)
        samples = next(iter(stems.values())).shape[0]
        return {
            "stems": {name: stems[name] for name in STEMS},  # fixed UI order
            "samplerate": model.samplerate,
            "duration": samples / model.samplerate,
            "model": MODEL_NAME,
            "device": device,
        }
    except ConversionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ConversionError(f"Stem splitting failed: {exc}") from exc


def save_stem(stem_array, samplerate: int, out_path, overwrite: bool = False) -> Path:
    """Save one stem (float32 ndarray (samples, 2)) as .wav or .mp3.

    WAV is written with the stdlib `wave` module (torchaudio 2.11 delegated
    `ta.save` to the separate torchcodec package — not worth a dependency for
    PCM16); MP3 goes through demucs' lameenc encoder, which is torchaudio-free.
    Same overwrite contract as remove_background: an explicitly chosen path is
    replaced only with `overwrite=True`; otherwise de-duplicated with ` (n)`.
    """
    import numpy as np

    out = Path(out_path)
    if out.suffix.lower() not in (".wav", ".mp3"):
        out = out.with_suffix(".wav")
    if not overwrite:
        out = unique_path(out)
    data = np.asarray(stem_array, dtype="float32")
    peak = float(np.abs(data).max()) if data.size else 0.0
    if peak > 0.99:  # demucs-style rescale: avoid clipping the int16 output
        data = data / (1.01 * peak)
    try:
        if out.suffix.lower() == ".mp3":
            import torch
            from demucs.audio import encode_mp3

            encode_mp3(torch.from_numpy(data.T.copy()), out, samplerate,
                       bitrate=320, quality=2, verbose=False)
        else:
            import wave

            pcm = (data * 32767.0).astype("<i2")
            with wave.open(str(out), "wb") as wf:
                wf.setnchannels(data.shape[1])
                wf.setsampwidth(2)
                wf.setframerate(samplerate)
                wf.writeframes(pcm.tobytes())
    except Exception as exc:  # noqa: BLE001
        raise ConversionError(f"Could not save the stem: {exc}") from exc
    return out
