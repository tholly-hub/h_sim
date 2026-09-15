"""
厩舎システム・騎手システム・血統表/系統図の包括単体テスト
"""

import os
import tempfile
import unittest

from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.management.jockey_manager import JockeyManager
from src.management.stable_manager import StableManager
from src.views.viewer import HorseViewer


class TestStableAndJockeySystem(unittest.TestCase):
    """厩舎・騎手システムの総合テスト"""

    def setUp(self):
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_file.close()
        self.db = Database(self.temp_db_file.name)
        self.db.initialize_schema(force_recreate=True)
        self.initializer = DatabaseInitializer(self.db)
        self.stable_mgr = StableManager(self.db, max_capacity=50, default_expand_step=5)
        self.jockey_mgr = JockeyManager(self.db, quota_miho=45, quota_ritto=45)
        self.viewer = HorseViewer(self.db)

    def tearDown(self):
        if os.path.exists(self.temp_db_file.name):
            try:
                os.remove(self.temp_db_file.name)
            except PermissionError:
                pass

    def test_stable_and_jockey_initial_even_distribution(self):
        """美浦30・栗東30厩舎、美浦30・栗東30騎手、および世代均等配分の検証"""
        breeder_ids = self.initializer.generate_initial_breeders(50)
        owner_ids = self.initializer.generate_initial_owners(100)
        trainer_ids = self.initializer.generate_initial_trainers(count_miho=30, count_ritto=30)
        jockey_ids = self.initializer.generate_initial_jockeys(count_miho=45, count_ritto=45)

        self.assertEqual(len(trainer_ids), 60)
        self.assertEqual(len(jockey_ids), 90)

        self.initializer.generate_initial_population(
            breeder_ids=breeder_ids,
            owner_ids=owner_ids,
            trainer_ids=trainer_ids,
            jockey_ids=jockey_ids,
            num_sires=60,
            num_dams=600,
            num_active_horses=1250,
        )

        with self.db.session() as conn:
            # 1. 美浦30、栗東30の確認
            miho_count = conn.execute("SELECT COUNT(*) FROM trainers WHERE location = '美浦'").fetchone()[0]
            ritto_count = conn.execute("SELECT COUNT(*) FROM trainers WHERE location = '栗東'").fetchone()[0]
            self.assertEqual(miho_count, 30)
            self.assertEqual(ritto_count, 30)

            # 2. 調教師の年齢分布 (美浦・栗東それぞれ50〜79歳の30世代各1名)
            for loc in ["美浦", "栗東"]:
                t_ages = [r["age"] for r in conn.execute("SELECT age FROM trainers WHERE location = ? ORDER BY age", (loc,)).fetchall()]
                self.assertEqual(t_ages, list(range(50, 80)))

            # 3. 騎手の年齢分布 (美浦・栗東それぞれ20〜49歳の30世代各1名)
            for loc in ["美浦", "栗東"]:
                j_ages = [r["age"] for r in conn.execute("SELECT age FROM jockeys WHERE location = ? AND is_active = 1 ORDER BY age", (loc,)).fetchall()]
                self.assertEqual(len(j_ages), 45)

            # 4. 全厩舎の初期枠数は30頭、均等入厩 (1250 / 60 = 各20〜21頭)
            counts = conn.execute(
                "SELECT trainer_id, COUNT(*) as cnt FROM horses WHERE is_active = 1 GROUP BY trainer_id"
            ).fetchall()
            self.assertEqual(len(counts), 60)
            for cnt_row in counts:
                self.assertIn(cnt_row["cnt"], [20, 21])

            # 5. 全現役馬に主戦騎手が割り当てられていること
            no_jockey = conn.execute(
                "SELECT COUNT(*) FROM horses WHERE is_active = 1 AND jockey_id IS NULL"
            ).fetchone()[0]
            self.assertEqual(no_jockey, 0)

    def test_stable_and_jockey_retirement_inheritance_cycle(self):
        """
        年次進行時の引退・厩舎継承サイクルの検証:
        - 50歳到達騎手（東西各1名）が現役引退
        - 80歳到達厩舎（東西各1厩舎）が引退
        - 引退騎手が引退厩舎を1対1で完全継承（苗字+厩舎、age=50、管理馬保持）
        - 新人騎手（東西各1名、20歳）がデビューし、騎手定員が完全維持される
        """
        breeder_ids = self.initializer.generate_initial_breeders(50)
        owner_ids = self.initializer.generate_initial_owners(100)
        trainer_ids = self.initializer.generate_initial_trainers(count_miho=30, count_ritto=30)
        jockey_ids = self.initializer.generate_initial_jockeys(count_miho=45, count_ritto=45)
        self.initializer.generate_initial_population(
            breeder_ids=breeder_ids,
            owner_ids=owner_ids,
            trainer_ids=trainer_ids,
            jockey_ids=jockey_ids,
            num_sires=60,
            num_dams=600,
            num_active_horses=1250,
        )

        # 1年進行処理を実行
        j_result = self.jockey_mgr.progress_year_and_maintain_quota(current_year=2)
        s_result = self.stable_mgr.progress_year_and_inherit(
            current_year=2,
            retired_jockeys_by_loc=j_result["retired_by_location"]
        )

        # 騎手引退確認 (美浦1名、栗東1名の計2名)
        self.assertGreaterEqual(j_result["retired_count"], 2)
        self.assertGreaterEqual(len(j_result["retired_by_location"]["美浦"]), 1)
        self.assertGreaterEqual(len(j_result["retired_by_location"]["栗東"]), 1)
        self.assertEqual(len(j_result["new_jockeys"]), j_result["retired_count"])

        # 厩舎引退・継承確認 (美浦1厩舎、栗東1厩舎の計2厩舎が継承)
        self.assertEqual(s_result["retired_trainers_count"], 2)
        self.assertEqual(s_result["inherited_stables_count"], 2)

        with self.db.session() as conn:
            # 現役騎手数確認 (美浦30名、栗東30名で完全維持)
            miho_j = conn.execute("SELECT COUNT(*) FROM jockeys WHERE location = '美浦' AND is_active = 1").fetchone()[0]
            ritto_j = conn.execute("SELECT COUNT(*) FROM jockeys WHERE location = '栗東' AND is_active = 1").fetchone()[0]
            self.assertEqual(miho_j, 45)
            self.assertEqual(ritto_j, 45)

            # 新人騎手（20歳）が東西各1名存在すること
            newbies_miho = conn.execute("SELECT COUNT(*) FROM jockeys WHERE location = '美浦' AND age = 18 AND is_active = 1").fetchone()[0]
            newbies_ritto = conn.execute("SELECT COUNT(*) FROM jockeys WHERE location = '栗東' AND age = 18 AND is_active = 1").fetchone()[0]
            self.assertGreaterEqual(newbies_miho, 1)
            self.assertGreaterEqual(newbies_ritto, 1)

            # 厩舎数確認 (美浦30、栗東30で維持)
            miho_t = conn.execute("SELECT COUNT(*) FROM trainers WHERE location = '美浦'").fetchone()[0]
            ritto_t = conn.execute("SELECT COUNT(*) FROM trainers WHERE location = '栗東'").fetchone()[0]
            self.assertEqual(miho_t, 30)
            self.assertEqual(ritto_t, 30)

            # 新規開業厩舎（50歳、開業1年目、元騎手ID紐付き）が東西各1厩舎存在すること
            for inh in s_result["inherited_stables"]:
                t_row = conn.execute("SELECT * FROM trainers WHERE trainer_id = ?", (inh["trainer_id"],)).fetchone()
                self.assertEqual(t_row["age"], 50)
                self.assertEqual(t_row["trainer_years"], 1)
                self.assertIsNotNone(t_row["former_jockey_id"])
                self.assertTrue(t_row["name"].endswith("厩舎"))

            # 厩舎所属馬が0頭になっていないこと、全現役馬が消えていないこと
            total_active_horses = conn.execute("SELECT COUNT(*) FROM horses WHERE is_active = 1").fetchone()[0]
            self.assertEqual(total_active_horses, 1250)
            zero_stables = conn.execute(
                """
                SELECT COUNT(*) FROM trainers t
                WHERE (SELECT COUNT(*) FROM horses h WHERE h.trainer_id = t.trainer_id AND h.is_active = 1) = 0
                """
            ).fetchone()[0]
            self.assertEqual(zero_stables, 0)

    def test_jockey_race_assignment_and_substitute_promotion(self):
        """お手馬重複時の代打手配および代打連対による主戦昇格の検証"""
        breeder_ids = self.initializer.generate_initial_breeders(5)
        owner_ids = self.initializer.generate_initial_owners(5)
        trainer_ids = self.initializer.generate_initial_trainers(count_miho=5, count_ritto=5)
        jockey_ids = self.initializer.generate_initial_jockeys(count_miho=10, count_ritto=10)

        self.initializer.generate_initial_population(
            breeder_ids=breeder_ids,
            owner_ids=owner_ids,
            trainer_ids=trainer_ids,
            jockey_ids=jockey_ids,
            num_sires=5,
            num_dams=5,
            num_active_horses=10,
        )

        # 2頭の馬に同じ主戦騎手を設定
        same_jockey_id = jockey_ids[0]
        with self.db.session() as conn:
            horses = conn.execute("SELECT horse_id FROM horses WHERE is_active = 1 LIMIT 2").fetchall()
            h1, h2 = horses[0]["horse_id"], horses[1]["horse_id"]
            conn.execute("UPDATE horses SET jockey_id = ? WHERE horse_id IN (?, ?)", (same_jockey_id, h1, h2))

        # 2頭が出走する場合の騎手手配
        assignments = self.jockey_mgr.assign_jockeys_for_race([h1, h2])
        self.assertEqual(len(assignments), 2)

        # 1頭は主戦（is_regular=True）、もう1頭は代打（is_regular=False）が割り当てられる
        regular_count = sum(1 for a in assignments if a.is_regular)
        sub_count = sum(1 for a in assignments if not a.is_regular)
        self.assertEqual(regular_count, 1)
        self.assertEqual(sub_count, 1)

        # 代打騎手が2着（連対）に入線した場合の昇格
        sub_assign = [a for a in assignments if not a.is_regular][0]
        promoted = self.jockey_mgr.handle_substitute_success(
            horse_id=sub_assign.horse_id,
            sub_jockey_id=sub_assign.assigned_jockey_id,
            finish_position=2,
        )
        self.assertTrue(promoted)

        # 馬の主戦騎手が代打騎手に乗り替わっていること
        with self.db.session() as conn:
            new_j = conn.execute("SELECT jockey_id FROM horses WHERE horse_id = ?", (sub_assign.horse_id,)).fetchone()[0]
            self.assertEqual(new_j, sub_assign.assigned_jockey_id)

    def test_pedigree_and_sire_line_display(self):
        """血統表およびサイアーライン系統図の表示確認"""
        breeder_ids = self.initializer.generate_initial_breeders(5)
        owner_ids = self.initializer.generate_initial_owners(5)
        trainer_ids = self.initializer.generate_initial_trainers(count_miho=5, count_ritto=5)
        jockey_ids = self.initializer.generate_initial_jockeys(count_miho=5, count_ritto=5)

        self.initializer.generate_initial_population(
            breeder_ids=breeder_ids,
            owner_ids=owner_ids,
            trainer_ids=trainer_ids,
            jockey_ids=jockey_ids,
            num_sires=5,
            num_dams=5,
            num_active_horses=10,
        )

        with self.db.session() as conn:
            h_id = conn.execute("SELECT horse_id FROM horses LIMIT 1").fetchone()[0]

        self.assertTrue(self.viewer.show_pedigree(h_id))
        self.assertTrue(self.viewer.show_sire_line_tree())
        self.assertTrue(self.viewer.show_rankings("horse", "career"))
        self.assertTrue(self.viewer.show_rankings("trainer", "career"))
        self.assertTrue(self.viewer.show_rankings("jockey", "career"))


if __name__ == "__main__":
    unittest.main()
