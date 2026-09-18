"""
レースシミュレーション＆走破タイム確定エンジン
- 良馬場基準タイムテーブル (1000m〜3600m)
- 能力・適性・競馬場・騎手・調教師・脚質補正
- 着差算出
- 0.1秒単位の時系列リプレイデータ生成
"""

from __future__ import annotations

import json
import math
import random
from typing import Any, Dict, List, Optional, Tuple

from src.models.horse import GenotypeMSTN, Horse, RunningStyle
from src.models.jockey import Jockey
from src.models.race import Race, RaceGrade, RaceResultRecord, RaceSurface
from src.models.trainer import Trainer
from src.race.track import TrackInfo, get_track_info


# 距離別ベースタイムテーブル (距離m -> 基準タイム秒)
# 1600m（8ハロン）で 120.0秒（1ハロンちょうど15.0秒）を基準点とし、
# 短距離になるほど1ハロンあたりのペースが速く、長距離になるほど1ハロンあたりのペースが遅くなるよう設定
BASE_TIMES: Dict[int, float] = {
    1000: 70.0,    # 5F (1Fあたり 14.00秒)
    1200: 85.8,    # 6F (1Fあたり 14.30秒)
    1400: 102.55,  # 7F (1Fあたり 14.65秒)
    1600: 120.0,   # 8F (1Fあたり 15.00秒 - 基準点)
    1800: 138.15,  # 9F (1Fあたり 15.35秒)
    2000: 156.5,   # 10F (1Fあたり 15.65秒)
    2200: 175.45,  # 11F (1Fあたり 15.95秒)
    2400: 194.4,   # 12F (1Fあたり 16.20秒)
    2500: 204.0,   # 12.5F (1Fあたり 16.32秒)
    3000: 252.0,   # 15F (1Fあたり 16.80秒)
    3200: 272.0,   # 16F (1Fあたり 17.00秒)
    3600: 311.4,   # 18F (1Fあたり 17.30秒)
}


def get_base_time(distance: int, surface: RaceSurface = RaceSurface.TURF) -> float:
    """距離に応じた良馬場基準タイム（秒）を線形補間/外挿で計算"""
    known_dists = sorted(BASE_TIMES.keys())
    if distance in BASE_TIMES:
        base = BASE_TIMES[distance]
    elif distance <= known_dists[0]:
        base = BASE_TIMES[known_dists[0]] * (distance / known_dists[0])
    elif distance >= known_dists[-1]:
        base = BASE_TIMES[known_dists[-1]] * (distance / known_dists[-1])
    else:
        for i in range(len(known_dists) - 1):
            d1, d2 = known_dists[i], known_dists[i + 1]
            if d1 <= distance <= d2:
                t1, t2 = BASE_TIMES[d1], BASE_TIMES[d2]
                ratio = (distance - d1) / (d2 - d1)
                base = t1 + ratio * (t2 - t1)
                break
        else:
            base = 120.0 * (distance / 1600.0)

    if surface == RaceSurface.DIRT:
        # ダートは一般的に1000mあたり2〜3秒（平均2.5秒）タイムがかかる
        base += 2.5 * (distance / 1000.0)

    return base


def calculate_margin(time_diff: float) -> str:
    """1着とのタイム差から着差文字列表現を算出"""
    if time_diff <= 0.001:
        return "同着"
    elif time_diff < 0.04:
        return "ハナ"
    elif time_diff < 0.08:
        return "アタマ"
    elif time_diff < 0.15:
        return "クビ"
    elif time_diff < 0.25:
        return "1/2"
    elif time_diff < 0.35:
        return "3/4"
    elif time_diff < 0.50:
        return "1"
    elif time_diff < 0.70:
        return "1 1/4"
    elif time_diff < 0.90:
        return "1 1/2"
    elif time_diff < 1.15:
        return "1 3/4"
    elif time_diff < 1.45:
        return "2"
    elif time_diff < 1.80:
        return "2 1/2"
    elif time_diff < 2.20:
        return "3"
    elif time_diff < 2.70:
        return "3 1/2"
    elif time_diff < 3.30:
        return "4"
    elif time_diff < 4.00:
        return "5"
    else:
        return "大差"


def get_jra_bracket(gate: int, total_horses: int) -> int:
    """
    JRA公式ルールに基づく枠番 (1〜8) の計算
    gate: 馬番 (1〜total_horses)
    total_horses: 出走頭数 (1〜18)
    """
    if total_horses <= 8:
        return min(8, max(1, gate))

    extra = total_horses - 8
    capacities = [1] * 8
    # 外枠 (8枠から順) に1頭ずつ追加
    for i in range(7, -1, -1):
        if extra <= 0:
            break
        capacities[i] += 1
        extra -= 1
    # 16頭超の場合、さらに8枠、7枠に追加
    for i in range(7, -1, -1):
        if extra <= 0:
            break
        capacities[i] += 1
        extra -= 1

    accum = 0
    for bracket_idx, cap in enumerate(capacities, start=1):
        accum += cap
        if gate <= accum:
            return bracket_idx
    return 8


class RaceEngine:
    """レース実行エンジン"""

    def __init__(self):
        pass

    def calculate_finish_time(
        self,
        horse: Horse,
        race: Race,
        track: TrackInfo,
        jockey: Optional[Jockey] = None,
        trainer: Optional[Trainer] = None,
        escape_count: int = 1,
        tactical_style: Optional[RunningStyle] = None,
    ) -> float:
        """
        走破タイム確定アルゴリズム
        Time = 基準タイム - (α * Speed + β * Accel) + 距離ペナルティ + コース補正 - 騎手/厩舎補正 + 乱数
        """
        base_time = get_base_time(race.distance, race.surface)
        eff = horse.current_ability_rate

        # 1. 騎手による馬の能力引き出し率 (Jockey Ability Extraction Rate)
        # 騎手技術50.0で1.00(100%)を基準とし、腕利きで最大108%、若手で92%前後
        if jockey is not None:
            j_power = (jockey.skill * 0.45 + jockey.drive * 0.35 + min(jockey.experience, 100.0) * 0.20)
            jockey_extraction = 0.92 + (j_power / 100.0) * 0.16
            if jockey.is_free == 1:
                jockey_extraction += 0.01
        else:
            jockey_extraction = 0.95

        effective_speed = horse.speed * eff * jockey_extraction
        effective_accel = horse.acceleration * eff * jockey_extraction
        effective_stamina = horse.stamina * eff * (0.95 + 0.05 * ((jockey_extraction - 0.92) / 0.16))
        effective_durability = horse.durability * eff
        effective_temperament = horse.temperament

        scale = race.distance / 1600.0
        style = tactical_style if tactical_style is not None else horse.running_style

        # 2. 脚質に応じた速度・瞬発力によるタイム短縮 (基準能力50.0からの向上でタイム短縮)
        # 初年度（能力50.0）で1600m 120.0秒（1F15秒）となり、能力向上（60, 70, 80, 90+）に伴い徐々にタイムが縮まる
        # 能力同値時の合計係数は全脚質0.650で統一（1600mで能力1pt向上につき約0.65秒短縮）
        dev_speed = effective_speed - 50.0
        dev_accel = effective_accel - 50.0

        if style == RunningStyle.ESCAPE:
            # 逃げ: スピード重視
            speed_bonus = (0.420 * dev_speed + 0.230 * dev_accel) * scale
        elif style == RunningStyle.LEADING:
            # 先行: スピードと瞬発力の安定バランス
            speed_bonus = (0.355 * dev_speed + 0.295 * dev_accel) * scale
        elif style == RunningStyle.BETWEEN:
            # 差し: 瞬発力（末脚）重視
            speed_bonus = (0.295 * dev_speed + 0.355 * dev_accel) * scale
        else:  # CLOSING (追込)
            # 追込: 絶大な瞬発力（直線一気）
            speed_bonus = (0.230 * dev_speed + 0.420 * dev_accel) * scale

        # 2. スタミナ・距離ペナルティ & 逃げ・先行馬の前半消耗による直線バテ
        opt_dist = 1800.0
        if horse.mstn_type == GenotypeMSTN.CC:
            opt_dist = 1200.0
        elif horse.mstn_type == GenotypeMSTN.TT:
            opt_dist = 2600.0

        # 最適距離から±200mの適性スイートスポット
        dist_diff = max(0.0, abs(race.distance - opt_dist) - 200.0)
        stamina_cover = max(0.0, (effective_stamina - 50.0) * 0.02)
        dist_penalty = max(0.0, ((dist_diff / 400.0) ** 1.3) * (0.8 - stamina_cover))

        if race.distance >= 2000 and effective_stamina < 50.0:
            dist_penalty += ((50.0 - effective_stamina) * 0.05) * scale

        # 逃げ・先行馬のスタミナ消耗（前でハイペースを刻むためスタミナ不足時に直線でバテて失速）
        if style == RunningStyle.ESCAPE:
            if effective_stamina < 70.0:
                dist_penalty += ((70.0 - effective_stamina) * 0.022) * scale
        elif style == RunningStyle.LEADING:
            if effective_stamina < 65.0:
                dist_penalty += ((65.0 - effective_stamina) * 0.012) * scale

        # 3. ペース展開補正（先行争いハイペース vs 単騎逃げスローペース）
        pace_penalty = 0.0
        if escape_count >= 2:
            # 逃げ馬が複数（ハイペース）: 逃げ勢に消耗、差し・追込に絶好の展開利
            if style == RunningStyle.ESCAPE:
                pace_penalty += min(0.35, 0.14 + (escape_count - 2) * 0.07) * scale
            elif style == RunningStyle.LEADING:
                pace_penalty += 0.05 * scale
            elif style == RunningStyle.BETWEEN:
                pace_penalty -= 0.09 * scale
            elif style == RunningStyle.CLOSING:
                pace_penalty -= 0.14 * scale
        else:
            # 単騎逃げ（スローペース）: 逃げ・先行馬にマイペース恩恵、追込は展開不利
            if style == RunningStyle.ESCAPE:
                pace_penalty -= 0.08 * scale
            elif style == RunningStyle.LEADING:
                pace_penalty -= 0.04 * scale
            elif style == RunningStyle.BETWEEN:
                pace_penalty += 0.01 * scale
            elif style == RunningStyle.CLOSING:
                pace_penalty += 0.04 * scale

        # 4. 競馬場特性補正（坂 & 直線距離の連続補正）
        track_penalty = 0.0
        if track.has_slope:
            slope_impact = 1.0 if track.slope_type == 'steep_slope' else 0.5
            if effective_durability < 60.0:
                track_penalty += ((60.0 - effective_durability) * 0.03) * slope_impact
            else:
                track_penalty -= ((effective_durability - 60.0) * 0.01) * slope_impact

        # 直線距離に応じた連続的な脚質適性（400m基準: 長いほど差し・追込有利、短いほど逃げ先行有利）
        sl_diff = (track.straight_length - 400.0) / 200.0
        if style == RunningStyle.ESCAPE:
            track_penalty += sl_diff * 0.12
        elif style == RunningStyle.LEADING:
            track_penalty += sl_diff * 0.04
        elif style == RunningStyle.BETWEEN:
            track_penalty -= sl_diff * 0.06
        elif style == RunningStyle.CLOSING:
            track_penalty -= sl_diff * 0.12

        # 4. 騎手補正 (スキル50.0を基準とし、名手で短縮、未熟で遅延)
        jockey_bonus = 0.0
        if jockey is not None:
            j_power = (jockey.skill * 0.5 + jockey.drive * 0.3 + min(jockey.experience, 100.0) * 0.2)
            jockey_bonus = ((j_power - 50.0) / 50.0) * 0.80 * scale
            if jockey.is_free == 1:
                jockey_bonus += 0.15 * scale

        # 5. 調教師スキル補正 (スキル50.0を基準)
        trainer_bonus = 0.0
        if trainer is not None:
            trainer_bonus = ((trainer.skill_level - 50.0) / 50.0) * 0.40 * scale

        # 6. 気性と展開乱数
        temp_factor = max(10.0, effective_temperament)
        noise_sd = (100.0 - temp_factor) * 0.012 + 0.15
        noise = random.gauss(0.0, noise_sd)

        vitality_bonus = ((horse.maternal_vitality - 50.0) / 50.0) * 0.30 * scale

        finish_time = (
            base_time
            - speed_bonus
            + dist_penalty
            + track_penalty
            + pace_penalty
            - jockey_bonus
            - trainer_bonus
            - vitality_bonus
            + noise
        )

        min_allowed = base_time * 0.65
        max_allowed = base_time * 1.35
        finish_time = max(min_allowed, min(max_allowed, finish_time))

        return round(finish_time, 2)


    def calculate_odds(
        self,
        valid_starters: List[Horse],
        race: Race,
        jockey_dict: Dict[int, Jockey],
        jockey_assignments: Optional[Dict[int, int]] = None,
    ) -> Dict[int, float]:
        """出走各馬の基礎能力・馬場適性・距離適性・調子・騎手総合力から高精度な単勝オッズを算出"""
        if not valid_starters:
            return {}

        race_surf = race.surface.value if hasattr(race.surface, "value") else str(race.surface)
        scores: Dict[int, float] = {}

        for horse in valid_starters:
            hid = horse.horse_id
            j_id = jockey_assignments.get(hid) if jockey_assignments else getattr(horse, "jockey_id", None)
            jockey = jockey_dict.get(j_id) if (jockey_dict and j_id) else None

            # 1. 基礎能力 (スピード 40%, 瞬発力 25%, スタミナ 25%)
            eff_rate = getattr(horse, "current_ability_rate", 1.0)
            base_ability = (
                horse.speed * 0.40 + horse.acceleration * 0.25 + horse.stamina * 0.25
            ) * eff_rate

            # 2. 馬場適性適合度 (芝・ダート)
            surf_apt = getattr(horse, "surface_aptitude", "turf")
            if surf_apt == "both":
                surf_bonus = 3.0
            elif surf_apt == race_surf:
                surf_bonus = 5.0
            else:
                surf_bonus = -25.0  # 不適性馬場は大減点

            # 3. 距離適性適合度
            min_d = getattr(horse, "apt_distance_min", 1200)
            max_d = getattr(horse, "apt_distance_max", 2000)
            if min_d <= race.distance <= max_d:
                dist_bonus = 5.0
            elif race.distance < min_d:
                dist_bonus = -min(20.0, ((min_d - race.distance) / 200.0) * 6.0)
            else:
                dist_bonus = -min(20.0, ((race.distance - max_d) / 200.0) * 6.0)

            # 4. 騎手総合力 (技術, 追い, 経験, フリー所属)
            if jockey:
                j_power = (
                    jockey.skill * 0.50
                    + jockey.drive * 0.30
                    + min(jockey.experience, 100.0) * 0.20
                )
                j_bonus = ((j_power - 50.0) / 50.0) * 6.0
                if getattr(jockey, "is_free", 0) == 1:
                    j_bonus += 1.5
            else:
                j_bonus = 0.0

            # 5. 調子係数
            cond = getattr(horse, "condition", 50.0)
            cond_factor = 1.0 + (cond - 50.0) * 0.003

            # 総合期待スコア
            raw_score = (base_ability + surf_bonus + dist_bonus + j_bonus) * cond_factor
            scores[hid] = max(10.0, raw_score)

        # Softmax による勝率算出（実力差が適切にオッズに反映される温度 4.2）
        max_s = max(scores.values())
        temp = 4.2
        exp_scores = {hid: math.exp((s - max_s) / temp) for hid, s in scores.items()}
        sum_exp = sum(exp_scores.values())
        probs = {hid: exp_scores[hid] / sum_exp for hid in scores}

        # 単勝払戻率 80% (JRA控除率20%)
        odds_map: Dict[int, float] = {}
        for hid, p in probs.items():
            if p <= 0.0001:
                odd = 999.9
            else:
                raw_odd = 0.80 / p
                odd = max(1.1, min(999.9, round(raw_odd, 1)))
            odds_map[hid] = odd

        return odds_map

    def generate_replay_data(
        self,
        race: Race,
        finish_times: Dict[int, float],
        horses: List[Horse],
        gate_map: Optional[Dict[int, int]] = None,
        odds_map: Optional[Dict[int, float]] = None,
        jockey_assignments: Optional[Dict[int, int]] = None,
        jockey_dict: Optional[Dict[int, Any]] = None,
        tactical_style_map: Optional[Dict[int, RunningStyle]] = None,
    ) -> Tuple[str, Dict[int, float]]:
        """
        物理ベースのリアルなレース展開シミュレーション
        - スタート時: 1番が最内、外側に向かって順番に横並び整列
        - 道中: 馬の重なりを防ぐ階層的レーン（1.2m〜8.0m）で自然な馬群集団を形成
        - 第3コーナー: 後方の差し・追込馬によるロングスパート（まくり戦術）、騎手の技量に応じたペース配分・無謀仕掛けの反映
        - 追い抜き: 前壁検知時に安全マージン（約2.0m）で空いているスペース（内または外）へ進路変更
        - 勝負所・直線: 差し・追込馬のスパート持ち出しと確定着順タイムの完全整合
        - 上がり3ハロン: 残り600m通過からゴールまでのタイムを正確に計測
        - ゴール後: 全頭が通過するまで減速しながら流し走行
        """
        distance = float(race.distance)
        max_finish_time = max(finish_times.values())
        fine_dt = 0.1
        max_sim_steps = int(math.ceil((max_finish_time + 40.0) / fine_dt))  # 安全上限ステップ数
        course_width = 30.0  # コース有効幅 (m: 従来の20.0mから1.5倍にワイド拡大)

        horse_map = {h.horse_id: h for h in horses if h.horse_id is not None}
        total_horses = min(18, len(finish_times))
        gate_map = gate_map or {h_id: min(18, max(1, idx + 1)) for idx, h_id in enumerate(finish_times.keys())}

        # 初期状態の設定 (t=0: スタートゲート横並び)
        sim_horses = []
        for h_id, f_time in finish_times.items():
            horse = horse_map.get(h_id)
            if not horse:
                continue
            gate_num = min(18, max(1, int(gate_map.get(h_id, 1))))
            bracket_num = get_jra_bracket(gate_num, total_horses)
            style = tactical_style_map.get(h_id, horse.running_style) if tactical_style_map else horse.running_style

            # 騎手の技量（skill: 30.0〜90.0）の取得
            j_id = jockey_assignments.get(h_id) if jockey_assignments else getattr(horse, "jockey_id", None)
            jockey = jockey_dict.get(j_id) if (jockey_dict and j_id) else None
            j_skill = float(getattr(jockey, "skill", 50.0))

            # 脚質ペースプロファイル（リアル競馬準拠のペース配分と終盤スパート）
            if style == RunningStyle.ESCAPE:
                # 逃げ: 前半ハイペースで主導権を握り、直線は粘り込み（スタミナ切れ時はfatigue_decayで減速）
                p_start, p_mid, p_corner, p_spurt = 1.065, 1.015, 0.985, 0.960
            elif style == RunningStyle.LEADING:
                # 先行: 好位内目キープから直線抜け出しを図る
                p_start, p_mid, p_corner, p_spurt = 1.030, 1.005, 0.990, 0.965
            elif style == RunningStyle.BETWEEN:
                # 差し: 中団待機、3〜4コーナーから仕掛け直線で鋭い末脚（1.135倍）
                p_start, p_mid, p_corner, p_spurt = 0.970, 0.990, 1.035, 1.135
            else:  # CLOSING (追込)
                # 追込: 後方待機、直線は大外一気で爆発的なトップスピード（1.205倍）
                p_start, p_mid, p_corner, p_spurt = 0.935, 0.965, 1.045, 1.205

            # 脚質と枠順に応じた階層的目標レーン（8頭立てに合わせて1.5m〜12.0mのワイドな走路を活用）
            gate_norm = (gate_num - 1) / max(1, total_horses - 1)  # 0.0(最内)〜1.0(大外)
            if style == RunningStyle.ESCAPE:
                base_pref = 1.5 + gate_norm * 1.5
            elif style == RunningStyle.LEADING:
                base_pref = 2.8 + gate_norm * 2.8
            elif style == RunningStyle.BETWEEN:
                base_pref = 4.8 + gate_norm * 3.8
            else:  # CLOSING
                base_pref = 7.5 + gate_norm * 4.5

            # 微小な個体オフセットを加えて集団内の重なりを分散
            lane_noise = ((gate_num * 11) % 7 - 3) * 0.25
            pref_lateral = max(1.5, min(14.0, base_pref + lane_noise))

            # スタート地点: 8頭立てに合わせてコース幅（2.0m 〜 28.0m）いっぱいに均等配置（各馬の間隔を大幅に拡大）
            full_span = course_width - 4.0  # 26.0m (2.0m 〜 28.0m)
            gate_spacing = full_span / max(1, total_horses - 1)  # 8頭なら 26.0 / 7 ≈ 3.71m (従来の1.6mから2.3倍に拡大！)
            init_lateral = 2.0 + (gate_num - 1) * gate_spacing
            base_v = distance / f_time

            # 各馬のスタミナ適性判定と直線での体力切れ（スタミナ枯渇）発生地点の算出
            eff_stamina = horse.stamina * horse.current_ability_rate
            req_stamina = 36.0 + (distance / 400.0) * 2.8
            opt_dist = 1200.0 if horse.mstn_type == GenotypeMSTN.CC else (2600.0 if horse.mstn_type == GenotypeMSTN.TT else 1800.0)
            dist_gap = max(0.0, abs(distance - opt_dist) - 400.0)
            dist_stam_loss = (dist_gap / 200.0) * 4.0
            net_stamina = (eff_stamina - req_stamina) - dist_stam_loss
            if style == RunningStyle.ESCAPE:
                net_stamina -= 4.0

            if net_stamina < 0:
                # バテる馬でも直線終盤（残り180m〜60m）から脚が上がるように調整
                exhaust_rem_dist = min(200.0, max(50.0, 70.0 + abs(net_stamina) * 3.5))
            else:
                exhaust_rem_dist = 0.0

            if style == RunningStyle.ESCAPE and net_stamina < 5.0:
                exhaust_rem_dist = max(exhaust_rem_dist, 110.0)

            sim_horses.append({
                "horse_id": h_id,
                "horse": horse,
                "gate_num": gate_num,
                "bracket_num": bracket_num,
                "style": style,
                "j_skill": j_skill,
                "finish_time": f_time,
                "base_v": base_v,
                "paces": (p_start, p_mid, p_corner, p_spurt),
                "pref_lateral": pref_lateral,
                "init_lateral": init_lateral,
                "cur_dist": 0.0,
                "cur_lateral": init_lateral,
                "cur_v": base_v * 0.70,
                "goal_passed_time": None,
                "goal_v": None,
                "fine_dists": [0.0],
                "fine_laterals": [round(init_lateral, 2)],
                "t_600": None,  # 残り600m通過時刻
                "exhaust_rem_dist": exhaust_rem_dist,
                "exhaust_start_dist": None,
                "makuri_active": False,
                "makuri_type": None,
                "makuri_surge": 0.0,
                "makuri_extra_lat": 0.0,
            })

        # 0.1秒単位の統合シミュレーション（全頭ゴール完了＋余韻走行まで動的に継続）
        all_finished_time = None
        sim_elapsed_time = 0.0
        for s in range(1, max_sim_steps):
            t = s * fine_dt
            sim_elapsed_time = t

            # 現在の先頭馬の走破距離（騎手の位置取り・届かない判断用）
            lead_cur_dist = max(h["cur_dist"] for h in sim_horses)

            # 1. 各馬の走破距離計算（ゴール前後で完全な速度連続性を保証）
            for h in sim_horses:
                f_time = h["finish_time"]
                cur_d = h["cur_dist"]
                p_start, p_mid, p_corner, p_spurt = h["paces"]
                base_v = h["base_v"]

                if cur_d < distance:
                    # ゴール前の走行フェーズ
                    prog = cur_d / distance if distance > 0 else 0.0
                    rem_m = distance - cur_d
                    style = h["style"]

                    # 第3コーナー付近（向正面後半〜3コーナー進入: prog 0.48〜0.68）のまくり戦術判断
                    lead_gap = lead_cur_dist - cur_d
                    if (0.48 <= prog < 0.68) and style in (RunningStyle.BETWEEN, RunningStyle.CLOSING):
                        # 「このまま直線に入ったら絶対に届かない！」（先頭と10.0m以上離れている）と騎手が判断した場合
                        if lead_gap >= 10.0 and not h["makuri_active"]:
                            h["makuri_active"] = True
                            j_skill = h["j_skill"]
                            if j_skill >= 60.0:
                                # 【上手い騎手】: 余力を残す絶妙なペースで追い上げる
                                h["makuri_type"] = "skilled"
                                h["makuri_surge"] = 0.045
                                h["makuri_extra_lat"] = 1.6
                            elif j_skill < 45.0:
                                # 【技術の低い騎手】: 焦って無謀な上がり！急激に追いすぎ＆大外回りでスタミナを激しく浪費
                                h["makuri_type"] = "reckless"
                                h["makuri_surge"] = 0.095
                                h["makuri_extra_lat"] = 3.2
                                # 無謀な上がりの反動: 直線でのバテ発生地点を前倒し
                                if h["exhaust_rem_dist"] == 0.0:
                                    h["exhaust_rem_dist"] = 160.0
                                else:
                                    h["exhaust_rem_dist"] = min(220.0, h["exhaust_rem_dist"] + 60.0)
                            else:
                                # 【標準的な騎手】
                                h["makuri_type"] = "normal"
                                h["makuri_surge"] = 0.065
                                h["makuri_extra_lat"] = 2.2

                    if prog < 0.10:
                        ratio = prog / 0.10
                        v_factor = 0.70 + (p_start - 0.70) * math.sin(ratio * math.pi / 2)
                    elif prog < 0.55:
                        # 向正面: 各馬の折り合い・押し上げ
                        ratio = (prog - 0.10) / 0.45
                        surge = 0.032 * math.sin((prog - 0.25) * math.pi / 0.30) if (h["horse_id"] % 3 == 0 and prog >= 0.25) else 0.0
                        h_seed = ((h["horse_id"] * 13 + s // 10) % 7 - 3) * 0.012
                        v_factor = p_start + (p_mid - p_start) * ratio + h_seed + surge
                    elif prog < 0.70:
                        # 3コーナー〜4コーナー手前: 差し・追込の進出・まくり
                        ratio = (prog - 0.55) / 0.15 if prog >= 0.55 else 0.0
                        if h.get("makuri_active", False):
                            # まくり発動中: 第3コーナーからの加速スパート
                            m_ratio = (prog - 0.48) / 0.22
                            m_surge = h["makuri_surge"] * math.sin(min(1.0, m_ratio) * math.pi / 2.0)
                            v_factor = p_mid + (p_corner - p_mid) * ratio + m_surge
                        else:
                            surge = 0.035 * ratio if style in (RunningStyle.BETWEEN, RunningStyle.CLOSING) else 0.0
                            v_factor = p_mid + (p_corner - p_mid) * ratio + surge
                    else:
                        # 最終コーナー〜直線スパート: 直線入り口でトップスピードに乗る
                        ratio = min(1.0, (prog - 0.70) / 0.30)
                        if style == RunningStyle.ESCAPE:
                            # 逃げ馬: 直線入り口から粘り込みを図るスパート
                            s_curve = math.sin(ratio * math.pi / 2.0)
                            v_factor = p_corner + (p_spurt - p_corner) * s_curve
                        elif style == RunningStyle.LEADING:
                            # 先行馬: 好位から粘り強くスパート
                            s_curve = math.sin(ratio * math.pi / 2.0)
                            v_factor = p_corner + (p_spurt - p_corner) * s_curve
                        else:
                            # 差し・追込馬: 直線に入ると一気にトップスピード（1.13〜1.20倍）へ加速し、前をごぼう抜き！
                            s_curve = math.sin(ratio * math.pi / 2.0) ** 0.65
                            v_factor = p_corner + (p_spurt - p_corner) * s_curve

                    step_v = base_v * v_factor

                    # 直線で体力が尽きた馬の継続的減速（スピードが落ち続ける）
                    if rem_m <= h["exhaust_rem_dist"]:
                        if h["exhaust_start_dist"] is None:
                            h["exhaust_start_dist"] = cur_d
                        run_after_exhaust = max(0.0, cur_d - h["exhaust_start_dist"])
                        # 体力が尽きた後は、距離が進むにつれて継続的にスピードが落ちる（最大減速率約22%に抑え自然な失速にする）
                        fatigue_decay = max(0.78, 1.0 - (run_after_exhaust / 160.0) * 0.22)
                        step_v = step_v * fatigue_decay

                    h["cur_v"] = step_v
                    new_d = cur_d + step_v * fine_dt

                    # 残り600m（上がり3ハロン区間）通過時刻の検出
                    if h["t_600"] is None and new_d >= distance - 600.0:
                        if new_d > cur_d and (distance - 600.0) >= cur_d:
                            frac = (distance - 600.0 - cur_d) / (new_d - cur_d)
                            h["t_600"] = (s - 1) * fine_dt + frac * fine_dt
                        else:
                            h["t_600"] = t

                    # ゴール板通過の瞬間を記録
                    if new_d >= distance and h["goal_passed_time"] is None:
                        h["goal_passed_time"] = t
                        h["goal_v"] = step_v
                else:
                    # ゴール後の流し走行（ゴール通過時の速度から滑らかに指数減速、急加速を完全根絶）
                    if h["goal_passed_time"] is None:
                        h["goal_passed_time"] = t
                        h["goal_v"] = h.get("cur_v", base_v * p_spurt)
                    
                    post_t = max(0.0, t - h["goal_passed_time"])
                    init_v = h["goal_v"]
                    min_v = 7.5  # クールダウン流し速度
                    decay_rate = 0.35  # 減速時定数
                    # 速度 v(t) = min_v + (init_v - min_v) * exp(-decay_rate * post_t)
                    cur_post_v = min_v + (init_v - min_v) * math.exp(-decay_rate * post_t)
                    h["cur_v"] = cur_post_v
                    new_d = cur_d + cur_post_v * fine_dt

                h["next_dist"] = new_d

            # 各馬の現在の通過順位（先頭からの走破距離順）を判定
            sorted_horses = sorted(sim_horses, key=lambda x: x["next_dist"], reverse=True)
            cur_rank_map = {h_item["horse_id"]: idx + 1 for idx, h_item in enumerate(sorted_horses)}

            # 2. 各馬の進路取り・前壁判定・スペース探索による暫定横移動
            for h in sim_horses:
                cur_lat = h["cur_lateral"]
                cur_d = h["next_dist"]
                pref_lat = h["pref_lateral"]
                rem_d = distance - cur_d
                r_pos = cur_rank_map.get(h["horse_id"], 1)

                if rem_d > 450.0:
                    # 【道中】: スタート直後（0〜350m）は急激に内に切れ込まず、緩やかに内側へ隊列を集約
                    if cur_d < 350.0:
                        prog_s = min(1.0, cur_d / 350.0)
                        ease = prog_s * prog_s * (3.0 - 2.0 * prog_s)  # 滑らかなS字イージング
                        base_lat = h["init_lateral"] + (pref_lat - h["init_lateral"]) * ease
                        target_lat = base_lat
                    else:
                        target_lat = pref_lat

                    # 前方の馬を検出 (0.5m < Δdist < 7.5m, 横差 |Δlat| < 1.8m)
                    front_slow_horse = None
                    min_gap = 999.0
                    for other in sim_horses:
                        if other["horse_id"] == h["horse_id"]:
                            continue
                        d_gap = other["next_dist"] - cur_d
                        l_gap = abs(other["cur_lateral"] - cur_lat)
                        if 0.5 < d_gap < 7.5 and l_gap < 1.8:
                            if d_gap < min_gap:
                                min_gap = d_gap
                                front_slow_horse = other

                    if front_slow_horse:
                        b_lat = front_slow_horse["cur_lateral"]
                        # 内側が空いているか (内ラチ 1.2m 以上かつ内側に馬がいない)
                        can_inside = (b_lat - 1.9 >= 1.2)
                        if can_inside:
                            # 内側に他馬が並走していないか確認
                            for other in sim_horses:
                                if other["horse_id"] in (h["horse_id"], front_slow_horse["horse_id"]):
                                    continue
                                if abs(other["next_dist"] - cur_d) < 4.0 and abs(other["cur_lateral"] - (b_lat - 1.9)) < 1.6:
                                    can_inside = False
                                    break

                        if can_inside:
                            target_lat = b_lat - 1.9  # インから追い抜き
                        else:
                            target_lat = b_lat + 2.0  # アウトから追い抜き

                    # まくり発動中は外目を通ってポジションを押し上げる
                    if h.get("makuri_active", False):
                        target_lat = min(10.0, target_lat + h.get("makuri_extra_lat", 2.2))

                    # 道中並走回避（安全マージン）
                    for other in sim_horses:
                        if other["horse_id"] == h["horse_id"]:
                            continue
                        if abs(other["next_dist"] - cur_d) < 3.8 and abs(other["cur_lateral"] - cur_lat) < 1.8:
                            if other["cur_lateral"] < cur_lat:
                                target_lat = max(target_lat, other["cur_lateral"] + 1.9)
                else:
                    # 【最後の直線】
                    # ルール1: 自分の前に馬がいない場合には、左右に動かない（直進！）
                    # ルール2: 前壁がある場合は、内側が空いていれば内側にも進路を取り、空いていなければ外へ回避して抜く！
                    front_blocker = None
                    min_block_dist = 999.0
                    for other in sim_horses:
                        if other["horse_id"] == h["horse_id"]:
                            continue
                        d_gap = other["next_dist"] - cur_d
                        l_gap = abs(other["cur_lateral"] - cur_lat)
                        # 前方 0.5m 〜 8.5m かつ 横差 1.8m 以内の先行馬
                        if 0.5 < d_gap < 8.5 and l_gap < 1.8:
                            if d_gap < min_block_dist:
                                min_block_dist = d_gap
                                front_blocker = other

                    if front_blocker is None:
                        # 前に馬がいない！左右に動かず現在のレーンをそのまま直進！
                        target_lat = cur_lat
                    else:
                        # 前壁あり: 内側・外側の空きスペースを判定
                        b_lat = front_blocker["cur_lateral"]
                        can_inside = (b_lat - 2.0 >= 1.2)
                        if can_inside:
                            # イン側に他馬がいないか確認
                            for other in sim_horses:
                                if other["horse_id"] in (h["horse_id"], front_blocker["horse_id"]):
                                    continue
                                if abs(other["next_dist"] - cur_d) < 4.5 and abs(other["cur_lateral"] - (b_lat - 2.0)) < 1.6:
                                    can_inside = False
                                    break

                        if can_inside:
                            # 内側が空いているのでインを突いて内側へ進路を取る！
                            target_lat = b_lat - 2.0
                        else:
                            # 内側が塞がっている場合は外側へ持ち出して追い抜く！
                            target_lat = min(course_width - 1.5, b_lat + 2.1)

                    # 直線での並走安全マージン（斜行・接触防止）
                    for other in sim_horses:
                        if other["horse_id"] == h["horse_id"]:
                            continue
                        if abs(other["next_dist"] - cur_d) < 3.8 and abs(other["cur_lateral"] - target_lat) < 1.8:
                            if other["cur_lateral"] < target_lat:
                                target_lat = max(target_lat, other["cur_lateral"] + 1.9)

                # 横移動の更新（スムーズなレーンチェンジ）
                # スタート直後（0〜350m）は急激な斜行を抑えるため 0.08m/ステップ（1秒で0.8m）、通常時は 0.22m/ステップ
                max_lat_delta = 0.08 if cur_d < 350.0 else 0.22
                lat_diff = target_lat - cur_lat
                if abs(lat_diff) <= max_lat_delta:
                    new_lat = target_lat
                else:
                    new_lat = cur_lat + math.copysign(max_lat_delta, lat_diff)

                # 道中は適度に広がりを持たせつつ外に広がりすぎないよう上限(10.0m)（スタート集結完了後350m以降）
                if rem_d > 450.0 and cur_d > 350.0:
                    h["temp_lateral"] = max(1.0, min(10.0, new_lat))
                else:
                    h["temp_lateral"] = max(1.0, min(course_width - 1.2, new_lat))

            # 3. 馬体同士の並走・追い抜き重なり完全防止（ペア間分離パス）
            # 前後差 3.8m 以内で横間隔が 2.0m 未満の場合、確実に左右へ押し広げて重なりを根絶
            for _ in range(8):
                for i in range(len(sim_horses)):
                    h_i = sim_horses[i]
                    for j in range(i + 1, len(sim_horses)):
                        h_j = sim_horses[j]
                        d_gap = abs(h_i["next_dist"] - h_j["next_dist"])
                        if d_gap < 3.8:
                            l_i = h_i["temp_lateral"]
                            l_j = h_j["temp_lateral"]
                            lat_gap = abs(l_i - l_j)
                            min_clearance = 2.0
                            if lat_gap < min_clearance:
                                push = (min_clearance - lat_gap) / 2.0 + 0.10
                                # 内ラチ(1.0m)や外ラチ(course_width - 1.2m)の壁際を考慮した退避
                                if l_i > l_j:
                                    if h_j["temp_lateral"] - push < 1.0:
                                        h_i["temp_lateral"] += push * 2.0
                                    elif h_i["temp_lateral"] + push > course_width - 1.2:
                                        h_j["temp_lateral"] -= push * 2.0
                                    else:
                                        h_i["temp_lateral"] += push
                                        h_j["temp_lateral"] -= push
                                elif l_i < l_j:
                                    if h_i["temp_lateral"] - push < 1.0:
                                        h_j["temp_lateral"] += push * 2.0
                                    elif h_i["temp_lateral"] + push > course_width - 1.2:
                                        h_i["temp_lateral"] -= push * 2.0
                                    else:
                                        h_i["temp_lateral"] -= push
                                        h_j["temp_lateral"] += push
                                else:
                                    # 完全に同じレーンの場合
                                    if h_i["horse_id"] > h_j["horse_id"]:
                                        h_i["temp_lateral"] += push * 2.0
                                    else:
                                        h_j["temp_lateral"] += push * 2.0

            # 境界クランプ & トラジェクトリ確定
            for h in sim_horses:
                c_dist = h["next_dist"]
                r_dist = distance - c_dist
                # 道中（スタート後350m以降〜直線入り口450m）は内ラチ沿い〜追い抜き幅（上限8.5m）
                if r_dist > 450.0 and c_dist > 350.0:
                    final_lat = max(0.8, min(8.5, h["temp_lateral"]))
                else:
                    final_lat = max(0.8, min(course_width - 1.0, h["temp_lateral"]))
                h["cur_lateral"] = final_lat
                h["cur_dist"] = c_dist
                h["fine_dists"].append(round(c_dist, 2))
                h["fine_laterals"].append(round(final_lat, 2))

            # 4. 全頭がゴール板を通過したかの確認（全頭ゴール＋余韻流し走行を保証）
            all_passed_goal = all(h["cur_dist"] >= distance for h in sim_horses)
            if all_passed_goal:
                if all_finished_time is None:
                    all_finished_time = t
                # 全頭ゴール後、さらに 3.0 秒間の流し走行（クールダウン）を行って終了
                if t - all_finished_time >= 3.0:
                    break

        total_sim_time = sim_elapsed_time

        # 上がり3ハロン（ラスト600m）タイムの計算
        last_3f_map: Dict[int, float] = {}
        for h in sim_horses:
            hid = h["horse_id"]
            f_time = h["finish_time"]
            t_600 = h.get("t_600")
            if t_600 is not None and f_time > t_600:
                l3f = round(f_time - t_600, 1)
            else:
                # 600m以下レースや何らかのフォールバック推計
                base_v = h["base_v"] * h["paces"][3]
                l3f = round(600.0 / max(12.0, base_v), 1)
            last_3f_map[hid] = l3f

        # 0.1秒単位（fine_dt）の完全トラジェクトリをそのまま保存（補間歪み・速度ジャンプをゼロ化）
        replay_dt = fine_dt
        horse_trajectories = []

        for h in sim_horses:
            horse_trajectories.append({
                "horse_id": h["horse_id"],
                "gate_number": h["gate_num"],
                "bracket_number": h["bracket_num"],
                "name": h["horse"].name,
                "style": h["style"].value,
                "finish_time": h["finish_time"],
                "odds": odds_map.get(h["horse_id"], 0.0) if odds_map else 0.0,
                "last_3f": last_3f_map.get(h["horse_id"], 0.0),
                "positions": h["fine_dists"],
                "laterals": h["fine_laterals"],
            })

        replay_payload = {
            "race_name": race.name,
            "grade": race.grade.value if hasattr(race, "grade") and race.grade else "",
            "track_id": race.track_id,
            "distance": race.distance,
            "dt": replay_dt,
            "total_time": round(total_sim_time, 2),
            "horses": horse_trajectories,
        }
        return json.dumps(replay_payload, ensure_ascii=False), last_3f_map

    def run_race(
        self,
        race: Race,
        starters: List[Horse],
        jockey_assignments: Dict[int, int],
        all_jockeys: List[Jockey],
        all_trainers: List[Trainer],
    ) -> List[RaceResultRecord]:
        if not starters:
            return []

        jockey_dict = {j.jockey_id: j for j in all_jockeys if j.jockey_id is not None}
        trainer_dict = {t.trainer_id: t for t in all_trainers if t.trainer_id is not None}
        track = get_track_info(race.track_id)

        # 出走馬の上限を最大18頭に厳密制限
        valid_starters = [h for h in starters if h.horse_id is not None][:18]
        random_order = list(valid_starters)
        random.shuffle(random_order)
        gate_map = {h.horse_id: min(18, max(1, gate)) for gate, h in enumerate(random_order, start=1)}

        # 逃げ馬の頭数を集計（展開・ペース判定用）
        escape_count = sum(1 for h in valid_starters if h.running_style == RunningStyle.ESCAPE)
        leading_count = sum(1 for h in valid_starters if h.running_style == RunningStyle.LEADING)
        forward_count = escape_count + leading_count

        # 騎手のスキルによる戦法判断・自在性 (tactical_style_map)
        # 基本は各馬の特性(horse.running_style)に応じるが、騎手スキルが高い場合、
        # 展開（逃げ馬多数のハイペース時や、逃げ不在のスローペース時）に応じて
        # 逃げ馬を中団待機(BETWEEN)させたり、追込馬を先行(LEADING)させたりする
        tactical_style_map: Dict[int, RunningStyle] = {}
        for horse in valid_starters:
            h_id = horse.horse_id
            orig_style = horse.running_style
            j_id = jockey_assignments.get(h_id)
            jockey = jockey_dict.get(j_id) if j_id else None
            j_skill = float(getattr(jockey, "skill", 50.0))

            chosen_style = orig_style
            if j_skill >= 58.0:
                if orig_style == RunningStyle.ESCAPE and escape_count >= 2:
                    # 逃げ馬が複数いて先行激化が予想される場合 -> 熟練騎手は無理をせず中団待機（差し）
                    chosen_style = RunningStyle.BETWEEN
                elif orig_style == RunningStyle.CLOSING and forward_count <= 1:
                    # 前が手薄でスローペース・前残り予想時 -> 追込馬を好位先行に位置づける
                    chosen_style = RunningStyle.LEADING

            tactical_style_map[h_id] = chosen_style

        finish_times: Dict[int, float] = {}
        for horse in valid_starters:
            h_id = horse.horse_id
            j_id = jockey_assignments.get(h_id)
            jockey = jockey_dict.get(j_id) if j_id else None
            t_id = horse.trainer_id
            trainer = trainer_dict.get(t_id) if t_id else None

            f_time = self.calculate_finish_time(
                horse, race, track, jockey, trainer,
                escape_count=escape_count,
                tactical_style=tactical_style_map.get(h_id),
            )
            finish_times[h_id] = f_time

        sorted_horse_ids = sorted(
            finish_times.keys(),
            key=lambda hid: (finish_times[hid], random.random()),
        )

        winning_time = finish_times[sorted_horse_ids[0]]

        # 単勝オッズの算出
        odds_map = self.calculate_odds(valid_starters, race, jockey_dict, jockey_assignments=jockey_assignments)

        # リプレイデータ生成 & 上がり3ハロンの算出
        replay_json, last_3f_map = self.generate_replay_data(
            race,
            finish_times,
            valid_starters,
            gate_map=gate_map,
            odds_map=odds_map,
            jockey_assignments=jockey_assignments,
            jockey_dict=jockey_dict,
            tactical_style_map=tactical_style_map,
        )

        prize_ratios = [1.0, 0.40, 0.25, 0.15, 0.10]
        horse_map = {h.horse_id: h for h in valid_starters if h.horse_id is not None}
        results: List[RaceResultRecord] = []

        for rank, h_id in enumerate(sorted_horse_ids, start=1):
            horse = horse_map[h_id]
            f_time = finish_times[h_id]
            time_diff = round(f_time - winning_time, 2)
            
            # 着差: 1着は "-"、2着以降は「一つ前の順位の馬（前走馬）との差」
            if rank == 1:
                margin = "-"
            else:
                prev_time = finish_times[sorted_horse_ids[rank - 2]]
                prev_diff = round(f_time - prev_time, 2)
                margin = calculate_margin(prev_diff)

            gate_num = min(18, max(1, gate_map.get(h_id, rank)))

            if rank <= len(prize_ratios):
                prize = int(race.base_prize * prize_ratios[rank - 1])
            else:
                prize = 0

            cond_prize = 0
            if rank == 1:
                cond_prize = race.condition_prize
            elif rank == 2 and race.grade in (RaceGrade.G1, RaceGrade.G2, RaceGrade.G3):
                cond_prize = int(race.condition_prize * 0.40)

            results.append(
                RaceResultRecord(
                    race_id=race.race_id if race.race_id is not None else 0,
                    horse_id=h_id,
                    finish_position=rank,
                    finish_time=f_time,
                    time_diff=time_diff,
                    margin=margin,
                    prize_awarded=prize,
                    condition_prize_awarded=cond_prize,
                    jockey_id=jockey_assignments.get(h_id),
                    trainer_id=horse.trainer_id,
                    running_style_used=tactical_style_map.get(h_id, horse.running_style).value,
                    gate_number=gate_num,
                    last_3f=last_3f_map.get(h_id, 0.0),
                    odds=odds_map.get(h_id, 0.0),
                    replay_data_json=replay_json if rank == 1 else None,
                )
            )

        return results
