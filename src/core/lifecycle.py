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

    MAX_RACING_AGE: int = 7             # 現役競走馬の上限年齢（7歳末引退、8歳以上は現役不可）
    TRAINER_OPEN_AGE: int = 60          # 調教師開業年齢 (60歳)
    TRAINER_RETIRE_AGE: int = 80        # 調教師定年引退年齢
    FARM_DEFAULT_CAPACITY: int = 15     # 牧場初期収容頭数
    FARM_MAX_CAPACITY: int = 30         # 牧場拡張上限
    BROODMARE_TARGET_COUNT: int = 600   # 繁殖牝馬の年間目標維持頭数

    def __init__(self, db: Database):
        self.db = db
        self.person_name_gen = PersonNameGenerator()
        self.jockey_mgr = JockeyManager(db=db, quota_miho=45, quota_ritto=45)
        self._ensure_columns_exist()

    def _ensure_columns_exist(self) -> None:
        """sires / dams テーブルに必要なPhase8カラムが存在することを確認"""
        with self.db.session() as conn:
            try:
                s_cols = [c[1] for c in conn.execute("PRAGMA table_info(sires)").fetchall()]
                if "is_imported" not in s_cols:
                    conn.execute("ALTER TABLE sires ADD COLUMN is_imported INTEGER NOT NULL DEFAULT 0")
                if "debut_year" not in s_cols:
                    conn.execute("ALTER TABLE sires ADD COLUMN debut_year INTEGER NOT NULL DEFAULT 1")
            except Exception:
                pass
            try:
                d_cols = [c[1] for c in conn.execute("PRAGMA table_info(dams)").fetchall()]
                if "debut_year" not in d_cols:
                    conn.execute("ALTER TABLE dams ADD COLUMN debut_year INTEGER NOT NULL DEFAULT 1")
            except Exception:
                pass

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

                # 成長型別ベース発揮率カーブ
                if growth_type == GrowthType.EARLY.value or growth_type == "early":
                    if age <= 2:
                        base_rate = 0.82 if is_female else 0.78
                    elif age == 3:
                        base_rate = 1.00
                    elif age == 4:
                        base_rate = 0.92 if is_female else 0.95
                    elif age == 5:
                        base_rate = 0.80 if is_female else 0.85
                    elif age == 6:
                        base_rate = 0.65 if is_female else 0.70
                    else:
                        base_rate = max(0.40, 0.65 - 0.12 * (age - 6))
                elif growth_type == GrowthType.LATE.value or growth_type == "late":
                    if age <= 2:
                        base_rate = 0.58 if is_female else 0.55
                    elif age == 3:
                        base_rate = 0.78 if is_female else 0.75
                    elif age == 4:
                        base_rate = 0.92 if is_female else 0.90
                    elif age in (5, 6):
                        base_rate = 1.00
                    elif age == 7:
                        base_rate = 0.85 if is_female else 0.88
                    else:
                        base_rate = max(0.40, 0.75 - 0.12 * (age - 7))
                else:
                    if age <= 2:
                        base_rate = 0.68 if is_female else 0.65
                    elif age == 3:
                        base_rate = 0.90 if is_female else 0.88
                    elif age in (4, 5):
                        base_rate = 1.00
                    elif age == 6:
                        base_rate = 0.85 if is_female else 0.88
                    elif age == 7:
                        base_rate = 0.70 if is_female else 0.72
                    else:
                        base_rate = max(0.40, 0.70 - 0.14 * (age - 7))

                trainer_bonus = 0.0
                if h["trainer_skill"] is not None:
                    trainer_bonus = (float(h["trainer_skill"]) - 50.0) / 100.0 * 0.06

                final_rate = round(min(1.05, max(0.40, base_rate + trainer_bonus)), 2)
                conn.execute(
                    "UPDATE horses SET current_ability_rate = ? WHERE horse_id = ?",
                    (final_rate, h["horse_id"]),
                )

            # 3. Phase 8 厳格な競走馬引退判定
            # - 4歳末: 1勝馬（career_wins <= 1）は引退
            # - 5歳末: 牝馬は全頭引退、牡馬条件馬（通算3勝以下かつ収得賞金1600万円未満）は引退
            # - 4歳以上オープン馬: ピークアウトかつ近走不振で引退
            # - 7歳末: 全頭引退 (MAX_RACING_AGE = 7)
            active_koba = conn.execute(
                """
                SELECT horse_id, name, sex, age, peak_age, current_ability_rate,
                       breeder_id, owner_id, g1_wins, g2_wins, g3_wins,
                       career_wins, career_starts, prize_money, condition_prize_money,
                       speed, stamina, acceleration, maternal_vitality, sire_id
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
                is_open = (h["g1_wins"] > 0 or h["g2_wins"] > 0 or h["g3_wins"] > 0 or wins >= 4 or cond_prize >= 16_000_000)
                is_female = sex in ("mare", "filly", "牝")

                # (1) 7歳超過は100%全頭引退
                if age > self.MAX_RACING_AGE:
                    retired_horse_ids.add(h["horse_id"])
                    retired_horses.append(h)
                    continue

                # (2) 4歳末で1勝以下は引退
                if age == 4 and wins <= 1:
                    retired_horse_ids.add(h["horse_id"])
                    retired_horses.append(h)
                    continue

                # (3) 5歳末で牝馬は全頭引退、牡馬条件馬は引退
                if age == 5:
                    if is_female or (not is_open):
                        retired_horse_ids.add(h["horse_id"])
                        retired_horses.append(h)
                        continue

                # (4) 6歳・7歳のオープン馬: ピークアウト・近走不振判定
                peak = h["peak_age"]
                rate = h["current_ability_rate"]
                is_peak_out = (age >= peak + 1.5) or (rate < 0.72)

                retire_prob = 0.0
                if age == 6:
                    retire_prob = 0.60 if is_peak_out else 0.25
                elif age == 7:
                    retire_prob = 0.90

                if random.random() < retire_prob:
                    retired_horse_ids.add(h["horse_id"])
                    retired_horses.append(h)

            print(f"[年進行] 2/8: 現役競走馬の引退処理（引退頭数: {len(retired_horses)}頭）...")

            for h in retired_horses:
                conn.execute(
                    "UPDATE horses SET is_active = 0, retired_year = ?, trainer_id = NULL, jockey_id = NULL WHERE horse_id = ?",
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
                    succ_reason = f"新調教師 {succ_name} (60歳) が新規就任"

                existing_trainer_names.add(succ_name)
                self.person_name_gen.register_trainer_name(succ_name)

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
                print(f"    - 【厩舎承継】{t['name']} (80歳定年引退) -> {succ_name} (初期スキル: {initial_skill}) / {succ_reason}")

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
        """
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
        """
        # 1. 既存稼働種牡馬の引退判定 (25歳定年、または産駒デビュー後3年間未勝利)
        active_sires = conn.execute(
            """
            SELECT s.sire_id, s.horse_id, s.breeder_id, s.sire_line, h.name, h.age,
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
            max_c_age = s["max_child_age"] or 0
            child_wins = s["total_child_wins"] or 0
            
            is_retire = False
            retire_reason = ""
            if age >= 25:
                is_retire = True
                retire_reason = f"{age}歳定年"
            elif max_c_age >= 4 and child_wins == 0:
                is_retire = True
                retire_reason = "産駒デビュー3年未勝利"

            if is_retire:
                conn.execute("UPDATE sires SET is_active = 0 WHERE horse_id = ?", (s["horse_id"],))
                conn.execute("UPDATE horses SET is_sire = 0 WHERE horse_id = ?", (s["horse_id"],))
                retired_sire_count += 1
                print(f"    - 【種牡馬引退】{s['name']} ({s['sire_line']}) 引退理由: {retire_reason}")

        # 2. 海外種牡馬の導入 (4年目以降、3年周期で1頭導入)
        imported_sire_count = 0
        if current_year >= 4 and (current_year - 4) % 3 == 0:
            avg_stats = conn.execute(
                """
                SELECT AVG(speed) as avg_spd, AVG(stamina) as avg_sta, AVG(acceleration) as avg_acc
                FROM horses h
                JOIN sires s ON h.horse_id = s.horse_id
                """
            ).fetchone()
            base_spd = avg_stats["avg_spd"] or 55.0
            base_sta = avg_stats["avg_sta"] or 55.0
            base_acc = avg_stats["avg_acc"] or 55.0

            # 上位30%〜最大1.1倍の能力
            imp_spd = round(min(95.0, (base_spd + 8.0) * random.uniform(1.0, 1.08)), 1)
            imp_sta = round(min(95.0, (base_sta + 8.0) * random.uniform(1.0, 1.08)), 1)
            imp_acc = round(min(95.0, (base_acc + 8.0) * random.uniform(1.0, 1.08)), 1)
            
            foreign_names = ["ガリレオ", "フランケル", "ドバウィ", "ディープインパクト", "シーザスターズ", "キングマン", "ウートデトリアン", "ジャスティファイ", "フライトライン", "シャマルダル"]
            random.shuffle(foreign_names)
            imp_name = f"{foreign_names[0]}{random.randint(1, 99)}"

            # 繋養牧場
            all_b_ids = [r["breeder_id"] for r in conn.execute("SELECT breeder_id FROM breeders").fetchall()]
            b_id = random.choice(all_b_ids) if all_b_ids else 1
            sire_lines = ["ノーザンダンサー系", "ミスタープロスペクター系", "サンデーサイレンス系", "ナスルーラ系", "ロベルト系", "ダンジグ系"]
            imp_sire_line = random.choice(sire_lines)

            cur = conn.execute(
                """
                INSERT INTO horses (
                    name, sex, birth_year, age, breeder_id, owner_id, is_active, is_sire,
                    mstn_type, speed, stamina, acceleration, temperament, durability,
                    maternal_vitality, growth_type, peak_age, current_ability_rate, running_style
                ) VALUES (?, 'horse', ?, 5, ?, 1, 0, 1, 'C/T', ?, ?, ?, 65.0, 65.0, 70.0, 'normal', 4.5, 1.0, 'between')
                """,
                (imp_name, current_year - 5, b_id, imp_spd, imp_sta, imp_acc),
            )
            imp_horse_id = cur.lastrowid
            conn.execute(
                """
                INSERT INTO sires (horse_id, breeder_id, sire_line, max_coverings, stud_fee, is_active, is_imported, debut_year)
                VALUES (?, ?, ?, 30, 3000000, 1, 1, ?)
                """,
                (imp_horse_id, b_id, imp_sire_line, current_year + 1),
            )
            imported_sire_count += 1
            print(f"    - 【海外種牡馬導入 [外]】{imp_name} ({imp_sire_line}・初年度種付け料: 3,000,000円) 導入完了！")

        # 3. 新種牡馬の昇格判定 (優先度1: 当年主要G1勝ちオープン馬, 優先度2: G1通算3勝以上, 優先度3: スコア順)
        ret_colts = [h for h in retired_horses if h["sex"] in ("horse", "colt")]
        # オープン馬の抽出
        open_colts = []
        for h in ret_colts:
            wins = h["career_wins"] or 0
            cond_prz = h.get("condition_prize_money", 0) if isinstance(h, dict) else (h["condition_prize_money"] if "condition_prize_money" in h.keys() else 0)
            is_open = (h["g1_wins"] > 0 or h["g2_wins"] > 0 or h["g3_wins"] > 0 or wins >= 4 or cond_prz >= 16_000_000)
            if is_open:
                open_colts.append(h)

        # 優先度1: 当年主要G1勝利馬
        # 優先度2: G1通算3勝以上
        # 優先度3: スコア順 (重賞勝利数, 3着内率, 勝率, 能力値)
        def sire_candidate_score(h):
            g1 = h["g1_wins"] or 0
            g2 = h["g2_wins"] or 0
            g3 = h["g3_wins"] or 0
            wins = h["career_wins"] or 0
            starts = h["career_starts"] or 1
            prz = h["prize_money"] or 0
            spd = h["speed"] or 50.0
            sta = h["stamina"] or 50.0
            acc = h["acceleration"] or 50.0
            win_rate = (wins / starts) * 100.0
            p1 = 1000 if g1 >= 1 else 0
            p2 = 500 if g1 >= 3 else 0
            num_score = (g1 * 60) + (g2 * 25) + (g3 * 10) + (wins * 4) + (win_rate * 0.5) + (prz // 10_000_000) + ((spd + sta + acc) / 3.0 * 0.5)
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
                if h["sire_id"]:
                    s_row = conn.execute("SELECT sire_line FROM sires WHERE horse_id = ?", (h["sire_id"],)).fetchone()
                    if s_row:
                        p_sire_line = s_row["sire_line"]
                if not p_sire_line:
                    p_sire_line = f"{h['name']}系"

                initial_fee = self.calculate_initial_stud_fee(
                    g1_wins=h["g1_wins"],
                    g2_wins=h["g2_wins"],
                    g3_wins=h["g3_wins"],
                    career_earnings=h["prize_money"],
                    speed=h["speed"],
                    stamina=h["stamina"],
                    acceleration=h["acceleration"],
                )

                conn.execute("UPDATE horses SET is_sire = 1 WHERE horse_id = ?", (h_id,))
                conn.execute(
                    """
                    INSERT INTO sires (horse_id, breeder_id, sire_line, max_coverings, stud_fee, is_active, is_imported, debut_year)
                    VALUES (?, ?, ?, 30, ?, 1, 0, ?)
                    """,
                    (h_id, h["breeder_id"], p_sire_line, initial_fee, current_year + 1),
                )
                new_sires_promoted += 1
                print(f"    - 【新種牡馬入り [新]】{h['name']} (牡{h['age']}歳・G1:{h['g1_wins']}勝/重賞:{h['g1_wins']+h['g2_wins']+h['g3_wins']}勝) -> 初年度種付け料: {initial_fee:,}円 ({p_sire_line})")

        return new_sires_promoted + imported_sire_count

    def _manage_broodmare_roster(self, conn: Any, current_year: int, retired_horses: List[Any]) -> int:
        """
        繁殖牝馬の定員600頭維持および入れ替えルール (Phase 8: ルールA/B/C/D)
        - A: 引退時オープン馬は繁殖牝馬確定
        - B: 産駒デビュー後3年間勝ち星なし & 20歳定年の繁殖牝馬は引退
        - C: 600 - B + A < 600 の場合、引退牝馬のランク上位から補充して600頭に調整
        - D: 600 - B + A > 600 の場合、2年連続勝利なし繁殖牝馬を下位から引退させて600頭に調整
        """
        # 1. B: 産駒デビュー後3年間勝ち星なし & 20歳定年の繁殖牝馬 引退
        active_dams = conn.execute(
            """
            SELECT d.dam_id, d.horse_id, d.breeder_id, h.name, h.age,
                   h.speed, h.stamina, h.acceleration, h.maternal_vitality,
                   MAX(c.age) as max_child_age,
                   COALESCE(SUM(c.career_wins), 0) as total_child_wins
            FROM dams d
            JOIN horses h ON d.horse_id = h.horse_id
            LEFT JOIN horses c ON c.dam_id = d.horse_id
            WHERE d.is_active = 1
            GROUP BY d.horse_id
            """
        ).fetchall()

        retired_dam_ids = set()
        for d in active_dams:
            age = d["age"]
            max_c_age = d["max_child_age"] or 0
            child_wins = d["total_child_wins"] or 0
            
            is_retire = False
            retire_reason = ""
            if age >= 20:
                is_retire = True
                retire_reason = f"{age}歳定年"
            elif max_c_age >= 4 and child_wins == 0:
                is_retire = True
                retire_reason = "産駒デビュー3年未勝利"

            if is_retire:
                retired_dam_ids.add(d["horse_id"])
                conn.execute("UPDATE dams SET is_active = 0 WHERE horse_id = ?", (d["horse_id"],))
                conn.execute("UPDATE horses SET is_dam = 0 WHERE horse_id = ?", (d["horse_id"],))
                print(f"    - 【繁殖牝馬引退】{d['name']} ({age}歳) 引退理由: {retire_reason}")

        surviving_dams_count = len(active_dams) - len(retired_dam_ids)

        # 2. A: 引退時オープン牝馬は繁殖牝馬確定
        ret_mares = [h for h in retired_horses if h["sex"] in ("mare", "filly", "牝")]
        
        open_mares = []
        non_open_mares = []
        for h in ret_mares:
            wins = h["career_wins"] or 0
            cond_prz = h.get("condition_prize_money", 0) if isinstance(h, dict) else (h["condition_prize_money"] if "condition_prize_money" in h.keys() else 0)
            is_open = (h["g1_wins"] > 0 or h["g2_wins"] > 0 or h["g3_wins"] > 0 or wins >= 4 or cond_prz >= 16_000_000)
            if is_open:
                open_mares.append(h)
            else:
                non_open_mares.append(h)

        promoted_mare_ids = set()
        # A: オープン牝馬確定昇格
        for h in open_mares:
            h_id = h["horse_id"]
            promoted_mare_ids.add(h_id)
            conn.execute("UPDATE horses SET is_dam = 1 WHERE horse_id = ?", (h_id,))
            conn.execute(
                """
                INSERT INTO dams (horse_id, breeder_id, is_active, debut_year)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(horse_id) DO UPDATE SET is_active = 1, breeder_id = excluded.breeder_id, debut_year = excluded.debut_year
                """,
                (h_id, h["breeder_id"], current_year + 1),
            )
            print(f"    - 【繁殖牝馬確定昇格 (A:オープン馬)】{h['name']} (牝{h['age']}歳・G1:{h['g1_wins']}勝/重賞:{h['g1_wins']+h['g2_wins']+h['g3_wins']}勝)")

        current_total = surviving_dams_count + len(promoted_mare_ids)
        target = self.BROODMARE_TARGET_COUNT  # 600頭

        # 3. C: 600頭に満たない場合 (不足) -> 引退牝馬のランク上位から補充
        if current_total < target:
            shortage = target - current_total
            print(f"    ※ 繁殖牝馬定員調整: 現在{current_total}頭 / 目標{target}頭 (不足: {shortage}頭を引退牝馬ランク上位から補充)")

            def mare_rank_score(m):
                wins = m["career_wins"] or 0
                prz = m["prize_money"] or 0
                spd = m["speed"] or 50.0
                sta = m["stamina"] or 50.0
                acc = m["acceleration"] or 50.0
                vit = m["maternal_vitality"] or 50.0
                return (wins * 20.0) + (prz // 1_000_000) + ((spd + sta + acc) / 3.0 * 0.6) + (vit * 0.4)

            sorted_non_open = sorted(non_open_mares, key=mare_rank_score, reverse=True)
            for m in sorted_non_open[:shortage]:
                m_id = m["horse_id"]
                promoted_mare_ids.add(m_id)
                conn.execute("UPDATE horses SET is_dam = 1 WHERE horse_id = ?", (m_id,))
                conn.execute(
                    """
                    INSERT INTO dams (horse_id, breeder_id, is_active, debut_year)
                    VALUES (?, ?, 1, ?)
                    ON CONFLICT(horse_id) DO UPDATE SET is_active = 1, breeder_id = excluded.breeder_id, debut_year = excluded.debut_year
                    """,
                    (m_id, m["breeder_id"], current_year + 1),
                )
                print(f"    - 【繁殖牝馬補充昇格 (C:ランク上位)】{m['name']} (牝{m['age']}歳・通算{m['career_wins']}勝)")

            # もしまだ足りない場合は過去の引退牝馬から能力上位を補填
            if len(promoted_mare_ids) + surviving_dams_count < target:
                remaining_shortage = target - (len(promoted_mare_ids) + surviving_dams_count)
                fallback_mares = conn.execute(
                    """
                    SELECT h.horse_id, h.name, h.age, h.breeder_id, h.career_wins,
                           ((h.speed + h.stamina + h.acceleration)/3.0 + h.maternal_vitality*0.5) as score
                    FROM horses h
                    LEFT JOIN dams d ON h.horse_id = d.horse_id
                    WHERE h.sex IN ('mare', 'filly', '牝') AND h.is_active = 0 AND (d.is_active IS NULL OR d.is_active = 0)
                    ORDER BY score DESC LIMIT ?
                    """,
                    (remaining_shortage,),
                ).fetchall()
                for fm in fallback_mares:
                    conn.execute("UPDATE horses SET is_dam = 1 WHERE horse_id = ?", (fm["horse_id"],))
                    conn.execute(
                        """
                        INSERT INTO dams (horse_id, breeder_id, is_active, debut_year)
                        VALUES (?, ?, 1, ?)
                        ON CONFLICT(horse_id) DO UPDATE SET is_active = 1, breeder_id = excluded.breeder_id, debut_year = excluded.debut_year
                        """,
                        (fm["horse_id"], fm["breeder_id"], current_year + 1),
                    )

        # 4. D: 600頭を超過している場合 (超過) -> 2年連続勝利なし繁殖牝馬を下位から引退
        elif current_total > target:
            excess = current_total - target
            print(f"    ※ 繁殖牝馬定員調整: 現在{current_total}頭 / 目標{target}頭 (超過: {excess}頭を不振・高齢繁殖牝馬から引退)")

            # 既存残存繁殖牝馬（今回新昇格した馬を除く）のスコア付け
            remaining_active_dams = [d for d in active_dams if d["horse_id"] not in retired_dam_ids]
            
            def dam_retire_priority(d):
                max_c_age = d["max_child_age"] or 0
                child_wins = d["total_child_wins"] or 0
                age = d["age"]
                spd = d["speed"] or 50.0
                sta = d["stamina"] or 50.0
                acc = d["acceleration"] or 50.0
                vit = d["maternal_vitality"] or 50.0
                # 産駒2年未勝利 (max_c_age >= 3 and child_wins == 0) は最優先で下位に
                is_winless_2y = (max_c_age >= 3 and child_wins == 0)
                p_penalty = -1000 if is_winless_2y else 0
                score = p_penalty + (child_wins * 20.0) + ((spd + sta + acc) / 3.0) + (vit * 0.5) - (max(0, age - 12) * 8.0)
                return score

            sorted_dams_to_retire = sorted(remaining_active_dams, key=dam_retire_priority)
            for d in sorted_dams_to_retire[:excess]:
                conn.execute("UPDATE dams SET is_active = 0 WHERE horse_id = ?", (d["horse_id"],))
                conn.execute("UPDATE horses SET is_dam = 0 WHERE horse_id = ?", (d["horse_id"],))
                print(f"    - 【繁殖牝馬定員超過引退 (D:不振・高齢)】{d['name']} ({d['age']}歳)")

        final_dam_count = conn.execute("SELECT COUNT(*) FROM dams WHERE is_active = 1").fetchone()[0]
        print(f"    ★ 繁殖牝馬 最終定員確定: {final_dam_count} 頭 (目標: {target}頭)")
        return len(promoted_mare_ids)
