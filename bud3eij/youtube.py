"""YouTube (yt-dlp) download helper for Bu D3eij."""
from __future__ import annotations

import shutil
from pathlib import Path

from .formats import ConversionError


# --------------------------------------------------------------------------- #
# YouTube download (yt-dlp + ffmpeg)
# --------------------------------------------------------------------------- #
YT_FORMATS = ("mp3", "mp4")


def download_youtube(url: str, fmt: str, out_dir, progress_hook=None) -> Path:
    """Download a YouTube (or other yt-dlp-supported) URL as mp3 or mp4.

    `fmt` is "mp3" (192 kbps audio) or "mp4" (best video+audio, merged).
    Saves into `out_dir` and returns the output path. Needs ffmpeg.
    """
    import yt_dlp

    fmt = fmt.lower().lstrip(".")
    if fmt not in YT_FORMATS:
        raise ConversionError(f"Unsupported download format: {fmt}")
    url = (url or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        raise ConversionError("Enter a valid video URL (must start with http:// or https://).")
    if shutil.which("ffmpeg") is None:
        raise ConversionError(
            "ffmpeg is not installed or not on PATH. Install it "
            "(e.g. 'winget install Gyan.FFmpeg') and restart the app."
        )

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(out_dir / "%(title)s.%(ext)s")
    opts: dict = {
        "outtmpl": outtmpl,
        "ffmpeg_location": shutil.which("ffmpeg"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,  # a single video, even if the URL has a list= param
        "restrictfilenames": True,  # filesystem-safe names
    }
    if progress_hook:
        opts["progress_hooks"] = [progress_hook]
    if fmt == "mp3":
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:  # mp4
        opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            produced = Path(ydl.prepare_filename(info))
    except yt_dlp.utils.DownloadError as exc:
        raise ConversionError(f"Download failed: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise ConversionError(f"Download failed: {exc}") from exc

    # The post-processor changes the extension; resolve the final file.
    out = produced.with_suffix(f".{fmt}")
    if not out.exists():
        # Fall back to whatever landed if the suffix guess is off.
        if produced.exists():
            return produced
        raise ConversionError("Download finished but the output file was not found.")
    return out
