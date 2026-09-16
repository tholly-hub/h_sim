"""
レース結果一覧 & 2Dトラック・レースリプレイビュー (PyQt6)
- 消化レースの選択・結果着順表
- 0.1秒ごとの展開データを用いたリアルタイム2Dアニメーション再生
- 再生、一時停止、シーク、速度変更
"""

from __future__ import annotations

import json
from typing import Optional
from PyQt6.QtCore import Qt
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
from src.gui.widgets.track_canvas import TrackCanvas, JRA_BRACKET_COLORS
from src.race.engine import get_jra_bracket
from src.race.track import get_track_info


class RaceReplayView(QWidget):
    """レース結果一覧 & 2Dレースリプレイ再生画面"""

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.current_race_id: Optional[int] = None
        self._init_ui()
        self.load_race_list()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. レース選択バー
        sel_frame = QFrame()
        sel_frame.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 8px;")
        sel_layout = QHBoxLayout(sel_frame)
        sel_layout.setContentsMargins(12, 8, 12, 8)
        sel_layout.setSpacing(10)

        # グレードフィルター
        sel_layout.addWidget(QLabel("グレード:"))
        self.combo_filter_grade = QComboBox()
        self.combo_filter_grade.addItem("全グレード", None)
        self.combo_filter_grade.addItem("🏆 G1 のみ", "G1")
        self.combo_filter_grade.addItem("🎖 重賞 (G1-G3)", "GRADED")
        self.combo_filter_grade.addItem("🏇 オープン・条件戦", "OP_COND")
        self.combo_filter_grade.addItem("🌱 未勝利・新馬", "MAIDEN")
        self.combo_filter_grade.currentIndexChanged.connect(self.load_race_list)
        sel_layout.addWidget(self.combo_filter_grade)

        # 競馬場フィルター
        sel_layout.addWidget(QLabel("競馬場:"))
        self.combo_filter_track = QComboBox()
        self.combo_filter_track.addItem("全競馬場", None)
        self.combo_filter_track.addItem("東京競馬場 (左)", "B")
        self.combo_filter_track.addItem("中山競馬場 (右)", "C")
        self.combo_filter_track.addItem("中京競馬場 (左)", "A")
        self.combo_filter_track.addItem("小倉競馬場 (右)", "D")
        self.combo_filter_track.currentIndexChanged.connect(self.load_race_list)
        sel_layout.addWidget(self.combo_filter_track)

        # レース選択コンボボックス
        sel_layout.addWidget(QLabel("レース選択:"))
        self.combo_races = QComboBox()
        self.combo_races.setMinimumWidth(380)
        self.combo_races.currentIndexChanged.connect(self._on_race_selected)
        sel_layout.addWidget(self.combo_races)

        self.btn_refresh = QPushButton("🔄 更新")
        self.btn_refresh.clicked.connect(self.load_race_list)
        sel_layout.addWidget(self.btn_refresh)

        sel_layout.addStretch()

        self.lbl_race_info = QLabel("-")
        self.lbl_race_info.setStyleSheet("font-weight: bold; color: #38bdf8;")
        sel_layout.addWidget(self.lbl_race_info)

        main_layout.addWidget(sel_frame)

        # 2. スプリッター（上: 2Dリプレイトラック & 再生バー、下: 結果着順表）
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 上部: リプレイキャンバス & コントローラー
        replay_widget = QWidget()
        replay_layout = QVBoxLayout(replay_widget)
        replay_layout.setContentsMargins(0, 0, 0, 0)
        replay_layout.setSpacing(8)

        self.track_canvas = TrackCanvas()
        self.track_canvas.time_updated.connect(self._on_canvas_time_updated)
        self.track_canvas.playback_finished.connect(self._on_playback_finished)
        replay_layout.addWidget(self.track_canvas)

        # コントロールバー（再生・停止・シーク・速度）
        ctrl_bar = QFrame()
        ctrl_bar.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 6px;")
        ctrl_layout = QHBoxLayout(ctrl_bar)
        ctrl_layout.setContentsMargins(10, 6, 10, 6)
        ctrl_layout.setSpacing(10)

        self.btn_play = QPushButton("▶ 再生")
        self.btn_play.clicked.connect(self._toggle_play)
        ctrl_layout.addWidget(self.btn_play)

        self.btn_stop = QPushButton("■ 停止")
        self.btn_stop.clicked.connect(self.track_canvas.stop)
        ctrl_layout.addWidget(self.btn_stop)

        # タイム表示
        self.lbl_time = QLabel("00:00.0 / 00:00.0")
        self.lbl_time.setStyleSheet("font-family: monospace; font-size: 13px; color: #f8fafc;")
        ctrl_layout.addWidget(self.lbl_time)

        # シークスライダー
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.sliderMoved.connect(self._on_slider_moved)
        ctrl_layout.addWidget(self.slider)

        # 速度変更 (デフォルト: 2.0x)
        ctrl_layout.addWidget(QLabel("速度:"))
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(["1.0x", "2.0x", "4.0x"])
        self.combo_speed.setCurrentIndex(1)
        self.combo_speed.currentIndexChanged.connect(self._on_speed_changed)
        ctrl_layout.addWidget(self.combo_speed)

        # 🎥 カメラ視点切替（デフォルト: 2D 俯瞰マップ）
        ctrl_layout.addWidget(QLabel("視点:"))
        self.combo_camera = QComboBox()
        self.combo_camera.addItem("2D 俯瞰マップ", "2d")
        self.combo_camera.addItem("3D 立体バードビュー", "3d_bird")
        self.combo_camera.addItem("3D チェイスカメラ", "3d_chase")
        self.combo_camera.setCurrentIndex(0)
        self.combo_camera.currentIndexChanged.connect(self._on_camera_changed)
        ctrl_layout.addWidget(self.combo_camera)

        # 📊 結果一覧の表示/非表示トグルボタン
        self.btn_toggle_result = QPushButton("📊 結果を表示")
        self.btn_toggle_result.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-weight: bold; border-radius: 4px; padding: 4px 10px;")
        self.btn_toggle_result.clicked.connect(self._toggle_result_visibility)
        ctrl_layout.addWidget(self.btn_toggle_result)

        replay_layout.addWidget(ctrl_bar)
        splitter.addWidget(replay_widget)

        # 下部: 結果着順表（ネタバレ防止のためレース前・レース中は非表示）
        self.result_widget = QWidget()
        result_layout = QVBoxLayout(self.result_widget)
        result_layout.setContentsMargins(0, 4, 0, 0)

        # 結果ヘッダー
        res_header = QLabel("🏁 確定着順・レース結果")
        res_header.setStyleSheet("font-size: 13px; font-weight: bold; color: #fbbf24; padding-left: 4px;")
        result_layout.addWidget(res_header)

        self.table_results = QTableWidget()
        self.table_results.setColumnCount(10)
        self.table_results.setHorizontalHeaderLabels([
            "着順", "馬番", "馬名", "人気/オッズ", "走破タイム", "着差", "上り3F", "騎手", "厩舎", "獲得本賞金"
        ])
        self.table_results.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_results.setAlternatingRowColors(True)
        self.table_results.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_results.setStyleSheet("QTableWidget { font-size: 13px; background-color: #0d131f; }")
        result_layout.addWidget(self.table_results)

        # 初期状態は非表示（レース画面を最大化）
        self.result_widget.setVisible(False)
        splitter.addWidget(self.result_widget)
        splitter.setStretchFactor(0, 1)

        main_layout.addWidget(splitter)

    def _toggle_result_visibility(self) -> None:
        """結果テーブルの手動表示/非表示切り替え"""
        is_vis = not self.result_widget.isVisible()
        self.result_widget.setVisible(is_vis)
        self.btn_toggle_result.setText("📊 結果を隠す" if is_vis else "📊 結果を表示")

    def _on_camera_changed(self, idx: int) -> None:
        """カメラ視点の変更"""
        mode = self.combo_camera.currentData()
        if mode:
            self.track_canvas.set_camera_mode(mode)

    def load_race_list(self) -> None:
        """レース選択コンボボックスに完了済みレースの一覧をロード（フィルター対応）"""
        self.combo_races.blockSignals(True)
        self.combo_races.clear()

        grade_filter = self.combo_filter_grade.currentData() if hasattr(self, "combo_filter_grade") else None
        track_filter = self.combo_filter_track.currentData() if hasattr(self, "combo_filter_track") else None

        query = """
            SELECT DISTINCT r.race_id, r.year, r.month, r.week, r.name, r.grade, r.distance, r.surface, r.track_id
            FROM results res
            JOIN races r ON res.race_id = r.race_id
            WHERE 1=1
        """
        params: list[Any] = []
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

        query += " ORDER BY r.year DESC, r.month DESC, r.week DESC, r.race_id DESC LIMIT 200"

        with self.db.session() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()

        if not rows:
            self.combo_races.addItem("（該当する完了レースがありません。ダッシュボードで進めてください）", None)
            self.lbl_race_info.setText("※ 該当する完了レースがありません。ダッシュボードでシミュレーションを進めてください。")
            self.current_race_id = None
            self.table_results.setRowCount(0)
            self.combo_races.blockSignals(False)
            return

        selected_idx = 0
        for idx, r in enumerate(rows):
            week_in_m = ((int(r["week"]) - 1) % 4) + 1
            track = get_track_info(r["track_id"])
            track_name = track.name if track else ""
            surf_jp = "芝" if r["surface"] == "TURF" else "ダート"
            label = f"[{r['year']}年 {r['month']}月{week_in_m}週] {r['name']} ({r['grade']}) - {track_name} {surf_jp}{r['distance']}m"
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
            turn_jp = "右回り" if turn == "right" else "左回り"
            self.lbl_race_info.setText(
                f"{rc['name']} ({rc['grade']}) - {track.name} {surf_jp} {rc['distance']}m [{turn_jp}・{rc['full_gate']}頭立]"
            )

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

        # テーブル更新
        self.table_results.setRowCount(len(rows))
        total_horses = len(rows)

        # DBのgate_numberを正としてhorse_id -> gate_numberマップを作成
        # これにより走る馬番と結果表の馬番が100%完全一致する
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

        # 単勝オッズに基づく人気順位の算出
        odds_list = []
        for r in rows:
            val = float(r["odds"]) if ("odds" in r.keys() and r["odds"] and float(r["odds"]) > 0) else 999.9
            odds_list.append((val, r["horse_id"]))
        sorted_by_odds = sorted(odds_list, key=lambda x: x[0])
        popularity_map = {hid: pop for pop, (_, hid) in enumerate(sorted_by_odds, start=1)}

        for idx, r in enumerate(rows):
            time_str = f"{int(r['finish_time'] // 60):02d}:{r['finish_time'] % 60:04.1f}"
            gate_num = gate_map[r["horse_id"]]

            # JRA枠番と枠色
            bracket_num = get_jra_bracket(gate_num, total_horses)
            bg_col, fg_col, _, _ = JRA_BRACKET_COLORS.get(bracket_num, ("#ffffff", "#000000", "#999999", "1枠"))

            # 0. 着順
            self.table_results.setItem(idx, 0, QTableWidgetItem(f"{r['finish_position']}着"))

            # 1. 馬番（JRA枠色背景）
            gate_item = QTableWidgetItem(f"{gate_num}番")
            gate_item.setBackground(QColor(bg_col))
            gate_item.setForeground(QColor(fg_col))
            gate_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_results.setItem(idx, 1, gate_item)

            # 2. 馬名
            self.table_results.setItem(idx, 2, QTableWidgetItem(r["horse_name"]))

            # 3. 人気 / オッズ
            odds_val = float(r["odds"]) if ("odds" in r.keys() and r["odds"]) else 0.0
            if odds_val > 0:
                pop_val = popularity_map.get(r["horse_id"], idx + 1)
                odds_text = f"{pop_val}人気 ({odds_val:.1f})"
            else:
                odds_text = "―"
            odds_item = QTableWidgetItem(odds_text)
            odds_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_results.setItem(idx, 3, odds_item)

            # 4. 走破タイム
            self.table_results.setItem(idx, 4, QTableWidgetItem(time_str))

            # 5. 着差（前走馬との差）
            margin_str = r["margin"] or "-"
            margin_item = QTableWidgetItem(margin_str)
            margin_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_results.setItem(idx, 5, margin_item)

            # 6. 上がり3ハロン（ラスト600mタイム）
            last_3f_val = float(r["last_3f"]) if ("last_3f" in r.keys() and r["last_3f"]) else 0.0
            last_3f_text = f"{last_3f_val:.1f}" if last_3f_val > 0 else "―"
            last_3f_item = QTableWidgetItem(last_3f_text)
            last_3f_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_results.setItem(idx, 6, last_3f_item)

            # 7. 騎手
            self.table_results.setItem(idx, 7, QTableWidgetItem(r["jockey_name"] or "―"))

            # 8. 厩舎
            self.table_results.setItem(idx, 8, QTableWidgetItem(r["trainer_name"] or "―"))

            # 9. 獲得本賞金
            self.table_results.setItem(idx, 9, QTableWidgetItem(f"{r['prize_awarded']:,}円"))

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

        self.slider.setRange(0, max(1, self.track_canvas.total_frames - 1))
        self.slider.setValue(0)
        self.btn_play.setText("▶ 再生")

        # レース選択時は結果表を非表示（ネタバレ防止 & レース画面最大化）
        self.result_widget.setVisible(False)
        self.btn_toggle_result.setText("📊 結果を表示")

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

    def _toggle_play(self) -> None:
        if self.track_canvas.timer.isActive():
            self.track_canvas.pause()
            self.btn_play.setText("▶ 再生")
        else:
            self.track_canvas.play()
            self.btn_play.setText("❚❚ 一時停止")

    def _on_playback_finished(self) -> None:
        self.btn_play.setText("▶ 再生")
        # レース終了時に結果着順表を自動表示！
        self.result_widget.setVisible(True)
        self.btn_toggle_result.setText("📊 結果を隠す")

    def _on_canvas_time_updated(self, cur: float, total: float) -> None:
        c_str = f"{int(cur // 60):02d}:{cur % 60:04.1f}"
        t_str = f"{int(total // 60):02d}:{total % 60:04.1f}"
        self.lbl_time.setText(f"{c_str} / {t_str}")
        self.slider.blockSignals(True)
        self.slider.setValue(self.track_canvas.current_frame_idx)
        self.slider.blockSignals(False)

    def _on_slider_moved(self, val: int) -> None:
        self.track_canvas.set_frame(val)

    def _on_speed_changed(self, idx: int) -> None:
        speeds = [1.0, 2.0, 4.0]
        self.track_canvas.set_speed(speeds[idx])
