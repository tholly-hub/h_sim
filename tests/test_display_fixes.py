import unittest
import sys
from PyQt6.QtWidgets import QApplication

from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.gui.views.dashboard_view import DashboardView
from src.gui.views.race_dialogs import RaceResultDialog
from src.gui.views.race_replay_view import RaceReplayView

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class TestDisplayFixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Database(":memory:")
        init_gen = DatabaseInitializer(cls.db)
        init_gen.initialize_all()

        # 21週以降の開催レースを1件取得（初年度は2歳戦が21週〜開始）
        with cls.db.session() as conn:
            cls.race_row = conn.execute("SELECT * FROM races WHERE year = 1 AND week >= 21 ORDER BY week ASC LIMIT 1").fetchone()
            from src.race.calendar import CalendarController
            cal = CalendarController(cls.db)
            cal.run_week(cls.race_row["year"], cls.race_row["week"])

    def test_dashboard_entry_table_horse_name_width(self):
        """ダッシュボード出馬表の馬名列がStretchで十分な幅が確保されていること"""
        dash = DashboardView(self.db)
        dash.resize(1200, 800)
        # 行選択して出走表をロード
        dash.table_races.selectRow(0)
        dash._on_race_cell_clicked(0, 1)

        # 出馬表テーブル
        table = dash.table_entry
        self.assertGreater(table.rowCount(), 0)

        # 馬名列（インデックス2）の幅が180px以上確保されていること
        name_width = table.columnWidth(2)
        print(f"ダッシュボード出馬表 馬名列幅: {name_width}px")
        self.assertGreaterEqual(name_width, 180)

        # オッズ表記が「○.○倍 (○人気)」形式になっていること
        odds_item = table.item(0, 7)
        self.assertIsNotNone(odds_item)
        print(f"ダッシュボード出馬表 オッズ表記: {odds_item.text()}")
        self.assertIn("人気", odds_item.text())

    def test_race_result_dialog_popularity_and_name_width(self):
        """レース結果ダイアログでオッズの後ろに何番人気かが表示され、馬名列が十分広いこと"""
        dlg = RaceResultDialog(self.db, self.race_row["race_id"])
        dlg.resize(980, 520)

        table = dlg.table
        self.assertGreater(table.rowCount(), 0)

        # 馬名列（インデックス2）の幅
        name_width = table.columnWidth(2)
        print(f"レース結果ダイアログ 馬名列幅: {name_width}px")
        self.assertGreaterEqual(name_width, 180)

        # オッズ/人気列（インデックス5）の表記
        odds_item = table.item(0, 5)
        self.assertIsNotNone(odds_item)
        odds_text = odds_item.text()
        print(f"レース結果ダイアログ オッズ/人気表記: {odds_text}")
        self.assertIn("人気", odds_text)
        self.assertTrue("倍 (" in odds_text or "(" in odds_text)

    def test_race_replay_view_all_horses_and_odds_format(self):
        """レース画面で全頭の着順が表示され、オッズの後ろに人気順が表示されること"""
        replay = RaceReplayView(self.db)
        replay.resize(1200, 800)
        replay.load_race_by_id(self.race_row["race_id"])

        table = replay.table_results
        # 全頭（8頭）が表示されていること
        print(f"レース画面結果テーブル 行数 (全頭): {table.rowCount()}頭")
        self.assertEqual(table.rowCount(), 8)

        # 馬名列（インデックス2）の幅
        name_width = table.columnWidth(2)
        print(f"レース画面結果テーブル 馬名列幅: {name_width}px")
        self.assertGreaterEqual(name_width, 180)

        # オッズ/人気（インデックス3）の表記
        odds_item = table.item(0, 3)
        self.assertIsNotNone(odds_item)
        odds_text = odds_item.text()
        print(f"レース画面結果テーブル オッズ/人気表記: {odds_text}")
        self.assertIn("人気", odds_text)

        # 再生終了時の自動表示とスプリッターサイズ
        replay._on_playback_finished()
        self.assertFalse(replay.result_widget.isHidden())
        self.assertEqual(replay.btn_toggle_result.text(), "📊 結果を隠す")


if __name__ == "__main__":
    unittest.main()
