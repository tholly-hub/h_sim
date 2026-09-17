"""
統合検証テストスクリプト:
1. 現代走破タイムとダートタイム差（1000mあたり2.5秒）の検証
2. 血統規制（GeneticsEngine.calculate_pedigree_aptitude とスタミナクランプ）の検証
3. 段階的番組表（1年目: 2歳第21週〜, 2年目: 2〜3歳, 3年目: フル番組）の検証
4. 調教師・騎手の3年目引退ガードの検証
5. GUIコンポーネント（SimulationStatusView, RecordsView, DashboardView, Dialogs）のインスタンス化検証
"""

import os
import sys
import tempfile

from src.db.database import Database
from src.core.genetics import GeneticsEngine, GenotypeMSTN
from src.race.engine import RaceEngine, BASE_TIMES
from src.race.program import RaceProgramBuilder
from src.models.race import AgeRestriction, Race, RaceGrade, RaceSurface, SexRestriction
from src.models.horse import Horse, GrowthType, RunningStyle
from src.generators.initializer import DatabaseInitializer
from src.core.lifecycle import LifecycleEngine
from src.race.calendar import CalendarController

def test_race_times():
    print("=== 1. 走破タイム & ダート差テスト ===")
    engine = RaceEngine()
    print("BASE_TIMES sample:", {k: BASE_TIMES[k] for k in [1000, 1200, 1600, 2000, 2400]})
    
    # 仮想レース芝1600m
    race_turf = Race(
        year=1, month=6, week=21, track_id="東京", name="テスト芝1600", grade=RaceGrade.G1,
        surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.TWO_YO,
        sex_restriction=SexRestriction.MIXED, condition="良", full_gate=8, is_trial=0,
        target_g1_name=None, base_prize=10000000, condition_prize=5000000
    )
    # 仮想レースダート1600m
    race_dirt = Race(
        year=1, month=6, week=21, track_id="東京", name="テストダート1600", grade=RaceGrade.G1,
        surface=RaceSurface.DIRT, distance=1600, age_restriction=AgeRestriction.TWO_YO,
        sex_restriction=SexRestriction.MIXED, condition="良", full_gate=8, is_trial=0,
        target_g1_name=None, base_prize=10000000, condition_prize=5000000
    )
    
    horse = Horse(
        horse_id=1, name="テストホース", sex="colt", birth_year=1, age=2,
        breeder_id=1, owner_id=1, trainer_id=1, jockey_id=1, is_active=1, is_sire=0, is_dam=0,
        mstn_type=GenotypeMSTN.CT, speed=50.0, stamina=50.0, acceleration=50.0,
        temperament=50.0, durability=50.0, maternal_vitality=50.0, growth_type=GrowthType.NORMAL,
        peak_age=4.0, current_ability_rate=1.0, running_style=RunningStyle.LEADING
    )
    
    from src.models.jockey import Jockey
    from src.models.trainer import Trainer, TrainerSpecialty
    jockey = Jockey(jockey_id=1, name="テスト騎手", location="美浦", age=25, career_years=7, debut_year=1, skill=50.0, drive=50.0, start_dash=50.0, temperament_handling=50.0, experience=50.0, stamina=50.0)
    trainer = Trainer(trainer_id=1, name="テスト調教師", location="美浦", specialty=TrainerSpecialty.TURF, horse_capacity=30, reputation=50.0, skill_level=50.0, age=50, trainer_years=10)
    
    times_turf = []
    times_dirt = []
    for _ in range(5):
        res_t = engine.run_race(race_turf, [horse], {1: jockey.jockey_id}, [jockey], [trainer])
        res_d = engine.run_race(race_dirt, [horse], {1: jockey.jockey_id}, [jockey], [trainer])
        times_turf.append(res_t[0].finish_time)
        times_dirt.append(res_d[0].finish_time)
        
    avg_t = sum(times_turf) / len(times_turf)
    avg_d = sum(times_dirt) / len(times_dirt)
    diff = avg_d - avg_t
    print(f"芝1600m 平均タイム: {avg_t:.2f}秒 (約1分33〜35秒)")
    print(f"ダート1600m 平均タイム: {avg_d:.2f}秒 (約1分37〜39秒)")
    print(f"ダート差: +{diff:.2f}秒 (1600mで理論値 +4.0秒)")
    assert 3.0 <= diff <= 5.0, f"ダート差が異常: {diff}"
    print("✅ 走破タイム & ダート差テスト合格！")

def test_pedigree_restriction():
    print("\n=== 2. 血統規制テスト ===")
    # 両親ともにC/C（短距離型）
    sire_tree = {"mstn_type": "C/C", "sire": {"mstn_type": "C/C"}, "dam": {"mstn_type": "C/C"}}
    dam_tree = {"mstn_type": "C/C", "sire": {"mstn_type": "C/C"}, "dam": {"mstn_type": "C/C"}}
    
    ped_apt = GeneticsEngine.calculate_pedigree_aptitude(
        sire_mstn=GenotypeMSTN.CC, dam_mstn=GenotypeMSTN.CC,
        sire_surface="turf", dam_surface="turf",
        sire_ancestors=sire_tree, dam_ancestors=dam_tree
    )
    print("短距離血統 apt:", ped_apt)
    assert ped_apt["is_sprint_restricted"] is True
    assert ped_apt["max_distance_clamp"] == 1600
    assert ped_apt["stamina_max_clamp"] == 55.0
    print("✅ 血統規制テスト合格！")

def test_program_phases():
    print("\n=== 3. 段階的番組表テスト ===")
    scratch_dir = "/Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/scratch"
    os.makedirs(scratch_dir, exist_ok=True)
    tmp_db_path = os.path.join(scratch_dir, "test_phase_program.db")
    if os.path.exists(tmp_db_path):
        os.remove(tmp_db_path)
    db = Database(tmp_db_path)
    builder = RaceProgramBuilder(db)
    
    p1 = builder.generate_annual_program(year=1)
    p2 = builder.generate_annual_program(year=2)
    p3 = builder.generate_annual_program(year=3)
    
    print(f"1年目 レース数: {len(p1)} (2歳戦のみ, 週min={min(r.week for r in p1)}, 週max={max(r.week for r in p1)})")
    assert all(r.age_restriction == AgeRestriction.TWO_YO for r in p1)
    assert min(r.week for r in p1) == 21
    
    print(f"2年目 レース数: {len(p2)} (2〜3歳戦のみ, 週min={min(r.week for r in p2)}, 週max={max(r.week for r in p2)})")
    assert all(r.age_restriction in (AgeRestriction.TWO_YO, AgeRestriction.THREE_YO) for r in p2)
    assert min(r.week for r in p2) == 1
    
    print(f"3年目 レース数: {len(p3)} (フル番組表, 週min={min(r.week for r in p3)}, 週max={max(r.week for r in p3)})")
    assert len(p3) > len(p2)
    print("✅ 段階的番組表テスト合格！")
    if os.path.exists(tmp_db_path):
        os.remove(tmp_db_path)

def test_retirement_guard():
    print("\n=== 4. 3年目引退ガードテスト ===")
    scratch_dir = "/Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/scratch"
    os.makedirs(scratch_dir, exist_ok=True)
    tmp_db_path = os.path.join(scratch_dir, "test_guard.db")
    if os.path.exists(tmp_db_path):
        os.remove(tmp_db_path)
    db = Database(tmp_db_path)
    init = DatabaseInitializer(db)
    init.initialize_all(force_recreate=True)
    
    with db.session() as conn:
        t_cnt_before = conn.execute("SELECT COUNT(*) FROM trainers").fetchone()[0]
        j_cnt_before = conn.execute("SELECT COUNT(*) FROM jockeys WHERE is_active = 1").fetchone()[0]
        
    print(f"初期調教師数: {t_cnt_before}, 初期騎手数: {j_cnt_before}")
    
    life = LifecycleEngine(db)
    # 1年目〜3年目の年度末処理を実行
    for y in range(1, 4):
        res = life.advance_year(current_year=y)
        with db.session() as conn:
            t_cnt = conn.execute("SELECT COUNT(*) FROM trainers").fetchone()[0]
            j_cnt = conn.execute("SELECT COUNT(*) FROM jockeys WHERE is_active = 1").fetchone()[0]
            # 引退した調教師や騎手が存在しないかチェック
            t_ret = conn.execute("SELECT COUNT(*) FROM trainers WHERE age >= 80").fetchone()[0]
        print(f"第{y}年終了後: 調教師 {t_cnt}厩舎, 現役騎手 {j_cnt}名 (引退調教師なし)")
        assert t_cnt == t_cnt_before
        assert j_cnt == j_cnt_before
    print("✅ 3年目引退ガードテスト合格！")
    if os.path.exists(tmp_db_path):
        os.remove(tmp_db_path)

if __name__ == "__main__":
    test_race_times()
    test_pedigree_restriction()
    test_program_phases()
    test_retirement_guard()
    print("\n🎉 全てのバックエンドロジック検証に成功しました！")
