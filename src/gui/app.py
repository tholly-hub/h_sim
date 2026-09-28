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
from src.gui.views.lineage_view import LineageView
from src.gui.views.rankings_view import RankingsView
from src.gui.views.simulation_status_view import SimulationStatusView


class LazyTabContainer(QWidget):
    """タブが選択された時に初めて内部Viewをインスタンス化する遅延コンテナ"""

    def __init__(self, factory_fn, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.factory_fn = factory_fn
        self.view: Optional[QWidget] = None
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

    def ensure_view(self) -> QWidget:
        if self.view is None:
            self.view = self.factory_fn()
            self._layout.addWidget(self.view)
        return self.view

    def is_loaded(self) -> bool:
        return self.view is not None


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

        # 第1タブ: ダッシュボード（起動時に即時生成・表示）
        self.view_dashboard = DashboardView(self.db)
        self.tabs.addTab(self.view_dashboard, "📊 ダッシュボード")

        # 第2〜7タブ: 遅延ロードコンテナ（タブ選択時に初めて初期化）
        self.container_rankings = LazyTabContainer(lambda: RankingsView(self.db, parent=self), parent=self)
        self.container_awards = LazyTabContainer(lambda: AwardsView(self.db, parent=self), parent=self)
        self.container_database = LazyTabContainer(lambda: DatabaseView(self.db), parent=self)
        self.container_lineage = LazyTabContainer(lambda: LineageView(self.db, parent=self), parent=self)
        self.container_analytics = LazyTabContainer(lambda: AnalyticsView(self.db), parent=self)
        self.container_sim_status = LazyTabContainer(lambda: SimulationStatusView(self.db), parent=self)

        self.tabs.addTab(self.container_rankings, "🏆 各種リーディング")
        self.tabs.addTab(self.container_awards, "👑 表彰")
        self.tabs.addTab(self.container_database, "📚 競馬データベース")
        self.tabs.addTab(self.container_lineage, "🌳 系統樹")
        self.tabs.addTab(self.container_analytics, "📈 能力推移 & 走破タイム")
        self.tabs.addTab(self.container_sim_status, "⚙️ シミュレーション状況")

        main_layout.addWidget(self.tabs)

        # ステータスバー
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(f"データベース接続完了: {self.db.db_path}")

    @property
    def view_rankings(self) -> Optional[RankingsView]:
        return self.container_rankings.view if self.container_rankings.is_loaded() else None

    @property
    def view_awards(self) -> Optional[AwardsView]:
        return self.container_awards.view if self.container_awards.is_loaded() else None

    @property
    def view_database(self) -> Optional[DatabaseView]:
        return self.container_database.view if self.container_database.is_loaded() else None

    @property
    def view_lineage(self) -> Optional[LineageView]:
        return self.container_lineage.view if self.container_lineage.is_loaded() else None

    @property
    def view_analytics(self) -> Optional[AnalyticsView]:
        return self.container_analytics.view if self.container_analytics.is_loaded() else None

    @property
    def view_sim_status(self) -> Optional[SimulationStatusView]:
        return self.container_sim_status.view if self.container_sim_status.is_loaded() else None

    def _connect_signals(self) -> None:
        """シミュレーション状況またはダッシュボードで進行した際に全画面を自動更新"""
        self.view_dashboard.simulation_completed.connect(self._on_simulation_completed)
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_simulation_completed(self) -> None:
        """シミュレーション進行完了時の全画面データ更新（ロード済みのViewのみ更新）"""
        self.view_dashboard.refresh_dashboard()
        if self.container_rankings.is_loaded() and self.container_rankings.view:
            self.container_rankings.view.refresh_data()
        if self.container_awards.is_loaded() and self.container_awards.view:
            self.container_awards.view.refresh_all()
        if self.container_database.is_loaded() and self.container_database.view:
            self.container_database.view.refresh_all()
        if self.container_lineage.is_loaded() and self.container_lineage.view:
            self.container_lineage.view.refresh_all()
        if self.container_analytics.is_loaded() and self.container_analytics.view:
            self.container_analytics.view.refresh_charts()
        if self.container_sim_status.is_loaded() and self.container_sim_status.view:
            self.container_sim_status.view.refresh_view()
        self.status_bar.showMessage("シミュレーション進行が完了し、全データを更新しました。", 5000)

    def _on_tab_changed(self, index: int) -> None:
        """タブ切り替え時に該当画面を遅延生成＆データ最新化"""
        try:
            if index == 0:
                self.view_dashboard.refresh_dashboard()
            elif index == 1:
                v = self.container_rankings.ensure_view()
                if hasattr(v, "ensure_loaded"):
                    v.ensure_loaded()
                else:
                    v.refresh_data()
            elif index == 2:
                v = self.container_awards.ensure_view()
                if hasattr(v, "ensure_loaded"):
                    v.ensure_loaded()
                else:
                    v.refresh_all()
            elif index == 3:
                v = self.container_database.ensure_view()
                v.refresh_all()
            elif index == 4:
                v = self.container_lineage.ensure_view()
                v.ensure_loaded()
            elif index == 5:
                v = self.container_analytics.ensure_view()
                if hasattr(v, "ensure_loaded"):
                    v.ensure_loaded()
                else:
                    v.refresh_charts()
            elif index == 6:
                v = self.container_sim_status.ensure_view()
                # シグナルを未接続なら接続
                if not getattr(v, "_connected_to_main", False):
                    v.simulation_completed.connect(self._on_simulation_completed)
                    v._connected_to_main = True
                v.refresh_view()
        except Exception as e:
            print(f"⚠️ [タブ切り替えエラー] index={index}: {e}", file=sys.stderr)
            traceback.print_exc()


def launch_gui(db_path: Optional[str] = None) -> None:
    """GUIアプリケーションの起動"""
    sys.excepthook = _global_exception_hook

    print("[1/3] GUI環境を初期化中...", flush=True)
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setStyleSheet(MAIN_STYLESHEET)

    print("[2/3] データベース接続中...", flush=True)
    db = Database(db_path) if db_path else get_db()
    print(f"      対象DB: {db.db_path}", flush=True)

    print("[3/3] メイン画面を構築中...", flush=True)
    window = MainWindow(db)
    
    print("[OK] メインウィンドウを表示します。", flush=True)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    launch_gui()
