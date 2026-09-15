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
    career_years: int = 1               # 騎手歴 (1〜42年)
    is_active: int = 1                  # 1: 現役, 0: 引退

    # 成長型・所属
    growth_type: str = "standard"       # 'early', 'standard', 'late', 'persistent'
    is_free: int = 0                    # 0: 厩舎所属, 1: フリー騎手
    trainer_id: Optional[int] = None    # 所属厩舎ID (フリーの場合はNULL)
    experience: float = 0.0             # 経験値 (0.0〜100.0)
    stamina: float = 50.0               # 体力パラメータ (40歳前後ピークで低下)

    # 能力値 (30.0〜99.0, 平均 50.0)
    skill: float = 50.0                 # 操縦技術・位置取り (経験・年数で向上)
    drive: float = 50.0                 # 直線推進力・追い (体力・年齢影響)
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
    def peak_age(self) -> int:
        """成長型に応じたピーク年齢 (36〜44歳)"""
        peaks = {
            "early": 36,
            "standard": 40,
            "late": 43,
            "persistent": 44,
        }
        return peaks.get(self.growth_type, 40)

    @property
    def total_ability(self) -> float:
        """総合能力評価値 (平均値)"""
        return round((self.skill + self.drive + self.start_dash + self.temperament_handling) / 4.0, 1)

    def can_become_free(self, strict: bool = True) -> bool:
        """
        フリー騎手への転向資格を判定
        strict=True (厳格条件):
          - 通算150勝以上 かつ G1 1勝以上、または
          - 重賞5勝以上（内G2以上2勝以上）、または
          - 通算250勝以上
        strict=False (標準条件):
          - 通算100勝以上 かつ G1 1勝以上、または
          - G2 3勝以上、または
          - G3 5勝以上
        """
        if self.is_free == 1:
            return True

        if strict:
            condition_1 = (self.career_wins >= 150 and self.g1_wins >= 1)
            condition_2 = ((self.g1_wins + self.g2_wins + self.g3_wins) >= 5 and (self.g1_wins + self.g2_wins) >= 2)
            condition_3 = (self.career_wins >= 250)
            return condition_1 or condition_2 or condition_3
        else:
            condition_1 = (self.career_wins >= 100 and self.g1_wins >= 1)
            condition_2 = (self.g2_wins >= 3)
            condition_3 = (self.g3_wins >= 5)
            return condition_1 or condition_2 or condition_3

    def advance_age_and_abilities(self, wins_this_year: int = 0, g1_this_year: int = 0, rides_this_year: int = 0) -> None:
        """
        年次加齢および成長・体力推移の計算
        - 経験値(experience)と技術(skill, temperament_handling)は騎乗数・勝利数・年数で着実に向上
        - ピーク年齢(40歳前後)以降は体力(stamina)と推進力(drive)が徐々に減退
        """
        self.age += 1
        self.career_years += 1

        # 経験値の加算
        exp_gain = 0.5 + (rides_this_year * 0.01) + (wins_this_year * 0.05) + (g1_this_year * 0.5)
        self.experience = min(100.0, self.experience + exp_gain)

        peak = self.peak_age
        if self.age <= peak:
            # ピーク前: 若手〜中堅の成長期
            growth_rate = max(0.2, (peak - self.age) / 20.0)
            self.skill = min(99.0, self.skill + 0.4 + growth_rate * 0.5 + (wins_this_year * 0.03))
            self.drive = min(99.0, self.drive + 0.3 + growth_rate * 0.4)
            self.start_dash = min(99.0, self.start_dash + 0.2 + growth_rate * 0.3)
            self.temperament_handling = min(99.0, self.temperament_handling + 0.3 + growth_rate * 0.4)
            self.stamina = min(95.0, self.stamina + 0.2)
        else:
            # ピーク後: ベテラン期 (40歳以降)
            # 技術・位置取り・折り合いは経験値により向上または維持
            self.skill = min(99.0, self.skill + 0.2 + (self.experience * 0.005))
            self.temperament_handling = min(99.0, self.temperament_handling + 0.25)
            self.start_dash = max(35.0, self.start_dash - 0.15)

            # 体力と推進力(追い)は年々低下
            decay_factor = (self.age - peak) * 0.12
            self.stamina = max(30.0, self.stamina - (0.6 + decay_factor))
            self.drive = max(35.0, self.drive - (0.5 + decay_factor))

        self.skill = round(self.skill, 1)
        self.drive = round(self.drive, 1)
        self.start_dash = round(self.start_dash, 1)
        self.temperament_handling = round(self.temperament_handling, 1)
        self.stamina = round(self.stamina, 1)
        self.experience = round(self.experience, 1)

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
            growth_type=row["growth_type"] if "growth_type" in keys else "standard",
            is_free=row["is_free"] if "is_free" in keys else 0,
            trainer_id=row["trainer_id"] if "trainer_id" in keys else None,
            experience=row["experience"] if "experience" in keys else 0.0,
            stamina=row["stamina"] if "stamina" in keys else 50.0,
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

