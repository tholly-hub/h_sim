"""
GUI起動 & 週進行 & ダイアログ連動テスト
"""
import os
import sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from src.db.database import Database
from src.gui.views.dashboard_view import DashboardView
from src.gui.views.annual_events_dialogs import SpringFoalingDialog, SpringBreedingDialog, YearEndAwardsDialog, UnvictoryRetirementDialog
from src.gui.views.simulation_status_view import SimulationStatusView
from src.gui.app import MainWindow

def test_gui_integration():
    print("=== GUIインテグレーション & 進行テスト ===")
    app = QApplication.instance() or QApplication(sys.argv)
    
    scratch_dir = "/Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/scratch"
    os.makedirs(scratch_dir, exist_ok=True)
    db_path = os.path.join(scratch_dir, "test_gui_crash.db")
    if os.path.exists(db_path):
        os.remove(db_path)
        
    db = Database(db_path)
    from src.generators.initializer import DatabaseInitializer
    init = DatabaseInitializer(db)
    init.initialize_all(force_recreate=True)
    
    window = MainWindow(db)
    window.show()
    print("✅ 1. メインウィンドウ初期化 & 表示成功")
    
    # ダッシュボードでの週進行をテスト (第21週 -> 第22週)
    dash = window.view_dashboard
    print(f"現在週: {dash.lbl_current_time.text()}")
    dash._advance_to_next_week()
    print(f"1週進行後: {dash.lbl_current_time.text()}")
    print("✅ 2. ダッシュボード「次の週に進む」正常完了")
    
    # 3月出産ダイアログのテスト
    foal_dlg = SpringFoalingDialog(db, 1, window)
    print(f"3月出産ダイアログ 表示頭数: {foal_dlg.table.rowCount()}")
    print("✅ 3. SpringFoalingDialog 初期化・読み込み成功")
    
    # 4月種付けダイアログのテスト
    breed_dlg = SpringBreedingDialog(db, 1, window)
    print(f"4月種付けダイアログ 表示頭数: {breed_dlg.table.rowCount()}")
    print("✅ 4. SpringBreedingDialog 初期化・読み込み成功")
    
    # 各タブの切り替えテスト
    for idx in range(5):
        window.tabs.setCurrentIndex(idx)
        print(f"タブ {idx} 切り替え成功")
    print("✅ 5. 全タブ切り替え成功")

    if os.path.exists(db_path):
        os.remove(db_path)
    print("\n🎉 すべてのGUIクラッシュテストに合格しました！")

if __name__ == "__main__":
    test_gui_integration()
