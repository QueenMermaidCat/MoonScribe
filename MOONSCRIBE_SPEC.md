# MoonScribe v1 — Build Specification

## Overview
Build a Windows desktop application called **MoonScribe**.

MoonScribe is a single-window rich text editor inspired by Notepad, designed for calm creative writing with minimal but expressive tools.

---

## Tech Stack
- Python
- PyQt6
- pyspellchecker (offline spellchecking — no cloud)

Optional later (NOT now):
- PyInstaller (for EXE packaging)

---

## Core Rules (STRICT)

- ONLY one main window
- **Session-only tabs**: multiple notes may be open at once as tabs, but ONLY
  for the current run. Every launch starts fresh with a single blank note.
  Tabs are NEVER persisted or reopened across sessions (deliberately unlike
  Notepad++). The tab strip is hidden while only one note is open, preserving
  the minimal look.
- NO AI features
- NO cloud sync
- NO extra popups unless file dialogs

Keep the app simple, stable, and fast.

---

## Main UI Layout

### 1. Menu Bar
- File — New / Open / Save / Save As / Export (Offline HTML, PDF, Plain Text) / Exit
- Edit — Undo / Redo / Cut / Copy / Paste / Select All / Word Wrap toggle
- Format — Show Glyph Panel / Theme submenu
- Help — About

### 2. Toolbar (top row)
- Font selector — grouped dropdown: ★ Favorites, Recently Used (last 10), then
  All Fonts, each entry previewed in its own face. A star toggle button beside
  it adds/removes the current font from favorites. Favorites, recents, and the
  last-used font all persist between sessions via QSettings; on launch the editor
  resumes typing in that last-used font.
- Font size dropdown
- Bold / Italic / Underline / Strikethrough (checkable toggles)
- Align left / center / right (checkable) + bullet list
- Text color picker
- Highlight color picker
- Theme dropdown (right side): MoonScribe Dark / Light Mode / Cosmic Mode
- Crescent-moon button (far right) — cycles through the themes

### 3. Emoji Bar (single-row strip under toolbar)
- Left: a "recently used" cluster (up to 8, most-recent first) that appears once
  the first emoji is used and persists between sessions (QSettings). A thin
  vertical divider separates it from the full strip.
- Right: the full scrollable emoji list (below).

- 100 emoji total, ordered by theme with mystical/space first
- Layout: one row tall, horizontally scrollable (never grows vertically)
- Button size ~32px (≈20–24 visible at the default ~900px window width; more show when wider)
- Face/emotion emoji intentionally excluded (rarely used)
- Click inserts emoji at cursor

Order: magical/mystical → gems → moons → battle → nature/plants → mythical creatures → weather → animals → objects (book/paper/key last).

Magical / mystical (incl. cosmic):
🔮 🧿 🕯️ ⚗️ ✨ 🌟 ⭐ 💫 🌠 ☄️ 🪐 🌌

Gems / treasure:
💎 💍 💠 👑

Moons (all phases, incl. every crescent):
🌑 🌒 🌓 🌔 🌕 🌖 🌗 🌘 🌙 🌚 🌛 🌜 🌝

Battle / weapons:
⚔️ 🗡️ 🛡️ 🏹 🪓 🔱 🗿 💥 🎯 🏰

Nature / plants:
🌸 🌹 🍃 🍁 🌿

Mythical creatures:
🧙 🧚 🧛 🧜 🧝 🧞 🦄 🐉 🐲

Weather / elemental (moons excluded):
☀️ 🌤️ ⛅ 🌥️ ☁️ 🌦️ 🌧️ ⛈️ 🌩️ 🌨️ ❄️ ☃️ 🌬️ 🌪️ 🌫️ 🌈 ⚡ 🔥 💧 🌊

Animals:
🐺 🦊 🦉 🦅 🐍 🦇 🕷️ 🕸️ 🦢 🐈 🦌 🐎 🦂 🐢 🦋 🦖 🐙 🦚 🦜 🐇

Objects (last):
📜 📖 🗝️

### 4. Glyph Bar (horizontal strip under the emoji bar)
A single strip two rows tall, horizontally scrollable (never grows
vertically). Glyphs fill column-major so scrolling reads left→right.
Shares the emoji-strip styling (gradient fill, violet panel line, rounded).
Hide/show via Format → "Show Glyph Panel"; no recently-used cluster.
Click inserts symbol at cursor.

Symbols — crescent moons at top, line-art next (astro/planets after the rest), colored tiles (☯ ☮ ✝ ⚜ ✡ ⚛ and zodiac) last:
☽ ☾
★ ☆ ✦ ✧ ✩ ✪ ✫ ✬ ✭ ✮ ✯ ✰ ✱ ✲ ✵ ✶ ✷ ✸ ✹ ✺ ✻ ✼ ✽ ⋆ ⁂ ❂ ❈ ❉ ❊ ❋ ⚝
✾ ✿ ❀ ❁ ❃ ⚘ ☥ ❦ ❧
☀ ☼ ☁ ☂ ☃ ❄ ☄
☉ ☿ ♀ ♁ ♂ ♃ ♄ ♅ ♆ ♇ ⚷ ⚸ ⚹ ⚚
☯ ☮ ✝ ⚜ ✡ ⚛
♈ ♉ ♊ ♋ ♌ ♍ ♎ ♏ ♐ ♑ ♒ ♓

### 5. Main Editor
- QTextEdit rich text editor
- Word wrap enabled
- Clean margins
- Smooth typing

### 6. Status Bar
- Left: custom-painted branding — a lavender crescent + "MoonScribe" logo in the
  bundled **Allura Regular** script (assets/fonts/Allura-Regular.ttf, loaded via
  QFontDatabase.addApplicationFont so it renders even when not installed; ~30px,
  normal weight, no extra italic). The logo has a left-to-right lavender gradient
  (#F2C4FB → #C39AE2 → #B48CD5) and a soft #C089EA glow, a #8976C6 divider, and a
  "A calm space for your thoughts." tagline in Segoe UI Italic (#9183C3).
- Right: live "Words: X | Characters: Y" + a full-screen toggle button

---

## File Features
- New Tab (opens a fresh blank note as a tab)
- Close Tab (Ctrl+W; the last remaining tab is replaced by a fresh blank one)
- Open (native .mnote, or import .html / .txt)
- Save / Save As → **.mnote** (native)
- Export → Offline HTML / PDF / Plain Text (one-way)
- Exit

Rules:
- **Tabs are session-only** — see Core Rules. Opening a file reuses the current
  tab when it is a pristine, untouched blank note; otherwise it opens in a new
  tab. Each tab carries its own path, unsaved state, theme canvas, word count,
  and spellcheck.
- **Prompt per unsaved tab**: closing a tab or the whole window warns
  (Save / Discard / Cancel) for each note that has unsaved changes; Cancel on
  any note aborts the close.
- **Autosave/recovery protects the active note only.** The 60-second backup and
  crash recovery cover the current tab, consistent with the session-only design.
- **Native format: `.mnote`** — the editor's own rich-text HTML written verbatim
  (no baked theme), so reopening in MoonScribe restores the note exactly and
  fully editable. Save and Save As always produce `.mnote`.
- **Open** loads `.mnote` as the editable document (Save writes back to it).
  Opening a `.html`/`.txt` imports it as a fresh note (Save routes to Save As so
  it becomes a `.mnote`, never overwriting the source).
- **Exports are one-way** and never change the current file or unsaved flag:
  - *Offline HTML* — bakes the active theme (background, text color, padding;
    Cosmic embeds the nebula as a data URI) inside `/* MOONSCRIBE-THEME-* */`
    markers, so double-clicking it opens in a browser looking like the app. The
    marker block is stripped if the file is later re-imported.
  - *PDF* — the formatted document printed to an A4 page (via QPdfWriter), for
    sharing or printing.
  - *Plain Text* — words only, no formatting.

---

## Editing Features
- Undo
- Redo
- Cut
- Copy
- Paste
- Select All
- Word wrap toggle
- Spellchecker (misspelled words underlined; right-click for suggestions; toggle on/off)

---

## Text Formatting
Toolbar:
- Font family
- Font size
- Text color
- Highlight color

Rules:
- Selected text → apply formatting
- No selection → apply to future typing

---

## Themes

Selectable from **Format → Theme** (exclusive checkable menu). Dark is the default.

### MoonScribe Dark (default)
- Dark charcoal background
- Soft silver text
- Purple accent

### Light Mode
- White background
- Dark text

### Cosmic Mode
- Editor canvas: the `MoonscribeTextbox.png` nebula artwork composited
  behind the text. Anchored in the bottom-right corner and scaled
  proportionally (KeepAspectRatioByExpanding) to fill on resize, so the
  crescent moon + orbital ring stay the visual focal point in the lower
  right. A radial vignette centered on the moon fades the artwork gently
  into a dark base (no hard edges), and a subtle dark overlay keeps text
  contrast excellent. Regenerated to fit on resize via the viewport
  palette Base brush.
- Chrome panels (toolbar, emoji bar, glyph panel, status bar): each is its
  own dark-navy vertical gradient (#030515 → #050717) outlined by a thin
  violet panel line (#301F58), with small gaps between panels. Option boxes
  (font/size/theme dropdowns) sit slightly lighter (#0F0C22 → #0A091D).
- Option text is soft white; glyph symbols are pale lavender (#C9C0E4),
  brightening toward white on hover. The glyph panel has a wider purple
  scrollbar (fill #493184, edge #A174D6).
- Dark violet accents; highlights lighter purple/navy

All three themes share the same layout, toolbar, logo status bar, and moon
button; Dark and Light use clean flat editor backgrounds (no nebula) for
maximum readability.

---

## Emoji System
- Always visible
- No popups
- Inserts at cursor

---

## Glyph System
- Dockable left panel
- Click inserts symbol
- Optional hide/show

---

## Autosave + Recovery

### Autosave
- Every 60 seconds, only while there are unsaved edits with real text
- Writes the editor HTML to a recovery file in the app-data folder
  (QStandardPaths AppDataLocation → `.../MoonScribe/MoonScribe/autosave.html`)
- The recovery copy is cleared on a real Save, on New, and on a clean exit,
  so it only survives an unexpected shutdown

### Recovery
On startup:
- If a recovery file exists → prompt: "Restore previous session?"
- If yes → load it (as an unsaved document, tied to its original path if any)
- If no → discard the recovery file

## App / Desktop Icon
- The window/taskbar icon is `MoonScribe-Icon.png` (crescent-moon artwork),
  set app-wide; a Windows AppUserModelID keeps the taskbar grouped under it.
- `assets/MoonScribe.ico` is generated from that PNG for a Desktop shortcut
  (`MoonScribe.lnk`) that launches the app windowless via pythonw.

---

## Status Bar
Words and character count live updates.

---

## UX Principles

- Minimal UI
- No clutter
- One window only
- No feature creep
- Fast typing experience

---

## Implementation Order

1. Main window + editor
2. File system
3. Toolbar
4. Emoji bar
5. Status bar
6. Glyph panel
7. Themes
8. Autosave/recovery

---

## Output Goal

A stable Windows desktop app called **MoonScribe** that is:
- Clean
- Minimal
- Creative
- Reliable
