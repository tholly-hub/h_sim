"""
時間進行・週進行・年進行の動作検証テスト (Step 6)
- 1年目第1週から確実に週進行できること
- 48週完了後の年進行と2年目開幕
- 3年目7月（第27週）の2歳新馬戦開幕とレース実行
"""

import unittest
from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.core.lifecycle import LifecycleEngine
from src.race.calendar import CalendarController
from src.gui.views.simulation_status_view import advance_one_week_core, get_current_sim_status
from src.gui.views.dashboard_view import get_latest_completed_week


class TestTimeProgression(unittest.TestCase):

    def setUp(self):
        self.db = Database(":memory:")
        self.initializer = DatabaseInitializer(self.db)
        self.initializer.initialize_all(force_recreate=True)
        self.lifecycle = LifecycleEngine(self.db)
        self.calendar = CalendarController(self.db)

    def test_initial_state_is_year1_week1(self):
        """初期化直後の状態が 1年目第1週 であること"""
        with self.db.session() as conn:
            cur_y, cur_w = get_latest_completed_week(conn)
            self.assertEqual(cur_y, 1)
            self.assertEqual(cur_w, 1)

    def test_week_progression_in_year1(self):
        """1年目でレースがない週でも 1週ずつ順調に進行すること"""
        # 1週進める (1年目1週 -> 1年目2週)
        y, w, res = advance_one_week_core(self.calendar, self.lifecycle, self.db)
        self.assertEqual(y, 1)
        self.assertEqual(w, 2)

        with self.db.session() as conn:
            cur_y, cur_w = get_latest_completed_week(conn)
            self.assertEqual(cur_y, 1)
            self.assertEqual(cur_w, 2)

        # さらに5週進める (第3週〜第7週)
        for expected_w in range(3, 8):
            y, w, res = advance_one_week_core(self.calendar, self.lifecycle, self.db)
            self.assertEqual(y, 1)
            self.assertEqual(w, expected_w)

    def test_year_advance_after_week48(self):
        """48週まで進んだ後にさらに進めると年度更新されて2年目第1週になること"""
        # 1年目48週まで進行状態を設定
        with self.db.session() as conn:
            conn.execute(
                "UPDATE system_status SET value_int = 48 WHERE key = 'current_week'"
            )

        # 次の週に進める
        y, w, res = advance_one_week_core(self.calendar, self.lifecycle, self.db)
        self.assertEqual(y, 2)
        self.assertEqual(w, 1)

        with self.db.session() as conn:
            cur_y, cur_w = get_latest_completed_week(conn)
            self.assertEqual(cur_y, 2)
            self.assertEqual(cur_w, 1)

    def test_year3_debut_races_run(self):
        """3年目第27週（7月）に2歳新馬戦が開幕し、レースが実行されること"""
        # 2年目終了まで年進行
        self.lifecycle.advance_year(current_year=1)
        self.lifecycle.advance_year(current_year=2)

        with self.db.session() as conn:
            conn.execute("UPDATE system_status SET value_int = 3 WHERE key = 'current_year'")
            conn.execute("UPDATE system_status SET value_int = 26 WHERE key = 'current_week'")

        # 第27週を実行
        y, w, res = advance_one_week_core(self.calendar, self.lifecycle, self.db)
        self.assertEqual(y, 3)
        self.assertEqual(w, 27)
        self.assertGreater(res.get("races_run", 0), 0, "3年目第27週には新馬戦が実行されること")
        self.assertGreater(res.get("starters_count", 0), 0, "出走頭数が存在すること")


if __name__ == "__main__":
    unittest.main()
