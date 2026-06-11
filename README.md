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
- **Marquee** tab (image editing): **Background Remover** (transparent PNG, three
  quality tiers — the Omega tier runs BiRefNet-HR on the GPU for hair-strand
  precision) and **Image Upscaler** (UltraSharp V2 on the GPU, to exact
  1080p / 2K / 4K)
- **Vanguard** tab (AI text tools): **AI Text Detector** (estimate how likely a
  text is AI-generated, with flagged passages), **Text Extraction** (offline OCR
  of any screenshot/photo, with copy-to-clipboard), and **What's The Font**
  (closest Google-Font matches for the lettering in an image)
- **Sonara** tab (audio tools): **Audio Stem Splitter** — split any song into
  **Vocals / Drums / Bass / Other** (Demucs `htdemucs_ft`, GPU-accelerated),
  then mix them live in the built-in player (play/pause, seek, per-stem
  mute/solo/volume) and save just the stems you want (WAV or MP3)
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

# 2. Install PyTorch first (CUDA build for NVIDIA GPUs — strongly recommended
#    for the Sonara stem splitter; without it a CPU build is used, ~20x slower)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126

# 3. Install the rest of the Python dependencies
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
python app.py --remove-bg "C:\path\photo.png"        # transparent PNG next to the source
python app.py --upscale "C:\path\small.png" 2K       # 1080p / 2K / 4K
python app.py --detect "C:\path\essay.docx"          # AI-likelihood estimate
python app.py --extract-text "C:\path\shot.png" Max  # OCR (Fast/Max): prints the text
python app.py --identify-font "C:\path\text.png"     # top-5 Google Font matches
python app.py --split-stems "C:\path\song.mp3"       # 4 stem WAVs next to the song
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
  --collect-all rembg --collect-all onnxruntime --copy-metadata pymatting --copy-metadata rembg `
  --collect-all tokenizers --collect-all rapidocr `
  --collect-all demucs --collect-all torch --collect-all torchaudio `
  --collect-all sounddevice --copy-metadata torch `
  --collect-all spandrel --collect-all transformers --collect-all timm `
  --collect-all kornia --collect-all torchvision `
  --exclude-module pymupdf.layout --exclude-module rapidocr_onnxruntime `
  --hidden-import win32timezone app.py
```

> Note: bundling PyTorch (CUDA) makes the one-folder build ~6 GB.

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
- **AI detection is an estimate, not proof** — detectors can mislabel edited,
  translated, or non-native-English human writing. Never treat the score as an
  accusation.
- **Font identification is a closest-match estimate** against ~3,500 Google
  Fonts — commercial fonts are shown as their nearest Google lookalike. A tight
  crop of large, clear text gives the best results. The ~64 MB font model
  downloads once on first use. **Text Extraction** (OCR) works fully offline
  out of the box; its **Fast** tier also reads Chinese, while **Max** is tuned
  for English (proper word spacing, catches faint/small lines) and fetches a
  small model once on first use. Nothing uses an online API — no accounts,
  no charges, no usage limits.
- **Stem splitting** is GPU-accelerated on NVIDIA cards (seconds per song);
  on CPU it works but takes ~15–25 minutes per song. The Demucs model
  (~320 MB) downloads once on first use. Stem playback mixes in real time —
  mute/solo/volume changes are heard instantly.

## Tech stack

Python 3.11 · customtkinter · tkinterdnd2 · Pillow · python-docx ·
pdfplumber · reportlab · pdf2docx · python-pptx ·
pymupdf4llm · mammoth · markdownify · yt-dlp · ffmpeg-python ·
rembg · onnxruntime (Real-ESRGAN, DeBERTa detector, font classifier) ·
rapidocr · tokenizers · demucs + PyTorch CUDA (stem splitter) · sounddevice ·
spandrel (UltraSharp V2 upscaler) · transformers/timm/kornia (BiRefNet-HR)
