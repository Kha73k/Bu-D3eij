# PROGRESS — Bu D3eij

Running log of what's done and what's next. Update at the end of each session.

_Last updated: 2026-06-09_

## Status: working app + standalone exe — v2.3.5 (Marquee filling progress bars)

Core app, all required conversions, Recent history, Batch Convert, YouTube
downloads, and a **Marquee** image-editing section (Background Remover **+ Image
Upscaler**) are complete and verified — **both from source and in the rebuilt
standalone exe**. v1.1 = PowerPoint + Markdown; v1.2 = bug fixes; v1.3 = YouTube
downloads + sun/moon toggle; v1.4 = visual redesign (file-type icons, hero Home,
table Recent); v1.4.5 = animated "Convert Now" button; v2.0 = Marquee / Background
Remover (rembg); v2.1 = Marquee Flash/Mid/Omega model selector; v2.2 = split the
logic into a `bud3eij/` package; **v2.3 = Marquee Image Upscaler (Real-ESRGAN)**.

The project is now a **private GitHub repo**: https://github.com/Kha73k/Bu-D3eij
(branch `main`; v1.4 developed on `redesign-1.4`). Commit/push as work lands.

## Completed

### 2026-06-09 — v2.3.5: Marquee filling progress bars (replace back-and-forth bars)
- **Both Marquee tools now show a filling bar instead of the indeterminate
  back-and-forth one.**
- **Upscaler — real progress + live %.** `upscale_image` gained an optional
  `progress(frac)` callback (kept GUI-agnostic — invoked on the worker thread). It
  plans the per-pass tile count up front (`math.ceil(h/_TILE) * math.ceil(w/_TILE)`
  summed across the ×4 passes) and reports `tiles_done / total` per tile (via a new
  `on_tile` hook in `_sr_x4`), reserving the tail for the fit/save step and ending at
  `1.0`. `_upscale_worker` marshals each fraction back with
  `self.after(0, self._set_up_progress, frac, target, tier)`, which sets the bar and
  shows `Upscaling to <target> with <tier>…  N%`. `on_upscale_run`/`_upscale_done`
  now drive a **determinate** bar (no `start()`/`stop()`).
- **Background Remover — eased fill.** rembg's `remove()` has no progress callback, so
  a true % isn't possible; instead a timer-driven **eased fill**
  (`_mq_fill_start`/`_mq_fill_tick`/`_mq_fill_stop`) creeps the determinate bar toward
  ~90% while the worker runs and snaps to 100% on success — a filling bar, not a
  bouncing one.
- **Verified from source:** headless upscale to 4K on a tiny 4:3 input → 14 monotonic
  progress updates 0.075 → 1.0, output exactly 3840×2160; GUI smoke confirmed the bg
  eased fill creeps within (0, 0.9] and the upscaler bar/`…  42%` status update.
  Pure-UX change — no deps, version, or build-command change.

### 2026-06-09 — v2.3: Marquee Image Upscaler (Real-ESRGAN)
- **Second Marquee tool.** Marquee became a multi-tool page: `_build_marquee` now
  renders a **tool switcher** (`CTkSegmentedButton`: Background Remover / Upscaler)
  over two self-contained panels (`_build_mq_bgremover` moved the existing bg UI;
  `_build_mq_upscaler` is new), swapped by `_show_mq_tool`.
- **Image Upscaler:** drop a low-res image → pick **QUALITY** (Fast/Max) + **TARGET**
  (1080p/2K/4K) → clean, sharp upscale saved where you choose. New module
  `bud3eij/upscale.py`: `upscale_image(src, out, target, model)` runs **Real-ESRGAN**
  on the **already-bundled onnxruntime** (no PyTorch); enough ×4 passes (tiled, capped
  ×16) to exceed the fitted size, then Lanczos-fit + **letterbox** to the exact
  `TARGETS` resolution. Output always exactly W×H; PNG default; Lanczos fallback if the
  model can't load. Handlers `on_upscale_*`/`_on_up_model_change`/`_upscale_worker`/
  `_upscale_done` mirror the bg ones; indeterminate progress (CPU SR is slow toward
  4K). CLI `--upscale FILE [TARGET]`. `APP_VERSION = "2.3"`.
- **QUALITY tiers (`UPSCALE_MODELS`, default Fast):** **Fast** =
  `realesr-general-x4v3` (~4.7 MB, SRVGGNetCompact — fast, great on real low-quality
  photos); **Max** = `RealESRGAN_x4plus.fp16` (~34 MB, RRDBNet — sharper textures but
  *much* slower on CPU). Both expose float32 NCHW [0,1] I/O + exact ×4 (verified on
  onnxruntime, dynamic shape), so they share one inference path; sessions cached per
  tier in `_UPSCALE_SESSIONS`. Each downloads once to `~/.bud3eij/models/` (or a
  bundled `bud3eij/models/` copy), then caches. **Build command unchanged**
  (onnxruntime/numpy already bundled; the module rides on the static import).
  `requirements.txt`: added `numpy`/`onnxruntime` explicitly (now direct deps).
- **Verified from source:** headless `upscale_image` for 1080p/2K/4K → **exact**
  1920×1080 / 2560×1440 / 3840×2160, RGB, black letterbox bars on a 4:3 input, AI
  path used (no fallback); **both tiers** to 1080p → exact (Fast ~4.8 s, Max ~68 s,
  confirming the speed trade); GUI smoke (tool switcher swaps panels, QUALITY +
  TARGET selectors, bg remover intact, no frame regressions); `--upscale` CLI.
  **Frozen exe rebuilt + re-verified** (final build with the Fast/Max selector):
  `--upscale <img> 2K` → exact 2560×1440 PNG (onnxruntime + Real-ESRGAN model path
  work frozen, using the `~/.bud3eij/models` cache); GUI launches clean. (Killed any
  running `Bu D3eij.exe` before each build to avoid the file-lock COLLECT failure.)

### 2026-06-08 — v2.2: restructure — split logic into a `bud3eij/` package
- **Why:** ahead of growing the Marquee image-editing section, `app.py` had reached
  ~2,290 lines. A single growing file doesn't hurt the *running app* (one exe, same
  performance — load is the heavy libs, not line count) but raises edit-mistake risk
  and the cost of each change. Split now, while it's clean.
- **What moved:** the pure, GUI-free logic from `app.py` into a new package:
  `bud3eij/formats.py` (format model + helpers + `ConversionError`),
  `bud3eij/converters.py` (`convert_file` + all converters),
  `bud3eij/youtube.py` (`download_youtube`), `bud3eij/background.py`
  (`remove_background` + `BG_MODELS`). `app.py` keeps the GUI, Recent-history store,
  CLI, and `main()`, and **re-exports** the package functions so `import app;
  app.<fn>` and the CLI/tests are unaffected. Done by a one-off slice script
  (`_refactor.py`, deleted after) so code moved verbatim. `app.py`: 2,287 → 1,732
  lines.
- **Version bumped to 2.2.** No behaviour/UI change and still **one program, one
  exe** — but the restructuring is a deliberate foundation improvement for future
  additions (esp. the growing image-editing section), so it earns a version. The
  PyInstaller command is unchanged (it follows the static `from bud3eij...` imports
  and bundles the package automatically).
- **Verified from source:** all modules compile + `import app` re-exports present;
  conversions (png→jpg/webp/gif, pdf→md/txt), `remove_background` (RGBA, alpha
  0/255), GUI smoke (all 7 frames build, Marquee selector intact), and the
  `--convert`/`--remove-bg` CLI. **Frozen exe rebuilt + re-verified:** `--convert
  pdf md` → structure-aware Markdown (bud3eij.converters bundled, trap-fix intact),
  `--remove-bg` → transparent PNG (bud3eij.background + rembg bundled), GUI launches
  clean. (Build gotcha: a stale running `Bu D3eij.exe` locked the file and the first
  rebuild silently failed because a `| tail` pipe masked PyInstaller's exit code —
  killed the process and rebuilt without the pipe; confirmed a fresh exe timestamp.)

### 2026-06-08 — v2.1: Marquee model selector (Flash / Mid / Omega)
- **Quality tier selector** added to the Marquee page — a `CTkSegmentedButton`
  (Flash / Mid / Omega) with a live caption, styled like the YouTube format
  toggle. Tiers map via the new `BG_MODELS` constant to rembg models:
  **Flash** = `u2netp` (fastest, ~4.7 MB), **Mid** *(default)* =
  `isnet-general-use` (balanced — replaces the v2.0 `u2net` default with a
  moderately-better model), **Omega** = `birefnet-general` (max precision; larger
  first-run download + slower inference).
- `remove_background` gained a `model` arg (default `isnet-general-use`); sessions
  are now cached **per model** in `_REMBG_SESSIONS` (was a single
  `_REMBG_SESSION`). The GUI passes the chosen tier's model through
  `on_marquee_remove` → `_marquee_worker` → `remove_background`; the CLI
  `--remove-bg` uses the default (Mid). `APP_VERSION = "2.1"`.
- **No build-command change:** all three session classes were already bundled by
  `--collect-all rembg`; each model downloads its own `.onnx` on first use. The exe
  was rebuilt only to embed the new `app.py`.
- **Verified from source (3/3 tiers):** headless `remove_background` for `u2netp`,
  `isnet-general-use`, `birefnet-general` → RGBA output, alpha extrema (0,255),
  transparent corner / opaque subject; GUI smoke (selector renders, default Mid,
  caption updates Flash/Mid/Omega). **Frozen exe rebuilt + verified:**
  `--remove-bg` (default Mid/isnet) → RGBA transparent PNG (proves rembg's dynamic
  session loader works in the bundle); all three tier modules present under
  `_internal/rembg/sessions` (`u2netp`, `dis_general_use`, `birefnet_general`);
  GUI launches with no startup crash.

### 2026-06-08 — v2.0: Marquee — Background Remover
- **New sidebar section "Marquee"** (image editing). Added to `NAV_ITEMS`
  (before Tools), `NAV_ICONS` (`"Marquee": "sparkles"`, reusing the bundled
  `assets/ui/sparkles.png` — no new asset/icon toolchain), and the `_build_frames`
  dict. `show_frame` is generic, so the nav/active-pill highlight works unchanged.
- **First tool — Background Remover:** drop/select an image → transparent **PNG**
  saved where the user specifies (`asksaveasfilename`, default `<stem>_no-bg.png`).
  Module function `remove_background(src, out_path=None)` (rembg, `u2net` model,
  lazy import) sits outside `convert_file`/`CONVERSIONS` like `download_youtube`;
  session cached in module-level `_REMBG_SESSION`; reuses `unique_path` so it never
  clobbers. New view `_build_marquee` mirrors the converter/YouTube pages
  (drop zone via `_register_drop` + `_make_labels_wrap`, image-only validation,
  worker thread + `self.after(0, …)` marshalling, indeterminate progress bar,
  ✓/✕ status, `add_history` → shows in Recent).
- **Dep added:** `rembg` (its heavy deps — onnxruntime/numpy/opencv-python-headless
  — were already in the venv). The `u2net.onnx` model (~176 MB) downloads once on
  first run to `~/.u2net/`. `APP_VERSION = "2.0"`.
- **Verified from source (3/3):** headless `remove_background` on a generated image
  → RGBA output, alpha extrema (0,255), background corner alpha 0 / subject center
  alpha 255; GUI smoke (Marquee nav appears, page builds, active pill red, all
  frames switch with no errors, button disabled with no file); file validation
  (image enables the button, a .txt is rejected).
- **CLI:** added `--remove-bg FILE` (mirrors `--convert`/`--download`) so the
  frozen exe's background remover can be smoke-tested headlessly.
- **Exe rebuilt + verified (3/3 in the frozen build):** applied the build delta —
  dropped `--exclude-module onnxruntime`, added `--collect-all rembg
  --collect-all onnxruntime` (kept the `pymupdf.layout`/`rapidocr` excludes), and
  added **`--copy-metadata pymatting`** after the first rebuild died with *"No
  package metadata was found for pymatting"* (rembg imports pymatting, whose
  `__init__` reads its own dist-info). Frozen `--remove-bg` → transparent RGBA PNG;
  frozen `--convert doc.pdf md` → real `#` heading (pymupdf4llm structure-aware,
  proving the trap-fix survived); GUI launches with no startup crash. The u2net
  model is **not** bundled (mirrors the ffmpeg decision — downloaded/cached on
  first use). CLAUDE.md build command + notes updated to match.

### 2026-06-08 — v1.4.5: animated Convert Now button
- New `GradientButton(ctk.CTkFrame)` widget (defined just above `class App`) —
  a drop-in for the old `CTkButton` (`grid`, `command`, `configure(state=…)`),
  plus `start_busy()`/`stop_busy()`. The whole visual is composed in Pillow
  (gradient + gloss + gaussian shine band + gaussian-blurred glow + text +
  white-tinted `assets/ui/sparkles.png`) and animated by swapping a `CTkImage`
  on an inner label each tick.
- States: disabled (flat grey, no anim), idle (sweeping shine + breathing glow,
  ~20 fps), hover (brighter + glow bloom + faster shine, ~30 fps), press (dim),
  busy (double-shine flow + "Converting…" dots). Static layers are cached by
  `(w, h, enabled)`; animation only runs while mapped (pauses on `<Unmap>`,
  cancelled on `<Destroy>`) so it's idle-cheap.
- Wired into the convert flow: `on_convert_click` calls `start_busy()`,
  `_convert_done` calls `stop_busy()`.
- Verified from source (idle/hover/busy/disabled renders) and in the rebuilt
  frozen exe (renders + sparkle asset bundles under `_internal/assets/ui`).

### Earlier completed work

### 2026-06-08 — v1.4: professional visual redesign
- **Icon assets:** sourced file-type icons (vscode-icons, MIT) + UI/nav icons
  (lucide, ISC) via the Iconify API, rendered to transparent PNGs locally
  (svglib + rlPyCairo/pycairo; two-background alpha trick). Committed under
  `assets/filetypes/` + `assets/ui/` with `assets/LICENSES.md`; generator kept at
  `tools/fetch_icons.py`. Dev-only render deps (svglib/pycairo/etc.) are NOT in
  requirements and NOT bundled.
- **Icon helpers:** `icon_key_for_ext`/`EXT_ICON`, `_filetype_icon(ext,size)`
  (colored, cached), `_ui_icon(name,size,light,dark)` (alpha-tinted per theme,
  cached); `self._icon_cache`.
- **Sidebar:** logo + "Convert anything" tagline; nav buttons get leading icons;
  active state swaps to a white icon on the red pill.
- **Home (restyled):** hero headline + honest subtitle + file-icon cluster,
  quick-action buttons, **Popular conversions** cards, **Supported formats**
  showcase. Home is now a `CTkScrollableFrame`.
- **Converter:** drop zone shows the selected file's type icon.
- **Recent:** rebuilt as a table (File icon+name · From · To · Status · Time ·
  Open/Folder).
- **Palette:** added `CARD`/`CARD_BORDER`/`SURFACE_SOFT`/`TEXT`; cleaner sidebar.
- **Build:** added `--add-data "assets;assets"`. `APP_VERSION = "1.4"`.
- Verified: GUI smoke (both themes), screenshots of Home/Converter/Recent in
  light + dark.

#### Gotchas fixed during 1.4
- `show_frame` now uses **grid/grid_remove** (not `tkraise`) — a
  `CTkScrollableFrame` (Home) wouldn't raise above the plain sibling frames.
- A transparent top-level frame let the stacked sibling show through (Home must
  be opaque).
- An **empty `CTkFrame` keeps its default 200px size** — the failed-row actions
  frame stretched table rows until built only when it has buttons.

### 2026-06-08 — v1.3: YouTube downloads + sun/moon toggle
- **Sun/moon appearance toggle** (sidebar): replaced the System/Light/Dark
  `CTkOptionMenu` with a compact toggle button (`_toggle_appearance`,
  `SUN_GLYPH`/`MOON_GLYPH` in "Segoe UI Symbol"). Verified visually in both
  modes (screenshots).
- **YouTube page** (`_build_youtube`): paste a URL, pick MP4/MP3 (segmented),
  download. Asks for the save folder each time; live progress via a yt-dlp
  `progress_hook` marshalled to the UI thread; results recorded in Recent.
  `download_youtube(url, fmt, out_dir, hook)` uses yt-dlp + ffmpeg (mp3 =
  FFmpegExtractAudio 192 kbps, mp4 = bestvideo+bestaudio merged).
- **CLI `--download URL FORMAT`** added (mirrors `--convert`; enables frozen-exe
  testing of yt-dlp).
- **Dep added:** yt-dlp. Build command gains `--collect-all yt_dlp` (its ~1800
  extractors load lazily and are missed by static analysis).
- Verified: GUI smoke test (YouTube page builds, nav OK), real end-to-end
  downloads (MP3 457 KB + MP4 534 KB of "Me at the zoo"), and a visual check of
  the page. `APP_VERSION = "1.3"`.
- **Repo:** initialized git, `.gitignore` (excludes `.venv`/`dist`/`build`/
  `.claude`/`_verify_*`), pushed to the new private GitHub repo.

### 2026-06-08 — v1.2: bug fixes + cleanup
- **Drop-zone overflow (reported):** long file names spilled past the Converter
  drop-zone border (centered `inner` frame grew wider than the fixed-size zone;
  Tk doesn't clip children). Fixed with a responsive `_make_labels_wrap()`
  helper that binds the zone's `<Configure>` to set the labels' `wraplength`.
  Verified the label fits at both default and minimum window sizes (incl. a
  pathological 150-char no-space name).
- **Export-path label overflow:** long chosen folders could overflow the
  controls card; the displayed path is now shortened with a middle ellipsis via
  `_ellipsize()` (full path still used for saving).
- **Batch history race:** `_batch_worker` mutated the shared `self.history` from
  the worker thread while the UI could iterate it; history writes are now
  marshalled with `self.after(0, self.add_history, ...)` like the single path.
- **PPTX→MD tables:** `_pptx_table_to_md` now escapes `|` (and `\`) in cells so
  cell content can't break the Markdown table; `pptx_to_md` uses
  `(para.level or 0)` to avoid a crash if a bullet level is `None`.
- **Copy:** Home tagline now mentions presentations + Markdown. `APP_VERSION = "1.2"`.
- Verified headless (ellipsize + pipe-escape) and via GUI smoke tests. No new
  dependencies; no converter behaviour changed.

### 2026-06-08 — v1.1: PowerPoint + Markdown
- **New conversions:** PDF→MD, DOCX→MD, PPTX→MD, PPTX→TXT, PPTX→PDF.
  - PDF→MD via `pymupdf4llm` (rides on the already-bundled PyMuPDF), pdfplumber
    text fallback. DOCX→MD via `mammoth` (→HTML) + `markdownify` (→MD).
    PPTX→MD/TXT via `python-pptx` (slides → `## ` sections, bullets, tables,
    notes). PPTX→PDF via PowerPoint COM (`_pptx_to_pdf_powerpoint`) with a
    reportlab text-only fallback — mirrors the DOCX→PDF strategy.
- **Format model:** added `PRESENTATION_EXTS = {"pptx"}`, `md` added to
  `DOC_EXTS` (output-only — no `CONVERSIONS` key), `category_of()` now returns
  "Presentation". Home "Supported formats" card updated.
- **Deps added:** python-pptx, pymupdf4llm, mammoth, markdownify.
- **Verified (headless 5/5):** PPTX→MD/TXT/PDF, DOCX→MD, PDF→MD against
  generated samples; PPTX→PDF confirmed on both the PowerPoint-COM path and the
  reportlab fallback; CLI (`--convert deck.pptx md`) and a GUI smoke test
  (all frames build; pptx dropdown offers pdf/txt/md). `APP_VERSION = "1.1"`.
- **Exe rebuilt + verified (5/5 in the frozen build):** PDF→MD, DOCX→MD,
  PPTX→MD/TXT/PDF all produce real structure-aware output from
  `dist\Bu D3eij\Bu D3eij.exe --convert ...`.
- **PyInstaller gotcha fixed:** pymupdf4llm's `__init__` activates the
  `pymupdf.layout` ONNX feature at import time; bundling its Python without the
  models/`onnxruntime` made `import pymupdf4llm` crash → PDF→MD silently fell
  back to flat pdfplumber text. Fix = `--exclude-module pymupdf.layout
  onnxruntime rapidocr_onnxruntime` (clean ImportError → classic text engine,
  leaner exe) plus `--collect-submodules pymupdf4llm --hidden-import tabulate`.
  Build command in CLAUDE.md/README updated to match.

### 2026-06-06 — Initial build
- Scaffolded `app.py` (CustomTkinter + tkinterdnd2), `requirements.txt`, `README.md`.
- Sidebar nav (Home, Converter, Recent, Batch Convert, Tools); drag-and-drop
  + click-to-browse upload zone; auto-detect input format; compatible-only
  "Convert to"; threaded conversion with progress bar + success/error status.
- Conversions implemented and verified (8/8 headless):
  - Images: JPG/PNG/WEBP/BMP/GIF/TIFF swaps (Pillow).
  - Docs: PDF→TXT (pdfplumber), PDF→DOCX (pdf2docx), DOCX→TXT (python-docx),
    DOCX→PDF (docx2pdf via Word, reportlab fallback).
  - A/V: MP4→MP3/WAV, MP3→WAV, WAV→MP3 (ffmpeg-python).
- Environment set up: installed ffmpeg (winget Gyan.FFmpeg) and Python 3.11;
  created `.venv` on 3.11; verified GUI builds and launches.

### 2026-06-06 — Follow-up
- **Python cleanup:** uninstalled system Python 3.14.5; 3.11.9 is now the
  only/default Python. `.venv` unaffected.
- **Recent tab (functional):** persistent history in
  `%LOCALAPPDATA%\Bu D3eij\history.json`; scrollable list with per-entry
  Open / Folder buttons + Clear; records single and batch conversions.
  Verified (record/persist/reload/clear).
- **Headless CLI:** `app.py --convert FILE FORMAT` (also enables frozen-exe testing).
- **Packaged exe:** PyInstaller one-folder windowed build at
  `dist\Bu D3eij\Bu D3eij.exe` (~250 MB). All 8 conversions verified running
  inside the frozen exe; GUI launches cleanly.
- Added `CLAUDE.md` + this file.

### 2026-06-06 — Branding
- Window icon + exe icon from `AppLogo.png` (generated multi-size `AppLogo.ico`).
- In-app logo (`DashboardLogo.png`) in the sidebar header and on the Home screen.
- `resource_path()` so assets resolve in dev and inside the exe; both images
  bundled into the exe via `--icon` + `--add-data`. Verified from source; exe rebuilt.

### 2026-06-06 — UI polish (layout & UX)
- Section headers with subtitles; consistent 24px padding and rounded "cards".
- Converter: drop zone shows the app icon and, once a file is picked, its name +
  category + size ("Image · 186 B · click to choose another"); grouped controls
  card with a `CONVERT FROM → CONVERT TO` layout; progress bar only appears while
  converting; status uses ✓ / ✕ icons.
- Home: logo + tagline, **Convert a File** / **Batch Convert** quick actions, and a
  "Supported formats" card.
- Tools (was a placeholder): live FFmpeg status, history count, version, and
  "Open history folder" / "Reveal last output" buttons.
- Batch view restyled to match; drag-over highlights the drop border; drop zones
  show a pointer cursor. Window default 1000x680. Verified via screenshots.

### 2026-06-06 — UI redesign (logo palette)
- Extracted the palette from `AppLogo.png` (brand red `#E11414`/`#B4000C`,
  highlight `#F01818`) and built `bud3eij_theme.json` (recolored CustomTkinter
  theme). Default appearance is now **Dark**.
- Restyled: logo sidebar with red active-nav highlight, red section titles,
  red-bordered drop zones with drag-hover highlight, neutral dropdowns with red
  accents, bold red "Convert Now" CTA, palette-based success/error status.
- Verified visually (screenshots of all four views) and rebuilt the exe with
  the theme bundled.

### 2026-06-06 — Converter controls + shortcut
- Converter: **Choose Export Path** button (per-conversion output folder) and
  **Clear** button (reset the form). `convert_file()` gained an `out_dir` arg
  (defaults to next-to-source); single conversions honour `self.export_dir`.
- Created a **Desktop shortcut** to `dist\Bu D3eij\Bu D3eij.exe`.

## Backlog / next steps
- [ ] Optional: bundle the Marquee model(s) into the exe (`--add-data` +
      `U2NET_HOME`) so the Background Remover works fully offline on a fresh
      machine; currently each tier's `.onnx` (u2netp / isnet-general-use /
      birefnet-general) is downloaded/cached by rembg on first use, like ffmpeg.
- [ ] Optional: Marquee polish — live before/after preview thumbnail; a dedicated
      "wand"/"scissors" nav icon via `tools/fetch_icons.py`; more rembg models /
      alpha-matting toggle.
- [ ] Optional: Windows "Send to → Convert" shell entry.
- [ ] Make **Tools** tab functional (e.g. ffmpeg status check, open output folder,
      appearance settings).
- [ ] Flesh out the **Home** screen (currently a simple placeholder).
- [ ] Add an **in-repo test script** (`tests/`) so verification is reproducible
      instead of ad-hoc temp scripts.
- [ ] Optional: per-file progress for large A/V; quality/bitrate options.
- [ ] Optional: bundle ffmpeg into the exe if it ever needs to run on a PC
      without ffmpeg installed (adds ~170 MB).

## Decisions & constraints
- **Python 3.11** (not 3.14) for guaranteed wheels of the native-extension deps.
- **High-fidelity docs:** pdf2docx + docx2pdf (Word); reportlab is the text-only
  DOCX→PDF fallback when Word/COM is unavailable.
- **Exe:** one-folder (faster, more reliable for this dep set) and **windowed**;
  ffmpeg is **not** bundled (relies on system install — app is for personal use).
- Output is always saved next to the source; existing files are never
  overwritten (numbered copies instead).
- See `CLAUDE.md` for environment paths, commands, and gotchas.
