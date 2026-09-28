import unittest
from unittest.mock import MagicMock
from src.db.database import Database
from src.race.rankings import RankingManager
from src.gui.views.rankings_view import RankingsView
from PyQt6.QtWidgets import QApplication

class TestJockeyRankingsAffiliation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_jockey_rankings_query_and_view_affiliation(self):
        db = MagicMock(spec=Database)
        
        # 1. RankingManager からの返却モックデータ（厩舎所属騎手とフリー騎手）
        mock_jockey_rows = [
            {
                "jockey_id": 1,
                "name": "武田豊",
                "age": 30,
                "location": "栗東",
                "is_free": 0,
                "trainer_id": 10,
                "trainer_name": "矢作厩舎",
                "debut_year": 1,
                "career_wins": 500,
                "career_earnings": 1000000000,
                "win_1": 80,
                "win_2": 40,
                "win_3": 30,
                "win_out": 200,
                "g1_cnt": 3,
                "g2_cnt": 5,
                "g3_cnt": 8,
                "total_earnings": 1500000000,
                "win_rate": 0.229,
                "representative_horses": ["コントレイル"],
                "representative_horse_ids": [101]
            },
            {
                "jockey_id": 2,
                "name": "ルメール",
                "age": 42,
                "location": "栗東",
                "is_free": 1,
                "trainer_id": None,
                "trainer_name": None,
                "debut_year": 1,
                "career_wins": 1000,
                "career_earnings": 3000000000,
                "win_1": 100,
                "win_2": 60,
                "win_3": 40,
                "win_out": 150,
                "g1_cnt": 5,
                "g2_cnt": 8,
                "g3_cnt": 10,
                "total_earnings": 2500000000,
                "win_rate": 0.286,
                "representative_horses": ["アーモンドアイ"],
                "representative_horse_ids": [102]
            }
        ]

        rank_mgr = MagicMock(spec=RankingManager)
        rank_mgr.get_jockey_rankings.return_value = mock_jockey_rows

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = [5] # current_year = 5
        db.session.return_value.__enter__.return_value = mock_conn

        view = RankingsView(db)
        view.rank_mgr = rank_mgr
        view.current_category = "jockey"
        view._load_ranking_table()

        # テーブルの行数
        self.assertEqual(view.rank_table.rowCount(), 2)

        # 1行目（1年目デビュー）の年齢（列2）、所属（列3）と区分（列4）
        item_age_1 = view.rank_table.item(0, 2)
        item_loc_1 = view.rank_table.item(0, 3)
        item_aff_1 = view.rank_table.item(0, 4)
        self.assertEqual(item_age_1.text(), "30歳 (1年デビュー)")
        self.assertEqual(item_loc_1.text(), "栗東")
        self.assertEqual(item_aff_1.text(), "矢作厩舎")

        # 2行目（初期デビュー: debut_year <= 0 をテスト）
        mock_jockey_rows[1]["debut_year"] = -5
        view._load_ranking_table()
        item_age_2 = view.rank_table.item(1, 2)
        item_loc_2 = view.rank_table.item(1, 3)
        item_aff_2 = view.rank_table.item(1, 4)
        self.assertEqual(item_age_2.text(), "42歳 (初期デビュー)")
        self.assertEqual(item_loc_2.text(), "栗東")
        self.assertEqual(item_aff_2.text(), "フリー")

if __name__ == "__main__":
    unittest.main()
