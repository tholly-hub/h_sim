"""
オッズ見直し・レース体系改定・サイアーリーディング世代別・順位推移グラフ・走破タイムグラフ改善の検証テスト
"""

import sys
import unittest
from PyQt6.QtWidgets import QApplication

from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.models.horse import GenotypeMSTN, GrowthType, Horse, RunningStyle
from src.models.race import AgeRestriction, Race, RaceGrade, RaceSurface, SexRestriction
from src.race.annual_program import generate_full_program
from src.race.calendar import CalendarController
from src.race.engine import RaceEngine
from src.race.entry import RaceEntryManager
from src.race.rankings import RankingManager

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class TestRankingsAndAnalyticsUpdates(unittest.TestCase):
    """追加改修項目の網羅的検証テスト"""

    def setUp(self):
        self.db = Database(":memory:")
        init = DatabaseInitializer(self.db)
        init.initialize_all(force_recreate=True, with_careers=True)
        self.rank_mgr = RankingManager(self.db)
        self.entry_mgr = RaceEntryManager(self.db)
        self.cal_ctrl = CalendarController(self.db)

    def test_graded_winner_is_open_and_cannot_enter_conditions(self):
        """重賞勝ち馬は通算勝利数に関わらずオープン馬となり、条件戦には出走できないこと"""
        h = Horse(
            horse_id=999,
            name="テスト重賞馬",
            sex="colt",
            birth_year=1,
            age=3,
            breeder_id=1,
            owner_id=1,
            speed=70.0,
            stamina=70.0,
            acceleration=70.0,
            temperament=70.0,
            durability=70.0,
            maternal_vitality=50.0,
            growth_type=GrowthType.NORMAL,
            peak_age=4.0,
            mstn_type=GenotypeMSTN.CT,
            running_style=RunningStyle.LEADING,
            career_starts=2,
            career_wins=1,
            g1_wins=1,  # 1勝馬だがG1勝ち
            is_active=1,
        )

        r_g1 = Race(
            name="日本ダービー", track_id="TOKYO", month=5, week=21, grade=RaceGrade.G1,
            surface=RaceSurface.TURF, distance=2400, age_restriction=AgeRestriction.THREE_YO,
            sex_restriction=SexRestriction.MIXED, full_gate=8, year=1
        )
        r_cond1 = Race(
            name="1勝クラス", track_id="TOKYO", month=5, week=21, grade=RaceGrade.COND_1W,
            surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.THREE_YO,
            sex_restriction=SexRestriction.MIXED, full_gate=8, year=1
        )

        self.assertTrue(self.entry_mgr.can_enter_race(h, r_g1))
        self.assertFalse(self.entry_mgr.can_enter_race(h, r_cond1))

    def test_three_yo_open_race_entry_conditions(self):
        """3歳馬は5月4週までは1勝でOP/重賞エントリー可能、6月1週以降は2勝必要であること"""
        h_1w = Horse(
            horse_id=1001,
            name="テスト1勝馬",
            sex="colt",
            birth_year=1,
            age=3,
            breeder_id=1,
            owner_id=1,
            speed=60.0,
            stamina=60.0,
            acceleration=60.0,
            temperament=60.0,
            durability=60.0,
            maternal_vitality=50.0,
            growth_type=GrowthType.NORMAL,
            peak_age=4.0,
            mstn_type=GenotypeMSTN.CT,
            running_style=RunningStyle.LEADING,
            career_starts=3,
            career_wins=1,
            is_active=1,
        )

        r_spring_g3 = Race(
            name="毎日杯", track_id="HANSHIN", month=3, week=12, grade=RaceGrade.G3,
            surface=RaceSurface.TURF, distance=1800, age_restriction=AgeRestriction.THREE_YO,
            sex_restriction=SexRestriction.MIXED, full_gate=8, year=1
        )
        r_summer_g3 = Race(
            name="ラジオNIKKEI賞", track_id="FUKUSHIMA", month=7, week=25, grade=RaceGrade.G3,
            surface=RaceSurface.TURF, distance=1800, age_restriction=AgeRestriction.THREE_YO,
            sex_restriction=SexRestriction.MIXED, full_gate=8, year=1
        )

        # 12週（春）は1勝で出走可能
        self.assertTrue(self.entry_mgr.can_enter_race(h_1w, r_spring_g3))
        # 25週（夏以降）は1勝では出走不可
        self.assertFalse(self.entry_mgr.can_enter_race(h_1w, r_summer_g3))

        # 2勝馬になれば夏以降も出走可能
        h_1w.career_wins = 2
        self.assertTrue(self.entry_mgr.can_enter_race(h_1w, r_summer_g3))

    def test_older_races_excluded_in_early_years(self):
        """1〜2年目は古馬限定/古馬混合重賞・Lが除外され、3年目以降に開催されること"""
        prog_y1 = generate_full_program(year=1)
        prog_y3 = generate_full_program(year=3)

        y1_older_graded = [
            r.name for r in prog_y1
            if r.grade in (RaceGrade.G1, RaceGrade.G2, RaceGrade.G3, RaceGrade.L)
            and r.age_restriction in (AgeRestriction.FOUR_YO_UP, AgeRestriction.THREE_YO_UP)
        ]
        self.assertEqual(len(y1_older_graded), 0, "1年目に古馬重賞・Lが含まれていてはなりません")

        y3_older_graded = [
            r.name for r in prog_y3
            if r.grade in (RaceGrade.G1, RaceGrade.G2, RaceGrade.G3, RaceGrade.L)
            and r.age_restriction in (AgeRestriction.FOUR_YO_UP, AgeRestriction.THREE_YO_UP)
        ]
        self.assertGreater(len(y3_older_graded), 20, "3年目以降は古馬重賞・Lが開催される必要があります")

    def test_sire_rankings_age_filter_and_history(self):
        """サイアーリーディングの年齢フィルター（総合・2歳・3歳）と順位推移履歴が取得できること"""
        sires_all = self.rank_mgr.get_sire_rankings(is_career=False, limit=10, age_filter=None)
        sires_2yo = self.rank_mgr.get_sire_rankings(is_career=False, limit=10, age_filter=2)
        sires_3yo = self.rank_mgr.get_sire_rankings(is_career=False, limit=10, age_filter=3)

        self.assertIsInstance(sires_all, list)
        self.assertIsInstance(sires_2yo, list)
        self.assertIsInstance(sires_3yo, list)

        if sires_all:
            s_id = sires_all[0]["sire_id"]
            history = self.rank_mgr.get_ranking_history("sire", s_id)
            self.assertIsInstance(history, list)
            if history:
                self.assertIn("rank", history[0])
                self.assertIn("wins", history[0])
                self.assertIn("earnings", history[0])
