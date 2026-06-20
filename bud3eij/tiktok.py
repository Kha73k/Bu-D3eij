"""TikTok downloader for Bu D3eij — SnapTik-style.

The primary engine is a TikTok **resolver API** (tikwm) that returns the
no-watermark video URL, the photo-post images, and the audio track directly —
the same approach SnapTik uses, and far more reliable than yt-dlp's TikTok
extractor (which upstream breaks whenever TikTok changes their page). yt-dlp is
kept as an automatic **fallback** for when the resolver is unreachable.

The caller picks a **mode** and the post type is auto-detected:

- ``"media"`` on a normal video       -> a no-watermark **MP4**
- ``"media"`` on a photo/slideshow    -> its **images** (a per-post subfolder)
- ``"mp3"``                           -> the post's sound as an **MP3**

Only the public TikTok link is sent to the resolver; nothing of the user's own
is uploaded. Like ``download_youtube`` this sits outside ``convert_file``.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from .formats import ConversionError, unique_path

# media = the video (mp4) or the photo images; mp3 = just the sound track.
TIKTOK_MODES = ("media", "mp3")

_RESOLVER = "https://www.tikwm.com/api/"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}
_TIMEOUT = 30
_CHUNK = 1 << 16  # 64 KiB
_CT_EXT = {
    "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
    "image/webp": ".webp", "image/heic": ".heic",
}


class _ResolverError(Exception):
    """The resolver was unreachable or returned no usable data (-> try yt-dlp)."""


def _safe_name(name: str) -> str:
    """Filesystem-safe file/folder stem (Windows-illegal chars out)."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", (name or "").strip())
    cleaned = cleaned.strip(" .")  # Windows dislikes trailing dot/space
    return cleaned[:80] or "tiktok"


def download_tiktok(url: str, mode: str = "media", out_dir=None, progress_hook=None) -> Path:
    """Download a TikTok post. Returns the saved file (video/mp3) or, for a
    photo post, the folder its images were saved into."""
    mode = (mode or "media").lower().strip()
    if mode not in TIKTOK_MODES:
        raise ConversionError(f"Unsupported TikTok mode: {mode}")
    url = (url or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        raise ConversionError("Enter a valid TikTok URL (must start with http:// or https://).")
    if out_dir is None:
        raise ConversionError("No output folder was given.")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Primary: resolver API. If it can't be reached, fall back to yt-dlp.
    try:
        data = _resolve(url)
    except _ResolverError as rexc:
        return _ytdlp_fallback(url, mode, out_dir, progress_hook, rexc)
    return _download_from_data(data, mode, out_dir, progress_hook)


# --------------------------------------------------------------------------- #
# Resolver path
# --------------------------------------------------------------------------- #
def _resolve(url: str) -> dict:
    """Ask the resolver for a post's direct media URLs. Raises _ResolverError."""
    api = _RESOLVER + "?" + urllib.parse.urlencode({"url": url, "hd": 1})
    try:
        req = urllib.request.Request(api, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001 - any network/parse error -> fall back
        raise _ResolverError(f"resolver request failed: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("code") != 0 or not payload.get("data"):
        msg = (payload or {}).get("msg") if isinstance(payload, dict) else None
        raise _ResolverError(msg or "resolver returned no data")
    return payload["data"]


def _download_from_data(data: dict, mode: str, out_dir: Path, progress_hook) -> Path:
    title = data.get("title") or str(data.get("id") or "tiktok")
    images = data.get("images") or []

    if mode == "mp3":
        music = data.get("music") or (data.get("music_info") or {}).get("play")
        if not music:
            raise ConversionError("This TikTok post has no downloadable audio.")
        dest = unique_path(out_dir / f"{_safe_name(title)}.mp3")
        _http_download(music, dest, progress_hook)
        return dest

    if images:  # photo / slideshow post -> images only
        folder = unique_path(out_dir / _safe_name(title))
        folder.mkdir(parents=True, exist_ok=True)
        total = len(images)
        for i, img_url in enumerate(images, 1):
            _download_image(img_url, folder, i)
            if progress_hook:
                progress_hook({"status": "downloading", "downloaded_bytes": i, "total_bytes": total})
        if progress_hook:
            progress_hook({"status": "finished"})
        return folder

    # video post -> no-watermark MP4 (hdplay/play are unwatermarked; wmplay is last resort)
    video = data.get("hdplay") or data.get("play") or data.get("wmplay")
    if not video:
        raise ConversionError("No downloadable video URL was returned for this link.")
    dest = unique_path(out_dir / f"{_safe_name(title)}.mp4")
    _http_download(video, dest, progress_hook)
    return dest


def _http_download(url: str, dest: Path, progress_hook=None) -> Path:
    """Stream a single file to `dest`, emitting yt-dlp-shaped progress dicts."""
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            with open(dest, "wb") as fh:
                while True:
                    chunk = resp.read(_CHUNK)
                    if not chunk:
                        break
                    fh.write(chunk)
                    done += len(chunk)
                    if progress_hook:
                        progress_hook({"status": "downloading", "downloaded_bytes": done,
                                       "total_bytes": total or None})
        if progress_hook:
            progress_hook({"status": "finished"})
    except Exception as exc:  # noqa: BLE001
        try:
            dest.unlink()
        except OSError:
            pass
        raise ConversionError(f"Download failed: {exc}") from exc
    return dest


def _download_image(url: str, folder: Path, index: int) -> Path:
    """Fetch one carousel image; pick the extension from its content type."""
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            ct = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            ext = _CT_EXT.get(ct, ".jpg")
            dest = folder / f"{index:02d}{ext}"
            with open(dest, "wb") as fh:
                while True:
                    chunk = resp.read(_CHUNK)
                    if not chunk:
                        break
                    fh.write(chunk)
    except Exception as exc:  # noqa: BLE001
        raise ConversionError(f"Image {index} failed to download: {exc}") from exc
    return dest


# --------------------------------------------------------------------------- #
# yt-dlp fallback (used only when the resolver is unreachable)
# --------------------------------------------------------------------------- #
def _ytdlp_fallback(url: str, mode: str, out_dir: Path, progress_hook, resolver_err) -> Path:
    try:
        import yt_dlp
    except Exception:  # noqa: BLE001
        raise ConversionError(f"Couldn't resolve the TikTok link ({resolver_err}).") from resolver_err

    from .ffmpeg import ensure_ffmpeg

    base = {
        "ffmpeg_location": ensure_ffmpeg(),
        "quiet": True, "no_warnings": True, "restrictfilenames": True,
    }
    if progress_hook:
        base["progress_hooks"] = [progress_hook]
    try:
        with yt_dlp.YoutubeDL({**base, "noplaylist": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
        photo = "/photo/" in (info.get("webpage_url") or url).lower() or bool(
            (info.get("formats") or []) and not any(
                f.get("vcodec") not in (None, "none") for f in info["formats"]))
        if mode == "mp3":
            opts = {**base, "noplaylist": True,
                    "outtmpl": str(out_dir / "%(title).80s [%(id)s].%(ext)s"),
                    "format": "bestaudio/best",
                    "postprocessors": [{"key": "FFmpegExtractAudio",
                                        "preferredcodec": "mp3", "preferredquality": "192"}]}
            suffix = ".mp3"
        elif photo:
            folder = unique_path(out_dir / "tiktok_photos")
            folder.mkdir(parents=True, exist_ok=True)
            with yt_dlp.YoutubeDL({**base, "noplaylist": False,
                                   "outtmpl": str(folder / "%(autonumber)02d.%(ext)s")}) as ydl:
                ydl.download([url])
            if any(p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") for p in folder.iterdir()):
                return folder
            raise ConversionError("No images were found in this TikTok photo post.")
        else:
            opts = {**base, "noplaylist": True,
                    "outtmpl": str(out_dir / "%(title).80s [%(id)s].%(ext)s"),
                    "format": "best", "merge_output_format": "mp4",
                    "postprocessors": [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}]}
            suffix = ".mp4"
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            produced = Path(ydl.prepare_filename(info))
        out = produced.with_suffix(suffix)
        return out if out.exists() else produced
    except Exception as yexc:  # noqa: BLE001
        raise ConversionError(
            f"TikTok download failed (resolver: {resolver_err}; yt-dlp: {yexc})."
        ) from yexc
