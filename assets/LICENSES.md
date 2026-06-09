# Bundled assets

These icons were rendered to PNG (via the Iconify API) from two open-source sets.
The UI font (Inter) is bundled under `assets/fonts/` — see the bottom of this file.

## File-type icons — `assets/filetypes/`
- **Source:** [vscode-icons](https://github.com/vscode-icons/vscode-icons)
- **License:** MIT
- Icons used: pdf (`file-type-pdf2`), word, powerpoint, text, markdown, image,
  video, audio, and `default-file`.

## UI / navigation icons — `assets/ui/`
- **Source:** [Lucide](https://github.com/lucide-icons/lucide)
- **License:** ISC
- Rendered as black silhouettes and re-tinted per theme at runtime.

Both licenses are permissive (attribution preserved here). The original SVGs were
fetched from https://api.iconify.design and rasterized locally; no Iconify code is
bundled.

## UI font — `assets/fonts/`
- **Source:** [Inter](https://github.com/rsms/inter) by Rasmus Andersson (v4.1)
- **License:** SIL Open Font License 1.1 (OFL)
- Files: `Inter-Regular.ttf`, `Inter-Medium.ttf`, `Inter-SemiBold.ttf`,
  `Inter-Bold.ttf` (the `extras/ttf` static instances). Loaded privately at runtime
  (not installed system-wide). The OFL permits bundling and redistribution with
  attribution; the fonts are not sold and the "Inter" reserved name is unmodified.
