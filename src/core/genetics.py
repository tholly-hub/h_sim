"""
遺伝モデルモジュール (Genetics Engine)
3層遺伝モデル（ポリジーン、ミオスタチン遺伝型、母系遺伝）およびインブリード（血量・近交係数）計算
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Set, Tuple

from src.models.horse import GenotypeMSTN, GrowthType, Horse, RunningStyle


class GeneticsEngine:
    """交配・遺伝計算エンジン"""

    HERITABILITY: float = 0.40      # ポリジーン遺伝率 h^2
    POPULATION_MEAN: float = 50.0   # 集団平均 μ
    ENVIRONMENTAL_STD: float = 5.5  # 環境・変異標準偏差 σ_e

    @classmethod
    def sample_mstn_offspring(cls, sire_mstn: GenotypeMSTN, dam_mstn: GenotypeMSTN) -> GenotypeMSTN:
        """
        メンデルの法則に従い、父と母からそれぞれ1アレルを受け継いで子のMSTN遺伝型を決定
        """
        def get_alleles(mstn: GenotypeMSTN) -> List[str]:
            if mstn == GenotypeMSTN.CC:
                return ["C", "C"]
            elif mstn == GenotypeMSTN.CT:
                return ["C", "T"]
            else:
                return ["T", "T"]

        sire_allele = random.choice(get_alleles(sire_mstn))
        dam_allele = random.choice(get_alleles(dam_mstn))
        alleles = sorted([sire_allele, dam_allele])

        if alleles == ["C", "C"]:
            return GenotypeMSTN.CC
        elif alleles == ["C", "T"]:
            return GenotypeMSTN.CT
        else:
            return GenotypeMSTN.TT

    @classmethod
    def calculate_polygenic_stat(cls, sire_val: float, dam_val: float) -> float:
        """
        ポリジーン遺伝の量的形質予測式:
        P_child = μ + 0.5 * h^2 * (P_sire - μ) + 0.5 * h^2 * (P_dam - μ) + ε
        """
        mu = cls.POPULATION_MEAN
        h2 = cls.HERITABILITY
        mid_parent_dev = 0.5 * h2 * (sire_val - mu) + 0.5 * h2 * (dam_val - mu)
        epsilon = random.gauss(0.0, cls.ENVIRONMENTAL_STD)
        child_val = mu + mid_parent_dev + epsilon
        return round(max(5.0, min(95.0, child_val)), 1)

    @classmethod
    def calculate_maternal_vitality(cls, sire_vitality: float, dam_vitality: float) -> float:
        """
        母系遺伝 (maternal vitality): 牝系の底力・心肺機能
        V_child = 0.70 * V_dam + 0.30 * V_sire + ε
        """
        noise = random.gauss(0.0, 3.0)
        vitality = 0.70 * dam_vitality + 0.30 * sire_vitality + noise
        return round(max(10.0, min(95.0, vitality)), 1)

    @classmethod
    def inherit_growth_type(
        cls, sire_growth: GrowthType, dam_growth: GrowthType
    ) -> Tuple[GrowthType, float]:
        """
        両親の成長型・ピーク年齢の継承
        """
        if random.random() < 0.10:
            growth = random.choice([GrowthType.EARLY, GrowthType.NORMAL, GrowthType.LATE])
        else:
            growth = random.choice([sire_growth, dam_growth])

        if growth == GrowthType.EARLY:
            peak_age = round(random.uniform(2.5, 3.5), 1)
        elif growth == GrowthType.NORMAL:
            peak_age = round(random.uniform(3.5, 5.0), 1)
        else:
            peak_age = round(random.uniform(5.0, 6.2), 1)

        return growth, peak_age

    @classmethod
    def inherit_running_style(
        cls, sire_style: RunningStyle, dam_style: RunningStyle
    ) -> RunningStyle:
        """脚質の継承（両親から優先継承、20%で変異）"""
        if random.random() < 0.20:
            return random.choice(list(RunningStyle))
        return random.choice([sire_style, dam_style])

    @classmethod
    def calculate_inbreeding(
        cls, sire_ancestors: Dict[str, Any], dam_ancestors: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        5代血統ツリーから共通祖先を検出し、血量（インブリード）と近交効果を算出
        """
        def collect_ancestors(node: Optional[Dict[str, Any]], depth: int = 1) -> List[Tuple[int, str, int]]:
            if not node or depth > 5:
                return []
            res = []
            h_id = node.get("horse_id")
            name = node.get("name", "")
            if h_id and "不明" not in name:
                res.append((h_id, name, depth))
            if node.get("sire"):
                res.extend(collect_ancestors(node["sire"], depth + 1))
            if node.get("dam"):
                res.extend(collect_ancestors(node["dam"], depth + 1))
            return res

        sire_list = collect_ancestors(sire_ancestors, 1)
        dam_list = collect_ancestors(dam_ancestors, 1)

        sire_map: Dict[int, List[int]] = {}
        names_map: Dict[int, str] = {}
        for h_id, name, d in sire_list:
            sire_map.setdefault(h_id, []).append(d)
            names_map[h_id] = name

        dam_map: Dict[int, List[int]] = {}
        for h_id, name, d in dam_list:
            dam_map.setdefault(h_id, []).append(d)
            names_map[h_id] = name

        common_ids = set(sire_map.keys()) & set(dam_map.keys())

        inbreeding_details: List[Dict[str, Any]] = []
        total_blood_pct = 0.0

        for cid in common_ids:
            s_depths = sire_map[cid]
            d_depths = dam_map[cid]
            name = names_map[cid]

            blood_fraction = 0.0
            for sd in s_depths:
                blood_fraction += (0.5) ** sd
            for dd in d_depths:
                blood_fraction += (0.5) ** dd

            blood_pct = round(blood_fraction * 100.0, 2)
            total_blood_pct += blood_pct

            depth_str = f"{"・".join(map(str, sorted(s_depths)))} × {"・".join(map(str, sorted(d_depths)))}"
            inbreeding_details.append({
                "horse_id": cid,
                "name": name,
                "cross_pattern": depth_str,
                "blood_pct": blood_pct,
            })

        speed_bonus = 0.0
        accel_bonus = 0.0
        temp_penalty = 0.0
        dura_penalty = 0.0
        evaluation_tag = "アウトブリード"

        if total_blood_pct == 0.0:
            evaluation_tag = "アウトブリード（健康・活力）"
            temp_penalty = -1.5
            dura_penalty = -1.5
        elif 15.0 <= total_blood_pct <= 20.0:
            evaluation_tag = "奇跡の血量（能力向上）"
            speed_bonus = round(random.uniform(2.0, 4.0), 1)
            accel_bonus = round(random.uniform(2.0, 3.5), 1)
            temp_penalty = round(random.uniform(1.0, 3.0), 1)
        elif total_blood_pct > 25.0:
            evaluation_tag = "危険な近親交配（気性難・虚弱化）"
            speed_bonus = round(random.uniform(1.0, 3.0), 1)
            temp_penalty = round(random.uniform(4.0, 9.0), 1)
            dura_penalty = round(random.uniform(5.0, 10.0), 1)
        else:
            evaluation_tag = f"インブリード ({total_blood_pct:.1f}%)"
            speed_bonus = round(random.uniform(1.0, 2.5), 1)
            temp_penalty = round(random.uniform(1.0, 2.5), 1)

        return {
            "total_blood_pct": round(total_blood_pct, 2),
            "evaluation_tag": evaluation_tag,
            "details": inbreeding_details,
            "speed_bonus": speed_bonus,
            "accel_bonus": accel_bonus,
            "temp_penalty": temp_penalty,
            "dura_penalty": dura_penalty,
        }
