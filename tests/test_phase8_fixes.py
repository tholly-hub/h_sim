"""
新機能（産駒一覧、昇順ソート、種牡馬・繁殖牝馬ソート＆繋養年数表示）の検証テスト
"""

import unittest
from PyQt6.QtWidgets import QApplication
from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.gui.views.progeny_dialog import ProgenyListDialog
from src.gui.views.database_view import DatabaseView
from src.gui.views.awards_view import AwardsView
from src.race.engine import RaceEngine
from src.models.horse import Horse, RunningStyle, GenotypeMSTN, GrowthType
from src.models.race import Race, RaceGrade, RaceSurface
from src.race.track import TrackInfo

class TestPhase8Fixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = Database(":memory:")
        initializer = DatabaseInitializer(self.db)
        initializer.initialize_all(force_recreate=True)

    def tearDown(self):
        pass

    def test_progeny_dialog_sire_and_dam(self):
        with self.db.session() as conn:
            sire_id = conn.execute("SELECT horse_id FROM sires LIMIT 1").fetchone()["horse_id"]
            dam_id = conn.execute("SELECT horse_id FROM dams LIMIT 1").fetchone()["horse_id"]

        # 種牡馬産駒一覧ダイアログの表示生成（エラーが出ないこと）
        dlg_sire = ProgenyListDialog(self.db, parent_id=sire_id, is_sire=True)
        self.assertIsNotNone(dlg_sire)

        # 繁殖牝馬産駒一覧ダイアログの表示生成（エラーが出ないこと）
        dlg_dam = ProgenyListDialog(self.db, parent_id=dam_id, is_sire=False)
        self.assertIsNotNone(dlg_dam)

    def test_database_view_sires_dams_sorting(self):
        db_view = DatabaseView(db=self.db)
        # 種牡馬ソート変更テスト
        for sort_key in ["progeny_desc", "name_asc", "years_desc", "winners_desc", "rate_desc", "graded_desc"]:
            idx = db_view.combo_sire_sort.findData(sort_key)
            self.assertGreaterEqual(idx, 0)
            db_view.combo_sire_sort.setCurrentIndex(idx)
            db_view.refresh_sires_list()

        # 繁殖牝馬ソート変更テスト
        for sort_key in ["progeny_desc", "name_asc", "years_desc", "winners_desc", "rate_desc"]:
            idx = db_view.combo_dam_sort.findData(sort_key)
            self.assertGreaterEqual(idx, 0)
            db_view.combo_dam_sort.setCurrentIndex(idx)
            db_view.refresh_broodmares_list()

    def test_race_finish_time_limits(self):
        engine = RaceEngine()
        horse = Horse(
            name="テスター",
            sex="colt",
            birth_year=1,
            age=3,
            breeder_id=1,
            owner_id=1,
            mstn_type=GenotypeMSTN.CT,
            speed=100.0,
            stamina=100.0,
            acceleration=100.0,
            temperament=100.0,
            durability=100.0,
            maternal_vitality=100.0,
            growth_type=GrowthType.NORMAL,
            peak_age=4.0,
            running_style=RunningStyle.LEADING,
            current_ability_rate=1.05,
        )
        race_1600 = Race(
            race_id=1,
            year=1,
            month=5,
            week=20,
            track_id="TOKYO",
            name="日本ダービー",
            grade=RaceGrade.G1,
            surface=RaceSurface.TURF,
            distance=1600,
            age_restriction="3yo",
            sex_restriction="mixed",
        )
        from src.race.track import get_track_info
        track = get_track_info("TOKYO")

        # 1600m で 1F 10.0秒 (80.0秒) 未満にならないことを確認
        t = engine.calculate_finish_time(horse, race_1600, track)
        self.assertGreaterEqual(t, 80.0)

    def test_horse_status_name_and_class_name(self):
        def _make_horse(**kwargs):
            base = {
                "name": "馬名",
                "sex": "colt",
                "birth_year": 1,
                "age": 3,
                "breeder_id": 1,
                "owner_id": 1,
                "mstn_type": GenotypeMSTN.CT,
                "speed": 60.0,
                "stamina": 60.0,
                "acceleration": 60.0,
                "temperament": 60.0,
                "durability": 60.0,
                "maternal_vitality": 60.0,
                "growth_type": GrowthType.NORMAL,
                "peak_age": 4.0,
            }
            base.update(kwargs)
            return Horse(**base)

        # 1歳馬: 入厩前
        yearling = _make_horse(name="1歳馬", age=1, is_active=False)
        self.assertEqual(yearling.status_name, "入厩前")
        self.assertEqual(yearling.class_name, "入厩前")

        # 当歳馬 (0歳): 入厩前
        foal = _make_horse(name="当歳馬", sex="filly", age=0, is_active=False)
        self.assertEqual(foal.status_name, "入厩前")
        self.assertEqual(foal.class_name, "入厩前")

        # 2歳未出走馬: 未出走
        unraced_2yo = _make_horse(name="2歳未出走", age=2, is_active=True, career_starts=0)
        self.assertEqual(unraced_2yo.status_name, "未出走")
        self.assertEqual(unraced_2yo.class_name, "未出走")

        # 3歳現役馬 (1戦0勝): 現役 / 未勝利
        maiden_3yo = _make_horse(name="3歳未勝利", age=3, is_active=True, career_starts=1, career_wins=0)
        self.assertEqual(maiden_3yo.status_name, "現役")
        self.assertEqual(maiden_3yo.class_name, "未勝利")

        # 種牡馬
        sire = _make_horse(name="種牡馬", sex="stallion", age=8, is_active=False, is_sire=True)
        self.assertEqual(sire.status_name, "種牡馬")
        self.assertEqual(sire.class_name, "種牡馬")

        # 繁殖牝馬
        dam = _make_horse(name="繁殖牝馬", sex="mare", age=8, is_active=False, is_dam=True)
        self.assertEqual(dam.status_name, "繁殖牝馬")
        self.assertEqual(dam.class_name, "繁殖牝馬")

        # 引退馬
        retired = _make_horse(name="引退馬", sex="gelding", age=6, is_active=False, career_starts=10)
        self.assertEqual(retired.status_name, "引退")
        self.assertEqual(retired.class_name, "引退")

if __name__ == "__main__":
    unittest.main()
