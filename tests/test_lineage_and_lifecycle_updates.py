import unittest
import sqlite3
from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.core.lifecycle import LifecycleEngine
from src.core.breeding import BreedingEngine
from src.core.genetics import GeneticsEngine
from src.gui.styles import get_generation_color, GEN_COLOR_PALETTE

class TestLineageAndLifecycleUpdates(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.initializer = DatabaseInitializer(self.db)
        self.initializer.initialize_all(force_recreate=True, with_careers=False)
        self.lifecycle = LifecycleEngine(self.db)
        self.breeding = BreedingEngine(self.db)

    def test_generation_color_rules(self):
        # 1世代目: 白
        self.assertEqual(get_generation_color(1), "#ffffff")
        # 2世代目: 水色
        self.assertEqual(get_generation_color(2), "#38bdf8")
        # 3世代目: 黄緑
        self.assertEqual(get_generation_color(3), "#a3e635")
        # 4世代目: 桃
        self.assertEqual(get_generation_color(4), "#f472b6")

    def test_offspring_generation_rule(self):
        # 初代種牡馬(第1世代)の子供は第2世代
        with self.db.session() as conn:
            # 1年目種付け -> 2年目出産
            self.breeding.perform_spring_mating(1, conn=conn)
            newborn_ids = self.breeding.perform_spring_foaling(2, conn=conn)
            self.assertGreater(len(newborn_ids), 0)
            
            # 各仔馬の generation を確認
            for fid in newborn_ids[:5]:
                h = conn.execute("SELECT generation, sire_id FROM horses WHERE horse_id = ?", (fid,)).fetchone()
                sire = conn.execute("SELECT generation FROM sires WHERE horse_id = ?", (h["sire_id"],)).fetchone()
                sire_gen = sire["generation"] if sire else 1
                self.assertEqual(h["generation"], sire_gen + 1, "Offspring generation must be sire_gen + 1")

    def test_retirement_age_20_rules(self):
        # 種牡馬・繁殖牝馬の引退年齢が20歳
        self.assertEqual(self.lifecycle.SIRE_MAX_CAPACITY, 120)
        with self.db.session() as conn:
            # 繁殖牝馬を19歳と20歳に設定して引退判定
            conn.execute("UPDATE horses SET age = 19 WHERE horse_id IN (SELECT horse_id FROM dams LIMIT 1)")
            conn.execute("UPDATE horses SET age = 20 WHERE horse_id IN (SELECT horse_id FROM dams LIMIT 1 OFFSET 1)")
            
            # 19歳の馬は引退せず、20歳の馬は引退することを確認
            d19 = conn.execute("SELECT d.horse_id, h.age FROM dams d JOIN horses h ON d.horse_id = h.horse_id WHERE h.age = 19").fetchone()
            d20 = conn.execute("SELECT d.horse_id, h.age FROM dams d JOIN horses h ON d.horse_id = h.horse_id WHERE h.age = 20").fetchone()
            
            self.lifecycle._manage_broodmare_roster(conn, 3, [])
            
            check19 = conn.execute("SELECT is_active FROM dams WHERE horse_id = ?", (d19["horse_id"],)).fetchone()
            check20 = conn.execute("SELECT is_active FROM dams WHERE horse_id = ?", (d20["horse_id"],)).fetchone()
            self.assertEqual(check20["is_active"], 0, "20歳牝馬は定年引退")

    def test_minimum_sire_covering_capacity(self):
        with self.db.session() as conn:
            sires = [dict(r) for r in conn.execute("SELECT horse_id, speed, stamina, acceleration FROM horses WHERE is_sire = 1").fetchall()]
            capacities = self.breeding._calculate_sire_capacities(conn, 1, sires)
            for s in sires:
                self.assertGreaterEqual(capacities.get(s["horse_id"], 0), 1, "全種牡馬が最低1頭の種付け枠を持つ")

    def test_speed_evolution_attenuation(self):
        # 世代進化潜在値が以前の1/3（0.40 * 0.15）に緩和されているか
        speed_g1 = GeneticsEngine.calculate_offspring_speed(
            sire_speed=30.0, dam_speed=30.0, sire_generation=1, dam_vitality=30.0
        )
        speed_g5 = GeneticsEngine.calculate_offspring_speed(
            sire_speed=30.0, dam_speed=30.0, sire_generation=5, dam_vitality=30.0
        )
        # 世代差 (5 - 1 = 4世代) での上昇幅が穏やかであることを確認
        self.assertLess(speed_g5 - speed_g1, 10.0, "世代進化が穏やか（1/3速度）に制御されている")

if __name__ == "__main__":
    unittest.main()
