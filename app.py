"""Bu D3eij — a simple desktop file converter.

A small CustomTkinter app that converts documents, images and audio/video
files. The conversion logic lives in plain module-level functions so it can be
imported and tested without launching the GUI.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD
# Conversion / download / editing logic now lives in the bud3eij package; these
# re-exports keep `app.<fn>` working for the CLI and headless tests.
from bud3eij.formats import (  # noqa: F401
    AV_EXTS,
    CONVERSIONS,
    ConversionError,
    DOC_EXTS,
    IMAGE_EXTS,
    PILLOW_FORMAT,
    PRESENTATION_EXTS,
    category_of,
    compatible_targets,
    detect_format,
    human_size,
    unique_path,
)
from bud3eij.converters import convert_file  # noqa: F401
from bud3eij.youtube import YT_FORMATS, download_youtube  # noqa: F401
from bud3eij.background import (  # noqa: F401
    BG_MODELS,
    DEFAULT_BG_TIER,
    remove_background,
)
from bud3eij.upscale import (  # noqa: F401
    DEFAULT_TARGET,
    DEFAULT_UPSCALE_TIER,
    TARGETS,
    UPSCALE_MODELS,
    upscale_image,
)
from bud3eij.vanguard import (  # noqa: F401
    CONFIDENCE_TIERS,
    DETECTOR_NAME,
    FLAG_THRESHOLD,
    detect_ai_text,
    extract_document_text,
)
from bud3eij.ocr import DEFAULT_OCR_TIER, OCR_MODELS, extract_text  # noqa: F401
from bud3eij.fontid import identify_font  # noqa: F401
from bud3eij.sonara import (  # noqa: F401
    AUDIO_EXTS,
    MODEL_NAME as SONARA_MODEL,
    STEMS,
    model_is_cached,
    save_stem,
    split_stems,
)
from bud3eij.stemplayer import StemPlayer  # noqa: F401
from bud3eij.nexus import (  # noqa: F401
    COMMON_TIMEZONES,
    CURRENCY_NAMES,
    DEFAULT_UNIT_CATEGORY,
    QR_EC_LEVELS,
    QR_TYPES,
    UNIT_CATEGORIES,
    WIFI_ENCRYPTIONS,
    WORLD_CLOCK_ZONES,
    build_qr_payload,
    convert_currency,
    convert_timezone,
    convert_units,
    currency_label,
    list_timezones,
    load_rates,
    make_qr,
    parse_datetime,
    refresh_rates,
    save_qr,
    tz_offset_str,
)


def resource_path(rel: str) -> str:
    """Absolute path to a bundled resource (works in dev and in a PyInstaller exe)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


# Bundled UI font (Inter). The static TTFs ship under assets/fonts and are
# loaded *privately* (process-only) at startup, so the app renders in Inter
# without requiring a system install — and it works the same in the frozen exe.
FONT_DIR = "assets/fonts"


def _load_app_fonts() -> None:
    """Register the bundled Inter TTFs as private fonts for this process (Windows).

    Uses GDI's AddFontResourceExW with FR_PRIVATE so Tk/Tkinter can resolve the
    'Inter' family without the font being installed system-wide. No-op (and never
    raises) off Windows or if the files are missing.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        directory = resource_path(FONT_DIR)
        for name in os.listdir(directory):
            if name.lower().endswith((".ttf", ".otf")):
                ctypes.windll.gdi32.AddFontResourceExW(
                    ctypes.c_wchar_p(os.path.join(directory, name)), 0x10, 0  # FR_PRIVATE
                )
    except Exception as exc:  # noqa: BLE001 - font is cosmetic; never block startup
        print("Could not load bundled fonts:", exc)


# --------------------------------------------------------------------------- #
# Recent-conversion history (persisted under %LOCALAPPDATA%\Bu D3eij)
# --------------------------------------------------------------------------- #
APP_DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Bu D3eij"
HISTORY_FILE = APP_DATA_DIR / "history.json"
MAX_HISTORY = 100


def load_history() -> list[dict]:
    """Load saved conversion history (newest first). Never raises."""
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        # Drop malformed entries — one non-dict would crash the Recent table.
        return [e for e in data if isinstance(e, dict)]
    except Exception:  # noqa: BLE001 - missing/corrupt file is fine
        return []


def save_history(history: list[dict]) -> None:
    """Persist conversion history. Never raises."""
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print("Could not save history:", exc)


def _setup_frozen_logging() -> None:
    """Give the windowed exe somewhere to print: tee stdout/stderr to a log file.

    In a PyInstaller --windowed build there is no console, so every print()
    and traceback silently vanishes — field failures become undebuggable.
    Never raises; a failure here just keeps the silent behaviour.
    """
    if not getattr(sys, "frozen", False):
        return
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        log_path = APP_DATA_DIR / "app.log"
        if log_path.exists() and log_path.stat().st_size > 1_000_000:
            log_path.unlink()  # crude size cap; this is a diagnostics tail
        stream = open(log_path, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
        stream.write(f"\n--- {APP_NAME} session {datetime.now():%Y-%m-%d %H:%M:%S} ---\n")
        if sys.stdout is None:
            sys.stdout = stream
        if sys.stderr is None:
            sys.stderr = stream
    except Exception:  # noqa: BLE001 - logging must never block startup
        pass


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #
APP_NAME = "Bu D3eij"
NAV_ITEMS = ["Home", "Converter", "Recent", "Batch Convert", "YouTube", "Marquee",
             "Vanguard", "Sonara", "Nexus", "Tools"]

# Logo-derived palette (extracted from AppLogo.png).
RED = "#E11414"
RED_HOVER = "#B4000C"
RED_DEEP = "#8C0008"
RED_BRIGHT = "#F01818"
SIDEBAR_FG = ("#F3EEEF", "#141011")
NAV_TEXT = ("#2A2426", "#F2E9EA")
DROP_BORDER = ("#E11414", "#B4000C")
# Status colors are (light, dark) tuples tuned for WCAG AA (>=4.5:1) on the
# light frames/cards in light mode AND on the dark surfaces in dark mode.
SUCCESS = ("#0E6E39", "#3DD17F")
ERROR = ("#B30F16", "#FF5C61")
WARNING = ("#8A4500", "#F2A65A")  # replaces the old low-contrast "orange"
MUTED = ("#595155", "#9C9194")
# Surfaces for the 1.4 redesign (light, dark).
CARD = ("#FFFFFF", "#252022")          # elevated card / panel
CARD_BORDER = ("#E8E1E2", "#332D30")   # hairline card border
CARD_SOFT = ("#DFD9DA", "#2B2629")     # soft controls card (every tool page)
SURFACE_SOFT = ("#FBECEC", "#221A1B")  # subtle red-tinted hero / accent surface
TEXT = ("#1A1416", "#F2E9EA")          # primary text
SUN_GLYPH = "☀"   # ☀ shown while in Dark mode (click → Light)
MOON_GLYPH = "☾"  # ☾ shown while in Light mode (click → Dark)
APP_VERSION = "4.2"

# Extension -> file-type icon (assets/filetypes/<key>.png). Falls back to "default".
EXT_ICON = {
    "pdf": "pdf", "docx": "word", "doc": "word", "txt": "text", "md": "markdown",
    "pptx": "powerpoint", "ppt": "powerpoint",
    "jpg": "image", "jpeg": "image", "png": "image", "webp": "image",
    "bmp": "image", "gif": "image", "tiff": "image", "tif": "image",
    "mp4": "video", "mp3": "audio", "wav": "audio",
}


def icon_key_for_ext(ext: str) -> str:
    return EXT_ICON.get(ext.lower().lstrip("."), "default")


# Nav label -> UI icon (assets/ui/<name>.png).
NAV_ICONS = {
    "Home": "house", "Converter": "repeat", "Recent": "clock",
    "Batch Convert": "layers", "YouTube": "youtube", "Marquee": "sparkles",
    "Vanguard": "shield-check", "Sonara": "audio-lines", "Nexus": "compass",
    "Tools": "wrench",
}

# Sonara stem rows: stem key -> (display name, assets/ui icon).
SONARA_STEM_META = {
    "vocals": ("Vocals", "mic"),
    "drums": ("Drums", "drum"),
    "bass": ("Bass", "guitar"),
    "other": ("Other", "music"),
}

ctk.set_appearance_mode("Dark")
try:
    ctk.set_default_color_theme(resource_path("bud3eij_theme.json"))
except Exception:  # noqa: BLE001 - fall back to a built-in theme
    ctk.set_default_color_theme("blue")


class GradientButton(ctk.CTkFrame):
    """A flashy, fully animated action button drawn entirely with Pillow.

    CustomTkinter (Tkinter) has no CSS engine — no gradients, sweeping shines,
    glows or transitions — so the button's whole visual is composed as a PIL
    image and swapped onto an inner label every animation tick. Effects:
      * a "living lava" base — the gradient continuously flows through deep
        red → brand red → ember orange → hot pink and back (seamless loop),
      * a top gloss sheen + a light band that sweeps across (the "shine"),
      * an orbiting comet: a white-hot light with a golden trail racing around
        the button's border,
      * rising ember sparkles that twinkle and drift up off the button,
      * a breathing glow when idle; brighter glow + faster everything on hover,
      * a click ripple bursting from the exact press point,
      * while a job runs (``start_busy``/``stop_busy``): flowing diagonal candy
        stripes, a double shine, and animated "<busy_text>…" dots,
      * ``stop_busy(success=True)`` fires a confetti burst + white flash — the
        little dopamine payoff when a job lands,
      * a flat, greyed, motionless look while disabled.

    Drop-in for ``CTkButton``: supports ``grid``, a ``command`` callback and
    ``configure(state="normal"|"disabled")``; ``icon`` is an ``assets/ui`` PNG
    name tinted white. Animation only runs while the widget is mapped (it
    pauses when you switch pages), pauses after IDLE_PAUSE_MS without input,
    and is fully cancelled on destroy, so it never burns CPU in the background.
    """

    # Set True by the App only while the OS window is actively being moved or
    # resized. The animation loop then skips its (window-repainting) compose but
    # keeps its timer alive, so the dragged window's content stops churning and
    # the cursor tracks smoothly; it resumes the instant the drag settles. This
    # is NOT toggled on tab switches (those don't move/resize the root), so a
    # freshly-shown button still paints immediately.
    _suspended = False

    GLOW_PAD = 9      # logical px of glow margin reserved around the body
    RADIUS = 0.34     # corner radius as a fraction of the body height
    # The looping "lava" palette the enabled body flows through (first == last
    # so the horizontal scroll wraps seamlessly).
    LAVA = ("#8C0008", "#E11414", "#FF6A00", "#FF2D55", "#F01818", "#8C0008")

    def __init__(self, master, text: str = "Convert", height: int = 46,
                 command=None, state: str = "normal", icon: str = "sparkles",
                 busy_text: str = "Converting", **_ignored):
        super().__init__(master, fg_color="transparent",
                         height=height + 2 * self.GLOW_PAD)
        self._text = text
        self._command = command
        self._btn_h = height
        self._icon_name = icon
        self._busy_text = busy_text
        self._enabled = state != "disabled"
        self._busy = False
        self._hover = False
        self._press = False
        # animation state
        self._phase = 0.0        # shine sweep position 0..1
        self._color_phase = 0.0  # lava gradient scroll position (wraps at 1)
        self._orbit = 0.0        # border-comet position (wraps at 1)
        self._breath = 0.0       # breathing oscillator (radians)
        self._glow = 0.0         # eased glow amount 0..1
        self._dots = 0           # animated "<busy_text>…" dot count
        self._dot_acc = 0
        self._idle_ms = 0        # ms without hover/press/busy; pauses the loop
        self._particles: list[dict] = []  # embers + confetti
        self._burst = None       # (x, y, t0) click ripple, widget coords
        self._flash_t0 = None    # success flash start time
        self._anim_id = None
        self._resize_id = None
        # cached static layers (rebuilt on size/state change)
        self._stat = None
        self._stat_key = None
        self._cur_img = None  # keep a ref so the PhotoImage isn't GC'd

        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._label = ctk.CTkLabel(self, text="", fg_color="transparent")
        self._label.grid(row=0, column=0, sticky="nsew")

        for w in (self, self._label):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.bind("<Button-1>", self._on_press)
            w.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", self._on_configure)
        self.bind("<Map>", lambda _e: self._start())
        self.bind("<Unmap>", lambda _e: self._stop())
        self.bind("<Destroy>", self._on_destroy)

    # ---- public drop-in API --------------------------------------------- #
    def configure(self, **kwargs):
        if "state" in kwargs:
            self.set_enabled(kwargs.pop("state") != "disabled")
        if "text" in kwargs:
            self._text = kwargs.pop("text")
            self._render()
        if kwargs:
            super().configure(**kwargs)

    def set_enabled(self, on: bool):
        on = bool(on)
        if on == self._enabled:
            return
        self._enabled = on
        if not on:
            self._hover = self._press = False
        if on:
            self._start()
        elif not self._busy:
            self._stop()
        self._render()

    def start_busy(self):
        """Switch to the animated '<busy_text>…' look (clicks ignored)."""
        self._busy = True
        self._phase = 0.0
        self._dots = 0
        self._dot_acc = 0
        self._idle_ms = 0
        self._start()

    def stop_busy(self, success: bool = False):
        """Leave the busy look; with ``success`` fire the confetti celebration."""
        self._busy = False
        if success:
            self._celebrate()
        if self._enabled:
            self._start()
        else:
            self._stop()
        self._render()

    def _celebrate(self):
        """Confetti burst + white flash — the payoff for a finished job."""
        import math
        import random

        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or h <= 1:
            return
        cx, cy = w / 2, h / 2
        for _ in range(26):
            ang = random.uniform(0.0, 2 * math.pi)
            speed = random.uniform(1.0, 3.2)
            self._particles.append({
                "x": cx + math.cos(ang) * 8, "y": cy + math.sin(ang) * 4,
                "vx": math.cos(ang) * speed,
                "vy": math.sin(ang) * speed * 0.7 - 0.9,
                "grav": 0.14,  # confetti falls; also marks it as celebration fx
                "age": 0.0, "life": random.uniform(0.55, 1.0),
                "size": random.choice((3, 4, 6)),
                "color": random.choice(("gold", "white", "pink", "red")),
            })
        self._flash_t0 = time.monotonic()
        self._idle_ms = 0
        self._start()

    # ---- event handlers -------------------------------------------------- #
    IDLE_PAUSE_MS = 12_000  # stop the idle shine after this long without input

    def _on_enter(self, _e):
        if self._enabled and not self._busy:
            self._hover = True
            self._idle_ms = 0
            self._start()  # resume if the idle pause stopped the loop

    def _on_leave(self, _e):
        self._hover = False
        self._press = False

    def _on_press(self, _e):
        if self._enabled and not self._busy:
            self._press = True

    def _on_release(self, e):
        fire = self._press and self._hover and self._enabled and not self._busy
        self._press = False
        if fire:
            # Ripple burst from the exact click point (instant feedback).
            self._burst = (e.x, e.y, time.monotonic())
            self._idle_ms = 0
            self._start()
            if self._command is not None:
                self._command()

    def _on_configure(self, _e):
        if self._resize_id is not None:
            try:
                self.after_cancel(self._resize_id)
            except Exception:  # noqa: BLE001
                pass
        self._resize_id = self.after(60, self._apply_resize)

    def _apply_resize(self):
        self._resize_id = None
        # _ensure_static is keyed on (w, h, alive) and rebuilds itself when the
        # size truly changes; nulling _stat here forced a full (lava strip + blur
        # + glow-dot sprites) rebuild on every <Configure>, e.g. each time the
        # page is shown — pure waste that added latency to CTA tab switches.
        self._render()

    def _on_destroy(self, event):
        if event.widget is self:
            self._stop()

    # ---- animation loop -------------------------------------------------- #
    def _start(self):
        if self._anim_id is not None:
            return
        try:
            if not self.winfo_ismapped():
                return
        except Exception:  # noqa: BLE001
            return
        if not (self._busy or self._enabled):
            self._render()
            return
        self._tick()

    def _stop(self):
        if self._anim_id is not None:
            try:
                self.after_cancel(self._anim_id)
            except Exception:  # noqa: BLE001
                pass
            self._anim_id = None

    def _tick(self):
        import math
        import random
        self._anim_id = None
        if not self.winfo_exists() or not self.winfo_ismapped():
            return
        # While the window is being dragged/resized, don't repaint (it's what
        # makes the moving window feel sluggish); keep the timer alive so the
        # animation resumes seamlessly the moment the drag stops.
        if GradientButton._suspended:
            if self._busy or self._enabled:
                self._anim_id = self.after(90, self._tick)
            return
        if self._busy:
            self._phase = (self._phase + 0.035) % 1.0
            self._color_phase = (self._color_phase + 0.011) % 1.0
            self._orbit = (self._orbit + 0.016) % 1.0
            target_glow = 0.34 + 0.12 * (0.5 + 0.5 * math.sin(self._breath))
            interval, spawn_p, cap = 33, 0.45, 9
        elif self._hover:
            self._phase = (self._phase + 0.022) % 1.0
            self._color_phase = (self._color_phase + 0.009) % 1.0
            self._orbit = (self._orbit + 0.012) % 1.0
            target_glow = 0.62
            interval, spawn_p, cap = 33, 0.65, 12
        else:
            self._phase = (self._phase + 0.012) % 1.0
            self._color_phase = (self._color_phase + 0.0035) % 1.0
            self._orbit = (self._orbit + 0.006) % 1.0
            target_glow = 0.10 + 0.08 * (0.5 + 0.5 * math.sin(self._breath))
            interval, spawn_p, cap = 50, 0.22, 6
        if self._press:
            target_glow = 0.25
        self._breath += 0.10
        self._glow += (target_glow - self._glow) * 0.25
        if self._busy:
            self._dot_acc += interval
            if self._dot_acc >= 400:
                self._dot_acc = 0
                self._dots = (self._dots + 1) % 4
        # ---- particles: spawn rising embers, advance everything ----
        if self._enabled or self._busy:
            embers = sum(1 for p in self._particles if "grav" not in p)
            if embers < cap and random.random() < spawn_p:
                self._spawn_ember()
        dt = interval / 1000.0
        alive = []
        for p in self._particles:
            p["age"] += dt
            if p["age"] >= p["life"]:
                continue
            p["vy"] += p.get("grav", 0.0)
            p["x"] += p["vx"] * dt * 60
            p["y"] += p["vy"] * dt * 60
            alive.append(p)
        self._particles = alive
        # Pause the idle animation after a while (the Converter is the landing
        # page, so a forever-spinning shine is constant CPU/battery drain).
        # Hover, busy, clicks, celebrations or re-mapping resume it.
        celebration = (self._burst is not None or self._flash_t0 is not None
                       or any("grav" in p for p in self._particles))
        if self._busy or self._hover or self._press or celebration:
            self._idle_ms = 0
        else:
            self._idle_ms += interval
            if self._idle_ms >= self.IDLE_PAUSE_MS:
                self._particles.clear()  # don't freeze embers mid-air
                self._render()
                return
        self._render()
        if self._busy or self._enabled:
            self._anim_id = self.after(interval, self._tick)

    def _spawn_ember(self):
        """Add one twinkling ember that drifts up off the button body."""
        import random

        scaling = self._get_widget_scaling()
        pad = max(1, int(round(self.GLOW_PAD * scaling)))
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 2 * pad + 12 or h <= 2 * pad:
            return
        self._particles.append({
            "x": random.uniform(pad + 6, w - pad - 6),
            "y": random.uniform(pad + (h - 2 * pad) * 0.35, h - pad - 4),
            "vx": random.uniform(-0.15, 0.15),
            "vy": random.uniform(-0.5, -0.22),
            "age": 0.0, "life": random.uniform(0.55, 1.1),
            "size": random.choice((3, 4)),
            "color": random.choice(("gold", "gold", "white")),
        })

    # ---- rendering ------------------------------------------------------- #
    @staticmethod
    def _load_font(px: int):
        from PIL import ImageFont
        px = max(8, px)
        # Prefer the bundled Inter (matches the app UI font); fall back to Segoe UI.
        for rel in ("assets/fonts/Inter-SemiBold.ttf", "assets/fonts/Inter-Bold.ttf"):
            try:
                return ImageFont.truetype(resource_path(rel), px)
            except Exception:  # noqa: BLE001
                continue
        fonts_dir = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
        for name in ("segoeuib.ttf", "seguisb.ttf", "arialbd.ttf"):
            try:
                return ImageFont.truetype(os.path.join(fonts_dir, name), px)
            except Exception:  # noqa: BLE001
                continue
        try:
            return ImageFont.truetype("arialbd.ttf", px)
        except Exception:  # noqa: BLE001
            return ImageFont.load_default()

    def _load_icon(self, px: int):
        try:
            from PIL import Image

            s = Image.open(
                resource_path(f"assets/ui/{self._icon_name}.png")).convert("RGBA")
            white = Image.new("RGBA", s.size, (255, 255, 255, 0))
            white.putalpha(s.split()[3])
            scale = px / max(white.size)
            return white.resize((max(1, int(white.width * scale)),
                                 max(1, int(white.height * scale))))
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _hex(color: str) -> tuple[int, int, int]:
        c = color.lstrip("#")
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)

    @classmethod
    def _lava_strip(cls, width: int):
        """A seamless 1-px-high loop of the LAVA palette, doubled for cropping."""
        from PIL import Image

        stops = [cls._hex(c) for c in cls.LAVA]
        row = Image.new("RGB", (width, 1))
        px = row.load()
        n = len(stops) - 1
        for x in range(width):
            t = x / width * n
            i = min(int(t), n - 1)
            f = t - i
            c0, c1 = stops[i], stops[i + 1]
            px[x, 0] = tuple(int(c0[k] + (c1[k] - c0[k]) * f) for k in range(3))
        strip = Image.new("RGB", (width * 2, 1))
        strip.paste(row, (0, 0))
        strip.paste(row, (width, 0))
        return strip

    @staticmethod
    def _glow_dot(rgb: tuple[int, int, int], radius: int):
        """A small radial-falloff glow sprite (RGBA) for particles/orbit."""
        from PIL import Image

        r = max(2, int(radius))
        s = Image.new("RGBA", (2 * r + 1, 2 * r + 1), rgb + (0,))
        px = s.load()
        for y in range(2 * r + 1):
            for x in range(2 * r + 1):
                d = ((x - r) ** 2 + (y - r) ** 2) ** 0.5
                if d <= r:
                    px[x, y] = rgb + (int(235 * (1 - d / r) ** 1.6),)
        return s

    @staticmethod
    def _perimeter(rw: int, rh: int, radius: int):
        """(total_length, point(dist)->(x,y)) along the rounded-rect border."""
        import math

        w, h, r = rw - 1, rh - 1, min(radius, min(rw, rh) // 2)
        sw, sh = max(0, w - 2 * r), max(0, h - 2 * r)
        arc = math.pi * r / 2
        total = 2 * sw + 2 * sh + 4 * arc

        def point(d: float):
            d = d % total
            if d < sw:                       # top edge, left -> right
                return (r + d, 0.0)
            d -= sw
            if d < arc:                      # top-right arc
                a = d / arc * (math.pi / 2)
                return (w - r + math.sin(a) * r, r - math.cos(a) * r)
            d -= arc
            if d < sh:                       # right edge, down
                return (float(w), r + d)
            d -= sh
            if d < arc:                      # bottom-right arc
                a = d / arc * (math.pi / 2)
                return (w - r + math.cos(a) * r, h - r + math.sin(a) * r)
            d -= arc
            if d < sw:                       # bottom edge, right -> left
                return (w - r - d, float(h))
            d -= sw
            if d < arc:                      # bottom-left arc
                a = d / arc * (math.pi / 2)
                return (r - math.sin(a) * r, h - r + math.cos(a) * r)
            d -= arc
            if d < sh:                       # left edge, up
                return (0.0, h - r - d)
            d -= sh
            a = d / arc * (math.pi / 2)      # top-left arc
            return (r - math.cos(a) * r, r - math.sin(a) * r)

        return total, point

    # particle palette: name -> RGB
    _DOT_COLORS = {
        "gold": (255, 196, 77), "white": (255, 255, 255),
        "pink": (255, 45, 85), "red": (255, 92, 97),
    }

    def _ensure_static(self, w: int, h: int, scaling: float):
        # Keyed on "alive": a running (busy) button renders the full lava look
        # even though clicks are disabled — the old design dropped to grey
        # mid-conversion, which is exactly the moment that should feel alive.
        alive = self._enabled or self._busy
        key = (w, h, alive)
        if self._stat_key == key and self._stat is not None:
            return self._stat
        import math

        from PIL import Image, ImageDraw, ImageFilter

        pad = max(1, int(round(self.GLOW_PAD * scaling)))
        rw = max(1, w - 2 * pad)
        rh = max(1, h - 2 * pad)
        radius = max(1, int(rh * self.RADIUS))

        mask = Image.new("L", (rw, rh), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, rw - 1, rh - 1], radius, fill=255)

        # Disabled keeps a flat grey gradient; alive gets the looping lava
        # strip (cropped + scrolled per tick in _compose).
        lava = self._lava_strip(512) if alive else None
        base_grey = None
        if not alive:
            c_l, c_r = (0x6E, 0x66, 0x68), (0x4A, 0x44, 0x46)
            row = Image.new("RGB", (rw, 1))
            rpx = row.load()
            for x in range(rw):
                t = x / max(1, rw - 1)
                rpx[x, 0] = (int(c_l[0] + (c_r[0] - c_l[0]) * t),
                             int(c_l[1] + (c_r[1] - c_l[1]) * t),
                             int(c_l[2] + (c_r[2] - c_l[2]) * t))
            base_grey = row.resize((rw, rh))

        # gloss sheen mask (vertical falloff from the top)
        gloss_peak = 60 if alive else 28
        gcol = Image.new("L", (1, rh))
        gpx = gcol.load()
        for y in range(rh):
            ty = y / max(1, rh - 1)
            gpx[0, y] = int(max(0.0, (0.5 - ty) / 0.5) * gloss_peak)
        gloss = gcol.resize((rw, rh))
        white_rgb = Image.new("RGB", (rw, rh), (255, 255, 255))

        band_w = max(int(rh * 1.4), int(rw * 0.15), 2)
        sb = Image.new("L", (band_w, 1))
        spx = sb.load()
        sigma = max(1.0, band_w * 0.22)
        for x in range(band_w):
            d = (x - band_w / 2) / sigma
            spx[x, 0] = int(150 * math.exp(-0.5 * d * d))
        shine_a = sb.resize((band_w, rh))
        shine_w = Image.new("RGB", (band_w, rh), (255, 255, 255))

        # diagonal candy stripes (busy): an L mask wider than the body so a
        # cropped window can slide for the flow effect
        period = max(18, int(rh * 0.65))
        stripes = Image.new("L", (rw + period, rh), 0)
        sd = ImageDraw.Draw(stripes)
        for x0 in range(-rh - period, rw + 2 * period, period):
            sd.polygon([(x0, rh), (x0 + period // 2, rh),
                        (x0 + period // 2 + rh, 0), (x0 + rh, 0)], fill=30)

        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if alive:
            ImageDraw.Draw(glow).rounded_rectangle(
                [pad - 2, pad - 2, w - pad + 1, h - pad + 1], radius + 2,
                fill=(0xFF, 0x22, 0x22, 255))
            glow = glow.filter(ImageFilter.GaussianBlur(max(2, int(pad * 1.1))))

        # orbit comet sprites: (sprite, lag along the path 0..1), head first
        halo = self._glow_dot(self._DOT_COLORS["gold"], int(5.5 * scaling) + 2)
        head = self._glow_dot((255, 255, 255), int(3.2 * scaling) + 1)
        orbit = [(halo, 0.0), (head, 0.0)]
        for i, alpha in enumerate((170, 120, 80, 48)):
            tr = self._glow_dot(self._DOT_COLORS["gold"],
                                max(2, int((4.2 - i * 0.8) * scaling)))
            tr.putalpha(tr.split()[3].point(lambda v, a=alpha: v * a // 255))
            orbit.append((tr, 0.016 * (i + 1)))

        dots = {(name, size): self._glow_dot(rgb, int(size * scaling))
                for name, rgb in self._DOT_COLORS.items() for size in (3, 4, 6)}

        self._stat = dict(
            pad=pad, rw=rw, rh=rh, mask=mask, lava=lava, base_grey=base_grey,
            gloss=gloss, white_rgb=white_rgb, band_w=band_w,
            shine_a=shine_a, shine_w=shine_w, stripes=stripes, period=period,
            glow=glow, perim=self._perimeter(rw, rh, radius), orbit=orbit,
            dots=dots,
            font=self._load_font(int(round(self._btn_h * 0.36 * scaling))),
            spark=self._load_icon(int(round(self._btn_h * 0.42 * scaling))),
        )
        self._stat_key = key
        return self._stat

    def _compose(self):
        import math

        from PIL import Image, ImageDraw, ImageEnhance

        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1 or h <= 1:
            return None
        scaling = self._get_widget_scaling()
        st = self._ensure_static(w, h, scaling)
        pad, rw, rh = st["pad"], st["rw"], st["rh"]
        now = time.monotonic()
        alive = self._enabled or self._busy

        # ---- body base: scrolling lava (enabled) or flat grey (disabled) ----
        if alive and st["lava"] is not None:
            strip = st["lava"]
            half = strip.width // 2
            off = int((self._color_phase % 1.0) * half)
            body = strip.crop((off, 0, off + half, 1)).resize((rw, rh))
        else:
            body = st["base_grey"].copy()
        body = Image.composite(st["white_rgb"], body, st["gloss"])  # top sheen

        if not alive:
            factor = 1.0
        elif self._press:
            factor = 0.90
        elif self._hover:
            factor = 1.10
        elif self._busy:
            factor = 1.05
        else:
            factor = 1.0 + 0.05 * (0.5 + 0.5 * math.sin(self._breath))
        if abs(factor - 1.0) > 1e-3:
            body = ImageEnhance.Brightness(body).enhance(factor)

        # ---- flowing candy stripes while busy ----
        if self._busy:
            period = st["period"]
            soff = int(self._phase * 2 * period) % period
            window = st["stripes"].crop((period - soff, 0, period - soff + rw, rh))
            body.paste(st["white_rgb"], (0, 0), window)

        # ---- sweeping shine (double band while busy) ----
        if alive:
            bw = st["band_w"]
            spans = [self._phase]
            if self._busy:
                spans.append((self._phase + 0.5) % 1.0)
            for ph in spans:
                sx = int(ph * (rw + bw)) - bw
                body.paste(st["shine_w"], (sx, 0), st["shine_a"])

        # ---- click ripple (expanding ring from the press point) ----
        if self._burst is not None:
            bx, by, t0 = self._burst
            age = now - t0
            dur = 0.45
            if age >= dur:
                self._burst = None
            else:
                frac = age / dur
                cx = min(max(bx - pad, 0), rw)
                cy = min(max(by - pad, 0), rh)
                radius = 6 + frac * rw * 0.55
                ring = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
                rd = ImageDraw.Draw(ring)
                alpha = int(180 * (1 - frac))
                width = max(2, int((4 - 3 * frac) * scaling))
                rd.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                           outline=(255, 240, 220, alpha), width=width)
                body.paste(ring, (0, 0), ring)

        # ---- icon + label (with a soft shadow for punch) ----
        draw = ImageDraw.Draw(body)
        label = (self._busy_text + "." * self._dots) if self._busy else self._text
        txt_color = (255, 255, 255) if alive else (190, 182, 184)
        font, spark = st["font"], st["spark"]
        bbox = draw.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        gap = max(2, int(rh * 0.12))
        show_spark = spark is not None and alive
        sw = (spark.width + gap) if show_spark else 0
        x0 = (rw - (tw + sw)) // 2
        y0 = (rh - th) // 2 - bbox[1]
        if show_spark:
            body.paste(spark, (x0, (rh - spark.height) // 2), spark)
            x0 += spark.width + gap
        if alive:
            draw.text((x0 + 1, y0 + 2), label, font=font, fill=(82, 0, 10))
        draw.text((x0, y0), label, font=font, fill=txt_color)

        body = body.convert("RGBA")
        body.putalpha(st["mask"])

        full = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if self._glow > 0.01 and alive and not self._press:
            g = st["glow"].copy()
            amt = min(1.0, self._glow)
            g.putalpha(g.split()[3].point(lambda v: int(v * amt)))
            full.alpha_composite(g)
        full.alpha_composite(body, (pad, pad))

        # ---- orbiting comet along the border ----
        if alive:
            total, ppt = st["perim"]
            for spr, lag in st["orbit"]:
                px, py = ppt(((self._orbit - lag) % 1.0) * total)
                ox = int(pad + px - spr.width / 2)
                oy = int(pad + py - spr.height / 2)
                if 0 <= ox and 0 <= oy and ox + spr.width <= w and oy + spr.height <= h:
                    full.alpha_composite(spr, (ox, oy))

        # ---- particles: rising embers + celebration confetti ----
        for p in self._particles:
            spr = st["dots"].get((p["color"], p["size"]))
            if spr is None:
                continue
            ox = int(p["x"] - spr.width / 2)
            oy = int(p["y"] - spr.height / 2)
            # alpha_composite rejects out-of-canvas targets; drifting particles
            # simply wink out at the widget edge
            if ox < 0 or oy < 0 or ox + spr.width > w or oy + spr.height > h:
                continue
            tl = p["age"] / p["life"]
            amt = math.sin(math.pi * min(1.0, tl))  # fade in, twinkle out
            im = spr.copy()
            im.putalpha(im.split()[3].point(lambda v, a=amt: int(v * a)))
            full.alpha_composite(im, (ox, oy))

        # ---- success flash (quick white pulse over the body) ----
        if self._flash_t0 is not None:
            age = now - self._flash_t0
            dur = 0.35
            if age >= dur:
                self._flash_t0 = None
            else:
                amt = int(150 * (1 - age / dur))
                fl = Image.new("RGBA", (rw, rh), (255, 255, 255, 0))
                fl.putalpha(st["mask"].point(lambda v, a=amt: v * a // 255))
                full.alpha_composite(fl, (pad, pad))
        return full

    def _render(self):
        if not self.winfo_exists():
            return
        try:
            img = self._compose()
        except Exception as exc:  # noqa: BLE001
            print("convert button render failed:", exc)
            return
        if img is None:
            return
        scaling = self._get_widget_scaling()
        ci = ctk.CTkImage(light_image=img, dark_image=img,
                          size=(img.width / scaling, img.height / scaling))
        self._cur_img = ci
        self._label.configure(image=ci)


class ScrollArea(ctk.CTkFrame):
    """Hosts the page frames so the app stays usable when the window is small.

    A page is gridded into ``.inner`` exactly as before. When the viewport is
    tall enough the page *fills* it (the inner window is stretched to the canvas
    height, so the pages' ``grid_rowconfigure(weight=1)`` still works — no visual
    change). When the window is shrunk below a page's natural height, a scrollbar
    appears and the mouse wheel scrolls the page into view.
    """

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg=self._bg())
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._sb = ctk.CTkScrollbar(self, orientation="vertical",
                                    command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._sb.set)
        self.inner = ctk.CTkFrame(self._canvas, fg_color="transparent")
        self.inner.grid_rowconfigure(0, weight=1)
        self.inner.grid_columnconfigure(0, weight=1)
        self._win = self._canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self._sync_after = None   # coalesces the heavier sync to one call per idle
        self._overflow = False    # last known "content taller than viewport" state
        self._canvas.bind("<Configure>", self._on_canvas)
        self.inner.bind("<Configure>", lambda _e: self._schedule_sync())
        # bind_all so the wheel works wherever the pointer is over a page; the
        # handler no-ops unless the page actually overflows (so inner scrollables
        # — the Recent list, textboxes — keep their own wheel behaviour).
        self._canvas.bind_all("<MouseWheel>", self._on_wheel, add="+")

    def _bg(self) -> str:
        return self._apply_appearance_mode(ctk.ThemeManager.theme["CTk"]["fg_color"])

    def refresh_bg(self):
        self._canvas.configure(bg=self._bg())

    def _on_canvas(self, event):
        # The embedded window's WIDTH must track the canvas immediately so the
        # page fills horizontally as the window resizes. The heavier part —
        # measuring content height, resizing the scrollregion, showing/hiding
        # the scrollbar — is coalesced to one call per idle so a fast resize
        # drag doesn't recompute it on every single pixel (that churn was ~24 ms
        # per resize step with all pages built).
        self._canvas.itemconfigure(self._win, width=event.width)
        self._schedule_sync()

    def _schedule_sync(self):
        if self._sync_after is None:
            self._sync_after = self.after_idle(self._run_sync)

    def _run_sync(self):
        self._sync_after = None
        self._sync()

    def _sync(self, canvas_h: int | None = None):
        if canvas_h is None:
            canvas_h = self._canvas.winfo_height()
        content_h = self.inner.winfo_reqheight()
        height = max(canvas_h, content_h)
        self._canvas.itemconfigure(self._win, height=height)
        self._canvas.configure(
            scrollregion=(0, 0, self._canvas.winfo_width(), height))
        overflow = content_h > canvas_h + 1
        # Only touch the scrollbar's grid when the overflow state actually flips
        # — grid/grid_remove forces a parent relayout, so doing it every pixel
        # made resizing thrash.
        if overflow != self._overflow:
            self._overflow = overflow
            if overflow:
                self._sb.grid(row=0, column=1, sticky="ns", padx=(2, 0))
            else:
                self._sb.grid_remove()
        if not overflow:
            self._canvas.yview_moveto(0.0)

    def to_top(self):
        # A page switch is infrequent and wants a snappy first paint, so size it
        # synchronously (the debounce is only to tame rapid resize-drag events).
        self._canvas.yview_moveto(0.0)
        self._sync()

    def _on_wheel(self, event):
        # Only hijack the wheel when the page overflows the viewport…
        if self._canvas.winfo_height() >= self.inner.winfo_reqheight():
            return
        # …and let a hovered Text widget that can still scroll keep its wheel.
        w = event.widget
        if isinstance(w, tk.Text):
            try:
                if w.yview() != (0.0, 1.0):
                    return
            except Exception:  # noqa: BLE001
                pass
        self._canvas.yview_scroll(int(-event.delta / 120), "units")


class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        # Enable native drag & drop on a CustomTkinter root.
        self.TkdndVersion = TkinterDnD._require(self)

        # Load + select the UI font (Inter) before any widgets/fonts are built.
        _load_app_fonts()
        self._init_fonts()

        self.title(APP_NAME)
        self.geometry("1000x680")
        self.minsize(880, 600)
        self._set_window_icon()

        self.selected_file: Path | None = None
        self.export_dir: Path | None = None
        self.batch_files: list[Path] = []
        self.marquee_file: Path | None = None
        self.upscale_file: Path | None = None
        self.vanguard_file: Path | None = None
        self.vg_ocr_file: Path | None = None
        self.vg_font_file: Path | None = None
        self.sonara_file: Path | None = None
        self.sonara_player = None            # StemPlayer while stems are loaded
        self.sonara_result: dict | None = None  # last split_stems result
        self.nx_rates: dict | None = None    # loaded currency rate table (lazy)
        self.nx_qr_logo: Path | None = None  # optional QR centre-logo image
        self.nx_qr_image = None              # last rendered QR PIL image (for copy)
        self._nxc_after = None               # converter live-recompute debounce
        self._nxq_after = None               # QR live-preview debounce
        self.batch_export_dir: Path | None = None
        self.history: list[dict] = load_history()
        self.appearance_mode = "Dark"  # toggled by the sun/moon button
        self._icon_cache: dict = {}  # (kind, name, size, colors) -> CTkImage
        self._current_frame = ""     # set by show_frame
        self._last_dirs: dict[str, str] = {}  # last-used folder per dialog
        self._active_jobs = 0        # running worker threads (close guard)
        self._convert_run = 0        # generation counter: Clear invalidates a run
        self._vg_run = 0             # generation counter: Reset invalidates a run
        self._vg_detecting = False   # a Vanguard detect worker is in flight
        self._sn_run = 0             # generation counter for Sonara splits
        self._sn_tick_after = None   # playback-position updater after() handle
        self._sn_slider_drag = False # True while the tick loop writes the slider
        self._recent_dirty = True    # rebuild the Recent table only when changed
        self._appearance_stale: set[str] = set()  # built pages that missed a theme toggle
        self._win_geom = None        # last (x,y,w,h); detects real move/resize
        self._anim_resume_id = None  # debounce handle for resuming button anims

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_frames()
        self.show_frame("Converter")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        # Pause the animated buttons while the window is actively dragged/resized
        # so the moving window's content stops churning (smoother cursor).
        self.bind("<Configure>", self._on_root_configure, add="+")

    # ---- animation throttling while the window is dragged ----------------- #
    def _on_root_configure(self, event):
        # Only the root's own geometry change matters (child <Configure> events
        # don't trigger this binding). Compare x/y/w/h so an unchanged event is
        # ignored — and crucially, tab switches never move/resize the root, so
        # this never fires for them.
        if event.widget is not self:
            return
        geom = (self.winfo_x(), self.winfo_y(), event.width, event.height)
        if geom == self._win_geom:
            return
        self._win_geom = geom
        GradientButton._suspended = True
        if self._anim_resume_id is not None:
            try:
                self.after_cancel(self._anim_resume_id)
            except Exception:  # noqa: BLE001
                pass
        self._anim_resume_id = self.after(130, self._resume_animations)

    def _resume_animations(self):
        self._anim_resume_id = None
        GradientButton._suspended = False

    def _set_window_icon(self):
        self._icon_path = resource_path("AppLogo.ico")
        if not os.path.exists(self._icon_path):
            return
        self._apply_icon()
        # Re-apply shortly after startup (CustomTkinter sets its own icon late).
        self.after(300, self._apply_icon)

    def _apply_icon(self):
        try:
            if self.winfo_exists():
                self.iconbitmap(self._icon_path)
        except Exception as exc:  # noqa: BLE001
            print("Could not set window icon:", exc)

    def _load_logo(self, name: str, width: int):
        """Load a logo as a width-scaled CTkImage, or None on failure."""
        try:
            from PIL import Image

            img = Image.open(resource_path(name))
            w, h = img.size
            return ctk.CTkImage(
                light_image=img, dark_image=img, size=(width, int(width * h / w))
            )
        except Exception as exc:  # noqa: BLE001
            print("Could not load logo", name, ":", exc)
            return None

    # ---- fonts ----------------------------------------------------------- #
    def _init_fonts(self) -> None:
        """Pick the UI font family and weight map from what Tk can actually see.

        Prefers Inter (its Medium/SemiBold faces register as their own Tk
        families); falls back to IBM Plex Sans, then Segoe UI. Each role maps to
        a (family, weight) pair so the hierarchy survives even if Inter is
        missing (semibold/medium degrade to the base family's bold/regular).
        """
        import tkinter.font as tkfont

        try:
            families = set(tkfont.families())
        except Exception:  # noqa: BLE001
            families = set()

        if "Inter" in families:
            base = "Inter"
            medium = "Inter Medium" if "Inter Medium" in families else "Inter"
            semibold = "Inter SemiBold" if "Inter SemiBold" in families else "Inter"
            self._font_spec = {
                "regular": (base, "normal"),
                "medium": (medium, "normal"),
                "semibold": (semibold, "normal"),
                "bold": (base, "bold"),
            }
        else:
            base = "IBM Plex Sans" if "IBM Plex Sans" in families else (
                "Segoe UI" if "Segoe UI" in families else None)
            # No dedicated medium/semibold faces -> keep the hierarchy via weight.
            self._font_spec = {
                "regular": (base, "normal"),
                "medium": (base, "normal"),
                "semibold": (base, "bold"),
                "bold": (base, "bold"),
            }
        # Make default-font widgets (entries, menus, etc.) use the same family.
        if base:
            try:
                ctk.ThemeManager.theme["CTkFont"]["family"] = base
            except Exception:  # noqa: BLE001
                pass

    def _font(self, size: int = 13, weight: str = "regular") -> ctk.CTkFont:
        """A CTkFont in the app UI family at the given role weight.

        weight is a role: 'regular' (400, body), 'medium' (500, labels),
        'semibold' (600, headings/CTAs), or 'bold'.
        """
        family, ctk_weight = self._font_spec.get(weight, self._font_spec["regular"])
        if family:
            return ctk.CTkFont(family=family, size=size, weight=ctk_weight)
        return ctk.CTkFont(size=size, weight=ctk_weight)

    # ---- icons ----------------------------------------------------------- #
    @staticmethod
    def _hex_rgb(color: str) -> tuple[int, int, int]:
        c = color.lstrip("#")
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)

    def _filetype_icon(self, ext: str, size: int = 36):
        """Colored file-type badge (CTkImage) for a file extension. Cached."""
        key = ("ft", icon_key_for_ext(ext), size)
        if key in self._icon_cache:
            return self._icon_cache[key]
        try:
            from PIL import Image

            img = Image.open(resource_path(f"assets/filetypes/{key[1]}.png")).convert("RGBA")
            w, h = img.size
            scale = size / max(w, h)
            ci = ctk.CTkImage(light_image=img, dark_image=img,
                              size=(int(w * scale), int(h * scale)))
        except Exception as exc:  # noqa: BLE001
            print("icon load failed", ext, exc)
            ci = None
        self._icon_cache[key] = ci
        return ci

    def _ui_icon(self, name: str, size: int = 18,
                 light: str = "#3A3436", dark: str = "#D8CFD1"):
        """Monochrome UI icon re-tinted per theme (CTkImage). Cached."""
        key = ("ui", name, size, light, dark)
        if key in self._icon_cache:
            return self._icon_cache[key]
        try:
            from PIL import Image

            base = Image.open(resource_path(f"assets/ui/{name}.png")).convert("RGBA")
            alpha = base.split()[3]

            def tint(hexcolor: str) -> "Image.Image":
                solid = Image.new("RGBA", base.size, self._hex_rgb(hexcolor) + (0,))
                solid.putalpha(alpha)
                return solid

            ci = ctk.CTkImage(light_image=tint(light), dark_image=tint(dark),
                              size=(size, size))
        except Exception as exc:  # noqa: BLE001
            print("ui icon load failed", name, exc)
            ci = None
        self._icon_cache[key] = ci
        return ci

    # ---- layout ---------------------------------------------------------- #
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=SIDEBAR_FG)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(len(NAV_ITEMS) + 1, weight=1)

        header = ctk.CTkFrame(sidebar, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(20, 14))
        self.sidebar_logo = self._load_logo("DashboardLogo.png", 150)
        if self.sidebar_logo is not None:
            ctk.CTkLabel(header, text="", image=self.sidebar_logo).pack(anchor="w")
        else:
            ctk.CTkLabel(
                header, text=APP_NAME, font=self._font(20, "semibold")
            ).pack(anchor="w")

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for i, name in enumerate(NAV_ITEMS, start=1):
            btn = ctk.CTkButton(
                sidebar, text="  " + name, anchor="w", height=40, corner_radius=8,
                image=self._ui_icon(NAV_ICONS[name], 18), compound="left",
                fg_color="transparent", hover_color=("#EBE0E1", "#2A2426"),
                text_color=NAV_TEXT,
                command=lambda n=name: self.show_frame(n),
            )
            btn.grid(row=i, column=0, padx=12, pady=3, sticky="ew")
            self.nav_buttons[name] = btn

        # Sun / moon appearance toggle (shows the mode you can switch to).
        self.theme_toggle = ctk.CTkButton(
            sidebar, text=SUN_GLYPH, width=44, height=36, corner_radius=18,
            font=ctk.CTkFont(family="Segoe UI Symbol", size=18),
            fg_color="transparent", border_width=1, border_color=MUTED,
            hover_color=RED_HOVER, text_color=NAV_TEXT,
            command=self._toggle_appearance,
        )
        self.theme_toggle.grid(row=len(NAV_ITEMS) + 2, column=0, padx=15, pady=20, sticky="s")

    def _build_frames(self):
        # The page host scrolls when the window is shrunk below a page's height
        # and fills the viewport otherwise (see ScrollArea). Pages grid into
        # `_frame_container` (the scroll area's inner frame) exactly as before.
        self._scroll_area = ScrollArea(self)
        self._scroll_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self._frame_container = self._scroll_area.inner
        # Frames are built lazily on first show (see show_frame). Building all
        # nine up front made startup slow and — because set_appearance_mode
        # redraws every registered widget — inflated the Light/Dark toggle with
        # the cost of sections the user may never open. Now only visited frames
        # exist, so the toggle's work set is exactly what's been used.
        self._frame_builders = {
            "Converter": self._build_converter,
            "Batch Convert": self._build_batch,
            "YouTube": self._build_youtube,
            "Marquee": self._build_marquee,
            "Vanguard": self._build_vanguard,
            "Sonara": self._build_sonara,
            "Nexus": self._build_nexus,
            "Home": self._build_home,
            "Recent": self._build_recent,
            "Tools": self._build_tools,
        }
        self.frames: dict[str, ctk.CTkFrame] = {}

    # ---- worker-job bookkeeping (close guard) ----------------------------- #
    def _job_started(self):
        self._active_jobs += 1

    def _job_finished(self):
        self._active_jobs = max(0, self._active_jobs - 1)

    def _on_close(self):
        if self._active_jobs > 0 and not messagebox.askyesno(
            APP_NAME,
            "A job is still running — quit anyway?\n"
            "Its output may be incomplete.",
        ):
            return
        if self.sonara_player is not None:  # release the audio device
            self.sonara_player.close()
        self.destroy()

    def show_frame(self, name: str):
        frame = self.frames.get(name)
        if frame is None:
            # First visit — build the frame now (lazy; see _build_frames).
            builder = self._frame_builders.get(name)
            if builder is None:
                return
            frame = builder(self._frame_container)
            frame.grid(row=0, column=0, sticky="nsew")
            self.frames[name] = frame
        # If this page missed a theme toggle while it was hidden (its widgets
        # were detached from CustomTkinter's redraw to keep the toggle fast),
        # bring it up to the current mode before it's shown.
        if name in self._appearance_stale:
            self._appearance_stale.discard(name)
            self._refresh_page_appearance(frame)
        self._current_frame = name
        # grid/grid_remove (not tkraise) so a CTkScrollableFrame raises reliably
        # above the plain sibling frames sharing the same grid cell.
        for f in self.frames.values():
            if f is not frame:
                f.grid_remove()
        frame.grid()
        for n, btn in self.nav_buttons.items():
            active = n == name
            icon = (self._ui_icon(NAV_ICONS[n], 18, light="#FFFFFF", dark="#FFFFFF")
                    if active else self._ui_icon(NAV_ICONS[n], 18))
            btn.configure(
                fg_color=RED if active else "transparent",
                text_color="#FFFFFF" if active else NAV_TEXT,
                image=icon,
            )
        if name == "Recent":
            self._refresh_recent()
        elif name == "Tools":
            self._refresh_tools()
        # New page may be taller/shorter than the last — recompute scroll + top.
        if hasattr(self, "_scroll_area"):
            self._scroll_area.to_top()

    def _toggle_appearance(self):
        """Flip between Dark and Light; the icon shows the mode you can switch to."""
        self.appearance_mode = "Light" if self.appearance_mode == "Dark" else "Dark"
        # ctk.set_appearance_mode redraws *every* registered widget — including
        # the ones on hidden pages — so the cost grew with each tool page opened
        # (~320 ms once all of them were built). Only the page on screen needs
        # to recolour now: detach the hidden built pages from CustomTkinter's
        # appearance tracker for the duration of the toggle, then mark them so
        # they recolour lazily the next time they're shown (see show_frame).
        detached = self._detach_hidden_pages()
        try:
            self._frozen_redraw(lambda: ctk.set_appearance_mode(self.appearance_mode))
        finally:
            self._reattach_pages(detached)
        if hasattr(self, "_scroll_area"):
            self._scroll_area.refresh_bg()  # raw tk.Canvas bg isn't auto-themed
        self.theme_toggle.configure(
            text=SUN_GLYPH if self.appearance_mode == "Dark" else MOON_GLYPH
        )

    @staticmethod
    def _collect_widgets(widget, into: set) -> None:
        into.add(widget)
        for child in widget.winfo_children():
            App._collect_widgets(child, into)

    def _detach_hidden_pages(self) -> list:
        """Remove every hidden built page's widgets from CustomTkinter's
        appearance-mode callback list so the next theme toggle skips them.

        Returns the removed callbacks so they can be re-added afterwards. The
        sidebar, the page on screen, and all the window chrome stay registered,
        so they recolour immediately; the hidden pages are flagged stale and
        recoloured on their next show_frame. Degrades to a no-op (full redraw)
        if CustomTkinter's internals ever move.
        """
        try:
            from customtkinter.windows.widgets.appearance_mode.appearance_mode_tracker \
                import AppearanceModeTracker
        except Exception:  # noqa: BLE001
            return []
        visible = self.frames.get(self._current_frame)
        hidden_widgets: set = set()
        for name, frame in self.frames.items():
            if frame is visible:
                continue
            self._collect_widgets(frame, hidden_widgets)
            self._appearance_stale.add(name)
        if not hidden_widgets:
            return []
        detached = [cb for cb in AppearanceModeTracker.callback_list
                    if getattr(cb, "__self__", None) in hidden_widgets]
        for cb in detached:
            try:
                AppearanceModeTracker.callback_list.remove(cb)
            except ValueError:
                pass
        return detached

    @staticmethod
    def _reattach_pages(detached: list) -> None:
        if not detached:
            return
        try:
            from customtkinter.windows.widgets.appearance_mode.appearance_mode_tracker \
                import AppearanceModeTracker
        except Exception:  # noqa: BLE001
            return
        existing = AppearanceModeTracker.callback_list
        for cb in detached:
            if cb not in existing:
                existing.append(cb)

    def _refresh_page_appearance(self, frame) -> None:
        """Bring a page that missed one or more theme toggles up to the current
        mode by recolouring its whole subtree (cost = that one page)."""
        mode = self.appearance_mode
        stack = [frame]
        while stack:
            w = stack.pop()
            fn = getattr(w, "_set_appearance_mode", None)
            if fn is not None:
                try:
                    fn(mode)
                except Exception:  # noqa: BLE001
                    pass
            stack.extend(w.winfo_children())

    def _frozen_redraw(self, fn):
        """Run `fn` with window painting frozen, then repaint once (no flicker).

        CustomTkinter recolours each widget's canvas individually with no
        double-buffering, so a theme switch visibly "sweeps" across the window —
        it looks like the app is redrawing itself. WM_SETREDRAW suppresses all
        intermediate GDI paints; we re-enable and force a single clean repaint of
        the whole window at the end. Degrades gracefully off Windows / without
        pywin32 (just runs `fn`).
        """
        hwnd = None
        try:
            import win32con
            import win32gui
            # Freeze Tk's CONTENT window (winfo_id), NOT the framed top-level
            # (GA_ROOT). Freezing the framed window also froze the OS-drawn title
            # bar, so the minimize/close buttons went blank until the next OS
            # repaint. The content HWND holds all the CTk widgets; the caption is
            # the parent's and stays live.
            hwnd = self.winfo_id()
            win32gui.SendMessage(hwnd, win32con.WM_SETREDRAW, False, 0)
        except Exception:  # noqa: BLE001
            hwnd = None
        try:
            fn()
            if hwnd is not None:
                self.update_idletasks()  # recompute layout while paints are held
        finally:
            if hwnd is not None:
                try:
                    import win32con
                    import win32gui
                    win32gui.SendMessage(hwnd, win32con.WM_SETREDRAW, True, 0)
                    win32gui.RedrawWindow(
                        hwnd, None, None,
                        win32con.RDW_INVALIDATE | win32con.RDW_ALLCHILDREN
                        | win32con.RDW_UPDATENOW | win32con.RDW_ERASE,
                    )
                except Exception:  # noqa: BLE001
                    pass

    def _section_header(self, parent, title: str, subtitle: str = ""):
        head = ctk.CTkFrame(parent, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        ctk.CTkLabel(
            head, text=title, font=self._font(24, "semibold"), text_color=RED
        ).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(head, text=subtitle, text_color=MUTED).pack(anchor="w", pady=(2, 0))

    def _bind_click(self, widget, command) -> None:
        """Make a whole card clickable (widget + all descendants)."""
        widget.bind("<Button-1>", lambda _e: command())
        try:
            widget.configure(cursor="hand2")
        except Exception:  # noqa: BLE001 - some widgets reject cursor
            pass
        for child in widget.winfo_children():
            self._bind_click(child, command)

    def _popular_card(self, parent, col, from_ext, to_ext, label):
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=12,
                            border_width=1, border_color=CARD_BORDER)
        card.grid(row=0, column=col, padx=5, sticky="ew")
        icons = ctk.CTkFrame(card, fg_color="transparent")
        icons.pack(padx=16, pady=(16, 6))
        ctk.CTkLabel(icons, text="", image=self._filetype_icon(from_ext, 30)).pack(side="left")
        ctk.CTkLabel(icons, text="", image=self._ui_icon("arrow-right", 16)).pack(side="left", padx=9)
        ctk.CTkLabel(icons, text="", image=self._filetype_icon(to_ext, 30)).pack(side="left")
        ctk.CTkLabel(
            card, text=label, text_color=TEXT, font=self._font(12, "medium"),
        ).pack(pady=(0, 14))
        self._bind_click(card, lambda: self.show_frame("Converter"))

    def _build_home(self, parent) -> ctk.CTkFrame:
        # NOTE: must be opaque — a transparent frame lets the stacked sibling
        # frame (same grid cell) show through when raised.
        frame = ctk.CTkScrollableFrame(parent, fg_color=("#EAE5E6", "#231F21"))
        frame.grid_columnconfigure(0, weight=1)

        # ---- hero ----
        hero = ctk.CTkFrame(frame, fg_color=SURFACE_SOFT, corner_radius=18)
        hero.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 16))
        hero.grid_columnconfigure(0, weight=1)
        text = ctk.CTkFrame(hero, fg_color="transparent")
        text.grid(row=0, column=0, sticky="w", padx=(28, 12), pady=(28, 24))
        ctk.CTkLabel(
            text, text="Welcome", anchor="w", text_color=TEXT,
            font=self._font(30, "semibold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            text, text="boss", anchor="w", text_color=RED,
            font=self._font(30, "semibold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            text, text="Time to work",
            anchor="w", justify="left", text_color=MUTED, font=ctk.CTkFont(size=13),
        ).pack(anchor="w", pady=(8, 16))
        actions = ctk.CTkFrame(text, fg_color="transparent")
        actions.pack(anchor="w")
        ctk.CTkButton(
            actions, text=" Convert a File", height=42, image=self._ui_icon("repeat", 18, "#FFFFFF", "#FFFFFF"),
            compound="left", font=self._font(14, "semibold"),
            command=lambda: self.show_frame("Converter"),
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            actions, text=" Batch", height=42, image=self._ui_icon("layers", 18),
            compound="left", fg_color="transparent", border_width=2, border_color=RED,
            text_color=TEXT, hover_color=("#F1DDDD", "#2E2A2C"),
            command=lambda: self.show_frame("Batch Convert"),
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            actions, text=" YouTube", height=42, image=self._ui_icon("youtube", 18),
            compound="left", fg_color="transparent", border_width=2, border_color=RED,
            text_color=TEXT, hover_color=("#F1DDDD", "#2E2A2C"),
            command=lambda: self.show_frame("YouTube"),
        ).pack(side="left")
        # Second row: the newer sections deserve a front-door too.
        actions2 = ctk.CTkFrame(text, fg_color="transparent")
        actions2.pack(anchor="w", pady=(10, 0))
        ctk.CTkButton(
            actions2, text=" Marquee", height=42, image=self._ui_icon("sparkles", 18),
            compound="left", fg_color="transparent", border_width=2, border_color=RED,
            text_color=TEXT, hover_color=("#F1DDDD", "#2E2A2C"),
            command=lambda: self.show_frame("Marquee"),
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            actions2, text=" Vanguard", height=42, image=self._ui_icon("shield-check", 18),
            compound="left", fg_color="transparent", border_width=2, border_color=RED,
            text_color=TEXT, hover_color=("#F1DDDD", "#2E2A2C"),
            command=lambda: self.show_frame("Vanguard"),
        ).pack(side="left")

        cluster = ctk.CTkFrame(hero, fg_color="transparent")
        cluster.grid(row=0, column=1, padx=(8, 26), pady=20, sticky="e")
        for idx, ext in enumerate(["pdf", "docx", "pptx", "mp4", "jpg", "mp3"]):
            r, c = divmod(idx, 3)
            tile = ctk.CTkFrame(cluster, width=60, height=60, fg_color=CARD, corner_radius=14)
            tile.grid(row=r, column=c, padx=6, pady=6)
            tile.grid_propagate(False)
            tile.grid_rowconfigure(0, weight=1)
            tile.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(tile, text="", image=self._filetype_icon(ext, 34)).grid(row=0, column=0)

        # ---- popular conversions ----
        ctk.CTkLabel(
            frame, text="Popular conversions", anchor="w", text_color=TEXT,
            font=self._font(15, "semibold"),
        ).grid(row=1, column=0, sticky="w", padx=10, pady=(2, 8))
        pop = ctk.CTkFrame(frame, fg_color="transparent")
        pop.grid(row=2, column=0, sticky="ew", padx=4, pady=(0, 16))
        for c in range(4):
            pop.grid_columnconfigure(c, weight=1, uniform="pop")
        for col, (fe, te, lbl) in enumerate([
            ("pdf", "docx", "PDF to Word"), ("docx", "pdf", "Word to PDF"),
            ("mp4", "mp3", "MP4 to MP3"), ("jpg", "png", "JPG to PNG"),
        ]):
            self._popular_card(pop, col, fe, te, lbl)

        # ---- supported formats ----
        ctk.CTkLabel(
            frame, text="Supported formats", anchor="w", text_color=TEXT,
            font=self._font(15, "semibold"),
        ).grid(row=3, column=0, sticky="w", padx=10, pady=(2, 8))
        card = ctk.CTkFrame(frame, fg_color=CARD, corner_radius=12,
                            border_width=1, border_color=CARD_BORDER)
        card.grid(row=4, column=0, sticky="ew", padx=6, pady=(0, 16))
        card.grid_columnconfigure(2, weight=1)
        for r, (rep_ext, cat, fmts) in enumerate([
            ("txt", "Documents", "PDF · DOCX · TXT · MD"),
            ("pptx", "Presentations", "PPTX"),
            ("jpg", "Images", "JPG · PNG · WEBP · BMP · GIF · TIFF"),
            ("mp4", "Audio / Video", "MP4 · MP3 · WAV"),
        ]):
            ctk.CTkLabel(card, text="", image=self._filetype_icon(rep_ext, 26)).grid(
                row=r, column=0, padx=(16, 10), pady=10)
            ctk.CTkLabel(
                card, text=cat, font=self._font(12, "medium"),
                text_color=TEXT, width=110, anchor="w",
            ).grid(row=r, column=1, sticky="w", pady=10)
            ctk.CTkLabel(card, text=fmts, text_color=MUTED, anchor="w").grid(
                row=r, column=2, sticky="w", padx=(0, 16), pady=10)
        return frame

    def _build_tools(self, parent) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent)
        frame.grid_columnconfigure(0, weight=1)
        self._section_header(frame, "Tools", "Status and utilities.")

        card = ctk.CTkFrame(frame, fg_color=CARD_SOFT, corner_radius=12)
        card.grid(row=1, column=0, sticky="ew", padx=24, pady=(4, 12))
        card.grid_columnconfigure(1, weight=1)

        self.tools_values: dict[str, ctk.CTkLabel] = {}
        for r, label in enumerate(["FFmpeg (audio / video)", "History", "Version"]):
            top = 14 if r == 0 else 6
            ctk.CTkLabel(
                card, text=label, font=self._font(12, "medium"), anchor="w",
            ).grid(row=r, column=0, sticky="w", padx=(18, 12), pady=(top, 6))
            value = ctk.CTkLabel(card, text="", text_color=MUTED, anchor="w")
            value.grid(row=r, column=1, sticky="w", padx=(0, 18), pady=(top, 6))
            self.tools_values[label] = value

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.grid(row=2, column=0, sticky="w", padx=24, pady=(2, 12))
        ctk.CTkButton(
            btns, text="Open history folder", width=170,
            command=lambda: self.open_folder(HISTORY_FILE),
        ).grid(row=0, column=0, padx=(0, 10))
        ctk.CTkButton(
            btns, text="Reveal last output", width=170,
            fg_color="gray50", hover_color="gray40", command=self._open_last_output,
        ).grid(row=0, column=1, padx=(0, 10))
        ctk.CTkButton(
            btns, text="Unload AI models", width=170,
            fg_color="gray50", hover_color="gray40", command=self._unload_models,
        ).grid(row=0, column=2)

        self.tools_note = ctk.CTkLabel(
            frame, text="", text_color=MUTED, anchor="w", justify="left",
            wraplength=620,
        )
        self.tools_note.grid(row=3, column=0, sticky="w", padx=24, pady=(0, 12))

        self._refresh_tools()
        return frame

    def _refresh_tools(self):
        """Recompute the Tools status rows (they go stale while the app runs)."""
        if not hasattr(self, "tools_values"):
            return
        ffmpeg_ok = shutil.which("ffmpeg") is not None
        self.tools_values["FFmpeg (audio / video)"].configure(
            text="Available" if ffmpeg_ok else "Not found on PATH",
            text_color=SUCCESS if ffmpeg_ok else WARNING,
        )
        self.tools_values["History"].configure(
            text=f"{len(self.history)} conversion(s) recorded")
        self.tools_values["Version"].configure(text=f"Bu D3eij {APP_VERSION}")

    def _unload_models(self):
        """Free the cached AI sessions (rembg, upscaler, detector, OCR, font ID)."""
        if self._active_jobs > 0:
            self.tools_note.configure(
                text="Can't unload while a job is running — try again when it finishes.",
                text_color=WARNING)
            return
        from bud3eij import background, fontid, ocr, sonara, upscale, vanguard

        background.unload_models()
        upscale.unload_models()
        vanguard.unload_models()
        ocr.unload_models()
        fontid.unload_models()
        sonara.unload_models()
        import gc

        gc.collect()
        self.tools_note.configure(
            text="AI models unloaded — they'll reload automatically on next use.",
            text_color=SUCCESS)

    def _open_last_output(self):
        for entry in self.history:
            if entry.get("ok") and entry.get("output"):
                self.open_folder(entry["output"])
                return
        self.tools_note.configure(
            text="No successful output to reveal yet.", text_color=MUTED)

    # ---- recent view ----------------------------------------------------- #
    def _recent_columns(self, widget) -> None:
        """Apply the shared table column layout to a header/row frame."""
        widget.grid_columnconfigure(0, weight=1)          # File (expands)
        for col, minw in ((1, 64), (2, 64), (3, 120), (4, 110), (5, 140)):
            widget.grid_columnconfigure(col, minsize=minw)

    def _build_recent(self, parent) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(3, weight=1)
        self._section_header(frame, "Recent", "Your conversion history.")

        bar = ctk.CTkFrame(frame, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=24)
        bar.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            bar, text="Clear history", width=120, height=32,
            image=self._ui_icon("layers", 16), compound="left",
            fg_color=("#E7DFE0", "#2E2A2C"), hover_color=("#D9CFD1", "#3A3438"),
            text_color=TEXT, command=self.clear_history,
        ).grid(row=0, column=1, sticky="e")

        head = ctk.CTkFrame(frame, fg_color="transparent")
        head.grid(row=2, column=0, sticky="ew", padx=30, pady=(12, 0))
        self._recent_columns(head)
        for col, title in enumerate(["File", "From", "To", "Status", "Time", ""]):
            ctk.CTkLabel(
                head, text=title, text_color=MUTED, anchor="w",
                font=self._font(11, "medium"),
            ).grid(row=0, column=col, sticky="w", padx=(2, 6))

        self.recent_scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        self.recent_scroll.grid(row=3, column=0, sticky="nsew", padx=24, pady=(4, 12))
        self.recent_scroll.grid_columnconfigure(0, weight=1)
        self._refresh_recent()
        return frame

    def _refresh_recent(self):
        if not hasattr(self, "recent_scroll"):
            return
        # Rebuilding the table is expensive (each row is ~12 CTk widgets, and on
        # a full 100-entry history that's seconds of widget churn). show_frame
        # calls this on every visit, so skip the work unless the history has
        # actually changed since the last build.
        if not self._recent_dirty:
            return
        for child in self.recent_scroll.winfo_children():
            child.destroy()
        if not self.history:
            ctk.CTkLabel(
                self.recent_scroll, text="No conversions yet — your results will appear here.",
                text_color=MUTED,
            ).grid(row=0, column=0, sticky="w", padx=10, pady=16)
            self._recent_dirty = False
            return
        for i, entry in enumerate(self.history):
            self._recent_row(i, entry)
        self._recent_dirty = False

    def _recent_row(self, i: int, entry: dict):
        src = entry.get("source", "") or ""
        out = entry.get("output", "") or ""
        ok = bool(entry.get("ok"))
        is_url = src.lower().startswith(("http://", "https://"))

        name = Path(out).name if (ok and out) else (
            self._ellipsize(src, 44) if is_url else (Path(src).name or "?"))
        from_ext = "URL" if is_url else (detect_format(src).upper() or "?")
        to_ext = (detect_format(out).upper() or "?") if out else "?"
        icon_ext = (detect_format(out) if (ok and out) else detect_format(src)) or "x"

        row = ctk.CTkFrame(self.recent_scroll, fg_color=CARD, corner_radius=8)
        row.grid(row=i, column=0, sticky="ew", pady=3, padx=2)
        self._recent_columns(row)

        fcell = ctk.CTkFrame(row, fg_color="transparent")
        fcell.grid(row=0, column=0, sticky="ew", padx=(10, 6), pady=8)
        ic = self._filetype_icon(icon_ext, 24)
        if ic is not None:
            ctk.CTkLabel(fcell, text="", image=ic).pack(side="left", padx=(0, 8))
        txt = ctk.CTkFrame(fcell, fg_color="transparent")
        txt.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(txt, text=self._ellipsize(name, 46), anchor="w", text_color=TEXT).pack(anchor="w")
        if not ok and entry.get("error"):
            ctk.CTkLabel(
                txt, text=self._ellipsize(str(entry["error"]), 60), anchor="w",
                text_color=MUTED, font=ctk.CTkFont(size=11),
            ).pack(anchor="w")

        ctk.CTkLabel(row, text=from_ext, text_color=MUTED, anchor="w").grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(row, text=to_ext, text_color=TEXT, anchor="w").grid(row=0, column=2, sticky="w")
        ctk.CTkLabel(
            row, text=("✓ Completed" if ok else "✕ Failed"),
            text_color=(SUCCESS if ok else ERROR), anchor="w",
        ).grid(row=0, column=3, sticky="w")
        ctk.CTkLabel(row, text=entry.get("time", ""), text_color=MUTED, anchor="w").grid(
            row=0, column=4, sticky="w")

        if ok and out:
            # Only build the actions frame when it has buttons — an empty
            # CTkFrame keeps its default 200px height and stretches the row.
            act = ctk.CTkFrame(row, fg_color="transparent")
            act.grid(row=0, column=5, sticky="e", padx=(0, 8))
            ctk.CTkButton(
                act, text="Open", width=50, height=26,
                command=lambda p=out: self.open_path(p),
            ).pack(side="left", padx=(0, 6))
            ctk.CTkButton(
                act, text="Folder", width=60, height=26,
                fg_color="transparent", border_width=1, border_color=CARD_BORDER,
                text_color=TEXT, hover_color=("#EBE0E1", "#332D30"),
                command=lambda p=out: self.open_folder(p),
            ).pack(side="left")

    def add_history(self, src, out, ok: bool, error="") -> None:
        entry = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "source": str(src) if src else "",
            "output": str(out) if out else "",
            "ok": bool(ok),
            "error": str(error),
        }
        self.history.insert(0, entry)
        del self.history[MAX_HISTORY:]
        save_history(self.history)
        self._recent_dirty = True
        # Rebuilding the table is expensive (up to 100 rows of widgets); only do
        # it when Recent is actually on screen — show_frame refreshes otherwise.
        if self._current_frame == "Recent":
            self.after(0, self._refresh_recent)

    def clear_history(self):
        if self.history and not messagebox.askyesno(
            APP_NAME, f"Delete all {len(self.history)} history entries?\n"
                      "This can't be undone (the converted files stay on disk)."
        ):
            return
        self.history = []
        save_history(self.history)
        self._recent_dirty = True
        self._refresh_recent()

    def open_path(self, path):
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            print("Open failed:", exc)

    def open_folder(self, path):
        p = Path(path)
        try:
            if p.exists():
                subprocess.Popen(["explorer", "/select,", str(p)])
            else:
                os.startfile(str(p.parent))  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            print("Open folder failed:", exc)

    # ---- converter view -------------------------------------------------- #
    def _build_converter(self, parent) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent)
        frame.grid_columnconfigure(0, weight=1)

        self._section_header(frame, "Converter", "Drop a file, choose a format, convert.")

        # ---- drop zone ----
        # On-theme folder icon from bundled assets (renders in the frozen exe;
        # AppLogo.png was never bundled). Swapped for the file's type icon on drop.
        self.drop_icon = self._ui_icon("folder-open", 46, light=RED, dark=RED_BRIGHT)
        dz = self._build_drop_zone(
            frame, row=1, icon=self.drop_icon, title="Drag & drop a file here",
            hint="or click to browse", on_drop=self.on_drop, on_click=self.browse_file,
        )
        self.drop_zone = dz["zone"]
        self.drop_icon_label = dz["icon"]
        self.drop_primary = dz["primary"]
        self.drop_secondary = dz["secondary"]

        # ---- controls card ----
        card = ctk.CTkFrame(frame, fg_color=CARD_SOFT, corner_radius=12)
        card.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 12))
        card.grid_columnconfigure(0, weight=1)

        fmt = ctk.CTkFrame(card, fg_color="transparent")
        fmt.grid(row=0, column=0, sticky="w", padx=18, pady=(16, 8))
        ctk.CTkLabel(fmt, text="CONVERT FROM", font=self._font(11, "medium"),
                     text_color=MUTED).grid(row=0, column=0, sticky="w", padx=2)
        ctk.CTkLabel(fmt, text="CONVERT TO", font=self._font(11, "medium"),
                     text_color=MUTED).grid(row=0, column=2, sticky="w", padx=(16, 0))
        self.from_menu = ctk.CTkOptionMenu(fmt, values=["-"], state="disabled", width=150)
        self.from_menu.grid(row=1, column=0, pady=(2, 0))
        ctk.CTkLabel(fmt, text="→", font=self._font(22, "semibold"),
                     text_color=RED).grid(row=1, column=1, padx=14)
        self.to_menu = ctk.CTkOptionMenu(fmt, values=["-"], state="disabled", width=150)
        self.to_menu.grid(row=1, column=2, pady=(2, 0))

        exp = ctk.CTkFrame(card, fg_color="transparent")
        exp.grid(row=1, column=0, sticky="ew", padx=18, pady=(6, 4))
        exp.grid_columnconfigure(0, weight=1)
        self.export_label = ctk.CTkLabel(
            exp, text="Output: next to the source file", text_color=MUTED, anchor="w",
        )
        self.export_label.grid(row=0, column=0, sticky="ew", padx=(2, 8))
        self.export_btn = ctk.CTkButton(
            exp, text="Choose Folder", width=130, command=self.choose_export_path
        )
        self.export_btn.grid(row=0, column=1, padx=(0, 8))
        self.clear_btn = ctk.CTkButton(
            exp, text="Clear", width=80, fg_color="gray50",
            hover_color="gray40", command=self.clear_converter,
        )
        self.clear_btn.grid(row=0, column=2)

        self.convert_btn = GradientButton(
            card, text="Convert Now", height=46, icon="sparkles",
            busy_text="Converting", command=self.on_convert_click, state="disabled",
        )
        self.convert_btn.grid(row=2, column=0, sticky="ew", padx=18, pady=(8, 16))

        self.progress = ctk.CTkProgressBar(frame, height=8)
        self.progress.set(0)
        self.progress.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 4))
        self.progress.grid_remove()  # only shown while converting

        self.status = ctk.CTkLabel(
            frame, text="Drop a file to begin.", text_color=MUTED,
            wraplength=620, justify="left", anchor="w",
        )
        self.status.grid(row=4, column=0, sticky="w", padx=24, pady=(4, 16))
        return frame

    # ---- batch view ------------------------------------------------------ #
    def _build_batch(self, parent) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(3, weight=1)

        self._section_header(frame, "Batch Convert", "Convert many files to one format at once.")

        dz = self._build_drop_zone(
            frame, row=1, icon=None, title="Drop multiple files here",
            hint="or click to browse", on_drop=self.on_batch_drop,
            on_click=self.browse_batch, height=120, title_size=15,
        )
        self.batch_drop = dz["zone"]
        self.batch_primary = dz["primary"]
        self.batch_label = dz["secondary"]

        ctrl = ctk.CTkFrame(frame, fg_color="transparent")
        ctrl.grid(row=2, column=0, sticky="w", padx=24, pady=8)
        ctk.CTkLabel(ctrl, text="Convert all to:").grid(row=0, column=0, padx=(0, 8))
        self.batch_to = ctk.CTkOptionMenu(ctrl, values=["-"], width=140, state="disabled")
        self.batch_to.grid(row=0, column=1, padx=(0, 16))
        self.batch_btn = ctk.CTkButton(
            ctrl, text=" Convert All", width=140, font=self._font(13, "semibold"),
            image=self._ui_icon("repeat", 16, "#FFFFFF", "#FFFFFF"), compound="left",
            command=self.on_batch_convert, state="disabled",
        )
        self.batch_btn.grid(row=0, column=2)
        ctk.CTkButton(
            ctrl, text="Save to…", width=90, fg_color="gray50", hover_color="gray40",
            command=self.choose_batch_export,
        ).grid(row=0, column=3, padx=(16, 8))
        self.batch_export_label = ctk.CTkLabel(
            ctrl, text="Output: next to each source", text_color=MUTED)
        self.batch_export_label.grid(row=0, column=4)
        ctk.CTkButton(
            ctrl, text="Clear", width=70, fg_color="transparent", border_width=1,
            border_color=MUTED, text_color=NAV_TEXT,
            hover_color=("#EBE0E1", "#2A2426"), command=self.reset_batch,
        ).grid(row=0, column=5, padx=(16, 0))

        # Read-only log: a Textbox is the right widget, but the user shouldn't
        # be able to type into their own results. Writes toggle the state.
        self.batch_list = ctk.CTkTextbox(frame, corner_radius=10)
        self.batch_list.grid(row=3, column=0, sticky="nsew", padx=24, pady=8)
        self.batch_list.configure(state="disabled")

        self.batch_progress = ctk.CTkProgressBar(frame, height=8)
        self.batch_progress.set(0)
        self.batch_progress.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 4))

        self.batch_status = ctk.CTkLabel(frame, text="", text_color=MUTED, anchor="w")
        self.batch_status.grid(row=5, column=0, sticky="w", padx=24, pady=(0, 14))
        return frame

    # ---- drag & drop helpers -------------------------------------------- #
    def _register_drop(self, zone, widgets, on_drop, on_click):
        def on_enter(_e):
            zone.configure(border_color=RED_BRIGHT)

        def on_leave(_e):
            zone.configure(border_color=DROP_BORDER)

        def on_drop_wrapped(event):
            on_leave(event)
            on_drop(event)

        for widget in widgets:
            try:
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", on_drop_wrapped)
                widget.dnd_bind("<<DropEnter>>", on_enter)
                widget.dnd_bind("<<DropLeave>>", on_leave)
            except Exception as exc:  # noqa: BLE001
                print("Drag & drop registration failed:", exc)
            widget.bind("<Button-1>", lambda _e: on_click())
            try:
                widget.configure(cursor="hand2")
            except Exception:  # noqa: BLE001
                pass

    def _parse_drop(self, event) -> list[Path]:
        try:
            paths = self.tk.splitlist(event.data)
        except Exception:  # noqa: BLE001
            paths = [event.data]
        return [Path(p) for p in paths]

    def _make_labels_wrap(self, container, labels, margin: int = 48) -> None:
        """Keep `labels` wrapped within `container`'s width so long text (e.g. a
        long filename) can never spill past the container's border."""
        def _update(event):
            wrap = max(event.width - margin, 120)
            for lbl in labels:
                lbl.configure(wraplength=wrap)

        container.bind("<Configure>", _update)

    @staticmethod
    def _ellipsize(text: str, limit: int = 52) -> str:
        """Shorten `text` with a middle ellipsis (keeps start and end visible)."""
        if len(text) <= limit:
            return text
        head = (limit - 1) // 2
        tail = limit - 1 - head
        return f"{text[:head]}…{text[-tail:]}"

    # ---- file dialogs that remember their last folder (per dialog key) ---- #
    def _ask_open(self, key: str, **kwargs) -> str:
        init = self._last_dirs.get(key)
        if init:
            kwargs.setdefault("initialdir", init)
        path = filedialog.askopenfilename(**kwargs)
        if path:
            self._last_dirs[key] = str(Path(path).parent)
        return path

    def _ask_open_multiple(self, key: str, **kwargs) -> tuple[str, ...]:
        init = self._last_dirs.get(key)
        if init:
            kwargs.setdefault("initialdir", init)
        paths = filedialog.askopenfilenames(**kwargs)
        if paths:
            self._last_dirs[key] = str(Path(paths[0]).parent)
        return paths

    def _ask_save(self, key: str, **kwargs) -> str:
        init = self._last_dirs.get(key)
        if init:
            kwargs.setdefault("initialdir", init)
        path = filedialog.asksaveasfilename(**kwargs)
        if path:
            self._last_dirs[key] = str(Path(path).parent)
        return path

    def _ask_dir(self, key: str, title: str) -> str:
        init = self._last_dirs.get(key)
        kwargs = {"initialdir": init} if init else {}
        folder = filedialog.askdirectory(title=title, **kwargs)
        if folder:
            self._last_dirs[key] = folder
        return folder

    # ---- shared tool-panel builders -------------------------------------- #
    def _build_drop_zone(self, parent, *, row: int, icon, title: str, hint: str,
                         on_drop, on_click, height: int = 200,
                         title_size: int = 16) -> dict:
        """Build the standard bordered drop zone every tool page uses.

        Returns its widgets: {"zone", "icon" (label or None), "primary",
        "secondary"} — the callers keep their own attribute names.
        """
        zone = ctk.CTkFrame(parent, height=height, corner_radius=14,
                            border_width=2, border_color=DROP_BORDER)
        zone.grid(row=row, column=0, sticky="ew", padx=24, pady=(4, 14))
        zone.grid_propagate(False)
        zone.grid_columnconfigure(0, weight=1)
        zone.grid_rowconfigure(0, weight=1)
        inner = ctk.CTkFrame(zone, fg_color="transparent")
        inner.grid(row=0, column=0)
        widgets: list = [zone, inner]
        icon_label = None
        if icon is not None:
            icon_label = ctk.CTkLabel(inner, text="", image=icon)
            icon_label.pack(pady=(0, 8))
            widgets.append(icon_label)
        primary = ctk.CTkLabel(inner, text=title, font=self._font(title_size, "semibold"))
        primary.pack()
        secondary = ctk.CTkLabel(inner, text=hint, text_color=MUTED)
        secondary.pack(pady=(2, 0))
        widgets += [primary, secondary]
        self._register_drop(zone, tuple(widgets), on_drop, on_click)
        # Wrap the filename / hint text to the zone width so long names stay inside.
        self._make_labels_wrap(zone, (primary, secondary))
        return {"zone": zone, "icon": icon_label, "primary": primary, "secondary": secondary}

    def _job_done(self, *, status_label, progress_bar, button,
                  src, out, error) -> None:
        """Shared end-of-job UI: hide progress, re-enable, report, record history."""
        self._job_finished()
        progress_bar.stop()
        progress_bar.grid_remove()
        progress_bar.configure(mode="determinate")
        progress_bar.set(0)
        button.configure(state="normal")
        if hasattr(button, "stop_busy"):  # GradientButton: confetti on success
            button.stop_busy(success=error is None)
        if error:
            status_label.configure(text=f"✕  {error}", text_color=ERROR)
            self.add_history(src, None, False, error)
        else:
            status_label.configure(text=f"✓  Saved to {out}", text_color=SUCCESS)
            self.add_history(src, out, True)

    @staticmethod
    def _not_a_file_message(path: Path) -> str:
        """Accurate copy for a drop that isn't a usable file."""
        if path.is_dir():
            return "That's a folder — drop a single file."
        return "Please drop a single file."

    # ---- shared Clear / Reset plumbing ----------------------------------- #
    def _clear_button(self, parent, command, *, text="Clear", height=46,
                      width=96):
        """The outlined Clear/Reset button used beside a tool's primary CTA."""
        return ctk.CTkButton(
            parent, text=text, width=width, height=height,
            font=self._font(14, "semibold"), fg_color="transparent",
            border_width=2, border_color=RED, text_color=TEXT,
            hover_color=("#F1DDDD", "#2E2A2C"), command=command)

    def _reset_image_tool(self, *, file_attr, icon_label, drop_icon, primary,
                          secondary, primary_text, hint_text, button, status,
                          status_text, progress=None, results=None) -> None:
        """Reset a drop-zone image/audio tool panel back to its initial state."""
        setattr(self, file_attr, None)
        if icon_label is not None and drop_icon is not None:
            icon_label.configure(image=drop_icon)
        primary.configure(text=primary_text)
        secondary.configure(text=hint_text)
        button.configure(state="disabled")
        if progress is not None:
            progress.grid_remove()
            progress.set(0)
        if results is not None:
            results.grid_remove()
        status.configure(text=status_text, text_color=MUTED)

    # ---- converter actions ---------------------------------------------- #
    def on_drop(self, event):
        paths = self._parse_drop(event)
        if not paths:
            return
        self.set_file(paths[0])
        if len(paths) > 1 and self.selected_file == paths[0]:
            self.status.configure(
                text=f"{len(paths)} files dropped — using {paths[0].name}. "
                     "Use Batch Convert for many files at once.",
                text_color=WARNING)

    def browse_file(self):
        path = self._ask_open("convert", title="Select a file to convert")
        if path:
            self.set_file(Path(path))

    def set_file(self, path: Path):
        if not path.is_file():
            self.status.configure(text=self._not_a_file_message(path), text_color=WARNING)
            return
        self.selected_file = path
        ext = detect_format(path)
        targets = compatible_targets(ext)
        try:
            size = human_size(path.stat().st_size)
        except OSError:
            size = "?"
        self.drop_primary.configure(text=path.name)
        ft_icon = self._filetype_icon(ext, 52)
        if ft_icon is not None:
            self.drop_icon_label.configure(image=ft_icon)
        self.from_menu.configure(values=[ext or "?"])
        self.from_menu.set(ext or "?")
        if targets:
            self.drop_secondary.configure(
                text=f"{category_of(ext)}  ·  {size}  ·  click to choose another")
            self.to_menu.configure(values=targets, state="normal")
            self.to_menu.set(targets[0])
            self.convert_btn.configure(state="normal")
            self.status.configure(text=f"Ready to convert {path.name}", text_color=MUTED)
        else:
            self.drop_secondary.configure(text="Unsupported format  ·  click to choose another")
            self.to_menu.configure(values=["-"], state="disabled")
            self.to_menu.set("-")
            self.convert_btn.configure(state="disabled")
            self.status.configure(text=f"Unsupported format: .{ext or '?'}", text_color=WARNING)

    def choose_export_path(self):
        folder = self._ask_dir("export", "Choose where to save converted files")
        if folder:
            self.export_dir = Path(folder)
            self.export_label.configure(text=f"Output: {self._ellipsize(str(self.export_dir))}")

    def clear_converter(self):
        """Reset the converter to a clean slate for the next file."""
        self._convert_run += 1  # invalidate any in-flight conversion's UI updates
        self.selected_file = None
        self.export_dir = None
        self.convert_btn.stop_busy()
        if self.drop_icon is not None:
            self.drop_icon_label.configure(image=self.drop_icon)
        self.drop_primary.configure(text="Drag & drop a file here")
        self.drop_secondary.configure(text="or click to browse")
        self.from_menu.configure(values=["-"], state="disabled")
        self.from_menu.set("-")
        self.to_menu.configure(values=["-"], state="disabled")
        self.to_menu.set("-")
        self.convert_btn.configure(state="disabled")
        self.progress.stop()
        self.progress.grid_remove()
        self.progress.configure(mode="determinate")
        self.progress.set(0)
        self.export_label.configure(text="Output: next to the source file")
        self.status.configure(text="Drop a file to begin.", text_color=MUTED)

    def on_convert_click(self):
        if not self.selected_file:
            return
        target = self.to_menu.get()
        if target in ("-", ""):
            return
        self._convert_run += 1
        run = self._convert_run
        self._job_started()
        self.convert_btn.configure(state="disabled")
        self.convert_btn.start_busy()
        self.progress.grid()
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.status.configure(
            text=f"Converting {self.selected_file.name} to .{target} …",
            text_color=MUTED,
        )
        threading.Thread(
            target=self._convert_worker, args=(self.selected_file, target, run),
            daemon=True,
        ).start()

    def _convert_worker(self, src: Path, target: str, run: int):
        try:
            out = convert_file(src, target, self.export_dir)
            self.after(0, self._convert_done, src, out, None, run)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.after(0, self._convert_done, src, None, exc, run)

    def _convert_done(self, src: Path, out: Path | None, error: Exception | None,
                      run: int):
        if run != self._convert_run:
            # The user hit Clear while this ran: record the result (it happened),
            # but don't resurrect status/progress over the cleared form.
            self._job_finished()
            self.add_history(src, out, error is None, error or "")
            return
        self._job_done(status_label=self.status, progress_bar=self.progress,
                       button=self.convert_btn, src=src, out=out, error=error)

    # ---- batch actions --------------------------------------------------- #
    def on_batch_drop(self, event):
        self.set_batch(self._parse_drop(event))

    def browse_batch(self):
        paths = self._ask_open_multiple("batch", title="Select files to convert")
        if paths:
            self.set_batch([Path(p) for p in paths])

    def choose_batch_export(self):
        folder = self._ask_dir("batch_export", "Choose where to save converted files")
        if folder:
            self.batch_export_dir = Path(folder)
            self.batch_export_label.configure(
                text=f"Output: {self._ellipsize(str(self.batch_export_dir), 36)}")

    def set_batch(self, paths: list[Path]):
        self.batch_files = [p for p in paths if p.is_file()]
        if not self.batch_files:
            return
        common: set[str] | None = None
        for p in self.batch_files:
            targets = set(compatible_targets(detect_format(p)))
            common = targets if common is None else (common & targets)
        common_sorted = sorted(common) if common else []

        self.batch_primary.configure(text=f"{len(self.batch_files)} file(s) selected")
        self.batch_label.configure(text="click to choose different files")
        self._batch_clear_log()
        for p in self.batch_files:
            self._batch_log(f"- {p.name}")

        if common_sorted:
            self.batch_to.configure(values=common_sorted, state="normal")
            self.batch_to.set(common_sorted[0])
            self.batch_btn.configure(state="normal")
        else:
            self.batch_to.configure(values=["-"], state="disabled")
            self.batch_to.set("-")
            self.batch_btn.configure(state="disabled")
            self._batch_log("\nNo common target format. Try files of the same type.")

    def on_batch_convert(self):
        target = self.batch_to.get()
        if target in ("-", "") or not self.batch_files:
            return
        self._job_started()
        self.batch_btn.configure(state="disabled")
        self.batch_progress.set(0)
        self.batch_status.configure(text=f"0 / {len(self.batch_files)} processed")
        self._batch_clear_log()
        files = list(self.batch_files)
        threading.Thread(
            target=self._batch_worker, args=(files, target, self.batch_export_dir),
            daemon=True,
        ).start()

    def _batch_worker(self, files: list[Path], target: str, out_dir: Path | None):
        total = len(files)
        for i, p in enumerate(files, start=1):
            try:
                out = convert_file(p, target, out_dir)
                self.after(0, self._batch_log, f"OK   {p.name} -> {out.name}")
                # Marshal history updates to the main thread (self.history is shared
                # with the UI; mutating it off-thread can race with _refresh_recent).
                self.after(0, self.add_history, p, out, True)
            except Exception as exc:  # noqa: BLE001
                traceback.print_exc()
                self.after(0, self._batch_log, f"FAIL {p.name}: {exc}")
                self.after(0, self.add_history, p, None, False, exc)
            self.after(0, self.batch_progress.set, i / total)
            self.after(0, self._batch_count, i, total)
        self.after(0, self._job_finished)
        self.after(0, lambda: self.batch_btn.configure(state="normal"))
        self.after(0, self._batch_log, f"\nDone: {total} file(s) processed.")

    def _batch_count(self, done: int, total: int):
        self.batch_status.configure(text=f"{done} / {total} processed")

    def _batch_clear_log(self):
        self.batch_list.configure(state="normal")
        self.batch_list.delete("1.0", "end")
        self.batch_list.configure(state="disabled")

    def _batch_log(self, msg: str):
        self.batch_list.configure(state="normal")
        self.batch_list.insert("end", msg + "\n")
        self.batch_list.see("end")
        self.batch_list.configure(state="disabled")

    def reset_batch(self):
        self.batch_files = []
        self.batch_primary.configure(text="Drop multiple files here")
        self.batch_label.configure(text="or click to browse")
        self.batch_to.configure(values=["-"], state="disabled")
        self.batch_to.set("-")
        self.batch_btn.configure(state="disabled")
        self._batch_clear_log()
        self.batch_progress.set(0)
        self.batch_status.configure(text="", text_color=MUTED)

    # ---- youtube view ---------------------------------------------------- #
    def _build_youtube(self, parent) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent)
        frame.grid_columnconfigure(0, weight=1)
        self._section_header(frame, "YouTube", "Paste a link, pick a format, download.")

        card = ctk.CTkFrame(frame, fg_color=CARD_SOFT, corner_radius=12)
        card.grid(row=1, column=0, sticky="ew", padx=24, pady=(4, 12))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card, text="VIDEO URL", font=self._font(11, "medium"), text_color=MUTED,
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(16, 2))
        self.yt_url = ctk.CTkEntry(
            card, placeholder_text="https://www.youtube.com/watch?v=…", height=40,
        )
        self.yt_url.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))
        self.yt_url.bind("<Return>", lambda _e: self.on_youtube_download())

        opts = ctk.CTkFrame(card, fg_color="transparent")
        opts.grid(row=2, column=0, sticky="w", padx=18, pady=(0, 6))
        ctk.CTkLabel(opts, text="Format:").grid(row=0, column=0, padx=(0, 10))
        self.yt_format = ctk.CTkSegmentedButton(
            opts, values=["MP4", "MP3"], selected_color=RED, selected_hover_color=RED_HOVER,
        )
        self.yt_format.set("MP4")
        self.yt_format.grid(row=0, column=1)
        ctk.CTkLabel(
            opts, text="MP4 = video · MP3 = audio (192 kbps)", text_color=MUTED,
        ).grid(row=0, column=2, padx=(14, 0))

        btnrow = ctk.CTkFrame(card, fg_color="transparent")
        btnrow.grid(row=3, column=0, sticky="ew", padx=18, pady=(2, 10))
        btnrow.grid_columnconfigure(0, weight=1)
        self.yt_btn = GradientButton(
            btnrow, text="Download", height=46, icon="download",
            busy_text="Downloading", command=self.on_youtube_download,
        )
        self.yt_btn.grid(row=0, column=0, sticky="ew")
        self._clear_button(btnrow, self.reset_youtube).grid(row=0, column=1, padx=(10, 0))

        self.yt_progress = ctk.CTkProgressBar(frame, height=8)
        self.yt_progress.set(0)
        self.yt_progress.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 4))
        self.yt_progress.grid_remove()

        self.yt_status = ctk.CTkLabel(
            frame, text="Paste a video link to begin.", text_color=MUTED,
            wraplength=620, justify="left", anchor="w",
        )
        self.yt_status.grid(row=3, column=0, sticky="w", padx=24, pady=(4, 16))
        return frame

    def on_youtube_download(self):
        url = self.yt_url.get().strip()
        if not url:
            self.yt_status.configure(text="Please paste a video URL.", text_color=WARNING)
            return
        fmt = self.yt_format.get().lower()
        folder = self._ask_dir("youtube", "Choose where to save the download")
        if not folder:
            self.yt_status.configure(text="Download cancelled (no folder chosen).", text_color=MUTED)
            return
        self._job_started()
        self._yt_last_ui = 0.0
        self.yt_btn.configure(state="disabled")
        self.yt_btn.start_busy()
        self.yt_progress.grid()
        self.yt_progress.configure(mode="determinate")
        self.yt_progress.set(0)
        self.yt_status.configure(text=f"Starting {fmt.upper()} download…", text_color=MUTED)
        threading.Thread(
            target=self._youtube_worker, args=(url, fmt, folder), daemon=True
        ).start()

    def _youtube_worker(self, url: str, fmt: str, folder: str):
        try:
            out = download_youtube(url, fmt, folder, progress_hook=self._yt_hook)
            self.after(0, self._youtube_done, url, out, None)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.after(0, self._youtube_done, url, None, exc)

    def _yt_hook(self, d: dict):
        # Runs on the worker thread; marshal everything to the UI thread.
        # yt-dlp fires this per network block — throttle, or hundreds of queued
        # after(0) UI updates per second choke the Tk event loop.
        status = d.get("status")
        if status == "downloading":
            now = time.monotonic()
            if now - getattr(self, "_yt_last_ui", 0.0) < 0.1:
                return
            self._yt_last_ui = now
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes") or 0
            if total:
                self.after(0, self._yt_progress_set, done / total,
                           f"Downloading… {int(done / total * 100)}%")
            else:
                self.after(0, self._yt_progress_set, None, "Downloading…")
        elif status == "finished":
            self.after(0, self._yt_progress_set, 1.0, "Processing with ffmpeg…")

    def _yt_progress_set(self, frac, text):
        if frac is None:
            if self.yt_progress.cget("mode") != "indeterminate":
                self.yt_progress.configure(mode="indeterminate")
                self.yt_progress.start()
        else:
            if self.yt_progress.cget("mode") != "determinate":
                self.yt_progress.stop()
                self.yt_progress.configure(mode="determinate")
            self.yt_progress.set(frac)
        if text:
            self.yt_status.configure(text=text, text_color=MUTED)

    def _youtube_done(self, url: str, out: Path | None, error: Exception | None):
        self._job_done(status_label=self.yt_status, progress_bar=self.yt_progress,
                       button=self.yt_btn, src=url, out=out, error=error)

    def reset_youtube(self):
        self.yt_url.delete(0, "end")
        self.yt_format.set("MP4")
        self.yt_progress.grid_remove()
        self.yt_progress.set(0)
        self.yt_status.configure(text="Paste a video link to begin.", text_color=MUTED)

    # ---- marquee (image editing) view ------------------------------------ #
    def _build_marquee(self, parent) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)
        self._section_header(
            frame, "Marquee",
            "Image editing — remove backgrounds or upscale to a crisp resolution.",
        )

        # ---- tool switcher ----
        switch = ctk.CTkFrame(frame, fg_color="transparent")
        switch.grid(row=1, column=0, sticky="w", padx=24, pady=(2, 6))
        self.mq_tool = ctk.CTkSegmentedButton(
            switch, values=["Background Remover", "Upscaler"],
            command=self._show_mq_tool,
            selected_color=RED, selected_hover_color=RED_HOVER,
        )
        self.mq_tool.set("Background Remover")
        self.mq_tool.grid(row=0, column=0)

        # ---- tool panels (only one shown at a time) ----
        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.grid(row=2, column=0, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)
        self.mq_panels = {
            "Background Remover": self._build_mq_bgremover(container),
            "Upscaler": self._build_mq_upscaler(container),
        }
        for p in self.mq_panels.values():
            p.grid(row=0, column=0, sticky="nsew")
        self._show_mq_tool("Background Remover")
        return frame

    def _show_mq_tool(self, name: str):
        for n, panel in self.mq_panels.items():
            (panel.grid if n == name else panel.grid_remove)()

    # ---- marquee: background remover panel ------------------------------- #
    def _build_mq_bgremover(self, parent) -> ctk.CTkFrame:
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.grid_columnconfigure(0, weight=1)

        self.mq_drop_icon = self._ui_icon("sparkles", 46, light=RED, dark=RED_BRIGHT)
        dz = self._build_drop_zone(
            panel, row=0, icon=self.mq_drop_icon, title="Drag & drop an image here",
            hint="or click to browse", on_drop=self.on_marquee_drop,
            on_click=self.browse_marquee,
        )
        self.mq_drop = dz["zone"]
        self.mq_icon_label = dz["icon"]
        self.mq_primary = dz["primary"]
        self.mq_secondary = dz["secondary"]

        card = ctk.CTkFrame(panel, fg_color=CARD_SOFT, corner_radius=12)
        card.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 12))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card, text="Drops the background and keeps your subject on a fully "
                       "transparent canvas. Output is always a PNG.",
            text_color=MUTED, anchor="w", justify="left", wraplength=620,
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 8))

        qual = ctk.CTkFrame(card, fg_color="transparent")
        qual.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 2))
        ctk.CTkLabel(qual, text="QUALITY", font=self._font(11, "medium"),
                     text_color=MUTED).grid(row=0, column=0, padx=(0, 12))
        self.mq_model = ctk.CTkSegmentedButton(
            qual, values=list(BG_MODELS), command=self._on_mq_model_change,
            selected_color=RED, selected_hover_color=RED_HOVER,
        )
        self.mq_model.set(DEFAULT_BG_TIER)
        self.mq_model.grid(row=0, column=1)
        self.mq_model_caption = ctk.CTkLabel(
            card, text=BG_MODELS[DEFAULT_BG_TIER][1], text_color=MUTED,
            anchor="w", justify="left", wraplength=620,
        )
        self.mq_model_caption.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 10))

        btnrow = ctk.CTkFrame(card, fg_color="transparent")
        btnrow.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 10))
        btnrow.grid_columnconfigure(0, weight=1)
        self.mq_btn = GradientButton(
            btnrow, text="Remove Background", height=46, icon="sparkles",
            busy_text="Removing", command=self.on_marquee_remove, state="disabled",
        )
        self.mq_btn.grid(row=0, column=0, sticky="ew")
        self._clear_button(btnrow, self.reset_marquee).grid(row=0, column=1, padx=(10, 0))

        self.mq_progress = ctk.CTkProgressBar(panel, height=8)
        self.mq_progress.set(0)
        self.mq_progress.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 4))
        self.mq_progress.grid_remove()  # only shown while processing

        self.mq_status = ctk.CTkLabel(
            panel, text="Drop an image to begin.", text_color=MUTED,
            wraplength=620, justify="left", anchor="w",
        )
        self.mq_status.grid(row=3, column=0, sticky="w", padx=24, pady=(4, 16))
        return panel

    # ---- marquee: upscaler panel ----------------------------------------- #
    def _build_mq_upscaler(self, parent) -> ctk.CTkFrame:
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.grid_columnconfigure(0, weight=1)

        self.up_drop_icon = self._ui_icon("sparkles", 46, light=RED, dark=RED_BRIGHT)
        dz = self._build_drop_zone(
            panel, row=0, icon=self.up_drop_icon,
            title="Drag & drop a low-res image here",
            hint="or click to browse  ·  JPG · PNG · WEBP · BMP · GIF · TIFF",
            on_drop=self.on_upscale_drop, on_click=self.browse_upscale,
        )
        self.up_drop = dz["zone"]
        self.up_icon_label = dz["icon"]
        self.up_primary = dz["primary"]
        self.up_secondary = dz["secondary"]

        card = ctk.CTkFrame(panel, fg_color=CARD_SOFT, corner_radius=12)
        card.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 12))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card, text="AI super-resolution (Real-ESRGAN) for clean, sharp detail, then "
                       "fit to the exact resolution — pad with bars, or crop to fill.",
            text_color=MUTED, anchor="w", justify="left", wraplength=620,
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 8))

        # quality (model tier) selector
        qual = ctk.CTkFrame(card, fg_color="transparent")
        qual.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 2))
        ctk.CTkLabel(qual, text="QUALITY", font=self._font(11, "medium"),
                     text_color=MUTED).grid(row=0, column=0, padx=(0, 12))
        self.up_model = ctk.CTkSegmentedButton(
            qual, values=list(UPSCALE_MODELS), command=self._on_up_model_change,
            selected_color=RED, selected_hover_color=RED_HOVER,
        )
        self.up_model.set(DEFAULT_UPSCALE_TIER)
        self.up_model.grid(row=0, column=1)
        self.up_model_caption = ctk.CTkLabel(
            card, text=UPSCALE_MODELS[DEFAULT_UPSCALE_TIER][2], text_color=MUTED,
            anchor="w", justify="left", wraplength=620,
        )
        self.up_model_caption.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 10))

        # target resolution + fit selectors
        res = ctk.CTkFrame(card, fg_color="transparent")
        res.grid(row=3, column=0, sticky="w", padx=18, pady=(0, 12))
        ctk.CTkLabel(res, text="TARGET", font=self._font(11, "medium"),
                     text_color=MUTED).grid(row=0, column=0, padx=(0, 12))
        self.up_target = ctk.CTkSegmentedButton(
            res, values=list(TARGETS),
            selected_color=RED, selected_hover_color=RED_HOVER,
        )
        self.up_target.set(DEFAULT_TARGET)
        self.up_target.grid(row=0, column=1)
        ctk.CTkLabel(res, text="FIT", font=self._font(11, "medium"),
                     text_color=MUTED).grid(row=0, column=2, padx=(18, 12))
        self.up_fit = ctk.CTkSegmentedButton(
            res, values=list(self.UPSCALE_FITS),
            selected_color=RED, selected_hover_color=RED_HOVER,
        )
        self.up_fit.set("Pad")
        self.up_fit.grid(row=0, column=3)

        btnrow = ctk.CTkFrame(card, fg_color="transparent")
        btnrow.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 10))
        btnrow.grid_columnconfigure(0, weight=1)
        self.up_btn = GradientButton(
            btnrow, text="Upscale Image", height=46, icon="sparkles",
            busy_text="Upscaling", command=self.on_upscale_run, state="disabled",
        )
        self.up_btn.grid(row=0, column=0, sticky="ew")
        self._clear_button(btnrow, self.reset_upscale).grid(row=0, column=1, padx=(10, 0))

        self.up_progress = ctk.CTkProgressBar(panel, height=8)
        self.up_progress.set(0)
        self.up_progress.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 4))
        self.up_progress.grid_remove()  # only shown while processing

        self.up_status = ctk.CTkLabel(
            panel, text="Drop a low-res image to begin.", text_color=MUTED,
            wraplength=620, justify="left", anchor="w",
        )
        self.up_status.grid(row=3, column=0, sticky="w", padx=24, pady=(4, 16))
        return panel

    # ---- marquee actions ------------------------------------------------- #
    def _set_image_file(self, path: Path, *, icon_label, default_icon, primary,
                        secondary, button, status, detail: str,
                        ready_text: str) -> Path | None:
        """Shared validation/preview for the image tools (path must exist).

        Returns the path if it's a usable image, else None — the labels,
        button state and status are updated either way.
        """
        ext = detect_format(path)
        primary.configure(text=path.name)
        if ext not in IMAGE_EXTS:
            if default_icon is not None:
                icon_label.configure(image=default_icon)
            secondary.configure(text="Not an image  ·  click to choose another")
            button.configure(state="disabled")
            status.configure(
                text=f"Unsupported file: .{ext or '?'} — pick an image.", text_color=WARNING)
            return None
        ft_icon = self._filetype_icon(ext, 52)
        if ft_icon is not None:
            icon_label.configure(image=ft_icon)
        secondary.configure(text=f"{detail}  ·  click to choose another")
        button.configure(state="normal")
        status.configure(text=ready_text, text_color=MUTED)
        return path

    _IMAGE_FILETYPES = [
        ("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tiff *.tif"),
        ("All files", "*.*"),
    ]

    def _on_mq_model_change(self, tier: str):
        blurb = BG_MODELS.get(tier, ("", ""))[1]
        self.mq_model_caption.configure(text=blurb)

    def on_marquee_drop(self, event):
        paths = self._parse_drop(event)
        if paths:
            self.set_marquee_file(paths[0])

    def browse_marquee(self):
        path = self._ask_open("marquee", title="Select an image",
                              filetypes=self._IMAGE_FILETYPES)
        if path:
            self.set_marquee_file(Path(path))

    def set_marquee_file(self, path: Path):
        if not path.is_file():
            self.mq_status.configure(text=self._not_a_file_message(path), text_color=WARNING)
            return
        try:
            size = human_size(path.stat().st_size)
        except OSError:
            size = "?"
        self.marquee_file = self._set_image_file(
            path, icon_label=self.mq_icon_label, default_icon=self.mq_drop_icon,
            primary=self.mq_primary, secondary=self.mq_secondary,
            button=self.mq_btn, status=self.mq_status,
            detail=f"Image  ·  {size}",
            ready_text=f"Ready to remove the background from {path.name}",
        )

    def on_marquee_remove(self):
        src = self.marquee_file
        if not src:
            return
        out = self._ask_save(
            "marquee_save",
            title="Save transparent PNG as",
            defaultextension=".png",
            initialfile=f"{src.stem}_no-bg.png",
            filetypes=[("PNG image", "*.png")],
        )
        if not out:
            self.mq_status.configure(
                text="Cancelled (no save location chosen).", text_color=MUTED)
            return
        tier = self.mq_model.get() or DEFAULT_BG_TIER
        model = BG_MODELS.get(tier, BG_MODELS[DEFAULT_BG_TIER])[0]
        self._job_started()
        self.mq_btn.configure(state="disabled")
        self.mq_btn.start_busy()
        self.mq_progress.grid()
        self._fill_start(self.mq_progress)
        self.mq_status.configure(
            text=f"Removing background with {tier}… "
                 "(the first use of a model downloads it once)",
            text_color=MUTED,
        )
        threading.Thread(
            target=self._marquee_worker, args=(src, Path(out), model), daemon=True
        ).start()

    def _marquee_worker(self, src: Path, out: Path, model: str):
        try:
            # overwrite=True: the save dialog already confirmed replacing `out`.
            result = remove_background(src, out, model, overwrite=True)
            self.after(0, self._marquee_done, src, result, None)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.after(0, self._marquee_done, src, None, exc)

    def _marquee_done(self, src: Path, out: Path | None, error: Exception | None):
        self._fill_stop(self.mq_progress)
        self._job_done(status_label=self.mq_status, progress_bar=self.mq_progress,
                       button=self.mq_btn, src=src, out=out, error=error)

    def reset_marquee(self):
        self._reset_image_tool(
            file_attr="marquee_file", icon_label=self.mq_icon_label,
            drop_icon=self.mq_drop_icon, primary=self.mq_primary,
            secondary=self.mq_secondary, primary_text="Drag & drop an image here",
            hint_text="or click to browse", button=self.mq_btn,
            progress=self.mq_progress, status=self.mq_status,
            status_text="Drop an image to begin.")

    # ---- eased fill (for workers with no real progress signal) ------------ #
    # Used by the bg remover, Text Extraction and What's The Font; state is
    # kept per bar so several tools can run at once.
    def _fill_start(self, bar):
        """Start a smooth determinate fill on `bar` that eases toward ~90%."""
        jobs = getattr(self, "_fill_jobs", None)
        if jobs is None:
            jobs = self._fill_jobs = {}
        jobs[bar] = {"value": 0.0, "after": None}
        bar.configure(mode="determinate")
        bar.set(0.0)
        self._fill_tick(bar)

    def _fill_tick(self, bar):
        # ease toward 0.9: cover a small fraction of the remaining gap each tick,
        # so the bar always keeps creeping while the worker thread runs.
        job = self._fill_jobs.get(bar)
        if job is None:
            return
        job["value"] = min(0.9, job["value"] + max(0.004, (0.9 - job["value"]) * 0.06))
        bar.set(job["value"])
        job["after"] = self.after(110, self._fill_tick, bar)

    def _fill_stop(self, bar):
        job = getattr(self, "_fill_jobs", {}).pop(bar, None)
        if job and job["after"] is not None:
            self.after_cancel(job["after"])

    # ---- marquee: upscaler actions --------------------------------------- #
    UPSCALE_FITS = {"Pad": "letterbox", "Crop": "crop"}  # label -> upscale_image fit

    def _on_up_model_change(self, tier: str):
        self.up_model_caption.configure(text=UPSCALE_MODELS.get(tier, ("", "", ""))[2])

    def on_upscale_drop(self, event):
        paths = self._parse_drop(event)
        if paths:
            self.set_upscale_file(paths[0])

    def browse_upscale(self):
        path = self._ask_open("upscale", title="Select an image to upscale",
                              filetypes=self._IMAGE_FILETYPES)
        if path:
            self.set_upscale_file(Path(path))

    def set_upscale_file(self, path: Path):
        if not path.is_file():
            self.up_status.configure(text=self._not_a_file_message(path), text_color=WARNING)
            return
        dims = "?"
        try:
            from PIL import Image

            with Image.open(path) as im:
                dims = f"{im.width}×{im.height}"
        except Exception:  # noqa: BLE001
            pass
        self.upscale_file = self._set_image_file(
            path, icon_label=self.up_icon_label, default_icon=self.up_drop_icon,
            primary=self.up_primary, secondary=self.up_secondary,
            button=self.up_btn, status=self.up_status,
            detail=f"{dims} source",
            ready_text=f"Ready to upscale {path.name}",
        )

    def on_upscale_run(self):
        src = self.upscale_file
        if not src:
            return
        target = self.up_target.get() or DEFAULT_TARGET
        tier = self.up_model.get() or DEFAULT_UPSCALE_TIER
        fit = self.UPSCALE_FITS.get(self.up_fit.get(), "letterbox")
        out = self._ask_save(
            "upscale_save",
            title="Save upscaled image as",
            defaultextension=".png",
            initialfile=f"{src.stem}_{target}.png",
            filetypes=[("PNG image", "*.png"), ("JPEG image", "*.jpg"),
                       ("WEBP image", "*.webp")],
        )
        if not out:
            self.up_status.configure(
                text="Cancelled (no save location chosen).", text_color=MUTED)
            return
        self._job_started()
        self.up_btn.configure(state="disabled")
        self.up_btn.start_busy()
        self.up_progress.grid()
        self.up_progress.configure(mode="determinate")
        self.up_progress.set(0)
        slow = "  This can take a while on CPU." if tier == "Max" else ""
        self.up_status.configure(
            text=f"Upscaling to {target} with {tier}… (AI super-resolution; the model "
                 f"downloads once on first use).{slow}",
            text_color=MUTED,
        )
        threading.Thread(
            target=self._upscale_worker, args=(src, Path(out), target, tier, fit),
            daemon=True,
        ).start()

    def _upscale_worker(self, src: Path, out: Path, target: str, tier: str, fit: str):
        def on_progress(frac: float):
            self.after(0, self._set_up_progress, frac, target, tier)

        try:
            # overwrite=True: the save dialog already confirmed replacing `out`.
            result = upscale_image(src, out, target, tier, fit=fit,
                                   progress=on_progress, overwrite=True)
            self.after(0, self._upscale_done, src, result, None)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.after(0, self._upscale_done, src, None, exc)

    def _set_up_progress(self, frac: float, target: str, tier: str):
        """Drive the real filling bar + live percentage from the worker's hook."""
        self.up_progress.set(max(0.0, min(1.0, frac)))
        self.up_status.configure(
            text=f"Upscaling to {target} with {tier}…  {int(frac * 100)}%", text_color=MUTED)

    def _upscale_done(self, src: Path, out: Path | None, error: Exception | None):
        self._job_done(status_label=self.up_status, progress_bar=self.up_progress,
                       button=self.up_btn, src=src, out=out, error=error)

    def reset_upscale(self):
        self._reset_image_tool(
            file_attr="upscale_file", icon_label=self.up_icon_label,
            drop_icon=self.up_drop_icon, primary=self.up_primary,
            secondary=self.up_secondary,
            primary_text="Drag & drop a low-res image here",
            hint_text="or click to browse  ·  JPG · PNG · WEBP · BMP · GIF · TIFF",
            button=self.up_btn, progress=self.up_progress, status=self.up_status,
            status_text="Drop a low-res image to begin.")

    # ===================================================================== #
    # Vanguard — AI text tools (detector / text extraction / font ID)
    # ===================================================================== #
    def _build_vanguard(self, parent) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)
        self._section_header(
            frame, "Vanguard",
            "AI text tools — detect AI writing, pull text out of images, identify fonts.",
        )

        # ---- tool switcher (same pattern as Marquee) ----
        switch = ctk.CTkFrame(frame, fg_color="transparent")
        switch.grid(row=1, column=0, sticky="w", padx=24, pady=(2, 6))
        self.vg_tool = ctk.CTkSegmentedButton(
            switch, values=["AI Detector", "Text Extraction", "What's The Font"],
            command=self._show_vg_tool,
            selected_color=RED, selected_hover_color=RED_HOVER,
        )
        self.vg_tool.set("AI Detector")
        self.vg_tool.grid(row=0, column=0)

        # ---- tool panels (only one shown at a time) ----
        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.grid(row=2, column=0, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)
        self.vg_panels = {
            "AI Detector": self._build_vg_detector(container),
            "Text Extraction": self._build_vg_ocr(container),
            "What's The Font": self._build_vg_font(container),
        }
        for p in self.vg_panels.values():
            p.grid(row=0, column=0, sticky="nsew")
        self._show_vg_tool("AI Detector")
        return frame

    def _show_vg_tool(self, name: str):
        for n, panel in self.vg_panels.items():
            (panel.grid if n == name else panel.grid_remove)()

    # ---- vanguard: AI detector panel -------------------------------------- #
    def _build_vg_detector(self, parent) -> ctk.CTkFrame:
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(3, weight=1)  # results row grows

        # ---- input card: paste text or upload a document ----
        incard = ctk.CTkFrame(panel, fg_color=CARD_SOFT, corner_radius=12)
        incard.grid(row=0, column=0, sticky="ew", padx=24, pady=(4, 10))
        incard.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(incard, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 6))
        top.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(top, text="Paste text below, or upload a .txt / .docx / .pdf",
                     text_color=MUTED, anchor="w").grid(row=0, column=0, sticky="w")
        self.vg_upload_btn = ctk.CTkButton(
            top, text=" Upload file", width=130, height=32,
            image=self._ui_icon("folder-open", 16), compound="left",
            fg_color="transparent", border_width=1, border_color=MUTED,
            text_color=NAV_TEXT, hover_color=("#EBE0E1", "#2A2426"),
            command=self.browse_vanguard,
        )
        self.vg_upload_btn.grid(row=0, column=1, sticky="e")

        self.vg_input = ctk.CTkTextbox(incard, height=170, wrap="word",
                                       border_width=1, border_color=DROP_BORDER)
        self.vg_input.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 6))
        # Drag a file onto the box to load its text (no click-to-browse — it's
        # editable). Highlight the border on hover like every other drop zone.
        try:
            self.vg_input.drop_target_register(DND_FILES)
            self.vg_input.dnd_bind("<<Drop>>", self.on_vanguard_drop)
            self.vg_input.dnd_bind(
                "<<DropEnter>>",
                lambda _e: self.vg_input.configure(border_color=RED_BRIGHT))
            self.vg_input.dnd_bind(
                "<<DropLeave>>",
                lambda _e: self.vg_input.configure(border_color=DROP_BORDER))
        except Exception as exc:  # noqa: BLE001
            print("Vanguard drag & drop registration failed:", exc)
        self.vg_source = ctk.CTkLabel(incard, text="Nothing loaded — type, paste, or drop a file.",
                                      text_color=MUTED, anchor="w", justify="left", wraplength=620)
        self.vg_source.grid(row=2, column=0, sticky="w", padx=18, pady=(0, 14))

        btnrow = ctk.CTkFrame(panel, fg_color="transparent")
        btnrow.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 8))
        btnrow.grid_columnconfigure(0, weight=1)
        self.vg_btn = GradientButton(
            btnrow, text="Detect AI Text", height=46, icon="shield-check",
            busy_text="Detecting", command=self.on_vanguard_detect,
        )
        self.vg_btn.grid(row=0, column=0, sticky="ew")
        self.vg_reset_btn = ctk.CTkButton(
            btnrow, text="Reset", width=110, height=46,
            font=self._font(14, "semibold"),
            fg_color="transparent", border_width=2, border_color=RED,
            text_color=TEXT, hover_color=("#F1DDDD", "#2E2A2C"),
            command=self.reset_vanguard,
        )
        self.vg_reset_btn.grid(row=0, column=1, padx=(10, 0))

        self.vg_progress = ctk.CTkProgressBar(panel, height=8)
        self.vg_progress.set(0)
        self.vg_progress.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 4))
        self.vg_progress.grid_remove()  # only while analysing

        # ---- results card (hidden until a run finishes) ----
        self.vg_results = ctk.CTkFrame(panel, fg_color=CARD_SOFT, corner_radius=12)
        self.vg_results.grid(row=3, column=0, sticky="nsew", padx=24, pady=(0, 8))
        self.vg_results.grid_columnconfigure(0, weight=1)
        self.vg_results.grid_rowconfigure(2, weight=1)

        head = ctk.CTkFrame(self.vg_results, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 2))
        head.grid_columnconfigure(1, weight=1)
        self.vg_score = ctk.CTkLabel(head, text="—", font=self._font(42, "semibold"))
        self.vg_score.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(head, text="  AI-likelihood", text_color=MUTED).grid(row=0, column=1, sticky="w")
        self.vg_chip = ctk.CTkLabel(
            head, text="", corner_radius=14, height=30, fg_color="transparent",
            text_color="#FFFFFF", font=self._font(13, "semibold"),
        )
        self.vg_chip.grid(row=0, column=2, sticky="e")

        ctk.CTkLabel(
            self.vg_results, text="Passages shaded red are the ones the model flags as "
            "most likely AI-generated:", text_color=MUTED, anchor="w",
            justify="left", wraplength=620,
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(2, 4))

        self.vg_out = ctk.CTkTextbox(self.vg_results, height=200, wrap="word")
        self.vg_out.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 6))
        self.vg_out.configure(state="disabled")
        # The underlying tk.Text — CTkTextbox has no tag API, so highlighting
        # must reach through. Centralised here so it's one private access.
        self.vg_out_text = self.vg_out._textbox  # noqa: SLF001

        self.vg_disclaimer = ctk.CTkLabel(
            self.vg_results,
            text="⚠ Estimate only — not proof. AI detectors can be wrong, especially on "
                 "edited, translated, or non-native-English writing. Don't use this to "
                 "make accusations.",
            text_color=MUTED, anchor="w", justify="left", wraplength=620,
            font=ctk.CTkFont(size=11),
        )
        self.vg_disclaimer.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 14))
        self.vg_results.grid_remove()

        self.vg_status = ctk.CTkLabel(
            panel, text="Paste or upload text, then Detect.", text_color=MUTED,
            wraplength=620, justify="left", anchor="w",
        )
        self.vg_status.grid(row=4, column=0, sticky="w", padx=24, pady=(2, 14))
        return panel

    # ---- vanguard: text extraction (OCR) panel ----------------------------- #
    def _build_vg_ocr(self, parent) -> ctk.CTkFrame:
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(3, weight=1)  # results row grows

        self.vgo_drop_icon = self._ui_icon("scan-text", 46, light=RED, dark=RED_BRIGHT)
        dz = self._build_drop_zone(
            panel, row=0, icon=self.vgo_drop_icon,
            title="Drag & drop a screenshot or photo here",
            hint="or click to browse  ·  JPG · PNG · WEBP · BMP · GIF · TIFF",
            on_drop=self.on_vg_ocr_drop, on_click=self.browse_vg_ocr, height=130,
        )
        self.vgo_drop = dz["zone"]
        self.vgo_icon_label = dz["icon"]
        self.vgo_primary = dz["primary"]
        self.vgo_secondary = dz["secondary"]

        card = ctk.CTkFrame(panel, fg_color=CARD_SOFT, corner_radius=12)
        card.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 10))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card, text="Reads every line of text out of the image — fully offline OCR.",
            text_color=MUTED, anchor="w", justify="left", wraplength=620,
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(12, 4))

        qual = ctk.CTkFrame(card, fg_color="transparent")
        qual.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 2))
        ctk.CTkLabel(qual, text="QUALITY", font=self._font(11, "medium"),
                     text_color=MUTED).grid(row=0, column=0, padx=(0, 12))
        self.vgo_model = ctk.CTkSegmentedButton(
            qual, values=list(OCR_MODELS), command=self._on_vgo_model_change,
            selected_color=RED, selected_hover_color=RED_HOVER,
        )
        self.vgo_model.set(DEFAULT_OCR_TIER)
        self.vgo_model.grid(row=0, column=1)
        self.vgo_model_caption = ctk.CTkLabel(
            card, text=OCR_MODELS[DEFAULT_OCR_TIER][1], text_color=MUTED,
            anchor="w", justify="left", wraplength=620,
        )
        self.vgo_model_caption.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 6))

        btnrow = ctk.CTkFrame(card, fg_color="transparent")
        btnrow.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 10))
        btnrow.grid_columnconfigure(0, weight=1)
        self.vgo_btn = GradientButton(
            btnrow, text="Extract Text", height=46, icon="scan-text",
            busy_text="Extracting", command=self.on_vg_ocr_run, state="disabled",
        )
        self.vgo_btn.grid(row=0, column=0, sticky="ew")
        self._clear_button(btnrow, self.reset_vg_ocr).grid(row=0, column=1, padx=(10, 0))

        self.vgo_progress = ctk.CTkProgressBar(panel, height=8)
        self.vgo_progress.set(0)
        self.vgo_progress.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 4))
        self.vgo_progress.grid_remove()  # only while extracting

        # ---- results card (hidden until a run finishes) ----
        self.vgo_results = ctk.CTkFrame(panel, fg_color=CARD_SOFT, corner_radius=12)
        self.vgo_results.grid(row=3, column=0, sticky="nsew", padx=24, pady=(0, 8))
        self.vgo_results.grid_columnconfigure(0, weight=1)
        self.vgo_results.grid_rowconfigure(1, weight=1)
        head = ctk.CTkFrame(self.vgo_results, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 4))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text="Extracted text", font=self._font(14, "semibold"),
                     anchor="w").grid(row=0, column=0, sticky="w")
        self.vgo_copy_btn = ctk.CTkButton(
            head, text="Copy to clipboard", width=150, height=32,
            command=self._vg_ocr_copy,
        )
        self.vgo_copy_btn.grid(row=0, column=1, sticky="e")
        self.vgo_out = ctk.CTkTextbox(self.vgo_results, height=180, wrap="word")
        self.vgo_out.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 14))
        self.vgo_out.configure(state="disabled")
        self.vgo_results.grid_remove()

        self.vgo_status = ctk.CTkLabel(
            panel, text="Drop an image to begin.", text_color=MUTED,
            wraplength=620, justify="left", anchor="w",
        )
        self.vgo_status.grid(row=4, column=0, sticky="w", padx=24, pady=(2, 10))
        return panel

    # ---- vanguard: what's-the-font panel ----------------------------------- #
    def _build_vg_font(self, parent) -> ctk.CTkFrame:
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(3, weight=1)  # results row grows

        self.vgf_drop_icon = self._ui_icon("type", 46, light=RED, dark=RED_BRIGHT)
        dz = self._build_drop_zone(
            panel, row=0, icon=self.vgf_drop_icon,
            title="Drag & drop an image of some text here",
            hint="or click to browse  ·  a tight crop of large, clear text works best",
            on_drop=self.on_vg_font_drop, on_click=self.browse_vg_font, height=120,
        )
        self.vgf_drop = dz["zone"]
        self.vgf_icon_label = dz["icon"]
        self.vgf_primary = dz["primary"]
        self.vgf_secondary = dz["secondary"]

        # button row (Identify + Clear) — the results card needs the room
        btnrow = ctk.CTkFrame(panel, fg_color="transparent")
        btnrow.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 10))
        btnrow.grid_columnconfigure(0, weight=1)
        self.vgf_btn = GradientButton(
            btnrow, text="Identify Font", height=46, icon="type",
            busy_text="Identifying", command=self.on_vg_font_run, state="disabled",
        )
        self.vgf_btn.grid(row=0, column=0, sticky="ew")
        self._clear_button(btnrow, self.reset_vg_font).grid(row=0, column=1, padx=(10, 0))

        self.vgf_progress = ctk.CTkProgressBar(panel, height=8)
        self.vgf_progress.set(0)
        self.vgf_progress.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 4))
        self.vgf_progress.grid_remove()  # only while identifying

        # ---- results card: 5 fixed match rows (hidden until a run finishes) ----
        self.vgf_results = ctk.CTkFrame(panel, fg_color=CARD_SOFT, corner_radius=12)
        self.vgf_results.grid(row=3, column=0, sticky="new", padx=24, pady=(0, 8))
        self.vgf_results.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.vgf_results, text="Closest font matches",
                     font=self._font(14, "semibold"), anchor="w",
                     ).grid(row=0, column=0, sticky="ew", padx=18, pady=(8, 2))
        self.vgf_rows = []
        for i in range(5):
            row = ctk.CTkFrame(self.vgf_results, fg_color="transparent")
            row.grid(row=1 + i, column=0, sticky="ew", padx=18, pady=1)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row, text=f"{i + 1}.", width=22, text_color=MUTED,
                         anchor="w").grid(row=0, column=0)
            name = ctk.CTkLabel(row, text="", font=self._font(14, "semibold"),
                                anchor="w", justify="left", wraplength=380)
            name.grid(row=0, column=1, sticky="w")
            bar = ctk.CTkProgressBar(row, width=140, height=8, progress_color=RED)
            bar.set(0)
            bar.grid(row=0, column=2, padx=(12, 8))
            pct = ctk.CTkLabel(row, text="", width=48, text_color=MUTED, anchor="e")
            pct.grid(row=0, column=3)
            self.vgf_rows.append({"frame": row, "name": name, "bar": bar, "pct": pct})
        self.vgf_disclaimer = ctk.CTkLabel(
            self.vgf_results,
            text="⚠ Closest matches, not an exact ID — commercial fonts appear as "
                 "their nearest Google Font lookalike.",
            text_color=MUTED, anchor="w", justify="left", wraplength=620,
            font=ctk.CTkFont(size=11),
        )
        self.vgf_disclaimer.grid(row=6, column=0, sticky="ew", padx=18, pady=(4, 8))
        self.vgf_results.grid_remove()

        self.vgf_status = ctk.CTkLabel(
            panel, text="Drop an image of text to begin.", text_color=MUTED,
            wraplength=620, justify="left", anchor="w",
        )
        self.vgf_status.grid(row=4, column=0, sticky="w", padx=24, pady=(2, 10))
        return panel

    @staticmethod
    def _vg_tier_text(tier: str):
        """(light, dark) text color for the score + status line (WCAG AA)."""
        if tier in ("Human", "Likely Human"):
            return SUCCESS
        if tier == "Uncertain":
            return WARNING  # amber, AA on the light card
        return ERROR  # Likely AI / AI

    @staticmethod
    def _vg_tier_chip(tier: str) -> str:
        """Solid chip background dark enough for white text (>=4.5:1, both modes)."""
        if tier in ("Human", "Likely Human"):
            return "#0E6E39"
        if tier == "Uncertain":
            return "#8A4500"
        return "#B30F16"  # Likely AI / AI

    # ---- vanguard actions ------------------------------------------------ #
    def on_vanguard_drop(self, event):
        paths = self._parse_drop(event)
        if paths:
            self.set_vanguard_file(paths[0])

    def browse_vanguard(self):
        path = self._ask_open(
            "vanguard",
            title="Select a .txt / .docx / .pdf",
            filetypes=[("Documents", "*.txt *.docx *.pdf"), ("All files", "*.*")],
        )
        if path:
            self.set_vanguard_file(Path(path))

    def set_vanguard_file(self, path: Path):
        if not path.is_file():
            self.vg_source.configure(text=self._not_a_file_message(path), text_color=WARNING)
            return
        ext = detect_format(path)
        if ext not in ("txt", "docx", "pdf"):
            self.vg_source.configure(
                text=f"Unsupported: .{ext or '?'} — use .txt, .docx, or .pdf.",
                text_color=WARNING)
            return
        # Extract on a worker thread — a large PDF takes seconds to minutes and
        # would freeze the whole window if read here on the UI thread.
        run = self._vg_run
        self.vg_upload_btn.configure(state="disabled")
        self.vg_btn.configure(state="disabled")
        self.vg_source.configure(text=f"Loading {path.name}…", text_color=MUTED)
        threading.Thread(
            target=self._vg_load_worker, args=(path, run), daemon=True
        ).start()

    def _vg_load_worker(self, path: Path, run: int):
        try:
            text = extract_document_text(path)
            self.after(0, self._vg_load_done, path, text, None, run)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.after(0, self._vg_load_done, path, None, exc, run)

    def _vg_load_done(self, path: Path, text: str | None,
                      error: Exception | None, run: int):
        self.vg_upload_btn.configure(state="normal")
        if run != self._vg_run:
            return  # the user reset (or started a detect) while this loaded
        self.vg_btn.configure(state="normal")
        if error:
            self.vg_source.configure(text=f"Couldn't read {path.name}: {error}",
                                     text_color=ERROR)
            return
        self.vanguard_file = path
        self.vg_input.delete("1.0", "end")
        self.vg_input.insert("1.0", text)
        self.vg_source.configure(
            text=f"Loaded {path.name}  ·  {len(text.split()):,} words", text_color=MUTED)

    def reset_vanguard(self):
        """Clear input, results, highlights and score — back to the initial state."""
        self._vg_run += 1  # invalidate any in-flight load/detect worker
        self._job_finished_if_vg_running()
        self.vanguard_file = None
        self.vg_input.delete("1.0", "end")
        self.vg_source.configure(
            text="Nothing loaded — type, paste, or drop a file.", text_color=MUTED)
        # hide + clear the results card
        self.vg_results.grid_remove()
        self.vg_score.configure(text="—", text_color=TEXT)
        self.vg_chip.configure(text="", fg_color="transparent")
        self.vg_out.configure(state="normal")
        self.vg_out_text.delete("1.0", "end")
        self.vg_out.configure(state="disabled")
        # reset progress + status + buttons
        self.vg_progress.grid_remove()
        self.vg_progress.set(0)
        self.vg_btn.stop_busy()
        self.vg_btn.configure(state="normal")
        self.vg_upload_btn.configure(state="normal")
        self.vg_status.configure(text="Paste or upload text, then Detect.", text_color=MUTED)

    def _job_finished_if_vg_running(self):
        """Reset abandons a running detect; release its slot in the close guard."""
        if getattr(self, "_vg_detecting", False):
            self._vg_detecting = False
            self._job_finished()

    def on_vanguard_detect(self):
        text = self.vg_input.get("1.0", "end").strip()
        if len(text.split()) < 5:
            self.vg_status.configure(
                text="Please enter or upload some text first.", text_color=WARNING)
            return
        self._vg_run += 1
        run = self._vg_run
        self._vg_detecting = True
        self._job_started()
        self.vg_btn.configure(state="disabled")
        self.vg_btn.start_busy()
        self.vg_progress.grid()
        self.vg_progress.configure(mode="determinate")
        self.vg_progress.set(0)
        self.vg_status.configure(
            text="Analysing… (loading the detector model — the first run after launch "
                 "is slower).",
            text_color=MUTED)
        threading.Thread(target=self._vanguard_worker, args=(text, run), daemon=True).start()

    def _vanguard_worker(self, text: str, run: int):
        def on_progress(frac: float):
            self.after(0, self._set_vg_progress, frac, run)

        try:
            result = detect_ai_text(text, is_file=False, progress=on_progress)
            self.after(0, self._vanguard_done, result, None, run)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.after(0, self._vanguard_done, None, exc, run)

    def _set_vg_progress(self, frac: float, run: int):
        if run != self._vg_run:
            return  # stale: the user reset while the worker was running
        self.vg_progress.set(max(0.0, min(1.0, frac)))
        self.vg_status.configure(text=f"Analysing…  {int(frac * 100)}%", text_color=MUTED)

    def _vanguard_done(self, result: dict | None, error: Exception | None, run: int):
        if run != self._vg_run:
            return  # stale: Reset already cleaned up the UI (and the job slot)
        self._vg_detecting = False
        self._job_finished()
        self.vg_progress.grid_remove()
        self.vg_progress.set(0)
        self.vg_btn.configure(state="normal")
        self.vg_btn.stop_busy(success=error is None)
        if error:
            self.vg_status.configure(text=f"✕  {error}", text_color=ERROR)
            return
        self._render_vanguard_result(result)

    def _render_vanguard_result(self, result: dict):
        import bisect

        score, tier = result["score"], result["tier"]
        color = self._vg_tier_text(tier)
        self.vg_score.configure(text=f"{score}%", text_color=color)
        self.vg_chip.configure(text=f"  {tier}  ", fg_color=self._vg_tier_chip(tier))

        text = result["text"]
        # Tcl 8.6 stores astral-plane chars (emoji etc.) as surrogate pairs, so a
        # tk Text "chars" offset counts them as 2 — convert Python offsets.
        astral = [i for i, ch in enumerate(text) if ord(ch) > 0xFFFF]

        def tk_off(i: int) -> int:
            return i + bisect.bisect_left(astral, i)

        box = self.vg_out_text  # underlying tk.Text for tag-based highlighting
        self.vg_out.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.tag_config("ai", background="#C0392B", foreground="#FFFFFF")
        flagged = 0
        for sp in result["spans"]:
            if sp["p_ai"] >= FLAG_THRESHOLD:
                flagged += 1
                box.tag_add("ai", f"1.0 + {tk_off(sp['start'])} chars",
                            f"1.0 + {tk_off(sp['end'])} chars")
        self.vg_out.configure(state="disabled")

        self.vg_results.grid()
        caveat = "  ⚠ Short text — treat with extra caution." if result["too_short"] else ""
        self.vg_status.configure(
            text=f"✓  {tier} · {score}% AI-likelihood · {flagged} of {len(result['spans'])} "
                 f"passages flagged · {result['model']}.{caveat}",
            text_color=color)

    # ---- vanguard: text extraction actions --------------------------------- #
    def _on_vgo_model_change(self, tier: str):
        self.vgo_model_caption.configure(text=OCR_MODELS.get(tier, ("", ""))[1])

    def on_vg_ocr_drop(self, event):
        paths = self._parse_drop(event)
        if paths:
            self.set_vg_ocr_file(paths[0])

    def browse_vg_ocr(self):
        path = self._ask_open("vg_ocr", title="Select an image to extract text from",
                              filetypes=self._IMAGE_FILETYPES)
        if path:
            self.set_vg_ocr_file(Path(path))

    def set_vg_ocr_file(self, path: Path):
        if not path.is_file():
            self.vgo_status.configure(text=self._not_a_file_message(path),
                                      text_color=WARNING)
            return
        self.vg_ocr_file = self._set_image_file(
            path, icon_label=self.vgo_icon_label, default_icon=self.vgo_drop_icon,
            primary=self.vgo_primary, secondary=self.vgo_secondary,
            button=self.vgo_btn, status=self.vgo_status,
            detail="Image",
            ready_text=f"Ready to extract the text from {path.name}",
        )

    def on_vg_ocr_run(self):
        src = self.vg_ocr_file
        if not src:
            return
        tier = self.vgo_model.get() or DEFAULT_OCR_TIER
        self._job_started()
        self.vgo_btn.configure(state="disabled")
        self.vgo_btn.start_busy()
        self.vgo_progress.grid()
        self._fill_start(self.vgo_progress)
        note = (" (the first Max run downloads a small model once)"
                if tier == "Max" else
                " (the first run after launch loads the OCR models and is slower)")
        self.vgo_status.configure(
            text=f"Reading the image with {tier}…{note}", text_color=MUTED)
        threading.Thread(target=self._vg_ocr_worker, args=(src, tier),
                         daemon=True).start()

    def _vg_ocr_worker(self, src: Path, tier: str):
        try:
            result = extract_text(src, model=tier)
            self.after(0, self._vg_ocr_done, src, result, None)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.after(0, self._vg_ocr_done, src, None, exc)

    def _vg_ocr_done(self, src: Path, result: dict | None, error: Exception | None):
        self._fill_stop(self.vgo_progress)
        self._job_finished()
        self.vgo_progress.grid_remove()
        self.vgo_progress.set(0)
        self.vgo_btn.configure(state="normal")
        self.vgo_btn.stop_busy(success=error is None and bool(result and result["count"]))
        if error:
            self.vgo_status.configure(text=f"✕  {error}", text_color=ERROR)
            return
        if not result["count"]:
            self.vgo_results.grid_remove()
            self.vgo_status.configure(
                text=f"No text found in {src.name} — try a sharper or closer image.",
                text_color=WARNING)
            return
        self.vgo_out.configure(state="normal")
        self.vgo_out.delete("1.0", "end")
        self.vgo_out.insert("1.0", result["text"])
        self.vgo_out.configure(state="disabled")
        self.vgo_results.grid()
        chars = len(result["text"])
        self.vgo_status.configure(
            text=f"✓  Extracted {result['count']} line(s) · {chars:,} characters "
                 f"from {src.name}.",
            text_color=SUCCESS)

    def _vg_ocr_copy(self):
        text = self.vgo_out.get("1.0", "end").rstrip("\n")
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.vgo_status.configure(text=f"✓  Copied {len(text):,} characters to the "
                                       "clipboard.", text_color=SUCCESS)

    def reset_vg_ocr(self):
        self._reset_image_tool(
            file_attr="vg_ocr_file", icon_label=self.vgo_icon_label,
            drop_icon=self.vgo_drop_icon, primary=self.vgo_primary,
            secondary=self.vgo_secondary,
            primary_text="Drag & drop a screenshot or photo here",
            hint_text="or click to browse  ·  JPG · PNG · WEBP · BMP · GIF · TIFF",
            button=self.vgo_btn, progress=self.vgo_progress, results=self.vgo_results,
            status=self.vgo_status, status_text="Drop an image to begin.")

    # ---- vanguard: what's-the-font actions --------------------------------- #
    def on_vg_font_drop(self, event):
        paths = self._parse_drop(event)
        if paths:
            self.set_vg_font_file(paths[0])

    def browse_vg_font(self):
        path = self._ask_open("vg_font", title="Select an image of text",
                              filetypes=self._IMAGE_FILETYPES)
        if path:
            self.set_vg_font_file(Path(path))

    def set_vg_font_file(self, path: Path):
        if not path.is_file():
            self.vgf_status.configure(text=self._not_a_file_message(path),
                                      text_color=WARNING)
            return
        self.vg_font_file = self._set_image_file(
            path, icon_label=self.vgf_icon_label, default_icon=self.vgf_drop_icon,
            primary=self.vgf_primary, secondary=self.vgf_secondary,
            button=self.vgf_btn, status=self.vgf_status,
            detail="Image",
            ready_text=f"Ready to identify the font in {path.name}",
        )

    def on_vg_font_run(self):
        src = self.vg_font_file
        if not src:
            return
        self._job_started()
        self.vgf_btn.configure(state="disabled")
        self.vgf_btn.start_busy()
        self.vgf_progress.grid()
        self._fill_start(self.vgf_progress)
        self.vgf_status.configure(
            text="Matching the lettering… (the first ever run downloads the "
                 "~64 MB font model once).",
            text_color=MUTED)
        threading.Thread(target=self._vg_font_worker, args=(src,), daemon=True).start()

    def _vg_font_worker(self, src: Path):
        try:
            result = identify_font(src, top_k=5)
            self.after(0, self._vg_font_done, src, result, None)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.after(0, self._vg_font_done, src, None, exc)

    def _vg_font_done(self, src: Path, result: dict | None, error: Exception | None):
        self._fill_stop(self.vgf_progress)
        self._job_finished()
        self.vgf_progress.grid_remove()
        self.vgf_progress.set(0)
        self.vgf_btn.configure(state="normal")
        self.vgf_btn.stop_busy(success=error is None)
        if error:
            self.vgf_status.configure(text=f"✕  {error}", text_color=ERROR)
            return
        matches = result["matches"]
        for i, slot in enumerate(self.vgf_rows):
            if i < len(matches):
                m = matches[i]
                slot["name"].configure(text=m["name"])
                slot["bar"].set(m["prob"])
                slot["pct"].configure(text=f"{m['prob']:.0%}")
                slot["frame"].grid()
            else:
                slot["frame"].grid_remove()
        self.vgf_results.grid()
        best = matches[0]
        self.vgf_status.configure(
            text=f"✓  Best match: {best['name']} ({best['prob']:.0%}) — "
                 f"closest of ~3,500 Google Fonts for {src.name}.",
            text_color=SUCCESS)

    def reset_vg_font(self):
        self._reset_image_tool(
            file_attr="vg_font_file", icon_label=self.vgf_icon_label,
            drop_icon=self.vgf_drop_icon, primary=self.vgf_primary,
            secondary=self.vgf_secondary,
            primary_text="Drag & drop an image of some text here",
            hint_text="or click to browse  ·  a tight crop of large, clear text works best",
            button=self.vgf_btn, progress=self.vgf_progress, results=self.vgf_results,
            status=self.vgf_status, status_text="Drop an image of text to begin.")

    # ===================================================================== #
    # Sonara — audio tools (stem splitter)
    # ===================================================================== #
    def _build_sonara(self, parent) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(4, weight=1)  # player row grows
        self._section_header(
            frame, "Sonara",
            "Audio tools — split a song into Vocals, Drums, Bass and Other.",
        )

        self.sn_drop_icon = self._ui_icon("audio-lines", 46, light=RED, dark=RED_BRIGHT)
        dz = self._build_drop_zone(
            frame, row=1, icon=self.sn_drop_icon,
            title="Drag & drop a song here",
            hint="or click to browse  ·  MP3 · WAV · FLAC · M4A · OGG · MP4",
            on_drop=self.on_sonara_drop, on_click=self.browse_sonara, height=120,
        )
        self.sn_drop = dz["zone"]
        self.sn_icon_label = dz["icon"]
        self.sn_primary = dz["primary"]
        self.sn_secondary = dz["secondary"]

        btnrow = ctk.CTkFrame(frame, fg_color="transparent")
        btnrow.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 10))
        btnrow.grid_columnconfigure(0, weight=1)
        self.sn_btn = GradientButton(
            btnrow, text="Split Stems", height=46, icon="audio-lines",
            busy_text="Splitting", command=self.on_sonara_split, state="disabled",
        )
        self.sn_btn.grid(row=0, column=0, sticky="ew")
        self._clear_button(btnrow, self.reset_sonara).grid(row=0, column=1, padx=(10, 0))

        self.sn_progress = ctk.CTkProgressBar(frame, height=8)
        self.sn_progress.set(0)
        self.sn_progress.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 4))
        self.sn_progress.grid_remove()  # only while splitting

        # ---- player card (hidden until a split finishes) ----
        self.sn_player_card = ctk.CTkFrame(frame, fg_color=CARD_SOFT, corner_radius=12)
        self.sn_player_card.grid(row=4, column=0, sticky="new", padx=24, pady=(0, 8))
        self.sn_player_card.grid_columnconfigure(0, weight=1)

        transport = ctk.CTkFrame(self.sn_player_card, fg_color="transparent")
        transport.grid(row=0, column=0, sticky="ew", padx=18, pady=(12, 2))
        transport.grid_columnconfigure(1, weight=1)
        self.sn_play_btn = ctk.CTkButton(
            transport, text=self.PLAY_GLYPH, width=46, height=34,
            font=ctk.CTkFont(family="Segoe UI Symbol", size=16),
            fg_color=RED, hover_color=RED_HOVER,
            command=self._sn_toggle_play,
        )
        self.sn_play_btn.grid(row=0, column=0)
        self.sn_seek = ctk.CTkSlider(transport, from_=0, to=1000,
                                     command=self._sn_on_seek)
        self.sn_seek.set(0)
        self.sn_seek.grid(row=0, column=1, sticky="ew", padx=(14, 14))
        self.sn_time = ctk.CTkLabel(transport, text="0:00 / 0:00",
                                    text_color=MUTED, width=92, anchor="e")
        self.sn_time.grid(row=0, column=2)

        # ---- 4 stem rows: icon · name · M · S · volume · Save ----
        self.sn_rows: dict[str, dict] = {}
        for i, (stem, (label, icon)) in enumerate(SONARA_STEM_META.items()):
            row = ctk.CTkFrame(self.sn_player_card, fg_color="transparent")
            row.grid(row=1 + i, column=0, sticky="ew", padx=18, pady=4)
            row.grid_columnconfigure(3, weight=1)
            ctk.CTkLabel(row, text="", width=26,
                         image=self._ui_icon(icon, 20)).grid(row=0, column=0)
            ctk.CTkLabel(row, text=label, width=66, anchor="w",
                         font=self._font(14, "semibold")).grid(row=0, column=1,
                                                               padx=(6, 4))
            mute = ctk.CTkButton(
                row, text="M", width=30, height=28,
                font=self._font(12, "semibold"),
                fg_color="transparent", border_width=1, border_color=MUTED,
                text_color=NAV_TEXT, hover_color=("#EBE0E1", "#2A2426"),
                command=lambda s=stem: self._sn_toggle_mute(s),
            )
            mute.grid(row=0, column=2, padx=(0, 4))
            solo = ctk.CTkButton(
                row, text="S", width=30, height=28,
                font=self._font(12, "semibold"),
                fg_color="transparent", border_width=1, border_color=MUTED,
                text_color=NAV_TEXT, hover_color=("#EBE0E1", "#2A2426"),
                command=lambda s=stem: self._sn_toggle_solo(s),
            )
            solo.grid(row=0, column=3, sticky="w")
            vol = ctk.CTkSlider(row, from_=0, to=100, width=230,
                                command=lambda v, s=stem: self._sn_set_volume(s, v))
            vol.set(100)
            vol.grid(row=0, column=4, padx=(10, 10), sticky="e")
            save = ctk.CTkButton(
                row, text="Save", width=64, height=28,
                command=lambda s=stem: self.on_sn_save_stem(s),
            )
            save.grid(row=0, column=5)
            self.sn_rows[stem] = {"mute": mute, "solo": solo,
                                  "volume": vol, "save": save}

        ctk.CTkLabel(
            self.sn_player_card,
            text="M mutes a stem in the mix · S plays only the soloed stem(s) · "
                 "Save exports a stem next to the original song.",
            text_color=MUTED, anchor="w", justify="left", wraplength=620,
            font=ctk.CTkFont(size=11),
        ).grid(row=5, column=0, sticky="ew", padx=18, pady=(4, 12))
        self.sn_player_card.grid_remove()

        self.sn_status = ctk.CTkLabel(
            frame, text="Drop a song to begin.", text_color=MUTED,
            wraplength=620, justify="left", anchor="w",
        )
        self.sn_status.grid(row=5, column=0, sticky="w", padx=24, pady=(2, 10))
        return frame

    PLAY_GLYPH = "▶"
    PAUSE_GLYPH = "⏸"

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        seconds = max(0, int(seconds))
        return f"{seconds // 60}:{seconds % 60:02d}"

    # ---- sonara: file selection ------------------------------------------- #
    def on_sonara_drop(self, event):
        paths = self._parse_drop(event)
        if paths:
            self.set_sonara_file(paths[0])

    def browse_sonara(self):
        path = self._ask_open(
            "sonara", title="Select a song",
            filetypes=[("Audio", "*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.opus "
                                 "*.wma *.aiff *.mp4 *.webm *.mkv"),
                       ("All files", "*.*")],
        )
        if path:
            self.set_sonara_file(Path(path))

    def set_sonara_file(self, path: Path):
        if not path.is_file():
            self.sn_status.configure(text=self._not_a_file_message(path),
                                     text_color=WARNING)
            return
        ext = detect_format(path)
        self.sn_primary.configure(text=path.name)
        if ext not in AUDIO_EXTS:
            self.sn_icon_label.configure(image=self.sn_drop_icon)
            self.sn_secondary.configure(text="Not an audio file  ·  click to choose another")
            self.sn_btn.configure(state="disabled")
            self.sn_status.configure(
                text=f"Unsupported file: .{ext or '?'} — pick an audio file.",
                text_color=WARNING)
            self.sonara_file = None
            return
        ft_icon = self._filetype_icon(ext, 52)
        if ft_icon is not None:
            self.sn_icon_label.configure(image=ft_icon)
        try:
            size = human_size(path.stat().st_size)
        except OSError:
            size = "?"
        self.sn_secondary.configure(text=f"Audio  ·  {size}  ·  click to choose another")
        self.sn_btn.configure(state="normal")
        self.sn_status.configure(text=f"Ready to split {path.name} into 4 stems.",
                                 text_color=MUTED)
        self.sonara_file = path

    # ---- sonara: splitting -------------------------------------------------- #
    def on_sonara_split(self):
        src = self.sonara_file
        if not src:
            return
        self._sn_run += 1
        run = self._sn_run
        self._sn_close_player()  # stop + drop any previous mix
        self.sn_player_card.grid_remove()
        self._job_started()
        self.sn_btn.configure(state="disabled")
        self.sn_btn.start_busy()
        self.sn_progress.grid()
        self.sn_progress.configure(mode="determinate")
        self.sn_progress.set(0)
        first_run = ("  ·  First run: downloading the Demucs model (~320 MB, "
                     "one-time)…" if not model_is_cached() else "")
        self.sn_status.configure(
            text=f"Splitting {src.name} with {SONARA_MODEL}…{first_run}",
            text_color=MUTED)
        threading.Thread(target=self._sonara_worker, args=(src, run),
                         daemon=True).start()

    def _sonara_worker(self, src: Path, run: int):
        def on_progress(frac: float):
            self.after(0, self._set_sn_progress, frac, run)

        try:
            result = split_stems(src, progress=on_progress)
            self.after(0, self._sonara_done, src, result, None, run)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.after(0, self._sonara_done, src, None, exc, run)

    def _set_sn_progress(self, frac: float, run: int):
        if run != self._sn_run:
            return
        self.sn_progress.set(max(0.0, min(1.0, frac)))
        self.sn_status.configure(text=f"Splitting…  {int(frac * 100)}%",
                                 text_color=MUTED)

    def _sonara_done(self, src: Path, result: dict | None,
                     error: Exception | None, run: int):
        self._job_finished()
        if run != self._sn_run:
            return  # a newer split superseded this one
        self.sn_progress.grid_remove()
        self.sn_progress.set(0)
        self.sn_btn.configure(state="normal")
        self.sn_btn.stop_busy(success=error is None)
        if error:
            self.sn_status.configure(text=f"✕  {error}", text_color=ERROR)
            return
        self.sonara_result = result
        self.sonara_player = StemPlayer(result["stems"], result["samplerate"])
        # reset the mixer UI to a clean state
        for stem, row in self.sn_rows.items():
            row["volume"].set(100)
            self._sn_style_toggle(row["mute"], False)
            self._sn_style_toggle(row["solo"], False)
        self.sn_seek.set(0)
        self.sn_play_btn.configure(text=self.PLAY_GLYPH)
        self.sn_time.configure(
            text=f"0:00 / {self._fmt_time(result['duration'])}")
        self.sn_player_card.grid()
        device = "GPU" if result["device"] == "cuda" else "CPU"
        self.sn_status.configure(
            text=f"✓  Split {src.name} into 4 stems on the {device} · play the mix, "
                 "tweak M/S/volume, and Save the stems you want.",
            text_color=SUCCESS)

    # ---- sonara: playback ---------------------------------------------------- #
    def _sn_close_player(self):
        self._sn_stop_tick()
        if self.sonara_player is not None:
            self.sonara_player.close()
            self.sonara_player = None
        self.sonara_result = None

    def reset_sonara(self):
        # Bump the generation counter so an in-flight split's _sonara_done no-ops.
        self._sn_run += 1
        self._sn_close_player()
        self.sn_player_card.grid_remove()
        self._reset_image_tool(
            file_attr="sonara_file", icon_label=self.sn_icon_label,
            drop_icon=self.sn_drop_icon, primary=self.sn_primary,
            secondary=self.sn_secondary, primary_text="Drag & drop a song here",
            hint_text="or click to browse  ·  MP3 · WAV · FLAC · M4A · OGG · MP4",
            button=self.sn_btn, progress=self.sn_progress, status=self.sn_status,
            status_text="Drop a song to begin.")

    def _sn_toggle_play(self):
        player = self.sonara_player
        if player is None:
            return
        player.toggle()
        if player.is_playing:
            self.sn_play_btn.configure(text=self.PAUSE_GLYPH)
            self._sn_tick()
        else:
            self.sn_play_btn.configure(text=self.PLAY_GLYPH)
            self._sn_stop_tick()

    def _sn_stop_tick(self):
        if self._sn_tick_after is not None:
            self.after_cancel(self._sn_tick_after)
            self._sn_tick_after = None

    def _sn_tick(self):
        self._sn_tick_after = None
        player = self.sonara_player
        if player is None:
            return
        frac = player.position / player.duration if player.duration else 0.0
        self._sn_slider_drag = True
        self.sn_seek.set(frac * 1000)
        self._sn_slider_drag = False
        self.sn_time.configure(
            text=f"{self._fmt_time(player.position)} / {self._fmt_time(player.duration)}")
        if player.finished or not player.is_playing:
            self.sn_play_btn.configure(text=self.PLAY_GLYPH)
            return
        self._sn_tick_after = self.after(100, self._sn_tick)

    def _sn_on_seek(self, value: float):
        if self._sn_slider_drag:  # the tick loop is writing the slider, not the user
            return
        player = self.sonara_player
        if player is None:
            return
        player.seek(float(value) / 1000.0)
        self.sn_time.configure(
            text=f"{self._fmt_time(player.position)} / {self._fmt_time(player.duration)}")

    def _sn_style_toggle(self, button, active: bool):
        button.configure(
            fg_color=RED if active else "transparent",
            text_color="#FFFFFF" if active else NAV_TEXT,
            border_color=RED if active else MUTED,
        )

    def _sn_toggle_mute(self, stem: str):
        player = self.sonara_player
        if player is None:
            return
        muted = not player.muted[stem]
        player.set_mute(stem, muted)
        self._sn_style_toggle(self.sn_rows[stem]["mute"], muted)

    def _sn_toggle_solo(self, stem: str):
        player = self.sonara_player
        if player is None:
            return
        soloed = not player.soloed[stem]
        player.set_solo(stem, soloed)
        self._sn_style_toggle(self.sn_rows[stem]["solo"], soloed)

    def _sn_set_volume(self, stem: str, value: float):
        if self.sonara_player is not None:
            self.sonara_player.set_volume(stem, float(value) / 100.0)

    # ---- sonara: saving stems ------------------------------------------------ #
    def on_sn_save_stem(self, stem: str):
        result, src = self.sonara_result, self.sonara_file
        if not result or not src:
            return
        out = self._ask_save(
            "sonara_save",
            title=f"Save the {SONARA_STEM_META[stem][0]} stem as",
            defaultextension=".wav",
            initialdir=str(src.parent),
            initialfile=f"{src.stem}_{stem}.wav",
            filetypes=[("WAV audio", "*.wav"), ("MP3 audio", "*.mp3")],
        )
        if not out:
            self.sn_status.configure(text="Cancelled (no save location chosen).",
                                     text_color=MUTED)
            return
        self._job_started()
        self.sn_rows[stem]["save"].configure(state="disabled")
        self.sn_status.configure(text=f"Saving the {stem} stem…", text_color=MUTED)
        threading.Thread(
            target=self._sn_save_worker,
            args=(stem, result["stems"][stem], result["samplerate"], Path(out)),
            daemon=True,
        ).start()

    def _sn_save_worker(self, stem: str, array, samplerate: int, out: Path):
        try:
            # overwrite=True: the save dialog already confirmed replacing `out`.
            saved = save_stem(array, samplerate, out, overwrite=True)
            self.after(0, self._sn_save_done, stem, saved, None)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.after(0, self._sn_save_done, stem, None, exc)

    def _sn_save_done(self, stem: str, out: Path | None, error: Exception | None):
        self._job_finished()
        self.sn_rows[stem]["save"].configure(state="normal")
        if error:
            self.sn_status.configure(text=f"✕  {error}", text_color=ERROR)
            if self.sonara_file:
                self.add_history(self.sonara_file, None, False, error)
            return
        self.sn_status.configure(text=f"✓  Saved to {out}", text_color=SUCCESS)
        if self.sonara_file:
            self.add_history(self.sonara_file, out, True)

    # ===================================================================== #
    # Nexus — everyday utilities (Converter + QR Code)
    # ===================================================================== #
    def _build_nexus(self, parent) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)
        self._section_header(
            frame, "Nexus",
            "Everyday utilities — convert currency, units and time zones, or "
            "make a QR code. All local, no account, no limits.",
        )

        # ---- tool switcher (same pattern as Marquee / Vanguard) ----
        switch = ctk.CTkFrame(frame, fg_color="transparent")
        switch.grid(row=1, column=0, sticky="w", padx=24, pady=(2, 6))
        self.nx_tool = ctk.CTkSegmentedButton(
            switch, values=["Converter", "QR Code"], command=self._show_nx_tool,
            selected_color=RED, selected_hover_color=RED_HOVER,
        )
        self.nx_tool.set("Converter")
        self.nx_tool.grid(row=0, column=0)

        # ---- tool panels (only one shown at a time) ----
        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.grid(row=2, column=0, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)
        self.nx_panels = {
            "Converter": self._build_nx_convert(container),
            "QR Code": self._build_nx_qr(container),
        }
        for p in self.nx_panels.values():
            p.grid(row=0, column=0, sticky="nsew")
        self._show_nx_tool("Converter")
        return frame

    def _show_nx_tool(self, name: str):
        for n, panel in self.nx_panels.items():
            (panel.grid if n == name else panel.grid_remove)()

    # ---- shared live-conversion helpers ---------------------------------- #
    def _bind_typing(self, widget, handler) -> None:
        """Fire `handler` live as the user types (entry or combobox)."""
        for t in (widget, getattr(widget, "_entry", None)):
            if t is None:
                continue
            try:
                t.bind("<KeyRelease>", handler, add="+")
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def _parse_float(text: str):
        text = (text or "").strip().replace(",", "")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _fmt_num(x: float) -> str:
        """Tidy number: integers grouped, otherwise 6 significant figures."""
        if abs(x) < 1e15 and float(x).is_integer():
            return f"{int(x):,}"
        return f"{x:,.6g}"

    def _fmt_money(self, x: float) -> str:
        return f"{x:,.2f}" if abs(x) >= 1 else f"{x:,.6f}"

    @staticmethod
    def _code_from_label(label: str) -> str:
        return (label or "").strip().split(" — ")[0].split()[0].upper() if label else ""

    # ---- nexus: converter panel ------------------------------------------ #
    def _build_nx_convert(self, parent) -> ctk.CTkFrame:
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.grid_columnconfigure(0, weight=1)

        cat = ctk.CTkFrame(panel, fg_color="transparent")
        cat.grid(row=0, column=0, sticky="w", padx=24, pady=(4, 8))
        self.nxc_cat = ctk.CTkSegmentedButton(
            cat, values=["Currency", "Units", "Time Zone"],
            command=self._show_nxc_cat,
            selected_color=RED, selected_hover_color=RED_HOVER,
        )
        self.nxc_cat.set("Currency")
        self.nxc_cat.grid(row=0, column=0)

        # input card holds the three swappable category sub-frames
        incard = ctk.CTkFrame(panel, fg_color=CARD_SOFT, corner_radius=12)
        incard.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 10))
        incard.grid_columnconfigure(0, weight=1)
        incard.grid_rowconfigure(0, weight=1)
        self.nxc_frames = {
            "Currency": self._build_nxc_currency(incard),
            "Units": self._build_nxc_units(incard),
            "Time Zone": self._build_nxc_timezone(incard),
        }
        for f in self.nxc_frames.values():
            f.grid(row=0, column=0, sticky="nsew")

        # shared result + actions card
        res = ctk.CTkFrame(panel, fg_color=CARD_SOFT, corner_radius=12)
        res.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 10))
        res.grid_columnconfigure(0, weight=1)
        self.nxc_result = ctk.CTkLabel(
            res, text="—", font=self._font(26, "semibold"), text_color=RED,
            anchor="w", justify="left", wraplength=560)
        self.nxc_result.grid(row=0, column=0, sticky="w", padx=18, pady=(14, 0))
        self.nxc_detail = ctk.CTkLabel(
            res, text="", text_color=MUTED, anchor="w", justify="left",
            wraplength=560)
        self.nxc_detail.grid(row=1, column=0, sticky="w", padx=18, pady=(2, 8))
        actions = ctk.CTkFrame(res, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="w", padx=18, pady=(0, 14))
        self.nxc_swap = ctk.CTkButton(
            actions, text=" Swap", width=104, image=self._ui_icon("arrow-left-right", 16),
            compound="left", fg_color="transparent", border_width=1, border_color=MUTED,
            text_color=NAV_TEXT, hover_color=("#EBE0E1", "#2A2426"),
            command=self._nxc_swap)
        self.nxc_swap.grid(row=0, column=0, padx=(0, 10))
        self.nxc_copy = ctk.CTkButton(
            actions, text="Copy result", width=130, command=self._nxc_copy)
        self.nxc_copy.grid(row=0, column=1)
        ctk.CTkButton(
            actions, text="Reset", width=90, fg_color="transparent", border_width=1,
            border_color=MUTED, text_color=NAV_TEXT,
            hover_color=("#EBE0E1", "#2A2426"), command=self.reset_nxc,
        ).grid(row=0, column=2, padx=(10, 0))
        self._make_labels_wrap(res, (self.nxc_result, self.nxc_detail))

        self.nxc_status = ctk.CTkLabel(
            panel, text="", text_color=MUTED, anchor="w", justify="left",
            wraplength=620)
        self.nxc_status.grid(row=3, column=0, sticky="w", padx=24, pady=(0, 8))

        self._show_nxc_cat("Currency")
        return panel

    def _show_nxc_cat(self, name: str):
        self.nxc_cat.set(name)  # keep state correct when called programmatically
        for n, f in self.nxc_frames.items():
            (f.grid if n == name else f.grid_remove)()
        self._nxc_compute()

    def _build_nxc_currency(self, parent) -> ctk.CTkFrame:
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        # rates load lazily from cache/seed; populate the dropdowns from them
        try:
            self._nx_ensure_rates()
        except Exception as exc:  # noqa: BLE001
            print("Could not load currency rates:", exc)
        self._nxc_currency_choices = self._currency_choices()
        choices = self._nxc_currency_choices

        row = ctk.CTkFrame(f, fg_color="transparent")
        row.grid(row=0, column=0, sticky="w", padx=18, pady=(14, 4))
        ctk.CTkLabel(row, text="AMOUNT", font=self._font(11, "medium"),
                     text_color=MUTED).grid(row=0, column=0, sticky="w", padx=2)
        ctk.CTkLabel(row, text="FROM  (type to search)", font=self._font(11, "medium"),
                     text_color=MUTED).grid(row=0, column=1, sticky="w", padx=2)
        ctk.CTkLabel(row, text="TO", font=self._font(11, "medium"),
                     text_color=MUTED).grid(row=0, column=3, sticky="w", padx=(16, 2))
        self.nxc_amount = ctk.CTkEntry(row, width=90)
        self.nxc_amount.insert(0, "1")
        self.nxc_amount.grid(row=1, column=0, padx=(2, 12))
        self._bind_typing(self.nxc_amount, self._nxc_schedule)
        self.nxc_from = ctk.CTkComboBox(row, values=choices, width=215,
                                        command=lambda _v: self._nxc_schedule())
        self.nxc_from.set(currency_label("USD") if "USD" in (self.nx_rates or {})
                          else choices[0])
        self.nxc_from.grid(row=1, column=1)
        self._attach_search(self.nxc_from, lambda: self._nxc_currency_choices,
                            self._nxc_schedule)
        ctk.CTkLabel(row, text="→", font=self._font(20, "semibold"),
                     text_color=RED).grid(row=1, column=2, padx=10)
        self.nxc_to = ctk.CTkComboBox(row, values=choices, width=215,
                                      command=lambda _v: self._nxc_schedule())
        self.nxc_to.set(currency_label("EUR"))
        self.nxc_to.grid(row=1, column=3)
        self._attach_search(self.nxc_to, lambda: self._nxc_currency_choices,
                            self._nxc_schedule)

        rrow = ctk.CTkFrame(f, fg_color="transparent")
        rrow.grid(row=1, column=0, sticky="w", padx=18, pady=(8, 14))
        self.nxc_rates_label = ctk.CTkLabel(rrow, text="", text_color=MUTED)
        self.nxc_rates_label.grid(row=0, column=0, padx=(0, 12))
        self.nxc_refresh = ctk.CTkButton(
            rrow, text=" Refresh", width=104, image=self._ui_icon("repeat", 14),
            compound="left", fg_color="transparent", border_width=1, border_color=MUTED,
            text_color=NAV_TEXT, hover_color=("#EBE0E1", "#2A2426"),
            command=self._nxc_refresh_rates)
        self.nxc_refresh.grid(row=0, column=1)
        self._nxc_update_rates_label()
        return f

    def _build_nxc_units(self, parent) -> ctk.CTkFrame:
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        catrow = ctk.CTkFrame(f, fg_color="transparent")
        catrow.grid(row=0, column=0, sticky="w", padx=18, pady=(14, 6))
        ctk.CTkLabel(catrow, text="CATEGORY", font=self._font(11, "medium"),
                     text_color=MUTED).grid(row=0, column=0, padx=(0, 10))
        self.nxc_unit_cat = ctk.CTkOptionMenu(
            catrow, values=list(UNIT_CATEGORIES), width=170,
            command=self._nxc_unit_cat_change)
        self.nxc_unit_cat.set(DEFAULT_UNIT_CATEGORY)
        self.nxc_unit_cat.grid(row=0, column=1)

        row = ctk.CTkFrame(f, fg_color="transparent")
        row.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 14))
        ctk.CTkLabel(row, text="VALUE", font=self._font(11, "medium"),
                     text_color=MUTED).grid(row=0, column=0, sticky="w", padx=2)
        ctk.CTkLabel(row, text="FROM", font=self._font(11, "medium"),
                     text_color=MUTED).grid(row=0, column=1, sticky="w", padx=2)
        ctk.CTkLabel(row, text="TO", font=self._font(11, "medium"),
                     text_color=MUTED).grid(row=0, column=3, sticky="w", padx=(16, 2))
        self.nxc_value = ctk.CTkEntry(row, width=100)
        self.nxc_value.insert(0, "1")
        self.nxc_value.grid(row=1, column=0, padx=(2, 12))
        self._bind_typing(self.nxc_value, self._nxc_schedule)
        self.nxc_unit_from = ctk.CTkOptionMenu(
            row, values=["-"], width=180, command=lambda _v: self._nxc_schedule())
        self.nxc_unit_from.grid(row=1, column=1)
        ctk.CTkLabel(row, text="→", font=self._font(20, "semibold"),
                     text_color=RED).grid(row=1, column=2, padx=10)
        self.nxc_unit_to = ctk.CTkOptionMenu(
            row, values=["-"], width=180, command=lambda _v: self._nxc_schedule())
        self.nxc_unit_to.grid(row=1, column=3)
        self._nxc_unit_cat_change(DEFAULT_UNIT_CATEGORY)
        return f

    def _nxc_unit_cat_change(self, cat: str):
        labels = [lbl for lbl, _ in UNIT_CATEGORIES.get(cat, [])]
        if not labels:
            return
        self.nxc_unit_cat.set(cat)  # keep state correct when called programmatically
        self.nxc_unit_from.configure(values=labels)
        self.nxc_unit_to.configure(values=labels)
        self.nxc_unit_from.set(labels[0])
        self.nxc_unit_to.set(labels[1] if len(labels) > 1 else labels[0])
        self._nxc_schedule()

    def _build_nxc_timezone(self, parent) -> ctk.CTkFrame:
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        # Full IANA set for search; show the short curated list until the user types.
        self._nxc_tz_list = list_timezones()
        self._nxc_tz_common = [z for z in COMMON_TIMEZONES
                               if z in self._nxc_tz_list] or self._nxc_tz_list
        common = self._nxc_tz_common

        row = ctk.CTkFrame(f, fg_color="transparent")
        row.grid(row=0, column=0, sticky="w", padx=18, pady=(14, 4))
        ctk.CTkLabel(row, text="DATE & TIME", font=self._font(11, "medium"),
                     text_color=MUTED).grid(row=0, column=0, sticky="w", padx=2)
        self.nxc_dt = ctk.CTkEntry(row, width=190)
        self.nxc_dt.insert(0, parse_datetime("now").strftime("%Y-%m-%d %H:%M"))
        self.nxc_dt.grid(row=1, column=0, padx=(2, 8))
        self._bind_typing(self.nxc_dt, self._nxc_schedule)
        ctk.CTkButton(row, text="Now", width=60, fg_color="transparent",
                      border_width=1, border_color=MUTED, text_color=NAV_TEXT,
                      hover_color=("#EBE0E1", "#2A2426"),
                      command=self._nxc_set_now).grid(row=1, column=1)

        zrow = ctk.CTkFrame(f, fg_color="transparent")
        zrow.grid(row=1, column=0, sticky="w", padx=18, pady=(8, 8))
        ctk.CTkLabel(zrow, text="FROM ZONE  (type to search)",
                     font=self._font(11, "medium"),
                     text_color=MUTED).grid(row=0, column=0, sticky="w", padx=2)
        ctk.CTkLabel(zrow, text="TO ZONE  (type to search)",
                     font=self._font(11, "medium"),
                     text_color=MUTED).grid(row=0, column=2, sticky="w", padx=(16, 2))
        self.nxc_tz_from = ctk.CTkComboBox(zrow, values=common, width=240,
                                           command=lambda _v: self._nxc_schedule())
        self.nxc_tz_from.set("Asia/Dubai" if "Asia/Dubai" in self._nxc_tz_list else "UTC")
        self.nxc_tz_from.grid(row=1, column=0)
        self._attach_search(self.nxc_tz_from, lambda: self._nxc_tz_list,
                            self._nxc_schedule, lambda: self._nxc_tz_common)
        ctk.CTkLabel(zrow, text="→", font=self._font(20, "semibold"),
                     text_color=RED).grid(row=1, column=1, padx=10)
        self.nxc_tz_to = ctk.CTkComboBox(zrow, values=common, width=240,
                                         command=lambda _v: self._nxc_schedule())
        self.nxc_tz_to.set("America/New_York"
                           if "America/New_York" in self._nxc_tz_list else "UTC")
        self.nxc_tz_to.grid(row=1, column=2)
        self._attach_search(self.nxc_tz_to, lambda: self._nxc_tz_list,
                            self._nxc_schedule, lambda: self._nxc_tz_common)

        # pinned world clock
        wc = ctk.CTkFrame(f, fg_color="transparent")
        wc.grid(row=2, column=0, sticky="w", padx=18, pady=(4, 14))
        ctk.CTkLabel(wc, text="WORLD CLOCK", font=self._font(11, "medium"),
                     text_color=MUTED).grid(row=0, column=0, columnspan=2,
                                            sticky="w", pady=(0, 2))
        self.nxc_world_rows = {}
        for i, z in enumerate(WORLD_CLOCK_ZONES):
            ctk.CTkLabel(wc, text=z, text_color=TEXT, anchor="w", width=150).grid(
                row=1 + i, column=0, sticky="w")
            lbl = ctk.CTkLabel(wc, text="—", text_color=MUTED, anchor="w")
            lbl.grid(row=1 + i, column=1, sticky="w", padx=(12, 0))
            self.nxc_world_rows[z] = lbl
        return f

    def _nxc_set_now(self):
        self.nxc_dt.delete(0, "end")
        self.nxc_dt.insert(0, parse_datetime("now").strftime("%Y-%m-%d %H:%M"))
        self._nxc_compute()

    # ---- nexus converter: live recompute --------------------------------- #
    def _nxc_schedule(self, *_):
        if self._nxc_after is not None:
            try:
                self.after_cancel(self._nxc_after)
            except Exception:  # noqa: BLE001
                pass
        self._nxc_after = self.after(150, self._nxc_compute)

    def _nxc_compute(self):
        self._nxc_after = None
        cat = self.nxc_cat.get()
        try:
            if cat == "Currency":
                self._nxc_compute_currency()
            elif cat == "Units":
                self._nxc_compute_units()
            else:
                self._nxc_compute_tz()
        except ConversionError as exc:
            self._nxc_show(None, "", str(exc), warn=True)
        except Exception as exc:  # noqa: BLE001
            self._nxc_show(None, "", str(exc), warn=True)

    def _nxc_show(self, result: str | None, detail: str, status: str = "",
                  warn: bool = False, copy: str = ""):
        self.nxc_result.configure(text=result if result else "—")
        self.nxc_detail.configure(text=detail)
        self.nxc_status.configure(text=status, text_color=WARNING if warn else MUTED)
        self._nxc_copy_text = copy

    def _nxc_compute_currency(self):
        rates = self._nx_ensure_rates()
        amount = self._parse_float(self.nxc_amount.get())
        src = self._code_from_label(self.nxc_from.get())
        dst = self._code_from_label(self.nxc_to.get())
        if amount is None or not src or not dst:
            self._nxc_show(None, "Enter an amount and pick two currencies.")
            return
        if src not in rates or dst not in rates:
            missing = src if src not in rates else dst
            self._nxc_show(None, "", f"No rate available for {missing}.", warn=True)
            return
        result = convert_currency(amount, src, dst, rates)
        one = convert_currency(1, src, dst, rates)
        inv = convert_currency(1, dst, src, rates)
        self._nxc_show(
            f"{self._fmt_money(result)} {dst}",
            f"{self._fmt_money(amount)} {src} = {self._fmt_money(result)} {dst}\n"
            f"1 {src} = {one:,.4f} {dst}   ·   1 {dst} = {inv:,.4f} {src}",
            copy=f"{result:.4f} {dst}")

    def _nxc_compute_units(self):
        cat = self.nxc_unit_cat.get()
        umap = dict(UNIT_CATEGORIES.get(cat, []))
        value = self._parse_float(self.nxc_value.get())
        src_label, dst_label = self.nxc_unit_from.get(), self.nxc_unit_to.get()
        if value is None or src_label not in umap or dst_label not in umap:
            self._nxc_show(None, "Enter a value and pick two units.")
            return
        result = convert_units(value, umap[src_label], umap[dst_label])
        self._nxc_show(
            f"{self._fmt_num(result)} {dst_label}",
            f"{self._fmt_num(value)} {src_label} = {self._fmt_num(result)} {dst_label}",
            copy=self._fmt_num(result))

    def _nxc_compute_tz(self):
        dt = parse_datetime(self.nxc_dt.get())
        src, dst = self.nxc_tz_from.get().strip(), self.nxc_tz_to.get().strip()
        out = convert_timezone(dt, src, dst)
        src_dt = convert_timezone(dt, src, src)
        day_delta = (out.date() - src_dt.date()).days
        note = ""
        if day_delta == 1:
            note = "  (next day)"
        elif day_delta == -1:
            note = "  (previous day)"
        elif day_delta != 0:
            note = f"  ({day_delta:+d} days)"
        self._nxc_show(
            out.strftime("%a, %d %b %Y  %H:%M"),
            f"{src}: {src_dt:%H:%M} ({tz_offset_str(src_dt)})   →   "
            f"{dst}: {out:%H:%M} ({tz_offset_str(out)}){note}",
            copy=out.strftime("%Y-%m-%d %H:%M %Z"))
        self._nxc_update_world_clock()

    def _nxc_update_world_clock(self):
        from datetime import datetime as _dt
        from zoneinfo import ZoneInfo

        for z, lbl in getattr(self, "nxc_world_rows", {}).items():
            try:
                now = _dt.now(ZoneInfo(z))
                lbl.configure(text=now.strftime("%H:%M  ·  %a %d %b"))
            except Exception:  # noqa: BLE001
                lbl.configure(text="—")

    def _nxc_swap(self):
        cat = self.nxc_cat.get()
        pair = {"Currency": (self.nxc_from, self.nxc_to),
                "Units": (self.nxc_unit_from, self.nxc_unit_to),
                "Time Zone": (self.nxc_tz_from, self.nxc_tz_to)}[cat]
        a, b = pair[0].get(), pair[1].get()
        pair[0].set(b)
        pair[1].set(a)
        self._nxc_compute()

    def _nxc_copy(self):
        text = getattr(self, "_nxc_copy_text", "")
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.nxc_status.configure(text=f"✓  Copied: {text}", text_color=SUCCESS)

    def reset_nxc(self):
        """Reset all three converter categories to their defaults and recompute."""
        self.nxc_amount.delete(0, "end")
        self.nxc_amount.insert(0, "1")
        self._nxc_currency_choices = self._currency_choices()
        self.nxc_from.set(currency_label("USD") if "USD" in (self.nx_rates or {})
                          else self._nxc_currency_choices[0])
        self.nxc_to.set(currency_label("EUR"))
        self._nxc_unit_cat_change(DEFAULT_UNIT_CATEGORY)
        self.nxc_value.delete(0, "end")
        self.nxc_value.insert(0, "1")
        self.nxc_dt.delete(0, "end")
        self.nxc_dt.insert(0, parse_datetime("now").strftime("%Y-%m-%d %H:%M"))
        self.nxc_tz_from.set("Asia/Dubai" if "Asia/Dubai" in self._nxc_tz_list else "UTC")
        self.nxc_tz_to.set("America/New_York"
                           if "America/New_York" in self._nxc_tz_list else "UTC")
        self.nxc_status.configure(text="", text_color=MUTED)
        self._nxc_compute()

    # ---- nexus converter: currency rate loading -------------------------- #
    def _nx_ensure_rates(self) -> dict:
        if self.nx_rates is None:
            data = load_rates()
            self.nx_rates = data["rates"]
            self._nx_rates_date = data["date"]
            self._nx_rates_source = data["source"]
        return self.nx_rates

    def _currency_codes(self) -> list[str]:
        rates = self.nx_rates or {"EUR": 1.0, "USD": 1.0, "GBP": 1.0, "JPY": 1.0}
        priority = ["USD", "EUR", "GBP", "BHD", "AED", "SAR", "JPY", "CAD", "CHF"]
        front = [c for c in priority if c in rates]
        rest = sorted(c for c in rates if c not in front)
        return front + rest

    def _currency_choices(self) -> list[str]:
        """Combobox labels like ``USD (US Dollar)`` in priority-then-A-Z order."""
        return [currency_label(c) for c in self._currency_codes()]

    def _attach_search(self, combo, get_values, on_change, get_default=None) -> None:
        """Make a CTkComboBox filter its dropdown list as the user types.

        The full IANA / currency lists are too long to scroll; typing narrows the
        dropdown (prefix matches first, then substring) so the next time the menu
        is opened it shows only the matches. `get_values()` is the full search
        corpus (so a currency refresh is picked up); when the field is cleared the
        dropdown falls back to `get_default()` (a short curated list for zones, or
        the full list for currencies if not given).
        """
        entry = getattr(combo, "_entry", None)

        def handler(_e=None):
            typed = (entry.get() if entry is not None else combo.get()).strip().lower()
            if typed:
                values = get_values()
                pref = [v for v in values if v.lower().startswith(typed)]
                sub = [v for v in values if typed in v.lower() and v not in pref]
                shown = (pref + sub)[:40] or ["(no match)"]
            else:
                shown = (get_default or get_values)()
            combo.configure(values=shown)
            on_change()

        if entry is not None:
            entry.bind("<KeyRelease>", handler, add="+")

    def _nxc_update_rates_label(self):
        if not hasattr(self, "nxc_rates_label"):
            return
        date = getattr(self, "_nx_rates_date", "?")
        source = {"network": "live", "cache": "cached",
                  "seed": "bundled snapshot"}.get(getattr(self, "_nx_rates_source", ""), "")
        self.nxc_rates_label.configure(text=f"Rates as of {date}  ·  {source}")

    def _nxc_refresh_rates(self):
        self.nxc_refresh.configure(state="disabled")
        self.nxc_rates_label.configure(text="Fetching today's rates…")
        self._job_started()
        threading.Thread(target=self._nxc_refresh_worker, daemon=True).start()

    def _nxc_refresh_worker(self):
        try:
            data = refresh_rates()
            self.after(0, self._nxc_refresh_done, data, None)
        except Exception as exc:  # noqa: BLE001
            self.after(0, self._nxc_refresh_done, None, exc)

    def _nxc_refresh_done(self, data: dict | None, error: Exception | None):
        self._job_finished()
        self.nxc_refresh.configure(state="normal")
        if error or not data:
            self._nxc_update_rates_label()
            self.nxc_status.configure(
                text=f"Couldn't refresh rates — still using the saved set. ({error})",
                text_color=WARNING)
            return
        self.nx_rates = data["rates"]
        self._nx_rates_date = data["date"]
        self._nx_rates_source = data["source"]
        self._nxc_currency_choices = self._currency_choices()
        self.nxc_from.configure(values=self._nxc_currency_choices)
        self.nxc_to.configure(values=self._nxc_currency_choices)
        self._nxc_update_rates_label()
        self.nxc_status.configure(text="✓  Updated to today's ECB rates.",
                                  text_color=SUCCESS)
        self._nxc_compute()

    # ---- nexus: QR code panel -------------------------------------------- #
    QR_FIELD_SPECS = {
        "Text / URL": [("text", "Text or URL", "textbox")],
        "Wi-Fi": [("ssid", "Network name (SSID)", "entry"),
                  ("password", "Password", "entry"),
                  ("encryption", "Security", "encryption"),
                  ("hidden", "Hidden network", "check")],
        "Email": [("to", "Email address", "entry"),
                  ("subject", "Subject", "entry"),
                  ("body", "Message", "textbox")],
        "Phone": [("number", "Phone number", "entry")],
        "SMS": [("number", "Phone number", "entry"),
                ("message", "Message", "textbox")],
        "vCard": [("first", "First name", "entry"), ("last", "Last name", "entry"),
                  ("org", "Organisation", "entry"), ("title", "Job title", "entry"),
                  ("phone", "Phone", "entry"), ("email", "Email", "entry"),
                  ("url", "Website", "entry")],
        "Geo": [("lat", "Latitude", "entry"), ("lon", "Longitude", "entry")],
    }

    def _build_nx_qr(self, parent) -> ctk.CTkFrame:
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(panel, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=2, sticky="w", padx=24, pady=(4, 8))
        self.nxq_type = ctk.CTkSegmentedButton(
            top, values=QR_TYPES, command=self._show_nxq_type,
            selected_color=RED, selected_hover_color=RED_HOVER)
        self.nxq_type.set("Text / URL")
        self.nxq_type.grid(row=0, column=0)

        # fields card (left, swappable per type)
        incard = ctk.CTkFrame(panel, fg_color=CARD_SOFT, corner_radius=12)
        incard.grid(row=1, column=0, sticky="new", padx=(24, 10), pady=(0, 10))
        incard.grid_columnconfigure(0, weight=1)
        incard.grid_rowconfigure(0, weight=1)
        self.nxq_fields: dict[str, dict] = {}
        self.nxq_groups: dict[str, ctk.CTkFrame] = {}
        for t in QR_TYPES:
            g = self._build_nxq_group(incard, t)
            g.grid(row=0, column=0, sticky="nsew")
            self.nxq_groups[t] = g

        # options card (left, below fields)
        opt = ctk.CTkFrame(panel, fg_color=CARD_SOFT, corner_radius=12)
        opt.grid(row=2, column=0, sticky="new", padx=(24, 10), pady=(0, 10))
        opt.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(opt, text="OPTIONS", font=self._font(11, "medium"),
                     text_color=MUTED).grid(row=0, column=0, columnspan=2,
                                            sticky="w", padx=16, pady=(12, 4))
        ctk.CTkLabel(opt, text="Error correction", text_color=TEXT,
                     anchor="w").grid(row=1, column=0, sticky="w", padx=16)
        self.nxq_ec = ctk.CTkSegmentedButton(
            opt, values=list(QR_EC_LEVELS), command=lambda _v: self._nxq_schedule(),
            selected_color=RED, selected_hover_color=RED_HOVER)
        self.nxq_ec.set("M")
        self.nxq_ec.grid(row=1, column=1, sticky="w", padx=10, pady=4)
        # module size
        ctk.CTkLabel(opt, text="Module size", text_color=TEXT,
                     anchor="w").grid(row=2, column=0, sticky="w", padx=16)
        srow = ctk.CTkFrame(opt, fg_color="transparent")
        srow.grid(row=2, column=1, sticky="w", padx=10, pady=2)
        self.nxq_scale = ctk.CTkSlider(srow, from_=4, to=24, number_of_steps=20,
                                       width=170, command=self._nxq_scale_change)
        self.nxq_scale.set(10)
        self.nxq_scale.grid(row=0, column=0)
        self.nxq_scale_lbl = ctk.CTkLabel(srow, text="10 px", width=48,
                                          text_color=MUTED)
        self.nxq_scale_lbl.grid(row=0, column=1, padx=(8, 0))
        # quiet-zone margin
        ctk.CTkLabel(opt, text="Quiet-zone margin", text_color=TEXT,
                     anchor="w").grid(row=3, column=0, sticky="w", padx=16)
        mrow = ctk.CTkFrame(opt, fg_color="transparent")
        mrow.grid(row=3, column=1, sticky="w", padx=10, pady=2)
        self.nxq_margin = ctk.CTkSlider(mrow, from_=0, to=10, number_of_steps=10,
                                        width=170, command=self._nxq_margin_change)
        self.nxq_margin.set(4)
        self.nxq_margin.grid(row=0, column=0)
        self.nxq_margin_lbl = ctk.CTkLabel(mrow, text="4", width=48, text_color=MUTED)
        self.nxq_margin_lbl.grid(row=0, column=1, padx=(8, 0))
        # colors
        ctk.CTkLabel(opt, text="Colors (FG / BG)", text_color=TEXT,
                     anchor="w").grid(row=4, column=0, sticky="w", padx=16)
        crow = ctk.CTkFrame(opt, fg_color="transparent")
        crow.grid(row=4, column=1, sticky="w", padx=10, pady=4)
        self.nxq_fg, self.nxq_bg = "#000000", "#FFFFFF"
        self.nxq_fg_btn = ctk.CTkButton(
            crow, text="", width=40, height=26, fg_color=self.nxq_fg,
            border_width=1, border_color=MUTED, hover=False,
            command=lambda: self._nxq_pick_color("fg"))
        self.nxq_fg_btn.grid(row=0, column=0, padx=(0, 8))
        self.nxq_bg_btn = ctk.CTkButton(
            crow, text="", width=40, height=26, fg_color=self.nxq_bg,
            border_width=1, border_color=MUTED, hover=False,
            command=lambda: self._nxq_pick_color("bg"))
        self.nxq_bg_btn.grid(row=0, column=1)
        # center logo
        ctk.CTkLabel(opt, text="Center logo", text_color=TEXT,
                     anchor="w").grid(row=5, column=0, sticky="w", padx=16, pady=(2, 12))
        lrow = ctk.CTkFrame(opt, fg_color="transparent")
        lrow.grid(row=5, column=1, sticky="w", padx=10, pady=(2, 12))
        ctk.CTkButton(lrow, text="Add…", width=70, command=self._nxq_pick_logo).grid(
            row=0, column=0)
        ctk.CTkButton(lrow, text="Clear", width=60, fg_color="transparent",
                      border_width=1, border_color=MUTED, text_color=NAV_TEXT,
                      hover_color=("#EBE0E1", "#2A2426"),
                      command=self._nxq_clear_logo).grid(row=0, column=1, padx=(8, 8))
        self.nxq_logo_label = ctk.CTkLabel(lrow, text="No logo", text_color=MUTED)
        self.nxq_logo_label.grid(row=0, column=2)

        # preview card (right). Don't grid_propagate(False) here: it would lock
        # the height to the default 200px and clip the Save/Copy buttons below
        # the 260px preview. The fixed-size preview label keeps the width stable.
        prev = ctk.CTkFrame(panel, fg_color=CARD_SOFT, corner_radius=12)
        prev.grid(row=1, column=1, rowspan=2, sticky="n", padx=(0, 24), pady=(0, 10))
        prev.grid_columnconfigure(0, weight=1)
        # A reusable transparent placeholder: configuring a CTkLabel with
        # image=None after it has shown an image is a CustomTkinter bug ("image
        # doesn't exist" on the next set), and image="" warns — so the empty
        # state swaps in this 1x1 transparent CTkImage instead.
        from PIL import Image as _PILImage
        self._nxq_blank = ctk.CTkImage(
            _PILImage.new("RGBA", (1, 1), (0, 0, 0, 0)), size=(1, 1))
        self.nxq_preview = ctk.CTkLabel(
            prev, text="Fill in the fields to preview your QR code.",
            width=260, height=260, wraplength=240, text_color=MUTED)
        self.nxq_preview.grid(row=0, column=0, padx=20, pady=(20, 6))
        self.nxq_payload_label = ctk.CTkLabel(
            prev, text="", text_color=MUTED, font=ctk.CTkFont(size=11),
            wraplength=240, justify="center")
        self.nxq_payload_label.grid(row=1, column=0, padx=12, pady=(0, 10))
        self.nxq_btn = GradientButton(
            prev, text="Save QR Code", height=44, icon="qr-code",
            busy_text="Generating", command=self.on_nxq_save, state="disabled")
        self.nxq_btn.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 8))
        actions = ctk.CTkFrame(prev, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 18))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)
        self.nxq_copy_btn = ctk.CTkButton(
            actions, text="Copy image", command=self._nxq_copy_image, state="disabled")
        self.nxq_copy_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(
            actions, text="Clear", fg_color="transparent", border_width=1,
            border_color=MUTED, text_color=NAV_TEXT,
            hover_color=("#EBE0E1", "#2A2426"), command=self.reset_nxq,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self.nxq_status = ctk.CTkLabel(
            panel, text="", text_color=MUTED, anchor="w", justify="left",
            wraplength=620)
        self.nxq_status.grid(row=3, column=0, columnspan=2, sticky="w",
                             padx=24, pady=(0, 8))

        self._show_nxq_type("Text / URL")
        return panel

    def _build_nxq_group(self, parent, kind: str) -> ctk.CTkFrame:
        g = ctk.CTkFrame(parent, fg_color="transparent")
        g.grid_columnconfigure(0, weight=1)
        self.nxq_fields[kind] = {}
        r = 0
        for key, label, kind_w in self.QR_FIELD_SPECS[kind]:
            if kind_w == "check":
                w = ctk.CTkCheckBox(g, text=label, command=self._nxq_schedule,
                                    onvalue=True, offvalue=False)
                w.grid(row=r, column=0, sticky="w", padx=18, pady=(6, 10))
                self.nxq_fields[kind][key] = w
                r += 1
                continue
            ctk.CTkLabel(g, text=label.upper(), font=self._font(11, "medium"),
                         text_color=MUTED).grid(row=r, column=0, sticky="w",
                                                padx=18, pady=(8 if r == 0 else 4, 0))
            r += 1
            if kind_w == "encryption":
                w = ctk.CTkSegmentedButton(
                    g, values=WIFI_ENCRYPTIONS, command=lambda _v: self._nxq_schedule(),
                    selected_color=RED, selected_hover_color=RED_HOVER)
                w.set(WIFI_ENCRYPTIONS[0])
                w.grid(row=r, column=0, sticky="w", padx=18, pady=(2, 6))
            elif kind_w == "textbox":
                w = ctk.CTkTextbox(g, height=70, wrap="word", border_width=1,
                                   border_color=CARD_BORDER)
                w.grid(row=r, column=0, sticky="ew", padx=18, pady=(2, 6))
                self._bind_typing(w, self._nxq_schedule)
            else:  # entry
                w = ctk.CTkEntry(g)
                w.grid(row=r, column=0, sticky="ew", padx=18, pady=(2, 6))
                self._bind_typing(w, self._nxq_schedule)
            self.nxq_fields[kind][key] = w
            r += 1
        return g

    def _show_nxq_type(self, name: str):
        self.nxq_type.set(name)  # keep state correct when called programmatically
        for n, g in self.nxq_groups.items():
            (g.grid if n == name else g.grid_remove)()
        self._nxq_compute()

    def _nxq_scale_change(self, value):
        self.nxq_scale_lbl.configure(text=f"{int(round(value))} px")
        self._nxq_schedule()

    def _nxq_margin_change(self, value):
        self.nxq_margin_lbl.configure(text=f"{int(round(value))}")
        self._nxq_schedule()

    def _nxq_pick_color(self, which: str):
        from tkinter import colorchooser

        current = self.nxq_fg if which == "fg" else self.nxq_bg
        _rgb, hexv = colorchooser.askcolor(color=current, title="Choose a color")
        if not hexv:
            return
        if which == "fg":
            self.nxq_fg = hexv
            self.nxq_fg_btn.configure(fg_color=hexv)
        else:
            self.nxq_bg = hexv
            self.nxq_bg_btn.configure(fg_color=hexv)
        self._nxq_schedule()

    def _nxq_pick_logo(self):
        path = self._ask_open("nexus_logo", title="Choose a center logo image",
                              filetypes=self._IMAGE_FILETYPES)
        if path:
            self.nx_qr_logo = Path(path)
            self.nxq_logo_label.configure(text=self._ellipsize(self.nx_qr_logo.name, 22))
            self._nxq_schedule()

    def _nxq_clear_logo(self):
        self.nx_qr_logo = None
        self.nxq_logo_label.configure(text="No logo")
        self._nxq_schedule()

    def _nxq_value(self, w):
        if isinstance(w, ctk.CTkTextbox):
            return w.get("1.0", "end").strip()
        if isinstance(w, ctk.CTkCheckBox):
            return bool(w.get())
        return w.get()  # CTkEntry / CTkSegmentedButton / CTkComboBox

    def _nxq_collect(self, kind: str) -> dict:
        return {k: self._nxq_value(w) for k, w in self.nxq_fields[kind].items()}

    def _nxq_schedule(self, *_):
        if self._nxq_after is not None:
            try:
                self.after_cancel(self._nxq_after)
            except Exception:  # noqa: BLE001
                pass
        self._nxq_after = self.after(180, self._nxq_compute)

    def _nxq_compute(self):
        self._nxq_after = None
        kind = self.nxq_type.get()
        payload = build_qr_payload(kind, self._nxq_collect(kind))
        if not payload:
            self.nx_qr_image = None
            self._nxq_payload = ""
            self.nxq_preview.configure(image=self._nxq_blank,
                                       text="Fill in the fields to preview your QR code.")
            self.nxq_payload_label.configure(text="")
            self.nxq_btn.configure(state="disabled")
            self.nxq_copy_btn.configure(state="disabled")
            return
        try:
            img = make_qr(
                payload, ec=self.nxq_ec.get(),
                scale=int(round(self.nxq_scale.get())),
                margin=int(round(self.nxq_margin.get())),
                fg=self.nxq_fg, bg=self.nxq_bg,
                logo_path=str(self.nx_qr_logo) if self.nx_qr_logo else None)
        except Exception as exc:  # noqa: BLE001
            self.nx_qr_image = None
            self._nxq_payload = ""
            self.nxq_preview.configure(image=self._nxq_blank, text=str(exc))
            self.nxq_btn.configure(state="disabled")
            self.nxq_copy_btn.configure(state="disabled")
            return
        self.nx_qr_image = img
        self._nxq_payload = payload
        self._nxq_preview_ctk = ctk.CTkImage(light_image=img, dark_image=img,
                                             size=(240, 240))
        self.nxq_preview.configure(image=self._nxq_preview_ctk, text="")
        self.nxq_payload_label.configure(
            text=self._ellipsize(payload.replace("\n", " "), 64))
        self.nxq_btn.configure(state="normal")
        self.nxq_copy_btn.configure(state="normal")

    def on_nxq_save(self):
        payload = getattr(self, "_nxq_payload", "")
        if not payload:
            return
        out = self._ask_save(
            "nexus_qr", title="Save QR code as", defaultextension=".png",
            initialfile="qr_code.png",
            filetypes=[("PNG image", "*.png"), ("SVG vector", "*.svg")])
        if not out:
            self.nxq_status.configure(text="Cancelled (no save location chosen).",
                                      text_color=MUTED)
            return
        opts = {"ec": self.nxq_ec.get(),
                "scale": int(round(self.nxq_scale.get())),
                "margin": int(round(self.nxq_margin.get())),
                "fg": self.nxq_fg, "bg": self.nxq_bg,
                "logo_path": str(self.nx_qr_logo) if self.nx_qr_logo else None}
        self._job_started()
        self.nxq_btn.configure(state="disabled")
        self.nxq_btn.start_busy()
        self.nxq_status.configure(text="Saving the QR code…", text_color=MUTED)
        threading.Thread(target=self._nxq_save_worker,
                         args=(payload, Path(out), opts), daemon=True).start()

    def _nxq_save_worker(self, payload: str, out: Path, opts: dict):
        try:
            fmt = "svg" if out.suffix.lower() == ".svg" else "png"
            if fmt == "svg":
                opts = {k: v for k, v in opts.items() if k != "logo_path"}
            saved = save_qr(payload, out, fmt=fmt, overwrite=True, **opts)
            self.after(0, self._nxq_save_done, payload, saved, None)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.after(0, self._nxq_save_done, payload, None, exc)

    def _nxq_save_done(self, payload: str, out: Path | None, error: Exception | None):
        self._job_finished()
        self.nxq_btn.configure(state="normal")
        self.nxq_btn.stop_busy(success=error is None)
        kind = self.nxq_type.get()
        if error:
            self.nxq_status.configure(text=f"✕  {error}", text_color=ERROR)
            self.add_history(f"QR Code · {kind}", None, False, error)
            return
        self.nxq_status.configure(text=f"✓  Saved to {out}", text_color=SUCCESS)
        self.add_history(f"QR Code · {kind}", out, True)

    def _nxq_copy_image(self):
        img = self.nx_qr_image
        if img is None:
            return
        try:
            import io

            import win32clipboard  # pywin32 (Windows dep)

            buf = io.BytesIO()
            img.convert("RGB").save(buf, "BMP")
            dib = buf.getvalue()[14:]  # strip the 14-byte BMP file header -> DIB
            buf.close()
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, dib)
            win32clipboard.CloseClipboard()
            self.nxq_status.configure(text="✓  QR image copied to the clipboard.",
                                      text_color=SUCCESS)
        except Exception:  # noqa: BLE001 - fall back to copying the encoded text
            try:
                self.clipboard_clear()
                self.clipboard_append(getattr(self, "_nxq_payload", ""))
                self.nxq_status.configure(
                    text="Copied the QR text (image copy unavailable here).",
                    text_color=WARNING)
            except Exception:  # noqa: BLE001
                self.nxq_status.configure(text="Couldn't copy the QR code.",
                                          text_color=ERROR)

    def reset_nxq(self):
        """Clear every QR field + reset the options back to their defaults."""
        for fields in self.nxq_fields.values():
            for w in fields.values():
                if isinstance(w, ctk.CTkTextbox):
                    w.delete("1.0", "end")
                elif isinstance(w, ctk.CTkCheckBox):
                    w.deselect()
                elif isinstance(w, ctk.CTkSegmentedButton):
                    w.set(WIFI_ENCRYPTIONS[0])
                elif isinstance(w, ctk.CTkEntry):
                    w.delete(0, "end")
        self.nxq_ec.set("M")
        self.nxq_scale.set(10)
        self.nxq_scale_lbl.configure(text="10 px")
        self.nxq_margin.set(4)
        self.nxq_margin_lbl.configure(text="4")
        self.nxq_fg, self.nxq_bg = "#000000", "#FFFFFF"
        self.nxq_fg_btn.configure(fg_color=self.nxq_fg)
        self.nxq_bg_btn.configure(fg_color=self.nxq_bg)
        self.nx_qr_logo = None
        self.nxq_logo_label.configure(text="No logo")
        self.nxq_status.configure(text="", text_color=MUTED)
        self._nxq_compute()


def _run_cli(args) -> int:
    """Headless mode: --convert, --download, --remove-bg, --upscale, --detect,
    --extract-text, or --identify-font. Returns exit code."""
    import argparse

    parser = argparse.ArgumentParser(prog=APP_NAME, description="Bu D3eij file converter")
    parser.add_argument(
        "--convert", nargs=2, metavar=("FILE", "FORMAT"),
        help="Convert FILE to FORMAT (e.g. --convert photo.png jpg) and exit.",
    )
    parser.add_argument(
        "--download", nargs=2, metavar=("URL", "FORMAT"),
        help="Download URL as FORMAT (mp3/mp4) into the current folder and exit.",
    )
    parser.add_argument(
        "--remove-bg", nargs="+", metavar="FILE [TIER]",
        help="Remove FILE's background (TIER: Flash/Mid/Omega, default Mid), "
             "save a transparent PNG next to it, and exit.",
    )
    parser.add_argument(
        "--upscale", nargs="+", metavar="FILE [TARGET]",
        help="Upscale FILE to TARGET (1080p/2K/4K; default 2K) next to it, and exit.",
    )
    parser.add_argument(
        "--detect", metavar="FILE",
        help="Estimate the AI-likelihood of a .txt/.docx/.pdf and exit.",
    )
    parser.add_argument(
        "--extract-text", nargs="+", metavar="FILE [TIER]",
        help="OCR all text out of an image (TIER: Fast/Max, default Fast), "
             "print it, and exit.",
    )
    parser.add_argument(
        "--identify-font", metavar="FILE",
        help="Identify the font in an image (top-5 Google Font matches) and exit.",
    )
    parser.add_argument(
        "--split-stems", metavar="FILE",
        help="Split an audio file into 4 stems (vocals/drums/bass/other), "
             "save them as WAVs next to it, and exit.",
    )
    parser.add_argument(
        "--qr", nargs="+", metavar="TEXT [OUTFILE]",
        help="Write a QR code PNG for TEXT (to OUTFILE, or qr_code.png in the "
             "current folder) and exit.",
    )
    parser.add_argument(
        # NB: the file converter already owns --convert FILE FORMAT, so the
        # Nexus unit converter gets its own flag rather than overloading it.
        "--convert-units", metavar="EXPR",
        help="Convert units, e.g. --convert-units \"100 km to mi\", and exit.",
    )
    parser.add_argument(
        "--convert-currency", nargs=3, metavar=("AMOUNT", "FROM", "TO"),
        help="Convert currency (cached/seed rates), e.g. "
             "--convert-currency 100 USD EUR, and exit.",
    )
    parser.add_argument(
        "--convert-tz", nargs=3, metavar=("DATETIME", "FROM", "TO"),
        help="Convert a date/time between zones, e.g. "
             "--convert-tz \"2026-06-13 14:30\" Asia/Dubai America/New_York.",
    )
    ns = parser.parse_args(args)
    if ns.convert:
        src, target = ns.convert
        try:
            out = convert_file(src, target)
            print(f"Saved: {out}")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    if ns.download:
        url, fmt = ns.download
        try:
            out = download_youtube(url, fmt, os.getcwd())
            print(f"Saved: {out}")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    if ns.remove_bg:
        if len(ns.remove_bg) > 2:
            parser.error("--remove-bg takes FILE and an optional TIER (Flash/Mid/Omega)")
        src = ns.remove_bg[0]
        tier = ns.remove_bg[1].title() if len(ns.remove_bg) > 1 else DEFAULT_BG_TIER
        if tier not in BG_MODELS:
            parser.error(f"unknown tier '{tier}' — use one of: {', '.join(BG_MODELS)}")
        try:
            out = remove_background(src, model=BG_MODELS[tier][0])
            print(f"Saved: {out}")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    if ns.upscale:
        if len(ns.upscale) > 2:
            parser.error("--upscale takes FILE and an optional TARGET (1080p/2K/4K)")
        src = ns.upscale[0]
        target = ns.upscale[1] if len(ns.upscale) > 1 else DEFAULT_TARGET
        try:
            out = upscale_image(src, target=target)
            print(f"Saved: {out}")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    if ns.detect:
        try:
            r = detect_ai_text(ns.detect, is_file=True)
            short = "  (short text — low confidence)" if r["too_short"] else ""
            print(f"{r['score']}% AI-likelihood · {r['tier']} · {r['model']}{short}")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    if ns.extract_text:
        if len(ns.extract_text) > 2:
            parser.error("--extract-text takes FILE and an optional TIER (Fast/Max)")
        src = ns.extract_text[0]
        tier = ns.extract_text[1].title() if len(ns.extract_text) > 1 else DEFAULT_OCR_TIER
        if tier not in OCR_MODELS:
            parser.error(f"unknown tier '{tier}' — use one of: {', '.join(OCR_MODELS)}")
        try:
            r = extract_text(src, model=tier)
            print(r["text"] if r["count"] else "(no text found)")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    if ns.identify_font:
        try:
            r = identify_font(ns.identify_font, top_k=5)
            for m in r["matches"]:
                print(f"{m['prob']:6.1%}  {m['name']}")
            print(f"(closest matches · {r['model']})")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    if ns.split_stems:
        try:
            src = Path(ns.split_stems)
            r = split_stems(src, progress=lambda f: print(
                f"\r{int(f * 100):3d}%", end="", flush=True))
            print()
            for stem, arr in r["stems"].items():
                out = save_stem(arr, r["samplerate"],
                                src.with_name(f"{src.stem}_{stem}.wav"))
                print(f"Saved: {out}")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    if ns.qr:
        if len(ns.qr) > 2:
            parser.error("--qr takes TEXT and an optional OUTFILE")
        text = ns.qr[0]
        out = ns.qr[1] if len(ns.qr) > 1 else os.path.join(os.getcwd(), "qr_code.png")
        try:
            fmt = "svg" if str(out).lower().endswith(".svg") else "png"
            saved = save_qr(text, out, fmt=fmt)
            print(f"Saved: {saved}")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    if ns.convert_units:
        try:
            expr = ns.convert_units.strip()
            if " to " not in expr:
                parser.error('--convert-units needs the form "<value> <from> to <to>"')
            left, dst = expr.rsplit(" to ", 1)
            parts = left.split(None, 1)
            if len(parts) != 2:
                parser.error('--convert-units needs the form "<value> <from> to <to>"')
            value = float(parts[0])
            result = convert_units(value, parts[1].strip(), dst.strip())
            print(f"{value} {parts[1].strip()} = {result} {dst.strip()}")
            return 0
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    if ns.convert_currency:
        amount, src, dst = ns.convert_currency
        try:
            rates = load_rates()["rates"]
            result = convert_currency(float(amount), src, dst, rates)
            print(f"{amount} {src.upper()} = {result:.4f} {dst.upper()}")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    if ns.convert_tz:
        dt_text, src, dst = ns.convert_tz
        try:
            out = convert_timezone(parse_datetime(dt_text), src, dst)
            print(f"{dst}: {out:%Y-%m-%d %H:%M} ({tz_offset_str(out)})")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    return 0


def main():
    _setup_frozen_logging()  # windowed exe: give print()/tracebacks a log file
    # If launched with flags (e.g. --convert), run headless; otherwise open the GUI.
    if len(sys.argv) > 1 and sys.argv[1].startswith("-"):
        sys.exit(_run_cli(sys.argv[1:]))
    app = App()
    # A bare file argument (e.g. a file dragged onto the exe) preloads the Converter.
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if path.is_file():
            app.set_file(path)
    app.mainloop()


if __name__ == "__main__":
    main()
