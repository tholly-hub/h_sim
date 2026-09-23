"""
データ閲覧・一覧表示モジュール (Viewer)
競走馬リスト、種牡馬リスト、繁殖牝馬リスト、個別詳細表示
"""

from __future__ import annotations

import os
import sqlite3
import webbrowser
from typing import Optional

from src.db.database import Database, get_db
from src.views.pedigree_builder import PedigreeBuilder


class HorseViewer:
    """各種リストおよび詳細データのコンソール表示クラス"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_db()

    def list_active_horses(
        self,
        age_filter: Optional[int] = None,
        sex_filter: Optional[str] = None,
        limit: int = 25,
        offset: int = 0,
    ) -> int:
        """
        現役競走馬リストを表示
        Returns:
            総該当頭数
        """
        query = """
            SELECT 
                h.horse_id, h.name, h.sex, h.age, 
                h.mstn_type, h.speed, h.stamina, h.acceleration, h.running_style,
                h.career_starts, h.career_wins, h.prize_money,
                o.name as owner_name, o.prefix,
                b.name as breeder_name
            FROM horses h
            JOIN owners o ON h.owner_id = o.owner_id
            JOIN breeders b ON h.breeder_id = b.breeder_id
            WHERE h.is_active = 1
        """
        params = []
        if age_filter is not None:
            query += " AND h.age = ?"
            params.append(age_filter)
        if sex_filter is not None:
            query += " AND h.sex = ?"
            params.append(sex_filter)

        with self.db.session() as conn:
            # 総件数のカウント
            count_query = f"SELECT COUNT(*) FROM ({query})"
            total_count = conn.execute(count_query, params).fetchone()[0]

            query += " ORDER BY h.horse_id ASC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()

            title_filter = ""
            if age_filter:
                title_filter += f" [{age_filter}歳馬]"
            if sex_filter:
                title_filter += f" [{sex_filter}]"

            print(f"\n==================== 現役競走馬リスト{title_filter} (全 {total_count} 頭中 {offset+1}〜{min(offset+limit, total_count)} 頭) ====================")
            print(f"{'ID':<5} | {'馬名':<18} | {'性':<4} | {'齢':<2} | {'MSTN':<4} | {'脚質':<6} | {'速度':<4} | {'持久':<4} | {'瞬発':<4} | {'馬主':<12} | {'生産牧場':<12} | {'戦績':<6}")
            print("-" * 102)

            style_map = {"escape": "逃げ", "leading": "先行", "between": "差し", "closing": "追込"}
            sex_map = {"colt": "牡", "filly": "牝", "horse": "牡", "mare": "牝", "gelding": "騸"}

            for r in rows:
                sex_jp = sex_map.get(r["sex"], r["sex"])
                style_jp = style_map.get(r["running_style"], r["running_style"])
                record_str = f"{r['career_starts']}戦{r['career_wins']}勝"
                print(
                    f"{r['horse_id']:<5} | {r['name']:<18} | {sex_jp:<4} | {r['age']:<2} | {r['mstn_type']:<4} | "
                    f"{style_jp:<6} | {r['speed']:>4.1f} | {r['stamina']:>4.1f} | {r['acceleration']:>4.1f} | "
                    f"{r['owner_name']:<12} | {r['breeder_name']:<12} | {record_str:<6}"
                )
            print("-" * 102)
            return total_count

    def list_sires(self) -> int:
        """種牡馬リストを表示（全頭）"""
        with self.db.session() as conn:
            rows = conn.execute(
                """
                SELECT 
                    s.sire_id, h.horse_id, h.name, h.age, s.sire_line,
                    s.stud_fee, s.max_coverings, s.annual_coverings,
                    h.mstn_type, h.speed, h.stamina, h.acceleration,
                    b.name as breeder_name
                FROM sires s
                JOIN horses h ON s.horse_id = h.horse_id
                JOIN breeders b ON s.breeder_id = b.breeder_id
                WHERE s.is_active = 1
                ORDER BY s.sire_id ASC
                """
            ).fetchall()

            print(f"\n==================================== 種牡馬リスト (全 {len(rows)} 頭) ====================================")
            print(f"{'ID':<4} | {'馬名':<18} | {'年齢':<3} | {'繋養牧場':<14} | {'系統 (サイアーライン)':<20} | {'種付料':>9} | {'種付枠':<5} | {'MSTN':<4} | {'速度':<4} | {'持久':<4} | {'瞬発':<4}")
            print("-" * 115)

            for r in rows:
                fee_str = f"{r['stud_fee']:,}円"
                cov_str = f"{r['annual_coverings']}/{r['max_coverings']}頭"
                print(
                    f"{r['sire_id']:<4} | {r['name']:<18} | {r['age']:<3}歳 | {r['breeder_name']:<14} | {r['sire_line']:<20} | "
                    f"{fee_str:>10} | {cov_str:<7} | {r['mstn_type']:<4} | {r['speed']:>4.1f} | {r['stamina']:>4.1f} | {r['acceleration']:>4.1f}"
                )
            print("-" * 115)
            return len(rows)

    def list_dams(self, breeder_id: Optional[int] = None, limit: int = 25, offset: int = 0) -> int:
        """
        繁殖牝馬リストを表示
        Returns:
            総頭数
        """
        query = """
            SELECT 
                d.dam_id, h.horse_id, h.name, h.age,
                h.mstn_type, h.speed, h.stamina, h.acceleration, h.maternal_vitality,
                b.name as breeder_name, b.breeder_id
            FROM dams d
            JOIN horses h ON d.horse_id = h.horse_id
            JOIN breeders b ON d.breeder_id = b.breeder_id
            WHERE d.is_active = 1
        """
        params = []
        if breeder_id is not None:
            query += " AND d.breeder_id = ?"
            params.append(breeder_id)

        with self.db.session() as conn:
            count_query = f"SELECT COUNT(*) FROM ({query})"
            total_count = conn.execute(count_query, params).fetchone()[0]

            query += " ORDER BY d.dam_id ASC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()

            title_extra = f" (牧場ID: {breeder_id})" if breeder_id else ""
            print(f"\n==================== 繁殖牝馬リスト{title_extra} (全 {total_count} 頭中 {offset+1}〜{min(offset+limit, total_count)} 頭) ====================")
            print(f"{'ID':<5} | {'馬名':<18} | {'年齢':<3} | {'繋養牧場':<14} | {'MSTN':<4} | {'速度':<4} | {'持久':<4} | {'瞬発':<4} | {'底力':<4}")
            print("-" * 79)

            for r in rows:
                print(
                    f"{r['dam_id']:<5} | {r['name']:<18} | {r['age']:<3}歳 | {r['breeder_name']:<14} | "
                    f"{r['mstn_type']:<4} | {r['speed']:>4.1f} | {r['stamina']:>4.1f} | {r['acceleration']:>4.1f} | {r['maternal_vitality']:>4.1f}"
                )
            print("-" * 79)
            return total_count

    def list_breeders(self, region_filter: Optional[str] = None) -> int:
        """生産牧場リスト（全50場）を表示"""
        query = """
            SELECT 
                b.breeder_id, b.name, b.region, b.reputation, b.funds, b.horse_capacity,
                (SELECT COUNT(*) FROM sires s WHERE s.breeder_id = b.breeder_id AND s.is_active = 1) as sire_count,
                (SELECT COUNT(*) FROM dams d WHERE d.breeder_id = b.breeder_id AND d.is_active = 1) as dam_count
            FROM breeders b
        """
        params = []
        if region_filter:
            query += " WHERE b.region = ?"
            params.append(region_filter)

        query += " ORDER BY b.breeder_id ASC"

        with self.db.session() as conn:
            rows = conn.execute(query, params).fetchall()

            title_filter = f" [{region_filter}地方]" if region_filter else ""
            print(f"\n==================== 生産牧場リスト{title_filter} (全 {len(rows)} 場) ====================")
            print(f"{'ID':<4} | {'牧場名':<16} | {'地方':<6} | {'評判':<5} | {'種牡馬':<4} | {'牝馬':<4} | {'繋養総数/枠':<14} | {'資金':>12}")
            print("-" * 86)

            for r in rows:
                total_horses = r['sire_count'] + r['dam_count']
                capacity_str = f"{total_horses} / {r['horse_capacity']}頭"
                funds_str = f"{r['funds']:,}円"
                print(
                    f"{r['breeder_id']:<4} | {r['name']:<16} | {r['region']:<6} | {r['reputation']:>5.1f} | "
                    f"{r['sire_count']:>3}頭 | {r['dam_count']:>3}頭 | {capacity_str:<14} | {funds_str:>12}"
                )
            print("-" * 86)
            return len(rows)

    def list_trainers(self, location_filter: Optional[str] = None) -> int:
        """厩舎リスト（美浦25・栗東25）を表示"""
        query = """
            SELECT 
                t.trainer_id, t.name, t.location, t.age, t.trainer_years, t.specialty, t.horse_capacity,
                t.reputation, t.career_wins, t.career_earnings, t.g1_wins, t.former_jockey_id,
                COUNT(h.horse_id) as actual_horses
            FROM trainers t
            LEFT JOIN horses h ON t.trainer_id = h.trainer_id AND h.is_active = 1
        """
        params = []
        if location_filter:
            query += " WHERE t.location = ?"
            params.append(location_filter)

        query += " GROUP BY t.trainer_id ORDER BY t.trainer_id ASC"

        with self.db.session() as conn:
            rows = conn.execute(query, params).fetchall()

            spec_labels = {
                "turf": "芝得意", "dirt": "ダート得意", "distance_long": "長距離得意",
                "distance_sprint": "短距離得意", "early_growth": "仕上り早", "late_growth": "晩成育成",
                "durability_care": "馬体ケア", "general": "万能"
            }

            title_filter = f" [{location_filter}]" if location_filter else ""
            print(f"\n==================== 厩舎リスト{title_filter} (全 {len(rows)} 厩舎) ====================")
            print(f"{'ID':<4} | {'厩舎名':<10} | {'所属':<4} | {'年齢':<4} | {'歴':<3} | {'特徴・得意分野':<10} | {'管理頭数/枠':<13} | {'通算勝':<5} | {'G1':<3} | {'通算賞金':>12}")
            print("-" * 83)

            for r in rows:
                cap_str = f"{r['actual_horses']} / {r['horse_capacity']}頭"
                earn_str = f"{r['career_earnings']:,}円"
                spec_str = spec_labels.get(r['specialty'], r['specialty'])
                age_val = r['age'] if 'age' in r.keys() and r['age'] is not None else 50
                years_val = r['trainer_years'] if 'trainer_years' in r.keys() and r['trainer_years'] is not None else 1
                print(
                    f"{r['trainer_id']:<4} | {r['name']:<10} | {r['location']:<4} | {age_val:<3}歳 | {years_val:<2}年 | {spec_str:<10} | "
                    f"{cap_str:<13} | {r['career_wins']:>4}勝 | {r['g1_wins']:>2}勝 | {earn_str:>12}"
                )
            print("-" * 83)
            return len(rows)

    def list_jockeys(self, location_filter: Optional[str] = None) -> int:
        """騎手リスト（美浦30・栗東30、計60名、女性騎手表示対応）を表示"""
        query = """
            SELECT 
                j.jockey_id, j.name, j.gender, j.location, j.age, j.career_years,
                j.skill, j.drive, j.start_dash, j.temperament_handling,
                j.career_wins, j.career_rides, j.career_earnings, j.g1_wins
            FROM jockeys j
            WHERE j.is_active = 1
        """
        params = []
        if location_filter:
            query += " AND j.location = ?"
            params.append(location_filter)

        query += " ORDER BY j.jockey_id ASC"

        with self.db.session() as conn:
            rows = conn.execute(query, params).fetchall()

            title_filter = f" [{location_filter}]" if location_filter else ""
            print(f"\n==================== 騎手リスト{title_filter} (全 {len(rows)} 名) ====================")
            print(f"{'ID':<4} | {'氏名':<13} | {'性':<2} | {'所属':<4} | {'年齢':<3} | {'歴':<3} | {'操縦':<4} | {'推進':<4} | {'出脚':<4} | {'折り':<4} | {'通算勝/騎乗':<11} | {'通算賞金':>12}")
            print("-" * 92)

            for r in rows:
                earn_str = f"{r['career_earnings']:,}円"
                rec_str = f"{r['career_wins']}/{r['career_rides']}回"
                gender_label = "♀" if ("gender" in r.keys() and r["gender"] == "female") else "♂"
                print(
                    f"{r['jockey_id']:<4} | {r['name']:<13} | {gender_label:<2} | {r['location']:<4} | {r['age']:<3}歳 | {r['career_years']:<2}年 | "
                    f"{r['skill']:>4.1f} | {r['drive']:>4.1f} | {r['start_dash']:>4.1f} | {r['temperament_handling']:>4.1f} | "
                    f"{rec_str:<11} | {earn_str:>12}"
                )
            print("-" * 92)
            return len(rows)

    def show_pedigree(self, horse_id: int) -> bool:
        """指定された競走馬の5代血統表（Pedigree Tree）をCLIおよびHTMLビューアとして表示"""
        with self.db.session() as conn:
            query = """
            SELECT 
                h.horse_id, h.name, h.age, h.sex,
                sire.name as s_name, dam.name as d_name,
                ss.name as ss_name, sd.name as sd_name,
                ds.name as ds_name, dd.name as dd_name
            FROM horses h
            LEFT JOIN horses sire ON h.sire_id = sire.horse_id
            LEFT JOIN horses dam ON h.dam_id = dam.horse_id
            LEFT JOIN horses ss ON sire.sire_id = ss.horse_id
            LEFT JOIN horses sd ON sire.dam_id = sd.horse_id
            LEFT JOIN horses ds ON dam.sire_id = ds.horse_id
            LEFT JOIN horses dd ON dam.dam_id = dd.horse_id
            WHERE h.horse_id = ?
            """
            row = conn.execute(query, (horse_id,)).fetchone()
            if not row:
                print(f"[エラー] 馬ID {horse_id} は存在しません。")
                return False

            unk = "不明"
            s_name = row["s_name"] or unk
            d_name = row["d_name"] or unk
            ss_name = row["ss_name"] or unk
            sd_name = row["sd_name"] or unk
            ds_name = row["ds_name"] or unk
            dd_name = row["dd_name"] or unk

            print(f"\n==================== 【血統概要】 {row['name']} (ID:{row['horse_id']}) ====================")
            print(f" {row['name']}")
            print(f"  ├─ 父: {s_name}")
            print(f"  │   ├─ 父父: {ss_name}")
            print(f"  │   └─ 父母: {sd_name}")
            print(f"  └─ 母: {d_name}")
            print(f"      ├─ 母父: {ds_name}")
            print(f"      └─ 母母: {dd_name}")
            print("----------------------------------------------------------------------")

            # インタラクティブな5代血統表HTMLの自動生成
            try:
                builder = PedigreeBuilder(self.db)
                os.makedirs("data", exist_ok=True)
                html_path = "data/pedigree.html"
                builder.build_html(horse_id, html_path)
                abs_path = os.path.abspath(html_path)
                print(f" [OK] 詳細な5代血統表HTMLを生成しました: {abs_path}")
                print("      ブラウザで開くと、表中の馬をクリックして戦績・血統を閲覧できます。")
                try:
                    webbrowser.open(f"file://{abs_path}")
                except Exception:
                    pass
            except Exception as e:
                print(f" [注意] HTML血統表生成中に軽微な警告: {e}")

            print("======================================================================\n")
            return True

    def show_sire_line_tree(self) -> bool:
        """始祖種牡馬から連なる系統図（Sire Line Tree）を表示"""
        with self.db.session() as conn:
            # 親がNULL（始祖馬）の種牡馬一覧を取得
            roots = conn.execute(
                """
                SELECT s.sire_id, h.horse_id, h.name, s.sire_line, b.name as breeder_name
                FROM sires s
                JOIN horses h ON s.horse_id = h.horse_id
                JOIN breeders b ON s.breeder_id = b.breeder_id
                WHERE h.sire_id IS NULL
                ORDER BY s.sire_id ASC
                """
            ).fetchall()

            print(f"\n========================= 【サイアーライン系統図 (始祖 {len(roots)} 系統)】 =========================")
            for r in roots:
                sons = conn.execute(
                    """
                    SELECT h.horse_id, h.name, s.sire_id
                    FROM sires s
                    JOIN horses h ON s.horse_id = h.horse_id
                    WHERE h.sire_id = ?
                    ORDER BY s.sire_id ASC
                    """,
                    (r["horse_id"],),
                ).fetchall()

                if sons:
                    son_names = ", ".join([s["name"] for s in sons])
                    son_str = f" ── 後継: [{son_names}]"
                else:
                    son_str = " ── (直系後継種牡馬: なし/現役中)"

                print(f" ■ {r['sire_line']:<20} [始祖: {r['name']} / 繋養: {r['breeder_name']}]{son_str}")
            print("========================================================================================\n")
            return True

    def show_rankings(self, category: str = "horse", period: str = "career") -> bool:
        """
        各種ランキング（生涯・当年成績）を表示
        category: 'horse', 'sire', 'dam', 'breeder', 'trainer', 'jockey'
        period: 'career' (通算), 'annual' (当年)
        """
        period_title = "通算成績" if period == "career" else "当年成績"
        with self.db.session() as conn:
            if category == "horse":
                # 競走馬は現役（is_active = 1）かつ 8歳以下に限定
                order_col = "h.prize_money" if period == "career" else "h.condition_prize_money"
                rows = conn.execute(
                    f"""
                    SELECT h.horse_id, h.name, h.age, h.sex,
                           h.career_starts, h.career_wins,
                           h.g1_wins, h.g2_wins, h.g3_wins, h.major_wins,
                           h.prize_money, o.name as owner_name, t.name as trainer_name
                    FROM horses h
                    JOIN owners o ON h.owner_id = o.owner_id
                    LEFT JOIN trainers t ON h.trainer_id = t.trainer_id
                    WHERE h.is_active = 1 AND h.age <= 8
                    ORDER BY {order_col} DESC, h.career_wins DESC LIMIT 20
                    """
                ).fetchall()
                print(f"\n==================== 現役競走馬ランキング【{period_title} (2〜8歳)】TOP 20 ====================")
                print(f"{'順位':<4} | {'馬名':<18} | {'年齢':<3} | {'性':<3} | {'戦績':<10} | {'重賞勝(G1/G2/G3)':<16} | {'総賞金':>14} | {'主な勝ち鞍':<18}")
                print("-" * 105)
                for idx, r in enumerate(rows, 1):
                    record_str = f"{r['career_starts']}戦{r['career_wins']}勝"
                    graded_str = f"{r['g1_wins']}/{r['g2_wins']}/{r['g3_wins']}"
                    major_str = r['major_wins'] if r['major_wins'] else "―"
                    if len(major_str) > 16:
                        major_str = major_str[:15] + "…"
                    print(
                        f"{idx:<4} | {r['name']:<18} | {r['age']:<3}歳 | {r['sex']:<3} | "
                        f"{record_str:<10} | {graded_str:^16} | {r['prize_money']:,}円 | {major_str:<18}"
                    )
                print("-" * 105)

            elif category == "trainer":
                is_career = (period == "career")
                starts_col = "t.career_starts" if is_career else "t.current_year_starts"
                win_col = "t.career_wins" if is_career else "t.current_year_wins"
                g1_col = "t.g1_wins" if is_career else "t.current_year_g1"
                g2_col = "t.g2_wins" if is_career else "t.current_year_g2"
                g3_col = "t.g3_wins" if is_career else "t.current_year_g3"
                earn_col = "t.career_earnings" if is_career else "t.current_year_earnings"

                # 代表馬サブクエリ（通算は歴代最高賞金馬、当年は当年現役最高賞金馬）
                best_subquery = (
                    "(SELECT h.name FROM horses h WHERE h.trainer_id = t.trainer_id ORDER BY h.prize_money DESC LIMIT 1)"
                    if is_career else
                    "(SELECT h.name FROM horses h WHERE h.trainer_id = t.trainer_id AND h.is_active = 1 ORDER BY h.condition_prize_money DESC, h.prize_money DESC LIMIT 1)"
                )

                rows = conn.execute(
                    f"""
                    SELECT t.trainer_id, t.name, t.location, t.specialty,
                           {starts_col} as starts, {win_col} as wins,
                           {g1_col} as g1, {g2_col} as g2, {g3_col} as g3,
                           {earn_col} as earnings,
                           {best_subquery} as best_horse
                    FROM trainers t
                    ORDER BY wins DESC, earnings DESC LIMIT 20
                    """
                ).fetchall()

                print(f"\n==================== 厩舎ランキング【{period_title}】TOP 20 ====================")
                print(f"{'順位':<4} | {'厩舎名':<12} | {'所属':<4} | {'特徴':<10} | {'戦績':<10} | {'重賞(G1/G2/G3)':<14} | {'獲得賞金':>14} | {'代表管理馬':<18}")
                print("-" * 98)
                for idx, r in enumerate(rows, 1):
                    rec_str = f"{r['starts']}戦{r['wins']}勝"
                    graded_str = f"{r['g1']}/{r['g2']}/{r['g3']}"
                    best_h = r['best_horse'] or "―"
                    print(
                        f"{idx:<4} | {r['name']:<12} | {r['location']:<4} | {r['specialty']:<10} | "
                        f"{rec_str:<10} | {graded_str:^14} | {r['earnings']:,}円 | {best_h:<18}"
                    )
                print("-" * 98)

            elif category == "jockey":
                is_career = (period == "career")
                starts_col = "j.career_starts" if is_career else "j.current_year_starts"
                win_col = "j.career_wins" if is_career else "j.current_year_wins"
                g1_col = "j.g1_wins" if is_career else "j.current_year_g1"
                g2_col = "j.g2_wins" if is_career else "j.current_year_g2"
                g3_col = "j.g3_wins" if is_career else "j.current_year_g3"
                earn_col = "j.career_earnings" if is_career else "j.current_year_earnings"

                best_subquery = (
                    "(SELECT h.name FROM horses h WHERE h.jockey_id = j.jockey_id ORDER BY h.prize_money DESC LIMIT 1)"
                    if is_career else
                    "(SELECT h.name FROM horses h WHERE h.jockey_id = j.jockey_id AND h.is_active = 1 ORDER BY h.condition_prize_money DESC, h.prize_money DESC LIMIT 1)"
                )

                rows = conn.execute(
                    f"""
                    SELECT j.jockey_id, j.name, j.gender, j.location, j.career_years,
                           {starts_col} as starts, {win_col} as wins,
                           {g1_col} as g1, {g2_col} as g2, {g3_col} as g3,
                           {earn_col} as earnings,
                           {best_subquery} as best_horse
                    FROM jockeys j
                    WHERE j.is_active = 1
                    ORDER BY wins DESC, earnings DESC LIMIT 20
                    """
                ).fetchall()

                print(f"\n==================== 騎手ランキング【{period_title}】TOP 20 ====================")
                print(f"{'順位':<4} | {'氏名':<13} | {'性':<2} | {'所属':<4} | {'騎手歴':<4} | {'戦績':<10} | {'重賞(G1/G2/G3)':<14} | {'獲得賞金':>14} | {'代表お手馬':<18}")
                print("-" * 102)
                for idx, r in enumerate(rows, 1):
                    rec_str = f"{r['starts']}戦{r['wins']}勝"
                    graded_str = f"{r['g1']}/{r['g2']}/{r['g3']}"
                    gender_label = "♀" if ("gender" in r.keys() and r["gender"] == "female") else "♂"
                    best_h = r['best_horse'] or "―"
                    print(
                        f"{idx:<4} | {r['name']:<13} | {gender_label:<2} | {r['location']:<4} | {r['career_years']:>3}年目 | "
                        f"{rec_str:<10} | {graded_str:^14} | {r['earnings']:,}円 | {best_h:<18}"
                    )
                print("-" * 102)

            elif category == "breeder":
                is_career = (period == "career")
                starts_col = "b.career_starts" if is_career else "b.current_year_starts"
                win_col = "b.career_wins" if is_career else "b.current_year_wins"
                g1_col = "b.g1_wins" if is_career else "b.current_year_g1"
                g2_col = "b.g2_wins" if is_career else "b.current_year_g2"
                g3_col = "b.g3_wins" if is_career else "b.current_year_g3"
                earn_col = "b.career_earnings" if is_career else "b.current_year_earnings"

                best_subquery = (
                    "(SELECT h.name FROM horses h WHERE h.breeder_id = b.breeder_id ORDER BY h.prize_money DESC LIMIT 1)"
                    if is_career else
                    "(SELECT h.name FROM horses h WHERE h.breeder_id = b.breeder_id AND h.is_active = 1 ORDER BY h.condition_prize_money DESC, h.prize_money DESC LIMIT 1)"
                )

                rows = conn.execute(
                    f"""
                    SELECT b.breeder_id, b.name, b.region,
                           {starts_col} as starts, {win_col} as wins,
                           {g1_col} as g1, {g2_col} as g2, {g3_col} as g3,
                           {earn_col} as earnings,
                           {best_subquery} as best_horse
                    FROM breeders b
                    ORDER BY wins DESC, earnings DESC LIMIT 20
                    """
                ).fetchall()

                print(f"\n==================== 生産牧場ランキング【{period_title}】TOP 20 ====================")
                print(f"{'順位':<4} | {'牧場名':<16} | {'地方':<6} | {'戦績':<10} | {'重賞(G1/G2/G3)':<14} | {'総生産賞金':>14} | {'代表産駒':<18}")
                print("-" * 98)
                for idx, r in enumerate(rows, 1):
                    rec_str = f"{r['starts']}戦{r['wins']}勝"
                    graded_str = f"{r['g1']}/{r['g2']}/{r['g3']}"
                    best_h = r['best_horse'] or "―"
                    print(
                        f"{idx:<4} | {r['name']:<16} | {r['region']:<6} | "
                        f"{rec_str:<10} | {graded_str:^14} | {r['earnings']:,}円 | {best_h:<18}"
                    )
                print("-" * 98)

            return True

    def show_horse_detail(self, horse_id: int) -> bool:
        """指定されたIDの馬の詳細情報（能力値・血統・戦績・厩舎・主戦騎手）を表示"""
        with self.db.session() as conn:
            row = conn.execute(
                """
                SELECT 
                    h.*, 
                    o.name as owner_name, o.prefix,
                    b.name as breeder_name, b.region as breeder_region,
                    t.name as trainer_name, t.location as trainer_loc, t.specialty as trainer_spec,
                    j.name as jockey_name, j.location as jockey_loc,
                    sire.name as sire_name,
                    dam.name as dam_name
                FROM horses h
                JOIN owners o ON h.owner_id = o.owner_id
                JOIN breeders b ON h.breeder_id = b.breeder_id
                LEFT JOIN trainers t ON h.trainer_id = t.trainer_id
                LEFT JOIN jockeys j ON h.jockey_id = j.jockey_id
                LEFT JOIN horses sire ON h.sire_id = sire.horse_id
                LEFT JOIN horses dam ON h.dam_id = dam.horse_id
                WHERE h.horse_id = ?
                """,
                (horse_id,),
            ).fetchone()

            if not row:
                print(f"[エラー] 馬ID {horse_id} は存在しません。")
                return False

            style_map = {"escape": "逃げ", "leading": "先行", "between": "差し", "closing": "追込"}
            growth_map = {"early": "早熟", "normal": "普通", "late": "晩成"}
            sex_map = {"colt": "牡馬", "filly": "牝馬", "horse": "牡馬", "mare": "牝馬", "gelding": "騸馬"}

            sire_display = row["sire_name"] if row["sire_name"] else "不明 (スタッドブック開始前の始祖馬)"
            dam_display = row["dam_name"] if row["dam_name"] else "不明 (スタッドブック開始前の始祖馬)"

            if row["is_sire"]:
                status_str = "種牡馬"
            elif row["is_dam"]:
                status_str = "繁殖牝馬"
            elif (row["age"] or 0) <= 1:
                status_str = "入厩前"
            elif row["is_active"]:
                if (row["career_starts"] or 0) == 0:
                    status_str = "未出走"
                else:
                    status_str = "現役競走馬"
            else:
                status_str = "引退"

            trainer_display = f"{row['trainer_name']} [{row['trainer_loc']}]" if row["trainer_name"] else "未入厩"
            jockey_display = f"{row['jockey_name']} [{row['jockey_loc']}]" if row["jockey_name"] else "未定"

            print(f"\n========================= 【馬情報詳細】 {row['name']} =========================")
            print(f" 馬名:        {row['name']} (ID: {row['horse_id']})")
            print(f" 性別 / 年齢: {sex_map.get(row['sex'], row['sex'])} / {row['age']}歳 (生年: {row['birth_year']}年目)")
            print(f" 馬主 / 牧場: {row['owner_name']} (冠名: {row['prefix']}) / {row['breeder_name']} [{row['breeder_region']}]")
            print(f" 厩舎 / 主戦: {trainer_display} / 主戦騎手: {jockey_display}")
            print(f" 現在の状態:  {status_str}")
            print("----------------------------------------------------------------------")
            print(" 【血統情報 (スタッドブック)】")
            print(f"  父馬 (Sire): {sire_display}")
            print(f"  母馬 (Dam):  {dam_display}")
            print("----------------------------------------------------------------------")
            print(" 【遺伝特性 & 能力値 (0.0〜100.0 / 平均 50.0)】")
            print(f"  ミオスタチン (MSTN): {row['mstn_type']} ({'短距離型' if row['mstn_type']=='C/C' else ('万能型' if row['mstn_type']=='C/T' else '長距離型')})")
            print(f"  最高速度:     {row['speed']:>5.1f}   持久力:     {row['stamina']:>5.1f}")
            print(f"  瞬発力:       {row['acceleration']:>5.1f}   気性:       {row['temperament']:>5.1f}")
            print(f"  耐久力:       {row['durability']:>5.1f}   母系底力:   {row['maternal_vitality']:>5.1f}")
            print("----------------------------------------------------------------------")
            print(" 【戦術・成長曲線】")
            print(f"  脚質:         {style_map.get(row['running_style'], row['running_style'])}")
            print(f"  成長タイプ:   {growth_map.get(row['growth_type'], row['growth_type'])} (ピーク年齢: {row['peak_age']}歳)")
            print(f"  現在の能力率: {int(row['current_ability_rate'] * 100)}%")
            print("----------------------------------------------------------------------")
            print(" 【生涯戦績】")
            print(f"  通算出走数:   {row['career_starts']} 戦 {row['career_wins']} 勝 (G1勝利数: {row['g1_wins']} 勝)")
            print(f"  総獲得賞金:   {row['prize_money']:,} 円 (収得賞金: {row['condition_prize_money']:,} 円)")
            print("======================================================================\n")
            return True
