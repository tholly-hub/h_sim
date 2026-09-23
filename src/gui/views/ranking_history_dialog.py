"""
年度別順位推移折れ線グラフダイアログ (RankingHistoryDialog)
- 騎手・調教師・馬主・生産牧場・種牡馬の各年度における順位推移を可視化
- 縦軸: 順位（上が1位の反転軸）
- 下部: 年度別成績詳細テーブル
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.ticker as ticker

from src.db.database import Database
from src.race.rankings import RankingManager


CATEGORY_TITLES = {
    "jockey": "騎手",
    "trainer": "調教師",
    "owner": "馬主",
    "breeder": "生産牧場",
    "sire": "種牡馬",
}


class RankingHistoryDialog(QDialog):
    """各リーディング対象の年度別順位推移グラフダイアログ"""

    def __init__(
        self,
        db: Database,
        category: str,
        entity_id: int,
        entity_name: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.db = db
        self.category = category
        self.entity_id = entity_id
        self.entity_name = entity_name
        self.rank_mgr = RankingManager(db)

        cat_title = CATEGORY_TITLES.get(category, "リーディング")
        self.setWindowTitle(f"📈 【{cat_title}】 {entity_name} - 年度別順位推移")
        self.resize(720, 580)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
            }
            QLabel {
                color: #f8fafc;
            }
            QTableWidget {
                background-color: #1e293b;
                color: #f8fafc;
                gridline-color: #334155;
                border: 1px solid #334155;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #0f172a;
                color: #94a3b8;
                padding: 4px;
                border: 1px solid #334155;
                font-weight: bold;
            }
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)

        self._init_ui()
        self._load_data_and_plot()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ヘッダー
        cat_title = CATEGORY_TITLES.get(self.category, "リーディング")
        header_lbl = QLabel(f"🏆 {self.entity_name} ({cat_title}) 年度別リーディング順位推移")
        header_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8;")
        layout.addWidget(header_lbl)

        # グラフ領域 (Matplotlib Canvas)
        self.figure = Figure(figsize=(7, 3.2), facecolor="#0f172a")
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        # 成績推移テーブル
        tbl_lbl = QLabel("📋 年度別詳細成績一覧")
        tbl_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #94a3b8;")
        layout.addWidget(tbl_lbl)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["年度", "順位", "勝利数", "獲得賞金"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # 閉じるボタン
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_close = QPushButton("閉じる")
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)

    def _load_data_and_plot(self) -> None:
        history = self.rank_mgr.get_ranking_history(self.category, self.entity_id)

        # グラフ描画
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor("#1e293b")

        if history:
            years = [h["year"] for h in history]
            ranks = [h["rank"] for h in history]

            ax.plot(
                years,
                ranks,
                marker="o",
                color="#38bdf8",
                linewidth=2.5,
                markersize=8,
                markerfacecolor="#facc15",
                markeredgecolor="#ffffff",
                markeredgewidth=1.5,
                label="順位",
            )

            # 各点に順位ラベル表示
            for y, r in zip(years, ranks):
                ax.annotate(
                    f"{r}位",
                    (y, r),
                    textcoords="offset points",
                    xytext=(0, -15 if r == 1 else 10),
                    ha="center",
                    fontsize=10,
                    fontweight="bold",
                    color="#f8fafc",
                )

            ax.invert_yaxis()  # 1位を上にする
            ax.set_ylabel("リーディング順位", color="#94a3b8", fontsize=11)
            ax.set_xlabel("年度", color="#94a3b8", fontsize=11)
            ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
            ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        else:
            ax.text(
                0.5,
                0.5,
                "データがありません",
                color="#94a3b8",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )

        ax.tick_params(colors="#94a3b8", labelsize=9)
        ax.grid(True, linestyle="--", alpha=0.3, color="#64748b")
        for spine in ax.spines.values():
            spine.set_color("#334155")

        self.figure.tight_layout()
        self.canvas.draw()

        # テーブル設定
        self.table.setRowCount(len(history))
        for idx, h in enumerate(history):
            item_y = QTableWidgetItem(f"{h['year']}年目")
            item_r = QTableWidgetItem(f"{h['rank']}位")
            item_w = QTableWidgetItem(f"{h['wins']}勝")
            item_e = QTableWidgetItem(f"{h['earnings']:,}円")

            item_y.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_r.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_w.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_e.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            if h["rank"] == 1:
                item_r.setForeground(Qt.GlobalColor.yellow)

            self.table.setItem(idx, 0, item_y)
            self.table.setItem(idx, 1, item_r)
            self.table.setItem(idx, 2, item_w)
            self.table.setItem(idx, 3, item_e)
