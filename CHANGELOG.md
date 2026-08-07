# Changelog

All notable changes to MoonScribe are recorded here. 🌙

The newest version is always at the top.

## v1.3.0 — 2026-08-05

### Fixed
- **The font no longer resets when you press Enter** — including on blank lines.
  Your chosen font and size now carry through as you write, and picking a new
  size for a fresh line no longer resizes text you'd already typed.

### Added
- **Formatting shortcuts** — Bold (Ctrl+B), Italic (Ctrl+I), Underline (Ctrl+U).
- **Faster colors** — the text-color (**A**) and highlight buttons now show a
  swatch of your current color; click to re-apply it instantly, or use the **▾**
  for a palette of colors ("More colours…" is there for anything custom).
- **Gentle glyph-panel toggle** — a soft chevron centered under the glyph strip
  collapses and reopens it with one tap.
- **Columns** — Format → Insert Columns splits part of a note into 2–5
  side-by-side columns (lovely for organizing lists), with soft dividers that
  match each theme. Each column edits and selects independently.
- **Notebooks** — File → Save Notebook bundles all your open tabs into one
  portable file, and File → Open Notebook brings the whole set back together
  (MoonScribe always starts fresh — notebooks only open when you ask).
  Double-clicking a saved `.mnote` or `.mnotebook` now opens it in MoonScribe.

## v1.2.1 — 2026-08-04

### Changed
- **Pastel Moon** now shows its dreamy starry sky in the writing area too, so the
  whole window shares one soft, twinkling background. It's painted intentionally,
  so it looks the same on every computer (before, the editor could appear plain
  white or starry depending on the machine).

## v1.2.0 — 2026-08-04

### Added
- **New theme: Pastel Moon** 🌸 — a soft pink and lavender theme with gently
  double-outlined panels floating on a dreamy gradient sky full of tiny stars.
  The writing area stays calm and near-white. Pick it from the Theme menu or the
  toolbar's theme dropdown.

## v1.1.0 — 2026-08-04

### Added
- **Gentle update notice** — on launch, MoonScribe quietly checks for a newer
  version and, if one exists, shows a soft dismissible bar under the toolbar
  with a link to download it. It never installs anything itself, stays
  completely silent when you're up to date or offline, and won't nag again once
  dismissed.
- The **About** box now shows the app version.

### Changed
- Refreshed the **About** box description: "A modern rich-text editor built for
  notes, journals, stories, and everyday writing."

## v1.0.1 — 2026-08-03

### Fixed
- The **File → Exit** menu item no longer shows the word "Exit" twice. Its
  shortcut column now reads a proper `Ctrl+Q` instead of the literal text
  "Exit" that Windows was displaying.

## v1.0.0 — 2026-08-03

The first public release of MoonScribe!

### Added
- **Three calm themes** — MoonScribe Dark, Light Mode, and a starry Cosmic mode.
- **Session-only tabs** — keep several notes open at once. Tabs stay only for the
  current run, so every launch opens fresh and uncluttered.
- **Gentle rich text** — bold, italic, underline, strikethrough, alignment,
  bullet lists, fonts, sizes, text color, and highlight.
- **Emoji & symbol strips** — a curated row of emojis and celestial glyphs.
- **Autosave & recovery** — a backup is saved every 60 seconds while you have
  unsaved changes, so an unexpected shutdown won't lose your work.
- **Spell check** — with right-click suggestions; toggle on or off.
- **Native `.mnote` format** plus export to HTML, PDF, or plain text.
- **Live word & character count**, full-screen mode, and a resizable window.
