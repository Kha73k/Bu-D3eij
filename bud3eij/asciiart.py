"""Image -> ASCII Art for Bu D3eij — a Marquee tool.

Pure, GUI-free logic (Pillow + numpy, both already deps) — no model, no download,
fully offline and instant. Maps an image's luminance onto a character ramp at a
chosen output width; optionally inverts the ramp. Exports plain `.txt` or a
rendered `.png` (mono-cell grid; `color=True` tints each glyph with the source
colour on black). Like the other Marquee tools it lives outside
`convert_file`/`CONVERSIONS`.
"""
from __future__ import annotations

from pathlib import Path

from .formats import ConversionError, IMAGE_EXTS, unique_path

# Luminance ramp, ordered brightest -> darkest (a space is the brightest cell).
RAMP = " .:-=+*#%@"
# Characters are ~2x taller than wide, so squash the row count to keep aspect.
ASPECT = 0.5
_MAX_WIDTH = 1000


def _grid(src, width: int, invert: bool, want_color: bool):
    """Return (chars 2-D ndarray, colors (rows,w,3) ndarray|None, width, rows)."""
    import numpy as np
    from PIL import Image

    src = Path(src)
    ext = src.suffix.lower().lstrip(".")
    if ext not in IMAGE_EXTS:
        raise ConversionError(f"ASCII art needs an image; got .{ext or '?'}")

    width = max(8, min(int(width), _MAX_WIDTH))
    try:
        with Image.open(src) as im:
            rgb = im.convert("RGB")
            w, h = rgb.size
            rows = max(1, int(round(width * (h / w) * ASPECT)))
            small = rgb.resize((width, rows))
        gray = np.asarray(small.convert("L"), dtype=np.float32)  # (rows, width)
    except ConversionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ConversionError(f"Could not read the image: {exc}") from exc

    n = len(RAMP) - 1
    norm = (gray / 255.0) if invert else (1.0 - gray / 255.0)
    idx = np.clip(np.rint(norm * n).astype(int), 0, n)
    ramp = np.array(list(RAMP))
    chars = ramp[idx]
    colors = np.asarray(small) if want_color else None
    return chars, colors, width, rows


def image_to_ascii(src, width: int = 120, invert: bool = False) -> str:
    """Return the image rendered as ASCII text (rows joined by newlines)."""
    chars, _, _, _ = _grid(src, width, invert, want_color=False)
    return "\n".join("".join(row) for row in chars)


def _render_png(chars, colors, out: Path) -> Path:
    """Render the character grid to a PNG using a fixed cell grid (mono look)."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    rows, width = chars.shape
    try:
        font = ImageFont.load_default(size=14)
    except TypeError:  # very old Pillow: unsized bitmap default
        font = ImageFont.load_default()

    # Fixed cell sized to the widest ramp glyph so nothing overflows its column.
    cw = 1
    for c in RAMP.strip() + "@":
        try:
            cw = max(cw, int(round(font.getlength(c))))
        except Exception:  # noqa: BLE001
            cw = max(cw, 8)
    try:
        a, b, c2, d = font.getbbox("@")
        ch = max(1, d - b) + 4
    except Exception:  # noqa: BLE001
        ch = 16

    color = colors is not None
    bg = (0, 0, 0) if color else (255, 255, 255)
    default_fg = (220, 220, 220) if color else (0, 0, 0)
    img = Image.new("RGB", (max(1, width * cw), max(1, rows * ch)), bg)
    draw = ImageDraw.Draw(img)
    for y in range(rows):
        for x in range(width):
            glyph = str(chars[y, x])
            if glyph == " ":
                continue
            if color:
                r, g, bl = colors[y, x]
                fg = (int(r), int(g), int(bl))
            else:
                fg = default_fg
            draw.text((x * cw, y * ch), glyph, font=font, fill=fg)
    img.save(out, "PNG")
    return out


def save_ascii(src, out_path, *, width: int = 120, invert: bool = False,
               color: bool = False, overwrite: bool = False) -> Path:
    """Save the ASCII art as `.txt` (plain) or `.png` (rendered); return the path.

    The output format is chosen by `out_path`'s suffix (defaults to `.txt`).
    `color` tints the PNG glyphs with the source colours (ignored for `.txt`).
    Honours the standard overwrite contract: an explicitly chosen path with
    `overwrite=True` is replaced; otherwise the path is de-duplicated.
    """
    out = Path(out_path)
    suffix = out.suffix.lower()
    if suffix not in (".txt", ".png"):
        out = out.with_suffix(".txt")
        suffix = ".txt"
    if not (overwrite and out_path):
        out = unique_path(out)

    if suffix == ".txt":
        text = image_to_ascii(src, width=width, invert=invert)
        out.write_text(text, encoding="utf-8")
        return out

    chars, colors, _, _ = _grid(src, width, invert, want_color=color)
    return _render_png(chars, colors, out)
