"""Bu D3eij core package: GUI-free conversion / download / editing logic."""

import os
import sys

# The installer bundles the Microsoft VC++ C++ runtime (msvcp140.dll etc.) next to
# the standalone python.exe (it ships the C runtime but not the C++ one that
# onnxruntime needs). Add that directory to the DLL search so C++ extension modules
# load on a clean machine without an admin VC++ redistributable. os.add_dll_directory
# is the right mechanism for extension-module dependencies on Python 3.8+ (PATH is no
# longer searched for those). No-op in dev (the runtime is in System32).
try:
    if sys.platform == "win32":
        os.add_dll_directory(os.path.dirname(os.path.abspath(sys.executable)))
except Exception:  # noqa: BLE001
    pass

# The installer's relocatable standalone Python ships no CA certificate bundle, so
# urllib / torch.hub HTTPS downloads (ffmpeg, the Vanguard / font / upscale models,
# Demucs checkpoints) fail on a clean machine with CERTIFICATE_VERIFY_FAILED.
# `truststore` routes Python's SSL verification through the OS trust store (which
# Windows always has), fixing every urllib-based download at once. No-op on a normal
# CPython (working defaults) or if truststore isn't installed.
try:
    import truststore as _truststore

    _truststore.inject_into_ssl()
except Exception:  # noqa: BLE001
    pass
