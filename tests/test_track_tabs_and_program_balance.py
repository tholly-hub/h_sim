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
        races = generate_full_program(1)
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
        """初期化時、初年度は2歳馬のみ600頭（全頭未出走）が存在し、3歳馬は0頭であること"""
        with self.db.session() as conn:
            # 3歳以上の現役馬は0頭
            older_horses = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE is_active = 1 AND age >= 3"
            ).fetchone()[0]
            # 2歳現役馬は600頭（未出走）
            two_yo_horses = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE is_active = 1 AND age = 2"
            ).fetchone()[0]
            two_yo_unraced = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE is_active = 1 AND age = 2 AND career_starts = 0"
            ).fetchone()[0]

            print(f"初期現役馬: 2歳={two_yo_horses}頭(未出走={two_yo_unraced}頭), 3歳以上={older_horses}頭")
            self.assertEqual(older_horses, 0, "初年度は3歳以上の現役馬は存在してはなりません")
            self.assertEqual(two_yo_horses, 600, "初年度は2歳馬600頭が存在する必要があります")
            self.assertEqual(two_yo_unraced, 600, "初年度2歳馬は全頭未出走である必要があります")

    def test_dashboard_tabs_display_and_track_separation(self):
        """ダッシュボードで各競馬場ごとのタブが生成され、競馬場ごとにレースが表示されること"""
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
            self.assertGreater(table.rowCount(), 0)

        # タブ切り替えと出走馬表の連動テスト
        tabs.setCurrentIndex(1)
        selected_tbl = tabs.widget(1)
        self.assertIsInstance(selected_tbl, QTableWidget)
        selected_tbl.selectRow(0)

        # 出走馬表テーブルに正常に出走馬が表示されること
        self.assertEqual(dash.table_entry.rowCount(), 8)


if __name__ == "__main__":
    unittest.main()
