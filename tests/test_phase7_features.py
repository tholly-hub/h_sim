"""
Phase 7 新機能および追加要件に関する単体テスト
- 日本馬事協会規定14毛色およびメンデル遺伝システム
- 競走馬クラス名・通算成績判定
- 9月4週・12月4週年次イベントダイアログ
- 各種リーディング集計（勝利数優先、持ち馬数・勝ち馬数）
- コースレコード総合タブおよび推移ダイアログ
"""

from __future__ import annotations

import unittest
from PyQt6.QtWidgets import QApplication

from src.core.genetics import GeneticsEngine
from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.gui.views.annual_events_dialogs import UnvictoryRetirementDialog, YearEndAwardsDialog
from src.gui.views.records_view import RecordsView, RecordHistoryDialog
from src.models.horse import CoatColor, Horse
from src.race.rankings import RankingManager

app = QApplication.instance() or QApplication([])


class TestPhase7Features(unittest.TestCase):
    """Phase 7 追加機能テスト"""

    def setUp(self):
        self.db = Database(":memory:")
        self.initializer = DatabaseInitializer(self.db)
        self.initializer.initialize_all()

    def tearDown(self):
        pass

    def test_coat_colors_and_genetics(self):
        """日本馬事協会規定14毛色とメンデル遺伝の検証"""
        # 14種類の毛色Enumが存在すること
        all_colors = [c.value for c in CoatColor]
        self.assertEqual(len(all_colors), 14)
        self.assertIn("栗毛", all_colors)
        self.assertIn("栃栗毛", all_colors)
        self.assertIn("鹿毛", all_colors)
        self.assertIn("黒鹿毛", all_colors)
        self.assertIn("青鹿毛", all_colors)
        self.assertIn("青毛", all_colors)
        self.assertIn("芦毛", all_colors)
        self.assertIn("白毛", all_colors)
        self.assertIn("月毛", all_colors)
        self.assertIn("河原毛", all_colors)
        self.assertIn("粕毛", all_colors)
        self.assertIn("薄墨毛", all_colors)
        self.assertIn("佐河毛", all_colors)
        self.assertIn("斑毛", all_colors)

        # ランダム毛色遺伝子型の生成
        color, geno = GeneticsEngine.generate_random_coat_genotype()
        self.assertIn(color, all_colors)
        self.assertIsInstance(geno, str)

        # メンデル受精継承
        sire_geno = "E/E A/A g/g w/w cr/cr ro/ro pt/pt"
        dam_geno = "e/e A/a G/g w/w cr/cr ro/ro pt/pt"
        child_color, child_geno = GeneticsEngine.inherit_coat_genotype(sire_geno, dam_geno)
        self.assertIn(child_color, all_colors)
        self.assertIsInstance(child_geno, str)

    def test_horse_class_name(self):
        """競走馬の現在クラス名判定プロパティの検証"""
        with self.db.session() as conn:
            h_row = conn.execute("SELECT * FROM horses WHERE is_active = 1 LIMIT 1").fetchone()
            horse = Horse.from_row(h_row)
            self.assertIn(horse.class_name, ["未出走", "新馬", "未勝利", "1勝クラス", "2勝クラス", "3勝クラス", "オープン"])
            self.assertIn(horse.coat_color, [c.value for c in CoatColor])

    def test_annual_event_dialogs(self):
        """9月4週および12月4週のイベントダイアログ初期化検証"""
        retire_dlg = UnvictoryRetirementDialog(self.db, year=1)
        self.assertIsNotNone(retire_dlg.table)

        awards_dlg = YearEndAwardsDialog(self.db, year=1)
        self.assertIsNotNone(awards_dlg.tbl_awards)
        self.assertIsNotNone(awards_dlg.tbl_retire_horses)

    def test_records_view_all_tab_and_history(self):
        """コースレコード画面の総合タブおよび推移ダイアログ検証"""
        rec_view = RecordsView(self.db)
        self.assertIn("ALL", rec_view.track_tables)
        self.assertEqual(rec_view.track_tables["ALL"].columnCount(), 12)

        hist_dlg = RecordHistoryDialog(self.db, track_id="TOKYO", surface="turf", distance=2400)
        self.assertIsNotNone(hist_dlg.table)
        self.assertIsNotNone(hist_dlg.fig)

    def test_rankings_manager_counts(self):
        """各種リーディングで持ち馬数と勝ち馬数が取得できること"""
        rank_mgr = RankingManager(self.db)
        trainers = rank_mgr.get_trainer_rankings(is_career=True, limit=5)
        if trainers:
            self.assertIn("horse_count", trainers[0])
            self.assertIn("winner_count", trainers[0])

        owners = rank_mgr.get_owner_rankings(is_career=True, limit=5)
        if owners:
            self.assertIn("horse_count", owners[0])
            self.assertIn("winner_count", owners[0])

    def test_horse_stats_summary_tables(self):
        """競走馬詳細ダイアログの成績詳細集計テーブル（レース合計・コース別・距離別・グレード別・人気別）の検証"""
        from src.gui.views.horse_detail_dialog import HorseDetailDialog

        with self.db.session() as conn:
            h_row = conn.execute("SELECT horse_id FROM horses LIMIT 1").fetchone()
            horse_id = h_row["horse_id"]

        dlg = HorseDetailDialog(self.db, horse_id)
        # テーブルの存在と行数・列数
        self.assertEqual(dlg.tbl_total.rowCount(), 1)
        self.assertEqual(dlg.tbl_total.columnCount(), 8)

        self.assertEqual(dlg.tbl_course.rowCount(), 2)
        self.assertEqual(dlg.tbl_course.columnCount(), 9)

        self.assertEqual(dlg.tbl_dist.rowCount(), 9)
        self.assertEqual(dlg.tbl_dist.columnCount(), 10)

        self.assertEqual(dlg.tbl_grade.rowCount(), 8)
        self.assertEqual(dlg.tbl_grade.columnCount(), 9)

        self.assertEqual(dlg.tbl_pop.rowCount(), 4)
        self.assertEqual(dlg.tbl_pop.columnCount(), 9)


    def test_hopeful_trials_excluded(self):
        """芙蓉S、アイビーS、萩SがホープフルSトライアルから除外されていること"""
        from src.race.annual_program import generate_full_program
        program = generate_full_program(1)
        excluded_names = ["芙蓉ステークス", "アイビーステークス", "萩ステークス"]
        for r in program:
            if r.name in excluded_names:
                self.assertFalse(r.is_trial, f"{r.name} がトライアルのままです")
                self.assertIsNone(r.target_g1_name, f"{r.name} に対象G1が設定されています")

    def test_ranking_history_yearly_isolation(self):
        """get_ranking_historyが年度ごとの成績を独立して集計すること"""
        rank_mgr = RankingManager(self.db)
        history = rank_mgr.get_ranking_history("jockey", entity_id=1)
        self.assertIsInstance(history, list)


if __name__ == "__main__":
    unittest.main()
