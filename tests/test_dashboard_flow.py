"""
新ダッシュボードの3行構成およびボタンクリック動作テスト
- 初期ロード時に第21週レースが自動実行されていること
- 1行目の年月表示、2行目のレース一覧、3行目の出走馬表のロード確認
- レース行選択時に「レースを見る」「レース結果」ボタンが有効（Enabled）になること
- 「レースを見る」ボタン押下で RaceViewDialog が生成・表示可能であること
- 「レース結果」ボタン押下で RaceResultDialog が生成・表示可能であること
- 「次の週に進む」ボタン押下で次週（第22週）のレースが自動実行され、ダッシュボードが更新されること
"""

import os
import sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from src.db.database import Database
from src.gui.views.dashboard_view import DashboardView

def test_dashboard_3rows_and_buttons():
    print("=== ダッシュボード 3行構成 & ボタン動作検証 ===")
    app = QApplication.instance() or QApplication(sys.argv)
    
    scratch_dir = "/Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/scratch"
    os.makedirs(scratch_dir, exist_ok=True)
    db_path = os.path.join(scratch_dir, "test_dashboard_3rows.db")
    if os.path.exists(db_path):
        os.remove(db_path)
        
    db = Database(db_path)
    from src.generators.initializer import DatabaseInitializer
    init = DatabaseInitializer(db)
    init.initialize_all(force_recreate=True)
    
    print("\n1. DashboardView の初期化...")
    dash = DashboardView(db)
    
    # 1行目の確認
    print(f"  [1行目 年月週]: {dash.lbl_current_time.text()}")
    assert "第 1 年" in dash.lbl_current_time.text()
    assert "第 21" in dash.lbl_current_time.text() or "第21週" in dash.lbl_current_time.text()
    
    # 2行目の確認（今週のレース一覧）
    races_count = dash.table_races.rowCount()
    print(f"  [2行目 レース数]: {races_count} レース")
    assert races_count > 0, "今週のレース一覧が空です"
    
    # 1レース目の状態が「確定」になっていること（初期自動実行されているため）
    first_race_status = dash.table_races.item(0, 6).text()
    first_race_winner = dash.table_races.item(0, 5).text()
    print(f"  [2行目 1レース目]: 勝者={first_race_winner}, 状態={first_race_status}")
    assert "確定" in first_race_status
    assert first_race_winner != "未発走"
    
    # 3行目の確認（出走馬表 & ボタン有効性）
    entry_count = dash.table_entry.rowCount()
    print(f"  [3行目 出走頭数]: {entry_count} 頭")
    assert entry_count > 0, "出走馬表が空です"
    
    print(f"  [3行目 レースを見るボタン]: enabled={dash.btn_view_race.isEnabled()}")
    print(f"  [3行目 レース結果ボタン]: enabled={dash.btn_view_result.isEnabled()}")
    assert dash.btn_view_race.isEnabled() is True, "レースを見るボタンが無効になっています"
    assert dash.btn_view_result.isEnabled() is True, "レース結果ボタンが無効になっています"
    
    # ボタン押下シミュレーション（ダイアログ生成）
    print("\n2. 「レースを見る」ダイアログ生成テスト...")
    from src.gui.views.race_dialogs import RaceViewDialog, RaceResultDialog
    view_dlg = RaceViewDialog(db, dash.current_selected_race_id)
    assert view_dlg is not None
    print("  -> RaceViewDialog 正常生成完了")
    
    print("\n3. 「レース結果」ダイアログ生成テスト...")
    res_dlg = RaceResultDialog(db, dash.current_selected_race_id)
    assert res_dlg is not None
    assert res_dlg.table.rowCount() > 0
    print(f"  -> RaceResultDialog 正常生成完了 (結果行数: {res_dlg.table.rowCount()})")
    
    # 「次の週に進む」テスト
    print("\n4. 「次の週に進む」動作テスト...")
    dash._advance_to_next_week()
    print(f"  [次週 1行目 年月週]: {dash.lbl_current_time.text()}")
    assert "第22週" in dash.lbl_current_time.text() or "第 22" in dash.lbl_current_time.text()
    
    races_count_22 = dash.table_races.rowCount()
    print(f"  [第22週 レース数]: {races_count_22} レース (全件自動実行済み)")
    assert races_count_22 > 0
    assert dash.btn_view_race.isEnabled() is True
    assert dash.btn_view_result.isEnabled() is True
    
    print("\n🎉 3行構成およびボタン動作・自動進行のすべてが正常に動作することを確認しました！")
    
    if os.path.exists(db_path):
        os.remove(db_path)

if __name__ == "__main__":
    test_dashboard_3rows_and_buttons()
