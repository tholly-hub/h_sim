"""
牧場枠管理・移籍・譲渡機能のテストモジュール
"""

import os
import tempfile
import unittest

from src.db.database import Database
from src.economy.transfer import BreederTransferManager, REGION_NEIGHBORS
from src.generators.initializer import DatabaseInitializer


class TestBreederTransfer(unittest.TestCase):
    """牧場均等配分、拡張、移籍、譲渡機能のテスト"""

    def setUp(self):
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_file.close()
        self.db = Database(self.temp_db_file.name)
        self.db.initialize_schema(force_recreate=True)
        self.initializer = DatabaseInitializer(self.db)
        self.transfer_mgr = BreederTransferManager(self.db, max_capacity=100, default_expand_step=5)

    def tearDown(self):
        if os.path.exists(self.temp_db_file.name):
            try:
                os.remove(self.temp_db_file.name)
            except PermissionError:
                pass

    def test_initial_even_distribution(self):
        """初期配置で全50牧場に種牡馬・繁殖牝馬が均等配置され、枠数が15頭であることを確認"""
        breeder_ids = self.initializer.generate_initial_breeders(count=50)
        owner_ids = self.initializer.generate_initial_owners(count=100)
        self.initializer.generate_initial_population(
            breeder_ids, owner_ids, num_sires=60, num_dams=600, num_active_horses=100
        )

        with self.db.session() as conn:
            # 1. 牧場数は50場
            self.assertEqual(len(breeder_ids), 50)

            # 2. 全牧場のキャパシティは15頭
            capacities = conn.execute("SELECT horse_capacity FROM breeders").fetchall()
            for cap in capacities:
                self.assertEqual(cap["horse_capacity"], 15)

            # 3. 繁殖牝馬は全50牧場に12頭ずつ均等配置 (600 / 50 = 12)
            dam_counts = conn.execute(
                "SELECT breeder_id, COUNT(*) as cnt FROM dams GROUP BY breeder_id"
            ).fetchall()
            self.assertEqual(len(dam_counts), 50)
            for dc in dam_counts:
                self.assertEqual(dc["cnt"], 12)

            # 4. 種牡馬は全50牧場に1頭以上（40場が1頭、10場が2頭、計60頭）
            sire_counts = conn.execute(
                "SELECT breeder_id, COUNT(*) as cnt FROM sires GROUP BY breeder_id"
            ).fetchall()
            self.assertEqual(len(sire_counts), 50)
            ones = sum(1 for sc in sire_counts if sc["cnt"] == 1)
            twos = sum(1 for sc in sire_counts if sc["cnt"] == 2)
            self.assertEqual(ones, 40)
            self.assertEqual(twos, 10)

            # 5. 全馬死亡フラグが0であること
            dead_count = conn.execute("SELECT COUNT(*) FROM horses WHERE is_dead = 1").fetchone()[0]
            self.assertEqual(dead_count, 0)

    def test_capacity_expansion(self):
        """牧場受け入れ枠の拡張機能（15頭 -> 20頭 ... 最大100頭）のテスト"""
        breeder_ids = self.initializer.generate_initial_breeders(count=5)
        target_b_id = breeder_ids[0]

        # 1回拡張 (+5) -> 20
        success = self.transfer_mgr.expand_capacity(target_b_id, step=5)
        self.assertTrue(success)
        inv = self.transfer_mgr.get_breeder_inventory(target_b_id)
        self.assertEqual(inv["capacity"], 20)

        # 複数回拡張して100（上限）へ
        for _ in range(20):
            self.transfer_mgr.expand_capacity(target_b_id, step=5)
        inv = self.transfer_mgr.get_breeder_inventory(target_b_id)
        self.assertEqual(inv["capacity"], 100)

        # 上限100頭に達しているため、これ以上の拡張はFalse
        success_after_max = self.transfer_mgr.expand_capacity(target_b_id, step=5)
        self.assertFalse(success_after_max)
        self.assertEqual(inv["capacity"], 100)

    def test_overflow_transfer_to_nearby_breeder(self):
        """枠数を超過した場合、枠上限まで拡張され、それでも溢れる場合は近隣牧場へ優先移籍するテスト"""
        breeder_ids = self.initializer.generate_initial_breeders(count=50)
        owner_ids = self.initializer.generate_initial_owners(count=10)
        self.initializer.generate_initial_population(
            breeder_ids, owner_ids, num_sires=60, num_dams=600, num_active_horses=10
        )

        target_b_id = breeder_ids[0]
        # 牧場枠をあえて現在頭数より小さくする（例: 頭数13-14頭に対して枠を5頭、かつ上限も5頭にする）
        with self.db.session() as conn:
            conn.execute("UPDATE breeders SET horse_capacity = 5 WHERE breeder_id = ?", (target_b_id,))

        # 上限5頭設定のTransferManagerで移籍を誘発
        strict_mgr = BreederTransferManager(self.db, max_capacity=5)
        records = strict_mgr.handle_overflow(target_b_id)

        self.assertTrue(len(records) > 0)
        for rec in records:
            self.assertEqual(rec.from_breeder_id, target_b_id)
            self.assertEqual(rec.reason, "overflow")
            # 移籍先牧場の頭数が枠内に収まっていることを確認
            dest_inv = strict_mgr.get_breeder_inventory(rec.to_breeder_id)
            self.assertGreaterEqual(dest_inv["capacity"], dest_inv["total_horses"])

    def test_ensure_minimum_population_rescue(self):
        """牧場所属馬が種牡馬0頭または繁殖牝馬0頭になりそうな時、近隣最大牧場から譲渡されるテスト"""
        breeder_ids = self.initializer.generate_initial_breeders(count=50)
        owner_ids = self.initializer.generate_initial_owners(count=10)
        self.initializer.generate_initial_population(
            breeder_ids, owner_ids, num_sires=60, num_dams=600, num_active_horses=10
        )

        target_b_id = breeder_ids[0]
        # target_b_id の種牡馬をあえて0頭にする（別の牧場へ一時移管）
        with self.db.session() as conn:
            conn.execute(
                "UPDATE sires SET breeder_id = ? WHERE breeder_id = ?",
                (breeder_ids[1], target_b_id)
            )

        inv_before = self.transfer_mgr.get_breeder_inventory(target_b_id)
        self.assertEqual(inv_before["sire_count"], 0)

        # 最低条件保証処理を実行
        rescue_records = self.transfer_mgr.ensure_minimum_population(target_b_id)
        self.assertEqual(len(rescue_records), 1)
        self.assertEqual(rescue_records[0].to_breeder_id, target_b_id)
        self.assertEqual(rescue_records[0].horse_type, "sire")
        self.assertEqual(rescue_records[0].reason, "rescue")

        # 譲渡後の状態確認: 種牡馬が1頭以上に戻っていること
        inv_after = self.transfer_mgr.get_breeder_inventory(target_b_id)
        self.assertGreaterEqual(inv_after["sire_count"], 1)
        self.assertGreaterEqual(inv_after["dam_count"], 1)


if __name__ == "__main__":
    unittest.main()
