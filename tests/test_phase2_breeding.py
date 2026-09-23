"""
Phase 2: 交配・遺伝・ライフサイクル総合テスト
- 3層遺伝モデル（ポリジーン、MSTN、母系遺伝、インブリード）
- 年間種付け・受胎・当歳誕生（各種牡馬上限30頭厳守、約500頭誕生）
- 年進行・加齢・8歳末引退・2歳デビュー・騎手厩舎世代交代・牧場動的分化保証
"""

import os
import unittest

from src.core.breeding import BreedingEngine
from src.core.genetics import GeneticsEngine
from src.core.lifecycle import LifecycleEngine
from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.models.horse import GenotypeMSTN, GrowthType, RunningStyle


class TestPhase2Breeding(unittest.TestCase):
    """Phase 2 機能の単体・結合テスト"""

    @classmethod
    def setUpClass(cls):
        cls.test_db_path = "data/test_phase2.db"
        cls.db = Database(cls.test_db_path)
        cls.initializer = DatabaseInitializer(cls.db)
        # 初期状態（全頭未出走、親NULL）でDB初期化
        cls.initializer.initialize_all(force_recreate=True)
        cls.breeding_engine = BreedingEngine(cls.db)
        cls.lifecycle_engine = LifecycleEngine(cls.db)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_db_path):
            try:
                os.remove(cls.test_db_path)
            except OSError:
                pass

    def test_1_genetics_engine(self):
        """遺伝エンジンの基本ロジック検証"""
        # 1. MSTN遺伝 (C/C x T/T -> 必ず C/T)
        mstn_res = GeneticsEngine.sample_mstn_offspring(GenotypeMSTN.CC, GenotypeMSTN.TT)
        self.assertEqual(mstn_res, GenotypeMSTN.CT)

        # 2. ポリジーン遺伝
        val = GeneticsEngine.calculate_polygenic_stat(60.0, 60.0)
        self.assertTrue(5.0 <= val <= 95.0)

        # 3. 母系遺伝
        vitality = GeneticsEngine.calculate_maternal_vitality(sire_vitality=40.0, dam_vitality=70.0)
        # 0.7*70 + 0.3*40 = 61.0 近傍
        self.assertTrue(50.0 <= vitality <= 75.0)

        # 4. インブリード計算
        # 同一馬同士の交配（極限テスト）
        dummy_tree = {
            "horse_id": 999, "name": "テスト祖先",
            "sire": {"horse_id": 100, "name": "名馬A", "sire": None, "dam": None},
            "dam": None
        }
        res = GeneticsEngine.calculate_inbreeding(dummy_tree, dummy_tree)
        self.assertGreater(res["total_blood_pct"], 0.0)
        self.assertIn("evaluation_tag", res)

    def test_2_annual_breeding_and_limits(self):
        """交配・当歳馬誕生と種牡馬30頭制限の検証"""
        # Year 1 で交配を実施
        newborn_ids = self.breeding_engine.perform_annual_breeding(current_year=1)
        self.assertEqual(len(newborn_ids), 600, "繁殖牝馬600頭から毎年600頭の当歳馬が誕生している必要があります")

        with self.db.session() as conn:
            # 1. 各種牡馬の種付け頭数が30頭以下であることの検証
            covering_stats = conn.execute(
                """
                SELECT sire_id, COUNT(*) as foal_count
                FROM horses
                WHERE birth_year = 1
                GROUP BY sire_id
                """
            ).fetchall()

            for stat in covering_stats:
                self.assertLessEqual(stat["foal_count"], 30, f"種牡馬 ID {stat['sire_id']} の種付け頭数が30頭を超過しています")

            # 2. 誕生馬の基本属性検証
            sample_foal = conn.execute(
                "SELECT * FROM horses WHERE horse_id = ?", (newborn_ids[0],)
            ).fetchone()
            self.assertEqual(sample_foal["age"], 0)
            self.assertEqual(sample_foal["birth_year"], 1)
            self.assertEqual(sample_foal["career_starts"], 0)
            self.assertIsNotNone(sample_foal["sire_id"])
            self.assertIsNotNone(sample_foal["dam_id"])
            self.assertIsNotNone(sample_foal["breeder_id"])

    def test_3_lifecycle_advance_year(self):
        """年進行・8歳末引退・新馬入厩・世代交代・牧場最低保証の検証"""
        # 1年目を進行 (Year 1 -> Year 2)
        summary = self.lifecycle_engine.advance_year(current_year=1)
        self.assertEqual(summary["advanced_to_year"], 2)

        with self.db.session() as conn:
            # 1. 現役馬の年齢上限（8歳末引退）検証: 9歳以上の現役競走馬がゼロであること
            active_over_age = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE is_active = 1 AND age > 8"
            ).fetchone()[0]
            self.assertEqual(active_over_age, 0, "8歳末で引退し、9歳以上の現役馬は存在してはなりません")

            # 2. 調教師世代交代検証: 80歳以上の現役調教師がゼロであること
            trainers_over_age = conn.execute(
                "SELECT COUNT(*) FROM trainers WHERE age >= 80"
            ).fetchone()[0]
            self.assertEqual(trainers_over_age, 0, "80歳定年で調教師は引退・承継される必要があります")

            # 3. 騎手世代交代検証: 30年超の現役騎手がゼロであること
            jockeys_over_career = conn.execute(
                "SELECT COUNT(*) FROM jockeys WHERE is_active = 1 AND age >= 60"
            ).fetchone()[0]
            self.assertEqual(jockeys_over_career, 0, "騎手は60歳定年で引退する必要があります")

            # 4. 牧場最低保証の検証: 全50牧場に種牡馬1頭以上、繁殖牝馬1頭以上が存在すること
            breeders = conn.execute("SELECT breeder_id FROM breeders").fetchall()
            for b in breeders:
                b_id = b["breeder_id"]
                s_cnt = conn.execute("SELECT COUNT(*) FROM sires WHERE breeder_id = ? AND is_active = 1", (b_id,)).fetchone()[0]
                d_cnt = conn.execute("SELECT COUNT(*) FROM dams WHERE breeder_id = ? AND is_active = 1", (b_id,)).fetchone()[0]
                self.assertGreaterEqual(s_cnt, 1, f"牧場 ID {b_id} の種牡馬が0頭になっています（最低1頭保証違反）")
                self.assertGreaterEqual(d_cnt, 1, f"牧場 ID {b_id} の繁殖牝馬が0頭になっています（最低1頭保証違反）")

    def test_4_repeat_mating_rule(self):
        """同一種牡馬の再種付けルール検証（産駒G1勝利必須＆生涯最大4回上限）"""
        # 1. 単体ロジック検証
        # ケースA: 初回交配 (産駒数0) -> OK
        hist_empty = {}
        self.assertTrue(BreedingEngine.can_mate_sire_and_dam(1, 10, hist_empty))

        # ケースB: 過去1頭産駒あり、G1未勝利 -> NG (再種付け不可)
        hist_no_g1 = {(1, 10): {"foal_count": 1, "has_g1_winner": False}}
        self.assertFalse(BreedingEngine.can_mate_sire_and_dam(1, 10, hist_no_g1))

        # ケースC: 過去産駒あり、G1勝利馬あり、産駒数3頭 -> OK (再種付け可能)
        hist_with_g1 = {(1, 10): {"foal_count": 3, "has_g1_winner": True}}
        self.assertTrue(BreedingEngine.can_mate_sire_and_dam(1, 10, hist_with_g1))

        # ケースD: 過去産駒あり、G1勝利馬あり、産駒数4頭 -> NG (生涯上限4回到達)
        hist_max_reached = {(1, 10): {"foal_count": 4, "has_g1_winner": True}}
        self.assertFalse(BreedingEngine.can_mate_sire_and_dam(1, 10, hist_max_reached))

        # 2. 2年目交配を実行し、G1勝ちのないペアが再種付けされていないことを検証
        newborn_y2 = self.breeding_engine.perform_annual_breeding(current_year=2)
        self.assertGreater(len(newborn_y2), 300)

        with self.db.session() as conn:
            # 1年目と2年目で同一種牡馬×同一繁殖牝馬のペアを調査
            duplicate_matings = conn.execute(
                """
                SELECT dam_id, sire_id, COUNT(*) as foal_count
                FROM horses
                WHERE birth_year IN (1, 2) AND dam_id IS NOT NULL AND sire_id IS NOT NULL
                GROUP BY dam_id, sire_id
                HAVING COUNT(*) > 1
                """
            ).fetchall()

            for dup in duplicate_matings:
                d_id = dup["dam_id"]
                s_id = dup["sire_id"]
                # 1年目の産駒がG1を勝っているか確認
                g1_check = conn.execute(
                    """
                    SELECT MAX(g1_wins) as max_g1
                    FROM horses
                    WHERE dam_id = ? AND sire_id = ? AND birth_year = 1
                    """,
                    (d_id, s_id),
                ).fetchone()
                has_g1 = g1_check["max_g1"] is not None and g1_check["max_g1"] > 0
                self.assertTrue(has_g1, f"dam {d_id} と sire {s_id} の再種付けは産駒G1未勝利のため許可されません")
                self.assertLessEqual(dup["foal_count"], 4, "同一種牡馬との産駒数は生涯最大4頭以下である必要があります")


if __name__ == "__main__":
    unittest.main()

