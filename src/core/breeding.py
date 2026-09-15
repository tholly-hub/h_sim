"""
交配・繁殖管理モジュール (Breeding Engine)
年間種付け処理、種牡馬30頭制限遵守、受胎・当歳馬約500頭誕生、サイアーライン多様性維持
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

from src.core.genetics import GeneticsEngine
from src.db.database import Database
from src.generators.name_generator import HorseNameGenerator
from src.models.horse import GenotypeMSTN, GrowthType, RunningStyle
from src.views.pedigree_builder import PedigreeBuilder


class BreedingEngine:
    """繁殖・交配シミュレーションエンジン"""

    MAX_COVERINGS_PER_SIRE: int = 30  # 種牡馬1頭あたりの年間上限種付け頭数
    TARGET_FOAL_COUNT: int = 500      # 年間誕生目標当歳数

    def __init__(self, db: Database):
        self.db = db
        self.name_gen = HorseNameGenerator()
        self.pedigree_builder = PedigreeBuilder(db)

    def _sync_existing_names(self, conn) -> None:
        """DB内の全馬名をジェネレータに登録して重複を防止"""
        rows = conn.execute("SELECT name FROM horses").fetchall()
        for r in rows:
            self.name_gen.register_name(r["name"])

    def perform_annual_breeding(self, current_year: int) -> List[int]:
        """
        1年分の交配・受胎・当歳馬誕生を一括シミュレート
        返り値: 新規誕生した当歳馬の horse_id リスト
        """
        print(f"\n==================== 【{current_year}年度 交配・出産シミュレーション】 ====================")

        newborn_ids: List[int] = []

        with self.db.session() as conn:
            print("[交配・出産] 1/4: データベースの既存馬名を同期中（重複防止）...")
            self._sync_existing_names(conn)

            # 1. 稼働中の種牡馬を取得
            sire_rows = conn.execute(
                """
                SELECT s.horse_id, s.breeder_id, s.sire_line, s.stud_fee,
                       h.name, h.speed, h.stamina, h.acceleration, h.temperament, h.durability,
                       h.maternal_vitality, h.mstn_type, h.growth_type, h.running_style
                FROM sires s
                JOIN horses h ON s.horse_id = h.horse_id
                WHERE s.is_active = 1
                """
            ).fetchall()

            if not sire_rows:
                print("[警告] 稼働中の種牡馬が存在しません。")
                return []

            # 2. 稼働中の繁殖牝馬を取得
            dam_rows = conn.execute(
                """
                SELECT d.horse_id, d.breeder_id,
                       h.name, h.speed, h.stamina, h.acceleration, h.temperament, h.durability,
                       h.maternal_vitality, h.mstn_type, h.growth_type, h.running_style,
                       h.owner_id
                FROM dams d
                JOIN horses h ON d.horse_id = h.horse_id
                WHERE d.is_active = 1
                """
            ).fetchall()

            if not dam_rows:
                print("[警告] 稼働中の繁殖牝馬が存在しません。")
                return []

            print(f"[交配・出産] 2/4: 稼働中 種牡馬 {len(sire_rows)} 頭、繁殖牝馬 {len(dam_rows)} 頭を確認しました。")

            # 馬主一覧の取得
            owners = conn.execute("SELECT owner_id, prefix FROM owners").fetchall()
            owner_list = [(o["owner_id"], o["prefix"]) for o in owners]

            # 種牡馬の年間種付けカウンター初期化 (sire_id -> count)
            sire_covering_count: Dict[int, int] = {s["horse_id"]: 0 for s in sire_rows}

            # サイアーライン別の現役種牡馬数を集計（絶滅危惧ラインの保護用）
            line_counts: Dict[str, int] = {}
            for s in sire_rows:
                line_counts[s["sire_line"]] = line_counts.get(s["sire_line"], 0) + 1

            # 繁殖牝馬リストをシャッフル
            dams = list(dam_rows)
            random.shuffle(dams)

            print(f"[交配・出産] 3/4: 交配マッチング・受胎判定および遺伝特性（ポリジーン・MSTN・底力）計算中...")

            foal_count = 0
            colt_count = 0
            filly_count = 0

            for dam in dams:
                # 目標頭数に達したら交配終了
                if foal_count >= self.TARGET_FOAL_COUNT:
                    break

                # 30頭制限に達していない種牡馬を抽出
                available_sires = [s for s in sire_rows if sire_covering_count[s["horse_id"]] < self.MAX_COVERINGS_PER_SIRE]
                if not available_sires:
                    break

                # 種牡馬の選択アルゴリズム:
                # 1) 同一牧場繋養種牡馬を優先（地元優先）
                # 2) 希少サイアーラインを優先保護
                # 3) インブリードが危険（25%超）な配合は除外
                candidates = []
                for s in available_sires:
                    weight = 1.0
                    if s["breeder_id"] == dam["breeder_id"]:
                        weight += 1.5
                    if line_counts.get(s["sire_line"], 0) <= 2:
                        weight += 2.0
                    avg_ability = (s["speed"] + s["stamina"] + s["acceleration"]) / 3.0
                    weight += max(0.0, (avg_ability - 50.0) * 0.1)

                    candidates.append((s, weight))

                total_w = sum(w for _, w in candidates)
                r_val = random.uniform(0, total_w)
                acc = 0.0
                chosen_sire = candidates[0][0]
                for s, w in candidates:
                    acc += w
                    if r_val <= acc:
                        chosen_sire = s
                        break

                # 近交判定（深さ4）
                sire_tree = self.pedigree_builder.get_ancestors_tree(chosen_sire["horse_id"], depth=4)
                dam_tree = self.pedigree_builder.get_ancestors_tree(dam["horse_id"], depth=4)
                inbreeding_info = GeneticsEngine.calculate_inbreeding(sire_tree, dam_tree)

                # 危険な近親交配 (25%超) は再試行
                retry = 0
                while inbreeding_info["total_blood_pct"] > 25.0 and retry < 3:
                    chosen_sire = random.choice(available_sires)
                    sire_tree = self.pedigree_builder.get_ancestors_tree(chosen_sire["horse_id"], depth=4)
                    inbreeding_info = GeneticsEngine.calculate_inbreeding(sire_tree, dam_tree)
                    retry += 1

                # 種付けカウント加算
                sire_covering_count[chosen_sire["horse_id"]] += 1

                # 受胎判定 (受胎率 88%)
                if random.random() > 0.88:
                    continue  # 不受胎

                # 当歳馬の誕生
                foal_count += 1
                is_colt = (random.random() < 0.5)
                sex_str = "colt" if is_colt else "filly"
                if is_colt:
                    colt_count += 1
                else:
                    filly_count += 1

                # 馬主と冠名の決定
                if random.random() < 0.60 and dam["owner_id"]:
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

                # インブリード効果の適用
                speed = round(max(10.0, min(95.0, speed + inbreeding_info["speed_bonus"])), 1)
                accel = round(max(10.0, min(95.0, accel + inbreeding_info["accel_bonus"])), 1)
                temp = round(max(10.0, min(95.0, temp - inbreeding_info["temp_penalty"])), 1)
                dura = round(max(10.0, min(95.0, dura - inbreeding_info["dura_penalty"])), 1)

                growth_type, peak_age = GeneticsEngine.inherit_growth_type(
                    GrowthType(chosen_sire["growth_type"]),
                    GrowthType(dam["growth_type"]),
                )
                running_style = GeneticsEngine.inherit_running_style(
                    RunningStyle(chosen_sire["running_style"]),
                    RunningStyle(dam["running_style"]),
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

            print(f"[交配・出産] 4/4: 全{len(newborn_ids)}頭の当歳馬をスタッドブックへ登録完了。")

        print("=================================================================================\n")
        return newborn_ids
