"""
Step 4 単体テスト: 世代交代によるタイム短縮ウェイト調整の検証
- 馬自身の成長によるタイム短縮が実競馬並み（マイルで約1.5〜2.5秒）に緩和されていること
- 種牡馬の世代交代・遺伝進化によるスピード向上とタイム短縮効果の検証
"""

import unittest
from src.db.database import Database
from src.models.horse import Horse, GenotypeMSTN, GrowthType, RunningStyle
from src.models.race import Race, RaceGrade, RaceSurface, AgeRestriction, SexRestriction
from src.race.track import TRACK_CONFIGS
from src.race.engine import RaceEngine
from src.core.genetics import GeneticsEngine


class TestStep4TimeAndEvolution(unittest.TestCase):

    def setUp(self):
        self.engine = RaceEngine()
        self.track = TRACK_CONFIGS["TOKYO"]
        self.race = Race(
            race_id=1,
            name="東京芝1600mテスト",
            grade=RaceGrade.G1,
            surface=RaceSurface.TURF,
            distance=1600,
            track_id="TOKYO",
            month=5,
            week=20,
            age_restriction=AgeRestriction.THREE_YO_UP,
            sex_restriction=SexRestriction.MIXED,
        )

    def test_horse_aging_growth_time_difference(self):
        """馬自身の成長（2歳 0.92 vs 古馬 1.00）によるタイム差が約1.5〜2.5秒程度であることの確認"""
        h_2yo = Horse(
            horse_id=1,
            name="テスト若駒2歳",
            sex="colt",
            birth_year=1,
            age=2,
            breeder_id=1,
            owner_id=1,
            mstn_type=GenotypeMSTN.CT,
            speed=20.0,
            stamina=20.0,
            acceleration=20.0,
            temperament=50.0,
            durability=50.0,
            maternal_vitality=50.0,
            growth_type=GrowthType.NORMAL,
            peak_age=4.5,
            running_style=RunningStyle.CLOSING,
            current_ability_rate=0.92,
        )

        h_koba = Horse(
            horse_id=2,
            name="テスト古馬4歳",
            sex="colt",
            birth_year=1,
            age=4,
            breeder_id=1,
            owner_id=1,
            mstn_type=GenotypeMSTN.CT,
            speed=20.0,
            stamina=20.0,
            acceleration=20.0,
            temperament=50.0,
            durability=50.0,
            maternal_vitality=50.0,
            growth_type=GrowthType.NORMAL,
            peak_age=4.5,
            running_style=RunningStyle.CLOSING,
            current_ability_rate=1.00,
        )

        times_2yo = [self.engine.calculate_finish_time(h_2yo, self.race, self.track) for _ in range(50)]
        times_koba = [self.engine.calculate_finish_time(h_koba, self.race, self.track) for _ in range(50)]

        avg_2yo = sum(times_2yo) / len(times_2yo)
        avg_koba = sum(times_koba) / len(times_koba)
        diff = avg_2yo - avg_koba

        # 差が 1.0 秒以上 3.0 秒以内（約1.5〜2.5秒）に収まっていること
        self.assertGreater(diff, 1.0, f"Diff was {diff:.2f}s, expected > 1.0s")
        self.assertLess(diff, 3.0, f"Diff was {diff:.2f}s, expected < 3.0s")

    def test_generation_evolution_impact(self):
        """世代交代（第1世代産駒 vs 第5世代産駒）による能力・タイム向上が大きいことの確認"""
        # 第1世代の種牡馬×繁殖牝馬からの産駒スピード
        spd_gen1 = [
            GeneticsEngine.calculate_offspring_speed(sire_speed=15.0, dam_speed=15.0, sire_generation=1)
            for _ in range(50)
        ]
        avg_spd_gen1 = sum(spd_gen1) / len(spd_gen1)

        # 第5世代の種牡馬×繁殖牝馬からの産駒スピード
        spd_gen5 = [
            GeneticsEngine.calculate_offspring_speed(sire_speed=30.0, dam_speed=25.0, sire_generation=5, dam_g1_wins=1)
            for _ in range(50)
        ]
        avg_spd_gen5 = sum(spd_gen5) / len(spd_gen5)

        self.assertGreater(avg_spd_gen5, avg_spd_gen1 + 10.0, f"Gen5 speed {avg_spd_gen5} should be much higher than Gen1 {avg_spd_gen1}")

        h_gen1 = Horse(
            horse_id=10,
            name="第1世代馬",
            sex="colt",
            birth_year=1,
            age=4,
            breeder_id=1,
            owner_id=1,
            mstn_type=GenotypeMSTN.CT,
            speed=avg_spd_gen1,
            stamina=20.0,
            acceleration=20.0,
            temperament=50.0,
            durability=50.0,
            maternal_vitality=50.0,
            growth_type=GrowthType.NORMAL,
            peak_age=4.5,
            running_style=RunningStyle.CLOSING,
            current_ability_rate=1.00,
        )

        h_gen5 = Horse(
            horse_id=11,
            name="第5世代馬",
            sex="colt",
            birth_year=1,
            age=4,
            breeder_id=1,
            owner_id=1,
            mstn_type=GenotypeMSTN.CT,
            speed=avg_spd_gen5,
            stamina=20.0,
            acceleration=20.0,
            temperament=50.0,
            durability=50.0,
            maternal_vitality=50.0,
            growth_type=GrowthType.NORMAL,
            peak_age=4.5,
            running_style=RunningStyle.CLOSING,
            current_ability_rate=1.00,
        )

        time_gen1 = sum(self.engine.calculate_finish_time(h_gen1, self.race, self.track) for _ in range(50)) / 50.0
        time_gen5 = sum(self.engine.calculate_finish_time(h_gen5, self.race, self.track) for _ in range(50)) / 50.0
        gen_diff = time_gen1 - time_gen5

        # 世代交代によるタイム短縮幅（約4秒）が、加齢成長によるタイム短縮幅（約1.5〜2.5秒）より大幅に大きいこと
        self.assertGreater(gen_diff, 3.0, f"Generation evolution diff was {gen_diff:.2f}s, expected > 3.0s")


if __name__ == "__main__":
    unittest.main()
