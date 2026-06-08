# Bu D3eij — Patch Notes

All notable changes to Bu D3eij are documented here.
This project follows a simple `MAJOR.MINOR` versioning scheme.

---

## v1.2 — 2026-06-08

Bug-fix and polish release — cleanup pass before the next round of features.

### Fixed
- **Long file names no longer overflow the Converter drop zone.** The file-name
  and hint text now wrap to the drop zone's width (and adapt as the window is
  resized), so they stay neatly inside the border.
- **Long output-folder paths no longer overflow the controls card** — the
  "Output:" path is shortened with a middle ellipsis (the full path is still
  used for saving).
- **Batch Convert history is now updated safely.** History writes from batch
  conversions are marshalled to the UI thread, fixing a rare race that could
  occur while the Recent list refreshed.
- **PowerPoint → Markdown tables are no longer broken by special characters.**
  Pipe (`|`) characters in slide-table cells are escaped, and slide bullet
  levels are handled defensively.

### Changed
- Home screen tagline now mentions presentations (PPTX) and Markdown output.

---

## v1.1 — 2026-06-08

Adds PowerPoint support and Markdown as an output format.

### New conversions
- **PowerPoint (.pptx)** is now a supported input:
  - PPTX → **Markdown** — one section per slide (titles as headings, body text as
    bullets, slide tables as Markdown tables, speaker notes included).
  - PPTX → **PDF** — high-fidelity via Microsoft PowerPoint, with a text-only
    fallback when PowerPoint isn't installed.
  - PPTX → **TXT** — plain-text extraction of all slide text.
- **Markdown (.md)** output for documents:
  - PDF → **MD** — structure-aware (headings, bold, lists, tables) via pymupdf4llm.
  - DOCX → **MD** — preserves headings, bold/italic, lists, and tables.

### Notes
- Markdown is an **output-only** format in this release.
- PowerPoint support is for modern **`.pptx`** only — legacy `.ppt` and
  slide-to-image export are not supported.
- PPTX → PDF uses Microsoft PowerPoint when available and otherwise falls back to
  a text-only PDF (so slide visuals/layout may be simplified without PowerPoint).
- Audio/video conversions still require FFmpeg on PATH (unchanged from 1.0).

---

## v1.0 — 2026-06-08

First public release. Bu D3eij is a Windows desktop file converter for
documents, images, and audio/video, with drag-and-drop, batch processing, and a
red logo-themed interface.

### Conversions
- **Images** — convert freely between JPG, JPEG, PNG, WEBP, BMP, GIF, and TIFF
  (Pillow). Alpha is flattened to white for formats without transparency.
- **Documents**
  - PDF → DOCX (pdf2docx) and PDF → TXT (pdfplumber).
  - DOCX → PDF (high-fidelity via Microsoft Word/COM, with a reportlab text-only
    fallback when Word is unavailable) and DOCX → TXT (python-docx).
- **Audio / Video** — MP4 → MP3, MP4 → WAV, MP3 → WAV, and WAV → MP3 (ffmpeg).

### Interface
- Sidebar navigation: **Home**, **Converter**, **Recent**, **Batch Convert**,
  and **Tools** — all functional.
- Drag-and-drop or click-to-browse upload zones with auto-detection of the input
  format; the "Convert to" list only shows valid targets for the dropped file.
- Converter shows the picked file's name, category, and size, and a clear
  `CONVERT FROM → CONVERT TO` layout.
- **Choose Export Path** to pick a per-conversion output folder, plus a
  **Clear** button to reset the form.
- Threaded conversions keep the UI responsive, with a progress bar and ✓ / ✕
  status messages.
- **Recent** tab: persistent conversion history with per-entry Open / Open Folder
  buttons and Clear, stored in `%LOCALAPPDATA%\Bu D3eij\history.json`.
- **Batch Convert**: queue multiple files and convert them in one pass.
- **Tools** tab: live FFmpeg status, history count, app version, and shortcuts to
  open the history folder or reveal the last output.

### Design
- Logo-derived red theme (`bud3eij_theme.json`), dark appearance by default.
- App and window icon from `AppLogo.ico`; in-app branding from `DashboardLogo.png`.

### Other
- **Headless CLI**: `Bu D3eij.exe --convert FILE FORMAT` (also works from source)
  for scripted, GUI-free conversions.
- Output is always saved next to the source (or your chosen export folder) and
  **never overwrites** existing files — numbered copies are created instead.
- Distributed as a standalone one-folder Windows build (no Python install
  required); FFmpeg uses the system installation.

### Known limitations
- FFmpeg is **not** bundled — MP4/MP3/WAV conversions require FFmpeg installed
  and on PATH.
- No per-file progress or quality/bitrate options for large audio/video files yet.
