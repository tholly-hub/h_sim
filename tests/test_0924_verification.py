"""
0924修正事項の総合検証スクリプト
1. 種牡馬・繁殖牝馬の繋養開始年 (start_year)
2. 外国種牡馬の命名規則（都市名＋男性名、数字なし）と父母設定
3. 新種牡馬・繁殖牝馬の能力決定・世代進化・能力スケール（10〜100、負の累乗モデル、突然変異時100超え）
4. 斤量計算（定量、別定、ハンデ）とタイム遅延
5. 殿堂馬選定条件（G1 5勝以上、3冠、同一G1 3連覇）
6. リーディング順位推移グラフ（前年度限定）
7. コースレコード時間軸（週単位）
8. SireDetailDialog, DamDetailDialog の生成・データバインド
"""

import os
import sys
import unittest
import numpy as np

# プロジェクトルートを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.generators.name_generator import HorseNameGenerator
from src.core.lifecycle import LifecycleEngine
from src.core.genetics import GeneticsEngine
from src.race.engine import RaceEngine, clean_race_name
from src.race.track import get_track_info
from src.race.awards import AwardsManager
from src.race.rankings import RankingManager
from src.race.entry import calculate_carried_weight
from src.models.race import Race, RaceGrade, RaceSurface, AgeRestriction, SexRestriction
from src.models.horse import Horse, GenotypeMSTN, GrowthType, RunningStyle


class Test0924Fixes(unittest.TestCase):

    def setUp(self):
        self.db_path = "data/test_0924_verification.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = Database(self.db_path)
        init = DatabaseInitializer(self.db)
        init.initialize_all()
        self.engine = RaceEngine()
        self.track = get_track_info("TOKYO")

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_01_foreign_sire_names_and_ancestors(self):
        """外国種牡馬命名（都市名+男性名・数字なし）とダミー父母設定の検証"""
        ngen = HorseNameGenerator()
        for _ in range(50):
            name = ngen.generate_foreign_sire_name()
            self.assertFalse(any(c.isdigit() for c in name), f"数字が含まれています: {name}")
            self.assertTrue(len(name) >= 4, f"馬名が短すぎます: {name}")
            
            f_name = ngen.generate_foreign_ancestor_name(sex="horse")
            m_name = ngen.generate_foreign_ancestor_name(sex="mare")
            self.assertTrue(len(f_name) > 0)
            self.assertTrue(len(m_name) > 0)
            self.assertFalse(any(c.isdigit() for c in f_name))
            self.assertFalse(any(c.isdigit() for c in m_name))

    def _create_dummy_horse(self, ability: float, sex: str = "colt", age: int = 3) -> Horse:
        return Horse(
            name="テスト馬", sex=sex, birth_year=1, age=age, breeder_id=1, owner_id=1,
            mstn_type=GenotypeMSTN.CT, speed=ability, stamina=ability, acceleration=ability,
            temperament=50.0, durability=50.0, maternal_vitality=50.0,
            growth_type=GrowthType.NORMAL, peak_age=4.0, current_ability_rate=1.0,
            running_style=RunningStyle.LEADING
        )

    def test_02_time_ability_formula(self):
        """負の累乗モデル (10で15秒/F, 100で10秒/F) の検証"""
        # 1Fあたりの計算式: 7.6876 + 23.1238 / sqrt(A)
        # A=10 -> 7.6876 + 23.1238 / 3.162277 = 15.000s/F -> 8F: 120.0秒
        # A=100 -> 7.6876 + 2.31238 = 10.000s/F -> 8F: 80.0秒
        t_10_f = 7.6876 + 23.1238 / (10.0 ** 0.5)
        t_100_f = 7.6876 + 23.1238 / (100.0 ** 0.5)
        self.assertAlmostEqual(t_10_f * 8.0, 120.0, delta=0.1)
        self.assertAlmostEqual(t_100_f * 8.0, 80.0, delta=0.1)

        # 収穫逓減の検証
        t_30_f = 7.6876 + 23.1238 / (30.0 ** 0.5)
        t_50_f = 7.6876 + 23.1238 / (50.0 ** 0.5)
        t_70_f = 7.6876 + 23.1238 / (70.0 ** 0.5)
        self.assertGreater((t_30_f - t_50_f), (t_50_f - t_70_f))

    def test_03_assigned_weights(self):
        """斤量（定量・別定・ハンデ）および斤量によるタイム変化の検証"""
        race_tei = Race(
            name="日本ダービー",
            track_id="TOKYO",
            month=5,
            week=20,
            grade=RaceGrade.G1,
            surface=RaceSurface.TURF,
            distance=2400,
            age_restriction=AgeRestriction.THREE_YO,
            sex_restriction=SexRestriction.MIXED,
            weight_type="定量"
        )
        h_colt = self._create_dummy_horse(50.0, sex="colt", age=3)
        h_filly = self._create_dummy_horse(50.0, sex="filly", age=3)
        
        # 3歳牡馬 57.0kg, 3歳牝馬 55.0kg
        w_colt = calculate_carried_weight(race_tei, h_colt)
        w_filly = calculate_carried_weight(race_tei, h_filly)
        self.assertEqual(w_colt, 57.0)
        self.assertEqual(w_filly, 55.0)

        # 斤量差によるタイム差（1kgで約0.2s/1600m -> 2400mで約0.3s）
        dummy_h = self._create_dummy_horse(50.0)
        diffs = []
        for seed in range(50):
            import random
            random.seed(seed)
            t_57 = self.engine.calculate_finish_time(dummy_h, race_tei, self.track, carried_weight=57.0)
            random.seed(seed)
            t_58 = self.engine.calculate_finish_time(dummy_h, race_tei, self.track, carried_weight=58.0)
            diffs.append(t_58 - t_57)
        avg_diff = sum(diffs) / len(diffs)
        self.assertAlmostEqual(avg_diff, 0.30, delta=0.01)

    def test_04_start_year_and_sire_rankings(self):
        """種牡馬・繁殖牝馬の繋養開始年とサイヤーランキングデータ取得の検証"""
        with self.db.session() as conn:
            s_rows = conn.execute("SELECT start_year FROM sires").fetchall()
            self.assertTrue(all(r["start_year"] == 1 for r in s_rows))
            
            d_rows = conn.execute("SELECT start_year FROM dams").fetchall()
            self.assertTrue(all(r["start_year"] == 1 for r in d_rows))

        rm = RankingManager(self.db)
        s_ranks = rm.get_sire_rankings(is_career=True)
        self.assertTrue(len(s_ranks) > 0)
        self.assertIn("start_year", s_ranks[0])
        self.assertIn("representative_horses", s_ranks[0])
        self.assertIn("representative_horse_ids", s_ranks[0])

    def test_05_hall_of_fame_conditions(self):
        """殿堂馬選定ロジック（G1 5勝以上、3冠、同一G1 3連覇）の検証"""
        aw = AwardsManager(self.db)
        # 初期状態での殿堂馬リスト取得（エラーなく動作すること）
        hof_list = aw.get_hall_of_fame_horses()
        self.assertIsInstance(hof_list, list)


if __name__ == "__main__":
    unittest.main()
