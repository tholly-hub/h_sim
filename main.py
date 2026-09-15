"""
競馬シミュレーションエンジン メインエントリポイント
Phase 1: DB環境確認、スキーマ作成、初期データ生成、競走馬/種牡馬/繁殖牝馬リスト確認、対話型メニュー
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# カレントディレクトリを sys.path に追加してモジュール参照を解決
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.core.breeding import BreedingEngine
from src.core.config import get_config
from src.core.lifecycle import LifecycleEngine
from src.db.database import get_db
from src.generators.initializer import DatabaseInitializer
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

            # 厩舎内訳 (美浦/栗東)
            trainers_miho = conn.execute("SELECT COUNT(*) FROM trainers WHERE location = '美浦'").fetchone()[0]
            trainers_ritto = conn.execute("SELECT COUNT(*) FROM trainers WHERE location = '栗東'").fetchone()[0]

            # 騎手内訳 (美浦/栗東/女性騎手)
            jockeys_miho = conn.execute("SELECT COUNT(*) FROM jockeys WHERE location = '美浦' AND is_active = 1").fetchone()[0]
            jockeys_ritto = conn.execute("SELECT COUNT(*) FROM jockeys WHERE location = '栗東' AND is_active = 1").fetchone()[0]
            female_jockeys = conn.execute("SELECT COUNT(*) FROM jockeys WHERE gender = 'female' AND is_active = 1").fetchone()[0]

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
            print(f"厩舎数:     {trainers_count} 厩舎 (美浦 {trainers_miho} / 栗東 {trainers_ritto})")
            print(f"現役騎手数: {jockeys_count} 名 (美浦 {jockeys_miho} / 栗東 {jockeys_ritto} / 内 女性騎手 {female_jockeys}名)")
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
                print("※ これ以上次のページはありません。")
        elif cmd == "p":
            if offset - limit >= 0:
                offset -= limit
            else:
                print("※ 最初のページです。")
        elif cmd == "q":
            break
        elif cmd.isdigit():
            viewer.show_horse_detail(int(cmd))
            input("\nEnterキーを押してリストに戻ります...")
        else:
            print("無効な入力です。")


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
                print("※ これ以上次のページはありません。")
        elif cmd == "p":
            if offset - limit >= 0:
                offset -= limit
            else:
                print("※ 最初のページです。")
        elif cmd == "q":
            break
        elif cmd.isdigit():
            viewer.show_horse_detail(int(cmd))
            input("\nEnterキーを押してリストに戻ります...")
        else:
            print("無効な入力です。")


def run_tests() -> None:
    """単体テストを実行"""
    print("\n--- 単体テスト実行中 ---")
    tests = ["test_phase1.py", "test_transfer.py", "test_phase2_stable_jockey.py", "test_phase3_features.py"]
    for t in tests:
        test_path = Path(__file__).resolve().parent / "tests" / t
        if test_path.exists():
            print(f"\n>> 実行中: {t}")
            subprocess.run([sys.executable, "-m", "unittest", f"tests/{t}"])


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
        print("  [1] データベース初期化＆初期データ生成 (--init)")
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
        print("  [12] 各種成績ランキング確認 (--stats)")
        print("  [13] 単体テスト実行")
        print("  [14] 設定情報確認・DBパス変更")
        print("  [15] 年間種付け・交配シミュレーション (--breed)")
        print("  [16] 年進行処理（加齢・引退・新馬入厩・世代交代・牧場分化） (--advance-year)")
        print("  [0] 終了")
        print("============================================================")
        try:
            choice = input("処理番号を入力してください (0-16): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n終了します。")
            break

        if choice == "1":
            confirm = input("既存データは上書きされます。初期化しますか？ (y/N): ").strip().lower()
            if confirm == "y":
                db = get_db()
                initializer = DatabaseInitializer(db)
                initializer.initialize_all(force_recreate=True)
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
            cat = input("カテゴリを選択 (horse/trainer/jockey/breeder、デフォルト: horse): ").strip().lower() or "horse"
            per = input("期間を選択 (career/annual、デフォルト: career): ").strip().lower() or "career"
            viewer.show_rankings(category=cat, period=per)
        elif choice == "13":
            run_tests()
        elif choice == "14":
            print(f"\n現在の設定ファイル: {config_mgr.config_path}")
            print(f"現在のDB配置パス:   {config_mgr.get_db_path()}")
            change = input("DB保存先パスを変更しますか？ (y/N): ").strip().lower()
            if change == "y":
                new_path = input("新しいDBファイルの絶対パスを入力してください: ").strip()
                if new_path:
                    config_mgr.set_db_path(new_path)
                    print(f"[OK] データベース保存先を変更しました: {config_mgr.get_db_path()}")
        elif choice == "15":
            db = get_db()
            breeding_engine = BreedingEngine(db)
            year_input = input("交配年（Year）を入力してください (デフォルト: 1): ").strip()
            year = int(year_input) if year_input.isdigit() else 1
            newborns = breeding_engine.perform_annual_breeding(current_year=year)
            print(f"[OK] {len(newborns)} 頭の当歳馬が誕生しました。")
            show_summary()
        elif choice == "16":
            db = get_db()
            lifecycle_engine = LifecycleEngine(db)
            year_input = input("現在の進行年（Year）を入力してください (デフォルト: 1): ").strip()
            year = int(year_input) if year_input.isdigit() else 1
            res = lifecycle_engine.advance_year(current_year=year)
            print(f"[OK] {res['advanced_to_year']} 年度へ進行しました。")
            show_summary()
        elif choice == "0":
            print("終了します。")
            break
        else:
            print("[警告] 0〜16の数字を入力してください。")


def main() -> None:
    parser = argparse.ArgumentParser(description="競馬シミュレーションエンジン CLI")
    parser.add_argument("--init", action="store_true", help="データベースを新規作成・初期データを生成")
    parser.add_argument("--summary", action="store_true", help="データベースの現状サマリを表示")
    parser.add_argument("--horses", action="store_true", help="現役競走馬リストを表示")
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

    args = parser.parse_args()
    config_mgr = get_config()
    viewer = HorseViewer()

    # オプションが何も指定されていない場合は対話メニューを起動
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
        show_summary()

    if args.summary:
        show_summary()

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
