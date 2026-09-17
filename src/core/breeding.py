"""
交配・繁殖管理モジュール (Breeding Engine)
年間種付け処理、種牡馬30頭制限遵守、受胎・当歳馬約500頭誕生、サイアーライン多様性維持
ユーザー指定4大種付け優先ルール（所属厩舎・優秀厩舎・若齢・実績上位）＋ニックス（系統相性）＋ドラフト選定
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Set, Tuple

from src.core.genetics import GeneticsEngine
from src.db.database import Database
from src.generators.name_generator import HorseNameGenerator
from src.models.horse import GenotypeMSTN, GrowthType, RunningStyle
from src.views.pedigree_builder import PedigreeBuilder


class BreedingEngine:
    """繁殖・交配シミュレーションエンジン"""

    MAX_COVERINGS_PER_SIRE: int = 30  # 種牡馬1頭あたりの年間上限種付け頭数
    TARGET_FOAL_COUNT: int = 600      # 年間誕生目標当歳数（牡300頭・牝300頭同数）

    def __init__(self, db: Database):
        self.db = db
        self.name_gen = HorseNameGenerator()
        self.pedigree_builder = PedigreeBuilder(db)

    def _sync_existing_names(self, conn) -> None:
        """
        馬名ジェネレータの禁止馬名セットを更新:
        1. 重賞(G1, G2, G3)勝利馬の名前（過去の引退馬も含め永久に重複不可）
        2. 現在活動中（現役・種牡馬・繁殖牝馬）の馬の名前（同時代重複不可）
        ※ 重賞未勝利で引退した馬の名前は再利用可能
        """
        # 1. 重賞勝利馬（G1, G2, G3のいずれかを勝利）
        rows_graded = conn.execute(
            """
            SELECT DISTINCT name FROM horses
            WHERE g1_wins > 0 OR g2_wins > 0 OR g3_wins > 0
            """
        ).fetchall()
        graded_names = {r["name"] for r in rows_graded}

        # 2. 現在活動中の馬（現役、供用中種牡馬、供用中繁殖牝馬）
        rows_active = conn.execute(
            """
            SELECT DISTINCT name FROM horses
            WHERE is_active = 1 OR is_sire = 1 OR is_dam = 1
            """
        ).fetchall()
        active_names = {r["name"] for r in rows_active}

        forbidden = graded_names | active_names
        self.name_gen.set_forbidden_names(forbidden)

    def _load_trainer_stats(self, conn) -> Dict[int, Dict[str, Any]]:
        """全調教師の通算成績・名声マップを取得"""
        rows = conn.execute(
            """
            SELECT trainer_id, name, career_wins, g1_wins, g2_wins, g3_wins, reputation
            FROM trainers
            """
        ).fetchall()
        return {r["trainer_id"]: dict(r) for r in rows}

    def _load_mating_history(self, conn) -> Dict[Tuple[int, int], Dict[str, Any]]:
        """
        全交配履歴（過去の産駒数およびG1勝利産駒の有無）を取得
        キー: (dam_id, sire_id)
        値: {"foal_count": int, "has_g1_winner": bool}
        """
        rows = conn.execute(
            """
            SELECT dam_id, sire_id, COUNT(*) as foal_count, MAX(g1_wins) as max_g1
            FROM horses
            WHERE dam_id IS NOT NULL AND sire_id IS NOT NULL
            GROUP BY dam_id, sire_id
            """
        ).fetchall()
        history: Dict[Tuple[int, int], Dict[str, Any]] = {}
        for r in rows:
            history[(r["dam_id"], r["sire_id"])] = {
                "foal_count": r["foal_count"],
                "has_g1_winner": (r["max_g1"] is not None and r["max_g1"] > 0),
            }
        return history

    @staticmethod
    def can_mate_sire_and_dam(
        dam_id: int, sire_id: int, mating_history: Dict[Tuple[int, int], Dict[str, Any]]
    ) -> bool:
        """
        同一種牡馬との交配ルール判定:
        - 初回交配 (過去産駒数 0): 可能
        - 再種付け (過去産駒数 >= 1):
          - 過去産駒にG1レース勝利馬がいる場合のみ許可
          - 生涯で最大4回を超えない (foal_count < 4)
        """
        record = mating_history.get((dam_id, sire_id))
        if not record or record["foal_count"] == 0:
            return True

        if record["foal_count"] >= 4:
            return False

        return record["has_g1_winner"]

    def _get_dam_sire_line(
        self, dam: Dict[str, Any], sire_line_map: Dict[int, str]
    ) -> str:
        """
        繁殖牝馬の父系（母の父のサイアーライン）を取得
        父IDが存在しない初期繁殖牝馬の場合は、大系統を決定論的に割り振る
        """
        dam_sire_id = dam.get("sire_id")
        if dam_sire_id and dam_sire_id in sire_line_map:
            return sire_line_map[dam_sire_id]

        # 初期繁殖牝馬などは名前とIDから決定論的に系統を分類
        h_id = dam["horse_id"]
        major_systems = GeneticsEngine.MAJOR_SYSTEMS
        return major_systems[h_id % len(major_systems)]

    def calculate_dam_priority_score(
        self,
        dam: Dict[str, Any],
        sire: Dict[str, Any],
        trainer_map: Dict[int, Dict[str, Any]],
        is_nicks: bool,
        inbreeding_pct: float,
    ) -> float:
        """
        種牡馬に対する繁殖牝馬の優先度スコアを計算
        【ユーザー指定4大優先ルール】
        1. 繁殖牝馬の所属厩舎が優先（同厩舎ゆかりの配合）
        2. 成績が良い厩舎が優先（元所属調教師の通算実績）
        3. 若い年齢の繁殖牝馬が優先
        4. 繁殖牝馬ランキング上位の馬が優先（G1勝利・重賞実績・能力値）
        【追加提案ルール】
        - 自家生産・同牧場優先（種牡馬と繁殖牝馬の牧場が一致）
        - ニックス（系統好相性）成立ボーナス
        - 危険な近親交配（18.75%超）のペナルティ
        """
        score = 50.0

        dam_trainer_id = dam.get("trainer_id")
        sire_trainer_id = sire.get("trainer_id")

        # 1. 繁殖牝馬の所属厩舎が優先（同厩舎ゆかり）
        if dam_trainer_id and sire_trainer_id and dam_trainer_id == sire_trainer_id:
            score += 30.0
        elif dam_trainer_id and dam_trainer_id in trainer_map:
            # 厩舎のゆかり（名声が高い厩舎に所属していた）
            score += 5.0

        # 2. 成績が良い厩舎が優先（元調教師の成績上位）
        if dam_trainer_id and dam_trainer_id in trainer_map:
            t_data = trainer_map[dam_trainer_id]
            g1_w = t_data.get("g1_wins", 0)
            c_w = t_data.get("career_wins", 0)
            trainer_score = min(25.0, (g1_w * 3.0) + (c_w * 0.05))
            score += trainer_score

        # 3. 若い年齢の繁殖牝馬が優先
        age = dam.get("age", 10)
        if 4 <= age <= 7:
            score += 20.0
        elif 8 <= age <= 11:
            score += 12.0
        elif 12 <= age <= 14:
            score += 5.0
        else:
            score += 0.0  # 15歳以上は高齢のため優先度低め

        # 4. 繁殖牝馬ランキング上位が優先（競走実績・能力値）
        g1_wins = dam.get("g1_wins", 0)
        g2_wins = dam.get("g2_wins", 0)
        g3_wins = dam.get("g3_wins", 0)
        if g1_wins > 0:
            score += 35.0
        elif (g2_wins + g3_wins) > 0:
            score += 20.0
        elif dam.get("condition_prize_money", 0) >= 16_000_000:
            score += 10.0

        # 能力値（スピード＋瞬発力＋スタミナ）上位ボーナス
        avg_ability = (dam["speed"] + dam["stamina"] + dam["acceleration"]) / 3.0
        if avg_ability >= 60.0:
            score += 15.0
        elif avg_ability >= 50.0:
            score += 8.0

        # 5. 【追加提案ルール】自家生産・同牧場優先
        if dam["breeder_id"] == sire["breeder_id"]:
            score += 25.0

        # 6. 【追加提案ルール】ニックス相性ボーナス
        if is_nicks:
            score += 20.0

        # 7. 危険なインブリードに対するペナルティ
        if inbreeding_pct > 25.0:
            score -= 100.0  # 危険すぎる配合は選抜対象外
        elif inbreeding_pct > 18.75:
            score -= 40.0

        return score

    def perform_annual_breeding(self, current_year: int) -> List[int]:
        """
        1年分の交配・受胎・当歳馬誕生を一括シミュレート
        返り値: 新規誕生した当歳馬の horse_id リスト
        """
        print(f"\n==================== 【{current_year}年度 交配・出産シミュレーション】 ====================")

        newborn_ids: List[int] = []

        with self.db.session() as conn:
            print("[交配・出産] 1/4: データベースの既存馬名、厩舎成績、過去交配履歴を同期中...")
            self._sync_existing_names(conn)
            trainer_map = self._load_trainer_stats(conn)
            mating_history = self._load_mating_history(conn)

            # 1. 稼働中の種牡馬を取得
            sire_rows = conn.execute(
                """
                SELECT s.horse_id, s.breeder_id, s.sire_line, s.stud_fee,
                       h.name, h.speed, h.stamina, h.acceleration, h.temperament, h.durability,
                       h.maternal_vitality, h.mstn_type, h.growth_type, h.running_style,
                       h.trainer_id, h.g1_wins, h.g2_wins, h.g3_wins, h.career_wins
                FROM sires s
                JOIN horses h ON s.horse_id = h.horse_id
                WHERE s.is_active = 1
                """
            ).fetchall()

            if not sire_rows:
                print("[警告] 稼働中の種牡馬が存在しません。")
                return []

            sire_list = [dict(s) for s in sire_rows]
            sire_line_map: Dict[int, str] = {s["horse_id"]: s["sire_line"] for s in sire_list}

            # 2. 稼働中の繁殖牝馬を取得
            dam_rows = conn.execute(
                """
                SELECT d.horse_id, d.breeder_id,
                       h.name, h.age, h.speed, h.stamina, h.acceleration, h.temperament, h.durability,
                       h.maternal_vitality, h.mstn_type, h.growth_type, h.running_style,
                       h.owner_id, h.trainer_id, h.sire_id, h.dam_id,
                       h.g1_wins, h.g2_wins, h.g3_wins, h.career_wins,
                       h.prize_money, h.condition_prize_money
                FROM dams d
                JOIN horses h ON d.horse_id = h.horse_id
                WHERE d.is_active = 1
                """
            ).fetchall()

            if not dam_rows:
                print("[警告] 稼働中の繁殖牝馬が存在しません。")
                return []

            dam_list = [dict(d) for d in dam_rows]

            print(f"[交配・出産] 2/4: 稼働中 種牡馬 {len(sire_list)} 頭、繁殖牝馬 {len(dam_list)} 頭を確認しました。")

            # 馬主一覧の取得
            owners = conn.execute("SELECT owner_id, prefix FROM owners").fetchall()
            owner_list = [(o["owner_id"], o["prefix"]) for o in owners]

            # 種牡馬の年間種付けカウンター初期化
            sire_covering_count: Dict[int, int] = {s["horse_id"]: 0 for s in sire_list}
            sire_dict: Dict[int, Dict[str, Any]] = {s["horse_id"]: s for s in sire_list}

            # サイアーライン別の現役種牡馬数を集計（希少ライン保護）
            line_counts: Dict[str, int] = {}
            for s in sire_list:
                line_counts[s["sire_line"]] = line_counts.get(s["sire_line"], 0) + 1

            print(f"[交配・出産] 3/4: 各繁殖牝馬の希望種牡馬選定とドラフト選抜（所属厩舎・厩舎成績・若齢・実績・ニックス）を実行中...")

            # 繁殖牝馬ごとに、各種牡馬との相性を評価して希望種牡馬をランキング（第1〜第3希望）
            dam_preferences: Dict[int, List[Tuple[int, float, Dict[str, Any], Dict[str, Any]]]] = {}

            for dam in dam_list:
                dam_line = self._get_dam_sire_line(dam, sire_line_map)
                dam_tree = self.pedigree_builder.get_ancestors_tree(dam["horse_id"], depth=4)

                scored_sires = []
                # 全種牡馬からランダムサンプリング＋有力・同牧場種牡馬で候補選定（高速化のため10〜15頭候補）
                candidate_sires = random.sample(sire_list, min(15, len(sire_list)))
                # 同牧場の種牡馬は必ず候補に含める
                home_sires = [s for s in sire_list if s["breeder_id"] == dam["breeder_id"]]
                candidate_sires = list({s["horse_id"]: s for s in (candidate_sires + home_sires)}.values())

                for sire in candidate_sires:
                    s_id = sire["horse_id"]

                    # ★ 同一種牡馬再種付けルール判定（産駒G1勝利必須＆生涯最大4回上限）
                    if not self.can_mate_sire_and_dam(dam["horse_id"], s_id, mating_history):
                        continue

                    nicks_res = GeneticsEngine.check_nicks(sire["sire_line"], dam_line)

                    sire_tree = self.pedigree_builder.get_ancestors_tree(s_id, depth=4)
                    inbreeding_res = GeneticsEngine.calculate_inbreeding(sire_tree, dam_tree)

                    # 危険すぎる近親交配(25%超)は希望から除外
                    if inbreeding_res["total_blood_pct"] > 25.0:
                        continue

                    # ユーザー指定4条件＋追加ルールの優先度スコア算出
                    p_score = self.calculate_dam_priority_score(
                        dam=dam,
                        sire=sire,
                        trainer_map=trainer_map,
                        is_nicks=nicks_res["is_nicks"],
                        inbreeding_pct=inbreeding_res["total_blood_pct"],
                    )

                    # 種牡馬自身の魅力度（能力・希少ライン保護など）
                    sire_ability = (sire["speed"] + sire["stamina"] + sire["acceleration"]) / 3.0
                    attractiveness = sire_ability * 0.5
                    if line_counts.get(sire["sire_line"], 0) <= 2:
                        attractiveness += 10.0  # 希少ライン保護

                    total_match_score = p_score + attractiveness
                    scored_sires.append((s_id, total_match_score, nicks_res, inbreeding_res))

                scored_sires.sort(key=lambda x: x[1], reverse=True)
                dam_preferences[dam["horse_id"]] = scored_sires[:3]  # 上位3頭を希望

            # ドラフト方式によるマッチング実行（各種牡馬 上限30頭）
            matched_pairs: List[Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]] = []
            unmatched_dams = list(dam_list)
            random.shuffle(unmatched_dams)

            # 第1希望から順にマッチング
            for pref_idx in range(3):
                sire_applications: Dict[int, List[Tuple[Dict[str, Any], float, Dict[str, Any], Dict[str, Any]]]] = {}
                remaining_dams = []

                for dam in unmatched_dams:
                    prefs = dam_preferences.get(dam["horse_id"], [])
                    if len(prefs) > pref_idx:
                        s_id, score, nicks_res, inbr_res = prefs[pref_idx]
                        if sire_covering_count[s_id] < self.MAX_COVERINGS_PER_SIRE:
                            sire_applications.setdefault(s_id, []).append((dam, score, nicks_res, inbr_res))
                        else:
                            remaining_dams.append(dam)
                    else:
                        remaining_dams.append(dam)

                # 各種牡馬ごとに優先度スコア上位順に選抜
                for s_id, apps in sire_applications.items():
                    apps.sort(key=lambda x: x[1], reverse=True)
                    sire_obj = sire_dict[s_id]
                    capacity_left = self.MAX_COVERINGS_PER_SIRE - sire_covering_count[s_id]

                    accepted = apps[:capacity_left]
                    rejected = apps[capacity_left:]

                    for dam, _, nicks_res, inbr_res in accepted:
                        matched_pairs.append((dam, sire_obj, nicks_res, inbr_res))
                        sire_covering_count[s_id] += 1
                        # 交配履歴カウントを更新
                        rec = mating_history.setdefault((dam["horse_id"], s_id), {"foal_count": 0, "has_g1_winner": False})
                        rec["foal_count"] += 1

                    for dam, _, _, _ in rejected:
                        remaining_dams.append(dam)

                unmatched_dams = remaining_dams

            # 3希望全てで漏れた牝馬は、空き枠のある種牡馬へマッチング
            available_sires = [s for s in sire_list if sire_covering_count[s["horse_id"]] < self.MAX_COVERINGS_PER_SIRE]
            for dam in unmatched_dams:
                if not available_sires:
                    break
                # 安全な種牡馬を探す
                dam_line = self._get_dam_sire_line(dam, sire_line_map)
                dam_tree = self.pedigree_builder.get_ancestors_tree(dam["horse_id"], depth=4)

                chosen_sire = None
                chosen_nicks = None
                chosen_inbr = None

                for s in list(available_sires):
                    s_id = s["horse_id"]
                    if not self.can_mate_sire_and_dam(dam["horse_id"], s_id, mating_history):
                        continue

                    sire_tree = self.pedigree_builder.get_ancestors_tree(s_id, depth=4)
                    inbr_res = GeneticsEngine.calculate_inbreeding(sire_tree, dam_tree)
                    if inbr_res["total_blood_pct"] <= 25.0:
                        chosen_sire = s
                        chosen_nicks = GeneticsEngine.check_nicks(s["sire_line"], dam_line)
                        chosen_inbr = inbr_res
                        break

                if chosen_sire is None:
                    # ルールを満たす種牡馬の中から選択
                    valid_sires = [
                        s for s in available_sires
                        if self.can_mate_sire_and_dam(dam["horse_id"], s["horse_id"], mating_history)
                    ]
                    if valid_sires:
                        chosen_sire = random.choice(valid_sires)
                        sire_tree = self.pedigree_builder.get_ancestors_tree(chosen_sire["horse_id"], depth=4)
                        chosen_inbr = GeneticsEngine.calculate_inbreeding(sire_tree, dam_tree)
                        chosen_nicks = GeneticsEngine.check_nicks(chosen_sire["sire_line"], dam_line)
                    else:
                        continue  # 有効な種牡馬がない場合は不受胎

                matched_pairs.append((dam, chosen_sire, chosen_nicks, chosen_inbr))
                sire_covering_count[chosen_sire["horse_id"]] += 1
                rec = mating_history.setdefault((dam["horse_id"], chosen_sire["horse_id"]), {"foal_count": 0, "has_g1_winner": False})
                rec["foal_count"] += 1
                if sire_covering_count[chosen_sire["horse_id"]] >= self.MAX_COVERINGS_PER_SIRE:
                    available_sires.remove(chosen_sire)

            print(f"[交配・出産] マッチング成立: {len(matched_pairs)}組。受胎判定および当歳馬生成を開始します。")

            # 受胎判定および当歳馬誕生シミュレーション
            foal_count = 0
            colt_count = 0
            filly_count = 0
            nicks_foal_count = 0

            for dam, chosen_sire, nicks_info, inbreeding_info in matched_pairs:
                if foal_count >= self.TARGET_FOAL_COUNT:
                    break

                # 受胎判定 (受胎率 88%)
                if random.random() > 0.88:
                    continue  # 不受胎

                # 牡馬・牝馬同数（各300頭）制御
                target_each = self.TARGET_FOAL_COUNT // 2
                if colt_count < target_each and filly_count < target_each:
                    is_colt = (random.random() < 0.5)
                elif colt_count < target_each:
                    is_colt = True
                else:
                    is_colt = False

                sex_str = "colt" if is_colt else "filly"
                if is_colt:
                    colt_count += 1
                else:
                    filly_count += 1
                foal_count += 1

                if nicks_info.get("is_nicks", False):
                    nicks_foal_count += 1

                # 馬主と冠名の決定
                if random.random() < 0.60 and dam.get("owner_id"):
                    owner_id = dam["owner_id"]
                    p_row = conn.execute("SELECT prefix FROM owners WHERE owner_id = ?", (owner_id,)).fetchone()
                    prefix = p_row["prefix"] if p_row else None
                else:
                    owner_id, prefix = random.choice(owner_list)

                # 馬名の生成 (純カタカナ・重複防止)
                foal_name = self.name_gen.generate_name(prefix=prefix, sex=sex_str)

                # 遺伝値の計算
                mstn = GeneticsEngine.sample_mstn_offspring(
                    GenotypeMSTN(chosen_sire["mstn_type"]),
                    GenotypeMSTN(dam["mstn_type"]),
                )
                speed = GeneticsEngine.calculate_polygenic_stat(chosen_sire["speed"], dam["speed"])
                stamina = GeneticsEngine.calculate_polygenic_stat(chosen_sire["stamina"], dam["stamina"])
                accel = GeneticsEngine.calculate_polygenic_stat(chosen_sire["acceleration"], dam["acceleration"])
                temp = GeneticsEngine.calculate_polygenic_stat(chosen_sire["temperament"], dam["temperament"])
                dura = GeneticsEngine.calculate_polygenic_stat(chosen_sire["durability"], dam["durability"])
                vitality = GeneticsEngine.calculate_maternal_vitality(chosen_sire["maternal_vitality"], dam["maternal_vitality"])

                # ★ 血統規制（5代血統表・両親の特性による適性規制）
                sire_tree_5 = self.pedigree_builder.get_ancestors_tree(chosen_sire["horse_id"], depth=5)
                dam_tree_5 = self.pedigree_builder.get_ancestors_tree(dam["horse_id"], depth=5)
                ped_apt = GeneticsEngine.calculate_pedigree_aptitude(
                    sire_mstn=GenotypeMSTN(chosen_sire["mstn_type"]),
                    dam_mstn=GenotypeMSTN(dam["mstn_type"]),
                    sire_surface="turf",
                    dam_surface="turf",
                    sire_ancestors=sire_tree_5,
                    dam_ancestors=dam_tree_5,
                )
                if ped_apt.get("stamina_max_clamp") is not None:
                    stamina = min(stamina, ped_apt["stamina_max_clamp"])

                # インブリード効果の適用
                speed += inbreeding_info["speed_bonus"]
                accel += inbreeding_info["accel_bonus"]
                temp -= inbreeding_info["temp_penalty"]
                dura -= inbreeding_info["dura_penalty"]

                # ★ ニックス効果の適用（スピード・瞬発力・底力にボーナス）
                if nicks_info.get("is_nicks", False):
                    speed += nicks_info.get("speed_bonus", 0.0)
                    accel += nicks_info.get("accel_bonus", 0.0)
                    vitality += nicks_info.get("vitality_bonus", 0.0)

                speed = round(max(10.0, min(95.0, speed)), 1)
                accel = round(max(10.0, min(95.0, accel)), 1)
                stamina = round(max(10.0, min(95.0, stamina)), 1)
                temp = round(max(10.0, min(95.0, temp)), 1)
                dura = round(max(10.0, min(95.0, dura)), 1)
                vitality = round(max(10.0, min(95.0, vitality)), 1)

                growth_type, peak_age = GeneticsEngine.inherit_growth_type(
                    GrowthType(chosen_sire["growth_type"]),
                    GrowthType(dam["growth_type"]),
                )
                running_style = Horse.determine_running_style(
                    speed, stamina, accel, dura
                )

                # DBへ INSERT
                cursor = conn.execute(
                    """
                    INSERT INTO horses (
                        name, sex, birth_year, age, breeder_id, owner_id,
                        sire_id, dam_id,
                        is_active, is_sire, is_dam, mstn_type,
                        speed, stamina, acceleration, temperament, durability, maternal_vitality,
                        growth_type, peak_age, current_ability_rate, running_style,
                        career_starts, career_wins, g1_wins, g2_wins, g3_wins, major_wins, prize_money, condition_prize_money
                    ) VALUES (
                        ?, ?, ?, 0, ?, ?,
                        ?, ?,
                        0, 0, 0, ?,
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, 0.2, ?,
                        0, 0, 0, 0, 0, '', 0, 0
                    )
                    """,
                    (
                        foal_name, sex_str, current_year, dam["breeder_id"], owner_id,
                        chosen_sire["horse_id"], dam["horse_id"],
                        mstn.value,
                        speed, stamina, accel, temp, dura, vitality,
                        growth_type.value, peak_age, running_style.value,
                    ),
                )
                newborn_ids.append(cursor.lastrowid)

            print(f"[交配・出産] 4/4: 全{len(newborn_ids)}頭（牡: {colt_count}頭、牝: {filly_count}頭、ニックス成立: {nicks_foal_count}頭）の当歳馬をスタッドブックへ登録完了。")

        print("=================================================================================\n")
        return newborn_ids
