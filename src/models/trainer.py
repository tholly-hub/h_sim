"""
厩舎（Trainer）モデル
美浦・栗東所属、得意分野（芝/ダート/距離/成長）、受け入れ頭数枠
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TrainerSpecialty(str, Enum):
    """厩舎の得意分野・育成特徴"""
    TURF = "turf"                      # 芝得意
    DIRT = "dirt"                      # ダート得意
    DISTANCE_LONG = "distance_long"    # 長距離得意・ステイヤー育成
    DISTANCE_SPRINT = "distance_sprint"# 短距離得意・スピード強化
    EARLY_GROWTH = "early_growth"      # 仕上がり早い・2歳早期デビュー
    LATE_GROWTH = "late_growth"        # 晩成・古馬成長重視
    DURABILITY_CARE = "durability_care"# 耐久重視・タフネス管理
    GENERAL = "general"                # 万能・オールラウンダー

    @property
    def label(self) -> str:
        labels = {
            self.TURF: "芝得意",
            self.DIRT: "ダート得意",
            self.DISTANCE_LONG: "長距離得意",
            self.DISTANCE_SPRINT: "短距離得意",
            self.EARLY_GROWTH: "仕上がり早い",
            self.LATE_GROWTH: "晩成育成",
            self.DURABILITY_CARE: "馬体ケア",
            self.GENERAL: "万能",
        }
        return labels.get(self, self.value)


@dataclass
class Trainer:
    """厩舎データモデル"""

    name: str                           # 苗字＋厩舎 (例: 武田厩舎)
    location: str                       # '美浦' または '栗東'
    specialty: TrainerSpecialty = TrainerSpecialty.GENERAL
    horse_capacity: int = 30            # 最大管理枠 (初期30頭、最大50頭)
    reputation: float = 50.0            # 評価・名声 (0.0〜100.0)
    skill_level: float = 50.0           # 調教師スキル (年数・勝利数で向上、減少しない)
    current_year_starts: int = 0
    current_year_wins: int = 0
    current_year_g1: int = 0
    current_year_g2: int = 0
    current_year_g3: int = 0
    current_year_earnings: int = 0
    career_starts: int = 0
    career_wins: int = 0
    career_earnings: int = 0
    g1_wins: int = 0
    g2_wins: int = 0
    g3_wins: int = 0
    age: int = 50                       # 年齢 (50〜80歳)
    trainer_years: int = 1              # 開業年数 (1〜30年)
    former_jockey_id: Optional[int] = None # 引退騎手が引き継いだ場合の元の騎手ID
    created_year: int = 1
    trainer_id: Optional[int] = None

    def calculate_skill_growth(self, wins_this_year: int = 0, g1_this_year: int = 0, g2_this_year: int = 0, g3_this_year: int = 0) -> float:
        """
        年次スキル成長値を計算（開業年数ベース + 当年成績ボーナス）
        スキルは常に向上し、減少しない
        """
        # 年数による基礎経験値向上 (年あたり +0.3〜0.5)
        base_growth = 0.35
        # 勝利数ボーナス (1勝ごとに +0.05)
        win_bonus = wins_this_year * 0.05
        # 有力重賞ボーナス
        graded_bonus = (g1_this_year * 1.0) + (g2_this_year * 0.5) + (g3_this_year * 0.25)
        
        total_delta = base_growth + win_bonus + graded_bonus
        # 上限は 99.0
        new_skill = min(99.0, self.skill_level + total_delta)
        return round(new_skill, 2)

    @classmethod
    def from_row(cls, row) -> Trainer:
        """SQLite Row オブジェクトからインスタンス生成"""
        keys = row.keys() if hasattr(row, "keys") else []
        return cls(
            trainer_id=row["trainer_id"],
            name=row["name"],
            location=row["location"],
            specialty=TrainerSpecialty(row["specialty"]),
            horse_capacity=row["horse_capacity"],
            reputation=row["reputation"],
            skill_level=row["skill_level"] if "skill_level" in keys else 50.0,
            current_year_starts=row["current_year_starts"] if "current_year_starts" in keys else 0,
            current_year_wins=row["current_year_wins"],
            current_year_g1=row["current_year_g1"] if "current_year_g1" in keys else 0,
            current_year_g2=row["current_year_g2"] if "current_year_g2" in keys else 0,
            current_year_g3=row["current_year_g3"] if "current_year_g3" in keys else 0,
            current_year_earnings=row["current_year_earnings"] if "current_year_earnings" in keys else 0,
            career_starts=row["career_starts"] if "career_starts" in keys else 0,
            career_wins=row["career_wins"],
            career_earnings=row["career_earnings"],
            g1_wins=row["g1_wins"],
            g2_wins=row["g2_wins"] if "g2_wins" in keys else 0,
            g3_wins=row["g3_wins"] if "g3_wins" in keys else 0,
            age=row["age"] if "age" in keys else 50,
            trainer_years=row["trainer_years"] if "trainer_years" in keys else 1,
            former_jockey_id=row["former_jockey_id"] if "former_jockey_id" in keys else None,
            created_year=row["created_year"],
        )


