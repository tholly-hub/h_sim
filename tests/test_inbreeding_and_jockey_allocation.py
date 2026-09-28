import unittest
from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.views.pedigree_builder import PedigreeBuilder
from src.race.rankings import RankingManager
from src.race.entry import RaceEntryManager
from src.models.race import Race, RaceGrade, RaceSurface, AgeRestriction, SexRestriction
from src.models.horse import Horse, GenotypeMSTN
from src.models.jockey import Jockey


class TestInbreedingAndJockeyAllocation(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.initializer = DatabaseInitializer(self.db)
        self.initializer.initialize_all()

    def test_calculate_inbreeding_outbreed(self):
        """重複祖先がない場合、アウトブリードと判定されること"""
        tree = {
            "horse_id": 1,
            "name": "テスト馬",
            "sex": "colt",
            "sire": {
                "horse_id": 2,
                "name": "父馬A",
                "sex": "horse",
                "sire": {
                    "horse_id": 4,
                    "name": "祖父A1",
                    "sex": "horse",
                },
                "dam": {
                    "horse_id": 5,
                    "name": "祖母A2",
                    "sex": "mare",
                }
            },
            "dam": {
                "horse_id": 3,
                "name": "母馬B",
                "sex": "mare",
                "sire": {
                    "horse_id": 6,
                    "name": "祖父B1",
                    "sex": "horse",
                },
                "dam": {
                    "horse_id": 7,
                    "name": "祖母B2",
                    "sex": "mare",
                }
            }
        }
        res = PedigreeBuilder.calculate_inbreeding(tree)
        self.assertTrue(res["is_outbreed"])
        self.assertEqual(res["summary_text"], "アウトブリード")
        self.assertEqual(len(res["inbreeds"]), 0)

    def test_calculate_inbreeding_3x5(self):
        """父方3世代目、母方5世代目に同一牡馬Aがいる場合: A 3×5 15.63%"""
        # 3代前: (1/2)^3 = 12.5%, 5代前: (1/2)^5 = 3.125% -> 計 15.625% -> 15.63%
        common_sire_node = {
            "horse_id": 100,
            "name": "名種牡馬A",
            "sex": "horse",
        }

        tree = {
            "horse_id": 1,
            "name": "クロス持ち馬",
            "sex": "colt",
            "sire": {  # gen 1
                "horse_id": 2,
                "name": "父",
                "sex": "horse",
                "sire": {  # gen 2
                    "horse_id": 4,
                    "name": "父父",
                    "sex": "horse",
                    "sire": common_sire_node,  # gen 3
                }
            },
            "dam": {  # gen 1
                "horse_id": 3,
                "name": "母",
                "sex": "mare",
                "sire": {  # gen 2
                    "horse_id": 5,
                    "name": "母父",
                    "sex": "horse",
                    "sire": {  # gen 3
                        "horse_id": 6,
                        "name": "母父父",
                        "sex": "horse",
                        "sire": {  # gen 4
                            "horse_id": 7,
                            "name": "母父父父",
                            "sex": "horse",
                            "sire": common_sire_node,  # gen 5
                        }
                    }
                }
            }
        }

        res = PedigreeBuilder.calculate_inbreeding(tree)
        self.assertFalse(res["is_outbreed"])
        self.assertEqual(len(res["inbreeds"]), 1)
        inb = res["inbreeds"][0]
        self.assertEqual(inb["name"], "名種牡馬A")
        self.assertEqual(inb["cross_str"], "3×5")
        self.assertAlmostEqual(inb["percentage"], 15.63, delta=0.01)
        self.assertEqual(inb["percentage_str"], "15.63%")
        self.assertEqual(inb["display"], "名種牡馬A 3×5 15.63%")

    def test_rankings_active_only(self):
        """リーディング集計で引退した騎手・種牡馬が除外されること"""
        rank_mgr = RankingManager(self.db)
        with self.db.session() as conn:
            # 騎手1人を引退（is_active = 0）に設定
            conn.execute("UPDATE jockeys SET is_active = 0 WHERE jockey_id = 1")
            # 種牡馬1頭を引退に設定
            conn.execute("UPDATE sires SET is_active = 0 WHERE sire_id = 1")

        j_ranks = rank_mgr.get_jockey_rankings(is_career=True)
        j_ids = [j["jockey_id"] for j in j_ranks]
        self.assertNotIn(1, j_ids)

        s_ranks = rank_mgr.get_sire_rankings(is_career=True)
        s_ids = [s["sire_id"] for s in s_ranks]
        self.assertNotIn(1, s_ids)

    def test_jockey_assignment_stable_equality(self):
        """厩舎所属騎手（2名）に対して均等・優先的に騎乗が割り振られること"""
        entry_mgr = RaceEntryManager(self.db)
        all_jockeys = [
            Jockey(jockey_id=1, name="騎手A", location="栗東", age=25, debut_year=1, skill=50.0, drive=50.0, start_dash=50.0, temperament_handling=50.0, current_year_starts=5, is_active=1, is_free=0, trainer_id=1),
            Jockey(jockey_id=2, name="騎手B", location="栗東", age=22, debut_year=1, skill=50.0, drive=50.0, start_dash=50.0, temperament_handling=50.0, current_year_starts=1, is_active=1, is_free=0, trainer_id=1),
        ]
        trainer_jockey_map = {1: [1, 2]}

        race = Race(
            race_id=1, year=1, month=1, week=1, track_id="TOKYO", name="3歳未勝利",
            grade=RaceGrade.MAIDEN, surface=RaceSurface.TURF, distance=1600,
            age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.MIXED
        )

        h1 = Horse(
            horse_id=10, name="馬1", sex="colt", birth_year=1, age=3, breeder_id=1, owner_id=1,
            trainer_id=1, mstn_type=GenotypeMSTN.CT, speed=50.0, stamina=50.0, acceleration=50.0,
            temperament=50.0, durability=50.0, maternal_vitality=50.0, growth_type="normal", peak_age=4.0
        )
        
        assigned = entry_mgr.assign_jockeys([h1], race, all_jockeys, trainer_jockey_map)
        # current_year_starts が少ない騎手B (ID: 2) が優先選抜されること
        self.assertEqual(assigned[10], 2)


if __name__ == "__main__":
    unittest.main()
