import unittest
import sqlite3
import os
import sys

# プロジェクトルート
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.core.lifecycle import LifecycleEngine
from src.gui.views.database_view import DatabaseView
from src.gui.views.sire_detail_dialog import SireDetailDialog
from src.gui.views.dam_detail_dialog import DamDetailDialog

from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def insert_test_horse(conn, **kwargs):
    defaults = {
        "name": "テスト馬",
        "sex": "horse",
        "birth_year": 1990,
        "age": 5,
        "breeder_id": 1,
        "owner_id": 1,
        "is_active": 0,
        "is_sire": 0,
        "is_dam": 0,
        "mstn_type": "C/T",
        "speed": 60.0,
        "stamina": 60.0,
        "acceleration": 60.0,
        "temperament": 60.0,
        "durability": 60.0,
        "maternal_vitality": 60.0,
        "growth_type": "normal",
        "peak_age": 4.5,
        "current_ability_rate": 1.0,
        "running_style": "between",
        "generation": 1,
    }
    defaults.update(kwargs)
    cols = list(defaults.keys())
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT INTO horses ({', '.join(cols)}) VALUES ({placeholders})"
    cur = conn.execute(sql, tuple(defaults[c] for c in cols))
    return cur.lastrowid


def insert_test_race(conn, **kwargs):
    defaults = {
        "name": "テストレース",
        "grade": "G1",
        "surface": "turf",
        "distance": 2000,
        "track_id": "TOKYO",
        "year": 1,
        "month": 5,
        "week": 20,
        "full_gate": 18,
        "age_restriction": "3yo_up",
        "sex_restriction": "mixed",
        "weight_type": "定量",
        "condition": "good",
        "base_prize": 100000000,
        "condition_prize": 50000000,
    }
    defaults.update(kwargs)
    cols = list(defaults.keys())
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT INTO races ({', '.join(cols)}) VALUES ({placeholders})"
    cur = conn.execute(sql, tuple(defaults[c] for c in cols))
    return cur.lastrowid


class Test0926Features(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.initializer = DatabaseInitializer(self.db)
        self.initializer.initialize_all(force_recreate=True)
        self.lifecycle = LifecycleEngine(self.db)

    def test_sire_retirement_rule_after_year_6(self):
        """6年目以降、直近3年間の産駒勝利数が0の場合に種牡馬引退することの検証"""
        with self.db.session() as conn:
            # テスト用の種牡馬を追加 (start_year=1, 就任6年目)
            sire_h_id = insert_test_horse(
                conn, name="テスト種牡馬A", sex="horse", is_sire=1, age=10
            )
            conn.execute("""
                INSERT INTO sires (horse_id, breeder_id, sire_line, start_year, is_active)
                VALUES (?, 1, 'テスト系', 1, 1)
            """, (sire_h_id,))

            # 6年目の年末処理を実行 (産駒勝利数0)
            retired_sires = self.lifecycle._manage_sire_roster(conn, current_year=6, retired_horses=[])
            
            # 引退状態を確認
            s_row = conn.execute("SELECT is_active FROM sires WHERE horse_id = ?", (sire_h_id,)).fetchone()
            h_row = conn.execute("SELECT is_sire FROM horses WHERE horse_id = ?", (sire_h_id,)).fetchone()
            self.assertEqual(s_row["is_active"], 0, "6年目以降直近3年産駒未勝利の種牡馬は引退していること")
            self.assertEqual(h_row["is_sire"], 0, "馬レコードのis_sireも0に更新されること")

    def test_sire_keeps_active_if_has_recent_wins(self):
        """直近3年間に産駒勝利がある種牡馬は引退しないことの検証"""
        with self.db.session() as conn:
            sire_h_id = insert_test_horse(
                conn, name="テスト種牡馬B", sex="horse", is_sire=1, age=10
            )
            conn.execute("""
                INSERT INTO sires (horse_id, breeder_id, sire_line, start_year, is_active)
                VALUES (?, 1, 'テスト系', 1, 1)
            """, (sire_h_id,))

            # 産駒を作成
            child_h_id = insert_test_horse(
                conn, name="テスト産駒B1", sex="colt", is_active=1, sire_id=sire_h_id, age=3
            )

            # 直近3年間 (4年目) に勝利レース結果を登録
            race_id = insert_test_race(conn, name="テストレース", year=4, week=20)
            conn.execute("""
                INSERT INTO results (race_id, horse_id, finish_position, finish_time, prize_awarded)
                VALUES (?, ?, 1, 120.0, 100000000)
            """, (race_id, child_h_id))

            # 6年目の年末処理を実行 (4年目に勝利あり -> 直近3年間に含まれる)
            self.lifecycle._manage_sire_roster(conn, current_year=6, retired_horses=[])

            s_row = conn.execute("SELECT is_active FROM sires WHERE horse_id = ?", (sire_h_id,)).fetchone()
            self.assertEqual(s_row["is_active"], 1, "直近3年間に産駒勝利がある種牡馬は現役継続すること")

    def test_database_sire_list_generation_colors(self):
        """種牡馬リストの世代別カラー判定の検証"""
        view = DatabaseView(self.db)
        
        with self.db.session() as conn:
            # 世代1〜8および海外種牡馬を登録
            for gen in range(1, 9):
                hid = insert_test_horse(
                    conn, name=f"世代種牡馬Gen{gen}", sex="horse", is_sire=1, generation=gen
                )
                st_yr = 1 if gen == 1 else gen
                conn.execute("""
                    INSERT INTO sires (horse_id, breeder_id, sire_line, start_year, generation, is_active, is_foreign)
                    VALUES (?, 1, 'テスト系', ?, ?, 1, 0)
                """, (hid, st_yr, gen))

            # 海外種牡馬
            hid_f = insert_test_horse(
                conn, name="海外種牡馬F", sex="horse", is_sire=1, generation=3
            )
            conn.execute("""
                INSERT INTO sires (horse_id, breeder_id, sire_line, start_year, generation, is_active, is_foreign)
                VALUES (?, 1, 'テスト系', 3, 3, 1, 1)
            """, (hid_f,))

        view.refresh_sires_list()
        
        # テーブル内の色とテキストをチェック
        palette = {
            1: "#ffffff",  # 初代 (start_year=1)
            2: "#38bdf8",  # 第2世代種牡馬 (水色)
            3: "#a3e635",  # 第3世代種牡馬 (黄緑)
            4: "#f472b6",  # 第4世代種牡馬 (桃)
            5: "#60a5fa",  # 第5世代種牡馬 (青)
            6: "#4ade80",  # 第6世代種牡馬 (緑)
            7: "#facc15",  # 第7世代種牡馬 (黄)
            8: "#c084fc",  # 第8世代種牡馬 (紫)
        }

        row_count = view.table_sires.rowCount()
        self.assertGreater(row_count, 0)

        found_foreign = False
        for r in range(row_count):
            item = view.table_sires.item(r, 0)
            if not item:
                continue
            text = item.text()
            color_hex = item.foreground().color().name().lower()

            if "海外種牡馬F" in text:
                self.assertIn("(外)", text)
                self.assertEqual(color_hex, "#ef4444")
                found_foreign = True

            for gen, expected_col in palette.items():
                if f"世代種牡馬Gen{gen}" in text:
                    self.assertEqual(color_hex, expected_col.lower(), f"Gen{gen}の色が一致すること")

        self.assertTrue(found_foreign, "海外種牡馬が見つかり(外)および赤色であること")

    def test_sire_and_dam_detail_race_history_tab(self):
        """種牡馬・繁殖牝馬カルテに競走成績タブが存在し、レース履歴が表示されることの検証"""
        with self.db.session() as conn:
            # 競走成績のある種牡馬
            sire_hid = insert_test_horse(
                conn, name="実績種牡馬", sex="horse", is_sire=1, age=7
            )
            conn.execute("""
                INSERT INTO sires (horse_id, breeder_id, sire_line, start_year, is_active)
                VALUES (?, 1, 'テスト系', 1, 1)
            """, (sire_hid,))

            # 競走成績のある繁殖牝馬
            dam_hid = insert_test_horse(
                conn, name="実績繁殖牝馬", sex="mare", is_dam=1, age=7
            )
            conn.execute("""
                INSERT INTO dams (horse_id, breeder_id, start_year, is_active)
                VALUES (?, 1, 1, 1)
            """, (dam_hid,))

            # レースを登録
            race_id = insert_test_race(conn, name="ダービー", year=1, month=5, week=22)

            conn.execute("""
                INSERT INTO results (race_id, horse_id, finish_position, finish_time, prize_awarded)
                VALUES (?, ?, 1, 145.5, 150000000)
            """, (race_id, sire_hid))

            conn.execute("""
                INSERT INTO results (race_id, horse_id, finish_position, finish_time, prize_awarded)
                VALUES (?, ?, 1, 146.0, 150000000)
            """, (race_id, dam_hid))

        # 種牡馬カルテ確認
        sire_dlg = SireDetailDialog(self.db, sire_hid)
        self.assertIsNotNone(sire_dlg.table_history)
        self.assertEqual(sire_dlg.table_history.rowCount(), 1)

        # 繁殖牝馬カルテ確認
        dam_dlg = DamDetailDialog(self.db, dam_hid)
        self.assertIsNotNone(dam_dlg.table_history)
        self.assertEqual(dam_dlg.table_history.rowCount(), 1)


if __name__ == "__main__":
    unittest.main()
