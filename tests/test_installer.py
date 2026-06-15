"""Installer bootstrap logic tests — plan composition, normalization, GPU probe,
and that every requirements file the plan references actually exists.

Run with the venv python: .\\.venv\\Scripts\\python tests\\test_installer.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "installer"))

import bootstrap as b  # noqa: E402

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  OK   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}  {detail}")


print("[1] plan_install composition")
check("core-only: just base, no torch",
      b.plan_install([]) == [("Core", "base.txt")])
check("vanguard only: core + vanguard, no torch",
      b.plan_install(["vanguard"]) == [("Core", "base.txt"), ("Vanguard", "vanguard.txt")])
check("marquee: torch (cpu) FIRST, then core, then marquee",
      b.plan_install(["marquee"]) == [
          ("PyTorch (CPU)", "torch-cpu.txt"),
          ("Core", "base.txt"),
          ("Marquee", "marquee.txt")])
cuda = b.plan_install(["marquee", "sonara"], "cuda")
check("cuda variant: torch-cuda is first", cuda[0] == ("PyTorch (CUDA 12.6)", "torch-cuda.txt"))
check("torch precedes the feature groups",
      [f for _, f in cuda] == ["torch-cuda.txt", "base.txt", "marquee.txt", "sonara.txt"])
allp = b.plan_install(["all"], "cpu")
check("'all' expands to every group + torch",
      [f for _, f in allp] == ["torch-cpu.txt", "base.txt", "marquee.txt", "vanguard.txt", "sonara.txt"])

print("\n[2] normalization + ordering")
check("unknown features dropped", b.normalize_features(["bogus", "vanguard"]) == ["vanguard"])
check("canonical order regardless of input order",
      b.normalize_features(["sonara", "marquee"]) == ["marquee", "sonara"])
check("vanguard alone needs no torch",
      all("torch" not in f for _, f in b.plan_install(["vanguard"])))
try:
    b.plan_install(["marquee"], "bogus")
    check("bad torch variant raises", False)
except ValueError:
    check("bad torch variant raises", True)

print("\n[3] referenced requirements files exist")
reqs = ROOT / "requirements"
referenced = {f for feats in (["all"],) for _, f in b.plan_install(feats, "cpu")}
referenced |= {b.TORCH_REQ["cuda"]}
missing = [f for f in referenced if not (reqs / f).exists()]
check("all plan requirements files present", not missing, str(missing))

print("\n[4] GPU detection returns a bool (no crash)")
got = b.detect_nvidia()
check("detect_nvidia() -> bool", isinstance(got, bool), repr(got))

print(f"\n==== {PASS} passed, {FAIL} failed ====")
sys.exit(1 if FAIL else 0)
