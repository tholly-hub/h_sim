import os, sys, tempfile, unittest
from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.race.calendar import CalendarController
from src.gui.views.dashboard_view import DashboardView

class TestDashboardView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_file = tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False)
        cls.temp_path = cls.temp_file.name
        cls.temp_file.close()
        cls.db = Database(cls.temp_path)
        init = DatabaseInitializer(cls.db)
        init.initialize_all(force_recreate=True)

    @classmethod
    def tearDownClass(cls):
        try:
            if os.path.exists(cls.temp_path):
                os.remove(cls.temp_path)
        except Exception:
            pass

    def test_dashboard_initial_load(self):
        # DashboardView を初期化（この時点で出馬表が正しく表示されるか）
        view = DashboardView(self.db)
        
        # レース一覧テーブルにレースが表示されているか
        self.assertTrue(view.table_races.rowCount() > 0)
        # 出走馬一覧テーブルに馬が表示されているか（出馬表が表示されない問題の解決検証）
        self.assertTrue(view.table_entry.rowCount() > 0)
        print(f'PASS: Dashboard loaded {view.table_races.rowCount()} races and {view.table_entry.rowCount()} entries.')

        # 別のレースを選択したときにも出馬表が正しく切り替わるか
        if view.table_races.rowCount() > 1:
            view._on_race_selected_by_row(1)
            self.assertTrue(view.table_entry.rowCount() > 0)
            print(f'PASS: Switched to race 1, loaded {view.table_entry.rowCount()} entries.')

if __name__ == '__main__':
    unittest.main()
