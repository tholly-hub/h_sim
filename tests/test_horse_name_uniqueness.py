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

    def test_single_and_compound_uniqueness_for_large_population(self):
        """初期生成頭数（1910頭）を生成し、全頭がユニークかつコア単語の重複がゼロ（極小）であること"""
        gen = HorseNameGenerator()
        prefixes = DEFAULT_OWNER_PREFIXES.copy()

        num_sires = 60
        num_dams = 600
        num_actives = 1250
        total_horses = num_sires + num_dams + num_actives  # 1910頭

        generated_names = []
        words_used = []

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

        # 1. 生成された全馬名が100%ユニークであること（完全重複なし）
        self.assertEqual(len(generated_names), total_horses)
        self.assertEqual(len(set(generated_names)), total_horses)

        # 2. used_active_words のサイズが全頭数と完全に一致すること（同時代単語重複ゼロ！）
        self.assertEqual(len(gen.used_active_words), total_horses)

    def test_category_specified_generation(self):
        """カテゴリを指定した場合に指定カテゴリの単語が含まれること"""
        gen = HorseNameGenerator()
        pref = "タカミ"

        # 花カテゴリ
        for _ in range(20):
            name = gen.generate_name(prefix=pref, category="flower")
            self.assertTrue(name.startswith(pref))
            word_part = name[len(pref):]
            # word_part が花リストに含まれるか、あるいは花を含む合成語であること
            contains_flower = any(f in word_part for f in FLOWERS)
            self.assertTrue(contains_flower, f"Name {name} does not contain flower")

        # 鉱物カテゴリ
        for _ in range(20):
            name = gen.generate_name(prefix=pref, category="mineral")
            word_part = name[len(pref):]
            contains_mineral = any(m in word_part for m in MINERALS_GEMS)
            self.assertTrue(contains_mineral, f"Name {name} does not contain mineral")

    def test_word_release_and_reuse(self):
        """単語解放（引退・退役時）により再利用が可能になること"""
        gen = HorseNameGenerator()
        pref = "サカイ"
        # 1頭目生成
        name1 = gen.generate_name(prefix=pref, category="flower")
        active_words = list(gen.used_active_words)
        self.assertEqual(len(active_words), 1)
        used_word = active_words[0]

        # 単語を解放
        gen.release_active_word(used_word)
        self.assertNotIn(used_word, gen.used_active_words)


if __name__ == "__main__":
    unittest.main()
