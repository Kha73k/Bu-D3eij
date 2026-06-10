"""GUI smoke test: builds the app, switches every frame, checks the v3.1
widgets/state, exercises set_file / clear / reset, then exits.

Run with the venv python: .\\.venv\\Scripts\\python tests\\test_gui_smoke.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app  # noqa: E402

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  OK   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}  {detail}")


a = app.App()
a.update()

# all frames build + switch
for name in app.NAV_ITEMS:
    a.show_frame(name)
    a.update()
check("all 8 frames switch", True)
check("_current_frame tracks", a._current_frame == app.NAV_ITEMS[-1], a._current_frame)

# new widgets exist
check("upscaler FIT selector", hasattr(a, "up_fit") and a.up_fit.get() == "Pad")
check("batch status label", hasattr(a, "batch_status"))
check("batch export label", hasattr(a, "batch_export_label"))
check("tools value labels", hasattr(a, "tools_values") and len(a.tools_values) == 3)
check("tools note label", hasattr(a, "tools_note"))
check("vg_out_text accessor", hasattr(a, "vg_out_text"))

# tools refresh reflects history count
a._refresh_tools()
check("tools history text", str(len(a.history)) in a.tools_values["History"].cget("text"))

# batch log is read-only (read state from the underlying tk.Text)
state = str(a.batch_list._textbox.cget("state"))
check("batch log read-only", state == "disabled", state)
a._batch_log("test line")
check("batch log still read-only after write",
      str(a.batch_list._textbox.cget("state")) == "disabled")
check("batch log received the line",
      "test line" in a.batch_list.get("1.0", "end"))

# converter: set a real file, then clear mid-"run" (generation counter)
tmp = Path(tempfile.mkdtemp(prefix="guicheck_"))
f = tmp / "doc.txt"
f.write_text("hello", encoding="utf-8")
a.show_frame("Converter")
a.update()
a.set_file(f)
check("set_file accepts txt", a.selected_file == f)
check("targets offered", a.to_menu.get() in ("pdf", "docx", "md"), a.to_menu.get())
run_before = a._convert_run
a.clear_converter()
check("clear bumps generation", a._convert_run == run_before + 1)
check("clear resets selection", a.selected_file is None)

# folder-drop copy
a.set_file(tmp)
check("folder drop message", "folder" in a.status.cget("text").lower(),
      a.status.cget("text"))

# vanguard reset bumps generation + clears
a.show_frame("Vanguard")
a.update()
a.vg_input.insert("1.0", "some text to clear")
vg_before = a._vg_run
a.reset_vanguard()
check("vanguard reset bumps generation", a._vg_run == vg_before + 1)
check("vanguard input cleared", a.vg_input.get("1.0", "end").strip() == "")

# job guard counters
a._job_started()
check("active jobs counted", a._active_jobs == 1)
a._job_finished()
check("active jobs released", a._active_jobs == 0)

# unload models button logic (no jobs running -> success note)
a._unload_models()
check("unload note set", "unloaded" in a.tools_note.cget("text"))

# GradientButton idle pause attributes
check("convert button idle pause wired", hasattr(a.convert_btn, "_idle_ms"))

# v3.1.5: all five action buttons share the animated GradientButton design
for name, btn, busy in [("convert", a.convert_btn, "Converting"),
                        ("youtube", a.yt_btn, "Downloading"),
                        ("bg-remover", a.mq_btn, "Removing"),
                        ("upscaler", a.up_btn, "Upscaling"),
                        ("vanguard", a.vg_btn, "Detecting")]:
    check(f"{name} button is a GradientButton",
          isinstance(btn, app.GradientButton))
    check(f"{name} busy text", getattr(btn, "_busy_text", "") == busy,
          getattr(btn, "_busy_text", ""))
a.vg_btn._celebrate()
check("celebration spawns confetti", len(a.vg_btn._particles) > 0)

a.update()
a.after(200, a.destroy)
a.mainloop()
print(f"\n==== {PASS} passed, {FAIL} failed ====")
raise SystemExit(1 if FAIL else 0)
