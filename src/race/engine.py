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

        # 2. 脚質に応じた速度・瞬発力によるタイム短縮 (基準能力50.0からの成長・向上)
        # 能力50.0で1F 15.0秒（1600mで120.0秒）、能力100.0で1F 10.0秒（1600mで80.0秒）に到達するよう
        # 1600m換算で能力1ptにつき0.80秒短縮（1Fあたり0.10秒短縮）
        dev_speed = effective_speed - 50.0
        dev_accel = effective_accel - 50.0

        if style == RunningStyle.ESCAPE:
            # 逃げ: スピード重視 (α=0.65, β=0.35)
            linear_bonus = (0.65 * dev_speed + 0.35 * dev_accel) * 0.80
        elif style == RunningStyle.LEADING:
            # 先行: バランス (α=0.52, β=0.48)
            linear_bonus = (0.52 * dev_speed + 0.48 * dev_accel) * 0.80
        elif style == RunningStyle.BETWEEN:
            # 差し: 瞬発力重視 (α=0.38, β=0.62)
            linear_bonus = (0.38 * dev_speed + 0.62 * dev_accel) * 0.80
        else:  # CLOSING (追込)
            # 追込: 極限瞬発力 (α=0.25, β=0.75)
            linear_bonus = (0.25 * dev_speed + 0.75 * dev_accel) * 0.80

        speed_bonus = linear_bonus * scale

        # 2. スタミナ・距離ペナルティ & 各脚質の消耗
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

        # 全脚質（逃げ・先行・差し・追込）のスタミナ消耗・体力枯渇による直線バテ・失速ペナルティ
        if style == RunningStyle.ESCAPE:
            if effective_stamina < 58.0:
                dist_penalty += ((58.0 - effective_stamina) * 0.011) * scale
        elif style == RunningStyle.LEADING:
            if effective_stamina < 57.0:
                dist_penalty += ((57.0 - effective_stamina) * 0.010) * scale
        elif style == RunningStyle.BETWEEN:
            if effective_stamina < 56.0:
                dist_penalty += ((56.0 - effective_stamina) * 0.010) * scale
        else:  # CLOSING (追込)
            if effective_stamina < 55.0:
                dist_penalty += ((55.0 - effective_stamina) * 0.009) * scale

        # 3. ペース展開補正（先行争いハイペース vs 単騎逃げスローペース）
        pace_penalty = 0.0
        if escape_count >= 2:
            # 逃げ馬が複数（ハイペース）: 逃げ勢に消耗、差し・追込に絶好の展開利
            if style == RunningStyle.ESCAPE:
                pace_penalty += min(0.18, 0.06 + (escape_count - 2) * 0.04) * scale
            elif style == RunningStyle.LEADING:
                pace_penalty += 0.02 * scale
            elif style == RunningStyle.BETWEEN:
                pace_penalty -= 0.08 * scale
            elif style == RunningStyle.CLOSING:
                pace_penalty -= 0.09 * scale
        else:
            # 単騎逃げ（スローペース）: 逃げ・先行馬にマイペース恩恵
            if style == RunningStyle.ESCAPE:
                pace_penalty -= 0.15 * scale
            elif style == RunningStyle.LEADING:
                pace_penalty -= 0.08 * scale
            elif style == RunningStyle.BETWEEN:
                pace_penalty += 0.02 * scale
            elif style == RunningStyle.CLOSING:
                pace_penalty += 0.04 * scale

        # 4. 騎手のペース配分・仕掛け巧拙補正
        # A. 逃げ馬: 向正面での息入れ・ペースコントロール（後続を見ながらペースを落としてスタミナ温存・直線二の脚）
        escape_pace_bonus = 0.0
        if jockey is not None and style == RunningStyle.ESCAPE:
            j_skill = float(getattr(jockey, "skill", 50.0))
            if j_skill >= 50.0:
                # 熟練騎手: 向正面で絶妙に息を入れ、直線での二の脚・粘り込みを引き出す
                escape_pace_bonus = ((j_skill - 50.0) / 50.0) * 0.32 * scale
            elif j_skill < 45.0:
                # 未熟な騎手: 息を入れられずオーバーペースで直線のスタミナ切れを招く
                escape_pace_bonus = -((45.0 - j_skill) / 50.0) * 0.12 * scale

        # B. 差し・追込馬: 3〜4コーナーでの捲り（まくり）仕掛け巧拙
        makuri_jockey_bonus = 0.0
        if jockey is not None and style in (RunningStyle.BETWEEN, RunningStyle.CLOSING):
            j_skill = float(getattr(jockey, "skill", 50.0))
            if j_skill >= 55.0:
                # 熟練騎手: 絶妙なタイミングの捲りで直線も持続
                makuri_jockey_bonus = ((j_skill - 50.0) / 50.0) * 0.14 * scale
            elif j_skill < 45.0:
                # 未熟な騎手: 早仕掛け・暴走により直線で脚が上がり失速
                makuri_jockey_bonus = -((45.0 - j_skill) / 50.0) * 0.14 * scale

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
            - escape_pace_bonus
            - makuri_jockey_bonus
            - trainer_bonus
            - vitality_bonus
            + noise
        )

        # 想定限界タイム（1Fあたり10.0秒）の厳格なガード
        min_allowed = (race.distance / 200.0) * 10.0
        if race.surface == RaceSurface.DIRT:
            min_allowed += 2.0 * (race.distance / 1000.0)
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
        """
        出走各馬の実績（勝率・連対率・重賞歴）・適性・基礎能力・調子・騎手からリアルな単勝オッズを算出
        - 実績がない馬（新馬・未勝利等）が不自然に1倍台になるのを防止
        - 圧倒的実績・実力を持つ馬のみが単勝1倍台となり、高い勝率と整合
        """
        if not valid_starters:
            return {}

        race_surf = race.surface.value if hasattr(race.surface, "value") else str(race.surface)
        scores: Dict[int, float] = {}

        # レース全体の出走馬の平均キャリア
        avg_starts = sum(getattr(h, "career_starts", 0) for h in valid_starters) / max(1, len(valid_starters))

        for horse in valid_starters:
            hid = horse.horse_id
            j_id = jockey_assignments.get(hid) if jockey_assignments else getattr(horse, "jockey_id", None)
            jockey = jockey_dict.get(j_id) if (jockey_dict and j_id) else None

            starts = getattr(horse, "career_starts", 0)
            wins = getattr(horse, "career_wins", 0)
            g1_w = getattr(horse, "g1_wins", 0)
            g2_w = getattr(horse, "g2_wins", 0)
            g3_w = getattr(horse, "g3_wins", 0)
            total_g_wins = g1_w + g2_w + g3_w

            # 1. 基礎能力（市場からの推定能力値）
            eff_rate = getattr(horse, "current_ability_rate", 1.0)
            # キャリアが浅いほど市場からの能力推計の確信度は低く、人気が割れやすい
            if starts == 0:
                market_weight = 0.40  # 新馬戦は能力が見えにくい
            elif starts <= 2:
                market_weight = 0.60
            else:
                market_weight = 0.85

            base_ability = (
                horse.speed * 0.40 + horse.acceleration * 0.35 + horse.stamina * 0.25
            ) * (0.60 + eff_rate * 0.40) * market_weight

            # 2. レース実績スコア (過去の戦績・勝率・重賞実績・連対率)
            perf_score = 0.0
            if starts > 0:
                win_rate = wins / starts
                # 勝率ボーナス (最大 14.0pt)
                perf_score += win_rate * 14.0

                # 重賞実績ボーナス (G1: +5.0pt, G2: +2.5pt, G3: +1.5pt)
                perf_score += min(15.0, g1_w * 5.0 + g2_w * 2.5 + g3_w * 1.5)

                # 連勝・好調ボーナス（収得賞金・通算勝利数）
                if wins >= 4:
                    perf_score += 4.0
                elif wins == 3:
                    perf_score += 2.5
                elif wins == 2:
                    perf_score += 1.5

                # 凡走続きペナルティ（5戦以上で1勝以下など実績不振馬）
                if starts >= 5 and wins == 0:
                    perf_score -= 5.0
                elif starts >= 8 and wins <= 1:
                    perf_score -= 4.0
            else:
                # 新馬戦は横一線に近いベースライン
                perf_score = 5.0

            # 3. 馬場適性適合度 (芝・ダート)
            surf_apt = getattr(horse, "surface_aptitude", "turf")
            is_dirt_race = ("ダート" in race_surf) or (race_surf.lower() == "dirt")
            is_turf_race = ("芝" in race_surf) or (race_surf.lower() == "turf")

            if surf_apt == "both":
                surf_bonus = 1.0
            elif (surf_apt == "dirt" and is_dirt_race) or (surf_apt == "turf" and is_turf_race):
                surf_bonus = 2.5
            else:
                surf_bonus = -6.0  # 不適性馬場での減点

            # 4. 距離適性適合度
            min_d = getattr(horse, "apt_distance_min", 1200)
            max_d = getattr(horse, "apt_distance_max", 2000)
            if min_d <= race.distance <= max_d:
                dist_bonus = 2.0
            elif race.distance < min_d:
                dist_diff = min_d - race.distance
                dist_bonus = -min(6.0, (dist_diff / 200.0) * 1.8)
            else:
                dist_diff = race.distance - max_d
                dist_bonus = -min(6.0, (dist_diff / 200.0) * 1.8)

            # 5. 騎手総合力
            if jockey:
                j_power = (
                    jockey.skill * 0.45
                    + jockey.drive * 0.35
                    + min(jockey.experience, 100.0) * 0.20
                )
                j_bonus = ((j_power - 50.0) / 50.0) * 3.0
                if getattr(jockey, "is_free", 0) == 1:
                    j_bonus += 0.8
            else:
                j_bonus = 0.0

            # 6. 調子係数
            cond = getattr(horse, "condition", 50.0)
            cond_factor = 1.0 + (cond - 50.0) * 0.0025

            # 総合期待スコア算出
            raw_score = (base_ability + perf_score + surf_bonus + dist_bonus + j_bonus) * cond_factor
            scores[hid] = max(2.0, raw_score)

        # Softmax による勝率算出
        # キャリアが浅い（新馬・未勝利）時は温度を高め（temp=7.5〜9.0）にして人気を割れやすくし、1倍台の乱発を防止
        if avg_starts < 1.0:
            temp = 8.5  # 新馬戦
        elif avg_starts < 3.0:
            temp = 7.0  # 未勝利・1勝クラス初期
        else:
            temp = 6.2  # 既出走古馬・重賞戦

        max_s = max(scores.values())
        exp_scores = {hid: math.exp((s - max_s) / temp) for hid, s in scores.items()}
        sum_exp = sum(exp_scores.values())
        raw_probs = {hid: exp_scores[hid] / sum_exp for hid in scores}

        # 最低支持率フロア (floor=0.005) とラプラススムージング
        n_horses = len(scores)
        floor_prob = 0.005
        rem_mass = max(0.0, 1.0 - (floor_prob * n_horses))
        probs = {hid: (raw_probs[hid] * rem_mass) + floor_prob for hid in scores}
        sum_p = sum(probs.values())
        probs = {hid: p / sum_p for hid, p in probs.items()}

        # 単勝払戻率 80% (JRA控除率20%)
        odds_map: Dict[int, float] = {}
        for hid, p in probs.items():
            raw_odd = 0.80 / max(0.001, p)
            odd = max(1.1, min(299.0, round(raw_odd, 1)))
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
            elif style == RunningStyle.LEADING:
                net_stamina -= 2.0
            elif style == RunningStyle.BETWEEN:
                net_stamina -= 1.0
            else:  # CLOSING
                net_stamina -= 0.5

            if net_stamina < 0:
                # バテる馬は直線（残り220m〜60m）から脚が上がり徐々に減速
                exhaust_rem_dist = min(220.0, max(50.0, 70.0 + abs(net_stamina) * 4.0))
            else:
                exhaust_rem_dist = 0.0

            if style == RunningStyle.ESCAPE and net_stamina < 5.0:
                exhaust_rem_dist = max(exhaust_rem_dist, 110.0)
            elif style == RunningStyle.LEADING and net_stamina < 3.0:
                exhaust_rem_dist = max(exhaust_rem_dist, 90.0)
            elif style == RunningStyle.BETWEEN and net_stamina < 1.5:
                exhaust_rem_dist = max(exhaust_rem_dist, 80.0)
            elif style == RunningStyle.CLOSING and net_stamina < 1.0:
                exhaust_rem_dist = max(exhaust_rem_dist, 70.0)

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
                "net_stamina": net_stamina,
                "exhaust_rem_dist": exhaust_rem_dist,
                "exhaust_start_dist": None,
                "makuri_active": False,
                "makuri_type": None,
                "makuri_surge": 0.0,
                "makuri_extra_lat": 0.0,
            })

        # 1. 各馬の0.1秒ごとの正確な走破距離プロファイル d(t) を生成
        # 各馬は厳密に t = f_time の瞬間に distance（ゴール板）に到達し、ゴール通過順と確定着順が100%完全に一致
        sim_elapsed_time = max_finish_time + 3.0
        total_steps = int(math.ceil(sim_elapsed_time / fine_dt)) + 1

        for h in sim_horses:
            f_time = h["finish_time"]
            style = h["style"]
            j_skill = h["j_skill"]
            exhaust_rem = h["exhaust_rem_dist"]
            net_stam = h.get("net_stamina", 0.0)

            # ゴールまでのステップ数
            goal_step = max(1, int(round(f_time / fine_dt)))

            # 各ステップのペースウェイト w(s)
            weights = []
            for s in range(goal_step):
                tau = min(1.0, (s * fine_dt) / f_time) if f_time > 0 else 1.0

                # スタート加速ランプ (0〜8%)
                ramp = 0.60 + 0.40 * math.sin(min(1.0, tau / 0.08) * math.pi / 2.0)

                # 脚質プロファイル (道中〜コーナー〜直線の速度推移)
                if style == RunningStyle.ESCAPE:
                    # 逃げ: スタート直後（0〜22%）ハナ争い -> 向正面（22〜52%）で後続を見ながらペースを落とし息入れ -> 直線で二の脚
                    if tau < 0.22:
                        base = 1.08  # 先手奪取
                    elif tau < 0.52:
                        # 向正面の息入れ（熟練騎手ほど絶妙にペースを落としてスタミナ温存）
                        if j_skill >= 50.0:
                            b_ease = 0.98 - ((j_skill - 50.0) / 50.0) * 0.03  # 0.95〜0.98
                        elif j_skill < 45.0:
                            b_ease = 1.06  # 息を入れられない暴走逃げ
                        else:
                            b_ease = 1.01
                        base = b_ease
                    elif tau < 0.75:
                        # 3〜4コーナー: 後続の捲りを受けつつコーナーワーク
                        base = 1.00
                    else:
                        # 最後の直線: 向正面で息を入れた熟練騎手は二の脚で粘り込み
                        if j_skill >= 50.0:
                            base = 0.98 + ((j_skill - 50.0) / 50.0) * 0.03
                        elif j_skill < 45.0:
                            base = 0.89  # 息が入らず直線で脚が上がる
                        else:
                            base = 0.94
                elif style == RunningStyle.LEADING:
                    # 先行: 好位キープから最終コーナー手前でスパート態勢に入り直線抜け出し
                    base = 1.02 if tau < 0.55 else (1.00 if tau < 0.75 else 1.01)
                elif style == RunningStyle.BETWEEN:
                    # 差し: 中団待機から3〜4コーナー（tau 0.50〜0.75）でグングン前に接近し直線で鋭い末脚
                    base = 0.96 if tau < 0.50 else (1.04 if tau < 0.75 else 1.13)
                else:  # CLOSING (追込)
                    # 追込: 後方待機から3コーナー過ぎから大外を捲り上げ、直線で爆発的スパート
                    base = 0.91 if tau < 0.50 else (1.06 if tau < 0.75 else 1.20)

                # まくり補正 (3〜4コーナー: tau 0.48〜0.75 にて前の馬群に一気に近づく)
                makuri_w = 0.0
                if 0.48 <= tau <= 0.75 and style in (RunningStyle.BETWEEN, RunningStyle.CLOSING):
                    m_ratio = (tau - 0.48) / 0.27
                    if j_skill >= 55.0:
                        # 熟練騎手: スムーズで持続する絶妙な捲り（前を射程圏に捉え直線も伸びる）
                        surge_val = 0.070 + ((j_skill - 55.0) / 45.0) * 0.030
                    elif j_skill < 45.0:
                        # 未熟な騎手: 3コーナーで一気に仕掛ける暴走捲り（コーナーで先頭に迫るが直線でバテる）
                        surge_val = 0.120 + ((45.0 - j_skill) / 45.0) * 0.050
                    else:
                        surge_val = 0.080
                    makuri_w = surge_val * math.sin(m_ratio * math.pi)

                # 直線バテ・失速補正 (スタミナ枯渇馬 または 未熟騎手の暴走捲り)
                fatigue_w = 1.0
                # A. 通常のスタミナ枯渇バテ
                if exhaust_rem > 0 and tau >= 0.78:
                    f_prog = (tau - 0.78) / 0.22
                    stam_deficit = abs(min(0.0, net_stam))
                    max_decay = min(0.35, 0.15 + (stam_deficit / 15.0) * 0.15)
                    fatigue_w = max(1.0 - max_decay, 1.0 - (f_prog ** 1.2) * max_decay)
                # B. 未熟騎手の暴走捲りによる直線での脚上がり（直線残り20%で失速）
                elif j_skill < 45.0 and style in (RunningStyle.BETWEEN, RunningStyle.CLOSING) and tau >= 0.82:
                    rush_prog = (tau - 0.82) / 0.18
                    rush_decay = ((45.0 - j_skill) / 45.0) * 0.18
                    fatigue_w = max(1.0 - rush_decay, 1.0 - (rush_prog ** 1.3) * rush_decay)

                # 微小揺らぎ
                noise = ((h["horse_id"] * 13 + s // 10) % 7 - 3) * 0.008

                w = max(0.40, ramp * (base + makuri_w + noise) * fatigue_w)
                weights.append(w)

            # 累積距離テーブルの構築 (t = 0 から t = f_time まで)
            sum_w = sum(weights)
            cum_w = 0.0
            dist_profile = [0.0]
            for w in weights:
                cum_w += w
                dist_profile.append(round(distance * (cum_w / sum_w), 3))
            dist_profile[-1] = distance  # 厳密にゴール板到達！

            # ゴール通過時の速度 v_goal
            last_w = weights[-1] if weights else 1.0
            v_goal = distance * (last_w / (sum_w * fine_dt))

            # ゴール後の減速流し走行 (t > f_time)
            min_v = 7.5
            decay_rate = 0.35
            cur_post_d = distance
            cur_post_v = v_goal
            for s in range(goal_step + 1, total_steps):
                post_t = (s - goal_step) * fine_dt
                cur_post_v = min_v + (v_goal - min_v) * math.exp(-decay_rate * post_t)
                cur_post_d += cur_post_v * fine_dt
                dist_profile.append(round(cur_post_d, 3))

            h["dist_profile"] = dist_profile
            h["goal_step"] = goal_step
            h["fine_dists"] = [0.0]
            h["fine_laterals"] = [round(h["init_lateral"], 2)]

        # 2. 0.1秒刻みで進路取り・追い抜き・並走回避の横位置シミュレーション
        for s in range(1, total_steps):
            t = s * fine_dt

            # 現在ステップの走破距離を適用
            for h in sim_horses:
                h["cur_dist"] = h["dist_profile"][s] if s < len(h["dist_profile"]) else h["dist_profile"][-1]

            # 現在の通過順位を判定
            sorted_by_d = sorted(sim_horses, key=lambda x: x["cur_dist"], reverse=True)
            cur_rank_map = {h_item["horse_id"]: idx + 1 for idx, h_item in enumerate(sorted_by_d)}

            # 各馬の進路取り・前壁回避計算
            for h in sim_horses:
                cur_lat = h["cur_lateral"]
                cur_d = h["cur_dist"]
                pref_lat = h["pref_lateral"]
                rem_d = distance - cur_d

                if rem_d > 450.0:
                    # 【道中】: スタート直後（0〜350m）は緩やかに内側へ隊列を集約
                    if cur_d < 350.0:
                        prog_s = min(1.0, cur_d / 350.0)
                        ease = prog_s * prog_s * (3.0 - 2.0 * prog_s)
                        base_lat = h["init_lateral"] + (pref_lat - h["init_lateral"]) * ease
                        target_lat = base_lat
                    else:
                        target_lat = pref_lat

                    # 前方の馬を検出
                    front_slow = None
                    min_gap = 999.0
                    for other in sim_horses:
                        if other["horse_id"] == h["horse_id"]:
                            continue
                        d_gap = other["cur_dist"] - cur_d
                        l_gap = abs(other["cur_lateral"] - cur_lat)
                        if 0.5 < d_gap < 9.0 and l_gap < 2.2:
                            if d_gap < min_gap:
                                min_gap = d_gap
                                front_slow = other

                    if front_slow:
                        b_lat = front_slow["cur_lateral"]
                        can_inside = (b_lat - 2.2 >= 1.2)
                        if can_inside:
                            for other in sim_horses:
                                if other["horse_id"] in (h["horse_id"], front_slow["horse_id"]):
                                    continue
                                if abs(other["cur_dist"] - cur_d) < 4.5 and abs(other["cur_lateral"] - (b_lat - 2.2)) < 1.9:
                                    can_inside = False
                                    break

                        target_lat = (b_lat - 2.2) if can_inside else (b_lat + 2.4)

                    # まくり進出中は外目を通る
                    if (distance - cur_d) < distance * 0.50 and (distance - cur_d) > 450.0 and h["style"] in (RunningStyle.BETWEEN, RunningStyle.CLOSING):
                        target_lat = min(10.0, target_lat + 1.8)
                else:
                    # 【最後の直線】
                    front_blocker = None
                    min_block_dist = 999.0
                    for other in sim_horses:
                        if other["horse_id"] == h["horse_id"]:
                            continue
                        d_gap = other["cur_dist"] - cur_d
                        l_gap = abs(other["cur_lateral"] - cur_lat)
                        if 0.5 < d_gap < 10.5 and l_gap < 2.3:
                            if d_gap < min_block_dist:
                                min_block_dist = d_gap
                                front_blocker = other

                    if front_blocker is None:
                        target_lat = cur_lat
                    else:
                        b_lat = front_blocker["cur_lateral"]
                        can_inside = (b_lat - 2.2 >= 1.2)
                        if can_inside:
                            for other in sim_horses:
                                if other["horse_id"] in (h["horse_id"], front_blocker["horse_id"]):
                                    continue
                                if abs(other["cur_dist"] - cur_d) < 5.0 and abs(other["cur_lateral"] - (b_lat - 2.2)) < 1.9:
                                    can_inside = False
                                    break
                        target_lat = (b_lat - 2.2) if can_inside else min(course_width - 1.5, b_lat + 2.5)

                # 横移動の更新
                max_lat_delta = 0.08 if cur_d < 350.0 else 0.26
                lat_diff = target_lat - cur_lat
                if abs(lat_diff) <= max_lat_delta:
                    new_lat = target_lat
                else:
                    new_lat = cur_lat + math.copysign(max_lat_delta, lat_diff)

                if rem_d > 450.0 and cur_d > 350.0:
                    h["temp_lateral"] = max(1.0, min(10.0, new_lat))
                else:
                    h["temp_lateral"] = max(1.0, min(course_width - 1.2, new_lat))

            # 並走・追い抜き時の重なり防止（前後左右の衝突判定を厳格化）
            for _ in range(12):
                for i in range(len(sim_horses)):
                    h_i = sim_horses[i]
                    for j in range(i + 1, len(sim_horses)):
                        h_j = sim_horses[j]
                        d_gap = abs(h_i["cur_dist"] - h_j["cur_dist"])
                        if d_gap < 4.8:
                            l_i = h_i["temp_lateral"]
                            l_j = h_j["temp_lateral"]
                            lat_gap = abs(l_i - l_j)
                            min_clearance = 2.5
                            if lat_gap < min_clearance:
                                push = (min_clearance - lat_gap) / 2.0 + 0.15
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
                                    if h_i["horse_id"] > h_j["horse_id"]:
                                        h_i["temp_lateral"] += push * 2.0
                                    else:
                                        h_j["temp_lateral"] += push * 2.0

            # 確定位置の記録
            for h in sim_horses:
                c_dist = h["cur_dist"]
                r_dist = distance - c_dist
                if r_dist > 450.0 and c_dist > 350.0:
                    final_lat = max(0.8, min(8.5, h["temp_lateral"]))
                else:
                    final_lat = max(0.8, min(course_width - 1.0, h["temp_lateral"]))
                h["cur_lateral"] = final_lat
                h["fine_dists"].append(round(c_dist, 2))
                h["fine_laterals"].append(round(final_lat, 2))

        total_sim_time = sim_elapsed_time

        # 上がり3ハロン（ラスト600m通過からゴールまで）タイムの正確な計算
        last_3f_map: Dict[int, float] = {}
        for h in sim_horses:
            hid = h["horse_id"]
            f_time = h["finish_time"]
            d_list = h["dist_profile"]
            
            # 残り600m地点（distance - 600.0）を跨いだステップを線形補間
            t_600 = None
            t_target_d = distance - 600.0
            if t_target_d > 0:
                for idx_d, d_val in enumerate(d_list):
                    if d_val >= t_target_d:
                        if idx_d > 0 and d_val > d_list[idx_d - 1]:
                            frac = (t_target_d - d_list[idx_d - 1]) / (d_val - d_list[idx_d - 1])
                            t_600 = (idx_d - 1) * fine_dt + frac * fine_dt
                        else:
                            t_600 = idx_d * fine_dt
                        break
            
            if t_600 is not None and f_time > t_600:
                l3f = round(f_time - t_600, 1)
            else:
                base_v = distance / f_time if f_time > 0 else 15.0
                l3f = round(600.0 / max(10.0, base_v), 1)
            last_3f_map[hid] = l3f

        # 0.1秒単位（fine_dt）の完全トラジェクトリを保存
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


def clean_race_name(name: str) -> str:
    """
    レース名から末尾の馬場・距離などの明示括弧（例: (芝1200m), (ダ1800m), (芝2000m)）を除去し、
    本来のレース名のみ（例: 新馬, 未勝利, 2勝クラス, 有馬記念）を返す。
    「東京優駿(日本ダービー)」等のレース別称括弧は保持する。
    """
    import re
    if not name:
        return ""
    cleaned = re.sub(r"\s*[\(（][^()（）]*(?:(?:芝|ダ|ダート|障)\s*\d+|\d+\s*m)[^()（）]*[\)）]\s*", "", str(name))
    return cleaned.strip() or str(name)

