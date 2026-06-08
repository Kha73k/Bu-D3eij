# CLAUDE.md — Bu D3eij

Guidance for working on this project across sessions. Keep this file and
`PROGRESS.md` up to date when things change.

## What this is
Bu D3eij is a Windows desktop **file converter** (documents, images, audio/video)
built with **CustomTkinter** + **tkinterdnd2** drag-and-drop. Single-file app
(`app.py`): conversion logic is plain module-level functions (importable and
testable without the GUI); the `App` class is a thin GUI layer on top.

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

# Install / update deps
.\.venv\Scripts\python -m pip install -r requirements.txt

# Build the standalone one-folder exe -> dist\Bu D3eij\Bu D3eij.exe
.\.venv\Scripts\pyinstaller --noconfirm --windowed --name "Bu D3eij" `
  --icon "AppLogo.ico" `
  --add-data "AppLogo.ico;." --add-data "DashboardLogo.png;." `
  --add-data "bud3eij_theme.json;." `
  --collect-all customtkinter --collect-all tkinterdnd2 `
  --collect-all pptx --collect-all mammoth --collect-all markdownify --collect-all bs4 `
  --collect-data pdfminer --collect-data pdfplumber `
  --collect-data docx --collect-data pdf2docx --collect-data reportlab `
  --collect-submodules pymupdf4llm --hidden-import tabulate `
  --collect-all yt_dlp `
  --exclude-module pymupdf.layout --exclude-module onnxruntime --exclude-module rapidocr_onnxruntime `
  --hidden-import win32timezone app.py
```

## Verifying changes (no formal test suite in repo yet)
- **Conversions (headless):** `import app`, generate samples (PIL image,
  reportlab PDF, python-docx DOCX, `wave` WAV, ffmpeg for MP4) in a temp dir,
  call `app.convert_file(src, target)`, and assert the output exists/opens.
  Run with the venv python; prepend the ffmpeg bin to PATH first.
- **GUI:** construct `app.App()`, call `update()`, switch frames via
  `show_frame(...)`, then `after(300, destroy); mainloop()`.
- **Frozen exe:** run `dist\Bu D3eij\Bu D3eij.exe --convert <file> <fmt>` and
  check the output file (proves bundled modules/data work, not just startup).

## Architecture / key code (`app.py`)
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
- **GUI:** sidebar nav (Home, Converter, Recent, Batch Convert, YouTube, Tools)
  raising stacked frames — all functional. The sidebar foot has a **sun/moon
  appearance toggle** (`_toggle_appearance`, `SUN_GLYPH`/`MOON_GLYPH` in
  "Segoe UI Symbol"), replacing the old Light/Dark/System dropdown. Each
  `_build_*` view starts with `_section_header(title, subtitle)`; controls sit in
  rounded "cards"
  (`fg_color=("#DFD9DA","#2B2629")`). Conversions run on a worker
  `threading.Thread`; UI updates are marshalled back with `self.after(0, ...)`
  (Tkinter is not thread-safe). Drop zones are built with an inner frame of
  labels (`drop_primary`/`drop_secondary`); `_register_drop(zone, widgets, ...)`
  wires DnD + click + drag-hover border on every child widget.
- **Avoiding text overflow:** a fixed-size container (`grid_propagate(False)`)
  does NOT clip its children, so an unbounded label (e.g. a long filename) spills
  past the border. Use `_make_labels_wrap(container, labels)` (binds
  `<Configure>` → responsive `wraplength`) for wrapping text, or `_ellipsize()`
  for single-line text like the export path. Set `wraplength` on any free-text
  label you add.
- **Recent/history:** persisted to `%LOCALAPPDATA%\Bu D3eij\history.json`
  (`load_history`/`save_history`, cap `MAX_HISTORY`). `add_history()` mutates the
  shared `self.history`, so off the main thread it must be called via
  `self.after(0, self.add_history, ...)` (both the single and batch paths do).
- **CLI:** `_run_cli()` / `main()` — `--convert FILE FORMAT` and
  `--download URL FORMAT` (mp3/mp4, saves to cwd) run headless; no flags → GUI.
  Both double as the way to smoke-test the frozen exe.
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
app.py            GUI + converters + CLI (single source file)
requirements.txt  runtime deps (pyinstaller is dev-only, installed separately)
README.md         user-facing docs
CLAUDE.md         this file
PROGRESS.md       running work log
AppLogo.png       source square logo -> exe/window icon
AppLogo.ico       generated multi-size icon (from AppLogo.png)
DashboardLogo.png in-app branding (sidebar header + Home banner)
bud3eij_theme.json logo-derived red CustomTkinter theme (must be bundled)
Bu D3eij.spec     PyInstaller spec (regenerated by the build command)
.venv\            Python 3.11 environment
dist\Bu D3eij\    built standalone app (~250 MB; keep the folder together)
```
`build\` (PyInstaller intermediates) is disposable and not kept.
