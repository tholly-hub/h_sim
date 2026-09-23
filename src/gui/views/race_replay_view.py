"""
レース結果一覧 & 2Dトラック・レースリプレイビュー (PyQt6)
- 消化レースの選択・結果着順表
- 0.1秒ごとの展開データを用いたリアルタイム2Dアニメーション再生
- 再生、一時停止、シーク、速度変更
"""

from __future__ import annotations

import json
import math
from typing import Any, Optional
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.db.database import Database
from src.gui.widgets.race_board_widget import RaceBoardWidget
from src.gui.widgets.track_canvas import TrackCanvas, JRA_BRACKET_COLORS
from src.race.engine import clean_race_name, get_jra_bracket
from src.race.track import get_track_info, check_is_course_record



TRACK_SORT_ORDER: dict[str, int] = {
    "TOKYO": 1,
    "NAKAYAMA": 2,
    "KYOTO": 3,
    "HANSHIN": 4,
    "CHUKYO": 5,
    "NIIGATA": 6,
    "FUKUSHIMA": 7,
    "KOKURA": 8,
    "OI": 9,
    "KAWASAKI": 10,
    "FUNABASHI": 11,
    "MORIOKA": 12,
}

GRADE_SORT_ORDER: dict[str, int] = {
    "MAIDEN": 1,
    "NEWCOMER": 2,
    "COND_1W": 3,
    "COND_2W": 4,
    "COND_3W": 5,
    "L": 6,
    "OP": 6,
    "G3": 7,
    "G2": 8,
    "G1": 9,
}


class RaceReplayView(QWidget):
    """レース結果一覧 & 2Dレースリプレイ再生画面"""

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.current_race_id: Optional[int] = None
        self.current_year: Optional[int] = None
        self.current_month: Optional[int] = None
        self.current_week: Optional[int] = None
        self._is_board_revealed: bool = False
        self._board_timer: Optional[QTimer] = None
        self._dialog_timer: Optional[QTimer] = None
        self._init_ui()
        self.load_race_list()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # 1. レース選択 & ナビゲーションバー (高さを38pxに固定してスリム化)
        sel_frame = QFrame()
        sel_frame.setFixedHeight(38)
        sel_frame.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 4px;")
        sel_layout = QHBoxLayout(sel_frame)
        sel_layout.setContentsMargins(6, 2, 6, 2)
        sel_layout.setSpacing(5)

        btn_style_nav = "background-color: #334155; color: #ffffff; font-weight: bold; padding: 2px 6px; font-size: 11px; border-radius: 3px;"
        lbl_style = "font-size: 11px; color: #94a3b8; font-weight: bold;"

        # 週ナビゲーション [◀ 前週] [次週 ▶]
        self.btn_prev_week = QPushButton("◀ 前週")
        self.btn_prev_week.setStyleSheet(btn_style_nav)
        self.btn_prev_week.clicked.connect(self._on_prev_week_clicked)
        sel_layout.addWidget(self.btn_prev_week)

        self.btn_next_week = QPushButton("次週 ▶")
        self.btn_next_week.setStyleSheet(btn_style_nav)
        self.btn_next_week.clicked.connect(self._on_next_week_clicked)
        sel_layout.addWidget(self.btn_next_week)

        # レースナビゲーション [◀ 前R] [次R ▶]
        self.btn_prev_race = QPushButton("◀ 前R")
        self.btn_prev_race.setStyleSheet(btn_style_nav)
        self.btn_prev_race.clicked.connect(self._on_prev_race_clicked)
        sel_layout.addWidget(self.btn_prev_race)

        self.btn_next_race = QPushButton("次R ▶")
        self.btn_next_race.setStyleSheet(btn_style_nav)
        self.btn_next_race.clicked.connect(self._on_next_race_clicked)
        sel_layout.addWidget(self.btn_next_race)

        self.btn_switch_track = QPushButton("📍 競馬場切替")
        self.btn_switch_track.setStyleSheet("background-color: #0284c7; color: #ffffff; font-weight: bold; padding: 2px 6px; font-size: 11px; border-radius: 3px;")
        self.btn_switch_track.clicked.connect(self._on_switch_track_clicked)
        sel_layout.addWidget(self.btn_switch_track)

        # グレードフィルター
        lbl_grade = QLabel("グレード:")
        lbl_grade.setStyleSheet(lbl_style)
        sel_layout.addWidget(lbl_grade)

        self.combo_filter_grade = QComboBox()
        self.combo_filter_grade.setStyleSheet("font-size: 11px; padding: 1px 3px;")
        self.combo_filter_grade.addItem("全グレード", None)
        self.combo_filter_grade.addItem("🏆 G1 のみ", "G1")
        self.combo_filter_grade.addItem("🎖 重賞 (G1-G3)", "GRADED")
        self.combo_filter_grade.addItem("🏇 オープン・条件戦", "OP_COND")
        self.combo_filter_grade.addItem("🌱 未勝利・新馬", "MAIDEN")
        self.combo_filter_grade.currentIndexChanged.connect(self.load_race_list)
        sel_layout.addWidget(self.combo_filter_grade)

        # 競馬場フィルター (JRA 8場 + 地方 4場)
        lbl_track = QLabel("競馬場:")
        lbl_track.setStyleSheet(lbl_style)
        sel_layout.addWidget(lbl_track)

        self.combo_filter_track = QComboBox()
        self.combo_filter_track.setStyleSheet("font-size: 11px; padding: 1px 3px;")
        self.combo_filter_track.addItem("全競馬場", None)
        self.combo_filter_track.addItem("東京競馬場 (JRA左)", "TOKYO")
        self.combo_filter_track.addItem("中山競馬場 (JRA右)", "NAKAYAMA")
        self.combo_filter_track.addItem("阪神競馬場 (JRA右)", "HANSHIN")
        self.combo_filter_track.addItem("京都競馬場 (JRA右)", "KYOTO")
        self.combo_filter_track.addItem("中京競馬場 (JRA左)", "CHUKYO")
        self.combo_filter_track.addItem("新潟競馬場 (JRA左)", "NIIGATA")
        self.combo_filter_track.addItem("福島競馬場 (JRA右)", "FUKUSHIMA")
        self.combo_filter_track.addItem("小倉競馬場 (JRA右)", "KOKURA")
        self.combo_filter_track.addItem("大井競馬場 (地方右)", "OI")
        self.combo_filter_track.addItem("川崎競馬場 (地方左)", "KAWASAKI")
        self.combo_filter_track.addItem("船橋競馬場 (地方左)", "FUNABASHI")
        self.combo_filter_track.addItem("盛岡競馬場 (地方左)", "MORIOKA")
        self.combo_filter_track.currentIndexChanged.connect(self.load_race_list)
        sel_layout.addWidget(self.combo_filter_track)

        # レース時期表示（何月何週のみを表示）
        lbl_held = QLabel("開催:")
        lbl_held.setStyleSheet(lbl_style)
        sel_layout.addWidget(lbl_held)

        self.lbl_race_week = QLabel("―月―週")
        self.lbl_race_week.setStyleSheet("""
            color: #fbbf24;
            font-size: 11px;
            font-weight: bold;
            padding: 1px 5px;
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 3px;
        """)
        sel_layout.addWidget(self.lbl_race_week)

        # 青字のレース名プルダウンメニュー（当該週のレース一覧）
        lbl_race = QLabel("レース:")
        lbl_race.setStyleSheet(lbl_style)
        sel_layout.addWidget(lbl_race)

        self.combo_races = QComboBox()
        self.combo_races.setMinimumWidth(260)
        self.combo_races.setStyleSheet("""
            QComboBox {
                color: #38bdf8;
                font-weight: bold;
                font-size: 11px;
                background-color: #0f172a;
                border: 1px solid #0284c7;
                border-radius: 3px;
                padding: 1px 5px;
            }
            QComboBox::drop-down {
                border-left: 1px solid #0284c7;
            }
            QComboBox QAbstractItemView {
                background-color: #0f172a;
                color: #e2e8f0;
                selection-background-color: #0284c7;
                selection-color: #ffffff;
            }
        """)
        self.combo_races.currentIndexChanged.connect(self._on_race_selected)
        sel_layout.addWidget(self.combo_races)

        self.btn_refresh = QPushButton("🔄 更新")
        self.btn_refresh.setStyleSheet("background-color: #334155; color: #ffffff; font-weight: bold; padding: 2px 6px; font-size: 11px; border-radius: 3px;")
        self.btn_refresh.clicked.connect(self.load_race_list)
        sel_layout.addWidget(self.btn_refresh)

        # 📋 出馬表ダイアログ表示ボタン
        self.btn_show_entries = QPushButton("📋 出馬表")
        self.btn_show_entries.setStyleSheet("background-color: #0284c7; color: #ffffff; font-weight: bold; padding: 2px 8px; font-size: 11px; border-radius: 3px;")
        self.btn_show_entries.clicked.connect(self._show_race_entry_dialog)
        sel_layout.addWidget(self.btn_show_entries)

        # 🏁 詳細結果ダイアログ表示ボタン
        self.btn_show_results = QPushButton("🏁 詳細結果")
        self.btn_show_results.setStyleSheet("background-color: #059669; color: #ffffff; font-weight: bold; padding: 2px 8px; font-size: 11px; border-radius: 3px;")
        self.btn_show_results.clicked.connect(self._show_race_result_dialog)
        sel_layout.addWidget(self.btn_show_results)

        sel_layout.addStretch()

        # 1段目はstretch=0（高さ38px固定）、2段目TrackCanvasはstretch=1（画面全体に最大化）、3段目ctrl_barはstretch=0（高さ固定）
        sel_frame.setSizePolicy(QFrame().sizePolicy().horizontalPolicy(), QFrame().sizePolicy().verticalPolicy())
        main_layout.addWidget(sel_frame, stretch=0)

        # 2. メイン表示エリア (TrackCanvasが画面横幅・高さをフル活用)
        self.track_canvas = TrackCanvas()
        self.track_canvas.time_updated.connect(self._on_canvas_time_updated)
        self.track_canvas.playback_finished.connect(self._on_playback_finished)
        main_layout.addWidget(self.track_canvas, stretch=1)

        # 3. コントロールバー（再生・停止・シーク・速度・視点）
        ctrl_bar = QFrame()
        ctrl_bar.setFixedHeight(38)
        ctrl_bar.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 6px;")
        ctrl_layout = QHBoxLayout(ctrl_bar)
        ctrl_layout.setContentsMargins(8, 2, 8, 2)
        ctrl_layout.setSpacing(8)

        self.btn_play = QPushButton("▶ 再生")
        self.btn_play.setStyleSheet("padding: 3px 10px; font-size: 12px; font-weight: bold;")
        self.btn_play.clicked.connect(self._toggle_play)
        ctrl_layout.addWidget(self.btn_play)

        self.btn_stop = QPushButton("■ 停止")
        self.btn_stop.setStyleSheet("padding: 3px 10px; font-size: 12px; font-weight: bold;")
        self.btn_stop.clicked.connect(self.track_canvas.stop)
        ctrl_layout.addWidget(self.btn_stop)

        # タイム表示
        self.lbl_time = QLabel("00:00.0 / 00:00.0")
        self.lbl_time.setStyleSheet("font-family: monospace; font-size: 12px; color: #f8fafc;")
        ctrl_layout.addWidget(self.lbl_time)

        # シークスライダー
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.sliderMoved.connect(self._on_slider_moved)
        ctrl_layout.addWidget(self.slider)

        # 速度変更 (デフォルト: 4.0x)
        lbl_speed = QLabel("速度:")
        lbl_speed.setStyleSheet("font-size: 11px; color: #94a3b8;")
        ctrl_layout.addWidget(lbl_speed)
        self.combo_speed = QComboBox()
        self.combo_speed.setStyleSheet("font-size: 11px; padding: 1px 4px;")
        self.combo_speed.addItems(["1.0x", "2.0x", "4.0x"])
        self.combo_speed.setCurrentIndex(2)
        self.combo_speed.currentIndexChanged.connect(self._on_speed_changed)
        ctrl_layout.addWidget(self.combo_speed)

        # 🎥 カメラ視点切替
        lbl_cam = QLabel("視点:")
        lbl_cam.setStyleSheet("font-size: 11px; color: #94a3b8;")
        ctrl_layout.addWidget(lbl_cam)
        self.combo_camera = QComboBox()
        self.combo_camera.setStyleSheet("font-size: 11px; padding: 1px 4px;")
        self.combo_camera.addItem("2D 俯瞰マップ", "2d")
        self.combo_camera.addItem("3D 立体バードビュー", "3d_bird")
        self.combo_camera.addItem("3D チェイスカメラ", "3d_chase")
        self.combo_camera.setCurrentIndex(0)
        self.combo_camera.currentIndexChanged.connect(self._on_camera_changed)
        ctrl_layout.addWidget(self.combo_camera)

        main_layout.addWidget(ctrl_bar, stretch=0)

        # 後方互換性用（テスト等の属性アクセス用）
        self.board_widget = RaceBoardWidget()
        self.board_widget.setVisible(False)

    def _on_prev_week_clicked(self) -> None:
        """前の週のレース一覧に移動"""
        with self.db.session() as conn:
            # 現在の週より前の完了週を取得
            if self.current_year is not None and self.current_week is not None:
                row = conn.execute(
                    """
                    SELECT r.year, r.month, r.week
                    FROM results res
                    JOIN races r ON res.race_id = r.race_id
                    WHERE (r.year < ?) OR (r.year = ? AND r.week < ?)
                    ORDER BY r.year DESC, r.week DESC
                    LIMIT 1
                    """,
                    (self.current_year, self.current_year, self.current_week),
                ).fetchone()
                if row:
                    self.current_year = int(row["year"])
                    self.current_month = int(row["month"])
                    self.current_week = int(row["week"])
                    self.current_race_id = None
                    self.load_race_list()

    def _on_next_week_clicked(self) -> None:
        """次の週のレース一覧に移動"""
        with self.db.session() as conn:
            # 現在の週より後の完了週を取得
            if self.current_year is not None and self.current_week is not None:
                row = conn.execute(
                    """
                    SELECT r.year, r.month, r.week
                    FROM results res
                    JOIN races r ON res.race_id = r.race_id
                    WHERE (r.year > ?) OR (r.year = ? AND r.week > ?)
                    ORDER BY r.year ASC, r.week ASC
                    LIMIT 1
                    """,
                    (self.current_year, self.current_year, self.current_week),
                ).fetchone()
                if row:
                    self.current_year = int(row["year"])
                    self.current_month = int(row["month"])
                    self.current_week = int(row["week"])
                    self.current_race_id = None
                    self.load_race_list()

    def _on_prev_race_clicked(self) -> None:
        """前のレースに移動（リスト上方向）"""
        idx = self.combo_races.currentIndex()
        if idx > 0:
            self.combo_races.setCurrentIndex(idx - 1)

    def _on_next_race_clicked(self) -> None:
        """次のレースに移動（リスト下方向）"""
        idx = self.combo_races.currentIndex()
        if idx < self.combo_races.count() - 1:
            self.combo_races.setCurrentIndex(idx + 1)

    def _on_switch_track_clicked(self) -> None:
        """別の競馬場に順次切り替え"""
        count = self.combo_filter_track.count()
        if count <= 1:
            return
        cur = self.combo_filter_track.currentIndex()
        # "全競馬場"(0)をスキップして各競馬場をローテーション (1〜count-1)
        next_idx = cur + 1 if cur < count - 1 else 1
        self.combo_filter_track.setCurrentIndex(next_idx)

    def _on_camera_changed(self, idx: int) -> None:
        """カメラ視点の変更"""
        mode = self.combo_camera.currentData()
        if mode:
            self.track_canvas.set_camera_mode(mode)

    def load_race_list(self) -> None:
        """レース選択コンボボックスに【当該週のレースのみ】をロード（フィルター対応）"""
        self.combo_races.blockSignals(True)
        self.combo_races.clear()

        grade_filter = self.combo_filter_grade.currentData() if hasattr(self, "combo_filter_grade") else None
        track_filter = self.combo_filter_track.currentData() if hasattr(self, "combo_filter_track") else None

        with self.db.session() as conn:
            # 1. 現在選択週が未決定の場合、最新の完了レースから年・月・週を特定
            if self.current_year is None or self.current_week is None:
                latest_row = conn.execute(
                    """
                    SELECT r.year, r.month, r.week
                    FROM results res
                    JOIN races r ON res.race_id = r.race_id
                    ORDER BY r.year DESC, r.week DESC, r.race_id DESC
                    LIMIT 1
                    """
                ).fetchone()
                if latest_row:
                    self.current_year = int(latest_row["year"])
                    self.current_month = int(latest_row["month"])
                    self.current_week = int(latest_row["week"])

            # 2. 当該週のレース一覧を取得
            query = """
                SELECT DISTINCT r.race_id, r.year, r.month, r.week, r.name, r.grade, r.distance, r.surface, r.track_id
                FROM results res
                JOIN races r ON res.race_id = r.race_id
                WHERE 1=1
            """
            params: list[Any] = []
            if self.current_year is not None and self.current_week is not None:
                query += " AND r.year = ? AND r.week = ?"
                params.extend([self.current_year, self.current_week])

            if grade_filter == "G1":
                query += " AND r.grade = 'G1'"
            elif grade_filter == "GRADED":
                query += " AND r.grade IN ('G1', 'G2', 'G3')"
            elif grade_filter == "OP_COND":
                query += " AND r.grade IN ('L', 'OP', 'COND_3W', 'COND_2W', 'COND_1W')"
            elif grade_filter == "MAIDEN":
                query += " AND r.grade IN ('MAIDEN', 'NEWCOMER')"

            if track_filter:
                query += " AND r.track_id = ?"
                params.append(track_filter)

            rows = conn.execute(query, tuple(params)).fetchall()

        if not rows:
            self.combo_races.addItem("（該当する完了レースがありません）", None)
            if self.current_year is not None and self.current_week is not None:
                week_in_m = ((int(self.current_week) - 1) % 4) + 1
                self.lbl_race_week.setText(f"{self.current_month}月{week_in_m}週")
            else:
                self.lbl_race_week.setText("―月―週")
            self.current_race_id = None
            self._cancel_timers()
            self._is_board_revealed = False
            self.board_widget.reset_board("東京", 1, "芝")
            self.board_widget.setVisible(False)
            self.combo_races.blockSignals(False)
            return

        # 開催週のラベル更新
        if self.current_year is not None and self.current_week is not None:
            first_r = rows[0]
            m_val = int(first_r["month"])
            week_in_m = ((int(first_r["week"]) - 1) % 4) + 1
            self.lbl_race_week.setText(f"{m_val}月{week_in_m}週")

        # 競馬場ごとにグループ化し、ダッシュボードと同じ順序でソート
        races_by_track: dict[str, list[Any]] = {}
        for r in rows:
            races_by_track.setdefault(r["track_id"], []).append(r)

        sorted_track_ids = sorted(
            races_by_track.keys(),
            key=lambda tid: TRACK_SORT_ORDER.get(tid, 99)
        )

        sorted_rows: list[tuple[Any, int]] = []
        with self.db.session() as conn:
            for tid in sorted_track_ids:
                track_races = races_by_track[tid]
                # 当該競馬場の全確定レースにおける正規レース番号マップを取得 (1R〜12R)
                official_num_map = self._get_official_race_number_map(
                    conn, self.current_year, self.current_week, tid
                )
                # 表示用ソート: グレード昇順、距離昇順、race_id昇順
                track_races = sorted(
                    track_races,
                    key=lambda r: (
                        GRADE_SORT_ORDER.get(str(r["grade"]), 99),
                        int(r["distance"] or 0),
                        int(r["race_id"] or 0),
                    ),
                )
                for r in track_races:
                    r_num = official_num_map.get(r["race_id"], 1)
                    sorted_rows.append((r, r_num))

        selected_idx = 0
        for idx, (r, r_num) in enumerate(sorted_rows):
            tid = r["track_id"]
            track = get_track_info(tid)
            track_name = track.name.replace("競馬場", "").strip() if track else ""
            surf_jp = "芝" if str(r["surface"]).upper() == "TURF" else "ダート"
            r_name = clean_race_name(r["name"])
            label = f"{track_name} {r_num}R: {r_name} ({r['grade']}) - {surf_jp}{r['distance']}m"
            self.combo_races.addItem(label, r["race_id"])
            if self.current_race_id is not None and r["race_id"] == self.current_race_id:
                selected_idx = idx

        self.combo_races.setCurrentIndex(selected_idx)
        self.combo_races.blockSignals(False)

        # 選択されたレースのデータを読み込み
        chosen_id = self.combo_races.currentData()
        if chosen_id is not None:
            self.current_race_id = chosen_id
            self._load_race_data(chosen_id)

    def _get_official_race_number_map(
        self, conn: Any, year: Optional[int], week: Optional[int], track_id: str
    ) -> dict[int, int]:
        """
        当該週・当該競馬場の全開催確定レース（resultsテーブルに存在するレース）における
        公式レース番号（1R〜12R）のマップ {race_id: race_number} を取得
        """
        if year is None or week is None:
            return {}
        query = """
            SELECT DISTINCT r.race_id, r.grade, r.distance
            FROM results res
            JOIN races r ON res.race_id = r.race_id
            WHERE r.year = ? AND r.week = ? AND r.track_id = ?
        """
        rows = conn.execute(query, (year, week, track_id)).fetchall()
        sorted_all = sorted(
            rows,
            key=lambda r: (
                GRADE_SORT_ORDER.get(str(r["grade"]), 99),
                int(r["distance"] or 0),
                int(r["race_id"] or 0),
            )
        )
        return {r["race_id"]: idx + 1 for idx, r in enumerate(sorted_all)}

    def load_race_by_id(self, race_id: int) -> None:
        """指定したrace_idのレースを直接読み込み（当該週を設定してレース一覧を更新）"""
        with self.db.session() as conn:
            rc = conn.execute("SELECT year, month, week FROM races WHERE race_id = ?", (race_id,)).fetchone()
            if rc:
                self.current_year = int(rc["year"])
                self.current_month = int(rc["month"])
                self.current_week = int(rc["week"])
        self.current_race_id = race_id
        self.load_race_list()

    def _on_race_selected(self, index: int) -> None:
        if index < 0:
            return
        race_id = self.combo_races.currentData()
        if race_id is not None:
            self.current_race_id = race_id
            self._load_race_data(race_id)

    def _load_race_data(self, race_id: int) -> None:
        """レース情報およびリプレイデータの読み込みと画面反映"""
        with self.db.session() as conn:
            rc = conn.execute("SELECT * FROM races WHERE race_id = ?", (race_id,)).fetchone()
            if not rc:
                return

            track = get_track_info(rc["track_id"])
            turn = track.turn  # 'right' or 'left'
            surf_jp = "芝" if rc["surface"] == "turf" else "ダート"
            week_in_m = ((int(rc["week"]) - 1) % 4) + 1
            self.lbl_race_week.setText(f"{rc['month']}月{week_in_m}週")

            # 結果行の取得
            rows = conn.execute(
                """
                SELECT r.*, h.name as horse_name, j.name as jockey_name, t.name as trainer_name
                FROM results r
                JOIN horses h ON r.horse_id = h.horse_id
                LEFT JOIN jockeys j ON r.jockey_id = j.jockey_id
                LEFT JOIN trainers t ON r.trainer_id = t.trainer_id
                WHERE r.race_id = ?
                ORDER BY r.finish_position ASC
                """,
                (race_id,),
            ).fetchall()

            # コースレコード判定 (共通関数を用いて初開催時・更新時を判定)
            winner_time = float(rows[0]["finish_time"]) if rows else 0.0
            is_record = check_is_course_record(
                conn=conn,
                track_id=rc["track_id"],
                surface=rc["surface"],
                distance=rc["distance"],
                finish_time=winner_time,
                year=rc["year"],
                week=rc["week"],
                race_id=rc["race_id"],
            )

            # 当該週・当該競馬場におけるレース番号を正確に計算 (1R〜12R: ダッシュボード・コンボボックスと完全一致)
            official_num_map = self._get_official_race_number_map(
                conn, rc["year"], rc["week"], rc["track_id"]
            )
            race_num = official_num_map.get(rc["race_id"], 11)

        total_horses = len(rows)

        # DBのgate_numberを正としてhorse_id -> gate_numberマップを作成
        gate_counts = {}
        for r in rows:
            g = r["gate_number"] if ("gate_number" in r.keys() and r["gate_number"]) else 1
            gate_counts[g] = gate_counts.get(g, 0) + 1

        is_stuck_gates = (max(gate_counts.values()) > 1 if gate_counts else True)
        gate_map: dict[int, int] = {}

        for idx, r in enumerate(rows):
            h_id = r["horse_id"]
            if not is_stuck_gates and "gate_number" in r.keys() and r["gate_number"]:
                gate_num = r["gate_number"]
            else:
                gate_num = (idx + 1)
            gate_map[h_id] = gate_num

        # LED着順掲示板への反映 (1〜5着)
        top5_horses = []
        for r in rows[:5]:
            top5_horses.append({
                "gate_number": gate_map.get(r["horse_id"], 1),
                "margin": r["margin"] or "",
            })

        f3 = float(rows[0]["last_3f"]) if (rows and "last_3f" in rows[0].keys() and rows[0]["last_3f"]) else None

        # ゴール確定時のデータを保持
        self._confirmed_board_data = {
            "track_name": track.name,
            "race_number": race_num,
            "surface_jp": surf_jp,
            "top5_horses": top5_horses,
            "finish_time": winner_time,
            "is_record": is_record,
            "f3_time": f3,
        }

        # 初期表示（レース前のため掲示板は非表示）
        self._cancel_timers()
        self._is_board_revealed = False
        self.track_canvas.hide_result_board()
        self.board_widget.setVisible(False)
        self.board_widget.reset_board(
            track_name=track.name,
            race_number=race_num,
            surface_jp=surf_jp,
        )

        # リプレイデータの読み込み（gate_mapを渡して完全同期）
        replay_data = None
        for r in rows:
            if r["replay_data_json"]:
                replay_data = r["replay_data_json"]
                break

        if replay_data:
            self.track_canvas.load_replay_data(
                replay_data,
                distance=rc["distance"],
                surface=rc["surface"],
                turn=turn,
                track_id=rc["track_id"],
                gate_map=gate_map,
            )
        else:
            synthetic_frames = self._build_synthetic_replay(rows, rc["distance"], gate_map)
            self.track_canvas.load_replay_data(
                json.dumps(synthetic_frames),
                distance=rc["distance"],
                surface=rc["surface"],
                turn=turn,
                track_id=rc["track_id"],
                gate_map=gate_map,
            )

        # 詳細レース結果情報（騎手・着差・上り3F・賞金・レコード）をTrackCanvasに反映
        results_map = {}
        for r in rows:
            h_id = r["horse_id"]
            results_map[h_id] = {
                "horse_id": h_id,
                "horse_name": r["horse_name"],
                "gate_number": gate_map.get(h_id, r["gate_number"] if ("gate_number" in r.keys() and r["gate_number"]) else 1),
                "finish_position": r["finish_position"],
                "finish_time": float(r["finish_time"]) if r["finish_time"] else 0.0,
                "margin": r["margin"] or "",
                "last_3f": float(r["last_3f"]) if ("last_3f" in r.keys() and r["last_3f"]) else None,
                "odds": float(r["odds"]) if ("odds" in r.keys() and r["odds"]) else 0.0,
                "prize_awarded": int(r["prize_awarded"]) if ("prize_awarded" in r.keys() and r["prize_awarded"]) else 0,
                "jockey_name": r["jockey_name"] or "",
                "trainer_name": r["trainer_name"] or "",
            }
        self.track_canvas.set_race_results(results_map, is_record=is_record)

        self.slider.setRange(0, max(1, self.track_canvas.total_frames - 1))
        self.slider.setValue(0)
        self.btn_play.setText("▶ 再生")

    def _build_synthetic_replay(self, rows: list, distance: int, gate_map: dict[int, int] | None = None) -> list:
        """DBに展開JSONがない場合のリアルタイム補間フレーム生成"""
        frames = []
        if not rows:
            return frames

        max_time = max(r["finish_time"] for r in rows)
        total_steps = int(math.ceil(max_time / 0.1)) + 1

        for step in range(total_steps):
            t = round(step * 0.1, 2)
            horses_frame = []
            for idx, r in enumerate(rows):
                f_time = float(r["finish_time"])
                rate = min(1.0, t / f_time) if f_time > 0 else 0.0
                dist_cov = rate * distance
                is_spurt = (distance - dist_cov <= 300.0) and (dist_cov < distance)
                gate_num = gate_map.get(r["horse_id"], idx + 1) if gate_map else (idx + 1)
                horses_frame.append({
                    "horse_id": r["horse_id"],
                    "number": gate_num,
                    "name": r["horse_name"],
                    "distance_covered": dist_cov,
                    "lane": idx % 4,
                    "is_spurt": is_spurt,
                })
            horses_frame.sort(key=lambda x: x["distance_covered"], reverse=True)
            frames.append({"time": t, "horses": horses_frame})
        return frames

    def _cancel_timers(self) -> None:
        """掲示板・ダイアログタイマーの安全な停止"""
        if self._board_timer and self._board_timer.isActive():
            self._board_timer.stop()
        if self._dialog_timer and self._dialog_timer.isActive():
            self._dialog_timer.stop()

    def _reveal_board_results(self) -> None:
        """ゴール数秒後にレース画面内掲示板の確定着順・タイム・確定ランプを点灯表示"""
        if hasattr(self, "_confirmed_board_data") and self._confirmed_board_data:
            d = self._confirmed_board_data
            self.track_canvas.set_result_board_data(
                track_name=d["track_name"],
                race_number=d["race_number"],
                surface_jp=d["surface_jp"],
                top5_horses=d["top5_horses"],
                finish_time=d["finish_time"],
                is_record=d["is_record"],
                f3_time=d["f3_time"],
                is_confirmed=True,
                is_visible=True,
            )
            self.board_widget.set_race_board_data(
                track_name=d["track_name"],
                race_number=d["race_number"],
                surface_jp=d["surface_jp"],
                top5_horses=d["top5_horses"],
                finish_time=d["finish_time"],
                is_record=d["is_record"],
                f3_time=d["f3_time"],
                is_confirmed=True,
            )

    def _toggle_play(self) -> None:
        if self.track_canvas.timer.isActive():
            self.track_canvas.pause()
            self.btn_play.setText("▶ 再生")
        else:
            if self.track_canvas.current_frame_idx < self.track_canvas.total_frames - 3:
                self._cancel_timers()
                self._is_board_revealed = False
                self.track_canvas.hide_result_board()
                self.board_widget.setVisible(False)
                if hasattr(self, "_confirmed_board_data") and self._confirmed_board_data:
                    d = self._confirmed_board_data
                    self.board_widget.reset_board(
                        track_name=d["track_name"],
                        race_number=d["race_number"],
                        surface_jp=d["surface_jp"],
                    )
            self.track_canvas.play()
            self.btn_play.setText("❚❚ 一時停止")

    def _on_playback_finished(self) -> None:
        self.btn_play.setText("▶ 再生")
        # ゴール完了時: レース画面内に掲示板枠を表示し、1.5秒後に着順・タイムを点灯
        if not self._is_board_revealed:
            self._is_board_revealed = True
            if hasattr(self, "_confirmed_board_data") and self._confirmed_board_data:
                d = self._confirmed_board_data
                self.track_canvas.reset_result_board(
                    track_name=d["track_name"],
                    race_number=d["race_number"],
                    surface_jp=d["surface_jp"],
                )
                self.board_widget.reset_board(
                    track_name=d["track_name"],
                    race_number=d["race_number"],
                    surface_jp=d["surface_jp"],
                )
            self._cancel_timers()
            self._board_timer = QTimer(self)
            self._board_timer.setSingleShot(True)
            self._board_timer.timeout.connect(self._reveal_board_results)
            self._board_timer.start(1500)

        # 詳細結果ダイアログは掲示板点灯の後（ゴール後3.5秒）に表示
        self._dialog_timer = QTimer(self)
        self._dialog_timer.setSingleShot(True)
        self._dialog_timer.timeout.connect(self._show_race_result_dialog)
        self._dialog_timer.start(3500)

    def _show_race_entry_dialog(self) -> None:
        """出馬表（枠番・馬名・性齢・騎手・調教師・脚質・予想オッズ・人気）ダイアログを表示"""
        if self.current_race_id is not None and not getattr(self, "_is_dialog_open", False):
            self._is_dialog_open = True
            try:
                from src.gui.views.race_dialogs import RaceEntryDialog
                dialog = RaceEntryDialog(self.db, self.current_race_id, parent=self)
                dialog.exec()
            finally:
                self._is_dialog_open = False

    def _show_race_result_dialog(self) -> None:
        """ダッシュボードと同じ詳細レース結果ダイアログ（確定着順・オッズ・上がり・賞金等）を表示"""
        if self.current_race_id is not None and not getattr(self, "_is_dialog_open", False):
            self._is_dialog_open = True
            try:
                from src.gui.views.race_dialogs import RaceResultDialog
                dialog = RaceResultDialog(self.db, self.current_race_id, parent=self)
                dialog.exec()
            finally:
                self._is_dialog_open = False

    def hideEvent(self, event: Any) -> None:
        """タブ切り替え・画面非表示時にタイマーとアニメーションを安全に停止"""
        super().hideEvent(event)
        self._cancel_timers()
        if hasattr(self, "track_canvas"):
            self.track_canvas.stop()

    def _on_canvas_time_updated(self, cur: float, total: float) -> None:
        c_str = f"{int(cur // 60):02d}:{cur % 60:04.1f}"
        t_str = f"{int(total // 60):02d}:{total % 60:04.1f}"
        self.lbl_time.setText(f"{c_str} / {t_str}")
        self.slider.blockSignals(True)
        self.slider.setValue(self.track_canvas.current_frame_idx)
        self.slider.blockSignals(False)

        # 先頭馬がゴールしているか判定
        is_end = (self.track_canvas.total_frames > 0 and self.track_canvas.current_frame_idx >= self.track_canvas.total_frames - 2)
        if is_end:
            # ゴール後: レース画面内に掲示板を表示（最初はブランク、数秒後に確定結果を点灯）
            if not self._is_board_revealed:
                self._is_board_revealed = True
                if hasattr(self, "_confirmed_board_data") and self._confirmed_board_data:
                    d = self._confirmed_board_data
                    self.track_canvas.reset_result_board(
                        track_name=d["track_name"],
                        race_number=d["race_number"],
                        surface_jp=d["surface_jp"],
                    )
                self._cancel_timers()
                self._board_timer = QTimer(self)
                self._board_timer.setSingleShot(True)
                self._board_timer.timeout.connect(self._reveal_board_results)
                self._board_timer.start(1500)
        else:
            # レース中は掲示板を表示しない
            if self._is_board_revealed or self.track_canvas.show_result_board:
                self._is_board_revealed = False
                self._cancel_timers()
                self.track_canvas.hide_result_board()
                self.board_widget.setVisible(False)

    def _on_slider_moved(self, val: int) -> None:
        self.track_canvas.set_frame(val)

    def _on_speed_changed(self, idx: int) -> None:
        speeds = [1.0, 2.0, 4.0]
        self.track_canvas.set_speed(speeds[idx])
