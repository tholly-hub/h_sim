"""
競走馬詳細ダイアログ (HorseDetailDialog)
- 出馬表の各馬クリック時に別ウィンドウとしてポップアップ
- プロフィール（名前、厩舎、牧場、馬主、主戦騎手、年齢、馬場適性、距離適性レンジ）
- 5代血統表タブ
- 成績集計タブ（通算成績、重賞内訳[G1/G2/G3/OP]、芝ダート別、距離別、競馬場別）
- レース出走全履歴テーブル（開催年・週、競馬場、レース名、グレード、距離、着順、タイム、上がり3Fなど）
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.db.database import Database, get_db
from src.gui.widgets.html_delegate import HTMLDelegate
from src.gui.widgets.pedigree_widget import PedigreeWidget
from src.models.horse import Horse
from src.race.engine import clean_race_name
from src.race.track import get_track_info
from src.views.pedigree_builder import PedigreeBuilder



GRADE_COLOR_MAP = {
    "G1": ("#b91c1c", "#ffffff"),      # 赤
    "G2": ("#1d4ed8", "#ffffff"),      # 青
    "G3": ("#15803d", "#ffffff"),      # 緑
    "L": ("#ca8a04", "#0f172a"),       # 黄
    "OP": ("#ca8a04", "#0f172a"),      # 黄
    "COND_3W": ("#0284c7", "#ffffff"), # 濃水色
    "COND_2W": ("#0284c7", "#ffffff"), # 濃水色
    "COND_1W": ("#0284c7", "#ffffff"), # 濃水色
    "MAIDEN": ("#475569", "#ffffff"),  # 灰
    "NEWCOMER": ("#ea580c", "#ffffff") # 橙
}


def format_finish_time(seconds: float) -> str:
    """走破タイムを分:秒.厘形式に変換"""
    if seconds <= 0:
        return "--:--.-"
    m = int(seconds // 60)
    s = seconds - (m * 60)
    return f"{m}:{s:04.1f}"


class HorseDetailDialog(QDialog):
    """競走馬詳細ダイアログ"""

    def __init__(self, db: Database, horse_id: int, parent: Optional[QWidget] = None, exclude_race_id: Optional[int] = None):
        super().__init__(parent)
        self.db = db
        self.horse_id = horse_id
        self.exclude_race_id = exclude_race_id  # 閲覧中のレースがあれば除外して過去戦績のみ表示
        self.pedigree_builder = PedigreeBuilder(db)

        self.setWindowTitle("🐎 競走馬カルテ・詳細情報")
        self.resize(1000, 720)
        self._init_ui()
        self._load_horse_data()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. ヘッダーカード: 基本プロフィール
        self.profile_card = QFrame()
        self.profile_card.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
            }
        """)
        card_layout = QVBoxLayout(self.profile_card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(6)

        # 馬名（大見出し）
        self.lbl_name = QLabel("-")
        self.lbl_name.setStyleSheet("font-size: 20px; font-weight: bold; color: #38bdf8;")
        card_layout.addWidget(self.lbl_name)

        # 基本諸元グリッド
        grid_info = QGridLayout()
        grid_info.setHorizontalSpacing(24)
        grid_info.setVerticalSpacing(4)

        self.lbl_trainer = QLabel("所属: -")
        self.lbl_breeder = QLabel("牧場: -")
        self.lbl_owner = QLabel("馬主: -")
        self.lbl_jockey = QLabel("騎手: -")
        self.lbl_aptitude = QLabel("適性: -")
        self.lbl_earnings = QLabel("生涯賞金: -")

        for lbl in (self.lbl_trainer, self.lbl_breeder, self.lbl_owner, self.lbl_jockey, self.lbl_aptitude, self.lbl_earnings):
            lbl.setStyleSheet("font-size: 13px; color: #cbd5e1;")

        grid_info.addWidget(self.lbl_trainer, 0, 0)
        grid_info.addWidget(self.lbl_breeder, 0, 1)
        grid_info.addWidget(self.lbl_owner, 0, 2)
        grid_info.addWidget(self.lbl_jockey, 1, 0)
        grid_info.addWidget(self.lbl_aptitude, 1, 1)
        grid_info.addWidget(self.lbl_earnings, 1, 2)

        card_layout.addLayout(grid_info)
        main_layout.addWidget(self.profile_card)

        # 2. タブウィジェット
        self.tabs = QTabWidget()

        # タブA: 出走レース全履歴
        self.history_tab = QWidget()
        hist_layout = QVBoxLayout(self.history_tab)
        self.table_history = QTableWidget()
        self.table_history.setColumnCount(14)
        self.table_history.setHorizontalHeaderLabels([
            "年・週", "競馬場", "レース名", "グレード", "馬場", "距離", "頭数", "人気", "着順", "タイム", "上り3F", "賞金", "結果", "動画"
        ])
        h_header = self.table_history.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_history.setColumnWidth(0, 95)
        self.table_history.setColumnWidth(1, 55)
        self.table_history.setColumnWidth(2, 140)
        self.table_history.setColumnWidth(3, 75)
        self.table_history.setColumnWidth(4, 45)
        self.table_history.setColumnWidth(5, 55)
        self.table_history.setColumnWidth(6, 45)
        self.table_history.setColumnWidth(7, 45)
        self.table_history.setColumnWidth(8, 45)
        self.table_history.setColumnWidth(9, 80)
        self.table_history.setColumnWidth(10, 55)
        self.table_history.setColumnWidth(11, 75)
        self.table_history.setColumnWidth(12, 60)
        self.table_history.setColumnWidth(13, 60)
        self.table_history.setItemDelegateForColumn(9, HTMLDelegate(self.table_history))
        h_header.setStretchLastSection(False)

        self.table_history.setAlternatingRowColors(True)
        self.table_history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        hist_layout.addWidget(self.table_history)
        self.tabs.addTab(self.history_tab, "📋 出走全レース履歴")

        # タブB: 5代血統表
        self.pedigree_tab = QWidget()
        ped_layout = QVBoxLayout(self.pedigree_tab)
        self.pedigree_widget = PedigreeWidget()
        self.pedigree_widget.horse_selected.connect(self._on_ancestor_clicked)
        ped_layout.addWidget(self.pedigree_widget)
        self.tabs.addTab(self.pedigree_tab, "🌳 5代血統表")

        # タブC: 成績詳細集計（画像フォーマット準拠・白背景・黒文字）
        self.stats_tab = QWidget()
        self.stats_tab.setStyleSheet("background-color: #ffffff;")
        stats_layout = QVBoxLayout(self.stats_tab)
        stats_layout.setContentsMargins(8, 8, 8, 8)

        self.scroll_stats = QScrollArea()
        self.scroll_stats.setWidgetResizable(True)
        self.scroll_stats.setStyleSheet("background-color: #ffffff; border: none;")
        stats_content = QWidget()
        stats_content.setStyleSheet("background-color: #ffffff;")
        self.stats_grid = QVBoxLayout(stats_content)
        self.stats_grid.setContentsMargins(12, 12, 12, 12)
        self.stats_grid.setSpacing(12)

        # 1. レース条件別成績
        lbl_sec1 = QLabel("レース条件別成績")
        lbl_sec1.setStyleSheet("font-size: 15px; font-weight: bold; color: #000000; margin-top: 4px;")
        self.stats_grid.addWidget(lbl_sec1)

        # 1-1. レース合計
        lbl_total = QLabel("レース合計")
        lbl_total.setStyleSheet("font-size: 13px; font-weight: bold; color: #1e293b; margin-top: 2px;")
        self.stats_grid.addWidget(lbl_total)

        self.tbl_total = self._create_stats_table(
            headers=["1着", "2着", "3着", "着外", "出走回数", "勝率", "連対率", "3着内率"],
            row_count=1,
            col_widths=[65, 65, 65, 65, 75, 75, 75, 75]
        )
        self.stats_grid.addWidget(self.tbl_total, alignment=Qt.AlignmentFlag.AlignLeft)

        # 1-2. コース別成績
        lbl_course = QLabel("コース別成績")
        lbl_course.setStyleSheet("font-size: 13px; font-weight: bold; color: #1e293b; margin-top: 6px;")
        self.stats_grid.addWidget(lbl_course)

        self.course_labels = ["芝", "ダート"]
        self.tbl_course = self._create_stats_table(
            headers=["", "1着", "2着", "3着", "着外", "出走回数", "勝率", "連対率", "3着内率"],
            row_count=len(self.course_labels),
            col_widths=[110, 65, 65, 65, 65, 75, 75, 75, 75]
        )
        for r_idx, clbl in enumerate(self.course_labels):
            item = QTableWidgetItem(clbl)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setForeground(QColor("#000000"))
            self.tbl_course.setItem(r_idx, 0, item)
        self.stats_grid.addWidget(self.tbl_course, alignment=Qt.AlignmentFlag.AlignLeft)

        # 2. 距離別成績
        lbl_sec2 = QLabel("距離別成績")
        lbl_sec2.setStyleSheet("font-size: 15px; font-weight: bold; color: #000000; margin-top: 10px;")
        self.stats_grid.addWidget(lbl_sec2)

        self.dist_rows_def = [
            ("芝", "1000-1200", lambda s, d: s == "turf" and d <= 1200),
            ("芝", "1401-1600", lambda s, d: s == "turf" and 1201 <= d <= 1600),
            ("芝", "1601-2000", lambda s, d: s == "turf" and 1601 <= d <= 2000),
            ("芝", "2001-2400", lambda s, d: s == "turf" and 2001 <= d <= 2400),
            ("芝", "2401-3600", lambda s, d: s == "turf" and d >= 2401),
            ("ダート", "1000-1200", lambda s, d: s == "dirt" and d <= 1200),
            ("ダート", "1201-1600", lambda s, d: s == "dirt" and 1201 <= d <= 1600),
            ("ダート", "1601-2000", lambda s, d: s == "dirt" and 1601 <= d <= 2000),
            ("ダート", "2001-2400", lambda s, d: s == "dirt" and d >= 2001),
        ]
        self.tbl_dist = self._create_stats_table(
            headers=["", "", "1着", "2着", "3着", "着外", "出走回数", "勝率", "連対率", "3着内率"],
            row_count=len(self.dist_rows_def),
            col_widths=[65, 100, 65, 65, 65, 65, 75, 75, 75, 75]
        )
        for r_idx, (surf_label, dist_label, _) in enumerate(self.dist_rows_def):
            s_item = QTableWidgetItem(surf_label)
            s_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            s_item.setForeground(QColor("#000000"))
            self.tbl_dist.setItem(r_idx, 0, s_item)

            d_item = QTableWidgetItem(dist_label)
            d_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            d_item.setForeground(QColor("#000000"))
            self.tbl_dist.setItem(r_idx, 1, d_item)
        self.stats_grid.addWidget(self.tbl_dist, alignment=Qt.AlignmentFlag.AlignLeft)

        # 3. グレード別成績
        lbl_sec3 = QLabel("グレード別成績")
        lbl_sec3.setStyleSheet("font-size: 15px; font-weight: bold; color: #000000; margin-top: 10px;")
        self.stats_grid.addWidget(lbl_sec3)

        self.grade_labels = [
            "新馬・未勝利", "1勝クラス", "2勝クラス", "3勝クラス",
            "リステッド", "G3", "G2", "G1"
        ]
        self.tbl_grade = self._create_stats_table(
            headers=["", "1着", "2着", "3着", "着外", "出走回数", "勝率", "連対率", "3着内率"],
            row_count=len(self.grade_labels),
            col_widths=[110, 65, 65, 65, 65, 75, 75, 75, 75]
        )
        for r_idx, glbl in enumerate(self.grade_labels):
            item = QTableWidgetItem(glbl)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setForeground(QColor("#000000"))
            self.tbl_grade.setItem(r_idx, 0, item)
        self.stats_grid.addWidget(self.tbl_grade, alignment=Qt.AlignmentFlag.AlignLeft)

        # 4. 人気別成績
        lbl_sec4 = QLabel("人気別成績")
        lbl_sec4.setStyleSheet("font-size: 15px; font-weight: bold; color: #000000; margin-top: 10px;")
        self.stats_grid.addWidget(lbl_sec4)

        self.pop_labels = ["1番人気", "2番人気", "3番人気", "4番人気以下"]
        self.tbl_pop = self._create_stats_table(
            headers=["", "1着", "2着", "3着", "着外", "出走回数", "勝率", "連対率", "3着内率"],
            row_count=len(self.pop_labels),
            col_widths=[110, 65, 65, 65, 65, 75, 75, 75, 75]
        )
        for r_idx, plbl in enumerate(self.pop_labels):
            item = QTableWidgetItem(plbl)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setForeground(QColor("#000000"))
            self.tbl_pop.setItem(r_idx, 0, item)
        self.stats_grid.addWidget(self.tbl_pop, alignment=Qt.AlignmentFlag.AlignLeft)

        self.stats_grid.addStretch()
        self.scroll_stats.setWidget(stats_content)
        stats_layout.addWidget(self.scroll_stats)
        self.tabs.addTab(self.stats_tab, "📊 成績詳細集計")

        main_layout.addWidget(self.tabs)

        # 閉じるボタン
        btn_close = QPushButton("閉じる")
        btn_close.setStyleSheet("background-color: #334155; font-weight: bold; padding: 6px 18px;")
        btn_close.clicked.connect(self.close)
        main_layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

    def _create_stats_table(self, headers: List[str], row_count: int, col_widths: List[int]) -> QTableWidget:
        tbl = QTableWidget()
        tbl.setColumnCount(len(headers))
        tbl.setRowCount(row_count)
        tbl.setHorizontalHeaderLabels(headers)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.setAlternatingRowColors(False)
        tbl.setShowGrid(True)
        tbl.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        tbl.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #334155;
                border: 1px solid #334155;
                color: #000000;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #0c3559;
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                padding: 3px;
                border: 1px solid #334155;
            }
            QTableWidget::item {
                color: #000000;
                background-color: #ffffff;
                padding: 2px 4px;
            }
        """)

        header = tbl.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        header.setFixedHeight(26)
        tbl.verticalHeader().setDefaultSectionSize(26)

        total_width = 0
        for idx, w in enumerate(col_widths):
            tbl.setColumnWidth(idx, w)
            total_width += w

        header.setStretchLastSection(False)
        tbl.setFixedSize(total_width + 2, 26 + (row_count * 26) + 2)
        return tbl

    def _populate_stats_row(self, table: QTableWidget, row_idx: int, matched_runs: List[Any], col_offset: int = 1) -> None:
        """指定した行に 1着, 2着, 3着, 着外, 出走回数, 勝率, 連対率, 3着内率 を書き込む"""
        n1 = sum(1 for r in matched_runs if r["finish_position"] == 1)
        n2 = sum(1 for r in matched_runs if r["finish_position"] == 2)
        n3 = sum(1 for r in matched_runs if r["finish_position"] == 3)
        n_out = sum(1 for r in matched_runs if r["finish_position"] >= 4)
        starts = n1 + n2 + n3 + n_out

        win_rate = f"{n1 / starts:.3f}" if starts > 0 else ""
        place2_rate = f"{(n1 + n2) / starts:.3f}" if starts > 0 else ""
        place3_rate = f"{(n1 + n2 + n3) / starts:.3f}" if starts > 0 else ""

        vals = [str(n1), str(n2), str(n3), str(n_out), str(starts), win_rate, place2_rate, place3_rate]
        for c_idx, val in enumerate(vals):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setForeground(QColor("#000000"))
            item.setBackground(QColor("#ffffff"))
            table.setItem(row_idx, col_offset + c_idx, item)

    def _load_horse_data(self) -> None:
        with self.db.session() as conn:
            h_row = conn.execute("SELECT * FROM horses WHERE horse_id = ?", (self.horse_id,)).fetchone()
            if not h_row:
                self.lbl_name.setText("該当馬が見つかりません")
                return

            horse = Horse.from_row(h_row)

            # 厩舎名
            trainer_name = "未所属"
            if horse.trainer_id:
                tr = conn.execute("SELECT name, location FROM trainers WHERE trainer_id = ?", (horse.trainer_id,)).fetchone()
                if tr:
                    trainer_name = f"{tr['name']} ({tr['location']})"

            # 生産牧場
            breeder_name = "不明"
            br = conn.execute("SELECT name, region FROM breeders WHERE breeder_id = ?", (horse.breeder_id,)).fetchone()
            if br:
                breeder_name = f"{br['name']} ({br['region']})"

            # 馬主
            owner_name = "不明"
            ow = conn.execute("SELECT name FROM owners WHERE owner_id = ?", (horse.owner_id,)).fetchone()
            if ow:
                owner_name = ow["name"]

            # 主戦騎手
            jockey_name = "未定"
            if horse.jockey_id:
                jk = conn.execute("SELECT name FROM jockeys WHERE jockey_id = ?", (horse.jockey_id,)).fetchone()
                if jk:
                    jockey_name = jk["name"]

            # レース履歴（直近順・降順で表示）
            # 各レースでの勝ちタイムと過去レコードの比較用サブクエリ、および人気順サブクエリを含む
            select_cols = """
                r.race_id, r.year, r.week, r.track_id, r.name AS race_name, r.grade, r.surface, r.distance, r.full_gate,
                res.finish_position, res.finish_time, res.last_3f, res.prize_awarded, res.odds,
                (
                    SELECT COUNT(*) + 1
                    FROM results res_pop
                    WHERE res_pop.race_id = res.race_id 
                      AND (res_pop.odds < res.odds OR (res_pop.odds = res.odds AND res_pop.gate_number < res.gate_number))
                ) AS popularity,
                (
                    SELECT MIN(res_prev.finish_time)
                    FROM results res_prev
                    JOIN races r_prev ON res_prev.race_id = r_prev.race_id
                    WHERE r_prev.track_id = r.track_id 
                      AND r_prev.surface = r.surface 
                      AND r_prev.distance = r.distance
                      AND res_prev.finish_position = 1
                      AND res_prev.finish_time > 0
                      AND (
                          r_prev.year < r.year
                          OR (r_prev.year = r.year AND r_prev.week < r.week)
                          OR (r_prev.year = r.year AND r_prev.week = r.week AND r_prev.race_id < r.race_id)
                      )
                ) AS past_record_time
            """
            if self.exclude_race_id:
                query_results = f"""
                    SELECT {select_cols}
                    FROM results res
                    JOIN races r ON res.race_id = r.race_id
                    WHERE res.horse_id = ? AND res.race_id != ?
                    ORDER BY r.year DESC, r.week DESC, r.race_id DESC
                """
                results = conn.execute(query_results, (self.horse_id, self.exclude_race_id)).fetchall()

                # 除外された今走の獲得賞金を取得して生涯獲得賞金から差し引く
                ex_row = conn.execute(
                    "SELECT prize_awarded FROM results WHERE horse_id = ? AND race_id = ?",
                    (self.horse_id, self.exclude_race_id)
                ).fetchone()
                adjusted_prize = horse.prize_money - (ex_row["prize_awarded"] if ex_row and ex_row["prize_awarded"] else 0)
                if adjusted_prize < 0:
                    adjusted_prize = 0
            else:
                query_results = f"""
                    SELECT {select_cols}
                    FROM results res
                    JOIN races r ON res.race_id = r.race_id
                    WHERE res.horse_id = ?
                    ORDER BY r.year DESC, r.week DESC, r.race_id DESC
                """
                results = conn.execute(query_results, (self.horse_id,)).fetchall()
                adjusted_prize = horse.prize_money


        # 1,2,3,着外の着順内訳計算
        wins_1 = sum(1 for r in results if r["finish_position"] == 1)
        wins_2 = sum(1 for r in results if r["finish_position"] == 2)
        wins_3 = sum(1 for r in results if r["finish_position"] == 3)
        unplaced = sum(1 for r in results if r["finish_position"] > 3)
        record_fmt = f"{wins_1}-{wins_2}-{wins_3}-{unplaced}"

        # ヘッダー情報セット
        sex_map = {"colt": "牡", "filly": "牝", "horse": "牡", "mare": "牝", "gelding": "セ"}
        sex_str = sex_map.get(horse.sex.value if hasattr(horse.sex, "value") else horse.sex, "")
        surf_jp = "芝" if horse.surface_aptitude == "turf" else ("ダート" if horse.surface_aptitude == "dirt" else "芝・ダート兼用")
        mstn_str = horse.mstn_type.value if hasattr(horse.mstn_type, "value") else str(horse.mstn_type)

        self.lbl_name.setText(f"{horse.name} ({sex_str}{horse.age}歳・【{horse.class_name}】・毛色: {horse.coat_color}・{mstn_str})")
        self.lbl_trainer.setText(f"所属: {trainer_name}")
        self.lbl_breeder.setText(f"牧場: {breeder_name}")
        self.lbl_owner.setText(f"馬主: {owner_name}")
        self.lbl_jockey.setText(f"騎手: {jockey_name} | 通算成績: {record_fmt}")
        self.lbl_aptitude.setText(f"適性: {surf_jp} / {horse.apt_distance_min}m〜{horse.apt_distance_max}m (幅{horse.apt_distance_range}m)")
        self.lbl_earnings.setText(f"生涯獲得賞金: {adjusted_prize // 10000:,} 万円")

        # 1. 履歴テーブルの反映
        self.table_history.setRowCount(len(results))
        for idx, r in enumerate(results):
            m_num = ((r['week'] - 1) // 4) + 1
            w_in_m = ((r['week'] - 1) % 4) + 1
            y_w = f"{r['year']}年{m_num}月{w_in_m}週"
            track = r["track_id"]
            r_name = clean_race_name(r["race_name"])
            grade = r["grade"]
            surf = "芝" if r["surface"] == "turf" else "ダート"
            dist = f"{r['distance']}m"
            starters = f"{r['full_gate']}頭"
            pop_str = f"{r['popularity']}人" if r["popularity"] else "-"
            pos = f"{r['finish_position']}着"
            
            # レコード判定 (1着かつその時点でコースレコード更新または初レコード)
            is_rec = False
            if r["finish_position"] == 1 and r["finish_time"] and float(r["finish_time"]) > 0:
                past_rec = r["past_record_time"]
                if past_rec is None or float(r["finish_time"]) < float(past_rec) - 0.001:
                    is_rec = True

            raw_f_time = format_finish_time(r["finish_time"])
            if is_rec:
                f_time_display = f"<span style='color: #ef4444; font-weight: bold;'>R</span> <span style='color: #facc15; font-weight: bold;'>{raw_f_time}</span>"
            elif r["finish_position"] == 1:
                f_time_display = f"<span style='color: #facc15; font-weight: bold;'>{raw_f_time}</span>"
            else:
                f_time_display = raw_f_time

            l_3f = f"{r['last_3f']:.1f}" if r["last_3f"] else "-"
            prz = f"{r['prize_awarded'] // 10000:,}万" if r["prize_awarded"] else "0"

            # グレード色分けアイテム (7色)
            bg_col, fg_col = GRADE_COLOR_MAP.get(grade, ("#334155", "#ffffff"))
            grade_item = QTableWidgetItem(grade)
            grade_item.setBackground(QColor(bg_col))
            grade_item.setForeground(QColor(fg_col))

            time_item = QTableWidgetItem(f_time_display)

            items = [
                QTableWidgetItem(y_w), QTableWidgetItem(track), QTableWidgetItem(r_name),
                grade_item, QTableWidgetItem(surf), QTableWidgetItem(dist),
                QTableWidgetItem(starters), QTableWidgetItem(pop_str), QTableWidgetItem(pos), time_item,
                QTableWidgetItem(l_3f), QTableWidgetItem(prz)
            ]
            for c, itm in enumerate(items):
                itm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if r["finish_position"] == 1 and c not in (3, 9):
                    itm.setForeground(Qt.GlobalColor.yellow)
                self.table_history.setItem(idx, c, itm)

            # 12: 結果ボタン
            r_id = r["race_id"]
            btn_res = QPushButton("🏁 結果")
            btn_res.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 11px; font-weight: bold; padding: 2px 4px; border: 1px solid #0284c7; border-radius: 3px;")
            btn_res.clicked.connect(lambda checked, rid=r_id: self._open_race_result(rid))
            self.table_history.setCellWidget(idx, 12, btn_res)

            # 13: 動画ボタン
            btn_replay = QPushButton("🎬 動画")
            btn_replay.setStyleSheet("background-color: #1e293b; color: #c084fc; font-size: 11px; font-weight: bold; padding: 2px 4px; border: 1px solid #9333ea; border-radius: 3px;")
            btn_replay.clicked.connect(lambda checked, rid=r_id: self._open_race_replay(rid))
            self.table_history.setCellWidget(idx, 13, btn_replay)

        # 2. 血統表の描画
        ancestors_tree = self.pedigree_builder.get_ancestors_tree(self.horse_id, depth=5)
        if ancestors_tree:
            self.pedigree_widget.set_tree_data(ancestors_tree)

        # 3. 成績集計
        self._calculate_stats_summary(results, horse)

    def _calculate_stats_summary(self, results: List[Any], horse: Horse) -> None:
        # 1-1. レース合計
        self._populate_stats_row(self.tbl_total, 0, results, col_offset=0)

        # 1-2. コース別成績 (芝、ダート)
        turf_runs = [r for r in results if r["surface"] == "turf"]
        dirt_runs = [r for r in results if r["surface"] == "dirt"]
        self._populate_stats_row(self.tbl_course, 0, turf_runs, col_offset=1)
        self._populate_stats_row(self.tbl_course, 1, dirt_runs, col_offset=1)

        # 2. 距離別成績 (9行、col_offset=2)
        for idx, (_, _, fn) in enumerate(self.dist_rows_def):
            matched = [r for r in results if fn(r["surface"], r["distance"])]
            self._populate_stats_row(self.tbl_dist, idx, matched, col_offset=2)

        # 3. グレード別成績 (8行、col_offset=1)
        for idx, glbl in enumerate(self.grade_labels):
            matched = []
            for r in results:
                g = r["grade"]
                if glbl == "新馬・未勝利" and g in ("NEWCOMER", "MAIDEN", "新馬", "未勝利"):
                    matched.append(r)
                elif glbl == "1勝クラス" and g in ("COND_1W", "1勝クラス"):
                    matched.append(r)
                elif glbl == "2勝クラス" and g in ("COND_2W", "2勝クラス"):
                    matched.append(r)
                elif glbl == "3勝クラス" and g in ("COND_3W", "3勝クラス"):
                    matched.append(r)
                elif glbl == "リステッド" and g in ("L", "OP", "リステッド", "オープン"):
                    matched.append(r)
                elif glbl == "G3" and g == "G3":
                    matched.append(r)
                elif glbl == "G2" and g == "G2":
                    matched.append(r)
                elif glbl == "G1" and g == "G1":
                    matched.append(r)

            self._populate_stats_row(self.tbl_grade, idx, matched, col_offset=1)

        # 4. 人気別成績 (4行、col_offset=1)
        for idx, plbl in enumerate(self.pop_labels):
            matched = []
            for r in results:
                pop = r["popularity"] if "popularity" in r.keys() else 0
                if plbl == "1番人気" and pop == 1:
                    matched.append(r)
                elif plbl == "2番人気" and pop == 2:
                    matched.append(r)
                elif plbl == "3番人気" and pop == 3:
                    matched.append(r)
                elif plbl == "4番人気以下" and pop >= 4:
                    matched.append(r)

            self._populate_stats_row(self.tbl_pop, idx, matched, col_offset=1)

    def _on_ancestor_clicked(self, ancestor_id: int) -> None:
        """祖先馬クリック時にその馬の詳細へ切り替え"""
        if ancestor_id and ancestor_id != self.horse_id:
            self.horse_id = ancestor_id
            self._load_horse_data()

    def _open_race_result(self, race_id: int) -> None:
        """指定したレースの結果詳細ダイアログを開く"""
        from src.gui.views.race_dialogs import RaceResultDialog
        dlg = RaceResultDialog(self.db, race_id, parent=self)
        dlg.exec()

    def _open_race_replay(self, race_id: int) -> None:
        """指定したレースのリプレイダイアログを開く"""
        from src.gui.views.race_dialogs import RaceViewDialog
        dlg = RaceViewDialog(self.db, race_id, parent=self)
        dlg.exec()

