import unittest
import os
import shutil
from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.core.lifecycle import LifecycleEngine
from src.core.breeding import BreedingEngine

class TestRosterRulesYear1To4(unittest.TestCase):
    def setUp(self):
        self.test_db_path = "data/test_roster_rules.db"
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        self.db = Database(self.test_db_path)
        self.init = DatabaseInitializer(self.db)
        self.init.initialize_all(force_recreate=True, include_yearlings=True)
        self.lifecycle = LifecycleEngine(db=self.db)
        self.breeding = BreedingEngine(db=self.db)

    def tearDown(self):
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def test_spring_mating_equal_coverings_years_1_to_3(self):
        """1〜3年目（1〜5年目）は全種牡馬100頭に均等6頭ずつ（合計600頭）種付けされることを検証"""
        with self.db.session() as conn:
            for yr in (1, 2, 3):
                pairs = self.breeding._match_sires_and_dams(conn, current_year=yr)
                self.assertEqual(len(pairs), 600, f"{yr}年目: 600頭の繁殖牝馬がすべてマッチングされること")
                
                sire_counts = {}
                for dam, sire, _, _ in pairs:
                    s_id = sire["horse_id"]
                    sire_counts[s_id] = sire_counts.get(s_id, 0) + 1

                self.assertEqual(len(sire_counts), 100, f"{yr}年目: 全100頭の種牡馬が使用されること")
                for s_id, count in sire_counts.items():
                    self.assertEqual(count, 6, f"{yr}年目: 種牡馬ID {s_id} の種付け数が6頭であること")

    def test_sire_roster_rules_year_1_to_3(self):
        """1〜2年目の年進行では種牡馬入れ替えなし、3年目終了時以降に入れ替えが発生することを検証"""
        with self.db.session() as conn:
            initial_sire_count = conn.execute("SELECT COUNT(*) FROM sires WHERE is_active = 1").fetchone()[0]
            self.assertEqual(initial_sire_count, 100)

            # ダミーの引退オープン牡馬
            conn.execute("""
                INSERT INTO horses (horse_id, name, sex, birth_year, age, is_active, breeder_id, owner_id,
                                    mstn_type, speed, stamina, acceleration, temperament, durability, maternal_vitality,
                                    growth_type, peak_age, current_ability_rate, running_style,
                                    g1_wins, g2_wins, g3_wins, career_wins, career_starts, prize_money, condition_prize_money, generation)
                VALUES (88001, 'テスト引退オープン牡馬', 'horse', 1, 5, 0, 1, 1, 'C/T', 70.0, 70.0, 70.0, 50.0, 50.0, 50.0, 'normal', 4.5, 1.0, 'between', 3, 2, 1, 8, 15, 500000000, 30000000, 1)
            """)
            fake_retired = [dict(conn.execute("SELECT * FROM horses WHERE horse_id = 88001").fetchone())]

            # 1年目: 入れ替えなし
            promoted_1 = self.lifecycle._manage_sire_roster(conn, current_year=1, retired_horses=fake_retired)
            self.assertEqual(promoted_1, 0, "1年目は種牡馬入れ替えが発生しないこと")

            # 2年目: 入れ替えなし
            promoted_2 = self.lifecycle._manage_sire_roster(conn, current_year=2, retired_horses=fake_retired)
            self.assertEqual(promoted_2, 0, "2年目は種牡馬入れ替えが発生しないこと")

            # 3年目終了時: G1・重賞実績を持つ引退オープン牡馬が新種牡馬昇格（海外種牡馬も導入）
            promoted_3 = self.lifecycle._manage_sire_roster(conn, current_year=3, retired_horses=fake_retired)
            self.assertGreaterEqual(promoted_3, 1, "3年目終了時は新種牡馬の昇格が行われること")
            
            # 新種牡馬登録されていることを確認
            new_sire = conn.execute("SELECT * FROM sires WHERE horse_id = 88001 AND is_active = 1").fetchone()
            self.assertIsNotNone(new_sire, "テスト引退オープン牡馬が種牡馬登録されていること")

    def test_broodmare_roster_rules_year_1_to_3(self):
        """1〜2年目は入れ替えなし、3年目終了時はオープン牝馬と同数の最下位牝馬が入れ替わり600頭維持されることを検証"""
        with self.db.session() as conn:
            initial_dam_count = conn.execute("SELECT COUNT(*) FROM dams WHERE is_active = 1").fetchone()[0]
            self.assertEqual(initial_dam_count, 600)

            # 1年目: 入れ替えなし
            promoted_1 = self.lifecycle._manage_broodmare_roster(conn, current_year=1, retired_horses=[])
            self.assertEqual(promoted_1, 0)
            cnt_1 = conn.execute("SELECT COUNT(*) FROM dams WHERE is_active = 1").fetchone()[0]
            self.assertEqual(cnt_1, 600)

            # 2年目: 入れ替えなし
            promoted_2 = self.lifecycle._manage_broodmare_roster(conn, current_year=2, retired_horses=[])
            self.assertEqual(promoted_2, 0)
            cnt_2 = conn.execute("SELECT COUNT(*) FROM dams WHERE is_active = 1").fetchone()[0]
            self.assertEqual(cnt_2, 600)

            # 3年目終了時: 引退オープン牝馬が2頭いる場合
            conn.execute("""
                INSERT INTO horses (horse_id, name, sex, birth_year, age, is_active, breeder_id, owner_id,
                                    mstn_type, speed, stamina, acceleration, temperament, durability, maternal_vitality,
                                    growth_type, peak_age, current_ability_rate, running_style,
                                    g1_wins, g2_wins, g3_wins, career_wins, career_starts, prize_money, condition_prize_money, generation)
                VALUES (77001, 'オープン牝馬A', 'filly', 1, 4, 0, 1, 1, 'C/T', 60.0, 60.0, 60.0, 50.0, 50.0, 60.0, 'normal', 4.5, 1.0, 'between', 1, 1, 0, 5, 10, 200000000, 20000000, 1),
                       (77002, 'オープン牝馬B', 'filly', 1, 4, 0, 1, 1, 'C/T', 62.0, 62.0, 62.0, 50.0, 50.0, 60.0, 'normal', 4.5, 1.0, 'between', 2, 0, 0, 6, 12, 300000000, 25000000, 1),
                       (77003, '未勝利牝馬C', 'filly', 1, 4, 0, 1, 1, 'C/T', 30.0, 30.0, 30.0, 50.0, 50.0, 30.0, 'normal', 4.5, 1.0, 'between', 0, 0, 0, 0, 5, 1000000, 0, 1)
            """)
            retired_horses_yr3 = [
                dict(conn.execute("SELECT * FROM horses WHERE horse_id = 77001").fetchone()),
                dict(conn.execute("SELECT * FROM horses WHERE horse_id = 77002").fetchone()),
                dict(conn.execute("SELECT * FROM horses WHERE horse_id = 77003").fetchone()),
            ]

            promoted_3 = self.lifecycle._manage_broodmare_roster(conn, current_year=3, retired_horses=retired_horses_yr3)
            self.assertEqual(promoted_3, 2, "オープン牝馬2頭のみ昇格すること")

            # 繁殖牝馬数が厳密に600頭維持されていること
            cnt_3 = conn.execute("SELECT COUNT(*) FROM dams WHERE is_active = 1").fetchone()[0]
            self.assertEqual(cnt_3, 600, "3年目終了時も繁殖牝馬数は厳密に600頭であること")

            # 未勝利牝馬は繁殖牝馬になっていないこと
            h_c = conn.execute("SELECT is_dam FROM horses WHERE horse_id = 77003").fetchone()
            self.assertEqual(h_c["is_dam"], 0)

            # 0歳・1歳馬が繁殖牝馬になっていないこと
            zero_one_dams = conn.execute("SELECT COUNT(*) FROM dams d JOIN horses h ON d.horse_id = h.horse_id WHERE h.age <= 1").fetchone()[0]
            self.assertEqual(zero_one_dams, 0, "0歳・1歳馬が繁殖牝馬になっていないこと")

if __name__ == "__main__":
    unittest.main()
