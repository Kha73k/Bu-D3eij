# Bu D3eij — Desktop File Converter

A simple, clean Windows desktop app for converting documents, images, and
audio/video files. Built with Python + [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
and native drag-and-drop via [tkinterdnd2](https://github.com/pmgagne/tkinterdnd2).

Drag a file in, pick a target format, click **Convert Now** — the output is
saved right next to the original.

## Features

- Drag & drop (or click to browse) a file onto the upload zone
- Auto-detects the input format and only offers compatible output formats
- Single-file **Converter** and a multi-file **Batch Convert** view
- **YouTube** tab: paste a link and download it as MP4 (video) or MP3 (audio)
- **Recent** tab: persistent history of your conversions with one-click *Open* / *Folder*
- Progress indicator with clear success / error messages
- Logo-derived red theme with a sun/moon toggle to switch Light / Dark
- Optional headless mode: `python app.py --convert photo.png jpg`

### Supported conversions

| Category      | Conversions |
|---------------|-------------|
| Documents     | PDF ↔ DOCX, PDF → TXT, PDF → MD, DOCX → TXT, DOCX → PDF, DOCX → MD |
| Presentations | PPTX → MD, PPTX → PDF, PPTX → TXT |
| Images        | JPG ↔ PNG, PNG/JPG → WEBP, and swaps between JPG, PNG, WEBP, BMP, GIF, TIFF |
| Audio/Video   | MP4 → MP3, MP4 → WAV, MP3 → WAV, WAV → MP3 |
| YouTube       | URL → MP4 (best video+audio), URL → MP3 (192 kbps) |

> Markdown (`.md`) is an output format only. PowerPoint support is for modern
> `.pptx` files (legacy `.ppt` is not supported). Downloading copyrighted
> content may breach YouTube's Terms of Service — download only what you may.

## Requirements

- **Python 3.11** — install with `winget install Python.Python.3.11`
  (or from [python.org](https://www.python.org/downloads/release/python-3119/)).
- **ffmpeg** — required for the audio/video conversions **and YouTube downloads**.
- **Microsoft Word** *(optional)* — enables high-fidelity **DOCX → PDF**.
  Without Word, the app automatically falls back to a text-only PDF.
- **Microsoft PowerPoint** *(optional)* — enables high-fidelity **PPTX → PDF**.
  Without PowerPoint, the app automatically falls back to a text-only PDF.

## Install

From the project folder (`Bu D3eij`):

```powershell
# 1. Create and activate a virtual environment (Python 3.11)
py -3.11 -m venv .venv
.\.venv\Scripts\activate

# 2. Install the Python dependencies
pip install -r requirements.txt
```

### Install ffmpeg

Easiest (Windows Package Manager):

```powershell
winget install Gyan.FFmpeg
```

Or download a build manually from
[gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) or
[ffmpeg.org/download.html](https://ffmpeg.org/download.html), then add its
`bin` folder to your `PATH`.

Verify it is on your PATH (open a **new** terminal after installing):

```powershell
ffmpeg -version
```

## Run

With the virtual environment active:

```powershell
python app.py
```

### Headless / command-line

Convert a single file, or download a video, without opening the window:

```powershell
python app.py --convert "C:\path\to\photo.png" jpg
python app.py --download "https://www.youtube.com/watch?v=…" mp3   # saves to the current folder
```

## Standalone .exe (no Python needed)

A pre-built one-folder app lives in `dist\Bu D3eij\`. Run
`dist\Bu D3eij\Bu D3eij.exe` (make a desktop shortcut to it if you like).
Keep the whole `Bu D3eij` folder together — zip it if you want to move it.
ffmpeg still needs to be installed for audio/video conversions and YouTube downloads.

To rebuild it yourself (with the venv active):

```powershell
pip install pyinstaller
pyinstaller --noconfirm --windowed --name "Bu D3eij" `
  --icon "AppLogo.ico" `
  --add-data "AppLogo.ico;." --add-data "DashboardLogo.png;." `
  --add-data "bud3eij_theme.json;." --add-data "assets;assets" `
  --collect-all customtkinter --collect-all tkinterdnd2 `
  --collect-all pptx --collect-all mammoth --collect-all markdownify --collect-all bs4 `
  --collect-data pdfminer --collect-data pdfplumber `
  --collect-data docx --collect-data pdf2docx --collect-data reportlab `
  --collect-submodules pymupdf4llm --hidden-import tabulate `
  --collect-all yt_dlp `
  --exclude-module pymupdf.layout --exclude-module onnxruntime --exclude-module rapidocr_onnxruntime `
  --hidden-import win32timezone app.py
```

The icon is generated from `AppLogo.png` once with:
`python -c "from PIL import Image; Image.open('AppLogo.png').save('AppLogo.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"`

## Usage

1. Open the **Converter** view (selected by default).
2. Drag a file onto the upload zone, or click it to browse.
3. *Convert from* fills in automatically; choose a format in *Convert to*.
4. Click **Convert Now**. The converted file is saved beside the source
   (e.g. `photo.png` → `photo.jpg`). Existing files are never overwritten —
   a numbered copy like `photo (1).jpg` is created instead.

Use **Choose Export Path** to send output to a specific folder instead of next
to the source, and **Clear** to reset the form for the next file.

For **Batch Convert**, drop several files, pick a single target format
(only formats valid for *every* selected file are offered), and click
**Convert All**.

The **Recent** tab lists past conversions (stored in
`%LOCALAPPDATA%\Bu D3eij\history.json`): use **Open** to launch a result,
**Folder** to reveal it in Explorer, or **Clear history** to empty the list.

## Notes & limitations

- **Audio/video** conversions need ffmpeg installed and on your PATH; if it
  is missing the app shows a clear message instead of failing silently.
- **DOCX → PDF** gives the best results when Microsoft Word is installed
  (via COM); otherwise it produces a text-only PDF with `reportlab`.
- **PPTX → PDF** gives the best results when Microsoft PowerPoint is installed
  (via COM); otherwise it produces a text-only PDF with `reportlab`.
- **PDF → DOCX** uses `pdf2docx` for layout-aware conversion. Very complex
  PDFs may still differ from the original.
- **Markdown output** (`PDF/DOCX/PPTX → MD`) is structure-aware
  (headings, bold, lists, tables) but is plain Markdown — images are not
  embedded, and very complex layouts may simplify.
- Image conversions to formats without transparency (JPG, BMP) flatten any
  alpha channel to RGB. Animated GIFs keep their animation when converting to
  WEBP/TIFF/PNG; converting to a still format uses the first frame.

## Tech stack

Python 3.11 · customtkinter · tkinterdnd2 · Pillow · python-docx ·
pdfplumber · reportlab · pdf2docx · python-pptx ·
pymupdf4llm · mammoth · markdownify · yt-dlp · ffmpeg-python
