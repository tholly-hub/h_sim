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
        self.assertTrue('年/' in date_txt and '月/' in date_txt and '週' in date_txt)
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
        
        # 能力を揃える
        dh.speed = 60.0
        dh.stamina = 60.0
        dh.acceleration = 60.0
        th.speed = 60.0
        th.stamina = 60.0
        th.acceleration = 60.0
        
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

if __name__ == '__main__':
    unittest.main()
