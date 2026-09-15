"""
Phase 3 新機能テストスイート
1. 馬名カタカナ完全準拠テスト
2. 騎手名拡充＆女性騎手生成テスト
3. 5代血統表＆HTML出力テスト
4. 競走馬引退定義（8歳以下）＆各種ランキング・代表馬表示テスト
"""

import os
import re
import unittest
from pathlib import Path

from src.data.horse_words import CATEGORY_DICT, ALL_WORDS
from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.generators.name_generator import HorseNameGenerator, PersonNameGenerator
from src.views.pedigree_builder import PedigreeBuilder
from src.views.viewer import HorseViewer


class TestPhase3Features(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_db_path = Path("tests/test_phase3.db")
        if cls.test_db_path.exists():
            cls.test_db_path.unlink()
        cls.db = Database(str(cls.test_db_path))
        cls.initializer = DatabaseInitializer(cls.db)
        cls.initializer.initialize_all(force_recreate=True)
        cls.viewer = HorseViewer(cls.db)

    @classmethod
    def tearDownClass(cls):
        if cls.test_db_path.exists():
            cls.test_db_path.unlink()
        html_path = Path("data/pedigree.html")
        if html_path.exists():
            pass

    def test_1_horse_words_pure_katakana(self):
        """馬名単語辞書がすべて純粋なカタカナのみであることを検証"""
        katakana_pattern = re.compile(r"^[\u30A0-\u30FFー]+$")
        for category, words in CATEGORY_DICT.items():
            for word in words:
                self.assertIsNotNone(
                    katakana_pattern.match(word),
                    f"辞書カテゴリ '{category}' 内にカタカナ以外の単語が含まれています: {word}"
                )

        # 生成器で100頭の名前を生成してもすべてカタカナのみか
        gen = HorseNameGenerator()
        for _ in range(100):
            name = gen.generate_name(prefix="トウカイ")
            self.assertIsNotNone(
                katakana_pattern.match(name),
                f"生成された馬名にカタカナ以外の文字が含まれています: {name}"
            )

    def test_2_female_jockeys_generation(self):
        """女性騎手が美浦・栗東に各5名程度（計10名）生成されていることを検証"""
        with self.db.session() as conn:
            total_jockeys = conn.execute("SELECT COUNT(*) FROM jockeys WHERE is_active = 1").fetchone()[0]
            female_jockeys = conn.execute("SELECT COUNT(*) FROM jockeys WHERE is_active = 1 AND gender = 'female'").fetchone()[0]
            miho_females = conn.execute("SELECT COUNT(*) FROM jockeys WHERE is_active = 1 AND gender = 'female' AND location = '美浦'").fetchone()[0]
            ritto_females = conn.execute("SELECT COUNT(*) FROM jockeys WHERE is_active = 1 AND gender = 'female' AND location = '栗東'").fetchone()[0]

            self.assertEqual(total_jockeys, 90)
            self.assertEqual(female_jockeys, 10)
            self.assertEqual(miho_females, 5)
            self.assertEqual(ritto_females, 5)

    def test_3_five_generation_pedigree(self):
        """現役馬から深さ5の祖先馬ツリーが完全に取得でき、HTMLが出力できることを検証"""
        with self.db.session() as conn:
            # 現役馬を1頭取得
            h_row = conn.execute("SELECT horse_id, name FROM horses WHERE is_active = 1 LIMIT 1").fetchone()
            self.assertIsNotNone(h_row)
            horse_id = h_row["horse_id"]

            builder = PedigreeBuilder(self.db)
            tree = builder.get_ancestors_tree(horse_id, depth=5)
            self.assertIsNotNone(tree)
            self.assertEqual(tree["name"], h_row["name"])

            # 深さ5までのノード数をカウント
            def count_nodes(node, current_depth=1):
                if not node or current_depth > 5:
                    return 0
                cnt = 1
                if "sire" in node and node["sire"]:
                    cnt += count_nodes(node["sire"], current_depth + 1)
                if "dam" in node and node["dam"]:
                    cnt += count_nodes(node["dam"], current_depth + 1)
                return cnt

            total_pedigree_nodes = count_nodes(tree, 1)
            # 初期現役馬は自身(1) + 父(1) + 母(1) = 3ノード（父・母は始祖馬のため親NULL）
            self.assertEqual(total_pedigree_nodes, 3, "初期状態では自身と父・母の3頭が連結されている必要があります")

            # HTML生成テスト
            test_html_path = "tests/test_pedigree.html"
            html_res = builder.build_html(horse_id, test_html_path)
            self.assertTrue(os.path.exists(test_html_path))
            with open(test_html_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn("5代血統表", content)
                self.assertIn(h_row["name"], content)
                self.assertIn("openModal", content)
            if os.path.exists(test_html_path):
                os.remove(test_html_path)

    def test_4_horse_retirement_and_rankings(self):
        """現役馬が8歳以下に限定され、各種ランキング・代表馬が正常に取得できることを検証"""
        with self.db.session() as conn:
            # 現役馬は全て8歳以下
            max_age_active = conn.execute("SELECT MAX(age) FROM horses WHERE is_active = 1").fetchone()[0]
            self.assertLessEqual(max_age_active, 8, "現役馬に9歳以上の馬が存在します")

            # 競走馬ランキング表示確認（エラーなく実行可能か）
            self.assertTrue(self.viewer.show_rankings(category="horse", period="career"))
            self.assertTrue(self.viewer.show_rankings(category="horse", period="annual"))

            # 厩舎ランキング（代表管理馬付き）
            self.assertTrue(self.viewer.show_rankings(category="trainer", period="career"))
            self.assertTrue(self.viewer.show_rankings(category="trainer", period="annual"))

            # 騎手ランキング（性別・代表お手馬付き）
            self.assertTrue(self.viewer.show_rankings(category="jockey", period="career"))
            self.assertTrue(self.viewer.show_rankings(category="jockey", period="annual"))

            # 生産牧場ランキング（代表産駒付き）
            self.assertTrue(self.viewer.show_rankings(category="breeder", period="career"))
            self.assertTrue(self.viewer.show_rankings(category="breeder", period="annual"))


if __name__ == "__main__":
    unittest.main()
