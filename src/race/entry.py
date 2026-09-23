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


# G1レース名の表記ゆれ正規化マップ
G1_ALIAS_MAP: Dict[str, str] = {
    '朝日杯FS': '朝日杯フューチュリティS',
    '朝日杯フューチュリティステークス': '朝日杯フューチュリティS',
    '阪神JF': '阪神ジュベナイルフィリーズ',
    'チャンピオンズC': 'チャンピオンズカップ',
    'マイルCS': 'マイルチャンピオンシップ',
    '全日本2歳優駿': '全日本２歳優駿',
    '日本ダービー': '東京優駿',
}


def normalize_g1_name(name: Optional[str]) -> Optional[str]:
    """G1名称の表記ゆれを公式・番組表名称に正規化"""
    if not name:
        return None
    clean = name.strip()
    return G1_ALIAS_MAP.get(clean, clean)


def calculate_carried_weight(race: Race, horse: Horse) -> float:
    """
    負担重量（斤量）の算出 (kg)
    - 2歳戦: 55.0kg (牝馬 54.0kg)
    - 3歳戦 (春季 1〜20週): 56.0kg (G1 57.0kg)
    - 3歳戦 (秋季 21週以降): 56.0kg / 57.0kg
    - 4歳以上古馬戦: G1/G2 58.0kg, G3/L/OP 57.0kg
    - 3歳以上混合戦: 3歳 56.0kg (秋57.0kg), 4歳以上 58.0kg
    - 牝馬減量: 一律 -2.0kg
    """
    is_female = horse.sex in ('filly', 'mare', '牝')
    age = horse.age

    if race.age_restriction == AgeRestriction.TWO_YO or age == 2:
        base_w = 55.0
    elif race.age_restriction == AgeRestriction.THREE_YO:
        if race.grade == RaceGrade.G1:
            base_w = 57.0
        elif race.week <= 20:
            base_w = 56.0
        else:
            base_w = 57.0
    elif race.age_restriction == AgeRestriction.THREE_YO_UP:
        if age == 3:
            base_w = 56.0 if race.week <= 36 else 57.0
        else:
            base_w = 58.0
    else:  # FOUR_YO_UP
        base_w = 58.0 if race.grade in (RaceGrade.G1, RaceGrade.G2) else 57.0

    if is_female:
        base_w -= 2.0

    return round(base_w, 1)


class RaceEntryManager:
    """レース出走管理クラス"""

    GRAND_PRIX_RACES: Set[str] = {"宝塚記念", "有馬記念", "東京大賞典"}

    def __init__(self, db: Database):
        self.db = db

    def get_priority_horses_for_g1(
        self, target_g1_name: str, year: int, conn: Optional[Any] = None
    ) -> List[int]:
        """
        対象G1の当年トライアル競走で優先出走権を獲得した馬のIDリストを取得
        ユーザー指定ルール:
        - G2トライアル: 上位2頭 (1〜2着)
        - G3トライアル: 上位1頭 (1着)
        - リステッド/オープン特別トライアル: 上位1頭 (1着)
        - 合計最大8頭まで
        """
        norm_target = normalize_g1_name(target_g1_name)
        # 表記ゆれも含めてクエリ
        possible_targets = [norm_target]
        for k, v in G1_ALIAS_MAP.items():
            if v == norm_target and k not in possible_targets:
                possible_targets.append(k)

        placeholders = ",".join("?" for _ in possible_targets)
        query = f"""
        SELECT r.horse_id, rc.grade, r.finish_position, rc.target_g1_name
        FROM results r
        JOIN races rc ON r.race_id = rc.race_id
        WHERE rc.year = ?
          AND rc.is_trial = 1
          AND rc.target_g1_name IN ({placeholders})
        ORDER BY rc.week ASC, r.finish_position ASC
        """
        params = [year] + possible_targets
        if conn is not None:
            cursor = conn.execute(query, tuple(params))
            rows = cursor.fetchall()
        else:
            with self.db.session() as session_conn:
                cursor = session_conn.execute(query, tuple(params))
                rows = cursor.fetchall()

        priority_horse_ids: List[int] = []
        for row in rows:
            h_id = row['horse_id']
            grade = row['grade']
            pos = row['finish_position']
            is_qualified = False
            # G2トライアル: 上位2頭
            if grade == 'G2' and pos <= 2:
                is_qualified = True
            # G3トライアル: 上位1頭
            elif grade == 'G3' and pos == 1:
                is_qualified = True
            # リステッド/オープン特別トライアル: 上位1頭
            elif grade in ('L', 'OP') and pos == 1:
                is_qualified = True

            if is_qualified and h_id not in priority_horse_ids:
                priority_horse_ids.append(h_id)
                if len(priority_horse_ids) >= 8:
                    break

        return priority_horse_ids

    def get_holding_priority_g1(
        self, horse_id: int, current_year: int, current_week: int, conn: Optional[Any] = None
    ) -> Optional[str]:
        """
        馬がまだ開催されていない当年G1の優先出走権を保持しているか確認
        - 保持している場合は正規化された対象G1名を返す（本番まで他のトライアル等への出走を自重・温存）
        """
        query = """
        SELECT rc.target_g1_name, rc.grade, r.finish_position
        FROM results r
        JOIN races rc ON r.race_id = rc.race_id
        WHERE r.horse_id = ?
          AND rc.year = ?
          AND rc.is_trial = 1
          AND rc.target_g1_name IS NOT NULL
        ORDER BY rc.week ASC
        """
        if conn is not None:
            rows = conn.execute(query, (horse_id, current_year)).fetchall()
        else:
            with self.db.session() as session_conn:
                rows = session_conn.execute(query, (horse_id, current_year)).fetchall()

        for row in rows:
            grade = row["grade"]
            pos = row["finish_position"]
            is_qual = False
            if grade == "G2" and pos <= 2:
                is_qual = True
            elif grade == "G3" and pos == 1:
                is_qual = True
            elif grade in ("L", "OP") and pos == 1:
                is_qual = True

            if is_qual:
                norm_g1 = normalize_g1_name(row["target_g1_name"])
                # そのG1が今週以降に開催されるか確認
                g1_check_query = """
                SELECT week FROM races
                WHERE year = ? AND (name = ? OR name LIKE ?)
                ORDER BY week ASC LIMIT 1
                """
                if conn is not None:
                    g1_row = conn.execute(g1_check_query, (current_year, norm_g1, f"{norm_g1}%")).fetchone()
                else:
                    with self.db.session() as s_conn:
                        g1_row = s_conn.execute(g1_check_query, (current_year, norm_g1, f"{norm_g1}%")).fetchone()

                if g1_row and g1_row["week"] >= current_week:
                    return norm_g1

        return None

    def get_horse_surface_preference(self, horse_id: int, conn: Optional[Any] = None) -> str:
        """
        馬の過去戦績から芝・ダート専念傾向を判定 ('turf', 'dirt', 'both')
        - 芝またはダートで勝利または重賞好走がある場合、その馬場に専念
        """
        query = """
        SELECT rc.surface, r.finish_position, r.prize_awarded, rc.grade
        FROM results r
        JOIN races rc ON r.race_id = rc.race_id
        WHERE r.horse_id = ?
        ORDER BY rc.year ASC, rc.week ASC
        """
        if conn is not None:
            rows = conn.execute(query, (horse_id,)).fetchall()
        else:
            with self.db.session() as s_conn:
                rows = s_conn.execute(query, (horse_id,)).fetchall()

        if not rows:
            return "both"

        turf_wins = sum(1 for r in rows if r["surface"] == "turf" and r["finish_position"] == 1)
        dirt_wins = sum(1 for r in rows if r["surface"] == "dirt" and r["finish_position"] == 1)
        turf_graded_top3 = sum(1 for r in rows if r["surface"] == "turf" and r["finish_position"] <= 3 and r["grade"] in ('G1', 'G2', 'G3'))
        dirt_graded_top3 = sum(1 for r in rows if r["surface"] == "dirt" and r["finish_position"] <= 3 and r["grade"] in ('G1', 'G2', 'G3'))

        if (turf_wins > 0 or turf_graded_top3 > 0) and dirt_wins == 0 and dirt_graded_top3 == 0:
            return "turf"
        if (dirt_wins > 0 or dirt_graded_top3 > 0) and turf_wins == 0 and turf_graded_top3 == 0:
            return "dirt"

        # 初勝利の馬場に専念
        for r in rows:
            if r["finish_position"] == 1:
                return r["surface"]

        return "both"

    def can_enter_race(
        self,
        horse: Horse,
        race: Race,
        last_run: Optional[Tuple[int, int]] = None,
        has_graded_top2: bool = False,
        conn: Optional[Any] = None,
    ) -> bool:
        """
        馬がレースの出走資格（年齢・性別・クラス・中2週・実績・優先出走権温存・芝ダート専念）を満たしているか判定
        """
        if horse.is_active != 1 or horse.is_dead == 1:
            return False

        is_grand_prix = any(gp in race.name for gp in self.GRAND_PRIX_RACES)

        # 1. 優先出走権保持馬の温存判定 (本番G1以外のレースへの出走をブロック)
        if horse.horse_id is not None and not is_grand_prix:
            holding_g1 = self.get_holding_priority_g1(
                horse.horse_id, race.year, race.week, conn=conn
            )
            if holding_g1:
                norm_race = normalize_g1_name(race.name)
                norm_hold = normalize_g1_name(holding_g1)
                if norm_race != norm_hold:
                    return False

        # 2. レース間隔制限 (※グランプリ競走: 宝塚記念・有馬記念・東京大賞典はレース間隔制限免除)
        if last_run is not None and not is_grand_prix:
            last_y, last_w = last_run
            diff_weeks = (race.year - last_y) * 48 + (race.week - last_w)
            min_interval = 4 if horse.career_wins == 0 else 5
            if diff_weeks < min_interval:
                return False

        # 3. G1勝利馬の出走制限（G3・リステッド競走は原則出走不可、ただしトライアル競走は出走可能）
        if getattr(horse, "g1_wins", 0) > 0 and race.grade in (RaceGrade.G3, RaceGrade.L):
            if not race.is_trial:
                return False

        # 4. 芝・ダート専念ルール（重賞・リステッド・特別戦では適性と異なる馬場を回避）
        is_graded_or_special = race.grade in (
            RaceGrade.G1, RaceGrade.G2, RaceGrade.G3, RaceGrade.L, RaceGrade.OP, RaceGrade.COND_3W
        )
        if is_graded_or_special and horse.horse_id is not None:
            surf_pref = self.get_horse_surface_preference(horse.horse_id, conn=conn)
            race_surf = "turf" if (race.surface == RaceSurface.TURF or str(race.surface).lower() in ("turf", "芝")) else "dirt"
            if surf_pref == "turf" and race_surf == "dirt":
                return False
            elif surf_pref == "dirt" and race_surf == "turf":
                return False

        # 5. 年齢制限チェック (※有馬記念・東京大賞典は3歳馬の出走も可能)
        if is_grand_prix and race.name in ("有馬記念", "東京大賞典"):
            if horse.age < 3:
                return False
        else:
            if race.age_restriction == AgeRestriction.TWO_YO and horse.age != 2:
                return False
            if race.age_restriction == AgeRestriction.THREE_YO and horse.age != 3:
                return False
            if race.age_restriction == AgeRestriction.THREE_YO_UP and horse.age < 3:
                return False
            if race.age_restriction == AgeRestriction.FOUR_YO_UP and horse.age < 4:
                return False

        # 6. 性別制限チェック
        is_female = horse.sex in ('filly', 'mare', '牝')
        is_male = horse.sex in ('colt', 'horse', 'gelding', '牡', '騸')
        sex_res_val = race.sex_restriction.value if hasattr(race.sex_restriction, 'value') else str(race.sex_restriction).lower()
        if sex_res_val in ('filly_mare', 'filly', 'mare') and not is_female:
            return False
        if sex_res_val in ('colt_horse', 'colt', 'horse') and not is_male:
            return False

        # 7. クラス・重賞・オープン出走資格チェック
        wins = horse.career_wins
        is_graded_winner = (
            getattr(horse, "g1_wins", 0) + getattr(horse, "g2_wins", 0) + getattr(horse, "g3_wins", 0)
        ) > 0
        is_open_race = race.grade in (RaceGrade.G1, RaceGrade.G2, RaceGrade.G3, RaceGrade.L, RaceGrade.OP)

        if is_open_race:
            if is_graded_winner:
                return True
            if horse.age == 2:
                return wins >= 1
            elif horse.age == 3:
                if race.week <= 20:
                    return wins >= 1
                else:
                    return wins >= 2 or has_graded_top2
            else:
                return wins >= 3 or getattr(horse, "is_open", False)

        if is_graded_winner:
            return False

        if race.grade == RaceGrade.NEWCOMER:
            return horse.career_starts == 0
        elif race.grade == RaceGrade.MAIDEN:
            return wins == 0
        elif race.grade == RaceGrade.COND_1W:
            return wins == 1
        elif race.grade == RaceGrade.COND_2W:
            return wins == 2
        elif race.grade == RaceGrade.COND_3W:
            return wins == 3

        return True

    def calculate_race_suitability(self, horse: Horse, race: Race, conn: Optional[Any] = None) -> float:
        """
        馬とレースの適性スコア（0.0〜100.0）を計算
        """
        score = 50.0

        # 1. 馬場適性判定 (実績傾向 + モデル属性)
        h_id = horse.horse_id
        surf_pref = self.get_horse_surface_preference(h_id, conn=conn) if h_id else "both"
        race_surf = "turf" if (race.surface == RaceSurface.TURF or str(race.surface).lower() in ("turf", "芝")) else "dirt"

        if surf_pref == "turf":
            score += 25.0 if race_surf == "turf" else -40.0
        elif surf_pref == "dirt":
            score += 25.0 if race_surf == "dirt" else -40.0
        else:
            score += 10.0

        # 2. 距離適性判定
        opt_dist = 1800.0
        if horse.mstn_type == GenotypeMSTN.CC:
            opt_dist = 1200.0
        elif horse.mstn_type == GenotypeMSTN.TT:
            opt_dist = 2600.0

        dist_diff = abs(race.distance - opt_dist)
        if dist_diff <= 200:
            score += 20.0
        elif dist_diff <= 400:
            score += 10.0
        elif dist_diff <= 800:
            score -= 10.0
        else:
            score -= 30.0

        # 3. 総合能力の加味
        overall = (horse.speed + horse.acceleration + horse.stamina) / 3.0
        score += (overall - 50.0) * 0.5

        return max(score, 0.0)

    def select_starters(
        self,
        race: Race,
        candidate_horses: List[Horse],
        priority_horse_ids: Optional[List[int]] = None,
        last_runs_map: Optional[Dict[int, Tuple[int, int]]] = None,
        graded_top2_set: Optional[Set[int]] = None,
        conn: Optional[Any] = None,
    ) -> List[Horse]:
        """
        出走馬選定（8頭限定、優先出走権 ＋ 適性合致馬 ＋ 収得賞金上位）
        ※ グランプリ競走（宝塚記念・有馬記念・東京大賞典）はその時点での芝・ダート成績上位8頭を最優先選出
        """
        if priority_horse_ids is None:
            priority_horse_ids = []
        if graded_top2_set is None:
            graded_top2_set = set()

        is_grand_prix = any(gp in race.name for gp in self.GRAND_PRIX_RACES)

        valid_candidates = []
        for h in candidate_horses:
            h_id = h.horse_id
            last_run = last_runs_map.get(h_id) if (last_runs_map and h_id is not None) else None
            has_top2 = h_id in graded_top2_set if (graded_top2_set and h_id is not None) else False
            if self.can_enter_race(h, race, last_run=last_run, has_graded_top2=has_top2, conn=conn):
                valid_candidates.append(h)

        if not valid_candidates:
            return []

        if is_grand_prix:
            # グランプリ: 実績・能力最上位8頭を直接選抜
            valid_candidates.sort(
                key=lambda h: (
                    (getattr(h, "g1_wins", 0) * 100 + getattr(h, "g2_wins", 0) * 30 + getattr(h, "g3_wins", 0) * 10),
                    h.condition_prize_money,
                    h.prize_money,
                    (h.speed + h.stamina + h.acceleration),
                ),
                reverse=True,
            )
            return valid_candidates[:8]

        priority_horses = [h for h in valid_candidates if h.horse_id in priority_horse_ids]
        other_horses = [h for h in valid_candidates if h.horse_id not in priority_horse_ids]

        scored_others = []
        for h in other_horses:
            suit = self.calculate_race_suitability(h, race, conn=conn)
            if suit >= 25.0 or len(other_horses) < 8:
                scored_others.append((suit, h))

        random.shuffle(scored_others)
        scored_others.sort(
            key=lambda item: (
                item[0] >= 50.0,
                item[1].condition_prize_money,
                item[0],
                item[1].prize_money,
            ),
            reverse=True,
        )

        filtered_others = [item[1] for item in scored_others]
        starters = priority_horses + filtered_others

        max_limit = min(8, race.full_gate if (hasattr(race, "full_gate") and race.full_gate) else 8)
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
        - 条件戦（新馬・未勝利・1勝・2勝・3勝クラス）:
          - まず自厩舎の所属騎手を最優先。
          - 自厩舎所属騎手が既に同レース他馬に騎乗（バッティング）している場合や不在時は、馬の主戦騎手、または空いているフリー騎手・他騎手を割り当て。
        - 重賞・リステッド・オープン（G1, G2, G3, L, OP）:
          - 上位有力馬には実力上位のフリー騎手を優先起用可能。
        """
        assigned: Dict[int, int] = {}
        busy_jockeys: Set[int] = set()

        free_jockeys = [j for j in all_jockeys if j.is_free == 1 and j.is_active == 1]
        free_jockeys.sort(
            key=lambda j: (j.experience * 0.3 + (j.skill + j.drive) * 0.7),
            reverse=True,
        )

        is_graded_or_open = race.grade in (
            RaceGrade.G1, RaceGrade.G2, RaceGrade.G3, RaceGrade.L, RaceGrade.OP
        )

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

            if is_graded_or_open:
                # 重賞・オープン戦: 有力馬（上位3頭）はフリー騎手を優先起用可能
                is_top_contender = (rank < 3)
                if is_top_contender and free_jockeys:
                    for fj in free_jockeys:
                        if fj.jockey_id not in busy_jockeys:
                            chosen_jockey_id = fj.jockey_id
                            break

                # フリー騎手を使わない／空きがない場合は自厩舎騎手
                if chosen_jockey_id is None and stable_jockey_id:
                    if stable_jockey_id not in busy_jockeys:
                        chosen_jockey_id = stable_jockey_id

                # 馬の主戦騎手
                if chosen_jockey_id is None and horse.jockey_id:
                    if horse.jockey_id not in busy_jockeys:
                        chosen_jockey_id = horse.jockey_id
            else:
                # 条件戦（新馬・未勝利・1〜3勝クラス）:
                # 1. 自厩舎所属騎手を最優先
                if stable_jockey_id and stable_jockey_id not in busy_jockeys:
                    chosen_jockey_id = stable_jockey_id

                # 2. 自厩舎所属騎手がバッティングしている等の場合は、馬の主戦騎手
                if chosen_jockey_id is None and horse.jockey_id:
                    if horse.jockey_id not in busy_jockeys:
                        chosen_jockey_id = horse.jockey_id

                # 3. 馬の主戦騎手も不在・バッティングの場合は、フリー騎手
                if chosen_jockey_id is None and free_jockeys:
                    for fj in free_jockeys:
                        if fj.jockey_id not in busy_jockeys:
                            chosen_jockey_id = fj.jockey_id
                            break

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
