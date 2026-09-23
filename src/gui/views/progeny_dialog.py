"""
種牡馬・繁殖牝馬 産駒一覧ダイアログ (ProgenyListDialog)
- 指定された種牡馬または繁殖牝馬の全産駒を一覧表示
- 通算獲得賞金順にソート
- 産駒名クリックで競走馬詳細ダイアログを表示
"""

from __future__ import annotations

from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
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

from src.db.database import Database, get_db
from src.gui.views.horse_detail_dialog import HorseDetailDialog, GRADE_COLOR_MAP


class ProgenyListDialog(QDialog):
    """種牡馬・繁殖牝馬の産駒一覧ダイアログ"""

    def __init__(
        self,
        db: Database,
        parent_id: int,
        is_sire: bool = True,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.db = db
        self.parent_id = parent_id
        self.is_sire = is_sire

        self.setWindowTitle("産駒一覧" if is_sire else "繁殖牝馬 産駒一覧")
        self.resize(850, 580)
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
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ヘッダー情報
        self.header_frame = QFrame()
        self.header_frame.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        h_layout = QHBoxLayout(self.header_frame)
        self.lbl_title = QLabel("産駒情報取得中...")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8;")
        h_layout.addWidget(self.lbl_title)

        h_layout.addStretch()

        self.lbl_stats = QLabel("")
        self.lbl_stats.setStyleSheet("font-size: 13px; color: #94a3b8;")
        h_layout.addWidget(self.lbl_stats)

        layout.addWidget(self.header_frame)

        # 産駒一覧テーブル
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "産駒名 (詳細)", "生年", "性齢", "相手馬", "通算成績", "総賞金", "主な勝鞍", "状態"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 180)  # 馬名
        self.table.setColumnWidth(1, 55)   # 生年
        self.table.setColumnWidth(2, 55)   # 性齢
        self.table.setColumnWidth(3, 150)  # 相手馬
        self.table.setColumnWidth(4, 85)   # 成績
        self.table.setColumnWidth(5, 100)  # 賞金
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)  # 主な勝鞍
        self.table.setColumnWidth(7, 65)   # 状態
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellClicked.connect(self._on_cell_clicked)
        layout.addWidget(self.table)

        # フッター閉じるボタン
        btn_close = QPushButton("閉じる")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
                padding: 6px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

    def _load_data(self) -> None:
        """産駒一覧データをロード"""
        with self.db.session() as conn:
            if self.is_sire:
                parent_row = conn.execute("""
                    SELECT h.name, s.sire_line 
                    FROM sires s 
                    JOIN horses h ON s.horse_id = h.horse_id 
                    WHERE s.horse_id = ?
                """, (self.parent_id,)).fetchone()
                p_name = parent_row["name"] if parent_row else "不明"
                line_info = f"（系統: {parent_row['sire_line']}）" if parent_row and "sire_line" in parent_row.keys() and parent_row["sire_line"] else ""
                self.lbl_title.setText(f"🐴 種牡馬: {p_name} {line_info} の産駒一覧")

                progeny_rows = conn.execute("""
                    SELECT h.*, 
                           dh.name as mate_name,
                           COUNT(res.result_id) as total_races,
                           SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END) as wins
                    FROM horses h
                    LEFT JOIN horses dh ON h.dam_id = dh.horse_id
                    LEFT JOIN results res ON h.horse_id = res.horse_id
                    WHERE h.sire_id = ?
                    GROUP BY h.horse_id
                    ORDER BY h.prize_money DESC, h.birth_year DESC
                """, (self.parent_id,)).fetchall()
            else:
                parent_row = conn.execute("""
                    SELECT h.name 
                    FROM dams d 
                    JOIN horses h ON d.horse_id = h.horse_id 
                    WHERE d.horse_id = ?
                """, (self.parent_id,)).fetchone()
                p_name = parent_row["name"] if parent_row else "不明"
                self.lbl_title.setText(f"🌸 繁殖牝馬: {p_name} の産駒一覧")

                progeny_rows = conn.execute("""
                    SELECT h.*, 
                           sh.name as mate_name,
                           COUNT(res.result_id) as total_races,
                           SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END) as wins
                    FROM horses h
                    LEFT JOIN horses sh ON h.sire_id = sh.horse_id
                    LEFT JOIN results res ON h.horse_id = res.horse_id
                    WHERE h.dam_id = ?
                    GROUP BY h.horse_id
                    ORDER BY h.prize_money DESC, h.birth_year DESC
                """, (self.parent_id,)).fetchall()

        sex_map = {"colt": "牡", "filly": "牝", "horse": "牡", "mare": "牝", "gelding": "セ"}
        
        self.table.setRowCount(len(progeny_rows))
        total_p = len(progeny_rows)
        win_p = sum(1 for r in progeny_rows if (r["wins"] or 0) > 0)
        self.lbl_stats.setText(f"総頭数: {total_p}頭 / 勝ち上がり: {win_p}頭")

        for idx, r in enumerate(progeny_rows):
            h_name = r["name"]
            b_year = f"{r['birth_year']}年"
            sex_age = f"{sex_map.get(r['sex'], '')}{r['age']}"
            mate = r["mate_name"] or "不明"
            races = r["total_races"] or 0
            wins = r["wins"] or 0
            rec_str = f"{races}戦{wins}勝"
            prz_val = r["prize_money"] or 0
            if prz_val >= 100_000_000:
                prize_str = f"{prz_val / 100_000_000:.2f}億円"
            else:
                prize_str = f"{prz_val // 10000:,}万円"
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
                if races == 0:
                    status_str = "未出走"
                    status_col = "#34d399"
                else:
                    status_str = "現役"
                    status_col = "#22c55e"
            else:
                status_str = "引退"
                status_col = "#94a3b8"

            # 主な勝鞍を取得
            with self.db.session() as conn:
                best_win = conn.execute("""
                    SELECT rc.name, rc.grade
                    FROM results res
                    JOIN races rc ON res.race_id = rc.race_id
                    WHERE res.horse_id = ? AND res.finish_position = 1
                    ORDER BY CASE rc.grade
                        WHEN 'G1' THEN 1 WHEN 'G2' THEN 2 WHEN 'G3' THEN 3
                        WHEN 'L' THEN 4 WHEN 'OP' THEN 5 ELSE 6 END ASC
                    LIMIT 1
                """, (r["horse_id"],)).fetchone()
                best_win_str = f"{best_win['name']} ({best_win['grade']})" if best_win else ("未勝利" if wins == 0 else "条件戦")

            name_item = QTableWidgetItem(h_name)
            name_item.setData(Qt.ItemDataRole.UserRole, r["horse_id"])
            name_item.setForeground(Qt.GlobalColor.cyan)

            status_item = QTableWidgetItem(status_str)
            status_item.setForeground(QColor(status_col))

            items = [
                name_item,
                QTableWidgetItem(b_year),
                QTableWidgetItem(sex_age),
                QTableWidgetItem(mate),
                QTableWidgetItem(rec_str),
                QTableWidgetItem(prize_str),
                QTableWidgetItem(best_win_str),
                status_item,
            ]

            for c, itm in enumerate(items):
                if c not in (0, 3, 6):
                    itm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(idx, c, itm)

    def _on_cell_clicked(self, row: int, col: int) -> None:
        """産駒名クリックで競走馬詳細ダイアログを表示"""
        if col == 0:
            item = self.table.item(row, 0)
            if item:
                horse_id = item.data(Qt.ItemDataRole.UserRole)
                if horse_id:
                    dlg = HorseDetailDialog(self.db, horse_id, parent=self)
                    dlg.exec()
