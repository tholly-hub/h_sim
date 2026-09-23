"""
レース出走条件（レース間隔・未勝利馬特例・G1勝利馬のG3/L出走制限・トライアル間隔）テスト
"""

import unittest
from src.db.database import Database
from src.models.horse import GenotypeMSTN, GrowthType, Horse, RunningStyle
from src.models.race import AgeRestriction, Race, RaceGrade, RaceSurface, SexRestriction
from src.race.annual_program import generate_full_program
from src.race.entry import RaceEntryManager, normalize_g1_name


class TestRaceEntryRules(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.db.initialize_schema()
        self.entry_mgr = RaceEntryManager(self.db)

    def _create_dummy_horse(self, career_wins: int = 0, g1_wins: int = 0, age: int = 4) -> Horse:
        return Horse(
            name="テストホース",
            sex="colt",
            birth_year=1,
            age=age,
            breeder_id=1,
            owner_id=1,
            mstn_type=GenotypeMSTN.CT,
            speed=60.0,
            stamina=60.0,
            acceleration=60.0,
            temperament=60.0,
            durability=60.0,
            maternal_vitality=60.0,
            growth_type=GrowthType.NORMAL,
            peak_age=4.5,
            career_starts=career_wins + 2,
            career_wins=career_wins,
            g1_wins=g1_wins,
            horse_id=1,
        )

    def _create_dummy_race(self, grade: RaceGrade, week: int = 10, is_trial: int = 0, target_g1: str = None) -> Race:
        return Race(
            name="テストレース",
            track_id="TOKYO",
            month=(week - 1) // 4 + 1,
            week=week,
            grade=grade,
            surface=RaceSurface.TURF,
            distance=2000,
            age_restriction=AgeRestriction.FOUR_YO_UP,
            sex_restriction=SexRestriction.MIXED,
            full_gate=8,
            is_trial=is_trial,
            target_g1_name=target_g1,
            base_prize=10_000_000,
            condition_prize=5_000_000,
            year=1,
        )

    def test_maiden_race_interval_rule(self):
        """未勝利馬（0勝馬）は中3週（間隔4週以上）で出走可能、4週未満は出走不可"""
        maiden_horse = self._create_dummy_horse(career_wins=0, g1_wins=0, age=3)
        race = Race(
            name="3歳未勝利",
            track_id="TOKYO",
            month=3,
            week=10,
            grade=RaceGrade.MAIDEN,
            surface=RaceSurface.TURF,
            distance=1800,
            age_restriction=AgeRestriction.THREE_YO,
            sex_restriction=SexRestriction.MIXED,
            year=1,
        )

        # 1. 中3週 (前走第6週 -> 今走第10週: 差4週) -> 出走可能
        self.assertTrue(self.entry_mgr.can_enter_race(maiden_horse, race, last_run=(1, 6)))

        # 2. 中2週以下 (前走第7週 -> 今走第10週: 差3週) -> 出走不可
        self.assertFalse(self.entry_mgr.can_enter_race(maiden_horse, race, last_run=(1, 7)))

        # 3. 中4週 (前走第5週 -> 今走第10週: 差5週) -> 出走可能
        self.assertTrue(self.entry_mgr.can_enter_race(maiden_horse, race, last_run=(1, 5)))

    def test_winner_race_interval_rule(self):
        """勝利経験馬（1勝以上）は中4週（間隔5週以上）で出走可能、5週未満（中3週以下）は出走不可"""
        winner_horse = self._create_dummy_horse(career_wins=3, g1_wins=0, age=4)
        race = self._create_dummy_race(RaceGrade.COND_3W, week=10)

        # 1. 中4週 (前走第5週 -> 今走第10週: 差5週) -> 出走可能
        self.assertTrue(self.entry_mgr.can_enter_race(winner_horse, race, last_run=(1, 5)))

        # 2. 中3週 (前走第6週 -> 今走第10週: 差4週) -> 出走不可
        self.assertFalse(self.entry_mgr.can_enter_race(winner_horse, race, last_run=(1, 6)))

        # 3. 中2週 (前走第7週 -> 今走第10週: 差3週) -> 出走不可
        self.assertFalse(self.entry_mgr.can_enter_race(winner_horse, race, last_run=(1, 7)))

        # 4. 年をまたいだ中4週 (前年第44週 -> 当年第1週: 差5週) -> 出走可能
        race_y2_w1 = self._create_dummy_race(RaceGrade.COND_3W, week=1)
        race_y2_w1.year = 2
        self.assertTrue(self.entry_mgr.can_enter_race(winner_horse, race_y2_w1, last_run=(1, 44)))

        # 5. 年をまたいだ中3週 (前年第45週 -> 当年第1週: 差4週) -> 出走不可
        self.assertFalse(self.entry_mgr.can_enter_race(winner_horse, race_y2_w1, last_run=(1, 45)))

    def test_g1_winner_restriction_on_g3_and_listed(self):
        """G1勝利馬はG3およびリステッドに出走不可。ただしトライアル競走なら出走可能"""
        g1_winner = self._create_dummy_horse(career_wins=5, g1_wins=1, age=4)
        non_g1_horse = self._create_dummy_horse(career_wins=4, g1_wins=0, age=4)

        # 通常のG3レース
        g3_normal = self._create_dummy_race(RaceGrade.G3, week=10, is_trial=0)
        # G3トライアルレース
        g3_trial = self._create_dummy_race(RaceGrade.G3, week=10, is_trial=1, target_g1="安田記念")
        # 通常のリステッドレース
        l_normal = self._create_dummy_race(RaceGrade.L, week=10, is_trial=0)
        # リステッドトライアルレース
        l_trial = self._create_dummy_race(RaceGrade.L, week=10, is_trial=1, target_g1="安田記念")
        # G2レース (制限対象外)
        g2_race = self._create_dummy_race(RaceGrade.G2, week=10, is_trial=0)
        # G1レース (制限対象外)
        g1_race = self._create_dummy_race(RaceGrade.G1, week=10, is_trial=0)

        # G1勝利馬のテスト
        self.assertFalse(self.entry_mgr.can_enter_race(g1_winner, g3_normal))
        self.assertTrue(self.entry_mgr.can_enter_race(g1_winner, g3_trial))
        self.assertFalse(self.entry_mgr.can_enter_race(g1_winner, l_normal))
        self.assertTrue(self.entry_mgr.can_enter_race(g1_winner, l_trial))
        self.assertTrue(self.entry_mgr.can_enter_race(g1_winner, g2_race))
        self.assertTrue(self.entry_mgr.can_enter_race(g1_winner, g1_race))

        # G1未勝利馬のテスト（通常G3やリステッドにも出走可能）
        self.assertTrue(self.entry_mgr.can_enter_race(non_g1_horse, g3_normal))
        self.assertTrue(self.entry_mgr.can_enter_race(non_g1_horse, l_normal))

    def test_annual_program_trial_intervals(self):
        """全トライアル競走と対象G1の開催週の間隔が最低5週（中4週以上）空いていることを検証"""
        races = generate_full_program(1)
        g1_races = {normalize_g1_name(r.name): r for r in races if r.grade.value == "G1"}
        trials = [r for r in races if r.is_trial]

        self.assertGreater(len(trials), 0)
        for t in trials:
            target_norm = normalize_g1_name(t.target_g1_name)
            self.assertIn(
                target_norm,
                g1_races,
                f"トライアル競走 {t.name} の対象G1 ({t.target_g1_name}) が番組表に見つかりません",
            )
            g1 = g1_races[target_norm]
            diff = g1.week - t.week
            self.assertGreaterEqual(
                diff,
                5,
                f"トライアル競走 {t.name} (第{t.week}週) と 対象G1 {g1.name} (第{g1.week}週) の間隔が {diff}週（中{diff-1}週）しかありません（最低中4週=5週必要）",
            )

    def test_2yo_open_entry_rule(self):
        """2歳馬は1勝以上していればオープンレース（G1/G2/G3/L/OP）に出走可能、0勝馬は出走不可"""
        h_2yo_0win = self._create_dummy_horse(career_wins=0, age=2)
        h_2yo_1win = self._create_dummy_horse(career_wins=1, age=2)
        h_2yo_2win = self._create_dummy_horse(career_wins=2, age=2)

        open_grades = [RaceGrade.G1, RaceGrade.G2, RaceGrade.G3, RaceGrade.L, RaceGrade.OP]
        for grade in open_grades:
            race_2yo = Race(
                name=f"2歳{grade.value}テスト",
                track_id="TOKYO",
                month=10,
                week=40,
                grade=grade,
                surface=RaceSurface.TURF,
                distance=1600,
                age_restriction=AgeRestriction.TWO_YO,
                sex_restriction=SexRestriction.MIXED,
                year=1,
            )
            # 0勝馬は出走不可
            self.assertFalse(
                self.entry_mgr.can_enter_race(h_2yo_0win, race_2yo),
                f"2歳0勝馬が {grade.value} レースに出走できてしまっています",
            )
            # 1勝馬は出走可能
            self.assertTrue(
                self.entry_mgr.can_enter_race(h_2yo_1win, race_2yo),
                f"2歳1勝馬が {grade.value} レースに出走できません",
            )
            # 2勝馬も出走可能
            self.assertTrue(
                self.entry_mgr.can_enter_race(h_2yo_2win, race_2yo),
                f"2歳2勝馬が {grade.value} レースに出走できません",
            )

    def test_3yo_open_entry_rule_spring_and_later(self):
        """3歳馬は5月4週（第20週）までは1勝クラス（1勝以上）でオープンに出走可能。第21週以降は1勝馬は出走不可"""
        h_3yo_0win = self._create_dummy_horse(career_wins=0, age=3)
        h_3yo_1win = self._create_dummy_horse(career_wins=1, age=3)
        h_3yo_4win = self._create_dummy_horse(career_wins=4, age=3)

        # 5月4週（week 20: 皐月賞・ダービー等の春競馬期間）
        race_spring_g2 = Race(
            name="弥生賞",
            track_id="NAKAYAMA",
            month=3,
            week=10,
            grade=RaceGrade.G2,
            surface=RaceSurface.TURF,
            distance=2000,
            age_restriction=AgeRestriction.THREE_YO,
            sex_restriction=SexRestriction.MIXED,
            year=1,
        )
        self.assertFalse(self.entry_mgr.can_enter_race(h_3yo_0win, race_spring_g2))
        self.assertTrue(self.entry_mgr.can_enter_race(h_3yo_1win, race_spring_g2))
        self.assertTrue(self.entry_mgr.can_enter_race(h_3yo_4win, race_spring_g2))

        # 5月4週（week 20）当日
        race_w20 = Race(
            name="東京優駿",
            track_id="TOKYO",
            month=5,
            week=20,
            grade=RaceGrade.G1,
            surface=RaceSurface.TURF,
            distance=2400,
            age_restriction=AgeRestriction.THREE_YO,
            sex_restriction=SexRestriction.MIXED,
            year=1,
        )
        self.assertFalse(self.entry_mgr.can_enter_race(h_3yo_0win, race_w20))
        self.assertTrue(self.entry_mgr.can_enter_race(h_3yo_1win, race_w20))

        # 6月1週（week 21: 夏競馬以降）
        race_w21 = Race(
            name="ラジオNIKKEI賞",
            track_id="FUKUSHIMA",
            month=6,
            week=21,
            grade=RaceGrade.G3,
            surface=RaceSurface.TURF,
            distance=1800,
            age_restriction=AgeRestriction.THREE_YO,
            sex_restriction=SexRestriction.MIXED,
            year=1,
        )
        # week 21以降は1勝馬は出走不可（重賞2着実績なし）
        self.assertFalse(self.entry_mgr.can_enter_race(h_3yo_1win, race_w21, has_graded_top2=False))
        # 重賞2着実績ありなら出走可能
        self.assertTrue(self.entry_mgr.can_enter_race(h_3yo_1win, race_w21, has_graded_top2=True))
        # 4勝馬は実績なしでも出走可能
        self.assertTrue(self.entry_mgr.can_enter_race(h_3yo_4win, race_w21, has_graded_top2=False))

    def test_condition_race_3w_rule(self):
        """3勝クラス（COND_3W）は3勝馬のみ出走可能であり、1勝馬は出走不可"""
        h_3yo_1win = self._create_dummy_horse(career_wins=1, age=3)
        h_3yo_3win = self._create_dummy_horse(career_wins=3, age=3)
        cond_3w_race = Race(
            name="3勝クラス特別",
            track_id="TOKYO",
            month=3,
            week=10,
            grade=RaceGrade.COND_3W,
            surface=RaceSurface.TURF,
            distance=1800,
            age_restriction=AgeRestriction.THREE_YO_UP,
            sex_restriction=SexRestriction.MIXED,
            year=1,
        )
        self.assertFalse(self.entry_mgr.can_enter_race(h_3yo_1win, cond_3w_race))
        self.assertTrue(self.entry_mgr.can_enter_race(h_3yo_3win, cond_3w_race))


if __name__ == "__main__":
    unittest.main()
