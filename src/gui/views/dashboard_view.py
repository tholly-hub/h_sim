"""
新ダッシュボードビュー (DashboardView)
- 3行構成:
  1行目: 年・月・週の表示 & 「⏩ 次の週に進む」ボタン
  2行目: 今週のレース一覧テーブル
  3行目: 出走馬表（オッズ、着順） & 「🎬 レースを見る」「🏁 レース結果」ボタン
- 自動実行仕様:
  - 最初の時点でその週に開催されるレースを全件自動実行
  - 「次の週に進む」ボタン押下時に次週へ進み、全レースを自動実行して即時表示
  - 出走馬表の馬名クリックで「競走馬詳細（血統表・成績）」ダイアログ（別ウィンドウ）を表示
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.lifecycle import LifecycleEngine
from src.db.database import Database, get_db
from src.gui.views.horse_detail_dialog import HorseDetailDialog
from src.gui.views.race_dialogs import RaceResultDialog, RaceViewDialog
from src.models.horse import Horse
from src.race.calendar import CalendarController


def format_finish_time(seconds: float) -> str:
    """走破タイムを分:秒.厘形式に変換"""
    if seconds <= 0:
        return "--:--.-"
    m = int(seconds // 60)
    s = seconds - (m * 60)
    return f"{m}:{s:04.1f}"


def get_latest_completed_week(conn) -> tuple[int, int]:
    """DB内の消化済み最新レースの年・週を取得（まだ1件もなければ 1, 21）"""
    row = conn.execute("""
        SELECT rc.year, rc.week
        FROM results r
        JOIN races rc ON r.race_id = rc.race_id
        ORDER BY rc.year DESC, rc.week DESC
        LIMIT 1
    """).fetchone()
    if not row:
        return 1, 21
    return row["year"], row["week"]


class DashboardView(QWidget):
    """3行構成ダッシュボード画面"""

    simulation_completed = pyqtSignal()

    def __init__(self, db: Optional[Database] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db or get_db()
        self.cal = CalendarController(self.db)
        self.life = LifecycleEngine(self.db)
        self.current_selected_race_id: Optional[int] = None
        self.viewing_year = 1
        self.viewing_week = 21

        self._init_ui()
        # 初回起動時に未実行なら今週のレースを自動実行して表示
        self._ensure_initial_week_run()
        self.refresh_dashboard()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(10)

        # ==========================================
        # 1行目: 年・月・週の表示 & 「次の週に進む」ボタン
        # ==========================================
        self.row1_frame = QFrame()
        self.row1_frame.setObjectName("CardFrame")
        self.row1_frame.setStyleSheet("""
            QFrame#CardFrame {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 4px;
            }
        """)
        row1_layout = QHBoxLayout(self.row1_frame)
        row1_layout.setContentsMargins(16, 8, 16, 8)

        self.lbl_current_time = QLabel("📅 第 1 年 6 月 第 1 週 (第21週)")
        self.lbl_current_time.setStyleSheet("font-size: 20px; font-weight: bold; color: #38bdf8;")
        row1_layout.addWidget(self.lbl_current_time)

        row1_layout.addStretch()

        lbl_select = QLabel("週の切替:")
        lbl_select.setStyleSheet("color: #94a3b8; font-size: 13px;")
        row1_layout.addWidget(lbl_select)

        self.combo_week = QComboBox()
        self.combo_week.setMinimumWidth(180)
        self.combo_week.currentIndexChanged.connect(self._on_week_selected)
        row1_layout.addWidget(self.combo_week)

        # 「次の週に進む」ボタン
        self.btn_next_week = QPushButton("⏩ 次の週に進む")
        self.btn_next_week.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #475569;
                color: #94a3b8;
            }
        """)
        self.btn_next_week.clicked.connect(self._advance_to_next_week)
        row1_layout.addWidget(self.btn_next_week)

        main_layout.addWidget(self.row1_frame)

        # ==========================================
        # 上下スプリッター（2行目と3行目を配置）
        # ==========================================
        splitter = QSplitter(Qt.Orientation.Vertical)

        # ==========================================
        # 2行目: 今週のレース一覧
        # ==========================================
        self.row2_group = QGroupBox("🏇 2行目: 今週の開催レース一覧 (レースをクリックすると下の出走馬表が切り替わります)")
        self.row2_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 13px; color: #f8fafc; }")
        row2_layout = QVBoxLayout(self.row2_group)
        row2_layout.setContentsMargins(8, 8, 8, 8)

        self.table_races = QTableWidget()
        self.table_races.setColumnCount(6)
        self.table_races.setHorizontalHeaderLabels([
            "競馬場", "レース名", "グレード", "馬場/距離", "頭数", "発走状態"
        ])
        self.table_races.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_races.setAlternatingRowColors(True)
        self.table_races.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_races.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_races.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table_races.cellClicked.connect(self._on_race_cell_clicked)
        self.table_races.itemSelectionChanged.connect(self._on_race_selection_changed)
        row2_layout.addWidget(self.table_races)

        splitter.addWidget(self.row2_group)

        # ==========================================
        # 3行目: 出走馬表 & 「レースを見る」「レース結果」ボタン
        # ==========================================
        self.row3_group = QGroupBox("📋 3行目: 出走馬表 & オッズ (レース結果ボタンを押すまで着順は伏せられます)")
        self.row3_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 13px; color: #f8fafc; }")
        row3_layout = QVBoxLayout(self.row3_group)
        row3_layout.setContentsMargins(8, 8, 8, 8)

        # 3行目の操作バー（レース名表示 & アクションボタン）
        action_bar = QFrame()
        action_bar.setStyleSheet("background-color: #1e293b; border-radius: 6px; padding: 4px 10px;")
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(8, 4, 8, 4)

        self.lbl_selected_race_title = QLabel("レースを選択してください")
        self.lbl_selected_race_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #fbbf24;")
        action_layout.addWidget(self.lbl_selected_race_title)

        action_layout.addStretch()

        self.btn_view_race = QPushButton("🎬 レースを見る (2D)")
        self.btn_view_race.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:disabled {
                background-color: #475569;
                color: #94a3b8;
            }
        """)
        self.btn_view_race.clicked.connect(self._open_race_view)
        action_layout.addWidget(self.btn_view_race)

        self.btn_view_result = QPushButton("🏁 レース結果")
        self.btn_view_result.setStyleSheet("""
            QPushButton {
                background-color: #f59e0b;
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #d97706;
            }
            QPushButton:disabled {
                background-color: #475569;
                color: #94a3b8;
            }
        """)
        self.btn_view_result.clicked.connect(self._open_race_result)
        action_layout.addWidget(self.btn_view_result)

        row3_layout.addWidget(action_bar)

        # 出走馬表テーブル（着順や走破タイムは表示しない純粋な出馬表）
        self.table_entry = QTableWidget()
        self.table_entry.setColumnCount(8)
        self.table_entry.setHorizontalHeaderLabels([
            "枠番", "馬番", "馬名 (クリックで詳細)", "性齢", "適性", "騎手", "厩舎", "人気/オッズ"
        ])
        header = self.table_entry.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_entry.setColumnWidth(0, 50)   # 枠番
        self.table_entry.setColumnWidth(1, 50)   # 馬番
        self.table_entry.setColumnWidth(2, 230)  # 馬名 (全文字最後まで確実に表示)
        self.table_entry.setColumnWidth(3, 60)   # 性齢
        self.table_entry.setColumnWidth(4, 75)   # 適性
        self.table_entry.setColumnWidth(5, 95)   # 騎手
        self.table_entry.setColumnWidth(6, 95)   # 厩舎
        self.table_entry.setColumnWidth(7, 130)  # 人気/オッズ
        header.setStretchLastSection(True)
        self.table_entry.setAlternatingRowColors(True)
        self.table_entry.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_entry.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_entry.cellClicked.connect(self._on_horse_cell_clicked)
        row3_layout.addWidget(self.table_entry)

        splitter.addWidget(self.row3_group)

        # 2行目と3行目の高さバランス設定 (4:6)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)

        main_layout.addWidget(splitter)

    def _ensure_initial_week_run(self) -> None:
        """初期状態で未実行のレースがあれば第21週を自動実行して確定させる"""
        with self.db.session() as conn:
            cnt = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
        if cnt == 0:
            # 1年目第21週のレースを即座に実行
            self.cal.run_week(1, 21)

    def refresh_dashboard(self) -> None:
        """DBの最新消化週を取得し、ダッシュボードを更新"""
        self._ensure_initial_week_run()
        with self.db.session() as conn:
            latest_y, latest_w = get_latest_completed_week(conn)

        self.viewing_year = latest_y
        self.viewing_week = latest_w

        # 週セレクタの項目を構築
        self._populate_week_selector(latest_y, latest_w)
        # その週のデータをロード
        self._load_week_data(self.viewing_year, self.viewing_week)

    def _populate_week_selector(self, current_year: int, current_week: int) -> None:
        """消化済みの週リストをコンボボックスに追加"""
        self.combo_week.blockSignals(True)
        self.combo_week.clear()

        # 過去すべての消化済み (year, week) を取得
        with self.db.session() as conn:
            rows = conn.execute("""
                SELECT DISTINCT rc.year, rc.week
                FROM results r
                JOIN races rc ON r.race_id = rc.race_id
                ORDER BY rc.year ASC, rc.week ASC
            """).fetchall()

        if not rows:
            self.combo_week.addItem(f"{current_year}年 第{current_week}週", (current_year, current_week))
        else:
            for r in rows:
                y = r["year"]
                w = r["week"]
                m = ((w - 1) // 4) + 1
                mw = ((w - 1) % 4) + 1
                label = f"{y}年 {m}月 第{mw}週 (第{w}週)"
                self.combo_week.addItem(label, (y, w))

        # 最新週を選択状態に
        self.combo_week.setCurrentIndex(self.combo_week.count() - 1)
        self.combo_week.blockSignals(False)

    def _on_week_selected(self, idx: int) -> None:
        """ユーザーが週を切り替えた時の処理"""
        data = self.combo_week.currentData()
        if data:
            y, w = data
            self.viewing_year = y
            self.viewing_week = w
            self._load_week_data(y, w)

    def _load_week_data(self, year: int, week: int) -> None:
        """指定した年・週のレース一覧と出走馬表をロード"""
        cur_month = ((week - 1) // 4) + 1
        m_week = ((week - 1) % 4) + 1
        self.lbl_current_time.setText(
            f"📅 第 {year} 年 {cur_month} 月 第 {m_week} 週 (通算 第{week}週)"
        )

        races = self.cal.get_races_for_week(year, week)

        with self.db.session() as conn:
            # 完了済みレースIDを取得
            done_ids: set[int] = set()
            if races:
                d_rows = conn.execute("""
                    SELECT DISTINCT res.race_id
                    FROM results res
                    WHERE res.race_id IN (""" +
                    ",".join(str(r.race_id) for r in races) + """)
                """).fetchall()
                done_ids = {dr["race_id"] for dr in d_rows}

        self.table_races.setRowCount(len(races))
        for row_idx, r in enumerate(races):
            track_name = r.track_id
            race_name = r.name
            grade_name = r.grade.value
            surf_jp = "芝" if r.surface.value == "turf" else "ダート"
            surf_dist = f"{surf_jp} {r.distance}m"
            gate_str = f"{r.full_gate}頭"
            is_done = (r.race_id in done_ids)
            status_str = "🏁 発走確定" if is_done else "⏳ 未発走"

            items = [
                QTableWidgetItem(track_name),
                QTableWidgetItem(race_name),
                QTableWidgetItem(grade_name),
                QTableWidgetItem(surf_dist),
                QTableWidgetItem(gate_str),
                QTableWidgetItem(status_str),
            ]

            # race_idを保持
            items[1].setData(Qt.ItemDataRole.UserRole, r.race_id)

            for col_idx, item in enumerate(items):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col_idx == 2 and grade_name in ("G1", "G2", "G3"):
                    item.setForeground(Qt.GlobalColor.yellow)
                if col_idx == 5:
                    item.setForeground(Qt.GlobalColor.green if is_done else Qt.GlobalColor.cyan)
                self.table_races.setItem(row_idx, col_idx, item)

        if races:
            self.table_races.selectRow(0)
            self._on_race_selected_by_row(0)
        else:
            self.table_entry.setRowCount(0)
            self.lbl_selected_race_title.setText("今週は開催レースがありません")
            self.btn_view_race.setEnabled(False)
            self.btn_view_result.setEnabled(False)
            self.current_selected_race_id = None

    def _on_race_cell_clicked(self, row: int, col: int) -> None:
        self._on_race_selected_by_row(row)

    def _on_race_selection_changed(self) -> None:
        row = self.table_races.currentRow()
        if row >= 0:
            self._on_race_selected_by_row(row)

    def _on_race_selected_by_row(self, row: int) -> None:
        item = self.table_races.item(row, 1)
        if not item:
            return
        race_id = item.data(Qt.ItemDataRole.UserRole)
        if race_id:
            self.current_selected_race_id = race_id
            self._load_race_entry(race_id)

    def _load_race_entry(self, race_id: int) -> None:
        """選択レースの出走馬表・オッズをロード（着順・タイムは完全非表示）"""
        with self.db.session() as conn:
            rc = conn.execute("SELECT * FROM races WHERE race_id = ?", (race_id,)).fetchone()
            if not rc:
                return

            surf_jp = "芝" if rc["surface"] == "turf" else "ダート"
            self.lbl_selected_race_title.setText(
                f"{rc['name']} ({rc['grade']}) - {rc['track_id']} {surf_jp} {rc['distance']}m [{rc['full_gate']}頭立]"
            )

            # 馬番順 (gate_number ASC) で取得（着順ではソートしない！）
            results = conn.execute("""
                SELECT res.*, h.name as horse_name, h.sex, h.age, h.mstn_type,
                       j.name as jockey_name, t.name as trainer_name
                FROM results res
                JOIN horses h ON res.horse_id = h.horse_id
                LEFT JOIN jockeys j ON res.jockey_id = j.jockey_id
                LEFT JOIN trainers t ON h.trainer_id = t.trainer_id
                WHERE res.race_id = ?
                ORDER BY res.gate_number ASC
            """, (race_id,)).fetchall()

        # もしまだ未実行のレースだった場合は自動実行して結果（出馬表）を即時生成
        if not results:
            with self.db.session() as conn:
                rc_info = conn.execute("SELECT year, week FROM races WHERE race_id = ?", (race_id,)).fetchone()
            if rc_info:
                self.cal.run_week(rc_info["year"], rc_info["week"])
                with self.db.session() as conn:
                    results = conn.execute("""
                        SELECT res.*, h.name as horse_name, h.sex, h.age, h.mstn_type,
                               j.name as jockey_name, t.name as trainer_name
                        FROM results res
                        JOIN horses h ON res.horse_id = h.horse_id
                        LEFT JOIN jockeys j ON res.jockey_id = j.jockey_id
                        LEFT JOIN trainers t ON h.trainer_id = t.trainer_id
                        WHERE res.race_id = ?
                        ORDER BY res.gate_number ASC
                    """, (race_id,)).fetchall()

        sex_map = {"colt": "牡", "filly": "牝", "horse": "牡", "mare": "牝", "gelding": "セ"}

        if results:
            from src.gui.widgets.track_canvas import JRA_BRACKET_COLORS
            from src.race.engine import get_jra_bracket
            from PyQt6.QtGui import QColor

            self.btn_view_race.setEnabled(True)
            self.btn_view_result.setEnabled(True)
            self.table_entry.setRowCount(len(results))

            total_h = len(results)

            # オッズに基づく人気順の算出
            odds_list = []
            for r in results:
                val = float(r["odds"]) if ("odds" in r.keys() and r["odds"] and float(r["odds"]) > 0) else 999.9
                odds_list.append((val, r["horse_id"]))
            sorted_by_odds = sorted(odds_list, key=lambda x: x[0])
            pop_map = {hid: pop for pop, (_, hid) in enumerate(sorted_by_odds, start=1)}

            for idx, r in enumerate(results):
                g_num = int(r["gate_number"])
                bracket_num = get_jra_bracket(g_num, total_h)
                bg_col, fg_col, _, bracket_name = JRA_BRACKET_COLORS.get(bracket_num, ("#ffffff", "#000000", "#999999", f"{bracket_num}枠"))

                h_name = r["horse_name"]
                sex_age = f"{sex_map.get(r['sex'], '')}{r['age']}"
                mstn = r["mstn_type"]
                j_name = r["jockey_name"] or "未定"
                t_name = r["trainer_name"] or "未定"
                
                # オッズ・人気 (例: 2.4倍 (1人気))
                pop = pop_map.get(r["horse_id"], idx + 1)
                odds_str = f"{r['odds']:.1f}倍 ({pop}人気)" if r["odds"] else f"{pop}人気"

                # 枠番アイテム
                bracket_item = QTableWidgetItem(bracket_name)
                bracket_item.setBackground(QColor(bg_col))
                bracket_item.setForeground(QColor(fg_col))

                # 馬番アイテム
                gate_item = QTableWidgetItem(f"{g_num}番")

                # 馬名アイテム
                name_item = QTableWidgetItem(h_name)
                name_item.setData(Qt.ItemDataRole.UserRole, r["horse_id"])
                name_item.setForeground(Qt.GlobalColor.cyan)

                items = [
                    bracket_item,
                    gate_item,
                    name_item,
                    QTableWidgetItem(sex_age),
                    QTableWidgetItem(mstn),
                    QTableWidgetItem(j_name),
                    QTableWidgetItem(t_name),
                    QTableWidgetItem(odds_str),
                ]

                for c, itm in enumerate(items):
                    itm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table_entry.setItem(idx, c, itm)
        else:
            self.btn_view_race.setEnabled(False)
            self.btn_view_result.setEnabled(False)
            self.table_entry.setRowCount(0)

    def _on_horse_cell_clicked(self, row: int, col: int) -> None:
        """出走馬表のセル（特に馬名）クリックで競走馬詳細ダイアログを開く（今走結果は除外）"""
        item = self.table_entry.item(row, 2)
        if item:
            horse_id = item.data(Qt.ItemDataRole.UserRole)
            if horse_id:
                dlg = HorseDetailDialog(
                    self.db,
                    horse_id,
                    exclude_race_id=self.current_selected_race_id,
                    parent=self,
                )
                dlg.exec()

    def _open_race_view(self) -> None:
        """別ウィンドウで2Dレース閲覧ダイアログを開く"""
        if self.current_selected_race_id:
            dlg = RaceViewDialog(self.db, self.current_selected_race_id, parent=self)
            dlg.exec()
        else:
            QMessageBox.warning(self, "未選択", "閲覧するレースを選択してください。")

    def _open_race_result(self) -> None:
        """別ウィンドウでレース結果ダイアログを開く"""
        if self.current_selected_race_id:
            dlg = RaceResultDialog(self.db, self.current_selected_race_id, parent=self)
            dlg.exec()
        else:
            QMessageBox.warning(self, "未選択", "結果を表示するレースを選択してください。")

    def _advance_to_next_week(self) -> None:
        """次の週に進み、その週の全レースを自動実行して表示更新"""
        self.btn_next_week.setEnabled(False)
        self.btn_next_week.setText("⏳ 進行中...")

        with self.db.session() as conn:
            latest_y, latest_w = get_latest_completed_week(conn)

        if latest_w >= 48:
            # 年度末処理を行い、次年度第1週へ
            self.life.advance_year(current_year=latest_y)
            next_y = latest_y + 1
            next_w = 1
            # 次年度第1週のレースを実行
            res = self.cal.run_week(next_y, next_w)
            QMessageBox.information(
                self,
                "年度更新 & レース完了",
                f"★ 第{latest_y}年度が終了し、第{next_y}年度 第1週 へ進行しました！\n"
                f"開催: {res.get('races_run', 0)}レース / 出走: {res.get('starters_count', 0)}頭"
            )
        else:
            next_y = latest_y
            next_w = latest_w + 1
            res = self.cal.run_week(next_y, next_w)

        self.btn_next_week.setText("⏩ 次の週に進む")
        self.btn_next_week.setEnabled(True)

        self.refresh_dashboard()
        self.simulation_completed.emit()
