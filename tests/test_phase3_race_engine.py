"""
Phase 3 包括テスト (unittestベース):
- レース番組表登録
- トライアル優先出走権 & フルゲート選定
- 走破タイム確定 & 着差 & リプレイJSON
- 週進行・月進行・年間48週完走
- 3歳未勝利足切り引退
- 5大リーディング集計
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# プロジェクトルートを sys.path に追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.models.horse import GenotypeMSTN, GrowthType, Horse, RunningStyle
from src.models.race import AgeRestriction, Race, RaceGrade, RaceSurface, SexRestriction
from src.race.calendar import CalendarController
from src.race.engine import RaceEngine, calculate_margin, get_base_time
from src.race.entry import RaceEntryManager
from src.race.program import RaceProgramBuilder
from src.race.rankings import RankingManager
from src.race.track import get_track_info


class TestPhase3RaceEngine(unittest.TestCase):
    """Phase 3 レースエンジン包括テストケース"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_file = Path(self.temp_dir) / "test_phase3.db"
        self.db = Database(db_path=self.db_file)
        self.db.initialize_schema(force_recreate=True)
        initializer = DatabaseInitializer(self.db)
        initializer.initialize_all(force_recreate=False)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_track_info(self):
        """競馬場モデルの取得テスト"""
        track_a = get_track_info('A')
        self.assertEqual(track_a.track_id, 'A')
        self.assertEqual(track_a.straight_length, 400.0)
        self.assertFalse(track_a.has_slope)

        track_b = get_track_info('B')
        self.assertTrue(track_b.has_slope)
        self.assertEqual(track_b.straight_length, 520.0)

        track_c = get_track_info('C')
        self.assertEqual(track_c.slope_type, 'steep_slope')

    def test_program_generation_and_registration(self):
        """番組表生成およびDB登録のテスト"""
        builder = RaceProgramBuilder(self.db)
        races = builder.generate_annual_program(year=1)

        self.assertGreaterEqual(len(races), 150)

        # 主要G1の存在確認
        g1_names = [r.name for r in races if r.grade == RaceGrade.G1]
        self.assertIn('皐月賞', g1_names)
        self.assertIn('日本ダービー', g1_names)
        self.assertIn('菊花賞', g1_names)
        self.assertIn('桜花賞', g1_names)
        self.assertIn('オークス', g1_names)
        self.assertIn('秋華賞', g1_names)
        self.assertIn('天皇賞（春）', g1_names)
        self.assertIn('ジャパンC', g1_names)
        self.assertIn('有馬記念', g1_names)
        self.assertIn('阪神ジュベナイルフィリーズ', g1_names)
        self.assertIn('朝日杯フューチュリティS', g1_names)
        self.assertIn('NHKマイルカップ', g1_names)
        self.assertIn('羽田盃', g1_names)
        self.assertIn('東京ダービー', g1_names)
        self.assertIn('ジャパンダートクラシック', g1_names)

        # DB登録テスト
        count = builder.register_annual_program(year=1)
        self.assertEqual(count, len(races))

        with self.db.session() as conn:
            cur = conn.execute("SELECT COUNT(*) as cnt FROM races WHERE year = 1")
            row = cur.fetchone()
            self.assertEqual(row['cnt'], count)

    def test_base_times_and_margins(self):
        """基準タイム計算および着差表現のテスト"""
        self.assertEqual(get_base_time(1000), 70.0)
        self.assertEqual(get_base_time(1600), 117.0)
        self.assertEqual(get_base_time(2400), 185.0)

        dirt_1600 = get_base_time(1600, surface=RaceSurface.DIRT)
        self.assertGreater(dirt_1600, 117.0)

        # 着差判定
        self.assertEqual(calculate_margin(0.0), "同着")
        self.assertEqual(calculate_margin(0.02), "ハナ")
        self.assertEqual(calculate_margin(0.05), "アタマ")
        self.assertEqual(calculate_margin(0.10), "クビ")
        self.assertEqual(calculate_margin(0.20), "1/2")
        self.assertEqual(calculate_margin(0.40), "1")
        self.assertEqual(calculate_margin(1.30), "2")
        self.assertEqual(calculate_margin(5.00), "大差")

    def test_race_engine_simulation(self):
        """レースシミュレーション実行テスト"""
        engine = RaceEngine()
        track_b = get_track_info('B')

        fast_horse = Horse(
            name="韋駄天号",
            sex="colt",
            birth_year=1,
            age=3,
            breeder_id=1,
            owner_id=1,
            mstn_type=GenotypeMSTN.CT,
            speed=90.0,
            stamina=80.0,
            acceleration=85.0,
            temperament=80.0,
            durability=75.0,
            maternal_vitality=80.0,
            growth_type=GrowthType.NORMAL,
            peak_age=4.0,
            horse_id=101,
        )

        slow_horse = Horse(
            name="のんびり号",
            sex="colt",
            birth_year=1,
            age=3,
            breeder_id=1,
            owner_id=1,
            mstn_type=GenotypeMSTN.TT,
            speed=30.0,
            stamina=30.0,
            acceleration=30.0,
            temperament=40.0,
            durability=40.0,
            maternal_vitality=40.0,
            growth_type=GrowthType.NORMAL,
            peak_age=4.0,
            horse_id=102,
        )

        race = Race(
            name="テスト記念",
            track_id="B",
            month=5,
            week=20,
            grade=RaceGrade.G1,
            surface=RaceSurface.TURF,
            distance=1600,
            age_restriction=AgeRestriction.THREE_YO,
            race_id=1,
            base_prize=100_000_000,
            condition_prize=50_000_000,
        )

        t_fast = engine.calculate_finish_time(fast_horse, race, track_b)
        t_slow = engine.calculate_finish_time(slow_horse, race, track_b)

        self.assertLess(t_fast, t_slow)
        self.assertTrue(90.0 <= t_fast <= 105.0)

        starters = [fast_horse, slow_horse]
        results = engine.run_race(race, starters, {101: 1, 102: 2}, [], [])

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].horse_id, 101)
        self.assertEqual(results[0].finish_position, 1)
        self.assertEqual(results[0].prize_awarded, 100_000_000)
        self.assertEqual(results[0].condition_prize_awarded, 50_000_000)
        self.assertIsNotNone(results[0].replay_data_json)

        replay = json.loads(results[0].replay_data_json)
        self.assertEqual(replay["distance"], 1600)
        self.assertEqual(len(replay["horses"]), 2)
        self.assertGreater(len(replay["horses"][0]["positions"]), 0)

    def test_priority_and_starters_selection(self):
        """トライアル優先出走権と出走馬選定テスト"""
        entry_mgr = RaceEntryManager(self.db)
        builder = RaceProgramBuilder(self.db)
        builder.register_annual_program(year=1)

        with self.db.session() as conn:
            cur = conn.execute("SELECT race_id FROM races WHERE name LIKE '%弥生賞%' AND year = 1")
            yayoi_race = cur.fetchone()
            self.assertIsNotNone(yayoi_race)
            yayoi_race_id = yayoi_race['race_id']

            conn.execute(
                """
                INSERT INTO results (race_id, horse_id, finish_position, finish_time, prize_awarded)
                VALUES (?, 1, 1, 120.0, 50000000),
                       (?, 2, 2, 120.2, 20000000),
                       (?, 3, 3, 120.5, 12000000)
                """,
                (yayoi_race_id, yayoi_race_id, yayoi_race_id),
            )

            priority_ids = entry_mgr.get_priority_horses_for_g1("皐月賞", year=1, conn=conn)
            self.assertEqual(set(priority_ids), {1, 2, 3})

    def test_calendar_week_and_rankings_simulation(self):
        """週間シミュレーションおよび5大リーディング集計テスト"""
        builder = RaceProgramBuilder(self.db)
        builder.register_annual_program(year=1)

        controller = CalendarController(self.db)

        # 第9週（弥生賞・チューリップ賞週）を実行
        res_week9 = controller.run_week(year=1, week=9)
        self.assertGreater(res_week9["races_run"], 0)
        self.assertGreater(res_week9["starters_count"], 0)

        # 第15週（皐月賞週）を実行
        res_week15 = controller.run_week(year=1, week=15)
        self.assertGreater(res_week15["races_run"], 0)

        # 第28週（3歳未勝利足切り週）を実行
        res_week28 = controller.run_week(year=1, week=28)
        self.assertIn("retired_maidens", res_week28)

        # リーディング集計テスト
        rankings = RankingManager(self.db)
        jockeys = rankings.get_jockey_rankings(limit=10)
        self.assertGreater(len(jockeys), 0)
        self.assertIn("career_wins", jockeys[0])

        trainers = rankings.get_trainer_rankings(limit=10)
        self.assertGreater(len(trainers), 0)

        owners = rankings.get_owner_rankings(limit=10)
        self.assertGreater(len(owners), 0)

        breeders = rankings.get_breeder_rankings(limit=10)
        self.assertGreater(len(breeders), 0)

    def test_full_year_simulation(self):
        """年間48週の全レースシミュレーション完走テスト"""
        builder = RaceProgramBuilder(self.db)
        builder.register_annual_program(year=1)

        controller = CalendarController(self.db)
        year_summary = controller.run_year(year=1)

        self.assertEqual(year_summary["year"], 1)
        self.assertEqual(year_summary["total_weeks"], 48)
        self.assertGreater(year_summary["total_races_run"], 150)
        self.assertGreater(year_summary["total_starters"], 500)

        with self.db.session() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM results")
            results_count = cur.fetchone()[0]
            self.assertGreater(results_count, 500)

            cur_g1 = conn.execute("SELECT COUNT(*) FROM horses WHERE g1_wins > 0")
            g1_winners = cur_g1.fetchone()[0]
            self.assertGreater(g1_winners, 0)


if __name__ == "__main__":
    unittest.main()
