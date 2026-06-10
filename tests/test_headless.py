"""Headless verification of the converters / tools (added in the v3.1 fix pass).

Run with the venv python: .\\.venv\\Scripts\\python tests\\test_headless.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FFMPEG_BIN = (r"C:\Users\Khalifa\AppData\Local\Microsoft\WinGet\Packages"
              r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
              r"\ffmpeg-8.1.1-full_build\bin")
if os.path.isdir(FFMPEG_BIN):
    os.environ["PATH"] = FFMPEG_BIN + os.pathsep + os.environ["PATH"]

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

# ---- 8. unload functions -----------------------------------------------------
print("\n[8] unload functions")
from bud3eij import background, fontid, ocr, upscale, vanguard  # noqa: E402

background.unload_models()
upscale.unload_models()
vanguard.unload_models()
ocr.unload_models()
fontid.unload_models()
check("unload functions run", True)
check("ocr engines cleared", not ocr._ENGINES)
check("fontid session cleared", fontid._SESSION is None and fontid._CONFIG is None)

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

print(f"\n==== {PASS} passed, {FAIL} failed ====")
sys.exit(1 if FAIL else 0)
