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
check("all 10 frames switch", True)
check("_current_frame tracks", a._current_frame == app.NAV_ITEMS[-1], a._current_frame)

# scroll area: fills the viewport when large (no scrollbar), scrolls when small
a.minsize(400, 300)
a.geometry("1100x820")
a.update()
a.show_frame("Converter")
a.update()
a._scroll_area._sync()
a.update()
check("scrollbar hidden when content fits",
      a._scroll_area._sb.winfo_manager() != "grid",
      a._scroll_area._sb.winfo_manager())
a.geometry("900x340")
a.update()
a.show_frame("Nexus")
a.update()
a.nx_tool.set("QR Code")
a._show_nx_tool("QR Code")
a._show_nxq_type("vCard")
a.update()
a._scroll_area._sync()
a.update()
check("scrollbar shows when window too small",
      a._scroll_area._sb.winfo_manager() == "grid",
      a._scroll_area._sb.winfo_manager())
a.geometry("1100x820")
a.update()

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

# v3.2: Vanguard is a multi-tool page (AI Detector / Text Extraction / Font ID)
a.show_frame("Vanguard")
a.update()
check("vg_tool switcher exists", hasattr(a, "vg_tool"))
check("vg_tool has 3 tools", set(a.vg_panels) ==
      {"AI Detector", "Text Extraction", "What's The Font"}, str(set(a.vg_panels)))
a._show_vg_tool("Text Extraction")
a.update()
check("ocr panel shown", a.vg_panels["Text Extraction"].winfo_manager() == "grid")
check("detector panel hidden", a.vg_panels["AI Detector"].winfo_manager() == "")
a._show_vg_tool("What's The Font")
a.update()
check("font panel shown", a.vg_panels["What's The Font"].winfo_manager() == "grid")
a._show_vg_tool("AI Detector")
check("ocr results read-only",
      str(a.vgo_out._textbox.cget("state")) == "disabled")
check("ocr copy button exists", hasattr(a, "vgo_copy_btn"))
check("ocr QUALITY selector", hasattr(a, "vgo_model") and a.vgo_model.get() == "Fast")
a._on_vgo_model_change("Max")
check("ocr tier caption updates",
      "English" in a.vgo_model_caption.cget("text"))
check("font has 5 result rows", len(a.vgf_rows) == 5)

# v4.0: Sonara page — stem rows, hidden player card, stub-player toggles
import numpy as np  # noqa: E402

a.show_frame("Sonara")
a.update()
check("sonara nav present", "Sonara" in app.NAV_ITEMS)
check("sonara player card hidden initially",
      a.sn_player_card.winfo_manager() == "")
check("sonara 4 stem rows", set(a.sn_rows) == set(app.STEMS), str(set(a.sn_rows)))
check("sonara rows complete",
      all({"mute", "solo", "volume", "save"} <= set(r) for r in a.sn_rows.values()))
stub = {s: np.zeros((1000, 2), dtype=np.float32) for s in app.STEMS}
a.sonara_player = app.StemPlayer(stub, 44100)
a._sn_toggle_mute("drums")
check("mute toggles player state", a.sonara_player.muted["drums"])
a._sn_toggle_solo("vocals")
check("solo toggles player state", a.sonara_player.soloed["vocals"])
a._sn_set_volume("bass", 50)
check("volume slider maps 0-100 to 0-1", a.sonara_player.volume["bass"] == 0.5)
check("time formatter", app.App._fmt_time(83) == "1:23", app.App._fmt_time(83))
a.sonara_player.close()
a.sonara_player = None

# non-audio file rejected by the Sonara drop
a.set_sonara_file(f)  # the txt from the converter check
check("sonara rejects non-audio",
      "Unsupported" in a.sn_status.cget("text"), a.sn_status.cget("text"))

# v4.2: Nexus — Converter (currency / units / timezone) + QR Code
a.show_frame("Nexus")
a.update()
check("nexus nav present", "Nexus" in app.NAV_ITEMS)
check("nx_tool has both tools", set(a.nx_panels) == {"Converter", "QR Code"},
      str(set(a.nx_panels)))
# converter category swap shows the right inputs
a.nx_tool.set("Converter")
a._show_nx_tool("Converter")
a._show_nxc_cat("Currency")
a.update()
check("currency inputs shown", a.nxc_frames["Currency"].winfo_manager() == "grid")
check("units inputs hidden", a.nxc_frames["Units"].winfo_manager() == "")
# live currency conversion produces a result
a.nxc_amount.delete(0, "end")
a.nxc_amount.insert(0, "100")
a.nxc_from.set("USD")
a.nxc_to.set("EUR")
a._nxc_compute()
a.update()
check("live currency result", a.nxc_result.cget("text") not in ("", "—"),
      a.nxc_result.cget("text"))
# units category + live temperature conversion (100 C -> 212 F)
a._show_nxc_cat("Units")
a._nxc_unit_cat_change("Temperature")
a.nxc_unit_from.set("Celsius")
a.nxc_unit_to.set("Fahrenheit")
a.nxc_value.delete(0, "end")
a.nxc_value.insert(0, "100")
a._nxc_compute()
a.update()
check("live units result 212", a.nxc_result.cget("text").startswith("212"),
      a.nxc_result.cget("text"))
a._nxc_swap()
a.update()
check("converter swap works", a.nxc_unit_from.get() == "Fahrenheit",
      a.nxc_unit_from.get())
# currency dropdown shows full-name labels incl. the pegged BHD
a._show_nxc_cat("Currency")
a.update()
check("currency labels show full names",
      any("Bahraini" in v for v in a.nxc_from.cget("values")),
      str(a.nxc_from.cget("values")[:3]))
# typeahead filtering narrows the dropdown (focus the entry, then KeyRelease)
ce = a.nxc_from._entry
ce.delete(0, "end")
ce.insert(0, "dinar")
ce.focus_force()
a.update()
ce.event_generate("<KeyRelease>", when="now")
a.update()
check("currency search filters", a.nxc_from.cget("values") == ["BHD (Bahraini Dinar)"],
      str(a.nxc_from.cget("values")))
# timezone tab + world clock + searchable zones
a._show_nxc_cat("Time Zone")
a.update()
check("timezone inputs shown", a.nxc_frames["Time Zone"].winfo_manager() == "grid")
check("world clock rows", len(a.nxc_world_rows) == len(app.WORLD_CLOCK_ZONES))
check("timezone default list is curated (not all ~600)",
      len(a.nxc_tz_from.cget("values")) == len(a._nxc_tz_common) < 60,
      str(len(a.nxc_tz_from.cget("values"))))
te = a.nxc_tz_from._entry
te.delete(0, "end")
te.insert(0, "dubai")
te.focus_force()
a.update()
te.event_generate("<KeyRelease>", when="now")
a.update()
check("timezone search filters to match", a.nxc_tz_from.cget("values") == ["Asia/Dubai"],
      str(a.nxc_tz_from.cget("values")))
# QR tool: 7 content types, GradientButton, live render
a.nx_tool.set("QR Code")
a._show_nx_tool("QR Code")
check("qr has 7 content types", len(a.nxq_groups) == 7, str(len(a.nxq_groups)))
check("qr save is a GradientButton", isinstance(a.nxq_btn, app.GradientButton))
a._show_nxq_type("Text / URL")
a.update()
check("qr text group shown", a.nxq_groups["Text / URL"].winfo_manager() == "grid")
check("qr wifi group hidden", a.nxq_groups["Wi-Fi"].winfo_manager() == "")
check("qr save disabled when empty", not a.nxq_btn._enabled)
a.nxq_fields["Text / URL"]["text"].insert("1.0", "https://example.com")
a._nxq_compute()
a.update()
check("qr live render + save enabled",
      a.nx_qr_image is not None and a.nxq_btn._enabled)
a._show_nxq_type("Wi-Fi")  # type swap (image -> placeholder, no CTkImage crash)
a.update()
check("qr wifi group now shown", a.nxq_groups["Wi-Fi"].winfo_manager() == "grid")

# v4.2.1: Clear/Reset buttons on the tool pages that lacked them
a.show_frame("YouTube")
a.update()
a.yt_url.insert(0, "https://example.com/watch")
a.reset_youtube()
check("youtube reset clears url", a.yt_url.get() == "")
a.show_frame("Batch Convert")
a.update()
a.batch_files = [Path("x")]
a.batch_primary.configure(text="3 file(s)")
a.reset_batch()
check("batch reset clears files",
      a.batch_files == [] and "Drop multiple" in a.batch_primary.cget("text"))
a.show_frame("Marquee")
a.update()
a.marquee_file = Path("x.png")
a.mq_btn.configure(state="normal")
a.reset_marquee()
check("marquee reset disables run + clears file",
      a.marquee_file is None and not a.mq_btn._enabled)
a.show_frame("Vanguard")
a.update()
a.vg_font_file = Path("x.png")
a.vgf_results.grid()
a.reset_vg_font()
check("font reset hides results", a.vgf_results.winfo_manager() == "")
a.show_frame("Nexus")
a.update()
a._show_nx_tool("Converter")
a._show_nxc_cat("Currency")
a.nxc_amount.delete(0, "end")
a.nxc_amount.insert(0, "999")
a.reset_nxc()
check("nexus converter reset restores amount", a.nxc_amount.get() == "1")
a._show_nx_tool("QR Code")
a._show_nxq_type("Wi-Fi")
a.nxq_fields["Wi-Fi"]["ssid"].insert(0, "Net")
a.nxq_scale.set(20)
a.reset_nxq()
check("qr reset clears fields + options",
      a.nxq_fields["Wi-Fi"]["ssid"].get() == "" and int(a.nxq_scale.get()) == 10)

# v3.1.5/v3.2/v4.0/v4.2: all nine action buttons share the animated GradientButton design
for name, btn, busy in [("convert", a.convert_btn, "Converting"),
                        ("youtube", a.yt_btn, "Downloading"),
                        ("bg-remover", a.mq_btn, "Removing"),
                        ("upscaler", a.up_btn, "Upscaling"),
                        ("vanguard", a.vg_btn, "Detecting"),
                        ("vg-ocr", a.vgo_btn, "Extracting"),
                        ("vg-font", a.vgf_btn, "Identifying"),
                        ("sonara", a.sn_btn, "Splitting"),
                        ("nexus-qr", a.nxq_btn, "Generating")]:
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
