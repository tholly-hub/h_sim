"""
GUIコンポーネントのインポートおよびHeadless初期化テスト
- MainWindow
- DashboardView
- SimulationStatusView
- RecordsView
- AnalyticsView
- RaceViewDialog / RaceResultDialog
- HorseDetailDialog
"""

import os
import sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from src.db.database import Database
from src.gui.app import MainWindow
from src.gui.views.dashboard_view import DashboardView
from src.gui.views.simulation_status_view import SimulationStatusView
from src.gui.views.records_view import RecordsView
from src.gui.views.database_view import DatabaseView
from src.gui.views.analytics_view import AnalyticsView
from src.gui.views.race_dialogs import RaceViewDialog, RaceResultDialog
from src.gui.views.horse_detail_dialog import HorseDetailDialog

def test_gui():
    print("=== GUI Headless インスタンス化テスト ===")
    app = QApplication.instance() or QApplication(sys.argv)
    
    # 既存のDBを使用（または新規）
    db = Database()
    
    # 各ビューの初期化
    print("1. DashboardView 初期化中...")
    dash = DashboardView(db)
    assert dash is not None
    print("  -> DashboardView OK")
    
    print("2. SimulationStatusView 初期化中...")
    sim_status = SimulationStatusView(db)
    assert sim_status is not None
    print("  -> SimulationStatusView OK")
    
    print("3. RecordsView & DatabaseView 初期化中...")
    records = RecordsView(db)
    assert records is not None
    db_view = DatabaseView(db)
    assert db_view is not None
    print("  -> RecordsView & DatabaseView OK")
    
    print("4. AnalyticsView 初期化中...")
    analytics = AnalyticsView(db)
    assert analytics is not None
    print("  -> AnalyticsView OK")
    
    print("5. MainWindow 初期化中...")
    main_win = MainWindow(db)
    assert main_win is not None
    print("  -> MainWindow OK")
    
    # データベースに馬やレースがあればダイアログもテスト
    with db.session() as conn:
        h = conn.execute("SELECT horse_id FROM horses LIMIT 1").fetchone()
        r = conn.execute("SELECT race_id FROM races LIMIT 1").fetchone()
        
    if h:
        print("6. HorseDetailDialog 初期化中...")
        h_dlg = HorseDetailDialog(db, h["horse_id"])
        assert h_dlg is not None
        print("  -> HorseDetailDialog OK")
        
    if r:
        print("7. RaceDialogs 初期化中...")
        res_dlg = RaceResultDialog(db, r["race_id"])
        view_dlg = RaceViewDialog(db, r["race_id"])
        assert res_dlg is not None
        assert view_dlg is not None
        print("  -> RaceDialogs OK")
        
    print("\n🎉 全てのGUIコンポーネントが正常に起動・初期化できました！")

if __name__ == "__main__":
    test_gui()
