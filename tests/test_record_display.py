"""
レコード表示（タイム左側赤字R、掲示板レコード表示）のテスト
"""

import unittest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication
import sys

from src.gui.widgets.track_canvas import TrackCanvas
from src.gui.widgets.race_board_widget import RaceBoardWidget
from src.gui.widgets.html_delegate import HTMLDelegate

# QApplicationインスタンス作成
app = QApplication.instance() or QApplication(sys.argv)


class TestRecordDisplay(unittest.TestCase):
    """レコード表示機能のテスト"""

    def test_track_canvas_record_flag(self):
        """TrackCanvasがis_recordフラグを保持することを確認"""
        canvas = TrackCanvas()
        canvas.set_race_results({}, is_record=True)
        self.assertTrue(canvas.is_record_time)

        canvas.set_race_results({}, is_record=False)
        self.assertFalse(canvas.is_record_time)

    def test_race_board_widget_record_mark(self):
        """RaceBoardWidgetのレコードマーク表示・非表示を確認"""
        board = RaceBoardWidget()
        board.set_race_board_data(
            track_name="東京",
            race_number=11,
            surface_jp="芝",
            top5_horses=[],
            finish_time=93.4,
            is_record=True,
            is_confirmed=True,
        )
        self.assertFalse(board.lbl_record_mark.isHidden())
        self.assertEqual(board.lbl_record_mark.text(), "R")

        board.set_race_board_data(
            track_name="東京",
            race_number=11,
            surface_jp="芝",
            top5_horses=[],
            finish_time=94.0,
            is_record=False,
            is_confirmed=True,
        )
        self.assertTrue(board.lbl_record_mark.isHidden())

    def test_html_delegate_instantiation(self):
        """HTMLDelegateが正常に初期化できることを確認"""
        delegate = HTMLDelegate()
        self.assertIsNotNone(delegate)

    def test_check_is_course_record_logic(self):
        """check_is_course_recordの判定ロジック（初開催・レコード更新・不更新）を確認"""
        import sqlite3
        from src.race.track import check_is_course_record

        # インメモリDBでテスト
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE races (
                race_id INTEGER PRIMARY KEY,
                year INTEGER,
                week INTEGER,
                track_id TEXT,
                surface TEXT,
                distance INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE results (
                race_id INTEGER,
                finish_position INTEGER,
                finish_time REAL
            )
        """)

        # 1. 初開催レース（過去データなし） -> True (初レコード)
        is_rec1 = check_is_course_record(
            conn, track_id="TOKYO", surface="turf", distance=2400,
            finish_time=144.5, year=1, week=1, race_id=1
        )
        self.assertTrue(is_rec1)

        # レース1の結果を登録 (勝ちタイム 144.5)
        conn.execute("INSERT INTO races VALUES (1, 1, 1, 'TOKYO', 'turf', 2400)")
        conn.execute("INSERT INTO results VALUES (1, 1, 144.5)")

        # 2. 次のレース（タイム 145.0 で遅い） -> False
        is_rec2 = check_is_course_record(
            conn, track_id="TOKYO", surface="turf", distance=2400,
            finish_time=145.0, year=1, week=2, race_id=2
        )
        self.assertFalse(is_rec2)

        # 3. 新レコード更新（タイム 143.8 で速い） -> True
        is_rec3 = check_is_course_record(
            conn, track_id="TOKYO", surface="turf", distance=2400,
            finish_time=143.8, year=1, week=3, race_id=3
        )
        self.assertTrue(is_rec3)

        # 4. 表記ゆれ対応（'芝' や 大文字） -> 正常に判定
        is_rec4 = check_is_course_record(
            conn, track_id="TOKYO", surface="芝", distance=2400,
            finish_time=143.8, year=1, week=3, race_id=3
        )
        self.assertTrue(is_rec4)

        conn.close()

    def test_horse_detail_dialog_record_display(self):
        """HorseDetailDialogの出走全レース履歴テーブルでレコード勝ちにR表示されることを確認"""
        from src.db.database import Database
        from src.generators.initializer import DatabaseInitializer
        from src.models.horse import Horse, GenotypeMSTN, GrowthType, RunningStyle
        from src.gui.views.horse_detail_dialog import HorseDetailDialog

        db = Database(":memory:")
        init_gen = DatabaseInitializer(db)
        init_gen.initialize_all()


        with db.session() as conn:
            h_row = conn.execute("SELECT horse_id FROM horses WHERE is_active = 1 LIMIT 1").fetchone()
            target_hid = h_row["horse_id"]

            # 同じコース条件のレースを2つ取得
            cond_row = conn.execute("""
                SELECT track_id, surface, distance, COUNT(*) as cnt 
                FROM races 
                GROUP BY track_id, surface, distance 
                HAVING cnt >= 2 
                LIMIT 1
            """).fetchone()
            r_rows = conn.execute("""
                SELECT race_id FROM races 
                WHERE track_id = ? AND surface = ? AND distance = ? 
                ORDER BY year, week, race_id LIMIT 2
            """, (cond_row["track_id"], cond_row["surface"], cond_row["distance"])).fetchall()
            r1_id = r_rows[0]["race_id"]
            r2_id = r_rows[1]["race_id"]


            # 1走目 (早い週のレース): 初開催レコード勝ち
            conn.execute("""
                INSERT INTO results (race_id, horse_id, finish_position, finish_time, last_3f, prize_awarded)
                VALUES (?, ?, 1, 144.5, 34.0, 7000000)
            """, (r1_id, target_hid))

            # 2走目 (遅い週のレース): 通常勝ち（レコードより遅い）
            conn.execute("""
                INSERT INTO results (race_id, horse_id, finish_position, finish_time, last_3f, prize_awarded)
                VALUES (?, ?, 1, 145.2, 34.5, 10000000)
            """, (r2_id, target_hid))

        dlg = HorseDetailDialog(db=db, horse_id=target_hid)

        # 行数は2行
        self.assertEqual(dlg.table_history.rowCount(), 2)

        # 降順なので 0行目が2走目(遅い週)、1行目が1走目(早い週)
        item_top = dlg.table_history.item(0, 9)  # 2走目のタイム
        item_bottom = dlg.table_history.item(1, 9)  # 1走目のタイム

        # 1走目（144.5秒）は初レコード勝ちのため赤字「R」を含む
        self.assertIn(">R<", item_bottom.text())
        self.assertIn("2:24.5", item_bottom.text())

        # 2走目（145.2秒）はレコード更新していないため「R」を含まない
        self.assertNotIn(">R<", item_top.text())
        self.assertIn("2:25.2", item_top.text())



if __name__ == "__main__":
    unittest.main()


