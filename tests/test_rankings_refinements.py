import os, sys, tempfile, unittest
from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.race.calendar import CalendarController
from src.race.rankings import RankingManager
from src.gui.views.rankings_view import RankingsView
from src.gui.views.sire_progeny_dialog import SireProgenyDialog


class TestRankingsRefinements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_file = tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False)
        cls.temp_path = cls.temp_file.name
        cls.temp_file.close()
        cls.db = Database(cls.temp_path)
        init = DatabaseInitializer(cls.db)
        init.initialize_all(force_recreate=True)
        cls.cal = CalendarController(cls.db)
        cls.rank_mgr = RankingManager(cls.db)

        # レースを数週実行して成績データを作成
        for w in range(21, 26):
            cls.cal.run_week(1, w)

    @classmethod
    def tearDownClass(cls):
        try:
            if os.path.exists(cls.temp_path):
                os.remove(cls.temp_path)
        except Exception:
            pass

    def test_jockey_rankings_breakdown_and_reps(self):
        rankings = self.rank_mgr.get_jockey_rankings(is_career=True, limit=10)
        self.assertTrue(len(rankings) > 0)
        for r in rankings:
            self.assertIn("win_1", r)
            self.assertIn("win_2", r)
            self.assertIn("win_3", r)
            self.assertIn("win_out", r)
            self.assertIn("g1_cnt", r)
            self.assertIn("g2_cnt", r)
            self.assertIn("g3_cnt", r)
            self.assertIn("representative_horses", r)
            self.assertTrue(len(r["representative_horses"]) <= 3)
        print("PASS: Jockey rankings breakdown [1-2-3-out], [G1-G2-G3], and representative horses verified.")

    def test_trainer_rankings_breakdown_and_reps(self):
        rankings = self.rank_mgr.get_trainer_rankings(is_career=True, limit=10)
        self.assertTrue(len(rankings) > 0)
        for r in rankings:
            self.assertIn("win_1", r)
            self.assertIn("win_2", r)
            self.assertIn("win_3", r)
            self.assertIn("win_out", r)
            self.assertIn("g1_cnt", r)
            self.assertIn("representative_horses", r)
            self.assertTrue(len(r["representative_horses"]) <= 3)
        print("PASS: Trainer rankings breakdown and representative horses verified.")

    def test_owner_and_breeder_rankings(self):
        o_ranks = self.rank_mgr.get_owner_rankings(is_career=True, limit=10)
        b_ranks = self.rank_mgr.get_breeder_rankings(is_career=True, limit=10)
        self.assertTrue(len(o_ranks) > 0)
        self.assertTrue(len(b_ranks) > 0)
        self.assertIn("representative_horses", o_ranks[0])
        self.assertIn("representative_horses", b_ranks[0])
        print("PASS: Owner and Breeder rankings breakdown verified.")

    def test_sire_rankings_and_progenies(self):
        s_ranks = self.rank_mgr.get_sire_rankings(is_career=True, limit=10)
        self.assertTrue(len(s_ranks) > 0)
        top_sire = s_ranks[0]
        sire_hid = top_sire["sire_horse_id"]
        self.assertIn("representative_horses", top_sire)

        # 産駒一覧取得テスト
        progenies = self.rank_mgr.get_sire_progenies(sire_hid)
        self.assertIsInstance(progenies, list)
        if len(progenies) >= 2:
            # 賞金降順チェック
            self.assertGreaterEqual(progenies[0]["prize_money"], progenies[1]["prize_money"])

        # SireProgenyDialog 起動テスト
        dlg = SireProgenyDialog(self.db, sire_hid, top_sire["sire_name"])
        self.assertEqual(dlg.table.columnCount(), 9)
        print("PASS: Sire rankings, active progenies sort, and SireProgenyDialog verified.")

    def test_rankings_view_ui(self):
        view = RankingsView(self.db)
        for cat in ["jockey", "trainer", "owner", "breeder", "sire"]:
            view._change_category(cat)
            self.assertGreater(view.rank_table.columnCount(), 5)
            self.assertGreaterEqual(view.rank_table.rowCount(), 1)
        print("PASS: RankingsView UI category switching and table rendering verified.")


if __name__ == '__main__':
    unittest.main()
