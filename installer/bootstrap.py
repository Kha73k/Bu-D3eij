"""Bu D3eij installer bootstrap — sets up the managed Python environment.

Run BY the target (relocatable / standalone) Python during installation: it
pip-installs the Core dependencies plus whichever optional feature groups the user
selected, with the CPU or CUDA PyTorch build. The feature -> requirements mapping
mirrors `requirements/` (see requirements/README.md + docs/DISTRIBUTION.md).

The Inno Setup installer (see installer/README.md) invokes this with the target
python after laying down the app source:

    python bootstrap.py --features marquee,vanguard --torch cpu --reqs-dir <dir>
    python bootstrap.py --features marquee,sonara  --torch cuda
    python bootstrap.py --features all --torch cuda --dry-run     # print the plan
    python bootstrap.py --detect-gpu                              # -> "cuda" | "cpu"

Exit code 0 on success; the failing step's pip exit code otherwise.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

# Optional feature groups (Core is always installed). Canonical display order.
OPTIONAL_FEATURES = ("marquee", "vanguard", "sonara")
# Groups that pull PyTorch — if any is selected, a torch group is installed first.
TORCH_FEATURES = {"marquee", "sonara"}

# group -> its requirements/<file> (Core == base.txt, always included).
REQ_FILES = {
    "core": "base.txt",
    "marquee": "marquee.txt",
    "vanguard": "vanguard.txt",
    "sonara": "sonara.txt",
}
TORCH_REQ = {"cpu": "torch-cpu.txt", "cuda": "torch-cuda.txt"}


def normalize_features(features) -> list[str]:
    """Expand 'all', drop unknowns, return the selected optional groups in order."""
    wanted = set(features)
    if "all" in wanted:
        return list(OPTIONAL_FEATURES)
    return [f for f in OPTIONAL_FEATURES if f in wanted]


def plan_install(features, torch_variant: str = "cpu") -> list[tuple[str, str]]:
    """Ordered list of (label, requirements_filename) to pip-install.

    Core is always included. If any selected group needs PyTorch, the torch group
    is installed FIRST so demucs/spandrel resolve against the chosen build (the
    documented install order). Raises ValueError on an unknown torch variant.
    """
    selected = normalize_features(features)
    plan: list[tuple[str, str]] = []
    if TORCH_FEATURES & set(selected):
        if torch_variant not in TORCH_REQ:
            raise ValueError(f"unknown torch variant: {torch_variant!r}")
        label = "PyTorch (CUDA 12.6)" if torch_variant == "cuda" else "PyTorch (CPU)"
        plan.append((label, TORCH_REQ[torch_variant]))
    plan.append(("Core", REQ_FILES["core"]))
    for f in selected:
        plan.append((f.capitalize(), REQ_FILES[f]))
    return plan


def detect_nvidia() -> bool:
    """Best-effort: True if an NVIDIA GPU looks present (drives the CUDA default)."""
    import shutil

    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            r = subprocess.run([smi, "-L"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and "GPU" in r.stdout:
                return True
        except Exception:  # noqa: BLE001
            pass
    try:  # fallback: Windows WMI video-controller names
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_VideoController).Name"],
            capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and "nvidia" in r.stdout.lower():
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def _pip_install(python: str, reqs_dir, filename: str, dry_run: bool = False) -> int:
    req = Path(reqs_dir) / filename
    if not req.exists():
        print(f"  missing requirements file: {req}", file=sys.stderr)
        return 1
    # --no-warn-script-location: the app imports these as modules and never calls
    # the installed console scripts, so pip's "not on PATH" notices are just noise.
    cmd = [python, "-m", "pip", "install", "--no-input",
           "--no-warn-script-location", "--disable-pip-version-check", "-r", str(req)]
    if dry_run:
        print(">>", " ".join(cmd), flush=True)
        return 0
    return subprocess.call(cmd)


# Plan label -> a plain-English description shown in the setup window.
_FRIENDLY = {
    "Core": "the core app (file converter, utilities, downloaders)",
    "Marquee": "the image tools (background remover, upscaler, image-to-prompt)",
    "Vanguard": "the text tools (AI detector, text extraction, font ID)",
    "Sonara": "the audio tools (stem splitter)",
}

_BANNER = (
    "\n" + "=" * 66 + "\n"
    "   Bu D3eij  -  Setup\n\n"
    "   Almost there! This window is installing the parts you chose.\n"
    "   It downloads the libraries the app needs and sets them up on\n"
    "   THIS computer - nothing of yours is uploaded anywhere.\n\n"
    "   Depending on what you picked and your internet speed this can\n"
    "   take from under a minute to several minutes. Please leave this\n"
    "   window open until it says \"All set\".\n"
    + "=" * 66 + "\n"
)


def _set_console_title(title: str) -> None:
    """Name the setup console so it's clearly Bu D3eij's, not a stray terminal."""
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    except Exception:  # noqa: BLE001 - cosmetic only
        pass


def _friendly_label(label: str) -> str:
    if label.startswith("PyTorch"):
        backend = "GPU" if "CUDA" in label else "CPU"
        return f"the AI engine (PyTorch, {backend} build)"
    return _FRIENDLY.get(label, label)


def run(features, torch_variant: str, reqs_dir, python: str | None = None,
        dry_run: bool = False) -> int:
    python = python or sys.executable
    plan = plan_install(features, torch_variant)

    if dry_run:  # terse output for the dev / CLI dry run
        print(f"Target Python: {python}")
        print(f"Requirements:  {reqs_dir}")
        for i, (label, filename) in enumerate(plan, 1):
            print(f"\n[{i}/{len(plan)}] {label}  ({filename})", flush=True)
            _pip_install(python, reqs_dir, filename, dry_run=True)
        print("\nPlan OK (dry run).", flush=True)
        return 0

    # Friendly, self-explaining setup console (this is what the user watches).
    _set_console_title("Bu D3eij  -  Setup")
    print(_BANNER, flush=True)
    total = len(plan)
    for i, (label, filename) in enumerate(plan, 1):
        friendly = _friendly_label(label)
        print("\n" + "-" * 66, flush=True)
        print(f"  Step {i} of {total}:  installing {friendly}", flush=True)
        if label.startswith("PyTorch"):
            print("  This is the big one. It can take several minutes to download\n"
                  "  and install - that is completely normal. Please keep this\n"
                  "  window open; it is working even when it looks quiet.", flush=True)
        print("-" * 66, flush=True)
        code = _pip_install(python, reqs_dir, filename)
        if code != 0:
            print("\n  Sorry - installing " + friendly + " did not finish.",
                  file=sys.stderr)
            print("  Please check your internet connection and run the installer\n"
                  "  again. Nothing was harmed on your PC.", file=sys.stderr)
            time.sleep(5)
            return code

    print("\n" + "=" * 66, flush=True)
    print("   All set! Bu D3eij is ready to use.", flush=True)
    print("   You can close this window - it will close on its own in a moment.", flush=True)
    print("=" * 66, flush=True)
    time.sleep(3)  # let the user read "All set" before the window closes
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Bu D3eij installer bootstrap")
    p.add_argument("--features", default="",
                   help="comma-separated optional groups: marquee,vanguard,sonara (or 'all')")
    p.add_argument("--torch", default="cpu", choices=["cpu", "cuda"],
                   help="PyTorch build for the torch features (default: cpu)")
    p.add_argument("--reqs-dir",
                   default=str(Path(__file__).resolve().parent.parent / "requirements"),
                   help="path to the requirements/ directory")
    p.add_argument("--python", default=None,
                   help="target python exe to install into (default: this interpreter)")
    p.add_argument("--dry-run", action="store_true",
                   help="print the install plan without running pip")
    p.add_argument("--detect-gpu", action="store_true",
                   help="print 'cuda' or 'cpu' from GPU detection, then exit")
    a = p.parse_args(argv)
    if a.detect_gpu:
        print("cuda" if detect_nvidia() else "cpu")
        return 0
    features = [f.strip().lower() for f in a.features.split(",") if f.strip()]
    return run(features, a.torch, a.reqs_dir, python=a.python, dry_run=a.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
