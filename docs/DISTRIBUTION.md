# Distribution architecture (Phase 1)

**Decided 2026-06-15.** The product is a **feature-selective installer that builds
a managed Python environment** — *not* a monolithic frozen `.exe`. Dependencies
install on demand; **CPU PyTorch by default, CUDA optional**; **Windows only**.

## Why this shape
Bundling all of PyTorch into one PyInstaller exe is ~6 GB and forces every user to
download everything. The installer-builds-env model lets a user install only the
feature groups they want, with the right torch build for their hardware, while the
heavy ML **model weights keep downloading on demand** (already how the app works).

## What the installer assembles
1. **Embedded Python 3.11** — shipped with the installer (Windows embeddable
   package / bundled base), so users don't need Python preinstalled.
2. **App source** — the `bud3eij/` package + `app.py` + `assets/` + theme + fonts
   (small; copied into the install dir).
3. **Selected feature dependencies** — pip-installed from `requirements/` per the
   user's choices (see below).
4. **PyTorch (CPU or CUDA)** — from the PyTorch index, only when a torch-dependent
   feature (Marquee / Sonara) is chosen. CPU default; CUDA if the user has an
   NVIDIA GPU and opts in.
5. **Launcher + Start-menu/desktop shortcut** that runs `app.py` in the env.

ML model **weights are not installed here** — they download on first use of each
tool into `~/.bud3eij/models/` (Vanguard self-hosted on Hugging Face; the rest
from their authors). The installer only sizes/explains them.

## Feature groups → dependencies
See [`requirements/README.md`](../requirements/README.md) for the file-level split.

| Group | Tools | requirements | torch |
|-------|-------|--------------|-------|
| **Core** (always) | File Converter, Nexus, YouTube, ASCII Art | `base.txt` | no |
| **Marquee** | Background Remover, Upscaler, Image → Prompt | `marquee.txt` | yes |
| **Vanguard** | AI Text Detector, Text Extraction, What's The Font | `vanguard.txt` | no |
| **Sonara** | Audio Stem Splitter | `sonara.txt` | yes |

`torch-cpu.txt` / `torch-cuda.txt` install once if Marquee or Sonara is selected.

## Install flow (installer pseudocode)
1. Welcome → license (MIT, with the AGPL/PyMuPDF + CC-BY-NC-SA/UltraSharp notices)
   → unsigned-build SmartScreen note.
2. Detect NVIDIA GPU → offer **CPU (default) / CUDA**.
3. Feature checklist (Core forced on; Marquee / Vanguard / Sonara optional) with a
   live download-size estimate.
4. Lay down embedded Python + app source.
5. `pip install` — a torch group (if any torch feature chosen) **first**, then
   `base.txt` + each selected group, into the env. Show a progress window.
6. Create the shortcut. Done. (Models download on first tool use.)

## Decisions baked in
- **PyMuPDF (AGPL-3.0)** is kept. MIT covers our source; the distributed
  environment is conveyed under AGPL, which the public GitHub source satisfies.
  License screen lists it. (See `THIRD_PARTY.md`.)
- **UltraSharp V2 (CC-BY-NC-SA)** stays download-on-demand + attributed; fine for
  a free build.

## Open items
- **Installer tooling** (Phase 2): Inno Setup for the component UI driving a
  post-install pip bootstrap with a progress window, vs. a custom bootstrapper.
- **UI feature-gating** (Phase 2): when a group isn't installed, hide/disable its
  page instead of letting a lazy import fail. The app's tool deps are all lazy, so
  a Core-only env still launches — the page just needs to know it's unavailable.
- **Pin torch versions** for reproducible installs (currently unpinned).
- **Offline / repair / uninstall**; an optional "pre-download models" step for
  air-gapped machines.
- **CI**: matrix-test that each feature group installs and its tools import.
