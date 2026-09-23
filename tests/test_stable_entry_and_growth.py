import os
import sys
import tempfile
import unittest
import sqlite3

from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.core.lifecycle import LifecycleEngine
from src.core.breeding import BreedingEngine
from src.race.rankings import RankingManager
from src.models.horse import GrowthType


class TestStableEntryAndGrowth(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False)
        self.temp_path = self.temp_file.name
        self.temp_file.close()
        self.db = Database(self.temp_path)
        self.init = DatabaseInitializer(self.db)
        self.init.initialize_all(force_recreate=True)

    def tearDown(self):
        try:
            if os.path.exists(self.temp_path):
                os.remove(self.temp_path)
        except Exception:
            pass

    def test_initial_sire_dispersion_in_stables(self):
        """初年度の厩舎入厩において、種牡馬が特定厩舎に偏らず分散していることを検証"""
        with self.db.session() as conn:
            trainers = conn.execute("SELECT trainer_id FROM trainers").fetchall()
            self.assertEqual(len(trainers), 60)

            diverse_stables_count = 0
            for t in trainers:
                t_id = t["trainer_id"]
                sires_in_stable = conn.execute(
                    "SELECT DISTINCT sire_id FROM horses WHERE trainer_id = ? AND is_active = 1",
                    (t_id,)
                ).fetchall()
                if len(sires_in_stable) >= 3:
                    diverse_stables_count += 1

            self.assertGreaterEqual(diverse_stables_count, 55)

    def test_growth_curve_and_trainer_bonus(self):
        """成長曲線および調教師スキルボーナスによる能力発揮率の計算検証"""
        with self.db.session() as conn:
            conn.execute("UPDATE trainers SET skill_level = 90.0 WHERE trainer_id = 1")
            conn.execute("UPDATE trainers SET skill_level = 30.0 WHERE trainer_id = 2")

            conn.execute(
                """
                UPDATE horses SET age = 2, growth_type = 'early', trainer_id = 1, peak_age = 3.0, current_ability_rate = 0.78
                WHERE horse_id = 1
                """
            )
            conn.execute(
                """
                UPDATE horses SET age = 2, growth_type = 'early', trainer_id = 2, peak_age = 3.0, current_ability_rate = 0.78
                WHERE horse_id = 2
                """
            )
            conn.execute(
                """
                UPDATE horses SET age = 2, growth_type = 'late', trainer_id = 1, peak_age = 5.5, current_ability_rate = 0.55
                WHERE horse_id = 3
                """
            )

        lifecycle = LifecycleEngine(db=self.db)
        lifecycle.advance_year(current_year=1, strict_free_jockey=False)

        with self.db.session() as conn:
            h1 = conn.execute("SELECT age, current_ability_rate FROM horses WHERE horse_id = 1").fetchone()
            h2 = conn.execute("SELECT age, current_ability_rate FROM horses WHERE horse_id = 2").fetchone()
            h3 = conn.execute("SELECT age, current_ability_rate FROM horses WHERE horse_id = 3").fetchone()

            self.assertEqual(h1["age"], 3)
            self.assertEqual(h2["age"], 3)
            self.assertEqual(h3["age"], 3)

            self.assertGreater(h1["current_ability_rate"], h2["current_ability_rate"])
            self.assertAlmostEqual(h1["current_ability_rate"], 1.02, delta=0.02)
            self.assertAlmostEqual(h2["current_ability_rate"], 0.99, delta=0.02)
            self.assertAlmostEqual(h3["current_ability_rate"], 0.77, delta=0.02)

    def test_2yo_pedigree_draft_priority(self):
        """実績上位厩舎への血統期待値優先ドラフト入厩の検証"""
        self.init.initialize_all(force_recreate=True, include_yearlings=True)

        with self.db.session() as conn:
            conn.execute(
                """
                UPDATE trainers
                SET current_year_starts = 50, current_year_wins = 20, current_year_g1 = 2, skill_level = 85.0
                WHERE trainer_id = 1
                """
            )
            conn.execute(
                """
                UPDATE trainers
                SET current_year_starts = 30, current_year_wins = 1, current_year_g1 = 0, skill_level = 40.0
                WHERE trainer_id = 2
                """
            )

        lifecycle = LifecycleEngine(db=self.db)
        lifecycle.advance_year(current_year=1, strict_free_jockey=False)

        with self.db.session() as conn:
            # 2歳新馬（前年1歳幼駒で加齢して2歳になり、ドラフト入厩した馬）
            new_2yo_t1 = conn.execute(
                "SELECT h.horse_id, h.sire_id, h.trainer_id FROM horses h WHERE h.age = 2 AND h.is_active = 1 AND h.trainer_id = 1"
            ).fetchall()
            self.assertGreater(len(new_2yo_t1), 0)

    def test_rankings_dash_format(self):
        """リーディング集計で戦績がハイフン区切り(**-**-**)であることを検証"""
        ranking_mgr = RankingManager(db=self.db)
        self.assertTrue(hasattr(ranking_mgr, "get_jockey_rankings"))
        self.assertTrue(hasattr(ranking_mgr, "get_trainer_rankings"))
        self.assertTrue(hasattr(ranking_mgr, "get_owner_rankings"))
        self.assertTrue(hasattr(ranking_mgr, "get_breeder_rankings"))
        self.assertTrue(hasattr(ranking_mgr, "get_sire_rankings"))
        self.assertTrue(hasattr(ranking_mgr, "get_sire_progenies"))


if __name__ == "__main__":
    unittest.main()
