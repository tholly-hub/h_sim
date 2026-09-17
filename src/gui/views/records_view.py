"""
コースレコード一覧ビュー (RecordsView)
- 各競馬場（JRA 8場、地方 4場）のコースレコードタイム
- 芝・ダート別、各距離別の最速走破タイム、達成年、達成馬名の一覧表
"""

from __future__ import annotations

from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
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


TRACK_NAMES = [
    "全競馬場",
    "東京", "中山", "阪神", "京都", "中京", "福島", "新潟", "小倉",
    "大井", "川崎", "船橋", "盛岡"
]


def format_finish_time(seconds: float) -> str:
    """走破タイムを分:秒.厘 (例: 1:33.4) 形式にフォーマット"""
    if seconds <= 0:
        return "--:--.-"
    m = int(seconds // 60)
    s = seconds - (m * 60)
    return f"{m}:{s:04.1f}"


class RecordsView(QWidget):
    """競馬場別コースレコード一覧タブ"""

    def __init__(self, db: Optional[Database] = None):
        super().__init__()
        self.db = db or get_db()
        self._init_ui()
        self.refresh_records()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # フィルタコントロール
        filter_frame = QFrame()
        filter_frame.setObjectName("CardFrame")
        filter_layout = QHBoxLayout(filter_frame)

        filter_layout.addWidget(QLabel("競馬場:"))
        self.combo_track = QComboBox()
        self.combo_track.addItems(TRACK_NAMES)
        self.combo_track.currentIndexChanged.connect(self.refresh_records)
        filter_layout.addWidget(self.combo_track)

        filter_layout.addWidget(QLabel("馬場:"))
        self.combo_surface = QComboBox()
        self.combo_surface.addItems(["全て", "芝", "ダート"])
        self.combo_surface.currentIndexChanged.connect(self.refresh_records)
        filter_layout.addWidget(self.combo_surface)

        self.btn_refresh = QPushButton("🔄 最新化")
        self.btn_refresh.clicked.connect(self.refresh_records)
        filter_layout.addWidget(self.btn_refresh)
        filter_layout.addStretch()

        layout.addWidget(filter_frame)

        # レコードタイム一覧テーブル
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "競馬場", "馬場", "距離", "レコードタイム", "上がり3F", "達成年", "達成馬名"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout.addWidget(self.table)

    def refresh_records(self) -> None:
        """データベースから各競馬場・トラック・距離別の最速レコードを抽出してテーブルを更新"""
        track_filter = self.combo_track.currentText()
        surface_filter = self.combo_surface.currentText()

        query = """
            SELECT 
                r.track_id,
                r.surface,
                r.distance,
                MIN(res.finish_time) AS record_time,
                res.last_3f,
                r.year,
                h.name AS horse_name
            FROM results res
            JOIN races r ON res.race_id = r.race_id
            JOIN horses h ON res.horse_id = h.horse_id
            WHERE res.finish_position = 1
        """
        params = []

        if track_filter != "全競馬場":
            query += " AND r.track_id = ?"
            params.append(track_filter)

        if surface_filter == "芝":
            query += " AND r.surface = 'turf'"
        elif surface_filter == "ダート":
            query += " AND r.surface = 'dirt'"

        query += """
            GROUP BY r.track_id, r.surface, r.distance
            ORDER BY 
                CASE r.track_id
                    WHEN '東京' THEN 1 WHEN '中山' THEN 2 WHEN '阪神' THEN 3 WHEN '京都' THEN 4
                    WHEN '中京' THEN 5 WHEN '福島' THEN 6 WHEN '新潟' THEN 7 WHEN '小倉' THEN 8
                    WHEN '大井' THEN 9 WHEN '川崎' THEN 10 WHEN '船橋' THEN 11 WHEN '盛岡' THEN 12
                    ELSE 99 END,
                r.surface DESC,
                r.distance ASC
        """

        with self.db.session() as conn:
            rows = conn.execute(query, params).fetchall()

        self.table.setRowCount(len(rows))
        for row_idx, r in enumerate(rows):
            track_name = r["track_id"]
            surf_name = "芝" if r["surface"] == "turf" else "ダート"
            dist_str = f"{r['distance']}m"
            rec_time = format_finish_time(r["record_time"])
            last_3f = f"{r['last_3f']:.1f}s" if r["last_3f"] else "--.-s"
            year_str = f"{r['year']}年"
            horse_name = r["horse_name"]

            items = [
                QTableWidgetItem(track_name),
                QTableWidgetItem(surf_name),
                QTableWidgetItem(dist_str),
                QTableWidgetItem(rec_time),
                QTableWidgetItem(last_3f),
                QTableWidgetItem(year_str),
                QTableWidgetItem(horse_name),
            ]
            for col_idx, item in enumerate(items):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col_idx == 3:
                    item.setForeground(Qt.GlobalColor.yellow)
                self.table.setItem(row_idx, col_idx, item)
