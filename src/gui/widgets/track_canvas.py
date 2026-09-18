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

from src.race.engine import get_jra_bracket
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
        self.playback_speed: float = 2.0

        # 大スケール・ワールド定義パラメータ
        self.world_straight = 1800.0            # 直線部長さ (px)
        self.world_r = 500.0                    # コーナー半径 (px)
        self.world_track_width = 195.0          # コース幅 (px) 従来の130.0から1.5倍に拡大！
        self.world_perimeter = 2.0 * self.world_straight + 2.0 * math.pi * self.world_r
        self.race_name: str = ""
        self.race_grade: str = ""

        # 順位バーの180度視点回転（3Dフリップ）アニメーション状態
        self.indicator_flip_factor: float = 1.0  # +1.0 (右向き) 〜 -1.0 (左向き)
        self.indicator_target_is_right: bool = True

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

                        is_finished = dist >= float(self.distance) - 0.1

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
        # 2. JRAテレビ中継風 リアルタイムHUD (スクリーン座標系)
        # ---------------------------------------------------------------------
        self._draw_jra_broadcast_hud(painter, w, h, horses)

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
        # 毛色カラーパレット (馬番に応じて美しいサラブレッド毛色を割り当て)
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
            body_col_hex, mane_col_hex = coat_colors[(num - 1) % len(coat_colors)]

            # -------------------------------------------------------------
            # 1. ワールド座標系: 全力スパート時の発光ブーストオーラ
            # -------------------------------------------------------------
            if is_spurt:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(245, 158, 11, 45)))
                painter.drawEllipse(QPointF(px, py), 28, 28)
                painter.setPen(QPen(QColor(251, 191, 36, 180), 2.0))
                painter.setBrush(QBrush(QColor(251, 191, 36, 60)))
                painter.drawEllipse(QPointF(px, py), 21, 21)

            # -------------------------------------------------------------
            # 2. ローカル座標系: 走る競走馬（進行方向 heading に回転）
            # -------------------------------------------------------------
            painter.save()
            painter.translate(px, py)
            painter.rotate(math.degrees(heading))  # +X 軸が進行方向

            # ギャロップ（襲歩）の歩法アニメーション計算
            # 走破距離に応じた動的な四肢の伸縮
            anim_phase = (pos_m * 1.7) % (2.0 * math.pi)
            stride_f = math.sin(anim_phase)          # 前脚の振幅 (-1.0〜+1.0)
            stride_b = -math.sin(anim_phase)         # 後脚の振幅 (-1.0〜+1.0)

            # A. 地面の立体楕円シャドウ (進行方向・脚の伸びに応じた影)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 110)))
            painter.drawEllipse(QRectF(-18.0, -9.0, 36.0, 18.0))

            # B. 四肢（4本の脚のダイナミックなギャロップスイング）
            painter.setPen(QPen(QColor(body_col_hex), 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            # 奥の前脚 & 後脚 (やや暗め)
            painter.setPen(QPen(QColor(body_col_hex).darker(130), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(7.0, -5.0), QPointF(11.0 - stride_f * 7.0, -11.0))
            painter.drawLine(QPointF(-8.0, -5.0), QPointF(-13.0 + stride_b * 8.0, -11.0))

            # 手前の前脚 & 後脚 (手前に力強く伸びる)
            painter.setPen(QPen(QColor(body_col_hex), 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(8.0, 5.0), QPointF(13.0 + stride_f * 8.5, 11.5))
            painter.drawLine(QPointF(-9.0, 5.0), QPointF(-15.0 - stride_b * 9.5, 11.5))

            # 黒い蹄（ひづめ）
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#0f172a")))
            painter.drawEllipse(QPointF(13.0 + stride_f * 8.5, 11.5), 1.8, 1.8)
            painter.drawEllipse(QPointF(-15.0 - stride_b * 9.5, 11.5), 1.8, 1.8)

            # C. なびく尾毛（テール: スピード感のある流線型）
            tail_path = QPainterPath()
            tail_path.moveTo(-11.0, 0.0)
            tail_path.quadTo(-18.0, -2.0, -25.0, stride_f * 2.5)
            tail_path.quadTo(-19.0, 2.0, -11.0, 1.0)
            tail_path.closeSubpath()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(mane_col_hex)))
            painter.drawPath(tail_path)

            # D. 馬体胴体（トルソー: 美しいサラブレッドの筋肉美）
            painter.setPen(QPen(QColor(mane_col_hex), 1.2))
            painter.setBrush(QBrush(QColor(body_col_hex)))
            painter.drawRoundedRect(QRectF(-12.0, -7.0, 24.0, 14.0), 7.0, 7.0)

            # E. 首と頭部・耳・たてがみ
            # 首から頭部への伸びやかなライン
            neck_head = QPainterPath()
            neck_head.moveTo(7.0, -4.5)
            neck_head.lineTo(19.0, -3.5)   # 頭部先端
            neck_head.lineTo(21.5, -1.0)   # 鼻口部
            neck_head.lineTo(19.0, 2.5)
            neck_head.lineTo(7.0, 4.5)
            neck_head.closeSubpath()
            painter.setPen(QPen(QColor(mane_col_hex), 1.0))
            painter.setBrush(QBrush(QColor(body_col_hex)))
            painter.drawPath(neck_head)

            # ピンと立った耳
            painter.setBrush(QBrush(QColor(body_col_hex).darker(115)))
            painter.drawEllipse(QPointF(16.5, -4.5), 2.2, 1.2)

            # たてがみ
            painter.setPen(QPen(QColor(mane_col_hex), 2.0))
            painter.drawLine(QPointF(8.0, -2.0), QPointF(15.0, -2.0))

            # F. 前傾姿勢で疾走する騎手（ジョッキー: モンキー乗りスタイル）
            # 勝負服（トルソー）
            painter.setPen(QPen(QColor("#0f172a"), 0.8))
            painter.setBrush(QBrush(QColor(border_col).darker(110)))
            painter.drawRoundedRect(QRectF(-4.0, -4.5, 8.0, 9.0), 3.0, 3.0)

            # 騎手ヘルメット (枠色)
            painter.setPen(QPen(QColor("#ffffff"), 0.8))
            painter.setBrush(QBrush(QColor(bg_col)))
            painter.drawEllipse(QPointF(4.5, 0.0), 3.5, 3.5)

            # 手綱ライン (騎手から頭部へ)
            painter.setPen(QPen(QColor("#ffffff"), 0.9))
            painter.drawLine(QPointF(3.0, -2.0), QPointF(15.0, -1.0))
            painter.drawLine(QPointF(3.0, 2.0), QPointF(15.0, 1.0))

            # G. JRA枠色ゼッケン & 馬番（馬体背中にクリア表示）
            saddle_rect = QRectF(-7.0, -6.5, 14.0, 13.0)
            painter.setPen(QPen(QColor(border_col), 1.5))
            painter.setBrush(QBrush(QColor(bg_col)))
            painter.drawRoundedRect(saddle_rect, 2.5, 2.5)

            painter.setPen(QColor(fg_col))
            painter.setFont(QFont("Arial", 8, QFont.Weight.Black))
            painter.drawText(saddle_rect, Qt.AlignmentFlag.AlignCenter, str(num))

            painter.restore()

            # -------------------------------------------------------------
            # 3. ワールド座標系: 上位馬の馬名プレート（ユーザー要望により非表示化）
            # -------------------------------------------------------------
            # コース上の馬体がすっきりと見え、馬群を遮らないように馬名タグは非表示化
            # （画面右下の中継HUDテロップには引き続き馬名・オッズ・差を表示）

            # -------------------------------------------------------------
            # 4. ワールド座標系: 先頭馬の強調インジケーター「▼」
            # -------------------------------------------------------------
            if rank == 0:
                painter.setPen(QPen(QColor("#b45309"), 1.2))
                painter.setBrush(QBrush(QColor("#fbbf24")))
                tri = QPainterPath()
                tri.moveTo(px, py - 20.0)
                tri.lineTo(px - 7.5, py - 32.0)
                tri.lineTo(px + 7.5, py - 32.0)
                tri.closeSubpath()
                painter.drawPath(tri)

    # =========================================================================
    # スクリーンHUD: JRA公式テレビ中継風 リアルタイム中継HUD
    # =========================================================================
    def _draw_jra_broadcast_hud(self, painter: QPainter, w: int, h: int, horses: List[Dict[str, Any]]) -> None:
        """添付スクリーンショット準拠のJRA公式テレビ中継風リアルタイムHUDを描画"""
        track = get_track_info(self.track_id)
        surf_jp = "TURF" if self.surface == "turf" else "DIRT"
        cur_sec = self.current_frame_idx * 0.1
        time_str = f"{int(cur_sec // 60):02d}:{cur_sec % 60:04.1f}"

        leader = horses[0] if horses else None
        leader_dist = float(leader.get("distance_covered", 0.0)) if leader else 0.0
        rem_dist = max(0.0, float(self.distance) - leader_dist)

        # ---------------------------------------------------------------------
        # 1. 画面左上: タイム & 残りハロン表示 (JRA公式スタイル)
        # ---------------------------------------------------------------------
        tl_x, tl_y = 24.0, 24.0
        tl_w, tl_h = 170.0, 56.0

        # 半透明ダークプレート
        painter.setPen(QPen(QColor("#38bdf8"), 1))
        painter.setBrush(QBrush(QColor(10, 15, 29, 230)))
        painter.drawRoundedRect(QRectF(tl_x, tl_y, tl_w, tl_h), 6, 6)

        # 残りハロン数アイコン（スクショの大文字テロップ）
        furlongs_rem = max(1, int(math.ceil(rem_dist / 200.0))) if rem_dist > 0 else 0
        furlong_str = f"{furlongs_rem}F" if rem_dist > 0 else "GOAL"

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#0284c7") if rem_dist > 0 else QColor("#10b981")))
        painter.drawRoundedRect(QRectF(tl_x + 6, tl_y + 6, 52, 44), 4, 4)

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        painter.drawText(QRectF(tl_x + 6, tl_y + 6, 52, 44), Qt.AlignmentFlag.AlignCenter, furlong_str)

        # TIME ラベル & タイム数字
        painter.setPen(QColor("#94a3b8"))
        painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        painter.drawText(int(tl_x + 66), int(tl_y + 22), "TIME")

        painter.setPen(QColor("#f8fafc"))
        painter.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        painter.drawText(int(tl_x + 66), int(tl_y + 45), time_str)

        # ---------------------------------------------------------------------
        # 2. 画面下部メインHUDバー (高さ 110px)
        # ---------------------------------------------------------------------
        hud_h = 110.0
        hud_y = h - hud_h
        hud_w = float(w)

        # メイン背景パネル
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(8, 12, 22, 240)))
        painter.drawRect(QRectF(0, hud_y, hud_w, hud_h))

        # 上部境界アクセントライン (ゴールド〜シアンのグラデーション風)
        painter.setPen(QPen(QColor("#38bdf8"), 2))
        painter.drawLine(QPointF(0, hud_y), QPointF(hud_w, hud_y))

        # -------------------------------------------------------------
        # 2-A. 左セクション: レース名/グレード・コース種別・勾配・時速 (幅 210px)
        # -------------------------------------------------------------
        sec_left_w = 210.0

        # 一番上: レース名 & グレード表示
        g_raw = str(getattr(self, "race_grade", "") or "").upper()
        g_text = g_raw if ("G1" in g_raw or "G2" in g_raw or "G3" in g_raw) else ("G1" if "G1" in getattr(self, "race_name", "") else "")
        g_bg = "#dc2626" if "G1" in g_text else ("#2563eb" if "G2" in g_text else ("#16a34a" if "G3" in g_text else "#0284c7"))

        cur_x = 14.0
        if g_text:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(g_bg)))
            painter.drawRoundedRect(QRectF(cur_x, hud_y + 8, 28, 16), 3, 3)
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Arial", 8, QFont.Weight.Black))
            painter.drawText(QRectF(cur_x, hud_y + 8, 28, 16), Qt.AlignmentFlag.AlignCenter, g_text)
            cur_x += 33.0

        r_name = str(getattr(self, "race_name", "") or f"{track.name} 特別")
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Hiragino Sans", 10, QFont.Weight.Bold))
        painter.drawText(int(cur_x), int(hud_y + 21), r_name[:10])

        # コース種別 & 距離 (行2)
        painter.setPen(QColor("#fbbf24"))
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        painter.drawText(int(14), int(hud_y + 42), f"{surf_jp} {self.distance:,}m")

        painter.setPen(QColor("#94a3b8"))
        painter.setFont(QFont("Hiragino Sans", 8))
        chute_info = track.chutes.get(self.distance, "")
        chute_label = f" ({chute_info[:8]})" if chute_info else ""
        painter.drawText(int(115), int(hud_y + 42), f"{track.name}・{'右' if self.turn == 'right' else '左'}{chute_label}")

        # 時速 (km/h) のリアルタイム計算
        speed_kmh = 0.0
        if leader and self.current_frame_idx > 0 and self.current_frame_idx < len(self.replay_frames):
            prev_horses = self.replay_frames[self.current_frame_idx - 1].get("horses", [])
            if prev_horses:
                prev_dist = float(prev_horses[0].get("distance_covered", 0.0))
                step_dist = max(0.0, leader_dist - prev_dist)
                speed_kmh = (step_dist / 0.1) * 3.6
        if speed_kmh < 1.0 and leader_dist > 5.0:
            speed_kmh = 58.0  # 安定表示用

        # 勾配 (中山等の坂を模した表示)
        slope_pct = 2.0 if (self.distance - leader_dist < 400 and self.distance - leader_dist > 150) else (0.0 if rem_dist <= 150 else 0.5)

        # 勾配 & 時速ボックス (行3)
        painter.setPen(QColor("#38bdf8"))
        painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        painter.drawText(int(14), int(hud_y + 66), f"◿ {slope_pct:+.1f}%")

        painter.setPen(QColor("#f8fafc"))
        painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        painter.drawText(int(78), int(hud_y + 66), f"◷ {speed_kmh:.1f} km/h")

        # 残り距離バー (行4)
        prog = min(1.0, leader_dist / max(1.0, float(self.distance)))
        bar_rect = QRectF(14, hud_y + 78, 180, 7)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(30, 41, 59)))
        painter.drawRoundedRect(bar_rect, 3.5, 3.5)
        if prog > 0:
            fill_rect = QRectF(14, hud_y + 78, 180 * prog, 7)
            painter.setBrush(QBrush(QColor("#10b981" if rem_dist == 0 else "#38bdf8")))
            painter.drawRoundedRect(fill_rect, 3.5, 3.5)

        # 境界線 1 (左セクションとミニマップの間)
        painter.setPen(QPen(QColor(51, 65, 85, 180), 1))
        painter.drawLine(QPointF(sec_left_w, hud_y + 8), QPointF(sec_left_w, hud_y + hud_h - 8))

        # -------------------------------------------------------------
        # 2-B. コース全体図（ミニマップ・レーダー）セクション (幅 175px)
        # -------------------------------------------------------------
        sec_map_w = 175.0
        sec_map_x = sec_left_w + 8.0
        map_rect = QRectF(sec_map_x, hud_y + 8, sec_map_w, hud_h - 16)

        painter.save()
        # 背景パネル
        painter.setPen(QPen(QColor(30, 41, 59), 1))
        painter.setBrush(QBrush(QColor(10, 16, 28, 220)))
        painter.drawRoundedRect(map_rect, 4, 4)

        # ヘッダーラベル
        painter.setFont(QFont("Arial", 7, QFont.Weight.Bold))
        painter.setPen(QColor("#38bdf8"))
        painter.drawText(QRectF(sec_map_x + 6, hud_y + 11, 80, 12), Qt.AlignmentFlag.AlignLeft, "COURSE MAP")

        # 縮小トラックの描画
        sl_m = self.world_straight
        r_m = self.world_r
        tw_m = self.world_track_width
        
        usable_map_w = sec_map_w - 16.0
        usable_map_h = hud_h - 38.0
        
        total_world_w = sl_m + 2.0 * r_m + tw_m + 60.0
        total_world_h = 2.0 * r_m + tw_m + 60.0
        scale_m = min(usable_map_w / total_world_w, usable_map_h / total_world_h)
        
        map_cx = sec_map_x + sec_map_w / 2.0
        map_cy = hud_y + 13.0 + usable_map_h / 2.0 + 6.0
        
        m_sl = sl_m * scale_m
        m_r = r_m * scale_m
        m_tw = max(4.0, tw_m * scale_m)

        # トラックコース帯
        mini_mid_rect = QRectF(map_cx - m_sl / 2.0 - m_r, map_cy - m_r, m_sl + 2 * m_r, 2 * m_r)
        surf_color_m = QColor("#047857") if self.surface == "turf" else QColor("#92400e")
        painter.setPen(QPen(surf_color_m, m_tw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(mini_mid_rect, m_r, m_r)
        
        # 内外柵
        painter.setPen(QPen(QColor("#334155"), 0.8))
        painter.drawRoundedRect(mini_mid_rect.adjusted(-m_tw/2, -m_tw/2, m_tw/2, m_tw/2), m_r + m_tw/2, m_r + m_tw/2)
        painter.drawRoundedRect(mini_mid_rect.adjusted(m_tw/2, m_tw/2, -m_tw/2, -m_tw/2), max(1.0, m_r - m_tw/2), max(1.0, m_r - m_tw/2))

        # ゴール位置標識
        gw_x, gw_y, _ = self._calc_horse_pos_world(self.distance, 15.0)
        gm_x = map_cx + gw_x * scale_m
        gm_y = map_cy + gw_y * scale_m
        painter.setPen(QPen(QColor("#ef4444"), 2.0))
        painter.drawLine(QPointF(gm_x, gm_y - 4), QPointF(gm_x, gm_y + 4))
        painter.setPen(QColor("#f87171"))
        painter.setFont(QFont("Arial", 6, QFont.Weight.Bold))
        painter.drawText(int(gm_x - 3), int(gm_y - 5), "G")

        # スタート位置標識
        sw_x, sw_y, _ = self._calc_horse_pos_world(0.0, 15.0)
        sm_x = map_cx + sw_x * scale_m
        sm_y = map_cy + sw_y * scale_m
        painter.setPen(QColor("#fbbf24"))
        painter.setFont(QFont("Arial", 6, QFont.Weight.Bold))
        painter.drawText(int(sm_x - 3), int(sm_y - 5), "S")

        # 各馬の現在地ドット（後方馬から描画し、先頭馬を一番上に描画）
        if horses:
            rev_horses = list(reversed(horses))
            for h_item in rev_horses:
                d_val = float(h_item.get("distance_covered", 0.0))
                l_val = float(h_item.get("lateral", 1.0))
                hw_x, hw_y, _ = self._calc_horse_pos_world(d_val, l_val)
                hm_x = map_cx + hw_x * scale_m
                hm_y = map_cy + hw_y * scale_m
                
                num = min(18, max(1, int(h_item.get("number", 1))))
                bracket = int(h_item.get("bracket", get_jra_bracket(num, len(horses))))
                bg_col, _, _, _ = JRA_BRACKET_COLORS.get(bracket, ("#ffffff", "#000000", "#999999", ""))
                
                is_cur_leader = (h_item.get("horse_id") == leader.get("horse_id")) if leader else False
                if is_cur_leader:
                    painter.setPen(QPen(QColor("#38bdf8"), 1.2))
                    painter.setBrush(QBrush(QColor(bg_col)))
                    painter.drawEllipse(QPointF(hm_x, hm_y), 3.2, 3.2)
                else:
                    painter.setPen(QPen(QColor(0, 0, 0, 150), 0.5))
                    painter.setBrush(QBrush(QColor(bg_col)))
                    painter.drawEllipse(QPointF(hm_x, hm_y), 2.2, 2.2)

        painter.restore()

        # 境界線 2 (ミニマップと中央セクションの間)
        painter.setPen(QPen(QColor(51, 65, 85, 180), 1))
        painter.drawLine(QPointF(sec_map_x + sec_map_w + 8.0, hud_y + 8), QPointF(sec_map_x + sec_map_w + 8.0, hud_y + hud_h - 8))

        # -------------------------------------------------------------
        # 2-C. 中央セクション: リアルタイム隊列インジケーター (可変幅センタリング & 180度視点回転フリップ)
        # -------------------------------------------------------------
        sec_right_w = 380.0
        avail_mid_start = sec_map_x + sec_map_w + 16.0
        avail_mid_w = max(180.0, (hud_w - sec_right_w - 16.0) - avail_mid_start)
        sec_mid_w = min(400.0, avail_mid_w)
        sec_mid_x = avail_mid_start + (avail_mid_w - sec_mid_w) / 2.0

        # 先頭馬の現在のワールド進行方向（進行ベクトル x 方向）を取得
        is_moving_right = True
        if leader:
            _, _, leader_heading = self._calc_horse_pos_world(leader_dist, float(leader.get("lateral", 1.0)))
            is_moving_right = math.cos(leader_heading) >= 0.0

        # 180度視点回転フリップアニメーションの進行度更新
        target_factor = 1.0 if is_moving_right else -1.0
        diff = target_factor - self.indicator_flip_factor
        if abs(diff) > 0.01:
            step = 0.15 if diff > 0 else -0.15
            if abs(diff) < abs(step):
                self.indicator_flip_factor = target_factor
            else:
                self.indicator_flip_factor += step
        else:
            self.indicator_flip_factor = target_factor

        # 表示上の向き (正なら右向き、負なら左向き) および 水平スケール (1.0 -> 0.0 -> 1.0)
        display_is_right = (self.indicator_flip_factor >= 0.0)
        flip_scale = max(0.04, abs(self.indicator_flip_factor))

        # 3Dフリップ変形（中央軸でクルッと180度回転）
        center_x = sec_mid_x + sec_mid_w / 2.0
        painter.save()
        painter.translate(center_x, 0)
        painter.scale(flip_scale, 1.0)
        painter.translate(-center_x, 0)

        # 隊列トラック背景領域
        field_rect = QRectF(sec_mid_x, hud_y + 10, sec_mid_w, hud_h - 20)
        painter.setPen(QPen(QColor(30, 41, 59), 1))
        painter.setBrush(QBrush(QColor(12, 18, 32, 200)))
        painter.drawRoundedRect(field_rect, 4, 4)

        # 内ラチ（上）・外ラチ（下）ライン表示
        painter.setPen(QPen(QColor("#10b981"), 1.5))  # 最内グリーンライン
        painter.drawLine(QPointF(sec_mid_x + 4, field_rect.top() + 10), QPointF(sec_mid_x + sec_mid_w - 4, field_rect.top() + 10))
        painter.setPen(QPen(QColor("#64748b"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(sec_mid_x + 4, field_rect.bottom() - 10), QPointF(sec_mid_x + sec_mid_w - 4, field_rect.bottom() - 10))

        # ラベル
        painter.setFont(QFont("Hiragino Sans", 7, QFont.Weight.Bold))
        painter.setPen(QColor("#34d399"))
        painter.drawText(int(sec_mid_x + 8), int(field_rect.top() + 8), "内 (IN)")
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(int(sec_mid_x + 8), int(field_rect.bottom() - 2), "外 (OUT)")

        # 馬群全体の最大遅れ距離（m）を動的に算出し、全馬が確実にバー内に収まるオートスケールを適用
        max_behind = 0.0
        if horses and leader:
            for h_item in horses:
                d = float(h_item.get("distance_covered", 0.0))
                diff = max(0.0, leader_dist - d)
                if diff > max_behind:
                    max_behind = diff

        # 最低70m、馬群の広がり（最後方+12m）に応じて動的にスケール調整（馬が消えるのを完全に防止）
        view_dist_span = max(70.0, max_behind + 12.0)

        # 有効描画範囲（矢印バッジ用のマージン 34px を確保）
        arrow_pad = 34.0
        left_bound = sec_mid_x + arrow_pad
        right_bound = sec_mid_x + sec_mid_w - arrow_pad
        usable_w = right_bound - left_bound

        if display_is_right:
            # 右向き走行（先頭馬が右端、後続馬が左側へ展開）
            leader_screen_x = right_bound
            arrow_cx = right_bound + 16.0
        else:
            # 左向き走行（先頭馬が左端、後続馬が右側へ展開）
            leader_screen_x = left_bound
            arrow_cx = left_bound - 16.0

        # 先頭の進行方向を示す矢印バッジ (▶ / ◀) の描画
        arrow_cy = (field_rect.top() + field_rect.bottom()) / 2.0
        arrow_path = QPainterPath()
        if display_is_right:
            arrow_path.moveTo(arrow_cx + 8.0, arrow_cy)
            arrow_path.lineTo(arrow_cx - 6.0, arrow_cy - 8.0)
            arrow_path.lineTo(arrow_cx - 6.0, arrow_cy + 8.0)
            arrow_path.closeSubpath()
        else:
            arrow_path.moveTo(arrow_cx - 8.0, arrow_cy)
            arrow_path.lineTo(arrow_cx + 6.0, arrow_cy - 8.0)
            arrow_path.lineTo(arrow_cx + 6.0, arrow_cy + 8.0)
            arrow_path.closeSubpath()

        # スタイリッシュな発光矢印
        painter.setPen(QPen(QColor("#38bdf8"), 2.0))
        painter.setBrush(QBrush(QColor("#0284c7")))
        painter.drawPath(arrow_path)

        # 距離目盛 & 順位バー上のリアルハロン棒標識（添付画像スタイル）
        # 1. 順位バー上のハロン棒標識（白丸看板＋赤文字数字＋赤白ストライプピン）
        max_furlong = int(self.distance // 200)
        for k in range(1, max_furlong + 1):
            f_dist = self.distance - 200 * k
            # 先頭馬からの相対遅れ (m)
            behind_f = leader_dist - f_dist
            if -8.0 <= behind_f <= view_dist_span + 8.0:
                f_ratio = behind_f / view_dist_span
                if display_is_right:
                    fx = leader_screen_x - f_ratio * usable_w
                else:
                    fx = leader_screen_x + f_ratio * usable_w

                if left_bound - 10 <= fx <= right_bound + 10:
                    # ハロン棒ポールピン（赤白交互）
                    painter.setPen(QPen(QColor("#dc2626"), 2.2))
                    painter.drawLine(QPointF(fx, field_rect.top() + 6), QPointF(fx, field_rect.bottom() - 6))
                    painter.setPen(QPen(QColor("#ffffff"), 1.8, Qt.PenStyle.DashLine))
                    painter.drawLine(QPointF(fx, field_rect.top() + 6), QPointF(fx, field_rect.bottom() - 6))

                    # ポール上部の白丸看板（拡大: 直径 19px）
                    f_badge_cy = field_rect.top() + 8.0
                    painter.setPen(QPen(QColor("#334155"), 1.5))
                    painter.setBrush(QBrush(QColor("#ffffff")))
                    painter.drawEllipse(QPointF(fx, f_badge_cy), 9.5, 9.5)

                    painter.setPen(QColor("#dc2626"))
                    painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
                    painter.drawText(
                        QRectF(fx - 9.5, f_badge_cy - 9.5, 19.0, 19.0),
                        Qt.AlignmentFlag.AlignCenter,
                        str(k),
                    )

        # 2. 補助距離目盛（-20m, -40m, ...）
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1, Qt.PenStyle.DotLine))
        step_m = 20.0 if view_dist_span <= 100.0 else 30.0
        cur_mark = step_m
        while cur_mark < view_dist_span - 5.0:
            if display_is_right:
                mx = leader_screen_x - (cur_mark / view_dist_span) * usable_w
            else:
                mx = leader_screen_x + (cur_mark / view_dist_span) * usable_w

            if left_bound - 10 <= mx <= right_bound + 10:
                painter.drawLine(QPointF(mx, field_rect.top() + 15), QPointF(mx, field_rect.bottom() - 15))
                painter.setFont(QFont("Arial", 7))
                painter.setPen(QColor(255, 255, 255, 70))
                painter.drawText(int(mx - 10), int(field_rect.bottom() - 2), f"-{int(cur_mark)}m")
                painter.setPen(QPen(QColor(255, 255, 255, 40), 1, Qt.PenStyle.DotLine))
            cur_mark += step_m

        # 各馬の隊列アイコンをプロット
        # 横軸: 進行方向に応じた配置（全馬が left_bound〜right_bound に確実に収まる）
        # 縦軸: lateral (1.0m = 最内上側, 19.0m = 外側下側)
        track_y_min = field_rect.top() + 16.0
        track_y_max = field_rect.bottom() - 16.0

        for rk in range(len(horses) - 1, -1, -1):
            h_data = horses[rk]
            d_covered = float(h_data.get("distance_covered", 0.0))
            lat_m = float(h_data.get("lateral", 1.0))
            num = min(18, max(1, int(h_data.get("number", rk + 1))))
            bracket = int(h_data.get("bracket", get_jra_bracket(num, len(horses))))

            # 先頭からの遅れ (m)
            behind_m = max(0.0, leader_dist - d_covered)
            ratio = min(1.0, behind_m / view_dist_span)

            if display_is_right:
                hx = leader_screen_x - ratio * usable_w
            else:
                hx = leader_screen_x + ratio * usable_w
            hx = max(left_bound, min(right_bound, hx))

            # 横位置 (1.5m〜28.0m を track_y_min〜track_y_max にマッピング)
            lat_ratio = max(0.0, min(1.0, (lat_m - 1.5) / 26.5))
            hy = track_y_min + lat_ratio * (track_y_max - track_y_min)

            bg_col, fg_col, border_col, _ = JRA_BRACKET_COLORS.get(bracket, ("#fff", "#000", "#999", ""))
            
            # 拡大された馬番丸アイコン（半径 13.0、直径 26px）
            c_rad = 13.0
            painter.setPen(QPen(QColor(border_col), 2.2))
            painter.setBrush(QBrush(QColor(bg_col)))
            painter.drawEllipse(QPointF(hx, hy), c_rad, c_rad)

            # 拡大された馬番数字（クリアな太字で視認性抜群）
            painter.setPen(QColor(fg_col))
            painter.setFont(QFont("Arial", 11 if num < 10 else 9, QFont.Weight.Bold))
            painter.drawText(QRectF(hx - c_rad, hy - c_rad, c_rad * 2, c_rad * 2), Qt.AlignmentFlag.AlignCenter, str(num))

        painter.restore()

        # 境界線 2
        painter.setPen(QPen(QColor(51, 65, 85, 180), 1))
        painter.drawLine(QPointF(hud_w - sec_right_w, hud_y + 8), QPointF(hud_w - sec_right_w, hud_y + hud_h - 8))

        # -------------------------------------------------------------
        # 2-C. 右セクション: 上位馬テロップ & JRAロゴ・レース名 (幅 460px)
        # -------------------------------------------------------------
        sec_right_w = 460.0
        sec_r_x = hud_w - sec_right_w + 14.0

        # JRAロゴバッジ & レース名ヘッダー
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#0284c7")))
        painter.drawRoundedRect(QRectF(sec_r_x, hud_y + 9, 36, 17), 3, 3)
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(sec_r_x, hud_y + 9, 36, 17), Qt.AlignmentFlag.AlignCenter, "JRA")

        painter.setPen(QColor("#f8fafc"))
        painter.setFont(QFont("Hiragino Sans", 11, QFont.Weight.Bold))
        r_name = str(self.race_name) if hasattr(self, "race_name") and self.race_name else f"{track.name} 特別"
        painter.drawText(int(sec_r_x + 44), int(hud_y + 23), r_name)

        # 上位3頭のミニリール表示
        top3 = horses[:3]
        row_y = hud_y + 35.0
        for rk, h_item in enumerate(top3):
            num = min(18, max(1, int(h_item.get("number", rk + 1))))
            bracket = int(h_item.get("bracket", get_jra_bracket(num, len(horses))))
            name = str(h_item.get("name", f"馬{num}"))
            odds_val = float(h_item.get("odds", 0.0))
            bg_col, fg_col, border_col, _ = JRA_BRACKET_COLORS.get(bracket, ("#fff", "#000", "#999", ""))

            # 順位 (1, 2, 3) 拡大
            painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            painter.setPen(QColor("#fbbf24" if rk == 0 else "#94a3b8"))
            painter.drawText(int(sec_r_x), int(row_y + 15), f"{rk + 1}")

            # ゼッケンバッジ (拡大: 20x20px)
            b_rect = QRectF(sec_r_x + 18, row_y - 1, 20, 20)
            painter.setPen(QPen(QColor(border_col), 1.2))
            painter.setBrush(QBrush(QColor(bg_col)))
            painter.drawRoundedRect(b_rect, 2.5, 2.5)
            painter.setPen(QColor(fg_col))
            painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            painter.drawText(b_rect, Qt.AlignmentFlag.AlignCenter, str(num))

            # 馬名 (230pxの余裕ある幅で長い馬名も最後まで表示)
            painter.setPen(QColor("#f8fafc" if rk == 0 else "#e2e8f0"))
            painter.setFont(QFont("Hiragino Sans", 10, QFont.Weight.Bold))
            painter.drawText(QRectF(sec_r_x + 46, row_y - 1, 230, 22), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)

            # 単勝オッズ (拡大: 10pt Bold ゴールド・右側に独立配置)
            if odds_val > 0:
                painter.setPen(QColor("#fbbf24"))
                painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                painter.drawText(QRectF(sec_r_x + 280, row_y - 1, 72, 22), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, f"{odds_val:.1f}倍")

            # タイム差 / 先頭からの距離 (拡大: 9.5pt)
            if rk > 0 and leader:
                diff_m = max(0.0, leader_dist - float(h_item.get("distance_covered", 0.0)))
                painter.setPen(QColor("#94a3b8"))
                painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
                painter.drawText(QRectF(sec_r_x + 356, row_y - 1, 80, 22), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, f"-{diff_m:.1f}m")
            elif rk == 0:
                painter.setPen(QColor("#38bdf8"))
                painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                painter.drawText(QRectF(sec_r_x + 356, row_y - 1, 80, 22), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "先頭")

            row_y += 23.0

        # -------------------------------------------------------------
        # 3. ゴール後の全頭着順オーバーレイ表示 (全頭ゴール後または最終フレーム時)
        # -------------------------------------------------------------
        total_horses = len(horses)
        all_finished = (total_horses > 0 and all(float(h_item.get("distance_covered", 0.0)) >= (float(self.distance) - 1.0) for h_item in horses))
        if all_finished or (self.total_frames > 0 and self.current_frame_idx >= self.total_frames - 1):
            try:
                self._draw_all_horses_result_overlay(painter, w, h, horses)
            except Exception as e:
                import traceback
                print(f"[ERROR in _draw_all_horses_result_overlay]: {e}\n{traceback.format_exc()}")

    def _draw_all_horses_result_overlay(self, painter: QPainter, w: int, h: int, horses: List[Dict[str, Any]]) -> None:
        """全頭ゴール後に画面中央に表示される全頭着順ボード（8頭立て全頭対応）"""
        total_h = len(horses)
        if total_h == 0:
            return

        board_w = min(540.0, float(w) - 40.0)
        row_h = 28.0
        header_h = 44.0
        board_h = header_h + row_h * total_h + 16.0

        board_x = (float(w) - board_w) / 2.0
        board_y = max(20.0, (float(h) - 110.0 - board_h) / 2.0)

        # 半透明ダークパネル
        painter.setPen(QPen(QColor("#38bdf8"), 2))
        painter.setBrush(QBrush(QColor(10, 15, 30, 235)))
        painter.drawRoundedRect(QRectF(board_x, board_y, board_w, board_h), 8, 8)

        # ヘッダーバー
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(14, 165, 233, 200)))
        painter.drawRoundedRect(QRectF(board_x + 2, board_y + 2, board_w - 4, 36), 6, 6)

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Hiragino Sans", 13, QFont.Weight.Bold))
        r_name = str(getattr(self, "race_name", "") or "レース結果")
        painter.drawText(QRectF(board_x, board_y + 6, board_w, 28), Qt.AlignmentFlag.AlignCenter, f"🏁 確定着順 - {r_name}")

        # 各馬の着順行
        cur_y = board_y + header_h + 4.0

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
            val = float(h_item.get("odds", 0.0))
            odds_list.append((val if val > 0 else 999.9, h_item.get("horse_id")))
        sorted_by_odds = sorted(odds_list, key=lambda x: x[0])
        pop_map = {hid: pop for pop, (_, hid) in enumerate(sorted_by_odds, start=1)}

        first_time = float(sorted_horses[0].get("finish_time", 0.0)) if sorted_horses else 0.0

        for rk, h_item in enumerate(sorted_horses):
            num = min(18, max(1, int(h_item.get("number", rk + 1))))
            bracket = int(h_item.get("bracket", get_jra_bracket(num, total_h)))
            name = str(h_item.get("name", f"馬{num}"))
            odds_val = float(h_item.get("odds", 0.0))
            f_time = float(h_item.get("finish_time", 0.0))
            pop = pop_map.get(h_item.get("horse_id"), rk + 1)
            bg_col, fg_col, border_col, _ = JRA_BRACKET_COLORS.get(bracket, ("#fff", "#000", "#999", ""))

            # 行の背景（ストライプ）
            if rk % 2 == 1:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(255, 255, 255, 12)))
                painter.drawRect(QRectF(board_x + 6, cur_y - 2, board_w - 12, row_h))

            # 着順
            painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            painter.setPen(QColor("#fbbf24" if rk == 0 else ("#e2e8f0" if rk < 3 else "#94a3b8")))
            painter.drawText(QRectF(board_x + 12, cur_y, 36, row_h - 4), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter, f"{rk + 1}着")

            # ゼッケン馬番
            z_rect = QRectF(board_x + 54, cur_y + 1, 24, 22)
            painter.setPen(QPen(QColor(border_col), 1.2))
            painter.setBrush(QBrush(QColor(bg_col)))
            painter.drawRoundedRect(z_rect, 3, 3)
            painter.setPen(QColor(fg_col))
            painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            painter.drawText(z_rect, Qt.AlignmentFlag.AlignCenter, str(num))

            # 馬名（全文字最後まで表示）
            painter.setPen(QColor("#ffffff" if rk == 0 else "#e2e8f0"))
            painter.setFont(QFont("Hiragino Sans", 11, QFont.Weight.Bold if rk == 0 else QFont.Weight.Medium))
            painter.drawText(QRectF(board_x + 88, cur_y, 220, row_h - 4), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)

            # オッズ・人気 (例: 2.4倍 (1人気))
            if odds_val > 0:
                painter.setPen(QColor("#fbbf24"))
                painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                pop_str = f"{odds_val:.1f}倍 ({pop}人気)"
            else:
                painter.setPen(QColor("#64748b"))
                painter.setFont(QFont("Arial", 9))
                pop_str = "―"
            painter.drawText(QRectF(board_x + 315, cur_y, 130, row_h - 4), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, pop_str)

            # タイム / 着差 (1着は走破タイム、2着以降はタイム差+X.XX秒)
            painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            if rk == 0:
                painter.setPen(QColor("#38bdf8"))
                if f_time > 0:
                    mins = int(f_time // 60)
                    secs = f_time % 60
                    diff_str = f"{mins}:{secs:04.1f}" if mins > 0 else f"{secs:.1f}s"
                else:
                    diff_str = "1着"
            else:
                if f_time > 0 and first_time > 0:
                    t_diff = max(0.0, f_time - first_time)
                    diff_str = f"+{t_diff:.2f}s"
                else:
                    diff_str = "―"
                painter.setPen(QColor("#94a3b8"))
            painter.drawText(QRectF(board_x + 455, cur_y, 70, row_h - 4), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, diff_str)

            cur_y += row_h


