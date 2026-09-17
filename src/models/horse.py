"""
競走馬（Horse）モデル
3層遺伝モデル（ミオスタチン・ポリジーン・母系遺伝）、成長・加齢、競走成績
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class GenotypeMSTN(str, Enum):
    """ミオスタチン遺伝子型"""
    CC = "C/C"  # 短距離・スプリント型
    CT = "C/T"  # 中距離・万能型
    TT = "T/T"  # 長距離・ステイヤー型


class GrowthType(str, Enum):
    """成長型"""
    EARLY = "early"    # 早熟 (ピーク 2.5〜3歳)
    NORMAL = "normal"  # 普通 (ピーク 4〜5歳)
    LATE = "late"      # 晩成 (ピーク 5〜6歳)


class RunningStyle(str, Enum):
    """脚質 (4区分)"""
    ESCAPE = "escape"      # 逃げ
    LEADING = "leading"    # 先行
    BETWEEN = "between"    # 差し
    CLOSING = "closing"    # 追込


@dataclass
class Horse:
    """競走馬データモデル"""

    name: str
    sex: str                            # 'colt', 'filly', 'horse', 'mare', 'gelding'
    birth_year: int
    age: int
    breeder_id: int
    owner_id: int

    # 遺伝3層構造
    mstn_type: GenotypeMSTN
    speed: float                        # 最高速度 (0.0〜100.0, 平均 50.0)
    stamina: float                      # 持久力 (0.0〜100.0, 平均 50.0)
    acceleration: float                 # 瞬発力 (0.0〜100.0, 平均 50.0)
    temperament: float                  # 気性 (0.0〜100.0, 平均 50.0)
    durability: float                   # 耐久力 (0.0〜100.0, 平均 50.0)
    maternal_vitality: float            # 心肺機能・底力補正 (0.0〜100.0)

    # 成長・脚質
    growth_type: GrowthType
    peak_age: float                     # 例: 3.0, 4.5, 5.5
    current_ability_rate: float = 1.0   # 現在の能力発揮率 (成長・加齢による係数 0.0〜1.0)
    running_style: RunningStyle = RunningStyle.BETWEEN

    # 所属・血統 (デフォルト値あり)
    trainer_id: Optional[int] = None
    jockey_id: Optional[int] = None
    sire_id: Optional[int] = None
    dam_id: Optional[int] = None

    # 状態フラグ
    is_active: int = 1                  # 1: 現役, 0: 引退
    is_sire: int = 0                    # 1: 種牡馬
    is_dam: int = 0                     # 1: 繁殖牝馬
    is_dead: int = 0                    # 1: 死亡・抹消

    # 競走成績
    prize_money: int = 0                # 生涯総賞金 (円)
    condition_prize_money: int = 0      # 累積収得賞金 (円)
    career_starts: int = 0
    career_wins: int = 0
    g1_wins: int = 0
    g2_wins: int = 0
    g3_wins: int = 0
    major_wins: Optional[str] = None    # 主な勝ち鞍 (例: "東京優駿(G1), 皐月賞(G1)")

    horse_id: Optional[int] = None

    @classmethod
    def from_row(cls, row) -> Horse:
        """SQLite Row オブジェクトからインスタンスを生成"""
        keys = row.keys() if hasattr(row, "keys") else []
        return cls(
            horse_id=row["horse_id"],
            name=row["name"],
            sex=row["sex"],
            birth_year=row["birth_year"],
            age=row["age"],
            breeder_id=row["breeder_id"],
            owner_id=row["owner_id"],
            trainer_id=row["trainer_id"] if "trainer_id" in keys else None,
            jockey_id=row["jockey_id"] if "jockey_id" in keys else None,
            sire_id=row["sire_id"],
            dam_id=row["dam_id"],
            is_active=row["is_active"],
            is_sire=row["is_sire"],
            is_dam=row["is_dam"],
            is_dead=row["is_dead"],
            mstn_type=GenotypeMSTN(row["mstn_type"]),
            speed=row["speed"],
            stamina=row["stamina"],
            acceleration=row["acceleration"],
            temperament=row["temperament"],
            durability=row["durability"],
            maternal_vitality=row["maternal_vitality"],
            growth_type=GrowthType(row["growth_type"]),
            peak_age=row["peak_age"],
            current_ability_rate=row["current_ability_rate"] if "current_ability_rate" in keys else 1.0,
            running_style=RunningStyle(row["running_style"]) if "running_style" in keys else RunningStyle.BETWEEN,
            prize_money=row["prize_money"],
            condition_prize_money=row["condition_prize_money"],
            career_starts=row["career_starts"],
            career_wins=row["career_wins"],
            g1_wins=row["g1_wins"],
            g2_wins=row["g2_wins"] if "g2_wins" in keys else 0,
            g3_wins=row["g3_wins"] if "g3_wins" in keys else 0,
            major_wins=row["major_wins"] if "major_wins" in keys else None,
        )

    @property
    def surface_aptitude(self) -> str:
        """
        馬場適性 ('turf': 芝得意, 'dirt': ダート得意, 'both': 両方得意/兼用)
        耐久力、母性活力、個体ハッシュに基づいて決定論的に算出 (芝約60%, ダート約28%, 兼用約12%)
        """
        seed_key = (self.horse_id or 0) * 31 + int(self.durability * 10) + int(self.maternal_vitality * 7) + hash(self.name)
        val = abs(seed_key) % 100
        if val < 60:
            return "turf"
        elif val < 88:
            return "dirt"
        else:
            return "both"

    @property
    def apt_distance_min(self) -> int:
        """最短適性距離 (m)"""
        return self._calc_distance_range()[0]

    @property
    def apt_distance_max(self) -> int:
        """最長適性距離 (m)"""
        return self._calc_distance_range()[1]

    @property
    def apt_distance_range(self) -> int:
        """適性距離レンジ幅 (m)"""
        d_min, d_max = self._calc_distance_range()
        return d_max - d_min

    def _calc_distance_range(self) -> tuple[int, int]:
        """
        遺伝型(MSTN)、スタミナ、耐久力から距離適性レンジ(最小距離, 最大距離)を算出
        狭いレンジ(幅200m: 例1000〜1200m)から広いレンジ(幅1200m: 例1200〜2400m)まで多彩に分布
        """
        seed = abs((self.horse_id or 0) * 17 + int(self.stamina * 13) + int(self.speed * 7))
        flexibility = (seed % 100) / 100.0  # 0.0〜1.0 (柔軟性・レンジ幅指標)

        # スタミナ・耐久力による距離シフト
        stamina_shift = int((self.stamina - 50.0) * 10)  # -200m 〜 +200m

        if self.mstn_type == GenotypeMSTN.CC:
            # 短距離型: 基本 1000〜1400m
            if flexibility < 0.35:
                # 狭レンジ (幅200m): 1000〜1200m または 1200〜1400m
                base_min = 1000 if (seed % 2 == 0) else 1200
                return (base_min, base_min + 200)
            elif flexibility < 0.75:
                # 中レンジ (幅400〜600m): 1000〜1400m または 1000〜1600m
                max_d = 1400 if (seed % 2 == 0) else 1600
                return (1000, max_d)
            else:
                # 広レンジでも最大1600mまでに厳格規制（短距離馬から長距離馬が出ないよう制限）
                return (1000, 1600)

        elif self.mstn_type == GenotypeMSTN.CT:
            # 中距離・万能型: 基本 1600〜2400m
            if flexibility < 0.30:
                # 狭レンジ (幅200〜400m): 1600〜1800m, 1800〜2000m, 2000〜2200m
                centers = [1600, 1800, 2000]
                c = centers[seed % len(centers)]
                return (c, c + 200 if (seed % 2 == 0) else c + 400)
            elif flexibility < 0.70:
                # 中レンジ (幅600〜800m): 1400〜2000m, 1600〜2400m
                return (1400, 2000) if (seed % 2 == 0) else (1600, 2400)
            else:
                # 広レンジ (幅1200m): 1200〜2400m (ユーザー指定例: スプリントからクラシックまで対応)
                return (1200, 2400)

        else:  # GenotypeMSTN.TT
            # 長距離・ステイヤー型: 基本 2000〜3600m
            if flexibility < 0.35:
                # 狭レンジ (幅400m): 2400〜2800m または 3000〜3400m
                base_min = 2400 if (seed % 2 == 0) else 3000
                return (base_min, min(3600, base_min + 400))
            elif flexibility < 0.75:
                # 中レンジ (幅600〜800m): 2000〜2600m または 2400〜3200m
                return (2000, 2600) if (seed % 2 == 0) else (2400, 3200)
            else:
                # 広レンジ (幅1400〜1600m): 1800〜3200m または 2000〜3600m
                return (1800, 3200) if (seed % 2 == 0) else (2000, 3600)

    @staticmethod
    def determine_running_style(
        speed: float,
        stamina: float,
        acceleration: float,
        durability: float,
    ) -> RunningStyle:
        """
        スピード・持続性(スタミナ/耐久力)・瞬発力などのパラメータから脚質を決定
        - 逃げ (ESCAPE): スピード特化、前半先行力
        - 先行 (LEADING): スピードと持続性のバランス型
        - 差し (BETWEEN): 瞬発力・キレ味重視の中団待機
        - 追込 (CLOSING): スタミナと直線一気の爆発力
        """
        # 各脚質の重視パラメータ (合計係数1.00で正規化し、能力特性を正確に判定)
        # 逃げ: スピード重視 (前向きなトップスピードとダッシュ力)
        escape_score = speed * 0.50 + acceleration * 0.35 + durability * 0.15
        # 先行: スピードと持続性(スタミナ/耐久力)の均整バランス
        leading_score = speed * 0.35 + stamina * 0.35 + durability * 0.30
        # 差し: 瞬発力(キレ味)重視の中団待機
        between_score = acceleration * 0.50 + speed * 0.30 + stamina * 0.20
        # 追込: 終盤の爆発的瞬発力とスタミナ(持続性)
        closing_score = acceleration * 0.45 + stamina * 0.40 + durability * 0.15

        scores = [
            (escape_score, RunningStyle.ESCAPE),
            (leading_score, RunningStyle.LEADING),
            (between_score, RunningStyle.BETWEEN),
            (closing_score, RunningStyle.CLOSING),
        ]
        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[0][1]

