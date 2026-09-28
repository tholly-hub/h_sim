"""
Step 2: 騎手減量記号・斤量表示 & 厳格な引退・フリー化ルールの検証テスト
- 見習騎手・女性騎手の減量制度（★▲△◇）
- 重賞・リステッドでの減量除外
- フリー化条件（通算300勝以上 かつ G1 10勝以上 または 重賞30勝以上）
- 引退条件（50歳定年、通算100勝未満・年間5勝未満3年連続、45歳以上年間5勝未満）
- レース結果への実効斤量記録
"""

import unittest
from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.models.jockey import Jockey
from src.management.jockey_manager import JockeyManager
from src.models.race import Race, RaceGrade, RaceSurface, AgeRestriction, SexRestriction
from src.race.engine import RaceEngine
from src.models.horse import Horse, GenotypeMSTN, GrowthType
from src.models.trainer import Trainer


class TestStep2JockeyAllowanceAndRules(unittest.TestCase):

    def setUp(self):
        self.db = Database(":memory:")
        self.jockey_mgr = JockeyManager(self.db, quota_miho=45, quota_ritto=45)

    def test_jockey_weight_allowance_rules(self):
        """見習騎手・女性騎手の減量制度（★▲△◇）の検証"""
        # 1. 1年目・通算10勝の男性見習騎手 -> ★ (-4.0kg)
        j1 = Jockey(name="新人1", location="美浦", age=18, debut_year=1, career_years=1, career_wins=10, gender="male")
        allow_kg, symbol = j1.get_weight_allowance(is_graded_or_listed=False)
        self.assertEqual(allow_kg, -4.0)
        self.assertEqual(symbol, "★")

        # 2. 2年目・通算40勝の男性見習騎手 -> ▲ (-3.0kg)
        j2 = Jockey(name="新人2", location="美浦", age=19, debut_year=1, career_years=2, career_wins=40, gender="male")
        allow_kg, symbol = j2.get_weight_allowance(is_graded_or_listed=False)
        self.assertEqual(allow_kg, -3.0)
        self.assertEqual(symbol, "▲")

        # 3. 3年目・通算80勝の男性見習騎手 -> △ (-2.0kg)
        j3 = Jockey(name="新人3", location="美浦", age=20, debut_year=1, career_years=3, career_wins=80, gender="male")
        allow_kg, symbol = j3.get_weight_allowance(is_graded_or_listed=False)
        self.assertEqual(allow_kg, -2.0)
        self.assertEqual(symbol, "△")

        # 4. 4年目・通算120勝の男性騎手 (101勝超) -> 減量なし (0.0kg)
        j4 = Jockey(name="若手4", location="美浦", age=21, debut_year=1, career_years=4, career_wins=120, gender="male")
        allow_kg, symbol = j4.get_weight_allowance(is_graded_or_listed=False)
        self.assertEqual(allow_kg, 0.0)
        self.assertEqual(symbol, "")

        # 5. 1年目・通算20勝の女性見習騎手 -> ★ (-4.0kg)
        j5_f = Jockey(name="女性新人", location="美浦", age=18, debut_year=1, career_years=1, career_wins=20, gender="female")
        allow_kg, symbol = j5_f.get_weight_allowance(is_graded_or_listed=False)
        self.assertEqual(allow_kg, -4.0)
        self.assertEqual(symbol, "★")

        # 6. 6年目・通算150勝の女性騎手 (ベテラン) -> ◇ (-2.0kg 永久適用)
        j6_f = Jockey(name="女性ベテラン", location="美浦", age=24, debut_year=1, career_years=6, career_wins=150, gender="female")
        allow_kg, symbol = j6_f.get_weight_allowance(is_graded_or_listed=False)
        self.assertEqual(allow_kg, -2.0)
        self.assertEqual(symbol, "◇")

        # 7. 重賞・リステッドでは全騎手減量なし (0.0kg, "")
        allow_kg, symbol = j1.get_weight_allowance(is_graded_or_listed=True)
        self.assertEqual(allow_kg, 0.0)
        self.assertEqual(symbol, "")
        allow_kg, symbol = j6_f.get_weight_allowance(is_graded_or_listed=True)
        self.assertEqual(allow_kg, 0.0)
        self.assertEqual(symbol, "")

    def test_strict_free_jockey_requirements(self):
        """フリー騎手転身条件（通算300勝以上 かつ G1 10勝以上 または 重賞30勝以上）の検証"""
        # 条件未達: 通算290勝 (G1 12勝) -> 不可
        j1 = Jockey(name="騎手1", location="美浦", age=28, debut_year=1, career_years=10, career_wins=290, g1_wins=12, g2_wins=10, g3_wins=15)
        self.assertFalse(j1.can_become_free(strict=True))

        # 条件未達: 通算400勝 (G1 5勝, 重賞20勝) -> 不可
        j2 = Jockey(name="騎手2", location="美浦", age=30, debut_year=1, career_years=12, career_wins=400, g1_wins=5, g2_wins=7, g3_wins=8)
        self.assertFalse(j2.can_become_free(strict=True))

        # 条件達成パターンA: 通算320勝、G1 10勝 (重賞25勝) -> 許可
        j3 = Jockey(name="トップ騎手A", location="栗東", age=32, debut_year=1, career_years=14, career_wins=320, g1_wins=10, g2_wins=5, g3_wins=10)
        self.assertTrue(j3.can_become_free(strict=True))

        # 条件達成パターンB: 通算350勝、G1 6勝、重賞32勝 (G1 6 + G2 10 + G3 16 = 32) -> 許可
        j4 = Jockey(name="トップ騎手B", location="栗東", age=33, debut_year=1, career_years=15, career_wins=350, g1_wins=6, g2_wins=10, g3_wins=16)
        self.assertTrue(j4.can_become_free(strict=True))

    def test_strict_jockey_retirement_rules(self):
        """騎手引退条件（50歳定年、通算100勝未満・3年連続5勝未満、45歳以上5勝未満）の検証"""
        self.db.initialize_schema(force_recreate=True)

        with self.db.session() as conn:
            # テスト用調教師の作成
            conn.execute("INSERT INTO trainers (trainer_id, name, location, specialty, horse_capacity, reputation, skill_level, age, trainer_years) VALUES (1, '美浦厩舎', '美浦', 'turf', 30, 50.0, 50.0, 65, 5)")
            conn.execute("INSERT INTO trainers (trainer_id, name, location, specialty, horse_capacity, reputation, skill_level, age, trainer_years) VALUES (2, '栗東厩舎', '栗東', 'dirt', 30, 50.0, 50.0, 65, 5)")

            # 騎手1: 50歳 (定年)
            conn.execute(
                "INSERT INTO jockeys (jockey_id, name, location, age, debut_year, career_years, is_active, skill, drive, start_dash, temperament_handling, trainer_id, current_year_wins, career_wins) VALUES (1, '長老騎手', '美浦', 49, -25, 30, 1, 60.0, 60.0, 60.0, 60.0, 1, 10, 400)"
            )
            # 騎手2: 30歳、通算40勝、当年2勝、過去2年連続5勝未満 (3年連続低迷)
            conn.execute(
                "INSERT INTO jockeys (jockey_id, name, location, age, debut_year, career_years, is_active, skill, drive, start_dash, temperament_handling, trainer_id, current_year_wins, career_wins, low_performance_years) VALUES (2, '低迷若手', '美浦', 29, 1, 10, 1, 40.0, 40.0, 40.0, 40.0, 1, 2, 40, 2)"
            )
            # 騎手3: 45歳、当年3勝 (45歳以上年間5勝未満)
            conn.execute(
                "INSERT INTO jockeys (jockey_id, name, location, age, debut_year, career_years, is_active, skill, drive, start_dash, temperament_handling, trainer_id, current_year_wins, career_wins) VALUES (3, 'ベテラン低迷', '栗東', 44, -20, 25, 1, 50.0, 50.0, 50.0, 50.0, 2, 3, 200)"
            )

        # 4年度目の年進行を実行（3年目ガード解除後）
        res = self.jockey_mgr.progress_year_and_maintain_quota(current_year=4, strict_free=True)
        retired_ids = {r["jockey_id"] for r in res["retired_jockeys"]}

        self.assertIn(1, retired_ids, "50歳到達で定年引退")
        self.assertIn(2, retired_ids, "通算100勝未満・3年連続5勝未満で引退")
        self.assertIn(3, retired_ids, "45歳以上で年間5勝未満で引退")

    def test_race_execution_records_carried_weight_with_allowance(self):
        """レース実行時に騎手減量記号付き実効斤量がresultsテーブルに記録されることの検証"""
        race = Race(
            race_id=1, year=3, month=7, week=27, name="2歳未勝利", grade=RaceGrade.MAIDEN,
            track_id="TOKYO", surface=RaceSurface.TURF, distance=1600,
            age_restriction=AgeRestriction.TWO_YO, sex_restriction=SexRestriction.MIXED,
            weight_type="定量", base_prize=5500000, condition_prize=4000000
        )

        starters = [
            Horse(
                horse_id=1, name="テスト馬A", sex="colt", birth_year=1, age=2, breeder_id=1, owner_id=1,
                mstn_type=GenotypeMSTN.CT, speed=15.0, stamina=15.0, acceleration=15.0, temperament=10.0,
                durability=15.0, maternal_vitality=10.0, growth_type=GrowthType.NORMAL, peak_age=4.5
            )
        ]

        # ★減量 (-4.0kg) の新人騎手
        rookie_jockey = Jockey(
            jockey_id=10, name="新人★騎手", location="美浦", age=18, debut_year=3, career_years=1,
            career_wins=5, gender="male", skill=50.0, drive=50.0, start_dash=50.0, temperament_handling=50.0
        )
        trainer = Trainer(trainer_id=1, name="テスト厩舎", location="美浦")

        engine = RaceEngine()
        results = engine.run_race(
            race, starters,
            jockey_assignments={1: 10},
            all_jockeys=[rookie_jockey],
            all_trainers=[trainer]
        )

        self.assertEqual(len(results), 1)
        res = results[0]
        # 2歳牡馬の基礎斤量55.0kg - ★4.0kg = 51.0kg
        self.assertEqual(res.carried_weight, 51.0, "新人騎手★の-4kg減量が実効斤量51.0kgとして記録される")


if __name__ == "__main__":
    unittest.main()
