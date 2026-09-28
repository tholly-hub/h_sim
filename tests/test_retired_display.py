import unittest
from unittest.mock import MagicMock, patch
from src.models.horse import Horse, GenotypeMSTN, GrowthType
from src.db.database import Database
from src.gui.views.database_view import DatabaseView
from src.gui.views.horse_detail_dialog import HorseDetailDialog
from PyQt6.QtWidgets import QApplication

class TestRetiredDisplayFixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @patch("src.gui.views.horse_detail_dialog.PedigreeBuilder")
    def test_retired_horse_detail_dialog_label(self, mock_ped_builder_cls):
        mock_builder = MagicMock()
        mock_builder.get_ancestors_tree.return_value = {}
        mock_ped_builder_cls.return_value = mock_builder

        db = MagicMock(spec=Database)
        
        # 現役馬
        active_row = {
            "horse_id": 1,
            "name": "アクティブ号",
            "sex": "colt",
            "birth_year": 1,
            "age": 4,
            "breeder_id": 1,
            "owner_id": 1,
            "trainer_id": 1,
            "jockey_id": 1,
            "sire_id": None,
            "dam_id": None,
            "coat_color": "鹿毛",
            "coat_genotype": "E/E A/A G/g W/w Cr/cr",
            "mstn_type": "C/T",
            "surface_aptitude": "turf",
            "growth_type": "normal",
            "speed": 60.0,
            "stamina": 60.0,
            "acceleration": 60.0,
            "temperament": 60.0,
            "durability": 60.0,
            "maternal_vitality": 60.0,
            "apt_distance_min": 1600,
            "apt_distance_max": 2400,
            "apt_distance_range": 800,
            "running_style": "between",
            "peak_age": 4.0,
            "current_ability_rate": 1.0,
            "career_starts": 10,
            "career_wins": 5,
            "g1_wins": 1,
            "g2_wins": 1,
            "g3_wins": 1,
            "prize_money": 100000000,
            "condition_prize_money": 16000000,
            "is_active": 1,
            "is_sire": 0,
            "is_dam": 0,
            "is_dead": 0,
            "generation": 1,
            "major_wins": "皐月賞(G1)"
        }

        # 引退馬
        retired_row = dict(active_row)
        retired_row.update({
            "horse_id": 2,
            "name": "リタイア号",
            "age": 6,
            "is_active": 0,
            "career_starts": 20,
            "career_wins": 8,
            "g1_wins": 2,
            "prize_money": 200000000
        })

        def mock_session_active():
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.side_effect = [
                active_row,
                {"name": "矢作厩舎", "location": "栗東"},
                {"name": "ノーザンF", "region": "早来"},
                {"name": "サンデーR"},
                {"name": "ルメール", "location": "栗東"},
                {"sire_line": "サンデーサイレンス系"},
            ]
            mock_conn.execute.return_value.fetchall.return_value = []
            return MagicMock(__enter__=MagicMock(return_value=mock_conn), __exit__=MagicMock(return_value=None))

        db.session = mock_session_active
        dlg_active = HorseDetailDialog(db, horse_id=1)
        self.assertIn("牡4歳", dlg_active.lbl_name.text())
        self.assertIn("【オープン】", dlg_active.lbl_name.text())

        def mock_session_retired():
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.side_effect = [
                retired_row,
                {"name": "矢作厩舎", "location": "栗東"},
                {"name": "ノーザンF", "region": "早来"},
                {"name": "サンデーR"},
                {"name": "ルメール", "location": "栗東"},
                {"sire_line": "サンデーサイレンス系"},
            ]
            mock_conn.execute.return_value.fetchall.return_value = []
            return MagicMock(__enter__=MagicMock(return_value=mock_conn), __exit__=MagicMock(return_value=None))

        db.session = mock_session_retired
        dlg_retired = HorseDetailDialog(db, horse_id=2)
        self.assertIn("(引退・【オープン】", dlg_retired.lbl_name.text())
        self.assertNotIn("6歳", dlg_retired.lbl_name.text())


    def test_database_view_leading_retired_display(self):
        db = MagicMock(spec=Database)
        view = DatabaseView(db)
        
        mock_rows = [
            {
                "horse_id": 1,
                "horse_name": "現役馬",
                "sex": "colt",
                "age": 4,
                "is_active": 1,
                "generation": 1,
                "sire_name": "父馬",
                "dam_name": "母馬",
                "trainer_name": "調教師",
                "total_starts": 10,
                "total_wins": 5,
                "graded_wins": 2,
                "total_prize": 100000000
            },
            {
                "horse_id": 2,
                "horse_name": "引退馬",
                "sex": "colt",
                "age": 8,
                "is_active": 0,
                "generation": 1,
                "sire_name": "父馬",
                "dam_name": "母馬",
                "trainer_name": "調教師",
                "total_starts": 20,
                "total_wins": 8,
                "graded_wins": 4,
                "total_prize": 200000000
            }
        ]

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = mock_rows
        db.session.return_value.__enter__.return_value = mock_conn

        view.refresh_leading()

        # 現役馬の性齢 (行0, 列2)
        item_active = view.table_leading.item(0, 2)
        self.assertEqual(item_active.text(), "牡4")

        # 引退馬の性齢 (行1, 列2)
        item_retired = view.table_leading.item(1, 2)
        self.assertEqual(item_retired.text(), "引退")

if __name__ == "__main__":
    unittest.main()
