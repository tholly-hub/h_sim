"""
年度代表馬および各部門賞 選考・記録モジュール (Annual Awards Engine)
- 12月4週終了時に当年成績を集計して表彰馬を自動選考
- カテゴリ:
  1. 年度代表馬 (Horse of the Year)
  2. 最優秀芝馬
  3. 最優秀ダート馬
  4. 最優秀中長距離馬 (1800m以上)
  5. 最優秀マイル・短距離馬 (1600m以下)
  6. 最優秀2歳牡馬
  7. 最優秀2歳牝馬
- 過去の年度代表馬推移の照会
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from src.db.database import Database


class AwardsManager:
    """年度代表馬・各部門賞管理クラス"""

    CATEGORIES = [
        ("horse_of_the_year", "年度代表馬"),
        ("best_turf_horse", "最優秀芝馬"),
        ("best_dirt_horse", "最優秀ダート馬"),
        ("best_intermediate_long", "最優秀中長距離馬"),
        ("best_sprinter_miler", "最優秀マイル・短距離馬"),
        ("best_older_female", "最優秀古馬牝馬"),
        ("best_2yo_colt", "最優秀2歳牡馬"),
        ("best_2yo_filly", "最優秀2歳牝馬"),
    ]

    def __init__(self, db: Database, conn: Optional[Any] = None):
        self.db = db
        self._ensure_table_exists(conn=conn)

    def _ensure_table_exists(self, conn: Optional[Any] = None) -> None:
        """annual_awards および milestone_records テーブルを作成"""
        ddl_awards = """
            CREATE TABLE IF NOT EXISTS annual_awards (
                award_id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                category TEXT NOT NULL,
                category_jp TEXT NOT NULL,
                horse_id INTEGER NOT NULL,
                horse_name TEXT NOT NULL,
                sex TEXT,
                age INTEGER,
                g1_wins INTEGER DEFAULT 0,
                g2_wins INTEGER DEFAULT 0,
                g3_wins INTEGER DEFAULT 0,
                year_prize INTEGER DEFAULT 0,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(year, category)
            )
        """
        ddl_milestones = """
            CREATE TABLE IF NOT EXISTS milestone_records (
                milestone_id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                entity_name TEXT NOT NULL,
                win_count INTEGER NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                week INTEGER NOT NULL,
                race_id INTEGER NOT NULL,
                race_name TEXT NOT NULL,
                horse_id INTEGER NOT NULL,
                horse_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(entity_type, entity_id, win_count)
            )
        """
        try:
            if conn is not None:
                conn.execute(ddl_awards)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_awards_year ON annual_awards(year)")
                conn.execute(ddl_milestones)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_milestones_type ON milestone_records(entity_type, win_count)")
            else:
                with self.db.session() as s_conn:
                    s_conn.execute(ddl_awards)
                    s_conn.execute("CREATE INDEX IF NOT EXISTS idx_awards_year ON annual_awards(year)")
                    s_conn.execute(ddl_milestones)
                    s_conn.execute("CREATE INDEX IF NOT EXISTS idx_milestones_type ON milestone_records(entity_type, win_count)")
        except Exception:
            pass

    def determine_annual_awards(self, year: int, conn: Optional[Any] = None) -> List[Dict[str, Any]]:
        """
        指定年度の年間成績を集計し、年度代表馬および各部門賞を決定してDBに保存
        """
        def _exec(db_conn):
            # 当年の全レース結果を馬ごとに集計
            query = """
                SELECT 
                    r.horse_id,
                    h.name,
                    h.sex,
                    h.age,
                    SUM(CASE WHEN rc.grade = 'G1' AND r.finish_position = 1 THEN 1 ELSE 0 END) as g1_wins,
                    SUM(CASE WHEN rc.grade = 'G2' AND r.finish_position = 1 THEN 1 ELSE 0 END) as g2_wins,
                    SUM(CASE WHEN rc.grade = 'G3' AND r.finish_position = 1 THEN 1 ELSE 0 END) as g3_wins,
                    SUM(CASE WHEN r.finish_position = 1 THEN 1 ELSE 0 END) as total_wins,
                    SUM(r.prize_awarded) as total_prize,
                    -- 芝成績
                    SUM(CASE WHEN rc.surface = 'turf' AND rc.grade = 'G1' AND r.finish_position = 1 THEN 1 ELSE 0 END) as turf_g1,
                    SUM(CASE WHEN rc.surface = 'turf' AND r.finish_position = 1 THEN 1 ELSE 0 END) as turf_wins,
                    SUM(CASE WHEN rc.surface = 'turf' THEN r.prize_awarded ELSE 0 END) as turf_prize,
                    -- ダート成績
                    SUM(CASE WHEN rc.surface = 'dirt' AND rc.grade = 'G1' AND r.finish_position = 1 THEN 1 ELSE 0 END) as dirt_g1,
                    SUM(CASE WHEN rc.surface = 'dirt' AND r.finish_position = 1 THEN 1 ELSE 0 END) as dirt_wins,
                    SUM(CASE WHEN rc.surface = 'dirt' THEN r.prize_awarded ELSE 0 END) as dirt_prize,
                    -- 中長距離 (1800m以上)
                    SUM(CASE WHEN rc.distance >= 1800 AND rc.grade = 'G1' AND r.finish_position = 1 THEN 1 ELSE 0 END) as long_g1,
                    SUM(CASE WHEN rc.distance >= 1800 AND r.finish_position = 1 THEN 1 ELSE 0 END) as long_wins,
                    SUM(CASE WHEN rc.distance >= 1800 THEN r.prize_awarded ELSE 0 END) as long_prize,
                    -- マイル短距離 (1600m以下)
                    SUM(CASE WHEN rc.distance <= 1600 AND rc.grade = 'G1' AND r.finish_position = 1 THEN 1 ELSE 0 END) as sprint_g1,
                    SUM(CASE WHEN rc.distance <= 1600 AND r.finish_position = 1 THEN 1 ELSE 0 END) as sprint_wins,
                    SUM(CASE WHEN rc.distance <= 1600 THEN r.prize_awarded ELSE 0 END) as sprint_prize
                FROM results r
                JOIN races rc ON r.race_id = rc.race_id
                JOIN horses h ON r.horse_id = h.horse_id
                WHERE rc.year = ?
                GROUP BY r.horse_id
            """
            rows = db_conn.execute(query, (year,)).fetchall()
            if not rows:
                return []

            stats = [dict(row) for row in rows]

            def score_horse(h, g1_k="g1_wins", g2_k="g2_wins", g3_k="g3_wins", prz_k="total_prize"):
                g1 = h.get(g1_k, 0)
                g2 = h.get(g2_k, 0)
                g3 = h.get(g3_k, 0)
                prz = h.get(prz_k, 0)
                return g1 * 100_000_000 + g2 * 10_000_000 + g3 * 2_000_000 + (prz // 1000)

            awards_result: List[Dict[str, Any]] = []

            # 2歳馬と3歳以上馬の集計データを分離（2歳馬が受賞できるのは最優秀2歳牡馬・最優秀2歳牝馬のみ）
            stats_2yo = [h for h in stats if h["age"] == 2]
            stats_3yo_up = [h for h in stats if h["age"] >= 3]

            # 1. 年度代表馬 (3歳以上のみ)
            sorted_hoty = sorted(stats_3yo_up, key=lambda h: score_horse(h), reverse=True)
            hoty = sorted_hoty[0] if sorted_hoty else None

            # 2. 最優秀2歳牡馬 (2歳牡馬のみ)
            c_2yo_colt = [h for h in stats_2yo if h["sex"] in ("colt", "horse")]
            best_2yo_colt = sorted(c_2yo_colt, key=lambda h: score_horse(h), reverse=True)[0] if c_2yo_colt else None

            # 3. 最優秀2歳牝馬 (2歳牝馬のみ)
            c_2yo_filly = [h for h in stats_2yo if h["sex"] in ("filly", "mare")]
            best_2yo_filly = sorted(c_2yo_filly, key=lambda h: score_horse(h), reverse=True)[0] if c_2yo_filly else None

            # 4. 最優秀芝馬 (3歳以上のみ)
            turf_candidates = [h for h in stats_3yo_up if h.get("turf_prize", 0) > 0]
            sorted_turf = sorted(turf_candidates, key=lambda h: score_horse(h, "turf_g1", "g2_wins", "g3_wins", "turf_prize"), reverse=True)
            best_turf = sorted_turf[0] if sorted_turf else None

            # 5. 最優秀ダート馬 (3歳以上のみ)
            dirt_candidates = [h for h in stats_3yo_up if h.get("dirt_prize", 0) > 0]
            sorted_dirt = sorted(dirt_candidates, key=lambda h: score_horse(h, "dirt_g1", "g2_wins", "g3_wins", "dirt_prize"), reverse=True)
            best_dirt = sorted_dirt[0] if sorted_dirt else None

            # 6. 最優秀中長距離馬 (3歳以上のみ)
            long_candidates = [h for h in stats_3yo_up if h.get("long_prize", 0) > 0]
            sorted_long = sorted(long_candidates, key=lambda h: score_horse(h, "long_g1", "g2_wins", "g3_wins", "long_prize"), reverse=True)
            best_long = sorted_long[0] if sorted_long else None

            # 7. 最優秀マイル・短距離馬 (3歳以上のみ)
            sprint_candidates = [h for h in stats_3yo_up if h.get("sprint_prize", 0) > 0]
            sorted_sprint = sorted(sprint_candidates, key=lambda h: score_horse(h, "sprint_g1", "g2_wins", "g3_wins", "sprint_prize"), reverse=True)
            best_sprint = sorted_sprint[0] if sorted_sprint else None

            # 8. 最優秀古馬牝馬 (4歳以上の牝馬のみ)
            c_older_female = [h for h in stats if h["age"] >= 4 and h["sex"] in ("filly", "mare") and h.get("total_prize", 0) > 0]
            best_older_female = sorted(c_older_female, key=lambda h: score_horse(h), reverse=True)[0] if c_older_female else None

            award_mappings = [
                ("horse_of_the_year", "年度代表馬", hoty, "当年GI最多勝利および最高獲得賞金"),
                ("best_turf_horse", "最優秀芝馬", best_turf, "芝レースにおける卓越した戦績"),
                ("best_dirt_horse", "最優秀ダート馬", best_dirt, "ダート重賞戦線における圧倒的活躍"),
                ("best_intermediate_long", "最優秀中長距離馬", best_long, "1800m〜3200m王道路線での優れた実績"),
                ("best_sprinter_miler", "最優秀マイル・短距離馬", best_sprint, "短距離・マイル戦線での傑出したスピード"),
                ("best_older_female", "最優秀古馬牝馬", best_older_female, "古馬牝馬戦線における優れた実績"),
                ("best_2yo_colt", "最優秀2歳牡馬", best_2yo_colt, "2歳牡馬王者としての活躍"),
                ("best_2yo_filly", "最優秀2歳牝馬", best_2yo_filly, "2歳牝馬女王としての活躍"),
            ]

            for cat_id, cat_jp, candidate, default_reason in award_mappings:
                if not candidate:
                    continue
                reason = f"{default_reason} (G1: {candidate['g1_wins']}勝, 年間賞金: {candidate['total_prize'] // 10000:,}万円)"
                db_conn.execute("""
                    INSERT OR REPLACE INTO annual_awards (
                        year, category, category_jp, horse_id, horse_name, sex, age,
                        g1_wins, g2_wins, g3_wins, year_prize, reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    year, cat_id, cat_jp, candidate["horse_id"], candidate["name"], candidate["sex"],
                    candidate["age"], candidate["g1_wins"], candidate["g2_wins"], candidate["g3_wins"],
                    candidate["total_prize"], reason
                ))
                awards_result.append({
                    "year": year,
                    "category": cat_id,
                    "category_jp": cat_jp,
                    "horse_name": candidate["name"],
                    "horse_id": candidate["horse_id"],
                    "g1_wins": candidate["g1_wins"],
                    "prize": candidate["total_prize"],
                    "reason": reason,
                })

            print(f"[表彰] 【{year}年度 JRA賞・年度代表馬選考】完了: 年度代表馬={hoty['name'] if hoty else '該当なし'}")
            return awards_result

        if conn is not None:
            return _exec(conn)
        else:
            with self.db.session() as s_conn:
                return _exec(s_conn)

    elect_annual_awards = determine_annual_awards

    def get_awards_by_year(self, year: int) -> List[Dict[str, Any]]:
        """指定年度の表彰馬一覧を取得"""
        with self.db.session() as conn:
            rows = conn.execute("""
                SELECT * FROM annual_awards
                WHERE year = ?
                ORDER BY award_id ASC
            """, (year,)).fetchall()
            return [dict(r) for r in rows]

    def get_horse_of_the_year_history(self) -> List[Dict[str, Any]]:
        """歴代の年度代表馬および全部門賞の推移を取得"""
        with self.db.session() as conn:
            rows = conn.execute("""
                SELECT * FROM annual_awards
                ORDER BY year DESC, award_id ASC
            """).fetchall()
            return [dict(r) for r in rows]

    # =========================================================================
    # 顕彰馬・特別功労・殿堂・100勝メモリアル管理機能
    # =========================================================================

    def get_hall_of_fame_horses(self) -> List[Dict[str, Any]]:
        """
        顕彰馬一覧を取得
        条件: 「異なるG1レースを5勝以上した馬」
        """
        query = """
            SELECT 
                h.horse_id,
                h.name AS horse_name,
                h.sex,
                h.age,
                h.prize_money,
                h.career_starts,
                h.career_wins,
                h.g1_wins,
                sire.name AS sire_name,
                dam.name AS dam_name,
                t.name AS trainer_name,
                o.name AS owner_name,
                b.name AS breeder_name,
                COUNT(DISTINCT rc.name) AS distinct_g1_wins,
                GROUP_CONCAT(DISTINCT rc.name) AS g1_titles
            FROM results res
            JOIN races rc ON res.race_id = rc.race_id
            JOIN horses h ON res.horse_id = h.horse_id
            LEFT JOIN horses sire ON h.sire_id = sire.horse_id
            LEFT JOIN horses dam ON h.dam_id = dam.horse_id
            LEFT JOIN trainers t ON h.trainer_id = t.trainer_id
            LEFT JOIN owners o ON h.owner_id = o.owner_id
            LEFT JOIN breeders b ON h.breeder_id = b.breeder_id
            WHERE rc.grade = 'G1' AND res.finish_position = 1
            GROUP BY h.horse_id
            HAVING distinct_g1_wins >= 5
            ORDER BY distinct_g1_wins DESC, h.g1_wins DESC, h.prize_money DESC
        """
        with self.db.session() as conn:
            rows = conn.execute(query).fetchall()
            return [dict(r) for r in rows]

    def get_special_merit_awards(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        特別功労者一覧を取得
        - 騎手: 通算1000勝以上 かつ G1レース10勝以上
        - 調教師: 通算500勝以上 かつ G1馬5頭以上 (厩舎名・調教師名を明記)
        """
        with self.db.session() as conn:
            # 騎手 特別功労 (通算1000勝以上 かつ G1 10勝以上)
            j_query = """
                SELECT 
                    j.jockey_id,
                    j.name,
                    j.name AS jockey_name,
                    j.location,
                    MAX(j.career_starts, COALESCE(r_stat.total_starts, 0)) AS career_starts,
                    MAX(j.career_wins, COALESCE(r_stat.total_wins, 0)) AS career_wins,
                    MAX(j.g1_wins, COALESCE(r_stat.g1_wins, 0)) AS g1_wins,
                    MAX(j.career_earnings, COALESCE(r_stat.total_earnings, 0)) AS career_earnings
                FROM jockeys j
                LEFT JOIN (
                    SELECT 
                        res.jockey_id,
                        COUNT(res.result_id) AS total_starts,
                        SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END) AS total_wins,
                        SUM(CASE WHEN res.finish_position = 1 AND rc.grade = 'G1' THEN 1 ELSE 0 END) AS g1_wins,
                        SUM(res.prize_awarded) AS total_earnings
                    FROM results res
                    JOIN races rc ON res.race_id = rc.race_id
                    GROUP BY res.jockey_id
                ) r_stat ON j.jockey_id = r_stat.jockey_id
                WHERE (j.career_wins >= 1000 OR r_stat.total_wins >= 1000)
                  AND (j.g1_wins >= 10 OR r_stat.g1_wins >= 10)
                ORDER BY career_wins DESC, g1_wins DESC
            """
            j_rows = conn.execute(j_query).fetchall()

            # 調教師 特別功労 (通算500勝以上 かつ G1馬5頭以上)
            t_query = """
                SELECT 
                    t.trainer_id,
                    t.name AS trainer_name,
                    t.name || '厩舎' AS stable_name,
                    t.location,
                    MAX(t.career_starts, COALESCE(r_stat.total_starts, 0)) AS total_starts,
                    MAX(t.career_wins, COALESCE(r_stat.total_wins, 0)) AS total_wins,
                    MAX(COALESCE(h_stat.g1_horse_cnt, 0), COALESCE(r_stat.g1_horse_count, 0)) AS g1_horse_count,
                    MAX(t.g1_wins, COALESCE(r_stat.g1_wins, 0)) AS g1_wins,
                    MAX(t.career_earnings, COALESCE(r_stat.total_earnings, 0)) AS career_earnings
                FROM trainers t
                LEFT JOIN (
                    SELECT 
                        res.trainer_id,
                        COUNT(res.result_id) AS total_starts,
                        SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END) AS total_wins,
                        COUNT(DISTINCT CASE WHEN res.finish_position = 1 AND rc.grade = 'G1' THEN res.horse_id ELSE NULL END) AS g1_horse_count,
                        SUM(CASE WHEN res.finish_position = 1 AND rc.grade = 'G1' THEN 1 ELSE 0 END) AS g1_wins,
                        SUM(res.prize_awarded) AS total_earnings
                    FROM results res
                    JOIN races rc ON res.race_id = rc.race_id
                    GROUP BY res.trainer_id
                ) r_stat ON t.trainer_id = r_stat.trainer_id
                LEFT JOIN (
                    SELECT 
                        h.trainer_id,
                        COUNT(DISTINCT h.horse_id) AS g1_horse_cnt
                    FROM horses h
                    WHERE h.g1_wins > 0
                    GROUP BY h.trainer_id
                ) h_stat ON t.trainer_id = h_stat.trainer_id
                WHERE (t.career_wins >= 500 OR r_stat.total_wins >= 500)
                  AND (COALESCE(h_stat.g1_horse_cnt, 0) >= 5 OR COALESCE(r_stat.g1_horse_count, 0) >= 5)
                ORDER BY total_wins DESC, g1_horse_count DESC
            """
            t_rows = conn.execute(t_query).fetchall()

            return {
                "jockeys": [dict(r) for r in j_rows],
                "trainers": [dict(r) for r in t_rows],
            }

    def get_hall_of_fame_legends(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        殿堂入り一覧を取得
        - 騎手: 通算2000勝以上 かつ G1レース20勝以上
        - 調教師: 通算1000勝以上 かつ G1馬10頭以上 (厩舎名・調教師名を明記)
        """
        with self.db.session() as conn:
            # 騎手 殿堂 (2000勝+G1 20勝)
            j_query = """
                SELECT 
                    j.jockey_id,
                    j.name,
                    j.name AS jockey_name,
                    j.location,
                    MAX(j.career_starts, COALESCE(r_stat.total_starts, 0)) AS career_starts,
                    MAX(j.career_wins, COALESCE(r_stat.total_wins, 0)) AS career_wins,
                    MAX(j.g1_wins, COALESCE(r_stat.g1_wins, 0)) AS g1_wins,
                    MAX(j.career_earnings, COALESCE(r_stat.total_earnings, 0)) AS career_earnings
                FROM jockeys j
                LEFT JOIN (
                    SELECT 
                        res.jockey_id,
                        COUNT(res.result_id) AS total_starts,
                        SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END) AS total_wins,
                        SUM(CASE WHEN res.finish_position = 1 AND rc.grade = 'G1' THEN 1 ELSE 0 END) AS g1_wins,
                        SUM(res.prize_awarded) AS total_earnings
                    FROM results res
                    JOIN races rc ON res.race_id = rc.race_id
                    GROUP BY res.jockey_id
                ) r_stat ON j.jockey_id = r_stat.jockey_id
                WHERE (j.career_wins >= 2000 OR r_stat.total_wins >= 2000)
                  AND (j.g1_wins >= 20 OR r_stat.g1_wins >= 20)
                ORDER BY career_wins DESC, g1_wins DESC
            """
            j_rows = conn.execute(j_query).fetchall()

            # 調教師 殿堂 (通算1000勝以上 かつ G1馬10頭以上)
            t_query = """
                SELECT 
                    t.trainer_id,
                    t.name AS trainer_name,
                    t.name || '厩舎' AS stable_name,
                    t.location,
                    MAX(t.career_starts, COALESCE(r_stat.total_starts, 0)) AS total_starts,
                    MAX(t.career_wins, COALESCE(r_stat.total_wins, 0)) AS total_wins,
                    MAX(COALESCE(h_stat.g1_horse_cnt, 0), COALESCE(r_stat.g1_horse_count, 0)) AS g1_horse_count,
                    MAX(t.g1_wins, COALESCE(r_stat.g1_wins, 0)) AS g1_wins,
                    MAX(t.career_earnings, COALESCE(r_stat.total_earnings, 0)) AS career_earnings
                FROM trainers t
                LEFT JOIN (
                    SELECT 
                        res.trainer_id,
                        COUNT(res.result_id) AS total_starts,
                        SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END) AS total_wins,
                        COUNT(DISTINCT CASE WHEN res.finish_position = 1 AND rc.grade = 'G1' THEN res.horse_id ELSE NULL END) AS g1_horse_count,
                        SUM(CASE WHEN res.finish_position = 1 AND rc.grade = 'G1' THEN 1 ELSE 0 END) AS g1_wins,
                        SUM(res.prize_awarded) AS total_earnings
                    FROM results res
                    JOIN races rc ON res.race_id = rc.race_id
                    GROUP BY res.trainer_id
                ) r_stat ON t.trainer_id = r_stat.trainer_id
                LEFT JOIN (
                    SELECT 
                        h.trainer_id,
                        COUNT(DISTINCT h.horse_id) AS g1_horse_cnt
                    FROM horses h
                    WHERE h.g1_wins > 0
                    GROUP BY h.trainer_id
                ) h_stat ON t.trainer_id = h_stat.trainer_id
                WHERE (t.career_wins >= 1000 OR r_stat.total_wins >= 1000)
                  AND (COALESCE(h_stat.g1_horse_cnt, 0) >= 10 OR COALESCE(r_stat.g1_horse_count, 0) >= 10)
                ORDER BY total_wins DESC, g1_horse_count DESC
            """
            t_rows = conn.execute(t_query).fetchall()

            return {
                "jockeys": [dict(r) for r in j_rows],
                "trainers": [dict(r) for r in t_rows],
            }

    def sync_all_milestones(self, conn: Optional[Any] = None) -> int:
        """
        全レース結果を走査し、騎手・調教師・馬主・生産牧場の100勝ごとメモリアル記録を同期・生成
        """
        def _exec(db_conn):
            self._ensure_table_exists(conn=db_conn)
            # 時系列順に勝利レコードを取得
            query = """
                SELECT 
                    res.result_id, res.finish_position, res.race_id, res.horse_id, res.jockey_id, res.trainer_id,
                    r.year, r.month, r.week, r.name AS race_name,
                    h.name AS horse_name, h.owner_id, h.breeder_id,
                    j.name AS jockey_name,
                    t.name AS trainer_name,
                    o.name AS owner_name,
                    b.name AS breeder_name
                FROM results res
                JOIN races r ON res.race_id = r.race_id
                JOIN horses h ON res.horse_id = h.horse_id
                LEFT JOIN jockeys j ON res.jockey_id = j.jockey_id
                LEFT JOIN trainers t ON res.trainer_id = t.trainer_id
                LEFT JOIN owners o ON h.owner_id = o.owner_id
                LEFT JOIN breeders b ON h.breeder_id = b.breeder_id
                WHERE res.finish_position = 1
                ORDER BY r.year ASC, r.week ASC, res.race_id ASC, res.result_id ASC
            """
            rows = db_conn.execute(query).fetchall()
            
            # 各主体の勝利数カウンタ
            win_counts = {
                "jockey": {},
                "trainer": {},
                "owner": {},
                "breeder": {},
            }
            inserted_count = 0

            for r in rows:
                entities = [
                    ("jockey", r["jockey_id"], r["jockey_name"]),
                    ("trainer", r["trainer_id"], r["trainer_name"]),
                    ("owner", r["owner_id"], r["owner_name"]),
                    ("breeder", r["breeder_id"], r["breeder_name"]),
                ]
                for e_type, e_id, e_name in entities:
                    if not e_id or not e_name:
                        continue
                    cur_w = win_counts[e_type].get(e_id, 0) + 1
                    win_counts[e_type][e_id] = cur_w

                    if cur_w % 100 == 0:
                        # 100勝ごとの節目達成！
                        db_conn.execute("""
                            INSERT OR IGNORE INTO milestone_records (
                                entity_type, entity_id, entity_name, win_count,
                                year, month, week, race_id, race_name, horse_id, horse_name
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            e_type, e_id, e_name, cur_w,
                            r["year"], r["month"], r["week"], r["race_id"], r["race_name"],
                            r["horse_id"], r["horse_name"]
                        ))
                        inserted_count += 1

            return inserted_count

        if conn is not None:
            return _exec(conn)
        else:
            with self.db.session() as s_conn:
                return _exec(s_conn)

    def get_milestone_records(self, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """100勝メモリアル記録一覧を取得"""
        query = "SELECT * FROM milestone_records WHERE 1=1"
        params = []
        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        query += " ORDER BY year DESC, week DESC, milestone_id DESC"

        with self.db.session() as conn:
            self._ensure_table_exists(conn=conn)
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]
