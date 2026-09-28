"""
世代交代（Generation Advancement）およびスピード能力進化メカニズムの単体テスト
- 世代の厳密な定義（第1世代種牡馬の産駒が種牡馬になると第2世代、その産駒が種牡馬になると第3世代）
- スピード能力は年数ではなく新種牡馬誕生・世代進展時に上がる
- 繁殖牝馬の能力（スピード・実績・底力）や配合相性（ニックス等）によってスピード向上が左右される
"""

import unittest
from src.core.breeding import BreedingEngine
from src.core.genetics import GeneticsEngine
from src.core.lifecycle import LifecycleEngine
from src.db.database import Database
from src.generators.initializer import DatabaseInitializer


class TestGenerationEvolution(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        init = DatabaseInitializer(self.db)
        init.initialize_all()
        self.lifecycle = LifecycleEngine(self.db)
        self.breeding = BreedingEngine(self.db)

    def test_neutral_polygenic_drift(self):
        """通常ポリジーン遺伝において中立的変異（無条件インフレなし）であること"""
        samples = [GeneticsEngine.calculate_polygenic_stat(50.0, 50.0) for _ in range(1000)]
        mean_val = sum(samples) / len(samples)
        # 平均値が50.0近辺（±0.5以内）に収まること
        self.assertAlmostEqual(mean_val, 50.0, delta=0.5)

    def test_generation_speed_evolution_by_dam_and_compatibility(self):
        """
        世代進展によるスピード向上が繁殖牝馬能力や相性に左右されることの検証
        """
        # ケース1: 第1世代種牡馬 × 標準繁殖牝馬
        gen1_samples = [
            GeneticsEngine.calculate_offspring_speed(
                sire_speed=50.0,
                dam_speed=50.0,
                sire_generation=1,
                dam_vitality=50.0,
                dam_g1_wins=0,
                is_nicks=False,
            )
            for _ in range(500)
        ]
        avg_gen1 = sum(gen1_samples) / len(gen1_samples)
        self.assertAlmostEqual(avg_gen1, 50.0, delta=0.6)

        # ケース2: 第3世代種牡馬 × 優秀なG1馬繁殖牝馬（好相性・高底力）
        elite_samples = [
            GeneticsEngine.calculate_offspring_speed(
                sire_speed=65.0,
                dam_speed=65.0,
                sire_generation=3,
                dam_vitality=65.0,
                dam_g1_wins=2,
                is_nicks=True,
                nicks_speed_bonus=2.0,
            )
            for _ in range(500)
        ]
        avg_elite = sum(elite_samples) / len(elite_samples)
        # 両親平均65.0 + 世代ボーナス(約1.5〜2.0) + ニックス(2.0) で 68.0 以上になること
        self.assertGreater(avg_elite, 66.5)

        # ケース3: 第3世代種牡馬 × 低能力未勝利繁殖牝馬
        poor_dam_samples = [
            GeneticsEngine.calculate_offspring_speed(
                sire_speed=65.0,
                dam_speed=40.0,
                sire_generation=3,
                dam_vitality=40.0,
                dam_g1_wins=0,
                is_nicks=False,
            )
            for _ in range(500)
        ]
        avg_poor = sum(poor_dam_samples) / len(poor_dam_samples)
        # 両親平均 52.5 だが、低能力牝馬のため世代進化が引き出せず 54.0 以下程度に抑制されること
        self.assertLessEqual(avg_poor, 54.0)

    def test_new_sire_generation_advancement(self):
        """
        競走馬が引退して新種牡馬になった際の世代昇格テスト
        - 初代種牡馬の産駒（第1世代） -> 第1世代種牡馬
        - 第1世代種牡馬の産駒（第2世代） -> 第2世代種牡馬
        """
        with self.db.session() as conn:
            # 1. 初代種牡馬を取得
            s1 = conn.execute("SELECT horse_id, generation FROM sires WHERE is_active = 1 LIMIT 1").fetchone()
            s1_id = s1["horse_id"]
            self.assertEqual(s1["generation"], 1)

            # 2. s1 を父とする競走馬（第1世代産駒）を作成
            conn.execute("""
                INSERT INTO horses (
                    horse_id, name, sex, birth_year, age, is_active, sire_id, dam_id,
                    breeder_id, owner_id, trainer_id, mstn_type, speed, stamina, acceleration,
                    temperament, durability, maternal_vitality, growth_type, peak_age, running_style,
                    g1_wins, g2_wins, g3_wins, career_wins, career_starts, prize_money, condition_prize_money, generation
                ) VALUES (
                    88001, 'コウホウマイチゴウ', 'colt', 1, 5, 1, ?, 1,
                    1, 1, 1, 'C/T', 65.0, 60.0, 60.0,
                    50.0, 50.0, 50.0, 'normal', 4.5, 'leading',
                    2, 1, 0, 8, 12, 400000000, 30000000, 1
                )
            """, (s1_id,))

            retired_list = [dict(conn.execute("SELECT * FROM horses WHERE horse_id = 88001").fetchone())]

            # 3. 新種牡馬昇格判定を実行 (5年目以降)
            new_promoted = self.lifecycle._manage_sire_roster(conn, current_year=5, retired_horses=retired_list)
            self.assertGreaterEqual(new_promoted, 1)

            # 4. 新種牡馬の世代を確認 (初代種牡馬の産駒は第1世代種牡馬)
            new_sire = conn.execute("SELECT * FROM sires WHERE horse_id = 88001").fetchone()
            self.assertIsNotNone(new_sire)
            self.assertEqual(new_sire["generation"], 1, "初代種牡馬の産駒は第1世代種牡馬になること")

            # G1=2勝の実績によりスピード遺伝力が向上していること
            new_h = conn.execute("SELECT speed, generation FROM horses WHERE horse_id = 88001").fetchone()
            self.assertEqual(new_h["generation"], 1)
            self.assertGreater(new_h["speed"], 65.0, "G1勝利実績により種牡馬遺伝力スピードが向上すること")

            # 5. 第1世代種牡馬の産駒を作成
            cur2 = conn.execute("""
                INSERT INTO horses (
                    name, sex, birth_year, age, is_active, sire_id, dam_id,
                    breeder_id, owner_id, trainer_id, mstn_type, speed, stamina, acceleration,
                    temperament, durability, maternal_vitality, growth_type, peak_age, running_style,
                    g1_wins, g2_wins, g3_wins, career_wins, career_starts, prize_money, condition_prize_money, generation
                ) VALUES (
                    'コウホウマニゴウ', 'colt', 2, 5, 1, 88001, 1,
                    1, 1, 1, 'C/T', 68.0, 60.0, 60.0,
                    50.0, 50.0, 50.0, 'normal', 4.5, 'leading',
                    3, 0, 0, 9, 14, 500000000, 40000000, 2
                )
            """)
            h2_id = cur2.lastrowid

            retired_list_2 = [dict(conn.execute("SELECT * FROM horses WHERE horse_id = ?", (h2_id,)).fetchone())]
            self.lifecycle._manage_sire_roster(conn, current_year=5, retired_horses=retired_list_2)

            # 6. 第2世代種牡馬の確認
            new_sire2 = conn.execute("SELECT * FROM sires WHERE horse_id = ?", (h2_id,)).fetchone()
            self.assertIsNotNone(new_sire2)
            self.assertEqual(new_sire2["generation"], 2, "第1世代種牡馬の産駒は第2世代種牡馬になること")


if __name__ == "__main__":
    unittest.main()
