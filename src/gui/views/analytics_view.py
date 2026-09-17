"""
タイム時系列推移 & 能力進化グラフビュー (PyQt6 / Matplotlib)
- 1600m走破タイム推移グラフ（世代別平均タイム、最速タイム、インフレ・進化の追跡）
- 世代別能力値推移（スピード・持久力・瞬発力）
"""

from __future__ import annotations

from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.db.database import Database
from src.gui.widgets.mpl_canvas import MplCanvas


class AnalyticsView(QWidget):
    """走破タイム推移 & 能力進化分析画面"""

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self._init_ui()
        self.refresh_charts()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # コントロールバー
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 8px;")
        ctrl_layout = QHBoxLayout(ctrl_frame)
        ctrl_layout.setContentsMargins(12, 8, 12, 8)

        ctrl_layout.addWidget(QLabel("馬場:"))
        self.combo_surface = QComboBox()
        self.combo_surface.addItem("芝", "turf")
        self.combo_surface.addItem("ダート", "dirt")
        self.combo_surface.currentIndexChanged.connect(self.refresh_charts)
        ctrl_layout.addWidget(self.combo_surface)

        ctrl_layout.addWidget(QLabel("距離:"))
        self.combo_dist = QComboBox()
        self.distances = [1000, 1200, 1400, 1600, 1700, 1800, 2000, 2200, 2400, 2500, 3000, 3200]
        for d in self.distances:
            self.combo_dist.addItem(f"{d}m", d)
        self.combo_dist.setCurrentIndex(3)  # 1600m
        self.combo_dist.currentIndexChanged.connect(self.refresh_charts)
        ctrl_layout.addWidget(self.combo_dist)

        ctrl_layout.addStretch()

        btn_reload = QPushButton("🔄 グラフ再描画")
        btn_reload.clicked.connect(self.refresh_charts)
        ctrl_layout.addWidget(btn_reload)

        main_layout.addWidget(ctrl_frame)

        # グラフ描画エリア（左右に2つのMatplotlib Canvas）
        charts_layout = QHBoxLayout()
        charts_layout.setSpacing(12)

        # 左: タイム推移グラフ
        time_box = QFrame()
        time_box.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 8px;")
        time_layout = QVBoxLayout(time_box)
        time_layout.setContentsMargins(10, 10, 10, 10)
        self.time_title = QLabel("走破タイム推移（年次・世代別）")
        self.time_title.setStyleSheet("font-weight: bold; color: #38bdf8; font-size: 14px;")
        time_layout.addWidget(self.time_title)

        self.canvas_time = MplCanvas(self, width=5.0, height=4.0)
        time_layout.addWidget(self.canvas_time)
        charts_layout.addWidget(time_box)

        # 右: 能力値推移グラフ
        stat_box = QFrame()
        stat_box.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 8px;")
        stat_layout = QVBoxLayout(stat_box)
        stat_layout.setContentsMargins(10, 10, 10, 10)
        stat_title = QLabel("世代別ポリジーン能力値進化")
        stat_title.setStyleSheet("font-weight: bold; color: #10b981; font-size: 14px;")
        stat_layout.addWidget(stat_title)

        self.canvas_stats = MplCanvas(self, width=5.0, height=4.0)
        stat_layout.addWidget(self.canvas_stats)
        charts_layout.addWidget(stat_box)

        main_layout.addLayout(charts_layout)

    def refresh_charts(self) -> None:
        """グラフデータを集計して描画"""
        target_dist = self.combo_dist.currentData() or 1600
        target_surface = self.combo_surface.currentData() or "turf"
        surf_jp = "芝" if target_surface == "turf" else "ダート"

        self.time_title.setText(f"{surf_jp} {target_dist}m 走破タイム推移（年次別）")

        # 1. タイム推移の集計
        with self.db.session() as conn:
            # 年ごとの平均タイム・最速タイム
            time_rows = conn.execute(
                """
                SELECT rc.year,
                       AVG(r.finish_time) as avg_time,
                       MIN(r.finish_time) as min_time,
                       COUNT(r.result_id) as count
                FROM results r
                JOIN races rc ON r.race_id = rc.race_id
                WHERE rc.distance = ? AND rc.surface = ? AND r.finish_position = 1
                GROUP BY rc.year
                ORDER BY rc.year ASC
                """,
                (target_dist, target_surface),
            ).fetchall()

            # 2. 世代別能力値推移の集計 (birth_yearごと)
            stat_rows = conn.execute(
                """
                SELECT birth_year,
                       AVG(speed) as avg_spd,
                       AVG(stamina) as avg_sta,
                       AVG(acceleration) as avg_acc,
                       COUNT(*) as count
                FROM horses
                WHERE birth_year >= 1
                GROUP BY birth_year
                ORDER BY birth_year ASC
                """
            ).fetchall()

        # タイムグラフ描画
        self.canvas_time.clear()
        ax1 = self.canvas_time.axes

        if time_rows:
            years = [r["year"] for r in time_rows]
            avg_times = [r["avg_time"] for r in time_rows]
            min_times = [r["min_time"] for r in time_rows]

            ax1.plot(years, avg_times, marker="o", color="#38bdf8", label="平均勝ちタイム", linewidth=2)
            ax1.plot(years, min_times, marker="s", color="#f59e0b", label="最速タイム", linewidth=2, linestyle="--")
            ax1.set_xlabel("シミュレーション年度 (Year)")
            ax1.set_ylabel("走破タイム (秒)")
            ax1.legend(facecolor="#161b26", edgecolor="#334155", labelcolor="#cbd5e1")
            ax1.set_title(f"芝 {target_dist}m 勝ち時計の年次推移")
        else:
            ax1.text(0.5, 0.5, f"芝 {target_dist}m のレース消化記録がまだありません",
                     horizontalalignment="center", verticalalignment="center",
                     transform=ax1.transAxes, color="#94a3b8", fontsize=11)
        self.canvas_time.draw()

        # 能力推移グラフ描画
        self.canvas_stats.clear()
        ax2 = self.canvas_stats.axes

        if stat_rows:
            b_years = [r["birth_year"] for r in stat_rows]
            spds = [r["avg_spd"] for r in stat_rows]
            stas = [r["avg_sta"] for r in stat_rows]
            accs = [r["avg_acc"] for r in stat_rows]

            ax2.plot(b_years, spds, marker="o", color="#ef4444", label="最高速度", linewidth=2)
            ax2.plot(b_years, stas, marker="^", color="#10b981", label="持久力", linewidth=2)
            ax2.plot(b_years, accs, marker="d", color="#f59e0b", label="瞬発力", linewidth=2)
            ax2.axhline(50.0, color="#64748b", linestyle=":", label="基準平均値 (50.0)")
            ax2.set_xlabel("生年・世代 (Birth Year)")
            ax2.set_ylabel("ポリジーン能力平均値")
            ax2.set_ylim(40.0, 70.0)
            ax2.legend(facecolor="#161b26", edgecolor="#334155", labelcolor="#cbd5e1")
            ax2.set_title("世代別平均能力値の進化推移")
        else:
            ax2.text(0.5, 0.5, "誕生世代データがまだありません",
                     horizontalalignment="center", verticalalignment="center",
                     transform=ax2.transAxes, color="#94a3b8", fontsize=11)
        self.canvas_stats.draw()
