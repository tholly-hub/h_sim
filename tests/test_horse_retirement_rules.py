"""
競走馬の引退ルール改定に関する単体テスト
- 3歳末: 未勝利以外の足切りなし（3歳9月4週の未勝利引退のみ）
- 4歳末: 条件馬は引退。オープン馬は成績推移・成長曲線に応じて引退
- 5歳末: 全ての牝馬は引退。牡馬条件馬は引退、牡馬オープン馬は成績推移・成長曲線に応じて引退
- 6歳末: 成績推移・成長曲線に応じて引退判断
- 7歳末: 全ての競走馬が100%引退
"""

import unittest
from src.core.lifecycle import LifecycleEngine
from src.db.database import Database
from src.generators.initializer import DatabaseInitializer


class TestHorseRetirementRules(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        init = DatabaseInitializer(self.db)
        init.initialize_all()
        self.lifecycle = LifecycleEngine(self.db)

    def test_retirement_age_and_class_rules(self):
        """改定後の競走馬引退ルールの動作検証"""
        with self.db.session() as conn:
            # 既存の現役馬を非アクティブにしてテスト用馬を登録
            conn.execute("UPDATE horses SET is_active = 0")

            # 1. 3歳馬（加齢前age=3 -> advance_yearでage=4）: 1勝馬
            conn.execute("""
                INSERT INTO horses (
                    horse_id, name, sex, birth_year, age, is_active, career_wins, condition_prize_money,
                    g1_wins, g2_wins, g3_wins, peak_age, current_ability_rate, growth_type,
                    breeder_id, owner_id, trainer_id, speed, stamina, acceleration,
                    mstn_type, temperament, durability, running_style, maternal_vitality
                ) VALUES (
                    80001, 'サンサイテスト', 'colt', 1, 3, 1, 1, 4000000, 0, 0, 0, 4.5, 0.90, 'normal',
                    1, 1, 1, 60.0, 60.0, 60.0,
                    'C/T', 50.0, 50.0, 'leading', 50.0
                )
            """)

            # 2. 4歳条件馬（加齢前age=4 -> advance_yearでage=5）: 2勝・収得賞金800万（非オープン）
            conn.execute("""
                INSERT INTO horses (
                    horse_id, name, sex, birth_year, age, is_active, career_wins, condition_prize_money,
                    g1_wins, g2_wins, g3_wins, peak_age, current_ability_rate, growth_type,
                    breeder_id, owner_id, trainer_id, speed, stamina, acceleration,
                    mstn_type, temperament, durability, running_style, maternal_vitality
                ) VALUES (
                    80002, 'ヨンサイジョウケン', 'colt', 1, 4, 1, 2, 8000000, 0, 0, 0, 4.5, 0.90, 'normal',
                    1, 1, 1, 60.0, 60.0, 60.0,
                    'C/T', 50.0, 50.0, 'leading', 50.0
                )
            """)

            # 3. 5歳牝馬オープン馬（加齢前age=5 -> advance_yearでage=6）: G1勝ち
            conn.execute("""
                INSERT INTO horses (
                    horse_id, name, sex, birth_year, age, is_active, career_wins, condition_prize_money,
                    g1_wins, g2_wins, g3_wins, peak_age, current_ability_rate, growth_type,
                    breeder_id, owner_id, trainer_id, speed, stamina, acceleration,
                    mstn_type, temperament, durability, running_style, maternal_vitality
                ) VALUES (
                    80003, 'ゴサイヒンバオープン', 'filly', 1, 5, 1, 5, 30000000, 1, 0, 0, 4.5, 0.95, 'normal',
                    1, 1, 1, 70.0, 70.0, 70.0,
                    'C/T', 50.0, 50.0, 'leading', 50.0
                )
            """)

            # 4. 7歳馬（加齢前age=7 -> advance_yearでage=8）: G1複数勝利の超名馬
            conn.execute("""
                INSERT INTO horses (
                    horse_id, name, sex, birth_year, age, is_active, career_wins, condition_prize_money,
                    g1_wins, g2_wins, g3_wins, peak_age, current_ability_rate, growth_type,
                    breeder_id, owner_id, trainer_id, speed, stamina, acceleration,
                    mstn_type, temperament, durability, running_style, maternal_vitality
                ) VALUES (
                    80004, 'ナナサイメイバ', 'horse', 1, 7, 1, 10, 80000000, 3, 2, 0, 5.0, 0.90, 'late',
                    1, 1, 1, 80.0, 80.0, 80.0,
                    'C/T', 50.0, 50.0, 'leading', 50.0
                )
            """)

        # 年進行を実行
        self.lifecycle.advance_year(current_year=1)

        with self.db.session() as conn:
            h1 = conn.execute("SELECT is_active, age FROM horses WHERE horse_id = 80001").fetchone()
            h2 = conn.execute("SELECT is_active, age FROM horses WHERE horse_id = 80002").fetchone()
            h3 = conn.execute("SELECT is_active, age FROM horses WHERE horse_id = 80003").fetchone()
            h4 = conn.execute("SELECT is_active, age FROM horses WHERE horse_id = 80004").fetchone()

            # 3歳馬（加齢後4歳）: 1勝馬でも年末引退せず現役継続
            self.assertEqual(h1["is_active"], 1)
            self.assertEqual(h1["age"], 4)

            # 4歳条件馬（加齢後5歳）: 100% 引退
            self.assertEqual(h2["is_active"], 0)

            # 5歳牝馬（加齢後6歳）: オープン馬であっても100% 引退
            self.assertEqual(h3["is_active"], 0)

            # 7歳馬（加齢後8歳）: 100% 引退
            self.assertEqual(h4["is_active"], 0)

    def test_young_unraced_horses_not_promoted_to_broodmare(self):
        """2歳以下の未出走牝馬（当歳・1歳幼駒・2歳新馬）が繁殖牝馬に昇格しないことの検証"""
        with self.db.session() as conn:
            # 繁殖牝馬を大量に引退させて目標600頭に不足する状況を作る
            conn.execute("UPDATE dams SET is_active = 0")
            conn.execute("UPDATE horses SET is_dam = 0 WHERE is_dam = 1")

            # 高能力の2歳未出走牝馬を挿入
            conn.execute("""
                INSERT INTO horses (
                    horse_id, name, sex, birth_year, age, is_active, career_starts, career_wins,
                    speed, stamina, acceleration, temperament, durability, maternal_vitality, mstn_type, growth_type,
                    peak_age, running_style, breeder_id, owner_id
                ) VALUES (
                    90001, 'テンサイニサイヒンバ', 'filly', 1, 1, 0, 0, 0,
                    99.0, 99.0, 99.0, 70.0, 70.0, 99.0, 'C/T', 'normal',
                    4.5, 'leading', 1, 1
                )
            """)

        # 年進行（加齢と繁殖牝馬補充）を実行
        self.lifecycle.advance_year(current_year=1)

        with self.db.session() as conn:
            h = conn.execute("SELECT is_dam, is_active, age FROM horses WHERE horse_id = 90001").fetchone()
            d = conn.execute("SELECT is_active FROM dams WHERE horse_id = 90001").fetchone()

            # 2歳以下の幼駒は繁殖牝馬になってはならない
            self.assertEqual(h["is_dam"], 0, "2歳以下の未出走幼駒が繁殖牝馬(is_dam=1)になってはなりません")
            self.assertIsNone(d, "2歳以下の未出走幼駒がdamsテーブルに登録されてはなりません")


if __name__ == "__main__":
    unittest.main()

