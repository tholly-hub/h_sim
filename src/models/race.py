"""
レース関連データモデル
- グレード、コース種別、馬場、条件、レース定義、レース結果
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RaceGrade(str, Enum):
    """競走格付け"""
    G1 = 'G1'
    G2 = 'G2'
    G3 = 'G3'
    L = 'L'             # リステッド
    OP = 'OP'           # オープン特別
    COND_3W = 'COND_3W' # 3勝クラス (1600万下)
    COND_2W = 'COND_2W' # 2勝クラス (1000万下)
    COND_1W = 'COND_1W' # 1勝クラス (500万下)
    MAIDEN = 'MAIDEN'   # 未勝利
    NEWCOMER = 'NEWCOMER' # 新馬


DEFAULT_GRADE_PRIZES: Dict[RaceGrade, tuple[int, int]] = {
    RaceGrade.G1: (150_000_000, 70_000_000),
    RaceGrade.G2: (60_000_000, 24_000_000),
    RaceGrade.G3: (40_000_000, 15_000_000),
    RaceGrade.L: (25_000_000, 10_000_000),
    RaceGrade.OP: (22_000_000, 10_000_000),
    RaceGrade.COND_3W: (18_400_000, 6_000_000),
    RaceGrade.COND_2W: (15_000_000, 5_000_000),
    RaceGrade.COND_1W: (11_000_000, 4_000_000),
    RaceGrade.NEWCOMER: (7_200_000, 4_000_000),
    RaceGrade.MAIDEN: (5_500_000, 4_000_000),
}


class RaceSurface(str, Enum):
    """コース馬場種別"""
    TURF = 'turf'
    DIRT = 'dirt'


class AgeRestriction(str, Enum):
    """年齢制限"""
    TWO_YO = '2yo'
    THREE_YO = '3yo'
    THREE_YO_UP = '3yo_up'
    FOUR_YO_UP = '4yo_up'


class SexRestriction(str, Enum):
    """性別制限"""
    MIXED = 'mixed'              # 混合 (牡・牝・セン)
    FILLY_MARE = 'filly_mare'    # 牝馬限定
    COLT_HORSE = 'colt_horse'    # 牡馬限定 (または牡・セン)


@dataclass
class Race:
    """レース番組定義データクラス"""
    name: str
    track_id: str                      # 'A', 'B', 'C', 'D'
    month: int                         # 1〜12
    week: int                          # 1〜48週
    grade: RaceGrade
    surface: RaceSurface
    distance: int                      # 1000〜3600m
    age_restriction: AgeRestriction
    sex_restriction: SexRestriction = SexRestriction.MIXED
    condition: str = 'good'            # 良馬場固定
    full_gate: int = 8                 # 8頭限定
    is_trial: int = 0                  # 1: トライアル競走
    target_g1_name: Optional[str] = None # 対象G1名
    base_prize: int = 0                # 1着本賞金 (円)
    condition_prize: int = 0           # 1着収得賞金 (円)
    year: int = 1
    race_id: Optional[int] = None

    @classmethod
    def from_row(cls, row) -> Race:
        keys = row.keys() if hasattr(row, 'keys') else []
        grade = RaceGrade(row['grade'])
        default_base, default_cond = DEFAULT_GRADE_PRIZES.get(grade, (10_000_000, 4_000_000))

        base_prize = row['base_prize'] if 'base_prize' in keys and row['base_prize'] else default_base
        condition_prize = row['condition_prize'] if 'condition_prize' in keys and row['condition_prize'] else default_cond

        return cls(
            race_id=row['race_id'] if 'race_id' in keys else None,
            year=row['year'] if 'year' in keys else 1,
            month=row['month'],
            week=row['week'],
            track_id=row['track_id'],
            name=row['name'],
            grade=grade,
            surface=RaceSurface(row['surface']),
            distance=row['distance'],
            age_restriction=AgeRestriction(row['age_restriction']),
            sex_restriction=SexRestriction(row['sex_restriction']),
            condition=row['condition'] if 'condition' in keys else 'good',
            full_gate=row['full_gate'] if 'full_gate' in keys else 18,
            is_trial=row['is_trial'] if 'is_trial' in keys else 0,
            target_g1_name=row['target_g1_name'] if 'target_g1_name' in keys else None,
            base_prize=base_prize,
            condition_prize=condition_prize,
        )


@dataclass
class RaceResultRecord:
    """レース出走結果レコード"""
    race_id: int
    horse_id: int
    finish_position: int
    finish_time: float
    time_diff: float
    margin: str
    prize_awarded: int
    condition_prize_awarded: int = 0
    jockey_id: Optional[int] = None
    trainer_id: Optional[int] = None
    running_style_used: str = 'leading'
    gate_number: int = 1
    last_3f: float = 0.0
    odds: float = 0.0
    replay_data_json: Optional[str] = None
    result_id: Optional[int] = None
