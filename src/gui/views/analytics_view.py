"""
タイム時系列推移 & 能力進化グラフビュー (PyQt6 / Matplotlib)
- 全距離・全馬場（芝・ダート）の走破タイム推移グラフ
- コースレコード更新点のハイライト表示 & レコード保持馬詳細（結果・動画ボタン完備）
- 世代別ポリジーン能力値推移（birth_year >= 0 対応、初期世代からの進化推跡）
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
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

import matplotlib.ticker as ticker

from src.db.database import Database
from src.gui.views.race_dialogs import RaceResultDialog, RaceViewDialog
from src.gui.views.records_view import format_finish_time
from src.gui.widgets.mpl_canvas import MplCanvas
from src.race.engine import clean_race_name


ALL_DISTANCES = [
    1000, 1200, 1400, 1500, 1600, 1700, 1800,
    2000, 2100, 2200, 2400, 2500, 2600, 3000, 3200, 3600
]


class AnalyticsView(QWidget):
    """走破タイム推移 & 能力進化分析画面"""

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.current_record_race_id: Optional[int] = None
        self._init_ui()
        self.refresh_charts()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(10)

        # コントロールバー
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 8px;")
        ctrl_layout = QHBoxLayout(ctrl_frame)
        ctrl_layout.setContentsMargins(12, 8, 12, 8)
        ctrl_layout.setSpacing(12)

        ctrl_layout.addWidget(QLabel("馬場:"))
        self.combo_surface = QComboBox()
        self.combo_surface.addItem("芝 (Turf)", "turf")
        self.combo_surface.addItem("ダート (Dirt)", "dirt")
        self.combo_surface.currentIndexChanged.connect(self.refresh_charts)
        ctrl_layout.addWidget(self.combo_surface)

        ctrl_layout.addWidget(QLabel("距離:"))
        self.combo_dist = QComboBox()
        for d in ALL_DISTANCES:
            self.combo_dist.addItem(f"{d}m", d)
        self.combo_dist.setCurrentIndex(4)  # 1600m デフォルト
        self.combo_dist.currentIndexChanged.connect(self.refresh_charts)
        ctrl_layout.addWidget(self.combo_dist)

        ctrl_layout.addStretch()

        btn_reload = QPushButton("🔄 グラフ再描画")
        btn_reload.setStyleSheet("background-color: #0284c7; color: #ffffff; font-weight: bold; padding: 4px 12px; border-radius: 4px;")
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
        time_layout.setSpacing(6)

        self.time_title = QLabel("走破タイム推移（年次・世代別）")
        self.time_title.setStyleSheet("font-weight: bold; color: #38bdf8; font-size: 14px;")
        time_layout.addWidget(self.time_title)

        self.canvas_time = MplCanvas(self, width=5.0, height=4.0)
        time_layout.addWidget(self.canvas_time)

        # レコード情報バー & アクションボタン
        self.record_bar = QFrame()
        self.record_bar.setStyleSheet("background-color: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 4px 8px;")
        rec_layout = QHBoxLayout(self.record_bar)
        rec_layout.setContentsMargins(6, 4, 6, 4)

        self.lbl_record_info = QLabel("🏆 コースレコード: -")
        self.lbl_record_info.setStyleSheet("color: #facc15; font-weight: bold; font-size: 12px;")
        rec_layout.addWidget(self.lbl_record_info)

        rec_layout.addStretch()

        self.btn_rec_result = QPushButton("🏁 レース結果")
        self.btn_rec_result.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 11px; font-weight: bold; padding: 3px 8px; border: 1px solid #0284c7; border-radius: 3px;")
        self.btn_rec_result.clicked.connect(self._open_record_result)
        self.btn_rec_result.setEnabled(False)
        rec_layout.addWidget(self.btn_rec_result)

        self.btn_rec_replay = QPushButton("🎬 レース動画")
        self.btn_rec_replay.setStyleSheet("background-color: #1e293b; color: #c084fc; font-size: 11px; font-weight: bold; padding: 3px 8px; border: 1px solid #9333ea; border-radius: 3px;")
        self.btn_rec_replay.clicked.connect(self._open_record_replay)
        self.btn_rec_replay.setEnabled(False)
        rec_layout.addWidget(self.btn_rec_replay)

        time_layout.addWidget(self.record_bar)
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

        self.time_title.setText(f"{surf_jp} {target_dist}m 走破タイム推移（年次別・レコード点）")

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

            # コース全期間最速レコードの特定
            rec_row = conn.execute(
                """
                SELECT r.race_id, rc.year, rc.name as race_name, rc.track_id,
                       r.finish_time, h.name as horse_name
                FROM results r
                JOIN races rc ON r.race_id = rc.race_id
                JOIN horses h ON r.horse_id = h.horse_id
                WHERE rc.distance = ? AND rc.surface = ? AND r.finish_position = 1
                ORDER BY r.finish_time ASC, rc.year DESC
                LIMIT 1
                """,
                (target_dist, target_surface),
            ).fetchone()

            # 2. 世代別能力値推移の集計 (birth_year >= 0 で初期世代も網羅)
            stat_rows = conn.execute(
                """
                SELECT birth_year,
                       AVG(speed) as avg_spd,
                       AVG(stamina) as avg_sta,
                       AVG(acceleration) as avg_acc,
                       COUNT(*) as count
                FROM horses
                WHERE birth_year >= 0
                GROUP BY birth_year
                ORDER BY birth_year ASC
                """
            ).fetchall()

        # レコード情報のUI反映
        if rec_row and rec_row["finish_time"]:
            self.current_record_race_id = rec_row["race_id"]
            t_str = format_finish_time(rec_row["finish_time"])
            r_name = clean_race_name(rec_row["race_name"])
            self.lbl_record_info.setText(
                f"🏆 レコード: {t_str} [{rec_row['horse_name']}] ({rec_row['year']}年 {rec_row['track_id']} {r_name})"
            )
            self.btn_rec_result.setEnabled(True)
            self.btn_rec_replay.setEnabled(True)
        else:
            self.current_record_race_id = None
            self.lbl_record_info.setText(f"🏆 コースレコード: （{surf_jp}{target_dist}mの記録なし）")
            self.btn_rec_result.setEnabled(False)
            self.btn_rec_replay.setEnabled(False)

        # タイムグラフ描画
        self.canvas_time.clear()
        ax1 = self.canvas_time.axes

        if time_rows:
            years = [r["year"] for r in time_rows]
            avg_times = [r["avg_time"] for r in time_rows]

            # 歴代レコードタイム推移（その年までに記録された史上最速タイム）
            cum_records = []
            cur_best = float("inf")
            for r in time_rows:
                if r["min_time"] < cur_best:
                    cur_best = r["min_time"]
                cum_records.append(cur_best)

            ax1.plot(years, avg_times, marker="o", color="#38bdf8", label="年間平均勝ちタイム (年末確定値)", linewidth=2)
            ax1.plot(years, cum_records, marker="s", color="#f59e0b", label="歴代レコードタイム推移", linewidth=2, linestyle="--")

            # コースレコード保持点（最速レコード）がある場合、スターマーカー★でハイライト
            if rec_row and rec_row["year"] in years:
                ax1.plot(
                    [rec_row["year"]], [rec_row["finish_time"]],
                    marker="*", markersize=14, color="#ef4444", label=f"史上最速レコード ({rec_row['horse_name']})"
                )

            # 縦軸を 分:秒 (例: 1:33.4) フォーマットに設定
            def _time_formatter(x, pos):
                return format_finish_time(x)

            ax1.yaxis.set_major_formatter(ticker.FuncFormatter(_time_formatter))
            ax1.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

            ax1.set_xlabel("年度 (Year)")
            ax1.set_ylabel("走破タイム (分:秒)")
            ax1.legend(facecolor="#161b26", edgecolor="#334155", labelcolor="#cbd5e1")
            ax1.set_title(f"{surf_jp} {target_dist}m 勝ち時計の年次・レコード推移")
        else:
            ax1.text(
                0.5, 0.5, f"{surf_jp} {target_dist}m のレース消化記録がまだありません",
                horizontalalignment="center", verticalalignment="center",
                transform=ax1.transAxes, color="#94a3b8", fontsize=11
            )
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

            all_vals = spds + stas + accs
            y_min = max(20.0, min(all_vals) - 5.0)
            y_max = min(100.0, max(all_vals) + 5.0)
            ax2.set_ylim(y_min, y_max)

            ax2.legend(facecolor="#161b26", edgecolor="#334155", labelcolor="#cbd5e1")
            ax2.set_title("世代別平均能力値の進化推移")
        else:
            ax2.text(
                0.5, 0.5, "誕生世代データがまだありません",
                horizontalalignment="center", verticalalignment="center",
                transform=ax2.transAxes, color="#94a3b8", fontsize=11
            )
        self.canvas_stats.draw()

    def _open_record_result(self) -> None:
        if self.current_record_race_id:
            dlg = RaceResultDialog(self.db, self.current_record_race_id, parent=self)
            dlg.exec()

    def _open_record_replay(self) -> None:
        if self.current_record_race_id:
            dlg = RaceViewDialog(self.db, self.current_record_race_id, parent=self)
            dlg.exec()
