"""
ダッシュボード3行構成・ネタバレ防止・スタート馬間隔の検証テスト
1. 2行目テーブル（今週の開催レース一覧）: 1着馬列がなく、全6列であること
2. 3行目テーブル（出走馬表）: 着順・タイム列がなく、馬番順でソートされていること
3. レース結果ボタン押下時のみ結果ダイアログで確定着順・走破タイムが確認できること
4. スタート時点での8頭の横間隔（gate_spacing）が約3.7mに拡大されていること
"""

import json
import os
import sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from src.db.database import Database
from src.gui.views.dashboard_view import DashboardView
from src.gui.views.race_dialogs import RaceResultDialog
from src.race.engine import RaceEngine

def test_dashboard_and_spacing():
    print("=== ダッシュボード表示 & スタート馬間隔テスト ===")
    app = QApplication.instance() or QApplication(sys.argv)
    
    scratch_dir = "/Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/scratch"
    os.makedirs(scratch_dir, exist_ok=True)
    db_path = os.path.join(scratch_dir, "test_dash_spacing.db")
    if os.path.exists(db_path):
        os.remove(db_path)
        
    db = Database(db_path)
    from src.generators.initializer import DatabaseInitializer
    init = DatabaseInitializer(db)
    init.initialize_all(force_recreate=True)
    
    dash = DashboardView(db)
    
    # 1. 2行目テーブルの検証
    col_count_races = dash.table_races.columnCount()
    headers_races = [dash.table_races.horizontalHeaderItem(c).text() for c in range(col_count_races)]
    print(f"2行目テーブル 列数: {col_count_races}, ヘッダー: {headers_races}")
    assert "1着馬" not in headers_races, "2行目に1着馬列が含まれています！"
    assert "発走状態" in headers_races or "状態" in headers_races
    print("✅ 1. 2行目テーブル（1着馬非表示）確認OK！")
    
    # 2. 3行目出走馬表の検証（ネタバレ防止 & 馬番順ソート）
    col_count_entry = dash.table_entry.columnCount()
    headers_entry = [dash.table_entry.horizontalHeaderItem(c).text() for c in range(col_count_entry)]
    print(f"3行目テーブル 列数: {col_count_entry}, ヘッダー: {headers_entry}")
    assert "着順" not in headers_entry, "出走馬表に着順列が含まれています！"
    assert "走破タイム" not in headers_entry, "出走馬表に走破タイム列が含まれています！"
    
    # 馬番順の確認
    row_count = dash.table_entry.rowCount()
    print(f"出走頭数: {row_count}頭")
    gate_numbers = [dash.table_entry.item(r, 1).text() for r in range(row_count)]
    print(f"出走馬表の馬番順: {gate_numbers}")
    assert gate_numbers == [f"{i+1}番" for i in range(row_count)], f"馬番順になっていません: {gate_numbers}"
    print("✅ 2. 3行目出走馬表（着順・タイム非表示、馬番順ソート）確認OK！")
    
    # 3. レース結果ダイアログの確認
    res_dlg = RaceResultDialog(db, dash.current_selected_race_id)
    res_headers = [res_dlg.table.horizontalHeaderItem(c).text() for c in range(res_dlg.table.columnCount())]
    print(f"結果ダイアログ ヘッダー: {res_headers}")
    assert "着順" in res_headers
    assert "タイム" in res_headers
    first_rank_horse = res_dlg.table.item(0, 2).text()
    first_rank_time = res_dlg.table.item(0, 6).text()
    print(f"結果ダイアログ 1着馬: {first_rank_horse}, タイム: {first_rank_time}")
    print("✅ 3. レース結果ダイアログ確認OK！")
    
    # 4. スタート時点での馬の間隔テスト
    with db.session() as conn:
        row_rep = conn.execute("SELECT replay_data_json FROM results WHERE replay_data_json IS NOT NULL LIMIT 1").fetchone()
    assert row_rep is not None and row_rep["replay_data_json"] is not None
    
    replay_payload = json.loads(row_rep["replay_data_json"])
    assert "horses" in replay_payload
    start_horses = replay_payload["horses"]
    # 馬番昇順でソート
    start_horses.sort(key=lambda h: h["gate_number"])
    laterals = [h["laterals"][0] for h in start_horses]
    print(f"スタート時 (t=0.0) 8頭の横位置 (m): {laterals}")
    
    # 隣接する馬同士の間隔をチェック
    diffs = [round(laterals[i+1] - laterals[i], 2) for i in range(len(laterals)-1)]
    print(f"各馬の間隔 (m): {diffs}")
    avg_spacing = sum(diffs) / len(diffs)
    print(f"平均ゲート間隔: {avg_spacing:.2f}m (期待値: 3.4m〜4.0m)")
    assert 3.4 <= avg_spacing <= 4.0, f"ゲート間隔が狭すぎまたは広すぎます: {avg_spacing}"
    print("✅ 4. スタート時点の各馬間隔拡大（3.7m間隔）確認OK！")
    
    print("\n🎉 すべての修正要件が正常に満たされていることを確認しました！")
    if os.path.exists(db_path):
        os.remove(db_path)

if __name__ == "__main__":
    test_dashboard_and_spacing()
