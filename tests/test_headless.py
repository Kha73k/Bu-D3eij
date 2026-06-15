"""Headless verification of the converters / tools (added in the v3.1 fix pass).

Run with the venv python: .\\.venv\\Scripts\\python tests\\test_headless.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shutil

# Prefer ffmpeg already on PATH; otherwise fall back to the default winget
# (Gyan.FFmpeg) install location under the current user's profile — no
# hard-coded user name, and version-agnostic via glob.
if not shutil.which("ffmpeg"):
    _packages = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    for _bin in sorted(_packages.glob("Gyan.FFmpeg_*/ffmpeg-*-full_build/bin")):
        if _bin.is_dir():
            os.environ["PATH"] = str(_bin) + os.pathsep + os.environ["PATH"]
            break

import app  # noqa: E402
from bud3eij.formats import CONVERSIONS, IMAGE_EXTS, PILLOW_FORMAT  # noqa: E402
from bud3eij.formats import ConversionError  # noqa: E402

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  OK   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}  {detail}")


tmp = Path(tempfile.mkdtemp(prefix="bud3eij_verify_"))
print(f"work dir: {tmp}")

# ---- 1. format model: tif alias -------------------------------------------
print("\n[1] .tif alias")
check("tif in IMAGE_EXTS", "tif" in IMAGE_EXTS)
check("tif in CONVERSIONS", "tif" in CONVERSIONS)
check("tif in PILLOW_FORMAT", PILLOW_FORMAT.get("tif") == "TIFF")

# ---- 2. image conversions ---------------------------------------------------
print("\n[2] image conversions")
from PIL import Image  # noqa: E402

src_png = tmp / "photo.png"
Image.new("RGB", (120, 90), (200, 30, 30)).save(src_png)
out = app.convert_file(src_png, "jpg")
check("png->jpg", out.exists() and out.suffix == ".jpg")

src_tif = tmp / "scan.tif"
Image.new("RGB", (60, 60), (10, 120, 10)).save(src_tif, "TIFF")
out = app.convert_file(src_tif, "png")
check("tif->png", out.exists())

# animated gif -> webp keeps frames (frames must differ or Pillow dedupes them)
src_gif = tmp / "anim.gif"
frames = [Image.new("RGB", (40, 40), c) for c in ((255, 0, 0), (0, 255, 0), (0, 0, 255))]
frames[0].save(src_gif, save_all=True, append_images=frames[1:], duration=100)
out = app.convert_file(src_gif, "webp")
with Image.open(out) as im:
    n = getattr(im, "n_frames", 1)
check("animated gif->webp keeps frames", n == 3, f"n_frames={n}")
# animated gif -> jpg still flattens cleanly
out = app.convert_file(src_gif, "jpg")
check("animated gif->jpg flattens", out.exists())

# ---- 3. txt -> pdf ----------------------------------------------------------
print("\n[3] txt->pdf")
src_txt = tmp / "note.txt"
src_txt.write_text("hello world\n\nsecond paragraph", encoding="utf-8")
out = app.convert_file(src_txt, "pdf")
check("txt->pdf valid header", out.read_bytes()[:4] == b"%PDF")

# ---- 4. ffmpeg error truncation --------------------------------------------
print("\n[4] ffmpeg error truncation")
bogus = tmp / "fake.mp4"
bogus.write_text("this is not a video", encoding="utf-8")
try:
    app.convert_file(bogus, "mp3")
    check("bogus mp4 raises", False)
except ConversionError as exc:
    msg = str(exc)
    check("bogus mp4 raises ConversionError", True)
    check("error message short", len(msg) <= 420, f"len={len(msg)}")
    check("error is single-paragraph", "\n" not in msg, repr(msg[:80]))

# ---- 5. upscaler: fits, dims, threshold, overwrite --------------------------
print("\n[5] upscaler")
from bud3eij.upscale import upscale_image  # noqa: E402

small = tmp / "small.png"
Image.new("RGB", (160, 120), (40, 40, 200)).save(small)  # 4:3
out_pad = upscale_image(small, tmp / "up_pad.png", "1080p", "Fast", fit="letterbox")
with Image.open(out_pad) as im:
    check("pad output exactly 1920x1080", im.size == (1920, 1080), str(im.size))
    px = im.load()
    check("pad has black bars", px[5, 540] == (0, 0, 0), str(px[5, 540]))
out_crop = upscale_image(small, tmp / "up_crop.png", "1080p", "Fast", fit="crop")
with Image.open(out_crop) as im:
    check("crop output exactly 1920x1080", im.size == (1920, 1080), str(im.size))
    px = im.load()
    check("crop has no black bars", px[5, 540] != (0, 0, 0), str(px[5, 540]))

# overwrite=True replaces the chosen path; default still de-duplicates
target_path = tmp / "up_fixed.png"
out1 = upscale_image(small, target_path, "1080p", "Fast")
out2 = upscale_image(small, target_path, "1080p", "Fast", overwrite=True)
out3 = upscale_image(small, target_path, "1080p", "Fast")  # no overwrite
check("overwrite=True keeps the chosen path", out2 == target_path, str(out2))
check("default still de-duplicates", out3 != target_path, str(out3))

# near-target input skips SR (fast path) but still hits exact dims
near = tmp / "near.png"
Image.new("RGB", (1700, 1000), (90, 90, 90)).save(near)
t0 = time.time()
out_near = upscale_image(near, tmp / "near_up.png", "1080p", "Fast")
dt = time.time() - t0
with Image.open(out_near) as im:
    check("near-target output exact", im.size == (1920, 1080), str(im.size))
check("near-target skipped SR (fast)", dt < 5, f"{dt:.1f}s")

# ---- 6. background remover overwrite ----------------------------------------
print("\n[6] background remover (Flash/u2netp)")
from bud3eij.background import remove_background  # noqa: E402

subject = Image.new("RGB", (96, 96), (255, 255, 255))
for x in range(28, 68):
    for y in range(28, 68):
        subject.putpixel((x, y), (180, 20, 20))
bg_src = tmp / "subject.png"
subject.save(bg_src)
bg_out = tmp / "subject_cut.png"
r1 = remove_background(bg_src, bg_out, "u2netp", overwrite=True)
r2 = remove_background(bg_src, bg_out, "u2netp", overwrite=True)
check("bg overwrite keeps chosen path", r1 == bg_out and r2 == bg_out, f"{r1} {r2}")
with Image.open(bg_out) as im:
    check("bg output is RGBA", im.mode == "RGBA", im.mode)
r3 = remove_background(bg_src, bg_out, "u2netp")  # no overwrite -> ' (1)'
check("bg default de-duplicates", r3 != bg_out, str(r3))

# v4.1 Omega: BiRefNet_HR on torch/CUDA (first ever run downloads ~444 MB)
print("\n[6b] background remover Omega (BiRefNet_HR)")
hr_out = remove_background(bg_src, tmp / "subject_hr.png", "birefnet-hr",
                           overwrite=True)
with Image.open(hr_out) as im:
    check("birefnet-hr output is RGBA", im.mode == "RGBA", im.mode)
    import numpy as np
    alpha = np.asarray(im)[:, :, 3]
    check("birefnet-hr subject opaque", alpha[48, 48] > 200, str(alpha[48, 48]))
    check("birefnet-hr corner transparent", alpha[3, 3] < 60, str(alpha[3, 3]))

# ---- 7. vanguard: token-weighted scoring ------------------------------------
print("\n[7] vanguard detect (loads the 1.7 GB model — slow first run)")
from bud3eij.vanguard import detect_ai_text  # noqa: E402

sample = ("The rapid advancement of artificial intelligence has transformed "
          "numerous industries. " * 6 + "I dunno, my cat just knocked my coffee "
          "over again this morning, classic Tuesday honestly. " * 4)
res = detect_ai_text(sample)
check("score is int 0-100", isinstance(res["score"], int) and 0 <= res["score"] <= 100,
      str(res["score"]))
check("tier present", bool(res["tier"]))
check("spans present", len(res["spans"]) > 0)
print(f"       -> {res['score']}% · {res['tier']} · {len(res['spans'])} spans")

# ---- 7b. vanguard: text extraction (OCR) ------------------------------------
print("\n[7b] text extraction (RapidOCR)")
from bud3eij.ocr import extract_text  # noqa: E402
from PIL import ImageDraw, ImageFont  # noqa: E402

inter = Path(__file__).resolve().parent.parent / "assets/fonts/Inter-SemiBold.ttf"
ocr_img = Image.new("RGB", (640, 200), "white")
d = ImageDraw.Draw(ocr_img)
ttf = ImageFont.truetype(str(inter), 40)
d.text((30, 40), "Hello Bu D3eij", fill="black", font=ttf)
d.text((30, 110), "OCR test 12345", fill="black", font=ttf)
ocr_src = tmp / "ocr_sample.png"
ocr_img.save(ocr_src)
ocr_res = extract_text(ocr_src)
check("ocr finds both lines", ocr_res["count"] == 2, str(ocr_res["lines"]))
check("ocr text content", "Hello" in ocr_res["text"] and "12345" in ocr_res["text"],
      repr(ocr_res["text"]))
check("ocr confidences sane",
      all(0 < c <= 1 for _, c in ocr_res["lines"]), str(ocr_res["lines"]))
# Max tier: English rec + tuned det + pre-upscale -> proper word spacing
max_res = extract_text(ocr_src, model="Max")
check("ocr Max finds both lines", max_res["count"] == 2, str(max_res["lines"]))
check("ocr Max keeps spaces", "OCR test 12345" in max_res["text"],
      repr(max_res["text"]))
try:
    extract_text(ocr_src, model="Ultra")
    check("ocr rejects bad tier", False)
except ConversionError:
    check("ocr rejects bad tier", True)
try:
    extract_text(tmp / "note.txt")
    check("ocr rejects non-image", False)
except ConversionError:
    check("ocr rejects non-image", True)

# ---- 7c. vanguard: font identification ---------------------------------------
print("\n[7c] font identification (downloads the ~64 MB model on first ever run)")
from bud3eij.fontid import identify_font  # noqa: E402

font_res = identify_font(ocr_src, top_k=5)
probs = [m["prob"] for m in font_res["matches"]]
check("font returns 5 matches", len(font_res["matches"]) == 5, str(len(probs)))
check("font probs descending 0-1",
      probs == sorted(probs, reverse=True) and all(0 < p <= 1 for p in probs),
      str(probs))
check("font names non-empty", all(m["name"] for m in font_res["matches"]))
print("       -> " + ", ".join(f"{m['name']} {m['prob']:.0%}"
                               for m in font_res["matches"][:3]))
try:
    identify_font(tmp / "note.txt")
    check("font rejects non-image", False)
except ConversionError:
    check("font rejects non-image", True)

# ---- 7d. sonara: stem splitting (Demucs htdemucs_ft) -------------------------
print("\n[7d] sonara stem splitter (first ever run downloads ~320 MB)")
import math  # noqa: E402
import struct  # noqa: E402
import wave as wave_mod  # noqa: E402

from bud3eij.sonara import STEMS, save_stem, split_stems  # noqa: E402
from bud3eij.stemplayer import StemPlayer  # noqa: E402

sn_src = tmp / "clip.wav"
sr = 44100
frames = []
for i in range(sr * 3):
    t = i / sr
    s = 0.4 * math.sin(2 * math.pi * 82 * t) + 0.3 * math.sin(2 * math.pi * 440 * t)
    v = int(max(-1.0, min(1.0, s)) * 32767)
    frames.append(struct.pack("<hh", v, v))
with wave_mod.open(str(sn_src), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes(b"".join(frames))

sn_fracs = []
sn_res = split_stems(sn_src, progress=sn_fracs.append)
check("sonara returns the 4 stems", set(sn_res["stems"]) == set(STEMS),
      str(set(sn_res["stems"])))
check("sonara stem shapes equal",
      len({a.shape for a in sn_res["stems"].values()}) == 1)
check("sonara samplerate 44100", sn_res["samplerate"] == 44100)
check("sonara duration ~3s", abs(sn_res["duration"] - 3.0) < 0.5,
      str(sn_res["duration"]))
check("sonara progress monotonic to 1.0",
      sn_fracs and sn_fracs == sorted(sn_fracs) and sn_fracs[-1] >= 0.99,
      f"n={len(sn_fracs)}")
sn_out = save_stem(sn_res["stems"]["vocals"], sn_res["samplerate"], tmp / "stem.wav")
sn_out2 = save_stem(sn_res["stems"]["vocals"], sn_res["samplerate"], tmp / "stem.wav")
with wave_mod.open(str(sn_out), "rb") as w:
    check("stem wav valid", w.getnchannels() == 2 and w.getframerate() == 44100)
check("stem save de-duplicates", sn_out2 != sn_out, str(sn_out2))
try:
    split_stems(tmp / "note.txt")
    check("sonara rejects non-audio", False)
except ConversionError:
    check("sonara rejects non-audio", True)

# ---- 7e. stem player mixing math (no audio device needed) --------------------
print("\n[7e] stem player mixing math")
import numpy as np  # noqa: E402

tone = {s: np.full((1000, 2), 0.2, dtype=np.float32) for s in STEMS}
sp = StemPlayer(tone, 44100)
sp.set_mute("drums", True)
check("mute zeroes the stem", sp._gains()["drums"] == 0.0)
sp.set_solo("vocals", True)
g = sp._gains()
check("solo isolates", g["vocals"] == 1.0 and g["bass"] == 0.0 and g["other"] == 0.0)
blk = sp._mix_block(0, 64)
check("solo mix == vocals only", np.allclose(blk, tone["vocals"][:64]))
sp.set_solo("vocals", False)
sp.set_mute("drums", False)
sp.set_volume("bass", 0.5)
check("volume scales", sp._gains()["bass"] == 0.5)
loud = StemPlayer({s: np.full((100, 2), 0.9, dtype=np.float32) for s in STEMS}, 44100)
check("mix clips to [-1,1]", float(np.abs(loud._mix_block(0, 32)).max()) <= 1.0)
tail = sp._mix_block(990, 64)
check("end-of-audio zero pad", tail.shape == (64, 2) and np.allclose(tail[10:], 0.0))

# ---- 7f. nexus: converter (units / currency / timezone) + QR -----------------
print("\n[7f] nexus utilities")
from bud3eij import nexus  # noqa: E402

# units incl. temperature offsets
check("units 100C->212F", abs(nexus.convert_units(100, "degC", "degF") - 212.0) < 1e-6)
check("units 0C->273.15K", abs(nexus.convert_units(0, "degC", "kelvin") - 273.15) < 1e-9)
check("units 1mi->1.609344km",
      abs(nexus.convert_units(1, "mile", "kilometer") - 1.609344) < 1e-6)
check("units 1GiB->1024MiB", nexus.convert_units(1, "gibibyte", "mebibyte") == 1024)
try:
    nexus.convert_units(1, "meter", "gram")
    check("units rejects mismatched dimensions", False)
except ConversionError:
    check("units rejects mismatched dimensions", True)

# currency math against a stubbed base-EUR table (+ inverse round-trip)
stub = {"EUR": 1.0, "USD": 1.25, "GBP": 0.8}
check("currency 100 USD->EUR", abs(nexus.convert_currency(100, "USD", "EUR", stub) - 80.0) < 1e-9)
check("currency 100 USD->GBP", abs(nexus.convert_currency(100, "USD", "GBP", stub) - 64.0) < 1e-9)
rt = nexus.convert_currency(nexus.convert_currency(100, "USD", "GBP", stub), "GBP", "USD", stub)
check("currency inverse round-trips", abs(rt - 100.0) < 1e-9)
try:
    nexus.convert_currency(1, "USD", "XYZ", stub)
    check("currency rejects unknown code", False)
except ConversionError:
    check("currency rejects unknown code", True)
# rates load offline from the bundled seed snapshot
rates = nexus.load_rates()
check("rates load offline (seed/cache)",
      rates["rates"].get("EUR") == 1.0 and len(rates["rates"]) > 10, rates.get("source"))
# USD-pegged Gulf currencies the ECB feed omits are added + correctly derived
check("BHD available (USD-pegged)", "BHD" in rates["rates"])
check("100 USD -> BHD ~ 37.6 (peg)",
      abs(nexus.convert_currency(100, "USD", "BHD", rates["rates"]) - 37.6) < 0.01)
check("100 BHD -> USD ~ 265.96 (peg)",
      abs(nexus.convert_currency(100, "BHD", "USD", rates["rates"]) - 265.957) < 0.01)
check("currency_label shows full name",
      nexus.currency_label("BHD") == "BHD (Bahraini Dinar)", nexus.currency_label("BHD"))

# timezone: known offset + a day rollover
out = nexus.convert_timezone(nexus.parse_datetime("2024-01-01 12:00"),
                             "America/New_York", "Asia/Tokyo")
check("tz NY noon -> Tokyo next day 02:00",
      out.strftime("%Y-%m-%d %H:%M") == "2024-01-02 02:00", out.strftime("%Y-%m-%d %H:%M"))
check("tz offset string", nexus.tz_offset_str(out) == "UTC+09:00", nexus.tz_offset_str(out))
roll = nexus.convert_timezone(nexus.parse_datetime("2024-01-01 23:30"),
                              "America/Los_Angeles", "Europe/London")
check("tz day rollover", roll.day == 2, str(roll))

# QR payloads (Wi-Fi escaping, vCard) + empty-input guard
wifi = nexus.build_qr_payload("Wi-Fi",
                              {"ssid": "Net;1", "password": "p:w", "encryption": "WPA/WPA2"})
check("wifi payload escaped", wifi == r"WIFI:T:WPA;S:Net\;1;P:p\:w;;", repr(wifi))
vc = nexus.build_qr_payload("vCard", {"first": "Ada", "last": "Lovelace", "email": "a@b.c"})
check("vcard payload",
      "BEGIN:VCARD" in vc and "FN:Ada Lovelace" in vc and "EMAIL:a@b.c" in vc, vc)
check("empty payload is blank", nexus.build_qr_payload("Geo", {"lat": "", "lon": ""}) == "")

# make_qr writes a PNG that decodes back to the payload
qr_png = tmp / "qr.png"
nexus.save_qr("https://bud3eij.test/Z9", qr_png, fmt="png", overwrite=True)
check("qr png written", qr_png.exists())
try:
    import cv2  # test-only decode (the app already ships opencv)

    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(qr_png)))
    check("qr decodes back to payload", decoded == "https://bud3eij.test/Z9", repr(decoded))
except ImportError:
    check("qr decode skipped (cv2 unavailable)", True)
# svg export keeps the chosen colors
svg_text = nexus.save_qr("hi", tmp / "qr.svg", fmt="svg", fg="#123456", bg="#ABCDEF",
                         overwrite=True).read_text(encoding="utf-8")
check("qr svg recolored", "#123456" in svg_text and "#ABCDEF" in svg_text)

# ---- 7g. marquee: ASCII art (pure PIL/numpy, no model) -----------------------
print("\n[7g] ASCII art")
from bud3eij.asciiart import image_to_ascii, save_ascii  # noqa: E402

asc_txt = image_to_ascii(ocr_src, width=100)
asc_lines = asc_txt.split("\n")
check("ascii respects width", max(len(line) for line in asc_lines) <= 100,
      str(max(len(line) for line in asc_lines)))
check("ascii has rows", len(asc_lines) > 3, str(len(asc_lines)))
check("ascii invert changes output",
      image_to_ascii(ocr_src, width=100, invert=True) != asc_txt)
asc_out_txt = save_ascii(ocr_src, tmp / "art.txt", width=80)
check("ascii .txt written", asc_out_txt.exists() and asc_out_txt.suffix == ".txt")
asc_out_png = save_ascii(ocr_src, tmp / "art.png", width=80, color=True)
with Image.open(asc_out_png) as im:
    check("ascii .png rendered RGB", im.mode == "RGB" and im.size[0] > 0, str(im.size))
ad1 = save_ascii(ocr_src, tmp / "artdup.txt", width=60)
ad2 = save_ascii(ocr_src, tmp / "artdup.txt", width=60)
ad3 = save_ascii(ocr_src, tmp / "artdup.txt", width=60, overwrite=True)
check("ascii default de-duplicates", ad2 != ad1, str(ad2))
check("ascii overwrite keeps chosen path", ad3 == ad1, str(ad3))
try:
    image_to_ascii(tmp / "note.txt")
    check("ascii rejects non-image", False)
except ConversionError:
    check("ascii rejects non-image", True)

# ---- 7h. marquee: image -> prompt (Qwen2-VL-2B — loads ~4.4 GB, slow) --------
print("\n[7h] image -> prompt (Qwen2-VL-2B; first ever run downloads ~4.4 GB)")
from bud3eij.imageprompt import PROMPT_MODES, image_to_prompt  # noqa: E402

check("PROMPT_MODES has Concise + Detailed",
      set(PROMPT_MODES) >= {"Concise", "Detailed"}, str(set(PROMPT_MODES)))
ip_text = image_to_prompt(src_png, mode="Detailed")
check("image_to_prompt returns text",
      isinstance(ip_text, str) and len(ip_text) > 10, repr(ip_text[:60]))
check("image_to_prompt concise mode returns text",
      isinstance(image_to_prompt(src_png, mode="Concise"), str))
try:
    image_to_prompt(tmp / "note.txt")
    check("image_to_prompt rejects non-image", False)
except ConversionError:
    check("image_to_prompt rejects non-image", True)

# ---- 8. unload functions -----------------------------------------------------
print("\n[8] unload functions")
from bud3eij import (  # noqa: E402
    background, fontid, imageprompt, ocr, sonara, upscale, vanguard,
)

background.unload_models()
upscale.unload_models()
vanguard.unload_models()
ocr.unload_models()
fontid.unload_models()
sonara.unload_models()
imageprompt.unload_models()
check("unload functions run", True)
check("ocr engines cleared", not ocr._ENGINES)
check("fontid session cleared", fontid._SESSION is None and fontid._CONFIG is None)
check("sonara model cleared", sonara._MODEL is None)
check("imageprompt model cleared", imageprompt._MODEL is None)

# ---- 9. youtube validation paths ---------------------------------------------
print("\n[9] youtube validation (no network)")
from bud3eij.youtube import download_youtube  # noqa: E402

try:
    download_youtube("notaurl", "mp4", tmp)
    check("bad url rejected", False)
except ConversionError:
    check("bad url rejected", True)
try:
    download_youtube("https://example.com", "flac", tmp)
    check("bad format rejected", False)
except ConversionError:
    check("bad format rejected", True)

# ---- 10. load_history validation ---------------------------------------------
print("\n[10] history validation")
bad_hist = tmp / "history.json"
bad_hist.write_text('[{"ok": true, "output": "x"}, "corrupt-entry", 42]',
                    encoding="utf-8")
orig = app.HISTORY_FILE
app.HISTORY_FILE = bad_hist
loaded = app.load_history()
app.HISTORY_FILE = orig
check("malformed entries dropped", loaded == [{"ok": True, "output": "x"}], str(loaded))

print("\n[11] feature-gating detection")
from bud3eij import features as _F  # noqa: E402
check("core section always available", _F.section_available("Converter") is True)
check("optional sections available in dev", all(
    _F.section_available(s) for s in ("Marquee", "Vanguard", "Sonara")))
_real_inst = _F._installed
_F._installed = lambda m: False  # simulate a Core-only install
try:
    check("group hidden when sentinel missing", _F.feature_available("marquee") is False)
    check("gated section hidden", _F.section_available("Sonara") is False)
    check("core unaffected when stubbed", _F.section_available("Nexus") is True)
    check("unknown group treated as core", _F.feature_available("") is True)
finally:
    _F._installed = _real_inst

print("\n[12] on-demand ffmpeg helper")
from bud3eij import ffmpeg as _ff  # noqa: E402
check("have_ffmpeg() true (ffmpeg on PATH in tests)", _ff.have_ffmpeg() is True)
_ffdir = _ff.ensure_ffmpeg()
check("ensure_ffmpeg returns a dir with ffmpeg.exe",
      os.path.isfile(os.path.join(_ffdir, "ffmpeg.exe")), _ffdir)
check("pinned ffmpeg url is the gyan github mirror",
      _ff._FFMPEG_URL.startswith("https://github.com/GyanD/codexffmpeg/"))

print(f"\n==== {PASS} passed, {FAIL} failed ====")
sys.exit(1 if FAIL else 0)
