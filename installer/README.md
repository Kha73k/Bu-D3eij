# installer/ — the feature-selective installer (Phase 2)

Builds the **feature-selective installer that sets up a managed Python environment**
(the Phase 1 decision — see [`docs/DISTRIBUTION.md`](../docs/DISTRIBUTION.md)). The
user picks feature groups + CPU/CUDA; the installer lays down a relocatable Python +
the app source, then runs `bootstrap.py` to pip-install exactly what was chosen.

## Base Python — `python-build-standalone` (NOT the embeddable package)
The installer ships a **relocatable standalone CPython 3.11** from
[`python-build-standalone`](https://github.com/astral-sh/python-build-standalone).
Why not the official Windows *embeddable* zip: it **omits tkinter / Tcl-Tk**, which
the entire CustomTkinter GUI depends on, and it has no `pip`/`venv` out of the box.
The standalone build includes tkinter, pip and venv, and is designed to be moved/
unpacked anywhere — exactly what an installer-built env needs.

## Components
| File | Role | Status |
|------|------|--------|
| `bootstrap.py` | Feature → pip plan; installs Core + selected groups + CPU/CUDA torch into the target Python. Also `--detect-gpu`. | ✅ done + tested |
| `bud3eij.iss` | Inno Setup script: component-selection UI, GPU detect, lay down Python + app source, run bootstrap with a progress window, create the shortcut. | ⬜ TODO |
| `launcher` | What the Start-menu/desktop shortcut runs: `pythonw.exe app.py` from the installed env (no console window). | ⬜ TODO |

## bootstrap.py
Pure-logic core (`plan_install`) is unit-tested in
[`tests/test_installer.py`](../tests/test_installer.py). Install order: a torch
group **first** (only if Marquee or Sonara is selected), then `base.txt`, then each
selected group — matching `requirements/README.md`.

```powershell
# Preview the plan (no install)
python installer\bootstrap.py --features all --torch cuda --dry-run

# GPU detection (installer calls this to default cpu/cuda)
python installer\bootstrap.py --detect-gpu        # -> cuda | cpu

# Real install into a target Python (the installer passes the standalone python)
python installer\bootstrap.py --features marquee,sonara --torch cpu `
    --reqs-dir <installdir>\requirements --python <installdir>\python\python.exe
```

## Install flow (target for `bud3eij.iss`)
1. Welcome → license (MIT + the PyMuPDF-AGPL / UltraSharp-NC notices) → unsigned
   SmartScreen note.
2. `--detect-gpu` → preselect **CPU** (default) or **CUDA**.
3. Component page: **Core** (forced) + optional **Marquee / Vanguard / Sonara**,
   with a live download-size estimate (numbers in `SYSTEM_REQUIREMENTS.md`).
4. Copy the standalone Python + the app source (`app.py`, `bud3eij/`, `assets/`,
   `bud3eij_theme.json`, `requirements/`) into the install dir.
5. Run `bootstrap.py` (progress window) to pip-install the selection.
6. Create the launcher + Start-menu/desktop shortcut. (Models download on first
   tool use; nothing else to fetch.)

## Remaining Phase 2 work
- Write `bud3eij.iss` + the launcher; wire `bootstrap.py` as a post-install step.
- Acquire/stage the standalone Python build in the installer inputs.
- UI feature-gating already lands in the app (`bud3eij/features.py`) so an env
  missing a group hides that section automatically.
- Test on a clean Windows VM (no Python / no model cache); then the GitHub
  Releases pipeline can publish the compiled installer.
