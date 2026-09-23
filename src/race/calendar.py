"""
年間レースカレンダー進行コントローラ (CalendarController)
- 週進行・月進行・年進行
- 出走馬・騎手割り当てとレース実行
- 成績・賞金の一括更新
- 3歳未勝利足切り引退処理 (第28週)
- 年末ライフサイクル (LifecycleEngine) との連携
"""

from __future__ import annotations

import collections
from typing import Any, Dict, List, Optional, Set

from src.db.database import Database
from src.models.horse import Horse
from src.models.jockey import Jockey
from src.models.race import AgeRestriction, Race, RaceGrade, RaceResultRecord
from src.models.trainer import Trainer
from src.race.engine import RaceEngine
from src.race.entry import RaceEntryManager
from src.race.program import RaceProgramBuilder


class CalendarController:
    """レース年間カレンダー進行管理クラス"""

    def __init__(self, db: Database):
        self.db = db
        self.entry_manager = RaceEntryManager(db)
        self.engine = RaceEngine()
        self.program_builder = RaceProgramBuilder(db)

    def get_races_for_week(self, year: int, week: int, conn: Optional[Any] = None) -> List[Race]:
        """指定年・週のレース番組一覧を取得（未登録なら年間番組表を自動登録）"""
        check_query = "SELECT COUNT(*) FROM races WHERE year = ?"
        query = "SELECT * FROM races WHERE year = ? AND week = ? ORDER BY race_id ASC"

        if conn is not None:
            c = conn.execute(check_query, (year,)).fetchone()[0]
            if c == 0:
                self.program_builder.register_annual_program(year=year)
            cursor = conn.execute(query, (year, week))
            rows = cursor.fetchall()
        else:
            with self.db.session() as session_conn:
                c = session_conn.execute(check_query, (year,)).fetchone()[0]
                if c == 0:
                    self.program_builder.register_annual_program(year=year)
                cursor = session_conn.execute(query, (year, week))
                rows = cursor.fetchall()
        return [Race.from_row(r) for r in rows]

    def load_active_horses(self, conn: Optional[Any] = None) -> List[Horse]:
        """現役競走馬一覧を取得"""
        query = "SELECT * FROM horses WHERE is_active = 1 AND is_dead = 0"
        if conn is not None:
            cursor = conn.execute(query)
            rows = cursor.fetchall()
        else:
            with self.db.session() as session_conn:
                cursor = session_conn.execute(query)
                rows = cursor.fetchall()
        return [Horse.from_row(r) for r in rows]

    def load_all_jockeys(self, conn: Optional[Any] = None) -> List[Jockey]:
        """現役騎手一覧を取得"""
        query = "SELECT * FROM jockeys WHERE is_active = 1"
        if conn is not None:
            cursor = conn.execute(query)
            rows = cursor.fetchall()
        else:
            with self.db.session() as session_conn:
                cursor = session_conn.execute(query)
                rows = cursor.fetchall()
        return [Jockey.from_row(r) for r in rows]

    def load_all_trainers(self, conn: Optional[Any] = None) -> List[Trainer]:
        """調教師一覧を取得"""
        query = "SELECT * FROM trainers"
        if conn is not None:
            cursor = conn.execute(query)
            rows = cursor.fetchall()
        else:
            with self.db.session() as session_conn:
                cursor = session_conn.execute(query)
                rows = cursor.fetchall()
        return [Trainer.from_row(r) for r in rows]

    def load_trainer_jockey_map(self, conn: Optional[Any] = None) -> Dict[int, int]:
        """調教師ID -> 所属騎手ID のマッピングを取得"""
        query = "SELECT trainer_id, jockey_id FROM jockeys WHERE trainer_id IS NOT NULL AND is_active = 1"
        if conn is not None:
            cursor = conn.execute(query)
            rows = cursor.fetchall()
        else:
            with self.db.session() as session_conn:
                cursor = session_conn.execute(query)
                rows = cursor.fetchall()
        return {r['trainer_id']: r['jockey_id'] for r in rows}

    def run_week(self, year: int, week: int) -> Dict[str, Any]:
        """
        指定週のレースを一括実行し、結果を保存・更新
        """
        with self.db.session() as conn:
            races = self.get_races_for_week(year, week, conn=conn)
            if not races:
                return {
                    "year": year,
                    "week": week,
                    "races_run": 0,
                    "starters_count": 0,
                    "message": f"第{week}週のレース番組はありません。",
                }

            all_horses = self.load_active_horses(conn=conn)
            all_jockeys = self.load_all_jockeys(conn=conn)
            all_trainers = self.load_all_trainers(conn=conn)
            trainer_jockey_map = self.load_trainer_jockey_map(conn=conn)

            # 全馬の直近出走週を取得（中2週判定用）
            recent_runs_cur = conn.execute(
                """
                SELECT r.horse_id, rc.year, rc.week
                FROM results r
                JOIN races rc ON r.race_id = rc.race_id
                ORDER BY rc.year DESC, rc.week DESC
                """
            )
            last_runs_map: Dict[int, Tuple[int, int]] = {}
            for row in recent_runs_cur.fetchall():
                h_id = row['horse_id']
                if h_id not in last_runs_map:
                    last_runs_map[h_id] = (row['year'], row['week'])

            # 過去に重賞2着以内に入った馬のセット（3歳夏秋重賞出走資格用）
            top2_cur = conn.execute(
                """
                SELECT DISTINCT r.horse_id
                FROM results r
                JOIN races rc ON r.race_id = rc.race_id
                WHERE rc.grade IN ('G1', 'G2', 'G3') AND r.finish_position <= 2
                """
            )
            graded_top2_set: Set[int] = {row['horse_id'] for row in top2_cur.fetchall()}

            busy_horse_ids: Set[int] = set()
            total_starters = 0
            race_summaries = []

            # 上位グレード（G1〜3勝C）から優先して出走選定を実施
            grade_order = {
                RaceGrade.G1: 1, RaceGrade.G2: 2, RaceGrade.G3: 3, RaceGrade.L: 4, RaceGrade.OP: 4,
                RaceGrade.COND_3W: 5, RaceGrade.COND_2W: 6, RaceGrade.COND_1W: 7,
                RaceGrade.NEWCOMER: 8, RaceGrade.MAIDEN: 9,
            }
            sorted_races = sorted(races, key=lambda r: grade_order.get(r.grade, 10))

            for race in sorted_races:
                priority_horse_ids: List[int] = []
                if race.grade == RaceGrade.G1:
                    priority_horse_ids = self.entry_manager.get_priority_horses_for_g1(
                        race.name, year, conn=conn
                    )

                candidates = [
                    h for h in all_horses
                    if h.horse_id not in busy_horse_ids
                ]

                starters = self.entry_manager.select_starters(
                    race,
                    candidates,
                    priority_horse_ids=priority_horse_ids,
                    last_runs_map=last_runs_map,
                    graded_top2_set=graded_top2_set,
                    conn=conn,
                )

                if not starters or len(starters) < 4:
                    continue

                for h in starters:
                    if h.horse_id is not None:
                        busy_horse_ids.add(h.horse_id)
                        last_runs_map[h.horse_id] = (year, week)

                total_starters += len(starters)

                jockey_assignments = self.entry_manager.assign_jockeys(
                    starters, race, all_jockeys, trainer_jockey_map
                )

                results = self.engine.run_race(
                    race, starters, jockey_assignments, all_jockeys, all_trainers
                )

                self._save_race_results_and_update_stats(conn, race, results)

                winner_rec = next((r for r in results if r.finish_position == 1), None)
                winner_name = "不明"
                if winner_rec:
                    wh = next((h for h in starters if h.horse_id == winner_rec.horse_id), None)
                    if wh:
                        winner_name = wh.name

                race_summaries.append({
                    "race_id": race.race_id,
                    "name": race.name,
                    "grade": race.grade.value,
                    "distance": race.distance,
                    "surface": race.surface.value,
                    "starters": len(starters),
                    "winner": winner_name,
                    "winning_time": results[0].finish_time if results else 0.0,
                })

            retired_maidens_count = 0
            # 3月第1週（第9週）: 当歳馬（0歳）誕生・出産処理
            if week == 9:
                from src.core.breeding import BreedingEngine
                BreedingEngine(self.db).perform_spring_foaling(year, conn=conn)

            # 4月第1週（第13週）: 種付け交配処理
            if week == 13:
                from src.core.breeding import BreedingEngine
                BreedingEngine(self.db).perform_spring_mating(year, conn=conn)

            # 未勝利馬は3歳9月末（第36週）でカット
            if week == 36:
                retired_maidens_count = self._process_3yo_maiden_retirement(conn, year)

            # 100勝メモリアル記録の自動同期
            from src.race.awards import AwardsManager
            awards_mgr = AwardsManager(self.db, conn=conn)
            awards_mgr.sync_all_milestones(conn=conn)

            # 12月4週（第48週）終了後、年度代表馬および各部門賞を自動選出
            annual_awards = []
            if week == 48:
                annual_awards = awards_mgr.determine_annual_awards(year, conn=conn)

            return {
                "year": year,
                "week": week,
                "races_run": len(race_summaries),
                "starters_count": total_starters,
                "retired_maidens": retired_maidens_count,
                "annual_awards": annual_awards,
                "races": race_summaries,
            }

    def _save_race_results_and_update_stats(
        self, conn: Any, race: Race, results: List[RaceResultRecord]
    ) -> None:
        """レース結果の保存および関係者（馬・騎手・厩舎・馬主・牧場）の成績更新"""
        is_g1 = race.grade == RaceGrade.G1
        is_g2 = race.grade == RaceGrade.G2
        is_g3 = race.grade == RaceGrade.G3

        for res in results:
            conn.execute(
                """
                INSERT INTO results (
                    race_id, horse_id, jockey_id, trainer_id, finish_position,
                    finish_time, margin, time_diff, prize_awarded,
                    running_style_used, gate_number, last_3f, odds, replay_data_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    res.race_id,
                    res.horse_id,
                    res.jockey_id,
                    res.trainer_id,
                    res.finish_position,
                    res.finish_time,
                    res.margin,
                    res.time_diff,
                    res.prize_awarded,
                    res.running_style_used,
                    res.gate_number,
                    getattr(res, "last_3f", 0.0),
                    getattr(res, "odds", 0.0),
                    res.replay_data_json,
                ),
            )

            is_win = 1 if res.finish_position == 1 else 0

            major_win_name = ""
            if is_win and (is_g1 or is_g2 or is_g3):
                major_win_name = f"{race.name}({race.grade.value})"

            conn.execute(
                """
                UPDATE horses
                SET prize_money = prize_money + ?,
                    condition_prize_money = condition_prize_money + ?,
                    career_starts = career_starts + 1,
                    career_wins = career_wins + ?,
                    g1_wins = g1_wins + ?,
                    g2_wins = g2_wins + ?,
                    g3_wins = g3_wins + ?,
                    major_wins = CASE
                        WHEN ? != '' AND (major_wins IS NULL OR major_wins = '') THEN ?
                        WHEN ? != '' THEN major_wins || ', ' || ?
                        ELSE major_wins
                    END
                WHERE horse_id = ?
                """,
                (
                    res.prize_awarded,
                    res.condition_prize_awarded,
                    is_win,
                    1 if is_win and is_g1 else 0,
                    1 if is_win and is_g2 else 0,
                    1 if is_win and is_g3 else 0,
                    major_win_name, major_win_name,
                    major_win_name, major_win_name,
                    res.horse_id,
                ),
            )

            # 3. 騎手の戦績更新
            if res.jockey_id:
                exp_add = 0.5 if (is_g1 or is_g2 or is_g3) else 0.1
                conn.execute(
                    """
                    UPDATE jockeys
                    SET career_starts = career_starts + 1,
                        career_wins = career_wins + ?,
                        current_year_starts = current_year_starts + 1,
                        current_year_wins = current_year_wins + ?,
                        career_earnings = career_earnings + ?,
                        current_year_earnings = current_year_earnings + ?,
                        experience = MIN(100.0, experience + ?),
                        g1_wins = g1_wins + ?,
                        g2_wins = g2_wins + ?,
                        g3_wins = g3_wins + ?
                    WHERE jockey_id = ?
                    """,
                    (
                        is_win,
                        is_win,
                        res.prize_awarded,
                        res.prize_awarded,
                        exp_add,
                        1 if is_win and is_g1 else 0,
                        1 if is_win and is_g2 else 0,
                        1 if is_win and is_g3 else 0,
                        res.jockey_id,
                    ),
                )

            # 4. 調教師の戦績更新
            if res.trainer_id:
                conn.execute(
                    """
                    UPDATE trainers
                    SET career_starts = career_starts + 1,
                        career_wins = career_wins + ?,
                        current_year_starts = current_year_starts + 1,
                        current_year_wins = current_year_wins + ?,
                        current_year_earnings = current_year_earnings + ?,
                        career_earnings = career_earnings + ?,
                        current_year_g1 = current_year_g1 + ?,
                        current_year_g2 = current_year_g2 + ?,
                        current_year_g3 = current_year_g3 + ?,
                        g1_wins = g1_wins + ?,
                        g2_wins = g2_wins + ?,
                        g3_wins = g3_wins + ?
                    WHERE trainer_id = ?
                    """,
                    (
                        is_win,
                        is_win,
                        res.prize_awarded,
                        res.prize_awarded,
                        1 if is_win and is_g1 else 0,
                        1 if is_win and is_g2 else 0,
                        1 if is_win and is_g3 else 0,
                        1 if is_win and is_g1 else 0,
                        1 if is_win and is_g2 else 0,
                        1 if is_win and is_g3 else 0,
                        res.trainer_id,
                    ),
                )

            # 5. 馬主・生産牧場の賞金・戦績更新
            cur = conn.execute("SELECT owner_id, breeder_id FROM horses WHERE horse_id = ?", (res.horse_id,))
            h_row = cur.fetchone()
            if h_row:
                owner_id = h_row['owner_id']
                breeder_id = h_row['breeder_id']

                if owner_id:
                    owner_share = int(res.prize_awarded * 0.8)
                    conn.execute(
                        """
                        UPDATE owners
                        SET funds = funds + ?,
                            career_earnings = career_earnings + ?,
                            career_wins = career_wins + ?,
                            g1_wins = g1_wins + ?
                        WHERE owner_id = ?
                        """,
                        (
                            owner_share,
                            res.prize_awarded,
                            is_win,
                            1 if is_win and is_g1 else 0,
                            owner_id,
                        ),
                    )

                if breeder_id:
                    breeder_bonus = int(res.prize_awarded * 0.1)
                    conn.execute(
                        """
                        UPDATE breeders
                        SET funds = funds + ?,
                            career_earnings = career_earnings + ?,
                            current_year_earnings = current_year_earnings + ?,
                            current_year_starts = current_year_starts + 1,
                            current_year_wins = current_year_wins + ?,
                            career_starts = career_starts + 1,
                            career_wins = career_wins + ?,
                            g1_wins = g1_wins + ?
                        WHERE breeder_id = ?
                        """,
                        (
                            breeder_bonus,
                            res.prize_awarded,
                            res.prize_awarded,
                            is_win,
                            is_win,
                            1 if is_win and is_g1 else 0,
                            breeder_id,
                        ),
                    )

    def _process_3yo_maiden_retirement(self, conn: Any, year: int) -> int:
        """3歳未勝利馬（第36週・9月4週終了時で0勝の未出走・未勝利馬）の引退判定"""
        cursor = conn.execute(
            """
            SELECT horse_id, sex, breeder_id
            FROM horses
            WHERE age = 3 AND career_wins = 0 AND is_active = 1 AND is_dead = 0
            """
        )
        maidens = cursor.fetchall()
        retired_count = 0

        for m in maidens:
            h_id = m['horse_id']
            sex = m['sex']
            breeder_id = m['breeder_id']

            conn.execute(
                "UPDATE horses SET is_active = 0, retired_year = ?, trainer_id = NULL, jockey_id = NULL WHERE horse_id = ?",
                (year, h_id),
            )
            retired_count += 1

        return retired_count

    def run_month(self, year: int, month: int) -> List[Dict[str, Any]]:
        """1ヶ月（4週）分のレースを一括シミュレーション実行"""
        start_week = (month - 1) * 4 + 1
        end_week = month * 4
        month_results = []
        for w in range(start_week, end_week + 1):
            res = self.run_week(year, w)
            month_results.append(res)
        return month_results

    def run_year(self, year: int) -> Dict[str, Any]:
        """年間48週分の全レースを一括実行"""
        total_races = 0
        total_starters = 0
        total_retired_maidens = 0

        for w in range(1, 49):
            res = self.run_week(year, w)
            total_races += res.get("races_run", 0)
            total_starters += res.get("starters_count", 0)
            total_retired_maidens += res.get("retired_maidens", 0)

        return {
            "year": year,
            "total_weeks": 48,
            "total_races_run": total_races,
            "total_starters": total_starters,
            "retired_maidens": total_retired_maidens,
        }
