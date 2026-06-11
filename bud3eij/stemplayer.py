"""Real-time stem playback mixer for Bu D3eij — the Sonara player.

Plays the four separated stems through ONE `sounddevice.OutputStream`,
summing the numpy arrays in the audio callback with per-stem gains. A single
shared clock means the stems can never drift, and mute/solo/volume changes
take effect on the next audio block (~23 ms). GUI-free and testable: the gain
logic and mixing live in `_gains()`/`_mix_block()`, which need no audio device.

Solo semantics (standard DAW behaviour): if ANY stem is soloed, only soloed
stems are audible; otherwise every non-muted stem plays at its volume.
"""
from __future__ import annotations

import threading


class StemPlayer:
    """Mixes and plays a dict of stems ({name: float32 ndarray (samples, 2)})."""

    def __init__(self, stems: dict, samplerate: int):
        import numpy as np

        if not stems:
            raise ValueError("StemPlayer needs at least one stem")
        self._np = np
        self.stems = {name: np.asarray(arr, dtype=np.float32)
                      for name, arr in stems.items()}
        lengths = {arr.shape[0] for arr in self.stems.values()}
        self._frames = max(lengths)
        self.samplerate = int(samplerate)
        self.volume = {name: 1.0 for name in self.stems}
        self.muted = {name: False for name in self.stems}
        self.soloed = {name: False for name in self.stems}
        self._idx = 0
        self._lock = threading.Lock()
        self._stream = None
        self._playing = False
        self.finished = False  # set by the callback at end-of-audio (GUI polls)

    # ---- mixing (pure math — unit-testable without an audio device) ------- #
    def _gains(self) -> dict:
        any_solo = any(self.soloed.values())
        gains = {}
        for name in self.stems:
            if any_solo:
                audible = self.soloed[name]
            else:
                audible = not self.muted[name]
            gains[name] = self.volume[name] if audible else 0.0
        return gains

    def _mix_block(self, start: int, frames: int):
        """Sum all stems over [start, start+frames) with current gains."""
        np = self._np
        out = np.zeros((frames, 2), dtype=np.float32)
        gains = self._gains()
        for name, arr in self.stems.items():
            g = gains[name]
            if g <= 0.0:
                continue
            chunk = arr[start:start + frames]
            out[:len(chunk)] += chunk * g
        return np.clip(out, -1.0, 1.0)

    # ---- transport --------------------------------------------------------- #
    @property
    def duration(self) -> float:
        return self._frames / self.samplerate

    @property
    def position(self) -> float:
        return self._idx / self.samplerate

    @property
    def is_playing(self) -> bool:
        return self._playing

    def _callback(self, outdata, frames, _time, _status):
        with self._lock:
            start = self._idx
            self._idx = min(self._frames, start + frames)
            ended = self._idx >= self._frames
        outdata[:] = self._mix_block(start, frames)
        if ended:
            self.finished = True
            self._playing = False
            raise self._sd.CallbackStop()

    def _ensure_stream(self):
        if self._stream is None:
            import sounddevice as sd  # lazy: opens PortAudio

            self._sd = sd
            self._stream = sd.OutputStream(
                samplerate=self.samplerate, channels=2, dtype="float32",
                callback=self._callback,
            )
        return self._stream

    def play(self):
        with self._lock:
            if self._idx >= self._frames:  # replay from the top after finishing
                self._idx = 0
        self.finished = False
        self._ensure_stream().start()
        self._playing = True

    def pause(self):
        if self._stream is not None:
            self._stream.stop()
        self._playing = False

    def toggle(self):
        if self._playing:
            self.pause()
        else:
            self.play()

    def seek(self, fraction: float):
        fraction = max(0.0, min(1.0, fraction))
        with self._lock:
            self._idx = int(self._frames * fraction)
        if self._idx < self._frames:
            self.finished = False

    def set_volume(self, name: str, value: float):
        self.volume[name] = max(0.0, min(1.0, float(value)))

    def set_mute(self, name: str, muted: bool):
        self.muted[name] = bool(muted)

    def set_solo(self, name: str, soloed: bool):
        self.soloed[name] = bool(soloed)

    def close(self):
        """Stop playback and release the audio device (idempotent)."""
        self._playing = False
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:  # noqa: BLE001 - releasing audio must never raise
                pass
