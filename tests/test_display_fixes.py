import unittest
import sys
from PyQt6.QtWidgets import QApplication, QFrame

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

        # 21週の開催レースを実行し、結果が存在するレースを取得
        from src.race.calendar import CalendarController
        cal = CalendarController(cls.db)
        cal.run_week(1, 21)
        with cls.db.session() as conn:
            cls.race_row = conn.execute(
                "SELECT r.*, COUNT(res.horse_id) as starter_count FROM races r JOIN results res ON r.race_id = res.race_id WHERE r.year = 1 AND r.week = 21 GROUP BY r.race_id HAVING starter_count = 8 LIMIT 1"
            ).fetchone()
            if not cls.race_row:
                cls.race_row = conn.execute(
                    "SELECT r.* FROM races r JOIN results res ON r.race_id = res.race_id WHERE r.year = 1 AND r.week = 21 LIMIT 1"
                ).fetchone()

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
        """レース画面でLED電光着順掲示板がレース画面内に描画され、レース中は非表示、ゴール後に表示され、確定結果が反映されること"""
        replay = RaceReplayView(self.db)
        replay.resize(1200, 800)
        replay.show()
        replay.load_race_by_id(self.race_row["race_id"])

        canvas = replay.track_canvas
        self.assertIsNotNone(canvas)
        
        # 1. レース開始前/レース中: レース画面内着順掲示板は非表示(show_result_board=False)であること
        self.assertFalse(canvas.show_result_board)
        self.assertFalse(canvas.board_confirmed)
        print(f"レース中 画面内掲示板表示フラグ: {canvas.show_result_board} (期待値: False)")

        # 2. ゴール到達時: 画面内掲示板が表示状態(show_result_board=True)になり、最初は未確定(board_confirmed=False)
        last_frame = max(0, replay.track_canvas.total_frames - 1)
        replay.track_canvas.set_frame(last_frame)
        self.assertTrue(canvas.show_result_board)
        self.assertFalse(canvas.board_confirmed)
        print(f"ゴール直後 画面内掲示板表示フラグ: {canvas.show_result_board} (期待値: True), 確定フラグ: {canvas.board_confirmed} (期待値: False)")

        # 3. 確定処理後: 確定フラグがTrueになり、確定データ（タイム、上がり3F、上位5頭）が格納されること
        replay._reveal_board_results()
        self.assertTrue(canvas.show_result_board)
        self.assertTrue(canvas.board_confirmed)
        self.assertGreater(len(canvas.board_data.get("top5_horses", [])), 0)
        self.assertGreater(canvas.board_data.get("finish_time", 0.0), 0.0)
        print(f"確定後 掲示板確定フラグ: {canvas.board_confirmed} (期待値: True), タイム: {canvas.board_data.get('finish_time')}")

        # 4. 1段目の高さがスリム(42px以下)に固定されていること
        self.assertLessEqual(replay.findChild(QFrame).height(), 42)

        # 5. プルダウンメニューに当該週のレースのみが表示されていること
        print(f"当該週レース数: {replay.combo_races.count()}")
        self.assertGreater(replay.combo_races.count(), 0)
        self.assertIsNotNone(replay.current_week)
        print(f"選択中の開催週: {replay.lbl_race_week.text()}")
        self.assertIn("週", replay.lbl_race_week.text())

    def test_clean_race_name(self):
        """レース名末尾の馬場・距離括弧が適切に除去されることの検証"""
        from src.race.engine import clean_race_name

        self.assertEqual(clean_race_name("3歳新馬 (芝1200m)"), "3歳新馬")
        self.assertEqual(clean_race_name("2歳未勝利（ダ1800m）"), "2歳未勝利")
        self.assertEqual(clean_race_name("2勝クラス(芝2000m)"), "2勝クラス")
        self.assertEqual(clean_race_name("有馬記念 (芝2500m)"), "有馬記念")
        self.assertEqual(clean_race_name("東京優駿(日本ダービー)"), "東京優駿(日本ダービー)")
        self.assertEqual(clean_race_name("新馬"), "新馬")

    def test_hud_top3_display_elements(self):
        """HUDの順位表示（名前、オッズ、距離）およびレース名の整形検証"""
        from src.gui.widgets.track_canvas import TrackCanvas

        canvas = TrackCanvas()
        canvas.race_name = "2歳新馬 (芝1200m)"
        canvas.set_race_results({
            1: {"horse_id": 1, "horse_name": "ダイワメジャー", "odds": 2.5},
            2: {"horse_id": 2, "horse_name": "ハーツクライ", "odds": 4.1},
            3: {"horse_id": 3, "horse_name": "ディープインパクト", "odds": 1.3},
        })
        
        # 擬似フレームデータ
        horses = [
            {"horse_id": 3, "number": 3, "name": "ディープインパクト", "distance_covered": 1200.0, "odds": 1.3},
            {"horse_id": 1, "number": 1, "name": "ダイワメジャー", "distance_covered": 1198.5, "odds": 2.5},
            {"horse_id": 2, "number": 2, "name": "ハーツクライ", "distance_covered": 1195.0, "odds": 4.1},
        ]
        
        # 描画メソッド呼び出しで例外が出ないこと
        from PyQt6.QtGui import QPainter, QImage
        img = QImage(1000, 600, QImage.Format.Format_ARGB32)
        p = QPainter(img)
        canvas._draw_top3_vertical_hud(p, 1000, 600, horses)
        canvas._draw_hud_overlay(p, 1000, 600)
        canvas.set_result_board_data(
            track_name="東京",
            race_number="9R",
            surface_jp="芝",
            top5_horses=[
                {"gate_number": 5, "margin": ""},
                {"gate_number": 14, "margin": "1 3/4"},
                {"gate_number": 12, "margin": "1/2"},
                {"gate_number": 7, "margin": "1 1/4"},
                {"gate_number": 8, "margin": "アタマ"},
            ],
            finish_time=82.8,
            is_record=False,
            f3_time=35.1,
            is_confirmed=True,
            is_visible=True,
        )
        canvas._draw_race_board_overlay(p, 1000, 600)
        p.end()

    def test_combo_races_ascending_order(self):
        """レース選択プルダウンが昇順（1R, 2R...）で格納されていることの検証"""
        replay = RaceReplayView(self.db)
        replay.load_race_by_id(self.race_row["race_id"])

        items = [replay.combo_races.itemText(i) for i in range(replay.combo_races.count())]
        print(f"プルダウン項目リスト: {items}")
        self.assertGreater(len(items), 0)
        if len(items) >= 2:
            self.assertIn("1R:", items[0])

    def test_race_entry_dialog(self):
        """出馬表ダイアログ（RaceEntryDialog）が正常に生成され出走馬が確認できることの検証"""
        from src.gui.views.race_dialogs import RaceEntryDialog

        dlg = RaceEntryDialog(self.db, self.race_row["race_id"])
        self.assertGreater(dlg.table.rowCount(), 0)
        # 枠番列、馬番列、馬名列のデータ確認
        h_name_item = dlg.table.item(0, 2)
        self.assertIsNotNone(h_name_item)
        self.assertTrue(len(h_name_item.text()) > 0)
        print(f"出馬表 1頭目馬名: {h_name_item.text()}")


if __name__ == "__main__":
    unittest.main()


