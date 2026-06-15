# Third-Party Licenses & Notices

Bu D3eij's own source code is licensed under the **MIT License** (see
[`LICENSE`](LICENSE)). The application depends on third-party libraries and
**downloads third-party AI models at runtime**. Those components are owned by
their respective authors and remain under their own licenses, summarized below.

Two of them carry obligations beyond a simple permissive license — read
**Important notices** first.

## Important notices

### PyMuPDF — AGPL-3.0 (affects distributed binaries)
The **PDF→Markdown** and **PDF→DOCX** converters depend on **PyMuPDF** (via
`pymupdf4llm` and `pdf2docx`), which is dual-licensed **GNU AGPL-3.0 or an
Artifex commercial license**. MIT covers Bu D3eij's own source, but any
**bundled binary** (the PyInstaller `.exe`) that includes PyMuPDF is a combined
work conveyed under the **AGPL-3.0**: whoever redistributes that binary must
provide the complete corresponding source (this repository) under
AGPL-compatible terms. This project is fully open-source, so publishing its
source here satisfies that obligation. A closed-source build would require an
Artifex commercial license, or removing the PyMuPDF-backed converters.

### UltraSharp V2 — CC-BY-NC-SA 4.0 (non-commercial)
The image upscaler's **Max** tier downloads Kim2091's **UltraSharp V2** models,
licensed **CC-BY-NC-SA 4.0** (non-commercial · attribution · share-alike). They
are **never bundled or re-hosted** — the app downloads them on demand from the
author's Hugging Face repository. Non-commercial use (a free tool) is permitted
with attribution. If Bu D3eij is ever monetized, swap this tier for a
permissively licensed upscaler.

## AI / ML models (downloaded on demand, not bundled)

| Tool | Model | Author / Source | License |
|------|-------|-----------------|---------|
| Vanguard · AI Text Detector | ai-text-detector-v1.01 (ONNX export) | desklib | MIT |
| Vanguard · Text Extraction | RapidOCR / PP-OCRv4 | RapidAI / PaddlePaddle | Apache-2.0 |
| Vanguard · What's The Font | font-classify-onnx | Storia AI | MIT |
| Marquee · Background Remover (Flash/Mid) | u2netp · isnet-general-use (via rembg) | rembg / Qin et al. | MIT / Apache-2.0 |
| Marquee · Background Remover (Omega) | BiRefNet_HR | ZhengPeng7 | MIT |
| Marquee · Image Upscaler (Fast) | 4x-UltraSharpV2_Lite | Kim2091 | CC-BY-NC-SA 4.0 |
| Marquee · Image Upscaler (Max) | 4x-UltraSharpV2 | Kim2091 | CC-BY-NC-SA 4.0 |
| Marquee · Image → Prompt | Qwen2-VL-2B-Instruct | Alibaba / Qwen | Apache-2.0 |
| Sonara · Stem Splitter | Demucs htdemucs_ft | Meta AI (FAIR) | MIT |

The Vanguard detector ONNX is a derivative of desklib's MIT-licensed model,
re-exported by this project and hosted for download. Every other model is pulled
from its author's own repository (Hugging Face / torch.hub) on first use.

## Python libraries

Permissive (MIT / BSD / Apache-2.0 / PSF / Unlicense / HPND):

- customtkinter (MIT), tkinterdnd2 (MIT), Pillow (HPND / MIT-CMU)
- python-docx (MIT), python-pptx (MIT), pdfplumber (MIT), markdownify (MIT)
- reportlab (BSD-3-Clause), mammoth (BSD-2-Clause), numpy (BSD-3-Clause)
- pint (BSD-3-Clause), qrcode (BSD-3-Clause)
- ffmpeg-python (Apache-2.0), pdf2docx (Apache-2.0)\*, transformers (Apache-2.0),
  timm (Apache-2.0), kornia (Apache-2.0), tokenizers (Apache-2.0),
  rapidocr (Apache-2.0), tzdata (Apache-2.0)
- onnxruntime (MIT), rembg (MIT), demucs (MIT), sounddevice (MIT), spandrel (MIT)
- torch · torchaudio · torchvision (BSD-3-Clause)
- pywin32 (PSF-2.0), yt-dlp (The Unlicense)

Copyleft / dual-licensed:

- **pymupdf4llm / PyMuPDF** — AGPL-3.0 or Artifex commercial (see Important
  notices).

\* `pdf2docx` is Apache-2.0 but depends on PyMuPDF (AGPL-3.0).

## External tools (not bundled)

- **FFmpeg** — needed at runtime for audio/video conversion and YouTube downloads.
  Bu D3eij uses a system ffmpeg if present, otherwise **downloads a pinned static
  build on demand** (gyan.dev essentials via its GitHub mirror, SHA-256 + size
  verified) into `~/.bud3eij/ffmpeg/` on first A/V use. It is **not bundled or
  re-distributed** by us — the user fetches it from the original distributor (the
  essentials build is GPL/LGPL).
- **Microsoft Word / PowerPoint** — optional; used via COM for high-fidelity
  DOCX/PPTX → PDF when installed. Not distributed.

## Bundled assets

Icons (vscode-icons — MIT; Lucide — ISC) and the Inter font (SIL OFL 1.1) — see
[`assets/LICENSES.md`](assets/LICENSES.md).

---

_License names above reflect each project's published license at the time of
writing; consult the upstream projects for full and current terms._
