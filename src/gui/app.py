"""
PyQt6 メインウィンドウ & GUIアプリケーション起動エントリ
- メイン画面のタブ体系（Phase 8刷新）:
  1. 📊 ダッシュボード (年・月・週、今週のレース、出馬表・オッズ、斤量、レース/結果ボタン[別窓]、馬詳細[別窓])
  2. 🏆 各種リーディング (騎手・調教師[年数・新人]、馬主・牧場[詳細馬連携]、サイアー[新/外])
  3. 👑 表彰 (年度代表馬・部門賞、リーディング最多勝・新人賞表彰、顕彰馬・殿堂)
  4. 📚 競馬データベース (競走馬リーディング、世代・クラス別名鑑、主要レース路線、種牡馬リスト、繁殖牝馬リスト、重賞DB、レコード)
  5. 📈 能力推移 & 走破タイム (芝・ダート別、各距離別走破タイム・能力推移グラフ)
  6. ⚙️ シミュレーション状況 (最後尾: 週・月・年進行、進捗、サマリー統計、ログ、DB完全初期化)
"""

from __future__ import annotations

import sys
import traceback
from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


def _global_exception_hook(exc_type, exc_value, exc_tb):
    """PyQt6のスロット内などで発生した未捕捉例外を安全に捕捉しクラッシュ(SIGABRT)を防止"""
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print(f"⚠️ [GUIエラー捕捉] 未捕捉の例外が発生しました:\n{tb_str}", file=sys.stderr)
    try:
        app = QApplication.instance()
        if app:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("⚠️ 処理エラー")
            msg_box.setText(f"処理中にエラーが発生しました。\n\n【詳細】\n{exc_value}")
            msg_box.setDetailedText(tb_str)
            msg_box.exec()
    except Exception:
        pass


from src.db.database import Database, get_db
from src.gui.styles import MAIN_STYLESHEET
from src.gui.views.analytics_view import AnalyticsView
from src.gui.views.awards_view import AwardsView
from src.gui.views.dashboard_view import DashboardView
from src.gui.views.database_view import DatabaseView
from src.gui.views.rankings_view import RankingsView
from src.gui.views.simulation_status_view import SimulationStatusView


class MainWindow(QMainWindow):
    """競馬シミュレーション メインウィンドウ"""

    def __init__(self, db: Optional[Database] = None):
        super().__init__()
        self.db = db or get_db()
        self.setWindowTitle("競馬シミュレーションエンジン - 統合データ分析・管理システム")
        self.resize(1320, 860)
        self.setMinimumSize(1080, 720)

        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # メインタブウィジェット
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # 各タブ画面のインスタンス化
        self.view_dashboard = DashboardView(self.db)
        self.view_rankings = RankingsView(self.db, parent=self)
        self.view_awards = AwardsView(self.db, parent=self)
        self.view_database = DatabaseView(self.db)
        self.view_analytics = AnalyticsView(self.db)
        self.view_sim_status = SimulationStatusView(self.db)

        # タブへの追加（新タブ体系: シミュレーション状況を一番右・最後尾へ）
        self.tabs.addTab(self.view_dashboard, "📊 ダッシュボード")
        self.tabs.addTab(self.view_rankings, "🏆 各種リーディング")
        self.tabs.addTab(self.view_awards, "👑 表彰")
        self.tabs.addTab(self.view_database, "📚 競馬データベース")
        self.tabs.addTab(self.view_analytics, "📈 能力推移 & 走破タイム")
        self.tabs.addTab(self.view_sim_status, "⚙️ シミュレーション状況")

        main_layout.addWidget(self.tabs)

        # ステータスバー
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(f"データベース接続完了: {self.db.db_path}")

    def _connect_signals(self) -> None:
        """シミュレーション状況またはダッシュボードで進行した際に全画面を自動更新"""
        self.view_dashboard.simulation_completed.connect(self._on_simulation_completed)
        self.view_sim_status.simulation_completed.connect(self._on_simulation_completed)
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_simulation_completed(self) -> None:
        """シミュレーション進行完了時の全画面データ更新"""
        self.view_dashboard.refresh_dashboard()
        self.view_rankings.refresh_data()
        self.view_awards.refresh_all()
        self.view_database.refresh_all()
        self.view_analytics.refresh_charts()
        self.view_sim_status.refresh_view()
        self.status_bar.showMessage("シミュレーション進行が完了し、全データを更新しました。", 5000)

    def _on_tab_changed(self, index: int) -> None:
        """タブ切り替え時に該当画面のデータを最新化"""
        if index == 0:
            self.view_dashboard.refresh_dashboard()
        elif index == 1:
            self.view_rankings.refresh_data()
        elif index == 2:
            self.view_awards.refresh_all()
        elif index == 3:
            self.view_database.refresh_all()
        elif index == 4:
            self.view_analytics.refresh_charts()
        elif index == 5:
            self.view_sim_status.refresh_view()


def launch_gui(db_path: Optional[str] = None) -> None:
    """GUIアプリケーションの起動"""
    sys.excepthook = _global_exception_hook

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setStyleSheet(MAIN_STYLESHEET)

    db = Database(db_path) if db_path else get_db()
    window = MainWindow(db)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    launch_gui()
