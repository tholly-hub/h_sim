"""
50世代タイム進化検証スクリプト
"""
import math
from src.race.engine import RaceEngine, get_base_time
from src.models.horse import Horse, RunningStyle, GenotypeMSTN, GrowthType
from src.models.race import Race, RaceGrade, RaceSurface
from src.race.track import get_track_info

def verify_50_gen_evolution():
    engine = RaceEngine()
    track = get_track_info("TOKYO")
    race_1600 = Race(
        race_id=1, year=1, month=5, week=20, track_id="TOKYO",
        name="安田記念", grade=RaceGrade.G1, surface=RaceSurface.TURF,
        distance=1600, age_restriction="3yo_up", sex_restriction="mixed"
    )

    print("世代(x) | 期待1F限界タイム (15*x^-0.1035) | 1600m期待タイム | シミュレーション走破タイム (1600m) | 1F換算タイム")
    print("-" * 90)

    # 世代 x = 1 から 50 までの推移
    for gen in [1, 5, 10, 20, 30, 40, 50]:
        # 世代 x におけるトップ層の能力値 (50世代で 58 -> 100 に進化)
        ability = min(100.0, 58.0 + (gen - 1) * (42.0 / 49.0))
        horse = Horse(
            name=f"第{gen}世代トップ馬",
            sex="horse",
            birth_year=gen,
            age=4,
            breeder_id=1,
            owner_id=1,
            mstn_type=GenotypeMSTN.CT,
            speed=ability,
            stamina=ability,
            acceleration=ability,
            temperament=70.0,
            durability=70.0,
            maternal_vitality=70.0,
            growth_type=GrowthType.NORMAL,
            peak_age=4.5,
            running_style=RunningStyle.LEADING,
            current_ability_rate=1.00,
        )

        expected_1f = 15.0 * (gen ** (-0.1035))
        expected_1600 = expected_1f * 8.0

        sim_times = [engine.calculate_finish_time(horse, race_1600, track) for _ in range(50)]
        avg_time = sum(sim_times) / len(sim_times)
        sim_1f = avg_time / 8.0

        print(f" {gen:2d}世代  | {expected_1f:6.2f} 秒/F                | {expected_1600:6.2f} 秒     | {avg_time:6.2f} 秒                   | {sim_1f:6.2f} 秒/F")

if __name__ == "__main__":
    verify_50_gen_evolution()
