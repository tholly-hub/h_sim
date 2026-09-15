"""
ライフサイクル管理モジュール (Lifecycle Engine)
年進行（加齢・能力推移）、2歳新馬入厩、8歳末競走馬引退、種牡馬・繁殖牝馬昇格、
騎手・厩舎世代交代（50歳開業・80歳引退承継・30年騎手現役）、牧場拡張・譲渡・動的分化
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Set, Tuple

from src.db.database import Database
from src.generators.name_generator import PersonNameGenerator
from src.management.jockey_manager import JockeyManager
from src.models.horse import GrowthType
from src.models.trainer import Trainer


class LifecycleEngine:
    """年進行およびライフサイクル総合エンジン"""

    MAX_RACING_AGE: int = 8             # 現役競走馬の上限年齢（8歳末引退、9歳以上は現役不可）
    TRAINER_OPEN_AGE: int = 50          # 調教師開業年齢
    TRAINER_RETIRE_AGE: int = 80        # 調教師定年引退年齢
    FARM_DEFAULT_CAPACITY: int = 15     # 牧場初期収容頭数
    FARM_MAX_CAPACITY: int = 30         # 牧場拡張上限

    def __init__(self, db: Database):
        self.db = db
        self.person_name_gen = PersonNameGenerator()
        self.jockey_mgr = JockeyManager(db=db, quota_miho=45, quota_ritto=45)

    def advance_year(self, current_year: int, strict_free_jockey: bool = True) -> Dict[str, Any]:
        """
        1年を進行させ、加齢・引退・入厩・世代交代・牧場動的分化を実行
        """
        next_year = current_year + 1
        print(f"\n==================== 【{current_year}年度 -> {next_year}年度 年進行処理】 ====================")

        with self.db.session() as conn:
            # 1. 馬の加齢 (全頭 age += 1)
            print("[年進行] 1/7: 生存全馬の加齢（age + 1）および古馬の発揮能力推移を計算中...")
            conn.execute("UPDATE horses SET age = age + 1")

            # 2. 古馬の能力発揮率の推移
            horses = conn.execute(
                "SELECT horse_id, age, peak_age, growth_type, speed, stamina, acceleration FROM horses"
            ).fetchall()

            for h in horses:
                age = h["age"]
                peak = h["peak_age"]
                if age < peak:
                    rate = max(0.4, 0.6 + 0.4 * (age / peak))
                else:
                    rate = max(0.4, 1.0 - 0.10 * (age - peak))
                conn.execute(
                    "UPDATE horses SET current_ability_rate = ? WHERE horse_id = ?",
                    (round(rate, 2), h["horse_id"]),
                )

            # 3. 8歳末現役競走馬の引退処理 (9歳以上は現役不可)
            retired_horses = conn.execute(
                """
                SELECT horse_id, name, sex, breeder_id, owner_id, g1_wins, g2_wins, g3_wins,
                       career_wins, prize_money, speed, stamina, acceleration, sire_id
                FROM horses
                WHERE is_active = 1 AND age > ?
                """,
                (self.MAX_RACING_AGE,),
            ).fetchall()

            print(f"[年進行] 2/7: 8歳末現役競走馬の引退処理（対象: {len(retired_horses)}頭、種牡馬・繁殖昇格判定）中...")

            new_sires_count = 0
            new_dams_count = 0

            for h in retired_horses:
                h_id = h["horse_id"]
                conn.execute("UPDATE horses SET is_active = 0, trainer_id = NULL, jockey_id = NULL WHERE horse_id = ?", (h_id,))

                if h["sex"] in ("horse", "colt"):
                    is_top_class = (h["g1_wins"] > 0 or h["g2_wins"] > 0 or h["career_wins"] >= 5 or (h["speed"] + h["stamina"]) > 120.0)
                    if is_top_class:
                        p_sire_line = None
                        if h["sire_id"]:
                            s_row = conn.execute("SELECT sire_line FROM sires WHERE horse_id = ?", (h["sire_id"],)).fetchone()
                            if s_row:
                                p_sire_line = s_row["sire_line"]
                        if not p_sire_line:
                            p_sire_line = f"{h['name']}系"

                        conn.execute("UPDATE horses SET is_sire = 1 WHERE horse_id = ?", (h_id,))
                        conn.execute(
                            """
                            INSERT INTO sires (horse_id, breeder_id, sire_line, max_coverings, stud_fee, is_active)
                            VALUES (?, ?, ?, 30, ?, 1)
                            """,
                            (h_id, h["breeder_id"], p_sire_line, (random.randint(1_500_000, 6_000_000) // 100_000) * 100_000),
                        )
                        new_sires_count += 1
                        print(f"    - 【種牡馬入り】{h['name']} (牡8歳・重賞{h['g1_wins']+h['g2_wins']+h['g3_wins']}勝) -> {p_sire_line}を継承")
                elif h["sex"] in ("mare", "filly"):
                    conn.execute("UPDATE horses SET is_dam = 1 WHERE horse_id = ?", (h_id,))
                    conn.execute(
                        "INSERT INTO dams (horse_id, breeder_id, is_active) VALUES (?, ?, 1)",
                        (h_id, h["breeder_id"]),
                    )
                    new_dams_count += 1

            print(f"    ※ 8歳現役馬 {len(retired_horses)}頭 引退完了（新種牡馬: {new_sires_count}頭 / 新繁殖牝馬: {new_dams_count}頭）")

            # 4. 2歳新馬の現役デビュー・厩舎入厩（自厩舎の所属騎手を基本主戦に設定）
            debut_horses = conn.execute(
                """
                SELECT horse_id, name, sex, speed, stamina, acceleration, growth_type
                FROM horses
                WHERE age = 2 AND is_active = 0 AND is_sire = 0 AND is_dam = 0
                ORDER BY (speed + stamina + acceleration) DESC
                """
            ).fetchall()

            print(f"[年進行] 3/7: 2歳新馬（{len(debut_horses)}頭）の美浦・栗東厩舎への入厩および主戦騎手配分中...")

            # 厩舎の取得 (美浦・栗東 計60厩舎)
            trainers = conn.execute(
                """
                SELECT trainer_id, location, specialty
                FROM trainers
                """
            ).fetchall()

            trainer_counts: Dict[int, int] = {}
            for t in trainers:
                cnt = conn.execute("SELECT COUNT(*) FROM horses WHERE trainer_id = ? AND is_active = 1", (t["trainer_id"],)).fetchone()[0]
                trainer_counts[t["trainer_id"]] = cnt

            # 各厩舎の所属騎手マップ
            stable_jockey_map: Dict[int, int] = {}
            j_active = conn.execute("SELECT jockey_id, trainer_id, is_free FROM jockeys WHERE is_active = 1").fetchall()
            for jr in j_active:
                if jr["trainer_id"] is not None:
                    stable_jockey_map[jr["trainer_id"]] = jr["jockey_id"]

            free_jockeys = [jr["jockey_id"] for jr in j_active if jr["is_free"] == 1]

            debut_count = 0
            for idx, h in enumerate(debut_horses):
                sorted_trainers = sorted(trainers, key=lambda t: trainer_counts[t["trainer_id"]])
                target_trainer = sorted_trainers[0]
                t_id = target_trainer["trainer_id"]

                # 主戦騎手の配分: 有力新馬はフリー騎手も考慮、基本は自厩舎の所属騎手
                assigned_jockey = None
                if idx < (len(debut_horses) // 10) and free_jockeys and (idx % 2 == 0):
                    assigned_jockey = free_jockeys[idx % len(free_jockeys)]
                elif t_id in stable_jockey_map:
                    assigned_jockey = stable_jockey_map[t_id]
                elif free_jockeys:
                    assigned_jockey = free_jockeys[idx % len(free_jockeys)]

                conn.execute(
                    """
                    UPDATE horses
                    SET is_active = 1, trainer_id = ?, jockey_id = ?
                    WHERE horse_id = ?
                    """,
                    (t_id, assigned_jockey, h["horse_id"]),
                )
                trainer_counts[t_id] += 1
                debut_count += 1

            print(f"    ※ 新馬 {debut_count}頭 が美浦・栗東の全60厩舎へ入厩・現役登録完了。")

            # 5. 騎手の世代交代・成長・体力減衰・多段階引退・調教助手転身 & 新人騎手補充
            print("[年進行] 4/7: 騎手の世代交代判定中（多段階引退・調教助手転身・フリー化・18歳新人デビュー）...")
            jockey_progress_result = self.jockey_mgr.progress_year_and_maintain_quota(
                current_year=current_year, strict_free=strict_free_jockey, conn=conn
            )
            ret_jockeys = jockey_progress_result["retired_jockeys"]
            promoted_free = jockey_progress_result["promoted_free_jockeys"]
            new_rookies = jockey_progress_result["new_jockeys"]

            for rj in ret_jockeys:
                print(f"    - 【騎手引退】{rj['name']} ({rj['age']}歳・通算{rj['career_wins']}勝/G1:{rj['g1_wins']}勝) 引退理由: {rj['reason']}")
            for pf in promoted_free:
                print(f"    - 【フリー転向】{pf['name']} (通算{pf['career_wins']}勝/G1:{pf['g1_wins']}勝) がフリー騎手へ転向！")
            for nr in new_rookies:
                print(f"    - 【新人デビュー】{nr.name} (18歳・{nr.location}) デビュー（定員90名維持）")

            # 6. 厩舎（調教師）のスキル向上 & 世代交代判定（80歳定年引退・調教助手/有力フリー騎手承継）
            print("[年進行] 5/7: 厩舎（調教師）のスキル向上および世代交代判定（80歳定年・調教助手/有力騎手承継）...")
            
            # 調教師の加齢 & スキル向上
            t_rows = conn.execute("SELECT * FROM trainers").fetchall()
            for tr in t_rows:
                t = Trainer.from_row(tr)
                new_skill = t.calculate_skill_growth(
                    wins_this_year=t.current_year_wins,
                    g1_this_year=t.current_year_g1,
                    g2_this_year=t.current_year_g2,
                    g3_this_year=t.current_year_g3,
                )
                conn.execute(
                    "UPDATE trainers SET age = age + 1, trainer_years = trainer_years + 1, skill_level = ? WHERE trainer_id = ?",
                    (new_skill, t.trainer_id),
                )

            retired_trainers = conn.execute(
                "SELECT trainer_id, name, location, age FROM trainers WHERE age >= ?",
                (self.TRAINER_RETIRE_AGE,),
            ).fetchall()

            existing_trainer_names: Set[str] = set(r["name"] for r in conn.execute("SELECT name FROM trainers").fetchall())

            # 有力な引退フリー騎手の抽出（この年に引退したフリー騎手で通算100勝以上またはG1勝ち）
            top_retired_free_jockeys = [
                rj for rj in ret_jockeys 
                if (rj.get("trainer_id") is None and (rj["career_wins"] >= 100 or rj["g1_wins"] >= 1))
            ]

            for t in retired_trainers:
                t_id = t["trainer_id"]
                succ_jockey_id = None
                initial_skill = 50.0
                succ_reason = ""

                # 優先1: 有力な引退フリー騎手（自厩舎に調教助手がいない場合、または優先割当）
                # 自厩舎所属の調教助手をチェック
                assistants = conn.execute(
                    """
                    SELECT assistant_id, jockey_id, name, age, career_wins, g1_wins 
                    FROM assistant_trainers 
                    WHERE trainer_id = ? AND is_active = 1
                    ORDER BY career_wins DESC, g1_wins DESC, age ASC
                    """,
                    (t_id,),
                ).fetchall()

                if top_retired_free_jockeys and not assistants:
                    top_free = top_retired_free_jockeys.pop(0)
                    succ_jockey_id = top_free["jockey_id"]
                    succ_name = PersonNameGenerator.get_stable_name_from_jockey(
                        top_free["name"], existing_names=existing_trainer_names
                    )
                    # フリー騎手実績に応じた初期厩舎スキルボーナス
                    initial_skill = round(50.0 + min(25.0, top_free["career_wins"] * 0.05 + top_free["g1_wins"] * 2.0), 1)
                    succ_reason = f"引退有力フリー騎手 {top_free['name']} (通算{top_free['career_wins']}勝/G1:{top_free['g1_wins']}勝) が承継"
                elif assistants:
                    # 優先2: 自厩舎所属の調教助手
                    top_asst = assistants[0]
                    succ_jockey_id = top_asst["jockey_id"]
                    succ_name = PersonNameGenerator.get_stable_name_from_jockey(
                        top_asst["name"], existing_names=existing_trainer_names
                    )
                    # 調教助手退任
                    conn.execute("UPDATE assistant_trainers SET is_active = 0 WHERE assistant_id = ?", (top_asst["assistant_id"],))
                    # 実績に応じた初期スキル
                    initial_skill = round(50.0 + min(18.0, top_asst["career_wins"] * 0.04 + top_asst["g1_wins"] * 1.5), 1)
                    succ_reason = f"自厩舎調教助手 {top_asst['name']} ({top_asst['age']}歳・通算{top_asst['career_wins']}勝) が承継"
                else:
                    # 優先3: 新規調教師
                    while True:
                        cand = self.person_name_gen.generate_trainer_name()
                        if cand not in existing_trainer_names:
                            succ_name = cand
                            break
                    initial_skill = 50.0
                    succ_reason = f"新調教師 {succ_name} (50歳) が新規就任"

                existing_trainer_names.add(succ_name)
                self.person_name_gen.register_trainer_name(succ_name)

                # 厩舎の事業承継登録
                conn.execute(
                    """
                    UPDATE trainers
                    SET name = ?, age = 50, trainer_years = 1, former_jockey_id = ?, skill_level = ?,
                        current_year_starts = 0, current_year_wins = 0, current_year_g1 = 0,
                        current_year_g2 = 0, current_year_g3 = 0, current_year_earnings = 0,
                        career_starts = 0, career_wins = 0, g1_wins = 0, g2_wins = 0, g3_wins = 0, career_earnings = 0
                    WHERE trainer_id = ?
                    """,
                    (succ_name, succ_jockey_id, initial_skill, t_id),
                )
                print(f"    - 【厩舎承継】{t['name']} (80歳定年引退) -> {succ_name} (初期スキル: {initial_skill}) / {succ_reason}")

            # 6. 生産牧場の動的分化・譲渡・拡張
            print("[年進行] 6/7: 生産牧場の動的収容バランス調整（最低1頭保証・あふれ移籍）中...")
            self._balance_breeders(conn)

            # 7. 当年（年度）成績リセット
            print("[年進行] 7/7: 各種当年成績のリセット（通算成績は保持・累積）中...")
            conn.execute(
                """
                UPDATE trainers
                SET current_year_starts = 0, current_year_wins = 0, current_year_g1 = 0,
                    current_year_g2 = 0, current_year_g3 = 0, current_year_earnings = 0
                """
            )
            conn.execute(
                """
                UPDATE jockeys
                SET current_year_starts = 0, current_year_wins = 0, current_year_g1 = 0,
                    current_year_g2 = 0, current_year_g3 = 0, current_year_earnings = 0
                """
            )
            conn.execute(
                """
                UPDATE breeders
                SET current_year_starts = 0, current_year_wins = 0, current_year_g1 = 0,
                    current_year_g2 = 0, current_year_g3 = 0, current_year_earnings = 0
                """
            )

        print(f"【年進行 完了】{current_year}年度から {next_year}年度 への移行処理がすべて正常に完了しました！")
        print("=================================================================================\n")
        return {
            "advanced_to_year": next_year,
            "retired_horses": len(retired_horses),
            "debut_horses": debut_count,
            "new_sires": new_sires_count,
            "new_dams": new_dams_count,
        }

    def _balance_breeders(self, conn) -> None:
        """
        牧場の動的拡張・あふれ移籍・最低条件（種牡馬1頭、繁殖牝馬1頭）保証
        """
        breeders = conn.execute("SELECT breeder_id, name, region FROM breeders").fetchall()

        for b in breeders:
            b_id = b["breeder_id"]
            sire_count = conn.execute(
                "SELECT COUNT(*) FROM sires WHERE breeder_id = ? AND is_active = 1", (b_id,)
            ).fetchone()[0]
            dam_count = conn.execute(
                "SELECT COUNT(*) FROM dams WHERE breeder_id = ? AND is_active = 1", (b_id,)
            ).fetchone()[0]

            total_horses = sire_count + dam_count

            # A. 最低条件の割れ防止（種牡馬1頭、繁殖牝馬1頭）
            if sire_count < 1:
                donor = conn.execute(
                    """
                    SELECT s.sire_id, s.horse_id, s.breeder_id
                    FROM sires s
                    JOIN breeders br ON s.breeder_id = br.breeder_id
                    WHERE s.is_active = 1 AND s.breeder_id != ?
                    ORDER BY (SELECT COUNT(*) FROM sires WHERE breeder_id = s.breeder_id AND is_active = 1) DESC
                    LIMIT 1
                    """,
                    (b_id,),
                ).fetchone()
                if donor:
                    conn.execute("UPDATE sires SET breeder_id = ? WHERE sire_id = ?", (b_id, donor["sire_id"]))
                    conn.execute("UPDATE horses SET breeder_id = ? WHERE horse_id = ?", (b_id, donor["horse_id"]))

            if dam_count < 1:
                donor = conn.execute(
                    """
                    SELECT d.dam_id, d.horse_id, d.breeder_id
                    FROM dams d
                    JOIN breeders br ON d.breeder_id = br.breeder_id
                    WHERE d.is_active = 1 AND d.breeder_id != ?
                    ORDER BY (SELECT COUNT(*) FROM dams WHERE breeder_id = d.breeder_id AND is_active = 1) DESC
                    LIMIT 1
                    """,
                    (b_id,),
                ).fetchone()
                if donor:
                    conn.execute("UPDATE dams SET breeder_id = ? WHERE dam_id = ?", (b_id, donor["dam_id"]))
                    conn.execute("UPDATE horses SET breeder_id = ? WHERE horse_id = ?", (b_id, donor["horse_id"]))

            # B. 枠あふれ移籍 (上限30頭を超過した場合、近隣牧場へ移籍)
            if total_horses > self.FARM_MAX_CAPACITY:
                excess = total_horses - self.FARM_MAX_CAPACITY
                excess_dams = conn.execute(
                    "SELECT dam_id, horse_id FROM dams WHERE breeder_id = ? AND is_active = 1 LIMIT ?",
                    (b_id, excess),
                ).fetchall()

                neighbor = conn.execute(
                    """
                    SELECT breeder_id
                    FROM breeders
                    WHERE breeder_id != ? AND region = ?
                    ORDER BY (SELECT COUNT(*) FROM dams WHERE breeder_id = breeders.breeder_id) ASC
                    LIMIT 1
                    """,
                    (b_id, b["region"]),
                ).fetchone()
                target_b_id = neighbor["breeder_id"] if neighbor else random.choice([x["breeder_id"] for x in breeders if x["breeder_id"] != b_id])

                for ed in excess_dams:
                    conn.execute("UPDATE dams SET breeder_id = ? WHERE dam_id = ?", (target_b_id, ed["dam_id"]))
                    conn.execute("UPDATE horses SET breeder_id = ? WHERE horse_id = ?", (target_b_id, ed["horse_id"]))
