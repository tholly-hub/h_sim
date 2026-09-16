"""
競馬シミュレーションエンジン メインエントリポイント
Phase 1: DB環境確認、スキーマ作成、初期データ生成、リスト確認
Phase 2: 交配・遺伝計算、牧場・馬主動的分化、世代交代・加齢・引退
Phase 3: レース番組表、走破タイム計算・レースシミュレーション、週/月/年進行、5大リーディング集計
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional

# カレントディレクトリを sys.path に追加してモジュール参照を解決
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.core.breeding import BreedingEngine
from src.core.config import get_config
from src.core.lifecycle import LifecycleEngine
from src.db.database import get_db
from src.generators.initializer import DatabaseInitializer
from src.race.calendar import CalendarController
from src.race.program import RaceProgramBuilder
from src.race.rankings import RankingManager
from src.views.viewer import HorseViewer


def show_summary() -> None:
    """現在のデータベース内の集計情報を表示"""
    db = get_db()
    try:
        with db.session() as conn:
            breeders_count = conn.execute("SELECT COUNT(*) FROM breeders").fetchone()[0]
            owners_count = conn.execute("SELECT COUNT(*) FROM owners").fetchone()[0]
            trainers_count = conn.execute("SELECT COUNT(*) FROM trainers").fetchone()[0]
            jockeys_count = conn.execute("SELECT COUNT(*) FROM jockeys WHERE is_active = 1").fetchone()[0]
            horses_count = conn.execute("SELECT COUNT(*) FROM horses").fetchone()[0]
            sires_count = conn.execute("SELECT COUNT(*) FROM sires").fetchone()[0]
            dams_count = conn.execute("SELECT COUNT(*) FROM dams").fetchone()[0]
            active_count = conn.execute("SELECT COUNT(*) FROM horses WHERE is_active = 1").fetchone()[0]
            young_count = conn.execute("SELECT COUNT(*) FROM horses WHERE age < 2 AND is_active = 0 AND is_sire = 0 AND is_dam = 0").fetchone()[0]
            retired_count = conn.execute("SELECT COUNT(*) FROM horses WHERE age >= 2 AND is_active = 0 AND is_sire = 0 AND is_dam = 0").fetchone()[0]
            races_count = conn.execute("SELECT COUNT(*) FROM races").fetchone()[0]
            results_count = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]

            # 厩舎内訳 (美浦/栗東)
            trainers_miho = conn.execute("SELECT COUNT(*) FROM trainers WHERE location = '美浦'").fetchone()[0]
            trainers_ritto = conn.execute("SELECT COUNT(*) FROM trainers WHERE location = '栗東'").fetchone()[0]

            # 騎手内訳 (美浦/栗東/女性騎手/所属/フリー)
            jockeys_miho = conn.execute("SELECT COUNT(*) FROM jockeys WHERE location = '美浦' AND is_active = 1").fetchone()[0]
            jockeys_ritto = conn.execute("SELECT COUNT(*) FROM jockeys WHERE location = '栗東' AND is_active = 1").fetchone()[0]
            female_jockeys = conn.execute("SELECT COUNT(*) FROM jockeys WHERE gender = 'female' AND is_active = 1").fetchone()[0]
            free_jockeys = conn.execute("SELECT COUNT(*) FROM jockeys WHERE is_free = 1 AND is_active = 1").fetchone()[0]
            stable_jockeys = conn.execute("SELECT COUNT(*) FROM jockeys WHERE is_free = 0 AND is_active = 1").fetchone()[0]
            assistants_count = conn.execute("SELECT COUNT(*) FROM assistant_trainers WHERE is_active = 1").fetchone()[0]

            # 厩舎平均スキル
            avg_trainer_skill = conn.execute("SELECT AVG(skill_level) FROM trainers").fetchone()[0] or 50.0

            # 能力平均値
            stats = conn.execute(
                """
                SELECT 
                    AVG(speed) as avg_spd, 
                    AVG(stamina) as avg_sta, 
                    AVG(acceleration) as avg_acc,
                    AVG(temperament) as avg_tem,
                    AVG(durability) as avg_dur
                FROM horses
                """
            ).fetchone()

            print("\n================ 当前データベース集計 ================")
            print(f"DBパス: {db.db_path}")
            print(f"生産牧場数: {breeders_count} 場 (全9地方)")
            print(f"馬主数:     {owners_count} 人 (固有冠名)")
            print(f"厩舎数:     {trainers_count} 厩舎 (美浦 {trainers_miho} / 栗東 {trainers_ritto} / 平均スキル {avg_trainer_skill:.1f})")
            print(f"現役騎手数: {jockeys_count} 名 (美浦 {jockeys_miho} / 栗東 {jockeys_ritto} / 所属 {stable_jockeys}名 / フリー {free_jockeys}名 / 女性 {female_jockeys}名)")
            print(f"調教助手数: {assistants_count} 名 (引退騎手転身・〜50歳定年)")
            print(f"登録番組数: {races_count} レース (年間48週体系)")
            print(f"消化レース: {results_count} 件の出走記録")
            print(f"総競走馬数: {horses_count} 頭")
            print(f"  - 現役競走馬: {active_count} 頭 (2〜8歳、厩舎均等入厩 / 主戦騎手配分 / 8歳末引退)")
            print(f"  - 種牡馬:     {sires_count} 頭 (各種牡馬 年間上限30頭)")
            print(f"  - 繁殖牝馬:   {dams_count} 頭 (各牧場 最低1頭保証)")
            print(f"  - 当歳・1歳馬: {young_count} 頭")
            print(f"  - 引退競走馬（功労馬等）: {retired_count} 頭")
            if stats and stats["avg_spd"] is not None:
                print("【全体平均能力値 (理論中央値 50.0)】")
                print(f"  最高速度: {stats['avg_spd']:.1f} | 持久力: {stats['avg_sta']:.1f} | "
                      f"瞬発力: {stats['avg_acc']:.1f} | 気性: {stats['avg_tem']:.1f} | 耐久力: {stats['avg_dur']:.1f}")
            print("======================================================\n")
    except Exception as e:
        print(f"DBの読み込みエラー（未初期化の可能性があります）: {e}")


def browse_active_horses() -> None:
    """現役競走馬のページング閲覧"""
    viewer = HorseViewer()
    offset = 0
    limit = 20
    while True:
        total = viewer.list_active_horses(limit=limit, offset=offset)
        print(f"[N] 次の{limit}頭  [P] 前の{limit}頭  [馬ID] 詳細確認  [Q] 戻る")
        cmd = input("選択してください: ").strip().lower()
        if cmd == "n":
            if offset + limit < total:
                offset += limit
            else:
                print(">> これ以上のデータはありません。")
        elif cmd == "p":
            if offset >= limit:
                offset -= limit
            else:
                print(">> 最初のページです。")
        elif cmd.isdigit():
            viewer.show_horse_detail(int(cmd))
        elif cmd == "q":
            break


def browse_dams() -> None:
    """繁殖牝馬のページング閲覧"""
    viewer = HorseViewer()
    offset = 0
    limit = 20
    while True:
        total = viewer.list_dams(limit=limit, offset=offset)
        print(f"[N] 次の{limit}頭  [P] 前の{limit}頭  [馬ID] 詳細確認  [Q] 戻る")
        cmd = input("選択してください: ").strip().lower()
        if cmd == "n":
            if offset + limit < total:
                offset += limit
            else:
                print(">> これ以上のデータはありません。")
        elif cmd == "p":
            if offset >= limit:
                offset -= limit
            else:
                print(">> 最初のページです。")
        elif cmd.isdigit():
            viewer.show_horse_detail(int(cmd))
        elif cmd == "q":
            break


def show_program(week: Optional[int] = None) -> None:
    """レース番組表一覧を表示"""
    db = get_db()
    with db.session() as conn:
        if week is not None:
            query = "SELECT * FROM races WHERE week = ? ORDER BY race_id ASC"
            rows = conn.execute(query, (week,)).fetchall()
            title = f"【第{week}週 レース番組表】"
        else:
            query = "SELECT * FROM races ORDER BY week ASC, race_id ASC"
            rows = conn.execute(query).fetchall()
            title = "【年間レース番組表一覧】"

        print(f"\n==================== {title} ====================")
        if not rows:
            print("登録されているレースがありません。(--register-program で登録してください)")
            return

        print(f"{'週':<3} | {'場':<2} | {'グレード':<8} | {'レース名':<22} | {'コース':<6} | {'距離':<5} | {'条件':<8} | {'頭数':<3}")
        print("-" * 75)
        for r in rows:
            surf = "芝" if r["surface"] == "turf" else "ダ"
            print(f"{r['week']:>2}週 | {r['track_id']:<2} | {r['grade']:<8} | {r['name']:<22} | {surf:<6} | {r['distance']:>4}m | {r['age_restriction']:<8} | {r['full_gate']:>2}頭")
        print("=================================================================\n")


def show_race_results(race_id: Optional[int] = None, limit: int = 10) -> None:
    """レース結果を表示"""
    db = get_db()
    with db.session() as conn:
        if race_id is not None:
            cur_race = conn.execute("SELECT * FROM races WHERE race_id = ?", (race_id,))
            race = cur_race.fetchone()
            if not race:
                print(f"指定されたレースID {race_id} が見つかりません。")
                return

            print(f"\n==================== 【第{race['week']}週】{race['name']} ({race['grade']}) 結果 ====================")
            rows = conn.execute(
                """
                SELECT r.*, h.name as horse_name, j.name as jockey_name, t.name as trainer_name
                FROM results r
                JOIN horses h ON r.horse_id = h.horse_id
                LEFT JOIN jockeys j ON r.jockey_id = j.jockey_id
                LEFT JOIN trainers t ON r.trainer_id = t.trainer_id
                WHERE r.race_id = ?
                ORDER BY r.finish_position ASC
                """,
                (race_id,),
            ).fetchall()

            print(f"{'着順':<4} | {'馬名':<18} | {'タイム':<7} | {'着差':<5} | {'騎手':<10} | {'厩舎':<12} | {'獲得賞金':>14}")
            print("-" * 85)
            for r in rows:
                time_str = f"{int(r['finish_time'] // 60):02d}:{r['finish_time'] % 60:04.1f}"
                print(f"{r['finish_position']:>2}着 | {r['horse_name']:<18} | {time_str:<7} | {r['margin']:<5} | {r['jockey_name'] or '―':<10} | {r['trainer_name'] or '―':<12} | {r['prize_awarded']:,}円")
            print("===================================================================================\n")
        else:
            # 直近の重賞レース結果一覧
            rows = conn.execute(
                """
                SELECT rc.race_id, rc.year, rc.week, rc.name as race_name, rc.grade,
                       h.name as winner_name, r.finish_time, j.name as jockey_name
                FROM results r
                JOIN races rc ON r.race_id = rc.race_id
                JOIN horses h ON r.horse_id = h.horse_id
                LEFT JOIN jockeys j ON r.jockey_id = j.jockey_id
                WHERE r.finish_position = 1 AND rc.grade IN ('G1', 'G2', 'G3')
                ORDER BY rc.year DESC, rc.week DESC, rc.race_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

            print(f"\n==================== 直近の主要重賞レース結果一覧 (最新 {limit} 件) ====================")
            if not rows:
                print("重賞レース結果はまだありません。(--simulate-week 等でレースを実行してください)")
                return

            print(f"{'レースID':<6} | {'年':<3} | {'週':<3} | {'グレード':<6} | {'レース名':<22} | {'勝ち馬':<18} | {'走破タイム':<8} | {'騎乗騎手':<10}")
            print("-" * 95)
            for r in rows:
                time_str = f"{int(r['finish_time'] // 60):02d}:{r['finish_time'] % 60:04.1f}"
                print(f"{r['race_id']:>6} | {r['year']:>2}年 | {r['week']:>2}週 | {r['grade']:<6} | {r['race_name']:<22} | {r['winner_name']:<18} | {time_str:<8} | {r['jockey_name'] or '―':<10}")
            print("======================================================================================\n")


def show_5_rankings(category: str = "jockey") -> None:
    """5大リーディング集計を表示"""
    db = get_db()
    mgr = RankingManager(db)

    if category == "jockey":
        rankings = mgr.get_jockey_rankings(limit=20)
        print(f"\n==================== 【騎手リーディング】TOP 20 ====================")
        print(f"{'順位':<4} | {'騎手名':<10} | {'所属':<4} | {'区分':<6} | {'戦績':<12} | {'勝率':<6} | {'重賞(G1/G2/G3)':<14} | {'獲得賞金':>14}")
        print("-" * 88)
        for idx, r in enumerate(rankings, 1):
            free_str = "フリー" if r["is_free"] == 1 else "所属"
            rec_str = f"{r['career_starts']}戦{r['career_wins']}勝"
            g_str = f"{r['g1_wins']}/{r['g2_wins']}/{r['g3_wins']}"
            print(f"{idx:>2}位 | {r['name']:<10} | {r['location']:<4} | {free_str:<6} | {rec_str:<12} | {r['win_rate']:<6.3f} | {g_str:^14} | {r['prize_money']:,}円")
        print("===================================================================\n")

    elif category == "trainer":
        rankings = mgr.get_trainer_rankings(limit=20)
        print(f"\n==================== 【調教師リーディング】TOP 20 ====================")
        print(f"{'順位':<4} | {'厩舎名':<12} | {'所属':<4} | {'スキル':<5} | {'戦績':<12} | {'勝率':<6} | {'重賞(G1/G2/G3)':<14} | {'獲得賞金':>14}")
        print("-" * 88)
        for idx, r in enumerate(rankings, 1):
            rec_str = f"{r['career_starts']}戦{r['career_wins']}勝"
            g_str = f"{r['g1_wins']}/{r['g2_wins']}/{r['g3_wins']}"
            print(f"{idx:>2}位 | {r['name']:<12} | {r['location']:<4} | {r['skill_level']:>4.1f} | {rec_str:<12} | {r['win_rate']:<6.3f} | {g_str:^14} | {r['prize_money']:,}円")
        print("=====================================================================\n")

    elif category == "owner":
        rankings = mgr.get_owner_rankings(limit=20)
        print(f"\n==================== 【馬主リーディング】TOP 20 ====================")
        print(f"{'順位':<4} | {'馬主名':<18} | {'冠名':<8} | {'勝数':<6} | {'G1勝':<4} | {'資金残高':>14} | {'獲得賞金総額':>16}")
        print("-" * 80)
        for idx, r in enumerate(rankings, 1):
            print(f"{idx:>2}位 | {r['name']:<18} | {r['prefix']:<8} | {r['career_wins']:>4}勝 | {r['g1_wins']:>2}勝 | {r['funds']:,}円 | {r['total_prize_money']:,}円")
        print("===================================================================\n")

    elif category == "breeder":
        rankings = mgr.get_breeder_rankings(limit=20)
        print(f"\n==================== 【生産牧場リーディング】TOP 20 ====================")
        print(f"{'順位':<4} | {'牧場名':<18} | {'所在地':<6} | {'勝数':<6} | {'G1勝':<4} | {'資金残高':>14} | {'生産馬獲得賞金':>16}")
        print("-" * 80)
        for idx, r in enumerate(rankings, 1):
            print(f"{idx:>2}位 | {r['name']:<18} | {r['region']:<6} | {r['career_wins']:>4}勝 | {r['g1_wins']:>2}勝 | {r['funds']:,}円 | {r['total_prize_money']:,}円")
        print("=====================================================================\n")

    elif category == "sire":
        rankings = mgr.get_sire_rankings(limit=20)
        print(f"\n==================== 【サイアーリーディング】TOP 20 ====================")
        print(f"{'順位':<4} | {'種牡馬名':<18} | {'系統':<18} | {'産駒数':<5} | {'産駒勝数':<7} | {'産駒G1':<5} | {'AEI':<5} | {'産駒獲得賞金':>16}")
        print("-" * 92)
        for idx, r in enumerate(rankings, 1):
            p_wins = r['progeny_wins'] or 0
            p_starts = r['progeny_starts'] or 0
            rec_str = f"{p_wins}勝/{p_starts}戦"
            g1_cnt = r['progeny_g1_wins'] or 0
            prize = r['progeny_prize_money'] or 0
            print(f"{idx:>2}位 | {r['sire_name']:<18} | {r['sire_line']:<18} | {r['progeny_count']:>4}頭 | {rec_str:<7} | {g1_cnt:>3}勝 | {r['aei']:>4.2f} | {prize:,}円")
        print("========================================================================\n")


def run_tests() -> None:
    """単体テストを実行"""
    tests = [
        "test_phase1.py",
        "test_phase2_breeding.py",
        "test_phase2_stable_jockey.py",
        "test_phase3_features.py",
        "test_horse_name_uniqueness.py",
        "test_trainer_jockey_system.py",
        "test_phase3_race_engine.py",
    ]
    for t in tests:
        test_path = Path(__file__).resolve().parent / "tests" / t
        if test_path.exists():
            print(f"\n>> 実行中: {t}")
            import os
            env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parent))
            subprocess.run([sys.executable, f"tests/{t}"], env=env)


def show_samples() -> None:
    """サンプルデータを表示"""
    sample_path = Path(__file__).resolve().parent / "show_samples.py"
    if sample_path.exists():
        subprocess.run([sys.executable, str(sample_path)])


def interactive_menu() -> None:
    """対話型コンソールメニュー"""
    config_mgr = get_config()
    viewer = HorseViewer()
    while True:
        print("\n============================================================")
        print("  競馬シミュレーションエンジン (Horse Racing Sim)")
        print("============================================================")
        print("  【基本情報確認】")
        print("  [1] データベース初期化＆初期データ・番組表生成 (--init)")
        print("  [2] データベース集計サマリ表示 (--summary)")
        print("  [3] 競走馬（現役馬）リスト確認 (--horses)")
        print("  [4] 種牡馬リスト確認 (--sires)")
        print("  [5] 繁殖牝馬リスト確認 (--dams)")
        print("  [6] 生産牧場リスト確認 (--breeders)")
        print("  [7] 厩舎リスト確認 (美浦/栗東) (--trainers)")
        print("  [8] 騎手リスト確認 (美浦/栗東) (--jockeys)")
        print("  [9] 個別馬詳細情報確認 (--horse-id <ID>)")
        print("  [10] 5代血統表出力（HTML/CLI） (--pedigree <ID>)")
        print("  [11] サイアーライン系統図出力 (--sire-tree)")
        print("  【レース開催・番組表 (Phase 3)】")
        print("  [12] 年間レース番組表・スケジュール確認 (--program)")
        print("  [13] 1週レース開催シミュレーション (--simulate-week)")
        print("  [14] 1ヶ月(4週)レース開催シミュレーション (--simulate-month)")
        print("  [15] 年間(48週)レース開催シミュレーション (--simulate-race-year)")
        print("  [16] レース結果・走破タイム閲覧 (--race-results)")
        print("  [17] 5大リーディングランキング確認 (--rankings)")
        print("  【繁殖・年進行 (Phase 2)】")
        print("  [18] 年間種付け・交配シミュレーション (--breed)")
        print("  [19] 年進行処理（加齢・引退・新馬入厩・承継） (--advance-year)")
        print("  【管理】")
        print("  [20] 単体テスト実行")
        print("  [21] 設定情報確認・DBパス変更")
        print("  【GUIデータ可視化 (Phase 4)】")
        print("  [22] GUIデータ可視化＆レース再生システム起動 (--gui)")
        print("  [0] 終了")
        print("============================================================")
        try:
            choice = input("処理番号を入力してください (0-21): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n終了します。")
            break

        if choice == "1":
            confirm = input("既存データは上書きされます。初期化しますか？ (y/N): ").strip().lower()
            if confirm == "y":
                db = get_db()
                initializer = DatabaseInitializer(db)
                initializer.initialize_all(force_recreate=True)
                builder = RaceProgramBuilder(db)
                builder.register_annual_program(year=1)
                print("[OK] 年間48週の全レース番組表を登録しました。")
                show_summary()
        elif choice == "2":
            show_summary()
        elif choice == "3":
            browse_active_horses()
        elif choice == "4":
            viewer.list_sires()
            h_id = input("\n詳細を確認したい馬IDを入力 (Enterで戻る): ").strip()
            if h_id.isdigit():
                viewer.show_horse_detail(int(h_id))
        elif choice == "5":
            browse_dams()
        elif choice == "6":
            reg = input("地方名で絞り込みますか？ (北海道/東北/関東/中部/北陸/近畿/中国/四国/九州、空欄で全件): ").strip()
            viewer.list_breeders(region_filter=reg if reg else None)
        elif choice == "7":
            loc = input("所属で絞り込みますか？ (美浦/栗東、空欄で全件): ").strip()
            viewer.list_trainers(location_filter=loc if loc else None)
        elif choice == "8":
            loc = input("所属で絞り込みますか？ (美浦/栗東、空欄で全件): ").strip()
            viewer.list_jockeys(location_filter=loc if loc else None)
        elif choice == "9":
            h_id = input("確認したい馬IDを入力してください: ").strip()
            if h_id.isdigit():
                viewer.show_horse_detail(int(h_id))
            else:
                print("数字で馬IDを入力してください。")
        elif choice == "10":
            h_id = input("血統表を確認したい馬IDを入力してください: ").strip()
            if h_id.isdigit():
                viewer.show_pedigree(int(h_id))
            else:
                print("数字で馬IDを入力してください。")
        elif choice == "11":
            viewer.show_sire_line_tree()
        elif choice == "12":
            w = input("指定週を入力してください (1〜48、空欄で全件): ").strip()
            show_program(week=int(w) if w.isdigit() else None)
        elif choice == "13":
            db = get_db()
            controller = CalendarController(db)
            w_str = input("開催する週を入力してください (1〜48、デフォルト: 1): ").strip()
            w = int(w_str) if w_str.isdigit() else 1
            res = controller.run_week(year=1, week=w)
            print(f"\n[OK] 第{w}週のレースシミュレーションが完了しました。 (開催レース数: {res['races_run']}, 出走頭数: {res['starters_count']})")
            if res.get("retired_maidens", 0) > 0:
                print(f"     ※ 第28週足切りにより {res['retired_maidens']} 頭の3歳未勝利馬が引退しました。")
            show_race_results(limit=5)
        elif choice == "14":
            db = get_db()
            controller = CalendarController(db)
            m_str = input("開催する月を入力してください (1〜12、デフォルト: 1): ").strip()
            m = int(m_str) if m_str.isdigit() else 1
            res_list = controller.run_month(year=1, month=m)
            total_races = sum(r['races_run'] for r in res_list)
            print(f"\n[OK] 第{m}月 (4週分) のレースシミュレーションが完了しました。 (総レース数: {total_races})")
            show_race_results(limit=5)
        elif choice == "15":
            confirm = input("年間48週の全レースを一括実行します。よろしいですか？ (y/N): ").strip().lower()
            if confirm == "y":
                db = get_db()
                controller = CalendarController(db)
                summary = controller.run_year(year=1)
                print(f"\n[OK] 年間48週の全レースシミュレーションが完了しました！")
                print(f"     総開催レース数: {summary['total_races_run']}")
                print(f"     総出走馬延べ数: {summary['total_starters']}")
                print(f"     未勝利引退馬数: {summary['retired_maidens']}")
                show_summary()
        elif choice == "16":
            r_id = input("レースIDを入力してください (空欄で直近重賞一覧): ").strip()
            show_race_results(race_id=int(r_id) if r_id.isdigit() else None)
        elif choice == "17":
            print("確認したいリーディングを選択してください:")
            print("  [1] 騎手リーディング")
            print("  [2] 調教師リーディング")
            print("  [3] 馬主リーディング")
            print("  [4] 生産牧場リーディング")
            print("  [5] サイアーリーディング")
            c = input("選択 (1-5): ").strip()
            cat_map = {"1": "jockey", "2": "trainer", "3": "owner", "4": "breeder", "5": "sire"}
            if c in cat_map:
                show_5_rankings(category=cat_map[c])
        elif choice == "18":
            db = get_db()
            breeding_engine = BreedingEngine(db)
            newborns = breeding_engine.perform_annual_breeding(current_year=1)
            print(f"[OK] {len(newborns)} 頭の当歳馬が誕生しました。")
            show_summary()
        elif choice == "19":
            db = get_db()
            lifecycle_engine = LifecycleEngine(db)
            res = lifecycle_engine.advance_year(current_year=1)
            print(f"[OK] {res['advanced_to_year']} 年度へ進行しました。")
            show_summary()
        elif choice == "20":
            run_tests()
        elif choice == "21":
            print(f"\n現在の設定ファイル: {config_mgr.config_path}")
            print(f"現在のDB配置パス:   {config_mgr.get_db_path()}")
            change = input("DB保存先パスを変更しますか？ (y/N): ").strip().lower()
            if change == "y":
                new_path = input("新しいDBファイルの絶対パスを入力してください: ").strip()
                if new_path:
                    config_mgr.set_db_path(new_path)
        elif choice == "22":
            from src.gui.app import launch_gui
            launch_gui()
        elif choice == "0":
            print("終了します。")
            break


def main() -> None:
    """コマンドライン引数の解析と実行"""
    parser = argparse.ArgumentParser(description="競馬シミュレーションエンジン (Horse Racing Sim)")
    parser.add_argument("--init", action="store_true", help="データベースを初期化し、初期個体群および番組表を生成")
    parser.add_argument("--summary", action="store_true", help="現在のDB内集計サマリを表示")
    parser.add_argument("--horses", action="store_true", help="現役競走馬リストを表示")
    parser.add_argument("--limit", type=int, default=20, help="表示件数上限 (デフォルト: 20)")
    parser.add_argument("--offset", type=int, default=0, help="オフセット件数 (デフォルト: 0)")
    parser.add_argument("--sires", action="store_true", help="種牡馬リストを表示")
    parser.add_argument("--dams", action="store_true", help="繁殖牝馬リストを表示")
    parser.add_argument("--breeders", action="store_true", help="生産牧場リストを表示")
    parser.add_argument("--trainers", action="store_true", help="厩舎リスト（美浦/栗東）を表示")
    parser.add_argument("--jockeys", action="store_true", help="騎手リスト（美浦/栗東）を表示")
    parser.add_argument("--location", type=str, help="厩舎や騎手の所属絞り込み (美浦/栗東)")
    parser.add_argument("--region", type=str, help="生産牧場リスト等の地域絞り込み (北海道/東北/関東/中部/北陸/近畿/中国/四国/九州)")
    parser.add_argument("--horse-id", type=int, help="指定IDの馬の詳細情報を表示")
    parser.add_argument("--pedigree", type=int, help="指定IDの馬の3代血統表を表示")
    parser.add_argument("--sire-tree", action="store_true", help="サイアーライン系統図を表示")
    parser.add_argument("--stats", type=str, choices=["horse", "trainer", "jockey", "breeder"], help="成績ランキングを表示")
    parser.add_argument("--period", type=str, choices=["career", "annual"], default="career", help="成績の期間 (career:通算, annual:当年)")
    parser.add_argument("--test", action="store_true", help="単体テストを実行")
    parser.add_argument("--samples", action="store_true", help="サンプルデータを表示")
    parser.add_argument("--breed", type=int, nargs="?", const=1, help="指定年度の交配・当歳馬誕生シミュレーションを実行 (デフォルト: 1)")
    parser.add_argument("--advance-year", type=int, nargs="?", const=1, help="指定年度からの1年進行処理を実行 (デフォルト: 1)")
    parser.add_argument("--set-db-path", type=str, help="データベースファイルの保存先パスを変更")
    parser.add_argument("--show-config", action="store_true", help="現在の設定を表示")
    parser.add_argument("--menu", action="store_true", help="対話型メニューを表示")

    # Phase 3 引数
    parser.add_argument("--register-program", type=int, nargs="?", const=1, help="年間48週の番組表を生成・DB登録 (デフォルト: 1年度)")
    parser.add_argument("--program", type=int, nargs="?", const=0, help="番組表を表示 (週指定可能、引数なしで全件)")
    parser.add_argument("--simulate-week", type=int, help="指定週のレースを開催実行 (1〜48)")
    parser.add_argument("--simulate-month", type=int, help="指定月のレースを開催実行 (1〜12)")
    parser.add_argument("--simulate-race-year", type=int, nargs="?", const=1, help="年間48週の全レースを一括シミュレーション実行")
    parser.add_argument("--race-results", type=int, nargs="?", const=0, help="レース結果を表示 (レースID指定可能、引数なしで直近重賞)")
    parser.add_argument("--rankings", type=str, choices=["jockey", "trainer", "owner", "breeder", "sire"], help="5大リーディングランキングを表示")
    parser.add_argument("--gui", action="store_true", help="PyQt6 GUIデータ可視化＆レース再生システムを起動")

    args = parser.parse_args()
    config_mgr = get_config()
    viewer = HorseViewer()

    if args.gui:
        from src.gui.app import launch_gui
        launch_gui()
        return

    if len(sys.argv) == 1 or args.menu:
        interactive_menu()
        return

    if args.set_db_path:
        config_mgr.set_db_path(args.set_db_path)
        print(f"[OK] データベースの保存先を変更しました: {config_mgr.get_db_path()}")

    if args.show_config:
        print(f"設定ファイル: {config_mgr.config_path}")
        print(f"DB配置パス:   {config_mgr.get_db_path()}")

    if args.init:
        db = get_db()
        initializer = DatabaseInitializer(db)
        initializer.initialize_all(force_recreate=True)
        builder = RaceProgramBuilder(db)
        builder.register_annual_program(year=1)
        print("[OK] 年間48週の番組表を登録しました。")
        show_summary()

    if args.summary:
        show_summary()

    if args.register_program is not None:
        db = get_db()
        builder = RaceProgramBuilder(db)
        count = builder.register_annual_program(year=args.register_program)
        print(f"[OK] {args.register_program} 年度の番組表 {count} レースを登録しました。")

    if args.program is not None:
        show_program(week=args.program if args.program > 0 else None)

    if args.simulate_week is not None:
        db = get_db()
        controller = CalendarController(db)
        res = controller.run_week(year=1, week=args.simulate_week)
        print(f"[OK] 第{args.simulate_week}週 レース完了 (開催: {res['races_run']}レース, 出走: {res['starters_count']}頭)")
        show_race_results(limit=5)

    if args.simulate_month is not None:
        db = get_db()
        controller = CalendarController(db)
        res_list = controller.run_month(year=1, month=args.simulate_month)
        print(f"[OK] 第{args.simulate_month}月 レース完了 (総レース: {sum(r['races_run'] for r in res_list)})")
        show_race_results(limit=5)

    if args.simulate_race_year is not None:
        db = get_db()
        controller = CalendarController(db)
        res = controller.run_year(year=args.simulate_race_year)
        print(f"[OK] {args.simulate_race_year} 年度 年間48週全レース完了！ (総レース: {res['total_races_run']}, 出走: {res['total_starters']}頭, 未勝利引退: {res['retired_maidens']}頭)")
        show_summary()

    if args.race_results is not None:
        show_race_results(race_id=args.race_results if args.race_results > 0 else None)

    if args.rankings is not None:
        show_5_rankings(category=args.rankings)

    if args.breed is not None:
        db = get_db()
        breeding_engine = BreedingEngine(db)
        newborns = breeding_engine.perform_annual_breeding(current_year=args.breed)
        print(f"[OK] {len(newborns)} 頭の当歳馬が誕生しました。")
        show_summary()

    if args.advance_year is not None:
        db = get_db()
        lifecycle_engine = LifecycleEngine(db)
        res = lifecycle_engine.advance_year(current_year=args.advance_year)
        print(f"[OK] {res['advanced_to_year']} 年度へ進行しました。")
        show_summary()

    if args.horses:
        viewer.list_active_horses(limit=args.limit, offset=args.offset)

    if args.sires:
        viewer.list_sires()

    if args.dams:
        viewer.list_dams(limit=args.limit, offset=args.offset)

    if args.breeders:
        viewer.list_breeders(region_filter=args.region)

    if args.trainers:
        viewer.list_trainers(location_filter=args.location)

    if args.jockeys:
        viewer.list_jockeys(location_filter=args.location)

    if args.horse_id is not None:
        viewer.show_horse_detail(args.horse_id)

    if args.pedigree is not None:
        viewer.show_pedigree(args.pedigree)

    if args.sire_tree:
        viewer.show_sire_line_tree()

    if args.stats:
        viewer.show_rankings(category=args.stats, period=args.period)

    if args.test:
        run_tests()

    if args.samples:
        show_samples()


if __name__ == "__main__":
    main()
