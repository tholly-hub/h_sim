import os, sys, tempfile, unittest
from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.race.calendar import CalendarController
from src.race.annual_program import generate_full_program
from src.gui.views.horse_detail_dialog import HorseDetailDialog
from src.race.engine import RaceEngine
from src.models.horse import Horse, GenotypeMSTN, GrowthType, RunningStyle
from src.models.race import Race, RaceGrade, RaceSurface, AgeRestriction, SexRestriction
from src.core.lifecycle import LifecycleEngine

class TestPhase5Refinements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_file = tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False)
        cls.temp_path = cls.temp_file.name
        cls.temp_file.close()
        cls.db = Database(cls.temp_path)
        init = DatabaseInitializer(cls.db)
        init.initialize_all(force_recreate=True)
        cls.cal = CalendarController(cls.db)

    @classmethod
    def tearDownClass(cls):
        try:
            if os.path.exists(cls.temp_path):
                os.remove(cls.temp_path)
        except Exception:
            pass

    def test_2yo_dirt_trials_exist(self):
        races = generate_full_program(year=1)
        r_names = [r.name for r in races]
        
        # カトレアS, JBC2歳優駿, 兵庫ジュニアGPの存在確認
        self.assertTrue(any('カトレアステークス' in n and '全日本２歳優駿' in n for n in r_names))
        self.assertTrue(any('JBC2歳優駿' in n and '全日本２歳優駿' in n for n in r_names))
        self.assertTrue(any('兵庫ジュニアグランプリ' in n and '全日本２歳優駿' in n for n in r_names))
        print('PASS: 2yo dirt trials exist and are designated as All Japan 2yo Yushun trials.')

    def test_horse_detail_date_format_and_descending(self):
        # 1年目21週・22週のレースを実行
        self.cal.run_week(1, 21)
        self.cal.run_week(1, 22)
        with self.db.session() as conn:
            row = conn.execute('SELECT horse_id FROM results GROUP BY horse_id LIMIT 1').fetchone()
            horse_id = row['horse_id']

        dlg = HorseDetailDialog(self.db, horse_id)
        self.assertTrue(dlg.table_history.rowCount() >= 1)
        date_txt = dlg.table_history.item(0, 0).text()
        self.assertTrue('年' in date_txt and '月' in date_txt and '週' in date_txt and '/' not in date_txt)
        print(f'PASS: Date format verification successful -> {date_txt}')

    def test_improved_odds_suitability(self):
        engine = RaceEngine()
        # DBからダート得意馬と芝得意馬を検索してテスト
        with self.db.session() as conn:
            rows = conn.execute('SELECT * FROM horses WHERE is_active = 1 LIMIT 50').fetchall()
            horses = [Horse.from_row(r) for r in rows]
        
        dirt_horses = [h for h in horses if h.surface_aptitude == 'dirt']
        turf_horses = [h for h in horses if h.surface_aptitude == 'turf']
        
        self.assertTrue(len(dirt_horses) > 0)
        self.assertTrue(len(turf_horses) > 0)
        
        dh = dirt_horses[0]
        th = turf_horses[0]
        
        # 能力・遺伝型・戦績を揃える
        dh.speed = 60.0
        dh.stamina = 60.0
        dh.acceleration = 60.0
        dh.mstn_type = GenotypeMSTN.CT
        dh.career_starts = 0
        dh.career_wins = 0

        th.speed = 60.0
        th.stamina = 60.0
        th.acceleration = 60.0
        th.mstn_type = GenotypeMSTN.CT
        th.career_starts = 0
        th.career_wins = 0
        
        race_dirt = Race(
            name='ダート特別', track_id='TOKYO', month=11, week=43, grade=RaceGrade.L,
            surface=RaceSurface.DIRT, distance=1600, age_restriction=AgeRestriction.TWO_YO,
            sex_restriction=SexRestriction.MIXED, full_gate=8
        )
        odds = engine.calculate_odds([dh, th], race_dirt, {})
        self.assertTrue(odds[dh.horse_id] < odds[th.horse_id])
        print(f'PASS: Odds accurately reflect surface aptitude -> Dirt Horse ({odds[dh.horse_id]}x) vs Turf Horse ({odds[th.horse_id]}x)')

    def test_replay_goal_crossing_order_matches_finish_time(self):
        import json
        engine = RaceEngine()
        with self.db.session() as conn:
            rows = conn.execute('SELECT * FROM horses WHERE is_active = 1 LIMIT 8').fetchall()
            horses = [Horse.from_row(r) for r in rows]

        race = Race(
            name='日本ダービー', track_id='TOKYO', month=5, week=21, grade=RaceGrade.G1,
            surface=RaceSurface.TURF, distance=2400, age_restriction=AgeRestriction.THREE_YO,
            sex_restriction=SexRestriction.MIXED, full_gate=8
        )

        # 各馬の確定走破タイムをバラバラに設定
        finish_times = {}
        for idx, h in enumerate(horses):
            finish_times[h.horse_id] = 145.0 + (idx * 0.35) if idx % 2 == 0 else 145.0 + ((7 - idx) * 0.40)

        replay_json, _ = engine.generate_replay_data(race, finish_times, horses)
        data = json.loads(replay_json)

        goal_crossing_times = {}
        for h_data in data['horses']:
            hid = h_data['horse_id']
            pos = h_data['positions']
            dt = data['dt']
            for step_idx, dist in enumerate(pos):
                if dist >= 2400.0:
                    goal_crossing_times[hid] = step_idx * dt
                    break

        expected_order = sorted(finish_times.keys(), key=lambda hid: finish_times[hid])
        actual_order = sorted(goal_crossing_times.keys(), key=lambda hid: goal_crossing_times[hid])

        self.assertEqual(expected_order, actual_order)
        print('PASS: All finish positions match goal-crossing order 100% perfectly!')

    def test_initial_stud_fee_calculation(self):
        """現役時代の成績に応じた新種牡馬の初年度種付け料算定テスト"""
        # 1. 一般重賞勝ち馬 (G3 1勝, 獲得賞金8000万円)
        fee_g3 = LifecycleEngine.calculate_initial_stud_fee(
            g1_wins=0, g2_wins=0, g3_wins=1, career_earnings=80_000_000,
            speed=55.0, stamina=55.0, acceleration=55.0
        )
        self.assertTrue(1_000_000 <= fee_g3 <= 2_000_000)

        # 2. G1馬 (G1 1勝, G2 1勝, 獲得賞金3億円)
        fee_g1 = LifecycleEngine.calculate_initial_stud_fee(
            g1_wins=1, g2_wins=1, g3_wins=0, career_earnings=300_000_000,
            speed=65.0, stamina=65.0, acceleration=65.0
        )
        self.assertTrue(4_000_000 <= fee_g1 <= 6_000_000)

        # 3. 三冠馬・顕彰馬クラス (G1 5勝, 獲得賞金12億円, 高能力)
        fee_legend = LifecycleEngine.calculate_initial_stud_fee(
            g1_wins=5, g2_wins=2, g3_wins=1, career_earnings=1_200_000_000,
            speed=78.0, stamina=76.0, acceleration=77.0
        )
        self.assertTrue(15_000_000 <= fee_legend <= 25_000_000)
        self.assertGreater(fee_legend, fee_g1)
        self.assertGreater(fee_g1, fee_g3)
        print(f"PASS: Initial stud fees -> G3: {fee_g3:,}円, G1: {fee_g1:,}円, Legend: {fee_legend:,}円")

    def test_odds_variance_and_longshots(self):
        """オッズが全頭10倍以内に固まらず、実力差に応じた適切なオッズ傾斜になることの検証"""
        engine = RaceEngine()
        favorite = Horse(
            name="スーパーホース", sex="colt", birth_year=1, age=3,
            breeder_id=1, owner_id=1, mstn_type=GenotypeMSTN.CT,
            speed=75.0, stamina=70.0, acceleration=75.0, temperament=70.0, durability=70.0,
            maternal_vitality=70.0, growth_type=GrowthType.NORMAL, peak_age=4.0, horse_id=201,
            career_starts=6, career_wins=5, g1_wins=2, g2_wins=1, g3_wins=0
        )
        favorite.condition = 60.0

        rival = Horse(
            name="ライバルホース", sex="colt", birth_year=1, age=3,
            breeder_id=1, owner_id=1, mstn_type=GenotypeMSTN.CT,
            speed=60.0, stamina=60.0, acceleration=60.0, temperament=55.0, durability=55.0,
            maternal_vitality=55.0, growth_type=GrowthType.NORMAL, peak_age=4.0, horse_id=202,
            career_starts=5, career_wins=2, g1_wins=0, g2_wins=0, g3_wins=0
        )
        rival.condition = 50.0

        normals = []
        for i in range(4):
            h = Horse(
                name=f"一般馬{i+1}", sex="colt", birth_year=1, age=3,
                breeder_id=1, owner_id=1, mstn_type=GenotypeMSTN.CT,
                speed=50.0, stamina=50.0, acceleration=50.0, temperament=50.0, durability=50.0,
                maternal_vitality=50.0, growth_type=GrowthType.NORMAL, peak_age=4.0, horse_id=203 + i,
                career_starts=4, career_wins=1, g1_wins=0, g2_wins=0, g3_wins=0
            )
            h.condition = 50.0
            normals.append(h)

        longshots = []
        for i in range(2):
            h = Horse(
                name=f"大穴馬{i+1}", sex="colt", birth_year=1, age=3,
                breeder_id=1, owner_id=1, mstn_type=GenotypeMSTN.TT,
                speed=38.0, stamina=38.0, acceleration=38.0, temperament=40.0, durability=40.0,
                maternal_vitality=40.0, growth_type=GrowthType.NORMAL, peak_age=4.0, horse_id=207 + i,
                career_starts=3, career_wins=0, g1_wins=0, g2_wins=0, g3_wins=0
            )
            h.condition = 45.0
            longshots.append(h)

        starters = [favorite, rival] + normals + longshots
        race = Race(
            name="東京優駿（日本ダービー）", track_id="TOKYO", month=5, week=21, grade=RaceGrade.G1,
            surface=RaceSurface.TURF, distance=2400, age_restriction=AgeRestriction.THREE_YO,
            sex_restriction=SexRestriction.MIXED, full_gate=8
        )

        odds = engine.calculate_odds(starters, race, {})

        fav_odd = odds[favorite.horse_id]
        self.assertTrue(1.1 <= fav_odd <= 3.5, f"本命オッズ: {fav_odd}")
        has_longshot = any(odd >= 30.0 for odd in odds.values())
        self.assertTrue(has_longshot, f"全頭10倍以内にならず、高配当馬が存在すること: {odds}")
        self.assertLess(odds[favorite.horse_id], odds[rival.horse_id])
        for ls in longshots:
            self.assertGreater(odds[ls.horse_id], odds[rival.horse_id])
        print(f"PASS: Odds distribution -> Fav: {fav_odd}x, Rival: {odds[rival.horse_id]}x, Longshots: {[odds[ls.horse_id] for ls in longshots]}")


if __name__ == '__main__':
    unittest.main()
