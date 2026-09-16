"""
Phase 4: PyQt6 GUIコンポーネント包括単体テスト
- オフスクリーン（QApplication無描画モード）によるテスト
- メインウィンドウ、タブ、各ビュー、血統表、キャンバスの初期化とデータ連携を検証
"""

import os
import sys
import unittest

# ヘッドレス（オフスクリーン）モードの設定
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication

from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.gui.app import MainWindow
from src.gui.views.analytics_view import AnalyticsView
from src.gui.views.dashboard_view import DashboardView
from src.gui.views.horse_browser_view import HorseBrowserView
from src.gui.views.race_replay_view import RaceReplayView
from src.gui.views.rankings_view import RankingsView
from src.race.program import RaceProgramBuilder


class TestPhase4GUI(unittest.TestCase):
    """Phase 4 GUIコンポーネントのテストケース"""

    @classmethod
    def setUpClass(cls):
        # QApplication インスタンスの確保
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication(sys.argv)

        cls.db_path = "/tmp/test_gui.db"
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = Database(cls.db_path)
        cls.db.initialize_schema(force_recreate=True)

        # テスト用初期データ作成
        init = DatabaseInitializer(cls.db)
        init.initialize_all(force_recreate=True, with_careers=True)
        prog = RaceProgramBuilder(cls.db)
        prog.register_annual_program(year=1)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.db_path):
            try:
                os.remove(cls.db_path)
            except Exception:
                pass

    def test_main_window_initialization(self):
        """MainWindow が正常に起動し、5つのタブが存在すること"""
        window = MainWindow(self.db)
        self.assertIsNotNone(window)
        self.assertEqual(window.tabs.count(), 5)
        tab_titles = [window.tabs.tabText(i) for i in range(5)]
        self.assertTrue(any("ダッシュボード" in t for t in tab_titles))
        self.assertTrue(any("競走馬" in t for t in tab_titles))
        self.assertTrue(any("リーディング" in t for t in tab_titles))
        self.assertTrue(any("タイム" in t for t in tab_titles))
        self.assertTrue(any("リプレイ" in t for t in tab_titles))

    def test_dashboard_view(self):
        """DashboardView が統計カードを正しく取得・反映できること"""
        dash = DashboardView(self.db)
        self.assertIn("頭", dash.card_active.val_lbl.text())
        self.assertIn("人", dash.card_owners.val_lbl.text())
        self.assertIn("場", dash.card_breeders.val_lbl.text())

    def test_horse_browser_view(self):
        """HorseBrowserView で馬が検索・選択され、詳細と血統表が更新されること"""
        browser = HorseBrowserView(self.db)
        self.assertGreater(browser.table.rowCount(), 0)

        # 最初の馬を選択
        h_id_item = browser.table.item(0, 0)
        self.assertIsNotNone(h_id_item)
        h_id = int(h_id_item.text())

        browser.select_horse_by_id(h_id)
        self.assertEqual(browser.current_horse_id, h_id)
        self.assertNotEqual(browser.lbl_d_name.text(), "-")
        self.assertGreater(browser.bar_spd.bar.value(), 0)

    def test_rankings_view(self):
        """RankingsView で各カテゴリのランキングが取得・表示できること"""
        view = RankingsView(self.db)
        # 騎手
        view._change_category("jockey")
        self.assertEqual(view.current_category, "jockey")
        self.assertGreaterEqual(view.rank_table.columnCount(), 5)

        # 調教師
        view._change_category("trainer")
        self.assertEqual(view.current_category, "trainer")

        # 馬主
        view._change_category("owner")
        self.assertEqual(view.current_category, "owner")

        # 牧場・馬主規模階層テーブル
        self.assertGreater(view.tier_table.rowCount(), 0)

    def test_analytics_view(self):
        """AnalyticsView でグラフが初期化・描画できること"""
        view = AnalyticsView(self.db)
        self.assertIsNotNone(view.canvas_time)
        self.assertIsNotNone(view.canvas_stats)
        view.refresh_charts()

    def test_race_replay_view(self):
        """RaceReplayView でリプレイ画面とトラックキャンバスが正常に初期化できること"""
        view = RaceReplayView(self.db)
        self.assertIsNotNone(view.track_canvas)
        self.assertIsNotNone(view.table_results)


if __name__ == "__main__":
    unittest.main()
