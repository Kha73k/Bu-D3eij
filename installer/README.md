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
| `build.ps1` | Staging: downloads the standalone Python + copies the app source into `build/` (the Inno Setup input). | ✅ verified (Py 3.11.15 + tkinter + pip) |
| `bud3eij.iss` | Inno Setup script: component UI, CPU/CUDA page (GPU-detected default), copy Python + app source, run bootstrap, create the shortcut. | ✍️ written, unverified |
| Launcher | The shortcut runs `{app}\python\pythonw.exe {app}\app.py` directly (no console window) — created by the `.iss`; no separate file. | ✅ in the `.iss` |

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

## Building the installer
Prereq: [Inno Setup 6](https://jrsoftware.org/isinfo.php) (free) on the build PC.
1. `pwsh installer\build.ps1` — downloads the standalone Python + stages the app
   source into `installer\build\`. (Verify/update `-PyRelease` against the
   python-build-standalone releases page.)
2. Compile `installer\bud3eij.iss` with Inno Setup (open in the IDE → Build, or
   `ISCC.exe installer\bud3eij.iss`) → `installer\dist\BuD3eij-Setup.exe`.
3. Test on a **clean Windows VM** (no Python, no `~/.bud3eij` model cache): run
   setup, pick a feature subset, confirm the env builds and the app launches with
   only the chosen sections visible (feature-gating). Easiest: `test-sandbox.ps1`
   opens the compiled installer in a fresh **Windows Sandbox** (enable it once via
   Windows Features). Note: Sandbox has no CUDA and no ffmpeg, so test the CPU path
   and doc/image/AI tools there (A/V + YouTube need a separate ffmpeg install).

`installer\build\` and `installer\dist\` are git-ignored (build artifacts).

## Install flow (implemented in `bud3eij.iss`)
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
- **Compile + smoke-test the `.iss`** on a clean VM — the untested part; fix any
  Inno Setup / bootstrap issues that only surface at install time.
- Confirm the `python-build-standalone` release tag in `build.ps1` is current.
- UI feature-gating already lands in the app (`bud3eij/features.py`), so an env
  missing a group hides that section automatically.
- Publishing a release: see **Releasing** below (manual for now — the CI workflow in
  `.github/workflows/release.yml` is dormant while the account's Actions billing is locked).

## Releasing (manual)
1. `pwsh installer\build.ps1` — re-stage the latest app source + Python.
2. Compile `installer\bud3eij.iss` in Inno Setup (F9) → `installer\dist\BuD3eij-Setup.exe`.
3. On GitHub: **Releases → Draft a new release** → create a tag (e.g. `v4.3.2`), add
   notes, **attach `BuD3eij-Setup.exe`**, then Publish. The website's Download button
   points at the repo's Releases page, so this is all it needs.

When Actions billing is restored, `release.yml` can do all three on a `v*` tag —
re-add its `push: tags: ['v*']` trigger.
