"""
馬主（Owner）モデル
初期100人、冠名（Prefix）、購買力・所有頭数の動的分化に対応
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Owner:
    """馬主データモデル"""

    name: str
    prefix: str                         # 冠名 (例: 「サトノ」「トウカイ」「シンボリ」など)
    funds: int = 100_000_000            # 購買力・資金 (円)
    horse_capacity: int = 20            # 最大所有頭数枠
    current_year_wins: int = 0          # 年間勝利数
    career_wins: int = 0                # 通算勝利数
    career_earnings: int = 0            # 通算所有馬獲得賞金 (円)
    g1_wins: int = 0                    # 通算G1勝利数
    created_year: int = 1
    owner_id: Optional[int] = None

    @classmethod
    def from_row(cls, row) -> Owner:
        """SQLite Row オブジェクトからインスタンスを生成"""
        return cls(
            owner_id=row["owner_id"],
            name=row["name"],
            prefix=row["prefix"],
            funds=row["funds"],
            horse_capacity=row["horse_capacity"],
            current_year_wins=row["current_year_wins"],
            career_wins=row["career_wins"],
            career_earnings=row["career_earnings"],
            g1_wins=row["g1_wins"],
            created_year=row["created_year"],
        )
