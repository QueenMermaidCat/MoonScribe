"""
MoonScribe — a calm rich text editor for notes, with session-only tabs.

Build progress (see MOONSCRIBE_SPEC.md):
  [x] Step 1: Main window + editor
  [x] Step 2: File system
  [x] Step 3: Toolbar
  [x] Step 4: Emoji bar
  [x] Step 5: Status bar
  [x] Step 6: Glyph panel
  [x] Step 7: Themes
  [x] Step 8: Autosave/recovery + spellchecker
"""

import base64
import json
import math
import os
import re
import sys
import tempfile


def resource_path(*parts):
    """Absolute path to a bundled asset, working both as a script and a frozen EXE.

    PyInstaller unpacks bundled data into a temp dir it exposes as sys._MEIPASS;
    running from source, assets sit next to this file.
    """
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)

from PyQt6.QtCore import (
    QEvent,
    QMarginsF,
    QPointF,
    QRectF,
    QSettings,
    QSize,
    QSizeF,
    QStandardPaths,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QActionGroup,
    QBrush,
    QColor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QIcon,
    QKeySequence,
    QLinearGradient,
    QPageLayout,
    QPageSize,
    QPainter,
    QPainterPath,
    QPalette,
    QPdfWriter,
    QPen,
    QPixmap,
    QRadialGradient,
    QStandardItem,
    QStandardItemModel,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextListFormat,
)
from PyQt6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyledItemDelegate,
    QTabBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)

try:
    from spellchecker import SpellChecker
except Exception:  # pyspellchecker not installed — spellcheck disables gracefully.
    SpellChecker = None

# .mnote is MoonScribe's own fully-editable format (rich-text HTML on disk).
# Save/Save As always write it; HTML/PDF/TXT are one-way exports.
NATIVE_EXT = ".mnote"
SAVE_FILTER = "MoonScribe Note (*.mnote)"
OPEN_FILTER = (
    "MoonScribe & readable files (*.mnote *.html *.htm *.txt);;"
    "MoonScribe Note (*.mnote);;"
    "Web Page (*.html *.htm);;"
    "Text File (*.txt);;"
    "All Files (*)"
)

# Background artwork for the Cosmic theme, shipped alongside the script.
COSMIC_ART = resource_path("MoonscribeTextbox.png")

# App / taskbar icon (the crescent-moon artwork), shipped alongside the script.
ICON_PNG = resource_path("MoonScribe-Icon.png")

# This build's version, and where to look for newer ones.  On launch the app
# quietly asks GitHub's public API for the latest release and, if it's newer,
# shows a gentle in-app notice pointing at the releases page.  Bump APP_VERSION
# on every release so older copies out in the wild know they're behind.
APP_VERSION = "1.1.0"
GITHUB_REPO = "QueenMermaidCat/MoonScribe"
LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases/latest"


def parse_version(text):
    """Turn a tag like 'v1.2.3' into a comparable tuple (1, 2, 3).

    Returns None when there's nothing numeric to compare, and stops at the first
    non-numeric piece (so '1.2.0-beta' reads as (1, 2, 0)).  Kept deliberately
    forgiving: a weird tag simply means "don't claim there's an update".
    """
    if not text:
        return None
    cleaned = str(text).strip().lstrip("vV").strip()
    numbers = []
    for piece in cleaned.split("."):
        digits = ""
        for ch in piece:
            if ch.isdigit():
                digits += ch
            else:
                break
        if not digits:
            break
        numbers.append(int(digits))
    return tuple(numbers) if numbers else None

# Markers wrapping the theme CSS baked into saved .html, so a note opens outside
# MoonScribe looking like its theme.  file_open() strips this block so re-opening
# in the app follows the live theme instead of the baked-in one.
THEME_MARK_START = "/* MOONSCRIBE-THEME-START */"
THEME_MARK_END = "/* MOONSCRIBE-THEME-END */"
_THEME_BLOCK_RE = re.compile(
    r"\n*" + re.escape(THEME_MARK_START) + r".*?" + re.escape(THEME_MARK_END) + r"\n*",
    re.DOTALL,
)

# Bundled Allura font for the "MoonScribe" logo, so it renders identically even
# when the font isn't installed on the user's machine.  register_logo_font()
# fills this in once a QApplication exists; until then it holds the fallback.
ALLURA_FONT = resource_path("assets", "fonts", "Allura-Regular.ttf")
LOGO_FONT_FAMILY = "Allura"


def register_logo_font():
    """Load the bundled Allura font and remember its real family name.

    Must be called after the QApplication is created.  Falls back gracefully to
    a script-like family if the file is missing or fails to load.
    """
    global LOGO_FONT_FAMILY
    font_id = QFontDatabase.addApplicationFont(ALLURA_FONT)
    families = QFontDatabase.applicationFontFamilies(font_id) if font_id != -1 else []
    if families:
        LOGO_FONT_FAMILY = families[0]
    return LOGO_FONT_FAMILY


# Generated caret PNGs go in a writable temp dir (the bundle dir is read-only).
_CARET_DIR = os.path.join(tempfile.gettempdir(), "moonscribe_cache")
_caret_cache = {}


def caret_icon(color):
    """Return a QSS-friendly path to a downward chevron tinted `color`.

    Qt hides a QComboBox's native arrow once ::drop-down is styled, so we supply
    our own.  Rendered at 2x and cached per colour so it stays crisp.
    """
    if color in _caret_cache:
        return _caret_cache[color]
    scale = 2
    w, h = 14 * scale, 8 * scale
    pix = QPixmap(w, h)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.6 * scale)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    inset = 3 * scale
    path = QPainterPath()
    path.moveTo(inset, inset)
    path.lineTo(w / 2, h - inset)
    path.lineTo(w - inset, inset)
    painter.drawPath(path)
    painter.end()

    os.makedirs(_CARET_DIR, exist_ok=True)
    out = os.path.join(_CARET_DIR, "caret_" + color.lstrip("#") + ".png")
    pix.save(out)
    qss_path = out.replace("\\", "/")
    _caret_cache[color] = qss_path
    return qss_path

# Emoji ordered by theme (see MOONSCRIBE_SPEC.md):
# magical/mystical, gems, moons, battle, mythical creatures, weather, animals, nature.
EMOJIS = [
    # Magical / mystical (incl. cosmic)
    "🔮", "🧿", "🕯️", "⚗️",
    "✨", "🌟", "⭐", "💫", "🌠", "☄️", "🪐", "🌌",
    # Gems / treasure
    "💎", "💍", "💠", "👑",
    # Moons (all phases, incl. every crescent)
    "🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘", "🌙", "🌚", "🌛", "🌜", "🌝",
    # Battle / weapons
    "⚔️", "🗡️", "🛡️", "🏹", "🪓", "🔱", "🗿", "💥", "🎯", "🏰",
    # Nature / plants
    "🌸", "🌹", "🍃", "🍁", "🌿",
    # Mythical creatures
    "🧙", "🧚", "🧛", "🧜", "🧝", "🧞", "🦄", "🐉", "🐲",
    # Weather / elemental (moons excluded)
    "☀️", "🌤️", "⛅", "🌥️", "☁️", "🌦️", "🌧️", "⛈️", "🌩️", "🌨️",
    "❄️", "☃️", "🌬️", "🌪️", "🌫️", "🌈", "⚡", "🔥", "💧", "🌊",
    # Animals
    "🐺", "🦊", "🦉", "🦅", "🐍", "🦇", "🕷️", "🕸️", "🦢", "🐈",
    "🦌", "🐎", "🦂", "🐢", "🦋", "🦖", "🐙", "🦚", "🦜", "🐇",
    # Objects (at the very end)
    "📜", "📖", "🗝️",
]

# Glyphs for the dockable left panel (see MOONSCRIBE_SPEC.md).
GLYPHS = [
    # Crescent moons stay at the top.
    "☽", "☾",
    # Line-art glyphs (calm, monochrome aesthetic).
    # Stars / sparkles
    "★", "☆", "✦", "✧", "✩", "✪", "✫", "✬", "✭", "✮", "✯", "✰",
    "✱", "✲", "✵", "✶", "✷", "✸", "✹", "✺", "✻", "✼", "✽",
    "⋆", "⁂", "❂", "❈", "❉", "❊", "❋", "⚝",
    # Flowers / ornaments
    "✾", "✿", "❀", "❁", "❃", "⚘", "☥", "❦", "❧",
    # Sky / weather
    "☀", "☼", "☁", "☂", "☃", "❄", "☄",
    # Planets / astro (rendered with an underline mark by the system font)
    "☉", "☿", "♀", "♁", "♂", "♃", "♄", "♅", "♆", "♇",
    "⚷", "⚸", "⚹", "⚚",
    # --- Colored emoji-style tiles pushed to the end for aesthetics ---
    # Symbols group; ⚜ yellow tile, ✡ / ⚛ purple tiles (⚛ last, next to zodiac)
    "☯", "☮", "✝", "⚜", "✡", "⚛",
    # Zodiac (render as purple tiles) — last
    "♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓",
]

# Color palettes for the three themes (see MOONSCRIBE_SPEC.md).
# The chrome (menus/toolbars/panels/status bar) uses a subtle vertical gradient
# from chrome_top to chrome_bottom.  "cosmic" flags the theme whose editor shows
# a painted nebula scene instead of a flat background.
DEFAULT_THEME = "MoonScribe Dark"
THEMES = {
    "MoonScribe Dark": {
        "chrome_top": "#242430",
        "chrome_bottom": "#191921",
        "chrome_fg": "#d6d6df",
        "muted": "#8a8a98",
        "editor_bg": "#202027",
        "editor_fg": "#e2e2ea",
        "placeholder": "#7a7a88",
        "button_hover": "#3a2f5c",
        "accent": "#7a63c4",
        "sel_bg": "#6a53a6",
        "sel_fg": "#ffffff",
        "scrollbar": "#55556a",
        "scrollbar_hover": "#8a8aa2",
        "surface": "#1e1e28",       # elevated panels (emoji/glyph)
        "border": "rgba(160,150,205,0.12)",  # soft, low-contrast hairline
        "glyph_fg": "#d6d6df",
        "glyph_fg_hover": "#ffffff",
        "cosmic": False,
    },
    "Light Mode": {
        "chrome_top": "#fbfbfe",
        "chrome_bottom": "#ececf3",
        "chrome_fg": "#26262c",
        "muted": "#7a7a86",
        "editor_bg": "#ffffff",
        "editor_fg": "#1c1c22",
        "placeholder": "#9a9aa6",
        "button_hover": "#e3e1ef",
        "accent": "#8a74d6",
        "sel_bg": "#c8bbef",
        "sel_fg": "#1c1c22",
        "scrollbar": "#c4c4d0",
        "scrollbar_hover": "#9a9aac",
        "surface": "#f4f4f9",
        "border": "rgba(40,30,70,0.12)",
        "glyph_fg": "#26262c",
        "glyph_fg_hover": "#111114",
        "cosmic": False,
    },
    "Cosmic Mode": {
        "chrome_top": "#151a38",
        "chrome_bottom": "#0a0c1e",
        "chrome_fg": "#ffffff",  # soft white option text on the dark panels
        "muted": "#9a92c4",
        "editor_bg": "#111226",  # fallback behind the painted scene
        "editor_fg": "#ece8fb",
        "placeholder": "#8f88bf",
        "button_hover": "#282162",
        "accent": "#6a56b0",
        "sel_bg": "#6d5aa8",
        "sel_fg": "#ffffff",
        "scrollbar": "#493184",
        "scrollbar_hover": "#a174d6",
        "surface": "#141634",
        "border": "rgba(140,120,215,0.16)",
        "glyph_fg": "#c9c0e4",   # pale lavender glyphs
        "glyph_fg_hover": "#ffffff",
        "cosmic": True,
    },
}


class HorizontalScrollArea(QScrollArea):
    """A scroll area whose mouse wheel scrolls sideways, never up/down."""

    def wheelEvent(self, event):
        bar = self.horizontalScrollBar()
        # Use whichever wheel axis moved; most mice only report vertical.
        delta = event.angleDelta().y() or event.angleDelta().x()
        bar.setValue(bar.value() - delta)
        event.accept()


class BrandingLabel(QWidget):
    """Custom-painted footer branding:  🌙 MoonScribe | tagline.

    "MoonScribe" is drawn in the bundled Allura script with a left-to-right
    lavender gradient and a soft (non-blurry) glow; the crescent shares the same
    palette.  Painting it ourselves keeps the gradient crisp at any scale.
    """

    GRAD_START = "#f2c4fb"   # light highlight
    GRAD_MID = "#c39ae2"     # main lavender
    GRAD_END = "#b48cd5"     # darker end
    GLOW = "#c089ea"
    DIVIDER = "#8976c6"
    TAGLINE = "#9183c3"

    MOON_GAP = 8      # space between crescent and logo
    DIV_GAP = 14      # space on each side of the divider
    PAD = 6           # left/right breathing room

    def __init__(self):
        super().__init__()
        self._logo_text = "MoonScribe"
        self._tag_text = "A calm space for your thoughts."

        # Allura is naturally slanted, so no extra italic and a normal weight.
        self._logo_font = QFont(LOGO_FONT_FAMILY)
        self._logo_font.setPixelSize(30)
        self._logo_font.setWeight(QFont.Weight.Normal)

        self._tag_font = QFont("Segoe UI")
        self._tag_font.setPixelSize(15)
        self._tag_font.setItalic(True)

    def _moon_diameter(self):
        return QFontMetricsF(self._logo_font).ascent() * 0.92

    def sizeHint(self):
        lm = QFontMetricsF(self._logo_font)
        tm = QFontMetricsF(self._tag_font)
        width = (
            self.PAD
            + self._moon_diameter() + self.MOON_GAP
            + lm.horizontalAdvance(self._logo_text)
            + self.DIV_GAP + self.DIV_GAP
            + tm.horizontalAdvance(self._tag_text)
            + self.PAD
        )
        height = max(lm.height(), tm.height(), self._moon_diameter()) + 8
        return QSize(int(width) + 2, int(height))

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        mid = self.height() / 2.0
        x = float(self.PAD)

        moon_d = self._moon_diameter()
        self._paint_moon(painter, x, mid, moon_d)
        x += moon_d + self.MOON_GAP

        lm = QFontMetricsF(self._logo_font)
        logo_w = lm.horizontalAdvance(self._logo_text)
        logo_baseline = mid + (lm.ascent() - lm.descent()) / 2.0
        self._paint_logo(painter, x, logo_baseline, logo_w)
        x += logo_w + self.DIV_GAP

        tm = QFontMetricsF(self._tag_font)
        div_h = tm.ascent() * 0.95
        pen = QPen(QColor(self.DIVIDER))
        pen.setWidthF(1.4)
        painter.setPen(pen)
        painter.drawLine(QPointF(x, mid - div_h / 2), QPointF(x, mid + div_h / 2))
        x += self.DIV_GAP

        painter.setFont(self._tag_font)
        painter.setPen(QColor(self.TAGLINE))
        tag_baseline = mid + (tm.ascent() - tm.descent()) / 2.0
        painter.drawText(QPointF(x, tag_baseline), self._tag_text)
        painter.end()

    def _lavender(self, x0, x1):
        grad = QLinearGradient(x0, 0, x1, 0)
        grad.setColorAt(0.0, QColor(self.GRAD_START))
        grad.setColorAt(0.5, QColor(self.GRAD_MID))
        grad.setColorAt(1.0, QColor(self.GRAD_END))
        return grad

    def _paint_logo(self, painter, x, baseline, width):
        painter.setFont(self._logo_font)
        # Soft halo: the same text behind, faint and lightly offset — a gentle
        # glow rather than a blur.
        glow = QColor(self.GLOW)
        glow.setAlpha(38)
        painter.setPen(glow)
        for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            painter.drawText(QPointF(x + dx, baseline + dy), self._logo_text)
        # Left-to-right lavender gradient fill.
        painter.setPen(QPen(QBrush(self._lavender(x, x + width)), 0))
        painter.drawText(QPointF(x, baseline), self._logo_text)

    def _paint_moon(self, painter, x, mid, diameter):
        r = diameter / 2.0
        cx, cy = x + r, mid
        outer = QPainterPath()
        outer.addEllipse(QPointF(cx, cy), r, r)
        inner = QPainterPath()
        inner.addEllipse(QPointF(cx + r * 0.55, cy - r * 0.22), r, r)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._lavender(x, x + diameter)))
        painter.drawPath(outer.subtracted(inner))


class _FontListDelegate(QStyledItemDelegate):
    """Keeps the dropdown rows evenly spaced and draws real section dividers.

    Preview faces vary wildly in height, so without a fixed size hint the rows
    bunch up unevenly once favorites/recents are added.  Separator rows carry no
    text — this delegate paints a thin line for them instead of a blank gap.
    """

    _SEP_ROLE = Qt.ItemDataRole.AccessibleDescriptionRole

    def sizeHint(self, option, index):
        if index.data(self._SEP_ROLE) == "separator":
            return QSize(0, 9)
        return QSize(0, 26)

    def paint(self, painter, option, index):
        if index.data(self._SEP_ROLE) == "separator":
            painter.save()
            mid = option.rect.center().y()
            painter.setPen(QPen(QColor("#3a2c63")))
            painter.drawLine(option.rect.left() + 10, mid, option.rect.right() - 10, mid)
            painter.restore()
            return
        super().paint(painter, option, index)


class FontPickerComboBox(QComboBox):
    """Font selector grouped into ★ Favorites, Recently Used, and All Fonts.

    Section titles are non-selectable header rows; each real entry previews in
    its own font and carries the family name in UserRole.  Emits fontSelected
    only for genuine user picks (not programmatic sync).
    """

    fontSelected = pyqtSignal(str)
    _FAMILY_ROLE = Qt.ItemDataRole.UserRole

    def __init__(self, favorites, recents):
        super().__init__()
        self.setMinimumWidth(168)
        self.setMaxVisibleItems(20)
        self.setItemDelegate(_FontListDelegate(self))
        self._item_model = QStandardItemModel(self)
        self.setModel(self._item_model)
        self._all_families = [
            f for f in QFontDatabase.families() if not f.startswith(("@", "."))
        ]
        self.set_lists(favorites, recents)
        self.activated.connect(self._on_activated)

    def set_lists(self, favorites, recents):
        """Rebuild the grouped model from the given favorite/recent lists."""
        self._item_model.blockSignals(True)
        self._item_model.clear()
        if favorites:
            self._add_header("\N{BLACK STAR}  Favorites")
            for fam in favorites:
                self._add_font(fam)
            self._add_separator()
        if recents:
            self._add_header("Recently Used")
            for fam in recents:
                self._add_font(fam)
            self._add_separator()
        self._add_header("All Fonts")
        for fam in self._all_families:
            self._add_font(fam)
        self._item_model.blockSignals(False)
        # Never leave a (non-selectable) header row showing as the value.
        for row in range(self._item_model.rowCount()):
            if self._item_model.item(row).data(self._FAMILY_ROLE):
                self.setCurrentIndex(row)
                break

    def _add_header(self, text):
        item = QStandardItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)  # non-selectable, greyed
        font = item.font()
        font.setBold(True)
        font.setUnderline(True)
        item.setFont(font)
        self._item_model.appendRow(item)

    def _add_separator(self):
        item = QStandardItem()
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        # _FontListDelegate draws a horizontal line for rows tagged this way.
        item.setData("separator", Qt.ItemDataRole.AccessibleDescriptionRole)
        self._item_model.appendRow(item)

    def _add_font(self, family):
        item = QStandardItem(family)
        item.setFont(QFont(family))  # preview in its own face
        item.setData(family, self._FAMILY_ROLE)
        self._item_model.appendRow(item)

    def _on_activated(self, index):
        family = self.itemData(index, self._FAMILY_ROLE)
        if family:
            self.fontSelected.emit(family)

    def current_family(self):
        return self.itemData(self.currentIndex(), self._FAMILY_ROLE)

    def set_current_family(self, family):
        """Select the first row matching `family` without emitting fontSelected."""
        for row in range(self._item_model.rowCount()):
            if self._item_model.item(row).data(self._FAMILY_ROLE) == family:
                self.setCurrentIndex(row)
                return


class SpellHighlighter(QSyntaxHighlighter):
    """Underlines misspelled words with a red wavy line as an overlay layer.

    The formatting is a highlight layer, not document content, so it never ends
    up in saved HTML.  The owning MoonScribe supplies the checker and on/off
    state, letting a menu toggle simply rehighlight to show or clear the marks.
    """

    _WORD_RE = re.compile(r"[A-Za-z][A-Za-z']*")

    def __init__(self, document, owner):
        super().__init__(document)
        self._owner = owner

    def highlightBlock(self, text):
        checker = self._owner._spell
        if checker is None or not self._owner._spell_enabled:
            return
        fmt = QTextCharFormat()
        fmt.setUnderlineColor(QColor("#e0564f"))
        fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        for match in self._WORD_RE.finditer(text):
            word = match.group()
            if len(word) < 2:
                continue
            if word.lower() not in checker:
                self.setFormat(match.start(), len(word), fmt)


class MoonScribe(QMainWindow):
    def __init__(self):
        super().__init__()
        # Roomy default; the writing area gets the extra space. The window can
        # still be dragged down to a 700px minimum before it stops narrowing.
        # Clamp to the screen so it never opens larger than a small display.
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen is not None else None
        default_w = min(950, avail.width()) if avail else 950
        default_h = min(880, avail.height()) if avail else 880
        self.resize(default_w, default_h)
        self.setMinimumWidth(min(700, default_w))

        # Session-only tabs: several notes can be open at once, but they're
        # never restored across launches — every start begins with one blank
        # tab.  Each tab is its own QTextEdit carrying its own path/state; the
        # `editor` property below always points at the current tab, so the rest
        # of the app keeps talking to "the editor" exactly as before.
        self._wrap_mode = QTextEdit.LineWrapMode.WidgetWidth  # word wrap on
        self._highlighters = []  # one spell highlighter per open editor

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        # We supply our own themed close (×) button per tab instead of the
        # style's default light-grey box, so leave tabsClosable off here.
        self.tabs.setTabsClosable(False)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # A slim "update available" notice lives just above the editor, tucked
        # under the toolbars.  It stays hidden unless the launch-time check finds
        # a newer release, so the calm layout is untouched the rest of the time.
        self._update_bar = self._make_update_bar()
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._update_bar)
        central_layout.addWidget(self.tabs)
        self.setCentralWidget(central)

        # Persisted font preferences (favorites + recently used).
        self.RECENT_MAX = 10
        self._settings = QSettings("MoonScribe", "MoonScribe")
        self._fav_fonts = list(self._settings.value("fonts/favorites", []) or [])
        self._recent_fonts = list(self._settings.value("fonts/recent", []) or [])
        self._last_font = self._settings.value("fonts/last", "") or ""

        # The document's base font: what blank lines and un-formatted text fall
        # back to.  Kept in step with toolbar picks (when nothing is selected)
        # and pushed onto the document as its default, so clicking into an
        # unwritten line never snaps the toolbar — or the next keystrokes — back
        # to the tiny built-in default face.
        self._base_font = QFont()
        self._base_font.setPointSize(12)  # applied to each editor's document

        # Recently used emojis, shown as a cluster at the left of the emoji bar.
        self.EMOJI_RECENT_MAX = 8
        self._recent_emojis = list(self._settings.value("emojis/recent", []) or [])

        # Restore the last-used theme, falling back to the default if unknown.
        saved_theme = self._settings.value("theme", DEFAULT_THEME)
        self._current_theme = saved_theme if saved_theme in THEMES else DEFAULT_THEME
        self._canvas_size = None  # last size the cosmic scene was painted at
        self._cosmic_art = QPixmap(COSMIC_ART)  # null if the file is missing

        # Spellchecker: a red wavy underline overlay plus right-click suggestions.
        self._spell = SpellChecker() if SpellChecker is not None else None
        self._spell_enabled = self._spell is not None
        # Each tab's editor gets its own highlighter + context menu in _new_editor.

        # Autosave / crash recovery bookkeeping.
        appdata = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
        self._recovery_path = os.path.join(appdata, "autosave.html")

        # Open the first blank tab now, so the rest of setup has a live editor.
        self._add_tab()

        self._build_menu()
        self._build_toolbar()
        self._build_emoji_bar()
        self._build_glyph_bar()
        self._build_status_bar()
        self._build_theme_menu()
        self._apply_theme(self._current_theme)
        # Crescent-moon artwork for the title bar / taskbar (falls back to the
        # painted crescent if the image is missing).
        icon = QIcon(ICON_PNG)
        self.setWindowIcon(icon if not icon.isNull() else self._moon_icon("#c9b9f5"))
        self._update_title()
        # (Per-editor signals — modification, format sync, counts, spellcheck —
        #  are wired up in _new_editor when each tab is created.)
        # Start typing in the last font used, so it carries across sessions.
        self._restore_last_font()

        # Autosave a recovery copy every 60 seconds while there are edits.
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(60_000)
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start()
        # Offer to restore a leftover recovery file once the window is up.
        QTimer.singleShot(0, self._maybe_recover)
        # A moment later, quietly check GitHub for a newer release.  Fully silent
        # if offline or if we're already current — it never blocks or nags.
        QTimer.singleShot(1500, self._check_for_update)

    # ---- Tabs (session-only) ----------------------------------------------
    # The whole app is written against `self.editor`; making it a property that
    # returns the current tab's QTextEdit means every existing feature keeps
    # working while operating on whichever note is in front.  Per-note bits
    # (file path, import name) live on the editor object itself.
    @property
    def editor(self):
        return self.tabs.currentWidget()

    @property
    def current_path(self):
        e = self.editor
        return e._path if e is not None else None

    @current_path.setter
    def current_path(self, value):
        e = self.editor
        if e is not None:
            e._path = value

    @property
    def _suggested_name(self):
        e = self.editor
        return e._suggested if e is not None else None

    @_suggested_name.setter
    def _suggested_name(self, value):
        e = self.editor
        if e is not None:
            e._suggested = value

    def _all_editors(self):
        return [self.tabs.widget(i) for i in range(self.tabs.count())]

    def _new_editor(self):
        """Build a fully wired editor for a new tab (same setup the single
        editor used to get, plus its own path/state and spell highlighter)."""
        editor = QTextEdit()
        editor.setFrameShape(QFrame.Shape.NoFrame)
        editor.setLineWrapMode(self._wrap_mode)
        editor.setPlaceholderText("Begin writing…")
        editor.document().setDocumentMargin(36)
        editor.document().setDefaultFont(self._base_font)

        # Per-note state (mirrors the old self.current_path / _suggested_name).
        editor._path = None
        editor._suggested = None

        # Right-click spelling suggestions for this note.
        editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        editor.customContextMenuRequested.connect(
            lambda pos, e=editor: self._editor_context_menu(e, pos)
        )
        editor._highlighter = SpellHighlighter(editor.document(), self)
        self._highlighters.append(editor._highlighter)

        # Repaint the cosmic scene whenever this note's writing area resizes.
        editor.viewport().installEventFilter(self)
        editor.document().modificationChanged.connect(
            lambda _=False, e=editor: self._on_modified_changed(e)
        )
        editor.currentCharFormatChanged.connect(self._sync_toolbar)
        editor.textChanged.connect(self._update_counts)

        # A brand-new note is pristine: setting the default font and attaching
        # the spell highlighter can dirty the document, so clear that here.
        # Otherwise every empty tab would falsely prompt "unsaved changes".
        editor.document().setModified(False)
        return editor

    def _add_tab(self, make_current=True):
        """Create a fresh blank tab and (by default) switch to it."""
        editor = self._new_editor()
        index = self.tabs.addTab(editor, "Untitled")
        self._install_close_button(editor, index)
        self._apply_editor_appearance_one(editor, THEMES[self._current_theme])
        if make_current:
            self.tabs.setCurrentIndex(index)
        self._update_tabbar_visibility()
        return editor

    def _close_icon(self, color):
        """A small, theme-coloured × drawn to match the tab text."""
        size = 16
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(color))
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        m = 4.5
        painter.drawLine(QPointF(m, m), QPointF(size - m, size - m))
        painter.drawLine(QPointF(size - m, m), QPointF(m, size - m))
        painter.end()
        return QIcon(pixmap)

    def _install_close_button(self, editor, index):
        """Give each tab our own × button so its colour follows the theme."""
        button = QToolButton()
        button.setObjectName("tabClose")
        button.setAutoRaise(True)
        button.setFixedSize(18, 18)
        button.setIconSize(QSize(11, 11))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip("Close tab")
        button.setIcon(self._close_icon(THEMES[self._current_theme]["chrome_fg"]))
        button.clicked.connect(
            lambda _=False, e=editor: self._close_tab(self.tabs.indexOf(e))
        )
        editor._close_btn = button
        self.tabs.tabBar().setTabButton(index, QTabBar.ButtonPosition.RightSide, button)

    def _refresh_close_buttons(self, color):
        for editor in self._all_editors():
            button = getattr(editor, "_close_btn", None)
            if button is not None:
                button.setIcon(self._close_icon(color))

    def _update_tabbar_visibility(self):
        """Keep the minimal look: the tab strip only appears with 2+ notes."""
        self.tabs.tabBar().setVisible(self.tabs.count() > 1)

    def _update_tab_label(self, editor):
        index = self.tabs.indexOf(editor)
        if index < 0:
            return
        if editor._path:
            name = os.path.basename(editor._path)
        elif editor._suggested:
            name = editor._suggested
        else:
            name = "Untitled"
        marker = "*" if editor.document().isModified() else ""
        self.tabs.setTabText(index, f"{marker}{name}")

    def _on_tab_changed(self, index):
        editor = self.editor
        if editor is None:
            return
        self._update_counts()
        self._update_title()
        self._sync_toolbar(editor.currentCharFormat())
        if THEMES[self._current_theme]["cosmic"]:
            editor._canvas_size = None
            self._refresh_cosmic_canvas(editor, force=True)
        editor.setFocus()

    def _on_modified_changed(self, editor):
        self._update_tab_label(editor)
        if editor is self.editor:
            self._update_title()

    def _target_editor_for_open(self):
        """Open into the current tab if it's pristine (blank + unsaved),
        otherwise open the file in a new tab."""
        e = self.editor
        if (
            e is not None
            and e._path is None
            and not e.document().isModified()
            and not e.toPlainText().strip()
        ):
            return e
        return self._add_tab()

    def _close_current_tab(self):
        self._close_tab(self.tabs.currentIndex())

    def _close_tab(self, index):
        editor = self.tabs.widget(index)
        if editor is None:
            return
        if not self._confirm_close_editor(editor):
            return
        if editor._highlighter in self._highlighters:
            self._highlighters.remove(editor._highlighter)
        self.tabs.removeTab(index)
        editor.deleteLater()
        # Never leave zero tabs — closing the last note opens a fresh blank one.
        if self.tabs.count() == 0:
            self._add_tab()
        self._update_tabbar_visibility()

    def _confirm_close_editor(self, editor):
        """Return True if this note is safe to close (saved, discarded, or had
        no unsaved changes).  Warns for THIS note specifically."""
        if not editor.document().isModified():
            return True
        self.tabs.setCurrentWidget(editor)  # show what's being decided on
        choice = QMessageBox.warning(
            self,
            "MoonScribe",
            "This note has unsaved changes. Save them?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if choice == QMessageBox.StandardButton.Save:
            return self.file_save()
        if choice == QMessageBox.StandardButton.Discard:
            return True
        return False  # Cancel

    # ---- Menu construction -------------------------------------------------
    def _build_menu(self):
        file_menu = self.menuBar().addMenu("&File")
        self._add_action(file_menu, "&New Tab", QKeySequence.StandardKey.New, self.file_new)
        self._add_action(file_menu, "&Open…", QKeySequence.StandardKey.Open, self.file_open)
        self._add_action(file_menu, "&Close Tab", QKeySequence.StandardKey.Close, self._close_current_tab)
        file_menu.addSeparator()
        self._add_action(file_menu, "&Save", QKeySequence.StandardKey.Save, self.file_save)
        self._add_action(file_menu, "Save &As…", QKeySequence.StandardKey.SaveAs, self.file_save_as)

        export_menu = file_menu.addMenu("&Export")
        self._add_action(export_menu, "Offline &HTML…", None, self.export_html)
        self._add_action(export_menu, "&PDF…", None, self.export_pdf)
        self._add_action(export_menu, "Plain &Text…", None, self.export_txt)

        file_menu.addSeparator()
        # Use an explicit Ctrl+Q rather than StandardKey.Quit: on Windows the
        # latter renders in the menu's shortcut column as the literal word
        # "Exit", so the row reads "Exit    Exit".
        self._add_action(file_menu, "E&xit", QKeySequence("Ctrl+Q"), self.close)

        edit_menu = self.menuBar().addMenu("&Edit")
        # These must act on the CURRENT tab, so route through the self.editor
        # property at trigger time — binding self.editor.undo directly here
        # would freeze them to whichever tab happened to be open at startup.
        self._add_action(edit_menu, "&Undo", QKeySequence.StandardKey.Undo, lambda: self.editor.undo())
        self._add_action(edit_menu, "&Redo", QKeySequence.StandardKey.Redo, lambda: self.editor.redo())
        edit_menu.addSeparator()
        self._add_action(edit_menu, "Cu&t", QKeySequence.StandardKey.Cut, lambda: self.editor.cut())
        self._add_action(edit_menu, "&Copy", QKeySequence.StandardKey.Copy, lambda: self.editor.copy())
        self._add_action(edit_menu, "&Paste", QKeySequence.StandardKey.Paste, lambda: self.editor.paste())
        edit_menu.addSeparator()
        self._add_action(edit_menu, "Select &All", QKeySequence.StandardKey.SelectAll, lambda: self.editor.selectAll())
        edit_menu.addSeparator()
        wrap_action = QAction("&Word Wrap", self, checkable=True)
        wrap_action.setChecked(True)
        wrap_action.toggled.connect(self._toggle_word_wrap)
        edit_menu.addAction(wrap_action)

        self.spell_action = QAction("Check &Spelling", self, checkable=True)
        self.spell_action.setChecked(self._spell_enabled)
        self.spell_action.setEnabled(self._spell is not None)
        self.spell_action.toggled.connect(self._toggle_spellcheck)
        edit_menu.addAction(self.spell_action)

        # Format menu is populated later (glyph toggle + theme submenu); create it
        # here so the menu order stays File / Edit / Format / Help.
        self.format_menu = self.menuBar().addMenu("F&ormat")

        help_menu = self.menuBar().addMenu("&Help")
        self._add_action(help_menu, "&About MoonScribe", None, self._show_about)

    def _add_action(self, menu, text, shortcut, handler):
        action = QAction(text, self)
        if shortcut is not None:
            action.setShortcut(shortcut)
        action.triggered.connect(handler)
        menu.addAction(action)
        return action

    def _toggle_word_wrap(self, on):
        self._wrap_mode = (
            QTextEdit.LineWrapMode.WidgetWidth if on else QTextEdit.LineWrapMode.NoWrap
        )
        for editor in self._all_editors():
            editor.setLineWrapMode(self._wrap_mode)

    # ---- Spellchecker ------------------------------------------------------
    def _toggle_spellcheck(self, on):
        self._spell_enabled = on
        for highlighter in self._highlighters:  # apply or clear across all tabs
            highlighter.rehighlight()

    def _editor_context_menu(self, editor, pos):
        """Standard editor menu, prefixed with spelling suggestions when the
        word under the cursor is misspelled."""
        menu = editor.createStandardContextMenu()
        if self._spell is not None and self._spell_enabled:
            cursor = editor.cursorForPosition(pos)
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            word = cursor.selectedText()
            if word and SpellHighlighter._WORD_RE.fullmatch(word) and word.lower() not in self._spell:
                first = menu.actions()[0] if menu.actions() else None
                suggestions = self._spell.candidates(word.lower()) or set()
                # Drop the word itself; keep a handful of the closest matches.
                picks = [s for s in suggestions if s != word.lower()][:5]
                new_actions = []
                if picks:
                    for suggestion in picks:
                        act = QAction(suggestion, menu)
                        act.triggered.connect(
                            lambda _=False, w=suggestion, c=QTextCursor(cursor): self._replace_word(c, w)
                        )
                        new_actions.append(act)
                else:
                    empty = QAction("(no suggestions)", menu)
                    empty.setEnabled(False)
                    new_actions.append(empty)
                menu.insertActions(first, new_actions)
                menu.insertSeparator(first)
        menu.exec(self.editor.viewport().mapToGlobal(pos))

    def _replace_word(self, cursor, replacement):
        if cursor.selectedText()[:1].isupper():
            replacement = replacement[:1].upper() + replacement[1:]
        cursor.insertText(replacement)

    def _show_about(self):
        recovery_dir = os.path.dirname(self._recovery_path)
        # Rich text so the "created by" credit can render in the Allura script
        # font (the same face as the footer logo), which only the rich-text
        # engine can draw from the loaded application font.
        html = (
            "<div style=\"font-family:'Segoe UI';\">"
            "<p>MoonScribe — a calm space for your thoughts.</p>"
            "<p>A modern rich-text editor built for notes, journals, "
            "stories, and everyday writing.</p>"
            f"<p style=\"color:#8a8a98;\">Version {APP_VERSION}</p>"
            "<p><b>Autosave &amp; recovery:</b><br>"
            "While you have unsaved changes, MoonScribe quietly saves a backup "
            "every 60 seconds, so an unexpected shutdown won't lose your work. "
            "It's cleared automatically when you save or exit normally.</p>"
            "<p>Backups are kept in:<br>"
            f"{recovery_dir}</p>"
            f"<p align='center' style=\"font-family:'{LOGO_FONT_FAMILY}'; "
            "font-size:26px; color:#c39ae2;\">created by MermaidCat</p>"
            "</div>"
        )
        box = QMessageBox(self)
        box.setWindowTitle("About MoonScribe")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(html)
        icon = QPixmap(ICON_PNG)
        if not icon.isNull():
            box.setIconPixmap(
                icon.scaled(
                    64, 64,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        box.exec()

    # ---- Toolbar -----------------------------------------------------------
    def _tool_button(self, tooltip, handler, text=None, font=None, checkable=False, objname=None):
        button = QToolButton()
        if text is not None:
            button.setText(text)
        if font is not None:
            button.setFont(font)
        if objname is not None:
            button.setObjectName(objname)
        button.setToolTip(tooltip)
        button.setCheckable(checkable)
        button.setAutoRaise(True)
        button.setFixedSize(34, 34)
        button.setIconSize(QSize(18, 18))
        button.clicked.connect(handler)
        return button

    def _build_toolbar(self):
        toolbar = QToolBar("Formatting")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        self._format_toolbar = toolbar  # used to size the window so it never overflows

        self.font_box = FontPickerComboBox(self._fav_fonts, self._recent_fonts)
        self.font_box.fontSelected.connect(self._on_font_selected)
        toolbar.addWidget(self.font_box)

        self.fav_btn = self._tool_button("Add to favorites", self._toggle_favorite)
        toolbar.addWidget(self.fav_btn)

        self.size_box = QComboBox()
        self.size_box.setEditable(True)
        self.size_box.addItems(
            ["8", "9", "10", "11", "12", "14", "16", "18", "20", "24", "28", "36", "48", "72"]
        )
        self.size_box.setCurrentText("12")
        self.size_box.activated.connect(lambda _: self._apply_size(self.size_box.currentText()))
        self.size_box.lineEdit().returnPressed.connect(
            lambda: self._apply_size(self.size_box.currentText())
        )
        toolbar.addWidget(self.size_box)
        toolbar.addSeparator()

        # Character-style toggles.
        bold_font = QFont(); bold_font.setPointSize(12); bold_font.setBold(True)
        italic_font = QFont(); italic_font.setPointSize(12); italic_font.setItalic(True)
        underline_font = QFont(); underline_font.setPointSize(12); underline_font.setUnderline(True)
        strike_font = QFont(); strike_font.setPointSize(12); strike_font.setStrikeOut(True)

        self.bold_btn = self._tool_button("Bold", self._toggle_bold, text="B", font=bold_font, checkable=True)
        self.italic_btn = self._tool_button("Italic", self._toggle_italic, text="I", font=italic_font, checkable=True)
        self.underline_btn = self._tool_button("Underline", self._toggle_underline, text="U", font=underline_font, checkable=True)
        self.strike_btn = self._tool_button("Strikethrough", self._toggle_strike, text="S", font=strike_font, checkable=True)
        for button in (self.bold_btn, self.italic_btn, self.underline_btn, self.strike_btn):
            toolbar.addWidget(button)
        toolbar.addSeparator()

        # Paragraph alignment + lists (icons painted per theme in _refresh_icons).
        self.align_left_btn = self._tool_button("Align left", lambda: self._align(Qt.AlignmentFlag.AlignLeft), checkable=True)
        self.align_center_btn = self._tool_button("Center", lambda: self._align(Qt.AlignmentFlag.AlignCenter), checkable=True)
        self.align_right_btn = self._tool_button("Align right", lambda: self._align(Qt.AlignmentFlag.AlignRight), checkable=True)
        self.list_btn = self._tool_button("Bullet list", self._toggle_bullets)
        for button in (self.align_left_btn, self.align_center_btn, self.align_right_btn, self.list_btn):
            toolbar.addWidget(button)
        toolbar.addSeparator()

        color_font = QFont(); color_font.setPointSize(14)
        self.text_color_btn = self._tool_button("Text color", self._pick_text_color, text="A", font=color_font)
        self.highlight_btn = self._tool_button(
            "Highlight color", self._pick_highlight_color, text="\N{LOWER LEFT PENCIL}", font=color_font
        )
        toolbar.addWidget(self.text_color_btn)
        toolbar.addWidget(self.highlight_btn)

        # Push the theme picker + moon accent to the far right.
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(THEMES))
        self.theme_combo.setCurrentText(self._current_theme)
        self.theme_combo.setFixedWidth(140)
        self.theme_combo.textActivated.connect(self._apply_theme)
        toolbar.addWidget(self.theme_combo)

        self.moon_btn = QToolButton()
        self.moon_btn.setObjectName("moonButton")
        self.moon_btn.setToolTip("Cycle theme")
        self.moon_btn.setFixedSize(38, 38)
        self.moon_btn.setIconSize(QSize(22, 22))
        self.moon_btn.clicked.connect(self._cycle_theme)
        toolbar.addWidget(self.moon_btn)

        # Guard against feedback loops when we programmatically update controls.
        self._syncing_toolbar = False

    # ---- Painted toolbar icons --------------------------------------------
    def _bars_icon(self, color, kind):
        size = 18
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(color))
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        rows = [3, 7, 11, 15]
        if kind == "list":
            for y in rows:
                painter.setBrush(QColor(color))
                painter.drawEllipse(QPointF(2.5, y), 1.1, 1.1)
                painter.drawLine(QPointF(6, y), QPointF(15, y))
        else:
            lengths = [14, 9, 13, 7]
            for y, length in zip(rows, lengths):
                if kind == "left":
                    x0 = 2
                elif kind == "right":
                    x0 = 16 - length
                else:
                    x0 = (size - length) / 2
                painter.drawLine(QPointF(x0, y), QPointF(x0 + length, y))
        painter.end()
        return QIcon(pixmap)

    def _moon_icon(self, color):
        size = 22
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        moon = QPainterPath()
        moon.addEllipse(QPointF(11, 11), 8, 8)
        shadow = QPainterPath()
        shadow.addEllipse(QPointF(14.5, 8), 8, 8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawPath(moon.subtracted(shadow))
        painter.end()
        return QIcon(pixmap)

    def _expand_icon(self, color):
        size = 18
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(color))
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        c, ln, s = 3, 4, size
        painter.drawPolyline([QPointF(c, c + ln), QPointF(c, c), QPointF(c + ln, c)])
        painter.drawPolyline([QPointF(s - c - ln, c), QPointF(s - c, c), QPointF(s - c, c + ln)])
        painter.drawPolyline([QPointF(c, s - c - ln), QPointF(c, s - c), QPointF(c + ln, s - c)])
        painter.drawPolyline([QPointF(s - c - ln, s - c), QPointF(s - c, s - c), QPointF(s - c, s - c - ln)])
        painter.end()
        return QIcon(pixmap)

    def _star_icon(self, color, filled):
        size = 18
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = cy = size / 2.0
        outer, inner = 7.4, 3.0
        path = QPainterPath()
        for i in range(10):
            radius = outer if i % 2 == 0 else inner
            angle = -math.pi / 2 + i * math.pi / 5
            point = QPointF(cx + radius * math.cos(angle), cy + radius * math.sin(angle))
            path.moveTo(point) if i == 0 else path.lineTo(point)
        path.closeSubpath()
        if filled:
            painter.setBrush(QColor("#e8c06a"))  # warm gold when favorited
            pen = QPen(QColor("#e8c06a")); pen.setWidthF(1.0)
        else:
            painter.setBrush(Qt.GlobalColor.transparent)
            pen = QPen(QColor(color)); pen.setWidthF(1.4)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)
        painter.end()
        return QIcon(pixmap)

    def _refresh_icons(self, color):
        self._chrome_fg = color
        self.align_left_btn.setIcon(self._bars_icon(color, "left"))
        self.align_center_btn.setIcon(self._bars_icon(color, "center"))
        self.align_right_btn.setIcon(self._bars_icon(color, "right"))
        self.list_btn.setIcon(self._bars_icon(color, "list"))
        self.moon_btn.setIcon(self._moon_icon(color))
        self.fullscreen_btn.setIcon(self._expand_icon(color))
        self._update_fav_button()

    # ---- Character formatting ---------------------------------------------
    def _toggle_bold(self):
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold if self.bold_btn.isChecked() else QFont.Weight.Normal)
        self._merge_format(fmt)

    def _toggle_italic(self):
        fmt = QTextCharFormat()
        fmt.setFontItalic(self.italic_btn.isChecked())
        self._merge_format(fmt)

    def _toggle_underline(self):
        fmt = QTextCharFormat()
        fmt.setFontUnderline(self.underline_btn.isChecked())
        self._merge_format(fmt)

    def _toggle_strike(self):
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(self.strike_btn.isChecked())
        self._merge_format(fmt)

    def _align(self, alignment):
        self.editor.setAlignment(alignment)
        self.editor.setFocus()

    def _toggle_bullets(self):
        cursor = self.editor.textCursor()
        if cursor.currentList() is not None:
            return  # already a list; leave it be
        cursor.createList(QTextListFormat.Style.ListDisc)
        self.editor.setFocus()

    def _cycle_theme(self):
        names = list(THEMES)
        nxt = names[(names.index(self._current_theme) + 1) % len(names)]
        self._apply_theme(nxt)

    def _merge_format(self, fmt):
        """Apply a char format to the selection, or to future typing if none."""
        cursor = self.editor.textCursor()
        cursor.mergeCharFormat(fmt)
        self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def _on_font_selected(self, family):
        self._apply_family(family)
        self._last_font = family
        self._record_recent(family)
        self._update_fav_button()

    def _restore_last_font(self):
        """Resume typing in the font used at the end of the last session."""
        family = self._last_font
        if not family or family not in self.font_box._all_families:
            return
        self.font_box.set_current_family(family)
        self._apply_family(family)

    def _apply_family(self, family):
        if getattr(self, "_syncing_toolbar", False):
            return
        fmt = QTextCharFormat()
        fmt.setFontFamilies([family])
        self._merge_format(fmt)
        if not self.editor.textCursor().hasSelection():
            self._base_font.setFamily(family)
            self.editor.document().setDefaultFont(self._base_font)

    def _record_recent(self, family):
        recents = self._recent_fonts
        if family in recents:
            recents.remove(family)
        recents.insert(0, family)
        del recents[self.RECENT_MAX:]
        self.font_box.set_lists(self._fav_fonts, recents)
        self.font_box.set_current_family(family)
        self._save_font_prefs()

    def _toggle_favorite(self):
        family = self.font_box.current_family()
        if not family:
            return
        if family in self._fav_fonts:
            self._fav_fonts.remove(family)
        else:
            self._fav_fonts.append(family)
            self._fav_fonts.sort(key=str.lower)
        self.font_box.set_lists(self._fav_fonts, self._recent_fonts)
        self.font_box.set_current_family(family)
        self._update_fav_button()
        self._save_font_prefs()

    def _update_fav_button(self):
        family = self.font_box.current_family()
        is_fav = family in self._fav_fonts
        self.fav_btn.setIcon(self._star_icon(getattr(self, "_chrome_fg", "#ffffff"), is_fav))
        self.fav_btn.setToolTip("Remove from favorites" if is_fav else "Add to favorites")

    def _save_font_prefs(self):
        self._settings.setValue("fonts/favorites", self._fav_fonts)
        self._settings.setValue("fonts/recent", self._recent_fonts)
        self._settings.setValue("fonts/last", self._last_font)

    def _apply_size(self, text):
        try:
            size = float(text)
        except ValueError:
            return
        if size <= 0:
            return
        fmt = QTextCharFormat()
        fmt.setFontPointSize(size)
        self._merge_format(fmt)
        if not self.editor.textCursor().hasSelection():
            self._base_font.setPointSizeF(size)
            self.editor.document().setDefaultFont(self._base_font)

    def _pick_text_color(self):
        color = QColorDialog.getColor(Qt.GlobalColor.black, self, "Text color")
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            self._merge_format(fmt)

    def _pick_highlight_color(self):
        color = QColorDialog.getColor(Qt.GlobalColor.yellow, self, "Highlight color")
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setBackground(color)
            self._merge_format(fmt)

    def _sync_toolbar(self, fmt):
        """Reflect the format under the cursor in the toolbar controls."""
        if not hasattr(self, "font_box"):  # toolbar not built yet (early setup)
            return
        self._syncing_toolbar = True
        families = fmt.fontFamilies()
        if families:
            self.font_box.set_current_family(families[0])
            self._update_fav_button()
        size = fmt.fontPointSize()
        if size > 0:
            self.size_box.setCurrentText(str(int(size)))

        self.bold_btn.setChecked(fmt.fontWeight() >= QFont.Weight.Bold.value)
        self.italic_btn.setChecked(fmt.fontItalic())
        self.underline_btn.setChecked(fmt.fontUnderline())
        self.strike_btn.setChecked(fmt.fontStrikeOut())

        alignment = self.editor.alignment()
        self.align_left_btn.setChecked(bool(alignment & Qt.AlignmentFlag.AlignLeft))
        self.align_center_btn.setChecked(bool(alignment & Qt.AlignmentFlag.AlignCenter))
        self.align_right_btn.setChecked(bool(alignment & Qt.AlignmentFlag.AlignRight))
        self._syncing_toolbar = False

    # ---- Emoji bar ---------------------------------------------------------
    def _build_emoji_bar(self):
        self.addToolBarBreak()  # put the emoji strip on its own row

        emoji_toolbar = QToolBar("Emoji")
        emoji_toolbar.setMovable(False)
        self.addToolBar(emoji_toolbar)

        self._emoji_font = QFont()
        self._emoji_font.setPointSize(18)  # larger glyphs, easier to see

        container = QWidget()
        container.setObjectName("emojiStrip")
        container.setFixedHeight(64)  # one row
        row = QHBoxLayout(container)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(8)

        # Recently used cluster (left) — hidden until the first emoji is used.
        self._recent_emoji_widget = QWidget()
        self._recent_emoji_layout = QHBoxLayout(self._recent_emoji_widget)
        self._recent_emoji_layout.setContentsMargins(0, 0, 0, 0)
        self._recent_emoji_layout.setSpacing(5)
        row.addWidget(self._recent_emoji_widget)

        self._emoji_divider = QFrame()
        self._emoji_divider.setObjectName("emojiDivider")
        self._emoji_divider.setFixedWidth(2)
        row.addWidget(self._emoji_divider)

        # Full emoji list (right, horizontally scrollable).
        strip = QWidget()
        strip.setObjectName("emojiFull")
        full_layout = QHBoxLayout(strip)
        full_layout.setContentsMargins(0, 0, 0, 0)
        full_layout.setSpacing(5)
        for emoji in EMOJIS:
            full_layout.addWidget(self._emoji_button(emoji))

        scroll = HorizontalScrollArea()
        scroll.setWidget(strip)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        row.addWidget(scroll, 1)

        emoji_toolbar.addWidget(container)
        self._rebuild_recent_emojis()

    def _emoji_button(self, emoji):
        button = QToolButton()
        button.setText(emoji)
        button.setFont(self._emoji_font)
        button.setAutoRaise(True)
        button.setFixedSize(40, 40)
        button.clicked.connect(lambda _, e=emoji: self._insert_emoji(e))
        return button

    def _insert_emoji(self, emoji):
        self._insert_text(emoji)
        self._record_recent_emoji(emoji)

    def _record_recent_emoji(self, emoji):
        recents = self._recent_emojis
        if emoji in recents:
            recents.remove(emoji)
        recents.insert(0, emoji)
        del recents[self.EMOJI_RECENT_MAX:]
        self._settings.setValue("emojis/recent", recents)
        self._rebuild_recent_emojis()

    def _rebuild_recent_emojis(self):
        layout = self._recent_emoji_layout
        while layout.count():
            widget = layout.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        for emoji in self._recent_emojis:
            layout.addWidget(self._emoji_button(emoji))
        has_recent = bool(self._recent_emojis)
        self._recent_emoji_widget.setVisible(has_recent)
        self._emoji_divider.setVisible(has_recent)

    def _insert_text(self, text):
        self.editor.insertPlainText(text)
        self.editor.setFocus()

    # ---- Glyph bar ---------------------------------------------------------
    def _build_glyph_bar(self):
        self.addToolBarBreak()  # put the glyph strip on its own row, below emoji

        glyph_toolbar = QToolBar("Glyphs")
        glyph_toolbar.setMovable(False)
        self.addToolBar(glyph_toolbar)

        glyph_font = QFont()
        glyph_font.setPointSize(16)

        container = QWidget()
        container.setObjectName("glyphStrip")
        container.setFixedHeight(92)  # two rows plus the horizontal scrollbar
        row = QHBoxLayout(container)
        row.setContentsMargins(8, 5, 8, 5)
        row.setSpacing(0)

        # Two-row grid, filled column-major so horizontal scrolling reads left→right.
        strip = QWidget()
        strip.setObjectName("glyphFull")
        grid = QGridLayout(strip)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)
        for index, glyph in enumerate(GLYPHS):
            button = QToolButton()
            button.setText(glyph)
            button.setFont(glyph_font)
            button.setAutoRaise(True)
            button.setFixedSize(34, 34)
            button.clicked.connect(lambda _, g=glyph: self._insert_text(g))
            grid.addWidget(button, index % 2, index // 2)  # two rows

        scroll = HorizontalScrollArea()
        scroll.setWidget(strip)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        row.addWidget(scroll, 1)

        glyph_toolbar.addWidget(container)
        self.glyph_toolbar = glyph_toolbar

        # Format menu entry to show/hide the strip.
        toggle = glyph_toolbar.toggleViewAction()
        toggle.setText("Show &Glyph Panel")
        self.format_menu.addAction(toggle)

    # ---- Status bar --------------------------------------------------------
    def _build_status_bar(self):
        bar = self.statusBar()
        bar.setSizeGripEnabled(False)

        self.branding = BrandingLabel()
        bar.addWidget(self.branding)

        self.count_label = QLabel()
        self.count_label.setObjectName("countLabel")
        bar.addPermanentWidget(self.count_label)

        self.fullscreen_btn = QToolButton()
        self.fullscreen_btn.setToolTip("Toggle full screen")
        self.fullscreen_btn.setAutoRaise(True)
        self.fullscreen_btn.setFixedSize(28, 28)
        self.fullscreen_btn.setIconSize(QSize(16, 16))
        self.fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        bar.addPermanentWidget(self.fullscreen_btn)

        self._update_counts()  # per-editor textChanged is wired in _new_editor

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _update_counts(self):
        if self.editor is None or not hasattr(self, "count_label"):
            return
        text = self.editor.toPlainText()
        # A word must contain at least one letter or digit, so a lone emoji
        # or stray punctuation isn't counted as a word.
        words = sum(1 for token in text.split() if any(ch.isalnum() for ch in token))
        chars = len(text)
        self.count_label.setText(f"Words: {words} | Characters: {chars}")

    # ---- Themes ------------------------------------------------------------
    def _build_theme_menu(self):
        theme_menu = self.format_menu.addMenu("&Theme")
        group = QActionGroup(self)
        group.setExclusive(True)
        self.theme_actions = {}
        for name in THEMES:
            action = QAction(name, self, checkable=True)
            action.setChecked(name == self._current_theme)
            action.triggered.connect(lambda _, n=name: self._apply_theme(n))
            group.addAction(action)
            theme_menu.addAction(action)
            self.theme_actions[name] = action

    # ---- Cosmic editor scene ----------------------------------------------
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize and THEMES[self._current_theme]["cosmic"]:
            editor = self.editor
            if editor is not None and obj is editor.viewport():
                self._refresh_cosmic_canvas(editor)
        return super().eventFilter(obj, event)

    def _refresh_cosmic_canvas(self, editor=None, force=False):
        """Repaint the nebula scene to fit the given editor's viewport exactly.

        Each tab keeps its own painted Base brush (cached on the editor), so
        switching notes shows the scene correctly sized for that tab."""
        editor = editor or self.editor
        if editor is None:
            return
        viewport = editor.viewport()
        width, height = viewport.width(), viewport.height()
        if width <= 0 or height <= 0:
            return
        if not force and getattr(editor, "_canvas_size", None) == (width, height):
            return
        editor._canvas_size = (width, height)

        scene = self._paint_cosmic_scene(width, height)
        palette = viewport.palette()
        palette.setBrush(QPalette.ColorRole.Base, QBrush(scene))
        viewport.setPalette(palette)
        viewport.update()

    def _paint_cosmic_scene(self, width, height):
        """Composite the Cosmic background from the artwork asset.

        The image is scaled proportionally and anchored bottom-right (keeping the
        crescent moon as the focal point), faded into a dark base so its edges melt
        away with no hard seam, then dimmed with a subtle overlay for text contrast.
        """
        base = QColor("#0d0a1c")
        pixmap = QPixmap(width, height)
        pixmap.fill(base)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if not self._cosmic_art.isNull():
            # Scale proportionally to cover the viewport, anchored to bottom-right.
            scaled = self._cosmic_art.scaled(
                width,
                height,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            # Near-full opacity keeps the nebula and stars crisp and vivid.
            painter.setOpacity(0.96)
            painter.drawPixmap(width - scaled.width(), height - scaled.height(), scaled)
            painter.setOpacity(1.0)

            # Vignette fade centred on the moon: clear at the focal point, melting
            # into the dark base toward the top-left where the text sits, so the
            # writing keeps contrast while the moon and stars stay bright.
            focal = QPointF(width * 0.82, height * 0.72)
            fade = QRadialGradient(focal, max(width, height) * 1.05)
            near = QColor(base); near.setAlpha(0)
            mid = QColor(base); mid.setAlpha(40)
            far = QColor(base); far.setAlpha(215)
            fade.setColorAt(0.0, near)
            fade.setColorAt(0.55, mid)
            fade.setColorAt(1.0, far)
            painter.fillRect(0, 0, width, height, QBrush(fade))

        # Whisper-thin overlay just to floor the contrast; light enough that the
        # artwork stays delightful rather than dulled.
        overlay = QColor("#0a0916")
        overlay.setAlpha(45)
        painter.fillRect(0, 0, width, height, overlay)

        painter.end()
        return pixmap

    def _apply_editor_appearance(self, theme):
        """Apply the theme's editor colours/background to every open tab."""
        for editor in self._all_editors():
            self._apply_editor_appearance_one(editor, theme)

    def _apply_editor_appearance_one(self, editor, theme):
        """Set one editor's text/placeholder/selection colours and background."""
        palette = editor.palette()
        palette.setColor(QPalette.ColorRole.Text, QColor(theme["editor_fg"]))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(theme["placeholder"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(theme["sel_bg"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(theme["sel_fg"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(theme["editor_bg"]))
        editor.setPalette(palette)

        if theme["cosmic"]:
            editor._canvas_size = None  # force a repaint at the current size
            self._refresh_cosmic_canvas(editor, force=True)
        else:
            viewport = editor.viewport()
            vpal = viewport.palette()
            vpal.setColor(QPalette.ColorRole.Base, QColor(theme["editor_bg"]))
            viewport.setPalette(vpal)

    def _apply_theme(self, name):
        theme = THEMES[name]
        self._current_theme = name

        chrome_bg = (
            "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {theme['chrome_top']}, stop:1 {theme['chrome_bottom']})"
        )
        # Cosmic gives every panel its own dark-navy gradient, a thin violet
        # panel line, small gaps between panels, and lighter option boxes.
        # Other themes keep their clean gradient / flush surfaces.
        if theme["cosmic"]:
            panel_grad = (
                "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                "stop:0 #030515, stop:1 #050717)"
            )
            optbox_grad = (
                "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                "stop:0 #0f0c22, stop:1 #0a091d)"
            )
            # Emoji strip fades from dark navy at the top to a dark purple at
            # the bottom — subtle but visible.
            emoji_grad = (
                "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                "stop:0 #050718, stop:1 #1a1036)"
            )
            chrome_fill = f"background: {panel_grad};"
            emoji_fill = f"background: {emoji_grad};"
            combo_fill = f"background: {optbox_grad};"
            panel_line = "#301f58"
            bar_edge = f"border: 1px solid {panel_line}; border-radius: 8px;"
            bar_margin = "margin: 3px 5px;"
            window_bg = "#020310"
            divider_col = "#4b3a7d"
        else:
            chrome_fill = f"background: {chrome_bg};"
            emoji_fill = f"background-color: {theme['surface']};"
            combo_fill = f"background-color: {theme['surface']};"
            panel_line = theme["border"]
            bar_edge = "border: none;"
            bar_margin = ""
            window_bg = theme["chrome_bottom"]
            divider_col = theme["muted"]

        caret_path = caret_icon(theme["chrome_fg"])

        self.setStyleSheet(
            f"""
            QMainWindow {{ background-color: {window_bg}; }}
            QMainWindow::separator {{ background: {window_bg}; width: 4px; height: 4px; }}
            QMenuBar {{ background: transparent; color: {theme['chrome_fg']}; padding: 3px 6px; }}
            QMenuBar::item {{ background: transparent; padding: 5px 12px; border-radius: 6px; }}
            QMenuBar::item:selected {{ background: {theme['button_hover']}; }}
            QMenu {{ background-color: {theme['chrome_bottom']}; color: {theme['chrome_fg']}; border: 1px solid {panel_line}; border-radius: 8px; padding: 4px; }}
            QMenu::item {{ padding: 6px 20px; border-radius: 6px; }}
            QMenu::item:selected {{ background: {theme['accent']}; }}
            QMenu::separator {{ height: 1px; background: {panel_line}; margin: 4px 8px; }}
            QToolBar {{ {chrome_fill} {bar_edge} {bar_margin} padding: 6px 9px; spacing: 5px; }}
            QToolBar::separator {{ background: {panel_line}; width: 1px; margin: 5px 7px; }}
            QStatusBar {{ {chrome_fill} {bar_edge} {bar_margin} color: {theme['chrome_fg']}; padding: 4px 12px; }}
            QStatusBar::item {{ border: none; }}
            QStatusBar QLabel {{ background: transparent; color: {theme['chrome_fg']}; }}
            QLabel#countLabel {{ color: {theme['muted']}; padding-right: 8px; }}
            #emojiStrip {{ {emoji_fill} border: 1px solid {panel_line}; border-radius: 10px; }}
            #emojiFull {{ {emoji_fill} border: none; }}
            #emojiDivider {{ background: {divider_col}; margin: 8px 2px; border: none; }}
            #glyphStrip {{ {emoji_fill} border: 1px solid {panel_line}; border-radius: 10px; }}
            #glyphFull {{ {emoji_fill} border: none; }}
            #glyphFull QToolButton {{ color: {theme['glyph_fg']}; }}
            #glyphFull QToolButton:hover {{ color: {theme['glyph_fg_hover']}; background: {theme['button_hover']}; }}
            QScrollArea {{ background: transparent; border: none; }}
            QToolButton {{ background: transparent; color: {theme['chrome_fg']}; border: none; border-radius: 8px; padding: 2px; }}
            QToolButton:hover {{ background: {theme['button_hover']}; }}
            QToolButton:checked {{ background: {theme['accent']}; }}
            QToolButton#moonButton {{ border: 1px solid {panel_line}; border-radius: 19px; background: {theme['button_hover']}; }}
            QToolButton#moonButton:hover {{ background: {theme['accent']}; }}
            QComboBox {{ {combo_fill} color: {theme['chrome_fg']}; border: 1px solid {panel_line}; border-radius: 8px; padding: 4px 8px; }}
            QComboBox:hover {{ border: 1px solid {theme['accent']}; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox::down-arrow {{ image: url({caret_path}); width: 11px; height: 7px; }}
            QComboBox QAbstractItemView {{ background-color: {theme['chrome_bottom']}; color: {theme['chrome_fg']}; border: 1px solid {panel_line}; border-radius: 8px; padding: 4px; selection-background-color: {theme['accent']}; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; border-radius: 4px; }}
            QScrollBar::handle:vertical {{ background: {theme['scrollbar']}; border-radius: 4px; min-height: 32px; }}
            QScrollBar::handle:vertical:hover {{ background: {theme['scrollbar_hover']}; }}
            QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 2px; border-radius: 4px; }}
            QScrollBar::handle:horizontal {{ background: {theme['scrollbar']}; border-radius: 4px; min-width: 32px; }}
            QScrollBar::handle:horizontal:hover {{ background: {theme['scrollbar_hover']}; }}
            QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
            QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
            QTabWidget::pane {{ border: none; }}
            QTabBar {{ background: transparent; qproperty-drawBase: 0; }}
            QTabBar::tab {{ background: {theme['surface']}; color: {theme['muted']}; border: 1px solid {panel_line}; border-bottom: none; border-top-left-radius: 8px; border-top-right-radius: 8px; padding: 5px 14px; margin: 3px 2px 0 0; }}
            QTabBar::tab:selected {{ background: {theme['button_hover']}; color: {theme['chrome_fg']}; }}
            QTabBar::tab:hover {{ background: {theme['button_hover']}; }}
            QToolButton#tabClose {{ border: none; background: transparent; border-radius: 5px; margin-left: 2px; }}
            QToolButton#tabClose:hover {{ background: {theme['button_hover']}; }}
            QFrame#updateBar {{ background: {theme['surface']}; border: 1px solid {theme['accent']}; border-radius: 8px; margin: 3px 5px 5px 5px; }}
            QLabel#updateText {{ background: transparent; color: {theme['chrome_fg']}; }}
            QPushButton#updateDownload {{ background: {theme['accent']}; color: #ffffff; border: none; border-radius: 6px; padding: 5px 16px; }}
            QPushButton#updateDownload:hover {{ background: {theme['sel_bg']}; }}
            QPushButton#updateDismiss {{ background: transparent; color: {theme['muted']}; border: none; border-radius: 6px; padding: 5px 12px; }}
            QPushButton#updateDismiss:hover {{ background: {theme['button_hover']}; color: {theme['chrome_fg']}; }}
            """
        )

        self._apply_editor_appearance(theme)
        self._refresh_icons(theme["chrome_fg"])
        self._refresh_close_buttons(theme["chrome_fg"])

        # Keep the toolbar dropdown and Format-menu radio in sync with the choice.
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentText(name)
        self.theme_combo.blockSignals(False)
        if hasattr(self, "theme_actions"):
            self.theme_actions[name].setChecked(True)

        self._settings.setValue("theme", name)

    # ---- Update notice -----------------------------------------------------
    def _make_update_bar(self):
        """Build the hidden 'update available' strip shown under the toolbars."""
        bar = QFrame()
        bar.setObjectName("updateBar")
        bar.hide()  # only revealed if a newer release is found
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 6, 8, 6)
        layout.setSpacing(10)

        self._update_label = QLabel("A new version of MoonScribe is available.")
        self._update_label.setObjectName("updateText")

        download = QPushButton("Download")
        download.setObjectName("updateDownload")
        download.setCursor(Qt.CursorShape.PointingHandCursor)
        download.clicked.connect(self._open_releases_page)

        dismiss = QPushButton("Dismiss")
        dismiss.setObjectName("updateDismiss")
        dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss.clicked.connect(self._dismiss_update)

        layout.addWidget(self._update_label)
        layout.addStretch(1)
        layout.addWidget(download)
        layout.addWidget(dismiss)
        return bar

    def _check_for_update(self):
        """Ask GitHub for the latest release, off the main thread's critical path.

        Everything here is wrapped so a failure (offline, DNS, TLS, bad JSON)
        stays completely invisible — the app carries on as if nothing happened.
        """
        try:
            self._net = QNetworkAccessManager(self)
            request = QNetworkRequest(QUrl(LATEST_RELEASE_API))
            # GitHub's API requires a User-Agent; Accept pins the API version.
            request.setHeader(
                QNetworkRequest.KnownHeaders.UserAgentHeader,
                f"MoonScribe/{APP_VERSION}",
            )
            request.setRawHeader(b"Accept", b"application/vnd.github+json")
            reply = self._net.get(request)
            reply.finished.connect(lambda: self._on_update_reply(reply))
        except Exception:
            pass  # never let the update check disturb the app

    def _on_update_reply(self, reply):
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                return
            raw = bytes(reply.readAll()).decode("utf-8", "replace")
            tag = str(json.loads(raw).get("tag_name", "")).strip()
            latest = parse_version(tag)
            current = parse_version(APP_VERSION)
            if latest is None or current is None or latest <= current:
                return  # up to date, or the tag was unreadable — say nothing
            dismissed = self._settings.value("updates/dismissed_version", "") or ""
            if tag == dismissed:
                return  # the user already waved this exact version away
            self._latest_tag = tag
            self._update_label.setText(
                f"🌙  MoonScribe {tag.lstrip('vV')} is available "
                f"— you have {APP_VERSION}."
            )
            self._update_bar.show()
        except Exception:
            pass  # any parsing hiccup: stay quiet
        finally:
            reply.deleteLater()

    def _open_releases_page(self):
        # Opens the releases page in the user's browser; the app never downloads
        # or installs anything itself — the person stays fully in control.
        QDesktopServices.openUrl(QUrl(RELEASES_PAGE))

    def _dismiss_update(self):
        # Remember this version so it won't nag again; a newer one still will.
        tag = getattr(self, "_latest_tag", "")
        if tag:
            self._settings.setValue("updates/dismissed_version", tag)
        self._update_bar.hide()

    # ---- File actions ------------------------------------------------------
    def file_new(self):
        # A new note simply opens a fresh tab — nothing is discarded.
        self._add_tab()
        self._update_title()

    def file_open(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open", "", OPEN_FILTER)
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as error:
            QMessageBox.warning(self, "MoonScribe", f"Could not open file:\n{error}")
            return

        # Reuse a blank current tab, otherwise open the file in its own tab.
        editor = self._target_editor_for_open()

        lower = path.lower()
        if lower.endswith((NATIVE_EXT, ".html", ".htm")):
            # Drop any baked-in theme block so the editor follows the live theme,
            # not the background stored when the note was last saved/exported.
            editor.setHtml(_THEME_BLOCK_RE.sub("\n", content))
        else:
            editor.setPlainText(content)

        if lower.endswith(NATIVE_EXT):
            # A native note: Save writes straight back to it.
            editor._path = path
            editor._suggested = None
        else:
            # An imported HTML/TXT file: treat it as a fresh note so Save routes
            # to Save As and writes a proper .mnote instead of overwriting it.
            editor._path = None
            editor._suggested = os.path.splitext(os.path.basename(path))[0]
        editor.document().setModified(False)
        self._update_title()

    def file_save(self):
        if self.current_path is None:
            return self.file_save_as()
        return self._write_to(self.current_path)

    def file_save_as(self):
        default = self._base_name() + NATIVE_EXT
        path, _ = QFileDialog.getSaveFileName(self, "Save As", default, SAVE_FILTER)
        if not path:
            return False
        if not path.lower().endswith(NATIVE_EXT):
            path += NATIVE_EXT
        return self._write_to(path)

    def _write_to(self, path):
        # Native .mnote: store the editor's own rich-text HTML verbatim, so
        # reopening in MoonScribe restores the note exactly, fully editable.
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.editor.toHtml())
        except OSError as error:
            QMessageBox.warning(self, "MoonScribe", f"Could not save file:\n{error}")
            return False

        self.current_path = path
        self._suggested_name = None
        self.editor.document().setModified(False)
        self._clear_recovery()  # the file on disk is now the source of truth
        self._update_title()
        return True

    # ---- Exports (one-way; never touch current_path or the modified flag) --
    def _base_name(self):
        """Best filename stem for Save As / Export dialogs."""
        if self.current_path:
            return os.path.splitext(os.path.basename(self.current_path))[0]
        return self._suggested_name or "untitled"

    def export_html(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export as Offline HTML", self._base_name() + ".html",
            "Web Page (*.html *.htm)",
        )
        if not path:
            return
        if not path.lower().endswith((".html", ".htm")):
            path += ".html"
        self._export_write(path, self._themed_html())

    def export_txt(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export as Plain Text", self._base_name() + ".txt", "Text File (*.txt)",
        )
        if not path:
            return
        if not path.lower().endswith(".txt"):
            path += ".txt"
        self._export_write(path, self.editor.toPlainText())

    def _export_write(self, path, content):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as error:
            QMessageBox.warning(self, "MoonScribe", f"Could not export file:\n{error}")

    def export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export as PDF", self._base_name() + ".pdf", "PDF Document (*.pdf)",
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            self._render_themed_pdf(path)
        except OSError as error:
            QMessageBox.warning(self, "MoonScribe", f"Could not export PDF:\n{error}")

    def _render_themed_pdf(self, path):
        """Paint each page with the active theme's background (nebula for Cosmic,
        solid fill otherwise) and lay the text over it in the theme's own colour,
        so the PDF looks like the note did in the app."""
        theme = THEMES[self._current_theme]
        writer = QPdfWriter(path)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
        writer.setResolution(150)

        full = writer.pageLayout().fullRectPixels(writer.resolution())
        page_w, page_h = full.width(), full.height()
        inset = round(page_w * 0.08)
        text_w, text_h = page_w - 2 * inset, page_h - 2 * inset

        # Rebuild the document with the theme's text colour as the default, so
        # writing left at the app's default colour prints legibly on the themed
        # page; text the user explicitly coloured keeps its own colour.
        doc = QTextDocument()
        doc.setDefaultFont(self._base_font)
        doc.setDefaultStyleSheet(f"body {{ color: {theme['editor_fg']}; }}")
        doc.setHtml(self.editor.toHtml())
        doc.setPageSize(QSizeF(text_w, text_h))

        cosmic_bg = self._paint_cosmic_scene(page_w, page_h) if theme["cosmic"] else None

        painter = QPainter(writer)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        try:
            for i in range(max(1, doc.pageCount())):
                if i:
                    writer.newPage()
                if cosmic_bg is not None:
                    painter.drawPixmap(0, 0, cosmic_bg)
                else:
                    painter.fillRect(QRectF(0, 0, page_w, page_h), QColor(theme["editor_bg"]))
                painter.save()
                painter.setClipRect(QRectF(inset, inset, text_w, text_h))
                painter.translate(inset, inset - i * text_h)
                doc.drawContents(painter, QRectF(0, i * text_h, text_w, text_h))
                painter.restore()
        finally:
            painter.end()

    # ---- Autosave / recovery ----------------------------------------------
    def _autosave(self):
        """Every 60s, mirror unsaved edits to a recovery file so a crash or
        power loss doesn't lose work.  Skips when there's nothing to protect."""
        if not self.editor.document().isModified():
            return
        if not self.editor.toPlainText().strip():
            return
        try:
            os.makedirs(os.path.dirname(self._recovery_path), exist_ok=True)
            with open(self._recovery_path, "w", encoding="utf-8") as f:
                f.write(self.editor.toHtml())
        except OSError:
            return  # a failed autosave shouldn't interrupt writing
        self._settings.setValue("recovery/active", True)
        self._settings.setValue("recovery/original", self.current_path or "")

    def _clear_recovery(self):
        """Drop the recovery copy — called after a real save, New, or clean exit."""
        self._settings.remove("recovery/active")
        self._settings.remove("recovery/original")
        try:
            if os.path.exists(self._recovery_path):
                os.remove(self._recovery_path)
        except OSError:
            pass

    def _maybe_recover(self):
        """On startup, offer to restore a recovery file left by a previous run."""
        if not self._settings.value("recovery/active", False, type=bool):
            return
        if not os.path.exists(self._recovery_path):
            self._clear_recovery()
            return
        choice = QMessageBox.question(
            self,
            "MoonScribe",
            "MoonScribe found unsaved work from your last session.\n"
            "Restore previous session?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            self._clear_recovery()
            return
        try:
            with open(self._recovery_path, "r", encoding="utf-8") as f:
                html = f.read()
        except OSError:
            self._clear_recovery()
            return
        self.editor.setHtml(_THEME_BLOCK_RE.sub("\n", html))
        original = self._settings.value("recovery/original", "") or ""
        self.current_path = original or None
        self.editor.document().setModified(True)  # still unsaved until they save
        self._update_title()

    def _cosmic_art_b64(self):
        """Base64 of the nebula PNG, cached, so cosmic notes stay self-contained."""
        if getattr(self, "_cosmic_b64", None) is None:
            try:
                with open(COSMIC_ART, "rb") as f:
                    self._cosmic_b64 = base64.b64encode(f.read()).decode("ascii")
            except OSError:
                self._cosmic_b64 = ""
        return self._cosmic_b64

    def _themed_html(self):
        """The document's HTML with the current theme's background, text color,
        and padding baked in, so double-clicking the saved .html opens (in a
        browser) looking like it did in the app.  The injected rules are wrapped
        in THEME_MARK_* so file_open() can strip them on the way back in."""
        html = self.editor.toHtml()
        theme = THEMES[self._current_theme]

        if theme["cosmic"]:
            art = self._cosmic_art_b64()
            base = "#0a0c1e"
            if art:
                background = (
                    "  background-color: #0a0c1e;\n"
                    "  background-image:\n"
                    "    linear-gradient(rgba(8,10,24,0.30), rgba(8,10,24,0.30)),\n"
                    "    radial-gradient(circle at 80% 74%, rgba(8,10,24,0) 28%, rgba(6,8,20,0.9) 78%),\n"
                    f'    url("data:image/png;base64,{art}");\n'
                    "  background-position: center, center, bottom right;\n"
                    "  background-size: cover, cover, cover;\n"
                    "  background-repeat: no-repeat;\n"
                    "  background-attachment: fixed;\n"
                )
            else:
                background = f"  background-color: {theme['editor_bg']};\n"
        else:
            base = theme["editor_bg"]
            background = f"  background-color: {theme['editor_bg']};\n"

        block = (
            f"\n{THEME_MARK_START}\n"
            f"html {{ background-color: {base}; }}\n"
            "body {\n"
            f"  color: {theme['editor_fg']};\n"
            "  margin: 0; padding: 40px; min-height: 100vh; box-sizing: border-box;\n"
            f"{background}"
            "}\n"
            f"{THEME_MARK_END}\n"
        )

        if "</style>" in html:
            return html.replace("</style>", block + "</style>", 1)
        return html.replace("<head>", "<head><style>" + block + "</style>", 1)

    # ---- Unsaved-changes handling -----------------------------------------
    def closeEvent(self, event):
        # Warn per unsaved tab; any Cancel aborts the whole close.
        for editor in self._all_editors():
            if editor.document().isModified():
                self.tabs.setCurrentWidget(editor)
                if not self._confirm_close_editor(editor):
                    event.ignore()
                    return
        self._clear_recovery()  # clean exit — no crash recovery needed
        event.accept()

    # ---- Title -------------------------------------------------------------
    def _update_title(self):
        e = self.editor
        name = e._path if (e is not None and e._path) else "Untitled"
        marker = "*" if (e is not None and e.document().isModified()) else ""
        self.setWindowTitle(f"{marker}{name} — MoonScribe")
        if e is not None:
            self._update_tab_label(e)


def main():
    # Silence harmless "CreateFontFaceFromHDC failed" chatter that Qt prints when
    # it enumerates a few legacy Windows bitmap fonts for the font picker.
    os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts=false")

    # Tell Windows we're our own app (not "python"), so the taskbar groups the
    # window under the MoonScribe icon instead of the generic Python one.
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MoonScribe.App")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setOrganizationName("MoonScribe")
    app.setApplicationName("MoonScribe")
    app.setWindowIcon(QIcon(ICON_PNG))
    register_logo_font()
    window = MoonScribe()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
