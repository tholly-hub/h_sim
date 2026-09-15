"""
生産牧場（Breeder）モデル
初期50場、動的分化ロジックに対応したプロパティと成績管理
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Breeder:
    """生産牧場データモデル"""

    name: str
    region: str = "北海道"               # 所在地（北海道、東北、関東、中部、北陸、近畿、中国、四国、九州）
    reputation: float = 50.0            # 評判 (0.0〜100.0)
    funds: int = 100_000_000            # 資金 (円)
    horse_capacity: int = 15            # 総繋養枠数 (初期15頭、最大100頭まで拡張可能)
    broodmare_capacity: int = 15        # 互換性用
    current_year_starts: int = 0          # 年間出走数
    current_year_wins: int = 0          # 年間勝利数
    current_year_g1: int = 0
    current_year_g2: int = 0
    current_year_g3: int = 0
    current_year_earnings: int = 0      # 年間獲得賞金
    career_starts: int = 0              # 通算出走数
    career_wins: int = 0                # 通算勝利数
    g1_wins: int = 0                    # 通算G1勝利数
    g2_wins: int = 0
    g3_wins: int = 0
    career_earnings: int = 0            # 通算生産馬獲得賞金 (円)
    created_year: int = 1               # 設立年
    breeder_id: Optional[int] = None

    @classmethod
    def from_row(cls, row) -> Breeder:
        """SQLite Row オブジェクトからインスタンスを生成"""
        keys = row.keys() if hasattr(row, "keys") else []
        capacity = row["horse_capacity"] if "horse_capacity" in keys else row.get("broodmare_capacity", 15)
        return cls(
            breeder_id=row["breeder_id"],
            name=row["name"],
            region=row["region"] if "region" in keys else "北海道",
            reputation=row["reputation"],
            funds=row["funds"],
            horse_capacity=capacity,
            broodmare_capacity=capacity,
            current_year_starts=row["current_year_starts"] if "current_year_starts" in keys else 0,
            current_year_wins=row["current_year_wins"],
            current_year_g1=row["current_year_g1"] if "current_year_g1" in keys else 0,
            current_year_g2=row["current_year_g2"] if "current_year_g2" in keys else 0,
            current_year_g3=row["current_year_g3"] if "current_year_g3" in keys else 0,
            current_year_earnings=row["current_year_earnings"] if "current_year_earnings" in keys else 0,
            career_starts=row["career_starts"] if "career_starts" in keys else 0,
            career_wins=row["career_wins"],
            g1_wins=row["g1_wins"],
            g2_wins=row["g2_wins"] if "g2_wins" in keys else 0,
            g3_wins=row["g3_wins"] if "g3_wins" in keys else 0,
            career_earnings=row["career_earnings"],
            created_year=row["created_year"],
        )

