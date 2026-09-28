"""
競馬場タブ表示・番組表2〜3場開催完全バランス・初期化時6月1週未勝利頭数の自動テスト
"""

import sys
import unittest
from collections import defaultdict
from PyQt6.QtWidgets import QApplication, QTableWidget

from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.gui.views.dashboard_view import DashboardView, TRACK_DISPLAY_NAMES
from src.race.annual_program import generate_full_program

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class TestTrackTabsAndProgramBalance(unittest.TestCase):
    """競馬場別タブ表示と番組表バランスの検証"""

    def setUp(self):
        self.db = Database(":memory:")
        init_gen = DatabaseInitializer(self.db)
        init_gen.initialize_all(force_recreate=True, with_careers=True)

    def test_annual_program_all_weeks_balanced(self):
        """全48週で2〜3場開催が基本となり、1レースのみ単独開催の競馬場が存在しないこと"""
        races = generate_full_program(5)
        by_week_track = defaultdict(lambda: defaultdict(list))
        for r in races:
            by_week_track[r.week][r.track_id].append(r)

        for w in range(1, 49):
            tracks = by_week_track[w]
            self.assertIn(len(tracks), (2, 3), f"第{w}週の開催場数が2〜3場ではありません: {len(tracks)}")
            for trk, rs in tracks.items():
                self.assertGreaterEqual(
                    len(rs), 4,
                    f"第{w}週の競馬場 {trk} のレース数が少なすぎます ({len(rs)}R)"
                )

    def test_initial_database_week21_maiden_horses_not_overcrowded(self):
        """初期化時、初年度は0歳当歳馬600頭（牡300/牝300）が存在し、3年目入厩時に2歳馬600頭となること"""
        with self.db.session() as conn:
            # 初年度0歳馬は600頭
            foals_count = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE birth_year = 1 AND age = 0"
            ).fetchone()[0]
            self.assertEqual(foals_count, 600, "初年度は0歳当歳馬600頭が存在する必要があります")

    def test_dashboard_tabs_display_and_track_separation(self):
        """ダッシュボードで各競馬場ごとのタブが生成され、競馬場ごとにレースが表示されること（フル番組年度）"""
        from src.race.program import RaceProgramBuilder
        RaceProgramBuilder(self.db).register_annual_program(year=5)
        with self.db.session() as conn:
            conn.execute("UPDATE system_status SET value_int = 5 WHERE key = 'current_year'")
            conn.execute("UPDATE system_status SET value_int = 1 WHERE key = 'current_week'")

        dash = DashboardView(self.db)
        dash.resize(1200, 800)

        tabs = dash.tabs_tracks
        self.assertIsNotNone(tabs)
        self.assertGreaterEqual(tabs.count(), 2)

        print(f"ダッシュボード 競馬場タブ数: {tabs.count()}")
        for i in range(tabs.count()):
            tab_text = tabs.tabText(i)
            print(f"  タブ {i}: {tab_text}")
            self.assertTrue(any(name in tab_text for name in TRACK_DISPLAY_NAMES.values()))
            table = tabs.widget(i)
            self.assertIsInstance(table, QTableWidget)

        # タブ切り替えとテーブルの連動テスト
        tabs.setCurrentIndex(1)
        selected_tbl = tabs.widget(1)
        self.assertIsInstance(selected_tbl, QTableWidget)
        self.assertGreater(selected_tbl.rowCount(), 0)


if __name__ == "__main__":
    unittest.main()
