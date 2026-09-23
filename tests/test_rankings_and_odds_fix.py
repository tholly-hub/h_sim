import os
import unittest
from PyQt6.QtWidgets import QApplication

from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.gui.views.rankings_view import RankingsView
from src.models.horse import GenotypeMSTN, GrowthType, Horse, RunningStyle
from src.models.jockey import Jockey
from src.models.race import AgeRestriction, Race, RaceGrade, RaceSurface, SexRestriction
from src.race.engine import RaceEngine
from src.race.rankings import RankingManager


class TestRankingsAndOddsFix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.test_db_path = "data/test_rankings_odds.db"
        for suffix in ["", "-shm", "-wal"]:
            p = f"{self.test_db_path}{suffix}"
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        self.db = Database(self.test_db_path)
        init = DatabaseInitializer(self.db)
        init.initialize_all(force_recreate=True, with_careers=True)

    def tearDown(self):
        for suffix in ["", "-shm", "-wal"]:
            p = f"{self.test_db_path}{suffix}"
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

    def test_odds_calculation_sanity(self):
        """2歳重賞や一般レースにおいて有力馬・各馬のオッズが適正範囲に収まり、700倍超の異常オッズが発生しないこと"""
        engine = RaceEngine()
        race = Race(
            name="サウジアラビアRC",
            track_id="TOKYO",
            month=10,
            week=37,
            grade=RaceGrade.G3,
            surface=RaceSurface.TURF,
            distance=1600,
            age_restriction=AgeRestriction.TWO_YO,
            sex_restriction=SexRestriction.MIXED,
            full_gate=8,
        )

        jockey = Jockey(
            name="ルメール",
            location="栗東",
            age=40,
            debut_year=1,
            skill=85.0,
            drive=80.0,
            start_dash=75.0,
            temperament_handling=80.0,
            jockey_id=1,
        )
        jockey_dict = {1: jockey}

        # 8頭の出走馬（実力馬から下級馬まで）
        horses = [
            Horse(
                name="有力馬A(早熟)",
                sex="colt",
                birth_year=1,
                age=2,
                breeder_id=1,
                owner_id=1,
                mstn_type=GenotypeMSTN.CT,
                speed=65.0,
                stamina=60.0,
                acceleration=65.0,
                temperament=60.0,
                durability=55.0,
                maternal_vitality=60.0,
                growth_type=GrowthType.EARLY,
                peak_age=3.0,
                current_ability_rate=0.78,
                running_style=RunningStyle.LEADING,
                horse_id=101,
            ),
            Horse(
                name="有力馬B(晩成・素質型)",
                sex="colt",
                birth_year=1,
                age=2,
                breeder_id=1,
                owner_id=1,
                mstn_type=GenotypeMSTN.CT,
                speed=68.0,
                stamina=65.0,
                acceleration=66.0,
                temperament=55.0,
                durability=55.0,
                maternal_vitality=60.0,
                growth_type=GrowthType.LATE,
                peak_age=5.5,
                current_ability_rate=0.55,
                running_style=RunningStyle.BETWEEN,
                horse_id=102,
            ),
            Horse(
                name="一般馬C",
                sex="colt",
                birth_year=1,
                age=2,
                breeder_id=1,
                owner_id=1,
                mstn_type=GenotypeMSTN.CC,
                speed=50.0,
                stamina=45.0,
                acceleration=50.0,
                temperament=50.0,
                durability=50.0,
                maternal_vitality=50.0,
                growth_type=GrowthType.NORMAL,
                peak_age=4.5,
                current_ability_rate=0.65,
                running_style=RunningStyle.BETWEEN,
                horse_id=103,
            ),
            Horse(
                name="大穴馬D",
                sex="filly",
                birth_year=1,
                age=2,
                breeder_id=1,
                owner_id=1,
                mstn_type=GenotypeMSTN.CC,
                speed=35.0,
                stamina=35.0,
                acceleration=35.0,
                temperament=40.0,
                durability=40.0,
                maternal_vitality=40.0,
                growth_type=GrowthType.LATE,
                peak_age=5.5,
                current_ability_rate=0.55,
                running_style=RunningStyle.CLOSING,
                horse_id=104,
            ),
        ]

        assignments = {h.horse_id: 1 for h in horses}
        odds_map = engine.calculate_odds(horses, race, jockey_dict, assignments)

        # 有力馬Aのオッズは 1.1〜10.0倍程度
        self.assertLess(odds_map[101], 10.0)
        # 有力馬B（晩成素質馬）も 1.5〜15.0倍程度で700倍には絶対にならない
        self.assertLess(odds_map[102], 20.0)
        # 大穴馬Dでも 300倍以内に収まる
        self.assertLess(odds_map[104], 300.0)
        # 全馬 700倍未満
        for hid, odd in odds_map.items():
            self.assertLess(odd, 700.0)

    def test_jockey_and_trainer_rankings_age(self):
        """騎手・調教師リーディングに年齢が含まれ、UIに正しく反映されること"""
        mgr = RankingManager(self.db)
        j_ranks = mgr.get_jockey_rankings(is_career=True, limit=5)
        self.assertTrue(len(j_ranks) > 0)
        self.assertIn("age", j_ranks[0])
        self.assertIsInstance(j_ranks[0]["age"], int)

        t_ranks = mgr.get_trainer_rankings(is_career=True, limit=5)
        self.assertTrue(len(t_ranks) > 0)
        self.assertIn("age", t_ranks[0])
        self.assertIsInstance(t_ranks[0]["age"], int)

        # UI検証
        view = RankingsView(self.db)
        view._change_category("jockey")
        self.assertEqual(view.rank_table.horizontalHeaderItem(2).text(), "年齢")
        self.assertIn("歳", view.rank_table.item(0, 2).text())

        view._change_category("trainer")
        self.assertEqual(view.rank_table.horizontalHeaderItem(2).text(), "年齢")
        self.assertIn("歳", view.rank_table.item(0, 2).text())

    def test_breeder_and_sire_rankings_counts(self):
        """生産牧場（種牡馬・繁殖牝馬数）およびサイアー（現役産駒数）が正しく取得・表示されること"""
        mgr = RankingManager(self.db)
        b_ranks = mgr.get_breeder_rankings(is_career=True, limit=5)
        self.assertTrue(len(b_ranks) > 0)
        self.assertIn("sire_count", b_ranks[0])
        self.assertIn("dam_count", b_ranks[0])

        s_ranks = mgr.get_sire_rankings(is_career=True, limit=5)
        self.assertTrue(len(s_ranks) > 0)
        self.assertIn("active_progeny_count", s_ranks[0])

        # UI検証
        view = RankingsView(self.db)
        view._change_category("breeder")
        self.assertEqual(view.rank_table.horizontalHeaderItem(3).text(), "種牡馬")
        self.assertEqual(view.rank_table.horizontalHeaderItem(4).text(), "繁殖牝馬")
        self.assertIn("頭", view.rank_table.item(0, 3).text())
        self.assertIn("頭", view.rank_table.item(0, 4).text())

        view._change_category("sire")
        self.assertEqual(view.rank_table.horizontalHeaderItem(4).text(), "現役産駒")
        self.assertIn("頭", view.rank_table.item(0, 4).text())


if __name__ == "__main__":
    unittest.main()
