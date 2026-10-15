# Changelog

All notable changes to MoonScribe are recorded here. 🌙

The newest version is always at the top.

## v1.4.1 — 2026-10-15

### Fixed
- **Saving a notebook no longer asks for the name every time.** Once you've
  opened or saved a notebook, **Save Notebook** writes straight back to that same
  file. There's also a new **Save Notebook As…** for when you want to save a copy
  under a different name.

## v1.4.0 — 2026-08-15

A few cozy little upgrades:

### Added
- **Expanded emoji collection.** Added more hearts, cat faces, animals, flowers,
  symbols, and other favorites.
- **Custom tab names.** Right-click any tab and select Rename to give it a custom
  name. Tab names are preserved when saving and reopening a Notebook.
- **Multi-selection formatting.** Hold Ctrl while selecting separate sections of
  text, then apply font, size, or color changes to all selected sections at once.

### Changed
- **New app icon** — a soft purple crescent moon.

## v1.3.0 — 2026-08-08

### Fixed
- **The font no longer resets when you press Enter** — including on blank lines.
  Your chosen font and size now carry through as you write, and picking a new
  size for a fresh line no longer resizes text you'd already typed.

### Changed
- **A friendlier Help box** — Help → About MoonScribe now shows a few handy,
  theme-matched tips (Tabs & Notebooks, Columns, Images, Updates & safety) in
  MoonScribe's own script font.
- The window now opens a touch wider, so each theme's moon is in view right away.

### Added
- **Formatting shortcuts** — Bold (Ctrl+B), Italic (Ctrl+I), Underline (Ctrl+U).
- **Faster colors** — the text-color (**A**) and highlight buttons now show a
  swatch of your current color; click to re-apply it instantly, or use the **▾**
  for a palette of colors ("More colours…" is there for anything custom).
- **Gentle glyph-panel toggle** — a soft chevron centered under the glyph strip
  collapses and reopens it with one tap.
- **Columns** — Format → Columns splits part of a note into 2–5 side-by-side
  columns (lovely for organizing lists), with soft dividers that match each
  theme. Each column edits and selects independently, and "Remove columns"
  takes them back to normal text (keeping your writing).
- **Notebooks** — File → Save Notebook bundles all your open tabs into one
  portable file, and File → Open Notebook brings the whole set back together
  (MoonScribe always starts fresh — notebooks only open when you ask).
  Double-clicking a saved `.mnote` or `.mnotebook` now opens it in MoonScribe.
- **Images** — Format → Insert Image (or just paste/drag one in) embeds a
  picture right in the note, so it travels with the file. Right-click an image
  to resize it with a slider or remove it — and the resize dialog matches your
  theme.

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
