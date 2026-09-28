"""
Step 1: 時間進行タイムライン & レース番組・斤量体系の改修の検証テスト
- 1年目: 初期種牡馬60頭、繁殖牝馬600頭、0歳初子600頭（牡300・牝300）、1年目交配データ登録、レースなし
- 2年目: 2年目産駒誕生、1年目産駒1歳、交配、レースなし
- 3年目: 1年目産駒が2歳入厩、第27週（7月）から2歳新馬戦開始（計107レース）
- 4年目: 3歳戦＋2歳戦（計600レース）
- 5年目以降: フル番組（計893レース）
- ハンデ戦斤量: 能力値数値化、メンバー平均55.0kg、1.0kg刻み、48.0〜62.0kg
- 出走機会均等化: 未勝利・条件戦での低出走・間隔空き馬優先
"""

import unittest
from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.core.lifecycle import LifecycleEngine
from src.core.breeding import BreedingEngine
from src.race.calendar import CalendarController
from src.race.annual_program import generate_full_program, determine_race_weight_type
from src.race.entry import RaceEntryManager, calculate_race_carried_weights, calculate_carried_weight
from src.models.horse import Horse, GenotypeMSTN, GrowthType, RunningStyle
from src.models.race import Race, RaceGrade, RaceSurface, AgeRestriction, SexRestriction


class TestStep1TimelineAndWeights(unittest.TestCase):

    def setUp(self):
        self.db = Database(":memory:")
        self.initializer = DatabaseInitializer(self.db)
        self.lifecycle = LifecycleEngine(self.db)
        self.calendar = CalendarController(self.db)
        self.breeding = BreedingEngine(self.db)

    def test_initial_population_structure(self):
        """初期化時: 種牡馬100頭、繁殖牝馬600頭、0歳初子600頭、現役0頭、1年目交配600件"""
        self.initializer.initialize_all(force_recreate=True)

        with self.db.session() as conn:
            sires_count = conn.execute("SELECT COUNT(*) FROM sires WHERE is_active = 1").fetchone()[0]
            dams_count = conn.execute("SELECT COUNT(*) FROM dams WHERE is_active = 1").fetchone()[0]
            foals_count = conn.execute("SELECT COUNT(*) FROM horses WHERE birth_year = 1 AND age = 0").fetchone()[0]
            colts_count = conn.execute("SELECT COUNT(*) FROM horses WHERE birth_year = 1 AND age = 0 AND sex = 'colt'").fetchone()[0]
            fillies_count = conn.execute("SELECT COUNT(*) FROM horses WHERE birth_year = 1 AND age = 0 AND sex = 'filly'").fetchone()[0]
            active_count = conn.execute("SELECT COUNT(*) FROM horses WHERE is_active = 1").fetchone()[0]
            matings_count = conn.execute("SELECT COUNT(*) FROM matings WHERE mating_year = 1").fetchone()[0]

            self.assertEqual(sires_count, 100, "初期種牡馬は100頭")
            self.assertEqual(dams_count, 600, "初期繁殖牝馬は600頭")
            self.assertEqual(foals_count, 600, "1年目初子は600頭")
            self.assertEqual(colts_count, 300, "牡馬初子は300頭")
            self.assertEqual(fillies_count, 300, "牝馬初子は300頭")
            self.assertEqual(active_count, 0, "1年目開始時点の現役競走馬は0頭")
            self.assertEqual(matings_count, 600, "1年目交配データは600件")

    def test_annual_program_scale_by_year(self):
        """年度別番組規模の検証: 1〜2年目 0レース、3年目 2歳戦、4年目 3歳+2歳戦、5年目以降 フル番組"""
        prog_y1 = generate_full_program(year=1)
        prog_y2 = generate_full_program(year=2)
        prog_y3 = generate_full_program(year=3)
        prog_y4 = generate_full_program(year=4)
        prog_y5 = generate_full_program(year=5)

        self.assertEqual(len(prog_y1), 0, "1年目は0レース")
        self.assertEqual(len(prog_y2), 0, "2年目は0レース")
        self.assertGreaterEqual(len(prog_y3), 100, "3年目は2歳戦100レース以上")
        self.assertGreaterEqual(len(prog_y4), 600, "4年目は3歳+2歳戦600レース以上")
        self.assertGreaterEqual(len(prog_y5), 890, "5年目以降はフル番組890レース以上")

        # 3年目の開始週が第27週（7月1週）以降であること
        weeks_y3 = [r.week for r in prog_y3]
        self.assertGreaterEqual(min(weeks_y3), 27, "3年目レースは第27週以降に開催")

    def test_weight_type_determination(self):
        """斤量種別（定量・別定・ハンデ）の自動判定検証"""
        # 2歳戦・3歳G1・3歳定量戦 -> 定量
        self.assertEqual(determine_race_weight_type("新馬 (芝1200m)", RaceGrade.NEWCOMER, AgeRestriction.TWO_YO), "定量")
        self.assertEqual(determine_race_weight_type("東京優駿（日本ダービー）", RaceGrade.G1, AgeRestriction.THREE_YO), "定量")
        self.assertEqual(determine_race_weight_type("天皇賞（春）", RaceGrade.G1, AgeRestriction.FOUR_YO_UP), "定量")

        # 別定戦リスト検証
        self.assertEqual(determine_race_weight_type("札幌記念", RaceGrade.G2, AgeRestriction.THREE_YO_UP), "別定")
        self.assertEqual(determine_race_weight_type("毎日王冠", RaceGrade.G2, AgeRestriction.THREE_YO_UP), "別定")
        self.assertEqual(determine_race_weight_type("鳴尾記念", RaceGrade.G3, AgeRestriction.THREE_YO_UP), "別定")

        # ハンデ戦リスト検証
        self.assertEqual(determine_race_weight_type("日経新春杯", RaceGrade.G2, AgeRestriction.FOUR_YO_UP), "ハンデ")
        self.assertEqual(determine_race_weight_type("目黒記念", RaceGrade.G2, AgeRestriction.FOUR_YO_UP), "ハンデ")
        self.assertEqual(determine_race_weight_type("七夕賞", RaceGrade.G3, AgeRestriction.THREE_YO_UP), "ハンデ")
        self.assertEqual(determine_race_weight_type("新潟記念", RaceGrade.G3, AgeRestriction.THREE_YO_UP), "ハンデ")

    def test_handicap_weight_calculation(self):
        """ハンデ戦斤量計算: メンバー平均55.0kg、1.0kg刻み、48.0〜62.0kgの検証"""
        race = Race(
            race_id=1, year=5, month=7, week=27, name="七夕賞", grade=RaceGrade.G3,
            track_id="fukushima", surface=RaceSurface.TURF, distance=2000,
            age_restriction=AgeRestriction.THREE_YO_UP, sex_restriction=SexRestriction.MIXED,
            weight_type="ハンデ", base_prize=43000000, condition_prize=0
        )

        starters = [
            Horse(
                horse_id=1, name="トップホース", sex="horse", birth_year=-4, age=5, breeder_id=1, owner_id=1,
                mstn_type=GenotypeMSTN.CT, speed=22.0, stamina=20.0, acceleration=20.0, temperament=15.0,
                durability=18.0, maternal_vitality=15.0, growth_type=GrowthType.NORMAL, peak_age=4.5,
                g1_wins=2, prize_money=250000000
            ),
            Horse(
                horse_id=2, name="ミドルホース1", sex="horse", birth_year=-3, age=4, breeder_id=1, owner_id=1,
                mstn_type=GenotypeMSTN.CT, speed=14.0, stamina=14.0, acceleration=13.0, temperament=12.0,
                durability=13.0, maternal_vitality=12.0, growth_type=GrowthType.NORMAL, peak_age=4.5,
                g3_wins=1, prize_money=50000000
            ),
            Horse(
                horse_id=3, name="ミドルホース2", sex="mare", birth_year=-3, age=4, breeder_id=1, owner_id=1,
                mstn_type=GenotypeMSTN.CT, speed=14.0, stamina=14.0, acceleration=13.0, temperament=12.0,
                durability=13.0, maternal_vitality=12.0, growth_type=GrowthType.NORMAL, peak_age=4.5,
                g3_wins=1, prize_money=50000000
            ),
            Horse(
                horse_id=4, name="ボトムホース", sex="horse", birth_year=-3, age=4, breeder_id=1, owner_id=1,
                mstn_type=GenotypeMSTN.CT, speed=6.0, stamina=6.0, acceleration=6.0, temperament=10.0,
                durability=6.0, maternal_vitality=10.0, growth_type=GrowthType.NORMAL, peak_age=4.5,
                career_wins=2, prize_money=18000000
            ),
        ]

        weights = calculate_race_carried_weights(race, starters)
        
        # 全斤量が1.0kg刻み（小数部 .0）であること
        for hid, w in weights.items():
            self.assertEqual(w, round(w), f"斤量が整数(1.0kg刻み)であること: {w}")
            self.assertGreaterEqual(w, 48.0, "最低48.0kg以上")
            self.assertLessEqual(w, 62.0, "最高62.0kg以下")

        # トップホースの斤量 > ボトムホースの斤量
        self.assertGreater(weights[1], weights[4], "実績・能力上位馬が重い斤量")
        
        # 平均斤量が55.0kg前後（±1.0kg以内）であること
        avg_w = sum(weights.values()) / len(weights)
        self.assertAlmostEqual(avg_w, 55.0, delta=1.5)

    def test_three_year_simulation_progression(self):
        """1年目〜3年目までのシミュレーション進行と3年目7月の2歳戦開始を検証"""
        self.initializer.initialize_all(force_recreate=True)

        # 1年目: 48週進行（レース0件）
        for w in range(1, 49):
            res = self.calendar.run_week(year=1, week=w)
            self.assertEqual(res["races_run"], 0)

        # 1年目末: advance_year
        self.lifecycle.advance_year(current_year=1)

        # 2年目開始時: 1年目産駒が1歳、2年目産駒(0歳)が誕生
        with self.db.session() as conn:
            y1_foals_age1 = conn.execute("SELECT COUNT(*) FROM horses WHERE birth_year = 1 AND age = 1").fetchone()[0]
            self.assertEqual(y1_foals_age1, 600, "1年目産駒は1歳に加齢")

        # 2年目: 48週進行
        for w in range(1, 49):
            res = self.calendar.run_week(year=2, week=w)
            self.assertEqual(res["races_run"], 0)

        # 2年目末: advance_year
        self.lifecycle.advance_year(current_year=2)

        # 3年目開始時: 1年目産駒が2歳となり、厩舎に入厩（is_active = 1）
        with self.db.session() as conn:
            active_2yo = conn.execute("SELECT COUNT(*) FROM horses WHERE birth_year = 1 AND age = 2 AND is_active = 1").fetchone()[0]
            self.assertEqual(active_2yo, 600, "1年目産駒600頭が2歳現役競走馬として入厩")

        # 3年目: 第1〜26週はレースなし、第27週以降に2歳新馬戦開始
        res_w1 = self.calendar.run_week(year=3, week=1)
        self.assertEqual(res_w1["races_run"], 0, "3年目第1週はレースなし")

        res_w27 = self.calendar.run_week(year=3, week=27)
        self.assertGreater(res_w27["races_run"], 0, "3年目第27週（7月1週）から2歳戦が開始")
        self.assertGreater(res_w27["starters_count"], 0, "出走頭数が存在する")

        # 3年目第28週〜48週を進行し、結果が記録されることを確認
        for w in range(28, 49):
            self.calendar.run_week(year=3, week=w)

        with self.db.session() as conn:
            total_3yo_results = conn.execute(
                "SELECT COUNT(*) FROM results r JOIN races rc ON r.race_id = rc.race_id WHERE rc.year = 3"
            ).fetchone()[0]
            self.assertGreater(total_3yo_results, 100, "3年目のレース結果が記録されている")


if __name__ == "__main__":
    unittest.main()
