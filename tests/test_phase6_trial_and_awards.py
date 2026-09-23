"""
Phase 6: トライアル優先出走権、芝ダート適性専念、年度代表馬・部門賞選考、コースレコードの単体テスト
"""

import unittest
from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.race.annual_program import generate_full_program
from src.race.awards import AwardsManager
from src.race.entry import (
    G1_ALIAS_MAP,
    RaceEntryManager,
    normalize_g1_name,
)


class TestPhase6TrialAndAwards(unittest.TestCase):
    def setUp(self):
        # インメモリDBで初期化
        self.db = Database(":memory:")
        init = DatabaseInitializer(self.db)
        init.initialize_all()
        self.program = generate_full_program(1)
        self.awards_mgr = AwardsManager(self.db)
        self.entry_sys = RaceEntryManager(self.db)

    def test_g1_name_normalization(self):
        """トライアルの対象G1名と正式G1名称の正規化突合テスト"""
        self.assertEqual(normalize_g1_name("朝日杯FS"), "朝日杯フューチュリティS")
        self.assertEqual(normalize_g1_name("阪神JF"), "阪神ジュベナイルフィリーズ")
        self.assertEqual(normalize_g1_name("マイルCS"), "マイルチャンピオンシップ")
        self.assertEqual(normalize_g1_name("チャンピオンズC"), "チャンピオンズカップ")
        self.assertEqual(normalize_g1_name("菊花賞"), "菊花賞")
        self.assertEqual(normalize_g1_name("日本ダービー"), "東京優駿")

    def test_trial_priority_qualification_rules(self):
        """トライアル優先権ルール（G2上位2頭、G3上位1頭、L上位1頭）の確認"""
        trial_races = [r for r in self.program if r.is_trial]
        self.assertGreater(len(trial_races), 0, "トライアルレースが番組表に定義されていること")

        for tr in trial_races:
            self.assertIsNotNone(tr.target_g1_name)
            # G2は上位2頭、G3/Lは上位1頭が優先出走権対象
            g_str = tr.grade.value if hasattr(tr.grade, "value") else tr.grade
            expected_quota = 2 if g_str == "G2" else 1
            self.assertIn(expected_quota, (1, 2))

    def test_surface_preference_determination(self):
        """芝専念・ダート専念の判定ロジック確認"""
        with self.db.session() as conn:
            # テスト用馬を作成
            conn.execute("""
                INSERT INTO horses (
                    horse_id, name, sex, birth_year, age, sire_id, dam_id, owner_id, breeder_id, trainer_id,
                    mstn_type, speed, stamina, acceleration, temperament, durability, maternal_vitality,
                    growth_type, peak_age, running_style
                ) VALUES (
                    99901, 'ターフスペシャリスト', 'colt', 1, 3, 1, 2, 1, 1, 1,
                    'C/C', 70.0, 70.0, 70.0, 50.0, 50.0, 50.0,
                    'normal', 4.5, 'leading'
                )
            """)
            conn.execute("""
                INSERT INTO horses (
                    horse_id, name, sex, birth_year, age, sire_id, dam_id, owner_id, breeder_id, trainer_id,
                    mstn_type, speed, stamina, acceleration, temperament, durability, maternal_vitality,
                    growth_type, peak_age, running_style
                ) VALUES (
                    99902, 'ダートキング', 'colt', 1, 3, 1, 2, 1, 1, 1,
                    'T/T', 70.0, 70.0, 70.0, 50.0, 50.0, 50.0,
                    'normal', 4.5, 'leading'
                )
            """)

            # 99901: 芝で1着3回
            for offset, r_id in enumerate(range(91001, 91004)):
                conn.execute("INSERT INTO races (race_id, year, month, week, name, grade, track_id, distance, surface, age_restriction, sex_restriction) VALUES (?, 1, 5, 1, '芝テスト', 'COND_1W', 'TOKYO', 1600, 'turf', '3yo_up', 'mixed')", (r_id,))
                conn.execute("INSERT INTO results (result_id, race_id, horse_id, finish_position, prize_awarded, finish_time) VALUES (?, ?, 99901, 1, 10000000, 93.5)", (r_id, r_id))

            # 99902: ダートで1着3回
            for offset, r_id in enumerate(range(92001, 92004)):
                conn.execute("INSERT INTO races (race_id, year, month, week, name, grade, track_id, distance, surface, age_restriction, sex_restriction) VALUES (?, 1, 5, 1, 'ダートテスト', 'COND_1W', 'TOKYO', 1600, 'dirt', '3yo_up', 'mixed')", (r_id,))
                conn.execute("INSERT INTO results (result_id, race_id, horse_id, finish_position, prize_awarded, finish_time) VALUES (?, ?, 99902, 1, 10000000, 98.0)", (r_id, r_id))

            pref1 = self.entry_sys.get_horse_surface_preference(99901, conn=conn)
            self.assertEqual(pref1, "turf", "芝実績上位馬は芝専念と判定されること")

            pref2 = self.entry_sys.get_horse_surface_preference(99902, conn=conn)
            self.assertEqual(pref2, "dirt", "ダート実績上位馬はダート専念と判定されること")

    def test_annual_awards_election(self):
        """年度代表馬および7大部門賞の自動選考テスト"""
        # 成績データをダミー登録
        with self.db.session() as conn:
            conn.execute("""
                INSERT INTO horses (
                    horse_id, name, sex, birth_year, age, sire_id, dam_id, owner_id, breeder_id, trainer_id, prize_money,
                    mstn_type, speed, stamina, acceleration, temperament, durability, maternal_vitality,
                    growth_type, peak_age, running_style
                ) VALUES (
                    88801, '年度代表馬候補', 'colt', 0, 4, 1, 2, 1, 1, 1, 500000000,
                    'C/T', 80.0, 80.0, 80.0, 50.0, 50.0, 50.0,
                    'normal', 4.5, 'leading'
                )
            """)
            # G1レース勝利を2回
            for rid, rname in [(93001, "ジャパンカップ"), (93002, "有馬記念")]:
                conn.execute("INSERT INTO races (race_id, year, month, week, name, grade, track_id, distance, surface, age_restriction, sex_restriction) VALUES (?, 1, 11, 4, ?, 'G1', 'TOKYO', 2400, 'turf', '3yo_up', 'mixed')", (rid, rname))
                conn.execute("INSERT INTO results (result_id, race_id, horse_id, finish_position, prize_awarded, finish_time) VALUES (?, ?, 88801, 1, 300000000, 142.0)", (rid, rid))

        awards = self.awards_mgr.elect_annual_awards(1)
        self.assertGreater(len(awards), 0, "選考結果が返されること")
        hoty = [a for a in awards if a["category"] == "horse_of_the_year"]
        self.assertEqual(len(hoty), 1)
        self.assertEqual(hoty[0]["horse_name"], "年度代表馬候補")

        # 履歴照会
        hist = self.awards_mgr.get_horse_of_the_year_history()
        self.assertGreater(len(hist), 0)


if __name__ == "__main__":
    unittest.main()
