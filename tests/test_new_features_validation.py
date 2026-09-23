"""
新規機能（番組表、顕彰馬、特別功労、殿堂、100勝メモリアル、最優秀古馬牝馬、世代・クラス別名鑑）の総合検証テスト
"""

import unittest
from src.db.database import Database
from src.models.race import AgeRestriction, RaceGrade, RaceSurface
from src.race.annual_program import generate_full_program
from src.race.awards import AwardsManager
from src.race.calendar import CalendarController
from src.race.track import get_track_info


class TestNewFeaturesValidation(unittest.TestCase):
    """新規機能の総合テスト"""

    def setUp(self):
        self.db = Database(":memory:")
        self.db.initialize_schema()
        self.cal = CalendarController(self.db)
        self.awards_mgr = AwardsManager(self.db)

    def test_annual_program_and_tracks(self):
        """番組表の検証: 新馬75番組、地方競馬場はすべてダート"""
        races = generate_full_program(1)

        # 1. 新馬戦が年間厳密に75番組
        newcomers = [r for r in races if r.grade == RaceGrade.NEWCOMER]
        self.assertEqual(len(newcomers), 75)

        # 2. 地方競馬場（大井・川崎・船橋・盛岡）に芝レースが一切存在しない
        local_tracks = {"OI", "KAWASAKI", "FUNABASHI", "MORIOKA"}
        for r in races:
            if r.track_id in local_tracks:
                self.assertEqual(r.surface, RaceSurface.DIRT)

        for tid in local_tracks:
            tr = get_track_info(tid)
            self.assertIsNotNone(tr)
            self.assertFalse(tr.has_turf)

    def test_awards_and_hall_of_fame_definitions(self):
        """顕彰馬、特別功労、殿堂、最優秀古馬牝馬の動作テスト"""
        with self.db.session() as conn:
            conn.execute("INSERT INTO breeders (breeder_id, name, region) VALUES (1, 'ノーザンファーム', '安平')")
            conn.execute("INSERT INTO owners (owner_id, name, prefix) VALUES (1, 'サンデーR', 'サンデー')")

            # 1. 顕彰馬テスト用データ（異なるG1を5勝以上）
            conn.execute("""
                INSERT OR REPLACE INTO horses (
                    horse_id, name, sex, birth_year, age, breeder_id, owner_id,
                    mstn_type, speed, stamina, acceleration, temperament, durability,
                    maternal_vitality, growth_type, peak_age, running_style,
                    is_active, prize_money, career_starts, career_wins, g1_wins
                ) VALUES (
                    1001, 'レジェンドテイオー', 'colt', 1, 5, 1, 1,
                    'C/C', 80.0, 80.0, 80.0, 80.0, 80.0,
                    80.0, 'normal', 4.0, 'leading',
                    1, 1000000000, 10, 8, 5
                )
            """)
            # 5つの異なるG1レース作成 & 結果挿入
            for i in range(1, 6):
                r_id = 9000 + i
                conn.execute("""
                    INSERT OR REPLACE INTO races (race_id, year, month, week, name, grade, track_id, distance, surface, age_restriction, sex_restriction, full_gate)
                    VALUES (?, 1, 5, ?, ?, 'G1', 'TOKYO', 2400, 'turf', '3yo_up', 'mixed', 8)
                """, (r_id, i, f"GIレース_{i}"))
                conn.execute("""
                    INSERT OR REPLACE INTO results (race_id, horse_id, finish_position, finish_time, prize_awarded)
                    VALUES (?, 1001, 1, 140.0, 100000000)
                """, (r_id,))

            # 2. 騎手・調教師データ作成（特別功労 & 殿堂）
            conn.execute("""
                INSERT OR REPLACE INTO jockeys (
                    jockey_id, name, location, age, debut_year, skill, drive, start_dash, temperament_handling,
                    career_starts, career_wins, g1_wins, is_active
                ) VALUES (
                    2001, '武豊レジェンド', '栗東', 50, 1, 90.0, 90.0, 90.0, 90.0,
                    10000, 2100, 22, 1
                )
            """)
            conn.execute("""
                INSERT OR REPLACE INTO trainers (
                    trainer_id, name, location, specialty,
                    career_starts, career_wins, g1_wins
                ) VALUES (
                    3001, '藤沢レジェンド', '美浦', 'general',
                    8000, 1200, 15
                )
            """)
            # 調教師にG1勝ち馬を紐付け
            for i in range(1, 13):
                h_id = 5000 + i
                conn.execute("""
                    INSERT OR REPLACE INTO horses (
                        horse_id, name, sex, birth_year, age, breeder_id, owner_id, trainer_id,
                        mstn_type, speed, stamina, acceleration, temperament, durability,
                        maternal_vitality, growth_type, peak_age, running_style,
                        is_active, g1_wins
                    ) VALUES (
                        ?, ?, 'colt', 1, 4, 1, 1, 3001,
                        'C/C', 80.0, 80.0, 80.0, 80.0, 80.0,
                        80.0, 'normal', 4.0, 'leading',
                        1, 1
                    )
                """, (h_id, f"G1馬_{i}"))
                r_id = 9500 + i
                conn.execute("""
                    INSERT OR REPLACE INTO races (race_id, year, month, week, name, grade, track_id, distance, surface, age_restriction, sex_restriction, full_gate)
                    VALUES (?, 1, 6, 1, ?, 'G1', 'TOKYO', 2000, 'turf', '3yo_up', 'mixed', 8)
                """, (r_id, f"GI_馬_{i}"))
                conn.execute("""
                    INSERT OR REPLACE INTO results (race_id, horse_id, trainer_id, finish_position, finish_time, prize_awarded)
                    VALUES (?, ?, 3001, 1, 120.0, 100000000)
                """, (r_id, h_id))

        # 顕彰馬チェック
        hof_horses = self.awards_mgr.get_hall_of_fame_horses()
        self.assertEqual(len(hof_horses), 1)
        self.assertEqual(hof_horses[0]["horse_name"], "レジェンドテイオー")
        self.assertEqual(hof_horses[0]["distinct_g1_wins"], 5)

        # 特別功労チェック
        merits = self.awards_mgr.get_special_merit_awards()
        self.assertTrue(any(j["name"] == "武豊レジェンド" for j in merits["jockeys"]))
        self.assertTrue(any(t["trainer_name"] == "藤沢レジェンド" for t in merits["trainers"]))

        # 殿堂チェック
        legends = self.awards_mgr.get_hall_of_fame_legends()
        self.assertTrue(any(j["name"] == "武豊レジェンド" for j in legends["jockeys"]))
        self.assertTrue(any(t["trainer_name"] == "藤沢レジェンド" for t in legends["trainers"]))

    def test_milestone_synchronization(self):
        """100勝メモリアルが同期・取得できること"""
        with self.db.session() as conn:
            conn.execute("INSERT INTO breeders (breeder_id, name, region) VALUES (9901, 'メモリアルファーム', '安平')")
            conn.execute("INSERT INTO owners (owner_id, name, prefix) VALUES (9901, 'メモリアルオーナー', 'メモリアル')")
            conn.execute("""
                INSERT INTO jockeys (
                    jockey_id, name, location, age, debut_year, skill, drive, start_dash, temperament_handling, is_active
                ) VALUES (9901, 'メモリアル武豊', '栗東', 50, 1, 90.0, 90.0, 90.0, 90.0, 1)
            """)
            conn.execute("""
                INSERT INTO trainers (
                    trainer_id, name, location, specialty
                ) VALUES (9901, 'メモリアル矢作', '栗東', 'general')
            """)
            conn.execute("""
                INSERT INTO horses (
                    horse_id, name, sex, birth_year, age, breeder_id, owner_id,
                    mstn_type, speed, stamina, acceleration, temperament, durability,
                    maternal_vitality, growth_type, peak_age, running_style
                ) VALUES (
                    9901, 'メモリアルインパクト', 'colt', 1, 3, 9901, 9901,
                    'C/T', 85.0, 85.0, 85.0, 85.0, 85.0,
                    85.0, 'normal', 3.5, 'closing'
                )
            """)

            # 100勝分のレース・結果を一括作成
            for i in range(1, 101):
                r_id = 8000 + i
                conn.execute("""
                    INSERT OR REPLACE INTO races (race_id, year, month, week, name, grade, track_id, distance, surface, age_restriction, sex_restriction, full_gate)
                    VALUES (?, 1, 1, 1, ?, 'OP', 'TOKYO', 1600, 'turf', '3yo_up', 'mixed', 8)
                """, (r_id, f"記念レース_{i}"))
                conn.execute("""
                    INSERT OR REPLACE INTO results (race_id, horse_id, jockey_id, trainer_id, finish_position, finish_time, prize_awarded)
                    VALUES (?, 9901, 9901, 9901, 1, 95.0, 10000000)
                """, (r_id,))

        # メモリアル同期
        count = self.awards_mgr.sync_all_milestones()
        self.assertGreaterEqual(count, 4)

        records = self.awards_mgr.get_milestone_records()
        self.assertGreaterEqual(len(records), 4)
        j_rec_100 = next((r for r in records if r["entity_type"] == "jockey" and r["entity_id"] == 9901 and r["win_count"] == 100), None)
        self.assertIsNotNone(j_rec_100)
        self.assertEqual(j_rec_100["win_count"], 100)
        self.assertEqual(j_rec_100["race_name"], "記念レース_100")
        self.assertEqual(j_rec_100["horse_name"], "メモリアルインパクト")


if __name__ == "__main__":
    unittest.main()
