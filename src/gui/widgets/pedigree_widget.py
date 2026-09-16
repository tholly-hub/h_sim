"""
5代血統表 ビジュアル表示ウィジェット (PyQt6)
- 階層化グリッド配置
- 各祖先馬をクリックして詳細表示や祖先血統表へのジャンプが可能
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class PedigreeCell(QFrame):
    """血統表の1セル（1頭分のカード）"""

    clicked = pyqtSignal(int)  # horse_id

    def __init__(self, horse_data: Optional[Dict[str, Any]], gen: int, is_male: bool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.horse_data = horse_data or {}
        self.horse_id = self.horse_data.get("horse_id")
        self.gen = gen
        self.is_male = is_male

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor if self.horse_id else Qt.CursorShape.ArrowCursor)

        # 世代に応じた背景色
        if is_male:
            bg_color = "#1e293b" if gen % 2 == 1 else "#172554"
            border_color = "#3b82f6"
            text_color = "#93c5fd"
        else:
            bg_color = "#2a1e2f" if gen % 2 == 1 else "#3b1d3d"
            border_color = "#ec4899"
            text_color = "#f472b6"

        self.setStyleSheet(f"""
            PedigreeCell {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 2px 4px;
            }}
            PedigreeCell:hover {{
                border: 1px solid #38bdf8;
                background-color: #334155;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(1)

        name = self.horse_data.get("name", "―")
        self.name_lbl = QLabel(name)
        self.name_lbl.setStyleSheet(f"font-weight: bold; color: {text_color}; font-size: {max(10, 13 - gen)}px;")
        layout.addWidget(self.name_lbl)

        # 系統・勝鞍などの補足
        sire_line = self.horse_data.get("sire_line")
        g1_wins = self.horse_data.get("g1_wins", 0)
        extra_parts = []
        if g1_wins:
            extra_parts.append(f"G1:{g1_wins}勝")
        if sire_line:
            extra_parts.append(sire_line)

        if extra_parts and gen <= 3:
            sub_lbl = QLabel(" / ".join(extra_parts))
            sub_lbl.setStyleSheet("color: #94a3b8; font-size: 9px;")
            layout.addWidget(sub_lbl)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.horse_id:
            self.clicked.emit(self.horse_id)
        super().mousePressEvent(event)


class PedigreeWidget(QWidget):
    """5代血統表ウィジェット"""

    horse_selected = pyqtSignal(int)  # 祖先馬がクリックされた時のシグナル

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(3)
        self.grid.setContentsMargins(4, 4, 4, 4)

        self.scroll.setWidget(self.container)
        main_layout.addWidget(self.scroll)

    def set_tree_data(self, tree: Dict[str, Any]) -> None:
        """5代血統ツリーデータを受け取ってグリッドを構築"""
        # 既存ウィジェットの削除
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not tree:
            return

        # 5代血統表のグリッド総行数は 2^4 = 16 行（第5世代の16頭分、あるいは2^5=32頭分）
        # ここでは5代（第1代:父母、第2代:祖父母、第3代:曾祖父母、第4代:玄祖父母、第5代）
        # 第5世代は32頭なので 32行 で構成
        TOTAL_ROWS = 32

        def render_node(node: Optional[Dict[str, Any]], gen: int, row_start: int, row_span: int, is_male: bool, col: int) -> None:
            if not node:
                return
            cell = PedigreeCell(node, gen=gen, is_male=is_male)
            cell.clicked.connect(self.horse_selected.emit)
            self.grid.addWidget(cell, row_start, col, row_span, 1)

            if gen < 5:
                sire_node = node.get("sire")
                dam_node = node.get("dam")
                half_span = row_span // 2
                if sire_node:
                    render_node(sire_node, gen + 1, row_start, half_span, True, col + 1)
                if dam_node:
                    render_node(dam_node, gen + 1, row_start + half_span, half_span, False, col + 1)

        # 起点馬の父母からスタート
        sire_root = tree.get("sire")
        dam_root = tree.get("dam")

        if sire_root:
            render_node(sire_root, gen=1, row_start=0, row_span=TOTAL_ROWS // 2, is_male=True, col=0)
        if dam_root:
            render_node(dam_root, gen=1, row_start=TOTAL_ROWS // 2, row_span=TOTAL_ROWS // 2, is_male=False, col=0)

        # カラムの幅均等ストレッチ
        for c in range(5):
            self.grid.setColumnStretch(c, 1)
