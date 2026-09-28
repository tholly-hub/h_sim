"""
PyQt6用 モダン・ダークテーマ スタイルシート (QSS)
"""

from __future__ import annotations
from typing import Optional

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

/* テーブルビュー・ツリービュー */
QTableWidget, QTableView, QTreeWidget, QTreeView {
    background-color: #12161f;
    alternate-background-color: #1a202c;
    gridline-color: #242c3d;
    color: #f8fafc;
    border: 1px solid #242c3d;
    border-radius: 6px;
    selection-background-color: #1e3a8a;
    selection-color: #ffffff;
}

QTableWidget::item, QTableView::item, QTreeWidget::item, QTreeView::item {
    background-color: transparent;
    padding: 6px;
    border: none;
}

QTableWidget::item:alternate, QTableView::item:alternate, QTreeWidget::item:alternate, QTreeView::item:alternate {
    background-color: #1a202c;
}

QTableWidget::item:hover, QTableView::item:hover, QTreeWidget::item:hover, QTreeView::item:hover {
    background-color: #1e293b;
}

QTableWidget::item:selected, QTableView::item:selected, QTreeWidget::item:selected, QTreeView::item:selected {
    background-color: #2563eb;
    color: #ffffff;
    font-weight: bold;
}

QHeaderView::section {
    background-color: #0b0f17;
    color: #cbd5e1;
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


# 世代別カラーパレット (第1世代: 白, 第2世代以降は7色ローテーション)
# 1: 白 (#ffffff)
# 2: 水色 (#38bdf8)
# 3: 黄緑 (#a3e635)
# 4: 桃 (#f472b6)
# 5: 青 (#60a5fa)
# 6: 緑 (#4ade80)
# 7: 黄 (#facc15)
# 8: 紫 (#c084fc)
GEN_COLOR_PALETTE = {
    1: "#ffffff",  # 第1世代: 白
    2: "#38bdf8",  # 第2世代: 水色
    3: "#a3e635",  # 第3世代: 黄緑
    4: "#f472b6",  # 第4世代: 桃
    5: "#60a5fa",  # 第5世代: 青
    6: "#4ade80",  # 第6世代: 緑
    7: "#facc15",  # 第7世代: 黄
    8: "#c084fc",  # 第8世代: 紫
}

GEN_ROTATION_CYCLE = [
    "#38bdf8",  # 第2世代: 水色
    "#a3e635",  # 第3世代: 黄緑
    "#f472b6",  # 第4世代: 桃
    "#60a5fa",  # 第5世代: 青
    "#4ade80",  # 第6世代: 緑
    "#facc15",  # 第7世代: 黄
    "#c084fc",  # 第8世代: 紫
]


def get_generation_color(
    generation: Optional[int], is_breeding: bool = False, start_year: Optional[int] = None
) -> str:
    """
    世代番号に応じた表示カラーコード（HEX）を返却
    - 初代 (第1世代, または初期導入種牡馬/繁殖牝馬 start_year <= 1): 白色 (#ffffff)
    - 第2世代以降: 7色ローテーション
      - 第2世代: 水色 (#38bdf8)
      - 第3世代: 黄緑 (#a3e635)
      - 第4世代: 桃 (#f472b6)
      - 第5世代: 青 (#60a5fa)
      - 第6世代: 緑 (#4ade80)
      - 第7世代: 黄 (#facc15)
      - 第8世代: 紫 (#c084fc)
      - 第9世代以降: 水色からローテーション
    """
    if generation is None:
        gen = 1
    else:
        try:
            gen = int(generation)
        except (ValueError, TypeError):
            gen = 1

    if is_breeding and start_year is not None and start_year <= 1:
        return "#ffffff"

    if gen <= 1:
        return "#ffffff"

    cycle_idx = (gen - 2) % len(GEN_ROTATION_CYCLE)
    return GEN_ROTATION_CYCLE[cycle_idx]

