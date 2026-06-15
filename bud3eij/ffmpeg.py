"""On-demand ffmpeg for Bu D3eij.

A/V conversion (`convert_av`), YouTube downloads (yt-dlp) and Sonara's audio
loader all shell out to ffmpeg/ffprobe. Rather than require a separate install,
`ensure_ffmpeg()` uses a system ffmpeg if one is on PATH, otherwise downloads a
pinned static Windows build once into the app cache (`~/.bud3eij/ffmpeg/bin/`) and
prepends it to PATH for this process - after which the existing
`shutil.which`/ffmpeg-python/yt-dlp code finds it unchanged.

Nothing is bundled in the installer (mirrors the on-demand model downloads); the
build is fetched from its original distributor (gyan.dev's GitHub mirror), so we
never redistribute ffmpeg (its essentials build is GPL - see THIRD_PARTY.md).
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from .formats import ConversionError

_CACHE_DIR = Path.home() / ".bud3eij" / "ffmpeg"
_BIN_DIR = _CACHE_DIR / "bin"

# Pinned static Windows build (gyan.dev essentials, GitHub-mirrored, immutable tag).
# Covers the codecs the app uses (libmp3lame / aac / h264 / ...). SHA-256 + exact
# size verified, like the model downloads.
_FFMPEG_URL = ("https://github.com/GyanD/codexffmpeg/releases/download/"
               "8.1.1/ffmpeg-8.1.1-essentials_build.zip")
_FFMPEG_SHA256 = "6f58ce889f59c311410f7d2b18895b33c03456463486f3b1ebc93d97a0f54541"
_FFMPEG_SIZE = 109_282_242
_WANTED = ("ffmpeg.exe", "ffprobe.exe")
_DOWNLOAD_TIMEOUT = 60  # socket timeout (s) per read: a stalled download fails, not hangs


def have_ffmpeg() -> bool:
    """True if ffmpeg is already usable (system PATH or the app cache)."""
    return shutil.which("ffmpeg") is not None or (_BIN_DIR / "ffmpeg.exe").exists()


def _prepend_path(directory: Path) -> None:
    s = str(directory)
    if s not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = s + os.pathsep + os.environ.get("PATH", "")


def ensure_ffmpeg() -> str:
    """Return a directory containing ffmpeg(.exe) + ffprobe, ensuring it's on PATH.

    Uses a system ffmpeg if present; otherwise downloads a pinned static build into
    the cache on first use. Raises ConversionError if ffmpeg can't be obtained.
    """
    found = shutil.which("ffmpeg")
    if found:
        return str(Path(found).parent)
    if not (_BIN_DIR / "ffmpeg.exe").exists():
        _download()
    if not (_BIN_DIR / "ffmpeg.exe").exists():
        raise ConversionError("ffmpeg download did not produce ffmpeg.exe.")
    _prepend_path(_BIN_DIR)
    return str(_BIN_DIR)


def _download() -> None:
    import hashlib
    import urllib.request
    import zipfile

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _CACHE_DIR / "ffmpeg.zip.part"
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(_FFMPEG_URL, timeout=_DOWNLOAD_TIMEOUT) as resp, \
                open(tmp, "wb") as fh:  # noqa: S310 - pinned HTTPS URL
            for block in iter(lambda: resp.read(1 << 20), b""):
                fh.write(block)
                digest.update(block)
    except Exception as exc:  # noqa: BLE001
        tmp.unlink(missing_ok=True)
        raise ConversionError(
            "Could not download ffmpeg (needed for audio/video and YouTube). "
            f"Check your internet connection, or install ffmpeg manually. ({exc})"
        ) from exc
    if tmp.stat().st_size != _FFMPEG_SIZE or digest.hexdigest() != _FFMPEG_SHA256:
        tmp.unlink(missing_ok=True)
        raise ConversionError("Downloaded ffmpeg failed its integrity check.")
    _BIN_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(tmp) as z:
            for entry in z.namelist():
                if os.path.basename(entry).lower() in _WANTED:
                    with z.open(entry) as src, open(_BIN_DIR / os.path.basename(entry), "wb") as dst:
                        shutil.copyfileobj(src, dst)
    finally:
        tmp.unlink(missing_ok=True)
