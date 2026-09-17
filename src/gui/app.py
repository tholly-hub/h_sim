"""
PyQt6 メインウィンドウ & GUIアプリケーション起動エントリ
- 5大メイン画面のタブ統合:
  1. 📊 ダッシュボード (年・月・週、今週のレース、出馬表・オッズ、レース/結果ボタン[別窓]、馬詳細[別窓])
  2. ⚙️ シミュレーション状況 (週・月・年進行、進捗、サマリー統計、ログ、DB完全初期化)
  3. ⏱️ コースレコード一覧 (12競馬場、芝・ダート別、各距離レコードタイム・年・馬名)
  4. 🏆 5大リーディング & 規模階層 (種牡馬・繁殖牝馬・馬主・厩舎・騎手)
  5. 📈 能力推移 & 走破タイム (芝・ダート別、各距離別走破タイム・能力推移グラフ)
- ダークテーマスタイルシート適用
"""

from __future__ import annotations

import sys
from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.db.database import Database, get_db
from src.gui.styles import MAIN_STYLESHEET
from src.gui.views.analytics_view import AnalyticsView
from src.gui.views.dashboard_view import DashboardView
from src.gui.views.rankings_view import RankingsView
from src.gui.views.records_view import RecordsView
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
        self.view_sim_status = SimulationStatusView(self.db)
        self.view_records = RecordsView(self.db)
        self.view_rankings = RankingsView(self.db)
        self.view_analytics = AnalyticsView(self.db)

        # タブへの追加（ユーザー要望に沿った新タブ体系）
        self.tabs.addTab(self.view_dashboard, "📊 ダッシュボード")
        self.tabs.addTab(self.view_sim_status, "⚙️ シミュレーション状況")
        self.tabs.addTab(self.view_records, "⏱️ コースレコード一覧")
        self.tabs.addTab(self.view_rankings, "🏆 5大リーディング & 規模階層")
        self.tabs.addTab(self.view_analytics, "📈 能力推移 & 走破タイム")

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
        self.view_sim_status.refresh_view()
        self.view_records.refresh_records()
        self.view_rankings.refresh_data()
        self.view_analytics.refresh_charts()
        self.status_bar.showMessage("シミュレーション進行が完了し、全データを更新しました。", 5000)

    def _on_tab_changed(self, index: int) -> None:
        """タブ切り替え時に該当画面のデータを最新化"""
        if index == 0:
            self.view_dashboard.refresh_dashboard()
        elif index == 1:
            self.view_sim_status.refresh_view()
        elif index == 2:
            self.view_records.refresh_records()
        elif index == 3:
            self.view_rankings.refresh_data()
        elif index == 4:
            self.view_analytics.refresh_charts()


def launch_gui(db_path: Optional[str] = None) -> None:
    """GUIアプリケーションの起動"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # アプリケーション全体にスタイルシートを適用
    app.setStyleSheet(MAIN_STYLESHEET)

    db = Database(db_path) if db_path else get_db()
    window = MainWindow(db)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    launch_gui()
