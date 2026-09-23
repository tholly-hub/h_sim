import os, sys, tempfile, unittest
from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.race.calendar import CalendarController
from src.gui.views.horse_detail_dialog import HorseDetailDialog

class TestHorseDetailExclude(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_file = tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False)
        cls.temp_path = cls.temp_file.name
        cls.temp_file.close()
        cls.db = Database(cls.temp_path)
        init = DatabaseInitializer(cls.db)
        init.initialize_all(force_recreate=True)
        cls.cal = CalendarController(cls.db)
        cls.cal.run_week(1, 21)
        cls.cal.run_week(1, 22)

    @classmethod
    def tearDownClass(cls):
        try:
            if os.path.exists(cls.temp_path):
                os.remove(cls.temp_path)
        except Exception:
            pass

    def test_exclude_race_id(self):
        with self.db.session() as conn:
            row = conn.execute('SELECT horse_id FROM results GROUP BY horse_id LIMIT 1').fetchone()
            horse_id = row['horse_id']
            res_all = conn.execute('SELECT race_id, prize_awarded FROM results WHERE horse_id = ?', (horse_id,)).fetchall()
            h_info = conn.execute('SELECT prize_money FROM horses WHERE horse_id = ?', (horse_id,)).fetchone()
            total_prize = h_info['prize_money']
            target_race_id = res_all[-1]['race_id']
            target_prize = res_all[-1]['prize_awarded']

        dlg_all = HorseDetailDialog(self.db, horse_id, exclude_race_id=None)
        self.assertEqual(dlg_all.table_history.rowCount(), len(res_all))
        self.assertEqual(dlg_all.lbl_earnings.text(), f'生涯獲得賞金: {total_prize // 10000:,} 万円')

        dlg_ex = HorseDetailDialog(self.db, horse_id, exclude_race_id=target_race_id)
        self.assertEqual(dlg_ex.table_history.rowCount(), len(res_all) - 1)
        adj_prize = total_prize - target_prize
        self.assertEqual(dlg_ex.lbl_earnings.text(), f'生涯獲得賞金: {adj_prize // 10000:,} 万円')
        print('PASS: test_exclude_race_id passed successfully!')

if __name__ == '__main__':
    unittest.main()
