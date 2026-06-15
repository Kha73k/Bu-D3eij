# Bu D3eij — Website Plan (Phase 3)

Living plan for the marketing site. Companion to `PHASES.md`. **Status: building —
landing + changelog drafted in `website/` (Tailwind + GSAP via CDN for preview);
refining the design, then deploy.**

## Locked decisions
- **Stack:** plain **HTML + Tailwind CSS + GSAP** (ScrollTrigger) for motion.
- **Theme:** match the app — **dark-first, logo-red accent, Inter**, **iOS liquid-glass**
  (glassmorphism) surfaces.
- **Scope (v1):** a **landing page + a changelog page**.
- **Hosting:** **GitHub Pages** (free) from this repo → `https://kha73k.github.io/Bu-D3eij`
  (custom domain optional later; ~$10–12/yr is the only possible cost, not required).
- **Deploy:** GitHub Actions → Pages from a `website/` folder (no manual branch juggling).

## Hosting / deploy
- Source in top-level `website/`.
- `.github/workflows/pages.yml`: build Tailwind → upload `website/` as the Pages
  artifact on push to `main`. Enable via repo Settings → Pages → Source: GitHub Actions.
- Free + unlimited for static content. Custom domain later via a `CNAME` file.

## Brand tokens (from the app's dark theme)
| Token | Value |
|-------|-------|
| Base bg | `#141011` (deepest) / `#1A1416` |
| Surface / card | `#252022` · soft `#2B2629` |
| Accent surface (red-tinted) | `#221A1B` |
| Primary red | `#E11414` (hover `#B4000C` · bright `#F01818` · deep `#8C0008`) |
| Text | `#F2E9EA` · muted `#9C9194` |
| Success / Error / Warning | `#3DD17F` / `#FF5C61` / `#F2A65A` |
| Font | **Inter** (self-host `assets/fonts/Inter-*.ttf`, or Google Fonts) |
| Logo | `AppLogo.png` (square mark) · `DashboardLogo.png` (wordmark) |

These map into `tailwind.config` (`theme.extend.colors`) so utilities like
`bg-brand`, `text-brand`, `bg-surface`, `bg-base` are available.

## Structure
```
website/
  index.html        landing page
  changelog.html    version history (curated from CHANGELOG.md / PROGRESS.md)
  assets/           logo, screenshots, gifs, fonts
  css/styles.css    built Tailwind output (Play CDN ok while iterating)
  tailwind.config.js
.github/workflows/pages.yml   deploy to GitHub Pages
```

## Landing page sections (top → bottom)
1. **Hero** — logo, name, tagline, Download CTA + "View on GitHub", hero screenshot/looping demo
2. **Value pillars** — 100% local · no accounts · no limits · free & open-source
3. **Feature showcase** — a block (screenshot/GIF + blurb) per section: Converter · Marquee · Vanguard · Sonara · Nexus
4. **How it works** — Download → Pick your features → Done (feature-selective installer is the hook)
5. **System requirements** — Win 10+, optional NVIDIA GPU, per-feature disk (from `SYSTEM_REQUIREMENTS.md`)
6. **Download** — big CTA → GitHub Release + the SmartScreen "More info → Run anyway" note
7. **FAQ** — private? free? no Python/ffmpeg needed, GPU optional, data never leaves the device
8. **Footer** — GitHub, MIT license, third-party credits

## Changelog page
- Version history (v1.0 → current), curated from `CHANGELOG.md` + `PROGRESS.md` highlights.
- Same theme; a simple vertical timeline / version cards.

## Tailwind setup
- **Dev:** Tailwind CLI (`npx tailwindcss -i input.css -o css/styles.css --watch`) with the
  brand-token config; ships a small purged CSS for production.
- **Quick-start alt:** Tailwind Play CDN while iterating on layout, swap to the built CSS before launch.
- Fold the user's Tailwind UI component ideas into the section layouts.

## Assets to capture (from the running app)
- Clean dark-mode screenshots of each section (Home, Converter, Marquee, Vanguard, Sonara, Nexus).
- 2–3 short screen recordings → GIF/MP4 (bg removal, stem splitter, a conversion).
- Logo files (already in the repo).

## Build phases
- **A. Content + assets** — final copy + capture screenshots/GIFs.
- **B. Design** — hero + one feature-block mockup (UI/UX skill), incorporating the user's
  Tailwind UI ideas; lock the look before building everything.
- **C. Build** — section by section (`index.html`, then `changelog.html`).
- **D. Deploy** — Pages Action + wire the Download CTA to the GitHub Release.

## Design language (liquid glass — built)
- **Glass:** `backdrop-blur 14–16px`, `rgba(255,255,255,.05)` fill, hairline border, a
  top rim-light `inset 0 1px rgba(255,255,255,.18)`, soft depth shadow, 16px radius / pills.
- **Ambient:** slow-drifting red-glow "blobs" behind the glass (GSAP); warm-dark base (no pure black).
- **Primary CTA:** red glass + red glow; press `scale(.97)`.
- **Motion (GSAP + ScrollTrigger):** signature `expo.out` (`cubic-bezier(.16,1,.3,1)`); hero
  stagger + scroll reveals + a **signature animation per feature** — Converter file-flow,
  Marquee before→after clip wipe (scrubbed), Vanguard scan-sweep, Sonara equalizer, Nexus flip.
  All gated behind `prefers-reduced-motion`; smooth-scroll anchors; ≤1–2 motions per view.
- Grounded in the **ui-ux-pro-max** skill (Modern-Dark / Glassmorphism styles + animation UX rules).

## Built so far
- `website/index.html` — full landing (nav · hero · pillars · 5 feature panels with the
  signature GSAP animations · how-it-works · requirements · download · FAQ · footer).
- `website/changelog.html` — version timeline.
- `website/assets/` — logos. Tailwind + GSAP via CDN for instant preview.

## Remaining
- Replace the CSS/SVG tool mocks with **real app screenshots/GIFs**.
- **Compile Tailwind** to a small static CSS (drop the Play CDN) before launch.
- **GitHub Pages deploy** (Action from `website/`) + wire the Download CTA to the GitHub Release.
- Optional: custom domain.

## Open / user to provide
- The Tailwind UI component ideas to use.
- Screenshots/recordings (or I script the app to capture them).
- Confirm the Pages URL / whether a custom domain is wanted.
