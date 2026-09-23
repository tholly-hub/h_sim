"""
レース出走体系（牡牝分離・古馬牝馬限定）および新馬・未勝利・条件戦の牝馬限定廃止に関するユニットテスト
"""

import unittest
from src.models.race import AgeRestriction, Race, RaceGrade, RaceSurface, SexRestriction
from src.models.horse import Horse
from src.race.annual_program import generate_full_program
from src.race.entry import RaceEntryManager
from src.db.database import Database
from src.generators.initializer import DatabaseInitializer


class TestRaceSexRestrictions(unittest.TestCase):
    def setUp(self):
        self.races = generate_full_program(year=3)
        self.db = Database(":memory:")
        init = DatabaseInitializer(self.db)
        init.initialize_all()
        self.entry_mgr = RaceEntryManager(self.db)

    def test_no_filly_restriction_in_lower_classes(self):
        """新馬戦、未勝利戦、1勝〜3勝クラスに牝馬限定戦が存在せず、すべてMIXEDであること"""
        lower_grades = {
            RaceGrade.NEWCOMER,
            RaceGrade.MAIDEN,
            RaceGrade.COND_1W,
            RaceGrade.COND_2W,
            RaceGrade.COND_3W,
        }
        for r in self.races:
            if r.grade in lower_grades:
                self.assertEqual(
                    r.sex_restriction,
                    SexRestriction.MIXED,
                    f"レース '{r.name}' (Grade: {r.grade}) は MIXED であるべきですが、{r.sex_restriction} となっています",
                )
                self.assertNotIn(
                    "牝馬限定",
                    r.name,
                    f"レース '{r.name}' の名前に '牝馬限定' が残っています",
                )

    def test_colt_g1_and_trials_restriction(self):
        """牡馬指定G1およびその前哨戦・トライアルがCOLT_HORSEであること"""
        expected_colt_keywords = [
            "朝日杯フューチュリティS",
            "京王杯2歳S",
            "デイリー杯2歳S",
            "皐月賞",
            "弥生賞ディープ記念",
            "スプリングS",
            "若葉ステークス",
            "日本ダービー",
            "青葉賞",
            "京都新聞杯",
            "プリンシパルS",
            "菊花賞",
            "セントライト記念",
            "神戸新聞杯",
        ]
        colt_race_names = {r.name: r for r in self.races if r.sex_restriction == SexRestriction.COLT_HORSE}

        for kw in expected_colt_keywords:
            matched = [r for name, r in colt_race_names.items() if kw in name]
            self.assertTrue(
                len(matched) > 0,
                f"牡馬限定指定キーワード '{kw}' に該当する COLT_HORSE レースが見つかりません",
            )
            for r in matched:
                self.assertEqual(r.sex_restriction, SexRestriction.COLT_HORSE)

    def test_filly_g1_and_trials_restriction(self):
        """牝馬指定G1およびその前哨戦・トライアル、古馬牝馬限定G1がFILLY_MAREであること"""
        expected_filly_keywords = [
            "阪神ジュベナイルフィリーズ",
            "アルテミスS",
            "ファンタジーS",
            "桜花賞",
            "チューリップ賞",
            "フィリーズレビュー",
            "アネモネS",
            "オークス",
            "フローラS",
            "スイートピーS",
            "秋華賞",
            "紫苑S",
            "ローズS",
            "ヴィクトリアマイル",
            "阪神牝馬S",
            "エリザベス女王杯",
            "府中牝馬S",
        ]
        filly_race_names = {r.name: r for r in self.races if r.sex_restriction == SexRestriction.FILLY_MARE}

        for kw in expected_filly_keywords:
            matched = [r for name, r in filly_race_names.items() if kw in name]
            self.assertTrue(
                len(matched) > 0,
                f"牝馬限定指定キーワード '{kw}' に該当する FILLY_MARE レースが見つかりません",
            )
            for r in matched:
                self.assertEqual(r.sex_restriction, SexRestriction.FILLY_MARE)

    def test_can_enter_race_sex_filtering(self):
        """can_enter_race で牡馬・牝馬の出走可否が正しく判定されること"""
        from src.models.horse import GenotypeMSTN, GrowthType
        colt = Horse(
            horse_id=1,
            name="テスト牡馬",
            sex="colt",
            birth_year=1,
            age=3,
            breeder_id=1,
            owner_id=1,
            mstn_type=GenotypeMSTN.CT,
            speed=70.0,
            stamina=70.0,
            acceleration=70.0,
            temperament=70.0,
            durability=70.0,
            maternal_vitality=70.0,
            growth_type=GrowthType.NORMAL,
            peak_age=4.0,
            career_wins=2,
            career_starts=3,
            is_active=1,
            is_dead=0,
        )
        filly = Horse(
            horse_id=2,
            name="テスト牝馬",
            sex="filly",
            birth_year=1,
            age=3,
            breeder_id=1,
            owner_id=1,
            mstn_type=GenotypeMSTN.CT,
            speed=70.0,
            stamina=70.0,
            acceleration=70.0,
            temperament=70.0,
            durability=70.0,
            maternal_vitality=70.0,
            growth_type=GrowthType.NORMAL,
            peak_age=4.0,
            career_wins=2,
            career_starts=3,
            is_active=1,
            is_dead=0,
        )

        colt_race = [r for r in self.races if "皐月賞" in r.name and r.grade == RaceGrade.G1][0]
        filly_race = [r for r in self.races if "桜花賞" in r.name and r.grade == RaceGrade.G1][0]
        # 3歳秋以降の2勝クラス（3歳以上条件）を選択
        mixed_race = [r for r in self.races if r.grade == RaceGrade.COND_2W and r.age_restriction == AgeRestriction.THREE_YO_UP][0]

        # 皐月賞 (COLT_HORSE): 牡馬は出走可能、牝馬は出走不可
        self.assertTrue(self.entry_mgr.can_enter_race(colt, colt_race))
        self.assertFalse(self.entry_mgr.can_enter_race(filly, colt_race))

        # 桜花賞 (FILLY_MARE): 牝馬は出走可能、牡馬は出走不可
        self.assertTrue(self.entry_mgr.can_enter_race(filly, filly_race))
        self.assertFalse(self.entry_mgr.can_enter_race(colt, filly_race))

        # 2勝クラス (MIXED): 牡馬も牝馬も出走可能
        self.assertTrue(self.entry_mgr.can_enter_race(colt, mixed_race))
        self.assertTrue(self.entry_mgr.can_enter_race(filly, mixed_race))

    def test_hopeful_stakes_and_trials_mixed_restriction(self):
        """ホープフルSおよびそのトライアルレースが2歳・牡牝混合(MIXED)であることの検証"""
        from src.models.horse import GenotypeMSTN, GrowthType

        hopeful_races = [r for r in self.races if "ホープフルS" in r.name or r.target_g1_name == "ホープフルS"]
        self.assertTrue(len(hopeful_races) >= 3, f"ホープフルSおよびトライアルが不足しています: {len(hopeful_races)}")

        for r in hopeful_races:
            self.assertEqual(
                r.age_restriction,
                AgeRestriction.TWO_YO,
                f"レース '{r.name}' の年齢制限は TWO_YO であるべきですが {r.age_restriction} です",
            )
            self.assertEqual(
                r.sex_restriction,
                SexRestriction.MIXED,
                f"レース '{r.name}' の性別制限は MIXED であるべきですが {r.sex_restriction} です",
            )

        # 2歳牡馬・2歳牝馬の双方が出走可能であることを確認
        colt_2yo = Horse(
            horse_id=10,
            name="テスト2歳牡馬",
            sex="colt",
            birth_year=1,
            age=2,
            breeder_id=1,
            owner_id=1,
            mstn_type=GenotypeMSTN.CT,
            speed=70.0,
            stamina=70.0,
            acceleration=70.0,
            temperament=70.0,
            durability=70.0,
            maternal_vitality=70.0,
            growth_type=GrowthType.NORMAL,
            peak_age=4.0,
            career_wins=1,
            career_starts=1,
            is_active=1,
            is_dead=0,
        )
        filly_2yo = Horse(
            horse_id=11,
            name="テスト2歳牝馬",
            sex="filly",
            birth_year=1,
            age=2,
            breeder_id=1,
            owner_id=1,
            mstn_type=GenotypeMSTN.CT,
            speed=70.0,
            stamina=70.0,
            acceleration=70.0,
            temperament=70.0,
            durability=70.0,
            maternal_vitality=70.0,
            growth_type=GrowthType.NORMAL,
            peak_age=4.0,
            career_wins=1,
            career_starts=1,
            is_active=1,
            is_dead=0,
        )

        for r in hopeful_races:
            self.assertTrue(
                self.entry_mgr.can_enter_race(colt_2yo, r),
                f"2歳牡馬が '{r.name}' に出走できません",
            )
            self.assertTrue(
                self.entry_mgr.can_enter_race(filly_2yo, r),
                f"2歳牝馬が '{r.name}' に出走できません",
            )


if __name__ == "__main__":
    unittest.main()

