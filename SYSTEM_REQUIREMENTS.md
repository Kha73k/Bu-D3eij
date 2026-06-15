# System Requirements

Bu D3eij is a **Windows-only** desktop application. Everything runs **locally** —
no account and no internet for the core converters. The AI tools download their
models once, on first use, then work offline.

## Minimum
- **OS:** Windows 10 64-bit (build 1903+) or Windows 11
- **CPU:** any modern x64 processor
- **RAM:** 8 GB
- **Disk:** ~500 MB for the app itself; AI models download on demand (table below)
- **GPU:** none required — the AI tools fall back to CPU automatically

## Recommended (for the AI tools)
- **GPU:** NVIDIA with CUDA support (e.g. RTX series), ~8 GB VRAM
  - With a CUDA GPU, stem splitting, upscaling, image captioning, and HR
    background removal run in seconds.
  - CPU-only: the same tools work but are far slower (stem splitting ~20×).
- **RAM:** 16 GB

## Optional
- **Microsoft Word / PowerPoint** — high-fidelity DOCX/PPTX → PDF (a text-only
  fallback is used when they're absent).
- **FFmpeg** — needed for audio/video conversion and YouTube downloads. **No
  manual install required**: the app uses a system ffmpeg if present, otherwise
  downloads a pinned static build (~109 MB) on first A/V use into
  `~/.bud3eij/ffmpeg/`.

## Disk usage by feature (models download on first use)

| Feature | Approx. model download |
|---------|------------------------|
| File Converter · Nexus utilities | none |
| Marquee · Background Remover | 5 MB (Flash) – ~450 MB (Omega / BiRefNet_HR) |
| Marquee · Image Upscaler | 28 MB (Fast) – 133 MB (Max) |
| Marquee · Image → Prompt | ~4.4 GB (Qwen2-VL-2B) |
| Vanguard · AI Text Detector | ~1.7 GB |
| Vanguard · Text Extraction (OCR) | ~15–25 MB |
| Vanguard · What's The Font | ~64 MB |
| Sonara · Stem Splitter | ~320 MB |

The PyTorch runtime (used by the Marquee AI tools, Image → Prompt, and Sonara)
adds roughly **2 GB (CPU build)** to **6 GB (CUDA build)**, depending on the
option chosen at install time. The lightweight tools (File Converter, Nexus, OCR,
font ID, AI Text Detector, basic background removal) do **not** need PyTorch.
