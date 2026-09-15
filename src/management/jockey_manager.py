"""
騎手管理モジュール (Jockey Management & Assignments)
- 美浦40名・栗東40名の定員一定維持
- 現役30年での引退と、引退同数の新人騎手誕生サイクル
- 実力に応じた有力馬配分（主戦騎手制度）
- 同一レースでお手馬重複時の代打騎手手配
- 代打好走時（連対等）の主戦騎手乗り替わり昇格処理
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.db.database import Database
from src.generators.name_generator import PersonNameGenerator
from src.models.jockey import Jockey


@dataclass
class JockeyAssignmentResult:
    """レース騎乗騎手割り当て結果"""
    horse_id: int
    horse_name: str
    assigned_jockey_id: int
    assigned_jockey_name: str
    is_regular: bool            # True: 主戦騎手, False: 代打騎手
    original_jockey_id: Optional[int]


class JockeyManager:
    """騎手ライフサイクルおよび騎乗割り当てマネージャー"""

    def __init__(self, db: Database, quota_miho: int = 45, quota_ritto: int = 45):
        self.db = db
        self.quota_miho = quota_miho
        self.quota_ritto = quota_ritto
        self.name_gen = PersonNameGenerator()

    def generate_rookie_jockey(
        self,
        location: str,
        current_year: int,
        mean_ability: float = 48.0,
        std_ability: float = 6.0,
        target_trainer_id: Optional[int] = None,
        conn: Optional[Any] = None,
    ) -> Jockey:
        """新人騎手を1名生成（18歳、キャリア1年目、厩舎専属所属）"""
        if conn is not None:
            existing = conn.execute("SELECT name FROM jockeys").fetchall()
            for r in existing:
                self.name_gen.register_jockey_name(r["name"])

            # 所属厩舎が指定されていない場合、同地域の所属騎手がいない厩舎を優先探索
            if target_trainer_id is None:
                trainer_rows = conn.execute(
                    """
                    SELECT t.trainer_id 
                    FROM trainers t
                    WHERE t.location = ? AND t.trainer_id NOT IN (
                        SELECT trainer_id FROM jockeys WHERE is_active = 1 AND trainer_id IS NOT NULL
                    )
                    """,
                    (location,),
                ).fetchall()
                if trainer_rows:
                    target_trainer_id = random.choice(trainer_rows)["trainer_id"]
                else:
                    t_cand = conn.execute(
                        "SELECT trainer_id FROM trainers WHERE location = ?", (location,)
                    ).fetchall()
                    if t_cand:
                        target_trainer_id = random.choice(t_cand)["trainer_id"]
        else:
            with self.db.session() as c:
                existing = c.execute("SELECT name FROM jockeys").fetchall()
                for r in existing:
                    self.name_gen.register_jockey_name(r["name"])

                if target_trainer_id is None:
                    trainer_rows = c.execute(
                        """
                        SELECT t.trainer_id 
                        FROM trainers t
                        WHERE t.location = ? AND t.trainer_id NOT IN (
                            SELECT trainer_id FROM jockeys WHERE is_active = 1 AND trainer_id IS NOT NULL
                        )
                        """,
                        (location,),
                    ).fetchall()
                    if trainer_rows:
                        target_trainer_id = random.choice(trainer_rows)["trainer_id"]
                    else:
                        t_cand = c.execute(
                            "SELECT trainer_id FROM trainers WHERE location = ?", (location,)
                        ).fetchall()
                        if t_cand:
                            target_trainer_id = random.choice(t_cand)["trainer_id"]

        name = self.name_gen.generate_jockey_name()
        g_type = random.choice(["early", "standard", "standard", "late", "persistent"])

        def sample_ability():
            val = random.gauss(mean_ability, std_ability)
            return round(max(30.0, min(80.0, val)), 1)

        return Jockey(
            name=name,
            location=location,
            age=18,
            debut_year=current_year,
            career_years=1,
            is_active=1,
            growth_type=g_type,
            is_free=0,
            trainer_id=target_trainer_id,
            experience=0.0,
            stamina=50.0,
            skill=sample_ability(),
            drive=sample_ability(),
            start_dash=sample_ability(),
            temperament_handling=sample_ability(),
        )

    def progress_year_and_maintain_quota(self, current_year: int, strict_free: bool = True, conn: Optional[Any] = None) -> Dict[str, Any]:
        """
        年次進行処理:
        1. 全現役騎手の加齢・経験値加算・成長＆40歳以降の体力減衰
        2. 多段階引退判定:
           - 5年目(22歳): 通算勝数 < 8勝
           - 10年目(27歳): 通算勝数 < 25勝
           - 20年目(37歳): 通算勝数 < 75勝 かつ 重賞0勝
           - 50歳以上: 年間勝数 < 3勝
           - 60歳定年引退
        3. 引退騎手の転身（50歳未満は所属厩舎の調教助手に就任、調教助手は50歳定年）
        4. フリー転向判定（条件を満たした所属騎手のフリー化）
        5. 引退同数の新人騎手（18歳）を補充（美浦45・栗東45の定員を完全維持）
        """
        retired_jockeys: List[Dict[str, Any]] = []
        retired_by_loc: Dict[str, List[Dict[str, Any]]] = {"美浦": [], "栗東": []}
        promoted_free_jockeys: List[Dict[str, Any]] = []
        new_assistants: List[Dict[str, Any]] = []
        new_jockeys: List[Jockey] = []

        if conn is not None:
            return self._execute_progress_year(
                conn, current_year, strict_free, retired_jockeys, retired_by_loc,
                promoted_free_jockeys, new_assistants, new_jockeys
            )
        else:
            with self.db.session() as c:
                return self._execute_progress_year(
                    c, current_year, strict_free, retired_jockeys, retired_by_loc,
                    promoted_free_jockeys, new_assistants, new_jockeys
                )

    def _execute_progress_year(
        self,
        conn: Any,
        current_year: int,
        strict_free: bool,
        retired_jockeys: List[Dict[str, Any]],
        retired_by_loc: Dict[str, List[Dict[str, Any]]],
        promoted_free_jockeys: List[Dict[str, Any]],
        new_assistants: List[Dict[str, Any]],
        new_jockeys: List[Jockey],
    ) -> Dict[str, Any]:
        # 1. 現役騎手の能力更新・引退判定
        active_rows = conn.execute(
            "SELECT * FROM jockeys WHERE is_active = 1 ORDER BY jockey_id"
        ).fetchall()

        for r in active_rows:
            j = Jockey.from_row(r)
            # 年次加齢と能力・体力推移
            j.advance_age_and_abilities(
                wins_this_year=j.current_year_wins,
                g1_this_year=j.current_year_g1,
                rides_this_year=j.current_year_rides,
            )

            # 多段階引退判定
            should_retire = False
            retire_reason = ""

            if j.age >= 60:
                should_retire = True
                retire_reason = "60歳定年引退"
            elif j.age >= 50 and j.current_year_wins < 3:
                should_retire = True
                retire_reason = "50歳以上年間成績不振"
            elif j.career_years == 5 and j.career_wins < 8:
                should_retire = True
                retire_reason = "5年目成績足切り"
            elif j.career_years == 10 and j.career_wins < 25:
                should_retire = True
                retire_reason = "10年目成績足切り"
            elif j.career_years == 20 and j.career_wins < 75 and (j.g1_wins + j.g2_wins + j.g3_wins) == 0:
                should_retire = True
                retire_reason = "20年目重賞未勝利足切り"

            if should_retire:
                conn.execute(
                    """
                    UPDATE jockeys 
                    SET age = ?, career_years = ?, is_active = 0,
                        skill = ?, drive = ?, start_dash = ?, temperament_handling = ?,
                        experience = ?, stamina = ?
                    WHERE jockey_id = ?
                    """,
                    (
                        j.age, j.career_years,
                        j.skill, j.drive, j.start_dash, j.temperament_handling,
                        j.experience, j.stamina, j.jockey_id
                    ),
                )
                ret_info = {
                    "jockey_id": j.jockey_id,
                    "name": j.name,
                    "location": j.location,
                    "age": j.age,
                    "career_years": j.career_years,
                    "career_wins": j.career_wins,
                    "g1_wins": j.g1_wins,
                    "reason": retire_reason,
                    "trainer_id": j.trainer_id,
                }
                retired_jockeys.append(ret_info)
                retired_by_loc[j.location].append(ret_info)

                # 50歳未満で引退した場合は調教助手に就任
                if j.age < 50 and j.trainer_id is not None:
                    conn.execute(
                        """
                        INSERT INTO assistant_trainers (
                            jockey_id, trainer_id, name, age, career_wins, g1_wins, is_active
                        ) VALUES (?, ?, ?, ?, ?, ?, 1)
                        """,
                        (j.jockey_id, j.trainer_id, j.name, j.age, j.career_wins, j.g1_wins),
                    )
                    new_assistants.append({
                        "jockey_id": j.jockey_id,
                        "name": j.name,
                        "trainer_id": j.trainer_id,
                        "age": j.age,
                    })
            else:
                # 現役継続: フリー化判定
                if j.is_free == 0 and j.can_become_free(strict=strict_free):
                    j.is_free = 1
                    j.trainer_id = None
                    promoted_free_jockeys.append({
                        "jockey_id": j.jockey_id,
                        "name": j.name,
                        "career_wins": j.career_wins,
                        "g1_wins": j.g1_wins,
                    })

                conn.execute(
                    """
                    UPDATE jockeys 
                    SET age = ?, career_years = ?, is_free = ?, trainer_id = ?,
                        skill = ?, drive = ?, start_dash = ?, temperament_handling = ?,
                        experience = ?, stamina = ?
                    WHERE jockey_id = ?
                    """,
                    (
                        j.age, j.career_years, j.is_free, j.trainer_id,
                        j.skill, j.drive, j.start_dash, j.temperament_handling,
                        j.experience, j.stamina, j.jockey_id
                    ),
                )

        # 2. 調教助手の加齢と50歳定年処理
        conn.execute("UPDATE assistant_trainers SET age = age + 1 WHERE is_active = 1")
        conn.execute("UPDATE assistant_trainers SET is_active = 0 WHERE age >= 50 AND is_active = 1")

        # 3. 引退分と同数の新人騎手を生成・登録（定員維持: 美浦45名・栗東45名）
        for loc in ["美浦", "栗東"]:
            for _ in range(len(retired_by_loc[loc])):
                rookie = self.generate_rookie_jockey(loc, current_year, conn=conn)
                cursor = conn.execute(
                    """
                    INSERT INTO jockeys (
                        name, gender, location, age, debut_year, career_years, is_active,
                        growth_type, is_free, trainer_id, experience, stamina,
                        skill, drive, start_dash, temperament_handling
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rookie.name, rookie.gender, rookie.location, rookie.age, rookie.debut_year, rookie.career_years,
                        rookie.growth_type, rookie.is_free, rookie.trainer_id, rookie.experience, rookie.stamina,
                        rookie.skill, rookie.drive, rookie.start_dash, rookie.temperament_handling,
                    ),
                )
                rookie.jockey_id = cursor.lastrowid
                new_jockeys.append(rookie)

        # 引退した騎手が主戦だった馬の主戦騎手リセット
        if retired_jockeys:
            retired_ids = [r["jockey_id"] for r in retired_jockeys]
            placeholders = ",".join("?" * len(retired_ids))
            conn.execute(
                f"UPDATE horses SET jockey_id = NULL WHERE jockey_id IN ({placeholders})",
                retired_ids,
            )

        return {
        "retired_count": len(retired_jockeys),
        "retired_jockeys": retired_jockeys,
        "retired_by_location": retired_by_loc,
        "promoted_free_count": len(promoted_free_jockeys),
        "promoted_free_jockeys": promoted_free_jockeys,
        "new_assistants_count": len(new_assistants),
        "new_jockeys": new_jockeys,
        "new_count": len(new_jockeys),
        }


    def assign_jockeys_for_race(self, horse_ids: List[int]) -> List[JockeyAssignmentResult]:
        """
        同一レースに出走する競走馬群への騎手手配ロジック:
        - 基本は各馬の主戦騎手（jockey_id）が騎乗。
        - 同一レースに同じ騎手のお手馬が重複した場合：
          - 最も能力値・賞金が高い馬に主戦騎手が先約騎乗。
          - あぶれた馬には、空いている所属騎手の中から実力上位の代打騎手を割り当て。
        """
        assignments: List[JockeyAssignmentResult] = []
        if not horse_ids:
            return assignments

        with self.db.session() as conn:
            # 出走馬情報の取得
            placeholders = ",".join("?" * len(horse_ids))
            horses = conn.execute(
                f"""
                SELECT h.horse_id, h.name, h.jockey_id, h.speed, h.stamina, h.prize_money, t.location as stable_loc
                FROM horses h
                LEFT JOIN trainers t ON h.trainer_id = t.trainer_id
                WHERE h.horse_id IN ({placeholders})
                ORDER BY h.prize_money DESC, (h.speed + h.stamina) DESC
                """,
                horse_ids,
            ).fetchall()

            # 利用可能な現役騎手リストの取得
            all_active_jockeys = conn.execute(
                """
                SELECT jockey_id, name, location, (skill + drive + start_dash + temperament_handling)/4.0 as total_ability
                FROM jockeys
                WHERE is_active = 1
                ORDER BY total_ability DESC
                """
            ).fetchall()

            busy_jockeys: set[int] = set()
            horses_needing_sub: List[Any] = []

            # 1. お手馬の先約騎乗判定（能力・賞金上位優先）
            for h in horses:
                j_id = h["jockey_id"]
                if j_id is not None and j_id not in busy_jockeys:
                    # 主戦騎乗成立
                    busy_jockeys.add(j_id)
                    j_row = conn.execute("SELECT name FROM jockeys WHERE jockey_id = ?", (j_id,)).fetchone()
                    assignments.append(JockeyAssignmentResult(
                        horse_id=h["horse_id"],
                        horse_name=h["name"],
                        assigned_jockey_id=j_id,
                        assigned_jockey_name=j_row["name"] if j_row else f"Jockey:{j_id}",
                        is_regular=True,
                        original_jockey_id=j_id,
                    ))
                else:
                    # お手馬重複または主戦未設定のため代打が必要
                    horses_needing_sub.append(h)

            # 2. 代打騎手の手配（厩舎所在地優先、実力上位の空き騎手から）
            for h in horses_needing_sub:
                stable_loc = h["stable_loc"] or "栗東"
                sub_chosen = None

                # まず同所属（美浦/栗東）の空き騎手から実力順で探索
                for j in all_active_jockeys:
                    if j["jockey_id"] not in busy_jockeys and j["location"] == stable_loc:
                        sub_chosen = j
                        break

                # 同所属に空きがなければ他方の空き騎手から探索
                if not sub_chosen:
                    for j in all_active_jockeys:
                        if j["jockey_id"] not in busy_jockeys:
                            sub_chosen = j
                            break

                if sub_chosen:
                    busy_jockeys.add(sub_chosen["jockey_id"])
                    assignments.append(JockeyAssignmentResult(
                        horse_id=h["horse_id"],
                        horse_name=h["name"],
                        assigned_jockey_id=sub_chosen["jockey_id"],
                        assigned_jockey_name=sub_chosen["name"],
                        is_regular=False,
                        original_jockey_id=h["jockey_id"],
                    ))

        return assignments

    def handle_substitute_success(self, horse_id: int, sub_jockey_id: int, finish_position: int) -> bool:
        """
        代打騎乗で好成績（1着〜2着の連対）を収めた場合、今後の主戦騎手として正式に乗り替わり昇格
        Returns:
            主戦昇格したかどうか
        """
        if finish_position <= 2:
            with self.db.session() as conn:
                conn.execute(
                    "UPDATE horses SET jockey_id = ? WHERE horse_id = ?",
                    (sub_jockey_id, horse_id),
                )
            return True
        return False
