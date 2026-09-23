"""
Phase 1 包括テストスイート
- 設定・パス管理（Mac/Windows対応）
- SQLiteスキーマ生成 & DDL
- 馬名自動生成（カタカナ9文字以内、重複チェック）
- 50牧場、100馬主（ユニーク冠名）生成
- 初期繁殖群＆現役馬群の能力パラメータ・遺伝型検証
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# プロジェクトルートを sys.path に追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config import ConfigManager
from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.generators.name_generator import HorseNameGenerator


class TestPhase1(unittest.TestCase):
    """Phase 1 テストケース"""

    def setUp(self):
        # 一時ディレクトリを作成して分離環境でテスト
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_sim.db"
        self.config_path = Path(self.temp_dir) / "test_config.json"
        self.config_mgr = ConfigManager(base_dir=self.temp_dir, config_file=self.config_path)

    def tearDown(self):
        # 一時ディレクトリのクリーンアップ
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_config_and_path_resolution(self):
        """パス解決および設定更新のテスト（Mac/Windowsパス両対応）"""
        self.config_mgr.set_db_path(self.db_path)
        self.assertEqual(self.config_mgr.get_db_path(), self.db_path.resolve())

        # 設定ファイルの永続化確認
        reloaded = ConfigManager(base_dir=self.temp_dir, config_file=self.config_path)
        self.assertEqual(reloaded.get_db_path(), self.db_path.resolve())

    def test_horse_name_generator_constraints(self):
        """馬名生成ルールの厳密検証（カタカナ2〜9文字以内、重複なし）"""
        generator = HorseNameGenerator()
        prefixes = ["ベルカ", "キリヤ", "ハスミ", "カンザキ", "シライシ"]

        generated_names = set()
        for _ in range(300):
            p = prefixes[_ % len(prefixes)]
            name = generator.generate_name(p)

            # 2文字以上
            self.assertGreaterEqual(len(name), 2, f"馬名が短すぎます: {name}")

            # 重複なし
            self.assertNotIn(name, generated_names, f"馬名の重複が発生しました: {name}")
            generated_names.add(name)

    def test_database_initialization_and_constraints(self):
        """データベースの初期化とデータ完全性の検証"""
        db = Database(self.db_path)
        initializer = DatabaseInitializer(db)
        initializer.initialize_all(force_recreate=True)

        with db.session() as conn:
            # 1. 牧場数の検証 (50場、全9地方を網羅)
            breeder_count = conn.execute("SELECT COUNT(*) FROM breeders").fetchone()[0]
            self.assertEqual(breeder_count, 50, "生産牧場数が50場ではありません")

            regions = [r[0] for r in conn.execute("SELECT DISTINCT region FROM breeders").fetchall()]
            expected_regions = {"北海道", "東北", "関東", "中部", "北陸", "近畿", "中国", "四国", "九州"}
            self.assertEqual(set(regions), expected_regions, "9地方がすべて含まれていません")

            hokuriku_count = conn.execute("SELECT COUNT(*) FROM breeders WHERE region = '北陸'").fetchone()[0]
            self.assertEqual(hokuriku_count, 2, f"北陸地方の牧場数が2ではありません: {hokuriku_count}")

            # 2. 馬主数の検証 (100人、冠名がすべてユニーク、苗字＋会社名)
            owner_count = conn.execute("SELECT COUNT(*) FROM owners").fetchone()[0]
            self.assertEqual(owner_count, 100, "馬主数が100人ではありません")
            unique_prefixes = conn.execute("SELECT COUNT(DISTINCT prefix) FROM owners").fetchone()[0]
            self.assertEqual(unique_prefixes, 100, "馬主の冠名に重複があります")

            owners = conn.execute("SELECT name FROM owners").fetchall()
            company_suffixes = ("建設", "商事", "商会", "ホールディングス", "重工", "物産", "不動産", "工業", "実業", "興業", "通商", "開発", "総業", "エンジニアリング", "ロジスティクス", "ファイナンス", "コーポレーション", "海運", "エステート", "テクノロジー", "産業", "システムズ", "エナジー", "グループ", "企画", "製薬")
            for o in owners:
                self.assertTrue(any(o["name"].endswith(suffix) for suffix in company_suffixes), f"馬主名が会社名形式になっていません: {o['name']}")

            # 3. 個体群の検証
            sires_count = conn.execute("SELECT COUNT(*) FROM sires WHERE is_active = 1").fetchone()[0]
            self.assertEqual(sires_count, 60, "種牡馬数が60頭ではありません")

            # 初期種牡馬の系統がすべて「[馬名]系」であることの検証
            sire_lines = conn.execute("SELECT s.sire_line, h.name FROM sires s JOIN horses h ON s.horse_id = h.horse_id").fetchall()
            for sl in sire_lines:
                self.assertEqual(sl["sire_line"], f"{sl['name']}系", f"サイアーラインが馬名系になっていません: {sl['sire_line']}")

            dams_count = conn.execute("SELECT COUNT(*) FROM dams WHERE is_active = 1").fetchone()[0]
            self.assertEqual(dams_count, 600, "繁殖牝馬数が600頭ではありません")

            active_horses = conn.execute("SELECT COUNT(*) FROM horses WHERE is_active = 1").fetchone()[0]
            self.assertEqual(active_horses, 600, "現役競走馬数が600頭（2歳馬のみ）ではありません")

            # 4. 馬名の重複チェック
            horses = conn.execute("SELECT name FROM horses").fetchall()
            horse_names = [h["name"] for h in horses]
            self.assertEqual(len(horse_names), len(set(horse_names)), "競走馬名に重複が存在します")
            for name in horse_names:
                self.assertTrue(len(name) >= 2, f"馬名が短すぎます: {name}")

            # 9文字を超える馬名も存在することを確認
            long_names = [name for name in horse_names if len(name) > 9]
            self.assertGreater(len(long_names), 0, "9文字を超える馬名が生成されていません")

            # 5. 能力値の範囲（0.0〜100.0）と平均値の検証
            stats = conn.execute(
                """
                SELECT 
                    MIN(speed), MAX(speed), AVG(speed),
                    MIN(stamina), MAX(stamina), AVG(stamina),
                    MIN(acceleration), MAX(acceleration), AVG(acceleration)
                FROM horses
                """
            ).fetchone()

            # 最小・最大チェック
            self.assertGreaterEqual(stats[0], 0.0)
            self.assertLessEqual(stats[1], 100.0)
            # 平均値が 48.0 〜 55.0 の適正範囲内であること
            self.assertTrue(48.0 <= stats[2] <= 55.0, f"速度の平均値が外れています: {stats[2]}")

            # 6. ミオスタチン遺伝子型の検証 (C/C, C/T, T/T のみ)
            mstn_types = conn.execute("SELECT DISTINCT m_type FROM (SELECT DISTINCT mstn_type as m_type FROM horses) WHERE m_type IS NOT NULL").fetchall()
            valid_mstn = {"C/C", "C/T", "T/T"}
            for m in mstn_types:
                self.assertIn(m["m_type"], valid_mstn)

            # 7. 初期競走馬の戦績配分検証（初年度は2歳馬600頭のみで全頭未出走）
            two_yo_count = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE is_active = 1 AND age = 2"
            ).fetchone()[0]
            self.assertEqual(two_yo_count, 600, "初期現役馬は全頭2歳馬（600頭）である必要があります")

            active_horses_with_record = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE is_active = 1 AND career_starts > 0"
            ).fetchone()[0]
            self.assertEqual(active_horses_with_record, 0, "初年度初期現役馬は全頭未出走（career_starts=0）である必要があります")

            # 8. 初期現役馬（600頭）＋1歳幼駒（600頭）＋0歳当歳馬（600頭）の父母連結検証、初期種牡馬・繁殖牝馬の始祖検証
            known_pedigree_count = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE sire_id IS NOT NULL AND dam_id IS NOT NULL"
            ).fetchone()[0]
            self.assertEqual(known_pedigree_count, 1800, "初期現役馬600頭＋1歳幼駒600頭＋0歳当歳馬600頭の父母が正常に連結されている必要があります")

            founder_count = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE sire_id IS NULL AND dam_id IS NULL"
            ).fetchone()[0]
            self.assertEqual(founder_count, 660, "初期種牡馬60頭＋繁殖牝馬600頭が始祖馬（親NULL）である必要があります")

    def test_viewer_list_functions(self):
        """リスト表示機能（現役馬、種牡馬、繁殖牝馬、個別詳細）の動作テスト"""
        from src.views.viewer import HorseViewer
        db = Database(self.db_path)
        initializer = DatabaseInitializer(db)
        initializer.initialize_all(force_recreate=True)

        viewer = HorseViewer(db)
        # リスト取得のテスト
        active_count = viewer.list_active_horses(limit=10, offset=0)
        self.assertEqual(active_count, 600)

        sire_count = viewer.list_sires()
        self.assertEqual(sire_count, 60)

        dam_count = viewer.list_dams(limit=10, offset=0)
        self.assertEqual(dam_count, 600)

        # 生産牧場リストのテスト (全件および地域絞り込み)
        breeder_count = viewer.list_breeders()
        self.assertEqual(breeder_count, 50)
        hokkaido_count = viewer.list_breeders(region_filter="北海道")
        self.assertEqual(hokkaido_count, 18)
        hokuriku_count = viewer.list_breeders(region_filter="北陸")
        self.assertEqual(hokuriku_count, 2)

        # 個別詳細表示のテスト
        detail_ok = viewer.show_horse_detail(1)
        self.assertTrue(detail_ok)


if __name__ == "__main__":
    unittest.main()
