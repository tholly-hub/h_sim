"""
2D追従スクロールカメラ式 競馬場トラック & レースリプレイ描画ウィジェット (PyQt6)
- 大スケール・トラックワールド上の馬群拡大表示 & 先頭馬追従スクロールカメラ
- 走る馬番とデータベース（結果着順表）の馬番の100%完全同期
- JRA公式8枠制の枠色（白・黒・赤・青・黄・緑・橙・桃）対応
- コース全体の走行位置がわかる全体ミニマップ（レーダー）
- テレビ中継風リアルタイム順位テロップ（LIVE TOP 5）
- 全頭ゴール通過まで滑らかに流し走行を継続
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional
from PyQt6.QtCore import QPointF, QRectF, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget

from src.race.engine import clean_race_name, get_jra_bracket
from src.race.track import get_track_info


# JRA公式8枠制カラーマップ
# 枠番: (背景色, 文字色, 枠線色, 枠名)
JRA_BRACKET_COLORS: Dict[int, tuple[str, str, str, str]] = {
    1: ("#ffffff", "#111827", "#94a3b8", "1枠"),  # 白
    2: ("#1e293b", "#f8fafc", "#475569", "2枠"),  # 黒
    3: ("#ef4444", "#ffffff", "#b91c1c", "3枠"),  # 赤
    4: ("#2563eb", "#ffffff", "#1d4ed8", "4枠"),  # 青
    5: ("#eab308", "#111827", "#ca8a04", "5枠"),  # 黄
    6: ("#16a34a", "#ffffff", "#15803d", "6枠"),  # 緑
    7: ("#ea580c", "#ffffff", "#c2410c", "7枠"),  # 橙
    8: ("#ec4899", "#ffffff", "#db2777", "8枠"),  # 桃
}

STYLE_JP_MAP = {
    "escape": "逃げ",
    "leading": "先行",
    "between": "差し",
    "closing": "追込",
}


class TrackCanvas(QWidget):
    """競馬場トラック & 2D追従スクロールカメラ描画キャンバス"""

    time_updated = pyqtSignal(float, float)  # 現在タイム(秒), レース総タイム(秒)
    playback_finished = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(640, 420)
        self.setStyleSheet("background-color: #06090e; border-radius: 8px;")

        # リプレイデータ
        self.replay_frames: List[Dict[str, Any]] = []
        self.horse_names: Dict[int, str] = {}
        self.horse_brackets: Dict[int, int] = {}
        self.total_frames: int = 0
        self.current_frame_idx: int = 0
        self.distance: int = 1600
        self.surface: str = "turf"
        self.turn: str = "right"                # 'right' (右回り) / 'left' (左回り)
        self.track_id: str = "A"
        self.camera_mode: str = "scroll_2d"     # 追従スクロール2Dカメラ

        # 再生タイマー (0.1秒 = 100ms ごと)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer_tick)
        self.playback_speed: float = 4.0

        # 大スケール・ワールド定義パラメータ
        self.world_straight = 1800.0            # 直線部長さ (px)
        self.world_r = 500.0                    # コーナー半径 (px)
        self.world_track_width = 195.0          # コース幅 (px) 従来の130.0から1.5倍に拡大！
        self.world_perimeter = 2.0 * self.world_straight + 2.0 * math.pi * self.world_r
        self.race_name: str = ""
        self.race_grade: str = ""
        self.race_results_info: Dict[int, Dict[str, Any]] = {}
        self.is_record_time: bool = False

        # 順位バーの180度視点回転（3Dフリップ）アニメーション状態
        self.indicator_flip_factor: float = 1.0  # +1.0 (右向き) 〜 -1.0 (左向き)
        self.indicator_target_is_right: bool = True

        # レース画面内結果掲示板（LED電光掲示板オーバーレイ）状態
        self.show_result_board: bool = False
        self.board_confirmed: bool = False
        self.board_data: Dict[str, Any] = {}

    def set_result_board_data(
        self,
        track_name: str = "",
        race_number: str = "11R",
        surface_jp: str = "芝",
        top5_horses: Optional[List[Dict[str, Any]]] = None,
        finish_time: float = 0.0,
        is_record: bool = False,
        f3_time: float = 0.0,
        is_confirmed: bool = False,
        is_visible: bool = True,
    ) -> None:
        """レース画面内に描画するLED電光掲示板のデータを設定"""
        self.show_result_board = is_visible
        self.board_confirmed = is_confirmed
        self.board_data = {
            "track_name": track_name,
            "race_number": race_number,
            "surface_jp": surface_jp,
            "top5_horses": top5_horses or [],
            "finish_time": finish_time,
            "is_record": is_record,
            "f3_time": f3_time,
        }
        self.update()

    def reset_result_board(
        self,
        track_name: str = "",
        race_number: str = "11R",
        surface_jp: str = "芝",
    ) -> None:
        """掲示板を未確定（枠のみ）状態で初期化"""
        self.show_result_board = True
        self.board_confirmed = False
        self.board_data = {
            "track_name": track_name,
            "race_number": race_number,
            "surface_jp": surface_jp,
            "top5_horses": [],
            "finish_time": 0.0,
            "is_record": False,
            "f3_time": 0.0,
        }
        self.update()

    def hide_result_board(self) -> None:
        """結果掲示板を非表示にする"""
        self.show_result_board = False
        self.board_confirmed = False
        self.update()

    def set_race_results(
        self,
        results: Dict[int, Dict[str, Any]] | List[Dict[str, Any]],
        is_record: bool = False,
    ) -> None:
        """レース結果詳細情報（騎手名・着差・上がり3F・賞金・レコード判定）を設定"""
        self.is_record_time = is_record
        if isinstance(results, dict):
            self.race_results_info = results
        elif isinstance(results, list):
            self.race_results_info = {
                r.get("horse_id", idx + 1): r for idx, r in enumerate(results)
            }
        self.update()

    def set_camera_mode(self, mode: str) -> None:
        """カメラ視点の切り替え"""
        self.camera_mode = mode
        self.update()

    def load_replay_data(
        self,
        replay_json_str: str,
        distance: int = 1600,
        surface: str = "turf",
        turn: str = "right",
        track_id: str = "A",
        gate_map: Optional[Dict[int, int]] = None,
    ) -> bool:
        """
        JSON展開データを読み込んで初期化（0.1秒単位のリサンプリング対応）
        gate_map: {horse_id: gate_number} DBのresultsテーブルと100%完全同期
        """
        self.stop()
        self.distance = distance
        self.surface = surface
        self.turn = turn
        self.track_id = track_id
        self.replay_frames = []
        self.current_frame_idx = 0
        self.horse_names.clear()
        self.horse_brackets.clear()

        # コース特性に応じて直線の長さを調整（大箱・中箱・小箱、全12競馬場対応）
        track = get_track_info(track_id)
        self.turn = track.turn
        self.world_straight = 1200.0 + max(0.0, track.straight_length - 280.0) * 2.8
        if track.size_type == "large":
            self.world_r = 520.0
        elif track.size_type == "medium":
            self.world_r = 480.0
        else:
            self.world_r = 430.0
        self.world_perimeter = 2.0 * self.world_straight + 2.0 * math.pi * self.world_r

        if not replay_json_str:
            self.update()
            return False

        try:
            raw_data = json.loads(replay_json_str)
            if isinstance(raw_data, dict):
                self.race_name = raw_data.get("race_name", "")
                self.race_grade = raw_data.get("grade", "")

            # パターン1: engine.py 形式の辞書
            if isinstance(raw_data, dict) and "horses" in raw_data and raw_data["horses"] and "positions" in raw_data["horses"][0]:
                dt = float(raw_data.get("dt", 0.5))
                horses = raw_data["horses"]
                total_horses = len(horses)
                total_time = float(raw_data.get("total_time", 0.0))
                if total_time <= 0:
                    total_time = max(float(h.get("finish_time", 120.0)) for h in horses) + 2.5

                target_dt = 0.1
                total_target_steps = int(math.ceil(total_time / target_dt)) + 1
                frames = []

                # 出走馬の馬番・枠番をDBのgate_mapと完全一致させる
                for idx, h in enumerate(horses):
                    h_id = h.get("horse_id", idx + 1)
                    if gate_map and h_id in gate_map:
                        g_num = min(18, max(1, int(gate_map[h_id])))
                    else:
                        raw_g = h.get("gate_number") or (idx + 1)
                        g_num = min(18, max(1, int(raw_g)))

                    b_num = get_jra_bracket(g_num, total_horses)
                    self.horse_names[h_id] = h.get("name", f"馬{g_num}")
                    self.horse_brackets[h_id] = b_num

                for s in range(total_target_steps):
                    t = round(s * target_dt, 2)
                    frame_horses = []
                    for idx, h in enumerate(horses):
                        positions = h.get("positions", [])
                        laterals = h.get("laterals", [])
                        f_time = float(h.get("finish_time", total_time))
                        h_id = h.get("horse_id", idx + 1)
                        name = self.horse_names.get(h_id, h.get("name", f"馬{idx+1}"))
                        style = h.get("style", "leading")
                        if gate_map and h_id in gate_map:
                            g_num = min(18, max(1, int(gate_map[h_id])))
                        else:
                            raw_g = h.get("gate_number") or (idx + 1)
                            g_num = min(18, max(1, int(raw_g)))
                        b_num = self.horse_brackets.get(h_id, get_jra_bracket(g_num, total_horses))

                        orig_step_float = t / dt if dt > 0 else 0.0
                        step_low = int(math.floor(orig_step_float))
                        step_high = min(len(positions) - 1, step_low + 1)
                        frac = orig_step_float - step_low

                        if not positions:
                            dist = (t / f_time) * self.distance if f_time > 0 else 0.0
                        elif step_low >= len(positions):
                            extra_t = (step_low - len(positions)) * dt + frac * dt
                            dist = float(positions[-1]) + max(0.0, extra_t * 9.0)
                        elif step_low == step_high or frac <= 0.0:
                            dist = float(positions[step_low])
                        else:
                            dist = (1.0 - frac) * float(positions[step_low]) + frac * float(positions[step_high])

                        # 横位置 (lateral m: 0.8〜20.0m) の補間
                        if not laterals:
                            # フォールバック: スタート時 g_num 順に横並び、その後内側へ集約
                            start_lat = 1.0 + (g_num - 1) * (17.5 / max(1, total_horses - 1))
                            in_run_lat = 1.0 + (g_num % 4) * 1.5
                            prog = dist / max(1.0, float(self.distance))
                            cur_lat = start_lat + (in_run_lat - start_lat) * min(1.0, prog * 8.0)
                        elif step_low >= len(laterals):
                            cur_lat = float(laterals[-1])
                        elif step_low == step_high or frac <= 0.0:
                            cur_lat = float(laterals[step_low])
                        else:
                            cur_lat = (1.0 - frac) * float(laterals[step_low]) + frac * float(laterals[step_high])

                        # 脚質ごとの勝負どころ（全力スパート発光区間）判定
                        rem_dist = max(0.0, float(self.distance) - dist)
                        prog = dist / max(1.0, float(self.distance))
                        st_lower = str(style).lower()

                        is_spurt = False
                        if 0.0 < dist < self.distance:
                            if "escape" in st_lower:
                                # 逃げ: スタート直後のハナ争い (0〜12%)、および直線入り口の二の脚 (残り450m〜250m)
                                is_spurt = (prog < 0.12) or (250.0 <= rem_dist <= 450.0)
                            elif "leading" in st_lower:
                                # 先行: 4コーナー〜直線半ばの抜け出し (残り400m〜150m)
                                is_spurt = (150.0 <= rem_dist <= 400.0)
                            elif "between" in st_lower:
                                # 差し: 直線勝負所の馬群突き抜け (残り350m〜50m)
                                is_spurt = (50.0 <= rem_dist <= 350.0)
                            else:  # closing / 追込
                                # 追込: 4コーナー大外からのロングスパート (残り450m〜ゴール前)
                                is_spurt = (10.0 <= rem_dist <= 450.0)

                        is_finished = (dist >= float(self.distance)) or (t >= f_time)

                        frame_horses.append({
                            "horse_id": h_id,
                            "number": g_num,
                            "bracket": b_num,
                            "name": name,
                            "distance_covered": dist,
                            "lateral": cur_lat,
                            "finish_time": f_time,
                            "style": style,
                            "odds": float(h.get("odds", 0.0)),
                            "is_spurt": is_spurt,
                            "is_finished": is_finished,
                        })

                    # 各フレームでの前後左右の重なり防止（クリアランス保証）
                    for _ in range(4):
                        for i_h in range(len(frame_horses)):
                            hi = frame_horses[i_h]
                            for j_h in range(i_h + 1, len(frame_horses)):
                                hj = frame_horses[j_h]
                                if abs(hi["distance_covered"] - hj["distance_covered"]) < 3.8:
                                    lat_gap = abs(hi["lateral"] - hj["lateral"])
                                    if lat_gap < 2.2:
                                        push = (2.2 - lat_gap) / 2.0 + 0.08
                                        if hi["lateral"] >= hj["lateral"]:
                                            hi["lateral"] += push
                                            hj["lateral"] = max(0.8, hj["lateral"] - push)
                                        else:
                                            hi["lateral"] = max(0.8, hi["lateral"] - push)
                                            hj["lateral"] += push

                    # ゴール板到達順（ゴール済みはfinish_time昇順、走行中は走破距離降順）で厳密にソート
                    def frame_rank_key(item):
                        if item["is_finished"]:
                            return (0, float(item["finish_time"]), 0.0)
                        else:
                            return (1, 0.0, -float(item["distance_covered"]))

                    frame_horses.sort(key=frame_rank_key)
                    frames.append({"time": t, "horses": frame_horses})

                self.replay_frames = frames

            # パターン2: 直接フレームリストの場合
            elif isinstance(raw_data, list):
                self.replay_frames = raw_data
                total_horses = len(self.replay_frames[0].get("horses", [])) if self.replay_frames else 18
                for frame in self.replay_frames:
                    h_list = frame.get("horses", [])
                    for idx, h in enumerate(h_list):
                        h_id = h.get("horse_id", idx + 1)
                        if h_id not in self.horse_names:
                            g_num = gate_map.get(h_id) if gate_map else h.get("number", idx + 1)
                            h["number"] = g_num
                            h["bracket"] = get_jra_bracket(g_num, total_horses)
                            self.horse_names[h_id] = h.get("name", f"馬{g_num}")
                            self.horse_brackets[h_id] = h["bracket"]
                    # 直接フレームリストでもゴール板到達順にソート
                    h_list.sort(key=lambda item: (
                        0 if item.get("is_finished", False) or float(item.get("distance_covered", 0.0)) >= float(self.distance) - 0.1 else 1,
                        float(item.get("finish_time", 999.0)),
                        -float(item.get("distance_covered", 0.0))
                    ))
            else:
                self.replay_frames = []

            self.total_frames = len(self.replay_frames)
            self.update()
            self._emit_time()
            return True
        except Exception as e:
            print(f"[リプレイ読み込みエラー] {e}")
            self.replay_frames = []
            self.total_frames = 0
            self.update()
            return False

    def play(self) -> None:
        """再生開始"""
        if self.replay_frames:
            interval = int(100 / self.playback_speed)
            self.timer.start(max(10, interval))

    def pause(self) -> None:
        """一時停止"""
        self.timer.stop()

    def stop(self) -> None:
        """停止して最初に戻る"""
        self.timer.stop()
        self.current_frame_idx = 0
        self._emit_time()
        self.update()

    def set_frame(self, frame_idx: int) -> None:
        """シークバー等による指定フレームへの移動"""
        if 0 <= frame_idx < self.total_frames:
            self.current_frame_idx = frame_idx
            self._emit_time()
            self.update()

    def set_speed(self, speed: float) -> None:
        """再生速度の変更"""
        self.playback_speed = speed
        if self.timer.isActive():
            self.play()

    def _on_timer_tick(self) -> None:
        if self.current_frame_idx < self.total_frames - 1:
            self.current_frame_idx += 1
            self._emit_time()
            self.update()
        else:
            self.timer.stop()
            self.playback_finished.emit()

    def _emit_time(self) -> None:
        cur_time = self.current_frame_idx * 0.1
        total_time = (self.total_frames - 1) * 0.1 if self.total_frames > 0 else 0.0
        self.time_updated.emit(cur_time, total_time)

    def _get_lap_distance(self) -> float:
        """競馬場の実周長 (m) を取得"""
        if self.track_id == "B":
            return 2080.0  # 東京競馬場 (芝約2080m)
        elif self.track_id == "C":
            return 1800.0  # 中山競馬場 (芝外回り約1800m)
        elif self.track_id == "A":
            return 1700.0  # 中京競馬場 (芝約1700m)
        elif self.track_id == "D":
            return 1600.0  # 小倉競馬場 (芝約1600m)
        return 1800.0

    # =========================================================================
    # ワールド座標系（大スケール）での位置計算
    # =========================================================================
    def _calc_horse_pos_world(self, pos_m: float, lateral: float | int = 1.0) -> tuple[float, float, float]:
        """
        走破距離から大スケール・トラックワールド座標 (wx, wy, heading_rad) を計算
        - pos_m: スタートからの走破距離 (m)
        - lateral: コース内ラチからの横位置 (m: 0.8〜20.0m) またはレーン番号(0〜3)
        - 右回り (right): 時計回り（向正面:左->右, 直線:右->左）
        - 左回り (left): 反時計回り（向正面:右->左, 直線:左->右）
        """
        sl = self.world_straight
        r = self.world_r
        peri = self.world_perimeter
        tw = self.world_track_width

        # lateralを0.0(最内)〜1.0(大外)に正規化 (コース幅 30.0m 対応)
        if isinstance(lateral, int) and 0 <= lateral <= 4:
            norm_lat = (lateral + 0.5) / 4.0
        else:
            norm_lat = max(0.02, min(0.98, float(lateral) / 30.0))

        # 最内ラチ沿い (-tw*0.42) 〜 最外ラチ沿い (+tw*0.42) で広々としたワイド走路を活用
        lane_disp = (norm_lat - 0.5) * (tw * 0.84)
        lane_r = r + lane_disp

        is_right = (self.turn == "right")

        # 実周長に対するピクセルスケール比 (px/m)
        lap_dist = self._get_lap_distance()
        scale = peri / max(500.0, lap_dist)

        # ゴール板の位置（スタンド前直線の終わり付近: 92%地点）
        goal_offset = sl + math.pi * r + sl * 0.92

        # スタート地点のピクセルオフセット（ゴールから総走破距離 race_dist 分手前の位置）
        total_race_px = self.distance * scale
        start_offset = (goal_offset - (total_race_px % peri)) % peri

        # 現在のトラック周回上の累積ピクセル距離 (常に単調増加・連続周回)
        dist_along = (start_offset + pos_m * scale) % peri

        heading = 0.0  # 進行方向アングル (ラジアン)

        if is_right:
            if dist_along < sl:
                x = -sl / 2.0 + dist_along
                y = -lane_r
                heading = 0.0
            elif dist_along < sl + math.pi * r:
                arc = dist_along - sl
                t = arc / (math.pi * r)
                x = sl / 2.0 + math.sin(t * math.pi) * lane_r
                y = -math.cos(t * math.pi) * lane_r
                heading = math.atan2(math.sin(t * math.pi), math.cos(t * math.pi))
            elif dist_along < sl * 2.0 + math.pi * r:
                s_dist = dist_along - (sl + math.pi * r)
                x = sl / 2.0 - s_dist
                y = lane_r
                heading = math.pi
            else:
                arc = dist_along - (sl * 2.0 + math.pi * r)
                t = arc / (math.pi * r)
                x = -sl / 2.0 - math.sin(t * math.pi) * lane_r
                y = math.cos(t * math.pi) * lane_r
                heading = math.atan2(-math.sin(t * math.pi), -math.cos(t * math.pi))
        else:
            if dist_along < sl:
                x = sl / 2.0 - dist_along
                y = -lane_r
                heading = math.pi
            elif dist_along < sl + math.pi * r:
                arc = dist_along - sl
                t = arc / (math.pi * r)
                x = -sl / 2.0 - math.sin(t * math.pi) * lane_r
                y = -math.cos(t * math.pi) * lane_r
                heading = math.atan2(math.sin(t * math.pi), -math.cos(t * math.pi))
            elif dist_along < sl * 2.0 + math.pi * r:
                s_dist = dist_along - (sl + math.pi * r)
                x = -sl / 2.0 + s_dist
                y = lane_r
                heading = 0.0
            else:
                arc = dist_along - (sl * 2.0 + math.pi * r)
                t = arc / (math.pi * r)
                x = sl / 2.0 + math.sin(t * math.pi) * lane_r
                y = math.cos(t * math.pi) * lane_r
                heading = math.atan2(-math.sin(t * math.pi), math.cos(t * math.pi))

        return float(x), float(y), float(heading)

    def _calc_track_outer_pos_world(self, pos_m: float, offset_px: float = 24.0) -> Tuple[float, float, float]:
        """全ハロン棒を向正面・コーナー・直線問わず、コース帯（芝・ダート）の外側（外ラチ外周）に配置"""
        sl = self.world_straight
        r = self.world_r
        peri = self.world_perimeter
        tw = self.world_track_width
        lane_r = r + tw / 2.0 + offset_px

        is_right = (self.turn == "right")
        lap_dist = self._get_lap_distance()
        scale = peri / max(500.0, lap_dist)
        goal_offset = sl + math.pi * r + sl * 0.92
        total_race_px = self.distance * scale
        start_offset = (goal_offset - (total_race_px % peri)) % peri
        dist_along = (start_offset + pos_m * scale) % peri

        heading = 0.0
        if is_right:
            if dist_along < sl:
                x = -sl / 2.0 + dist_along
                y = -lane_r
                heading = 0.0
            elif dist_along < sl + math.pi * r:
                arc = dist_along - sl
                t = arc / (math.pi * r)
                x = sl / 2.0 + math.sin(t * math.pi) * lane_r
                y = -math.cos(t * math.pi) * lane_r
                heading = math.atan2(math.sin(t * math.pi), math.cos(t * math.pi))
            elif dist_along < sl * 2.0 + math.pi * r:
                s_dist = dist_along - (sl + math.pi * r)
                x = sl / 2.0 - s_dist
                y = lane_r
                heading = math.pi
            else:
                arc = dist_along - (sl * 2.0 + math.pi * r)
                t = arc / (math.pi * r)
                x = -sl / 2.0 - math.sin(t * math.pi) * lane_r
                y = math.cos(t * math.pi) * lane_r
                heading = math.atan2(-math.sin(t * math.pi), -math.cos(t * math.pi))
        else:
            if dist_along < sl:
                x = sl / 2.0 - dist_along
                y = -lane_r
                heading = math.pi
            elif dist_along < sl + math.pi * r:
                arc = dist_along - sl
                t = arc / (math.pi * r)
                x = -sl / 2.0 - math.sin(t * math.pi) * lane_r
                y = -math.cos(t * math.pi) * lane_r
                heading = math.atan2(math.sin(t * math.pi), -math.cos(t * math.pi))
            elif dist_along < sl * 2.0 + math.pi * r:
                s_dist = dist_along - (sl + math.pi * r)
                x = -sl / 2.0 + s_dist
                y = lane_r
                heading = 0.0
            else:
                arc = dist_along - (sl * 2.0 + math.pi * r)
                t = arc / (math.pi * r)
                x = sl / 2.0 + math.sin(t * math.pi) * lane_r
                y = math.cos(t * math.pi) * lane_r
                heading = math.atan2(-math.sin(t * math.pi), math.cos(t * math.pi))

        return float(x), float(y), float(heading)

    # =========================================================================
    # メイン描画処理
    # =========================================================================
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # 背景（夜間フィールド・濃紺）
        painter.fillRect(0, 0, w, h, QColor("#080c14"))

        # 先頭馬のワールド座標を取得（カメラの中心点）
        cam_x, cam_y = 0.0, 0.0
        horses = []
        if self.replay_frames and self.current_frame_idx < len(self.replay_frames):
            horses = self.replay_frames[self.current_frame_idx].get("horses", [])

        if horses:
            # 先頭馬の位置
            leader = horses[0]
            pos_m = float(leader.get("distance_covered", 0.0))
            lat_m = float(leader.get("lateral", 1.0))
            cam_x, cam_y, _ = self._calc_horse_pos_world(pos_m, lat_m)
        else:
            # レース開始前: スタート地点にカメラを合わせる
            cam_x, cam_y, _ = self._calc_horse_pos_world(0.0, 1.0)

        # ---------------------------------------------------------------------
        # 1. 2D追従スクロールカメラ描画 (ワールド座標系)
        # ---------------------------------------------------------------------
        painter.save()
        # 画面中央 (w/2, h/2 - 30) に先頭馬 (cam_x, cam_y) をセンタリング (下部HUD領域分少し上寄り)
        painter.translate(w / 2.0 - cam_x, (h - 110) / 2.0 - cam_y)

        self._draw_world_track(painter)
        self._draw_world_horses(painter, horses)

        painter.restore()

        # ---------------------------------------------------------------------
        # 2. JRAテレビ中継風 リアルタイムHUD & 下部2段情報HUD (スクリーン座標系)
        # ---------------------------------------------------------------------
        self._draw_jra_broadcast_hud(painter, w, h, horses)
        self._draw_hud_overlay(painter, w, h)

    def _draw_world_track(self, painter: QPainter) -> None:
        """大スケール・ワールドトラック（外柵・芝/ダートコース・内柵・ゴールゲート）の描画"""
        sl = self.world_straight
        r = self.world_r
        tw = self.world_track_width

        mid_rect = QRectF(-sl / 2.0 - r, -r, sl + 2 * r, 2 * r)
        outer_rect = mid_rect.adjusted(-tw / 2.0, -tw / 2.0, tw / 2.0, tw / 2.0)
        inner_rect = mid_rect.adjusted(tw / 2.0, tw / 2.0, -tw / 2.0, -tw / 2.0)

        # 1. 外側敷地
        outer_r = r + tw / 2.0
        painter.setPen(QPen(QColor("#1e293b"), 3))
        painter.setBrush(QBrush(QColor("#0a101d")))
        painter.drawRoundedRect(outer_rect, outer_r, outer_r)

        # 2. コース帯（芝・ダート）
        surf_color = QColor("#065f46") if self.surface == "turf" else QColor("#78350f")
        track_pen = QPen(surf_color, tw)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(mid_rect, r, r)

        # 3. 内馬場（内柵 & 内側広場）
        inner_r = max(10.0, r - tw / 2.0)
        painter.setPen(QPen(QColor("#334155"), 3))
        painter.setBrush(QBrush(QColor("#062319") if self.surface == "turf" else QColor("#1e1510")))
        painter.drawRoundedRect(inner_rect, inner_r, inner_r)

        # 5. リアルハロン棒（添付画像準拠: 白丸看板＋赤数字＋赤白ストライプポール、1ハロン=200m）
        # 全ハロン棒を向正面・直線・コーナー問わず、コース帯（芝生）の外側（外ラチ外周）に配置
        max_furlong = int(self.distance // 200)
        for k in range(1, max_furlong + 1):
            rem_m = 200 * k
            pos_m = self.distance - rem_m
            if pos_m < 0:
                continue

            hx, hy, _ = self._calc_track_outer_pos_world(pos_m, offset_px=24.0)

            # A. 地面の立体シャドウ
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 90)))
            painter.drawEllipse(QPointF(hx + 3, hy + 2), 14, 7)

            # B. 筋交いサポート（斜めの白い支えブレース）
            painter.setPen(QPen(QColor("#e2e8f0"), 2.0))
            painter.drawLine(QPointF(hx - 9, hy + 2), QPointF(hx, hy - 16))
            painter.drawLine(QPointF(hx + 9, hy + 2), QPointF(hx, hy - 16))

            # C. 円柱ポール支柱（赤白交互のボーダーストライプ）
            pole_w = 10.0
            pole_h = 32.0
            pole_top_y = hy - pole_h
            pole_x = hx - pole_w / 2.0

            # 4段のストライプ（白・赤・白・赤）
            stripe_h = pole_h / 4.0
            for s_idx in range(4):
                col = "#dc2626" if s_idx % 2 == 1 else "#f8fafc"
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(col)))
                painter.drawRect(QRectF(pole_x, pole_top_y + s_idx * stripe_h, pole_w, stripe_h))

            # ポール外枠ライン
            painter.setPen(QPen(QColor("#475569"), 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(pole_x, pole_top_y, pole_w, pole_h))

            # D. ポール上部の円形白看板（添付画像デザインの拡大版: 直径 35px）
            head_r = 17.5  # 半径17.5px (直径35px) に拡大！
            head_cx = hx
            head_cy = pole_top_y - head_r + 2.0

            # 看板シャドウ
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 80)))
            painter.drawEllipse(QPointF(head_cx + 2, head_cy + 2), head_r, head_r)

            # 看板本体（純白背景＋濃紺グレー枠線）
            painter.setPen(QPen(QColor("#1e293b"), 2.2))
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.drawEllipse(QPointF(head_cx, head_cy), head_r, head_r)

            # E. 看板中央の赤い太字数字（極太フォントで数字を大きく・ハッキリ表示）
            painter.setPen(QColor("#dc2626"))
            f_size = 16 if k < 10 else 13
            painter.setFont(QFont("Arial", f_size, QFont.Weight.Black))
            painter.drawText(
                QRectF(head_cx - head_r, head_cy - head_r, head_r * 2, head_r * 2),
                Qt.AlignmentFlag.AlignCenter,
                str(k),
            )

        # 6. 立体ゴール板ゲート (ワイド走路対応)
        gx_in, gy_in, _ = self._calc_horse_pos_world(self.distance, 1.0)
        gx_out, gy_out, _ = self._calc_horse_pos_world(self.distance, 29.0)

        # 赤白のゴールライン
        painter.setPen(QPen(QColor("#ef4444"), 8))
        painter.drawLine(QPointF(gx_in, gy_in), QPointF(gx_out, gy_out))
        painter.setPen(QPen(QColor("#ffffff"), 4, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(gx_in, gy_in), QPointF(gx_out, gy_out))

        # ゴールゲート支柱
        painter.setPen(QPen(QColor("#cbd5e1"), 4))
        painter.setBrush(QBrush(QColor("#f8fafc")))
        painter.drawEllipse(QPointF(gx_in, gy_in), 8, 8)
        painter.drawEllipse(QPointF(gx_out, gy_out), 8, 8)

        # ゴールゲート上部アーチ
        g_mid_x = (gx_in + gx_out) / 2.0
        g_mid_y = max(gy_in, gy_out) + 24.0
        painter.setPen(QColor("#f87171"))
        painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        painter.drawText(QRectF(g_mid_x - 60, g_mid_y, 120, 24), Qt.AlignmentFlag.AlignCenter, "🏁 GOAL")

    def _draw_world_horses(self, painter: QPainter, horses: List[Dict[str, Any]]) -> None:
        """迫力ある2D競走馬レンダリング（流線型馬体・四肢のダイナミックなギャロップアニメーション・騎手・JRA枠色ゼッケン）"""
        # 14種類の毛色カラーマップ (体, たてがみ/尾)
        coat_color_map = {
            "栗毛": ("#78350f", "#451a03"),
            "栃栗毛": ("#5c3a21", "#3e2723"),
            "鹿毛": ("#6b4226", "#291e18"),
            "黒鹿毛": ("#291e18", "#120c08"),
            "青鹿毛": ("#1e293b", "#0f172a"),
            "青毛": ("#111827", "#030712"),
            "芦毛": ("#94a3b8", "#cbd5e1"),
            "白毛": ("#f8fafc", "#e2e8f0"),
            "月毛": ("#eab308", "#fef08a"),
            "河原毛": ("#d97706", "#451a03"),
            "粕毛": ("#78716c", "#44403c"),
            "薄墨毛": ("#64748b", "#1e293b"),
            "佐河毛": ("#a16207", "#713f12"),
            "斑毛": ("#a8a29e", "#ffffff"),
        }
        coat_colors = [
            ("#5c3a21", "#3e2723"),  # 鹿毛 (体, たてがみ/尾)
            ("#78350f", "#451a03"),  # 栗毛
            ("#291e18", "#120c08"),  # 黒鹿毛
            ("#1e293b", "#0f172a"),  # 青鹿毛/青毛
            ("#94a3b8", "#cbd5e1"),  # 芦毛
            ("#6b4226", "#451a03"),  # 栃栗毛
        ]

        # 後方の馬から順に描画（先頭馬が手前に重なるよう逆順ループ）
        for rank in range(len(horses) - 1, -1, -1):
            h_data = horses[rank]
            pos_m = float(h_data.get("distance_covered", 0.0))
            lat_m = float(h_data.get("lateral", 1.0))
            num = min(18, max(1, int(h_data.get("number", rank + 1))))
            bracket = int(h_data.get("bracket", get_jra_bracket(num, len(horses))))
            name = str(h_data.get("name", f"馬{num}"))
            is_spurt = h_data.get("is_spurt", False)

            px, py, heading = self._calc_horse_pos_world(pos_m, lat_m)

            bg_col, fg_col, border_col, _ = JRA_BRACKET_COLORS.get(
                bracket, ("#ffffff", "#000000", "#94a3b8", "1枠")
            )
            c_name = h_data.get("coat_color")
            if c_name and c_name in coat_color_map:
                body_col_hex, mane_col_hex = coat_color_map[c_name]
            else:
                body_col_hex, mane_col_hex = coat_colors[(num - 1) % len(coat_colors)]

            # -------------------------------------------------------------
            # 1. ワールド座標系: 全力スパート時の発光ブーストオーラ
            # -------------------------------------------------------------
            if is_spurt:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(245, 158, 11, 55)))
                painter.drawEllipse(QPointF(px, py), 24, 24)
                painter.setPen(QPen(QColor(251, 191, 36, 200), 1.8))
                painter.setBrush(QBrush(QColor(251, 191, 36, 75)))
                painter.drawEllipse(QPointF(px, py), 17, 17)

            # -------------------------------------------------------------
            # 2. ローカル座標系: 走る競走馬（進行方向 heading に回転）
            # -------------------------------------------------------------
            painter.save()
            painter.translate(px, py)
            painter.rotate(math.degrees(heading))  # +X 軸が進行方向

            # 馬体サイズを30%縮小 (スケール0.70)
            horse_scale = 0.70
            painter.scale(horse_scale, horse_scale)

            # ギャロップ（襲歩）の歩法アニメーション計算
            # 走破距離に応じた動的な四肢の伸縮
            anim_phase = (pos_m * 1.8) % (2.0 * math.pi)
            stride_f = math.sin(anim_phase)          # 前脚の振幅 (-1.0〜+1.0)
            stride_b = -math.sin(anim_phase)         # 後脚の振幅 (-1.0〜+1.0)

            # A. 地面の立体楕円シャドウ (進行方向・脚の伸びに応じた影)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 115)))
            painter.drawEllipse(QRectF(-22.0, -11.0, 44.0, 22.0))

            # B. 四肢（4本の脚のダイナミックなギャロップスイング）
            # 奥の前脚 & 後脚 (やや暗め)
            painter.setPen(QPen(QColor(body_col_hex).darker(135), 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(9.0, -6.0), QPointF(14.0 - stride_f * 9.0, -13.5))
            painter.drawLine(QPointF(-10.0, -6.0), QPointF(-16.0 + stride_b * 10.0, -13.5))

            # 手前の前脚 & 後脚 (手前に力強く伸びる)
            painter.setPen(QPen(QColor(body_col_hex), 3.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(10.0, 6.0), QPointF(16.5 + stride_f * 10.5, 14.0))
            painter.drawLine(QPointF(-11.0, 6.0), QPointF(-18.5 - stride_b * 11.5, 14.0))

            # 黒い蹄（ひづめ）
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#0f172a")))
            painter.drawEllipse(QPointF(16.5 + stride_f * 10.5, 14.0), 2.2, 2.2)
            painter.drawEllipse(QPointF(-18.5 - stride_b * 11.5, 14.0), 2.2, 2.2)

            # C. なびく尾毛（テール: スピード感のある流線型）
            tail_path = QPainterPath()
            tail_path.moveTo(-13.0, 0.0)
            tail_path.quadTo(-22.0, -3.0, -30.0, stride_f * 3.5)
            tail_path.quadTo(-23.0, 3.0, -13.0, 1.5)
            tail_path.closeSubpath()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(mane_col_hex)))
            painter.drawPath(tail_path)

            # D. 馬体胴体（トルソー: 美しいサラブレッドの筋肉美）
            painter.setPen(QPen(QColor(mane_col_hex), 1.5))
            painter.setBrush(QBrush(QColor(body_col_hex)))
            painter.drawRoundedRect(QRectF(-15.0, -8.5, 30.0, 17.0), 8.5, 8.5)

            # E. 首と頭部・耳・たてがみ
            # 首から頭部への伸びやかなライン
            neck_head = QPainterPath()
            neck_head.moveTo(9.0, -5.5)
            neck_head.lineTo(23.0, -4.5)   # 頭部先端
            neck_head.lineTo(26.0, -1.0)   # 鼻口部
            neck_head.lineTo(23.0, 3.0)
            neck_head.lineTo(9.0, 5.5)
            neck_head.closeSubpath()
            painter.setPen(QPen(QColor(mane_col_hex), 1.2))
            painter.setBrush(QBrush(QColor(body_col_hex)))
            painter.drawPath(neck_head)

            # ピンと立った耳
            painter.setBrush(QBrush(QColor(body_col_hex).darker(120)))
            painter.drawEllipse(QPointF(20.0, -5.5), 2.8, 1.6)

            # たてがみ
            painter.setPen(QPen(QColor(mane_col_hex), 2.5))
            painter.drawLine(QPointF(10.0, -2.5), QPointF(18.0, -2.5))

            # F. 前傾姿勢で疾走する騎手（ジョッキー: モンキー乗りスタイル）
            # 勝負服（トルソー）
            painter.setPen(QPen(QColor("#0f172a"), 1.0))
            painter.setBrush(QBrush(QColor(border_col).darker(110)))
            painter.drawRoundedRect(QRectF(-5.0, -5.5, 10.0, 11.0), 3.5, 3.5)

            # 騎手ヘルメット (枠色)
            painter.setPen(QPen(QColor("#ffffff"), 1.0))
            painter.setBrush(QBrush(QColor(bg_col)))
            painter.drawEllipse(QPointF(5.5, 0.0), 4.2, 4.2)

            # 手綱ライン (騎手から頭部へ)
            painter.setPen(QPen(QColor("#ffffff"), 1.1))
            painter.drawLine(QPointF(4.0, -2.5), QPointF(18.0, -1.2))
            painter.drawLine(QPointF(4.0, 2.5), QPointF(18.0, 1.2))

            # G. JRA枠色ゼッケン & 馬番（馬番は元の大きさのまま高い視認性を維持）
            # スケールを解除して実ピクセルサイズでゼッケンと馬番を描画
            painter.save()
            painter.scale(1.0 / horse_scale, 1.0 / horse_scale)
            saddle_rect = QRectF(-8.0, -7.5, 16.0, 15.0)
            painter.setPen(QPen(QColor(border_col), 1.6))
            painter.setBrush(QBrush(QColor(bg_col)))
            painter.drawRoundedRect(saddle_rect, 2.5, 2.5)

            painter.setPen(QColor(fg_col))
            painter.setFont(QFont("Arial", 9, QFont.Weight.Black))
            painter.drawText(saddle_rect, Qt.AlignmentFlag.AlignCenter, str(num))
            painter.restore()

            painter.restore()

            # -------------------------------------------------------------
            # 3. ワールド座標系: 先頭馬の強調インジケーター「▼」
            # -------------------------------------------------------------
            if rank == 0:
                painter.setPen(QPen(QColor("#b45309"), 1.2))
                painter.setBrush(QBrush(QColor("#fbbf24")))
                tri = QPainterPath()
                tri.moveTo(px, py - 17.0)
                tri.lineTo(px - 7.0, py - 27.0)
                tri.lineTo(px + 7.0, py - 27.0)
                tri.closeSubpath()
                painter.drawPath(tri)

    # =========================================================================
    # メイン描画処理
    # =========================================================================
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # 背景（夜間フィールド・濃紺）
        painter.fillRect(0, 0, w, h, QColor("#080c14"))

        # 先頭馬のワールド座標を取得（カメラの中心点）
        cam_x, cam_y = 0.0, 0.0
        horses = []
        if self.replay_frames and self.current_frame_idx < len(self.replay_frames):
            horses = self.replay_frames[self.current_frame_idx].get("horses", [])

        if horses:
            # 先頭馬の位置
            leader = horses[0]
            pos_m = float(leader.get("distance_covered", 0.0))
            lat_m = float(leader.get("lateral", 1.0))
            cam_x, cam_y, _ = self._calc_horse_pos_world(pos_m, lat_m)
        else:
            # レース開始前: スタート地点にカメラを合わせる
            cam_x, cam_y, _ = self._calc_horse_pos_world(0.0, 1.0)

        # ---------------------------------------------------------------------
        # 1. 2D追従スクロールカメラ描画 (ワールド座標系)
        # ---------------------------------------------------------------------
        painter.save()
        # 画面中央に先頭馬 (cam_x, cam_y) をセンタリング (下部スリムHUD 68px 分だけ少し上寄り)
        painter.translate(w / 2.0 - cam_x, (h - 68.0) / 2.0 - cam_y)

        self._draw_world_track(painter)
        self._draw_world_horses(painter, horses)

        painter.restore()

        # ---------------------------------------------------------------------
        # 2. JRAテレビ中継風 リアルタイムHUD (スクリーン座標系)
        # ---------------------------------------------------------------------
        # 左上: タイム & 残りハロン
        self._draw_jra_broadcast_hud(painter, w, h, horses)

        # レース開始前（フレーム0）: 画面左上に出走馬一覧HUDを表示
        self._draw_pre_race_entries_overlay(painter, w, h, horses)

        # 右上: 縦並びリアルタイム上位3頭順位表 (JRA公式テロップスタイル)
        # スタートするまで（フレーム0）または結果掲示板表示時は非表示
        if self.current_frame_idx > 0 and not getattr(self, "show_result_board", False):
            self._draw_top3_vertical_hud(painter, w, h, horses)

        # 下部: リアルタイム情報HUD（レース情報・スピード・勾配・ミニマップ・隊列インジケーター）
        self._draw_hud_overlay(painter, w, h)

        # ---------------------------------------------------------------------
        # 3. レース画面内 結果掲示板オーバーレイ (ゴール後に表示)
        # ---------------------------------------------------------------------
        if getattr(self, "show_result_board", False):
            self._draw_race_board_overlay(painter, w, h)

    # =========================================================================
    # スクリーンHUD: JRA公式テレビ中継風 リアルタイム中継HUD
    # =========================================================================
    def _draw_pre_race_entries_overlay(self, painter: QPainter, w: int, h: int, horses: List[Dict[str, Any]]) -> None:
        """レース開始前（フレーム0）に画面左寄りに出走馬一覧HUDを表示（馬番順）"""
        if not horses or self.current_frame_idx > 0 or getattr(self, "show_result_board", False):
            return

        # 馬番順（number 昇順）にソート
        sorted_horses = sorted(horses, key=lambda h: int(h.get("number", 999)))

        total_h = len(sorted_horses)
        row_h = 24.0
        panel_w = 265.0
        max_rows = min(12, total_h)
        panel_h = 32.0 + max_rows * row_h + 8.0
        px = 20.0
        py = 80.0

        # 半透明ダークパネル
        painter.setPen(QPen(QColor("#0284c7"), 1.2))
        painter.setBrush(QBrush(QColor(10, 15, 29, 230)))
        painter.drawRoundedRect(QRectF(px, py, panel_w, panel_h), 6, 6)

        # ヘッダー
        painter.setPen(QColor("#38bdf8"))
        painter.setFont(QFont("Hiragino Sans", 11, QFont.Weight.Bold))
        painter.drawText(int(px + 12), int(py + 22), f"📋 出走馬一覧 ({total_h}頭立)")

        # 各出走馬 (馬番順)
        for idx in range(max_rows):
            h_item = sorted_horses[idx]
            hid = h_item.get("horse_id")
            num = min(18, max(1, int(h_item.get("number", idx + 1))))
            bracket = int(h_item.get("bracket", get_jra_bracket(num, total_h)))
            bg_col, fg_col, border_col, _ = JRA_BRACKET_COLORS.get(bracket, ("#fff", "#000", "#999", ""))

            name = str(h_item.get("name", ""))
            if (not name or name.startswith("馬")) and hid in self.race_results_info:
                name = str(self.race_results_info[hid].get("horse_name", name))
            if not name:
                name = f"馬{num}"

            odds_val = float(h_item.get("odds", 0.0))
            if odds_val <= 0.0 and hid in self.race_results_info:
                odds_val = float(self.race_results_info[hid].get("odds", 0.0))
            odds_str = f"{odds_val:.1f}倍" if odds_val > 0.0 else "--"

            ry = py + 30.0 + idx * row_h

            # 枠色ゼッケン (20x18)
            z_rect = QRectF(px + 10.0, ry + 3.0, 20.0, 18.0)
            painter.setPen(QPen(QColor(border_col), 1.0))
            painter.setBrush(QBrush(QColor(bg_col)))
            painter.drawRoundedRect(z_rect, 2, 2)
            painter.setPen(QColor(fg_col))
            painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            painter.drawText(z_rect, Qt.AlignmentFlag.AlignCenter, str(num))

            # 馬名 (全文字)
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Hiragino Sans", 10, QFont.Weight.Bold))
            painter.drawText(QRectF(px + 36.0, ry + 2.0, 150.0, 20.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)

            # 予想オッズ
            painter.setPen(QColor("#facc15"))
            painter.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
            painter.drawText(QRectF(px + 190.0, ry + 2.0, 65.0, 20.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, odds_str)

    def _draw_jra_broadcast_hud(self, painter: QPainter, w: int, h: int, horses: List[Dict[str, Any]]) -> None:
        """添付スクリーンショット準拠のJRA公式テレビ中継風リアルタイムHUD（画面左上: タイム & ハロン）"""
        cur_sec = self.current_frame_idx * 0.1
        time_str = f"{int(cur_sec // 60):02d}:{cur_sec % 60:04.1f}"

        leader = horses[0] if horses else None
        leader_dist = float(leader.get("distance_covered", 0.0)) if leader else 0.0
        rem_dist = max(0.0, float(self.distance) - leader_dist)

        # ---------------------------------------------------------------------
        # 画面左上: タイム & 残りハロン表示 (JRA公式スタイル)
        # ---------------------------------------------------------------------
        tl_x, tl_y = 20.0, 20.0
        tl_w, tl_h = 165.0, 52.0

        # 半透明ダークプレート
        painter.setPen(QPen(QColor("#38bdf8"), 1))
        painter.setBrush(QBrush(QColor(10, 15, 29, 230)))
        painter.drawRoundedRect(QRectF(tl_x, tl_y, tl_w, tl_h), 6, 6)

        # 残りハロン数アイコン
        furlongs_rem = max(1, int(math.ceil(rem_dist / 200.0))) if rem_dist > 0 else 0
        furlong_str = f"{furlongs_rem}F" if rem_dist > 0 else "GOAL"

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#0284c7") if rem_dist > 0 else QColor("#10b981")))
        painter.drawRoundedRect(QRectF(tl_x + 5, tl_y + 5, 48, 42), 4, 4)

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Arial", 15, QFont.Weight.Bold))
        painter.drawText(QRectF(tl_x + 5, tl_y + 5, 48, 42), Qt.AlignmentFlag.AlignCenter, furlong_str)

        # TIME ラベル & タイム数字
        painter.setPen(QColor("#94a3b8"))
        painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        painter.drawText(int(tl_x + 60), int(tl_y + 20), "TIME")

        painter.setPen(QColor("#f8fafc"))
        painter.setFont(QFont("Arial", 15, QFont.Weight.Bold))
        painter.drawText(int(tl_x + 60), int(tl_y + 42), time_str)

    def _draw_top3_vertical_hud(self, painter: QPainter, w: int, h: int, horses: List[Dict[str, Any]]) -> None:
        """
        画面右上: 上位3頭のリアルタイム順位表（右側縦書き・縦並びカードスタック）
        表示項目: [順位・馬番] 名前、オッズ、距離
        JRAテレビ中継の順位テロップに完全準拠
        ※ スタートするまで（フレーム0）は何も表示しない
        """
        if not horses or self.current_frame_idx == 0:
            return

        top3 = horses[:3]
        total_horses = len(horses)
        leader = horses[0]
        leader_dist = float(leader.get("distance_covered", 0.0))

        top_w = 325.0
        row_h = 34.0
        top_h = row_h * len(top3) + 8.0
        top_x = float(w) - top_w - 20.0
        top_y = 20.0

        # 背景パネル
        painter.setPen(QPen(QColor("#38bdf8"), 1.2))
        painter.setBrush(QBrush(QColor(10, 15, 29, 235)))
        painter.drawRoundedRect(QRectF(top_x, top_y, top_w, top_h), 6, 6)

        # 各行の描画
        rank_badges = [
            ("1", "#f59e0b", "#000000"),  # 1位: 金色
            ("2", "#94a3b8", "#000000"),  # 2位: 銀色
            ("3", "#b45309", "#ffffff"),  # 3位: 銅色
        ]

        for rk, h_item in enumerate(top3):
            ry = top_y + 4.0 + rk * row_h
            hid = h_item.get("horse_id")
            num = min(18, max(1, int(h_item.get("number", rk + 1))))
            bracket = int(h_item.get("bracket", get_jra_bracket(num, total_horses)))
            
            # 馬名の完全取得（DB結果マップからもフォールバック）
            name = str(h_item.get("name", ""))
            if (not name or name.startswith("馬")) and hid in self.race_results_info:
                name = str(self.race_results_info[hid].get("horse_name", name))
            if not name:
                name = f"馬{num}"

            bg_col, fg_col, border_col, _ = JRA_BRACKET_COLORS.get(bracket, ("#fff", "#000", "#999", ""))

            # 単勝オッズの取得
            odds_val = float(h_item.get("odds", 0.0))
            if odds_val <= 0.0 and hid in self.race_results_info:
                odds_val = float(self.race_results_info[hid].get("odds", 0.0))
            odds_str = f"{odds_val:.1f}倍" if odds_val > 0.0 else "--"

            # 1. 順位丸バッジ (18x18)
            r_str, r_bg, r_fg = rank_badges[rk]
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(r_bg)))
            painter.drawEllipse(QPointF(top_x + 14.0, ry + 17.0), 9.0, 9.0)
            painter.setPen(QColor(r_fg))
            painter.setFont(QFont("Arial", 9, QFont.Weight.Black))
            painter.drawText(QRectF(top_x + 5.0, ry + 8.0, 18.0, 18.0), Qt.AlignmentFlag.AlignCenter, r_str)

            # 2. 枠番・馬番ゼッケン (20x18)
            z_rect = QRectF(top_x + 28.0, ry + 8.0, 20.0, 18.0)
            painter.setPen(QPen(QColor(border_col), 1.0))
            painter.setBrush(QBrush(QColor(bg_col)))
            painter.drawRoundedRect(z_rect, 3, 3)
            painter.setPen(QColor(fg_col))
            painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            painter.drawText(z_rect, Qt.AlignmentFlag.AlignCenter, str(num))

            # 3. 馬名 (名前 - スライスせず全文字を完全表示)
            font_size = 10 if len(name) <= 8 else (9 if len(name) <= 10 else 8)
            painter.setPen(QColor("#ffffff" if rk == 0 else "#e2e8f0"))
            painter.setFont(QFont("Hiragino Sans", font_size, QFont.Weight.Bold))
            painter.drawText(QRectF(top_x + 52.0, ry + 5.0, 136.0, 24.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)

            # 4. オッズ (オッズ)
            painter.setPen(QColor("#facc15"))
            painter.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
            painter.drawText(QRectF(top_x + 192.0, ry + 6.0, 56.0, 22.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, odds_str)

            # 5. 距離 (先頭 / 着差)
            if rk == 0:
                painter.setPen(QColor("#38bdf8"))
                dist_str = "先頭"
            else:
                diff_m = max(0.0, leader_dist - float(h_item.get("distance_covered", 0.0)))
                painter.setPen(QColor("#94a3b8"))
                dist_str = f"-{diff_m:.1f}m"

            painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            painter.drawText(QRectF(top_x + 252.0, ry + 6.0, 65.0, 22.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, dist_str)

            # 区切り線
            if rk < len(top3) - 1:
                painter.setPen(QPen(QColor(51, 65, 85, 140), 1))
                painter.drawLine(QPointF(top_x + 8.0, ry + row_h), QPointF(top_x + top_w - 8.0, ry + row_h))

    def _calculate_slope_pct(self, leader_dist: float) -> float:
        """現在の1位馬の走破位置（leader_dist）に応じたリニアな勾配率 (%) を計算"""
        rem = max(0.0, float(self.distance) - leader_dist)
        t_id = str(getattr(self, "track_id", "A")).upper()

        if t_id == "C":
            if 70.0 <= rem <= 240.0:
                mid = 145.0
                ratio = (240.0 - rem) / (240.0 - mid) if rem >= mid else (rem - 70.0) / (mid - 70.0)
                return round(2.2 * max(0.0, min(1.0, ratio)), 1)
            elif rem < 70.0:
                return 0.0
            return 0.2
        elif t_id == "E":
            if 80.0 <= rem <= 210.0:
                mid = 140.0
                ratio = (210.0 - rem) / (210.0 - mid) if rem >= mid else (rem - 80.0) / (mid - 80.0)
                return round(1.8 * max(0.0, min(1.0, ratio)), 1)
            return 0.0
        elif t_id == "A":
            if 240.0 <= rem <= 360.0:
                mid = 290.0
                ratio = (360.0 - rem) / (360.0 - mid) if rem >= mid else (rem - 240.0) / (mid - 240.0)
                return round(2.0 * max(0.0, min(1.0, ratio)), 1)
            return 0.0
        elif t_id == "B":
            if 300.0 <= rem <= 500.0:
                mid = 400.0
                ratio = (500.0 - rem) / (500.0 - mid) if rem >= mid else (rem - 300.0) / (mid - 300.0)
                return round(1.5 * max(0.0, min(1.0, ratio)), 1)
            return 0.0
        elif t_id == "D":
            if 600.0 <= rem <= 820.0:
                ratio = (820.0 - rem) / 220.0
                return round(2.8 * max(0.0, min(1.0, ratio)), 1)
            elif 380.0 <= rem < 600.0:
                ratio = (600.0 - rem) / 220.0
                return round(-2.8 * max(0.0, min(1.0, ratio)), 1)
            return 0.0
        return 0.0

    def _draw_hud_overlay(self, painter: QPainter, w: int, h: int) -> None:
        """スリム化された下部HUD（高さ68px: レース情報・スピード・勾配・ミニマップ・隊列バー）"""
        if not self.replay_frames:
            return

        frame = self.replay_frames[min(self.current_frame_idx, len(self.replay_frames) - 1)]
        horses = frame.get("horses", [])
        leader = horses[0] if horses else None
        leader_dist = float(leader.get("distance_covered", 0.0)) if leader else 0.0
        rem_dist = max(0.0, float(self.distance) - leader_dist)

        track = get_track_info(self.track_id)
        surf_jp = "芝" if self.surface == "turf" else "ダート"

        # ---------------------------------------------------------------------
        # メインHUDバー: 1段スリム構成 (高さ 68px)
        # ---------------------------------------------------------------------
        hud_h = 68.0
        hud_y = h - hud_h
        hud_w = float(w)

        # メイン背景パネル
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(8, 12, 22, 245)))
        painter.drawRect(QRectF(0, hud_y, hud_w, hud_h))

        # 上部境界アクセントライン (シアン)
        painter.setPen(QPen(QColor("#38bdf8"), 2))
        painter.drawLine(QPointF(0, hud_y), QPointF(hud_w, hud_y))

        # =====================================================================
        # 左ブロック: レース名・距離・スピード・勾配 (幅 380px)
        # =====================================================================
        sec1_w = min(400.0, max(320.0, hud_w * 0.35))

        # 1-A. レース名 & グレードバッジ (行1)
        g_raw = str(getattr(self, "race_grade", "") or "").upper()
        g_text = g_raw if ("G1" in g_raw or "G2" in g_raw or "G3" in g_raw) else ("G1" if "G1" in getattr(self, "race_name", "") else "")
        g_bg = "#dc2626" if "G1" in g_text else ("#2563eb" if "G2" in g_text else ("#16a34a" if "G3" in g_text else "#0284c7"))

        cur_x = 14.0
        if g_text:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(g_bg)))
            painter.drawRoundedRect(QRectF(cur_x, hud_y + 8, 36, 20), 3, 3)
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Arial", 10, QFont.Weight.Black))
            painter.drawText(QRectF(cur_x, hud_y + 8, 36, 20), Qt.AlignmentFlag.AlignCenter, g_text)
            cur_x += 42.0

        r_name_raw = str(getattr(self, "race_name", "") or f"{track.name} 特別")
        r_name = clean_race_name(r_name_raw)
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Hiragino Sans", 13, QFont.Weight.Bold))
        painter.drawText(int(cur_x), int(hud_y + 23), r_name[:11])

        # コース種別 & 距離 & 競馬場名
        painter.setPen(QColor("#fbbf24"))
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        track_turn_str = "右" if self.turn == "right" else "左"
        painter.drawText(int(cur_x + 145), int(hud_y + 23), f"{track.name} {surf_jp}{self.distance:,}m ({track_turn_str})")

        # 1-B. スピード表示 & リニア勾配 & 残り距離 (行2)
        speed_kmh = 0.0
        if leader and self.current_frame_idx > 0 and self.current_frame_idx < len(self.replay_frames):
            prev_horses = self.replay_frames[self.current_frame_idx - 1].get("horses", [])
            if prev_horses:
                prev_dist = float(prev_horses[0].get("distance_covered", 0.0))
                step_dist = max(0.0, leader_dist - prev_dist)
                speed_kmh = (step_dist / 0.1) * 3.6
        if speed_kmh < 1.0 and leader_dist > 5.0:
            speed_kmh = 58.5

        slope_pct = self._calculate_slope_pct(leader_dist)

        painter.setPen(QColor("#38bdf8"))
        painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        painter.drawText(int(14), int(hud_y + 52), f"⏱ {speed_kmh:.1f} km/h")

        if slope_pct >= 1.5:
            slope_color = QColor("#ef4444")
        elif slope_pct > 0.0:
            slope_color = QColor("#fbbf24")
        elif slope_pct < -0.5:
            slope_color = QColor("#34d399")
        else:
            slope_color = QColor("#94a3b8")
        painter.setPen(slope_color)
        painter.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        painter.drawText(int(145), int(hud_y + 52), f"◿ {slope_pct:+.1f}%")

        painter.setPen(QColor("#f8fafc"))
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        painter.drawText(int(235), int(hud_y + 51), f"残り {int(rem_dist)}m")

        # 縦境界線 (左ブロックと中央ミニマップの間)
        painter.setPen(QPen(QColor(51, 65, 85, 180), 1))
        painter.drawLine(QPointF(sec1_w, hud_y + 6), QPointF(sec1_w, hud_y + hud_h - 6))

        # =====================================================================
        # 中央ブロック: コース全体図ミニマップ (幅 140px)
        # =====================================================================
        sec2_map_w = 140.0
        sec2_map_x = sec1_w + 10.0
        map_rect = QRectF(sec2_map_x, hud_y + 6, sec2_map_w, hud_h - 12)

        painter.save()
        painter.setPen(QPen(QColor(30, 41, 59), 1))
        painter.setBrush(QBrush(QColor(10, 16, 28, 220)))
        painter.drawRoundedRect(map_rect, 4, 4)

        sl_m = self.world_straight
        r_m = self.world_r
        tw_m = self.world_track_width
        usable_map_w = sec2_map_w - 14.0
        usable_map_h = map_rect.height() - 8.0
        total_world_w = sl_m + 2.0 * r_m + tw_m + 60.0
        total_world_h = 2.0 * r_m + tw_m + 60.0
        scale_m = min(usable_map_w / total_world_w, usable_map_h / total_world_h)
        map_cx = sec2_map_x + sec2_map_w / 2.0
        map_cy = map_rect.top() + map_rect.height() / 2.0

        m_sl = sl_m * scale_m
        m_r = r_m * scale_m
        m_tw = max(3.0, tw_m * scale_m)

        mini_mid_rect = QRectF(map_cx - m_sl / 2.0 - m_r, map_cy - m_r, m_sl + 2 * m_r, 2 * m_r)
        surf_color_m = QColor("#047857") if self.surface == "turf" else QColor("#92400e")
        painter.setPen(QPen(surf_color_m, m_tw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(mini_mid_rect, m_r, m_r)

        # ゴール & スタート
        gw_x, gw_y, _ = self._calc_horse_pos_world(self.distance, 15.0)
        gm_x = map_cx + gw_x * scale_m
        gm_y = map_cy + gw_y * scale_m
        painter.setPen(QPen(QColor("#ef4444"), 2.0))
        painter.drawLine(QPointF(gm_x, gm_y - 3), QPointF(gm_x, gm_y + 3))

        sw_x, sw_y, _ = self._calc_horse_pos_world(0.0, 15.0)
        sm_x = map_cx + sw_x * scale_m
        sm_y = map_cy + sw_y * scale_m
        painter.setPen(QColor("#fbbf24"))
        painter.setFont(QFont("Arial", 6, QFont.Weight.Bold))
        painter.drawText(int(sm_x - 3), int(sm_y - 3), "S")

        # 各馬ミニドット
        if horses:
            for h_item in reversed(horses):
                d_val = float(h_item.get("distance_covered", 0.0))
                l_val = float(h_item.get("lateral", 1.0))
                hw_x, hw_y, _ = self._calc_horse_pos_world(d_val, l_val)
                hm_x = map_cx + hw_x * scale_m
                hm_y = map_cy + hw_y * scale_m
                num = min(18, max(1, int(h_item.get("number", 1))))
                bracket = int(h_item.get("bracket", get_jra_bracket(num, len(horses))))
                bg_col, _, _, _ = JRA_BRACKET_COLORS.get(bracket, ("#fff", "#000", "#999", ""))
                is_cur_leader = (h_item.get("horse_id") == leader.get("horse_id")) if leader else False
                if is_cur_leader:
                    painter.setPen(QPen(QColor("#38bdf8"), 1.2))
                    painter.setBrush(QBrush(QColor(bg_col)))
                    painter.drawEllipse(QPointF(hm_x, hm_y), 2.5, 2.5)
                else:
                    painter.setPen(QPen(QColor(0, 0, 0, 150), 0.5))
                    painter.setBrush(QBrush(QColor(bg_col)))
                    painter.drawEllipse(QPointF(hm_x, hm_y), 1.8, 1.8)
        painter.restore()

        # 縦境界線 (ミニマップと隊列インジケーターの間)
        painter.setPen(QPen(QColor(51, 65, 85, 180), 1))
        painter.drawLine(QPointF(sec2_map_x + sec2_map_w + 8.0, hud_y + 6), QPointF(sec2_map_x + sec2_map_w + 8.0, hud_y + hud_h - 6))

        # =====================================================================
        # 右ブロック: リアルタイム隊列インジケーター (順位バー) (幅 半分)
        # =====================================================================
        sec_mid_x = sec2_map_x + sec2_map_w + 16.0
        avail_indicator_w = hud_w - sec_mid_x - 16.0
        sec_mid_w = min(540.0, max(240.0, avail_indicator_w * 0.55))
        field_rect = QRectF(sec_mid_x, hud_y + 6, sec_mid_w, hud_h - 12)

        is_moving_right = True
        if leader:
            _, _, leader_heading = self._calc_horse_pos_world(leader_dist, float(leader.get("lateral", 1.0)))
            is_moving_right = math.cos(leader_heading) >= 0.0

        target_factor = 1.0 if is_moving_right else -1.0
        diff = target_factor - self.indicator_flip_factor
        if abs(diff) > 0.01:
            step = 0.15 if diff > 0 else -0.15
            self.indicator_flip_factor += step if abs(diff) >= abs(step) else diff
        else:
            self.indicator_flip_factor = target_factor

        display_is_right = (self.indicator_flip_factor >= 0.0)
        flip_scale = max(0.04, abs(self.indicator_flip_factor))

        center_x = sec_mid_x + sec_mid_w / 2.0
        painter.save()
        painter.translate(center_x, 0)
        painter.scale(flip_scale, 1.0)
        painter.translate(-center_x, 0)

        painter.setPen(QPen(QColor(30, 41, 59), 1))
        painter.setBrush(QBrush(QColor(12, 18, 32, 220)))
        painter.drawRoundedRect(field_rect, 4, 4)

        # 内ラチ・外ラチライン
        painter.setPen(QPen(QColor("#10b981"), 1.2))
        painter.drawLine(QPointF(sec_mid_x + 4, field_rect.top() + 6), QPointF(sec_mid_x + sec_mid_w - 4, field_rect.top() + 6))
        painter.setPen(QPen(QColor("#64748b"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(sec_mid_x + 4, field_rect.bottom() - 6), QPointF(sec_mid_x + sec_mid_w - 4, field_rect.bottom() - 6))

        max_behind = 0.0
        if horses and leader:
            for h_item in horses:
                d = float(h_item.get("distance_covered", 0.0))
                diff = max(0.0, leader_dist - d)
                if diff > max_behind:
                    max_behind = diff
        view_dist_span = max(70.0, max_behind + 12.0)

        arrow_pad = 28.0
        left_bound = sec_mid_x + arrow_pad
        right_bound = sec_mid_x + sec_mid_w - arrow_pad
        usable_w = right_bound - left_bound

        if display_is_right:
            leader_screen_x = right_bound
            arrow_cx = right_bound + 13.0
        else:
            leader_screen_x = left_bound
            arrow_cx = left_bound - 13.0

        arrow_cy = field_rect.center().y()
        arrow_path = QPainterPath()
        if display_is_right:
            arrow_path.moveTo(arrow_cx + 7.0, arrow_cy)
            arrow_path.lineTo(arrow_cx - 5.0, arrow_cy - 6.0)
            arrow_path.lineTo(arrow_cx - 5.0, arrow_cy + 6.0)
        else:
            arrow_path.moveTo(arrow_cx - 7.0, arrow_cy)
            arrow_path.lineTo(arrow_cx + 5.0, arrow_cy - 6.0)
            arrow_path.lineTo(arrow_cx + 5.0, arrow_cy + 6.0)
        arrow_path.closeSubpath()
        painter.setPen(QPen(QColor("#38bdf8"), 1.5))
        painter.setBrush(QBrush(QColor("#0284c7")))
        painter.drawPath(arrow_path)

        # ハロン棒標識
        max_furlong = int(self.distance // 200)
        for k in range(1, max_furlong + 1):
            f_dist = self.distance - 200 * k
            behind_f = leader_dist - f_dist
            if -8.0 <= behind_f <= view_dist_span + 8.0:
                f_ratio = behind_f / view_dist_span
                fx = leader_screen_x - f_ratio * usable_w if display_is_right else leader_screen_x + f_ratio * usable_w
                if left_bound - 6 <= fx <= right_bound + 6:
                    painter.setPen(QPen(QColor("#dc2626"), 1.8))
                    painter.drawLine(QPointF(fx, field_rect.top() + 4), QPointF(fx, field_rect.bottom() - 4))
                    f_badge_cy = field_rect.top() + 7.0
                    painter.setPen(QPen(QColor("#334155"), 1.0))
                    painter.setBrush(QBrush(QColor("#ffffff")))
                    painter.drawEllipse(QPointF(fx, f_badge_cy), 7.0, 7.0)
                    painter.setPen(QColor("#dc2626"))
                    painter.setFont(QFont("Arial", 7, QFont.Weight.Bold))
                    painter.drawText(QRectF(fx - 7.0, f_badge_cy - 7.0, 14.0, 14.0), Qt.AlignmentFlag.AlignCenter, str(k))

        track_y_min = field_rect.top() + 11.0
        track_y_max = field_rect.bottom() - 11.0

        for rk in range(len(horses) - 1, -1, -1):
            h_data = horses[rk]
            d_covered = float(h_data.get("distance_covered", 0.0))
            lat_m = float(h_data.get("lateral", 1.0))
            num = min(18, max(1, int(h_data.get("number", rk + 1))))
            bracket = int(h_data.get("bracket", get_jra_bracket(num, len(horses))))

            behind_m = max(0.0, leader_dist - d_covered)
            ratio = min(1.0, behind_m / view_dist_span)
            hx = leader_screen_x - ratio * usable_w if display_is_right else leader_screen_x + ratio * usable_w
            hx = max(left_bound, min(right_bound, hx))

            lat_ratio = max(0.0, min(1.0, (lat_m - 1.5) / 26.5))
            hy = track_y_min + lat_ratio * (track_y_max - track_y_min)

            bg_col, fg_col, border_col, _ = JRA_BRACKET_COLORS.get(bracket, ("#fff", "#000", "#999", ""))
            c_rad = 10.0
            painter.setPen(QPen(QColor(border_col), 1.5))
            painter.setBrush(QBrush(QColor(bg_col)))
            painter.drawEllipse(QPointF(hx, hy), c_rad, c_rad)

            painter.setPen(QColor(fg_col))
            painter.setFont(QFont("Arial", 9 if num < 10 else 7, QFont.Weight.Bold))
            painter.drawText(QRectF(hx - c_rad, hy - c_rad, c_rad * 2, c_rad * 2), Qt.AlignmentFlag.AlignCenter, str(num))

        painter.restore()

    def _draw_race_board_overlay(self, painter: QPainter, w: int, h: int) -> None:
        """
        実写・JRA競馬場LED電光着順掲示板（添付写真完全準拠）
        - 背景: 濃紺・スチール枠
        - 数字・文字スロット: 暗緑がかったグレー（#18262a）
        - 最上段: 競馬場名（縦書き「東\n京」）、レース番号（黄色LED「9」+白「R」）、赤枠朱色「確定」ランプ
        - 1〜5着: 青丸ローマ数字（Ⅰ〜Ⅴ）、黄色LED馬番（0埋めなし）、シアン「>」記号、黄色LED着差
        - 下部: 芝/ダート（白）+良（黄色LEDスロット）、タイム（白）+1.22.8（黄色LEDスロット）、4F/3Fタイム
        """
        d = getattr(self, "board_data", {})
        raw_track_name = str(d.get("track_name", "東京"))
        track_name = raw_track_name.replace("競馬場", "").strip() or "東京"
        race_number_raw = str(d.get("race_number", "11"))
        r_num_digits = "".join(filter(str.isdigit, race_number_raw)) or "11"

        surface_jp = str(d.get("surface_jp", "芝"))
        top5 = d.get("top5_horses", [])
        finish_time = float(d.get("finish_time", 0.0))
        is_record = bool(d.get("is_record", False))
        f3_time = float(d.get("f3_time", 0.0))
        is_confirmed = bool(getattr(self, "board_confirmed", False))

        board_w = 230.0
        board_h = 440.0
        board_x = float(w) - board_w - 20.0
        board_y = 20.0

        # メインフレーム（外枠スチールベゼル + 濃紺LED掲示板背景）
        painter.save()

        # 1. 外側プレート
        painter.setPen(QPen(QColor("#3a4754"), 2.5))
        painter.setBrush(QBrush(QColor("#111822")))
        painter.drawRoundedRect(QRectF(board_x, board_y, board_w, board_h), 6, 6)

        # 共通スロット描画ヘルパー
        def draw_slot(rect: QRectF):
            painter.setPen(QPen(QColor("#24363c"), 1.0))
            painter.setBrush(QBrush(QColor("#18262a")))
            painter.drawRoundedRect(rect, 2, 2)

        # =====================================================================
        # 1. 最上段ヘッダー: 競馬場名 (縦書き) + レース番号 (特大) + 「確 定」
        # =====================================================================
        # 競馬場名（2文字縦書き）
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Hiragino Sans", 14, QFont.Weight.Medium))
        t_chars = list(track_name[:2])
        if len(t_chars) == 1:
            painter.drawText(QRectF(board_x + 8, board_y + 8, 24, 34), Qt.AlignmentFlag.AlignCenter, t_chars[0])
        elif len(t_chars) >= 2:
            painter.drawText(QRectF(board_x + 8, board_y + 6, 24, 18), Qt.AlignmentFlag.AlignCenter, t_chars[0])
            painter.drawText(QRectF(board_x + 8, board_y + 24, 24, 18), Qt.AlignmentFlag.AlignCenter, t_chars[1])

        # レース番号（細身・クリアな黄色LED数字 + 白「R」）
        f_rnum = QFont("Helvetica Neue", 28, QFont.Weight.Normal)
        f_rnum.setStyleHint(QFont.StyleHint.SansSerif)
        painter.setPen(QColor("#ffd43b"))
        painter.setFont(f_rnum)
        painter.drawText(QRectF(board_x + 36, board_y + 4, 38, 38), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, r_num_digits)

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Arial", 12, QFont.Weight.Normal))
        painter.drawText(int(board_x + 76), int(board_y + 22), "R")

        # 確定ランプ（赤枠 + 朱色背景 + 白文字）
        kakutei_rect = QRectF(board_x + board_w - 92.0, board_y + 8.0, 82.0, 34.0)
        if is_confirmed:
            painter.setPen(QPen(QColor("#f87171"), 2.0))
            painter.setBrush(QBrush(QColor("#c53030")))
            painter.drawRoundedRect(kakutei_rect, 3, 3)
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Hiragino Sans", 16, QFont.Weight.Bold))
            painter.drawText(kakutei_rect, Qt.AlignmentFlag.AlignCenter, "確 定")
        else:
            painter.setPen(QPen(QColor("#24363c"), 1.2))
            painter.setBrush(QBrush(QColor("#18262a")))
            painter.drawRoundedRect(kakutei_rect, 3, 3)
            painter.setPen(QColor("#334155"))
            painter.setFont(QFont("Hiragino Sans", 16, QFont.Weight.Normal))
            painter.drawText(kakutei_rect, Qt.AlignmentFlag.AlignCenter, "確 定")

        # =====================================================================
        # 2. 1〜5着の行表示 (Ⅰ〜Ⅴ)
        # =====================================================================
        roman_nums = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ"]
        row_y_start = board_y + 50.0
        row_h = 36.0

        for i in range(5):
            ry = row_y_start + i * row_h

            # 着順サークル (青丸バッジ + 白ローマ数字: 細身でクリア)
            pos_rect = QRectF(board_x + 10, ry + 4, 26, 26)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#0284c7")))
            painter.drawEllipse(pos_rect)
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Hiragino Sans", 13, QFont.Weight.Normal))
            painter.drawText(pos_rect, Qt.AlignmentFlag.AlignCenter, roman_nums[i])

            # 馬番スロット（暗緑がかったグレースロット）
            gate_slot_rect = QRectF(board_x + 42, ry + 3, 44, 28)
            draw_slot(gate_slot_rect)

            # 着差スロット（暗緑がかったグレースロット）
            margin_slot_rect = QRectF(board_x + 108, ry + 3, board_w - 118, 28)
            draw_slot(margin_slot_rect)

            # 着差の「>」記号（2〜5着の行間、シアン色）
            if i > 0:
                painter.setPen(QColor("#38bdf8"))
                painter.setFont(QFont("Arial", 14, QFont.Weight.Normal))
                painter.drawText(QRectF(board_x + 88, ry + 3, 18, 28), Qt.AlignmentFlag.AlignCenter, ">")

            # 確定データ表示
            if is_confirmed and i < len(top5):
                h_info = top5[i]
                g_num = int(h_info.get("gate_number", 0))
                gate_str = str(g_num) if g_num > 0 else ""
                margin_str = str(h_info.get("margin", "")) if i > 0 else ""

                # 馬番（細身・はっきりとした黄色LED数字）
                f_gate = QFont("Helvetica Neue", 20, QFont.Weight.Normal)
                f_gate.setStyleHint(QFont.StyleHint.SansSerif)
                painter.setPen(QColor("#ffd43b"))
                painter.setFont(f_gate)
                painter.drawText(gate_slot_rect, Qt.AlignmentFlag.AlignCenter, gate_str)

                # 着差（黄色フォント・すっきり表示）
                if margin_str:
                    painter.setPen(QColor("#ffd43b"))
                    painter.setFont(QFont("Hiragino Sans", 13, QFont.Weight.Normal))
                    painter.drawText(margin_slot_rect, Qt.AlignmentFlag.AlignCenter, margin_str)

        # =====================================================================
        # 3. 下部エリア: 馬場状態（左） & タイム・4F・3F（右）
        # =====================================================================
        bot_y = row_y_start + 5 * row_h + 10.0

        # --- 左側: 馬場状態 (芝 / 良, ダート / 稍重等) ---
        # 芝
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Hiragino Sans", 13, QFont.Weight.Medium))
        painter.drawText(QRectF(board_x + 10, bot_y, 48, 20), Qt.AlignmentFlag.AlignCenter, "芝")

        turf_slot = QRectF(board_x + 10, bot_y + 22, 48, 28)
        draw_slot(turf_slot)
        if surface_jp == "芝" and is_confirmed:
            painter.setPen(QColor("#ffd43b"))
            painter.setFont(QFont("Hiragino Sans", 16, QFont.Weight.Medium))
            painter.drawText(turf_slot, Qt.AlignmentFlag.AlignCenter, "良")

        # ダート
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Hiragino Sans", 11, QFont.Weight.Medium))
        painter.drawText(QRectF(board_x + 10, bot_y + 54, 48, 18), Qt.AlignmentFlag.AlignCenter, "ダート")

        dirt_slot = QRectF(board_x + 10, bot_y + 74, 48, 28)
        draw_slot(dirt_slot)
        if surface_jp == "ダート" and is_confirmed:
            painter.setPen(QColor("#ffd43b"))
            painter.setFont(QFont("Hiragino Sans", 16, QFont.Weight.Medium))
            painter.drawText(dirt_slot, Qt.AlignmentFlag.AlignCenter, "良")

        # --- 右側: タイム (1.22.8) / 4F (47.2) / 3F (35.1) ---
        right_x = board_x + 68

        # 1. タイム
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Hiragino Sans", 12, QFont.Weight.Medium))
        painter.drawText(QRectF(right_x, bot_y + 22, 44, 28), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "タイム")

        time_slot = QRectF(right_x + 44, bot_y + 22, board_w - (right_x + 44 - board_x) - 10, 28)
        draw_slot(time_slot)

        f_time_font = QFont("Helvetica Neue", 19, QFont.Weight.Normal)
        f_time_font.setStyleHint(QFont.StyleHint.SansSerif)

        if is_confirmed and finish_time > 0:
            m = int(finish_time // 60)
            s = finish_time - (m * 60)
            # 添付画像スタイル: 1.22.8
            time_str = f"{m}.{s:04.1f}"

            if is_record:
                # レコード表示: 赤枠 + 左側に赤字「R」 + 右側にタイム
                painter.setPen(QPen(QColor("#ef4444"), 1.5))
                painter.setBrush(QBrush(QColor("#450a0a")))
                painter.drawRoundedRect(time_slot, 2, 2)

                # タイムの左側に赤字で「R」
                r_width = 16.0
                r_rect = QRectF(time_slot.x() + 4, time_slot.y(), r_width, time_slot.height())
                painter.setPen(QColor("#ef4444"))
                painter.setFont(QFont("Arial", 16, QFont.Weight.Bold))
                painter.drawText(r_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "R")

                # タイム文字（黄色・細身クリア）
                t_rect = QRectF(time_slot.x() + r_width + 2, time_slot.y(), time_slot.width() - r_width - 6, time_slot.height())
                painter.setPen(QColor("#ffd43b"))
                painter.setFont(f_time_font)
                painter.drawText(t_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, time_str)
            else:
                painter.setPen(QColor("#ffd43b"))
                painter.setFont(f_time_font)
                painter.drawText(time_slot, Qt.AlignmentFlag.AlignCenter, time_str)

        # 2. 4Fタイム (推定4F: 3F * 1.33 + 0.2)
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Arial", 13, QFont.Weight.Medium))
        painter.drawText(QRectF(right_x + 6, bot_y + 56, 38, 24), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "4F")

        f4_slot = QRectF(right_x + 44, bot_y + 54, board_w - (right_x + 44 - board_x) - 10, 24)
        draw_slot(f4_slot)

        f_sub_font = QFont("Helvetica Neue", 16, QFont.Weight.Normal)
        f_sub_font.setStyleHint(QFont.StyleHint.SansSerif)

        if is_confirmed and f3_time > 0:
            f4_time = round(f3_time * 1.33 + 0.2, 1)
            painter.setPen(QColor("#ffd43b"))
            painter.setFont(f_sub_font)
            painter.drawText(f4_slot, Qt.AlignmentFlag.AlignCenter, f"{f4_time:.1f}")

        # 3. 3Fタイム
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Arial", 13, QFont.Weight.Medium))
        painter.drawText(QRectF(right_x + 6, bot_y + 82, 38, 24), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "3F")

        f3_slot = QRectF(right_x + 44, bot_y + 80, board_w - (right_x + 44 - board_x) - 10, 24)
        draw_slot(f3_slot)

        if is_confirmed and f3_time > 0:
            painter.setPen(QColor("#ffd43b"))
            painter.setFont(f_sub_font)
            painter.drawText(f3_slot, Qt.AlignmentFlag.AlignCenter, f"{f3_time:.1f}")

        painter.restore()

    def _draw_all_horses_result_overlay(self, painter: QPainter, w: int, h: int, horses: List[Dict[str, Any]]) -> None:
        """全頭ゴール後に画面中央に表示される確定着順ボード（騎手名・着差・上がり3F・賞金・レコードR対応）"""
        total_h = len(horses)
        if total_h == 0:
            return

        # スケール・サイズ計算
        base_w = 860.0
        board_w = min(base_w, max(460.0, float(w) - 24.0))
        scale = board_w / base_w

        row_h = 28.0 if total_h <= 10 else (24.0 if total_h <= 14 else 21.0)
        title_h = 38.0
        col_hdr_h = 24.0
        board_h = title_h + col_hdr_h + row_h * total_h + 14.0

        board_x = (float(w) - board_w) / 2.0
        board_y = max(10.0, (float(h) - 70.0 - board_h) / 2.0)

        # 半透明ダークパネル
        painter.setPen(QPen(QColor("#38bdf8"), 2))
        painter.setBrush(QBrush(QColor(10, 15, 30, 240)))
        painter.drawRoundedRect(QRectF(board_x, board_y, board_w, board_h), 8, 8)

        # 最上段ヘッダーバー（タイトル）
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(14, 165, 233, 210)))
        painter.drawRoundedRect(QRectF(board_x + 2, board_y + 2, board_w - 4, title_h - 4), 6, 6)

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Hiragino Sans", max(10, int(13 * scale)), QFont.Weight.Bold))
        r_name = str(getattr(self, "race_name", "") or "レース結果")
        painter.drawText(QRectF(board_x, board_y + 4, board_w, title_h - 8), Qt.AlignmentFlag.AlignCenter, f"🏁 確定着順 - {r_name}")

        # 各列の幅定義 (scale連動)
        w_pos = 38.0 * scale
        w_gate = 28.0 * scale
        w_name = 165.0 * scale
        w_jockey = 82.0 * scale
        w_odds = 95.0 * scale
        w_time = 108.0 * scale
        w_margin = 72.0 * scale
        w_last3f = 64.0 * scale
        w_prize = 110.0 * scale

        x_pos = board_x + 12.0 * scale
        x_gate = x_pos + w_pos + 4.0 * scale
        x_name = x_gate + w_gate + 6.0 * scale
        x_jockey = x_name + w_name + 4.0 * scale
        x_odds = x_jockey + w_jockey + 4.0 * scale
        x_time = x_odds + w_odds + 6.0 * scale
        x_margin = x_time + w_time + 4.0 * scale
        x_last3f = x_margin + w_margin + 4.0 * scale
        x_prize = x_last3f + w_last3f + 4.0 * scale

        # カラム見出し行
        col_hdr_y = board_y + title_h + 2.0
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 22)))
        painter.drawRect(QRectF(board_x + 6, col_hdr_y, board_w - 12, col_hdr_h))

        painter.setPen(QColor("#94a3b8"))
        painter.setFont(QFont("Hiragino Sans", max(8, int(9 * scale)), QFont.Weight.Bold))
        painter.drawText(QRectF(x_pos, col_hdr_y, w_pos, col_hdr_h), Qt.AlignmentFlag.AlignCenter, "着順")
        painter.drawText(QRectF(x_gate, col_hdr_y, w_gate, col_hdr_h), Qt.AlignmentFlag.AlignCenter, "馬番")
        painter.drawText(QRectF(x_name + 4, col_hdr_y, w_name - 4, col_hdr_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "馬名")
        painter.drawText(QRectF(x_jockey, col_hdr_y, w_jockey, col_hdr_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "騎手")
        painter.drawText(QRectF(x_odds, col_hdr_y, w_odds, col_hdr_h), Qt.AlignmentFlag.AlignCenter, "人気(オッズ)")
        painter.drawText(QRectF(x_time, col_hdr_y, w_time, col_hdr_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "タイム")
        painter.drawText(QRectF(x_margin, col_hdr_y, w_margin, col_hdr_h), Qt.AlignmentFlag.AlignCenter, "着差")
        painter.drawText(QRectF(x_last3f, col_hdr_y, w_last3f, col_hdr_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "上り3F")
        painter.drawText(QRectF(x_prize - 4, col_hdr_y, w_prize, col_hdr_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "獲得賞金")

        # 各馬の着順行
        cur_y = col_hdr_y + col_hdr_h + 2.0

        # ゴール板通過順（finish_time昇順）で確実にソート
        sorted_horses = sorted(
            horses,
            key=lambda x: (
                0 if x.get("is_finished", False) or float(x.get("distance_covered", 0.0)) >= float(self.distance) - 0.1 else 1,
                float(x.get("finish_time", 999.0)),
                -float(x.get("distance_covered", 0.0))
            )
        )

        # 単勝オッズによる人気順の算出
        odds_list = []
        for h_item in sorted_horses:
            hid = h_item.get("horse_id")
            res_info = self.race_results_info.get(hid, {})
            val = float(res_info.get("odds") or h_item.get("odds", 0.0))
            odds_list.append((val if val > 0 else 999.9, hid))
        sorted_by_odds = sorted(odds_list, key=lambda x: x[0])
        pop_map = {hid: pop for pop, (_, hid) in enumerate(sorted_by_odds, start=1)}

        first_time = float(sorted_horses[0].get("finish_time", 0.0)) if sorted_horses else 0.0

        for rk, h_item in enumerate(sorted_horses):
            hid = h_item.get("horse_id")
            res_info = self.race_results_info.get(hid, {})

            num = min(18, max(1, int(res_info.get("gate_number") or h_item.get("number", rk + 1))))
            bracket = int(h_item.get("bracket", get_jra_bracket(num, total_h)))
            name = str(res_info.get("horse_name") or h_item.get("name", f"馬{num}"))
            jockey_name = str(res_info.get("jockey_name") or h_item.get("jockey_name") or "―")
            odds_val = float(res_info.get("odds") or h_item.get("odds", 0.0))
            f_time = float(res_info.get("finish_time") or h_item.get("finish_time", 0.0))
            pop = pop_map.get(hid, rk + 1)
            margin_str = str(res_info.get("margin") or "")
            last_3f_val = res_info.get("last_3f")
            prize_val = int(res_info.get("prize_awarded") or 0)

            bg_col, fg_col, border_col, _ = JRA_BRACKET_COLORS.get(bracket, ("#fff", "#000", "#999", ""))

            # 行の背景（ストライプ）
            if rk % 2 == 1:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(255, 255, 255, 12)))
                painter.drawRect(QRectF(board_x + 6, cur_y - 1, board_w - 12, row_h))

            # 1. 着順
            painter.setFont(QFont("Arial", max(9, int(10 * scale)), QFont.Weight.Bold))
            painter.setPen(QColor("#fbbf24" if rk == 0 else ("#e2e8f0" if rk < 3 else "#94a3b8")))
            painter.drawText(QRectF(x_pos, cur_y, w_pos, row_h - 2), Qt.AlignmentFlag.AlignCenter, f"{rk + 1}着")

            # 2. ゼッケン馬番
            z_w = min(24.0, w_gate)
            z_rect = QRectF(x_gate + (w_gate - z_w) / 2.0, cur_y + (row_h - 20) / 2.0, z_w, 20)
            painter.setPen(QPen(QColor(border_col), 1.2))
            painter.setBrush(QBrush(QColor(bg_col)))
            painter.drawRoundedRect(z_rect, 3, 3)
            painter.setPen(QColor(fg_col))
            painter.setFont(QFont("Arial", max(8, int(9 * scale)), QFont.Weight.Bold))
            painter.drawText(z_rect, Qt.AlignmentFlag.AlignCenter, str(num))

            # 3. 馬名
            painter.setPen(QColor("#ffffff" if rk == 0 else "#e2e8f0"))
            painter.setFont(QFont("Hiragino Sans", max(8, int(10 * scale)), QFont.Weight.Bold if rk == 0 else QFont.Weight.Medium))
            painter.drawText(QRectF(x_name + 4, cur_y, w_name - 6, row_h - 2), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)

            # 4. 騎手名
            painter.setPen(QColor("#cbd5e1"))
            painter.setFont(QFont("Hiragino Sans", max(8, int(9 * scale))))
            painter.drawText(QRectF(x_jockey, cur_y, w_jockey, row_h - 2), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, jockey_name)

            # 5. 人気(オッズ)
            if odds_val > 0:
                painter.setPen(QColor("#fbbf24"))
                painter.setFont(QFont("Arial", max(8, int(9 * scale))))
                pop_str = f"{pop}人 ({odds_val:.1f})"
            else:
                painter.setPen(QColor("#64748b"))
                painter.setFont(QFont("Arial", max(8, int(8 * scale))))
                pop_str = "―"
            painter.drawText(QRectF(x_odds, cur_y, w_odds, row_h - 2), Qt.AlignmentFlag.AlignCenter, pop_str)

            # 6. 走破タイム (レコード時はタイム左側に赤字「R」)
            time_rect = QRectF(x_time, cur_y, w_time, row_h - 2)
            if f_time > 0:
                mins = int(f_time // 60)
                secs = f_time - (mins * 60)
                t_str = f"{mins}:{secs:04.1f}" if mins > 0 else f"{secs:.1f}"
            else:
                t_str = "--:--.-"

            if rk == 0 and self.is_record_time:
                # レコードタイム: 左側に赤字「R」、右側にタイム
                painter.setFont(QFont("Arial", max(9, int(10 * scale)), QFont.Weight.Bold))
                painter.setPen(QColor("#ef4444"))
                painter.drawText(QRectF(x_time, cur_y, 18 * scale, row_h - 2), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "R")

                painter.setPen(QColor("#38bdf8"))
                painter.drawText(QRectF(x_time + 18 * scale, cur_y, w_time - 18 * scale, row_h - 2), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, t_str)
            else:
                painter.setFont(QFont("Arial", max(8, int(9 * scale)), QFont.Weight.Bold if rk == 0 else QFont.Weight.Normal))
                painter.setPen(QColor("#38bdf8" if rk == 0 else "#e2e8f0"))
                painter.drawText(time_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, t_str)

            # 7. 着差
            if rk == 0:
                display_margin = "―"
            elif margin_str:
                display_margin = margin_str
            elif f_time > 0 and first_time > 0:
                diff = max(0.0, f_time - first_time)
                display_margin = f"+{diff:.1f}s"
            else:
                display_margin = "―"

            painter.setFont(QFont("Hiragino Sans", max(8, int(9 * scale)), QFont.Weight.Bold if display_margin != "―" else QFont.Weight.Normal))
            painter.setPen(QColor("#fbbf24" if display_margin != "―" else "#64748b"))
            painter.drawText(QRectF(x_margin, cur_y, w_margin, row_h - 2), Qt.AlignmentFlag.AlignCenter, display_margin)

            # 8. 上り3Fタイム
            if last_3f_val is not None and float(last_3f_val) > 0:
                f3_str = f"{float(last_3f_val):.1f}"
                painter.setPen(QColor("#38bdf8"))
            else:
                f3_str = "―"
                painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Arial", max(8, int(9 * scale))))
            painter.drawText(QRectF(x_last3f, cur_y, w_last3f, row_h - 2), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, f3_str)

            # 9. 獲得賞金
            if prize_val > 0:
                man = prize_val // 10000
                if man >= 10000:
                    oku = man // 10000
                    rem = man % 10000
                    prize_str = f"{oku}億{rem:,}万" if rem > 0 else f"{oku}億円"
                else:
                    prize_str = f"{man:,}万円"
                painter.setPen(QColor("#fde047"))
            else:
                prize_str = "0円"
                painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Hiragino Sans", max(8, int(9 * scale))))
            painter.drawText(QRectF(x_prize - 4, cur_y, w_prize, row_h - 2), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, prize_str)

            cur_y += row_h


