"""
リーディング集計モジュール (Rankings & Leaderboards)
- 騎手リーディング
- 調教師リーディング
- 馬主リーディング
- 生産牧場リーディング
- サイアー（種牡馬）リーディング
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from src.db.database import Database


class RankingManager:
    """各種リーディングランキング集計クラス"""

    def __init__(self, db: Database):
        self.db = db

    def get_jockey_rankings(self, limit: int = 20) -> List[Dict[str, Any]]:
        """騎手リーディング（勝利数順）"""
        query = """
        SELECT
            jockey_id, name, location, is_free,
            career_starts, career_wins,
            g1_wins, g2_wins, g3_wins,
            career_earnings AS prize_money,
            CASE WHEN career_starts > 0
                 THEN ROUND(CAST(career_wins AS REAL) / career_starts, 3)
                 ELSE 0.0 END AS win_rate
        FROM jockeys
        WHERE career_starts > 0
        ORDER BY career_wins DESC, career_earnings DESC
        LIMIT ?
        """
        with self.db.session() as conn:
            cursor = conn.execute(query, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_trainer_rankings(self, limit: int = 20) -> List[Dict[str, Any]]:
        """調教師リーディング（勝利数順）"""
        query = """
        SELECT
            trainer_id, name, location, specialty, skill_level,
            career_starts, career_wins,
            g1_wins, g2_wins, g3_wins,
            career_earnings AS prize_money,
            CASE WHEN career_starts > 0
                 THEN ROUND(CAST(career_wins AS REAL) / career_starts, 3)
                 ELSE 0.0 END AS win_rate
        FROM trainers
        WHERE career_starts > 0
        ORDER BY career_wins DESC, career_earnings DESC
        LIMIT ?
        """
        with self.db.session() as conn:
            cursor = conn.execute(query, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_owner_rankings(self, limit: int = 20) -> List[Dict[str, Any]]:
        """馬主リーディング（獲得賞金順）"""
        query = """
        SELECT
            owner_id, name, prefix, funds,
            career_wins, g1_wins,
            career_earnings AS total_prize_money
        FROM owners
        WHERE career_earnings > 0 OR career_wins > 0
        ORDER BY career_earnings DESC, career_wins DESC
        LIMIT ?
        """
        with self.db.session() as conn:
            cursor = conn.execute(query, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_breeder_rankings(self, limit: int = 20) -> List[Dict[str, Any]]:
        """生産牧場リーディング（獲得賞金順）"""
        query = """
        SELECT
            breeder_id, name, region, funds,
            career_wins, g1_wins,
            career_earnings AS total_prize_money
        FROM breeders
        WHERE career_earnings > 0 OR career_wins > 0
        ORDER BY career_earnings DESC, g1_wins DESC
        LIMIT ?
        """
        with self.db.session() as conn:
            cursor = conn.execute(query, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_sire_rankings(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        サイアー（種牡馬）リーディング
        - 産駒獲得賞金
        - 産駒勝利数
        - AEI (アーニングインデックス)
        """
        query = """
        SELECT
            s.sire_id,
            s.sire_line,
            h_sire.name AS sire_name,
            COUNT(h_progeny.horse_id) AS progeny_count,
            SUM(h_progeny.career_starts) AS progeny_starts,
            SUM(h_progeny.career_wins) AS progeny_wins,
            SUM(h_progeny.g1_wins) AS progeny_g1_wins,
            SUM(h_progeny.prize_money) AS progeny_prize_money
        FROM sires s
        JOIN horses h_sire ON s.horse_id = h_sire.horse_id
        LEFT JOIN horses h_progeny ON h_progeny.sire_id = s.horse_id
        GROUP BY s.sire_id
        HAVING progeny_prize_money > 0 OR progeny_wins > 0
        ORDER BY progeny_prize_money DESC, progeny_wins DESC
        LIMIT ?
        """
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

            cursor = conn.execute(query, (limit,))
            rows = cursor.fetchall()

            rankings = []
            for r in rows:
                data = dict(r)
                p_count = data['progeny_count'] or 1
                p_prize = data['progeny_prize_money'] or 0
                sire_avg = p_prize / p_count
                aei = round(sire_avg / global_avg_prize, 2) if global_avg_prize > 0 else 1.00
                data['aei'] = aei
                rankings.append(data)

            return rankings
