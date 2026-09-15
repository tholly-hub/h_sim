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

    def __init__(self, db: Database, quota_miho: int = 30, quota_ritto: int = 30):
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
    ) -> Jockey:
        """新人騎手を1名生成（20歳、キャリア1年目）"""
        with self.db.session() as conn:
            existing = conn.execute("SELECT name FROM jockeys").fetchall()
            for r in existing:
                self.name_gen.register_jockey_name(r["name"])

        name = self.name_gen.generate_jockey_name()

        def sample_ability():
            val = random.gauss(mean_ability, std_ability)
            return round(max(30.0, min(80.0, val)), 1)

        return Jockey(
            name=name,
            location=location,
            age=20,
            debut_year=current_year,
            career_years=1,
            is_active=1,
            skill=sample_ability(),
            drive=sample_ability(),
            start_dash=sample_ability(),
            temperament_handling=sample_ability(),
        )

    def progress_year_and_maintain_quota(self, current_year: int) -> Dict[str, Any]:
        """
        年次進行処理:
        1. 全現役騎手の年齢・キャリア年数を+1
        2. 50歳到達（キャリア30年満了）の騎手を引退（is_active = 0）
        3. 美浦・栗東で引退した人数と同数の新人騎手を補充（20歳、定員各30名を完全維持）
        """
        retired_jockeys: List[Dict[str, Any]] = []
        retired_by_loc: Dict[str, List[Dict[str, Any]]] = {"美浦": [], "栗東": []}
        new_jockeys: List[Jockey] = []

        with self.db.session() as conn:
            # 1 & 2. 現役騎手の更新と引退判定 (50歳で引退)
            active_rows = conn.execute(
                "SELECT * FROM jockeys WHERE is_active = 1 ORDER BY jockey_id"
            ).fetchall()

            for r in active_rows:
                new_age = r["age"] + 1
                new_career = r["career_years"] + 1

                if new_age >= 50 or new_career > 30:
                    # 50歳定年引退 (厩舎開業へ)
                    conn.execute(
                        """
                        UPDATE jockeys 
                        SET age = ?, career_years = ?, is_active = 0 
                        WHERE jockey_id = ?
                        """,
                        (new_age, new_career, r["jockey_id"]),
                    )
                    ret_info = {
                        "jockey_id": r["jockey_id"],
                        "name": r["name"],
                        "location": r["location"],
                        "age": new_age,
                        "career_years": new_career,
                        "career_wins": r["career_wins"],
                        "g1_wins": r["g1_wins"],
                    }
                    retired_jockeys.append(ret_info)
                    retired_by_loc[r["location"]].append(ret_info)
                else:
                    # 現役継続
                    conn.execute(
                        """
                        UPDATE jockeys 
                        SET age = ?, career_years = ? 
                        WHERE jockey_id = ?
                        """,
                        (new_age, new_career, r["jockey_id"]),
                    )

            # 3. 引退分と同数の新人騎手を生成・登録（定員維持: 各地区30名）
            for loc in ["美浦", "栗東"]:
                for _ in range(len(retired_by_loc[loc])):
                    rookie = self.generate_rookie_jockey(loc, current_year)
                    cursor = conn.execute(
                        """
                        INSERT INTO jockeys (
                            name, location, age, debut_year, career_years, is_active,
                            skill, drive, start_dash, temperament_handling
                        ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                        """,
                        (
                            rookie.name, rookie.location, rookie.age, rookie.debut_year, rookie.career_years,
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
