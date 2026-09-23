"""
年間レース番組表 (Race Program / Calendar)
- 年間48週 (12ヶ月 × 4週) の全レース体系 (約1,070レース)
- JRA 8場 ＋ 地方 4場（大井・川崎・船橋・盛岡）の12場完全対応
- 実在レース名に全面準拠（G1, G2, G3, リステッド, 冠名付き3勝クラス）
- 3歳ダート三冠（羽田盃・東京ダービー・ジャパンダートクラシック）＋古馬ダート王道
- 2歳王者決定戦（阪神JF・朝日杯FS・ホープフルS・全日本2歳優駿）
- 現役馬頭数に適正な週22〜24レース配分（8頭立て限定・頭数割れ防止）
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from src.db.database import Database
from src.models.race import AgeRestriction, Race, RaceGrade, RaceSurface, SexRestriction
from src.race.annual_program import GRADE_PRIZE_MAP, generate_full_program


class RaceProgramBuilder:
    """実在レース名・12競馬場・8頭限定適正バランス番組表生成クラス"""

    def __init__(self, db: Database):
        self.db = db

    def generate_annual_program(self, year: int = 1) -> List[Race]:
        """
        年間レース一覧を生成
        全年齢・全グレードのフル番組表（年間48週）を生成
        """
        all_races = generate_full_program(year=year)
        return all_races

    def register_annual_program(self, year: int = 1) -> int:
        """年間番組表をDBへ登録"""
        races = self.generate_annual_program(year=year)
        with self.db.session() as conn:
            conn.execute("DELETE FROM results WHERE race_id IN (SELECT race_id FROM races WHERE year = ?)", (year,))
            conn.execute("DELETE FROM races WHERE year = ?", (year,))
            for r in races:
                conn.execute(
                    """
                    INSERT INTO races (
                        year, month, week, track_id, name, grade, surface, distance,
                        age_restriction, sex_restriction, condition, full_gate,
                        is_trial, target_g1_name, base_prize, condition_prize
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        r.year, r.month, r.week, r.track_id, r.name, r.grade.value,
                        r.surface.value, r.distance, r.age_restriction.value,
                        r.sex_restriction.value, r.condition, r.full_gate,
                        r.is_trial, r.target_g1_name, r.base_prize, r.condition_prize,
                    ),
                )
        return len(races)
