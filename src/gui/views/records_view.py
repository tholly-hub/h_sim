"""
競馬場別コースレコード一覧ビュー (RecordsView) & コースレコード推移ダイアログ (RecordHistoryDialog)
- 最先頭に「総合」タブ（全競馬場を通じた距離別・芝ダート別最高レコード一覧）
- 競馬場別タブ（東京、中山、阪神、京都、中京、新潟、福島、小倉、大井、川崎、船橋、盛岡）
- 芝・ダート別、短距離から昇順
- レコード保持馬、父馬、母馬、レース名表示
- 行クリックでコースレコード推移ダイアログ（時系列リスト + m:ss.f タイム推移グラフ）を表示
- 「🏁 レース結果」「🎬 レース動画」ボタン完備
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.ticker as ticker

from src.db.database import Database, get_db
from src.race.engine import clean_race_name


TRACK_LIST = [
    ("ALL", "総合 (全競馬場)"),
    ("TOKYO", "東京"),
    ("NAKAYAMA", "中山"),
    ("HANSHIN", "阪神"),
    ("KYOTO", "京都"),
    ("CHUKYO", "中京"),
    ("NIIGATA", "新潟"),
    ("FUKUSHIMA", "福島"),
    ("KOKURA", "小倉"),
    ("OI", "大井"),
    ("KAWASAKI", "川崎"),
    ("FUNABASHI", "船橋"),
    ("MORIOKA", "盛岡"),
]

TRACK_NAME_MAP = {
    "TOKYO": "東京",
    "NAKAYAMA": "中山",
    "HANSHIN": "阪神",
    "KYOTO": "京都",
    "CHUKYO": "中京",
    "NIIGATA": "新潟",
    "FUKUSHIMA": "福島",
    "KOKURA": "小倉",
    "OI": "大井",
    "KAWASAKI": "川崎",
    "FUNABASHI": "船橋",
    "MORIOKA": "盛岡",
}


def format_finish_time(seconds: float) -> str:
    """走破タイムを分:秒.厘 (例: 1:33.4) 形式にフォーマット"""
    if seconds <= 0:
        return "--:--.-"
    m = int(seconds // 60)
    s = seconds - (m * 60)
    return f"{m}:{s:04.1f}"


class RecordHistoryDialog(QDialog):
    """コースレコード推移ダイアログ（時系列リスト + Matplotlib推移グラフ）"""

    def __init__(
        self,
        db: Database,
        track_id: str,
        surface: str,
        distance: int,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.db = db
        self.track_id = track_id
        self.surface = surface
        self.distance = distance

        track_label = "全競馬場総合" if track_id == "ALL" else TRACK_NAME_MAP.get(track_id, track_id)
        surf_label = "芝" if surface == "turf" else "ダート"
        self.setWindowTitle(f"⏱ レコード推移: {track_label} {surf_label}{distance}m")
        self.resize(750, 600)
        self._init_ui()
        self._load_history()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QDialog { background-color: #0f172a; color: #f8fafc; }
            QTableWidget {
                background-color: #1e293b;
                gridline-color: #334155;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #334155;
                color: #38bdf8;
                font-weight: bold;
                border: 1px solid #475569;
                padding: 4px;
            }
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        track_label = "全競馬場総合" if self.track_id == "ALL" else TRACK_NAME_MAP.get(self.track_id, self.track_id)
        surf_label = "芝" if self.surface == "turf" else "ダート"

        # タイトル
        title_lbl = QLabel(f"📈 コースレコード更新推移: {track_label} {surf_label}{self.distance}m")
        title_lbl.setFont(QFont("Hiragino Sans", 13, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #38bdf8;")
        layout.addWidget(title_lbl)

        # 履歴テーブル
        self.table = QTableWidget()
        headers = ["更新年・週", "競馬場", "タイム", "更新馬名", "性齢", "騎手", "レース名"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setMaximumHeight(200)
        layout.addWidget(self.table)

        # グラフ描画領域
        self.fig = Figure(figsize=(7, 3.5), facecolor="#1e293b")
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        layout.addWidget(self.canvas)

        # 閉じるボタン
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_close = QPushButton("閉じる")
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)

    def _load_history(self) -> None:
        """時系列でのレコード更新履歴を抽出してテーブルとグラフにプロット"""
        with self.db.session() as conn:
            if self.track_id == "ALL":
                sql = """
                    SELECT r.year, r.week, r.track_id, r.name AS race_name,
                           res.finish_time, h.name AS horse_name, h.sex, h.age, j.name AS jockey_name
                    FROM results res
                    JOIN races r ON res.race_id = r.race_id
                    JOIN horses h ON res.horse_id = h.horse_id
                    LEFT JOIN jockeys j ON res.jockey_id = j.jockey_id
                    WHERE res.finish_position = 1 AND r.surface = ? AND r.distance = ? AND res.finish_time > 0
                    ORDER BY r.year ASC, r.week ASC, res.finish_time ASC
                """
                all_winner_rows = conn.execute(sql, (self.surface, self.distance)).fetchall()
            else:
                sql = """
                    SELECT r.year, r.week, r.track_id, r.name AS race_name,
                           res.finish_time, h.name AS horse_name, h.sex, h.age, j.name AS jockey_name
                    FROM results res
                    JOIN races r ON res.race_id = r.race_id
                    JOIN horses h ON res.horse_id = h.horse_id
                    LEFT JOIN jockeys j ON res.jockey_id = j.jockey_id
                    WHERE res.finish_position = 1 AND r.track_id = ? AND r.surface = ? AND r.distance = ? AND res.finish_time > 0
                    ORDER BY r.year ASC, r.week ASC, res.finish_time ASC
                """
                all_winner_rows = conn.execute(sql, (self.track_id, self.surface, self.distance)).fetchall()

        # 時系列順にレコードが更新された瞬間のみを抽出
        history: List[dict] = []
        best_time = float("inf")

        for r in all_winner_rows:
            f_time = float(r["finish_time"])
            if f_time < best_time - 0.001:
                best_time = f_time
                history.append(r)

        # テーブル更新
        self.table.setRowCount(len(history))
        for idx, r in enumerate(history):
            m_num = ((r["week"] - 1) // 4) + 1
            w_num = ((r["week"] - 1) % 4) + 1
            yw_str = f"{r['year']}年{m_num}月{w_num}週"
            t_name = TRACK_NAME_MAP.get(r["track_id"], r["track_id"])
            t_str = format_finish_time(r["finish_time"])
            h_str = r["horse_name"]
            sa_str = f"{r['age']}歳"
            jk_str = r["jockey_name"] or "-"
            rc_str = clean_race_name(r["race_name"])

            self.table.setItem(idx, 0, QTableWidgetItem(yw_str))
            self.table.setItem(idx, 1, QTableWidgetItem(t_name))
            time_item = QTableWidgetItem(t_str)
            time_item.setForeground(QColor("#facc15"))
            time_item.setFont(QFont("Hiragino Sans", 10, QFont.Weight.Bold))
            self.table.setItem(idx, 2, time_item)
            self.table.setItem(idx, 3, QTableWidgetItem(h_str))
            self.table.setItem(idx, 4, QTableWidgetItem(sa_str))
            self.table.setItem(idx, 5, QTableWidgetItem(jk_str))
            self.table.setItem(idx, 6, QTableWidgetItem(rc_str))

        # グラフ描画
        self.ax.clear()
        self.ax.set_facecolor("#1e293b")

        if history:
            labels = [f"{r['year']}年\n{r['horse_name'][:4]}" for r in history]
            times = [float(r["finish_time"]) for r in history]
            x_indices = list(range(len(history)))

            self.ax.plot(x_indices, times, marker="o", color="#38bdf8", linewidth=2.5, markersize=8, label="レコードタイム")

            for i, (x, y) in enumerate(zip(x_indices, times)):
                self.ax.annotate(
                    format_finish_time(y),
                    (x, y),
                    textcoords="offset points",
                    xytext=(0, 8),
                    ha="center",
                    color="#facc15",
                    fontsize=9,
                    fontweight="bold",
                )

            self.ax.set_xticks(x_indices)
            self.ax.set_xticklabels(labels, color="#94a3b8", fontsize=9)
            self.ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda val, pos: format_finish_time(val)))
            self.ax.tick_params(colors="#94a3b8")
            self.ax.grid(True, linestyle="--", alpha=0.3, color="#475569")
            self.ax.invert_yaxis()  # タイムが速い（小さい）ほど上向きに表示
            self.ax.set_title(f"歴代レコードタイム更新推移 (全{len(history)}回更新)", color="#f8fafc", fontsize=11, fontweight="bold")
        else:
            self.ax.text(0.5, 0.5, "レコード履歴データがありません", color="#94a3b8", ha="center", va="center")

        self.fig.tight_layout()
        self.canvas.draw()


class RecordsView(QWidget):
    """競馬場別・総合コースレコード一覧タブ"""

    def __init__(self, db: Optional[Database] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db or get_db()
        self.track_tables: Dict[str, QTableWidget] = {}
        self._init_ui()
        self.refresh_records()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # ヘッダー説明バー
        head_bar = QFrame()
        head_bar.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 6px; padding: 6px 12px;")
        head_layout = QHBoxLayout(head_bar)
        lbl_info = QLabel("🏆 各競馬場・芝ダート別コースレコード一覧（行クリックで推移グラフ・父母血統・結果＆動画完備）")
        lbl_info.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 14px;")
        head_layout.addWidget(lbl_info)

        head_layout.addStretch()

        btn_refresh = QPushButton("🔄 最新化")
        btn_refresh.setStyleSheet("background-color: #0284c7; color: #ffffff; font-weight: bold; padding: 4px 12px; border-radius: 4px;")
        btn_refresh.clicked.connect(self.refresh_records)
        head_layout.addWidget(btn_refresh)
        layout.addWidget(head_bar)

        # 競馬場別タブ (最先頭に総合タブ)
        self.tab_tracks = QTabWidget()
        for track_id, track_name in TRACK_LIST:
            tab_page = QWidget()
            p_layout = QVBoxLayout(tab_page)
            p_layout.setContentsMargins(4, 8, 4, 4)

            table = QTableWidget()
            if track_id == "ALL":
                table.setColumnCount(12)
                table.setHorizontalHeaderLabels([
                    "馬場", "距離", "レコードタイム", "上がり3F", "競馬場", "達成年", "達成馬名", "父馬", "母馬", "レース名", "結果", "動画"
                ])
                table.setColumnWidth(0, 50)   # 馬場
                table.setColumnWidth(1, 60)   # 距離
                table.setColumnWidth(2, 95)   # レコードタイム
                table.setColumnWidth(3, 70)   # 上がり3F
                table.setColumnWidth(4, 70)   # 競馬場
                table.setColumnWidth(5, 65)   # 達成年
                table.setColumnWidth(6, 130)  # 達成馬名
                table.setColumnWidth(7, 120)  # 父馬
                table.setColumnWidth(8, 120)  # 母馬
                table.setColumnWidth(9, 130)  # レース名
                table.setColumnWidth(10, 60)  # 結果
                table.setColumnWidth(11, 60)  # 動画
            else:
                table.setColumnCount(11)
                table.setHorizontalHeaderLabels([
                    "馬場", "距離", "レコードタイム", "上がり3F", "達成年", "達成馬名", "父馬", "母馬", "レース名", "結果", "動画"
                ])
                table.setColumnWidth(0, 50)   # 馬場
                table.setColumnWidth(1, 60)   # 距離
                table.setColumnWidth(2, 95)   # レコードタイム
                table.setColumnWidth(3, 70)   # 上がり3F
                table.setColumnWidth(4, 65)   # 達成年
                table.setColumnWidth(5, 140)  # 達成馬名
                table.setColumnWidth(6, 130)  # 父馬
                table.setColumnWidth(7, 130)  # 母馬
                table.setColumnWidth(8, 140)  # レース名
                table.setColumnWidth(9, 65)   # 結果
                table.setColumnWidth(10, 65)  # 動画

            table.horizontalHeader().setStretchLastSection(False)
            table.setAlternatingRowColors(True)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.cellDoubleClicked.connect(lambda r, c, tid=track_id: self._on_row_clicked(tid, r, c))
            table.cellClicked.connect(lambda r, c, tid=track_id: self._on_row_clicked(tid, r, c))

            p_layout.addWidget(table)
            icon_str = "🌐" if track_id == "ALL" else "📍"
            self.tab_tracks.addTab(tab_page, f"{icon_str} {track_name}")
            self.track_tables[track_id] = table

        layout.addWidget(self.tab_tracks)

    def refresh_records(self) -> None:
        """全競馬場のコースレコードおよび総合レコードを抽出して各タブのテーブルに反映"""
        # 1. 各競馬場別レコード
        query_track = """
            WITH ranked_records AS (
                SELECT 
                    res.race_id,
                    r.track_id,
                    r.surface,
                    r.distance,
                    res.finish_time,
                    res.last_3f,
                    r.year,
                    r.name AS race_name,
                    h.horse_id,
                    h.name AS horse_name,
                    sire.name AS sire_name,
                    dam.name AS dam_name,
                    ROW_NUMBER() OVER (
                        PARTITION BY r.track_id, r.surface, r.distance 
                        ORDER BY res.finish_time ASC, r.year DESC
                    ) AS rn
                FROM results res
                JOIN races r ON res.race_id = r.race_id
                JOIN horses h ON res.horse_id = h.horse_id
                LEFT JOIN horses sire ON h.sire_id = sire.horse_id
                LEFT JOIN horses dam ON h.dam_id = dam.horse_id
                WHERE res.finish_position = 1 AND res.finish_time > 0
            )
            SELECT * FROM ranked_records 
            WHERE rn = 1
            ORDER BY 
                CASE surface WHEN 'turf' THEN 1 ELSE 2 END,
                distance ASC
        """

        # 2. 全競馬場総合レコード (距離・馬場ごとの最速)
        query_all = """
            WITH ranked_all AS (
                SELECT 
                    res.race_id,
                    r.track_id,
                    r.surface,
                    r.distance,
                    res.finish_time,
                    res.last_3f,
                    r.year,
                    r.name AS race_name,
                    h.horse_id,
                    h.name AS horse_name,
                    sire.name AS sire_name,
                    dam.name AS dam_name,
                    ROW_NUMBER() OVER (
                        PARTITION BY r.surface, r.distance 
                        ORDER BY res.finish_time ASC, r.year DESC
                    ) AS rn
                FROM results res
                JOIN races r ON res.race_id = r.race_id
                JOIN horses h ON res.horse_id = h.horse_id
                LEFT JOIN horses sire ON h.sire_id = sire.horse_id
                LEFT JOIN horses dam ON h.dam_id = dam.horse_id
                WHERE res.finish_position = 1 AND res.finish_time > 0
            )
            SELECT * FROM ranked_all 
            WHERE rn = 1
            ORDER BY 
                CASE surface WHEN 'turf' THEN 1 ELSE 2 END,
                distance ASC
        """

        with self.db.session() as conn:
            track_rows = conn.execute(query_track).fetchall()
            all_rows = conn.execute(query_all).fetchall()

        # 総合タブの描画
        self._record_data_map: Dict[str, List[dict]] = {}
        self._record_data_map["ALL"] = all_rows
        tbl_all = self.track_tables["ALL"]
        tbl_all.setRowCount(len(all_rows))
        for idx, r in enumerate(all_rows):
            t_name = TRACK_NAME_MAP.get(r["track_id"], r["track_id"])
            surf_str = "芝" if r["surface"] == "turf" else "ダート"
            dist_str = f"{r['distance']}m"
            rec_time = format_finish_time(r["finish_time"])
            l3f_str = f"{r['last_3f']:.1f}s" if r["last_3f"] else "--.-s"
            year_str = f"{r['year']}年"
            h_name = r["horse_name"] or "-"
            s_name = r["sire_name"] or "-"
            d_name = r["dam_name"] or "-"
            r_name = clean_race_name(r["race_name"]) if r["race_name"] else "-"

            time_item = QTableWidgetItem(rec_time)
            time_item.setForeground(QColor("#facc15"))
            time_item.setFont(QFont("Hiragino Sans", 10, QFont.Weight.Bold))

            items = [
                QTableWidgetItem(surf_str),
                QTableWidgetItem(dist_str),
                time_item,
                QTableWidgetItem(l3f_str),
                QTableWidgetItem(t_name),
                QTableWidgetItem(year_str),
                QTableWidgetItem(h_name),
                QTableWidgetItem(s_name),
                QTableWidgetItem(d_name),
                QTableWidgetItem(r_name),
            ]
            for c_idx, item in enumerate(items):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                tbl_all.setItem(idx, c_idx, item)

            race_id = r["race_id"]
            btn_res = QPushButton("🏁 結果")
            btn_res.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 11px; font-weight: bold; padding: 2px 4px; border: 1px solid #0284c7; border-radius: 3px;")
            btn_res.clicked.connect(lambda checked, rid=race_id: self._open_race_result(rid))
            tbl_all.setCellWidget(idx, 10, btn_res)

            btn_replay = QPushButton("🎬 動画")
            btn_replay.setStyleSheet("background-color: #1e293b; color: #c084fc; font-size: 11px; font-weight: bold; padding: 2px 4px; border: 1px solid #9333ea; border-radius: 3px;")
            btn_replay.clicked.connect(lambda checked, rid=race_id: self._open_race_replay(rid))
            tbl_all.setCellWidget(idx, 11, btn_replay)

        # 各競馬場別テーブルの描画
        grouped: Dict[str, List[dict]] = {tid: [] for tid, _ in TRACK_LIST if tid != "ALL"}
        for r in track_rows:
            tid = r["track_id"]
            if tid in grouped:
                grouped[tid].append(r)

        for tid, table in self.track_tables.items():
            if tid == "ALL":
                continue
            t_rows = grouped.get(tid, [])
            self._record_data_map[tid] = t_rows
            table.setRowCount(len(t_rows))
            for idx, r in enumerate(t_rows):
                surf_str = "芝" if r["surface"] == "turf" else "ダート"
                dist_str = f"{r['distance']}m"
                rec_time = format_finish_time(r["finish_time"])
                l3f_str = f"{r['last_3f']:.1f}s" if r["last_3f"] else "--.-s"
                year_str = f"{r['year']}年"
                h_name = r["horse_name"] or "-"
                s_name = r["sire_name"] or "-"
                d_name = r["dam_name"] or "-"
                r_name = clean_race_name(r["race_name"]) if r["race_name"] else "-"

                time_item = QTableWidgetItem(rec_time)
                time_item.setForeground(QColor("#facc15"))
                time_item.setFont(QFont("Hiragino Sans", 10, QFont.Weight.Bold))

                items = [
                    QTableWidgetItem(surf_str),
                    QTableWidgetItem(dist_str),
                    time_item,
                    QTableWidgetItem(l3f_str),
                    QTableWidgetItem(year_str),
                    QTableWidgetItem(h_name),
                    QTableWidgetItem(s_name),
                    QTableWidgetItem(d_name),
                    QTableWidgetItem(r_name),
                ]
                for c_idx, item in enumerate(items):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(idx, c_idx, item)

                race_id = r["race_id"]
                btn_res = QPushButton("🏁 結果")
                btn_res.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 11px; font-weight: bold; padding: 2px 4px; border: 1px solid #0284c7; border-radius: 3px;")
                btn_res.clicked.connect(lambda checked, rid=race_id: self._open_race_result(rid))
                table.setCellWidget(idx, 9, btn_res)

                btn_replay = QPushButton("🎬 動画")
                btn_replay.setStyleSheet("background-color: #1e293b; color: #c084fc; font-size: 11px; font-weight: bold; padding: 2px 4px; border: 1px solid #9333ea; border-radius: 3px;")
                btn_replay.clicked.connect(lambda checked, rid=race_id: self._open_race_replay(rid))
                table.setCellWidget(idx, 10, btn_replay)

    def _on_row_clicked(self, track_id: str, row: int, col: int) -> None:
        """行クリック時にレコード推移ダイアログを表示（結果・動画ボタン列以外）"""
        limit_col = 10 if track_id == "ALL" else 9
        if col >= limit_col:
            return

        rows = self._record_data_map.get(track_id, [])
        if 0 <= row < len(rows):
            rec = rows[row]
            dlg = RecordHistoryDialog(
                self.db,
                track_id=track_id,
                surface=rec["surface"],
                distance=rec["distance"],
                parent=self,
            )
            dlg.exec()

    def _open_race_result(self, race_id: int) -> None:
        """レース結果ダイアログ表示"""
        from src.gui.views.race_dialogs import RaceResultDialog
        dlg = RaceResultDialog(self.db, race_id, parent=self)
        dlg.exec()

    def _open_race_replay(self, race_id: int) -> None:
        """レースリプレイダイアログ表示"""
        from src.gui.views.race_dialogs import RaceViewDialog
        dlg = RaceViewDialog(self.db, race_id, parent=self)
        dlg.exec()
