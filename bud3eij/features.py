"""Feature-group availability detection for Bu D3eij.

The app is delivered by a feature-selective installer (see `docs/DISTRIBUTION.md`):
a Core-only install won't have the heavy optional dependencies. Every tool already
imports its deps lazily, so `app.py` launches regardless — but the GUI should hide
a section whose dependencies aren't installed instead of letting a lazy import fail
when the user clicks it.

This module reports which feature groups are available by probing sentinel packages
with `importlib.util.find_spec`, which locates a module **without importing it** —
so checking for `torch` etc. is fast and doesn't load the heavy library. The set of
installed packages *is* the source of truth (the installer pip-installs exactly the
chosen groups), so no separate manifest is needed.
"""
from __future__ import annotations

import importlib.util

# Feature group -> sentinel modules (ALL must be importable for the group to count
# as installed). Each sentinel is unique to that group's requirements/<group>.txt
# (see requirements/README.md). onnxruntime is deliberately NOT used as a sentinel
# because it is shared by marquee + vanguard.
FEATURE_SENTINELS: dict[str, tuple[str, ...]] = {
    "marquee": ("rembg", "spandrel", "torch"),
    "vanguard": ("tokenizers", "rapidocr"),
    "sonara": ("demucs", "sounddevice", "torch"),
}

# Nav-section label -> feature group. Sections not listed here are Core (the File
# Converter, Recent, Batch, YouTube, Nexus, Tools, Home) and are always available.
SECTION_FEATURE: dict[str, str] = {
    "Marquee": "marquee",
    "Vanguard": "vanguard",
    "Sonara": "sonara",
}


def _installed(module: str) -> bool:
    """True if `module` can be located on sys.path without importing it."""
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):  # missing parent package / bad name
        return False


def feature_available(group: str) -> bool:
    """True if every sentinel package for `group` is installed.

    An unknown/empty group (i.e. Core) is always available.
    """
    sentinels = FEATURE_SENTINELS.get(group)
    if not sentinels:
        return True
    return all(_installed(m) for m in sentinels)


def section_available(section: str) -> bool:
    """True if a nav section's feature group is installed (Core -> always True)."""
    return feature_available(SECTION_FEATURE.get(section, ""))


def available_features() -> dict[str, bool]:
    """Map each optional feature group -> whether it's installed."""
    return {group: feature_available(group) for group in FEATURE_SENTINELS}
