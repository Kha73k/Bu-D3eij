# PROGRESS — Bu D3eij

Running log of what's done and what's next. Update at the end of each session.

_Last updated: 2026-06-14 (Marquee Image → Prompt + ASCII Art; DPI drag fix; debounced resize)_

## Status: working app — v4.3.2 (Marquee Image → Prompt + ASCII Art; smooth-drag DPI fix; debounced resize; exe rebuilt)

Core app, all required conversions, Recent history, Batch Convert, YouTube
downloads, a **Marquee** image-editing section (Background Remover **+ Image
Upscaler**), a **Vanguard** AI-text section (**AI Text Detector + Text
Extraction + What's The Font**), a **Sonara** audio section (stem splitter +
mixer), and a **Nexus** utilities section (**Converter** — currency/units/time
zones — **+ QR Code**) are complete and verified. v1.1 = PowerPoint +
Markdown; v1.2 = bug
fixes; v1.3 = YouTube downloads + sun/moon toggle; v1.4 = visual redesign (file-type
icons, hero Home, table Recent); v1.4.5 = animated "Convert Now" button; v2.0 =
Marquee / Background Remover (rembg); v2.1 = Marquee Flash/Mid/Omega model selector;
v2.2 = split the logic into a `bud3eij/` package; v2.3 = Marquee Image Upscaler
(Real-ESRGAN); v2.3.5 = Marquee filling progress bars; **v3.0 = Vanguard AI Text
Detector (desklib DeBERTa-v3-large on onnxruntime)**; v3.1 = audit-fix pass;
v3.1.5 = dopamine CTA redesign; v3.2 = Vanguard becomes multi-tool (OCR +
font identification); **v4.0 = Sonara audio section — Demucs stem splitter +
real-time 4-stem mixer (first PyTorch/CUDA dependency)**; v4.1 = Marquee GPU
upgrade (UltraSharp V2 + BiRefNet-HR); **v4.2 = Nexus utilities section
(offline currency/units/time-zone converter + QR-code generator)**; **v4.3 =
Marquee gains Image → Prompt (Qwen2-VL-2B image captioner) + ASCII Art**.

The project is now a **private GitHub repo**: https://github.com/Kha73k/Bu-D3eij
(branch `main`; v1.4 developed on `redesign-1.4`). Commit/push as work lands.

## Completed

### 2026-06-17 — Post-launch fix: Sonara crash under pythonw (v4.3.3)
A friend's install hit `Stem splitting failed: 'NoneType' object has no attribute
'write'`. Cause: the installer launches the app via **pythonw.exe** (no console), so
`sys.stdout`/`sys.stderr` are `None`; Demucs/tqdm progress output writes to them and
crashes. `_setup_frozen_logging()` already redirected None streams to `app.log` — but
it was gated behind `sys.frozen`, so it ran only in the (old) PyInstaller exe, never
the pythonw-launched install. **Fix:** drop the `frozen` gate so it runs whenever
stdout/stderr is `None` (covers pythonw + frozen) — protects Sonara and any tool that
writes to those streams. Bumped to **v4.3.3** and rebuilt the installer (Inno Setup,
~30 MB). Verified: app compiles, `import app`, and under simulated `None` streams the
redirect engages so `print()`/Demucs writes no longer crash. Slipped past pre-launch
because the Sandbox tests exercised Core + Vanguard, not Sonara. **User to publish a
v4.3.3 release** with the rebuilt exe.

### 2026-06-16 — 🚀 Public launch
Bu D3eij is live. Repo flipped to **public** (https://github.com/Kha73k/Bu-D3eij),
release **v4.3.2** published with `BuD3eij-Setup.exe` (~30 MB — built locally via
Inno Setup 7 from `installer/build.ps1` + `installer/bud3eij.iss`), and the
marketing site live + free on **Cloudflare**
(https://bu-d3eij.khalifaarefalhashel.workers.dev), whose Download button resolves
to `releases/latest`. Phases 0–4 complete. Optional post-launch polish: real
screenshots for the site, a custom domain, compiling Tailwind to drop the CDN, and
re-enabling the `release.yml` CI workflow if/when the account's Actions billing is
restored.

### 2026-06-15 — Public-launch prep: bundle the VC++ C++ runtime for onnxruntime
Second clean-machine fix from VM testing: with SSL fixed, Vanguard's detector then
failed with *"DLL load failed while importing onnxruntime_pybind11_state: The
specified module could not be found."* `onnxruntime` is a C++ extension needing the
MS VC++ C++ runtime (`msvcp140.dll`, `vcomp140.dll`); the standalone Python ships
only the C runtime (`vcruntime140`), and a fresh Windows has no VC++ redistributable.
**Fix (no admin):** `installer/build.ps1` bundles the redistributable VC++ DLLs
(`msvcp140`/`_1`/`_2`, `vcomp140`, `concrt140`) next to `python.exe`, and
`bud3eij/__init__.py` calls `os.add_dll_directory(<python dir>)` so the loader finds
them (`add_dll_directory` is the correct path for 3.8+ extension-module deps — PATH
is no longer searched for those). Verified the DLLs stage, `bud3eij` imports on the
standalone python, and onnxruntime still loads in dev. Affects onnxruntime
everywhere (Vanguard detector/OCR/fontid + Marquee rembg Flash/Mid). **Confirmed
in the Sandbox (user): no errors** — Core conversions (ffmpeg on-demand) + the
Vanguard AI Detector (onnxruntime) both work cold. The installer is now validated
end-to-end on a pristine Windows.

### 2026-06-15 — Public-launch prep: fix standalone-Python SSL (truststore)
VM (Windows Sandbox) testing surfaced a launch-blocker: in the installed app every
on-demand download failed with `[SSL: CERTIFICATE_VERIFY_FAILED] unable to get
local issuer certificate`. Root cause: the relocatable **standalone Python**
(python-build-standalone) ships **no CA certificate bundle**, and Python's `ssl`
reads only a static snapshot of the Windows cert store — which a fresh machine may
not have populated (Windows fills roots on demand). This broke **every urllib-based
download**: ffmpeg AND the Vanguard/font/upscale models AND torch.hub/Demucs (the
huggingface_hub paths worked because they bundle certifi). **Fix:** added
**`truststore`** to `requirements/base.txt` and call `truststore.inject_into_ssl()`
in `bud3eij/__init__.py` (try/except → no-op on a normal CPython) — routes all SSL
verification through the live OS trust store (Windows SChannel), like a browser.
Verified the injection takes effect (`ssl.create_default_context()` → a `truststore`
context) and the app imports clean; user to re-verify in the Sandbox after a
rebuild. Masked on the dev host, which has ambient CA certs the clean VM lacks.

### 2026-06-15 — Public-launch prep, Phase 2 start (feature-selective installer)
Began the installer (tracked in `PHASES.md`). Base Python decided:
**python-build-standalone** (relocatable, ships tkinter + pip — the Windows
*embeddable* zip omits tkinter, which the GUI needs); the installer = an Inno
Setup component UI over a Python bootstrap.
- **`installer/bootstrap.py`:** turns a feature selection + CPU/CUDA choice into
  the ordered pip plan (a torch group first iff Marquee/Sonara is picked, then
  Core, then each group) and runs it into the target Python. Flags: `--detect-gpu`
  (nvidia-smi → WMI fallback), `--dry-run`, `--reqs-dir`, `--python`. The pure
  `plan_install` logic is unit-tested.
- **`installer/README.md`:** build plan + base-Python rationale + remaining work
  (the `.iss`, launcher, staging the standalone Python, clean-VM test).
- **Verified:** `tests/test_installer.py` 12/0 (plan composition/order,
  normalization, bad-variant raise, referenced reqs files exist, GPU probe);
  dry-run prints the correct 5-step plan; `--detect-gpu` → `cuda` on the 3070 Ti.
- **`installer/bud3eij.iss` + `installer/build.ps1`:** the Inno Setup script
  (component UI, GPU-detected CPU/CUDA page, copy Python + source, run bootstrap,
  create the shortcut) and the staging script (downloads python-build-standalone,
  copies the app source into `installer/build/`, git-ignored). Both **written but
  UNVERIFIED** — Inno Setup isn't installed here, so they can't be compiled/run in
  this environment. The staging copy logic was exercised (`build.ps1 -SkipPython`
  stages the source); both files are forced ASCII-only (PowerShell 5.1 + ISCC
  misread non-ASCII-without-BOM, which first broke `build.ps1`).
- **Compiled + installed (dev machine):** the user compiled the `.iss` (Inno
  Setup 7) and ran a **Core** install — succeeded; the installed standalone env
  imports/launches `app.py` cleanly (`%LOCALAPPDATA%\Programs\Bu D3eij`). The pip
  "yellow" lines were harmless (already-satisfied / scripts-not-on-PATH). Added a
  finish-page **"Launch Bu D3eij"** checkbox (`[Run]` postinstall). Staging was
  verified end-to-end earlier (downloads Py 3.11.15; tkinter + pip import).
- **Cold-start VM test PASSED (Windows Sandbox):** on a clean Windows (no Python /
  ffmpeg / model cache) the installer ran, **only the chosen sections appeared**
  (feature-gating), and an on-demand AI model downloaded + worked. Added
  `installer/test-sandbox.ps1` to spin this up in one command. Also quieted pip's
  harmless "script not on PATH" notices in the install window
  (`--no-warn-script-location` + `--disable-pip-version-check`) — they alarmed
  without meaning anything (the app imports modules, never the console scripts).
- **ffmpeg now on-demand (`bud3eij/ffmpeg.py`):** A/V conversion, YouTube and
  Sonara no longer need a manually-installed ffmpeg — `ensure_ffmpeg()` uses a
  system one if present, else downloads a pinned static build (gyan 8.1.1
  essentials, SHA-256 + size verified, ~109 MB) into `~/.bud3eij/ffmpeg/` on first
  A/V use and prepends it to PATH; the existing `convert_av`/`download_youtube`/
  `_load_audio` paths then work unchanged (Sonara best-effort + torchaudio
  fallback). Nothing bundled/re-distributed (THIRD_PARTY/SYSTEM_REQUIREMENTS
  updated). Verified: helper returns the system ffmpeg; extraction yields
  ffmpeg.exe + ffprobe.exe; headless `[12]`.
- **Next:** confirm a torch feature (Marquee/Sonara) install on a clean VM; then
  the GitHub Releases pipeline.

### 2026-06-15 — Public-launch prep, Phase 1 start (distribution foundation)
Architecture + dependency contract for the public build (tracked in `PHASES.md`).
- **Decided:** packaging = a **feature-selective installer that builds a managed
  Python env** (embedded Python + pip-installs the chosen feature groups), not a
  monolithic PyInstaller exe — fits the on-demand + CPU-default + feature-select
  goals. Blueprint in **`docs/DISTRIBUTION.md`**.
- **Decided:** keep **PyMuPDF** (AGPL-3.0) — accept AGPL on the distributed env
  (MIT source + public repo satisfies it); no code change.
- **`requirements/` split** (the feature→dep contract the installer composes):
  `base.txt` (Core: Converter/Nexus/YouTube/ASCII — no torch), `marquee.txt`
  (rembg/onnxruntime/spandrel/transformers/timm/kornia + torch), `vanguard.txt`
  (onnxruntime/tokenizers/rapidocr/PyYAML — no torch), `sonara.txt`
  (demucs/sounddevice + torch), and `torch-cpu.txt`/`torch-cuda.txt`
  (`--index-url` pinned). Root `requirements.txt` now composes them via `-r`
  (dev "everything" install unchanged). Verified the graph resolves to 29
  packages = all 28 originals + explicit `PyYAML` (was transitive). Mapping
  cross-checked against the actual lazy imports in each `bud3eij/` module.
- **Feature-gating (`bud3eij/features.py`):** the GUI now hides a nav section +
  the Home quick-action whose feature group isn't installed, detected via
  `importlib.util.find_spec` on sentinel packages (fast — no heavy import) — so a
  Core-only install launches clean instead of crashing on a click. `show_frame`
  guards stray navigations. Tested: GUI smoke 112/0 (+3 gating checks) + headless
  `[11]`.
- **Next in Phase 1:** the embedded-Python + pip-bootstrap implementation (the
  installer itself), torch version pinning, and a GitHub Releases pipeline.

### 2026-06-15 — Public-launch prep, Phase 0 (repo readiness)
First phase of the GitHub public-launch roadmap (see `project-launch-plan.md` on
the Desktop). Decisions locked with the user: on-demand model delivery, CPU
torch default (CUDA optional), MIT license, ship v1 unsigned, Windows-only.
- **Secrets/history scan:** clean — no keys/tokens; `.gitignore` already covers
  `.venv`/`dist`/`build`/`*.log`/models/export dirs; single author in history.
- **MIT `LICENSE`** added (source code); **`THIRD_PARTY.md`** documents every
  library + on-demand model license. **Two flags surfaced:** *PyMuPDF* is
  **AGPL-3.0** (pulled by `pymupdf4llm`/`pdf2docx`) — MIT covers our source but a
  bundled `.exe` is conveyed under AGPL (public source satisfies it; decide for
  Phase 1); *UltraSharp V2* (upscaler Max) is **CC-BY-NC-SA 4.0** non-commercial —
  fine for a free build (download-on-demand, attributed), swap if ever monetized.
- **`SYSTEM_REQUIREMENTS.md`** added (Win 10+, GPU optional w/ CPU fallback,
  per-feature model download sizes — also feeds the installer + website phases).
- **Home-path scrub:** `C:\Users\Khalifa\…` removed from `CLAUDE.md` (→
  `%LOCALAPPDATA%`) and `tests/test_headless.py` (now derives ffmpeg from PATH /
  `shutil.which` + a glob of the winget dir — also fixes a portability bug).
- **`MIGRATION_PROMPT.txt`** untracked (`git rm --cached` + gitignored; local
  copy kept) — personal new-PC doc, not for the public repo.
- **Vanguard model now downloadable** (the last blocker): `vanguard._ensure_file`
  gained a SHA-256 + exact-size-verified on-demand download from `_BASE_URL`
  (Hugging Face), mirroring `fontid.py`. Local cache hashes baked into
  `VANGUARD_FILE_META`. **Pending user action:** create the HF repo and upload
  `model.onnx` + `tokenizer.json`; `_BASE_URL` is set to
  `Kha73k/bud3eij-vanguard-detector` (change the constant if a different repo name
  is used). Verified: compiles + resolves from cache with no download triggered.

### 2026-06-14 — Debounced resize reflow (v4.3.2)
Follow-up to the drag fix: window **resize** was sluggish on content-heavy tabs
(Marquee/Nexus) but fine on empty ones. **Profiled** (`cProfile` over a simulated
resize sweep): each width change drives **~500 Tcl draw calls / ~50 ms** of
CustomTkinter re-rendering (rounded-rect cards via `draw_engine`/`ctk_canvas`) —
an architecture cost, not Python-tunable. Doing that per resize-pixel (the
`ScrollArea._on_canvas` `itemconfigure(width)`) was the lag. **Fix:** `_on_canvas`
**fully defers** the width apply — during the drag it only records `_pending_w` +
resets a timer (cheap, so the `<Configure>` stream stays dense and the timer
can't fire mid-drag), applying the final width **once `_RESIZE_MS`=120 ms after
the drag settles** (`_flush_width_timer`/`_flush_width`); `_sync` calls
`_apply_pending_width()` first so page switches/tests still measure the real
width. Iterated with the user: a leading-edge apply (one reflow per burst) and
short settles (50 ms) both reintroduced mid-drag jank — the 40 ms reflow block
spaced out the event stream so the timer fired during the drag; removing the
leading apply + a 120 ms settle is smooth. This is an explicit **smooth-drag vs
live-content** trade (the ~50 ms reflow makes both impossible on busy tabs);
**user chose smooth drag + snap-on-release.** Verified: GUI smoke 109/0;
user-confirmed smooth in source. Pairs with the PMv2 drag fix below.

### 2026-06-14 — Smooth window drag in the .exe via per-monitor-v2 DPI (v4.3.1)
User report: window dragging laggy **in the rebuilt .exe** (all tabs, move +
resize), smooth from source. **Diagnosed, not guessed:** the `GradientButton`
suspend works and renders are ~2.5 ms (so not the animation); display is 100 %
(no DPI virtualization); the exe's process uses **~0 % CPU during a drag** → the
cost is Windows redrawing the *window*, not the app. Both source and exe ran at
**per-monitor-v1** awareness (set by CustomTkinter); v1 makes Tk window
drag/resize janky on Windows. **Key context:** the 2026-06-13 drag fix was
**source-only ("exe rebuild pending")** and the exe was never rebuilt until v4.3,
so the user's prior reference exe was **v4.1** (pre-fix) — this is the first exe
to even contain the drag handling, and it was still laggy. **Fix:** `app.py` sets
**`SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2 = -4)`** at the very top
(before any GUI import, with fallbacks to v1 → `SetProcessDPIAware`), so
CustomTkinter's later v1 call is a no-op. The win is largest in the frozen exe,
which has no `python.exe` manifest to set awareness. No visual change at 100 %.
**Verified:** awareness probe now reports v2; GUI smoke 109/0; **user-confirmed
dragging is smooth in the rebuilt exe.** (Resize is still relatively slow — a
separate, pre-existing ScrollArea reflow cost, not addressed here.)

### 2026-06-14 — Marquee: Image → Prompt + ASCII Art (v4.3)
Two new tools in the **Marquee** multi-tool switcher (now 4 tools), same pattern
as the existing panels (`_build_mq_<tool>` + `_show_mq_tool`); pure logic in
`bud3eij/`, re-exported from `app.py`; both also exposed as headless CLI flags.
- **Image → Prompt** (`bud3eij/imageprompt.py`): `image_to_prompt(src, mode)`
  describes an image as a detailed text-to-image prompt. A free **DETAIL** mode
  swaps the instruction (Concise = one-liner / Detailed = full prompt) — same
  model, no tier. Copy-to-clipboard, **no file output** (mirrors the Vanguard
  OCR panel: `_build_mq_imageprompt` + `on_ip_*`/`_ip_*`/`reset_imageprompt`).
  CLI: `--image-prompt FILE [Concise|Detailed]`.
  - **Model: Qwen2-VL-2B-Instruct** (Apache-2.0, **ungated**, ~4.4 GB) on torch
    CUDA in bf16 (~5–6 GB peak, fits 8 GB), loaded via `from_pretrained` into
    `HF_HOME = ~/.bud3eij/models/hf`, **revision pinned**, `unload_models()`
    wired to the Tools button. It's a **first-class transformers model (no
    `trust_remote_code`)** so it stays compatible with the project's
    `transformers>=5` pin and needs **no new pip dep or build collector**
    (transformers/torch/torchvision are already collected).
  - **Florence-2 was the original pick and was dropped:** its `trust_remote_code`
    config code crashes on transformers 5.11 (`Florence2LanguageConfig has no
    attribute 'forced_bos_token_id'` — generation attrs moved out of
    `PretrainedConfig` in transformers 5.x). Verified up front per the
    model-gating rule; not a rabbit hole — pivoted to a model that loads cleanly.
- **ASCII Art** (`bud3eij/asciiart.py`, pure PIL+numpy, **no model/download**):
  `image_to_ascii(src, width, invert)` (preview/copy/`.txt`) and
  `save_ascii(src, out, width, invert, color, overwrite)` (`.txt` or a rendered
  `.png` via a fixed character-cell grid; `color` tints glyphs from the source).
  GUI: WIDTH (80/120/160/200) + Invert + Colour, preview textbox + Copy + Save…
  (`_build_mq_ascii` + `on_asc_*`/`_asc_*`/`reset_ascii`). CLI: `--ascii FILE [WIDTH]`.
- **Verified:** headless module tests (ASCII width/invert/dedup + `.png` render;
  Image → Prompt load+caption on CUDA — confirmed a detailed, on-point prompt
  for a test scene) and a GUI wiring smoke (4 tools build/switch, CTAs are
  GradientButtons, resets clean). Added to `tests/test_headless.py` +
  `tests/test_gui_smoke.py`; exe rebuilt.

### 2026-06-14 — Theme-toggle + resize responsiveness fix (perf)
- **Diagnosed by measurement, not guesswork** (throwaway probes under
  `tools/_perf_probe*.py` + an instrumented launcher driven via real OS
  drag/resize). Findings: a same-monitor **window move is smooth** (~2 ms/event,
  `<Configure>` fires continuously and the `GradientButton._suspended` pause
  engages); both monitors are 100 % DPI so cross-monitor rescale wasn't it. The
  two real costs were the **theme toggle** (~320 ms once every page was built)
  and **window resize** (~68 ms/step, ~24 ms of it new ScrollArea churn). Root
  cause of both: CustomTkinter redraws **every registered widget across all built
  pages**, and `ScrollArea._sync` recomputed layout on every resize pixel.
- **Toggle fix — visible-page-only redraw.** `_toggle_appearance` now
  `_detach_hidden_pages()` (removes hidden built pages' widget callbacks from
  `AppearanceModeTracker.callback_list`) around the `set_appearance_mode` call,
  restores them in a `finally` (`_reattach_pages`), and flags each hidden page in
  `self._appearance_stale`. `show_frame` recolours a stale page's subtree
  (`_refresh_page_appearance`) just before showing it. **Measured 320 → ~46 ms**
  with all pages built (≈ the Converter-only cost). Supersedes the old
  Recent-rows-destroy hack. Degrades to a full redraw if CTk internals move.
- **Resize fix — coalesced ScrollArea sync.** `_on_canvas` sets only the embedded
  window *width* immediately (page keeps filling horizontally) and debounces the
  heavier `_sync` to one call per idle (`_schedule_sync`/`_run_sync`); `_sync`
  grid/grid_removes the scrollbar only when the overflow state flips
  (`self._overflow`). `to_top()` (page switch) still syncs synchronously for a
  snappy first paint.
- **Verified:** 93/93 GUI smoke tests (added 4 covering the toggle: mode flips,
  hidden pages marked stale + visible one not, no callback leak after toggle,
  stale page refreshed on show). Real-app run confirmed the toggle is visually
  instant and a page hidden during a toggle recolours correctly when reopened
  (both Dark→Light and Light→Dark).

### 2026-06-13 — Scrollable pages + Clear/Reset everywhere (v4.2.1)
- **`ScrollArea`** now hosts the page frames (root col 1): a `tk.Canvas` +
  `CTkScrollbar` + inner `CTkFrame`. Pages grid into `_scroll_area.inner` (==
  `_frame_container`) unchanged. `_sync` sets the inner window height to
  `max(canvas_h, content_reqheight)`, so pages **fill the viewport when large**
  (weight rows still expand — no visual change) and **scroll when the window is
  shrunk** below a page's natural height (scrollbar + mouse wheel). `_on_wheel`
  (single `bind_all`) no-ops unless the page overflows, so the Recent list /
  textboxes keep their own wheel. `_toggle_appearance` → `refresh_bg()` (raw
  canvas bg isn't themed); `show_frame` → `to_top()`.
- **Clear/Reset on every tool page** that lacked one (Converter + AI Detector
  already had it): YouTube, Batch, Marquee ×2, Vanguard OCR + Font, Sonara, Nexus
  Converter + QR. Outlined button via `_clear_button`; drop-zone panels share
  `_reset_image_tool`. `reset_sonara` also closes the player + bumps `_sn_run`.
- Tests: gui smoke +8 (scroll show/hide both ways, six reset handlers) → 89 green;
  headless unchanged (83).

### 2026-06-13 — Nexus polish (currency names/pegs + searchable zones)
Follow-up to the v4.2 Nexus section after a first exe build + review:
- **Currency dropdowns now show full names** (`currency_label` → `USD (US Dollar)`;
  `_code_from_label` still extracts the code) and are **typeahead-filtered** —
  3-letter codes alone were unreadable.
- **Bahraini Dinar + the other USD-pegged Gulf currencies** (BHD/AED/SAR/QAR/OMR)
  added via `USD_PEGGED` + `_augment_pegged` (derived from the USD rate at load,
  so they survive a live refresh; the ECB/Frankfurter feed doesn't publish them).
  100 USD → 37.60 BHD (peg 1 BHD = 2.65957 USD), verified.
- **Time-zone pickers are now searchable** — the full IANA set (~600) was an
  unscrollable native-menu mess. Default to a short curated list
  (`COMMON_TIMEZONES`, ~32); `_attach_search` filters the full set as you type
  (prefix-first) and restores the curated list when cleared. Shared helper
  `_attach_search(combo, get_values, on_change, get_default)` binds the
  combobox's `_entry` KeyRelease (real keystrokes fire it; synthetic test events
  need `focus_force` first). Tests added to both suites (81 GUI / 83 headless).

### 2026-06-13 — Nexus utilities section (v4.2)
New sidebar section **Nexus** — everyday utilities that are free online but
walled behind ads/sign-ins/limits, done 100% locally. Same multi-tool switcher
pattern as Marquee/Vanguard (`_build_nexus` + `self.nx_tool` segmented +
`self.nx_panels` swapped by `_show_nx_tool`). Pure logic in **`bud3eij/nexus.py`**
(lazy imports), re-exported from `app.py`; registered as a **lazy frame builder**
(per the same-day perf change) and added to `NAV_ITEMS`/`NAV_ICONS` (lucide
`compass`). Two tools:
- **Converter** (`_build_nx_convert`, `nxc_*`) — a category segmented
  (Currency / Units / Time Zone) swaps the input rows; conversions are **live**
  (debounced ~150 ms) with **Copy result** + **⇄ Swap** (no GradientButton, no
  history). *Currency*: ECB daily rates via the open **Frankfurter** endpoint
  (`api.frankfurter.dev/v1/latest`, stdlib `urllib`, needs a User-Agent), cached
  to `~/.bud3eij/nexus/rates.json` and **seeded** by a bundled snapshot
  (`assets/data/rates_seed.json`) so a fresh offline machine still converts;
  "Rates as of <date>" + **Refresh** (worker thread, WARNING-not-error if
  offline). *Units*: **`pint`** across 11 categories (temperatures with correct
  offsets). *Time Zone*: stdlib **`zoneinfo`** + the **`tzdata`** package, with a
  pinned world-clock list and a day-rollover note.
- **QR Code** (`_build_nx_qr`, `nxq_*`) — a content-type segmented
  (Text/URL · Wi-Fi · Email · Phone · SMS · vCard · Geo) swaps the fields;
  options (EC L/M/Q/H, module size, quiet-zone margin, FG/BG colour pickers,
  optional **centre logo** → auto-bumps EC to H); **live preview** (debounced);
  **Save** = a `GradientButton` (icon `qr-code`, "Generating") → PNG or **SVG**
  (worker thread + `add_history`); **Copy image** to the clipboard via pywin32
  `CF_DIB` (falls back to copying the payload text). Encoder = `qrcode[pil]`.
- **CLI**: `--qr "TEXT" [OUTFILE]`, `--convert-units "100 km to mi"`,
  `--convert-currency AMT SRC DST`, `--convert-tz "<datetime>" SRC DST`. NB the
  file converter already owns `--convert FILE FORMAT`, so the unit converter got
  its **own** flag (`--convert-units`) rather than overloading `--convert`.
- **Gotcha fixed:** `CTkLabel.configure(image=None)` after an image has been
  shown is a CustomTkinter bug ("image doesn't exist" on the *next* set), and
  `image=""` warns — the QR preview's empty state swaps in a reusable 1×1
  transparent `CTkImage` (`self._nxq_blank`) instead. Also: the `_show_*`/
  `_nxc_unit_cat_change` handlers now `.set()` their segmented/option value so
  they're correct when called programmatically (tests), not only on click.
- **Deps**: `pint`, `tzdata`, `qrcode[pil]` added to `requirements.txt`; build
  command gains `--collect-all pint tzdata qrcode` + the seed `--add-data`. No
  ML models, nothing in `~/.bud3eij/models/`, nothing for the Unload button.
- **Verified**: `tests/test_headless.py` (units incl. temperature, currency math
  + inverse, tz offset + day rollover, Wi-Fi/vCard payloads, `make_qr` → PNG that
  decodes back via cv2, SVG recolour) and `tests/test_gui_smoke.py` (Nexus nav,
  switcher, category/type swaps, live conversion, QR `GradientButton`) both green
  (79 / 77). New icons `assets/ui/compass.png` + `qr-code.png` via
  `tools/fetch_icons.py`.

### 2026-06-13 — UI responsiveness pass (tab switch / drag / theme toggle)
User reported three things: tabs slow to open, window dragging sluggish, and a
stuttery Light/Dark toggle. **Measured first** (throwaway probes timing
`show_frame`/`_toggle_appearance` with forced `update_idletasks`) — the
`GradientButton` animation was a red herring (one `_compose` ≈ **1 ms**; a first
"suspend the animation everywhere" attempt was scrapped after it made tabs/toggle
*worse*). All fixes in `app.py`, no visual/API change (`_recent_row` untouched, so
rows look identical). The four landed changes:
- **Recent `_recent_dirty` flag** (tab-open delay): the Recent table is the app's
  heaviest widget set (~12 CTk widgets/row) and was **rebuilt on every visit**
  (493 ms @14 rows, ~3.4 s @100). `_refresh_recent` now early-returns unless the
  history changed; flag set on `add_history`/`clear_history`/initial build.
  → Recent re-open **493 → ~52 ms**.
- **Lazy frame building** (toggle + startup): `_build_frames` no longer builds all
  9 frames up front — `show_frame` builds each on first visit (`_frame_builders`
  map + `_frame_container`). Since `set_appearance_mode` redraws *every* registered
  widget, only-visited frames now exist → toggle scales with what you've opened.
  → toggle right after launch (Converter only) **252 → ~38 ms**; startup lighter.
  Also `_toggle_appearance` drops hidden Recent rows first (they redraw even when
  off-screen), rebuilt lazily on next visit.
- **Drag-only animation pause** (sluggish drag): the only thing repainting the
  window during a move is the button animation (each tick swaps a `CTkImage`).
  `GradientButton._suspended` (class flag) makes `_tick` skip the compose but keep
  its timer alive; the App sets it **only on a real root move/resize** (root
  `<Configure>` with a changed `(x,y,w,h)` — never on tab switches, so no
  paint-skip regression) and clears it 130 ms after the drag settles. → smooth.
- **Flicker-free toggle** (`_frozen_redraw`): CTk recolors each widget's canvas
  with no double-buffering, so the switch visibly "swept" across the window
  ("looks like the app is reopening"). Now wraps `set_appearance_mode` in a
  Windows **WM_SETREDRAW** freeze on Tk's **content** HWND (`winfo_id()`, *not*
  `GA_ROOT` — freezing the framed window blanked the title-bar min/close buttons
  until the next OS paint), then one `RedrawWindow`. Degrades gracefully without
  pywin32. → one clean atomic flip, caption untouched.
- **`GradientButton._apply_resize` no longer nulls `_stat`:** `_ensure_static`
  already rebuilds on real `(w,h,alive)` change, so the unconditional invalidation
  forced a full static-layer rebuild on every `<Configure>` (each CTA-page show).
- **Verified:** GUI smoke 59/59; correctness probes (Recent dirty round-trip;
  4× toggle through the WM_SETREDRAW path, no errors) green; user-confirmed in the
  running app (tabs fast, drag smooth, toggle clean, title bar intact). Source-only
  change — **exe rebuild pending** (no build-command change needed; pywin32 already
  bundled).

### 2026-06-11 — v4.1: Marquee gets the GPU treatment (model audit follow-up)
User request: audit every AI model and replace each with the best free local
option, no accounts/APIs/limits — then implement the Marquee pair as v4.1.
**`APP_VERSION = "4.1"`.** Both tools now ride the torch-CUDA stack v4.0
introduced. New deps: spandrel (+ cu126 torchvision — pip's default is the CPU
wheel, force-reinstall from the cu126 index), transformers, timm, kornia.
- **Upscaler (`bud3eij/upscale.py`):** ONNX Real-ESRGAN → **UltraSharp V2 via
  spandrel** on CUDA, same public API. Measured A/B (PSNR + crops on degraded
  renders): Fast = `4x-UltraSharpV2_Lite` (RealPLKSR, 22.64 dB, ~78 ms GPU —
  beats the old *Max* by ~1.8 dB), Max = `4x-UltraSharpV2` (DAT-2, 23.42 dB).
  **Rejected after measuring:** ClearReality SPAN (fast but ringing artifacts,
  ~20.3 dB) and 4xNomos8kHAT-L (slower AND worse here, 21.5 dB; its main repo
  is also gated). SHA-256-pinned downloads unchanged in shape (4-tuples).
- **BG remover Omega (`bud3eij/background.py`):** `birefnet-general` (onnx CPU)
  → **BiRefNet_HR** (MIT, ZhengPeng7/BiRefNet_HR) on CUDA fp16 at 2048², via
  transformers `trust_remote_code` with a **pinned revision**; cache
  `HF_HOME=~/.bud3eij/models/hf`. Visual check: keeps individual hair strands
  Flash deletes; ~1.4 s warm. **RMBG-2.0 rejected:** benchmark leader but the
  HF repo is gated behind an account — violates the no-accounts rule (and
  BiRefNet_HR beats it on hair). Flash/Mid stay rembg.
- **Verified:** headless 60 checks (incl. new Omega + new upscaler contracts:
  exact dims, pad/crop, overwrite, SR-skip) + GUI smoke 59 checks, all green;
  tokenizers downgraded to 0.22.2 by transformers — Vanguard suite re-ran
  clean. Build command gained `--collect-all
  spandrel/transformers/timm/kornia/torchvision`. Exe rebuild on request.

### 2026-06-11 — v4.0: Sonara — Audio Stem Splitter (Demucs) + real-time mixer
User request (`sonara_stem_splitter_prompt.md`): new sidebar section **Sonara**
with one tool — split a song into Vocals/Drums/Bass/Other, play them back with
per-stem Mute/Solo/Volume in real time, and save the stems the user wants.
**`APP_VERSION = "4.0"`.** Decisions made with the user: **PyTorch CUDA build**
(cu126 — the app's first torch dep; htdemucs_ft ≈ seconds/song on the RTX
3070 Ti vs 15–25 min CPU; venv/exe grow ~4–5 GB, personal build) and
**htdemucs_ft only** (no tiers). Playback = **sounddevice** (one OutputStream
mixing 4 numpy arrays — sample-accurate, no drift; pygame's 4 channels share
no clock).
- **`bud3eij/sonara.py`:** PyPI demucs (4.0.1, pinned) **predates `demucs.api`**,
  so it drives `pretrained.get_model` + per-submodel `apply_model` directly
  (mirroring BagOfModels averaging) and injects a lazy **`_CountingPool`** for
  real segment-level progress (params positional-only — demucs forwards its own
  `pool=` kwarg; collided on first run). Own `_load_audio` (demucs' load_track
  `sys.exit`s); `save_stem` writes WAV via stdlib `wave` (**torchaudio 2.11
  removed `ta.save` to torchcodec** — found when saving died) and MP3 via
  lameenc. Checkpoints → `TORCH_HOME=~/.bud3eij/models/torch`;
  `model_is_cached()` first-run warning; `unload_models()` +
  `torch.cuda.empty_cache()`.
- **`bud3eij/stemplayer.py`:** `StemPlayer` — single OutputStream callback,
  DAW solo semantics, pure-numpy `_gains()`/`_mix_block()` (unit-tested without
  a device), seek/position/finished, `close()` wired into `_on_close`.
  Gotcha: Bluetooth sinks take ~1 s before the callback starts (looked like a
  stuck position in testing).
- **GUI:** Sonara nav (lucide `audio-lines`; stem icons mic/drum/guitar/music)
  → drop zone → Split Stems GradientButton (busy "Splitting") → **real**
  progress bar (counting pool) → player card: ▶/⏸, seek slider (write-guard
  flag so the 100 ms tick loop doesn't re-trigger seek), time label, 4 stem
  rows (M/S red-active toggles, volume sliders, per-stem Save → wav/mp3 +
  history). CLI `--split-stems FILE`.
- **Verified:** headless 57 checks + GUI smoke 59 checks all green; module
  verify (6 s clip split in ~6 s on CUDA incl. model load, monotonic progress,
  wav+mp3 saves); CLI smoke (4 stems next to source); a scripted GUI run
  (real split → play → live solo/mute gains → pause); panel screenshot at
  1000×680. **Exe NOT rebuilt yet** — build command gained
  `--collect-all demucs/torch/torchaudio/sounddevice --copy-metadata torch`
  (~6 GB exe; rebuild on request).

### 2026-06-10 — v3.2: Vanguard multi-tool — Text Extraction (OCR) + What's The Font
User request: two new image tools, self-contained in Vanguard — extract all text
from a screenshot/image (with copy-to-clipboard), and identify the font(s) in an
image of text. **`APP_VERSION = "3.2"`.** Vanguard now uses the same
`CTkSegmentedButton` switcher pattern as Marquee (`self.vg_tool`:
"AI Detector" / "Text Extraction" / "What's The Font", panels in `self.vg_panels`,
`_show_vg_tool`); the detector moved verbatim into `_build_vg_detector`.
- **Text Extraction (`bud3eij/ocr.py`):** `extract_text(src, model="Fast")` on
  **RapidOCR** (`rapidocr` pip pkg, Apache-2.0), running on the already-bundled
  onnxruntime. Panel `_build_vg_ocr` (`vgo_*`): drop zone → **QUALITY**
  segmented (Fast/Max) → Extract Text GradientButton → eased-fill progress →
  read-only results textbox + **Copy to clipboard** (pure Tk
  `clipboard_append`). CLI `--extract-text FILE [TIER]`.
  Verified: 2-line Inter render OCR'd at 98–99% confidence.
  **Quality tiers (added same session after user feedback — merged words +
  skipped lines):** **Fast** = PP-OCRv4 mobile det/cls/rec (~15 MB) bundled
  inside the wheel (fully offline, also reads Chinese; weakness: the ch rec
  drops English spaces). **Max** = English rec (`Rec.lang_type=EN`, ~10 MB
  one-time download into `~/.bud3eij/models/rapidocr/` via
  `Global.model_root_dir`) + `Det.box_thresh=0.4`/`Det.unclip_ratio=2.0`
  (recovers lines the default det skips/garbles) + Lanczos ~2× pre-upscale of
  images < 1600 px (BGR ndarray input). Measured on clean/blurred/dense
  samples: Max = perfect spacing, all lines, no merging, same ~2 s speed.
  **PP-OCRv4 server models tested and REJECTED** — ~10× slower and they
  fragment/skip lines on screenshot-style images.
- **What's The Font (`bud3eij/fontid.py`):** `identify_font(src, top_k=5)` on
  `storia/font-classify-onnx` (EfficientNet-B3, MIT, ~3,500 Google Fonts) —
  64 MB model + config download SHA-256-verified to `~/.bud3eij/models/fontid/`
  on first use (exact byte-size gate: a truncated 33 MB download initially passed
  a min-size check and died with INVALID_PROTOBUF). **Preprocessing must mirror
  upstream exactly:** crop (not resize) to 1024 → letterbox to 320 with a
  **white** pad → ImageNet normalise; a black pad made everything classify as
  "Zilla Slab Highlight" at 100%. Results are **closest matches** with a visible
  disclaimer (Inter → Instrument Sans 86%; Comic Sans → Poor Story 96% — sane
  lookalikes; commercial fonts can't be named exactly by any offline model).
  Panel `_build_vg_font` (`vgf_*`): drop zone → bare Identify Font
  GradientButton (no blurb card — the 5-row results card + disclaimer must fit
  the default 680px window; verified by screenshot) → 5 result rows with
  confidence bars. CLI `--identify-font FILE`.
- **Shared plumbing:** the bg-remover's `_mq_fill_*` eased fill generalised to
  per-bar `_fill_start/_fill_tick/_fill_stop`; both new tools wired into
  `_job_started/_finished` and Tools "Unload AI models"
  (`ocr.unload_models()`/`fontid.unload_models()`); new lucide icons
  `scan-text.png` + `type.png` (added to `tools/fetch_icons.py` UI list, along
  with the previously missing `shield-check`). `requirements.txt` + build
  command gained `rapidocr` / `--collect-all rapidocr` (models live in the
  wheel; the `rapidocr_onnxruntime` exclude is the legacy name — no conflict).
- **Verified:** `tests\test_headless.py` 39/39 (new OCR + font-ID checks),
  `tests\test_gui_smoke.py` 46/46 (switcher, panel swaps, read-only results box,
  copy button, 7 GradientButtons), CLI smoke of both new flags, and
  screenshot review of all three panels in dark mode. Exe **not** rebuilt this
  session (build-command change documented in CLAUDE.md).

### 2026-06-10 — v3.1.5: "dopamine" CTA redesign — GradientButton v2 on all 5 actions
User request: a crazier, dopamine-enhancing Convert button, applied to every
primary action. **`APP_VERSION = "3.1.5"`** (pure-UX pass, mirrors the 1.4.5
button precedent). The Pillow-composed `GradientButton` was redesigned and now
powers **five** CTAs: Converter "Convert Now", YouTube "Download", Marquee
"Remove Background" + "Upscale Image", Vanguard "Detect AI Text".
- **New effects:** living **lava gradient** (the body scrolls through a looping
  deep-red→red→ember-orange→hot-pink palette, `LAVA` + `_lava_strip`); an
  **orbiting comet** with a golden trail racing around the border
  (`_perimeter` path + pre-rendered `_glow_dot` sprites — no per-tick blurs);
  **rising ember sparkles**; a **click ripple** expanding from the exact press
  point; busy = lava + **flowing candy stripes** + double shine + per-button
  `busy_text` dots (Converting/Downloading/Removing/Upscaling/Detecting); and
  `stop_busy(success=True)` fires a **confetti burst + white flash** — wired
  through `_job_done(success=error is None)` so every successful job ends with
  a little celebration. Text gained a soft shadow; `icon=` picks the white-
  tinted `assets/ui` glyph (sparkles/download/shield-check).
- **Fixes folded in:** the busy state used to render on the **grey** base
  (static cache keyed on `enabled`, and busy buttons are disabled) — now keyed
  on `alive = enabled or busy`, so a running job shows the full lava look;
  out-of-canvas particles are skipped (PIL `alpha_composite` raises on
  negative coords); the 12 s idle pause is kept — clicks/celebrations reset it,
  ambient embers deliberately don't (it would never sleep), and pausing clears
  ember particles so none freeze mid-air.
- **Verified:** 7 composed state renders inspected visually (idle ×2 lava
  phases, hover, ripple, busy stripes, celebration, disabled grey); a live
  soak test drove start_busy → confetti → page switches → second button with
  zero exceptions; `tests/test_gui_smoke.py` extended to assert all five CTAs
  are GradientButtons with the right busy texts + confetti spawning (34/34
  green). Frozen exe rebuilt + boot-verified.

### 2026-06-10 — v3.1: full-codebase audit + fix pass
A complete audit of the app (hidden bugs, performance, code quality, UI/UX)
followed by an approved fix pass covering every finding. **`APP_VERSION = "3.1"`.**
No new tool; behaviour hardening + consistency. Highlights, by severity:
- **Critical — PPTX→PDF could close the user's running PowerPoint.** PowerPoint
  is *single-instance* COM, so `Dispatch` attached to an already-open PowerPoint
  and the cleanup `Quit()` closed the user's presentations. Now tries
  `GetActiveObject` first and only Quits an instance it started (`owned` flag).
- **High — DOCX→PDF rewritten as direct Word COM** (docx2pdf dropped from the
  code *and* `requirements.txt`): docx2pdf only quit Word on success, leaking a
  hidden WINWORD.EXE per failed conversion. New path: `DisplayAlerts=0`,
  `Documents.Open → SaveAs(17) → Close(0)` + `Quit()` both in `finally`.
  Verified incl. a no-leak check on a corrupt docx (`tests/test_com_paths.py`).
- **High — Vanguard file load moved off the UI thread** (`_vg_load_worker`):
  a large PDF froze the entire window during extract.
- **High — Clear/Reset races fixed with generation counters**
  (`_convert_run`/`_vg_run`): a finishing worker could resurrect status/results
  over a cleared form (Converter "Clear", Vanguard "Reset"). Stale completions
  now return early (history still recorded for conversions that completed).
- **High — save-dialog overwrite honoured:** `remove_background`/`upscale_image`
  gained `overwrite=`; when the user confirms "Replace?" in `asksaveasfilename`
  the file is actually replaced instead of silently saving `name (1).png`.
  Auto-named outputs still never clobber.
- **Medium fixes:** Recent table only rebuilds when visible (a batch used to
  rebuild a 100-row table once per file); yt-dlp progress hook throttled to
  ≥100 ms (it fires per network block and flooded the Tk queue); Tools stats
  (ffmpeg / history count) refresh on page show; `load_history` drops non-dict
  entries (a corrupt entry crashed startup); ffmpeg errors raise only the last
  ~3 stderr lines (full dump goes to stderr/log) so the status label isn't
  flooded; Vanguard overall score now weighted by **scored tokens** (char
  weights let truncated mega-chunks dominate on huge docs); upscaler skips SR
  below `_SR_MIN_GAIN=1.25×` (a full ×4 pass + ~GB RAM for a Lanczos-downscaled
  result); model downloads get a 30 s socket timeout + **SHA-256 pinning**;
  `WM_DELETE_WINDOW` warns when a job is still running (`_active_jobs`).
- **Refactor (M10):** shared `_build_drop_zone` (Converter/Batch/both Marquee
  panels), `_job_done` finish helper, `_set_image_file` validation,
  `_ask_open/_ask_save/_ask_dir` dialog wrappers that **remember the last
  folder per dialog**, `CARD_SOFT` constant, `vg_out_text` accessor.
- **UI/UX:** Home hero gained Marquee + Vanguard quick actions; Clear-history
  confirmation; Batch got a **Save to…** export folder, a read-only log, and an
  `n / N processed` counter; Vanguard input border highlights on drag-hover;
  upscaler **FIT (Pad/Crop)** selector (the dormant `fit` param implemented:
  `_fit_crop` = cover + centre-trim); accurate copy for folder drops /
  extensionless files / multi-file drops; upscaler hint lists all image types.
- **Low/quick wins:** `.tif` accepted everywhere as a `tiff` alias; animated
  GIF/WEBP/TIFF/PNG conversions keep animation (`save_all`); MP4 downloads add
  an `FFmpegVideoRemuxer` so webm-only sources still land as `.mp4`; Vanguard
  txt reads share `_read_text` (cp1252 fallback) with the converters; tk
  highlight offsets corrected for astral chars (Tcl surrogate pairs);
  `--remove-bg FILE [TIER]` + arg validation; a bare file argument opens the
  GUI preloaded; the windowed exe tees stdout/stderr to
  `%LOCALAPPDATA%\Bu D3eij\app.log` (`_setup_frozen_logging`); Tools gained
  **Unload AI models** (rembg/upscaler/vanguard `unload_models()`, ~GBs of RAM);
  GradientButton pauses its idle animation after 12 s without input (hover
  resumes) — it's the landing page, so the forever-shine was constant CPU.
- **Tests now live in the repo (`tests/`)** — the backlog item: 29-check
  `test_headless.py`, 23-check `test_gui_smoke.py`, 5-check `test_com_paths.py`
  (all green; plain scripts, run with the venv python).
- **Verified:** all three test scripts pass (57 checks total) including real
  DOCX→PDF/PPTX→PDF through the new COM paths with WINWORD leak checks, crop vs
  pad letterboxing pixels, overwrite vs de-dup paths, CLI tier/validation runs,
  and a real `--remove-bg img Flash`. **Frozen exe rebuilt + re-verified**
  (build command unchanged): `--convert note.txt pdf` → valid `%PDF`,
  `--upscale tiny.png 1080p` → exact 1920×1080, `--remove-bg tiny.png Flash` →
  RGBA PNG (new CLI tier arg works frozen), the new
  `%LOCALAPPDATA%\Bu D3eij\app.log` captures the windowed exe's output
  (session header + `Saved:` lines — `_setup_frozen_logging` works in the
  bundle), and the GUI boots with no startup crash.

### 2026-06-09 — Enhancement pass (typography, copy, .txt fix, Vanguard reset, contrast)
A multi-area polish pass on v3.0 — no new features, improvements only. Each area
was done and verified in isolation. **`APP_VERSION = "3.0.1"`** (polish bump).
- **1. Typography — Inter app-wide.** Bundled the four static Inter weights
  (Regular/Medium/SemiBold/Bold) under **`assets/fonts/`** and load them *privately*
  at startup via GDI `AddFontResourceExW(..., FR_PRIVATE)` (`_load_app_fonts`), so the
  app renders in Inter **without a system install** (works the same in the frozen exe).
  Neither Inter nor the theme's old `Roboto` was installed, so the app had silently
  been using Tk's fallback. The theme default family is now **Inter**
  (`bud3eij_theme.json` `CTkFont` → Inter; `_init_fonts` re-confirms availability at
  runtime and falls back IBM Plex Sans → Segoe UI). New `App._font(size, weight)` helper
  maps **roles → weights**: regular(400)=`Inter`, medium(500)=`Inter Medium`,
  semibold(600)=`Inter SemiBold` (Inter's heavier faces register as their own Tk
  families). Applied intentionally: **headings & CTAs → SemiBold, uppercase field
  labels/column headers/chips → Medium, body → Regular**. The Pillow-drawn
  `GradientButton` text also uses bundled Inter now. **Build command unchanged** —
  `--add-data "assets;assets"` already bundles `assets/fonts/`.
- **2. UI copy.** Home hero `Convert anything, to everything.` → **“Welcome / boss”**
  (boss in brand red), hero subtitle → **“Time to work”**; removed the sidebar
  **“Convert anything”** tagline (logo kept).
- **3. Bug fix — `.txt` input.** Root cause: `CONVERSIONS` had no `"txt"` key, so
  `.txt` was a valid *output* but never a valid *input* → `compatible_targets("txt")`
  returned `[]` → the Converter showed “Unsupported format”. Added
  `"txt": ["pdf", "docx", "md"]` to [formats.py](bud3eij/formats.py) plus three minimal,
  lazy-import converters in [converters.py](bud3eij/converters.py) — `txt_to_pdf`
  (reportlab), `txt_to_docx` (python-docx), `txt_to_md` (verbatim copy) — and their
  dispatch cases. No existing converter logic touched. Verified end-to-end (md/docx/pdf
  outputs + GUI now accepts a `.txt`, offering pdf/docx/md).
- **4. Vanguard Reset.** Added a secondary **Reset** button beside **Detect AI Text**
  (`reset_vanguard`) that clears the input, results card, highlights, score/chip,
  progress and status back to the exact initial state. Detection logic untouched.
- **5. Accessibility / contrast (light mode), WCAG AA.** Audited every fg/bg pair with
  an in-code contrast checker (`_contrast_audit.py`, throwaway). Fixes:
  - **Segmented buttons** (the Marquee/YouTube/Vanguard toggles) had `text_color` white
    in *both* modes while unselected segments were light-gray in light mode → white-on-
    light-gray (≈1.35:1, invisible). Unselected/track now a dark warm gray `#5C5457` in
    light mode (white text 7.34:1); selected stays brand red (white 4.87:1).
  - **`MUTED`** light value `#6B6164` failed on the `#DFD9DA` cards (4.28:1) → `#595155`
    (≥5.5:1 on every light surface).
  - **`"orange"` warnings** (≈1.4–2.0:1) → new `WARNING = ("#8A4500", "#F2A65A")`
    (≥5.1:1 light, ≥7:1 dark).
  - **`SUCCESS`/`ERROR`** were single colors that failed as status text in light mode
    (2.5–3.3:1); now mode-aware tuples `("#0E6E39","#3DD17F")` / `("#B30F16","#FF5C61")`
    (≥4.5:1 in both modes; large score text ≥3:1).
  - **Vanguard tier color** split into `_vg_tier_text` (mode-aware, score + status) and
    `_vg_tier_chip` (solid dark bg so the white chip text clears 4.5:1; amber chip was
    2.4:1). All pairs verified ≥4.5:1 normal / ≥3:1 large, both modes.
- **Verified:** headless import + `.txt`→md/docx/pdf; GUI smoke (Inter resolves to
  Inter/Inter Medium/Inter SemiBold, all 8 frames build/switch, Vanguard reset returns
  to initial state, Converter accepts `.txt`); light-mode screenshots of Home, Marquee,
  YouTube, Vanguard, Converter. **Frozen exe rebuilt + re-verified** (build command
  unchanged — `--add-data "assets;assets"` already bundles `assets/fonts/`): the new
  Inter TTFs + theme ship under `_internal/`, `--convert note.txt pdf` → valid `%PDF`
  (new `txt_to_pdf` + reportlab work frozen), and the windowed GUI boots with no startup
  crash (theme + private font load OK in the bundle).

### 2026-06-09 — v3.0: Vanguard — AI Text Detector
- **New third section, `Vanguard`** (AI content detection), alongside Converter and
  Marquee. First tool: an **AI Text Detector** — paste text or upload a `.txt/.docx/.pdf`,
  get an overall **AI-likelihood %**, a **confidence tier** (Human / Likely Human /
  Uncertain / Likely AI / AI), and **sentence-level highlighting** of the passages the
  model flags. New nav icon `assets/ui/shield-check.png` (drawn with PIL). `APP_VERSION
  = "3.0"`.
- **Engine (user chose "Local — Accuracy"):** `desklib/ai-text-detector-v1.01` — a
  DeBERTa-v3-large fine-tune, **#1 open model on the RAID** robustness benchmark — run on
  the already-bundled **onnxruntime** (no PyTorch at runtime). New module
  `bud3eij/vanguard.py`: `extract_document_text` (txt/docx/pdf, same engines as
  `converters.py`), `_chunk_spans` (≈3-sentence chunks, capped at 200 by merging),
  `_score_chunks` (batched, sigmoid→P(AI)), `detect_ai_text(source, is_file, progress)`
  → length-weighted overall score + per-chunk `spans`. Tokenises with the light
  **`tokenizers`** lib via the model's own `tokenizer.json`. CLI `--detect FILE`.
- **Model export (one-off dev step, `_export_vanguard.py` in a throwaway `.venv_export`
  with torch):** rebuilt desklib's custom head (backbone → mean-pool → linear → 1 logit),
  `torch.onnx.export`ed → **fp32 ONNX (~1.7 GB)**. Verified parity: fp32 ONNX matches
  PyTorch **exactly (Δ=0.0000)** and the fast tokenizer is byte-identical to HF's. Tried
  to shrink it but **fp32 is the only viable format**: dynamic **int8** drifted +0.15
  toward false positives, and **fp16 won't load in onnxruntime** for this graph
  (`Cast`/`Clip` op-type mismatches). Both rejected.
- **Personal-use only (user's call), so the 1.7 GB model is neither bundled nor hosted:**
  `model.onnx` + `tokenizer.json` sit in the local cache `~/.bud3eij/models/vanguard/`,
  which both the source app and the frozen exe load (`_ensure_file` checks `_MEIPASS`
  bundle → dev `vanguard_model/` → cache). Build command adds only **`--collect-all
  tokenizers`** (onnxruntime/numpy already collected); `requirements.txt` += `tokenizers`.
- **Known limitation (accepted):** desklib catches real AI text near-100% but **over-flags
  some genuine human writing** as AI (a casual post scored 78%, a simple student essay
  99% in testing) — the inherent false-positive problem of *every* AI detector. The UI
  leads with a **disclaimer** ("estimate, not proof") and labels borderline text
  "Uncertain"; results must never be treated as an accusation.
- **Verified:** fp32 ONNX parity (Δ=0.0000) + tokenizer match; headless `--detect` on a
  mixed file → `89% · AI`; quality probe (AI samples ≈100%, human mixed 50–99%); GUI
  build smoke (panel, tier chip, highlight tags) — frozen-exe re-verify + rebuild below.

### 2026-06-09 — v2.3.5: Marquee filling progress bars (replace back-and-forth bars)
- **Both Marquee tools now show a filling bar instead of the indeterminate
  back-and-forth one.**
- **Upscaler — real progress + live %.** `upscale_image` gained an optional
  `progress(frac)` callback (kept GUI-agnostic — invoked on the worker thread). It
  plans the per-pass tile count up front (`math.ceil(h/_TILE) * math.ceil(w/_TILE)`
  summed across the ×4 passes) and reports `tiles_done / total` per tile (via a new
  `on_tile` hook in `_sr_x4`), reserving the tail for the fit/save step and ending at
  `1.0`. `_upscale_worker` marshals each fraction back with
  `self.after(0, self._set_up_progress, frac, target, tier)`, which sets the bar and
  shows `Upscaling to <target> with <tier>…  N%`. `on_upscale_run`/`_upscale_done`
  now drive a **determinate** bar (no `start()`/`stop()`).
- **Background Remover — eased fill.** rembg's `remove()` has no progress callback, so
  a true % isn't possible; instead a timer-driven **eased fill**
  (`_mq_fill_start`/`_mq_fill_tick`/`_mq_fill_stop`) creeps the determinate bar toward
  ~90% while the worker runs and snaps to 100% on success — a filling bar, not a
  bouncing one.
- **Verified from source:** headless upscale to 4K on a tiny 4:3 input → 14 monotonic
  progress updates 0.075 → 1.0, output exactly 3840×2160; GUI smoke confirmed the bg
  eased fill creeps within (0, 0.9] and the upscaler bar/`…  42%` status update.
  Pure-UX change — no deps, version, or build-command change.

### 2026-06-09 — v2.3: Marquee Image Upscaler (Real-ESRGAN)
- **Second Marquee tool.** Marquee became a multi-tool page: `_build_marquee` now
  renders a **tool switcher** (`CTkSegmentedButton`: Background Remover / Upscaler)
  over two self-contained panels (`_build_mq_bgremover` moved the existing bg UI;
  `_build_mq_upscaler` is new), swapped by `_show_mq_tool`.
- **Image Upscaler:** drop a low-res image → pick **QUALITY** (Fast/Max) + **TARGET**
  (1080p/2K/4K) → clean, sharp upscale saved where you choose. New module
  `bud3eij/upscale.py`: `upscale_image(src, out, target, model)` runs **Real-ESRGAN**
  on the **already-bundled onnxruntime** (no PyTorch); enough ×4 passes (tiled, capped
  ×16) to exceed the fitted size, then Lanczos-fit + **letterbox** to the exact
  `TARGETS` resolution. Output always exactly W×H; PNG default; Lanczos fallback if the
  model can't load. Handlers `on_upscale_*`/`_on_up_model_change`/`_upscale_worker`/
  `_upscale_done` mirror the bg ones; indeterminate progress (CPU SR is slow toward
  4K). CLI `--upscale FILE [TARGET]`. `APP_VERSION = "2.3"`.
- **QUALITY tiers (`UPSCALE_MODELS`, default Fast):** **Fast** =
  `realesr-general-x4v3` (~4.7 MB, SRVGGNetCompact — fast, great on real low-quality
  photos); **Max** = `RealESRGAN_x4plus.fp16` (~34 MB, RRDBNet — sharper textures but
  *much* slower on CPU). Both expose float32 NCHW [0,1] I/O + exact ×4 (verified on
  onnxruntime, dynamic shape), so they share one inference path; sessions cached per
  tier in `_UPSCALE_SESSIONS`. Each downloads once to `~/.bud3eij/models/` (or a
  bundled `bud3eij/models/` copy), then caches. **Build command unchanged**
  (onnxruntime/numpy already bundled; the module rides on the static import).
  `requirements.txt`: added `numpy`/`onnxruntime` explicitly (now direct deps).
- **Verified from source:** headless `upscale_image` for 1080p/2K/4K → **exact**
  1920×1080 / 2560×1440 / 3840×2160, RGB, black letterbox bars on a 4:3 input, AI
  path used (no fallback); **both tiers** to 1080p → exact (Fast ~4.8 s, Max ~68 s,
  confirming the speed trade); GUI smoke (tool switcher swaps panels, QUALITY +
  TARGET selectors, bg remover intact, no frame regressions); `--upscale` CLI.
  **Frozen exe rebuilt + re-verified** (final build with the Fast/Max selector):
  `--upscale <img> 2K` → exact 2560×1440 PNG (onnxruntime + Real-ESRGAN model path
  work frozen, using the `~/.bud3eij/models` cache); GUI launches clean. (Killed any
  running `Bu D3eij.exe` before each build to avoid the file-lock COLLECT failure.)

### 2026-06-08 — v2.2: restructure — split logic into a `bud3eij/` package
- **Why:** ahead of growing the Marquee image-editing section, `app.py` had reached
  ~2,290 lines. A single growing file doesn't hurt the *running app* (one exe, same
  performance — load is the heavy libs, not line count) but raises edit-mistake risk
  and the cost of each change. Split now, while it's clean.
- **What moved:** the pure, GUI-free logic from `app.py` into a new package:
  `bud3eij/formats.py` (format model + helpers + `ConversionError`),
  `bud3eij/converters.py` (`convert_file` + all converters),
  `bud3eij/youtube.py` (`download_youtube`), `bud3eij/background.py`
  (`remove_background` + `BG_MODELS`). `app.py` keeps the GUI, Recent-history store,
  CLI, and `main()`, and **re-exports** the package functions so `import app;
  app.<fn>` and the CLI/tests are unaffected. Done by a one-off slice script
  (`_refactor.py`, deleted after) so code moved verbatim. `app.py`: 2,287 → 1,732
  lines.
- **Version bumped to 2.2.** No behaviour/UI change and still **one program, one
  exe** — but the restructuring is a deliberate foundation improvement for future
  additions (esp. the growing image-editing section), so it earns a version. The
  PyInstaller command is unchanged (it follows the static `from bud3eij...` imports
  and bundles the package automatically).
- **Verified from source:** all modules compile + `import app` re-exports present;
  conversions (png→jpg/webp/gif, pdf→md/txt), `remove_background` (RGBA, alpha
  0/255), GUI smoke (all 7 frames build, Marquee selector intact), and the
  `--convert`/`--remove-bg` CLI. **Frozen exe rebuilt + re-verified:** `--convert
  pdf md` → structure-aware Markdown (bud3eij.converters bundled, trap-fix intact),
  `--remove-bg` → transparent PNG (bud3eij.background + rembg bundled), GUI launches
  clean. (Build gotcha: a stale running `Bu D3eij.exe` locked the file and the first
  rebuild silently failed because a `| tail` pipe masked PyInstaller's exit code —
  killed the process and rebuilt without the pipe; confirmed a fresh exe timestamp.)

### 2026-06-08 — v2.1: Marquee model selector (Flash / Mid / Omega)
- **Quality tier selector** added to the Marquee page — a `CTkSegmentedButton`
  (Flash / Mid / Omega) with a live caption, styled like the YouTube format
  toggle. Tiers map via the new `BG_MODELS` constant to rembg models:
  **Flash** = `u2netp` (fastest, ~4.7 MB), **Mid** *(default)* =
  `isnet-general-use` (balanced — replaces the v2.0 `u2net` default with a
  moderately-better model), **Omega** = `birefnet-general` (max precision; larger
  first-run download + slower inference).
- `remove_background` gained a `model` arg (default `isnet-general-use`); sessions
  are now cached **per model** in `_REMBG_SESSIONS` (was a single
  `_REMBG_SESSION`). The GUI passes the chosen tier's model through
  `on_marquee_remove` → `_marquee_worker` → `remove_background`; the CLI
  `--remove-bg` uses the default (Mid). `APP_VERSION = "2.1"`.
- **No build-command change:** all three session classes were already bundled by
  `--collect-all rembg`; each model downloads its own `.onnx` on first use. The exe
  was rebuilt only to embed the new `app.py`.
- **Verified from source (3/3 tiers):** headless `remove_background` for `u2netp`,
  `isnet-general-use`, `birefnet-general` → RGBA output, alpha extrema (0,255),
  transparent corner / opaque subject; GUI smoke (selector renders, default Mid,
  caption updates Flash/Mid/Omega). **Frozen exe rebuilt + verified:**
  `--remove-bg` (default Mid/isnet) → RGBA transparent PNG (proves rembg's dynamic
  session loader works in the bundle); all three tier modules present under
  `_internal/rembg/sessions` (`u2netp`, `dis_general_use`, `birefnet_general`);
  GUI launches with no startup crash.

### 2026-06-08 — v2.0: Marquee — Background Remover
- **New sidebar section "Marquee"** (image editing). Added to `NAV_ITEMS`
  (before Tools), `NAV_ICONS` (`"Marquee": "sparkles"`, reusing the bundled
  `assets/ui/sparkles.png` — no new asset/icon toolchain), and the `_build_frames`
  dict. `show_frame` is generic, so the nav/active-pill highlight works unchanged.
- **First tool — Background Remover:** drop/select an image → transparent **PNG**
  saved where the user specifies (`asksaveasfilename`, default `<stem>_no-bg.png`).
  Module function `remove_background(src, out_path=None)` (rembg, `u2net` model,
  lazy import) sits outside `convert_file`/`CONVERSIONS` like `download_youtube`;
  session cached in module-level `_REMBG_SESSION`; reuses `unique_path` so it never
  clobbers. New view `_build_marquee` mirrors the converter/YouTube pages
  (drop zone via `_register_drop` + `_make_labels_wrap`, image-only validation,
  worker thread + `self.after(0, …)` marshalling, indeterminate progress bar,
  ✓/✕ status, `add_history` → shows in Recent).
- **Dep added:** `rembg` (its heavy deps — onnxruntime/numpy/opencv-python-headless
  — were already in the venv). The `u2net.onnx` model (~176 MB) downloads once on
  first run to `~/.u2net/`. `APP_VERSION = "2.0"`.
- **Verified from source (3/3):** headless `remove_background` on a generated image
  → RGBA output, alpha extrema (0,255), background corner alpha 0 / subject center
  alpha 255; GUI smoke (Marquee nav appears, page builds, active pill red, all
  frames switch with no errors, button disabled with no file); file validation
  (image enables the button, a .txt is rejected).
- **CLI:** added `--remove-bg FILE` (mirrors `--convert`/`--download`) so the
  frozen exe's background remover can be smoke-tested headlessly.
- **Exe rebuilt + verified (3/3 in the frozen build):** applied the build delta —
  dropped `--exclude-module onnxruntime`, added `--collect-all rembg
  --collect-all onnxruntime` (kept the `pymupdf.layout`/`rapidocr` excludes), and
  added **`--copy-metadata pymatting`** after the first rebuild died with *"No
  package metadata was found for pymatting"* (rembg imports pymatting, whose
  `__init__` reads its own dist-info). Frozen `--remove-bg` → transparent RGBA PNG;
  frozen `--convert doc.pdf md` → real `#` heading (pymupdf4llm structure-aware,
  proving the trap-fix survived); GUI launches with no startup crash. The u2net
  model is **not** bundled (mirrors the ffmpeg decision — downloaded/cached on
  first use). CLAUDE.md build command + notes updated to match.

### 2026-06-08 — v1.4.5: animated Convert Now button
- New `GradientButton(ctk.CTkFrame)` widget (defined just above `class App`) —
  a drop-in for the old `CTkButton` (`grid`, `command`, `configure(state=…)`),
  plus `start_busy()`/`stop_busy()`. The whole visual is composed in Pillow
  (gradient + gloss + gaussian shine band + gaussian-blurred glow + text +
  white-tinted `assets/ui/sparkles.png`) and animated by swapping a `CTkImage`
  on an inner label each tick.
- States: disabled (flat grey, no anim), idle (sweeping shine + breathing glow,
  ~20 fps), hover (brighter + glow bloom + faster shine, ~30 fps), press (dim),
  busy (double-shine flow + "Converting…" dots). Static layers are cached by
  `(w, h, enabled)`; animation only runs while mapped (pauses on `<Unmap>`,
  cancelled on `<Destroy>`) so it's idle-cheap.
- Wired into the convert flow: `on_convert_click` calls `start_busy()`,
  `_convert_done` calls `stop_busy()`.
- Verified from source (idle/hover/busy/disabled renders) and in the rebuilt
  frozen exe (renders + sparkle asset bundles under `_internal/assets/ui`).

### Earlier completed work

### 2026-06-08 — v1.4: professional visual redesign
- **Icon assets:** sourced file-type icons (vscode-icons, MIT) + UI/nav icons
  (lucide, ISC) via the Iconify API, rendered to transparent PNGs locally
  (svglib + rlPyCairo/pycairo; two-background alpha trick). Committed under
  `assets/filetypes/` + `assets/ui/` with `assets/LICENSES.md`; generator kept at
  `tools/fetch_icons.py`. Dev-only render deps (svglib/pycairo/etc.) are NOT in
  requirements and NOT bundled.
- **Icon helpers:** `icon_key_for_ext`/`EXT_ICON`, `_filetype_icon(ext,size)`
  (colored, cached), `_ui_icon(name,size,light,dark)` (alpha-tinted per theme,
  cached); `self._icon_cache`.
- **Sidebar:** logo + "Convert anything" tagline; nav buttons get leading icons;
  active state swaps to a white icon on the red pill.
- **Home (restyled):** hero headline + honest subtitle + file-icon cluster,
  quick-action buttons, **Popular conversions** cards, **Supported formats**
  showcase. Home is now a `CTkScrollableFrame`.
- **Converter:** drop zone shows the selected file's type icon.
- **Recent:** rebuilt as a table (File icon+name · From · To · Status · Time ·
  Open/Folder).
- **Palette:** added `CARD`/`CARD_BORDER`/`SURFACE_SOFT`/`TEXT`; cleaner sidebar.
- **Build:** added `--add-data "assets;assets"`. `APP_VERSION = "1.4"`.
- Verified: GUI smoke (both themes), screenshots of Home/Converter/Recent in
  light + dark.

#### Gotchas fixed during 1.4
- `show_frame` now uses **grid/grid_remove** (not `tkraise`) — a
  `CTkScrollableFrame` (Home) wouldn't raise above the plain sibling frames.
- A transparent top-level frame let the stacked sibling show through (Home must
  be opaque).
- An **empty `CTkFrame` keeps its default 200px size** — the failed-row actions
  frame stretched table rows until built only when it has buttons.

### 2026-06-08 — v1.3: YouTube downloads + sun/moon toggle
- **Sun/moon appearance toggle** (sidebar): replaced the System/Light/Dark
  `CTkOptionMenu` with a compact toggle button (`_toggle_appearance`,
  `SUN_GLYPH`/`MOON_GLYPH` in "Segoe UI Symbol"). Verified visually in both
  modes (screenshots).
- **YouTube page** (`_build_youtube`): paste a URL, pick MP4/MP3 (segmented),
  download. Asks for the save folder each time; live progress via a yt-dlp
  `progress_hook` marshalled to the UI thread; results recorded in Recent.
  `download_youtube(url, fmt, out_dir, hook)` uses yt-dlp + ffmpeg (mp3 =
  FFmpegExtractAudio 192 kbps, mp4 = bestvideo+bestaudio merged).
- **CLI `--download URL FORMAT`** added (mirrors `--convert`; enables frozen-exe
  testing of yt-dlp).
- **Dep added:** yt-dlp. Build command gains `--collect-all yt_dlp` (its ~1800
  extractors load lazily and are missed by static analysis).
- Verified: GUI smoke test (YouTube page builds, nav OK), real end-to-end
  downloads (MP3 457 KB + MP4 534 KB of "Me at the zoo"), and a visual check of
  the page. `APP_VERSION = "1.3"`.
- **Repo:** initialized git, `.gitignore` (excludes `.venv`/`dist`/`build`/
  `.claude`/`_verify_*`), pushed to the new private GitHub repo.

### 2026-06-08 — v1.2: bug fixes + cleanup
- **Drop-zone overflow (reported):** long file names spilled past the Converter
  drop-zone border (centered `inner` frame grew wider than the fixed-size zone;
  Tk doesn't clip children). Fixed with a responsive `_make_labels_wrap()`
  helper that binds the zone's `<Configure>` to set the labels' `wraplength`.
  Verified the label fits at both default and minimum window sizes (incl. a
  pathological 150-char no-space name).
- **Export-path label overflow:** long chosen folders could overflow the
  controls card; the displayed path is now shortened with a middle ellipsis via
  `_ellipsize()` (full path still used for saving).
- **Batch history race:** `_batch_worker` mutated the shared `self.history` from
  the worker thread while the UI could iterate it; history writes are now
  marshalled with `self.after(0, self.add_history, ...)` like the single path.
- **PPTX→MD tables:** `_pptx_table_to_md` now escapes `|` (and `\`) in cells so
  cell content can't break the Markdown table; `pptx_to_md` uses
  `(para.level or 0)` to avoid a crash if a bullet level is `None`.
- **Copy:** Home tagline now mentions presentations + Markdown. `APP_VERSION = "1.2"`.
- Verified headless (ellipsize + pipe-escape) and via GUI smoke tests. No new
  dependencies; no converter behaviour changed.

### 2026-06-08 — v1.1: PowerPoint + Markdown
- **New conversions:** PDF→MD, DOCX→MD, PPTX→MD, PPTX→TXT, PPTX→PDF.
  - PDF→MD via `pymupdf4llm` (rides on the already-bundled PyMuPDF), pdfplumber
    text fallback. DOCX→MD via `mammoth` (→HTML) + `markdownify` (→MD).
    PPTX→MD/TXT via `python-pptx` (slides → `## ` sections, bullets, tables,
    notes). PPTX→PDF via PowerPoint COM (`_pptx_to_pdf_powerpoint`) with a
    reportlab text-only fallback — mirrors the DOCX→PDF strategy.
- **Format model:** added `PRESENTATION_EXTS = {"pptx"}`, `md` added to
  `DOC_EXTS` (output-only — no `CONVERSIONS` key), `category_of()` now returns
  "Presentation". Home "Supported formats" card updated.
- **Deps added:** python-pptx, pymupdf4llm, mammoth, markdownify.
- **Verified (headless 5/5):** PPTX→MD/TXT/PDF, DOCX→MD, PDF→MD against
  generated samples; PPTX→PDF confirmed on both the PowerPoint-COM path and the
  reportlab fallback; CLI (`--convert deck.pptx md`) and a GUI smoke test
  (all frames build; pptx dropdown offers pdf/txt/md). `APP_VERSION = "1.1"`.
- **Exe rebuilt + verified (5/5 in the frozen build):** PDF→MD, DOCX→MD,
  PPTX→MD/TXT/PDF all produce real structure-aware output from
  `dist\Bu D3eij\Bu D3eij.exe --convert ...`.
- **PyInstaller gotcha fixed:** pymupdf4llm's `__init__` activates the
  `pymupdf.layout` ONNX feature at import time; bundling its Python without the
  models/`onnxruntime` made `import pymupdf4llm` crash → PDF→MD silently fell
  back to flat pdfplumber text. Fix = `--exclude-module pymupdf.layout
  onnxruntime rapidocr_onnxruntime` (clean ImportError → classic text engine,
  leaner exe) plus `--collect-submodules pymupdf4llm --hidden-import tabulate`.
  Build command in CLAUDE.md/README updated to match.

### 2026-06-06 — Initial build
- Scaffolded `app.py` (CustomTkinter + tkinterdnd2), `requirements.txt`, `README.md`.
- Sidebar nav (Home, Converter, Recent, Batch Convert, Tools); drag-and-drop
  + click-to-browse upload zone; auto-detect input format; compatible-only
  "Convert to"; threaded conversion with progress bar + success/error status.
- Conversions implemented and verified (8/8 headless):
  - Images: JPG/PNG/WEBP/BMP/GIF/TIFF swaps (Pillow).
  - Docs: PDF→TXT (pdfplumber), PDF→DOCX (pdf2docx), DOCX→TXT (python-docx),
    DOCX→PDF (docx2pdf via Word, reportlab fallback).
  - A/V: MP4→MP3/WAV, MP3→WAV, WAV→MP3 (ffmpeg-python).
- Environment set up: installed ffmpeg (winget Gyan.FFmpeg) and Python 3.11;
  created `.venv` on 3.11; verified GUI builds and launches.

### 2026-06-06 — Follow-up
- **Python cleanup:** uninstalled system Python 3.14.5; 3.11.9 is now the
  only/default Python. `.venv` unaffected.
- **Recent tab (functional):** persistent history in
  `%LOCALAPPDATA%\Bu D3eij\history.json`; scrollable list with per-entry
  Open / Folder buttons + Clear; records single and batch conversions.
  Verified (record/persist/reload/clear).
- **Headless CLI:** `app.py --convert FILE FORMAT` (also enables frozen-exe testing).
- **Packaged exe:** PyInstaller one-folder windowed build at
  `dist\Bu D3eij\Bu D3eij.exe` (~250 MB). All 8 conversions verified running
  inside the frozen exe; GUI launches cleanly.
- Added `CLAUDE.md` + this file.

### 2026-06-06 — Branding
- Window icon + exe icon from `AppLogo.png` (generated multi-size `AppLogo.ico`).
- In-app logo (`DashboardLogo.png`) in the sidebar header and on the Home screen.
- `resource_path()` so assets resolve in dev and inside the exe; both images
  bundled into the exe via `--icon` + `--add-data`. Verified from source; exe rebuilt.

### 2026-06-06 — UI polish (layout & UX)
- Section headers with subtitles; consistent 24px padding and rounded "cards".
- Converter: drop zone shows the app icon and, once a file is picked, its name +
  category + size ("Image · 186 B · click to choose another"); grouped controls
  card with a `CONVERT FROM → CONVERT TO` layout; progress bar only appears while
  converting; status uses ✓ / ✕ icons.
- Home: logo + tagline, **Convert a File** / **Batch Convert** quick actions, and a
  "Supported formats" card.
- Tools (was a placeholder): live FFmpeg status, history count, version, and
  "Open history folder" / "Reveal last output" buttons.
- Batch view restyled to match; drag-over highlights the drop border; drop zones
  show a pointer cursor. Window default 1000x680. Verified via screenshots.

### 2026-06-06 — UI redesign (logo palette)
- Extracted the palette from `AppLogo.png` (brand red `#E11414`/`#B4000C`,
  highlight `#F01818`) and built `bud3eij_theme.json` (recolored CustomTkinter
  theme). Default appearance is now **Dark**.
- Restyled: logo sidebar with red active-nav highlight, red section titles,
  red-bordered drop zones with drag-hover highlight, neutral dropdowns with red
  accents, bold red "Convert Now" CTA, palette-based success/error status.
- Verified visually (screenshots of all four views) and rebuilt the exe with
  the theme bundled.

### 2026-06-06 — Converter controls + shortcut
- Converter: **Choose Export Path** button (per-conversion output folder) and
  **Clear** button (reset the form). `convert_file()` gained an `out_dir` arg
  (defaults to next-to-source); single conversions honour `self.export_dir`.
- Created a **Desktop shortcut** to `dist\Bu D3eij\Bu D3eij.exe`.

## Backlog / next steps
- [ ] Optional: bundle the Marquee model(s) into the exe (`--add-data` +
      `U2NET_HOME`) so the Background Remover works fully offline on a fresh
      machine; currently each tier's `.onnx` (u2netp / isnet-general-use /
      birefnet-general) is downloaded/cached by rembg on first use, like ffmpeg.
- [ ] Optional: Marquee polish — live before/after preview thumbnail; a dedicated
      "wand"/"scissors" nav icon via `tools/fetch_icons.py`; more rembg models /
      alpha-matting toggle.
- [ ] Optional: Windows "Send to → Convert" shell entry.
- [ ] Make **Tools** tab functional (e.g. ffmpeg status check, open output folder,
      appearance settings).
- [ ] Flesh out the **Home** screen (currently a simple placeholder).
- [x] Add an **in-repo test script** (`tests/`) so verification is reproducible
      instead of ad-hoc temp scripts. _(Done in v3.1: test_headless.py,
      test_gui_smoke.py, test_com_paths.py.)_
- [ ] Optional: per-file progress for large A/V; quality/bitrate options.
- [ ] Optional: bundle ffmpeg into the exe if it ever needs to run on a PC
      without ffmpeg installed (adds ~170 MB).

## Decisions & constraints
- **Python 3.11** (not 3.14) for guaranteed wheels of the native-extension deps.
- **High-fidelity docs:** pdf2docx + docx2pdf (Word); reportlab is the text-only
  DOCX→PDF fallback when Word/COM is unavailable.
- **Exe:** one-folder (faster, more reliable for this dep set) and **windowed**;
  ffmpeg is **not** bundled (relies on system install — app is for personal use).
- Output is always saved next to the source; existing files are never
  overwritten (numbered copies instead).
- See `CLAUDE.md` for environment paths, commands, and gotchas.
