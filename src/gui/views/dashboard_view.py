"""
ダッシュボード & 年週進行コントローラー (PyQt6)
- 現在のシミュレーション年・週表示
- 主要統計サマリーカード
- 1週進行 / 1ヶ月進行 / 1年進行（QThread非同期実行によるUIフリーズ防止）
- 実行ログ表示
"""

from __future__ import annotations

import io
import sys
from typing import Optional
from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.lifecycle import LifecycleEngine
from src.db.database import Database, get_db
from src.race.calendar import CalendarController


class OutputRedirector(QObject):
    """sys.stdout / sys.stderr をフックしてUIログへ転送する"""
    text_written = pyqtSignal(str)

    def __init__(self, original_stream):
        super().__init__()
        self.original_stream = original_stream

    def write(self, text: str) -> None:
        if self.original_stream:
            self.original_stream.write(text)
        if text:
            self.text_written.emit(text)

    def flush(self) -> None:
        if self.original_stream:
            self.original_stream.flush()


class DataResetWorker(QThread):
    """バックグラウンドでデータベースの完全初期化・再生成を実行するワーカー"""
    progress_msg = pyqtSignal(str)
    finished_reset = pyqtSignal(bool, str)

    def __init__(self, db: Database):
        super().__init__()
        self.db = db

    def run(self) -> None:
        try:
            from src.generators.initializer import DatabaseInitializer
            init_engine = DatabaseInitializer(self.db)
            init_engine.initialize_all(force_recreate=True)
            self.finished_reset.emit(True, "✅ データの完全初期化および再生成が正常に完了しました！")
        except Exception as e:
            self.finished_reset.emit(False, f"❌ 初期化中にエラーが発生しました: {e}")



def get_current_sim_status(conn) -> tuple[int, int]:
    """DB内の消化済みレースから現在のシミュレーション年・進行対象週を取得"""
    row = conn.execute("""
        SELECT rc.year, rc.week
        FROM results r
        JOIN races rc ON r.race_id = rc.race_id
        ORDER BY rc.year DESC, rc.week DESC
        LIMIT 1
    """).fetchone()

    if not row:
        return 1, 1

    last_year = row["year"]
    last_week = row["week"]

    if last_week >= 48:
        return last_year + 1, 1
    else:
        return last_year, last_week + 1


class SimulationWorker(QThread):
    """バックグラウンドでシミュレーション進行を実行するワーカー"""

    step_progress = pyqtSignal(int, int, str)  # 現在ステップ, 最大ステップ, メッセージ
    log_emitted = pyqtSignal(str)              # ログ文字列
    finished_simulation = pyqtSignal(bool, str)

    def __init__(self, db: Database, mode: str = "week", steps: int = 1):
        super().__init__()
        self.db = db
        self.mode = mode      # 'week', 'month', 'year'
        self.steps = steps

    def run(self) -> None:
        try:
            cal = CalendarController(self.db)
            life = LifecycleEngine(self.db)

            with self.db.session() as conn:
                cur_year, cur_week = get_current_sim_status(conn)

            if self.mode == "week":
                self.step_progress.emit(0, 1, f"{cur_year}年 第{cur_week}週 シミュレーション中...")
                if cur_week <= 48:
                    res = cal.run_week(cur_year, cur_week)
                    self.log_emitted.emit(f"第{cur_week}週 レース完了 (開催: {res.get('races_run', 0)}レース, 出走: {res.get('starters_count', 0)}頭)")
                else:
                    self.log_emitted.emit(f"{cur_year}年度末の年度更新処理を実行します。")
                    life.advance_year(current_year=cur_year)
                self.step_progress.emit(1, 1, "完了")

            elif self.mode == "month":
                for w_idx in range(4):
                    with self.db.session() as conn:
                        y, w = get_current_sim_status(conn)
                    self.step_progress.emit(w_idx, 4, f"{y}年 第{w}週 進行中...")
                    if w <= 48:
                        cal.run_week(y, w)
                        self.log_emitted.emit(f"{y}年 第{w}週 完了")
                    else:
                        life.advance_year(current_year=y)
                        self.log_emitted.emit(f"★ {y+1}年度への年度更新が完了しました！")
                self.step_progress.emit(4, 4, "完了")

            elif self.mode == "year":
                with self.db.session() as conn:
                    y, w = get_current_sim_status(conn)

                weeks_to_run = 48 - w + 1
                for idx, week_num in enumerate(range(w, 49)):
                    self.step_progress.emit(idx, weeks_to_run + 1, f"{y}年 第{week_num}週 開催中...")
                    cal.run_week(y, week_num)

                # 年末年度更新
                self.step_progress.emit(weeks_to_run, weeks_to_run + 1, f"{y}年末 年度更新処理中（引退・交配・加齢）...")
                life.advance_year(current_year=y)
                self.log_emitted.emit(f"★ {y+1}年度への年度更新が完了しました！")
                self.step_progress.emit(weeks_to_run + 1, weeks_to_run + 1, "完了")

            self.finished_simulation.emit(True, "シミュレーションが正常に進行しました。")
        except Exception as e:
            self.finished_simulation.emit(False, f"エラーが発生しました: {e}")


class StatCard(QFrame):
    """統計サマリーカード"""

    def __init__(self, title: str, initial_value: str = "-", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            StatCard {
                background-color: #161b26;
                border: 1px solid #242c3d;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("statLabel")
        layout.addWidget(self.title_lbl)

        self.val_lbl = QLabel(initial_value)
        self.val_lbl.setObjectName("statValue")
        layout.addWidget(self.val_lbl)

    def set_value(self, value: str) -> None:
        self.val_lbl.setText(value)


class DashboardView(QWidget):
    """メインダッシュボード画面"""

    simulation_completed = pyqtSignal()  # シミュレーション進行完了時に他タブへ通知

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.worker: Optional[SimulationWorker] = None
        self.reset_worker: Optional[DataResetWorker] = None
        self._init_ui()
        self._init_stdout_redirection()
        self.refresh_stats()

    def _init_stdout_redirection(self) -> None:
        """ターミナル標準出力 (stdout/stderr) をUIログ欄へリダイレクト"""
        self._stdout_redirector = OutputRedirector(sys.stdout)
        self._stderr_redirector = OutputRedirector(sys.stderr)
        self._stdout_redirector.text_written.connect(self._append_stream_text)
        self._stderr_redirector.text_written.connect(self._append_stream_text)
        sys.stdout = self._stdout_redirector
        sys.stderr = self._stderr_redirector

    def _append_stream_text(self, text: str) -> None:
        """ターミナル標準出力をUIログ欄へリアルタイム反映"""
        try:
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(text)
            self.log_text.setTextCursor(cursor)
            self.log_text.ensureCursorVisible()
        except Exception:
            pass

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # 1. ヘッダー（現在年・週・進行ボタン・初期化ボタン）
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 8px;")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(16, 12, 16, 12)

        info_layout = QVBoxLayout()
        self.year_week_lbl = QLabel("シミュレーション 1年目 / 1月1週 (第1週)")
        self.year_week_lbl.setStyleSheet("font-size: 22px; font-weight: 800; color: #38bdf8;")
        self.sub_info_lbl = QLabel("年間48週体系 / 全4場・良馬場固定")
        self.sub_info_lbl.setObjectName("subText")
        info_layout.addWidget(self.year_week_lbl)
        info_layout.addWidget(self.sub_info_lbl)
        header_layout.addLayout(info_layout)

        header_layout.addStretch()

        # 進行ボタン群
        self.btn_1w = QPushButton("▶ 1週進める")
        self.btn_1w.setObjectName("primaryBtn")
        self.btn_1w.clicked.connect(lambda: self._start_simulation("week"))
        header_layout.addWidget(self.btn_1w)

        self.btn_1m = QPushButton("▶▶ 1ヶ月進める (4週)")
        self.btn_1m.clicked.connect(lambda: self._start_simulation("month"))
        header_layout.addWidget(self.btn_1m)

        self.btn_1y = QPushButton("⏩ 1年進める (年度更新)")
        self.btn_1y.setObjectName("goldBtn")
        self.btn_1y.clicked.connect(lambda: self._start_simulation("year"))
        header_layout.addWidget(self.btn_1y)

        # データ初期化・再生成ボタン
        self.btn_reset = QPushButton("🔄 データ初期化・再生成")
        self.btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #3b1820;
                color: #f87171;
                border: 1px solid #7f1d1d;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #4c1d28;
                border: 1px solid #ef4444;
                color: #ffffff;
            }
        """)
        self.btn_reset.clicked.connect(self._confirm_and_reset_data)
        header_layout.addWidget(self.btn_reset)

        main_layout.addWidget(header_frame)

        # プログレスバー
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(14)
        main_layout.addWidget(self.progress_bar)

        # 2. 統計カードグリッド (2行 × 4列)
        cards_layout = QGridLayout()
        cards_layout.setSpacing(12)

        self.card_active = StatCard("現役競走馬")
        self.card_foals = StatCard("当歳・1歳馬")
        self.card_sires = StatCard("繋養種牡馬")
        self.card_dams = StatCard("繁殖牝馬")
        self.card_owners = StatCard("登録馬主")
        self.card_breeders = StatCard("生産牧場")
        self.card_trainers = StatCard("開業厩舎 (美浦/栗東)")
        self.card_jockeys = StatCard("現役騎手 (定員90名)")

        cards_layout.addWidget(self.card_active, 0, 0)
        cards_layout.addWidget(self.card_foals, 0, 1)
        cards_layout.addWidget(self.card_sires, 0, 2)
        cards_layout.addWidget(self.card_dams, 0, 3)
        cards_layout.addWidget(self.card_owners, 1, 0)
        cards_layout.addWidget(self.card_breeders, 1, 1)
        cards_layout.addWidget(self.card_trainers, 1, 2)
        cards_layout.addWidget(self.card_jockeys, 1, 3)

        main_layout.addLayout(cards_layout)

        # 3. 進行ログエリア
        log_group = QGroupBox("シミュレーション実行ログ")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(12, 12, 12, 12)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #0b0f17; border: 1px solid #1e293b; color: #94a3b8; font-family: monospace;")
        log_layout.addWidget(self.log_text)

        main_layout.addWidget(log_group)

    def refresh_stats(self) -> None:
        """データベースから最新指標を取得してカードを更新"""
        try:
            with self.db.session() as conn:
                cur_year, cur_week = get_current_sim_status(conn)
                cur_m = ((cur_week - 1) // 4) + 1
                cur_wm = ((cur_week - 1) % 4) + 1
                self.year_week_lbl.setText(f"シミュレーション {cur_year}年目 / {cur_m}月{cur_wm}週 (第{cur_week}週)")
                active_c = conn.execute("SELECT COUNT(*) FROM horses WHERE is_active = 1").fetchone()[0]
                foal_c = conn.execute("SELECT COUNT(*) FROM horses WHERE age < 2 AND is_active = 0 AND is_sire = 0 AND is_dam = 0").fetchone()[0]
                sire_c = conn.execute("SELECT COUNT(*) FROM sires WHERE is_active = 1").fetchone()[0]
                dam_c = conn.execute("SELECT COUNT(*) FROM dams WHERE is_active = 1").fetchone()[0]
                owner_c = conn.execute("SELECT COUNT(*) FROM owners").fetchone()[0]
                breeder_c = conn.execute("SELECT COUNT(*) FROM breeders").fetchone()[0]
                trainer_c = conn.execute("SELECT COUNT(*) FROM trainers").fetchone()[0]
                jockey_c = conn.execute("SELECT COUNT(*) FROM jockeys WHERE is_active = 1").fetchone()[0]

                self.card_active.set_value(f"{active_c:,} 頭")
                self.card_foals.set_value(f"{foal_c:,} 頭")
                self.card_sires.set_value(f"{sire_c} 頭")
                self.card_dams.set_value(f"{dam_c} 頭")
                self.card_owners.set_value(f"{owner_c} 人")
                self.card_breeders.set_value(f"{breeder_c} 場")
                self.card_trainers.set_value(f"{trainer_c} 厩舎")
                self.card_jockeys.set_value(f"{jockey_c} 名")
        except Exception as e:
            self.log_text.append(f"[集計更新エラー] {e}\n")

    def _start_simulation(self, mode: str) -> None:
        """非同期シミュレーション開始"""
        self._set_buttons_enabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.worker = SimulationWorker(self.db, mode=mode)
        self.worker.step_progress.connect(self._on_progress)
        self.worker.log_emitted.connect(self._on_log)
        self.worker.finished_simulation.connect(self._on_finished)
        self.worker.start()

    def _confirm_and_reset_data(self) -> None:
        """データ初期化・再生成の確認ダイアログ"""
        reply = QMessageBox.question(
            self,
            "データ初期化・再生成の確認",
            "データベースを完全に初期化し、初期競走馬・種牡馬・騎手・調教師データを再生成しますか？\n\n"
            "※現在のシミュレーション進行状態やレース結果はすべてリセットされます。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._start_reset()

    def _start_reset(self) -> None:
        """バックグラウンドでデータ完全初期化を実行"""
        self._set_buttons_enabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # インジケーター表示
        self.sub_info_lbl.setText("🔄 データベース初期化・初期個体群を再生成中...")
        self.log_text.clear()

        self.reset_worker = DataResetWorker(self.db)
        self.reset_worker.finished_reset.connect(self._on_reset_finished)
        self.reset_worker.start()

    def _on_reset_finished(self, success: bool, msg: str) -> None:
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 1)
        self._set_buttons_enabled(True)
        self.sub_info_lbl.setText("年間48週体系 / 全4場・良馬場固定")
        self.refresh_stats()
        self.simulation_completed.emit()
        if success:
            QMessageBox.information(self, "完了", msg)
        else:
            QMessageBox.critical(self, "エラー", msg)

    def _on_progress(self, cur: int, total: int, msg: str) -> None:
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(cur)
        self.sub_info_lbl.setText(msg)

    def _on_log(self, text: str) -> None:
        self.log_text.append(text)

    def _on_finished(self, success: bool, msg: str) -> None:
        self.progress_bar.setVisible(False)
        self._set_buttons_enabled(True)
        self.sub_info_lbl.setText("年間48週体系 / 全4場・良馬場固定")
        self.log_text.append(msg)
        self.refresh_stats()
        self.simulation_completed.emit()

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self.btn_1w.setEnabled(enabled)
        self.btn_1m.setEnabled(enabled)
        self.btn_1y.setEnabled(enabled)
        self.btn_reset.setEnabled(enabled)
