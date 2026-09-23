"""
リーディング集計モジュール (Rankings & Leaderboards)
- 騎手リーディング [1着-2着-3着-着外], [G1-G2-G3], 代表乗鞍
- 調教師リーディング [1着-2着-3着-着外], [G1-G2-G3], 代表持ち馬
- 馬主リーディング [1着-2着-3着-着外], [G1-G2-G3], 代表持ち馬
- 生産牧場リーディング [1着-2着-3着-着外], [G1-G2-G3], 代表産駒
- サイアー（種牡馬）リーディング [1着-2着-3着-着外], [G1-G2-G3], 代表産駒, 現役産駒一覧
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from src.db.database import Database


class RankingManager:
    """各種リーディングランキング集計クラス"""

    def __init__(self, db: Database):
        self.db = db

    def _get_current_year(self) -> int:
        """レース結果が存在する最新年度、または1年目を返す"""
        with self.db.session() as conn:
            row = conn.execute(
                """
                SELECT MAX(r.year) as max_y
                FROM results res
                JOIN races r ON res.race_id = r.race_id
                """
            ).fetchone()
            if row and row["max_y"]:
                return int(row["max_y"])
            return 1

    def get_jockey_rankings(self, is_career: bool = False, limit: int = 20) -> List[Dict[str, Any]]:
        """騎手リーディング"""
        cur_year = self._get_current_year()

        if is_career:
            query = """
            SELECT
                j.jockey_id, j.name, j.age, j.location, j.is_free, j.career_wins, j.career_earnings,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END), 0) AS win_1,
                COALESCE(SUM(CASE WHEN res.finish_position = 2 THEN 1 ELSE 0 END), 0) AS win_2,
                COALESCE(SUM(CASE WHEN res.finish_position = 3 THEN 1 ELSE 0 END), 0) AS win_3,
                COALESCE(SUM(CASE WHEN res.finish_position >= 4 THEN 1 ELSE 0 END), 0) AS win_out,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G1' THEN 1 ELSE 0 END), 0) AS g1_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G2' THEN 1 ELSE 0 END), 0) AS g2_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G3' THEN 1 ELSE 0 END), 0) AS g3_cnt,
                COALESCE(SUM(res.prize_awarded), 0) AS total_earnings,
                COUNT(res.result_id) AS total_starts
            FROM jockeys j
            LEFT JOIN results res ON j.jockey_id = res.jockey_id
            LEFT JOIN races r ON res.race_id = r.race_id
            GROUP BY j.jockey_id
            HAVING total_starts > 0 OR win_1 > 0 OR j.is_active = 1
            ORDER BY win_1 DESC, win_2 DESC, win_3 DESC, total_earnings DESC
            LIMIT ?
            """
            params = (limit,)
        else:
            query = """
            SELECT
                j.jockey_id, j.name, j.age, j.location, j.is_free, j.career_wins, j.career_earnings,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END), 0) AS win_1,
                COALESCE(SUM(CASE WHEN res.finish_position = 2 THEN 1 ELSE 0 END), 0) AS win_2,
                COALESCE(SUM(CASE WHEN res.finish_position = 3 THEN 1 ELSE 0 END), 0) AS win_3,
                COALESCE(SUM(CASE WHEN res.finish_position >= 4 THEN 1 ELSE 0 END), 0) AS win_out,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G1' THEN 1 ELSE 0 END), 0) AS g1_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G2' THEN 1 ELSE 0 END), 0) AS g2_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G3' THEN 1 ELSE 0 END), 0) AS g3_cnt,
                COALESCE(SUM(res.prize_awarded), 0) AS total_earnings,
                COUNT(res.result_id) AS total_starts
            FROM jockeys j
            LEFT JOIN (
                SELECT res_inner.*, r_inner.grade, r_inner.year
                FROM results res_inner
                JOIN races r_inner ON res_inner.race_id = r_inner.race_id
                WHERE r_inner.year = ?
            ) res ON j.jockey_id = res.jockey_id
            LEFT JOIN races r ON res.race_id = r.race_id
            GROUP BY j.jockey_id
            HAVING total_starts > 0 OR win_1 > 0 OR j.is_active = 1
            ORDER BY win_1 DESC, win_2 DESC, win_3 DESC, total_earnings DESC
            LIMIT ?
            """
            params = (cur_year, limit)

        with self.db.session() as conn:
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                starts = d["win_1"] + d["win_2"] + d["win_3"] + d["win_out"]
                d["starts"] = starts
                d["win_rate"] = round(d["win_1"] / starts, 3) if starts > 0 else 0.0

                # 代表乗鞍 (重賞勝ちのある現役馬、最大3頭)
                rep_horses = conn.execute(
                    """
                    SELECT DISTINCT h.name, h.g1_wins, (h.g1_wins + h.g2_wins + h.g3_wins) as total_graded, h.prize_money
                    FROM horses h
                    WHERE h.is_active = 1
                      AND (h.jockey_id = ? OR h.horse_id IN (SELECT horse_id FROM results WHERE jockey_id = ?))
                      AND (h.g1_wins > 0 OR h.g2_wins > 0 OR h.g3_wins > 0)
                    ORDER BY h.g1_wins DESC, total_graded DESC, h.prize_money DESC
                    LIMIT 3
                    """,
                    (d["jockey_id"], d["jockey_id"]),
                ).fetchall()
                d["representative_horses"] = [h["name"] for h in rep_horses]
                results.append(d)

            return results

    def get_trainer_rankings(self, is_career: bool = False, limit: int = 20) -> List[Dict[str, Any]]:
        """調教師リーディング"""
        cur_year = self._get_current_year()

        if is_career:
            query = """
            SELECT
                t.trainer_id, t.name, t.age, t.location, t.specialty, t.skill_level, t.career_wins, t.career_earnings,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END), 0) AS win_1,
                COALESCE(SUM(CASE WHEN res.finish_position = 2 THEN 1 ELSE 0 END), 0) AS win_2,
                COALESCE(SUM(CASE WHEN res.finish_position = 3 THEN 1 ELSE 0 END), 0) AS win_3,
                COALESCE(SUM(CASE WHEN res.finish_position >= 4 THEN 1 ELSE 0 END), 0) AS win_out,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G1' THEN 1 ELSE 0 END), 0) AS g1_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G2' THEN 1 ELSE 0 END), 0) AS g2_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G3' THEN 1 ELSE 0 END), 0) AS g3_cnt,
                COALESCE(SUM(res.prize_awarded), 0) AS total_earnings,
                COUNT(res.result_id) AS total_starts
            FROM trainers t
            LEFT JOIN results res ON t.trainer_id = res.trainer_id
            LEFT JOIN races r ON res.race_id = r.race_id
            GROUP BY t.trainer_id
            HAVING total_starts > 0 OR win_1 > 0 OR t.trainer_id IS NOT NULL
            ORDER BY win_1 DESC, win_2 DESC, win_3 DESC, total_earnings DESC
            LIMIT ?
            """
            params = (limit,)
        else:
            query = """
            SELECT
                t.trainer_id, t.name, t.age, t.location, t.specialty, t.skill_level, t.career_wins, t.career_earnings,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END), 0) AS win_1,
                COALESCE(SUM(CASE WHEN res.finish_position = 2 THEN 1 ELSE 0 END), 0) AS win_2,
                COALESCE(SUM(CASE WHEN res.finish_position = 3 THEN 1 ELSE 0 END), 0) AS win_3,
                COALESCE(SUM(CASE WHEN res.finish_position >= 4 THEN 1 ELSE 0 END), 0) AS win_out,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G1' THEN 1 ELSE 0 END), 0) AS g1_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G2' THEN 1 ELSE 0 END), 0) AS g2_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G3' THEN 1 ELSE 0 END), 0) AS g3_cnt,
                COALESCE(SUM(res.prize_awarded), 0) AS total_earnings,
                COUNT(res.result_id) AS total_starts
            FROM trainers t
            LEFT JOIN (
                SELECT res_inner.*, r_inner.grade, r_inner.year
                FROM results res_inner
                JOIN races r_inner ON res_inner.race_id = r_inner.race_id
                WHERE r_inner.year = ?
            ) res ON t.trainer_id = res.trainer_id
            LEFT JOIN races r ON res.race_id = r.race_id
            GROUP BY t.trainer_id
            HAVING total_starts > 0 OR win_1 > 0 OR t.trainer_id IS NOT NULL
            ORDER BY win_1 DESC, win_2 DESC, win_3 DESC, total_earnings DESC
            LIMIT ?
            """
            params = (cur_year, limit)

        with self.db.session() as conn:
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                starts = d["win_1"] + d["win_2"] + d["win_3"] + d["win_out"]
                d["starts"] = starts
                d["win_rate"] = round(d["win_1"] / starts, 3) if starts > 0 else 0.0

                # 代表持ち馬 (重賞勝ちのある現役管理馬、最大3頭)
                rep_horses = conn.execute(
                    """
                    SELECT h.name, h.g1_wins, (h.g1_wins + h.g2_wins + h.g3_wins) as total_graded, h.prize_money
                    FROM horses h
                    WHERE h.is_active = 1
                      AND h.trainer_id = ?
                      AND (h.g1_wins > 0 OR h.g2_wins > 0 OR h.g3_wins > 0)
                    ORDER BY h.g1_wins DESC, total_graded DESC, h.prize_money DESC
                    LIMIT 3
                    """,
                    (d["trainer_id"],),
                ).fetchall()
                d["representative_horses"] = [h["name"] for h in rep_horses]

                # 持ち馬数 & 勝ち馬数
                counts = conn.execute(
                    """
                    SELECT 
                        COUNT(*) AS h_count,
                        COUNT(CASE WHEN career_wins > 0 THEN 1 END) AS w_count
                    FROM horses
                    WHERE trainer_id = ? AND is_active = 1
                    """,
                    (d["trainer_id"],),
                ).fetchone()
                d["horse_count"] = counts["h_count"] if counts else 0
                d["winner_count"] = counts["w_count"] if counts else 0
                results.append(d)

            return results

    def get_owner_rankings(self, is_career: bool = False, limit: int = 20) -> List[Dict[str, Any]]:
        """馬主リーディング"""
        cur_year = self._get_current_year()

        if is_career:
            query = """
            SELECT
                o.owner_id, o.name, o.prefix, o.funds,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END), 0) AS win_1,
                COALESCE(SUM(CASE WHEN res.finish_position = 2 THEN 1 ELSE 0 END), 0) AS win_2,
                COALESCE(SUM(CASE WHEN res.finish_position = 3 THEN 1 ELSE 0 END), 0) AS win_3,
                COALESCE(SUM(CASE WHEN res.finish_position >= 4 THEN 1 ELSE 0 END), 0) AS win_out,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G1' THEN 1 ELSE 0 END), 0) AS g1_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G2' THEN 1 ELSE 0 END), 0) AS g2_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G3' THEN 1 ELSE 0 END), 0) AS g3_cnt,
                COALESCE(SUM(res.prize_awarded), 0) AS total_earnings,
                COUNT(res.result_id) AS total_starts
            FROM owners o
            JOIN horses h ON o.owner_id = h.owner_id
            LEFT JOIN results res ON h.horse_id = res.horse_id
            LEFT JOIN races r ON res.race_id = r.race_id
            GROUP BY o.owner_id
            HAVING total_starts > 0 OR total_earnings > 0 OR o.owner_id IS NOT NULL
            ORDER BY win_1 DESC, win_2 DESC, win_3 DESC, total_earnings DESC
            LIMIT ?
            """
            params = (limit,)
        else:
            query = """
            SELECT
                o.owner_id, o.name, o.prefix, o.funds,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END), 0) AS win_1,
                COALESCE(SUM(CASE WHEN res.finish_position = 2 THEN 1 ELSE 0 END), 0) AS win_2,
                COALESCE(SUM(CASE WHEN res.finish_position = 3 THEN 1 ELSE 0 END), 0) AS win_3,
                COALESCE(SUM(CASE WHEN res.finish_position >= 4 THEN 1 ELSE 0 END), 0) AS win_out,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G1' THEN 1 ELSE 0 END), 0) AS g1_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G2' THEN 1 ELSE 0 END), 0) AS g2_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G3' THEN 1 ELSE 0 END), 0) AS g3_cnt,
                COALESCE(SUM(res.prize_awarded), 0) AS total_earnings,
                COUNT(res.result_id) AS total_starts
            FROM owners o
            JOIN horses h ON o.owner_id = h.owner_id
            LEFT JOIN (
                SELECT res_inner.*, r_inner.grade, r_inner.year
                FROM results res_inner
                JOIN races r_inner ON res_inner.race_id = r_inner.race_id
                WHERE r_inner.year = ?
            ) res ON h.horse_id = res.horse_id
            LEFT JOIN races r ON res.race_id = r.race_id
            GROUP BY o.owner_id
            HAVING total_starts > 0 OR total_earnings > 0 OR o.owner_id IS NOT NULL
            ORDER BY win_1 DESC, win_2 DESC, win_3 DESC, total_earnings DESC
            LIMIT ?
            """
            params = (cur_year, limit)

        with self.db.session() as conn:
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                starts = d["win_1"] + d["win_2"] + d["win_3"] + d["win_out"]
                d["starts"] = starts

                # 代表持ち馬 (重賞勝ちのある現役所有馬、最大3頭)
                rep_horses = conn.execute(
                    """
                    SELECT h.name, h.g1_wins, (h.g1_wins + h.g2_wins + h.g3_wins) as total_graded, h.prize_money
                    FROM horses h
                    WHERE h.is_active = 1
                      AND h.owner_id = ?
                      AND (h.g1_wins > 0 OR h.g2_wins > 0 OR h.g3_wins > 0)
                    ORDER BY h.g1_wins DESC, total_graded DESC, h.prize_money DESC
                    LIMIT 3
                    """,
                    (d["owner_id"],),
                ).fetchall()
                d["representative_horses"] = [h["name"] for h in rep_horses]

                # 持ち馬数 & 勝ち馬数
                counts = conn.execute(
                    """
                    SELECT 
                        COUNT(*) AS h_count,
                        COUNT(CASE WHEN career_wins > 0 THEN 1 END) AS w_count
                    FROM horses
                    WHERE owner_id = ? AND is_active = 1
                    """,
                    (d["owner_id"],),
                ).fetchone()
                d["horse_count"] = counts["h_count"] if counts else 0
                d["winner_count"] = counts["w_count"] if counts else 0
                results.append(d)

            return results

    def get_breeder_rankings(self, is_career: bool = False, limit: int = 20) -> List[Dict[str, Any]]:
        """生産牧場リーディング"""
        cur_year = self._get_current_year()

        if is_career:
            query = """
            SELECT
                b.breeder_id, b.name, b.region, b.funds,
                (SELECT COUNT(*) FROM horses h_sire WHERE h_sire.breeder_id = b.breeder_id AND h_sire.is_sire = 1) AS sire_count,
                (SELECT COUNT(*) FROM horses h_dam WHERE h_dam.breeder_id = b.breeder_id AND h_dam.is_dam = 1) AS dam_count,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END), 0) AS win_1,
                COALESCE(SUM(CASE WHEN res.finish_position = 2 THEN 1 ELSE 0 END), 0) AS win_2,
                COALESCE(SUM(CASE WHEN res.finish_position = 3 THEN 1 ELSE 0 END), 0) AS win_3,
                COALESCE(SUM(CASE WHEN res.finish_position >= 4 THEN 1 ELSE 0 END), 0) AS win_out,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G1' THEN 1 ELSE 0 END), 0) AS g1_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G2' THEN 1 ELSE 0 END), 0) AS g2_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G3' THEN 1 ELSE 0 END), 0) AS g3_cnt,
                COALESCE(SUM(res.prize_awarded), 0) AS total_earnings,
                COUNT(res.result_id) AS total_starts
            FROM breeders b
            JOIN horses h ON b.breeder_id = h.breeder_id
            LEFT JOIN results res ON h.horse_id = res.horse_id
            LEFT JOIN races r ON res.race_id = r.race_id
            GROUP BY b.breeder_id
            HAVING total_starts > 0 OR total_earnings > 0 OR b.breeder_id IS NOT NULL
            ORDER BY win_1 DESC, win_2 DESC, win_3 DESC, total_earnings DESC
            LIMIT ?
            """
            params = (limit,)
        else:
            query = """
            SELECT
                b.breeder_id, b.name, b.region, b.funds,
                (SELECT COUNT(*) FROM horses h_sire WHERE h_sire.breeder_id = b.breeder_id AND h_sire.is_sire = 1) AS sire_count,
                (SELECT COUNT(*) FROM horses h_dam WHERE h_dam.breeder_id = b.breeder_id AND h_dam.is_dam = 1) AS dam_count,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END), 0) AS win_1,
                COALESCE(SUM(CASE WHEN res.finish_position = 2 THEN 1 ELSE 0 END), 0) AS win_2,
                COALESCE(SUM(CASE WHEN res.finish_position = 3 THEN 1 ELSE 0 END), 0) AS win_3,
                COALESCE(SUM(CASE WHEN res.finish_position >= 4 THEN 1 ELSE 0 END), 0) AS win_out,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G1' THEN 1 ELSE 0 END), 0) AS g1_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G2' THEN 1 ELSE 0 END), 0) AS g2_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G3' THEN 1 ELSE 0 END), 0) AS g3_cnt,
                COALESCE(SUM(res.prize_awarded), 0) AS total_earnings,
                COUNT(res.result_id) AS total_starts
            FROM breeders b
            JOIN horses h ON b.breeder_id = h.breeder_id
            LEFT JOIN (
                SELECT res_inner.*, r_inner.grade, r_inner.year
                FROM results res_inner
                JOIN races r_inner ON res_inner.race_id = r_inner.race_id
                WHERE r_inner.year = ?
            ) res ON h.horse_id = res.horse_id
            LEFT JOIN races r ON res.race_id = r.race_id
            GROUP BY b.breeder_id
            HAVING total_starts > 0 OR total_earnings > 0 OR b.breeder_id IS NOT NULL
            ORDER BY win_1 DESC, win_2 DESC, win_3 DESC, total_earnings DESC
            LIMIT ?
            """
            params = (cur_year, limit)

        with self.db.session() as conn:
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                starts = d["win_1"] + d["win_2"] + d["win_3"] + d["win_out"]
                d["starts"] = starts

                # 代表産駒 (重賞勝ちのある現役生産馬、最大3頭)
                rep_horses = conn.execute(
                    """
                    SELECT h.name, h.g1_wins, (h.g1_wins + h.g2_wins + h.g3_wins) as total_graded, h.prize_money
                    FROM horses h
                    WHERE h.is_active = 1
                      AND h.breeder_id = ?
                      AND (h.g1_wins > 0 OR h.g2_wins > 0 OR h.g3_wins > 0)
                    ORDER BY h.g1_wins DESC, total_graded DESC, h.prize_money DESC
                    LIMIT 3
                    """,
                    (d["breeder_id"],),
                ).fetchall()
                d["representative_horses"] = [h["name"] for h in rep_horses]

                # 持ち馬数 & 勝ち馬数 (生産馬ベース)
                counts = conn.execute(
                    """
                    SELECT 
                        COUNT(*) AS h_count,
                        COUNT(CASE WHEN career_wins > 0 THEN 1 END) AS w_count
                    FROM horses
                    WHERE breeder_id = ? AND is_active = 1
                    """,
                    (d["breeder_id"],),
                ).fetchone()
                d["horse_count"] = counts["h_count"] if counts else 0
                d["winner_count"] = counts["w_count"] if counts else 0
                results.append(d)

            return results

    def get_sire_rankings(
        self, is_career: bool = False, limit: int = 20, age_filter: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        サイアー（種牡馬）リーディング
        - age_filter: None=総合, 2=2歳馬, 3=3歳馬
        """
        cur_year = self._get_current_year()

        if is_career:
            age_clause = "AND (r.year - h_progeny.birth_year + 1) = ?" if age_filter else ""
            query = f"""
            SELECT
                s.sire_id,
                s.horse_id AS sire_horse_id,
                s.sire_line,
                s.stud_fee,
                h_sire.name AS sire_name,
                (SELECT COUNT(*) FROM horses h_act WHERE h_act.sire_id = s.horse_id AND h_act.is_active = 1) AS active_progeny_count,
                COUNT(DISTINCT h_progeny.horse_id) AS progeny_count,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END), 0) AS win_1,
                COALESCE(SUM(CASE WHEN res.finish_position = 2 THEN 1 ELSE 0 END), 0) AS win_2,
                COALESCE(SUM(CASE WHEN res.finish_position = 3 THEN 1 ELSE 0 END), 0) AS win_3,
                COALESCE(SUM(CASE WHEN res.finish_position >= 4 THEN 1 ELSE 0 END), 0) AS win_out,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G1' THEN 1 ELSE 0 END), 0) AS g1_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G2' THEN 1 ELSE 0 END), 0) AS g2_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G3' THEN 1 ELSE 0 END), 0) AS g3_cnt,
                COALESCE(SUM(res.prize_awarded), 0) AS total_earnings,
                COUNT(res.result_id) AS total_starts
            FROM sires s
            JOIN horses h_sire ON s.horse_id = h_sire.horse_id
            LEFT JOIN horses h_progeny ON h_progeny.sire_id = s.horse_id
            LEFT JOIN results res ON h_progeny.horse_id = res.horse_id
            LEFT JOIN races r ON res.race_id = r.race_id {age_clause}
            GROUP BY s.sire_id
            HAVING total_earnings > 0 OR win_1 > 0 OR s.sire_id IS NOT NULL
            ORDER BY win_1 DESC, win_2 DESC, win_3 DESC, total_earnings DESC
            LIMIT ?
            """
            params = (age_filter, limit) if age_filter else (limit,)
        else:
            age_clause = "AND (res.year - h_progeny.birth_year + 1) = ?" if age_filter else ""
            query = f"""
            SELECT
                s.sire_id,
                s.horse_id AS sire_horse_id,
                s.sire_line,
                s.stud_fee,
                h_sire.name AS sire_name,
                (SELECT COUNT(*) FROM horses h_act WHERE h_act.sire_id = s.horse_id AND h_act.is_active = 1) AS active_progeny_count,
                COUNT(DISTINCT h_progeny.horse_id) AS progeny_count,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END), 0) AS win_1,
                COALESCE(SUM(CASE WHEN res.finish_position = 2 THEN 1 ELSE 0 END), 0) AS win_2,
                COALESCE(SUM(CASE WHEN res.finish_position = 3 THEN 1 ELSE 0 END), 0) AS win_3,
                COALESCE(SUM(CASE WHEN res.finish_position >= 4 THEN 1 ELSE 0 END), 0) AS win_out,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G1' THEN 1 ELSE 0 END), 0) AS g1_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G2' THEN 1 ELSE 0 END), 0) AS g2_cnt,
                COALESCE(SUM(CASE WHEN res.finish_position = 1 AND r.grade = 'G3' THEN 1 ELSE 0 END), 0) AS g3_cnt,
                COALESCE(SUM(res.prize_awarded), 0) AS total_earnings,
                COUNT(res.result_id) AS total_starts
            FROM sires s
            JOIN horses h_sire ON s.horse_id = h_sire.horse_id
            LEFT JOIN horses h_progeny ON h_progeny.sire_id = s.horse_id
            LEFT JOIN (
                SELECT res_inner.*, r_inner.grade, r_inner.year
                FROM results res_inner
                JOIN races r_inner ON res_inner.race_id = r_inner.race_id
                WHERE r_inner.year = ?
            ) res ON h_progeny.horse_id = res.horse_id
            LEFT JOIN races r ON res.race_id = r.race_id
            WHERE 1=1 {age_clause}
            GROUP BY s.sire_id
            HAVING total_earnings > 0 OR win_1 > 0 OR s.sire_id IS NOT NULL
            ORDER BY win_1 DESC, win_2 DESC, win_3 DESC, total_earnings DESC
            LIMIT ?
            """
            params = (cur_year, age_filter, limit) if age_filter else (cur_year, limit)

        with self.db.session() as conn:
            cur_avg = conn.execute(
                """
                SELECT AVG(prize_money) AS avg_prize
                FROM horses
                WHERE sire_id IS NOT NULL AND career_starts > 0
                """
            )
            row_avg = cur_avg.fetchone()
            global_avg_prize = row_avg['avg_prize'] if row_avg and row_avg['avg_prize'] else 1.0

            rows = conn.execute(query, params).fetchall()
            rankings = []
            for r in rows:
                data = dict(r)
                p_count = data['progeny_count'] or 1
                p_prize = data['total_earnings'] or 0
                sire_avg = p_prize / p_count
                aei = round(sire_avg / global_avg_prize, 2) if global_avg_prize > 0 else 1.00
                data['aei'] = aei

                # 代表産駒 (重賞勝ちのある現役産駒、最大3頭)
                rep_horses = conn.execute(
                    """
                    SELECT h.name, h.g1_wins, (h.g1_wins + h.g2_wins + h.g3_wins) as total_graded, h.prize_money
                    FROM horses h
                    WHERE h.is_active = 1
                      AND h.sire_id = ?
                      AND (h.g1_wins > 0 OR h.g2_wins > 0 OR h.g3_wins > 0)
                    ORDER BY h.g1_wins DESC, total_graded DESC, h.prize_money DESC
                    LIMIT 3
                    """,
                    (data["sire_horse_id"],),
                ).fetchall()
                data["representative_horses"] = [h["name"] for h in rep_horses]
                rankings.append(data)

            return rankings

    def get_sire_progenies(self, sire_horse_id: int) -> List[Dict[str, Any]]:
        """種牡馬の現役産駒一覧（獲得賞金降順）"""
        query = """
        SELECT
            h.horse_id,
            h.name,
            h.sex,
            h.age,
            h.running_style,
            t.name AS trainer_name,
            o.name AS owner_name,
            h.career_starts,
            h.career_wins,
            h.g1_wins,
            h.g2_wins,
            h.g3_wins,
            h.major_wins,
            h.prize_money
        FROM horses h
        LEFT JOIN trainers t ON h.trainer_id = t.trainer_id
        LEFT JOIN owners o ON h.owner_id = o.owner_id
        WHERE h.sire_id = ? AND h.is_active = 1
        ORDER BY h.prize_money DESC, h.career_wins DESC, h.horse_id ASC
        """
        with self.db.session() as conn:
            rows = conn.execute(query, (sire_horse_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_ranking_history(self, category: str, entity_id: int) -> List[Dict[str, Any]]:
        """
        指定エンティティ（騎手・調教師・馬主・牧場・種牡馬）の各年度における順位推移履歴を取得
        category: 'jockey', 'trainer', 'owner', 'breeder', 'sire'
        戻り値: [{'year': 1, 'rank': 3, 'wins': 45, 'earnings': 850000000, 'name': '...'}, ...]
        """
        with self.db.session() as conn:
            # 全開催年度を取得
            years_rows = conn.execute(
                "SELECT DISTINCT year FROM races ORDER BY year ASC"
            ).fetchall()
            years = [r["year"] for r in years_rows]
            if not years:
                years = [1]

            history = []

            for y in years:
                if category == "jockey":
                    q = """
                    SELECT j.jockey_id AS id, j.name,
                           COALESCE(SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END), 0) AS win_1,
                           COALESCE(SUM(CASE WHEN res.finish_position = 2 THEN 1 ELSE 0 END), 0) AS win_2,
                           COALESCE(SUM(CASE WHEN res.finish_position = 3 THEN 1 ELSE 0 END), 0) AS win_3,
                           COALESCE(SUM(res.prize_awarded), 0) AS earnings
                    FROM jockeys j
                    LEFT JOIN (
                        SELECT res_sub.* 
                        FROM results res_sub
                        JOIN races r_sub ON res_sub.race_id = r_sub.race_id
                        WHERE r_sub.year = ?
                    ) res ON j.jockey_id = res.jockey_id
                    GROUP BY j.jockey_id
                    ORDER BY win_1 DESC, win_2 DESC, win_3 DESC, earnings DESC, j.jockey_id ASC
                    """
                elif category == "trainer":
                    q = """
                    SELECT t.trainer_id AS id, t.name,
                           COALESCE(SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END), 0) AS win_1,
                           COALESCE(SUM(CASE WHEN res.finish_position = 2 THEN 1 ELSE 0 END), 0) AS win_2,
                           COALESCE(SUM(CASE WHEN res.finish_position = 3 THEN 1 ELSE 0 END), 0) AS win_3,
                           COALESCE(SUM(res.prize_awarded), 0) AS earnings
                    FROM trainers t
                    LEFT JOIN (
                        SELECT res_sub.*, h.trainer_id
                        FROM results res_sub
                        JOIN races r_sub ON res_sub.race_id = r_sub.race_id
                        JOIN horses h ON res_sub.horse_id = h.horse_id
                        WHERE r_sub.year = ?
                    ) res ON t.trainer_id = res.trainer_id
                    GROUP BY t.trainer_id
                    ORDER BY win_1 DESC, win_2 DESC, win_3 DESC, earnings DESC, t.trainer_id ASC
                    """
                elif category == "owner":
                    q = """
                    SELECT o.owner_id AS id, o.name,
                           COALESCE(SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END), 0) AS win_1,
                           COALESCE(SUM(CASE WHEN res.finish_position = 2 THEN 1 ELSE 0 END), 0) AS win_2,
                           COALESCE(SUM(CASE WHEN res.finish_position = 3 THEN 1 ELSE 0 END), 0) AS win_3,
                           COALESCE(SUM(res.prize_awarded), 0) AS earnings
                    FROM owners o
                    LEFT JOIN (
                        SELECT res_sub.*, h.owner_id
                        FROM results res_sub
                        JOIN races r_sub ON res_sub.race_id = r_sub.race_id
                        JOIN horses h ON res_sub.horse_id = h.horse_id
                        WHERE r_sub.year = ?
                    ) res ON o.owner_id = res.owner_id
                    GROUP BY o.owner_id
                    ORDER BY win_1 DESC, win_2 DESC, win_3 DESC, earnings DESC, o.owner_id ASC
                    """
                elif category == "breeder":
                    q = """
                    SELECT b.breeder_id AS id, b.name,
                           COALESCE(SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END), 0) AS win_1,
                           COALESCE(SUM(CASE WHEN res.finish_position = 2 THEN 1 ELSE 0 END), 0) AS win_2,
                           COALESCE(SUM(CASE WHEN res.finish_position = 3 THEN 1 ELSE 0 END), 0) AS win_3,
                           COALESCE(SUM(res.prize_awarded), 0) AS earnings
                    FROM breeders b
                    LEFT JOIN (
                        SELECT res_sub.*, h.breeder_id
                        FROM results res_sub
                        JOIN races r_sub ON res_sub.race_id = r_sub.race_id
                        JOIN horses h ON res_sub.horse_id = h.horse_id
                        WHERE r_sub.year = ?
                    ) res ON b.breeder_id = res.breeder_id
                    GROUP BY b.breeder_id
                    ORDER BY win_1 DESC, win_2 DESC, win_3 DESC, earnings DESC, b.breeder_id ASC
                    """
                elif category == "sire":
                    q = """
                    SELECT s.sire_id AS id, h_sire.name,
                           COALESCE(SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END), 0) AS win_1,
                           COALESCE(SUM(CASE WHEN res.finish_position = 2 THEN 1 ELSE 0 END), 0) AS win_2,
                           COALESCE(SUM(CASE WHEN res.finish_position = 3 THEN 1 ELSE 0 END), 0) AS win_3,
                           COALESCE(SUM(res.prize_awarded), 0) AS earnings
                    FROM sires s
                    JOIN horses h_sire ON s.horse_id = h_sire.horse_id
                    LEFT JOIN (
                        SELECT res_sub.*, h_progeny.sire_id
                        FROM results res_sub
                        JOIN races r_sub ON res_sub.race_id = r_sub.race_id
                        JOIN horses h_progeny ON res_sub.horse_id = h_progeny.horse_id
                        WHERE r_sub.year = ?
                    ) res ON s.horse_id = res.sire_id
                    GROUP BY s.sire_id
                    ORDER BY win_1 DESC, win_2 DESC, win_3 DESC, earnings DESC, s.sire_id ASC
                    """
                else:
                    return []

                ranked_rows = conn.execute(q, (y,)).fetchall()
                target_rank = None
                target_wins = 0
                target_earnings = 0
                target_name = ""

                for rank_idx, row in enumerate(ranked_rows, start=1):
                    if row["id"] == entity_id:
                        target_rank = rank_idx
                        target_wins = row["win_1"]
                        target_earnings = row["earnings"]
                        target_name = row["name"]
                        break

                if target_rank is not None:
                    history.append({
                        "year": y,
                        "rank": target_rank,
                        "wins": target_wins,
                        "earnings": target_earnings,
                        "name": target_name,
                    })

            return history
