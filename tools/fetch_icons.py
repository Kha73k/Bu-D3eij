"""Regenerate the bundled icon assets (dev tool, not shipped).

Fetches SVGs from the Iconify API and rasterizes them to transparent RGBA PNGs:
- file-type icons -> assets/filetypes/  (vscode-icons, MIT)
- UI / nav icons  -> assets/ui/         (lucide, ISC; black silhouettes,
  re-tinted per theme at runtime by App._ui_icon)

Alpha is recovered with the two-background trick (render over white + black),
which works without a system Cairo install.

Dev-only deps (NOT in requirements.txt, NOT bundled):
    pip install svglib rlPyCairo pillow numpy
Note: rlPyCairo prefers cairocffi; if cairocffi is installed it will fail to load
on Windows, so uninstall it (`pip uninstall cairocffi`) to fall back to pycairo.

Run from the project root:  python tools/fetch_icons.py
"""
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg

BASE = "https://api.iconify.design"
ROOT = Path(__file__).resolve().parent.parent / "assets"

FILETYPES = {
    "pdf": "file-type-pdf2", "word": "file-type-word",
    "powerpoint": "file-type-powerpoint", "text": "file-type-text",
    "markdown": "file-type-markdown", "image": "file-type-image",
    "video": "file-type-video", "audio": "file-type-audio",
    "default": "default-file",
}
UI = ["house", "repeat", "clock", "layers", "youtube", "wrench",
      "folder-open", "arrow-right", "arrow-left-right", "sparkles", "download",
      "shield-check", "scan-text", "type"]


def get_svg(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "bud3eij/1.4"})
    return urllib.request.urlopen(req, timeout=30).read()


def _render_on(drawing, bg) -> np.ndarray:
    tmp = Path(tempfile.mktemp(suffix=".png"))
    renderPM.drawToFile(drawing, str(tmp), fmt="PNG", backend="rlPyCairo", bg=bg)
    arr = np.asarray(Image.open(tmp).convert("RGB")).astype(np.float64)
    tmp.unlink(missing_ok=True)
    return arr


def svg_to_rgba_png(svg_bytes: bytes, dest: Path, size: int) -> int:
    tf = Path(tempfile.mktemp(suffix=".svg"))
    tf.write_bytes(svg_bytes)
    d = svg2rlg(str(tf))
    tf.unlink(missing_ok=True)
    s = size / max(d.width, d.height)
    d.scale(s, s)
    d.width *= s
    d.height *= s
    rw = _render_on(d, 0xFFFFFF)  # Rw = C*A + (1-A)
    rb = _render_on(d, 0x000000)  # Rb = C*A
    alpha = (1.0 - (rw - rb) / 255.0).mean(axis=2).clip(0, 1)
    a3 = alpha[..., None]
    color = np.where(a3 > 1e-4, rb / np.maximum(a3, 1e-4), 0).clip(0, 255)
    rgba = np.dstack([color, alpha * 255.0]).astype(np.uint8)
    Image.fromarray(rgba, "RGBA").save(dest)
    return dest.stat().st_size


def main():
    (ROOT / "filetypes").mkdir(parents=True, exist_ok=True)
    (ROOT / "ui").mkdir(parents=True, exist_ok=True)
    for key, name in FILETYPES.items():
        svg_to_rgba_png(get_svg(f"{BASE}/vscode-icons:{name}.svg"),
                        ROOT / "filetypes" / f"{key}.png", 128)
        print("filetypes/" + key)
    for name in UI:
        # force black so svglib draws lucide's stroke="currentColor"
        svg_to_rgba_png(get_svg(f"{BASE}/lucide:{name}.svg?color=%23000000"),
                        ROOT / "ui" / f"{name}.png", 96)
        print("ui/" + name)
    print("done ->", ROOT)


if __name__ == "__main__":
    main()
