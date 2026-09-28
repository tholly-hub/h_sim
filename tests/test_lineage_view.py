"""
LineageView (系統樹タブ) のユニットテスト
"""

import os
import sys
import unittest
from PyQt6.QtWidgets import QApplication

from src.db.database import Database
from src.gui.app import MainWindow
from src.gui.views.lineage_view import LineageView, SireLineageWidget, SireTreeNode, DamLineageWidget, DamTreeNode


class TestLineageView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Headless Qt App
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        # データベース接続
        self.db_path = "data/horse_racing_sim.db"
        if not os.path.exists(self.db_path):
            self.db_path = "G:\\マイドライブ\\h_sim\\data\\horse_racing_sim.db"
        self.db = Database(self.db_path)

    def test_lineage_view_init(self):
        """LineageViewの初期化テスト"""
        view = LineageView(self.db)
        self.assertIsNotNone(view.tab_sires)
        self.assertIsNotNone(view.tab_dams)
        self.assertEqual(view.main_tabs.count(), 2)

    def test_sire_lineage_data_loading(self):
        """種牡馬サイヤーラインのデータ読み込みと存続/断絶分類テスト"""
        sire_widget = SireLineageWidget(self.db)
        sire_widget.refresh_data()

        # ルートサイヤーが存在すること
        self.assertGreater(len(sire_widget.root_sire_ids), 0)
        
        # 存続系列ツリーと断絶系列ツリーにアイテムが投入されていること
        total_items = sire_widget.tree_active.topLevelItemCount() + sire_widget.tree_extinct.topLevelItemCount()
        self.assertEqual(total_items, len(sire_widget.root_sire_ids))

    def test_tree_building_and_layout(self):
        """系統樹の再帰的ノード構築およびレイアウト計算テスト"""
        sire_widget = SireLineageWidget(self.db)
        sire_widget.refresh_data()

        if sire_widget.root_sire_ids:
            root_id = sire_widget.root_sire_ids[0]
            sire_widget._select_sire_line(root_id)

            canvas = sire_widget.canvas_widget
            self.assertIsNotNone(canvas.root_node)
            self.assertGreater(len(canvas.node_rect_map), 0)
            self.assertGreater(canvas.width(), 0)
            self.assertGreater(canvas.height(), 0)

    def test_dam_lineage_data_loading(self):
        """繁殖牝馬ファミリーナンバーのデータ読み込みと存続/断絶分類テスト"""
        dam_widget = DamLineageWidget(self.db)
        dam_widget.refresh_data()

        # 始祖繁殖牝馬（族）が存在すること
        self.assertGreater(len(dam_widget.root_dam_ids), 0)

        # 存続族と断絶族に正しく分類されていること
        total_items = dam_widget.tree_active.topLevelItemCount() + dam_widget.tree_extinct.topLevelItemCount()
        self.assertEqual(total_items, len(dam_widget.root_dam_ids))

        # 最初の族を選択してキャンバスにノードが描画されること
        self.assertIsNotNone(dam_widget.canvas.root_node)
        self.assertGreater(len(dam_widget.canvas.node_rect_map), 0)
        self.assertGreater(dam_widget.canvas.width(), 0)
        self.assertGreater(dam_widget.canvas.height(), 0)

    def test_main_window_tabs(self):
        """MainWindowのタブ配置が正しく系統樹タブを含んでいるかテスト"""
        win = MainWindow(self.db)
        self.assertEqual(win.tabs.count(), 7)
        self.assertEqual(win.tabs.tabText(3), "📚 競馬データベース")
        self.assertEqual(win.tabs.tabText(4), "🌳 系統樹")
        self.assertEqual(win.tabs.tabText(5), "📈 能力推移 & 走破タイム")
        self.assertEqual(win.tabs.tabText(6), "⚙️ シミュレーション状況")


if __name__ == "__main__":
    unittest.main()

