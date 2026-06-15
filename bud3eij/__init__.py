"""Bu D3eij core package: GUI-free conversion / download / editing logic."""

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
