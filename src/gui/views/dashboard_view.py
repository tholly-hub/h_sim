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
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.lifecycle import LifecycleEngine
from src.db.database import Database, get_db
from src.gui.views.annual_events_dialogs import (
    SpringBreedingDialog,
    SpringFoalingDialog,
    UnvictoryRetirementDialog,
    YearEndAwardsDialog,
)
from src.gui.views.horse_detail_dialog import HorseDetailDialog
from src.gui.views.race_dialogs import RaceResultDialog, RaceViewDialog
from src.models.horse import Horse
from src.models.race import RaceGrade
from src.race.engine import clean_race_name
from src.race.calendar import CalendarController


TRACK_SORT_ORDER: Dict[str, int] = {
    "TOKYO": 1,
    "NAKAYAMA": 2,
    "KYOTO": 3,
    "HANSHIN": 4,
    "CHUKYO": 5,
    "NIIGATA": 6,
    "FUKUSHIMA": 7,
    "KOKURA": 8,
    "OI": 9,
    "KAWASAKI": 10,
    "FUNABASHI": 11,
    "MORIOKA": 12,
}

TRACK_DISPLAY_NAMES: Dict[str, str] = {
    "TOKYO": "東京競馬場",
    "NAKAYAMA": "中山競馬場",
    "KYOTO": "京都競馬場",
    "HANSHIN": "阪神競馬場",
    "CHUKYO": "中京競馬場",
    "NIIGATA": "新潟競馬場",
    "FUKUSHIMA": "福島競馬場",
    "KOKURA": "小倉競馬場",
    "OI": "大井競馬場",
    "KAWASAKI": "川崎競馬場",
    "FUNABASHI": "船橋競馬場",
    "MORIOKA": "盛岡競馬場",
}

GRADE_SORT_ORDER: Dict[Any, int] = {
    RaceGrade.MAIDEN: 1,
    "MAIDEN": 1,
    "未勝利": 1,
    RaceGrade.NEWCOMER: 2,
    "NEWCOMER": 2,
    "新馬": 2,
    RaceGrade.COND_1W: 3,
    "COND_1W": 3,
    "1勝クラス": 3,
    RaceGrade.COND_2W: 4,
    "COND_2W": 4,
    "2勝クラス": 4,
    RaceGrade.COND_3W: 5,
    "COND_3W": 5,
    "3勝クラス": 5,
    RaceGrade.L: 6,
    "L": 6,
    "リステッド": 6,
    RaceGrade.OP: 6,
    "OP": 6,
    "オープン": 6,
    RaceGrade.G3: 7,
    "G3": 7,
    RaceGrade.G2: 8,
    "G2": 8,
    RaceGrade.G1: 9,
    "G1": 9,
}


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
        # 1行目: 年・月・週の表示 & 週切替 & 「🎬 レースを見る」「⏩ 次の週に進む」ボタン
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
        row1_layout.setSpacing(10)

        self.lbl_current_time = QLabel("📅 第 1 年 6 月 第 1 週 (第21週)")
        self.lbl_current_time.setStyleSheet("font-size: 18px; font-weight: bold; color: #38bdf8;")
        row1_layout.addWidget(self.lbl_current_time)

        row1_layout.addStretch()

        lbl_select = QLabel("切替:")
        lbl_select.setStyleSheet("color: #94a3b8; font-size: 13px;")
        row1_layout.addWidget(lbl_select)

        # 年セレクタ & 週セレクタ
        self.combo_year = QComboBox()
        self.combo_year.setMinimumWidth(90)
        self.combo_year.currentIndexChanged.connect(self._on_year_selected)
        row1_layout.addWidget(self.combo_year)

        self.combo_week = QComboBox()
        self.combo_week.setMinimumWidth(160)
        self.combo_week.currentIndexChanged.connect(self._on_week_selected)
        row1_layout.addWidget(self.combo_week)

        # 「🎬 レースを見る」ボタン（1行目・次の週に進むの左に配置）
        self.btn_view_race_top = QPushButton("🎬 レースを見る")
        self.btn_view_race_top.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:disabled {
                background-color: #475569;
                color: #94a3b8;
            }
        """)
        self.btn_view_race_top.clicked.connect(self._open_race_view)
        row1_layout.addWidget(self.btn_view_race_top)

        # 「⏩ 次の週に進む」ボタン
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
        # 2行目: 今週のレース一覧 (競馬場別タブ表示)
        # ==========================================
        self.row2_group = QGroupBox("🏇 今週の開催レース一覧 (競馬場タブを選択し、レースをクリックすると出走馬表が切り替わります)")
        self.row2_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 13px; color: #f8fafc; }")
        row2_layout = QVBoxLayout(self.row2_group)
        row2_layout.setContentsMargins(6, 6, 6, 6)

        self.tabs_tracks = QTabWidget()
        self.tabs_tracks.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #334155;
                background-color: #0f172a;
                border-radius: 6px;
            }
            QTabBar::tab {
                background: #1e293b;
                color: #94a3b8;
                font-weight: bold;
                font-size: 13px;
                padding: 6px 18px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 3px;
                border: 1px solid #334155;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background: #2563eb;
                color: #ffffff;
            }
            QTabBar::tab:hover:!selected {
                background: #334155;
                color: #f1f5f9;
            }
        """)
        self.tabs_tracks.currentChanged.connect(self._on_track_tab_changed)
        row2_layout.addWidget(self.tabs_tracks)

        self.track_tables: Dict[str, QTableWidget] = {}

        splitter.addWidget(self.row2_group)

        # ==========================================
        # 3行目: 出走馬表 & 「レースを見る」「レース結果」ボタン
        # ==========================================
        self.row3_group = QGroupBox("📋 出走馬表 & オッズ (レース結果ボタンを押すまで着順は伏せられます)")
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
            "枠番", "馬番", "馬名 (クリックで詳細)", "性齢", "斤量", "騎手", "厩舎", "人気/オッズ"
        ])
        header = self.table_entry.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_entry.setColumnWidth(0, 50)   # 枠番
        self.table_entry.setColumnWidth(1, 50)   # 馬番
        self.table_entry.setColumnWidth(2, 230)  # 馬名 (全文字最後まで確実に表示)
        self.table_entry.setColumnWidth(3, 60)   # 性齢
        self.table_entry.setColumnWidth(4, 70)   # 斤量
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

    @property
    def table_races(self) -> Optional[QTableWidget]:
        """現在選択中の競馬場タブのテーブル（後方互換用）"""
        cur = self.tabs_tracks.currentWidget()
        if isinstance(cur, QTableWidget):
            return cur
        if self.track_tables:
            return next(iter(self.track_tables.values()))
        return None

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
        """消化済みの年・週リストを各コンボボックスに設定"""
        self.combo_year.blockSignals(True)
        self.combo_week.blockSignals(True)
        self.combo_year.clear()
        self.combo_week.clear()

        # 過去すべての消化済み (year, week) を取得
        with self.db.session() as conn:
            rows = conn.execute("""
                SELECT DISTINCT rc.year, rc.week
                FROM results r
                JOIN races rc ON r.race_id = rc.race_id
                ORDER BY rc.year ASC, rc.week ASC
            """).fetchall()

        self._year_weeks_map: Dict[int, List[int]] = {}
        if not rows:
            self._year_weeks_map[current_year] = [current_week]
        else:
            for r in rows:
                y = r["year"]
                w = r["week"]
                self._year_weeks_map.setdefault(y, []).append(w)

        for y in sorted(self._year_weeks_map.keys()):
            self.combo_year.addItem(f"{y}年目", y)

        # 最新年を選択
        latest_y = current_year if current_year in self._year_weeks_map else max(self._year_weeks_map.keys())
        idx_y = self.combo_year.findData(latest_y)
        if idx_y >= 0:
            self.combo_year.setCurrentIndex(idx_y)

        self._update_weeks_for_year(latest_y, select_week=current_week)

        self.combo_year.blockSignals(False)
        self.combo_week.blockSignals(False)

    def _update_weeks_for_year(self, year: int, select_week: Optional[int] = None) -> None:
        """指定された年の週リストを combo_week にロード"""
        self.combo_week.blockSignals(True)
        self.combo_week.clear()

        weeks = self._year_weeks_map.get(year, [21])
        for w in sorted(weeks):
            m = ((w - 1) // 4) + 1
            mw = ((w - 1) % 4) + 1
            label = f"{m}月 第{mw}週 (第{w}週)"
            self.combo_week.addItem(label, w)

        if select_week is not None and select_week in weeks:
            idx = self.combo_week.findData(select_week)
            if idx >= 0:
                self.combo_week.setCurrentIndex(idx)
        else:
            self.combo_week.setCurrentIndex(self.combo_week.count() - 1)

        self.combo_week.blockSignals(False)

    def _on_year_selected(self, idx: int) -> None:
        """年セレクタが変更された時の処理"""
        y = self.combo_year.currentData()
        if y is not None:
            self._update_weeks_for_year(y)
            w = self.combo_week.currentData()
            if w is not None:
                self.viewing_year = y
                self.viewing_week = w
                self._load_week_data(y, w)

    def _on_week_selected(self, idx: int) -> None:
        """ユーザーが週を切り替えた時の処理"""
        y = self.combo_year.currentData()
        w = self.combo_week.currentData()
        if y is not None and w is not None:
            self.viewing_year = y
            self.viewing_week = w
            self._load_week_data(y, w)

    def _load_week_data(self, year: int, week: int) -> None:
        """指定した年・週のレース一覧を競馬場別タブにロードし、出走馬表を表示"""
        from PyQt6.QtGui import QColor

        cur_month = ((week - 1) // 4) + 1
        m_week = ((week - 1) % 4) + 1
        self.lbl_current_time.setText(
            f"📅 第 {year} 年 {cur_month} 月 第 {m_week} 週 (通算 第{week}週)"
        )

        races = self.cal.get_races_for_week(year, week)

        with self.db.session() as conn:
            # 完了済みレースIDと出走頭数を取得
            done_map: Dict[int, int] = {}
            if races:
                d_rows = conn.execute("""
                    SELECT res.race_id, COUNT(*) as cnt
                    FROM results res
                    WHERE res.race_id IN (""" +
                    ",".join(str(r.race_id) for r in races) + """)
                    GROUP BY res.race_id
                """).fetchall()
                done_map = {dr["race_id"]: dr["cnt"] for dr in d_rows}

        # 消化済み週の場合は出走馬がいた開催確定レースのみを表示
        if done_map:
            display_races = [r for r in races if r.race_id in done_map]
        else:
            display_races = races

        # 競馬場ごとにレースをグループ化
        races_by_track: Dict[str, List[Race]] = {}
        for r in display_races:
            races_by_track.setdefault(r.track_id, []).append(r)

        # 競馬場の表示順序でソート
        sorted_tracks = sorted(
            races_by_track.keys(),
            key=lambda trk: TRACK_SORT_ORDER.get(trk, 99)
        )

        self.tabs_tracks.blockSignals(True)
        self.tabs_tracks.clear()
        self.track_tables.clear()

        first_race_id: Optional[int] = None

        # グレード別カラーマップ (新馬: 黄緑, 未勝利: 明るい灰, 条件戦: 水色, リステッド: 黄色, G3: 緑, G2: 青, G1: 赤)
        GRADE_COLOR_MAP = {
            "G1": "#ef4444",      # 赤
            "G2": "#3b82f6",      # 青
            "G3": "#22c55e",      # 緑
            "L": "#facc15",       # 黄色
            "リステッド": "#facc15",
            "OP": "#fbbf24",      # オレンジ寄りの黄
            "オープン": "#fbbf24",
            "3勝クラス": "#38bdf8", # 水色
            "COND_3W": "#38bdf8",
            "2勝クラス": "#38bdf8",
            "COND_2W": "#38bdf8",
            "1勝クラス": "#38bdf8",
            "COND_1W": "#38bdf8",
            "新馬": "#84cc16",     # 黄緑
            "NEWCOMER": "#84cc16",
            "未勝利": "#94a3b8",   # 明るい灰
            "MAIDEN": "#94a3b8",
        }

        for trk in sorted_tracks:
            track_races = races_by_track[trk]
            # 各競馬場内でのレースソート: グレード昇順（未勝利->新馬->1勝->2勝->3勝->L/OP->G3->G2->G1）、距離昇順
            track_races = sorted(
                track_races,
                key=lambda r: (
                    GRADE_SORT_ORDER.get(r.grade, 99),
                    r.distance,
                    r.race_id or 0,
                ),
            )

            tbl = QTableWidget()
            tbl.setColumnCount(6)
            tbl.setHorizontalHeaderLabels([
                "R", "レース名", "グレード", "馬場/距離", "頭数", "発走状態"
            ])
            header = tbl.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            tbl.setColumnWidth(0, 60)   # R
            tbl.setColumnWidth(2, 85)   # グレード
            tbl.setColumnWidth(3, 110)  # 馬場/距離
            tbl.setColumnWidth(4, 70)   # 頭数
            tbl.setColumnWidth(5, 100)  # 発走状態
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # レース名
            tbl.setAlternatingRowColors(True)
            tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            tbl.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

            tbl.setRowCount(len(track_races))
            for r_idx, r in enumerate(track_races):
                r_num_str = f"第{r_idx + 1}R"
                race_name = clean_race_name(r.name)
                grade_name = r.grade.value if hasattr(r.grade, "value") else str(r.grade)
                surf_jp = "芝" if (r.surface.value if hasattr(r.surface, "value") else str(r.surface)) == "turf" else "ダート"
                surf_dist = f"{surf_jp} {r.distance}m"
                gate_str = f"{done_map.get(r.race_id, r.full_gate)}頭"
                is_done = (r.race_id in done_map)
                status_str = "🏁 発走確定" if is_done else "⏳ 未発走"

                items = [
                    QTableWidgetItem(r_num_str),
                    QTableWidgetItem(race_name),
                    QTableWidgetItem(grade_name),
                    QTableWidgetItem(surf_dist),
                    QTableWidgetItem(gate_str),
                    QTableWidgetItem(status_str),
                ]

                # race_idを保持
                items[1].setData(Qt.ItemDataRole.UserRole, r.race_id)

                col_color = GRADE_COLOR_MAP.get(grade_name, "#f8fafc")
                for col_idx, item in enumerate(items):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if col_idx in (1, 2):  # レース名とグレードに色を適用
                        item.setForeground(QColor(col_color))
                    if col_idx == 5:
                        item.setForeground(QColor("#22c55e") if is_done else QColor("#38bdf8"))
                    tbl.setItem(r_idx, col_idx, item)

                if first_race_id is None and track_races:
                    first_race_id = track_races[0].race_id

            # イベント接続
            tbl.cellClicked.connect(lambda row, col, t=tbl: self._on_track_race_selected(t, row))
            tbl.itemSelectionChanged.connect(lambda t=tbl: self._on_track_table_selection_changed(t))

            self.track_tables[trk] = tbl
            tab_title = f"📍 {TRACK_DISPLAY_NAMES.get(trk, trk)} ({len(track_races)}R)"
            self.tabs_tracks.addTab(tbl, tab_title)

        self.tabs_tracks.blockSignals(False)

        if sorted_tracks and first_race_id:
            first_tbl = self.track_tables[sorted_tracks[0]]
            first_tbl.selectRow(0)
            self.current_selected_race_id = first_race_id
            self._load_race_entry(first_race_id)
        else:
            self.table_entry.setRowCount(0)
            self.lbl_selected_race_title.setText("今週は開催レースがありません")
            self.btn_view_race.setEnabled(False)
            self.btn_view_race_top.setEnabled(False)
            self.btn_view_result.setEnabled(False)
            self.current_selected_race_id = None

    def _on_track_tab_changed(self, index: int) -> None:
        """競馬場タブが切り替わったときの処理"""
        if index < 0 or index >= self.tabs_tracks.count():
            return
        widget = self.tabs_tracks.widget(index)
        if isinstance(widget, QTableWidget):
            cur_row = widget.currentRow()
            if cur_row < 0:
                cur_row = 0
                widget.selectRow(0)
            self._on_track_race_selected(widget, cur_row)

    def _on_track_table_selection_changed(self, table: QTableWidget) -> None:
        """テーブルの行選択変更時の処理"""
        row = table.currentRow()
        if row >= 0:
            self._on_track_race_selected(table, row)

    def _on_track_race_selected(self, table: QTableWidget, row: int) -> None:
        """テーブル内の指定行のレースを出走馬表にロード"""
        item = table.item(row, 1)
        if not item:
            return
        race_id = item.data(Qt.ItemDataRole.UserRole)
        if race_id:
            self.current_selected_race_id = race_id
            self._load_race_entry(race_id)

    def _on_race_selected_by_row(self, row: int) -> None:
        """後方互換用: 現在アクティブなテーブルの指定行を選択"""
        tbl = self.table_races
        if tbl and 0 <= row < tbl.rowCount():
            tbl.selectRow(row)
            self._on_track_race_selected(tbl, row)

    def _on_race_cell_clicked(self, row: int, col: int) -> None:
        """後方互換用: セルクリックイベント"""
        self._on_race_selected_by_row(row)

    def _load_race_entry(self, race_id: int) -> None:
        """選択レースの出走馬表・オッズをロード（着順・タイムは完全非表示）"""
        from src.race.entry import calculate_carried_weight
        from src.models.race import Race

        with self.db.session() as conn:
            rc = conn.execute("SELECT * FROM races WHERE race_id = ?", (race_id,)).fetchone()
            if not rc:
                return

            surf_jp = "芝" if rc["surface"] == "turf" else "ダート"
            r_name = clean_race_name(rc["name"])
            track_name = TRACK_DISPLAY_NAMES.get(rc["track_id"], rc["track_id"])
            self.lbl_selected_race_title.setText(
                f"{r_name} ({rc['grade']}) - {track_name} {surf_jp} {rc['distance']}m [{rc['full_gate']}頭立]"
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
            self.btn_view_race_top.setEnabled(True)
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

            # レースオブジェクト生成（斤量計算用）
            try:
                race_obj = Race.from_row(rc)
            except Exception:
                race_obj = None

            for idx, r in enumerate(results):
                g_num = int(r["gate_number"])
                bracket_num = get_jra_bracket(g_num, total_h)
                bg_col, fg_col, _, bracket_name = JRA_BRACKET_COLORS.get(bracket_num, ("#ffffff", "#000000", "#999999", f"{bracket_num}枠"))

                h_name = r["horse_name"]
                sex_age = f"{sex_map.get(r['sex'], '')}{r['age']}"
                j_name = r["jockey_name"] or "未定"
                t_name = r["trainer_name"] or "未定"
                
                # 斤量 (kg)
                if "carried_weight" in r.keys() and r["carried_weight"] and float(r["carried_weight"]) > 0:
                    cw_str = f"{float(r['carried_weight']):.1f}kg"
                elif race_obj:
                    # 計算
                    from types import SimpleNamespace
                    temp_horse = SimpleNamespace(sex=r["sex"], age=r["age"])
                    cw_val = calculate_carried_weight(race_obj, temp_horse)  # type: ignore
                    cw_str = f"{cw_val:.1f}kg"
                else:
                    cw_str = "57.0kg"

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
                    QTableWidgetItem(cw_str),
                    QTableWidgetItem(j_name),
                    QTableWidgetItem(t_name),
                    QTableWidgetItem(odds_str),
                ]

                for c, itm in enumerate(items):
                    itm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table_entry.setItem(idx, c, itm)
        else:
            self.btn_view_race.setEnabled(False)
            self.btn_view_race_top.setEnabled(False)
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
            # 1. 年度更新処理（8歳馬・ピークアウト馬引退、種牡馬・繁殖牝馬昇格、騎手・調教師世代交代・承継、2歳新馬入厩、全馬加齢）
            self.life.advance_year(current_year=latest_y)
            next_y = latest_y + 1
            next_w = 1

            # 2. 1月第1週（新シーズン開幕）のJRA表彰式 & 新シーズン体制発表ダイアログの表示
            try:
                awards_dlg = YearEndAwardsDialog(self.db, latest_y, self)
                awards_dlg.exec()
            except Exception as e:
                print(f"YearEndAwardsDialog Error: {e}")

            # 3. 次年度第1週（1月第1週）のレースを実行
            # ※既に引退馬・引退騎手・引退調教師の処理が完了しているため、1月1週のレースには一切出走・騎乗・出走登録されません
            res = self.cal.run_week(next_y, next_w)
            QMessageBox.information(
                self,
                "新シーズン開幕 & レース完了",
                f"★ 第{latest_y}年度が終了し、第{next_y}年度 第1週（1月第1週）へ進行しました！\n"
                f"開催: {res.get('races_run', 0)}レース / 出走: {res.get('starters_count', 0)}頭"
            )
        else:
            next_y = latest_y
            next_w = latest_w + 1

            # レースを実行（run_week内で3月第1週の出産、4月第1週の種付け、36週の未勝利引退が自動実行される）
            res = self.cal.run_week(next_y, next_w)

            # 3月第1週 (第9週) 進行時: 当歳馬（0歳）誕生発表ダイアログ
            if next_w == 9:
                try:
                    foal_dlg = SpringFoalingDialog(self.db, next_y, self)
                    foal_dlg.exec()
                except Exception as e:
                    print(f"SpringFoalingDialog Error: {e}")

            # 4月第1週 (第13週) 進行時: 春季種付け交配発表ダイアログ
            if next_w == 13:
                try:
                    breed_dlg = SpringBreedingDialog(self.db, next_y, self)
                    breed_dlg.exec()
                except Exception as e:
                    print(f"SpringBreedingDialog Error: {e}")

            # 9月第4週 (第36週) 進行時: 3歳未勝利馬 引退発表ダイアログ
            # （第36週のレース終了時点で3歳未勝利馬は引退処理されます）
            if next_w == 36:
                try:
                    retire_dlg = UnvictoryRetirementDialog(self.db, next_y, self)
                    retire_dlg.exec()
                except Exception as e:
                    print(f"UnvictoryRetirementDialog Error: {e}")

        self.btn_next_week.setText("⏩ 次の週に進む")
        self.btn_next_week.setEnabled(True)

        self.refresh_dashboard()
        self.simulation_completed.emit()
