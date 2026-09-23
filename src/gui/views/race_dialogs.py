"""
レース閲覧・レース結果表示ダイアログ (RaceViewDialog / RaceResultDialog)
- レースボタン押下時: 2Dレース閲覧ダイアログ（別ウィンドウ）
- レース結果ボタン押下時: 確定着順・詳細結果ダイアログ（別ウィンドウ）
"""

from __future__ import annotations

from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.db.database import Database, get_db
from src.gui.views.race_replay_view import RaceReplayView
from src.race.engine import clean_race_name
from src.race.track import check_is_course_record



def format_finish_time(seconds: float) -> str:
    """走破タイムを分:秒.厘 (例: 1:33.4) 形式にフォーマット"""
    if seconds <= 0:
        return "--:--.-"
    m = int(seconds // 60)
    s = seconds - (m * 60)
    return f"{m}:{s:04.1f}"


class RaceViewDialog(QDialog):
    """2Dレース閲覧ダイアログ（別ウィンドウ）"""

    def __init__(self, db: Database, race_id: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.race_id = race_id
        self.setWindowTitle("🏇 レース閲覧 (2Dシミュレーション)")
        self.setWindowState(Qt.WindowState.WindowMaximized)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # RaceReplayViewをダイアログ内に配置
        self.replay_view = RaceReplayView(self.db, parent=self)
        self.replay_view.load_race_by_id(race_id)
        layout.addWidget(self.replay_view)

        # 閉じるボタン
        btn_close = QPushButton("閉じる")
        btn_close.setStyleSheet("background-color: #343a40; font-weight: bold; padding: 6px 16px;")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)


class RaceResultDialog(QDialog):
    """レース結果ダイアログ（別ウィンドウ）"""

    def __init__(self, db: Database, race_id: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.race_id = race_id
        self.setWindowTitle("🏁 レース結果・確定着順")
        self.resize(980, 520)

        self._init_ui()
        self._load_results()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ヘッダー情報
        self.lbl_race_title = QLabel("レース結果")
        self.lbl_race_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #fcc419;")
        layout.addWidget(self.lbl_race_title)

        self.lbl_race_cond = QLabel("")
        self.lbl_race_cond.setStyleSheet("font-size: 13px; color: #adb5bd;")
        layout.addWidget(self.lbl_race_cond)

        # 結果テーブル
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "着順", "馬番", "馬名", "性齢", "騎手", "オッズ/人気", "タイム", "着差", "上り3F", "賞金"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 55)   # 着順
        self.table.setColumnWidth(1, 45)   # 馬番
        self.table.setColumnWidth(2, 230)  # 馬名 (全文字最後まで確実に表示)
        self.table.setColumnWidth(3, 50)   # 性齢
        self.table.setColumnWidth(4, 90)   # 騎手
        self.table.setColumnWidth(5, 125)  # オッズ/人気
        self.table.setColumnWidth(6, 75)   # タイム
        self.table.setColumnWidth(7, 65)   # 着差
        self.table.setColumnWidth(8, 65)   # 上り3F
        self.table.setColumnWidth(9, 85)   # 賞金
        header.setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._on_cell_clicked)
        from src.gui.widgets.html_delegate import HTMLDelegate
        self.table.setItemDelegateForColumn(6, HTMLDelegate(self.table))
        layout.addWidget(self.table)

        # フッターボタン
        btn_layout = QHBoxLayout()
        hint = QLabel("※ 馬名をダブルクリックすると競走馬の詳細（血統表・成績）を表示します")
        hint.setStyleSheet("color: #868e96; font-size: 11px;")
        btn_layout.addWidget(hint)
        btn_layout.addStretch()

        btn_close = QPushButton("閉じる")
        btn_close.setStyleSheet("background-color: #343a40; font-weight: bold; padding: 6px 18px;")
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def _load_results(self) -> None:
        with self.db.session() as conn:
            rc = conn.execute("SELECT * FROM races WHERE race_id = ?", (self.race_id,)).fetchone()
            if not rc:
                self.lbl_race_title.setText("指定されたレースが見つかりません。")
                return

            surf_jp = "芝" if rc["surface"] == "turf" else "ダート"
            r_name = clean_race_name(rc["name"])
            self.lbl_race_title.setText(f"{r_name} ({rc['grade']})")
            self.lbl_race_cond.setText(
                f"{rc['year']}年 {rc['month']}月 第{((rc['week']-1)%4)+1}週 | {rc['track_id']} {surf_jp} {rc['distance']}m | 天候: 晴 / 馬場: 良"
            )

            query = """
                SELECT 
                    res.finish_position,
                    res.gate_number,
                    res.horse_id,
                    h.name AS horse_name,
                    h.sex,
                    h.age,
                    j.name AS jockey_name,
                    res.odds,
                    res.finish_time,
                    res.margin,
                    res.time_diff,
                    res.last_3f,
                    res.prize_awarded
                FROM results res
                JOIN horses h ON res.horse_id = h.horse_id
                LEFT JOIN jockeys j ON res.jockey_id = j.jockey_id
                WHERE res.race_id = ?
                ORDER BY res.finish_position ASC
            """
            rows = conn.execute(query, (self.race_id,)).fetchall()

            # レコード判定 (共通関数を用いて初開催時・更新時を判定)
            winner_time = float(rows[0]["finish_time"]) if rows else 0.0
            is_record = check_is_course_record(
                conn=conn,
                track_id=rc["track_id"],
                surface=rc["surface"],
                distance=rc["distance"],
                finish_time=winner_time,
                year=rc["year"],
                week=rc["week"],
                race_id=rc["race_id"],
            )


        self.table.setRowCount(len(rows))
        sex_map = {"colt": "牡", "filly": "牝", "horse": "牡", "mare": "牝", "gelding": "セ"}

        # オッズから人気順を算出
        odds_list = []
        for r in rows:
            val = float(r["odds"]) if (r["odds"] and float(r["odds"]) > 0) else 999.9
            odds_list.append((val, r["horse_id"]))
        sorted_by_odds = sorted(odds_list, key=lambda x: x[0])
        popularity_map = {hid: pop for pop, (_, hid) in enumerate(sorted_by_odds, start=1)}

        for r_idx, r in enumerate(rows):
            pos_str = f"{r['finish_position']}着"
            gate_str = str(r["gate_number"])
            h_name = r["horse_name"]
            sex_age = f"{sex_map.get(r['sex'], '')}{r['age']}"
            j_name = r["jockey_name"] or "未定"
            pop = popularity_map.get(r["horse_id"], r_idx + 1)
            pop_odds = f"{r['odds']:.1f}倍 ({pop}人気)" if r["odds"] else "-"
            raw_f_time = format_finish_time(r["finish_time"])
            if r_idx == 0 and is_record:
                f_time_display = f"<span style='color: #ef4444; font-weight: bold;'>R</span> <span style='color: #38bdf8; font-weight: bold;'>{raw_f_time}</span>"
            elif r_idx == 0:
                f_time_display = f"<span style='color: #38bdf8; font-weight: bold;'>{raw_f_time}</span>"
            else:
                f_time_display = raw_f_time

            # 着差
            margin_str = r["margin"] if r["margin"] else ("-" if r["finish_position"] == 1 else f"{r['time_diff']:.1f}s")
            last_3f = f"{r['last_3f']:.1f}" if r["last_3f"] else "--.-"
            prize = f"{r['prize_awarded'] // 10000:,}万" if r["prize_awarded"] else "0"

            time_item = QTableWidgetItem(f_time_display)

            items = [
                QTableWidgetItem(pos_str),
                QTableWidgetItem(gate_str),
                QTableWidgetItem(h_name),
                QTableWidgetItem(sex_age),
                QTableWidgetItem(j_name),
                QTableWidgetItem(pop_odds),
                time_item,
                QTableWidgetItem(margin_str),
                QTableWidgetItem(last_3f),
                QTableWidgetItem(prize),
            ]

            # horse_idを保持
            items[2].setData(Qt.ItemDataRole.UserRole, r["horse_id"])

            for c_idx, item in enumerate(items):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if r_idx == 0 and c_idx != 6:
                    item.setForeground(Qt.GlobalColor.yellow)
                self.table.setItem(r_idx, c_idx, item)

    def _on_cell_clicked(self, row: int, col: int) -> None:
        item = self.table.item(row, 2)
        if item:
            horse_id = item.data(Qt.ItemDataRole.UserRole)
            if horse_id:
                from src.gui.views.horse_detail_dialog import HorseDetailDialog
                dlg = HorseDetailDialog(self.db, horse_id, parent=self)
                dlg.exec()


class RaceEntryDialog(QDialog):
    """出馬表・出走馬一覧ダイアログ（別ウィンドウ）"""

    def __init__(self, db: Database, race_id: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.race_id = race_id
        self.setWindowTitle("📋 出馬表・出走馬一覧")
        self.resize(980, 520)

        self._init_ui()
        self._load_entries()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ヘッダー情報
        self.lbl_race_title = QLabel("出馬表")
        self.lbl_race_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #38bdf8;")
        layout.addWidget(self.lbl_race_title)

        self.lbl_race_cond = QLabel("")
        self.lbl_race_cond.setStyleSheet("font-size: 13px; color: #adb5bd;")
        layout.addWidget(self.lbl_race_cond)

        # 出馬表テーブル
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "枠", "馬番", "馬名", "性齢", "騎手", "調教師", "脚質", "予想オッズ", "人気"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 45)   # 枠
        self.table.setColumnWidth(1, 50)   # 馬番
        self.table.setColumnWidth(2, 230)  # 馬名
        self.table.setColumnWidth(3, 60)   # 性齢
        self.table.setColumnWidth(4, 100)  # 騎手
        self.table.setColumnWidth(5, 100)  # 調教師
        self.table.setColumnWidth(6, 65)   # 脚質
        self.table.setColumnWidth(7, 95)   # 予想オッズ
        self.table.setColumnWidth(8, 70)   # 人気
        header.setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._on_cell_clicked)
        layout.addWidget(self.table)

        # フッターボタン
        btn_layout = QHBoxLayout()
        hint = QLabel("※ 馬名をダブルクリックすると競走馬の詳細（血統表・成績）を表示します")
        hint.setStyleSheet("color: #868e96; font-size: 11px;")
        btn_layout.addWidget(hint)
        btn_layout.addStretch()

        btn_close = QPushButton("閉じる")
        btn_close.setStyleSheet("background-color: #343a40; font-weight: bold; padding: 6px 18px;")
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def _load_entries(self) -> None:
        from src.gui.widgets.track_canvas import JRA_BRACKET_COLORS
        from src.race.engine import get_jra_bracket
        from PyQt6.QtGui import QColor

        with self.db.session() as conn:
            rc = conn.execute("SELECT * FROM races WHERE race_id = ?", (self.race_id,)).fetchone()
            if not rc:
                self.lbl_race_title.setText("指定されたレースが見つかりません。")
                return

            surf_jp = "芝" if rc["surface"] == "turf" else "ダート"
            r_name = clean_race_name(rc["name"])
            self.lbl_race_title.setText(f"{r_name} ({rc['grade']})")
            self.lbl_race_cond.setText(
                f"{rc['year']}年 {rc['month']}月 第{((rc['week']-1)%4)+1}週 | {rc['track_id']} {surf_jp} {rc['distance']}m [{rc['full_gate']}頭立]"
            )

            query = """
                SELECT res.horse_id, res.gate_number, res.odds,
                       h.name AS horse_name, h.sex, h.age, h.running_style,
                       j.name AS jockey_name,
                       t.name AS trainer_name
                FROM results res
                JOIN horses h ON res.horse_id = h.horse_id
                LEFT JOIN jockeys j ON res.jockey_id = j.jockey_id
                LEFT JOIN trainers t ON h.trainer_id = t.trainer_id
                WHERE res.race_id = ?
                ORDER BY res.gate_number ASC
            """
            rows = conn.execute(query, (self.race_id,)).fetchall()

        self.table.setRowCount(len(rows))
        sex_map = {"colt": "牡", "filly": "牝", "horse": "牡", "mare": "牝", "gelding": "セ"}
        style_map = {"escape": "逃げ", "leading": "先行", "between": "差し", "closing": "追込"}

        # オッズから人気順を算出
        odds_list = []
        for r in rows:
            odds_val = float(r["odds"]) if r["odds"] else 999.9
            odds_list.append((odds_val, r["horse_id"]))
        odds_list.sort(key=lambda x: x[0])
        popularity_map = {h_id: idx + 1 for idx, (_, h_id) in enumerate(odds_list)}

        total_h = len(rows)

        for r_idx, r in enumerate(rows):
            g_num = r["gate_number"] if r["gate_number"] else (r_idx + 1)
            bracket = get_jra_bracket(g_num, total_h)
            bg_col, fg_col, _, _ = JRA_BRACKET_COLORS.get(bracket, ("#ffffff", "#000000", "#94a3b8", ""))

            # 枠番アイテム (枠色着色)
            bracket_item = QTableWidgetItem(f"{bracket}")
            bracket_item.setBackground(QColor(bg_col))
            bracket_item.setForeground(QColor(fg_col))

            # 馬番アイテム
            gate_item = QTableWidgetItem(str(g_num))
            gate_item.setBackground(QColor(bg_col))
            gate_item.setForeground(QColor(fg_col))

            h_name = r["horse_name"]
            sex_age = f"{sex_map.get(r['sex'], '')}{r['age']}"
            j_name = r["jockey_name"] or "未定"
            t_name = r["trainer_name"] or "未定"
            style_str = style_map.get(r["running_style"], "-")
            pop = popularity_map.get(r["horse_id"], r_idx + 1)
            odds_str = f"{r['odds']:.1f}倍" if r["odds"] else "--"
            pop_str = f"{pop}人気"

            odds_item = QTableWidgetItem(odds_str)
            odds_item.setForeground(Qt.GlobalColor.yellow)

            items = [
                bracket_item,
                gate_item,
                QTableWidgetItem(h_name),
                QTableWidgetItem(sex_age),
                QTableWidgetItem(j_name),
                QTableWidgetItem(t_name),
                QTableWidgetItem(style_str),
                odds_item,
                QTableWidgetItem(pop_str),
            ]

            # horse_idを保持
            items[2].setData(Qt.ItemDataRole.UserRole, r["horse_id"])

            for c_idx, item in enumerate(items):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r_idx, c_idx, item)

    def _on_cell_clicked(self, row: int, col: int) -> None:
        item = self.table.item(row, 2)
        if item:
            horse_id = item.data(Qt.ItemDataRole.UserRole)
            if horse_id:
                from src.gui.views.horse_detail_dialog import HorseDetailDialog
                dlg = HorseDetailDialog(self.db, horse_id, parent=self, exclude_race_id=self.race_id)
                dlg.exec()

