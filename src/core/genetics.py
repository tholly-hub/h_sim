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

    HERITABILITY: float = 0.65      # 相加的遺伝率
    POPULATION_MEAN: float = 50.0   # 初期集団平均 μ
    ENVIRONMENTAL_STD: float = 4.0  # 環境・変異標準偏差 σ_e

    # 主要系統大分類 (Major Sire Line Systems)
    MAJOR_SYSTEMS: List[str] = [
        "サンデーサイレンス系",  # SS系 (ヘイロー系含む)
        "キングマンボ系",        # MP系 (ミスタープロスペクター系含む)
        "ノーザンダンサー系",    # ND系 (サドラーズウェルズ、ダンチヒ等)
        "ロベルト系",            # ROB系 (ヘイルトゥリーズン系)
        "ナスルーラ系",          # NAS系 (グレイソヴリン、トニービン等)
        "マイナー系",            # その他系統 (トウルビヨン、ヒペリオン等)
    ]

    # ニックス（好相性）ペアの定義 (双方向対応)
    NICKS_PAIRS: Set[Tuple[str, str]] = {
        ("サンデーサイレンス系", "キングマンボ系"),
        ("キングマンボ系", "サンデーサイレンス系"),
        ("サンデーサイレンス系", "ノーザンダンサー系"),
        ("ノーザンダンサー系", "サンデーサイレンス系"),
        ("サンデーサイレンス系", "ロベルト系"),
        ("ロベルト系", "サンデーサイレンス系"),
        ("キングマンボ系", "ノーザンダンサー系"),
        ("ノーザンダンサー系", "キングマンボ系"),
        ("キングマンボ系", "ロベルト系"),
        ("ロベルト系", "キングマンボ系"),
        ("ナスルーラ系", "サンデーサイレンス系"),
        ("サンデーサイレンス系", "ナスルーラ系"),
    }

    @classmethod
    def get_major_system(cls, line_name: Optional[str]) -> str:
        """
        サイアーライン名から主要6大系統グループを判定（架空系統名も決定論的に分類）
        """
        if not line_name:
            return "マイナー系"

        ln = line_name.lower()
        if any(k in ln for k in ["サンデー", "sunday", "ヘイロー", "halo", "ディープ", "ハーツ"]):
            return "サンデーサイレンス系"
        if any(k in ln for k in ["キングマンボ", "kingmambo", "ミスプロ", "prospector", "ロードカナロア"]):
            return "キングマンボ系"
        if any(k in ln for k in ["ノーザン", "northern", "ダンサー", "サドラー", "danzig", "クロフネ"]):
            return "ノーザンダンサー系"
        if any(k in ln for k in ["ロベルト", "roberto", "ブライアン", "グラス", "エピファネイア"]):
            return "ロベルト系"
        if any(k in ln for k in ["ナスルーラ", "nasrullah", "グレイ", "grey", "トニービン"]):
            return "ナスルーラ系"

        # 既存架空サイアーライン等の決定論的分類（ハッシュ剰余）
        idx = hash(line_name) % len(cls.MAJOR_SYSTEMS)
        return cls.MAJOR_SYSTEMS[idx]

    @classmethod
    def check_nicks(cls, sire_line: Optional[str], dam_line: Optional[str]) -> Dict[str, Any]:
        """
        種牡馬の父系と母系（母父または母の系統）のニックス（系統相性）を判定
        返り値:
        - is_nicks: bool (ニックス成立フラグ)
        - sire_system: 種牡馬の大系統
        - dam_system: 繁殖牝馬の大系統
        - label: ニックス表示名
        - speed_bonus: スピード補正
        - accel_bonus: 加速・瞬発力補正
        - vitality_bonus: 底力・気性補正
        """
        s_sys = cls.get_major_system(sire_line)
        d_sys = cls.get_major_system(dam_line)

        is_nicks = (s_sys, d_sys) in cls.NICKS_PAIRS

        if is_nicks:
            speed_bonus = round(random.uniform(1.2, 2.5), 1)
            accel_bonus = round(random.uniform(1.0, 2.0), 1)
            vitality_bonus = round(random.uniform(1.0, 2.0), 1)
            label = f"黄金ニックス成立（{s_sys} × {d_sys}）"
        else:
            speed_bonus = 0.0
            accel_bonus = 0.0
            vitality_bonus = 0.0
            label = "通常配合"

        return {
            "is_nicks": is_nicks,
            "sire_system": s_sys,
            "dam_system": d_sys,
            "label": label,
            "speed_bonus": speed_bonus,
            "accel_bonus": accel_bonus,
            "vitality_bonus": vitality_bonus,
        }

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
        育種選抜相加的遺伝モデル:
        両親の相加平均（Mid-Parent Value）を期待値として遺伝し、
        優秀な親同士の交配により世代を超えて能力が向上・進化する。
        P_child = (P_sire + P_dam) / 2.0 + 育種ドリフト + ε
        """
        mid_parent = (sire_val + dam_val) / 2.0
        # 優秀な形質の集積・品種改良効果（0.25pt向上傾向）および遺伝的変異
        epsilon = random.gauss(0.25, cls.ENVIRONMENTAL_STD)
        child_val = mid_parent + epsilon
        return round(max(10.0, min(99.0, child_val)), 1)

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

    @classmethod
    def calculate_pedigree_aptitude(
        cls,
        sire_mstn: GenotypeMSTN,
        dam_mstn: GenotypeMSTN,
        sire_ancestors: Optional[Dict[str, Any]] = None,
        dam_ancestors: Optional[Dict[str, Any]] = None,
        sire_surface: str = "turf",
        dam_surface: str = "turf",
    ) -> Dict[str, Any]:
        """
        種牡馬・繁殖牝馬および5代血統表の各馬の特性に基づいて距離適性・馬場適性を厳格に規制
        - 短距離特性馬(C/C等)から極端な長距離馬が出ないようスタミナ上限・距離上限をクランプ
        - 祖先血統の芝・ダートシェアから子の馬場適性(芝/ダート/兼用)を決定
        """
        # 1. 5代祖先木から血統情報を収集（世代ごとの寄与度: 2^-depth）
        def collect_nodes(node: Optional[Dict[str, Any]], depth: int = 1) -> List[Tuple[Dict[str, Any], float]]:
            if not node or depth > 5:
                return []
            res = []
            weight = (0.5) ** depth
            res.append((node, weight))
            if node.get("sire"):
                res.extend(collect_nodes(node["sire"], depth + 1))
            if node.get("dam"):
                res.extend(collect_nodes(node["dam"], depth + 1))
            return res

        sire_nodes = collect_nodes(sire_ancestors, 1) if sire_ancestors else []
        dam_nodes = collect_nodes(dam_ancestors, 1) if dam_ancestors else []
        all_nodes = sire_nodes + dam_nodes

        # 短距離血統シェア・ダート血統シェアの集計
        dirt_weight = 0.0
        turf_weight = 0.0
        sprint_weight = 0.0
        stayer_weight = 0.0
        total_w = 0.0

        for node, w in all_nodes:
            total_w += w
            n_mstn = node.get("mstn_type", "C/T")
            if n_mstn == "C/C":
                sprint_weight += w
            elif n_mstn == "T/T":
                stayer_weight += w
            else:
                sprint_weight += w * 0.4
                stayer_weight += w * 0.4

        # 親自身の重みも合算 (父0.5, 母0.5)
        if sire_mstn == GenotypeMSTN.CC:
            sprint_weight += 0.5
        elif sire_mstn == GenotypeMSTN.TT:
            stayer_weight += 0.5
        else:
            sprint_weight += 0.2
            stayer_weight += 0.2

        if dam_mstn == GenotypeMSTN.CC:
            sprint_weight += 0.5
        elif dam_mstn == GenotypeMSTN.TT:
            stayer_weight += 0.5
        else:
            sprint_weight += 0.2
            stayer_weight += 0.2

        total_w += 1.0

        # 短距離血統比率 (0.0〜1.0)
        sprint_ratio = sprint_weight / max(0.1, total_w)

        # 2. 馬場適性の決定（両親の馬場適性 ＋ 血統親和性）
        # 両親の馬場適性から確率バイアスを計算
        prob_turf = 0.60
        prob_dirt = 0.28
        prob_both = 0.12

        if sire_surface == "dirt" and dam_surface == "dirt":
            # 両親ダート特化: ダート適性が圧倒的
            prob_dirt = 0.78
            prob_both = 0.18
            prob_turf = 0.04
        elif sire_surface == "turf" and dam_surface == "turf":
            # 両親芝特化: 芝適性が圧倒的
            prob_turf = 0.78
            prob_both = 0.18
            prob_dirt = 0.04
        elif (sire_surface == "both") or (dam_surface == "both"):
            # 兼用馬の血統: 兼用の確率が倍増
            prob_both = 0.35
            prob_turf = 0.40
            prob_dirt = 0.25
        elif (sire_surface == "turf" and dam_surface == "dirt") or (sire_surface == "dirt" and dam_surface == "turf"):
            # 芝×ダート交配: 兼用の確率が最大化
            prob_both = 0.45
            prob_turf = 0.30
            prob_dirt = 0.25

        r_surf = random.random()
        if r_surf < prob_turf:
            chosen_surface = "turf"
        elif r_surf < prob_turf + prob_dirt:
            chosen_surface = "dirt"
        else:
            chosen_surface = "both"

        # 3. 距離適性上限クランプ判定
        # 両親が短距離適性（C/C同士）、または短距離血統シェアが65%以上の場合は
        # スタミナ上限を55.0以下に制限し、距離適性上限を最大1600mに厳格クランプ
        is_sprint_restricted = (sire_mstn == GenotypeMSTN.CC and dam_mstn == GenotypeMSTN.CC) or (sprint_ratio >= 0.65)

        return {
            "surface_aptitude": chosen_surface,
            "is_sprint_restricted": is_sprint_restricted,
            "max_distance_clamp": 1600 if is_sprint_restricted else None,
            "stamina_max_clamp": 55.0 if is_sprint_restricted else None,
            "sprint_ratio": sprint_ratio,
        }
