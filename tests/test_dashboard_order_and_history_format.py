import os
import unittest
from PyQt6.QtWidgets import QApplication

from src.db.database import Database
from src.gui.views.dashboard_view import (
    DashboardView,
    GRADE_SORT_ORDER,
    TRACK_SORT_ORDER,
)
from src.gui.views.horse_detail_dialog import HorseDetailDialog
from src.models.horse import Horse
from src.models.race import AgeRestriction, Race, RaceGrade, RaceSurface, SexRestriction
from src.race.calendar import CalendarController


class TestDashboardOrderAndHistoryFormat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.test_db_path = "data/test_order_format.db"
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        self.db = Database(self.test_db_path)
        self.db.initialize_schema()

    def tearDown(self):
        for suffix in ["", "-shm", "-wal"]:
            p = f"{self.test_db_path}{suffix}"
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

    def test_dashboard_races_sorting_order(self):
        """ダッシュボードのレース一覧が競馬場順かつグレード昇順（未勝利->新馬->1勝->...->G1）にソートされること"""
        cal = CalendarController(self.db)
        # 年間番組表登録
        cal.program_builder.register_annual_program(year=1)

        dashboard = DashboardView(db=self.db)
        # 第21週のデータをロード
        dashboard._load_week_data(1, 21)

        row_count = dashboard.table_races.rowCount()
        self.assertGreater(row_count, 0)

        # テーブル内のレースの競馬場とグレード順序を検証
        prev_track_order = -1
        prev_grade_order = -1
        current_track = None

        for row in range(row_count):
            track_id = dashboard.table_races.item(row, 0).text()
            grade_str = dashboard.table_races.item(row, 2).text()

            t_order = TRACK_SORT_ORDER.get(track_id, 99)
            g_order = GRADE_SORT_ORDER.get(grade_str, 99)

            if track_id != current_track:
                # 競馬場が変わった場合、競馬場順序が前以上であること
                self.assertGreaterEqual(t_order, prev_track_order)
                current_track = track_id
                prev_track_order = t_order
                prev_grade_order = g_order
            else:
                # 同一競馬場内では、グレード順序が昇順（前以上）であること
                self.assertGreaterEqual(
                    g_order,
                    prev_grade_order,
                    f"Row {row}: Grade {grade_str} (order {g_order}) should be >= previous grade order {prev_grade_order} in track {track_id}"
                )
                prev_grade_order = g_order

    def test_horse_history_date_format_no_slashes(self):
        """競走馬詳細ダイアログの出走履歴において、年・週カラムにスラッシュ(/)が含まれず「〇年〇月〇週」形式であること"""
        # ダミーの馬およびレース結果を作成
        with self.db.session() as conn:
            conn.execute("""
                INSERT INTO breeders (breeder_id, name) VALUES (1, 'テスト牧場')
            """)
            conn.execute("""
                INSERT INTO owners (owner_id, name, prefix) VALUES (1, 'テスト馬主', 'テスト')
            """)
            conn.execute("""
                INSERT INTO horses (
                    horse_id, name, sex, birth_year, age, breeder_id, owner_id,
                    mstn_type, speed, stamina, acceleration, temperament, durability,
                    maternal_vitality, growth_type, peak_age, running_style, prize_money
                )
                VALUES (
                    1, 'テストホース', 'colt', 1, 3, 1, 1,
                    'C/T', 60.0, 60.0, 60.0, 50.0, 50.0,
                    50.0, 'normal', 4.5, 'leading', 5000000
                )
            """)
            conn.execute("""
                INSERT INTO races (race_id, year, month, week, track_id, name, grade, surface, distance, full_gate, age_restriction, sex_restriction)
                VALUES (101, 1, 6, 21, 'TOKYO', '日本ダービー', 'G1', 'turf', 2400, 8, '3yo', 'mixed')
            """)
            conn.execute("""
                INSERT INTO results (race_id, horse_id, finish_position, finish_time, last_3f, prize_awarded, gate_number)
                VALUES (101, 1, 1, 142.5, 34.2, 150000000, 1)
            """)

        dialog = HorseDetailDialog(horse_id=1, db=self.db)
        self.assertEqual(dialog.table_history.rowCount(), 1)

        date_str = dialog.table_history.item(0, 0).text()
        # '/' が含まれていないこと
        self.assertNotIn("/", date_str)
        # 正しい形式であることを確認（例: "1年6月1週"）
        self.assertEqual(date_str, "1年6月1週")


if __name__ == "__main__":
    unittest.main()
