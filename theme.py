"""Midnight-blue + soft-neon-green theme.

Palette (eye-comfort goals: no pure white, no harsh neon, calm blue surfaces)
    bg-0   #0a1522   window / main surfaces   (deep midnight blue)
    bg-1   #0f2136   fields, combo, lists     (slightly lighter blue)
    bg-2   #16304e   hover state
    line   #23405f   borders
    line-2 #2f5580   bright borders / focus
    text   #d7e6f2   soft blue-white text
    mute   #8fa8c0   secondary text
    neon   #4ade80   accent — "neon green" soft enough for long reading
    neon-2 #86efac   lighter accent (hover text, status)
    ink    #07180f   text *on* neon buttons (dark on bright = best contrast)
"""

DARK_THEME = """
/* ───────────────────────── GLOBAL ───────────────────────── */
QWidget {
    background-color: #0a1522;
    color: #d7e6f2;
    font-family: 'Segoe UI', 'Inter', 'Noto Sans', 'DejaVu Sans', Arial, sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #0a1522;
}

QToolTip {
    color: #d7e6f2;
    background-color: #0f2136;
    border: 1px solid #2f5580;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 12px;
}

QLabel {
    color: #c9dcee;
    background-color: transparent;
    padding: 2px;
}

/* ──────────────────────── BUTTONS ──────────────────────── */
/* secondary (default) style: dark blue, soft-neon text + border */
QPushButton {
    background-color: #112540;
    color: #86efac;
    border: 1px solid #2f5580;
    border-radius: 8px;
    padding: 6px 18px;
    min-height: 28px;
    font-size: 13px;
    letter-spacing: 0.3px;
}
QPushButton:hover {
    background-color: #16304e;
    border-color: #4ade80;
    color: #a7f3c9;
}
QPushButton:pressed {
    background-color: #0d1c31;
    border-color: #4ade80;
}
QPushButton:focus {
    border-color: #4ade80;
}
QPushButton:disabled {
    background-color: #0e1e33;
    color: #4d6884;
    border-color: #1c3352;
}

/* primary action (Run): neon fill, dark text for maximum comfort/contrast */
QPushButton#run_button {
    background-color: #4ade80;
    color: #07180f;
    border: 1px solid #3cc96e;
    font-weight: 600;
}
QPushButton#run_button:hover {
    background-color: #6ee7a0;
    border-color: #6ee7a0;
    color: #07180f;
}
QPushButton#run_button:pressed {
    background-color: #40c96f;
    color: #07180f;
}
QPushButton#run_button:disabled {
    background-color: #1c3a2c;
    border-color: #22513a;
    color: #5b7a68;
}

/* ─────────────────────── TEXT EDITS ─────────────────────── */
QTextEdit {
    background-color: #0d1f33;
    color: #dbe9f7;                 /* soft blue-white — easy on the eyes */
    border: 1px solid #23405f;
    border-radius: 8px;
    padding: 10px;
    font-family: 'Cascadia Code', 'JetBrains Mono', 'Consolas',
                 'DejaVu Sans Mono', monospace;
    font-size: 12px;
    selection-background-color: #4ade80;
    selection-color: #07180f;
}
QTextEdit:focus { border: 1px solid #4ade80; }
QTextEdit:disabled { color: #5c7a99; }

/* ─────────────────────── COMBO BOX ──────────────────────── */
QComboBox {
    background-color: #0f2136;
    color: #d7e6f2;
    border: 1px solid #2f5580;
    border-radius: 8px;
    padding: 5px 14px;
    min-width: 170px;
    font-size: 13px;
}
QComboBox:hover { border-color: #4ade80; }
QComboBox:focus { border-color: #4ade80; }
QComboBox:disabled { background-color: #0e1e33; color: #4d6884; border-color: #1c3352; }
QComboBox::drop-down {
    border: none;
    width: 26px;
    padding-right: 6px;
}
QComboBox QAbstractItemView {
    background-color: #0f2136;
    color: #d7e6f2;
    border: 1px solid #2f5580;
    border-radius: 8px;
    outline: none;
    font-size: 13px;
    min-height: 24px;
    selection-background-color: #4ade80;
    selection-color: #07180f;
}
QComboBox QAbstractItemView::item { padding: 5px 10px; }
QComboBox QAbstractItemView::item:hover { background-color: #16304e; color: #a7f3c9; }
QComboBox QAbstractItemView::item:selected { background-color: #4ade80; color: #07180f; }

/* ─────────────────────── LINE EDIT ──────────────────────── */
QLineEdit {
    background-color: #0f2136;
    color: #d7e6f2;
    border: 1px solid #23405f;
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: #4ade80;
    selection-color: #07180f;
}
QLineEdit:focus { border: 1px solid #4ade80; }

/* ─────────────────────── SCROLLBARS ─────────────────────── */
QScrollBar:vertical {
    background-color: transparent;
    width: 12px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background-color: #27476b;
    min-height: 20px;
    border-radius: 5px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover { background-color: #4ade80; }
QScrollBar::handle:vertical:pressed { background-color: #3cc96e; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal {
    background-color: transparent;
    height: 12px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background-color: #27476b;
    min-width: 20px;
    border-radius: 5px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover { background-color: #4ade80; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }

/* ─────────────────────── STATUS LABEL ───────────────────── */
QLabel#status_label {
    color: #86efac;
    padding-left: 10px;
    font-style: italic;
}

/* ─────────────────────── MISC / GENERIC ─────────────────── */
QProgressBar {
    background-color: #0f2136;
    color: #d7e6f2;
    border: 1px solid #23405f;
    border-radius: 6px;
    text-align: center;
    font-size: 12px;
    padding: 0px;
}
QProgressBar::chunk {
    background-color: #4ade80;
    border-radius: 5px;
}

QTabWidget::pane {
    border: 1px solid #23405f;
    border-radius: 6px;
    background-color: #0a1522;
}
QTabBar::tab {
    background-color: #0a1522;
    color: #c9dcee;
    padding: 8px 18px;
    border: none;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected {
    background-color: #0f2136;
    border-bottom: 2px solid #4ade80;
    color: #86efac;
}

QMessageBox {
    background-color: #0a1522;
    color: #d7e6f2;
}
QMessageBox QLabel { color: #d7e6f2; }
QMessageBox QPushButton {
    background-color: #112540;
    color: #86efac;
    border: 1px solid #2f5580;
    border-radius: 8px;
    padding: 7px 20px;
    min-width: 80px;
}
QMessageBox QPushButton:hover {
    background-color: #16304e;
    border-color: #4ade80;
    color: #a7f3c9;
}
"""
