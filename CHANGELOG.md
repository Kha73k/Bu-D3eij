# Bu D3eij — Patch Notes

All notable changes to Bu D3eij are documented here.
This project follows a simple `MAJOR.MINOR.PATCH` versioning scheme.

---

## v4.3.2 — 2026-06-14

### Fixed
- **Resizing the window is smooth on every tab now**, including content-heavy
  ones (Marquee, Nexus). Those pages were doing a full ~50 ms re-layout on every
  resize pixel; the page now re-flows to the new width **once, the moment you let
  go of the edge**, so dragging the edge stays fluid (the content snaps to fit on
  release). Light tabs are unchanged. (Live content re-flow during the drag isn't
  feasible without the per-frame redraw cost that caused the lag — this keeps the
  drag itself smooth.)

---

## v4.3.1 — 2026-06-14

### Fixed
- **Window dragging is smooth again in the standalone .exe.** The app now sets
  **per-monitor-v2 DPI awareness** at startup (before the UI loads). The previous
  exe ran at the older per-monitor-v1 awareness, under which Windows redraws the
  window laggily while it's dragged — most noticeable in the .exe, which (unlike
  running from Python) has no manifest of its own to set this. No visual change.

---

## v4.3 — 2026-06-14

Two new **Marquee** image tools — same no-account, fully-offline, GPU-friendly
rule as the rest of the app.

### Added
- **Image → Prompt.** Drop in an image and get a detailed text-to-image prompt
  back — the subject, setting, art style, lighting, colour palette and
  composition — ready to paste into an image generator. Runs **Qwen2-VL-2B**
  on your GPU, fully offline; pick **Concise** (a one-liner) or **Detailed**
  (a full prompt) and copy the result to the clipboard. The ~4.4 GB model
  downloads once on first use, then it's offline forever.
- **ASCII Art.** Turn any image into ASCII — choose the output width, optionally
  invert the shading, and (for the PNG export) colour each character from the
  source. Preview it, copy it, or save it as a `.txt` or a rendered `.png`.
  Instant and 100% offline — no model, no download.
- Both ship as headless flags too: `--image-prompt FILE [Concise|Detailed]`
  and `--ascii FILE [WIDTH]`.

### Notes
- The obvious smaller captioner (Microsoft's Florence-2) was evaluated and
  skipped: its bundled model code is incompatible with the app's current
  transformers version. Qwen2-VL is a first-class transformers model (no remote
  code), is ungated and Apache-licensed, and produces richer, instructable
  prompts — and it fits comfortably in 8 GB.

---

## v4.1 — 2026-06-11

The Marquee image tools get the same GPU treatment as Sonara — best-in-class
local models, measured before being adopted. Still no accounts, no APIs,
no limits.

### Changed
- **Image Upscaler rebuilt on UltraSharp V2.** Both tiers were replaced after a
  measured comparison (the new **Fast** tier produces cleaner detail than the
  old *Max* did, in a fraction of the time):
  - **Fast** = UltraSharp V2 Lite — sharp, artifact-free, near-instant on GPU
  - **Max** = UltraSharp V2 — the overall quality winner in our tests
  Upscales now run on your NVIDIA GPU (automatic CPU fallback), so Max → 4K
  takes seconds instead of ~10 minutes.
- **Background Remover's Omega tier upgraded to BiRefNet-HR** — the current
  open state of the art for cut-out quality, running on the GPU. The visible
  difference: fine hair strands and wispy edges that the lighter tiers erase
  are preserved. Flash and Mid are unchanged (instant, fully offline).

### Notes
- New models download once on first use (Fast ~28 MB, Max ~133 MB, Omega
  ~444 MB) into the app's local cache, then everything is offline.
- The stronger-on-paper RMBG-2.0 was evaluated and skipped: it requires a
  HuggingFace account agreement (gated download), which breaks this app's
  no-accounts rule — and BiRefNet-HR actually preserves hair better.

---

## v4.0 — 2026-06-11

A whole new direction: **Sonara**, the audio-tools section.

### Added
- **Audio Stem Splitter** — drop a song (MP3, WAV, FLAC, M4A, OGG, even the
  audio of an MP4) and it's split into four stems: **Vocals, Drums, Bass,
  Other**, using Demucs `htdemucs_ft` — the best open-source separation model.
  Runs on your NVIDIA GPU when available (seconds per song) and falls back to
  CPU. A real progress bar tracks the split; the model (~320 MB) downloads once
  on first use.
- **Built-in stem mixer** — after the split, play the mix right in the app:
  - **▶ / ⏸** play-pause and a **seek bar** with live position
  - per-stem **M** (mute) and **S** (solo) buttons — applied instantly while
    playing, like a DAW
  - per-stem **volume sliders**
  - per-stem **Save** buttons — export only the stems you want (WAV or MP3),
    next to the original song
- Headless too: `--split-stems FILE` writes all four stem WAVs next to the file.
- **Tools → Unload AI models** also frees the Demucs model (GPU memory included).

### Notes
- Everything runs locally — no accounts, no APIs, no usage limits.
- This release adds PyTorch (CUDA) as a dependency, which makes the install and
  the standalone build several GB larger. Worth it: stem separation quality is
  in a different league from anything lighter.

---

## v3.2 — 2026-06-10

Vanguard grows into a multi-tool page: two new image tools join the AI detector.

### Added
- **Text Extraction** — drop or pick a screenshot/photo and every line of text
  is read out of it (offline OCR, nothing leaves your machine). Results appear
  in a textbox with a **Copy to clipboard** button, plus a line/character count.
  Two **QUALITY** tiers: **Fast** (instant, fully offline, also reads Chinese)
  and **Max** (best for English — proper word spacing and catches faint/small
  lines the Fast tier can miss; a small model downloads once on first use).
  No accounts, no APIs, no usage limits — everything runs on your machine.
  Also headless: `--extract-text FILE [Fast|Max]`.
- **What's The Font** — drop an image of some text and get the five **closest
  matches from ~3,500 Google Fonts**, each with a confidence bar. A tight crop
  of large, clear text works best. The ~64 MB font model downloads once on
  first use (integrity-checked), then it's fully offline.
  Also headless: `--identify-font FILE`.
- Vanguard now has a tool switcher (AI Detector / Text Extraction /
  What's The Font), just like Marquee; both new action buttons get the full
  animated treatment, and **Tools → Unload AI models** frees the new engines too.

### Notes
- Font identification is a **closest-match estimate**, not an exact ID —
  commercial fonts (Helvetica, Proxima Nova, …) are shown as their nearest
  Google Font lookalike; the panel says so.
- OCR's Fast tier ships inside the app (no downloads) and reads English and
  Chinese; the Max tier is tuned for English and is just as quick after its
  one-time small download.

---

## v3.1.5 — 2026-06-10

The action buttons go full dopamine.

### Changed
- **Every primary button is now the animated showpiece** — Convert Now,
  Download (YouTube), Remove Background, Upscale Image, and Detect AI Text all
  share one redesigned animated button:
  - a **living lava gradient** that continuously flows through deep red →
    ember orange → hot pink,
  - a **comet** with a golden trail orbiting the button's border,
  - **ember sparkles** that twinkle and rise off the surface,
  - a **ripple** that bursts from the exact point you click,
  - while working: flowing **candy stripes**, a double shine, and live
    "Converting… / Downloading… / Removing… / Upscaling… / Detecting…" dots,
  - and when a job finishes successfully — a **confetti burst with a white
    flash**. You earned it.

### Notes
- Pure-UI release; no conversion behavior changed. The animation still pauses
  when its page is hidden and goes to sleep after ~12 s without input, so the
  extra flair costs nothing in the background. The busy state previously
  dropped to grey mid-job — it now keeps the full color treatment, which is
  exactly when the button should feel most alive.

---

## v3.1 — 2026-06-10

A full-codebase audit followed by a fix pass — no new tools, everything gets
safer, faster, and more consistent.

### Fixed
- **PPTX → PDF no longer closes your open PowerPoint.** Converting a deck while
  PowerPoint was running could quit it (with all your presentations); the app
  now only closes PowerPoint instances it started itself.
- **DOCX → PDF no longer leaks hidden Word processes** when a conversion fails;
  Word is now driven directly and always cleaned up.
- **Save dialogs respect "Replace?"** — confirming an overwrite in the Marquee
  tools actually overwrites instead of silently saving a `name (1).png` copy.
- **Clear / Reset during a running job** can no longer be undone by the job
  finishing afterwards (Converter and Vanguard).
- Loading a large PDF into Vanguard no longer freezes the window; ffmpeg errors
  no longer dump pages of log into the status line; a corrupted history file no
  longer crashes the app at startup; `.tif` files are now accepted; animated
  GIFs keep their animation when converted to WEBP/TIFF/PNG.

### Added
- **Upscaler FIT selector** — choose **Pad** (letterbox bars) or **Crop**
  (fill the frame) for the target resolution.
- **Batch upgrades:** pick an output folder ("Save to…"), a live `n / N`
  counter, and a read-only results log.
- **Home quick actions** for Marquee and Vanguard; file dialogs remember their
  last folder; Vanguard's input highlights when you drag a file over it.
- **Tools → "Unload AI models"** frees the cached rembg / upscaler / detector
  models (multiple GB of RAM); Tools stats now refresh on every visit.
- **Safety & polish:** closing the app warns if a job is still running;
  clearing history asks first; the windowed exe writes diagnostics to
  `%LOCALAPPDATA%\Bu D3eij\app.log`; model downloads are integrity-checked;
  dragging a file onto the exe opens it straight in the Converter;
  `--remove-bg FILE [TIER]` picks a quality tier from the CLI.
- **In-repo tests** (`tests/`) — 57 automated checks covering conversions, the
  GUI, and the Word/PowerPoint COM paths.

### Notes
- Vanguard's overall score is now weighted by what the model actually scored,
  improving accuracy on very long documents. The upscaler skips the slow AI
  pass when the input is already close to the target size (plain high-quality
  resampling looks identical there and saves minutes + RAM).

---

## v1.4.5 — 2026-06-08

A flashy upgrade to the main action button.

### Changed
- **Animated "Convert Now" button.** The flat button is replaced by a fully
  animated control: a red gradient with a top gloss, a light **shine that sweeps
  across**, and a gentle **breathing glow** while it waits. Hovering brightens it
  and blooms the glow; pressing dims it; and during a conversion it switches to a
  continuous **double-shine "flow"** with animated `Converting…` dots. It greys
  out, flat and motionless, when no file is selected.

### Notes
- CustomTkinter has no CSS, so the whole button is drawn as an image and
  animated by swapping frames. The animation pauses whenever the Converter page
  isn't on screen, so it doesn't use CPU in the background.

---

## v1.4 — 2026-06-08

A visual redesign for a cleaner, more professional look.

### Added
- **Colorful file-type icons** throughout — the Converter drop zone shows the
  dropped file's type, Recent lists each row's icon, and the Home page shows a
  file-icon showcase. (Icons from vscode-icons / Lucide; see `assets/LICENSES.md`.)
- **Redesigned Home** — a hero ("Convert anything, to everything."), quick action
  buttons, a **Popular conversions** row (PDF↔Word, MP4→MP3, JPG→PNG), and a
  **Supported formats** showcase.
- **Recent is now a table** — File · From · To · Status (✓ Completed / ✕ Failed)
  · Time, with per-row Open / Folder actions.
- **Sidebar nav icons** and a small "Convert anything" tagline.

### Changed
- Refreshed surfaces, spacing, and typography across all pages (both light and
  dark themes; dark remains the default).

### Notes
- This is a UI-only release — no conversion behavior changed. The app is built on
  CustomTkinter, so the look is a clean flat design (no web-style gradients,
  shadows, or 3D icons).

---

## v1.3 — 2026-06-08

Adds YouTube downloads and a nicer appearance toggle.

### Added
- **YouTube downloads** — a new **YouTube** page: paste a video link, choose
  **MP4** (best video+audio, merged) or **MP3** (192 kbps audio), and download.
  You're asked where to save each download, and progress is shown live.
  Results are recorded in **Recent**. (Uses `yt-dlp`; needs FFmpeg, same as the
  audio/video conversions.)
- **Headless `--download`** — `Bu D3eij.exe --download <URL> <mp3|mp4>` saves to
  the current folder (mirrors `--convert`).

### Changed
- **Appearance switch is now a sun/moon toggle button** in the sidebar
  (☀ in dark mode → click for light, ☾ in light mode → click for dark),
  replacing the System/Light/Dark dropdown.

### Notes
- Downloading copyrighted content may be against YouTube's Terms of Service —
  use this for content you have the right to download.

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
