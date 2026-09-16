"""
レース出走登録・優先出走権・フルゲート選定・騎手アサイン管理モジュール
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Set, Tuple

from src.db.database import Database
from src.models.horse import GenotypeMSTN, Horse
from src.models.jockey import Jockey
from src.models.race import AgeRestriction, Race, RaceGrade, RaceSurface, SexRestriction


class RaceEntryManager:
    """レース出走管理クラス"""

    def __init__(self, db: Database):
        self.db = db

    def get_priority_horses_for_g1(
        self, target_g1_name: str, year: int, conn: Optional[Any] = None
    ) -> List[int]:
        """
        対象G1の当年トライアル競走で優先出走権を獲得した馬のIDリストを取得
        - 重賞トライアル: 1〜3着
        - リステッド/オープン特別トライアル: 1着
        """
        query = """
        SELECT r.horse_id, rc.grade, r.finish_position
        FROM results r
        JOIN races rc ON r.race_id = rc.race_id
        WHERE rc.year = ?
          AND rc.is_trial = 1
          AND rc.target_g1_name = ?
        ORDER BY r.finish_position ASC
        """
        if conn is not None:
            cursor = conn.execute(query, (year, target_g1_name))
            rows = cursor.fetchall()
        else:
            with self.db.session() as session_conn:
                cursor = session_conn.execute(query, (year, target_g1_name))
                rows = cursor.fetchall()

        priority_horse_ids: List[int] = []
        for row in rows:
            h_id = row['horse_id']
            grade = row['grade']
            pos = row['finish_position']
            if grade in ('G2', 'G3') and pos <= 3:
                if h_id not in priority_horse_ids:
                    priority_horse_ids.append(h_id)
            elif grade in ('L', 'OP') and pos == 1:
                if h_id not in priority_horse_ids:
                    priority_horse_ids.append(h_id)

        return priority_horse_ids

    def can_enter_race(self, horse: Horse, race: Race) -> bool:
        """馬がレースの出走資格（年齢・性別・クラス）を満たしているか判定"""
        if horse.is_active != 1 or horse.is_dead == 1:
            return False

        # 1. 年齢制限チェック
        if race.age_restriction == AgeRestriction.TWO_YO and horse.age != 2:
            return False
        if race.age_restriction == AgeRestriction.THREE_YO and horse.age != 3:
            return False
        if race.age_restriction == AgeRestriction.THREE_YO_UP and horse.age < 3:
            return False
        if race.age_restriction == AgeRestriction.FOUR_YO_UP and horse.age < 4:
            return False

        # 2. 性別制限チェック
        is_female = horse.sex in ('filly', 'mare')
        is_male = horse.sex in ('colt', 'horse', 'gelding')
        if race.sex_restriction == SexRestriction.FILLY_MARE and not is_female:
            return False
        if race.sex_restriction == SexRestriction.COLT_HORSE and not is_male:
            return False

        # 3. クラス条件チェック
        c_prize = horse.condition_prize_money
        if race.grade == RaceGrade.NEWCOMER:
            return horse.career_starts == 0
        elif race.grade == RaceGrade.MAIDEN:
            return horse.career_wins == 0
        elif race.grade == RaceGrade.COND_1W:
            return c_prize <= 4_000_000 and horse.career_wins >= 1
        elif race.grade == RaceGrade.COND_2W:
            return c_prize <= 10_000_000 and horse.career_wins >= 1
        elif race.grade == RaceGrade.COND_3W:
            return c_prize <= 16_000_000 and horse.career_wins >= 1

        return True

    def calculate_race_suitability(self, horse: Horse, race: Race) -> float:
        """馬とレースの適性スコア（0.0〜100.0）を計算"""
        score = 50.0

        opt_dist = 1800
        if horse.mstn_type == GenotypeMSTN.CC:
            opt_dist = 1200
        elif horse.mstn_type == GenotypeMSTN.TT:
            opt_dist = 2600

        dist_diff = abs(race.distance - opt_dist)
        dist_penalty = (dist_diff / 200.0) * 5.0
        score -= min(dist_penalty, 30.0)

        c_prize = horse.condition_prize_money
        if race.grade in (RaceGrade.G1, RaceGrade.G2, RaceGrade.G3):
            if c_prize >= 16_000_000:
                score += 20.0
            elif c_prize >= 10_000_000:
                score += 10.0
            else:
                score -= 20.0
        elif race.grade == RaceGrade.COND_3W:
            if 10_000_000 < c_prize <= 16_000_000:
                score += 25.0
        elif race.grade == RaceGrade.COND_2W:
            if 4_000_000 < c_prize <= 10_000_000:
                score += 25.0
        elif race.grade == RaceGrade.COND_1W:
            if 0 < c_prize <= 4_000_000 and horse.career_wins >= 1:
                score += 25.0
        elif race.grade == RaceGrade.MAIDEN and horse.career_wins == 0:
            score += 30.0
        elif race.grade == RaceGrade.NEWCOMER and horse.career_starts == 0:
            score += 35.0

        overall_ability = (horse.speed + horse.acceleration + horse.stamina) / 3.0
        score += (overall_ability - 50.0) * 0.2

        return max(score, 0.0)

    def select_starters(
        self,
        race: Race,
        candidate_horses: List[Horse],
        priority_horse_ids: Optional[List[int]] = None,
    ) -> List[Horse]:
        """
        出走馬選定（優先出走権 ＋ 収得賞金上位 ＋ フルゲート足切り）
        """
        if priority_horse_ids is None:
            priority_horse_ids = []

        valid_candidates = [h for h in candidate_horses if self.can_enter_race(h, race)]
        if not valid_candidates:
            return []

        priority_horses = [h for h in valid_candidates if h.horse_id in priority_horse_ids]
        other_horses = [h for h in valid_candidates if h.horse_id not in priority_horse_ids]

        random.shuffle(other_horses)
        other_horses.sort(
            key=lambda h: (h.condition_prize_money, h.prize_money),
            reverse=True,
        )

        starters = priority_horses + other_horses
        max_limit = min(18, race.full_gate if (hasattr(race, "full_gate") and race.full_gate) else 18)
        return starters[:max_limit]

    def assign_jockeys(
        self,
        starters: List[Horse],
        race: Race,
        all_jockeys: List[Jockey],
        trainer_jockey_map: Dict[int, int],
    ) -> Dict[int, int]:
        """
        出走馬に対する騎手アサイン
        - 基本: 自厩舎の所属騎手
        - 重賞(G1, G2, G3)または有力馬(能力上位): リーディング/実力上位のフリー騎手を優先起用可能
        - バッティング解決: 有力馬から順に確定、重複時は所属騎手または空いている騎手を手配
        """
        assigned: Dict[int, int] = {}
        busy_jockeys: Set[int] = set()

        free_jockeys = [j for j in all_jockeys if j.is_free == 1 and j.is_active == 1]
        free_jockeys.sort(
            key=lambda j: (j.experience * 0.3 + (j.skill + j.drive) * 0.7),
            reverse=True,
        )

        is_graded_race = race.grade in (RaceGrade.G1, RaceGrade.G2, RaceGrade.G3)

        sorted_starters = sorted(
            starters,
            key=lambda h: (h.speed + h.acceleration + h.stamina, h.condition_prize_money),
            reverse=True,
        )

        for rank, horse in enumerate(sorted_starters):
            h_id = horse.horse_id
            if h_id is None:
                continue

            t_id = horse.trainer_id
            stable_jockey_id = trainer_jockey_map.get(t_id) if t_id else None
            chosen_jockey_id: Optional[int] = None

            # 1. 重賞または有力馬（上位3頭）でフリー騎手を起用
            is_top_contender = rank < 3 or is_graded_race
            if is_top_contender and free_jockeys:
                for fj in free_jockeys:
                    if fj.jockey_id not in busy_jockeys:
                        chosen_jockey_id = fj.jockey_id
                        break

            # 2. フリー騎手を使わない、または空きがない場合は自厩舎所属騎手
            if chosen_jockey_id is None and stable_jockey_id:
                if stable_jockey_id not in busy_jockeys:
                    chosen_jockey_id = stable_jockey_id

            # 3. 自厩舎騎手も塞がっている場合は、馬の主戦騎手
            if chosen_jockey_id is None and horse.jockey_id:
                if horse.jockey_id not in busy_jockeys:
                    chosen_jockey_id = horse.jockey_id

            # 4. それでも決まらない場合は、まだ空いている騎手を割り当て
            if chosen_jockey_id is None:
                available_jockeys = [
                    j for j in all_jockeys
                    if j.is_active == 1 and j.jockey_id not in busy_jockeys
                ]
                if available_jockeys:
                    available_jockeys.sort(
                        key=lambda j: (j.skill + j.drive),
                        reverse=True,
                    )
                    chosen_jockey_id = available_jockeys[0].jockey_id

            if chosen_jockey_id is not None:
                assigned[h_id] = chosen_jockey_id
                busy_jockeys.add(chosen_jockey_id)

        return assigned
