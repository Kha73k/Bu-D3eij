# PROGRESS — Bu D3eij

Running log of what's done and what's next. Update at the end of each session.

_Last updated: 2026-06-08_

## Status: working app + standalone exe — v1.4.5

Core app, all required conversions, Recent history, Batch Convert, and a
packaged one-folder exe are complete and verified. v1.1 = PowerPoint + Markdown;
v1.2 = bug fixes; v1.3 = YouTube downloads + sun/moon toggle; v1.4 = visual
redesign (file-type icons, hero Home, table Recent); v1.4.5 = animated
"Convert Now" button.

The project is now a **private GitHub repo**: https://github.com/Kha73k/Bu-D3eij
(branch `main`; v1.4 developed on `redesign-1.4`). Commit/push as work lands.

## Completed

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
