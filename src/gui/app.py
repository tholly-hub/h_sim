"""
PyQt6 メインウィンドウ & GUIアプリケーション起動エントリ
- 5大メイン画面のタブ統合
- ダッシュボード・馬情報・リーディング・推移グラフ・レースリプレイ
- ダークテーマスタイルシート適用
"""

from __future__ import annotations

import sys
from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
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
from src.gui.views.horse_browser_view import HorseBrowserView
from src.gui.views.race_replay_view import RaceReplayView
from src.gui.views.rankings_view import RankingsView


class MainWindow(QMainWindow):
    """競馬シミュレーション メインウィンドウ"""

    def __init__(self, db: Optional[Database] = None):
        super().__init__()
        self.db = db or get_db()
        self.setWindowTitle("競馬シミュレーションエンジン - データ可視化 & 分析システム (Phase 4)")
        self.resize(1280, 840)
        self.setMinimumSize(1024, 700)

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

        # 各画面のインスタンス化
        self.view_dashboard = DashboardView(self.db)
        self.view_horses = HorseBrowserView(self.db)
        self.view_rankings = RankingsView(self.db)
        self.view_analytics = AnalyticsView(self.db)
        self.view_replay = RaceReplayView(self.db)

        # タブへの追加
        self.tabs.addTab(self.view_dashboard, "📊 ダッシュボード")
        self.tabs.addTab(self.view_horses, "🐎 競走馬・血統表ブラウザ")
        self.tabs.addTab(self.view_rankings, "🏆 5大リーディング & 規模階層")
        self.tabs.addTab(self.view_analytics, "📈 1600mタイム・能力推移")
        self.tabs.addTab(self.view_replay, "🎬 レース結果 & 2Dリプレイ")

        main_layout.addWidget(self.tabs)

        # ステータスバー
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(f"データベース接続完了: {self.db.db_path}")

    def _connect_signals(self) -> None:
        """ダッシュボードでシミュレーションが進行した際に全画面を自動更新"""
        self.view_dashboard.simulation_completed.connect(self._on_simulation_completed)
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_simulation_completed(self) -> None:
        """シミュレーション進行完了時の全画面データ更新"""
        self.view_horses.search_horses()
        self.view_rankings.refresh_data()
        self.view_analytics.refresh_charts()
        self.view_replay.load_race_list()
        self.status_bar.showMessage("シミュレーション進行が完了し、全データを更新しました。", 5000)

    def _on_tab_changed(self, index: int) -> None:
        """タブ切り替え時に該当画面のデータを最新化"""
        if index == 1:
            self.view_horses.search_horses()
        elif index == 2:
            self.view_rankings.refresh_data()
        elif index == 3:
            self.view_analytics.refresh_charts()
        elif index == 4:
            self.view_replay.load_race_list()


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
