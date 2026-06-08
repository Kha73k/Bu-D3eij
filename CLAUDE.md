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
- **Microsoft Word is installed**, so DOCX→PDF uses the high-fidelity
  `docx2pdf` (Word/COM) path; `reportlab` is the text-only fallback.
- **Microsoft PowerPoint** (if installed) is used for PPTX→PDF via COM
  (`win32com.client` + `SaveAs(..., 32)`); `reportlab` is the text-only fallback.

## Commands
```powershell
# Run the GUI
.\.venv\Scripts\python app.py

# Headless conversion (also works on the exe)
.\.venv\Scripts\python app.py --convert "C:\path\photo.png" jpg

# Headless background removal -> transparent PNG (also works on the exe)
.\.venv\Scripts\python app.py --remove-bg "C:\path\photo.png"

# Install / update deps
.\.venv\Scripts\python -m pip install -r requirements.txt

# Build the standalone one-folder exe -> dist\Bu D3eij\Bu D3eij.exe
.\.venv\Scripts\pyinstaller --noconfirm --windowed --name "Bu D3eij" `
  --icon "AppLogo.ico" `
  --add-data "AppLogo.ico;." --add-data "DashboardLogo.png;." `
  --add-data "bud3eij_theme.json;." --add-data "assets;assets" `
  --collect-all customtkinter --collect-all tkinterdnd2 `
  --collect-all pptx --collect-all mammoth --collect-all markdownify --collect-all bs4 `
  --collect-data pdfminer --collect-data pdfplumber `
  --collect-data docx --collect-data pdf2docx --collect-data reportlab `
  --collect-submodules pymupdf4llm --hidden-import tabulate `
  --collect-all yt_dlp `
  --collect-all rembg --collect-all onnxruntime --copy-metadata pymatting --copy-metadata rembg `
  --exclude-module pymupdf.layout --exclude-module rapidocr_onnxruntime `
  --hidden-import win32timezone app.py
```

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

## Verifying changes (no formal test suite in repo yet)
- **Conversions (headless):** `import app`, generate samples (PIL image,
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
`BG_MODELS`). `app.py` holds the GUI (`App`, `GradientButton`, palette/icons),
the Recent-history store (`load_history`/`save_history`), the CLI (`_run_cli`),
and `main()`, and it re-exports the package functions (so `app.convert_file`,
`app.remove_background`, etc. still resolve). Converters still **import heavy deps
lazily** inside each function — keep that. The bullets below describe behaviour and
still apply; only the file a function lives in changed.
- **Format model:** `IMAGE_EXTS`/`DOC_EXTS`/`PRESENTATION_EXTS`/`AV_EXTS`, and
  `CONVERSIONS` (input ext → list of valid targets). `md` is an **output-only**
  format (it has no `CONVERSIONS` key). `compatible_targets()` drives the UI's
  "Convert to" options. Add new conversions here AND in the `convert_file`
  dispatch.
- **Dispatch:** `convert_file(src, target)` validates against `CONVERSIONS`,
  computes a non-clobbering output path with `unique_path()` (saves next to the
  source; never overwrites — adds ` (n)`), and routes to the right converter.
- **Converters:** `convert_image` (Pillow), `pdf_to_txt` (pdfplumber),
  `pdf_to_md` (pymupdf4llm, pdfplumber text fallback), `pdf_to_docx` (pdf2docx),
  `docx_to_txt` (python-docx), `docx_to_md` (mammoth→HTML + markdownify→MD),
  `docx_to_pdf` (`_docx_to_pdf_word` → `_docx_to_pdf_reportlab` fallback),
  `pptx_to_md`/`pptx_to_txt` (python-pptx), `pptx_to_pdf`
  (`_pptx_to_pdf_powerpoint` COM → `_pptx_to_pdf_reportlab` fallback),
  `convert_av` (ffmpeg-python). Each **imports its heavy deps lazily** inside
  the function for fast startup — keep this pattern.
- **YouTube download:** `download_youtube(url, fmt, out_dir, progress_hook)`
  (yt-dlp, lazy import) — `fmt` is `mp3` (FFmpegExtractAudio 192 kbps) or `mp4`
  (`bestvideo+bestaudio`, `merge_output_format=mp4`). Needs ffmpeg (sets
  `ffmpeg_location`). Not part of `convert_file` (it has no source file); the
  GUI **YouTube** page (`_build_youtube` + `on_youtube_download`/`_youtube_worker`/
  `_yt_hook`) and the `--download URL FORMAT` CLI both call it. Output folder is
  asked per-download (filedialog); results go through `add_history`.
- **Marquee → Background Remover (v2.0, model selector in v2.1):**
  `remove_background(src, out_path=None, model="isnet-general-use")` (rembg, lazy
  import) opens the image, runs the chosen rembg model, and saves a transparent
  **PNG** (output is always PNG — the only listed image format that keeps alpha).
  Like `download_youtube` it sits **outside** `convert_file`/`CONVERSIONS` (no
  target-format choice). Sessions are cached per model in the module-level dict
  `_REMBG_SESSIONS` (each model loaded once). **v2.1** added a **QUALITY** tier
  selector (`CTkSegmentedButton`) mapped by `BG_MODELS` (top of GUI section):
  **Flash** = `u2netp` (fastest, ~4.7 MB), **Mid** (default `DEFAULT_BG_TIER`) =
  `isnet-general-use` (balanced), **Omega** = `birefnet-general` (max precision,
  big/slow). Each model downloads its own `.onnx` into `~/.u2net/` on first use,
  then caches — **all three ride on the existing `--collect-all rembg` bundle, so
  the build command does NOT change** (rebuild the exe only to embed new `app.py`).
  The GUI **Marquee** page (`_build_marquee` + `_on_mq_model_change`/
  `on_marquee_drop`/`browse_marquee`/`set_marquee_file`/`on_marquee_remove`/
  `_marquee_worker`/`_marquee_done`) validates the drop is an image (`IMAGE_EXTS`),
  asks the output path per-run via `asksaveasfilename` (defaults `<stem>_no-bg.png`),
  shows an **indeterminate** progress bar while the worker thread runs (rembg has no
  progress callback), and records the result via `add_history`. Nav icon reuses the
  bundled `assets/ui/sparkles.png`.
- **GUI:** sidebar nav (Home, Converter, Recent, Batch Convert, YouTube,
  Marquee, Tools) raising stacked frames — all functional. The sidebar foot has a **sun/moon
  appearance toggle** (`_toggle_appearance`, `SUN_GLYPH`/`MOON_GLYPH` in
  "Segoe UI Symbol"), replacing the old Light/Dark/System dropdown. Each
  `_build_*` view starts with `_section_header(title, subtitle)`; controls sit in
  rounded "cards"
  (`fg_color=("#DFD9DA","#2B2629")`). Conversions run on a worker
  `threading.Thread`; UI updates are marshalled back with `self.after(0, ...)`
  (Tkinter is not thread-safe). Drop zones are built with an inner frame of
  labels (`drop_primary`/`drop_secondary`); `_register_drop(zone, widgets, ...)`
  wires DnD + click + drag-hover border on every child widget.
- **Animated Convert button (1.4.5):** the Converter's "Convert Now" is a custom
  `GradientButton(ctk.CTkFrame)` (defined just above `class App`), not a
  `CTkButton`. CustomTkinter has no CSS, so the whole button is **composed in
  Pillow** (red gradient + gloss + gaussian shine band + blurred glow + text +
  white-tinted `assets/ui/sparkles.png`) and animated by swapping a `CTkImage`
  on an inner label each tick. It's a drop-in: supports `grid`, `command`,
  `configure(state="normal"|"disabled")`, plus `start_busy()`/`stop_busy()`
  (the convert flow calls these in `on_convert_click`/`_convert_done`). States:
  disabled (flat grey), idle (sweeping shine + breathing glow), hover (brighter
  + glow bloom), press (dim), busy (double-shine flow + "Converting…" dots).
  Static layers cache by `(w, h, enabled)`; the loop only runs while **mapped**
  (pauses on `<Unmap>`, cancelled on `<Destroy>`) so it's idle-cheap. Render is
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
- **Frame stacking gotchas (cost real time in 1.4):** `show_frame` uses
  **grid/grid_remove**, NOT `tkraise` — a `CTkScrollableFrame` (Home) will not
  raise above plain sibling frames sharing the grid cell. A top-level page frame
  must be **opaque** (a transparent one shows the stacked sibling behind it). And
  an **empty `CTkFrame` keeps its default 200×200** — only build a sub-frame once
  it has children, or it stretches its row (hit on failed Recent rows).
- **Recent/history:** persisted to `%LOCALAPPDATA%\Bu D3eij\history.json`
  (`load_history`/`save_history`, cap `MAX_HISTORY`). `add_history()` mutates the
  shared `self.history`, so off the main thread it must be called via
  `self.after(0, self.add_history, ...)` (both the single and batch paths do).
- **CLI:** `_run_cli()` / `main()` — `--convert FILE FORMAT`,
  `--download URL FORMAT` (mp3/mp4, saves to cwd), and `--remove-bg FILE`
  (transparent PNG next to the source) run headless; no flags → GUI. All three
  double as the way to smoke-test the frozen exe.
- **Branding/assets:** `resource_path()` resolves bundled files in dev and in
  the frozen exe (`sys._MEIPASS`). Window + exe icon = `AppLogo.ico`; in-app
  logo (sidebar header + Home banner) = `DashboardLogo.png` loaded via
  `_load_logo()` → `CTkImage`. Both must be passed to PyInstaller (`--icon` +
  `--add-data`) or they won't appear in the exe.
- **Theme:** logo-derived red palette in `bud3eij_theme.json` (a recolored
  CustomTkinter theme) loaded via `set_default_color_theme(resource_path(...))`;
  appearance defaults to **Dark**. Palette constants (`RED`, `RED_HOVER`,
  `SIDEBAR_FG`, `DROP_BORDER`, `SUCCESS`, `ERROR`) sit at the top of the GUI
  section for targeted accents (active nav, drop-zone border + drag hover,
  section titles). The theme file must be bundled (`--add-data`). Regenerate
  the palette from the logo with `extract_palette` approach if the logo changes.

## Conventions & gotchas
- Match the existing style: type hints, lazy converter imports, small focused
  methods, `# noqa: BLE001` on the broad `except` blocks that intentionally
  catch-all (fallbacks / UI safety).
- **CTk + tkinterdnd2:** the root subclasses both `ctk.CTk` and
  `TkinterDnD.DnDWrapper` and calls `TkinterDnD._require(self)` in `__init__`.
  Drop targets are registered on widgets via `_register_drop`; dropped paths
  are parsed with `self.tk.splitlist(event.data)` (handles `{spaced paths}`).
- **docx2pdf** drives Word via COM → must `pythoncom.CoInitialize()` on the
  worker thread (handled in `_docx_to_pdf_word`). **PPTX→PDF** does the same with
  PowerPoint COM in `_pptx_to_pdf_powerpoint` (CoInitialize, `Presentations.Open`
  with absolute paths + `WithWindow=False`, `SaveAs(out, 32)`, then `Quit`).
- **Markdown converters:** `pdf_to_md` uses pymupdf4llm (rides on the bundled
  PyMuPDF) and falls back to pdfplumber text; `docx_to_md` goes DOCX→HTML
  (mammoth) → MD (markdownify); `pptx_to_md` builds MD by hand from python-pptx
  (`## ` per slide, bullets by paragraph level, tables via `_pptx_table_to_md`,
  speaker notes). `md` is output-only — no `md` key in `CONVERSIONS`.
- **ffmpeg-python:** use real ffmpeg flag names as kwargs (e.g. `{"b:a":"192k"}`,
  not `audio_bitrate`); `vn=None` to drop video when extracting audio.
- **Images:** flatten alpha to RGB for formats without transparency
  (jpg/jpeg/bmp/gif).
- **PyInstaller:** contrib hooks already cover pymupdf/fitz, docx2pdf,
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
  background.py   remove_background + BG_MODELS (Marquee)
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
assets\LICENSES.md icon attributions; regenerate via tools\fetch_icons.py (dev)
tools\fetch_icons.py  dev-only icon generator (Iconify -> PNG; not bundled)
Bu D3eij.spec     PyInstaller spec (regenerated by the build command)
.venv\            Python 3.11 environment
dist\Bu D3eij\    built standalone app (~250 MB; keep the folder together)
```
`build\` (PyInstaller intermediates) is disposable and not kept.
