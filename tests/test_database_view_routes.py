"""
主要レース路線（MAJOR_ROUTES）の単体テスト
- 3歳牡馬3冠（皐月賞、日本ダービー、菊花賞）の勝ち馬表示
- 3歳牝馬3冠（桜花賞、オークス、秋華賞）の勝ち馬表示
- 表記揺れ（東京優駿/日本ダービー、優駿牝馬/オークス等）の吸収確認
- 3冠・2冠タイトルの判定確認
"""

import unittest
import sys
from PyQt6.QtWidgets import QApplication
from src.db.database import Database
from src.gui.views.database_view import DatabaseView, MAJOR_ROUTES

from src.generators.initializer import DatabaseInitializer

app = QApplication.instance() or QApplication(sys.argv)


class TestDatabaseViewMajorRoutes(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        init = DatabaseInitializer(self.db)
        init.initialize_all()

        with self.db.session() as conn:
            horses = conn.execute("SELECT horse_id, name FROM horses WHERE age = 2 LIMIT 3").fetchall()
            self.h1_id, self.h1_name = horses[0]["horse_id"], horses[0]["name"]
            self.h2_id, self.h2_name = horses[1]["horse_id"], horses[1]["name"]
            self.h3_id, self.h3_name = horses[2]["horse_id"], horses[2]["name"]

            # 1年目(year=1)のレースIDを取得
            r_satsuki = conn.execute("SELECT race_id FROM races WHERE year=1 AND name='皐月賞'").fetchone()
            r_derby = conn.execute("SELECT race_id FROM races WHERE year=1 AND name='東京優駿（日本ダービー）'").fetchone()
            r_kikka = conn.execute("SELECT race_id FROM races WHERE year=1 AND name='菊花賞'").fetchone()

            r_ouka = conn.execute("SELECT race_id FROM races WHERE year=1 AND name='桜花賞'").fetchone()
            r_oaks = conn.execute("SELECT race_id FROM races WHERE year=1 AND name='優駿牝馬（オークス）'").fetchone()
            r_shuka = conn.execute("SELECT race_id FROM races WHERE year=1 AND name='秋華賞'").fetchone()

            # 短距離2冠用レース (year=2 で古馬G1を追加登録)
            conn.execute("INSERT INTO races (race_id, year, month, week, track_id, name, grade, surface, distance, age_restriction, sex_restriction) VALUES (90301, 2, 3, 12, 'CHUKYO', '高松宮記念', 'G1', 'turf', 1200, '4yo_up', 'mixed')")
            conn.execute("INSERT INTO races (race_id, year, month, week, track_id, name, grade, surface, distance, age_restriction, sex_restriction) VALUES (90302, 2, 9, 36, 'NAKAYAMA', 'スプリンターズS', 'G1', 'turf', 1200, '3yo_up', 'mixed')")

            # 勝ち馬結果登録
            # h1: 牡馬3冠制覇 (year=1)
            conn.execute("INSERT INTO results (race_id, horse_id, finish_position, finish_time) VALUES (?, ?, 1, 120.0)", (r_satsuki["race_id"], self.h1_id))
            conn.execute("INSERT INTO results (race_id, horse_id, finish_position, finish_time) VALUES (?, ?, 1, 144.0)", (r_derby["race_id"], self.h1_id))
            conn.execute("INSERT INTO results (race_id, horse_id, finish_position, finish_time) VALUES (?, ?, 1, 180.0)", (r_kikka["race_id"], self.h1_id))

            # h2: 牝馬3冠制覇 (year=1)
            conn.execute("INSERT INTO results (race_id, horse_id, finish_position, finish_time) VALUES (?, ?, 1, 95.0)", (r_ouka["race_id"], self.h2_id))
            conn.execute("INSERT INTO results (race_id, horse_id, finish_position, finish_time) VALUES (?, ?, 1, 144.0)", (r_oaks["race_id"], self.h2_id))
            conn.execute("INSERT INTO results (race_id, horse_id, finish_position, finish_time) VALUES (?, ?, 1, 120.0)", (r_shuka["race_id"], self.h2_id))

            # h3: 短距離2冠 (year=2)
            conn.execute("INSERT INTO results (race_id, horse_id, finish_position, finish_time) VALUES (90301, ?, 1, 68.0)", (self.h3_id,))
            conn.execute("INSERT INTO results (race_id, horse_id, finish_position, finish_time) VALUES (90302, ?, 1, 67.5)", (self.h3_id,))

    def test_classic_colt_derby_display(self):
        """3歳牡馬3冠で「東京優駿（日本ダービー）」の勝ち馬が表示されることを検証"""
        view = DatabaseView(self.db)
        view.combo_route_select.setCurrentIndex(0)  # classic_colt
        view.refresh_major_routes()

        # テーブルのヘッダー確認
        headers = [view.table_major_routes.horizontalHeaderItem(i).text() for i in range(view.table_major_routes.columnCount())]
        self.assertEqual(headers[0], "年度")
        self.assertEqual(headers[1], "第1冠: 皐月賞")
        self.assertEqual(headers[2], "第2冠: 東京優駿（日本ダービー）")
        self.assertEqual(headers[3], "第3冠: 菊花賞")
        self.assertEqual(headers[4], "制覇タイトル")

        # 1年目の勝ち馬セル確認
        self.assertEqual(view.table_major_routes.item(0, 0).text(), "1年")
        self.assertEqual(view.table_major_routes.item(0, 1).text(), f"🏆 {self.h1_name}")
        self.assertEqual(view.table_major_routes.item(0, 2).text(), f"🏆 {self.h1_name}")  # 東京優駿（日本ダービー）
        self.assertEqual(view.table_major_routes.item(0, 3).text(), f"🏆 {self.h1_name}")
        self.assertIn("3冠達成", view.table_major_routes.item(0, 4).text())

    def test_triple_tiara_oaks_display(self):
        """3歳牝馬3冠で「優駿牝馬（オークス）」の勝ち馬が表示されることを検証"""
        view = DatabaseView(self.db)
        # triple_tiara を選択
        idx = [i for i, r in enumerate(MAJOR_ROUTES) if r["id"] == "triple_tiara"][0]
        view.combo_route_select.setCurrentIndex(idx)
        view.refresh_major_routes()

        # テーブルのヘッダー確認
        headers = [view.table_major_routes.horizontalHeaderItem(i).text() for i in range(view.table_major_routes.columnCount())]
        self.assertEqual(headers[1], "第1冠: 桜花賞")
        self.assertEqual(headers[2], "第2冠: 優駿牝馬（オークス）")
        self.assertEqual(headers[3], "第3冠: 秋華賞")

        # 1年目の勝ち馬セル確認
        self.assertEqual(view.table_major_routes.item(0, 1).text(), f"🏆 {self.h2_name}")
        self.assertEqual(view.table_major_routes.item(0, 2).text(), f"🏆 {self.h2_name}")  # 優駿牝馬（オークス）
        self.assertEqual(view.table_major_routes.item(0, 3).text(), f"🏆 {self.h2_name}")
        self.assertIn("3冠達成", view.table_major_routes.item(0, 4).text())

    def test_sprint_route_display(self):
        """古馬短距離2冠で「スプリンターズS」の勝ち馬が表示されることを検証"""
        view = DatabaseView(self.db)
        idx = [i for i, r in enumerate(MAJOR_ROUTES) if r["id"] == "sprint"][0]
        view.combo_route_select.setCurrentIndex(idx)
        view.refresh_major_routes()

        headers = [view.table_major_routes.horizontalHeaderItem(i).text() for i in range(view.table_major_routes.columnCount())]
        self.assertEqual(headers[1], "春: 高松宮記念")
        self.assertEqual(headers[2], "秋: スプリンターズS")

        # 2年目の短距離勝ち馬確認 (row 1)
        self.assertEqual(view.table_major_routes.item(1, 1).text(), f"🏆 {self.h3_name}")
        self.assertEqual(view.table_major_routes.item(1, 2).text(), f"🏆 {self.h3_name}")
        self.assertIn("2冠達成", view.table_major_routes.item(1, 3).text())

    def test_alias_compatibility(self):
        """レース名が『東京優駿』や『優駿牝馬』として登録されていた場合のエイリアス互換性テスト"""
        # 別年(2026年)に別名で登録
        with self.db.session() as conn:
            conn.execute("INSERT INTO races (race_id, year, month, week, track_id, name, grade, surface, distance, age_restriction, sex_restriction) VALUES (90104, 2026, 5, 21, 'TOKYO', '東京優駿', 'G1', 'turf', 2400, '3yo', 'colt_horse')")
            conn.execute("INSERT INTO results (race_id, horse_id, finish_position, finish_time) VALUES (90104, ?, 1, 144.0)", (self.h1_id,))

        view = DatabaseView(self.db)
        view.combo_route_select.setCurrentIndex(0)
        view.refresh_major_routes()

        # 2026年の日本ダービー（東京優駿）にh1が表示されること
        row_count = view.table_major_routes.rowCount()
        last_row = row_count - 1
        self.assertEqual(view.table_major_routes.item(last_row, 0).text(), "2026年")
        self.assertEqual(view.table_major_routes.item(last_row, 2).text(), f"🏆 {self.h1_name}")


if __name__ == "__main__":
    unittest.main()
