# Bu D3eij — Public Launch Phases

Living tracker for taking Bu D3eij from a private personal app to a polished
public GitHub launch. Companion to `PROGRESS.md` (chronological dev log) — this
file is the **forward-looking roadmap + status** so we don't lose the thread when
issues pull us sideways. Update the checkboxes and decision log as we go.

Roadmap origin: `project-launch-plan.md` (Desktop).

## Vision
Discover on a marketing site → download a feature-selective installer → choose
features → automated setup. Two deliverables: (1) marketing website,
(2) feature-selective Windows installer.

## Locked decisions
- **Model/dependency delivery:** on-demand (don't force a 6 GB download on everyone).
- **PyTorch:** CPU default, CUDA optional.
- **Packaging:** feature-selective installer that builds a managed Python env
  (embedded Python + pip-installs the chosen feature groups) — not a monolithic exe.
- **App license:** MIT (source). The distributed binary additionally carries
  AGPL via PyMuPDF — see flags.
- **Code signing:** ship v1 unsigned (document the SmartScreen step); revisit later.
- **Platform:** Windows only.
- **Vanguard model host:** Hugging Face — `Kha73k/bud3eij-vanguard-detector`.

## Open flags (carry until resolved)
- ✅ **PyMuPDF AGPL-3.0** — RESOLVED (2026-06-15): accept on the distributed env;
  MIT source + the public repo satisfies AGPL, no code change (via
  `pymupdf4llm` / `pdf2docx`).
- ⚠️ **UltraSharp V2 CC-BY-NC-SA** (upscaler Max tier). Fine for a free build
  (download-on-demand, attributed); swap if ever monetized.

## Phases

### Phase 0 — Repo readiness ✅ DONE (2026-06-15)
Make the repo safe + legal to be public.
- [x] Secrets / git-history scan (clean)
- [x] MIT `LICENSE`
- [x] `THIRD_PARTY.md` (libraries + on-demand models; AGPL/NC flags)
- [x] `SYSTEM_REQUIREMENTS.md`
- [x] Home-path scrub (`CLAUDE.md`, `test_headless.py`) + test portability fix
- [x] Untrack `MIGRATION_PROMPT.txt`
- [x] Host Vanguard model on HF + wire on-demand download + verify end-to-end
- [x] Committed to `launch-prep`

### Phase 1 — Distribution foundation ⏳ IN PROGRESS
A reliable, downloadable build + model/dependency delivery.
- [x] **Distribution architecture decision** → installer-builds-env
  ([`docs/DISTRIBUTION.md`](docs/DISTRIBUTION.md))
- [x] Resolve the PyMuPDF/AGPL call → accept on the binary
- [x] Feature → dependency contract (`requirements/` split + composed root)
- [ ] UI feature-gating (hide/disable a page when its group isn't installed)
- [ ] Bundle/launch implementation (embedded Python + app source + pip bootstrap)
- [ ] Pin torch versions for reproducible installs
- [ ] GitHub Releases pipeline (tag → artifact)
- Depends on: Phase 0. (ML model weights already download on demand in the app.)

### Phase 2 — Feature-selective installer ⬜ TODO
Installer where users pick features; auto-configures.
- [ ] Installer tech (Inno Setup / custom bootstrapper)
- [ ] Feature groups: Core (Converter + Nexus) · Marquee · Vanguard · Sonara
- [ ] GPU detect → CPU vs CUDA torch
- [ ] Post-install model-pack fetch + verify
- Depends on: Phase 1.

### Phase 3 — Marketing website ⬜ TODO (parallelizable after Phase 1)
Discover → motivate → download.
- [ ] Landing: hero, value prop, per-section showcase, system reqs, FAQ/privacy
- [ ] Lead with "100% local · no accounts · no limits"
- [ ] Download CTA → installer (wire after Phase 2)
- [ ] Host (GitHub Pages / Vercel)

### Phase 4 — Polish & launch ⬜ TODO
- [ ] End-to-end test on a clean Windows box (no Python / CUDA / model cache)
- [ ] Public README rewrite, `CONTRIBUTING`, issue templates
- [ ] Flip repo public → publish release → publish site → announce

## Decision log
- **2026-06-15** — Locked the five decisions above; chose Hugging Face to host the
  Vanguard model; completed Phase 0 and committed it to `launch-prep`.
- **2026-06-15** — Phase 1 kickoff: packaging = installer-builds-env; accept AGPL
  on the binary (keep PyMuPDF). Added `docs/DISTRIBUTION.md` + the `requirements/`
  feature split (base/marquee/vanguard/sonara + torch-cpu/cuda); pushed
  `launch-prep` to GitHub.
