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
from src.models.horse import GenotypeMSTN, GrowthType, Horse, RunningStyle
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

    def _ensure_matings_table(self, conn) -> None:
        """交配・受胎記録テーブルを作成"""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS matings (
                mating_id INTEGER PRIMARY KEY AUTOINCREMENT,
                mating_year INTEGER NOT NULL,
                dam_id INTEGER NOT NULL,
                sire_id INTEGER NOT NULL,
                is_nicks INTEGER NOT NULL DEFAULT 0,
                nicks_speed_bonus REAL NOT NULL DEFAULT 0.0,
                nicks_accel_bonus REAL NOT NULL DEFAULT 0.0,
                nicks_vitality_bonus REAL NOT NULL DEFAULT 0.0,
                inbreeding_speed_bonus REAL NOT NULL DEFAULT 0.0,
                inbreeding_accel_bonus REAL NOT NULL DEFAULT 0.0,
                inbreeding_temp_penalty REAL NOT NULL DEFAULT 0.0,
                inbreeding_dura_penalty REAL NOT NULL DEFAULT 0.0,
                inbreeding_pct REAL NOT NULL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def _calculate_sire_capacities(
        self, conn: Any, current_year: int, sire_list: List[Dict[str, Any]]
    ) -> Dict[int, int]:
        """
        種牡馬ごとの年間種付け可能頭数を決定（合計600頭を厳密に維持）
        - 就任1〜5年目: 基本6頭
        - 就任6年目以降:
          - 通算実績（全産駒のG1・重賞・賞金）＋直近3年の産駒実績＋自身の実績による総合評価
          - 成績最上位層: 最大25〜30頭
          - 上位層: 15〜24頭
          - 中位層: 6〜14頭
          - 下位層: 最低2〜4頭
          - 前年キャパシティからの急激な減少を防止（前年比フロアガード）
          - 全種牡馬に最低1頭種付けを完全保証
        """
        target_total = self.TARGET_FOAL_COUNT  # 600頭
        capacities: Dict[int, int] = {}
        
        # 1. 産駒の通算実績と直近3年実績を集計
        # 通算実績
        all_child_stats_rows = conn.execute(
            """
            SELECT
                c.sire_id,
                COUNT(c.horse_id) as total_foals,
                SUM(c.g1_wins) as total_g1,
                SUM(c.g2_wins + c.g3_wins) as total_graded,
                SUM(c.career_wins) as total_wins,
                SUM(c.prize_money) as total_prize,
                MAX(c.g1_wins) as max_g1,
                MAX(c.g2_wins + c.g3_wins) as max_graded
            FROM horses c
            WHERE c.sire_id IS NOT NULL
            GROUP BY c.sire_id
            """
        ).fetchall()
        all_stats: Dict[int, Dict[str, Any]] = {
            r["sire_id"]: {
                "total_foals": r["total_foals"] or 0,
                "total_g1": r["total_g1"] or 0,
                "total_graded": r["total_graded"] or 0,
                "total_wins": r["total_wins"] or 0,
                "total_prize": r["total_prize"] or 0,
                "max_g1": r["max_g1"] or 0,
                "max_graded": r["max_graded"] or 0,
            }
            for r in all_child_stats_rows
        }

        # 現役産駒の実績
        active_child_stats_rows = conn.execute(
            """
            SELECT
                c.sire_id,
                COUNT(c.horse_id) as active_foals,
                SUM(c.g1_wins) as active_g1,
                SUM(c.g2_wins + c.g3_wins) as active_graded,
                SUM(c.prize_money) as active_prize,
                MAX(c.g1_wins) as active_max_g1,
                MAX(c.g2_wins + c.g3_wins) as active_max_graded
            FROM horses c
            WHERE c.sire_id IS NOT NULL AND c.is_active = 1
            GROUP BY c.sire_id
            """
        ).fetchall()
        active_stats: Dict[int, Dict[str, Any]] = {
            r["sire_id"]: {
                "active_foals": r["active_foals"] or 0,
                "active_g1": r["active_g1"] or 0,
                "active_graded": r["active_graded"] or 0,
                "active_prize": r["active_prize"] or 0,
                "active_max_g1": r["active_max_g1"] or 0,
                "active_max_graded": r["active_max_graded"] or 0,
            }
            for r in active_child_stats_rows
        }

        # sires テーブルの start_year, max_coverings(前年値) 情報を取得
        sires_db_rows = conn.execute(
            "SELECT horse_id, start_year, max_coverings FROM sires WHERE is_active = 1"
        ).fetchall()
        sires_db_map: Dict[int, Dict[str, Any]] = {
            r["horse_id"]: {
                "start_year": (r["start_year"] if "start_year" in r.keys() and r["start_year"] else 1),
                "last_max_coverings": (r["max_coverings"] if "max_coverings" in r.keys() and r["max_coverings"] else 6),
            }
            for r in sires_db_rows
        }

        # 各種牡馬のスコア算出
        sire_scores: Dict[int, float] = {}
        for sire in sire_list:
            s_id = sire["horse_id"]
            db_info = sires_db_map.get(s_id, {"start_year": 1, "last_max_coverings": 6})
            start_yr = db_info["start_year"]
            years_in_service = current_year - start_yr + 1
            ast = all_stats.get(s_id, {"total_foals": 0, "total_g1": 0, "total_graded": 0, "total_wins": 0, "total_prize": 0, "max_g1": 0, "max_graded": 0})
            act = active_stats.get(s_id, {"active_foals": 0, "active_g1": 0, "active_graded": 0, "active_prize": 0, "active_max_g1": 0, "active_max_graded": 0})

            # 基礎能力値スコア
            s_ability = (sire.get("speed", 10.0) + sire.get("stamina", 10.0) + sire.get("acceleration", 10.0)) / 3.0
            own_g1 = sire.get("g1_wins", 0) or 0
            own_graded = (sire.get("g2_wins", 0) or 0) + (sire.get("g3_wins", 0) or 0)

            if years_in_service <= 5:
                # 1〜5年目は基礎点中心（一律6〜8頭ベース）
                score = 50.0 + (s_ability - 10.0) * 2.0 + own_g1 * 10.0 + own_graded * 3.0
            else:
                # 6年目以降: 通算実績 + 現役実績の複合スコア
                score = 30.0 + (s_ability - 10.0)
                score += own_g1 * 5.0
                # 通算産駒実績
                score += ast["total_g1"] * 25.0
                score += ast["total_graded"] * 8.0
                score += (ast["total_prize"] / 50_000_000)
                # 現役産駒実績（直近の勢い）
                score += act["active_g1"] * 30.0
                score += act["active_graded"] * 12.0
                score += (act["active_prize"] / 30_000_000)

                # 最高実績ボーナス
                if ast["max_g1"] > 0:
                    score += 20.0
                elif ast["max_graded"] > 0:
                    score += 10.0

            sire_scores[s_id] = max(10.0, score)

        # スコア順にソートして割り当て
        sorted_sires = sorted(sire_list, key=lambda s: sire_scores[s["horse_id"]], reverse=True)
        raw_caps: Dict[int, int] = {}

        for rank, sire in enumerate(sorted_sires, 1):
            s_id = sire["horse_id"]
            db_info = sires_db_map.get(s_id, {"start_year": 1, "last_max_coverings": 6})
            start_yr = db_info["start_year"]
            last_cap = db_info["last_max_coverings"]
            years_in_service = current_year - start_yr + 1
            score = sire_scores[s_id]
            ast = all_stats.get(s_id, {"total_foals": 0, "total_g1": 0, "total_graded": 0, "total_wins": 0, "total_prize": 0, "max_g1": 0, "max_graded": 0})

            if years_in_service <= 5:
                # 若手種牡馬: 6頭
                base_cap = 6
            else:
                # 実績上位層への集中（最大25〜30頭）
                if rank <= 3 and (ast["total_g1"] > 0 or ast["total_graded"] >= 2 or score > 150):
                    base_cap = random.randint(26, 30)
                elif rank <= 8 and (ast["total_g1"] > 0 or ast["total_graded"] > 0 or score > 100):
                    base_cap = random.randint(18, 25)
                elif rank <= 15 and (ast["total_graded"] > 0 or score > 60):
                    base_cap = random.randint(12, 17)
                elif rank <= 30:
                    base_cap = random.randint(6, 11)
                elif score > 40:
                    base_cap = random.randint(4, 6)
                else:
                    base_cap = random.randint(2, 4)

                # 前年キャパシティからの急落を防止（前年の70%を下回らないガード）
                floor_cap = max(1, int(last_cap * 0.70))
                base_cap = max(base_cap, floor_cap)

            raw_caps[s_id] = max(1, min(self.MAX_COVERINGS_PER_SIRE, base_cap))

        # 合計が 600 頭になるように按分・微調整（全頭最低1頭は厳守）
        total_raw = sum(raw_caps.values())
        diff = target_total - total_raw

        capacities = raw_caps.copy()
        if diff != 0:
            all_s_ids = list(capacities.keys())
            if diff > 0:
                # 不足分を上位から最大30頭まで均等加算
                for s_id in sorted(all_s_ids, key=lambda sid: sire_scores[sid], reverse=True):
                    if diff <= 0:
                        break
                    addable = min(diff, self.MAX_COVERINGS_PER_SIRE - capacities[s_id])
                    if addable > 0:
                        capacities[s_id] += 1
                        diff -= 1
                # それでも余る場合は全種牡馬で上限まで
                while diff > 0:
                    added_any = False
                    for s_id in all_s_ids:
                        if diff <= 0:
                            break
                        if capacities[s_id] < self.MAX_COVERINGS_PER_SIRE:
                            capacities[s_id] += 1
                            diff -= 1
                            added_any = True
                    if not added_any:
                        break
            elif diff < 0:
                # 超過分を下位から（最低1頭を保ちつつ）減算
                for s_id in sorted(all_s_ids, key=lambda sid: sire_scores[sid]):
                    if diff >= 0:
                        break
                    if capacities[s_id] > 1:
                        capacities[s_id] -= 1
                        diff += 1
                while diff < 0:
                    reduced_any = False
                    for s_id in reversed(sorted(all_s_ids, key=lambda sid: sire_scores[sid])):
                        if diff >= 0:
                            break
                        if capacities[s_id] > 1:
                            capacities[s_id] -= 1
                            diff += 1
                            reduced_any = True
                    if not reduced_any:
                        break

        # DBの max_coverings を更新（次年度のフロア計算用）
        for s_id, cap in capacities.items():
            conn.execute("UPDATE sires SET max_coverings = ? WHERE horse_id = ?", (cap, s_id))

        return capacities

    def _match_sires_and_dams(
        self, conn, current_year: int
    ) -> List[Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]]:
        """
        供用中種牡馬と繁殖牝馬のマッチング（最大30頭制限・ドラフト選抜）を実行
        """
        self._sync_existing_names(conn)
        trainer_map = self._load_trainer_stats(conn)
        mating_history = self._load_mating_history(conn)

        # 1. 稼働中の種牡馬を取得
        sire_rows = conn.execute(
            """
            SELECT s.horse_id, s.breeder_id, s.sire_line, s.stud_fee, s.generation as sire_generation, s.is_foreign,
                   h.name, h.speed, h.stamina, h.acceleration, h.temperament, h.durability,
                   h.maternal_vitality, h.mstn_type, h.growth_type, h.running_style,
                   h.coat_color, h.coat_genotype,
                   h.trainer_id, h.g1_wins, h.g2_wins, h.g3_wins, h.career_wins,
                   h.sire_id as sire_parent_id, h.generation as horse_generation
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
                   h.coat_color, h.coat_genotype,
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

        print(f"[交配選抜] 稼働中 種牡馬 {len(sire_list)} 頭、繁殖牝馬 {len(dam_list)} 頭のマッチングを開始します。")

        # 種牡馬ごとの種付け可能頭数を算定 (合計600頭)
        sire_capacities = self._calculate_sire_capacities(conn, current_year, sire_list)
        sire_covering_count: Dict[int, int] = {s["horse_id"]: 0 for s in sire_list}
        sire_dict: Dict[int, Dict[str, Any]] = {s["horse_id"]: s for s in sire_list}

        line_counts: Dict[str, int] = {}
        for s in sire_list:
            line_counts[s["sire_line"]] = line_counts.get(s["sire_line"], 0) + 1

        # 繁殖牝馬ごとに希望種牡馬を選定
        dam_preferences: Dict[int, List[Tuple[int, float, Dict[str, Any], Dict[str, Any]]]] = {}

        for dam in dam_list:
            dam_line = self._get_dam_sire_line(dam, sire_line_map)
            dam_tree = self.pedigree_builder.get_ancestors_tree(dam["horse_id"], depth=4, conn=conn)

            scored_sires = []
            candidate_sires = random.sample(sire_list, min(15, len(sire_list)))
            home_sires = [s for s in sire_list if s["breeder_id"] == dam["breeder_id"]]
            candidate_sires = list({s["horse_id"]: s for s in (candidate_sires + home_sires)}.values())

            for sire in candidate_sires:
                s_id = sire["horse_id"]

                if not self.can_mate_sire_and_dam(dam["horse_id"], s_id, mating_history):
                    continue

                nicks_res = GeneticsEngine.check_nicks(sire["sire_line"], dam_line)
                sire_tree = self.pedigree_builder.get_ancestors_tree(s_id, depth=4, conn=conn)
                inbreeding_res = GeneticsEngine.calculate_inbreeding(sire_tree, dam_tree)

                if inbreeding_res["total_blood_pct"] > 25.0:
                    continue

                p_score = self.calculate_dam_priority_score(
                    dam=dam,
                    sire=sire,
                    trainer_map=trainer_map,
                    is_nicks=nicks_res["is_nicks"],
                    inbreeding_pct=inbreeding_res["total_blood_pct"],
                )

                sire_ability = (sire["speed"] + sire["stamina"] + sire["acceleration"]) / 3.0
                attractiveness = sire_ability * 0.5
                if sire.get("is_foreign"):
                    attractiveness += 15.0  # 海外の有力種牡馬は配合人気が高い
                if line_counts.get(sire["sire_line"], 0) <= 2:
                    attractiveness += 10.0

                total_match_score = p_score + attractiveness
                scored_sires.append((s_id, total_match_score, nicks_res, inbreeding_res))

            scored_sires.sort(key=lambda x: x[1], reverse=True)
            dam_preferences[dam["horse_id"]] = scored_sires[:3]

        # ドラフト選抜
        matched_pairs: List[Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]] = []
        unmatched_dams = list(dam_list)
        random.shuffle(unmatched_dams)

        for pref_idx in range(3):
            sire_applications: Dict[int, List[Tuple[Dict[str, Any], float, Dict[str, Any], Dict[str, Any]]]] = {}
            remaining_dams = []

            for dam in unmatched_dams:
                prefs = dam_preferences.get(dam["horse_id"], [])
                if len(prefs) > pref_idx:
                    s_id, score, nicks_res, inbr_res = prefs[pref_idx]
                    s_cap = sire_capacities.get(s_id, 6)
                    if sire_covering_count[s_id] < s_cap:
                        sire_applications.setdefault(s_id, []).append((dam, score, nicks_res, inbr_res))
                    else:
                        remaining_dams.append(dam)
                else:
                    remaining_dams.append(dam)

            for s_id, apps in sire_applications.items():
                apps.sort(key=lambda x: x[1], reverse=True)
                sire_obj = sire_dict[s_id]
                s_cap = sire_capacities.get(s_id, 6)
                capacity_left = s_cap - sire_covering_count[s_id]

                accepted = apps[:capacity_left]
                rejected = apps[capacity_left:]

                for dam, _, nicks_res, inbr_res in accepted:
                    matched_pairs.append((dam, sire_obj, nicks_res, inbr_res))
                    sire_covering_count[s_id] += 1
                    rec = mating_history.setdefault((dam["horse_id"], s_id), {"foal_count": 0, "has_g1_winner": False})
                    rec["foal_count"] += 1

                for dam, _, _, _ in rejected:
                    remaining_dams.append(dam)

            unmatched_dams = remaining_dams

        available_sires = [s for s in sire_list if sire_covering_count[s["horse_id"]] < sire_capacities.get(s["horse_id"], 6)]
        
        # 最低1頭保証: まだ1頭も種付けされていない種牡馬を優先して割り当て
        zero_cover_sires = [s for s in available_sires if sire_covering_count[s["horse_id"]] == 0]
        if zero_cover_sires and unmatched_dams:
            for s in list(zero_cover_sires):
                if not unmatched_dams:
                    break
                s_id = s["horse_id"]
                chosen_dam_idx = -1
                best_dam_nicks = None
                best_dam_inbr = None
                
                # 最も相性の良い牝馬を探す
                for d_idx, dam in enumerate(unmatched_dams):
                    if not self.can_mate_sire_and_dam(dam["horse_id"], s_id, mating_history):
                        continue
                    dam_tree = self.pedigree_builder.get_ancestors_tree(dam["horse_id"], depth=4, conn=conn)
                    sire_tree = self.pedigree_builder.get_ancestors_tree(s_id, depth=4, conn=conn)
                    inbr_res = GeneticsEngine.calculate_inbreeding(sire_tree, dam_tree)
                    if inbr_res["total_blood_pct"] <= 25.0:
                        chosen_dam_idx = d_idx
                        dam_line = self._get_dam_sire_line(dam, sire_line_map)
                        best_dam_nicks = GeneticsEngine.check_nicks(s["sire_line"], dam_line)
                        best_dam_inbr = inbr_res
                        break
                
                if chosen_dam_idx >= 0:
                    dam = unmatched_dams.pop(chosen_dam_idx)
                    matched_pairs.append((dam, s, best_dam_nicks, best_dam_inbr))
                    sire_covering_count[s_id] += 1
                    rec = mating_history.setdefault((dam["horse_id"], s_id), {"foal_count": 0, "has_g1_winner": False})
                    rec["foal_count"] += 1
                    if sire_covering_count[s_id] >= sire_capacities.get(s_id, 6):
                        if s in available_sires:
                            available_sires.remove(s)

        # 残りの牝馬を空きスロットへ割り当て
        for dam in unmatched_dams:
            if not available_sires:
                break
            dam_line = self._get_dam_sire_line(dam, sire_line_map)
            dam_tree = self.pedigree_builder.get_ancestors_tree(dam["horse_id"], depth=4, conn=conn)

            chosen_sire = None
            chosen_nicks = None
            chosen_inbr = None

            # 種付け数がまだ少ない種牡馬を優先
            available_sires.sort(key=lambda s: (sire_covering_count[s["horse_id"]], -s.get("speed", 10.0)))

            for s in list(available_sires):
                s_id = s["horse_id"]
                if not self.can_mate_sire_and_dam(dam["horse_id"], s_id, mating_history):
                    continue
                sire_tree = self.pedigree_builder.get_ancestors_tree(s_id, depth=4, conn=conn)
                inbr_res = GeneticsEngine.calculate_inbreeding(sire_tree, dam_tree)
                if inbr_res["total_blood_pct"] <= 25.0:
                    chosen_sire = s
                    chosen_nicks = GeneticsEngine.check_nicks(s["sire_line"], dam_line)
                    chosen_inbr = inbr_res
                    break

            if chosen_sire is None:
                valid_sires = [
                    s for s in available_sires
                    if self.can_mate_sire_and_dam(dam["horse_id"], s["horse_id"], mating_history)
                ]
                if valid_sires:
                    chosen_sire = random.choice(valid_sires)
                elif available_sires:
                    chosen_sire = random.choice(available_sires)
                else:
                    continue

                sire_tree = self.pedigree_builder.get_ancestors_tree(chosen_sire["horse_id"], depth=4, conn=conn)
                chosen_inbr = GeneticsEngine.calculate_inbreeding(sire_tree, dam_tree)
                chosen_nicks = GeneticsEngine.check_nicks(chosen_sire["sire_line"], dam_line)

            matched_pairs.append((dam, chosen_sire, chosen_nicks, chosen_inbr))
            sire_covering_count[chosen_sire["horse_id"]] += 1
            rec = mating_history.setdefault((dam["horse_id"], chosen_sire["horse_id"]), {"foal_count": 0, "has_g1_winner": False})
            rec["foal_count"] += 1
            if sire_covering_count[chosen_sire["horse_id"]] >= sire_capacities.get(chosen_sire["horse_id"], 6):
                available_sires.remove(chosen_sire)

        # 最終チェック: もし万が一まだ種付け0頭の種牡馬がいる場合、複数頭割り当て済みの種牡馬から1頭振り替え
        zero_sires = [s for s in sire_list if sire_covering_count[s["horse_id"]] == 0]
        if zero_sires:
            for zs in zero_sires:
                zs_id = zs["horse_id"]
                for p_idx, (dam, cur_sire, nicks_res, inbr_res) in enumerate(matched_pairs):
                    cur_s_id = cur_sire["horse_id"]
                    if sire_covering_count[cur_s_id] > 1 and self.can_mate_sire_and_dam(dam["horse_id"], zs_id, mating_history):
                        dam_line = self._get_dam_sire_line(dam, sire_line_map)
                        dam_tree = self.pedigree_builder.get_ancestors_tree(dam["horse_id"], depth=4, conn=conn)
                        zs_tree = self.pedigree_builder.get_ancestors_tree(zs_id, depth=4, conn=conn)
                        zs_inbr = GeneticsEngine.calculate_inbreeding(zs_tree, dam_tree)
                        if zs_inbr["total_blood_pct"] <= 25.0:
                            zs_nicks = GeneticsEngine.check_nicks(zs["sire_line"], dam_line)
                            matched_pairs[p_idx] = (dam, zs, zs_nicks, zs_inbr)
                            sire_covering_count[cur_s_id] -= 1
                            sire_covering_count[zs_id] += 1
                            rec_old = mating_history.get((dam["horse_id"], cur_s_id))
                            if rec_old and rec_old["foal_count"] > 0:
                                rec_old["foal_count"] -= 1
                            rec_new = mating_history.setdefault((dam["horse_id"], zs_id), {"foal_count": 0, "has_g1_winner": False})
                            rec_new["foal_count"] += 1
                            break

        return matched_pairs

    def perform_spring_mating(self, current_year: int, conn: Optional[Any] = None) -> Dict[str, Any]:
        """
        毎年4月: 供用中種牡馬×繁殖牝馬の種付け交配イベント
        受胎ペアを matings テーブルに記録
        """
        print(f"\n==================== 【第{current_year}年度 4月 春季種付け交配イベント】 ====================")
        if conn is not None:
            return self._perform_spring_mating_impl(conn, current_year)
        else:
            with self.db.session() as s_conn:
                return self._perform_spring_mating_impl(s_conn, current_year)

    def _perform_spring_mating_impl(self, conn: Any, current_year: int) -> Dict[str, Any]:
        self._ensure_matings_table(conn)

        # 既に当年4月の種付け記録が存在するかチェック
        existing = conn.execute("SELECT COUNT(*) FROM matings WHERE mating_year = ?", (current_year,)).fetchone()[0]
        if existing > 0:
            print(f"[4月種付け] 既に第{current_year}年度の種付け（{existing}頭）が完了しています。")
            return {"year": current_year, "mated_count": existing, "already_done": True}

        matched_pairs = self._match_sires_and_dams(conn, current_year)
        if not matched_pairs:
            print("[警告] 交配ペアが成立しませんでした。")
            return {"year": current_year, "mated_count": 0, "already_done": False}

        # matings テーブルに INSERT
        for dam, chosen_sire, nicks_info, inbr_info in matched_pairs:
            conn.execute(
                """
                INSERT INTO matings (
                    mating_year, dam_id, sire_id,
                    is_nicks, nicks_speed_bonus, nicks_accel_bonus, nicks_vitality_bonus,
                    inbreeding_speed_bonus, inbreeding_accel_bonus, inbreeding_temp_penalty, inbreeding_dura_penalty, inbreeding_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    current_year, dam["horse_id"], chosen_sire["horse_id"],
                    1 if nicks_info.get("is_nicks") else 0,
                    float(nicks_info.get("speed_bonus", 0.0)),
                    float(nicks_info.get("accel_bonus", 0.0)),
                    float(nicks_info.get("vitality_bonus", 0.0)),
                    float(inbr_info.get("speed_bonus", 0.0)),
                    float(inbr_info.get("accel_bonus", 0.0)),
                    float(inbr_info.get("temp_penalty", 0.0)),
                    float(inbr_info.get("dura_penalty", 0.0)),
                    float(inbr_info.get("total_blood_pct", 0.0)),
                ),
            )

        print(f"[4月種付け] 全{len(matched_pairs)}組の交配・受胎が完了しました。（翌年3月に出産予定）")
        print("=================================================================================\n")
        return {
            "year": current_year,
            "mated_count": len(matched_pairs),
            "already_done": False,
        }

    def perform_spring_foaling(self, current_year: int, conn: Optional[Any] = None) -> List[int]:
        """
        毎年3月: 前年4月に種付けされた受胎馬から当歳馬（0歳）が誕生する出産イベント
        返り値: 新規誕生した当歳馬の horse_id リスト
        """
        print(f"\n==================== 【第{current_year}年度 3月 春季当歳馬誕生（出産）イベント】 ====================")
        if conn is not None:
            return self._perform_spring_foaling_impl(conn, current_year)
        else:
            with self.db.session() as s_conn:
                return self._perform_spring_foaling_impl(s_conn, current_year)

    def _perform_spring_foaling_impl(self, conn: Any, current_year: int) -> List[int]:
        newborn_ids: List[int] = []
        self._ensure_matings_table(conn)
        self._sync_existing_names(conn)

        # 既に当年生まれの0歳馬がDBに存在するかチェック (birth_year = current_year, age = 0)
        existing_foals = conn.execute(
            "SELECT COUNT(*) FROM horses WHERE birth_year = ? AND age = 0",
            (current_year,),
        ).fetchone()[0]

        if existing_foals >= self.TARGET_FOAL_COUNT:
            print(f"[3月出産] 既に第{current_year}年度生まれの当歳馬（{existing_foals}頭）が登録済みです。")
            rows = conn.execute("SELECT horse_id FROM horses WHERE birth_year = ? AND age = 0", (current_year,)).fetchall()
            return [r["horse_id"] for r in rows]

        # 前年（current_year - 1）の交配データを取得
        mating_year = current_year - 1
        mating_rows = conn.execute(
            """
            SELECT m.*,
                   s.horse_id as sire_horse_id, s.breeder_id as sire_breeder_id, s.generation as sire_generation, s.is_foreign as sire_is_foreign,
                   s_h.name as sire_name, s_h.speed as sire_speed, s_h.stamina as sire_stamina, s_h.acceleration as sire_accel,
                   s_h.temperament as sire_temp, s_h.durability as sire_dura, s_h.maternal_vitality as sire_vitality,
                   s_h.mstn_type as sire_mstn, s_h.growth_type as sire_growth, s_h.running_style as sire_style,
                   s_h.coat_color as sire_coat_color, s_h.coat_genotype as sire_coat_genotype, s_h.generation as sire_h_generation,
                   s_h.sire_id as sire_parent_id,
                   d.horse_id as dam_horse_id, d.breeder_id as dam_breeder_id, d.generation as dam_generation,
                   d_h.name as dam_name, d_h.speed as dam_speed, d_h.stamina as dam_stamina, d_h.acceleration as dam_accel,
                   d_h.temperament as dam_temp, d_h.durability as dam_dura, d_h.maternal_vitality as dam_vitality,
                   d_h.mstn_type as dam_mstn, d_h.growth_type as dam_growth, d_h.running_style as dam_style,
                   d_h.coat_color as dam_coat_color, d_h.coat_genotype as dam_coat_genotype, d_h.generation as dam_h_generation,
                   d_h.owner_id as dam_owner_id,
                   d_h.g1_wins as dam_g1_wins, d_h.g2_wins as dam_g2_wins, d_h.g3_wins as dam_g3_wins
            FROM matings m
            JOIN sires s ON m.sire_id = s.horse_id
            JOIN horses s_h ON s.horse_id = s_h.horse_id
            JOIN dams d ON m.dam_id = d.horse_id
            JOIN horses d_h ON d.horse_id = d_h.horse_id
            WHERE m.mating_year = ?
            """,
            (mating_year,),
        ).fetchall()

        # もし前年の交配データが存在しない場合は、即時マッチングして生成
        if not mating_rows:
            print(f"[3月出産] 前年（第{mating_year}年）の交配データが見つからないため、新規交配マッチングを実行して出産します...")
            matched_pairs = self._match_sires_and_dams(conn, mating_year)
            pairs_to_process = []
            for dam, sire, nicks_res, inbr_res in matched_pairs:
                s_gen = max(int(sire.get("sire_generation", 1) or 1), int(sire.get("horse_generation", 1) or 1))
                d_gen = max(int(dam.get("dam_generation", 1) or 1), int(dam.get("generation", 1) or 1))
                pairs_to_process.append({
                    "dam_id": dam["horse_id"], "sire_id": sire["horse_id"],
                    "sire_generation": s_gen,
                    "sire_is_foreign": sire.get("is_foreign", 0),
                    "sire_parent_id": sire.get("sire_parent_id") or sire.get("sire_id"),
                    "dam_generation": d_gen,
                    "dam_breeder_id": dam["breeder_id"], "dam_owner_id": dam.get("owner_id"),
                    "dam_g1_wins": dam.get("g1_wins", 0),
                    "dam_g2_wins": dam.get("g2_wins", 0),
                    "dam_g3_wins": dam.get("g3_wins", 0),
                    "sire_speed": sire["speed"], "sire_stamina": sire["stamina"], "sire_accel": sire["acceleration"],
                    "sire_temp": sire["temperament"], "sire_dura": sire["durability"], "sire_vitality": sire["maternal_vitality"],
                    "sire_mstn": sire["mstn_type"], "sire_growth": sire["growth_type"],
                    "sire_coat_genotype": sire.get("coat_genotype"),
                    "dam_speed": dam["speed"], "dam_stamina": dam["stamina"], "dam_accel": dam["acceleration"],
                    "dam_temp": dam["temperament"], "dam_dura": dam["durability"], "dam_vitality": dam["maternal_vitality"],
                    "dam_mstn": dam["mstn_type"], "dam_growth": dam["growth_type"],
                    "dam_coat_genotype": dam.get("coat_genotype"),
                    "is_nicks": 1 if nicks_res.get("is_nicks") else 0,
                    "nicks_speed_bonus": nicks_res.get("speed_bonus", 0.0),
                    "nicks_accel_bonus": nicks_res.get("accel_bonus", 0.0),
                    "nicks_vitality_bonus": nicks_res.get("vitality_bonus", 0.0),
                    "inbreeding_speed_bonus": inbr_res.get("speed_bonus", 0.0),
                    "inbreeding_accel_bonus": inbr_res.get("accel_bonus", 0.0),
                    "inbreeding_temp_penalty": inbr_res.get("temp_penalty", 0.0),
                    "inbreeding_dura_penalty": inbr_res.get("dura_penalty", 0.0),
                })
        else:
            pairs_to_process = []
            for r in mating_rows:
                rd = dict(r)
                s_gen = max(int(rd.get("sire_generation", 1) or 1), int(rd.get("sire_h_generation", 1) or 1))
                d_gen = max(int(rd.get("dam_generation", 1) or 1), int(rd.get("dam_h_generation", 1) or 1))
                rd["sire_generation"] = s_gen
                rd["dam_generation"] = d_gen
                rd["sire_is_foreign"] = rd.get("sire_is_foreign", 0)
                pairs_to_process.append(rd)

        owners = conn.execute("SELECT owner_id, prefix FROM owners").fetchall()
        owner_list = [(o["owner_id"], o["prefix"]) for o in owners]

        colt_count = 0
        filly_count = 0
        foal_count = 0
        target_each = self.TARGET_FOAL_COUNT // 2

        for p in pairs_to_process:
            if foal_count >= self.TARGET_FOAL_COUNT:
                break

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

            # 馬主決定
            if random.random() < 0.60 and p.get("dam_owner_id"):
                owner_id = p["dam_owner_id"]
                p_row = conn.execute("SELECT prefix FROM owners WHERE owner_id = ?", (owner_id,)).fetchone()
                prefix = p_row["prefix"] if p_row else None
            else:
                owner_id, prefix = random.choice(owner_list)

            foal_name = self.name_gen.generate_name(prefix=prefix, sex=sex_str)

            mstn = GeneticsEngine.sample_mstn_offspring(
                GenotypeMSTN(p["sire_mstn"]),
                GenotypeMSTN(p["dam_mstn"]),
            )

            # スピード能力: 世代進化・新種牡馬・繁殖牝馬能力・配合相性連動モデル
            sire_gen = int(p.get("sire_generation", 1) or 1)
            dam_g1 = int(p.get("dam_g1_wins", 0) or 0)
            dam_g_all = dam_g1 + int(p.get("dam_g2_wins", 0) or 0) + int(p.get("dam_g3_wins", 0) or 0)

            speed = GeneticsEngine.calculate_offspring_speed(
                sire_speed=float(p["sire_speed"]),
                dam_speed=float(p["dam_speed"]),
                sire_generation=sire_gen,
                dam_vitality=float(p["dam_vitality"]),
                dam_g1_wins=dam_g1,
                dam_graded_wins=dam_g_all,
                is_nicks=bool(p.get("is_nicks")),
                nicks_speed_bonus=float(p.get("nicks_speed_bonus", 0.0)),
                inbreeding_speed_bonus=float(p.get("inbreeding_speed_bonus", 0.0)),
            )

            stamina = GeneticsEngine.calculate_polygenic_stat(p["sire_stamina"], p["dam_stamina"])
            accel = GeneticsEngine.calculate_polygenic_stat(p["sire_accel"], p["dam_accel"])
            temp = GeneticsEngine.calculate_polygenic_stat(p["sire_temp"], p["dam_temp"])
            dura = GeneticsEngine.calculate_polygenic_stat(p["sire_dura"], p["dam_dura"])
            vitality = GeneticsEngine.calculate_maternal_vitality(p["sire_vitality"], p["dam_vitality"])

            sire_tree_5 = self.pedigree_builder.get_ancestors_tree(p["sire_id"], depth=5, conn=conn)
            dam_tree_5 = self.pedigree_builder.get_ancestors_tree(p["dam_id"], depth=5, conn=conn)
            ped_apt = GeneticsEngine.calculate_pedigree_aptitude(
                sire_mstn=GenotypeMSTN(p["sire_mstn"]),
                dam_mstn=GenotypeMSTN(p["dam_mstn"]),
                sire_surface="turf",
                dam_surface="turf",
                sire_ancestors=sire_tree_5,
                dam_ancestors=dam_tree_5,
            )
            if ped_apt.get("stamina_max_clamp") is not None:
                stamina = min(stamina, ped_apt["stamina_max_clamp"])

            # 加速・気性・耐久へのインブリード・ニックス補正
            accel += float(p.get("inbreeding_accel_bonus", 0.0))
            temp -= float(p.get("inbreeding_temp_penalty", 0.0))
            dura -= float(p.get("inbreeding_dura_penalty", 0.0))

            if p.get("is_nicks"):
                accel += float(p.get("nicks_accel_bonus", 0.0))
                vitality += float(p.get("nicks_vitality_bonus", 0.0))

            # 海外種牡馬産駒の「異系活力（アウトブリード）ボーナス」
            if bool(p.get("sire_is_foreign")):
                speed += round(random.uniform(2.0, 4.0), 1)
                accel += round(random.uniform(2.0, 3.5), 1)
                dura += round(random.uniform(2.0, 4.0), 1)
                vitality += round(random.uniform(2.0, 4.0), 1)
                temp += round(random.uniform(1.0, 3.0), 1)

            speed = round(max(10.0, min(100.0, speed)), 1)
            accel = round(max(10.0, min(95.0, accel)), 1)
            stamina = round(max(10.0, min(95.0, stamina)), 1)
            temp = round(max(10.0, min(95.0, temp)), 1)
            dura = round(max(10.0, min(95.0, dura)), 1)
            vitality = round(max(10.0, min(95.0, vitality)), 1)

            growth_type, peak_age = GeneticsEngine.inherit_growth_type(
                GrowthType(p["sire_growth"]),
                GrowthType(p["dam_growth"]),
            )
            running_style = Horse.determine_running_style(speed, stamina, accel, dura)

            sire_coat_geno = p.get("sire_coat_genotype") or "E/E A/A g/g w/w cr/cr ro/ro pt/pt"
            dam_coat_geno = p.get("dam_coat_genotype") or "E/E A/A g/g w/w cr/cr ro/ro pt/pt"
            coat_color, coat_genotype = GeneticsEngine.inherit_coat_genotype(sire_coat_geno, dam_coat_geno)

            cursor = conn.execute(
                """
                INSERT INTO horses (
                    name, sex, birth_year, age, breeder_id, owner_id,
                    sire_id, dam_id,
                    is_active, is_sire, is_dam, mstn_type,
                    speed, stamina, acceleration, temperament, durability, maternal_vitality,
                    growth_type, peak_age, current_ability_rate, running_style,
                    coat_color, coat_genotype,
                    career_starts, career_wins, g1_wins, g2_wins, g3_wins, major_wins, prize_money, condition_prize_money, generation
                ) VALUES (
                    ?, ?, ?, 0, ?, ?,
                    ?, ?,
                    0, 0, 0, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, 0.2, ?,
                    ?, ?,
                    0, 0, 0, 0, 0, '', 0, 0, ?
                )
                """,
                (
                    foal_name, sex_str, current_year, p["dam_breeder_id"], owner_id,
                    p["sire_id"], p["dam_id"],
                    mstn.value,
                    speed, stamina, accel, temp, dura, vitality,
                    growth_type.value, peak_age, running_style.value,
                    coat_color, coat_genotype,
                    1 if p.get("sire_parent_id") is None else (sire_gen + 1),
                ),
            )
            newborn_ids.append(cursor.lastrowid)

        print(f"[3月出産] 全{len(newborn_ids)}頭（牡: {colt_count}頭、牝: {filly_count}頭）の当歳馬（0歳）が誕生し、スタッドブックへ登録されました！")
        print("=================================================================================\n")
        return newborn_ids

    def perform_annual_breeding(self, current_year: int, conn: Optional[Any] = None) -> List[int]:
        """
        後方互換用: 1年分の交配・受胎・当歳馬誕生を一括シミュレート
        """
        self.perform_spring_mating(current_year - 1, conn=conn)
        return self.perform_spring_foaling(current_year, conn=conn)

