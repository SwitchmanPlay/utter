"""Dark, minimal Qt stylesheet in the spirit of Handy's UI."""

ACCENT = "#7c8cff"
ACCENT_HOVER = "#93a0ff"
BG = "#141518"
BG_ELEVATED = "#1d1f24"
BG_INPUT = "#23262d"
BORDER = "#2c3039"
TEXT = "#e8e9ee"
TEXT_MUTED = "#8b90a0"
DANGER = "#ff6b6b"

QSS = f"""
* {{
    font-family: "Segoe UI", "Inter", system-ui, sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QDialog, QWidget#root {{
    background: {BG};
}}
QWidget#card {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QLabel#title {{
    font-size: 20px;
    font-weight: 600;
}}
QLabel#muted, QLabel#status {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QPlainTextEdit, QTextEdit {{
    background: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 10px;
    font-size: 14px;
    selection-background-color: {ACCENT};
}}
QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {ACCENT};
}}
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QKeySequenceEdit {{
    background: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    min-height: 20px;
}}
QComboBox:hover, QLineEdit:hover, QKeySequenceEdit:hover {{
    border: 1px solid {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    outline: 0;
}}
QPushButton {{
    background: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 14px;
    min-height: 20px;
}}
QPushButton:hover {{
    border: 1px solid {ACCENT};
    background: #2a2e37;
}}
QPushButton:pressed {{
    background: #1a1c22;
}}
QPushButton:disabled {{
    color: {TEXT_MUTED};
    border-color: {BORDER};
    background: {BG_ELEVATED};
}}
QPushButton#primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: #0d0f16;
    font-weight: 600;
}}
QPushButton#primary:hover {{
    background: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}
QPushButton#primary:disabled {{
    background: #3a3f57;
    border-color: #3a3f57;
    color: #8a8fa8;
}}
QPushButton#danger:hover {{
    border-color: {DANGER};
    color: {DANGER};
}}
QPushButton#flat {{
    background: transparent;
    border: none;
    color: {TEXT_MUTED};
    padding: 4px 8px;
}}
QPushButton#flat:hover {{
    color: {TEXT};
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {BORDER};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
    background: {TEXT};
}}
QSlider::handle:horizontal:hover {{
    background: {ACCENT_HOVER};
}}
QProgressBar {{
    background: {BG_INPUT};
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 4px;
}}
QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {BORDER};
    background: {BG_INPUT};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    top: -1px;
    background: {BG_ELEVATED};
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    padding: 8px 16px;
    border: none;
}}
QTabBar::tab:selected {{
    color: {TEXT};
    border-bottom: 2px solid {ACCENT};
}}
QMenuBar {{
    background: {BG};
    border-bottom: 1px solid {BORDER};
}}
QMenuBar::item {{
    padding: 6px 10px;
    background: transparent;
}}
QMenuBar::item:selected {{
    background: {BG_INPUT};
    border-radius: 6px;
}}
QMenu {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {ACCENT};
    color: #0d0f16;
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 8px;
}}
QStatusBar {{
    background: {BG};
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_MUTED};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QToolTip {{
    background: {BG_ELEVATED};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 6px;
    border-radius: 6px;
}}
QListWidget {{
    background: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    outline: 0;
}}
QListWidget::item {{
    padding: 6px;
}}
QListWidget::item:selected {{
    background: {ACCENT};
    color: #0d0f16;
    border-radius: 6px;
}}
QFrame#overlay {{
    background: rgba(20, 21, 24, 235);
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
"""
