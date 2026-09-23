"""
関係者（調教師・馬主・生産牧場）所属馬・勝ち馬一覧ダイアログ (EntityHorsesDialog)
- 調教師の管理馬・勝ち馬
- 馬主の所有馬・勝ち馬
- 生産牧場の生産馬・勝ち馬
"""

from __future__ import annotations

from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
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


class EntityHorsesDialog(QDialog):
    """調教師・馬主・生産牧場の所有/管理/生産馬一覧ダイアログ"""

    def __init__(
        self,
        db: Database,
        entity_type: str,  # "trainer", "owner", "breeder"
        entity_id: int,
        entity_name: str,
        only_winners: bool = False,
        year: Optional[int] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.db = db
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.entity_name = entity_name
        self.only_winners = only_winners
        self.year = year

        type_names = {"trainer": "厩舎", "owner": "馬主", "breeder": "生産牧場"}
        t_name = type_names.get(entity_type, "")
        title_suffix = "勝ち馬一覧" if only_winners else "所属・関連馬一覧"
        self.setWindowTitle(f"{self.entity_name} ({t_name}) - {title_suffix}")
        self.resize(800, 520)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
            }
            QTableWidget {
                background-color: #1e293b;
                color: #f8fafc;
                gridline-color: #334155;
                border: 1px solid #334155;
                border-radius: 6px;
                selection-background-color: #3b82f6;
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #334155;
                color: #f8fafc;
                font-weight: bold;
                padding: 4px;
                border: 1px solid #1e293b;
            }
        """)

        self._init_ui()
        self._load_data()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # ヘッダー
        h_frame = QFrame()
        h_frame.setStyleSheet("background-color: #1e293b; border-radius: 6px; padding: 6px;")
        h_lay = QHBoxLayout(h_frame)
        self.lbl_title = QLabel(self.windowTitle())
        self.lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8;")
        h_lay.addWidget(self.lbl_title)
        h_lay.addStretch()

        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet("color: #94a3b8; font-size: 12px;")
        h_lay.addWidget(self.lbl_count)
        layout.addWidget(h_frame)

        # テーブル
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "馬名 (詳細)", "性齢", "サイアー", "母馬", "通算成績", "総獲得賞金", "主な勝鞍", "状態"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, 55)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(4, 85)
        self.table.setColumnWidth(5, 100)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(7, 60)

        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellClicked.connect(self._on_cell_clicked)
        layout.addWidget(self.table)

        btn_close = QPushButton("閉じる")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #ffffff;
                font-weight: bold;
                padding: 6px 18px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

    def _load_data(self) -> None:
        where_field = {
            "trainer": "h.trainer_id",
            "owner": "h.owner_id",
            "breeder": "h.breeder_id",
        }.get(self.entity_type, "h.trainer_id")

        query = f"""
            SELECT h.*, 
                   sire.name as sire_name,
                   dam.name as dam_name,
                   COUNT(res.result_id) as total_starts,
                   SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END) as total_wins
            FROM horses h
            LEFT JOIN horses sire ON h.sire_id = sire.horse_id
            LEFT JOIN horses dam ON h.dam_id = dam.horse_id
            LEFT JOIN results res ON h.horse_id = res.horse_id
            WHERE {where_field} = ?
        """
        params: list[Any] = [self.entity_id]

        if self.only_winners:
            query += " GROUP BY h.horse_id HAVING total_wins > 0 ORDER BY h.prize_money DESC"
        else:
            query += " GROUP BY h.horse_id ORDER BY h.is_active DESC, h.prize_money DESC"

        with self.db.session() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()

        sex_map = {"colt": "牡", "filly": "牝", "horse": "牡", "mare": "牝", "gelding": "セ"}
        self.table.setRowCount(len(rows))
        self.lbl_count.setText(f"該当頭数: {len(rows)}頭")

        for idx, r in enumerate(rows):
            h_name = r["name"]
            sex_age = f"{sex_map.get(r['sex'], '')}{r['age']}"
            s_name = r["sire_name"] or "-"
            d_name = r["dam_name"] or "-"
            rec_str = f"{r['total_starts'] or 0}戦{r['total_wins'] or 0}勝"
            prz = r["prize_money"] or 0.0
            prz_str = f"{prz // 10000:,}万円"
            maj_str = r["major_wins"] or ("未勝利" if (r['total_wins'] or 0) == 0 else "条件戦")
            if r["is_sire"]:
                status_str = "種牡馬"
                status_col = "#facc15"
            elif r["is_dam"]:
                status_str = "繁殖牝馬"
                status_col = "#f472b6"
            elif r["age"] <= 1:
                status_str = "入厩前"
                status_col = "#38bdf8"
            elif r["is_active"]:
                if (r["total_starts"] or 0) == 0:
                    status_str = "未出走"
                    status_col = "#34d399"
                else:
                    status_str = "現役"
                    status_col = "#22c55e"
            else:
                status_str = "引退"
                status_col = "#94a3b8"

            name_item = QTableWidgetItem(h_name)
            name_item.setData(Qt.ItemDataRole.UserRole, r["horse_id"])
            name_item.setForeground(QColor("#38bdf8"))

            status_item = QTableWidgetItem(status_str)
            status_item.setForeground(QColor(status_col))

            items = [
                name_item,
                QTableWidgetItem(sex_age),
                QTableWidgetItem(s_name),
                QTableWidgetItem(d_name),
                QTableWidgetItem(rec_str),
                QTableWidgetItem(prz_str),
                QTableWidgetItem(maj_str),
                status_item,
            ]

            for c, itm in enumerate(items):
                if c not in (0, 2, 3, 6):
                    itm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(idx, c, itm)

    def _on_cell_clicked(self, row: int, col: int) -> None:
        if col == 0:
            item = self.table.item(row, 0)
            if item:
                hid = item.data(Qt.ItemDataRole.UserRole)
                if hid:
                    dlg = HorseDetailDialog(self.db, hid, parent=self)
                    dlg.exec()
