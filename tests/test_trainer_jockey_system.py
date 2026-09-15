"""
厩舎（調教師スキル・所属騎手・調教助手承継）および騎手（成長曲線・体力低下・18歳デビュー・フリー化条件・多段階引退・定員維持）
包括テストスイート
"""

import os
import unittest
from pathlib import Path

from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.management.jockey_manager import JockeyManager
from src.models.jockey import Jockey
from src.models.trainer import Trainer
from src.core.lifecycle import LifecycleEngine


class TestTrainerJockeySystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_db_path = Path("tests/test_trainer_jockey.db")
        if cls.test_db_path.exists():
            cls.test_db_path.unlink()
        cls.db = Database(str(cls.test_db_path))
        cls.initializer = DatabaseInitializer(cls.db)
        cls.initializer.initialize_all(force_recreate=True)
        cls.lifecycle = LifecycleEngine(cls.db)
        cls.jockey_mgr = JockeyManager(cls.db, quota_miho=45, quota_ritto=45)

    @classmethod
    def tearDownClass(cls):
        if cls.test_db_path.exists():
            cls.test_db_path.unlink()

    def test_1_initial_jockeys_and_trainers_quota(self):
        """初期生成時の騎手定員（90名・美浦45/栗東45）、厩舎（60厩舎）、所属騎手配備を検証"""
        with self.db.session() as conn:
            jockeys_count = conn.execute("SELECT COUNT(*) FROM jockeys WHERE is_active = 1").fetchone()[0]
            miho_count = conn.execute("SELECT COUNT(*) FROM jockeys WHERE is_active = 1 AND location = '美浦'").fetchone()[0]
            ritto_count = conn.execute("SELECT COUNT(*) FROM jockeys WHERE is_active = 1 AND location = '栗東'").fetchone()[0]
            self.assertEqual(jockeys_count, 90, "騎手定員は90名である必要があります")
            self.assertEqual(miho_count, 45, "美浦騎手は45名である必要があります")
            self.assertEqual(ritto_count, 45, "栗東騎手は45名である必要があります")

            # 厩舎数
            trainers_count = conn.execute("SELECT COUNT(*) FROM trainers").fetchone()[0]
            self.assertEqual(trainers_count, 60, "厩舎数は60である必要があります")

            # 全60厩舎に1名ずつ所属騎手が配備されているか
            stable_jockeys = conn.execute("SELECT COUNT(DISTINCT trainer_id) FROM jockeys WHERE is_active = 1 AND trainer_id IS NOT NULL").fetchone()[0]
            self.assertEqual(stable_jockeys, 60, "全60厩舎に所属騎手が配備されている必要があります")

            # 調教師初期スキル
            t_skills = conn.execute("SELECT skill_level FROM trainers").fetchall()
            for ts in t_skills:
                self.assertGreaterEqual(ts["skill_level"], 45.0)

    def test_2_trainer_skill_growth_never_decreases(self):
        """調教師スキルが開業年数や成績によって向上し、減少しないことを検証"""
        t = Trainer(name="テスト厩舎", location="栗東", age=55, trainer_years=5, skill_level=52.0)
        skill_1 = t.calculate_skill_growth(wins_this_year=0)
        self.assertGreater(skill_1, 52.0, "勝利数0でも年数経験によりスキルが向上するべき")
        
        skill_2 = t.calculate_skill_growth(wins_this_year=20, g1_this_year=1, g2_this_year=2)
        self.assertGreater(skill_2, skill_1, "勝利数・重賞数が多い年はさらにスキルが伸びるべき")
        self.assertLessEqual(skill_2, 99.0, "上限99.0を超えないこと")

    def test_3_jockey_growth_curve_and_stamina_decay(self):
        """騎手の成長曲線と40歳以降の体力・推進力減退および経験・技術向上の検証"""
        young_j = Jockey(
            name="若手 騎手", location="美浦", age=20, debut_year=1, career_years=2,
            growth_type="standard", skill=50.0, drive=50.0, stamina=60.0, experience=5.0
        )
        young_j.advance_age_and_abilities(wins_this_year=15, g1_this_year=0, rides_this_year=100)
        self.assertEqual(young_j.age, 21)
        self.assertGreater(young_j.skill, 50.0, "若手期は技術が向上")
        self.assertGreater(young_j.stamina, 60.0, "若手期は体力が向上")

        veteran_j = Jockey(
            name="ベテラン 騎手", location="栗東", age=45, debut_year=-26, career_years=28,
            growth_type="standard", skill=80.0, drive=75.0, stamina=70.0, experience=70.0
        )
        veteran_j.advance_age_and_abilities(wins_this_year=10, g1_this_year=0, rides_this_year=80)
        self.assertEqual(veteran_j.age, 46)
        self.assertGreaterEqual(veteran_j.skill, 80.0, "40歳以降も経験により技術は維持または微増")
        self.assertLess(veteran_j.stamina, 70.0, "40歳以降は体力が減退")
        self.assertLess(veteran_j.drive, 75.0, "40歳以降は推進力（追い）が減退")

    def test_4_free_jockey_strictness_comparison(self):
        """フリー騎手転向条件の標準条件と厳格条件（ユーザー要望）の検証・比較"""
        j_a = Jockey(name="テストA", location="美浦", age=28, debut_year=1, career_wins=100, g1_wins=0, g2_wins=0, g3_wins=5)
        self.assertTrue(j_a.can_become_free(strict=False), "標準条件ではG3 5勝でフリー化可能")
        self.assertFalse(j_a.can_become_free(strict=True), "厳格条件ではG3 5勝のみではフリー化不可（重賞5勝中G2以上2勝以上が必要）")

        j_b = Jockey(name="テストB", location="栗東", age=30, debut_year=1, career_wins=120, g1_wins=1)
        self.assertTrue(j_b.can_become_free(strict=False), "標準条件では100勝+G1でフリー化可能")
        self.assertFalse(j_b.can_become_free(strict=True), "厳格条件では150勝+G1が必要なため不可")

        j_c = Jockey(name="テストC", location="栗東", age=32, debut_year=1, career_wins=180, g1_wins=1)
        self.assertTrue(j_c.can_become_free(strict=False))
        self.assertTrue(j_c.can_become_free(strict=True), "厳格条件でも150勝+G1達成者はフリー化可能")

    def test_5_multi_year_advancement_and_quota_sustainability(self):
        """複数年の年進行シミュレーションを行い、定員90名維持・世代交代・調教助手承継が正常に稼働することを検証"""
        for year in range(1, 4):
            res = self.lifecycle.advance_year(current_year=year, strict_free_jockey=True)
            with self.db.session() as conn:
                active_jockeys = conn.execute("SELECT COUNT(*) FROM jockeys WHERE is_active = 1").fetchone()[0]
                self.assertEqual(active_jockeys, 90, f"{year}年目進行後も現役騎手は90名一定である必要があります")

                active_trainers = conn.execute("SELECT COUNT(*) FROM trainers").fetchone()[0]
                self.assertEqual(active_trainers, 60, f"{year}年目進行後も厩舎数は60一定である必要があります")


if __name__ == '__main__':
    unittest.main()
