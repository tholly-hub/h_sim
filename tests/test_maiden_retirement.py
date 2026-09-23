"""
未出走2歳馬および3歳未勝利馬の引退ルール検証テスト
ルール:
- 2歳馬は年越し時（2年目1月）に引退せず、3歳現役馬として継続する。
- 3歳馬は9月4週（第36週）終了時点で未勝利（0勝・未出走含む）だった馬が引退（retired_year記録）となる。
- 2歳馬は9月4週終了時にも引退しない。
"""

import unittest
from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.race.calendar import CalendarController
from src.core.lifecycle import LifecycleEngine


class TestMaidenAnd2yoRetirement(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.init = DatabaseInitializer(self.db)
        self.init.initialize_all()
        self.cal = CalendarController(self.db)
        self.lifecycle = LifecycleEngine(self.db)

    def test_2yo_not_retired_on_new_year(self):
        """1年目終了・年進行（2年目1月）で未出走2歳馬が引退せず3歳現役馬として存続することを検証"""
        # 1年目を進行 (48週)
        for w in range(1, 49):
            self.cal.run_week(1, w)

        # 年進行実行
        self.lifecycle.advance_year(1)

        with self.db.session() as conn:
            # 2年目1月時点での3歳馬（元2歳馬）の確認
            three_yo_active = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE age = 3 AND is_active = 1"
            ).fetchone()[0]
            three_yo_retired = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE age = 3 AND is_active = 0"
            ).fetchone()[0]

            # 3歳馬は全員現役であること（引退馬が0頭）
            self.assertEqual(three_yo_retired, 0, "2年目1月時点で3歳馬（元2歳馬）が引退していてはいけない")
            self.assertGreater(three_yo_active, 0, "2年目1月時点で3歳現役馬が存在すること")

            # 1年目に引退した競走馬一覧（retired_year = 1）に3歳馬や2歳馬が含まれていないこと
            retire_year1_young = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE retired_year = 1 AND age <= 3"
            ).fetchone()[0]
            self.assertEqual(retire_year1_young, 0, "1年目の引退馬一覧に2歳馬や3歳馬が含まれていてはいけない")

            # 新2歳馬（元1歳馬）が入厩して現役になっていること
            two_yo_active = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE age = 2 AND is_active = 1"
            ).fetchone()[0]
            self.assertGreater(two_yo_active, 0, "2年目の新2歳馬が入厩して現役になっていること")

    def test_3yo_maiden_retired_at_week_36(self):
        """2年目第36週（9月4週）で3歳未勝利馬が引退し、2歳馬は引退しないことを検証"""
        # 1年目進行 -> 年進行
        for w in range(1, 49):
            self.cal.run_week(1, w)
        self.lifecycle.advance_year(1)

        # 2年目 第1週〜第35週を進行
        for w in range(1, 36):
            self.cal.run_week(2, w)

        with self.db.session() as conn:
            # 第35週終了時点では3歳未勝利馬もまだ引退していないこと
            maidens_before_w36 = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE age = 3 AND career_wins = 0 AND is_active = 1"
            ).fetchone()[0]
            self.assertGreater(maidens_before_w36, 0, "第36週前は3歳未勝利馬も現役であること")

        # 2年目 第36週（9月4週）を実行
        self.cal.run_week(2, 36)

        with self.db.session() as conn:
            # 第36週終了後、3歳かつ未勝利の馬は全員 is_active = 0 かつ retired_year = 2
            active_3yo_maidens = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE age = 3 AND career_wins = 0 AND is_active = 1"
            ).fetchone()[0]
            self.assertEqual(active_3yo_maidens, 0, "第36週終了後、3歳未勝利馬は現役であってはならない（全員引退）")

            retired_3yo_maidens = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE age = 3 AND career_wins = 0 AND is_active = 0 AND retired_year = 2"
            ).fetchone()[0]
            self.assertGreater(retired_3yo_maidens, 0, "3歳未勝利馬に retired_year = 2 が記録されていること")

            # 3歳の勝利馬（1勝以上）は現役を維持していること
            active_3yo_winners = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE age = 3 AND career_wins > 0 AND is_active = 1"
            ).fetchone()[0]
            self.assertGreater(active_3yo_winners, 0, "3歳の勝ち馬は第36週以降も現役であること")

            # 2歳馬は第36週で未勝利であっても引退しないこと
            retired_2yo = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE age = 2 AND is_active = 0"
            ).fetchone()[0]
            self.assertEqual(retired_2yo, 0, "2歳馬は第36週で引退してはならない")

            # 3歳未勝利引退牝馬が繁殖牝馬（is_dam = 1）になっていないこと（0勝のため繁殖入り不可）
            maidens_promoted_to_dam = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE age = 3 AND career_wins = 0 AND is_dam = 1"
            ).fetchone()[0]
            self.assertEqual(maidens_promoted_to_dam, 0, "0勝の未勝利牝馬が繁殖牝馬になってはならない")

    def test_dam_promotion_requires_at_least_one_win(self):
        """現役牝馬が引退時に繁殖牝馬になる条件は1勝以上であり、0勝牝馬は繁殖牝馬にならないことを検証"""
        with self.db.session() as conn:
            # 1勝の牝馬を作成
            # オープン馬（4勝・重賞勝ち）の牝馬を作成
            c1 = conn.execute("""
                INSERT INTO horses (
                    name, sex, birth_year, age, breeder_id, owner_id, is_active,
                    mstn_type, speed, stamina, acceleration, temperament, durability, maternal_vitality,
                    growth_type, peak_age, current_ability_rate, running_style,
                    prize_money, condition_prize_money, career_starts, career_wins, g3_wins
                ) VALUES (
                    'テストオープンヒンバ', 'filly', 1, 5, 1, 1, 1,
                    'C/T', 70.0, 70.0, 70.0, 50.0, 50.0, 50.0,
                    'normal', 4.0, 0.60, 'leading',
                    50000000, 30000000, 10, 4, 1
                )
            """)
            h_win_id = c1.lastrowid

            # 0勝の牝馬を作成
            c2 = conn.execute("""
                INSERT INTO horses (
                    name, sex, birth_year, age, breeder_id, owner_id, is_active,
                    mstn_type, speed, stamina, acceleration, temperament, durability, maternal_vitality,
                    growth_type, peak_age, current_ability_rate, running_style,
                    prize_money, condition_prize_money, career_starts, career_wins
                ) VALUES (
                    'テストミショウリヒンバ', 'filly', 1, 4, 1, 1, 1,
                    'C/T', 60.0, 60.0, 60.0, 50.0, 50.0, 50.0,
                    'normal', 4.0, 0.60, 'leading',
                    2000000, 0, 5, 0
                )
            """)
            h_maiden_id = c2.lastrowid

        # 年進行で引退判定
        self.lifecycle.advance_year(1)

        with self.db.session() as conn:
            win_horse = conn.execute("SELECT is_dam, is_active FROM horses WHERE horse_id = ?", (h_win_id,)).fetchone()
            maiden_horse = conn.execute("SELECT is_dam, is_active FROM horses WHERE horse_id = ?", (h_maiden_id,)).fetchone()

            # 0勝馬が引退した場合、is_dam は 0 であること
            if maiden_horse["is_active"] == 0:
                self.assertEqual(maiden_horse["is_dam"], 0, "0勝牝馬は引退しても繁殖牝馬になってはならない")

            # オープン牝馬が引退した場合、is_dam は 1 であること
            if win_horse["is_active"] == 0:
                self.assertEqual(win_horse["is_dam"], 1, "オープン牝馬は引退時に繁殖牝馬確定となること")
                dam_entry = conn.execute("SELECT * FROM dams WHERE horse_id = ?", (h_win_id,)).fetchone()
                self.assertIsNotNone(dam_entry, "damsテーブルに登録されていること")


if __name__ == "__main__":
    unittest.main()
