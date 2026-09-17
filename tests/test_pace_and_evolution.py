import unittest
import numpy as np

from src.models.horse import Horse, GenotypeMSTN, GrowthType, RunningStyle
from src.models.race import Race, RaceSurface, RaceGrade, AgeRestriction
from src.models.jockey import Jockey
from src.models.trainer import Trainer
from src.race.engine import RaceEngine, BASE_TIMES, get_base_time
from src.race.track import get_track_info
from src.core.genetics import GeneticsEngine


class TestPaceAndEvolution(unittest.TestCase):
    """ベースタイム・ペース傾斜および世代能力向上・タイム短縮の検証テスト"""

    def setUp(self):
        self.engine = RaceEngine()

    def test_base_times_and_pace_gradient(self):
        """距離別ペース傾斜（短距離ほど1F速く、長距離ほど1F遅い、1600mで120秒）の確認"""
        # 1600mでちょうど 120.0 秒（1F 15.00秒）
        t1600 = get_base_time(1600)
        self.assertEqual(t1600, 120.0)
        pace1600 = t1600 / (1600 / 200.0)
        self.assertEqual(pace1600, 15.00)

        # 距離リスト
        distances = [1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400, 3000, 3200]
        paces = []
        for d in distances:
            bt = get_base_time(d)
            furlongs = d / 200.0
            pace_per_f = bt / furlongs
            paces.append(pace_per_f)

        # 距離が伸びるにつれて1ハロンあたりのペース（秒数）が単調増加することを確認
        for i in range(len(paces) - 1):
            self.assertLess(
                paces[i],
                paces[i + 1],
                f"距離 {distances[i]}m のペース {paces[i]:.2f}s/F は {distances[i+1]}m のペース {paces[i+1]:.2f}s/F より速くなければなりません"
            )

        print("\n--- 距離別ベースタイム & 1ハロンペース傾斜 ---")
        for d, p in zip(distances, paces):
            bt = get_base_time(d)
            m = int(bt // 60)
            s = bt % 60
            print(f"距離: {d:4d}m | 基準タイム: {m}分{s:04.1f}秒 ({bt:5.1f}s) | 1F平均ペース: {p:.2f}秒/F")

    def test_initial_horse_finish_time_1600m(self):
        """初年度の標準馬（能力50）が走ったときに1600mで約120.0秒となることの確認"""
        horse_50 = Horse(
            horse_id=1,
            name="スタンダード号",
            sex="colt",
            birth_year=1,
            age=3,
            breeder_id=1,
            owner_id=1,
            mstn_type=GenotypeMSTN.CT,
            speed=50.0,
            stamina=50.0,
            acceleration=50.0,
            durability=50.0,
            temperament=50.0,
            maternal_vitality=50.0,
            growth_type=GrowthType.NORMAL,
            peak_age=4.0,
            running_style=RunningStyle.LEADING,
            current_ability_rate=1.0,
        )

        race_1600 = Race(
            race_id=1,
            name="テストマイル",
            track_id="TOKYO",
            month=5,
            week=20,
            grade=RaceGrade.OP,
            surface=RaceSurface.TURF,
            distance=1600,
            age_restriction=AgeRestriction.THREE_YO_UP,
        )
        track = get_track_info("TOKYO")
        jockey_50 = Jockey(
            jockey_id=1,
            name="普通騎手",
            location="美浦",
            age=25,
            debut_year=1,
            skill=50.0,
            drive=50.0,
            experience=50.0,
        )
        trainer_50 = Trainer(
            trainer_id=1,
            name="普通厩舎",
            location="美浦",
            skill_level=50.0,
        )

        # 100回試走して平均と分散を確認
        times = [
            self.engine.calculate_finish_time(
                horse_50, race_1600, track, jockey=jockey_50, trainer=trainer_50
            )
            for _ in range(100)
        ]
        avg_time = float(np.mean(times))
        print(f"\n標準馬(能力50) 1600m走破タイム 100回平均: {avg_time:.2f}秒 (目標: 120.0秒前後)")
        self.assertAlmostEqual(avg_time, 120.0, delta=1.5)

    def test_ability_evolution_shortens_time(self):
        """能力向上に伴うタイム短縮の確認 (50 -> 60 -> 70 -> 80 -> 90)"""
        race_1600 = Race(
            race_id=1,
            name="テストマイル",
            track_id="TOKYO",
            month=5,
            week=20,
            grade=RaceGrade.OP,
            surface=RaceSurface.TURF,
            distance=1600,
            age_restriction=AgeRestriction.THREE_YO_UP,
        )
        track = get_track_info("TOKYO")
        jockey_master = Jockey(
            jockey_id=1,
            name="名手",
            location="栗東",
            age=35,
            debut_year=1,
            skill=80.0,
            drive=80.0,
            experience=90.0,
        )
        trainer_master = Trainer(
            trainer_id=1,
            name="名伯楽",
            location="栗東",
            skill_level=80.0,
        )

        abilities = [50.0, 60.0, 70.0, 80.0, 90.0]
        avg_times = []

        print("\n--- 能力向上による1600m走破タイム短縮推移 ---")
        for ab in abilities:
            h = Horse(
                horse_id=1,
                name=f"能力{int(ab)}号",
                sex="colt",
                birth_year=1,
                age=4,
                breeder_id=1,
                owner_id=1,
                mstn_type=GenotypeMSTN.CT,
                speed=ab,
                stamina=ab,
                acceleration=ab,
                durability=ab,
                temperament=70.0,
                maternal_vitality=ab,
                growth_type=GrowthType.NORMAL,
                peak_age=4.0,
                running_style=RunningStyle.LEADING,
                current_ability_rate=1.0,
            )
            times = [
                self.engine.calculate_finish_time(
                    h, race_1600, track, jockey=jockey_master, trainer=trainer_master
                )
                for _ in range(50)
            ]
            mean_t = float(np.mean(times))
            avg_times.append(mean_t)
            m = int(mean_t // 60)
            s = mean_t % 60
            print(f"能力: {ab:4.1f} | 走破タイム: {m}分{s:04.2f}秒 ({mean_t:5.2f}s)")

        # 能力が上がるにつれてタイムが短縮していること
        for i in range(len(avg_times) - 1):
            self.assertGreater(
                avg_times[i],
                avg_times[i + 1],
                f"能力 {abilities[i]} のタイム {avg_times[i]} は能力 {abilities[i+1]} のタイム {avg_times[i+1]} より遅くなければなりません"
            )

        # 能力90の馬は1分36秒以下（現代級のタイム）に到達していること
        self.assertLess(avg_times[-1], 98.0)

    def test_generational_breeding_progress(self):
        """交配・世代交代による能力向上シミュレーション"""
        # 初代: 平均50.0
        current_sires = [55.0, 56.0, 54.0, 58.0, 57.0]
        current_dams = [52.0, 53.0, 51.0, 55.0, 54.0]

        gen_means = [50.0]
        print("\n--- 世代交配による能力値進化シミュレーション (5世代) ---")
        print("第0世代 (初期集団): 平均能力 50.0")

        for gen in range(1, 6):
            foal_stats = []
            for _ in range(50):
                s = float(np.random.choice(current_sires))
                d = float(np.random.choice(current_dams))
                child_val = GeneticsEngine.calculate_polygenic_stat(s, d)
                foal_stats.append(child_val)

            avg_foal = float(np.mean(foal_stats))
            gen_means.append(avg_foal)
            print(f"第{gen}世代 (産駒50頭): 平均能力 {avg_foal:.1f} (最高: {max(foal_stats):.1f})")

            # 優秀な上位馬を次代の種牡馬・繁殖牝馬に選抜（Selection）
            sorted_foals = sorted(foal_stats, reverse=True)
            current_sires = sorted_foals[:10]
            current_dams = sorted_foals[5:20]

        # 世代を経て能力が向上していること
        self.assertGreater(gen_means[-1], gen_means[0] + 3.0)


if __name__ == "__main__":
    unittest.main()
