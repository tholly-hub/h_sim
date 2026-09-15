"""
牧場枠管理・移籍・譲渡モジュール (Transfer & Capacity Management)
- 9地方の近隣優先度に基づく移籍・譲渡
- 牧場拡張（初期15頭〜最大100頭）
- 枠溢れ馬の近隣優先移籍
- 最低所属条件（種牡馬1頭、繁殖牝馬1頭）を下回る場合の近隣最大牧場からの譲渡
- 死亡（事故・高齢）ロジックの完全排除
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.db.database import Database

# 9地方の地理的近隣優先度マップ（自地方 -> 最も近い地方 -> 遠い地方）
REGION_NEIGHBORS: Dict[str, List[str]] = {
    "北海道": ["東北", "関東", "北陸", "中部", "近畿", "中国", "四国", "九州"],
    "東北": ["北海道", "関東", "北陸", "中部", "近畿", "中国", "四国", "九州"],
    "関東": ["東北", "中部", "北陸", "近畿", "北海道", "中国", "四国", "九州"],
    "北陸": ["中部", "近畿", "関東", "東北", "中国", "四国", "九州", "北海道"],
    "中部": ["北陸", "関東", "近畿", "東北", "中国", "四国", "九州", "北海道"],
    "近畿": ["中部", "北陸", "中国", "四国", "関東", "九州", "東北", "北海道"],
    "中国": ["四国", "近畿", "九州", "中部", "北陸", "関東", "東北", "北海道"],
    "四国": ["中国", "近畿", "九州", "中部", "北陸", "関東", "東北", "北海道"],
    "九州": ["四国", "中国", "近畿", "中部", "北陸", "関東", "東北", "北海道"],
}


@dataclass
class TransferRecord:
    """移籍・譲渡の実行記録"""
    horse_id: int
    horse_name: str
    horse_type: str  # 'sire' または 'dam'
    from_breeder_id: int
    from_breeder_name: str
    to_breeder_id: int
    to_breeder_name: str
    reason: str  # 'overflow'（枠溢れ移籍）または 'rescue'（最低数割れ譲渡）


class BreederTransferManager:
    """牧場のキャパシティ管理・移籍・譲渡を担当するクラス"""

    def __init__(self, db: Database, max_capacity: int = 100, default_expand_step: int = 5):
        self.db = db
        self.max_capacity = max_capacity
        self.default_expand_step = default_expand_step

    def get_breeder_inventory(self, breeder_id: int) -> Dict[str, Any]:
        """
        指定牧場の繋養状況（種牡馬一覧、繁殖牝馬一覧、枠数、空き状況）を取得
        """
        with self.db.session() as conn:
            breeder_row = conn.execute(
                "SELECT breeder_id, name, region, horse_capacity, funds FROM breeders WHERE breeder_id = ?",
                (breeder_id,),
            ).fetchone()

            if not breeder_row:
                raise ValueError(f"Breeder ID {breeder_id} does not exist.")

            sires = conn.execute(
                """
                SELECT s.sire_id, s.horse_id, h.name
                FROM sires s
                JOIN horses h ON s.horse_id = h.horse_id
                WHERE s.breeder_id = ? AND s.is_active = 1
                """,
                (breeder_id,),
            ).fetchall()

            dams = conn.execute(
                """
                SELECT d.dam_id, d.horse_id, h.name
                FROM dams d
                JOIN horses h ON d.horse_id = h.horse_id
                WHERE d.breeder_id = ? AND d.is_active = 1
                """,
                (breeder_id,),
            ).fetchall()

            total_horses = len(sires) + len(dams)
            capacity = breeder_row["horse_capacity"]

            return {
                "breeder_id": breeder_row["breeder_id"],
                "name": breeder_row["name"],
                "region": breeder_row["region"],
                "capacity": capacity,
                "funds": breeder_row["funds"],
                "sires": [dict(s) for s in sires],
                "dams": [dict(d) for d in dams],
                "sire_count": len(sires),
                "dam_count": len(dams),
                "total_horses": total_horses,
                "available_slots": capacity - total_horses,
            }

    def expand_capacity(self, breeder_id: int, step: Optional[int] = None) -> bool:
        """
        牧場受け入れ枠を拡張する（最大 max_capacity まで）
        Returns:
            拡張が成功したか否か
        """
        increase = step if step is not None else self.default_expand_step
        with self.db.session() as conn:
            row = conn.execute(
                "SELECT horse_capacity FROM breeders WHERE breeder_id = ?",
                (breeder_id,),
            ).fetchone()
            if not row:
                return False

            current_capacity = row["horse_capacity"]
            if current_capacity >= self.max_capacity:
                return False  # すでに上限到達

            new_capacity = min(self.max_capacity, current_capacity + increase)
            conn.execute(
                """
                UPDATE breeders 
                SET horse_capacity = ?, broodmare_capacity = ?
                WHERE breeder_id = ?
                """,
                (new_capacity, new_capacity, breeder_id),
            )
            return True

    def find_target_breeder_for_transfer(
        self,
        from_region: str,
        exclude_breeder_ids: List[int],
        allow_expansion: bool = True,
    ) -> Optional[int]:
        """
        移籍先の牧場を選定する。
        - 自地方優先、次いで近隣地方マップ順に探索。
        - 空き枠（available_slots > 0）がある牧場を優先。
        - 空きがない場合で allow_expansion=True かつ枠上限未満なら拡張して受け入れ可能とする。
        """
        priority_regions = [from_region] + REGION_NEIGHBORS.get(from_region, [])

        with self.db.session() as conn:
            all_breeders = conn.execute(
                """
                SELECT 
                    b.breeder_id, b.name, b.region, b.horse_capacity,
                    (
                        (SELECT COUNT(*) FROM sires s WHERE s.breeder_id = b.breeder_id AND s.is_active = 1) +
                        (SELECT COUNT(*) FROM dams d WHERE d.breeder_id = b.breeder_id AND d.is_active = 1)
                    ) as current_count
                FROM breeders b
                """
            ).fetchall()

            breeders_by_region: Dict[str, List[Dict[str, Any]]] = {}
            for b in all_breeders:
                if b["breeder_id"] in exclude_breeder_ids:
                    continue
                reg = b["region"]
                if reg not in breeders_by_region:
                    breeders_by_region[reg] = []
                breeders_by_region[reg].append(dict(b))

            # 1. 空き枠がある牧場を近隣順に探す
            for region in priority_regions:
                candidate_breeders = breeders_by_region.get(region, [])
                vacant = [
                    b for b in candidate_breeders
                    if (b["horse_capacity"] - b["current_count"]) > 0
                ]
                if vacant:
                    # 近隣同地方内からはランダムに選ぶ
                    chosen = random.choice(vacant)
                    return chosen["breeder_id"]

            # 2. 全場満杯だが、拡張可能な牧場を近隣順に探す
            if allow_expansion:
                for region in priority_regions:
                    candidate_breeders = breeders_by_region.get(region, [])
                    expandable = [
                        b for b in candidate_breeders
                        if b["horse_capacity"] < self.max_capacity
                    ]
                    if expandable:
                        chosen = random.choice(expandable)
                        self.expand_capacity(chosen["breeder_id"])
                        return chosen["breeder_id"]

        return None

    def transfer_horse(
        self,
        horse_id: int,
        horse_type: str,
        from_breeder_id: int,
        to_breeder_id: int,
        reason: str,
    ) -> TransferRecord:
        """
        馬（種牡馬または繁殖牝馬）を指定牧場へ移籍させる。
        """
        with self.db.session() as conn:
            # 馬名・牧場名の取得
            horse_row = conn.execute("SELECT name FROM horses WHERE horse_id = ?", (horse_id,)).fetchone()
            from_row = conn.execute("SELECT name FROM breeders WHERE breeder_id = ?", (from_breeder_id,)).fetchone()
            to_row = conn.execute("SELECT name FROM breeders WHERE breeder_id = ?", (to_breeder_id,)).fetchone()

            horse_name = horse_row["name"] if horse_row else f"ID:{horse_id}"
            from_name = from_row["name"] if from_row else f"Breeder:{from_breeder_id}"
            to_name = to_row["name"] if to_row else f"Breeder:{to_breeder_id}"

            # テーブル更新
            if horse_type == "sire":
                conn.execute(
                    "UPDATE sires SET breeder_id = ? WHERE horse_id = ?",
                    (to_breeder_id, horse_id),
                )
            elif horse_type == "dam":
                conn.execute(
                    "UPDATE dams SET breeder_id = ? WHERE horse_id = ?",
                    (to_breeder_id, horse_id),
                )

            # horses テーブルの breeder_id （現在の繋養地）も更新
            conn.execute(
                "UPDATE horses SET breeder_id = ? WHERE horse_id = ?",
                (to_breeder_id, horse_id),
            )

        return TransferRecord(
            horse_id=horse_id,
            horse_name=horse_name,
            horse_type=horse_type,
            from_breeder_id=from_breeder_id,
            from_breeder_name=from_name,
            to_breeder_id=to_breeder_id,
            to_breeder_name=to_name,
            reason=reason,
        )

    def handle_overflow(self, breeder_id: int) -> List[TransferRecord]:
        """
        牧場の繋養頭数が枠数を超えている場合、
        まず牧場拡張を試み、枠数上限（100頭）に達して溢れた馬を近隣牧場優先で移籍させる。
        ※最低条件（種牡馬1頭、繁殖牝馬1頭）は必ず維持する。
        """
        records: List[TransferRecord] = []
        inv = self.get_breeder_inventory(breeder_id)

        # 枠数を超えていなければ何もしない
        if inv["total_horses"] <= inv["capacity"]:
            return records

        overflow_count = inv["total_horses"] - inv["capacity"]

        # まず拡張を試みる（上限100頭まで）
        if inv["capacity"] < self.max_capacity:
            needed_increase = overflow_count
            self.expand_capacity(breeder_id, step=needed_increase)
            inv = self.get_breeder_inventory(breeder_id)
            if inv["total_horses"] <= inv["capacity"]:
                return records
            overflow_count = inv["total_horses"] - inv["capacity"]

        # 上限に達してもなお溢れている馬を移籍させる
        sires = inv["sires"].copy()
        dams = inv["dams"].copy()

        # 最低条件（種牡馬1、繁殖牝馬1）を割らないように移籍候補を選定
        movable_horses: List[Tuple[int, str]] = []
        if len(sires) > 1:
            for s in sires[1:]:
                movable_horses.append((s["horse_id"], "sire"))
        if len(dams) > 1:
            for d in dams[1:]:
                movable_horses.append((d["horse_id"], "dam"))

        # ランダムに溢れ数分選出
        random.shuffle(movable_horses)
        targets = movable_horses[:overflow_count]

        for horse_id, h_type in targets:
            target_breeder_id = self.find_target_breeder_for_transfer(
                from_region=inv["region"],
                exclude_breeder_ids=[breeder_id],
                allow_expansion=True,
            )
            if target_breeder_id:
                rec = self.transfer_horse(
                    horse_id=horse_id,
                    horse_type=h_type,
                    from_breeder_id=breeder_id,
                    to_breeder_id=target_breeder_id,
                    reason="overflow",
                )
                records.append(rec)

        return records

    def ensure_minimum_population(self, breeder_id: int) -> List[TransferRecord]:
        """
        牧場の最低条件として「種牡馬1頭、繁殖牝馬1頭」を下回る可能性がある（または下回っている）場合、
        その時最も大きな近隣牧場から馬を譲渡してもらう。
        """
        records: List[TransferRecord] = []
        inv = self.get_breeder_inventory(breeder_id)

        need_sire = (inv["sire_count"] < 1)
        need_dam = (inv["dam_count"] < 1)

        if not need_sire and not need_dam:
            return records

        priority_regions = [inv["region"]] + REGION_NEIGHBORS.get(inv["region"], [])

        with self.db.session() as conn:
            for h_type in (["sire"] if need_sire else []) + (["dam"] if need_dam else []):
                # 近隣地方順に探索
                donor_found = False
                for region in priority_regions:
                    # その地域で、譲渡可能な馬（種牡馬>1 または 繁殖牝馬>1）を持ち、かつ総頭数が最も多い牧場を探す
                    query = f"""
                        SELECT 
                            b.breeder_id, b.name, b.region,
                            COUNT(h_table.horse_id) as donor_available_count,
                            (
                                (SELECT COUNT(*) FROM sires s WHERE s.breeder_id = b.breeder_id AND s.is_active = 1) +
                                (SELECT COUNT(*) FROM dams d WHERE d.breeder_id = b.breeder_id AND d.is_active = 1)
                            ) as total_count
                        FROM breeders b
                        JOIN {'sires' if h_type == 'sire' else 'dams'} h_table 
                            ON b.breeder_id = h_table.breeder_id AND h_table.is_active = 1
                        WHERE b.region = ? AND b.breeder_id != ?
                        GROUP BY b.breeder_id
                        HAVING donor_available_count > 1
                        ORDER BY total_count DESC, donor_available_count DESC
                    """
                    donors = conn.execute(query, (region, breeder_id)).fetchall()

                    if donors:
                        donor = donors[0]
                        donor_breeder_id = donor["breeder_id"]

                        # 譲渡元から馬を1頭選ぶ
                        horse_query = f"""
                            SELECT horse_id FROM {'sires' if h_type == 'sire' else 'dams'}
                            WHERE breeder_id = ? AND is_active = 1
                            LIMIT 1
                        """
                        horse_row = conn.execute(horse_query, (donor_breeder_id,)).fetchone()
                        if horse_row:
                            target_horse_id = horse_row["horse_id"]
                            rec = self.transfer_horse(
                                horse_id=target_horse_id,
                                horse_type=h_type,
                                from_breeder_id=donor_breeder_id,
                                to_breeder_id=breeder_id,
                                reason="rescue",
                            )
                            records.append(rec)
                            donor_found = True
                            break

                if not donor_found:
                    # 見つからなかった場合のログ（通常50場あれば必ず見つかる）
                    pass

        return records

    def audit_and_balance_all(self) -> Dict[str, Any]:
        """
        全牧場の監査と自動調整を一括実行:
        1. 全牧場で最低条件（種牡馬1頭、繁殖牝馬1頭）をチェックし、不足があれば近隣最大牧場から譲渡。
        2. 全牧場で枠溢れをチェックし、拡張または近隣移籍を実行。
        """
        with self.db.session() as conn:
            all_breeders = conn.execute("SELECT breeder_id FROM breeders ORDER BY breeder_id ASC").fetchall()

        rescue_records: List[TransferRecord] = []
        overflow_records: List[TransferRecord] = []

        # Step 1: 最低条件の保証
        for b in all_breeders:
            res = self.ensure_minimum_population(b["breeder_id"])
            rescue_records.extend(res)

        # Step 2: 枠溢れの解消
        for b in all_breeders:
            ovf = self.handle_overflow(b["breeder_id"])
            overflow_records.extend(ovf)

        return {
            "rescues": rescue_records,
            "overflows": overflow_records,
            "total_rescues": len(rescue_records),
            "total_overflows": len(overflow_records),
        }
