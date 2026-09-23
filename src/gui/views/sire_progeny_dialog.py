"""
種牡馬の現役産駒一覧ダイアログ (PyQt6)
- 指定された種牡馬の現役産駒を獲得賞金降順で一覧表示
- 行クリックまたはダブルクリックで競走馬詳細ダイアログ (HorseDetailDialog) を表示
"""

from __future__ import annotations

from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.db.database import Database
from src.gui.views.horse_detail_dialog import HorseDetailDialog
from src.race.rankings import RankingManager


SEX_JP = {
    "colt": "牡",
    "filly": "牝",
    "horse": "牡",
    "mare": "牝",
    "gelding": "セン",
}

STYLE_JP = {
    "escape": "逃げ",
    "leading": "先行",
    "between": "差し",
    "closing": "追込",
}


class SireProgenyDialog(QDialog):
    """種牡馬の現役産駒一覧ダイアログ"""

    def __init__(
        self,
        db: Database,
        sire_horse_id: int,
        sire_name: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.db = db
        self.sire_horse_id = sire_horse_id
        self.sire_name = sire_name
        self.rank_mgr = RankingManager(db)

        self.setWindowTitle(f"種牡馬「{self.sire_name}」現役産駒一覧")
        self.resize(920, 560)
        self._init_ui()
        self._load_progenies()

    def _init_ui(self) -> None:
        self.setStyleSheet(
            """
            QDialog {
                background-color: #0d1117;
                color: #e6edf3;
            }
            QTableWidget {
                background-color: #161b22;
                gridline-color: #30363d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                selection-background-color: #1f6feb;
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #21262d;
                color: #8b949e;
                font-weight: bold;
                border: 1px solid #30363d;
                padding: 6px;
            }
            QPushButton {
                background-color: #238636;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ヘッダー情報
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 8px;")
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(12, 8, 12, 8)

        self.title_lbl = QLabel(f"🏆 種牡馬: {self.sire_name} の現役産駒一覧 (獲得賞金順)")
        self.title_lbl.setFont(QFont("Hiragino Sans", 13, QFont.Weight.Bold))
        self.title_lbl.setStyleSheet("color: #58a6ff;")
        h_layout.addWidget(self.title_lbl)

        h_layout.addStretch()

        self.count_lbl = QLabel("産駒数: 0頭")
        self.count_lbl.setStyleSheet("color: #8b949e; font-weight: bold;")
        h_layout.addWidget(self.count_lbl)

        layout.addWidget(header_frame)

        # 産駒一覧テーブル
        self.table = QTableWidget()
        headers = ["馬名", "性齢", "脚質", "所属厩舎", "馬主", "戦績", "重賞(G1/G2/G3)", "主な勝ち鞍", "総獲得賞金"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        # クリック・ダブルクリックイベント
        self.table.cellDoubleClicked.connect(self._on_cell_clicked)
        self.table.cellClicked.connect(self._on_cell_clicked)

        layout.addWidget(self.table)

        # フッター・ヘルプテキスト & 閉じるボタン
        footer_layout = QHBoxLayout()
        hint_lbl = QLabel("※ 馬名または行をクリックすると、詳細な競走成績・血統情報が閲覧できます。")
        hint_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        footer_layout.addWidget(hint_lbl)

        footer_layout.addStretch()

        close_btn = QPushButton("閉じる")
        close_btn.setStyleSheet("background-color: #30363d; color: #c9d1d9;")
        close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(close_btn)

        layout.addLayout(footer_layout)

    def _load_progenies(self) -> None:
        # 種牡馬の毛色取得
        sire_coat = "鹿毛"
        with self.db.session() as conn:
            s_row = conn.execute("SELECT coat_color FROM horses WHERE horse_id = ?", (self.sire_horse_id,)).fetchone()
            if s_row and s_row["coat_color"]:
                sire_coat = s_row["coat_color"]

        self.title_lbl.setText(f"🏆 種牡馬: {self.sire_name} (毛色: {sire_coat}) の現役産駒一覧 (獲得賞金順)")

        progenies = self.rank_mgr.get_sire_progenies(self.sire_horse_id)
        self.count_lbl.setText(f"現役産駒数: {len(progenies)}頭")
        self.table.setRowCount(len(progenies))

        self.horse_ids = []
        for row_idx, h in enumerate(progenies):
            self.horse_ids.append(h["horse_id"])

            # 性齢
            sex_str = SEX_JP.get(h.get("sex", ""), "牡")
            age_val = h.get("age", 3)
            sex_age_str = f"{sex_str}{age_val}"

            # 脚質
            style_str = STYLE_JP.get(h.get("running_style", ""), "先行")

            # 厩舎・馬主
            t_name = h.get("trainer_name") or "未定"
            o_name = h.get("owner_name") or "未定"

            # 戦績
            starts = h.get("career_starts", 0)
            wins = h.get("career_wins", 0)
            record_str = f"{starts}戦{wins}勝"

            # 重賞勝
            g1 = h.get("g1_wins", 0)
            g2 = h.get("g2_wins", 0)
            g3 = h.get("g3_wins", 0)
            graded_str = f"{g1}-{g2}-{g3}" if (g1 + g2 + g3 > 0) else "-"

            # 主な勝ち鞍
            major_str = h.get("major_wins") or ("重賞未勝利" if (g1 + g2 + g3 == 0) else "-")

            # 賞金
            prize = h.get("prize_money", 0)
            prize_str = f"{prize:,}円"

            self.table.setItem(row_idx, 0, QTableWidgetItem(h.get("name", "")))
            self.table.setItem(row_idx, 1, QTableWidgetItem(sex_age_str))
            self.table.setItem(row_idx, 2, QTableWidgetItem(style_str))
            self.table.setItem(row_idx, 3, QTableWidgetItem(t_name))
            self.table.setItem(row_idx, 4, QTableWidgetItem(o_name))
            self.table.setItem(row_idx, 5, QTableWidgetItem(record_str))
            self.table.setItem(row_idx, 6, QTableWidgetItem(graded_str))
            self.table.setItem(row_idx, 7, QTableWidgetItem(major_str))
            self.table.setItem(row_idx, 8, QTableWidgetItem(prize_str))

            # 色付け（重賞馬・G1馬はハイライト）
            if g1 > 0:
                self.table.item(row_idx, 0).setForeground(Qt.GlobalColor.yellow)
            elif (g2 + g3) > 0:
                self.table.item(row_idx, 0).setForeground(Qt.GlobalColor.cyan)

    def _on_cell_clicked(self, row: int, col: int) -> None:
        if 0 <= row < len(self.horse_ids):
            hid = self.horse_ids[row]
            dlg = HorseDetailDialog(self.db, hid, parent=self)
            dlg.exec()
