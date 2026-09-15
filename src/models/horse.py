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
