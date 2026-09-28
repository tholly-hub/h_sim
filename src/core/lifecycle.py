"""
ライフサイクル管理モジュール (Lifecycle Engine)
年進行（加齢・能力推移）、2歳新馬入厩、8歳末競走馬引退、種牡馬・繁殖牝馬昇格、
騎手・厩舎世代交代（50歳開業・80歳引退承継・30年騎手現役）、牧場拡張・譲渡・動的分化
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Set, Tuple

from src.db.database import Database
from src.generators.name_generator import HorseNameGenerator, PersonNameGenerator
from src.management.jockey_manager import JockeyManager
from src.models.horse import GrowthType
from src.models.trainer import Trainer


class LifecycleEngine:
    """年進行およびライフサイクル総合エンジン"""

    MAX_RACING_AGE: int = 7             # 現役競走馬の上限年齢（7歳末引退、8歳以上は現役不可）
    TRAINER_OPEN_AGE: int = 60          # 調教師開業年齢 (60歳)
    TRAINER_RETIRE_AGE: int = 80        # 調教師定年引退年齢
    FARM_DEFAULT_CAPACITY: int = 15     # 牧場初期収容頭数
    FARM_MAX_CAPACITY: int = 30         # 牧場拡張上限
    BROODMARE_TARGET_COUNT: int = 600   # 繁殖牝馬の年間目標維持頭数
    SIRE_MAX_CAPACITY: int = 120        # 種牡馬の最大頭数上限 (120頭)

    def __init__(self, db: Database):
        self.db = db
        self.horse_name_gen = HorseNameGenerator()
        self.person_name_gen = PersonNameGenerator()
        self.jockey_mgr = JockeyManager(db=db, quota_miho=45, quota_ritto=45)
        self._ensure_columns_exist()

    def _ensure_columns_exist(self) -> None:
        """sires / dams / horses テーブルに必要なPhase8および世代管理カラムが存在することを確認"""
        with self.db.session() as conn:
            try:
                s_cols = [c[1] for c in conn.execute("PRAGMA table_info(sires)").fetchall()]
                if "is_imported" not in s_cols:
                    conn.execute("ALTER TABLE sires ADD COLUMN is_imported INTEGER NOT NULL DEFAULT 0")
                if "debut_year" not in s_cols:
                    conn.execute("ALTER TABLE sires ADD COLUMN debut_year INTEGER NOT NULL DEFAULT 1")
                if "generation" not in s_cols:
                    conn.execute("ALTER TABLE sires ADD COLUMN generation INTEGER NOT NULL DEFAULT 1")
            except Exception:
                pass
            try:
                d_cols = [c[1] for c in conn.execute("PRAGMA table_info(dams)").fetchall()]
                if "debut_year" not in d_cols:
                    conn.execute("ALTER TABLE dams ADD COLUMN debut_year INTEGER NOT NULL DEFAULT 1")
                if "generation" not in d_cols:
                    conn.execute("ALTER TABLE dams ADD COLUMN generation INTEGER NOT NULL DEFAULT 1")
            except Exception:
                pass
            try:
                h_cols = [c[1] for c in conn.execute("PRAGMA table_info(horses)").fetchall()]
                if "generation" not in h_cols:
                    conn.execute("ALTER TABLE horses ADD COLUMN generation INTEGER NOT NULL DEFAULT 1")
            except Exception:
                pass

            # 世代番号（generation）の整合性を自動修復
            try:
                # 始祖（親なし）は generation = 1
                conn.execute("UPDATE horses SET generation = 1 WHERE (sire_id IS NULL AND dam_id IS NULL) AND generation != 1")
                # 父種牡馬から再帰的に世代番号を確実に同期（最大10世代まで伝播）
                for _ in range(10):
                    conn.execute("""
                        UPDATE horses
                        SET generation = (
                            CASE
                                WHEN horses.sire_id IS NULL THEN 1
                                WHEN (SELECT s.sire_id FROM horses s WHERE s.horse_id = horses.sire_id) IS NULL THEN 1
                                ELSE (SELECT s.generation + 1 FROM horses s WHERE s.horse_id = horses.sire_id)
                            END
                        )
                        WHERE (sire_id IS NOT NULL OR dam_id IS NOT NULL)
                          AND generation != (
                            CASE
                                WHEN horses.sire_id IS NULL THEN 1
                                WHEN (SELECT s.sire_id FROM horses s WHERE s.horse_id = horses.sire_id) IS NULL THEN 1
                                ELSE (SELECT s.generation + 1 FROM horses s WHERE s.horse_id = horses.sire_id)
                            END
                        )
                    """)
                # sires, dams テーブルと同期
                conn.execute("UPDATE sires SET generation = (SELECT generation FROM horses WHERE horses.horse_id = sires.horse_id)")
                conn.execute("UPDATE dams SET generation = (SELECT generation FROM horses WHERE horses.horse_id = dams.horse_id)")
            except Exception as e:
                print(f"[警告] 世代番号同期中に例外が発生しました: {e}")

    def advance_year(self, current_year: int, strict_free_jockey: bool = True) -> Dict[str, Any]:
        """
        1年を進行させ、加齢・引退・入厩・世代交代・牧場動的分化を実行
        """
        next_year = current_year + 1
        print(f"\n==================== 【{current_year}年度 -> {next_year}年度 年進行処理】 ====================")

        with self.db.session() as conn:
            # 1. 馬の加齢 (全頭 age += 1)
            print("[年進行] 1/8: 生存全馬の加齢（age + 1）および古馬の発揮能力推移を計算中...")
            conn.execute("UPDATE horses SET age = age + 1")

            # 2. 古馬の能力発揮率の推移（成長型・年齢曲線 ＋ 所属調教師スキルボーナス）
            horses = conn.execute(
                """
                SELECT h.horse_id, h.age, h.sex, h.peak_age, h.growth_type, h.trainer_id,
                       t.skill_level as trainer_skill
                FROM horses h
                LEFT JOIN trainers t ON h.trainer_id = t.trainer_id
                """
            ).fetchall()

            for h in horses:
                age = h["age"]
                growth_type = h["growth_type"]
                sex = h["sex"]
                peak = h["peak_age"] if h["peak_age"] else 4.5

                # 牝馬は早熟傾向、牡馬は古馬になってから活躍する傾向
                is_female = sex in ("mare", "filly", "牝")

                # 成長型別ベース発揮率カーブ（馬自身の加齢成長によるタイム短縮幅を約1.5〜2.5秒程度に緩和し、世代交代のウェイトを主因とする）
                if growth_type == GrowthType.EARLY.value or growth_type == "early":
                    if age <= 2:
                        base_rate = 0.96 if is_female else 0.94
                    elif age == 3:
                        base_rate = 1.00
                    elif age == 4:
                        base_rate = 0.98 if is_female else 0.99
                    elif age == 5:
                        base_rate = 0.95 if is_female else 0.96
                    elif age == 6:
                        base_rate = 0.91 if is_female else 0.93
                    else:
                        base_rate = max(0.75, 0.91 - 0.05 * (age - 6))
                elif growth_type == GrowthType.LATE.value or growth_type == "late":
                    if age <= 2:
                        base_rate = 0.90 if is_female else 0.88
                    elif age == 3:
                        base_rate = 0.95 if is_female else 0.93
                    elif age == 4:
                        base_rate = 0.98 if is_female else 0.97
                    elif age in (5, 6):
                        base_rate = 1.00
                    elif age == 7:
                        base_rate = 0.96 if is_female else 0.97
                    else:
                        base_rate = max(0.75, 0.96 - 0.05 * (age - 7))
                else:
                    if age <= 2:
                        base_rate = 0.93 if is_female else 0.91
                    elif age == 3:
                        base_rate = 0.98 if is_female else 0.96
                    elif age in (4, 5):
                        base_rate = 1.00
                    elif age == 6:
                        base_rate = 0.96 if is_female else 0.97
                    elif age == 7:
                        base_rate = 0.91 if is_female else 0.93
                    else:
                        base_rate = max(0.75, 0.91 - 0.05 * (age - 7))

                trainer_bonus = 0.0
                if h["trainer_skill"] is not None:
                    trainer_bonus = (float(h["trainer_skill"]) - 50.0) / 100.0 * 0.04

                final_rate = round(min(1.05, max(0.70, base_rate + trainer_bonus)), 2)
                conn.execute(
                    "UPDATE horses SET current_ability_rate = ? WHERE horse_id = ?",
                    (final_rate, h["horse_id"]),
                )

            # 3. 競走馬引退判定
            # - 3歳末(加齢後age==4): 足切りなし(3歳9月4週の未勝利引退のみ)
            # - 4歳末(加齢後age==5): 条件馬は100%引退。オープン馬は成績推移・成長曲線に応じて引退
            # - 5歳末(加齢後age==6): 牝馬は100%全頭引退。牡馬条件馬は引退、牡馬オープン馬は成績推移・成長曲線に応じて引退
            # - 6歳末(加齢後age==7): 成績推移・成長曲線に応じて引退判断
            # - 7歳末(加齢後age>=8): 100%全頭引退 (MAX_RACING_AGE = 7)
            active_koba = conn.execute(
                """
                SELECT horse_id, name, sex, age, peak_age, current_ability_rate,
                       breeder_id, owner_id, g1_wins, g2_wins, g3_wins,
                       career_wins, career_starts, prize_money, condition_prize_money,
                       speed, stamina, acceleration, maternal_vitality, sire_id, generation
                FROM horses
                WHERE is_active = 1 AND age >= 4
                """
            ).fetchall()

            retired_horse_ids = set()
            retired_horses = []

            for h in active_koba:
                age = h["age"]
                sex = h["sex"]
                wins = h["career_wins"] or 0
                cond_prize = h["condition_prize_money"] or 0
                is_open = (
                    (h["g1_wins"] or 0) > 0
                    or (h["g2_wins"] or 0) > 0
                    or (h["g3_wins"] or 0) > 0
                    or (wins >= 4)
                    or (cond_prize >= 16_000_000)
                )
                is_female = sex in ("mare", "filly", "牝")

                # (1) 7歳末超過（加齢後8歳以上）は100%全頭引退
                if age > self.MAX_RACING_AGE:
                    retired_horse_ids.add(h["horse_id"])
                    retired_horses.append(h)
                    continue

                # (2) 3歳末（加齢後4歳）は年末引退なし（3歳9月4週の未勝利引退のみ）
                if age == 4:
                    continue

                peak = h["peak_age"] if h["peak_age"] else 4.5
                rate = h["current_ability_rate"] if h["current_ability_rate"] else 0.80
                # 加齢前の実年齢でピークアウト判定 (age - 1)
                real_age = age - 1
                is_peak_out = (real_age >= peak + 1.0) or (rate < 0.75)

                # (3) 4歳末（加齢後5歳）: 条件クラスは100%引退、オープン馬は成績・成長曲線に応じて引退
                if age == 5:
                    if not is_open:
                        retired_horse_ids.add(h["horse_id"])
                        retired_horses.append(h)
                        continue
                    else:
                        retire_prob = 0.70 if rate < 0.65 else (0.40 if is_peak_out else 0.05)
                        if random.random() < retire_prob:
                            retired_horse_ids.add(h["horse_id"])
                            retired_horses.append(h)
                            continue

                # (4) 5歳末（加齢後6歳）: 牝馬は100%全頭引退、牡馬条件馬は100%引退、牡馬オープン馬は成績・成長曲線に応じ判断
                if age == 6:
                    if is_female or (not is_open):
                        retired_horse_ids.add(h["horse_id"])
                        retired_horses.append(h)
                        continue
                    else:
                        retire_prob = 0.85 if rate < 0.65 else (0.65 if is_peak_out else 0.20)
                        if random.random() < retire_prob:
                            retired_horse_ids.add(h["horse_id"])
                            retired_horses.append(h)
                            continue

                # (5) 6歳末（加齢後7歳）: 条件馬は引退、オープン馬は成績・成長曲線に応じ判断
                if age == 7:
                    if not is_open:
                        retired_horse_ids.add(h["horse_id"])
                        retired_horses.append(h)
                        continue
                    else:
                        retire_prob = 0.85 if is_peak_out else 0.50
                        if random.random() < retire_prob:
                            retired_horse_ids.add(h["horse_id"])
                            retired_horses.append(h)
                            continue

            print(f"[年進行] 2/8: 現役競走馬の引退処理（引退頭数: {len(retired_horses)}頭）...")

            for h in retired_horses:
                conn.execute(
                    "UPDATE horses SET is_active = 0, retired_year = ? WHERE horse_id = ?",
                    (current_year, h["horse_id"]),
                )

            # 4. 種牡馬の新陳代謝・引退・選定 & 海外種牡馬導入 (Phase 8)
            print("[年進行] 3/8: 種牡馬の引退判定および新種牡馬・海外種牡馬の選定中...")
            new_sires_count = self._manage_sire_roster(conn, current_year, retired_horses)

            # 5. 繁殖牝馬の定員600頭維持 & 入れ替えルール (Phase 8: ルールA/B/C/D)
            print("[年進行] 4/8: 繁殖牝馬の定員600頭維持および入れ替え処理（ルールA〜D）中...")
            new_dams_count = self._manage_broodmare_roster(conn, current_year, retired_horses)

            # 4. 2歳新馬の現役デビュー・厩舎ドラフト入厩
            # 厩舎は馬の真の個体値を知ることはできず、種牡馬・繁殖牝馬の血統期待値＋種付料＋評判（観測ノイズ）から評価して指名
            # 2年目以降は、厩舎の実績（前年勝率・重賞勝数・スキル）の高い厩舎から優先的に評判馬を獲得
            debut_horses_raw = conn.execute(
                """
                SELECT h.horse_id, h.name, h.sex, h.sire_id, h.dam_id,
                       s_h.speed as sire_spd, s_h.stamina as sire_sta, s_h.acceleration as sire_acc,
                       s.stud_fee as sire_fee,
                       d_h.speed as dam_spd, d_h.stamina as dam_sta, d_h.acceleration as dam_acc
                FROM horses h
                LEFT JOIN horses s_h ON h.sire_id = s_h.horse_id
                LEFT JOIN sires s ON h.sire_id = s.horse_id
                LEFT JOIN horses d_h ON h.dam_id = d_h.horse_id
                WHERE h.age = 2 AND h.is_active = 0 AND h.is_sire = 0 AND h.is_dam = 0
                """
            ).fetchall()

            # 血統期待値スコアの算出（厩舎から見た評価額・評判スコア）
            evaluated_horses = []
            for dh in debut_horses_raw:
                sire_ability = (
                    (dh["sire_spd"] or 50.0) + (dh["sire_sta"] or 50.0) + (dh["sire_acc"] or 50.0)
                ) / 3.0
                dam_ability = (
                    (dh["dam_spd"] or 50.0) + (dh["dam_sta"] or 50.0) + (dh["dam_acc"] or 50.0)
                ) / 3.0
                fee_bonus = ((dh["sire_fee"] or 2_000_000) / 1_000_000) * 1.5
                # 観測ノイズ（血統だけでは測れない個体差の不確実性）
                noise = random.gauss(0.0, 3.5)
                pedigree_score = round(sire_ability * 0.5 + dam_ability * 0.5 + fee_bonus + noise, 2)
                evaluated_horses.append({
                    "horse_id": dh["horse_id"],
                    "name": dh["name"],
                    "pedigree_score": pedigree_score,
                })

            # 評判・血統スコアの高い順にソート
            evaluated_horses.sort(key=lambda x: x["pedigree_score"], reverse=True)

            print(f"[年進行] 3/7: 2歳新馬（{len(evaluated_horses)}頭）の厩舎実績優先ドラフト入厩および主戦騎手配分中...")

            # 厩舎の取得および実績スコア算出（前年勝率、前年重賞、調教師スキル）
            trainers = conn.execute(
                """
                SELECT trainer_id, name, location, skill_level,
                       current_year_starts, current_year_wins, current_year_g1, current_year_g2, current_year_g3,
                       career_starts, career_wins
                FROM trainers
                """
            ).fetchall()

            # 厩舎のドラフト優先度スコア計算
            trainer_priority_list = []
            trainer_counts: Dict[int, int] = {}
            for t in trainers:
                t_id = t["trainer_id"]
                cnt = conn.execute("SELECT COUNT(*) FROM horses WHERE trainer_id = ? AND is_active = 1", (t_id,)).fetchone()[0]
                trainer_counts[t_id] = cnt

                y_starts = t["current_year_starts"]
                y_wins = t["current_year_wins"]
                win_rate = (y_wins / y_starts) if y_starts > 0 else (t["career_wins"] / max(1, t["career_starts"]))
                g_points = t["current_year_g1"] * 5.0 + t["current_year_g2"] * 3.0 + t["current_year_g3"] * 1.5
                skill = float(t["skill_level"])

                # 実績スコア: 勝率 + 重賞実績 + スキル + 微少ゆらぎ
                perf_score = (win_rate * 40.0) + g_points + (skill * 0.4) + random.uniform(-1.0, 1.0)
                trainer_priority_list.append({
                    "trainer_id": t_id,
                    "perf_score": perf_score,
                })

            # 実績上位順にソート（ドラフト指名権順位）
            trainer_priority_list.sort(key=lambda x: x["perf_score"], reverse=True)

            # 各厩舎の所属騎手マップ
            stable_jockey_map: Dict[int, int] = {}
            j_active = conn.execute("SELECT jockey_id, trainer_id, is_free FROM jockeys WHERE is_active = 1").fetchall()
            for jr in j_active:
                if jr["trainer_id"] is not None:
                    stable_jockey_map[jr["trainer_id"]] = jr["jockey_id"]

            free_jockeys = [jr["jockey_id"] for jr in j_active if jr["is_free"] == 1]

            # ラウンドドラフト方式で各厩舎に良血馬・評判馬を優先配分
            # 収容バランスを保ちつつ、実績上位厩舎が血統期待値上位馬を先に選択
            debut_count = 0
            horse_idx = 0
            total_debut = len(evaluated_horses)

            while horse_idx < total_debut:
                # 厩舎の現役所属頭数が少ない順、かつ同頭数の場合は実績スコア上位順に指名
                available_trainers = sorted(
                    trainer_priority_list,
                    key=lambda t: (trainer_counts[t["trainer_id"]], -t["perf_score"])
                )

                for t_info in available_trainers:
                    if horse_idx >= total_debut:
                        break
                    
                    target_horse = evaluated_horses[horse_idx]
                    t_id = t_info["trainer_id"]

                    # 主戦騎手の配分: 上位血統馬は有力フリー騎手も考慮、基本は自厩舎の所属騎手
                    assigned_jockey = None
                    if horse_idx < (total_debut // 10) and free_jockeys and (horse_idx % 2 == 0):
                        assigned_jockey = free_jockeys[horse_idx % len(free_jockeys)]
                    elif t_id in stable_jockey_map:
                        assigned_jockey = stable_jockey_map[t_id]
                    elif free_jockeys:
                        assigned_jockey = free_jockeys[horse_idx % len(free_jockeys)]

                    conn.execute(
                        """
                        UPDATE horses
                        SET is_active = 1, trainer_id = ?, jockey_id = ?
                        WHERE horse_id = ?
                        """,
                        (t_id, assigned_jockey, target_horse["horse_id"]),
                    )
                    trainer_counts[t_id] += 1
                    debut_count += 1
                    horse_idx += 1

            print(f"    ※ 新馬 {debut_count}頭 が厩舎実績優先ドラフトにより全60厩舎へ入厩・現役登録完了。")

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
                "SELECT trainer_id, name, location, age, trainer_years FROM trainers WHERE age >= ? OR trainer_years >= 30",
                (self.TRAINER_RETIRE_AGE,),
            ).fetchall()

            existing_trainer_names: Set[str] = set(r["name"] for r in conn.execute("SELECT name FROM trainers").fetchall())

            # 有力な引退フリー騎手の抽出
            top_retired_free_jockeys = [
                rj for rj in ret_jockeys 
                if ((rj.get("trainer_id") if isinstance(rj, dict) else (rj["trainer_id"] if "trainer_id" in rj.keys() else None)) is None and ((rj["career_wins"] or 0) >= 100 or (rj["g1_wins"] or 0) >= 1))
            ]

            for t in retired_trainers:
                t_id = t["trainer_id"]
                succ_jockey_id = None
                initial_skill = 50.0
                succ_reason = ""

                # 優先1: 引退フリー騎手
                if top_retired_free_jockeys:
                    top_free = top_retired_free_jockeys.pop(0)
                    succ_jockey_id = top_free["jockey_id"]
                    succ_name = PersonNameGenerator.get_stable_name_from_jockey(
                        top_free["name"], existing_names=existing_trainer_names
                    )
                    initial_skill = round(50.0 + min(25.0, top_free["career_wins"] * 0.05 + top_free["g1_wins"] * 2.0), 1)
                    succ_reason = f"引退有力フリー騎手 {top_free['name']} (通算{top_free['career_wins']}勝/G1:{top_free['g1_wins']}勝) が承継"
                else:
                    # 優先2: 自厩舎所属の調教助手
                    assistants = conn.execute(
                        """
                        SELECT assistant_id, jockey_id, name, age, career_wins, g1_wins 
                        FROM assistant_trainers 
                        WHERE trainer_id = ? AND is_active = 1
                        ORDER BY career_wins DESC, g1_wins DESC, age ASC
                        """,
                        (t_id,),
                    ).fetchall()

                    if assistants:
                        top_asst = assistants[0]
                        succ_jockey_id = top_asst["jockey_id"]
                        succ_name = PersonNameGenerator.get_stable_name_from_jockey(
                            top_asst["name"], existing_names=existing_trainer_names
                        )
                        conn.execute("UPDATE assistant_trainers SET is_active = 0 WHERE assistant_id = ?", (top_asst["assistant_id"],))
                        initial_skill = round(50.0 + min(18.0, top_asst["career_wins"] * 0.04 + top_asst["g1_wins"] * 1.5), 1)
                        succ_reason = f"自厩舎調教助手 {top_asst['name']} ({top_asst['age']}歳・通算{top_asst['career_wins']}勝) が承継"
                    else:
                        # 優先3: 他厩舎の調教助手を引き抜き
                        other_assts = conn.execute(
                            """
                            SELECT assistant_id, jockey_id, name, age, career_wins, g1_wins 
                            FROM assistant_trainers 
                            WHERE is_active = 1
                            ORDER BY career_wins DESC, g1_wins DESC, age ASC
                            """
                        ).fetchall()
                        if other_assts:
                            top_asst = other_assts[0]
                            succ_jockey_id = top_asst["jockey_id"]
                            succ_name = PersonNameGenerator.get_stable_name_from_jockey(
                                top_asst["name"], existing_names=existing_trainer_names
                            )
                            conn.execute("UPDATE assistant_trainers SET is_active = 0 WHERE assistant_id = ?", (top_asst["assistant_id"],))
                            initial_skill = round(50.0 + min(18.0, top_asst["career_wins"] * 0.04 + top_asst["g1_wins"] * 1.5), 1)
                            succ_reason = f"他厩舎調教助手 {top_asst['name']} ({top_asst['age']}歳・通算{top_asst['career_wins']}勝) を引き抜いて承継"
                        else:
                            # 優先4: 新規調教師
                            while True:
                                cand = self.person_name_gen.generate_trainer_name()
                                if cand not in existing_trainer_names:
                                    succ_name = cand
                                    break
                            initial_skill = 50.0
                            succ_reason = f"新調教師 {succ_name} (60歳) が新規就任"

                existing_trainer_names.add(succ_name)
                self.person_name_gen.register_trainer_name(succ_name)

                retire_why = "80歳定年引退" if t["age"] >= self.TRAINER_RETIRE_AGE else "開業30年引退"

                # 厩舎の事業承継登録
                conn.execute(
                    """
                    UPDATE trainers
                    SET name = ?, age = 60, trainer_years = 1, former_jockey_id = ?, skill_level = ?,
                        current_year_starts = 0, current_year_wins = 0, current_year_g1 = 0,
                        current_year_g2 = 0, current_year_g3 = 0, current_year_earnings = 0,
                        career_starts = 0, career_wins = 0, g1_wins = 0, g2_wins = 0, g3_wins = 0, career_earnings = 0
                    WHERE trainer_id = ?
                    """,
                    (succ_name, succ_jockey_id, initial_skill, t_id),
                )
                print(f"    - 【厩舎承継】{t['name']} ({retire_why}) -> {succ_name} (初期スキル: {initial_skill}) / {succ_reason}")

            # 6. 生産牧場の動的分化・譲渡・拡張
            print("[年進行] 6/8: 生産牧場の動的収容バランス調整（最低1頭保証・あふれ移籍）中...")
            self._balance_breeders(conn)

            # 7. 種牡馬の種付け料の動的改定（当年の産駒活躍実績・G1重賞・サイアーリーディング連動）
            print("[年進行] 7/8: 稼働種牡馬の種付け料を産駒成績（獲得賞金・重賞勝利数）に基づき動的改定中...")
            fee_updates = self._update_sire_stud_fees(conn, current_year=current_year)
            for fu in fee_updates:
                sign = "+" if fu["delta"] > 0 else ""
                print(f"    - 【種付け料改定】{fu['name']} (サイアー順位:{fu['rank']}位/産駒G1:{fu['g1_wins']}勝): {fu['old_fee']:,}円 -> {fu['new_fee']:,}円 ({sign}{fu['delta']:,}円)")

            # 8. 当年（年度）成績リセット
            print("[年進行] 8/8: 各種当年成績のリセット（通算成績は保持・累積）中...")
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
            # 9. システム状態の年更新（新年度開幕・第1週未消化状態）
            try:
                conn.execute(
                    """
                    INSERT INTO system_status (key, value_int) VALUES ('current_year', ?), ('current_week', 0)
                    ON CONFLICT(key) DO UPDATE SET value_int = excluded.value_int, updated_at = CURRENT_TIMESTAMP
                    """,
                    (next_year,),
                )
            except Exception:
                pass

        print(f"【年進行 完了】{current_year}年度から {next_year}年度 への移行処理がすべて正常に完了しました！")
        print("=================================================================================\n")
        return {
            "advanced_to_year": next_year,
            "retired_horses": len(retired_horses),
            "debut_horses": debut_count,
            "new_sires": new_sires_count,
            "new_dams": new_dams_count,
            "stud_fee_updates": fee_updates,
        }

    @staticmethod
    def calculate_initial_stud_fee(
        g1_wins: int = 0,
        g2_wins: int = 0,
        g3_wins: int = 0,
        career_earnings: int = 0,
        speed: float = 50.0,
        stamina: float = 50.0,
        acceleration: float = 50.0,
    ) -> int:
        """
        現役時代の成績・獲得賞金・能力値に基づく新種牡馬の初年度種付け料算定
        - ベース: 100万円
        - G1勝利数: 1勝につき +200万円（3勝以上でさらにプレミアム）
        - G2勝利数: 1勝につき +60万円
        - G3勝利数: 1勝につき +30万円
        - 獲得賞金: 1億円につき +40万円
        - 基礎能力: 3能力平均60超でボーナス
        - 10万円単位で丸め (下限100万円、上限2,500万円)
        """
        fee = 1_000_000
        if g1_wins >= 4:
            fee += g1_wins * 2_500_000 + 4_000_000
        elif g1_wins >= 2:
            fee += g1_wins * 2_000_000 + 1_500_000
        elif g1_wins == 1:
            fee += 2_000_000

        fee += g2_wins * 600_000
        fee += g3_wins * 300_000
        fee += (career_earnings // 100_000_000) * 400_000

        avg_ab = (speed + stamina + acceleration) / 3.0
        if avg_ab > 65.0:
            fee += int((avg_ab - 65.0) * 150_000)

        rounded = (fee // 100_000) * 100_000
        return max(1_000_000, min(25_000_000, rounded))

    def _update_sire_stud_fees(self, conn: Any, current_year: int) -> List[Dict[str, Any]]:
        """
        年次進行時の種牡馬種付け料の動的改定:
        当年の産駒実績（獲得賞金、G1/重賞勝利数、産駒勝数）に応じて翌年の種付け料を増減
        ※ 1〜2年目は種付け料の改定を行わない（3年目終了時から改定開始）
        """
        if current_year < 3:
            return []

        rows = conn.execute(
            """
            SELECT
                s.horse_id, s.stud_fee, h.name, h.age,
                COUNT(DISTINCT c.horse_id) as active_children,
                COALESCE(SUM(res.prize_awarded), 0) as year_earnings,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END), 0) as year_wins,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND rc.grade = 'G1' THEN 1 ELSE 0 END), 0) as year_g1,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND rc.grade = 'G2' THEN 1 ELSE 0 END), 0) as year_g2,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND rc.grade = 'G3' THEN 1 ELSE 0 END), 0) as year_g3
            FROM sires s
            JOIN horses h ON s.horse_id = h.horse_id
            LEFT JOIN horses c ON c.sire_id = s.horse_id AND c.is_active = 1
            LEFT JOIN results res ON c.horse_id = res.horse_id
            LEFT JOIN races rc ON res.race_id = rc.race_id AND rc.year = ?
            WHERE s.is_active = 1
            GROUP BY s.horse_id
            ORDER BY year_earnings DESC
            """,
            (current_year,),
        ).fetchall()

        updates = []
        for rank, r in enumerate(rows, start=1):
            s_id = r["horse_id"]
            old_fee = r["stud_fee"]
            ch_count = r["active_children"]
            earnings = r["year_earnings"]
            g1_cnt = r["year_g1"]
            g2_cnt = r["year_g2"]
            g3_cnt = r["year_g3"]
            wins = r["year_wins"]

            if ch_count == 0:
                continue

            delta = 0

            # 1. 産駒G1/重賞勝利実績
            if g1_cnt > 0:
                delta += g1_cnt * 1_500_000
            if g2_cnt > 0:
                delta += g2_cnt * 500_000
            if g3_cnt > 0:
                delta += g3_cnt * 200_000

            # 2. リーディング順位および産駒獲得賞金
            if rank <= 3 and earnings >= 300_000_000:
                delta += 2_000_000
            elif rank <= 10 and earnings >= 150_000_000:
                delta += 1_000_000
            elif earnings >= 80_000_000:
                delta += 300_000

            # 3. 産駒不振による減額判定
            if ch_count >= 3 and wins == 0 and earnings < 20_000_000:
                delta -= 500_000
            elif ch_count >= 5 and earnings < 40_000_000 and (g1_cnt + g2_cnt + g3_cnt) == 0:
                delta -= 300_000

            if delta != 0:
                new_fee = max(500_000, min(30_000_000, old_fee + delta))
                new_fee = (new_fee // 100_000) * 100_000
                if new_fee != old_fee:
                    conn.execute("UPDATE sires SET stud_fee = ? WHERE horse_id = ?", (new_fee, s_id))
                    updates.append({
                        "horse_id": s_id,
                        "name": r["name"],
                        "old_fee": old_fee,
                        "new_fee": new_fee,
                        "delta": new_fee - old_fee,
                        "rank": rank,
                        "g1_wins": g1_cnt,
                    })

        return updates

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

    def _manage_sire_roster(self, conn: Any, current_year: int, retired_horses: List[Any]) -> int:
        """
        種牡馬の新陳代謝・引退判定・新種牡馬認定および海外種牡馬導入 (Phase 8)
        ※ 1〜2年目は種牡馬の入れ替えを行わず、初期60頭を維持（3年目終了時から入れ替え開始）
        """
        if current_year < 3:
            print(f"    ※ 種牡馬入れ替え: 第{current_year}年度は初期種牡馬体制を維持（入れ替えなし）")
            return 0

        # 1. 既存稼働種牡馬の引退判定 (20歳定年、または就任6年目以降直近3年間の産駒勝利数0)
        active_sires = conn.execute(
            """
            SELECT s.sire_id, s.horse_id, s.breeder_id, s.sire_line, h.name, h.age, s.start_year,
                   MAX(c.age) as max_child_age,
                   COALESCE(SUM(c.career_wins), 0) as total_child_wins
            FROM sires s
            JOIN horses h ON s.horse_id = h.horse_id
            LEFT JOIN horses c ON c.sire_id = s.horse_id
            WHERE s.is_active = 1
            GROUP BY s.horse_id
            """
        ).fetchall()

        retired_sire_count = 0
        for s in active_sires:
            age = s["age"]
            start_yr = s["start_year"] or 1
            years_in_service = max(1, current_year - start_yr + 1)
            
            is_retire = False
            retire_reason = ""
            if age >= 20:
                is_retire = True
                retire_reason = f"{age}歳定年"
            elif years_in_service >= 6:
                # 6年目以降: 直近3年間 (current_year - 2 〜 current_year) の産駒勝利数が0
                recent_wins = conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM results res
                    JOIN races r ON res.race_id = r.race_id
                    JOIN horses ch ON res.horse_id = ch.horse_id
                    WHERE ch.sire_id = ?
                      AND res.finish_position = 1
                      AND r.year BETWEEN ? AND ?
                    """,
                    (s["horse_id"], current_year - 2, current_year),
                ).fetchone()[0]
                if recent_wins == 0:
                    is_retire = True
                    retire_reason = f"就任{years_in_service}年目・直近3年間産駒勝利数0"

            if is_retire:
                conn.execute("UPDATE sires SET is_active = 0 WHERE horse_id = ?", (s["horse_id"],))
                conn.execute("UPDATE horses SET is_sire = 0 WHERE horse_id = ?", (s["horse_id"],))
                retired_sire_count += 1
                print(f"    - 【種牡馬引退】{s['name']} ({s['sire_line']}) 引退理由: {retire_reason}")

        # 2. 海外種牡馬の導入 (7年目終了時以降、3年周期で1頭導入)
        imported_sire_count = 0
        if current_year >= 7 and (current_year - 7) % 3 == 0:
            top_sire_stats = conn.execute(
                """
                SELECT h.speed, h.stamina, h.acceleration, h.maternal_vitality, h.temperament, h.durability, h.generation,
                       COALESCE((SELECT SUM(pr.prize_money) FROM horses pr WHERE pr.sire_id = s.horse_id), 0) as total_prog_prize
                FROM sires s
                JOIN horses h ON s.horse_id = h.horse_id
                WHERE s.is_active = 1
                ORDER BY total_prog_prize DESC, (h.speed + h.stamina + h.acceleration) DESC
                LIMIT 10
                """
            ).fetchall()

            if top_sire_stats:
                base_spd = sum(r["speed"] for r in top_sire_stats) / len(top_sire_stats)
                base_sta = sum(r["stamina"] for r in top_sire_stats) / len(top_sire_stats)
                base_acc = sum(r["acceleration"] for r in top_sire_stats) / len(top_sire_stats)
                base_vit = sum(r["maternal_vitality"] for r in top_sire_stats) / len(top_sire_stats)
                base_temp = sum(r["temperament"] for r in top_sire_stats) / len(top_sire_stats)
                base_dura = sum(r["durability"] for r in top_sire_stats) / len(top_sire_stats)
                # 世代を当時の国内トップ種牡馬の最新世代に同期
                max_gen = max((r["generation"] for r in top_sire_stats if r["generation"]), default=1)
                imp_gen = max(1, max_gen)
            else:
                base_spd = 25.0
                base_sta = 25.0
                base_acc = 25.0
                base_vit = 65.0
                base_temp = 65.0
                base_dura = 65.0
                imp_gen = 1

            # 海外種牡馬の能力: トップ10平均の1.05〜1.20倍（25%の確率で1.20〜1.25倍の超大物）
            is_superstar = (random.random() < 0.25)
            if is_superstar:
                mult = random.uniform(1.20, 1.25)
                tier_label = "【超大物・SS級】"
                stud_fee = random.choice([6000000, 8000000, 10000000])
            else:
                mult = random.uniform(1.05, 1.20)
                tier_label = "【有力・A級】"
                stud_fee = random.choice([4000000, 5000000, 6000000])

            imp_spd = round(min(100.0, max(15.0, base_spd * mult)), 1)
            imp_sta = round(min(100.0, max(15.0, base_sta * mult)), 1)
            imp_acc = round(min(100.0, max(15.0, base_acc * mult)), 1)

            # サブパラメーター（母系活力・気性・耐久）も同様に1.05〜1.20倍（超大物は最大1.25倍）
            imp_vit = round(min(100.0, max(20.0, base_vit * mult)), 1)
            imp_temp = round(min(100.0, max(20.0, base_temp * mult)), 1)
            imp_dura = round(min(100.0, max(20.0, base_dura * mult)), 1)

            # 距離適性 (MSTN) を短距離・万能・長距離からサンプリング
            imp_mstn = random.choices(["C/C", "C/T", "T/T"], weights=[0.25, 0.50, 0.25])[0]
            
            # 外国種牡馬の名前生成: 「都市名」+「男性名前」（数字なし）
            imp_name = self.horse_name_gen.generate_foreign_sire_name()

            # 外国種牡馬の父・母の名前をランダム生成して登録
            sire_parent_name = self.horse_name_gen.generate_foreign_ancestor_name("horse")
            dam_parent_name = self.horse_name_gen.generate_foreign_ancestor_name("mare")

            # 繋養牧場
            all_b_ids = [r["breeder_id"] for r in conn.execute("SELECT breeder_id FROM breeders").fetchall()]
            b_id = random.choice(all_b_ids) if all_b_ids else 1
            # サイアーラインは「父親の名前」系とする
            imp_sire_line = f"{sire_parent_name}系"

            # ダミーの父馬レコード
            dummy_parent_gen = max(1, imp_gen - 1)
            cur_p_sire = conn.execute(
                """
                INSERT INTO horses (
                    name, sex, birth_year, age, breeder_id, owner_id, is_active, is_sire, is_dam,
                    mstn_type, speed, stamina, acceleration, temperament, durability, maternal_vitality,
                    growth_type, peak_age, current_ability_rate, running_style, generation
                ) VALUES (
                    ?, 'horse', ?, 12, ?, 1, 0, 0, 0,
                    ?, ?, ?, ?, ?, ?, ?,
                    'normal', 4.5, 1.0, 'between', ?
                )
                """,
                (sire_parent_name, current_year - 12, b_id, imp_mstn, imp_spd, imp_sta, imp_acc, imp_temp, imp_dura, imp_vit, dummy_parent_gen),
            )
            dummy_sire_id = cur_p_sire.lastrowid

            # ダミーの母馬レコード
            cur_p_dam = conn.execute(
                """
                INSERT INTO horses (
                    name, sex, birth_year, age, breeder_id, owner_id, is_active, is_sire, is_dam,
                    mstn_type, speed, stamina, acceleration, temperament, durability, maternal_vitality,
                    growth_type, peak_age, current_ability_rate, running_style, generation
                ) VALUES (
                    ?, 'mare', ?, 12, ?, 1, 0, 0, 0,
                    ?, ?, ?, ?, ?, ?, ?,
                    'normal', 4.5, 1.0, 'between', ?
                )
                """,
                (dam_parent_name, current_year - 12, b_id, imp_mstn, imp_spd, imp_sta, imp_acc, imp_temp, imp_dura, imp_vit, dummy_parent_gen),
            )
            dummy_dam_id = cur_p_dam.lastrowid

            cur = conn.execute(
                """
                INSERT INTO horses (
                    name, sex, birth_year, age, breeder_id, owner_id, sire_id, dam_id, is_active, is_sire,
                    mstn_type, speed, stamina, acceleration, temperament, durability,
                    maternal_vitality, growth_type, peak_age, current_ability_rate, running_style, generation
                ) VALUES (?, 'horse', ?, 5, ?, 1, ?, ?, 0, 1, ?, ?, ?, ?, ?, ?, ?, 'normal', 4.5, 1.0, 'between', ?)
                """,
                (imp_name, current_year - 5, b_id, dummy_sire_id, dummy_dam_id, imp_mstn, imp_spd, imp_sta, imp_acc, imp_temp, imp_dura, imp_vit, imp_gen),
            )
            imp_horse_id = cur.lastrowid
            conn.execute(
                """
                INSERT INTO sires (horse_id, breeder_id, sire_line, max_coverings, stud_fee, generation, start_year, is_active, is_foreign)
                VALUES (?, ?, ?, 30, ?, ?, ?, 1, 1)
                """,
                (imp_horse_id, b_id, imp_sire_line, stud_fee, imp_gen, current_year),
            )
            imported_sire_count += 1
            print(f"    - 【海外種牡馬導入 [外]{tier_label}】{imp_name} (父:{sire_parent_name} 母:{dam_parent_name} / {imp_sire_line}・MSTN:{imp_mstn}・第{imp_gen}世代・繋養開始:{current_year}年・能力SPD:{imp_spd}/STA:{imp_sta}/ACC:{imp_acc}/VIT:{imp_vit}・初年度種付け料: {stud_fee:,}円) 導入完了！")

        # 3. 新種牡馬の昇格判定 (優先度1: 当年主要G1勝ちオープン馬, 優先度2: G1通算3勝以上, 優先度3: スコア順)
        ret_colts = [
            h for h in retired_horses
            if h["sex"] in ("horse", "colt") and (h.get("career_starts", 0) if isinstance(h, dict) else (h["career_starts"] or 0)) > 0 and (h.get("age", 0) if isinstance(h, dict) else (h["age"] or 0)) >= 3
        ]
        # オープン馬の抽出
        open_colts = []
        for h in ret_colts:
            wins = h["career_wins"] or 0
            cond_prz = (h["condition_prize_money"] if "condition_prize_money" in h.keys() else 0) if not isinstance(h, dict) else h.get("condition_prize_money", 0)
            cond_prz = cond_prz or 0
            is_open = (
                (h["g1_wins"] or 0) > 0
                or (h["g2_wins"] or 0) > 0
                or (h["g3_wins"] or 0) > 0
                or wins >= 4
                or cond_prz >= 16_000_000
            )
            if is_open:
                open_colts.append(h)

        def sire_candidate_score(h):
            g1 = h["g1_wins"] or 0
            g2 = h["g2_wins"] or 0
            g3 = h["g3_wins"] or 0
            wins = h["career_wins"] or 0
            starts = h["career_starts"] or 1
            prz = h["prize_money"] or 0
            spd = h["speed"] or 10.0
            sta = h["stamina"] or 10.0
            acc = h["acceleration"] or 10.0
            win_rate = (wins / starts) * 100.0
            p1 = 1000 if g1 >= 1 else 0
            p2 = 500 if g1 >= 3 else 0
            num_score = (g1 * 80) + (g2 * 35) + (g3 * 15) + (wins * 5) + (win_rate * 0.8) + (prz // 10_000_000) + ((spd + sta + acc) / 3.0 * 1.5)
            return p1 + p2 + num_score

        sorted_colts = sorted(open_colts, key=sire_candidate_score, reverse=True)

        # 必要な補充頭数 (最低でも引退枠の補充、またはG1勝ち馬は必ず昇格)
        needed_sires = max(0, retired_sire_count - imported_sire_count)
        
        new_sires_promoted = 0
        for h in sorted_colts:
            g1 = h["g1_wins"] or 0
            # G1勝ち馬は無条件で昇格、その他は定員枠まで
            if g1 > 0 or new_sires_promoted < needed_sires or new_sires_promoted < 2:
                h_id = h["horse_id"]
                p_sire_line = None
                sire_gen = 1
                if h["sire_id"]:
                    s_row = conn.execute("SELECT sire_line, generation FROM sires WHERE horse_id = ?", (h["sire_id"],)).fetchone()
                    if s_row:
                        p_sire_line = s_row["sire_line"]
                        if s_row["generation"]:
                            sire_gen = s_row["generation"]
                    else:
                        h_row = conn.execute("SELECT generation FROM horses WHERE horse_id = ?", (h["sire_id"],)).fetchone()
                        if h_row and h_row["generation"]:
                            sire_gen = h_row["generation"]
                if not p_sire_line:
                    p_sire_line = f"{h['name']}系"

                # 自身の競走馬世代を引き継ぐ（競走馬誕生時に sire_gen + 1 に設定済み）
                dam_or_sire_gen = (h["generation"] if "generation" in h.keys() else 1) if not isinstance(h, dict) else h.get("generation", 1)
                new_sire_gen = dam_or_sire_gen or (sire_gen + 1)

                # 競走成績および本人の能力からの決定因子 (1/3スピードに緩和)
                g1_w = h["g1_wins"] or 0
                g_all = (h["g1_wins"] or 0) + (h["g2_wins"] or 0) + (h["g3_wins"] or 0)
                potential_boost = (g1_w * 0.4) + (g_all * 0.13) + min(1.0, (h["career_wins"] or 0) * 0.07)
                
                # 突然変異フラグ判定
                is_mutation = (random.random() < 0.015)
                cur_spd = h["speed"] or 10.0
                new_sire_speed = cur_spd + potential_boost
                if is_mutation:
                    new_sire_speed = round(min(115.0, new_sire_speed + random.uniform(1.5, 3.5)), 1)
                else:
                    new_sire_speed = round(min(100.0, new_sire_speed), 1)

                initial_fee = self.calculate_initial_stud_fee(
                    g1_wins=h["g1_wins"],
                    g2_wins=h["g2_wins"],
                    g3_wins=h["g3_wins"],
                    career_earnings=h["prize_money"],
                    speed=new_sire_speed,
                    stamina=h["stamina"],
                    acceleration=h["acceleration"],
                )

                conn.execute("UPDATE horses SET speed = ?, generation = ?, is_sire = 1 WHERE horse_id = ?", (new_sire_speed, new_sire_gen, h_id))
                conn.execute(
                    """
                    INSERT INTO sires (horse_id, breeder_id, sire_line, max_coverings, stud_fee, generation, start_year, is_active, is_new)
                    VALUES (?, ?, ?, 30, ?, ?, ?, 1, 1)
                    """,
                    (h_id, h["breeder_id"], p_sire_line, initial_fee, new_sire_gen, current_year),
                )
                new_sires_promoted += 1
                print(f"    - 【新種牡馬入り [新]】{h['name']} (牡{h['age']}歳・第{new_sire_gen}世代種牡馬・繋養開始:{current_year}年・G1:{h['g1_wins']}勝/重賞:{g_all}勝/能力:{new_sire_speed}) -> 初年度種付け料: {initial_fee:,}円 ({p_sire_line})")

        # 4. 最大頭数120頭の厳格維持（超過時はスコア下位を入れ替え引退）
        active_sire_rows = conn.execute(
            """
            SELECT s.horse_id, s.start_year, s.stud_fee, h.name, h.age, h.speed, h.stamina, h.acceleration,
                   COUNT(ch.horse_id) as prog_count,
                   SUM(CASE WHEN ch.career_wins > 0 THEN 1 ELSE 0 END) as winner_count
            FROM sires s
            JOIN horses h ON s.horse_id = h.horse_id
            LEFT JOIN horses ch ON s.horse_id = ch.sire_id
            WHERE s.is_active = 1
            GROUP BY s.horse_id
            """
        ).fetchall()

        cur_sire_count = len(active_sire_rows)
        if cur_sire_count > self.SIRE_MAX_CAPACITY:
            excess = cur_sire_count - self.SIRE_MAX_CAPACITY
            def sire_eval_score(r):
                age = r["age"] or 10
                p_cnt = r["prog_count"] or 0
                w_cnt = r["winner_count"] or 0
                fee = r["stud_fee"] or 0
                spd = r["speed"] or 10.0
                return (w_cnt * 10.0) + (p_cnt * 2.0) + (fee / 1_000_000) + spd - (max(0, age - 15) * 5.0)

            # 就任1年目(新種牡馬)以外を対象に下位を引退
            vet_sires = [r for r in active_sire_rows if (r["start_year"] or 1) < current_year]
            vet_sires.sort(key=sire_eval_score)
            retire_targets = vet_sires[:excess]
            for ts in retire_targets:
                conn.execute("UPDATE sires SET is_active = 0 WHERE horse_id = ?", (ts["horse_id"],))
                conn.execute("UPDATE horses SET is_sire = 0 WHERE horse_id = ?", (ts["horse_id"],))
                print(f"    - 【種牡馬定員超過引退 (120頭上限)】{ts['name']} ({ts['age']}歳)")

        return new_sires_promoted + imported_sire_count

    def _manage_broodmare_roster(self, conn: Any, current_year: int, retired_horses: List[Any]) -> int:
        """
        繁殖牝馬の定員600頭維持および入れ替えルール:
        - 1〜2年目: 入れ替えなし（初期600頭を維持）
        - 3年目以降:
          1. 引退時にオープン馬（G1/G2/G3勝ち、通算4勝以上、または収得賞金1600万円以上）である牝馬のみが繁殖牝馬に昇格
          2. 昇格した頭数と同数の既存繁殖牝馬（ランキング下位：産駒成績・能力・年齢等のスコア下位）が引退して入れ替わり、定員600頭を厳格維持
        """
        target = self.BROODMARE_TARGET_COUNT  # 600頭

        # 1〜2年目は入れ替えなし
        if current_year < 3:
            final_cnt = conn.execute("SELECT COUNT(*) FROM dams WHERE is_active = 1").fetchone()[0]
            print(f"    ※ 繁殖牝馬入れ替え: 第{current_year}年度は初期繁殖牝馬体制を維持（入れ替えなし、稼働数: {final_cnt}頭）")
            return 0

        # 3年目以降: 当年引退牝馬から引退時オープン牝馬を抽出
        ret_mares = [
            h for h in retired_horses
            if h["sex"] in ("mare", "filly", "牝")
            and (h.get("age", 0) if isinstance(h, dict) else (h["age"] or 0)) >= 3
            and (h.get("career_starts", 0) if isinstance(h, dict) else (h["career_starts"] or 0)) > 0
        ]
        open_mares = []
        for h in ret_mares:
            wins = h["career_wins"] or 0
            cond_prz = (h["condition_prize_money"] if "condition_prize_money" in h.keys() else 0) if not isinstance(h, dict) else h.get("condition_prize_money", 0)
            cond_prz = cond_prz or 0
            is_open = (
                (h["g1_wins"] or 0) > 0
                or (h["g2_wins"] or 0) > 0
                or (h["g3_wins"] or 0) > 0
                or wins >= 4
                or cond_prz >= 16_000_000
            )
            if is_open:
                open_mares.append(h)

        promoted_mare_ids = set()
        for h in open_mares:
            h_id = h["horse_id"]
            dam_gen = (h["generation"] if "generation" in h.keys() else 1) if not isinstance(h, dict) else h.get("generation", 1)
            dam_gen = dam_gen or 1
            promoted_mare_ids.add(h_id)
            conn.execute("UPDATE horses SET is_dam = 1, generation = ? WHERE horse_id = ?", (dam_gen, h_id))
            conn.execute(
                """
                INSERT INTO dams (horse_id, breeder_id, is_active, start_year, generation)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(horse_id) DO UPDATE SET is_active = 1, breeder_id = excluded.breeder_id, start_year = excluded.start_year, generation = excluded.generation
                """,
                (h_id, h["breeder_id"], current_year, dam_gen),
            )
            g_all = (h["g1_wins"] or 0) + (h["g2_wins"] or 0) + (h["g3_wins"] or 0)
            print(f"    - 【繁殖牝馬昇格 (引退オープン馬)】{h['name']} (牝{h['age']}歳・第{dam_gen}世代・繋養開始:{current_year}年・G1:{h['g1_wins']}勝/重賞:{g_all}勝/通算{h['career_wins']}勝)")

        num_promoted = len(promoted_mare_ids)

        # 既存繁殖牝馬の成績・能力・年齢・産駒成績を総合評価
        active_dams = conn.execute(
            """
            SELECT d.dam_id, d.horse_id, d.breeder_id, h.name, h.age,
                   h.speed, h.stamina, h.acceleration, h.maternal_vitality,
                   MAX(c.age) as max_child_age,
                   COALESCE(SUM(c.career_wins), 0) as total_child_wins
            FROM dams d
            JOIN horses h ON d.horse_id = h.horse_id
            LEFT JOIN horses c ON c.dam_id = d.horse_id
            WHERE d.is_active = 1 AND d.horse_id NOT IN ({})
            GROUP BY d.horse_id
            """.format(",".join("?" for _ in promoted_mare_ids) if promoted_mare_ids else "0"),
            tuple(promoted_mare_ids) if promoted_mare_ids else (),
        ).fetchall()

        # 1. 既存繁殖牝馬の20歳定年引退判定
        age_retired_count = 0
        age_retired_ids = set()
        for d in active_dams:
            age = d["age"] or 0
            if age >= 20:
                conn.execute("UPDATE dams SET is_active = 0 WHERE horse_id = ?", (d["horse_id"],))
                conn.execute("UPDATE horses SET is_dam = 0 WHERE horse_id = ?", (d["horse_id"],))
                age_retired_ids.add(d["horse_id"])
                age_retired_count += 1
                print(f"    - 【繁殖牝馬引退 (20歳定年)】{d['name']} ({age}歳)")

        remaining_active_dams = [d for d in active_dams if d["horse_id"] not in age_retired_ids]

        def dam_rank_score(d):
            child_wins = d["total_child_wins"] or 0
            max_c_age = d["max_child_age"] or 0
            age = d["age"] or 10
            spd = d["speed"] or 10.0
            sta = d["stamina"] or 10.0
            acc = d["acceleration"] or 10.0
            vit = d["maternal_vitality"] or 10.0
            # 産駒デビュー後未勝利ペナルティ
            p_penalty = -500.0 if (max_c_age >= 4 and child_wins == 0) else 0.0
            return p_penalty + (child_wins * 25.0) + ((spd + sta + acc) / 3.0) + (vit * 0.5) - (max(0, age - 15) * 10.0)

        sorted_existing_dams = sorted(remaining_active_dams, key=dam_rank_score)

        # 昇格頭数が定年引退頭数を上回る場合、その差分だけランキング下位繁殖牝馬を入れ替え引退
        needed_rank_retire = max(0, num_promoted - age_retired_count)
        if needed_rank_retire > 0:
            for d in sorted_existing_dams[:needed_rank_retire]:
                conn.execute("UPDATE dams SET is_active = 0 WHERE horse_id = ?", (d["horse_id"],))
                conn.execute("UPDATE horses SET is_dam = 0 WHERE horse_id = ?", (d["horse_id"],))
                print(f"    - 【繁殖牝馬入れ替え引退 (ランキング下位)】{d['name']} ({d['age']}歳)")
            sorted_existing_dams = sorted_existing_dams[needed_rank_retire:]

        # 最終定員調整（常に600頭維持）
        cur_count = conn.execute("SELECT COUNT(*) FROM dams WHERE is_active = 1").fetchone()[0]
        if cur_count > target:
            excess = cur_count - target
            for d in sorted_existing_dams[:excess]:
                conn.execute("UPDATE dams SET is_active = 0 WHERE horse_id = ?", (d["horse_id"],))
                conn.execute("UPDATE horses SET is_dam = 0 WHERE horse_id = ?", (d["horse_id"],))
                print(f"    - 【繁殖牝馬定員超過引退】{d['name']} ({d['age']}歳)")
        elif cur_count < target:
            shortage = target - cur_count
            fallback_mares = conn.execute(
                """
                SELECT h.horse_id, h.name, h.age, h.breeder_id, h.career_wins, h.generation,
                       ((h.speed + h.stamina + h.acceleration)/3.0 + h.maternal_vitality*0.5) as score
                FROM horses h
                LEFT JOIN dams d ON h.horse_id = d.horse_id
                WHERE h.sex IN ('mare', 'filly', '牝')
                  AND h.is_active = 0
                  AND h.age >= 3
                  AND h.age < 20
                  AND h.career_starts > 0
                  AND h.is_dead = 0
                  AND (d.is_active IS NULL OR d.is_active = 0)
                ORDER BY score DESC LIMIT ?
                """,
                (shortage,),
            ).fetchall()
            for fm in fallback_mares:
                dam_gen = (fm["generation"] or 1)
                conn.execute("UPDATE horses SET is_dam = 1, generation = ? WHERE horse_id = ?", (dam_gen, fm["horse_id"]))
                conn.execute(
                    """
                    INSERT INTO dams (horse_id, breeder_id, is_active, start_year, generation)
                    VALUES (?, ?, 1, ?, ?)
                    ON CONFLICT(horse_id) DO UPDATE SET is_active = 1, breeder_id = excluded.breeder_id, start_year = excluded.start_year, generation = excluded.generation
                    """,
                    (fm["horse_id"], fm["breeder_id"], current_year, dam_gen),
                )
                print(f"    - 【繁殖牝馬補充】{fm['name']} (牝{fm['age']}歳・第{dam_gen}世代・通算{fm['career_wins']}勝)")

        final_dam_count = conn.execute("SELECT COUNT(*) FROM dams WHERE is_active = 1").fetchone()[0]
        print(f"    ★ 繁殖牝馬 最終定員確定: {final_dam_count} 頭 (目標: {target}頭)")
        return num_promoted
