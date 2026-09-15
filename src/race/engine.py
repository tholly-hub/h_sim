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


# 仕様書準拠の良馬場初期基準タイム (m -> 秒)
BASE_TIMES: Dict[int, float] = {
    1000: 70.0,
    1200: 85.0,
    1400: 101.0,
    1600: 117.0,
    1800: 133.0,
    2000: 150.0,
    2200: 167.2,
    2400: 185.0,
    2500: 198.5,
    3000: 240.0,
    3200: 263.0,
    3600: 299.0,
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
            base = 117.0 * (distance / 1600.0)

    if surface == RaceSurface.DIRT:
        base += 1.8 * (distance / 1600.0)

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
    ) -> float:
        """
        走破タイム確定アルゴリズム
        Time = 基準タイム - (α * Speed + β * Accel) + 距離ペナルティ + コース補正 - 騎手/厩舎補正 + 乱数
        """
        base_time = get_base_time(race.distance, race.surface)
        eff = horse.current_ability_rate

        effective_speed = horse.speed * eff
        effective_accel = horse.acceleration * eff
        effective_stamina = horse.stamina * eff
        effective_durability = horse.durability * eff
        effective_temperament = horse.temperament

        # 1. 速度・瞬発力によるタイム短縮
        scale = race.distance / 1600.0
        speed_bonus = (0.16 * effective_speed + 0.10 * effective_accel) * scale

        # 2. スタミナ・距離ペナルティ
        opt_dist = 1800.0
        if horse.mstn_type == GenotypeMSTN.CC:
            opt_dist = 1200.0
        elif horse.mstn_type == GenotypeMSTN.TT:
            opt_dist = 2600.0

        dist_diff = abs(race.distance - opt_dist)
        stamina_cover = max(0.0, (effective_stamina - 50.0) * 0.02)
        dist_penalty = max(0.0, ((dist_diff / 400.0) ** 1.3) * (0.8 - stamina_cover))

        if race.distance >= 2000 and effective_stamina < 50.0:
            dist_penalty += ((50.0 - effective_stamina) * 0.05) * scale

        # 3. 競馬場特性補正
        track_penalty = 0.0
        if track.has_slope:
            slope_impact = 1.0 if track.slope_type == 'steep_slope' else 0.5
            if effective_durability < 60.0:
                track_penalty += ((60.0 - effective_durability) * 0.03) * slope_impact
            else:
                track_penalty -= ((effective_durability - 60.0) * 0.01) * slope_impact

        style = horse.running_style
        if track.straight_length >= 450.0:
            if style in (RunningStyle.BETWEEN, RunningStyle.CLOSING):
                track_penalty -= 0.35
            elif style == RunningStyle.ESCAPE:
                track_penalty += 0.30
        elif track.straight_length <= 320.0:
            if style in (RunningStyle.ESCAPE, RunningStyle.LEADING):
                track_penalty -= 0.35
            elif style == RunningStyle.CLOSING:
                track_penalty += 0.40

        # 4. 騎手補正
        jockey_bonus = 0.0
        if jockey is not None:
            j_power = (jockey.skill * 0.5 + jockey.drive * 0.3 + min(jockey.experience, 100.0) * 0.2)
            jockey_bonus = (j_power / 100.0) * 1.2
            if jockey.is_free == 1:
                jockey_bonus += 0.2

        # 5. 調教師スキル補正
        trainer_bonus = 0.0
        if trainer is not None:
            trainer_bonus = (trainer.skill_level / 100.0) * 0.6

        # 6. 気性と展開乱数
        temp_factor = max(10.0, effective_temperament)
        noise_sd = (100.0 - temp_factor) * 0.012 + 0.15
        noise = random.gauss(0.0, noise_sd)

        vitality_bonus = (horse.maternal_vitality / 100.0) * 0.4

        finish_time = (
            base_time
            - speed_bonus
            + dist_penalty
            + track_penalty
            - jockey_bonus
            - trainer_bonus
            - vitality_bonus
            + noise
        )

        min_allowed = base_time * 0.75
        max_allowed = base_time * 1.30
        finish_time = max(min_allowed, min(max_allowed, finish_time))

        return round(finish_time, 2)

    def generate_replay_data(
        self,
        race: Race,
        finish_times: Dict[int, float],
        horses: List[Horse],
    ) -> str:
        distance = float(race.distance)
        max_finish_time = max(finish_times.values())
        total_steps = int(math.ceil(max_finish_time / 0.5)) + 1

        horse_map = {h.horse_id: h for h in horses if h.horse_id is not None}

        horse_trajectories = []
        for h_id, f_time in finish_times.items():
            horse = horse_map.get(h_id)
            if not horse:
                continue

            style = horse.running_style
            if style == RunningStyle.ESCAPE:
                pace_weights = (1.10, 1.00, 0.92)
            elif style == RunningStyle.LEADING:
                pace_weights = (1.04, 1.01, 0.96)
            elif style == RunningStyle.BETWEEN:
                pace_weights = (0.95, 1.00, 1.06)
            else:
                pace_weights = (0.90, 0.98, 1.12)

            positions: List[float] = []

            for step in range(total_steps):
                t = step * 0.5
                if t >= f_time:
                    positions.append(distance)
                else:
                    ratio = t / f_time
                    if ratio < 0.33:
                        w = pace_weights[0]
                    elif ratio < 0.66:
                        w = pace_weights[1]
                    else:
                        w = pace_weights[2]

                    dist = distance * (ratio ** (1.0 / w))
                    dist = min(distance, max(0.0, dist))
                    positions.append(round(dist, 1))

            horse_trajectories.append({
                "horse_id": h_id,
                "name": horse.name,
                "style": style.value,
                "finish_time": f_time,
                "positions": positions,
            })

        replay_payload = {
            "race_name": race.name,
            "distance": race.distance,
            "dt": 0.5,
            "total_time": round(max_finish_time, 2),
            "horses": horse_trajectories,
        }
        return json.dumps(replay_payload, ensure_ascii=False)

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

        finish_times: Dict[int, float] = {}
        for horse in starters:
            h_id = horse.horse_id
            if h_id is None:
                continue

            j_id = jockey_assignments.get(h_id)
            jockey = jockey_dict.get(j_id) if j_id else None
            t_id = horse.trainer_id
            trainer = trainer_dict.get(t_id) if t_id else None

            f_time = self.calculate_finish_time(horse, race, track, jockey, trainer)
            finish_times[h_id] = f_time

        sorted_horse_ids = sorted(
            finish_times.keys(),
            key=lambda hid: (finish_times[hid], random.random()),
        )

        winning_time = finish_times[sorted_horse_ids[0]]
        replay_json = self.generate_replay_data(race, finish_times, starters)

        prize_ratios = [1.0, 0.40, 0.25, 0.15, 0.10]
        horse_map = {h.horse_id: h for h in starters if h.horse_id is not None}
        results: List[RaceResultRecord] = []

        for rank, h_id in enumerate(sorted_horse_ids, start=1):
            horse = horse_map[h_id]
            f_time = finish_times[h_id]
            time_diff = round(f_time - winning_time, 2)
            margin = calculate_margin(time_diff) if rank > 1 else "-"

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
                    running_style_used=horse.running_style.value,
                    replay_data_json=replay_json if rank == 1 else None,
                )
            )

        return results
