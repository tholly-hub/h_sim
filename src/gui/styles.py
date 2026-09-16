"""
PyQt6用 モダン・ダークテーマ スタイルシート (QSS)
"""

MAIN_STYLESHEET = """
QMainWindow, QDialog {
    background-color: #12161f;
    color: #e2e8f0;
}

QWidget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Hiragino Kaku Gothic ProN", Meiryo, sans-serif;
    font-size: 13px;
    color: #e2e8f0;
}

/* タブバー */
QTabWidget::pane {
    border: 1px solid #1e293b;
    background-color: #161b26;
    border-radius: 8px;
}

QTabBar::tab {
    background-color: #0f172a;
    color: #94a3b8;
    padding: 10px 24px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: bold;
    font-size: 13px;
}

QTabBar::tab:selected {
    background-color: #1e293b;
    color: #38bdf8;
    border-bottom: 2px solid #38bdf8;
}

QTabBar::tab:hover:!selected {
    background-color: #1e293b;
    color: #cbd5e1;
}

/* ボタン */
QPushButton {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #3b82f6;
}

QPushButton:pressed {
    background-color: #1d4ed8;
}

QPushButton:disabled {
    background-color: #334155;
    color: #64748b;
}

/* 特殊アクションボタン */
QPushButton#primaryBtn {
    background-color: #059669;
    font-size: 14px;
    padding: 10px 20px;
}
QPushButton#primaryBtn:hover {
    background-color: #10b981;
}

QPushButton#goldBtn {
    background-color: #d97706;
}
QPushButton#goldBtn:hover {
    background-color: #f59e0b;
}

QPushButton#dangerBtn {
    background-color: #dc2626;
}
QPushButton#dangerBtn:hover {
    background-color: #ef4444;
}

/* 入力・選択ボックス */
QLineEdit, QComboBox, QSpinBox {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #2563eb;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #38bdf8;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid #334155;
}

QComboBox QAbstractItemView {
    background-color: #1e293b;
    color: #f8fafc;
    selection-background-color: #2563eb;
    border: 1px solid #475569;
}

/* テーブルビュー */
QTableWidget, QTableView {
    background-color: #161b26;
    alternate-background-color: #1a202c;
    gridline-color: #242c3d;
    border: 1px solid #242c3d;
    border-radius: 6px;
    selection-background-color: #1e3a8a;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #0f172a;
    color: #94a3b8;
    padding: 8px 6px;
    border: none;
    border-bottom: 2px solid #334155;
    border-right: 1px solid #1e293b;
    font-weight: 700;
}

/* グループボックス・フレーム */
QGroupBox {
    border: 1px solid #242c3d;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 16px;
    background-color: #161b26;
    font-weight: bold;
    color: #38bdf8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
}

/* スクロールバー */
QScrollBar:vertical {
    background-color: #12161f;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #334155;
    min-height: 24px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background-color: #475569;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #12161f;
    height: 10px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background-color: #334155;
    min-width: 24px;
    border-radius: 5px;
}

/* プログレスバー */
QProgressBar {
    border: 1px solid #334155;
    border-radius: 6px;
    background-color: #1e293b;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #38bdf8);
    border-radius: 5px;
}

/* ラベル */
QLabel#cardTitle {
    font-size: 15px;
    font-weight: bold;
    color: #f8fafc;
}

QLabel#statValue {
    font-size: 26px;
    font-weight: 800;
    color: #38bdf8;
}

QLabel#statLabel {
    font-size: 12px;
    color: #94a3b8;
}

QLabel#subText {
    color: #64748b;
    font-size: 11px;
}
"""
