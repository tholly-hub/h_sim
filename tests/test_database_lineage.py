import os
import sys
import unittest
from PyQt6.QtWidgets import QApplication

from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.gui.views.database_view import DatabaseView


class TestDatabaseLineage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.db = Database(':memory:')
        self.init = DatabaseInitializer(self.db)
        self.init.initialize_all()
        self.view = DatabaseView(self.db)

    def test_lineage_trees_no_extinct(self):
        """断絶した系統が表示されず、存続系統のみ表示されることのテスト"""
        self.view.refresh_all()

        # 種牡馬タブ: サイアーライン別種牡馬（初期100頭が供用中）
        self.view.sires_sub_tabs.setCurrentIndex(2)
        self.view.refresh_lineage_sires()
        sire_roots = self.view.tree_lineage_sires.topLevelItemCount()
        self.assertGreater(sire_roots, 0, "供用中種牡馬がいる系統が表示されること")
        for i in range(sire_roots):
            item = self.view.tree_lineage_sires.topLevelItem(i)
            self.assertNotEqual(item.text(1), "0頭")

        # 繁殖牝馬タブ: ファミリーナンバー別繁殖牝馬（初期600頭が始祖族として供用中）
        self.view.dams_sub_tabs.setCurrentIndex(2)
        self.view.refresh_family_dams()
        family_roots = self.view.tree_family_dams.topLevelItemCount()
        self.assertGreater(family_roots, 0, "供用中繁殖牝馬がいるファミリーナンバーが表示されること")
        for i in range(family_roots):
            item = self.view.tree_family_dams.topLevelItem(i)
            self.assertNotEqual(item.text(1), "0頭")

        # 父馬を持つ繁殖牝馬を擬似的に登録してサイアーライン別繁殖牝馬の挙動をテスト
        with self.db.session() as conn:
            sire_h_id = conn.execute("SELECT horse_id FROM sires LIMIT 1").fetchone()["horse_id"]
            conn.execute(f"UPDATE horses SET sire_id = {sire_h_id} WHERE horse_id IN (SELECT horse_id FROM dams LIMIT 5)")

        # 繁殖牝馬タブ: サイアーライン別繁殖牝馬
        self.view.dams_sub_tabs.setCurrentIndex(1)
        self.view.refresh_lineage_dams()
        dam_lineage_roots = self.view.tree_lineage_dams.topLevelItemCount()
        self.assertGreater(dam_lineage_roots, 0, "父系に供用中繁殖牝馬が存在する系統が表示されること")
        for i in range(dam_lineage_roots):
            item = self.view.tree_lineage_dams.topLevelItem(i)
            self.assertNotEqual(item.text(1), "0頭")

        # 擬似的に現役競走馬を有効化してサイアーライン別競走馬の挙動をテスト
        with self.db.session() as conn:
            conn.execute("UPDATE horses SET is_active = 1, age = 2 WHERE horse_id IN (SELECT horse_id FROM horses WHERE sire_id IS NOT NULL LIMIT 10)")
        
        self.view.sires_sub_tabs.setCurrentIndex(1)
        self.view.refresh_lineage_horses()
        horse_roots = self.view.tree_lineage_horses.topLevelItemCount()
        self.assertGreater(horse_roots, 0, "現役競走馬が存在する系統のみが表示されること")
        for i in range(horse_roots):
            item = self.view.tree_lineage_horses.topLevelItem(i)
            self.assertNotEqual(item.text(1), "0頭")


if __name__ == '__main__':
    unittest.main()
