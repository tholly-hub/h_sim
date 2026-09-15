"""
厩舎管理モジュール (Stable & Trainer Management)
- 美浦・栗東の厩舎管理
- 入厩・転厩・受入枠拡張（初期30頭〜最大50頭）
- 枠超過時の他厩舎転厩（東西同一優先、空き枠優先、最低1頭所属保証・0頭防止）
- 厩舎特徴（芝/ダート/長距離/短距離/仕上がり等）の判定
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.db.database import Database
from src.generators.name_generator import PersonNameGenerator
from src.models.trainer import TrainerSpecialty


@dataclass
class TransferRecordStable:
    """転厩レコード"""
    horse_id: int
    horse_name: str
    from_trainer_id: int
    from_trainer_name: str
    to_trainer_id: int
    to_trainer_name: str
    reason: str


class StableManager:
    """厩舎管理クラス"""

    def __init__(self, db: Database, max_capacity: int = 50, default_expand_step: int = 5):
        self.db = db
        self.max_capacity = max_capacity
        self.default_expand_step = default_expand_step

    def get_trainer_inventory(self, trainer_id: int) -> Dict[str, Any]:
        """指定厩舎の所属馬状況・枠数・空き状況を取得"""
        with self.db.session() as conn:
            trainer_row = conn.execute(
                "SELECT * FROM trainers WHERE trainer_id = ?",
                (trainer_id,),
            ).fetchone()
            if not trainer_row:
                raise ValueError(f"Trainer ID {trainer_id} does not exist.")

            horses = conn.execute(
                """
                SELECT horse_id, name, age, sex, speed, stamina, prize_money
                FROM horses
                WHERE trainer_id = ? AND is_active = 1
                ORDER BY prize_money DESC, speed DESC
                """,
                (trainer_id,),
            ).fetchall()

            total = len(horses)
            cap = trainer_row["horse_capacity"]

            return {
                "trainer_id": trainer_row["trainer_id"],
                "name": trainer_row["name"],
                "location": trainer_row["location"],
                "specialty": trainer_row["specialty"],
                "capacity": cap,
                "reputation": trainer_row["reputation"],
                "career_wins": trainer_row["career_wins"],
                "horses": [dict(h) for h in horses],
                "total_horses": total,
                "available_slots": cap - total,
            }

    def expand_capacity(self, trainer_id: int, step: Optional[int] = None) -> bool:
        """厩舎の受入枠を拡張（最大 max_capacity まで）"""
        increase = step if step is not None else self.default_expand_step
        with self.db.session() as conn:
            row = conn.execute(
                "SELECT horse_capacity FROM trainers WHERE trainer_id = ?",
                (trainer_id,),
            ).fetchone()
            if not row:
                return False

            current_cap = row["horse_capacity"]
            if current_cap >= self.max_capacity:
                return False

            new_cap = min(self.max_capacity, current_cap + increase)
            conn.execute(
                "UPDATE trainers SET horse_capacity = ? WHERE trainer_id = ?",
                (new_cap, trainer_id),
            )
            return True

    def find_target_stable_for_transfer(
        self,
        from_location: str,
        exclude_trainer_ids: List[int],
        allow_expansion: bool = True,
    ) -> Optional[int]:
        """
        転厩先厩舎を選定。
        1. 同じ所属地（美浦なら美浦、栗東なら栗東）で空き枠のある厩舎から選定
        2. 他方の所属地で空き枠のある厩舎から選定
        3. 空き枠がなければ拡張可能な厩舎を拡張して選定
        """
        priority_locations = [from_location, "栗東" if from_location == "美浦" else "美浦"]

        with self.db.session() as conn:
            all_trainers = conn.execute(
                """
                SELECT 
                    t.trainer_id, t.name, t.location, t.horse_capacity,
                    (SELECT COUNT(*) FROM horses h WHERE h.trainer_id = t.trainer_id AND h.is_active = 1) as current_count
                FROM trainers t
                """
            ).fetchall()

            trainers_by_loc: Dict[str, List[Dict[str, Any]]] = {"美浦": [], "栗東": []}
            for t in all_trainers:
                if t["trainer_id"] in exclude_trainer_ids:
                    continue
                trainers_by_loc[t["location"]].append(dict(t))

            # 1. 空き枠のある厩舎を優先探索
            for loc in priority_locations:
                candidates = trainers_by_loc.get(loc, [])
                vacant = [t for t in candidates if (t["horse_capacity"] - t["current_count"]) > 0]
                if vacant:
                    chosen = random.choice(vacant)
                    return chosen["trainer_id"]

            # 2. 空き枠がなければ、拡張可能な厩舎を探索・拡張
            if allow_expansion:
                for loc in priority_locations:
                    candidates = trainers_by_loc.get(loc, [])
                    expandable = [t for t in candidates if t["horse_capacity"] < self.max_capacity]
                    if expandable:
                        chosen = random.choice(expandable)
                        self.expand_capacity(chosen["trainer_id"])
                        return chosen["trainer_id"]

        return None

    def transfer_horse(
        self,
        horse_id: int,
        from_trainer_id: int,
        to_trainer_id: int,
        reason: str = "transfer",
    ) -> Optional[TransferRecordStable]:
        """馬を他厩舎へ転厩させる。※所属馬ゼロ防止（最低1頭保証）"""
        with self.db.session() as conn:
            # 元厩舎の所属頭数を確認（最低1頭保証）
            cnt = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE trainer_id = ? AND is_active = 1",
                (from_trainer_id,),
            ).fetchone()[0]

            if cnt <= 1:
                # 0頭になってしまうため転厩中止
                return None

            horse_row = conn.execute("SELECT name FROM horses WHERE horse_id = ?", (horse_id,)).fetchone()
            from_row = conn.execute("SELECT name FROM trainers WHERE trainer_id = ?", (from_trainer_id,)).fetchone()
            to_row = conn.execute("SELECT name FROM trainers WHERE trainer_id = ?", (to_trainer_id,)).fetchone()

            conn.execute(
                "UPDATE horses SET trainer_id = ? WHERE horse_id = ?",
                (to_trainer_id, horse_id),
            )

        return TransferRecordStable(
            horse_id=horse_id,
            horse_name=horse_row["name"] if horse_row else f"ID:{horse_id}",
            from_trainer_id=from_trainer_id,
            from_trainer_name=from_row["name"] if from_row else f"Trainer:{from_trainer_id}",
            to_trainer_id=to_trainer_id,
            to_trainer_name=to_row["name"] if to_row else f"Trainer:{to_trainer_id}",
            reason=reason,
        )

    def enroll_horse(self, horse_id: int, target_trainer_id: int) -> Optional[TransferRecordStable]:
        """
        新馬（または未入厩馬）を指定厩舎に入厩させる。
        枠が上限に達している場合は、成績下位馬を他厩舎へ転厩させて枠を空けてから入厩。
        """
        inv = self.get_trainer_inventory(target_trainer_id)
        transfer_record = None

        if inv["total_horses"] >= inv["capacity"]:
            # まず枠拡張を試みる
            if inv["capacity"] < self.max_capacity:
                self.expand_capacity(target_trainer_id)
            else:
                # 枠拡張できない場合は、成績・評価が最も低い馬を1頭他厩舎へ転厩
                candidates = inv["horses"]
                if candidates and len(candidates) > 1:
                    # 賞金が最も少なく、能力の低い馬を後方から選出
                    lowest_horse = candidates[-1]
                    target_stable = self.find_target_stable_for_transfer(
                        from_location=inv["location"],
                        exclude_trainer_ids=[target_trainer_id],
                    )
                    if target_stable:
                        transfer_record = self.transfer_horse(
                            horse_id=lowest_horse["horse_id"],
                            from_trainer_id=target_trainer_id,
                            to_trainer_id=target_stable,
                            reason="capacity_overflow_transfer",
                        )

        # 指定厩舎へ入厩
        with self.db.session() as conn:
            conn.execute(
                "UPDATE horses SET trainer_id = ? WHERE horse_id = ?",
                (target_trainer_id, horse_id),
            )

        return transfer_record

    def progress_year_and_inherit(
        self,
        current_year: int,
        retired_jockeys_by_loc: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        """
        厩舎の年次進行および80歳引退厩舎の引き継ぎ処理:
        1. 全現役厩舎の年齢(age)と開業年数(trainer_years)を+1、当年勝利数をリセット
        2. 80歳到達（開業30年満了）の調教師が引退
        3. 同年に50歳で引退した現役騎手（東西各1名）が、引退厩舎を1対1で完全継承
           - 厩舎名を新調教師の苗字（[苗字]厩舎）に更新（重複時はフルネームでユニーク化）
           - age = 50, trainer_years = 1, former_jockey_id = 引退騎手ID
           - 開業年 = current_year, 個人通算成績をリセット (0勝, 0円)
           - 管理馬・管理枠はそのまま引き継ぎ（馬の散逸・消失ゼロ保証）
        """
        retired_trainers: List[Dict[str, Any]] = []
        inherited_stables: List[Dict[str, Any]] = []
        name_gen = PersonNameGenerator()

        if retired_jockeys_by_loc is None:
            retired_jockeys_by_loc = {"美浦": [], "栗東": []}

        with self.db.session() as conn:
            # 既存の厩舎名を取得
            existing_names = {r["name"] for r in conn.execute("SELECT name FROM trainers").fetchall()}
            for n in existing_names:
                name_gen.register_trainer_name(n)

            # 1. 全厩舎の年齢・開業年数を+1
            rows = conn.execute("SELECT * FROM trainers ORDER BY trainer_id").fetchall()

            stables_retiring_by_loc: Dict[str, List[Dict[str, Any]]] = {"美浦": [], "栗東": []}

            for r in rows:
                new_age = r["age"] + 1
                new_years = r["trainer_years"] + 1

                if new_age >= 80 or new_years > 30:
                    # 80歳引退
                    stables_retiring_by_loc[r["location"]].append({
                        "trainer_id": r["trainer_id"],
                        "old_name": r["name"],
                        "location": r["location"],
                        "age": new_age,
                        "trainer_years": new_years,
                        "career_wins": r["career_wins"],
                        "g1_wins": r["g1_wins"],
                    })
                    retired_trainers.append(stables_retiring_by_loc[r["location"]][-1])
                else:
                    # 現役継続
                    conn.execute(
                        """
                        UPDATE trainers 
                        SET age = ?, trainer_years = ?, current_year_wins = 0 
                        WHERE trainer_id = ?
                        """,
                        (new_age, new_years, r["trainer_id"]),
                    )

            # 2. 80歳引退厩舎を、50歳引退騎手が継承
            for loc in ["美浦", "栗東"]:
                ret_stables = stables_retiring_by_loc[loc]
                candidates_jockey = list(retired_jockeys_by_loc.get(loc, []))

                for s_info in ret_stables:
                    t_id = s_info["trainer_id"]
                    former_jockey_id = None
                    new_trainer_name = None

                    if candidates_jockey:
                        j_info = candidates_jockey.pop(0)
                        former_jockey_id = j_info["jockey_id"]
                        j_name = j_info["name"]
                        base_name = name_gen.get_stable_name_from_jockey(j_name)

                        # 重複チェック
                        check_dup = conn.execute(
                            "SELECT 1 FROM trainers WHERE name = ? AND trainer_id != ?",
                            (base_name, t_id),
                        ).fetchone()
                        if check_dup:
                            # 苗字重複時はフルネームまたは数字付与
                            clean_j_name = j_name.replace(" ", "")
                            new_trainer_name = f"{clean_j_name}厩舎"
                        else:
                            new_trainer_name = base_name
                    else:
                        # 万が一引退騎手がいない場合の安全策: 新規調教師を生成
                        new_trainer_name = name_gen.generate_trainer_name()

                    # 厩舎の継承アップデート
                    conn.execute(
                        """
                        UPDATE trainers 
                        SET name = ?, age = 50, trainer_years = 1, former_jockey_id = ?,
                            created_year = ?, career_wins = 0, career_earnings = 0,
                            g1_wins = 0, current_year_wins = 0
                        WHERE trainer_id = ?
                        """,
                        (new_trainer_name, former_jockey_id, current_year, t_id),
                    )

                    inherited_stables.append({
                        "trainer_id": t_id,
                        "old_name": s_info["old_name"],
                        "new_name": new_trainer_name,
                        "location": loc,
                        "former_jockey_id": former_jockey_id,
                    })

        return {
            "retired_trainers_count": len(retired_trainers),
            "retired_trainers": retired_trainers,
            "inherited_stables_count": len(inherited_stables),
            "inherited_stables": inherited_stables,
        }
