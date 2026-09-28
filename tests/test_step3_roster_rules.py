"""
Step 3 単体テスト: 種牡馬・繁殖牝馬入れ替えルールおよび0歳・1歳馬保護の検証
"""

import unittest
from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.core.lifecycle import LifecycleEngine
from src.core.breeding import BreedingEngine


class TestStep3RosterRules(unittest.TestCase):

    def setUp(self):
        self.db = Database(":memory:")
        self.initializer = DatabaseInitializer(self.db)
        self.initializer.initialize_all(force_recreate=True)
        self.lifecycle = LifecycleEngine(self.db)
        self.breeding = BreedingEngine(self.db)

    def test_no_roster_change_year1_and_year2(self):
        """1〜2年目は種牡馬・繁殖牝馬の入れ替えが行われないことの確認"""
        # 1年目年進行
        self.lifecycle.advance_year(current_year=1)
        with self.db.session() as conn:
            sire_cnt = conn.execute("SELECT COUNT(*) FROM sires WHERE is_active = 1").fetchone()[0]
            dam_cnt = conn.execute("SELECT COUNT(*) FROM dams WHERE is_active = 1").fetchone()[0]
            self.assertEqual(sire_cnt, 100, f"Expected 100 sires, got {sire_cnt}")
            self.assertEqual(dam_cnt, 600, f"Expected 600 dams, got {dam_cnt}")

        # 2年目年進行
        self.lifecycle.advance_year(current_year=2)
        with self.db.session() as conn:
            sire_cnt = conn.execute("SELECT COUNT(*) FROM sires WHERE is_active = 1").fetchone()[0]
            dam_cnt = conn.execute("SELECT COUNT(*) FROM dams WHERE is_active = 1").fetchone()[0]
            self.assertEqual(sire_cnt, 100, f"Expected 100 sires, got {sire_cnt}")
            self.assertEqual(dam_cnt, 600, f"Expected 600 dams, got {dam_cnt}")

    def test_no_unstarted_or_zero_age_in_roster(self):
        """0歳馬や未出走馬が種牡馬・繁殖牝馬に昇格しないことの確認"""
        with self.db.session() as conn:
            # テスト用に未出走の0歳牝馬・1歳牝馬をDBに用意
            conn.execute("""
                INSERT INTO horses (
                    name, sex, birth_year, age, breeder_id, owner_id, is_active,
                    career_starts, speed, stamina, acceleration, temperament, durability, maternal_vitality,
                    mstn_type, growth_type, peak_age, running_style, current_ability_rate
                ) VALUES (
                    'テストゼロサイ', 'filly', 3, 0, 1, 1, 0,
                    0, 80.0, 80.0, 80.0, 50.0, 50.0, 50.0,
                    'C/T', 'normal', 4.5, 'leading', 0.2
                )
            """)
            zero_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # 3年目の年進行（引退馬なし）
        self.lifecycle.advance_year(current_year=3)

        with self.db.session() as conn:
            # 0歳馬が繁殖牝馬になっていないことを検証
            is_dam = conn.execute("SELECT is_dam FROM horses WHERE horse_id = ?", (zero_id,)).fetchone()[0]
            self.assertEqual(is_dam, 0, "0-year-old unstarted horse must not become dam")

            # 全繁殖牝馬・種牡馬を検証: career_starts == 0 かつ age < 3 の馬がいないこと（初期配置の親馬を除く）
            new_dams_invalid = conn.execute("""
                SELECT h.horse_id, h.name, h.age, h.career_starts
                FROM dams d
                JOIN horses h ON d.horse_id = h.horse_id
                WHERE d.start_year >= 3 AND (h.career_starts = 0 OR h.age < 3)
            """).fetchall()
            self.assertEqual(len(new_dams_invalid), 0, f"Found invalid new dams: {new_dams_invalid}")

    def test_year3_open_mare_promotion_and_600_quota(self):
        """3年目終了時に引退オープン牝馬が昇格し、同数の最下位牝馬と入れ替わって600頭が維持されることの確認"""
        with self.db.session() as conn:
            # 3年目末に引退するオープン牝馬を登録（加齢判定前age=4、is_active=1）
            conn.execute("""
                INSERT INTO horses (
                    name, sex, birth_year, age, breeder_id, owner_id, is_active,
                    career_starts, career_wins, g1_wins, prize_money, speed, stamina, acceleration,
                    temperament, durability, maternal_vitality,
                    mstn_type, growth_type, peak_age, running_style, current_ability_rate
                ) VALUES (
                    'オープンヒンバテスト', 'mare', 1, 5, 1, 1, 1,
                    10, 5, 2, 200000000, 75.0, 75.0, 75.0,
                    50.0, 50.0, 50.0,
                    'C/T', 'normal', 4.5, 'leading', 1.0
                )
            """)
            open_mare_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # 3年目の年進行を実行
        self.lifecycle.advance_year(current_year=3)

        with self.db.session() as conn:
            # 600頭が維持されていること
            dam_cnt = conn.execute("SELECT COUNT(*) FROM dams WHERE is_active = 1").fetchone()[0]
            self.assertEqual(dam_cnt, 600, f"Broodmare count should remain 600, got {dam_cnt}")

            # 引退オープン牝馬が繁殖牝馬に昇格していること
            promoted = conn.execute("SELECT is_dam FROM horses WHERE horse_id = ?", (open_mare_id,)).fetchone()
            self.assertIsNotNone(promoted)
            self.assertEqual(promoted[0], 1, "Open class mare should be promoted to dam")

    def test_1yo_horses_never_retire(self):
        """競走馬から生まれた子が1歳時点で引退しないことの確認"""
        with self.db.session() as conn:
            # 1歳馬（初期生成の初子）のカウント
            c1 = conn.execute("SELECT COUNT(*) FROM horses WHERE age = 0").fetchone()[0]
            self.assertEqual(c1, 600)

        # 1年目終了（age 0 -> age 1）
        self.lifecycle.advance_year(current_year=1)

        with self.db.session() as conn:
            # 1歳馬が全頭健在（retired_year is null, is_active=0, is_dead=0）であることを確認
            active_or_young = conn.execute("SELECT COUNT(*) FROM horses WHERE age = 1 AND retired_year IS NULL").fetchone()[0]
            self.assertEqual(active_or_young, 600, f"Expected 600 1-year-old horses, found {active_or_young}")


if __name__ == "__main__":
    unittest.main()
