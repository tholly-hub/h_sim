import unittest
from unittest.mock import MagicMock
from src.db.database import Database
from src.gui.views.weekly_event_dialog import WeeklyEventDialog
from PyQt6.QtWidgets import QApplication

class TestWeeklyEventDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_weekly_event_dialog_load_data(self):
        db = MagicMock(spec=Database)
        mock_conn = MagicMock()

        # レース結果モック
        mock_races = [
            {
                "race_id": 101,
                "race_name": "中山金杯",
                "grade": "G3",
                "surface": "turf",
                "distance": 2000,
                "finish_position": 1,
                "horse_id": 1,
                "horse_name": "ゴールドシップ",
                "sex": "colt",
                "age": 4,
                "sire_name": "ステイゴールド",
                "dam_name": "ポイントフラッグ",
                "jockey_name": "内田博幸",
                "trainer_name": "須貝尚介"
            },
            {
                "race_id": 102,
                "race_name": "3歳新馬",
                "grade": "NEWCOMER",
                "surface": "dirt",
                "distance": 1800,
                "finish_position": 1,
                "horse_id": 2,
                "horse_name": "ニューカマー",
                "sex": "filly",
                "age": 3,
                "sire_name": "父馬",
                "dam_name": "母馬",
                "jockey_name": "川田将雅",
                "trainer_name": "中内田充正"
            }
        ]

        mock_conn.execute.return_value.fetchall.side_effect = [
            mock_races,  # 1. 今週の全レース結果取得
            [],          # 2. milestone_records
        ]
        db.session.return_value.__enter__.return_value = mock_conn

        dlg = WeeklyEventDialog(db, year=4, week=1)
        self.assertEqual(dlg.tbl_graded.rowCount(), 1)
        self.assertEqual(dlg.tbl_breakthrough.rowCount(), 1)

if __name__ == "__main__":
    unittest.main()
