"""
シミュレーション状況管理ビュー (SimulationStatusView)
- 現在のシミュレーション年・週表示
- 1週進行 / 1ヶ月進行 / 1年進行（QThread非同期ワーカー）
- 主要統計サマリーカード
- リアルタイム実行ログ
- データ完全初期化
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


def get_current_sim_status(conn) -> tuple[int, int]:
    """DB内の消化済みレースから現在のシミュレーション年・進行対象週を取得（1年目は第21週から開始）"""
    row = conn.execute("""
        SELECT rc.year, rc.week
        FROM results r
        JOIN races rc ON r.race_id = rc.race_id
        ORDER BY rc.year DESC, rc.week DESC
        LIMIT 1
    """).fetchone()

    if not row:
        return 1, 21

    last_year = row["year"]
    last_week = row["week"]

    if last_week >= 48:
        return last_year + 1, 1
    else:
        return last_year, last_week + 1


def advance_one_week_core(
    cal: CalendarController,
    life: LifecycleEngine,
    db: Database,
    log_callback=None,
) -> tuple[int, int, dict]:
    """
    シミュレーションを確実に1週進めるコア関数。
    最新消化週が48週以上の場合は、まず年度更新（advance_year: 全頭加齢・引退昇格・新馬入厩・世代交代）を行い、
    その後に次年度第1週（1月第1週）のレースを実行する。
    それ以外の場合は次週のレースを実行する。
    戻り値: (実行した年, 実行した週, レース実行結果辞書)
    """
    with db.session() as conn:
        row = conn.execute("""
            SELECT rc.year, rc.week
            FROM results r
            JOIN races rc ON r.race_id = rc.race_id
            ORDER BY rc.year DESC, rc.week DESC
            LIMIT 1
        """).fetchone()

        if not row:
            latest_y, latest_w = 1, 20  # まだ1件もなければ1年目21週へ
        else:
            latest_y, latest_w = row["year"], row["week"]

    if latest_w >= 48:
        if log_callback:
            log_callback(f"★ 第{latest_y}年度末の年度更新処理（全頭加齢・引退昇格・新馬入厩・世代交代）を実行します...")
        life.advance_year(current_year=latest_y)
        if log_callback:
            log_callback(f"★ 第{latest_y + 1}年度が開幕しました！")
        target_y = latest_y + 1
        target_w = 1
    else:
        target_y = latest_y
        target_w = latest_w + 1

    res = cal.run_week(target_y, target_w)
    return target_y, target_w, res


class SimulationWorker(QThread):
    """バックグラウンドでシミュレーション進行を実行するワーカー"""

    step_progress = pyqtSignal(int, int, str)
    log_emitted = pyqtSignal(str)
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

            if self.mode == "week":
                self.step_progress.emit(0, 1, "1週進行中...")
                y, w, res = advance_one_week_core(
                    cal, life, self.db, log_callback=lambda msg: self.log_emitted.emit(msg)
                )
                self.log_emitted.emit(
                    f"{y}年 第{w}週 レース完了 (開催: {res.get('races_run', 0)}レース, 出走: {res.get('starters_count', 0)}頭)"
                )
                self.step_progress.emit(1, 1, "1週進行完了")

            elif self.mode == "month":
                # 1ヶ月 = 4週分進行
                total_steps = 4
                for step_idx in range(total_steps):
                    self.step_progress.emit(step_idx, total_steps, f"1ヶ月進行中 ({step_idx + 1}/{total_steps}週)...")
                    y, w, res = advance_one_week_core(
                        cal, life, self.db, log_callback=lambda msg: self.log_emitted.emit(msg)
                    )
                    self.log_emitted.emit(
                        f"{y}年 第{w}週 完了 (開催: {res.get('races_run', 0)}レース, 出走: {res.get('starters_count', 0)}頭)"
                    )
                self.step_progress.emit(total_steps, total_steps, "1ヶ月進行完了")

            elif self.mode == "year":
                # 1年間 = 48週分進行
                total_steps = 48
                for step_idx in range(total_steps):
                    self.step_progress.emit(step_idx, total_steps, f"1年間進行中 ({step_idx + 1}/{total_steps}週)...")
                    y, w, res = advance_one_week_core(
                        cal, life, self.db, log_callback=lambda msg: self.log_emitted.emit(msg)
                    )
                    if w % 4 == 0 or w == 1:
                        self.log_emitted.emit(
                            f"{y}年 第{w}週 完了 (開催: {res.get('races_run', 0)}レース, 出走: {res.get('starters_count', 0)}頭)"
                        )
                self.step_progress.emit(total_steps, total_steps, "1年間シミュレーション完了")

            self.finished_simulation.emit(True, f"シミュレーション進行（{self.mode}）が完了しました。")
        except Exception as e:
            self.finished_simulation.emit(False, f"エラーが発生しました: {e}")


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


class SimulationStatusView(QWidget):
    """シミュレーション状況タブウィジェット"""

    simulation_completed = pyqtSignal()

    def __init__(self, db: Optional[Database] = None):
        super().__init__()
        self.db = db or get_db()
        self.worker: Optional[SimulationWorker] = None
        self.reset_worker: Optional[DataResetWorker] = None

        self._init_ui()
        self._init_stdout_redirect()
        self.refresh_view()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. ヘッダー (現在の進行年・週)
        header_frame = QFrame()
        header_frame.setObjectName("CardFrame")
        header_layout = QHBoxLayout(header_frame)

        self.label_year_week = QLabel("📅 シミュレーション状況: 計算中...")
        self.label_year_week.setStyleSheet("font-size: 20px; font-weight: bold; color: #4dabf7;")
        header_layout.addWidget(self.label_year_week)
        header_layout.addStretch()

        self.btn_reset_data = QPushButton("⚠️ データベース完全初期化")
        self.btn_reset_data.setStyleSheet("""
            QPushButton {
                background-color: #721c24;
                color: #f8d7da;
                border: 1px solid #f5c6cb;
                padding: 6px 14px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
                color: #ffffff;
            }
        """)
        self.btn_reset_data.clicked.connect(self._on_btn_reset_clicked)
        header_layout.addWidget(self.btn_reset_data)

        main_layout.addWidget(header_frame)

        # 2. 進行コントロール & プログレスバー
        control_group = QGroupBox("⏩ シミュレーション進行コントロール")
        control_layout = QVBoxLayout(control_group)

        btn_layout = QHBoxLayout()
        self.btn_advance_week = QPushButton("▶ 1週進める")
        self.btn_advance_week.setStyleSheet("background-color: #1971c2; font-size: 14px; font-weight: bold; padding: 8px;")
        self.btn_advance_week.clicked.connect(lambda: self._start_simulation("week"))

        self.btn_advance_month = QPushButton("⏩ 1ヶ月(4週)進める")
        self.btn_advance_month.setStyleSheet("background-color: #0c8599; font-size: 14px; font-weight: bold; padding: 8px;")
        self.btn_advance_month.clicked.connect(lambda: self._start_simulation("month"))

        self.btn_advance_year = QPushButton("⏭ 1年間進める")
        self.btn_advance_year.setStyleSheet("background-color: #2f9e44; font-size: 14px; font-weight: bold; padding: 8px;")
        self.btn_advance_year.clicked.connect(lambda: self._start_simulation("year"))

        btn_layout.addWidget(self.btn_advance_week)
        btn_layout.addWidget(self.btn_advance_month)
        btn_layout.addWidget(self.btn_advance_year)
        control_layout.addLayout(btn_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("待機中: %p%")
        control_layout.addWidget(self.progress_bar)

        self.lbl_progress_status = QLabel("進行ステータス: 待機中")
        self.lbl_progress_status.setStyleSheet("color: #adb5bd; font-size: 12px;")
        control_layout.addWidget(self.lbl_progress_status)

        main_layout.addWidget(control_group)

        # 3. 主要サマリーカード
        stats_group = QGroupBox("📊 シミュレーション全体統計")
        stats_layout = QGridLayout(stats_group)

        self.card_active_horses = self._create_card("現役競走馬", "0 頭", "#339af0")
        self.card_sires = self._create_card("繋養種牡馬", "0 頭", "#51cf66")
        self.card_dams = self._create_card("繋養繁殖牝馬", "0 頭", "#ff922b")
        self.card_trainers = self._create_card("調教師 (厩舎)", "0 厩舎", "#cc5de8")
        self.card_jockeys = self._create_card("騎手 (現役)", "0 名", "#20c997")
        self.card_total_races = self._create_card("消化済みレース", "0 レース", "#f06595")

        stats_layout.addWidget(self.card_active_horses, 0, 0)
        stats_layout.addWidget(self.card_sires, 0, 1)
        stats_layout.addWidget(self.card_dams, 0, 2)
        stats_layout.addWidget(self.card_trainers, 1, 0)
        stats_layout.addWidget(self.card_jockeys, 1, 1)
        stats_layout.addWidget(self.card_total_races, 1, 2)

        main_layout.addWidget(stats_group)

        # 4. 実行ログ
        log_group = QGroupBox("📝 リアルタイム実行ログ")
        log_layout = QVBoxLayout(log_group)
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setStyleSheet("background-color: #141517; font-family: monospace; font-size: 12px; color: #ced4da;")
        log_layout.addWidget(self.text_log)

        main_layout.addWidget(log_group, stretch=1)

    def _create_card(self, title: str, initial_value: str, color: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: #25262b;
                border-left: 4px solid {color};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        layout = QVBoxLayout(frame)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #868e96; font-size: 12px;")
        lbl_val = QLabel(initial_value)
        lbl_val.setObjectName("CardValue")
        lbl_val.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: bold;")
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_val)
        return frame

    def _init_stdout_redirect(self) -> None:
        self.redirector = OutputRedirector(sys.stdout)
        self.redirector.text_written.connect(self._append_log)
        sys.stdout = self.redirector

    def _append_log(self, text: str) -> None:
        self.text_log.moveCursor(QTextCursor.MoveOperation.End)
        self.text_log.insertPlainText(text)
        self.text_log.moveCursor(QTextCursor.MoveOperation.End)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self.btn_advance_week.setEnabled(enabled)
        self.btn_advance_month.setEnabled(enabled)
        self.btn_advance_year.setEnabled(enabled)
        self.btn_reset_data.setEnabled(enabled)

    def _start_simulation(self, mode: str) -> None:
        self._set_buttons_enabled(False)
        self.progress_bar.setValue(0)
        self.lbl_progress_status.setText(f"ステータス: {mode} 進行処理を開始中...")

        self.worker = SimulationWorker(self.db, mode=mode)
        self.worker.step_progress.connect(self._on_worker_progress)
        self.worker.log_emitted.connect(self._append_log_line)
        self.worker.finished_simulation.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_progress(self, current: int, total: int, msg: str) -> None:
        pct = int((current / max(1, total)) * 100)
        self.progress_bar.setValue(pct)
        self.lbl_progress_status.setText(f"ステータス: {msg}")

    def _append_log_line(self, msg: str) -> None:
        self._append_log(msg + "\n")

    def _on_worker_finished(self, success: bool, message: str) -> None:
        self._set_buttons_enabled(True)
        self.progress_bar.setValue(100 if success else 0)
        self.lbl_progress_status.setText(f"ステータス: {message}")
        self.refresh_view()
        self.simulation_completed.emit()

    def _on_btn_reset_clicked(self) -> None:
        reply = QMessageBox.question(
            self,
            "データ完全初期化の確認",
            "データベースを完全に削除し、初期状態（初期種牡馬・繁殖牝馬・競走馬・厩舎・騎手）に再生成します。\n現在の進行履歴・レース結果はすべてリセットされます。実行しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._set_buttons_enabled(False)
            self.progress_bar.setValue(0)
            self.lbl_progress_status.setText("ステータス: データベース初期化処理を実行中...")
            self.reset_worker = DataResetWorker(self.db)
            self.reset_worker.finished_reset.connect(self._on_reset_finished)
            self.reset_worker.start()

    def _on_reset_finished(self, success: bool, msg: str) -> None:
        self._set_buttons_enabled(True)
        self.progress_bar.setValue(100 if success else 0)
        self.lbl_progress_status.setText(f"ステータス: {msg}")
        self.refresh_view()
        self.simulation_completed.emit()
        if success:
            QMessageBox.information(self, "完了", msg)
        else:
            QMessageBox.critical(self, "エラー", msg)

    def refresh_view(self) -> None:
        """統計と現在週表示をDB最新情報で更新"""
        with self.db.session() as conn:
            cur_year, cur_week = get_current_sim_status(conn)
            cur_month = (cur_week - 1) // 4 + 1
            month_week = (cur_week - 1) % 4 + 1
            self.label_year_week.setText(
                f"📅 シミュレーション状況: 第 {cur_year} 年 {cur_month} 月 第 {month_week} 週 (通算 第{cur_week}週)"
            )

            cnt_active = conn.execute("SELECT COUNT(*) FROM horses WHERE is_active = 1").fetchone()[0]
            cnt_sires = conn.execute("SELECT COUNT(*) FROM sires WHERE is_active = 1").fetchone()[0]
            cnt_dams = conn.execute("SELECT COUNT(*) FROM dams WHERE is_active = 1").fetchone()[0]
            cnt_trainers = conn.execute("SELECT COUNT(*) FROM trainers").fetchone()[0]
            cnt_jockeys = conn.execute("SELECT COUNT(*) FROM jockeys WHERE is_active = 1").fetchone()[0]
            cnt_races = conn.execute("SELECT COUNT(DISTINCT race_id) FROM results").fetchone()[0]

        self._update_card(self.card_active_horses, f"{cnt_active:,} 頭")
        self._update_card(self.card_sires, f"{cnt_sires:,} 頭")
        self._update_card(self.card_dams, f"{cnt_dams:,} 頭")
        self._update_card(self.card_trainers, f"{cnt_trainers:,} 厩舎")
        self._update_card(self.card_jockeys, f"{cnt_jockeys:,} 名")
        self._update_card(self.card_total_races, f"{cnt_races:,} レース")

    def _update_card(self, frame: QFrame, val_str: str) -> None:
        lbl = frame.findChild(QLabel, "CardValue")
        if lbl:
            lbl.setText(val_str)
