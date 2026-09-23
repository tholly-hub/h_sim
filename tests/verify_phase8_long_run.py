"""
Phase 8 統合検証スクリプト
- 10年分のシミュレーションを連続実行
- 各年度の繁殖牝馬頭数（600頭維持）の検証
- 種牡馬数および海外種牡馬導入の検証
- 重賞・主要レース・表彰の生成確認
"""

import sys
from pathlib import Path

from src.core.lifecycle import LifecycleEngine
from src.db.database import Database
from src.generators.initializer import DatabaseInitializer
from src.race.calendar import CalendarController
from src.race.program import RaceProgramBuilder


def run_verification():
    db_path = "data/test_verify_10years.db"
    if Path(db_path).exists():
        Path(db_path).unlink()

    db = Database(db_path)
    db.initialize_schema(force_recreate=True)

    print("=== 1. データベース初期化 ===")
    init = DatabaseInitializer(db)
    init.initialize_all(force_recreate=True, with_careers=True)

    prog_builder = RaceProgramBuilder(db)
    prog_builder.register_annual_program(year=1)

    cal = CalendarController(db)
    life = LifecycleEngine(db)

    print("\n=== 2. 10年分シミュレーション実行開始 ===")
    for y in range(1, 11):
        print(f"\n--- [第 {y} 年目 開始] ---")
        if y > 1:
            prog_builder.register_annual_program(year=y)

        # 1〜48週を実行
        for w in range(1, 49):
            cal.run_week(y, w)

        # 年末加齢・新陳代謝処理
        life.advance_year(current_year=y)

        # 検証チェック
        with db.session() as conn:
            # 繁殖牝馬頭数
            dam_cnt = conn.execute("SELECT COUNT(*) FROM dams WHERE is_active = 1").fetchone()[0]
            # 種牡馬頭数
            sire_cnt = conn.execute("SELECT COUNT(*) FROM sires WHERE is_active = 1").fetchone()[0]
            # 海外種牡馬頭数
            foreign_sire_cnt = conn.execute("SELECT COUNT(*) FROM sires WHERE is_foreign = 1").fetchone()[0]
            # 現役馬頭数
            active_cnt = conn.execute("SELECT COUNT(*) FROM horses WHERE is_active = 1").fetchone()[0]
            # 表彰件数
            award_cnt = conn.execute("SELECT COUNT(*) FROM annual_awards WHERE year = ?", (y,)).fetchone()[0]

        print(f"[第 {y} 年目 結果]")
        print(f"  - 現役繁殖牝馬数: {dam_cnt} 頭 (厳密な定員600頭維持)")
        print(f"  - 現役種牡馬数: {sire_cnt} 頭 (海外種牡馬導入数: {foreign_sire_cnt} 頭)")
        print(f"  - 現役競走馬数: {active_cnt} 頭")
        print(f"  - 年度表彰項目数: {award_cnt} 冠")

        assert dam_cnt == 600, f"第{y}年目に繁殖牝馬頭数が600頭ではありませんでした（実際: {dam_cnt}頭）"

    # テスト用DB削除
    if Path(db_path).exists():
        Path(db_path).unlink()

    print("\n🎉 10年分のシミュレーションが全件エラーなく正常終了し、繁殖牝馬600頭維持を確認しました！")


if __name__ == "__main__":
    run_verification()
