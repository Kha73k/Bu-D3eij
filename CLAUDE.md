# CLAUDE.md — Bu D3eij

Guidance for working on this project across sessions. Keep this file and
`PROGRESS.md` up to date when things change.

## What this is
Bu D3eij is a Windows desktop **file converter** (documents, images, audio/video)
built with **CustomTkinter** + **tkinterdnd2** drag-and-drop. The pure logic lives
in the **`bud3eij/` package** (`formats`, `converters`, `youtube`, `background`) as
plain module-level functions (importable and testable without the GUI); **`app.py`**
is the GUI (`App` class + views), the Recent-history store, the CLI, and the entry
point, and it **re-exports** the package functions so `app.<fn>` and `import app`
keep working for headless tests. (It was one big `app.py` through v2.1; the logic
was split into the package in **v2.2** — same single program and same UI/output,
reorganized for safe growth before the image-editing section expands.)
**v2.0** opens a second direction — an image-editing area called **Marquee**;
its first tool is a **Background Remover** (rembg) that exports a transparent PNG.
**v3.1** was a full audit-fix pass (no new direction): COM safety, thread-race
fixes, shared panel helpers, and an in-repo `tests/` suite — details inline below.
**v3.2** turns **Vanguard into a multi-tool page** (same switcher pattern as
Marquee): AI Detector + two new image tools — **Text Extraction** (RapidOCR) and
**What's The Font** (Storia font-classify) — details inline below.
**v4.0** opens a third direction — an audio-tools area called **Sonara**; its
first tool is an **Audio Stem Splitter** (Demucs `htdemucs_ft` on **PyTorch
CUDA** — the app's first torch dependency) with a real-time 4-stem playback
mixer (`sounddevice`) — details inline below.
**v4.1** gave both Marquee tools the same GPU treatment: the upscaler moved to
**UltraSharp V2 via spandrel** and the bg remover's Omega tier to
**BiRefNet_HR** — details inline below.
**v4.2** opens a fourth direction — a utilities area called **Nexus** (same
multi-tool switcher as Marquee/Vanguard): a **Converter** (currency · units ·
time zones — all offline, no account, no limits) and a **QR Code** generator.
Pure logic lives in `bud3eij/nexus.py`; new deps are **`pint`** (units),
**`tzdata`** (time zones) and **`qrcode[pil]`** (QR) — no ML, nothing in
`~/.bud3eij/models/` — details inline below.

## Environment (important)
- **Runtime is the Python 3.11 venv at `.venv`** — always use it:
  `.\.venv\Scripts\python ...`. (System `python` is also 3.11 now, but the
  dependencies live in the venv.) 3.11 was chosen for guaranteed wheels of the
  doc stack (pdf2docx→PyMuPDF, docx2pdf→pywin32, reportlab, lxml).
- **ffmpeg** (for MP4/MP3/WAV) is installed via winget (Gyan.FFmpeg) at:
  `C:\Users\Khalifa\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin`
  It is on the **user PATH for newly-opened terminals only**. An agent shell
  started before the install will NOT see it, so for A/V work prepend that
  `bin` to `$env:PATH`, or `shutil.which("ffmpeg")` returns None.
- **Microsoft Word is installed**, so DOCX→PDF uses a high-fidelity **direct
  Word-COM** path (`_docx_to_pdf_word`; docx2pdf was dropped in v3.1 — it leaked
  a hidden WINWORD.EXE on every failed conversion); `reportlab` is the
  text-only fallback.
- **Microsoft PowerPoint** (if installed) is used for PPTX→PDF via COM
  (`win32com.client` + `SaveAs(..., 32)`); `reportlab` is the text-only fallback.
- **PyTorch is CUDA (cu126)** for Sonara/Demucs — installed **separately from
  requirements.txt** because it needs the PyTorch index:
  `.\.venv\Scripts\python -m pip install torch torchaudio --index-url
  https://download.pytorch.org/whl/cu126` (then `pip install -r` covers the
  rest). The machine's RTX 3070 Ti runs `htdemucs_ft` in seconds; a plain
  `pip install -r requirements.txt` on a fresh env would resolve the CPU torch
  wheel instead — still works, ~20× slower. **v4.1 update:** torch is no longer
  Sonara-only — the Marquee upscaler (spandrel) and the bg remover's Omega tier
  (BiRefNet_HR via transformers) run on it too. `torchvision` must also be the
  **cu126 build** (spandrel's pip pull grabs the CPU wheel — reinstall it from
  the cu126 index with `--force-reinstall --no-deps`). Vanguard/OCR/fontid stay
  on onnxruntime.

## Commands
```powershell
# Run the GUI
.\.venv\Scripts\python app.py

# Headless conversion (also works on the exe)
.\.venv\Scripts\python app.py --convert "C:\path\photo.png" jpg

# Headless background removal -> transparent PNG (also works on the exe)
.\.venv\Scripts\python app.py --remove-bg "C:\path\photo.png"

# Headless OCR / font identification (also work on the exe)
.\.venv\Scripts\python app.py --extract-text "C:\path\screenshot.png"
.\.venv\Scripts\python app.py --identify-font "C:\path\text.png"

# Headless stem splitting -> 4 WAVs next to the source (also works on the exe)
.\.venv\Scripts\python app.py --split-stems "C:\path\song.mp3"

# Headless Nexus utilities (also work on the exe)
.\.venv\Scripts\python app.py --qr "https://example.com" out.png   # PNG or .svg
.\.venv\Scripts\python app.py --convert-units "100 km to mi"
.\.venv\Scripts\python app.py --convert-currency 100 USD EUR
.\.venv\Scripts\python app.py --convert-tz "2026-06-13 14:30" Asia/Dubai America/New_York

# Install / update deps
.\.venv\Scripts\python -m pip install -r requirements.txt

# Build the standalone one-folder exe -> dist\Bu D3eij\Bu D3eij.exe
.\.venv\Scripts\pyinstaller --noconfirm --windowed --name "Bu D3eij" `
  --icon "AppLogo.ico" `
  --add-data "AppLogo.ico;." --add-data "DashboardLogo.png;." `
  --add-data "bud3eij_theme.json;." --add-data "assets;assets" `
  --add-data "assets/data/rates_seed.json;assets/data" `
  --collect-all customtkinter --collect-all tkinterdnd2 `
  --collect-all pptx --collect-all mammoth --collect-all markdownify --collect-all bs4 `
  --collect-data pdfminer --collect-data pdfplumber `
  --collect-data docx --collect-data pdf2docx --collect-data reportlab `
  --collect-submodules pymupdf4llm --hidden-import tabulate `
  --collect-all yt_dlp `
  --collect-all rembg --collect-all onnxruntime --copy-metadata pymatting --copy-metadata rembg `
  --collect-all tokenizers --collect-all rapidocr `
  --collect-all demucs --collect-all torch --collect-all torchaudio `
  --collect-all sounddevice --copy-metadata torch `
  --collect-all spandrel --collect-all transformers --collect-all timm `
  --collect-all kornia --collect-all torchvision `
  --collect-all pint --collect-all tzdata --collect-all qrcode `
  --exclude-module pymupdf.layout --exclude-module rapidocr_onnxruntime `
  --hidden-import win32timezone app.py
```

> **v4.2 Nexus (utilities) build note — already applied above:**
> `--collect-all pint` (its unit-definition data file isn't picked up by static
> analysis), `--collect-all tzdata` (the IANA zone database — Windows has none),
> and `--collect-all qrcode`. The ECB seed snapshot is bundled with
> `--add-data "assets/data/rates_seed.json;assets/data"` (belt-and-suspenders —
> `--add-data "assets;assets"` already sweeps it in, but the explicit flag
> documents the dependency). **No ML models** — nothing downloads into
> `~/.bud3eij/models/`; the only writable cache is `~/.bud3eij/nexus/rates.json`
> (the in-app **Refresh**), and the app converts offline from the seed without it.

> **v4.1 Marquee GPU models build note — already applied above:**
> `--collect-all spandrel/transformers/timm/kornia/torchvision` cover the new
> upscaler loader and the BiRefNet_HR path (transformers needs its data files;
> BiRefNet's pinned remote code imports timm + kornia + torchvision at
> runtime). The UltraSharp V2 weights (~28 + ~133 MB) download SHA-256-verified
> into `~/.bud3eij/models/`; BiRefNet_HR (~444 MB + code, revision-pinned)
> lands in `HF_HOME = ~/.bud3eij/models/hf` — none are bundled.

> **v4.0 Sonara (stem splitter) build note — already applied above:**
> `--collect-all demucs` (it ships `remote/*.yaml` model manifests),
> `--collect-all torch --collect-all torchaudio --copy-metadata torch` (the CUDA
> DLLs ride inside `torch/lib` — the exe folder grows to **~6 GB** and the build
> takes much longer; this is a personal build, disk-only cost), and
> `--collect-all sounddevice` (bundles the PortAudio DLL). The Demucs
> checkpoints (4 × ~80 MB) are **not bundled** — they download once via
> torch.hub into `TORCH_HOME = ~/.bud3eij/models/torch` (set by
> `bud3eij/sonara.py` before the lazy demucs import).

> **v3.2 Vanguard tools (OCR + font ID) build note — already applied above:**
> `--collect-all rapidocr` was added: Text Extraction uses the **`rapidocr`** pip
> package whose PP-OCRv4 mobile models (det+cls+rec, ~15 MB) and config YAMLs ship
> **inside the wheel** — collect-all bundles them, so OCR is fully offline in the
> exe. This does NOT conflict with `--exclude-module rapidocr_onnxruntime` (that's
> the *legacy* package name, kept excluded for the pymupdf.layout trap). What's The
> Font's model (`storia/font-classify-onnx`, ~64 MB + config) is **not bundled** —
> it downloads SHA-256-verified into `~/.bud3eij/models/fontid/` on first use
> (`fontid._ensure_file`), like the upscaler/Vanguard models.

> **v3.0 Vanguard (AI text detector) build note — already applied above:**
> `--collect-all tokenizers` was added: the detector tokenizes with the HF
> `tokenizers` (Rust) library, whose binary extension + data PyInstaller misses by
> static analysis. `onnxruntime`/`numpy` are already collected (rembg/upscaler), so
> nothing else changes. The DeBERTa-v3 ONNX model (~1.7 GB) + `tokenizer.json` are
> **not bundled** (keeps the exe lean) and — for this personal build — **not hosted**
> either: they sit in the local cache `~/.bud3eij/models/vanguard/`, which both the
> source app and the frozen exe load from (`vanguard._ensure_file`).

> **v2.0 Background Remover (rembg) build notes — already applied above:**
> - **rembg needs `onnxruntime` at runtime**, so the old `--exclude-module
>   onnxruntime` was removed and `--collect-all rembg --collect-all onnxruntime`
>   added.
> - **Keep** `--exclude-module pymupdf.layout` and `--exclude-module
>   rapidocr_onnxruntime` — `pymupdf.layout` (NOT onnxruntime) is the real PDF→MD
>   trap-fix, so dropping only the onnxruntime exclude keeps PDF→MD structure-aware.
> - **`--copy-metadata pymatting` is required:** rembg imports `pymatting` at
>   import time, and `pymatting/__init__.py` calls `importlib.metadata.version(...)`
>   on itself — without its dist-info the frozen exe dies with *"No package metadata
>   was found for pymatting"*. (`--collect-all` copies code/data but NOT metadata.)
>   `--copy-metadata rembg` is kept defensively.
> - **The u2net model is NOT bundled** (mirrors the ffmpeg decision): rembg
>   downloads `%USERPROFILE%\.u2net\u2net.onnx` (~176 MB) on first use and caches
>   it. To make the exe fully offline on a fresh machine, add
>   `--add-data "%USERPROFILE%\.u2net\u2net.onnx;u2net"` and point `U2NET_HOME` at
>   that bundled dir before importing rembg.

## Verifying changes
- **In-repo test scripts (`tests/`, added v3.1):** plain scripts (no pytest) —
  each prints OK/FAIL lines and exits non-zero on failure. Run with the venv
  python: `tests\test_headless.py` (format model, conversions incl. animated
  GIF, ffmpeg error truncation, upscaler fits/overwrite/SR-threshold,
  bg-remover overwrite, vanguard scoring, OCR text extraction, font ID,
  sonara stem split + StemPlayer mix math, **v4.2 nexus** (units incl.
  temperature, currency math + inverse against a stubbed rate table, tz offset +
  day rollover, Wi-Fi/vCard payloads, `make_qr`→PNG that decodes back via cv2,
  SVG recolour),
  history validation — loads the Vanguard + Demucs models, so the first run is
  slow), `tests\test_gui_smoke.py` (all
  frames + the v3.1 widgets/counters + the v3.2 Vanguard switcher/panels + the
  v4.0 Sonara page/stub-player toggles + the **v4.2 Nexus** switcher/category
  swaps + live conversion + QR type swap),
  `tests\test_com_paths.py` (direct-Word
  DOCX→PDF incl. the no-WINWORD-leak check, owned-PowerPoint PPTX→PDF; needs
  Office installed).
- **Conversions (headless, ad-hoc):** `import app`, generate samples (PIL image,
  reportlab PDF, python-docx DOCX, `wave` WAV, ffmpeg for MP4) in a temp dir,
  call `app.convert_file(src, target)`, and assert the output exists/opens.
  Run with the venv python; prepend the ffmpeg bin to PATH first.
- **GUI:** construct `app.App()`, call `update()`, switch frames via
  `show_frame(...)`, then `after(300, destroy); mainloop()`.
- **Frozen exe:** run `dist\Bu D3eij\Bu D3eij.exe --convert <file> <fmt>` (and
  `--remove-bg <image>`, `--download <url> <fmt>`) and check the output file
  (proves bundled modules/data work, not just startup). For the Background
  Remover this is the key check — it exercises the rembg/onnxruntime bundle.

## Architecture / key code
**Where things live (after the v2.2 package split):** the pure logic is in the
`bud3eij/` package — `formats.py` (format model, helpers, `ConversionError`),
`converters.py` (`convert_file` + every document/image/AV converter),
`youtube.py` (`download_youtube`), `background.py` (`remove_background` +
`BG_MODELS`), and (v4.2) `nexus.py` (the Nexus utilities — currency/units/tz
converters + QR builders). `app.py` holds the GUI (`App`, `GradientButton`, palette/icons),
the Recent-history store (`load_history`/`save_history`), the CLI (`_run_cli`),
and `main()`, and it re-exports the package functions (so `app.convert_file`,
`app.remove_background`, etc. still resolve). Converters still **import heavy deps
lazily** inside each function — keep that. The bullets below describe behaviour and
still apply; only the file a function lives in changed.
- **Format model:** `IMAGE_EXTS`/`DOC_EXTS`/`PRESENTATION_EXTS`/`AV_EXTS`, and
  `CONVERSIONS` (input ext → list of valid targets). `md` is an **output-only**
  format (it has no `CONVERSIONS` key); `txt` is both an input
  (`txt → pdf/docx/md`) and an output. `compatible_targets()` drives the UI's
  "Convert to" options — **a missing `CONVERSIONS` key is exactly why a format
  shows "Unsupported"** (the v3.0 `.txt`-input bug: `txt` was an output target but
  had no key, so it was rejected as input). Add new conversions here AND in the
  `convert_file` dispatch.
- **Dispatch:** `convert_file(src, target)` validates against `CONVERSIONS`,
  computes a non-clobbering output path with `unique_path()` (saves next to the
  source; never overwrites — adds ` (n)`), and routes to the right converter.
  **`tif` is an input alias of `tiff`** (v3.1) — present in `IMAGE_EXTS`,
  `CONVERSIONS`, `PILLOW_FORMAT`, and `EXT_ICON`.
  **Overwrite exception (v3.1):** `remove_background`/`upscale_image` take
  `overwrite=True`, used by the GUI when the path came from `asksaveasfilename`
  (the dialog already confirmed replacing); auto-named outputs still never clobber.
- **Converters:** `convert_image` (Pillow), `pdf_to_txt` (pdfplumber),
  `pdf_to_md` (pymupdf4llm, pdfplumber text fallback), `pdf_to_docx` (pdf2docx),
  `docx_to_txt` (python-docx), `docx_to_md` (mammoth→HTML + markdownify→MD),
  `docx_to_pdf` (`_docx_to_pdf_word` → `_docx_to_pdf_reportlab` fallback),
  `txt_to_pdf` (reportlab), `txt_to_docx` (python-docx), `txt_to_md` (verbatim
  copy via `_read_text`, utf-8 → cp1252 fallback),
  `pptx_to_md`/`pptx_to_txt` (python-pptx), `pptx_to_pdf`
  (`_pptx_to_pdf_powerpoint` COM → `_pptx_to_pdf_reportlab` fallback),
  `convert_av` (ffmpeg-python). Each **imports its heavy deps lazily** inside
  the function for fast startup — keep this pattern. v3.1 details:
  `_docx_to_pdf_word` is **direct Word COM** (see Conventions — never reintroduce
  docx2pdf); `convert_image` keeps **animation** when source has `n_frames > 1`
  and the target supports it (gif/webp/tiff/png → `save_all=True`); `convert_av`
  prints the **full ffmpeg stderr** to stderr but raises only its last ~3 lines
  (≤400 chars) so the GUI status label can't be flooded.
- **YouTube download:** `download_youtube(url, fmt, out_dir, progress_hook)`
  (yt-dlp, lazy import) — `fmt` is `mp3` (FFmpegExtractAudio 192 kbps) or `mp4`
  (`bestvideo+bestaudio`, `merge_output_format=mp4`). Needs ffmpeg (sets
  `ffmpeg_location`). Not part of `convert_file` (it has no source file); the
  GUI **YouTube** page (`_build_youtube` + `on_youtube_download`/`_youtube_worker`/
  `_yt_hook`) and the `--download URL FORMAT` CLI both call it. Output folder is
  asked per-download (filedialog, remembers the last folder); results go through
  `add_history`. v3.1: the mp4 path adds an **`FFmpegVideoRemuxer`** postprocessor
  (`preferedformat` — yt-dlp's spelling) so a single-file webm-only download still
  lands as `.mp4`; `_yt_hook` is **throttled to ≥100 ms** between UI posts
  (yt-dlp fires per network block — unthrottled it floods the Tk event queue).
- **Marquee = a multi-tool image-editing page (tool switcher added v2.3).**
  `_build_marquee` is now a shared `_section_header` + a `CTkSegmentedButton`
  (`self.mq_tool`: "Background Remover" / "Upscaler") + a container holding two
  self-contained panels, `_build_mq_bgremover` and `_build_mq_upscaler`, swapped by
  `_show_mq_tool` (grid/grid_remove). Each panel keeps its own drop zone, controls,
  progress bar, and status, with its own `mq_*`/`up_*` attrs and handlers. Add the
  next image tool as a third value + `_build_mq_<tool>` panel.
- **Marquee → Background Remover (v2.0, model selector in v2.1):**
  `remove_background(src, out_path=None, model="isnet-general-use")` (rembg, lazy
  import) opens the image, runs the chosen rembg model, and saves a transparent
  **PNG** (output is always PNG — the only listed image format that keeps alpha).
  Like `download_youtube` it sits **outside** `convert_file`/`CONVERSIONS` (no
  target-format choice). Sessions are cached per model in the module-level dict
  `_REMBG_SESSIONS` (each model loaded once). **v2.1** added a **QUALITY** tier
  selector (`CTkSegmentedButton`) mapped by `BG_MODELS` (top of module):
  **Flash** = `u2netp` (fastest, ~4.7 MB), **Mid** (default `DEFAULT_BG_TIER`) =
  `isnet-general-use` (balanced) — both rembg/onnx, downloading their `.onnx`
  into `~/.u2net/` on first use. **Omega was upgraded in v4.1** to
  **`birefnet-hr`** = the official **BiRefNet_HR** (MIT, ZhengPeng7/BiRefNet_HR)
  on **torch CUDA** fp16 at 2048², loaded via `transformers`
  `AutoModelForImageSegmentation(trust_remote_code=True)` with a **pinned
  revision** (`BIREFNET_HR_REVISION`); weights+code cache in
  `HF_HOME = ~/.bud3eij/models/hf`. Measured: keeps individual hair strands
  that Flash deletes outright; ~1.4 s warm on the 3070 Ti (~8 s first load).
  RMBG-2.0 scored higher overall in published benchmarks but is **gated behind
  a HF account** — rejected (no-accounts rule); BiRefNet_HR beats it on hair.
  The bg-remover panel (`_build_mq_bgremover` + `_on_mq_model_change`/
  `on_marquee_drop`/`browse_marquee`/`set_marquee_file`/`on_marquee_remove`/
  `_marquee_worker`/`_marquee_done`) validates the drop is an image (`IMAGE_EXTS`),
  asks the output path per-run via `asksaveasfilename` (defaults `<stem>_no-bg.png`),
  shows a **filling (determinate) progress bar** while the worker thread runs, and
  records the result via `add_history`. Because rembg's `remove()` has no progress
  callback, the bar is an **eased simulated fill** (`_fill_start(bar)`/`_fill_tick`/
  `_fill_stop(bar)` — generalised per-bar in v3.2, also used by the Vanguard OCR and
  font panels): a timer creeps the bar toward ~90% while the worker runs and snaps
  it to 100% on success — a filling bar, not the old back-and-forth one. Nav icon
  reuses the bundled `assets/ui/sparkles.png`. v3.1: `remove_background` gained
  `overwrite` (see Dispatch bullet) and `unload_models()` (clears
  `_REMBG_SESSIONS`; wired to the Tools "Unload AI models" button).
- **Marquee → Image Upscaler (v2.3; engine replaced in v4.1):**
  `upscale_image(src, out_path=None, target="2K", model="Fast",
  fit="letterbox")` in `bud3eij/upscale.py` (lazy import) super-resolves a
  low-quality image with **Kim2091's UltraSharp V2** models loaded through
  **spandrel** on **torch CUDA** (auto CPU fallback). Runs enough ×4 passes
  (tiled, capped at ×16) to exceed the fitted size, then Lanczos-fits +
  **letterboxes** to the exact `TARGETS` resolution (1080p 1920×1080 / 2K
  2560×1440 / 4K 3840×2160) — output is always exactly W×H. Always saves (PNG
  default; honours a chosen `.jpg`/`.webp`), via `unique_path`. Falls back to
  Lanczos if the model can't load (never hard-fails). **QUALITY tiers** in
  `UPSCALE_MODELS` (`DEFAULT_UPSCALE_TIER = "Fast"`): **Fast** =
  `4x-UltraSharpV2_Lite` (RealPLKSR, ~28 MB), **Max** = `4x-UltraSharpV2`
  (DAT-2, ~133 MB). **Chosen by a measured A/B** (PSNR on degraded test
  renders + visual crops): Lite beat the old ONNX *Max* by ~1.8 dB at a
  fraction of its time, full V2 by ~2.6 dB; SPAN models (ClearReality) were
  faster but artifact-prone, and HAT-L was slower AND worse — don't revisit
  without re-measuring. Models cached per tier in `_UPSCALE_SESSIONS` (loaded
  via `spandrel.ModelLoader`, device remembered on the model object); each
  downloads once to `~/.bud3eij/models/` (or a bundled copy via
  `sys._MEIPASS`). GUI panel `_build_mq_upscaler` + `_on_up_model_change`/`on_upscale_drop`/
  `browse_upscale`/`set_upscale_file`/`on_upscale_run`/`_upscale_worker`/
  `_set_up_progress`/`_upscale_done`; **QUALITY** (`self.up_model`, Fast/Max) +
  **TARGET** (`self.up_target`, 1080p/2K/4K) `CTkSegmentedButton`s. **Real filling
  progress bar + live %:** `upscale_image` takes an optional `progress(frac)` callback
  — it plans the per-pass tile count up front and reports `tiles_done/total` (reserving
  the tail for the fit/save step, ending at 1.0); `_upscale_worker` marshals each
  fraction back via `self.after(0, self._set_up_progress, …)`, which sets the bar and
  shows `Upscaling to <target> with <tier>…  N%`. (CPU SR is slow, esp. Max → 4K, so
  the live bar matters.) CLI: `--upscale FILE [TARGET]` (uses the Fast tier).
  **v3.1 changes:** `UPSCALE_MODELS` values are now **4-tuples** `(filename, url,
  blurb, sha256)` — the blurb stays at index 2; downloads stream via `urlopen`
  with a **30 s socket timeout** and are **SHA-256-verified** (mismatch → delete +
  clear error). `fit` is now real: `"letterbox"` (pad, default) or `"crop"`
  (cover + center-trim), exposed as the **FIT** segmented (`self.up_fit`,
  Pad/Crop via `App.UPSCALE_FITS`). SR is **skipped below `_SR_MIN_GAIN`
  (1.25×)** — a full ×4 pass then a Lanczos *down*scale costs minutes + ~GB RAM
  for a near-identical result. Also gained `overwrite` + `unload_models()`.
- **Vanguard = a multi-tool AI-text page (tool switcher added v3.2).** Same
  pattern as Marquee: `_build_vanguard` is `_section_header` + a
  `CTkSegmentedButton` (`self.vg_tool`: "AI Detector" / "Text Extraction" /
  "What's The Font") + a container of self-contained panels in `self.vg_panels`,
  swapped by `_show_vg_tool` (grid/grid_remove). The detector lives in
  `_build_vg_detector` (attrs `vg_*`), Text Extraction in `_build_vg_ocr`
  (attrs `vgo_*`), What's The Font in `_build_vg_font` (attrs `vgf_*`). Add the
  next text tool as a fourth value + `_build_vg_<tool>` panel.
- **Vanguard → AI Text Detector (v3.0):** `detect_ai_text(source, is_file=False,
  progress=None)` in `bud3eij/vanguard.py` (lazy import) estimates how likely text is
  AI-generated using **`desklib/ai-text-detector-v1.01`** (a DeBERTa-v3-large fine-tune,
  #1 open model on the **RAID** robustness benchmark) exported to ONNX and run on the
  already-bundled **onnxruntime** — *no PyTorch*. Tokenises with the light **`tokenizers`**
  (Rust) lib via the model's own `tokenizer.json` (verified byte-identical to HF's
  tokenizer). The text is split into ~3-sentence chunks (`_chunk_spans`, capped at
  `_MAX_CHUNKS=200` by merging more sentences on huge docs), **batch**-scored
  (`_score_chunks`, `_BATCH=8`) through sigmoid→P(AI); the **overall score** is a
  **scored-token-weighted** mean (v3.1 — `_score_chunks` returns `(probs, tokens)`;
  char-length weights let truncated mega-chunks dominate with unscored text)
  → `CONFIDENCE_TIERS` (Human / Likely Human / Uncertain / Likely AI
  / AI). Returns a GUI-agnostic dict (`score` 0-100, `tier`, per-chunk `spans` with char
  offsets + `p_ai`, `too_short`, `model`); chunks ≥ `FLAG_THRESHOLD=0.60` get highlighted.
  `extract_document_text` reads `.txt/.docx/.pdf` (same engines as `converters.py`).
  Like the other models it sits **outside** `convert_file`/`CONVERSIONS`. **Model export
  is a one-off dev step** (`_export_vanguard.py`, run in a throwaway `.venv_export` with
  torch — never the runtime venv): the custom head (backbone → attention-masked mean-pool →
  linear → 1 logit) is rebuilt and `torch.onnx.export`ed (`dynamo=False`) → **fp32, ~1.7 GB**
  `model.onnx`. **fp32 is the only viable format here:** it matched torch exactly
  (Δ=0.0000), but dynamic **int8** drifted +0.15 toward false positives and **fp16 won't
  load in onnxruntime** for this graph (`Cast`/`Clip` op-type mismatches) — both rejected.
  Because the app is **personal-use only**, the 1.7 GB `model.onnx` + `tokenizer.json` are
  **neither bundled nor hosted**: they live in the local cache `~/.bud3eij/models/vanguard/`
  where `_ensure_file` finds them (it checks, in order, a `sys._MEIPASS` bundle → a dev-local
  `vanguard_model/` → the cache; raises a clear error if absent). **Caveat (by design):**
  desklib catches AI text near-100% but over-flags some clean/simple/non-native *human*
  writing as AI — inherent to all detectors; the UI shows an estimate + disclaimer, never an
  accusation. GUI panel `_build_vg_detector` (was `_build_vanguard` before the
  v3.2 switcher; paste `CTkTextbox` + Upload/
  drag-drop, **Detect AI Text** button, determinate progress + live %, results card with big
  score %, tier chip, a read-only textbox that **highlights flagged passages** via tk
  `Text` tags, a **Reset** button (`reset_vanguard`, beside Detect — clears input/
  results/highlights/score back to the initial state), and a visible **disclaimer**).
  Tier colour is split for contrast: **`_vg_tier_text`** (mode-aware (light,dark) for
  the score + status text) and **`_vg_tier_chip`** (a solid dark bg so the white chip
  text clears WCAG AA in both modes). Handlers
  `on_vanguard_drop`/`browse_vanguard`/`set_vanguard_file`/`on_vanguard_detect`/
  `reset_vanguard`/`_vanguard_worker`/`_set_vg_progress`/`_vanguard_done`/
  `_render_vanguard_result`. Nav icon `assets/ui/shield-check.png`. CLI: `--detect FILE`.
  **v3.1 GUI hardening:** `set_vanguard_file` extracts on a **worker thread**
  (`_vg_load_worker`/`_vg_load_done` — a big PDF used to freeze the whole window);
  detect/reset are guarded by the **`self._vg_run` generation counter** (Reset
  increments it; stale `_vanguard_done`/`_set_vg_progress` callbacks return
  early instead of resurrecting results); highlight offsets get a surrogate-pair
  correction (`tk_off` in `_render_vanguard_result`) because Tcl 8.6 counts
  astral chars (emoji) as 2; the private `_textbox` access is centralised as
  `self.vg_out_text`; `unload_models()` frees the ~2 GB session (Tools button).
  **Detection is an estimate, NOT proof**
  — the UI says so; never phrase results as an accusation.
- **Vanguard → Text Extraction (v3.2):** `extract_text(src, model="Fast")` in
  `bud3eij/ocr.py` (lazy import) OCRs every text line out of an image with
  **RapidOCR** (`rapidocr` pip package, Apache-2.0) on the already-bundled
  **onnxruntime**. **QUALITY tiers** in `OCR_MODELS` (`DEFAULT_OCR_TIER =
  "Fast"`), engines cached per tier in `_ENGINES` + `unload_models()`:
  - **Fast** = PP-OCRv4 mobile det/cls/rec (~15 MB) shipped **inside the wheel**
    (no downloads, fully offline; the ch models also read Chinese). Weakness:
    the ch recognizer **drops spaces in English** ("two words in one") and the
    default detector skips faint/odd lines.
  - **Max** = the measured-best English recipe: **`Rec.lang_type=EN`** (the
    English-dedicated recognizer fixes spacing) + looser detection
    (`Det.box_thresh=0.4`, `Det.unclip_ratio=2.0` — recovers skipped lines;
    the default unclip crops glyphs so the rec garbles + score-filters them) +
    `_prepared_input` (Lanczos ~2× pre-upscale of images < 1600 px, passed as a
    **BGR ndarray**). Just as fast as Fast; only the ~10 MB en rec model
    downloads once (rapidocr SHA-256-verifies its own downloads) into
    `~/.bud3eij/models/rapidocr/` via `Global.model_root_dir` (NOT the package
    dir — keeps the frozen exe folder pristine). **The PP-OCRv4 *server* models
    were tested and rejected**: ~10× slower and they fragment/skip lines on
    UI-style screenshots (tuned for large natural photos) — don't "upgrade" to
    them without re-measuring.
  Returns a GUI-agnostic `{"text", "lines": [(text, conf)], "count"}`. Sits
  **outside** `convert_file`/`CONVERSIONS` (produces text, not a file). GUI
  panel `_build_vg_ocr` + `_on_vgo_model_change`/`on_vg_ocr_drop`/
  `browse_vg_ocr`/`set_vg_ocr_file` (via `_set_image_file`)/`on_vg_ocr_run`/
  `_vg_ocr_worker`/`_vg_ocr_done`/`_vg_ocr_copy`: drop zone → **QUALITY**
  segmented (`self.vgo_model`, Fast/Max) → **Extract Text** GradientButton →
  eased-fill progress → results card with a read-only textbox + a **Copy to
  clipboard** button (`clipboard_clear()`/`clipboard_append()` — pure Tk).
  Zero lines found is a WARNING status, not an error. No history entries (like
  the detector — nothing is saved to disk). Panel icon `assets/ui/scan-text.png`.
  CLI: `--extract-text FILE [TIER]` (Fast/Max, prints the text).
- **Sonara = the audio-tools page (v4.0); first tool: Audio Stem Splitter.**
  `split_stems(src, progress=None)` in `bud3eij/sonara.py` (lazy import) splits a
  song into **vocals / drums / bass / other** with **Demucs `htdemucs_ft`** (a
  fine-tuned *bag of 4* Hybrid Transformer models — best open quality) on
  **PyTorch CUDA** (`device="cuda" if available else "cpu"`; seconds per song on
  the 3070 Ti, ~20 min on CPU). **PyPI demucs (4.0.1, pinned) predates
  `demucs.api`**, so the module drives `pretrained.get_model` + per-submodel
  `apply_model` directly (mirroring BagOfModels weight-averaging) and injects a
  lazy **`_CountingPool`** for real segment-level progress (apply_model submits
  every segment up front, executes lazily in `result()` — done/submitted is the
  fraction; pool/job params are **positional-only** because demucs forwards its
  own `pool=` inside the kwargs). Audio is decoded via its own `_load_audio`
  (ffmpeg `AudioFile` → torchaudio fallback) because demucs' `load_track`
  **`sys.exit`s** on failure. Returns GUI-agnostic `{"stems": {name: float32
  (N,2) ndarray}, "samplerate", "duration", "model", "device"}`. `save_stem`
  writes WAV via the **stdlib `wave`** module (torchaudio 2.11 delegated
  `ta.save` to the separate torchcodec pkg — not worth a dep) and MP3 via
  demucs' lameenc `encode_mp3`; same `overwrite` contract as the other tools.
  Checkpoints download once to `TORCH_HOME = ~/.bud3eij/models/torch`;
  `model_is_cached()` drives the one-time first-run download warning;
  `unload_models()` frees the model + `torch.cuda.empty_cache()` (Tools button).
  **Playback — `bud3eij/stemplayer.py`:** `StemPlayer(stems, samplerate)` mixes
  all stems through **one `sounddevice.OutputStream`** (a single clock = no
  drift; gain changes apply next ~23 ms block). Solo semantics are standard DAW:
  any solo → only soloed stems audible, else non-muted stems at their volume.
  The gain/mix math lives in `_gains()`/`_mix_block()` (pure numpy — unit-tested
  without an audio device). `play/pause/toggle`, `seek(frac)`, `position`,
  `finished` flag (callback raises `CallbackStop` at end; the GUI tick poll
  flips the ▶ button back), `close()` releases the device (wired into
  `_on_close`). Note: Bluetooth sinks take ~1 s to wake before position advances.
  GUI page `_build_sonara` (attrs `sn_*`): drop zone (AUDIO_EXTS incl. mp4/webm
  — ffmpeg uses the audio track) → **Split Stems** GradientButton → real
  progress bar + live % → **player card** (hidden until done): ▶/⏸ (`PLAY_GLYPH`/
  `PAUSE_GLYPH`, Segoe UI Symbol), seek slider (0-1000; `_sn_slider_drag` flag
  stops the 100 ms `_sn_tick` updater's writes from re-triggering seek), time
  label, and 4 stem rows (icon `mic`/`drum`/`guitar`/`music` via
  `SONARA_STEM_META` + name + **M**/**S** toggles (red when active,
  `_sn_style_toggle`) + volume slider 0-100 + per-stem **Save** →
  `_ask_save("sonara_save")`, wav/mp3, worker + `add_history`). Handlers
  `on_sonara_drop/browse_sonara/set_sonara_file/on_sonara_split/_sonara_worker/
  _set_sn_progress/_sonara_done/_sn_toggle_play/_sn_tick/_sn_on_seek/
  _sn_toggle_mute/_sn_toggle_solo/_sn_set_volume/on_sn_save_stem/
  _sn_save_worker/_sn_save_done`; `_sn_run` generation counter; a new split
  `_sn_close_player()`s the old mix (~340 MB RAM for a 4-min song). Nav icon
  `assets/ui/audio-lines.png`. CLI: `--split-stems FILE` (4 WAVs next to it).
- **Vanguard → What's The Font (v3.2):** `identify_font(src, top_k=5)` in
  `bud3eij/fontid.py` (lazy import) classifies the lettering in an image against
  **~3,500 Google Fonts** with `storia/font-classify-onnx` (EfficientNet-B3, MIT)
  on the already-bundled **onnxruntime**. Preprocessing **must mirror the
  upstream pipeline exactly**: CutMax = *crop* (not resize) to 1024 →
  letterbox-resize to the config's 320×320 with a **WHITE pad** → ImageNet
  normalise → NCHW (a black pad made everything score as "Zilla Slab Highlight" —
  cost real time in v3.2). `model.onnx` (~64 MB) + `model_config.yaml`
  (classnames + input size) download SHA-256-verified (30 s timeout, **exact**
  byte-size gate — a truncated download once passed a `>` min-size check) into
  `~/.bud3eij/models/fontid/`; `_ensure_file` checks `sys._MEIPASS` first like
  the upscaler. Returns `{"matches": [{"name","family","style","prob"}],
  "model"}`, softmax top-k descending; `_display_name` splits classnames
  (`AbhayaLibre-Bold` → "Abhaya Libre", "Bold"; `[wght]` suffix → "Variable").
  **Closest-match only, never an exact ID** — commercial fonts come back as their
  nearest Google lookalike; the UI disclaimer says so (tight crops of large text
  work best — e.g. Inter → "Instrument Sans" at 86%). Session cached in
  `fontid._SESSION` + `unload_models()`. GUI panel `_build_vg_font` +
  `on_vg_font_drop`/`browse_vg_font`/`set_vg_font_file`/`on_vg_font_run`/
  `_vg_font_worker`/`_vg_font_done`: drop zone → bare **Identify Font**
  GradientButton (no blurb card — the 5-row results card needs the vertical room
  at the default 1000×680 window) → eased-fill progress → results card with 5
  pre-built rows (rank, name, confidence bar + %), disclaimer. Panel icon
  `assets/ui/type.png`. CLI: `--identify-font FILE` (prints top-5).
- **Nexus = the utilities page (v4.2); two tools: Converter + QR Code.** Same
  multi-tool switcher as Marquee/Vanguard: `_build_nexus` = `_section_header` +
  a `CTkSegmentedButton` (`self.nx_tool`: "Converter" / "QR Code") + a container
  of panels in `self.nx_panels`, swapped by `_show_nx_tool`. Pure logic in
  **`bud3eij/nexus.py`** (lazy imports), re-exported from `app.py`; **no ML**,
  nothing in `~/.bud3eij/models/`, nothing for the Tools "Unload AI models"
  button. Registered as a **lazy frame builder** (don't build eagerly). Nav icon
  `assets/ui/compass.png`.
  - **Nexus → Converter (`_build_nx_convert`, attrs `nxc_*`):** a top category
    `CTkSegmentedButton` (`self.nxc_cat`: Currency / Units / Time Zone) swaps the
    input sub-frame (`self.nxc_frames`, grid/grid_remove via `_show_nxc_cat`);
    a shared result card shows a big result + detail line + **Copy result**
    (`_nxc_copy` → pure Tk clipboard) + **⇄ Swap** (`_nxc_swap`). **Live** —
    every input recomputes on a **150 ms debounce** (`_nxc_schedule` → `after` →
    `_nxc_compute`, which dispatches to `_nxc_compute_currency/_units/_tz`). No
    file output ⇒ **no `add_history`, no progress bar, no GradientButton**. The
    `_show_*`/`_nxc_unit_cat_change` handlers `.set()` their segmented/option
    value so they're correct when called programmatically (tests), not only on
    click. Use `_bind_typing(widget, handler)` to fire on every keystroke (binds
    the entry, reaching `widget._entry` for comboboxes).
    - **Currency:** `load_rates()` → `convert_currency(amount, src, dst, rates)`
      (base-EUR cross-rate; EUR is implied 1.0). Rates load **offline-first:
      cache (`~/.bud3eij/nexus/rates.json`) → bundled seed
      (`assets/data/rates_seed.json`)** — a fresh machine still converts. The
      ECB/Frankfurter feed omits the **USD-pegged Gulf currencies**, so
      `USD_PEGGED` (BHD/AED/SAR/QAR/OMR, fixed units-per-USD) is added by
      `_augment_pegged` at load (derived from the USD rate, so the pegs stay
      consistent across a refresh; the cache stores only the pure ECB set).
      Dropdowns show **full-name labels** (`currency_label` → `USD (US Dollar)`;
      `_code_from_label` extracts the code back) and are **typeahead-filtered**
      via `_attach_search` (the combobox values narrow as you type).
      **Refresh** (`_nxc_refresh_rates`, worker thread) calls `refresh_rates()`
      → fetches ECB rates from the open **Frankfurter** endpoint
      (`api.frankfurter.dev/v1/latest`, stdlib `urllib`, **needs a User-Agent**
      — a bare request 403s; `.dev/latest` 404s, the `/v1/` path is required),
      caches them, and recomputes; a failure is a **WARNING, not an error**
      (keeps the cached set). "Rates as of <date> · live/cached/bundled snapshot".
    - **Units:** `convert_units(value, src_unit, dst_unit)` via **`pint`** (one
      shared lazy `UnitRegistry`). `UNIT_CATEGORIES` (11 categories → `[(label,
      pint_unit)]`) drives a category `CTkOptionMenu` + From/To menus; pint
      handles **temperature offsets** correctly (the reason we don't roll our own
      factor table). Mismatched dimensions raise `ConversionError`.
    - **Time Zone:** `convert_timezone(dt, src_tz, dst_tz)` (stdlib `zoneinfo` +
      the bundled **`tzdata`**); `parse_datetime` accepts ISO / `YYYY-MM-DD HH:MM`
      / bare date / bare time / "now"; `tz_offset_str` shows `UTC±HH:MM`; a
      **day-rollover note** (next/previous day) and a pinned **world clock**
      (`WORLD_CLOCK_ZONES`). The From/To comboboxes show a short curated list
      (`COMMON_TIMEZONES`, ~32) by default — the full IANA set (`list_timezones()`,
      ~600) is a scroll-arrow mess — and `_attach_search` **filters the full set
      as you type** (prefix matches first), falling back to the curated list when
      cleared. `_attach_search(combo, get_values, on_change, get_default=None)` is
      the shared typeahead helper (binds the combobox's `_entry` KeyRelease).
  - **Nexus → QR Code (`_build_nx_qr`, attrs `nxq_*`):** a content-type
    `CTkSegmentedButton` (`self.nxq_type`, `QR_TYPES`: Text/URL · Wi-Fi · Email ·
    Phone · SMS · vCard · Geo) swaps the field group (`self.nxq_groups`, built by
    `_build_nxq_group` from `QR_FIELD_SPECS`; widgets stored in
    `self.nxq_fields[kind]`). `build_qr_payload(kind, fields)` makes the encoded
    string (e.g. `WIFI:T:WPA;S:..;P:..;;` with `;,:"\\` escaped; vCard 3.0;
    `mailto:`/`tel:`/`SMSTO:`/`geo:`) — **returns "" when essentials are blank**
    so the empty state shows a placeholder, not a meaningless QR. Options:
    EC L/M/Q/H, module size + quiet-zone margin sliders, FG/BG via
    `tkinter.colorchooser`, optional **centre logo** (`make_qr` auto-bumps EC to
    H and pastes it on a white backing). **Live preview** (180 ms debounce,
    `_nxq_compute` → `make_qr` → `CTkImage`). **Save** = a `GradientButton` (icon
    `qr-code`, busy "Generating") → `_ask_save("nexus_qr")` → worker `save_qr`
    (PNG or **SVG**, `overwrite=True`) → `add_history(f"QR Code · {kind}", out,
    True)`. **Copy image** → clipboard `CF_DIB` via pywin32 (falls back to
    copying the payload text). Encoder = `qrcode[pil]`.
    **Gotcha (cost real time):** `CTkLabel.configure(image=None)` after an image
    has been shown is a CustomTkinter bug ("image doesn't exist" on the *next*
    set) and `image=""` warns — the empty/error state swaps in a reusable 1×1
    transparent `CTkImage` (`self._nxq_blank`) instead. **Never pass `image=None`
    to a CTkLabel that has shown an image.**
  Marquee, Vanguard, Tools) raising stacked frames — all functional. The sidebar foot has a **sun/moon
  appearance toggle** (`_toggle_appearance`, `SUN_GLYPH`/`MOON_GLYPH` in
  "Segoe UI Symbol"), replacing the old Light/Dark/System dropdown. Each
  `_build_*` view starts with `_section_header(title, subtitle)`; controls sit in
  rounded "cards" (`fg_color=CARD_SOFT` — the constant replaced the repeated
  `("#DFD9DA","#2B2629")` literal in v3.1). Conversions run on a worker
  `threading.Thread`; UI updates are marshalled back with `self.after(0, ...)`
  (Tkinter is not thread-safe). Drop zones are built via the shared
  **`_build_drop_zone(parent, row=…, icon=…, title=…, hint=…, on_drop=…,
  on_click=…)`** helper (v3.1 — used by Converter, Batch, both Marquee panels;
  returns `{"zone","icon","primary","secondary"}`), which wires
  `_register_drop` (DnD + click + drag-hover border) and `_make_labels_wrap`.
  **Use it for any new tool panel.** Other v3.1 shared plumbing — use these
  rather than re-rolling per panel:
  - **`_job_started()`/`_job_finished()`** around every worker, and
    **`_job_done(status_label=…, progress_bar=…, button=…, src=…, out=…,
    error=…)`** as the standard finish (hides progress, re-enables, sets ✓/✕
    status, records history). `_on_close` (wired to `WM_DELETE_WINDOW`) warns
    before quitting while `_active_jobs > 0`.
  - **Generation counters** `self._convert_run`/`self._vg_run`: Clear/Reset
    increments them; stale worker completions check and return early.
  - **`_ask_open`/`_ask_open_multiple`/`_ask_save`/`_ask_dir(key, …)`** wrap the
    filedialogs and remember the last folder per key (`self._last_dirs`).
  - **`_set_image_file(...)`** is the shared image-validation/preview for the
    Marquee panels; `_not_a_file_message(path)` words folder-vs-file drops.
  - **`_setup_frozen_logging()`** (called in `main()`) tees stdout/stderr of the
    windowed exe to `%LOCALAPPDATA%\Bu D3eij\app.log` so prints aren't lost.
  - The Recent table only refreshes when it's the visible frame
    (`self._current_frame`, set by `show_frame`); Tools stats refresh on show
    (`_refresh_tools`); a bare file argument to the exe preloads the Converter.
- **Animated action buttons (`GradientButton`, redesigned v3.1.5):** all eight
  primary CTAs — Converter "Convert Now", YouTube "Download", Marquee "Remove
  Background" + "Upscale Image", Vanguard "Detect AI Text" + "Extract Text"
  + "Identify Font" (v3.2), Sonara "Split Stems" (v4.0) — are the same
  custom `GradientButton(ctk.CTkFrame)` (defined just above `class App`), not
  `CTkButton`s. CustomTkinter has no CSS, so the whole visual is **composed in
  Pillow** and animated by swapping a `CTkImage` on an inner label each tick.
  v3.1.5 "dopamine" effects: a **living lava base** (the gradient scrolls
  through the looping `LAVA` palette deep-red → red → ember orange → hot pink),
  top gloss + sweeping shine, an **orbiting comet** (white-hot head + golden
  trail racing along the rounded-rect border via `_perimeter`), **rising ember
  particles** (`_spawn_ember`, capped per state), a **click ripple** from the
  press point (`_burst`), and on `stop_busy(success=True)` a **confetti burst +
  white flash** (`_celebrate` — the payoff; `_job_done` passes
  `success=error is None`). Busy = lava + **flowing diagonal candy stripes** +
  double shine + animated `busy_text` dots (per-button: Converting /
  Downloading / Removing / Upscaling / Detecting / Extracting / Identifying /
  Splitting); `icon=` names an
  `assets/ui/*.png` tinted white. Drop-in API: `grid`, `command`,
  `configure(state=…)`, `start_busy()`/`stop_busy(success=…)`. Static layers
  cache by `(w, h, alive)` where **alive = enabled or busy** (a running button
  shows full lava even though clicks are disabled — keying on `enabled` alone
  made the old busy state grey). The loop only runs while **mapped** (pauses on
  `<Unmap>`, cancelled on `<Destroy>`) and pauses after `IDLE_PAUSE_MS` (12 s)
  without input — clicks/celebrations reset the idle clock, plain embers don't
  (or it would never pause). Particle/orbit sprites are pre-rendered radial
  glows (`_glow_dot`) — never per-tick Gaussian blurs; out-of-canvas particles
  are skipped (negative `alpha_composite` coords raise). Render is
  device-pixel correct via `_get_widget_scaling()` (source rendered at realized
  px, `CTkImage size = px / scaling`).
- **Avoiding text overflow:** a fixed-size container (`grid_propagate(False)`)
  does NOT clip its children, so an unbounded label (e.g. a long filename) spills
  past the border. Use `_make_labels_wrap(container, labels)` (binds
  `<Configure>` → responsive `wraplength`) for wrapping text, or `_ellipsize()`
  for single-line text like the export path. Set `wraplength` on any free-text
  label you add.
- **Icons (1.4):** bundled PNGs under `assets/`. `_filetype_icon(ext, size)`
  returns a colored, aspect-preserved `CTkImage` (ext mapped via `EXT_ICON`/
  `icon_key_for_ext`, fallback `default`). `_ui_icon(name, size, light, dark)`
  loads a black lucide silhouette and **re-tints its alpha** per theme (pass
  white/white for icons on the red active-nav pill). Both cache in
  `self._icon_cache`. Regenerate assets with `tools/fetch_icons.py` (needs the
  dev-only svglib/pycairo, not in requirements).
- **Typography — Inter (enhancement pass):** the UI font is **Inter**, bundled as
  four static TTFs under `assets/fonts/` (OFL) and loaded *privately* (process-only)
  at startup by `_load_app_fonts()` via GDI `AddFontResourceExW(..., FR_PRIVATE)` — so
  Inter renders **without a system install**, in dev and the frozen exe alike (it's
  bundled by the existing `--add-data "assets;assets"`; **no build-command change**).
  `App._init_fonts()` (called first in `__init__`, before any widget) confirms the
  family is visible to Tk and sets the theme default (`bud3eij_theme.json` `CTkFont` →
  Inter), falling back IBM Plex Sans → Segoe UI. Use **`self._font(size, weight)`** for
  any new label — `weight` is a *role*: `"regular"` (400 body, family `Inter`),
  `"medium"` (500 labels, family `Inter Medium`), `"semibold"` (600 headings/CTAs,
  family `Inter SemiBold`). Inter's heavier faces register as their **own Tk families**
  (that's why medium/semibold are selected by family at `weight="normal"`, not by Tk's
  binary bold flag). Plain body labels can omit the font (they inherit Inter from the
  theme default). Don't reintroduce raw `CTkFont(weight="bold")` for UI text — use the
  helper so the weight scale stays intentional. (`GradientButton` draws its text in
  Pillow from the bundled `Inter-SemiBold.ttf`.)
- **Frame stacking gotchas (cost real time in 1.4):** `show_frame` uses
  **grid/grid_remove**, NOT `tkraise` — a `CTkScrollableFrame` (Home) will not
  raise above plain sibling frames sharing the grid cell. A top-level page frame
  must be **opaque** (a transparent one shows the stacked sibling behind it). And
  an **empty `CTkFrame` keeps its default 200×200** — only build a sub-frame once
  it has children, or it stretches its row (hit on failed Recent rows).
- **Lazy frame building + UI responsiveness (perf, 2026-06-13):** `_build_frames`
  no longer builds all nine pages up front — it stores `self._frame_container` +
  `self._frame_builders` (name→`_build_*` method) and leaves `self.frames` empty;
  **`show_frame` builds a frame on its first visit** and caches it. Reason:
  `set_appearance_mode` redraws *every* registered CTk widget, so building only
  what's been opened keeps both startup and the Light/Dark toggle cheap (toggle
  right after launch went ~252 → ~38 ms). Keep new pages lazy — register the
  builder, don't call it in `_build_frames`. Two more levers, both in `app.py`:
  (1) **drag-only animation pause** — `GradientButton._suspended` (class flag)
  makes the button's `_tick` skip its window-repainting compose; the App raises it
  **only on a genuine root move/resize** (`_on_root_configure`: root `<Configure>`
  with a changed `(x,y,w,h)`, debounced 130 ms via `_resume_animations`) so a
  dragged window stops churning. Do NOT trigger it on tab switches or wrap the
  toggle in it (an earlier global version did and broke first-paint / helped
  nothing). (2) **flicker-free toggle** — `_frozen_redraw(fn)` wraps
  `set_appearance_mode` in a Windows **`WM_SETREDRAW`** freeze on **Tk's content
  HWND (`self.winfo_id()`)**, then one `RedrawWindow`. Freeze the content window,
  **never `GA_ROOT`** — that froze the OS title bar and blanked the min/close
  buttons. Degrades gracefully without pywin32.
- **Recent/history:** persisted to `%LOCALAPPDATA%\Bu D3eij\history.json`
  (`load_history`/`save_history`, cap `MAX_HISTORY`). `add_history()` mutates the
  shared `self.history`, so off the main thread it must be called via
  `self.after(0, self.add_history, ...)` (both the single and batch paths do).
  v3.1: `load_history` drops non-dict entries (one corrupt entry used to crash
  `_recent_row` at startup); "Clear history" asks for confirmation.
  **Perf (2026-06-13):** the Recent table is the app's heaviest widget set
  (~12 CTk widgets/row, up to 100 rows). `_refresh_recent` is **guarded by
  `self._recent_dirty`** and rebuilds only when the history actually changed —
  `show_frame` calls it on every Recent visit but it no-ops when clean (it was
  rebuilding from scratch each time: ~0.5 s at 14 rows, seconds at 100).
  `add_history`/`clear_history`/the initial build set the flag. Because
  `set_appearance_mode` redraws every registered widget (hidden ones too), the
  Recent rows also taxed the theme toggle, so `_toggle_appearance` **destroys
  the rows (marking dirty) when Recent isn't on screen** before flipping — they
  rebuild lazily on the next visit. Don't reintroduce an unconditional
  per-show rebuild.
- **CLI:** `_run_cli()` / `main()` — `--convert FILE FORMAT`,
  `--download URL FORMAT` (mp3/mp4, saves to cwd), `--remove-bg FILE [TIER]`
  (transparent PNG next to the source; TIER = Flash/Mid/Omega, default Mid),
  `--upscale FILE [TARGET]` (1080p/2K/4K, default 2K), `--detect FILE`,
  `--extract-text FILE [TIER]` (Fast/Max, prints the OCR'd text),
  `--identify-font FILE` (prints the top-5 font matches),
  `--split-stems FILE` (saves the 4 stem WAVs next to the source), and the v4.2
  Nexus flags — `--qr "TEXT" [OUTFILE]` (PNG, or `.svg` by extension),
  `--convert-units "100 km to mi"`, `--convert-currency AMT SRC DST`,
  `--convert-tz "<datetime>" SRC DST` — run
  headless; extra positional args are rejected with a clear `parser.error`.
  (**Note:** the file converter already owns `--convert FILE FORMAT`, so the unit
  converter is `--convert-units`, not an overload of `--convert`.)
  No flags → GUI; a **bare file argument** (e.g. a file dragged onto the exe)
  opens the GUI with the Converter preloaded. All of these double as the way to
  smoke-test the frozen exe.
- **Branding/assets:** `resource_path()` resolves bundled files in dev and in
  the frozen exe (`sys._MEIPASS`). Window + exe icon = `AppLogo.ico`; in-app
  logo (sidebar header + Home banner) = `DashboardLogo.png` loaded via
  `_load_logo()` → `CTkImage`. Both must be passed to PyInstaller (`--icon` +
  `--add-data`) or they won't appear in the exe.
- **Theme:** logo-derived red palette in `bud3eij_theme.json` (a recolored
  CustomTkinter theme) loaded via `set_default_color_theme(resource_path(...))`;
  appearance defaults to **Dark**. Palette constants (`RED`, `RED_HOVER`,
  `SIDEBAR_FG`, `DROP_BORDER`, `SUCCESS`, `ERROR`, `WARNING`, `MUTED`) sit at the top of
  the GUI section for targeted accents (active nav, drop-zone border + drag hover,
  section titles). The theme file must be bundled (`--add-data`). Regenerate
  the palette from the logo with `extract_palette` approach if the logo changes.
- **Contrast / WCAG AA (enhancement pass):** status colours are **(light, dark)
  tuples** tuned to ≥4.5:1 (normal) on the light cards/frames in light mode AND the
  dark surfaces in dark mode: `SUCCESS=("#0E6E39","#3DD17F")`,
  `ERROR=("#B30F16","#FF5C61")`, `WARNING=("#8A4500","#F2A65A")` (use `WARNING` for
  warning text — **never `"orange"`**, which fails contrast), `MUTED=("#595155",…)`.
  The **`CTkSegmentedButton`** theme uses a dark unselected fill (`#5C5457`) in light
  mode so its **white text isn't invisible** on a light gray (the old bug — selected
  stays brand red, white 4.87:1). When adding coloured text or a coloured chip, check
  fg/bg both ways with the WCAG formula (a throwaway `_contrast_audit.py` was used) —
  white-on-saturated-colour and grey-on-grey are the usual failures.

## Conventions & gotchas
- Match the existing style: type hints, lazy converter imports, small focused
  methods, `# noqa: BLE001` on the broad `except` blocks that intentionally
  catch-all (fallbacks / UI safety).
- **CTk + tkinterdnd2:** the root subclasses both `ctk.CTk` and
  `TkinterDnD.DnDWrapper` and calls `TkinterDnD._require(self)` in `__init__`.
  Drop targets are registered on widgets via `_register_drop`; dropped paths
  are parsed with `self.tk.splitlist(event.data)` (handles `{spaced paths}`).
- **Office COM (rules tightened in v3.1):** both paths `pythoncom.CoInitialize()`
  on the worker thread. `_docx_to_pdf_word` drives Word **directly**:
  `DisplayAlerts = 0`, `Documents.Open` → `SaveAs(FileFormat=17)` →
  `doc.Close(0)` in a `finally`, `word.Quit()` in a `finally` — Word is
  **multi-instance** COM, so Dispatch always creates our own instance and Quit
  is safe. `_pptx_to_pdf_powerpoint` is the opposite case: **PowerPoint is
  single-instance** COM — `Dispatch` attaches to a running PowerPoint and
  `Quit()` would close the user's open presentations — so it tries
  `GetActiveObject` first and only Quits when it `owned` (started) the
  instance. Preserve both patterns when touching these.
- **Markdown converters:** `pdf_to_md` uses pymupdf4llm (rides on the bundled
  PyMuPDF) and falls back to pdfplumber text; `docx_to_md` goes DOCX→HTML
  (mammoth) → MD (markdownify); `pptx_to_md` builds MD by hand from python-pptx
  (`## ` per slide, bullets by paragraph level, tables via `_pptx_table_to_md`,
  speaker notes). `md` is output-only — no `md` key in `CONVERSIONS`.
- **ffmpeg-python:** use real ffmpeg flag names as kwargs (e.g. `{"b:a":"192k"}`,
  not `audio_bitrate`); `vn=None` to drop video when extracting audio.
- **Images:** flatten alpha to RGB for formats without transparency
  (jpg/jpeg/bmp/gif); animated sources keep animation when the target supports
  it (gif/webp/tiff/png, `save_all=True`).
- **PyInstaller:** contrib hooks already cover pymupdf/fitz, pywin32,
  tkinterdnd2, customtkinter, cv2, pdfminer, reportlab, etc. The 1.1 deps need
  explicit collectors in the build command: `--collect-all pptx mammoth
  markdownify bs4` (python-pptx ships a default template; markdownify→bs4 needs
  its submodules) and `--collect-submodules pymupdf4llm --hidden-import tabulate`.
  **yt-dlp** loads its ~1800 extractors lazily, so static analysis misses them —
  use `--collect-all yt_dlp` (this enlarges the exe but is required for downloads
  to work). ffmpeg is NOT bundled (relies on the system install; yt-dlp mp3/mp4
  both need it).
- **pymupdf4llm + the `pymupdf.layout` trap (PDF→MD):** pymupdf4llm's
  `__init__` tries `import pymupdf.layout` and, if it succeeds, calls
  `pymupdf.layout.activate()` at **import time**. `pymupdf.layout` is a separate
  ~20 MB ONNX-model feature needing `onnxruntime`; when PyInstaller bundles its
  Python but not the models/runtime, `activate()` raises a *non-ImportError* and
  the whole `import pymupdf4llm` dies (PDF→MD then silently falls back to flat
  pdfplumber text). Fix: `--exclude-module pymupdf.layout --exclude-module
  onnxruntime --exclude-module rapidocr_onnxruntime` so the import cleanly
  `ImportError`s → classic text engine (which gives great Markdown and is what we
  want). `pdf_to_md` also calls `use_layout(False)` defensively and logs the
  reason on any fallback. **Do not remove these excludes** — they keep the exe
  lean and PDF→MD structure-aware. The harmless "Consider using the
  pymupdf_layout package…" stderr line is expected.

## Layout
```
app.py            GUI (App + views) + Recent-history store + CLI + entry point;
                  re-exports the bud3eij functions for headless use
bud3eij\          pure, GUI-free logic (importable/testable without the GUI):
  __init__.py
  formats.py      format model, helpers, ConversionError
  converters.py   convert_file + all document/image/AV converters
  youtube.py      download_youtube (yt-dlp)
  background.py   remove_background + BG_MODELS (Marquee bg remover)
  upscale.py      upscale_image + TARGETS (Marquee Real-ESRGAN upscaler)
  vanguard.py     detect_ai_text + CONFIDENCE_TIERS (Vanguard AI text detector)
  ocr.py          extract_text (Vanguard Text Extraction, RapidOCR)
  fontid.py       identify_font + FONTID_FILES (Vanguard What's The Font)
  sonara.py       split_stems + save_stem + STEMS (Sonara stem splitter, Demucs)
  stemplayer.py   StemPlayer (real-time 4-stem mixer on sounddevice)
  nexus.py        currency/units/timezone converters + QR builders (Nexus, v4.2)
requirements.txt  runtime deps (pyinstaller is dev-only, installed separately)
README.md         user-facing docs
CLAUDE.md         this file
PROGRESS.md       running work log
AppLogo.png       source square logo -> exe/window icon
AppLogo.ico       generated multi-size icon (from AppLogo.png)
DashboardLogo.png in-app branding (sidebar header + Home banner)
bud3eij_theme.json logo-derived red CustomTkinter theme (must be bundled)
assets\filetypes\ colored file-type icons (vscode-icons, MIT) — must be bundled
assets\ui\        monochrome nav/UI icons (lucide, ISC), tinted at runtime
assets\fonts\     bundled Inter TTFs (Regular/Medium/SemiBold/Bold, OFL) — the UI font
assets\data\      rates_seed.json — bundled ECB currency snapshot (Nexus offline seed)
assets\LICENSES.md icon attributions; regenerate via tools\fetch_icons.py (dev)
tools\fetch_icons.py  dev-only icon generator (Iconify -> PNG; not bundled)
tests\            verification scripts (v3.1): test_headless.py,
                  test_gui_smoke.py, test_com_paths.py — plain scripts, venv python
Bu D3eij.spec     PyInstaller spec (regenerated by the build command)
.venv\            Python 3.11 environment
dist\Bu D3eij\    built standalone app (~250 MB; keep the folder together)
```
`build\` (PyInstaller intermediates) is disposable and not kept.
