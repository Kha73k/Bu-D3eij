# requirements/ — per-feature dependency split

The app is delivered by a **feature-selective installer that builds a managed
Python environment** (see [`docs/DISTRIBUTION.md`](../docs/DISTRIBUTION.md)). This
folder is the **feature → dependency contract** the installer composes from.

| File | Feature group | Tools | torch? |
|------|---------------|-------|--------|
| `base.txt` | **Core** (always) | File Converter · Nexus · YouTube · ASCII Art | no |
| `marquee.txt` | Marquee | Background Remover · Upscaler · Image → Prompt | **yes** |
| `vanguard.txt` | Vanguard | AI Text Detector · Text Extraction · What's The Font | no |
| `sonara.txt` | Sonara | Audio Stem Splitter | **yes** |
| `torch-cpu.txt` | PyTorch (default) | needed if Marquee or Sonara is selected | — |
| `torch-cuda.txt` | PyTorch (CUDA 12.6) | optional, NVIDIA GPU | — |

## Install order
PyTorch must be installed **before** the feature groups (from the PyTorch index,
not PyPI), so `demucs`/`spandrel` resolve against the chosen build:

```powershell
# 1. PyTorch — pick ONE (only if installing Marquee and/or Sonara)
pip install -r requirements/torch-cpu.txt      # default
pip install -r requirements/torch-cuda.txt     # NVIDIA GPU

# 2. Core + whichever feature groups the user picked
pip install -r requirements/base.txt
pip install -r requirements/marquee.txt
pip install -r requirements/vanguard.txt
pip install -r requirements/sonara.txt
```

The root [`requirements.txt`](../requirements.txt) composes **all** of these — it's
the dev "everything" install.

## Notes
- `onnxruntime` appears in both `marquee.txt` and `vanguard.txt`; pip de-duplicates.
- ML model **weights** are not pip deps — they download on first tool use into
  `~/.bud3eij/models/` (and `~/.u2net/`). The installer only estimates their size.
- torch is pinned to the tested combo — `torch==2.12.0` / `torchaudio==2.11.0` /
  `torchvision==0.27.0` (the version numbers resolve to the `+cpu` or `+cu126`
  build per the index URL; both verified to exist on cp311/win_amd64).
