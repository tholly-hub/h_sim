"""
騎手（Jockey）モデル
美浦・栗東所属、年齢、キャリア年数（最大30年現役）、能力値、成績
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Jockey:
    """騎手データモデル"""

    name: str                           # 氏名 (例: 武田 豊, 桜井 さくら)
    location: str                       # '美浦' または '栗東'
    age: int                            # 年齢 (20〜50歳)
    debut_year: int                     # デビュー年
    gender: str = "male"                # 'male' または 'female'
    career_years: int = 1               # 騎手歴 (1〜30年)
    is_active: int = 1                  # 1: 現役, 0: 引退

    # 能力値 (30.0〜90.0, 平均 50.0)
    skill: float = 50.0                 # 操縦技術・位置取り
    drive: float = 50.0                 # 直線推進力・追い
    start_dash: float = 50.0            # スタートダッシュ
    temperament_handling: float = 50.0  # 気性難カバー・折り合い

    # 成績
    current_year_starts: int = 0
    current_year_wins: int = 0
    current_year_rides: int = 0
    current_year_g1: int = 0
    current_year_g2: int = 0
    current_year_g3: int = 0
    career_starts: int = 0
    career_wins: int = 0
    career_rides: int = 0
    career_earnings: int = 0
    g1_wins: int = 0
    g2_wins: int = 0
    g3_wins: int = 0
    jockey_id: Optional[int] = None

    @property
    def total_ability(self) -> float:
        """総合能力評価値 (平均値)"""
        return round((self.skill + self.drive + self.start_dash + self.temperament_handling) / 4.0, 1)

    @classmethod
    def from_row(cls, row) -> Jockey:
        """SQLite Row オブジェクトからインスタンス生成"""
        keys = row.keys() if hasattr(row, "keys") else []
        return cls(
            jockey_id=row["jockey_id"],
            name=row["name"],
            gender=row["gender"] if "gender" in keys else "male",
            location=row["location"],
            age=row["age"],
            debut_year=row["debut_year"],
            career_years=row["career_years"],
            is_active=row["is_active"],
            skill=row["skill"],
            drive=row["drive"],
            start_dash=row["start_dash"],
            temperament_handling=row["temperament_handling"],
            current_year_starts=row["current_year_starts"] if "current_year_starts" in keys else 0,
            current_year_wins=row["current_year_wins"],
            current_year_rides=row["current_year_rides"],
            current_year_g1=row["current_year_g1"] if "current_year_g1" in keys else 0,
            current_year_g2=row["current_year_g2"] if "current_year_g2" in keys else 0,
            current_year_g3=row["current_year_g3"] if "current_year_g3" in keys else 0,
            career_starts=row["career_starts"] if "career_starts" in keys else 0,
            career_wins=row["career_wins"],
            career_rides=row["career_rides"],
            career_earnings=row["career_earnings"],
            g1_wins=row["g1_wins"],
            g2_wins=row["g2_wins"] if "g2_wins" in keys else 0,
            g3_wins=row["g3_wins"] if "g3_wins" in keys else 0,
        )

