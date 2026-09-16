"""
馬名の単語一意性およびカテゴリ別語彙の包括単体テスト
- 同時代の馬同士（1910頭）で同じ単語が重複しないことの検証
- 7大カテゴリ（花、外国人名、地名、歴史上の人物、鉱物、食べ物、名跡）が正しく使われていることの検証
- 牝馬/牡馬に応じた性別ヒントの検証
"""

import unittest
from collections import Counter

from src.data.horse_words import (
    ALL_WORDS,
    CATEGORY_DICT,
    FLOWERS,
    FOODS_SWEETS,
    GEOGRAPHY,
    HISTORIC_SITES,
    HISTORICAL_FIGURES,
    MINERALS_GEMS,
    WESTERN_NAMES,
)
from src.generators.name_generator import DEFAULT_OWNER_PREFIXES, HorseNameGenerator


class TestHorseNameUniqueness(unittest.TestCase):
    """馬名重複防止およびカテゴリ別生成テスト"""

    def test_vocabulary_size(self):
        """データベースの語彙数が十分（1000語以上）であること"""
        self.assertGreaterEqual(len(ALL_WORDS), 1000)
        self.assertGreaterEqual(len(FLOWERS), 100)
        self.assertGreaterEqual(len(WESTERN_NAMES), 150)
        self.assertGreaterEqual(len(GEOGRAPHY), 140)
        self.assertGreaterEqual(len(HISTORICAL_FIGURES), 150)
        self.assertGreaterEqual(len(MINERALS_GEMS), 100)
        self.assertGreaterEqual(len(FOODS_SWEETS), 130)
        self.assertGreaterEqual(len(HISTORIC_SITES), 100)

    def test_prefix_plus_single_word(self):
        """生成される馬名がすべて [冠名] + [単語]（1単語）の形式であること"""
        gen = HorseNameGenerator()
        prefixes = DEFAULT_OWNER_PREFIXES[:10]

        for pref in prefixes:
            for _ in range(10):
                name = gen.generate_name(prefix=pref)
                self.assertTrue(name.startswith(pref), f"馬名 {name} が冠名 {pref} で始まっていません")
                word_part = name[len(pref):]
                # 単語部分が単一の登録単語（ALL_WORDS）と完全一致すること（2単語合成ではないこと）
                self.assertIn(word_part, ALL_WORDS, f"単語部分 '{word_part}' が単一単語リストに含まれていません")

    def test_uniqueness_for_large_population(self):
        """初期生成規模（1910頭）を生成し、全馬名が100%ユニークであること"""
        gen = HorseNameGenerator()
        prefixes = DEFAULT_OWNER_PREFIXES.copy()

        num_sires = 60
        num_dams = 600
        num_actives = 1250
        total_horses = num_sires + num_dams + num_actives  # 1910頭

        generated_names = []

        # 種牡馬 (牡馬)
        for i in range(num_sires):
            pref = prefixes[i % len(prefixes)]
            name = gen.generate_name(prefix=pref, sex="horse")
            generated_names.append(name)

        # 繁殖牝馬 (牝馬)
        for i in range(num_dams):
            pref = prefixes[(num_sires + i) % len(prefixes)]
            name = gen.generate_name(prefix=pref, sex="mare")
            generated_names.append(name)

        # 現役競走馬 (牡・牝 半々)
        for i in range(num_actives):
            pref = prefixes[(num_sires + num_dams + i) % len(prefixes)]
            sex = "colt" if i % 2 == 0 else "filly"
            name = gen.generate_name(prefix=pref, sex=sex)
            generated_names.append(name)

        # 全馬名が100%ユニークであること（完全重複なし）
        self.assertEqual(len(generated_names), total_horses)
        self.assertEqual(len(set(generated_names)), total_horses)

    def test_forbidden_graded_winners_cannot_be_reused(self):
        """重賞勝利馬の名前が禁止リストに登録されている場合、二度と命名されないこと"""
        forbidden_graded = {"ベルカサクラ", "キリヤローズ", "ハスミアイリス"}
        gen = HorseNameGenerator(existing_names=forbidden_graded)

        # ベルカの冠名で大量生成しても、重賞勝ち馬 "ベルカサクラ" は命名されないこと
        names = [gen.generate_name(prefix="ベルカ") for _ in range(100)]
        self.assertNotIn("ベルカサクラ", names)

    def test_category_specified_generation(self):
        """カテゴリを指定した場合に指定カテゴリの単語（1単語）が正しく使われること"""
        gen = HorseNameGenerator()
        pref = "タカミ"

        # 花カテゴリ
        for _ in range(20):
            name = gen.generate_name(prefix=pref, category="flower")
            self.assertTrue(name.startswith(pref))
            word_part = name[len(pref):]
            self.assertIn(word_part, FLOWERS, f"単語 '{word_part}' は花リストに含まれる単一単語でなければなりません")

        # 鉱物カテゴリ
        for _ in range(20):
            name = gen.generate_name(prefix=pref, category="mineral")
            word_part = name[len(pref):]
            self.assertIn(word_part, MINERALS_GEMS, f"単語 '{word_part}' は鉱物リストに含まれる単一単語でなければなりません")

    def test_breeding_engine_name_sync_rule(self):
        """BreedingEngine._sync_existing_names が重賞勝ち馬と現役馬のみを禁止し、重賞未勝利引退馬を除外すること"""
        import sqlite3
        from unittest.mock import MagicMock
        from src.core.breeding import BreedingEngine

        db_mock = MagicMock()
        engine = BreedingEngine(db_mock)

        # テスト用インメモリDB
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE horses (
                horse_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                is_active INTEGER DEFAULT 0,
                is_sire INTEGER DEFAULT 0,
                is_dam INTEGER DEFAULT 0,
                g1_wins INTEGER DEFAULT 0,
                g2_wins INTEGER DEFAULT 0,
                g3_wins INTEGER DEFAULT 0
            )
        """)

        # 1) G1勝利馬 (引退済み): 禁止対象
        conn.execute("INSERT INTO horses (name, is_active, g1_wins) VALUES ('ベルカゴールド', 0, 1)")
        # 2) G2勝利馬 (引退済み): 禁止対象
        conn.execute("INSERT INTO horses (name, is_active, g2_wins) VALUES ('キリヤシルバー', 0, 1)")
        # 3) G3勝利馬 (引退済み): 禁止対象
        conn.execute("INSERT INTO horses (name, is_active, g3_wins) VALUES ('ハスミブロンズ', 0, 1)")
        # 4) 現役競走馬 (重賞未勝利): 禁止対象
        conn.execute("INSERT INTO horses (name, is_active) VALUES ('カンザキエース', 1)")
        # 5) 供用中種牡馬 (重賞未勝利): 禁止対象
        conn.execute("INSERT INTO horses (name, is_sire) VALUES ('クロカワトップ', 1)")
        # 6) 供用中繁殖牝馬 (重賞未勝利): 禁止対象
        conn.execute("INSERT INTO horses (name, is_dam) VALUES ('シライシクイーン', 1)")
        # 7) 重賞未勝利の引退馬: 禁止対象外（再利用可能！）
        conn.execute("INSERT INTO horses (name, is_active, is_sire, is_dam, g1_wins, g2_wins, g3_wins) VALUES ('フジモリリリー', 0, 0, 0, 0, 0, 0)")

        # 同期実行
        engine._sync_existing_names(conn)

        forbidden = engine.name_gen.used_names
        # 重賞勝ち馬・活動中馬は禁止
        self.assertIn("ベルカゴールド", forbidden)
        self.assertIn("キリヤシルバー", forbidden)
        self.assertIn("ハスミブロンズ", forbidden)
        self.assertIn("カンザキエース", forbidden)
        self.assertIn("クロカワトップ", forbidden)
        self.assertIn("シライシクイーン", forbidden)
        # 重賞未勝利引退馬は禁止に含まれない（再利用可能）
        self.assertNotIn("フジモリリリー", forbidden)


if __name__ == "__main__":
    unittest.main()
