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
from src.gui.widgets.pedigree_widget import PedigreeWidget
from src.models.horse import Horse
from src.views.pedigree_builder import PedigreeBuilder


def format_finish_time(seconds: float) -> str:
    """走破タイムを分:秒.厘形式に変換"""
    if seconds <= 0:
        return "--:--.-"
    m = int(seconds // 60)
    s = seconds - (m * 60)
    return f"{m}:{s:04.1f}"


class HorseDetailDialog(QDialog):
    """競走馬詳細ウィンドウ"""

    def __init__(self, db: Database, horse_id: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.horse_id = horse_id
        self.pedigree_builder = PedigreeBuilder(db)

        self.setWindowTitle("🐎 競走馬詳細・血統・成績")
        self.resize(960, 680)

        self._init_ui()
        self._load_horse_data()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. ヘッダー概要カード
        self.profile_card = QFrame()
        self.profile_card.setStyleSheet("background-color: #1e293b; border-radius: 8px; padding: 12px;")
        card_layout = QGridLayout(self.profile_card)

        self.lbl_name = QLabel("競走馬名")
        self.lbl_name.setStyleSheet("font-size: 22px; font-weight: bold; color: #38bdf8;")
        card_layout.addWidget(self.lbl_name, 0, 0, 1, 2)

        self.lbl_trainer = QLabel("所属厩舎: -")
        self.lbl_breeder = QLabel("生産牧場: -")
        self.lbl_owner = QLabel("馬主: -")
        self.lbl_jockey = QLabel("主戦騎手: -")
        self.lbl_aptitude = QLabel("適性: -")
        self.lbl_earnings = QLabel("生涯賞金: -")

        for lbl in (self.lbl_trainer, self.lbl_breeder, self.lbl_owner, self.lbl_jockey, self.lbl_aptitude, self.lbl_earnings):
            lbl.setStyleSheet("font-size: 13px; color: #cbd5e1;")

        card_layout.addWidget(self.lbl_trainer, 1, 0)
        card_layout.addWidget(self.lbl_jockey, 1, 1)
        card_layout.addWidget(self.lbl_breeder, 2, 0)
        card_layout.addWidget(self.lbl_owner, 2, 1)
        card_layout.addWidget(self.lbl_aptitude, 3, 0)
        card_layout.addWidget(self.lbl_earnings, 3, 1)

        main_layout.addWidget(self.profile_card)

        # 2. タブウィジェット
        self.tabs = QTabWidget()

        # タブA: 出走レース全履歴
        self.history_tab = QWidget()
        hist_layout = QVBoxLayout(self.history_tab)
        self.table_history = QTableWidget()
        self.table_history.setColumnCount(11)
        self.table_history.setHorizontalHeaderLabels([
            "年・週", "競馬場", "レース名", "グレード", "馬場", "距離", "頭数", "着順", "タイム", "上り3F", "賞金"
        ])
        self.table_history.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
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

        # タブC: 成績集計（通算・重賞・距離別・芝ダート別・競馬場別）
        self.stats_tab = QWidget()
        stats_layout = QVBoxLayout(self.stats_tab)
        self.scroll_stats = QScrollArea()
        self.scroll_stats.setWidgetResizable(True)
        stats_content = QWidget()
        self.stats_grid = QVBoxLayout(stats_content)

        self.lbl_record_overall = QLabel("通算成績: -")
        self.lbl_record_graded = QLabel("重賞内訳: -")
        self.lbl_record_surface = QLabel("馬場別成績: -")
        self.lbl_record_distance = QLabel("距離別成績: -")
        self.lbl_record_track = QLabel("競馬場別成績: -")

        for lbl in (self.lbl_record_overall, self.lbl_record_graded, self.lbl_record_surface, self.lbl_record_distance, self.lbl_record_track):
            lbl.setStyleSheet("font-size: 13px; color: #f1f5f9; padding: 4px;")
            lbl.setWordWrap(True)

        grp1 = QGroupBox("【通算成績 & 重賞内訳】")
        l1 = QVBoxLayout(grp1)
        l1.addWidget(self.lbl_record_overall)
        l1.addWidget(self.lbl_record_graded)
        self.stats_grid.addWidget(grp1)

        grp2 = QGroupBox("【馬場別（芝・ダート）成績】")
        l2 = QVBoxLayout(grp2)
        l2.addWidget(self.lbl_record_surface)
        self.stats_grid.addWidget(grp2)

        grp3 = QGroupBox("【距離別成績】")
        l3 = QVBoxLayout(grp3)
        l3.addWidget(self.lbl_record_distance)
        self.stats_grid.addWidget(grp3)

        grp4 = QGroupBox("【主要競馬場別成績】")
        l4 = QVBoxLayout(grp4)
        l4.addWidget(self.lbl_record_track)
        self.stats_grid.addWidget(grp4)

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

            # レース履歴
            query_results = """
                SELECT 
                    r.year, r.week, r.track_id, r.name AS race_name, r.grade, r.surface, r.distance, r.full_gate,
                    res.finish_position, res.finish_time, res.last_3f, res.prize_awarded
                FROM results res
                JOIN races r ON res.race_id = r.race_id
                WHERE res.horse_id = ?
                ORDER BY r.year ASC, r.week ASC
            """
            results = conn.execute(query_results, (self.horse_id,)).fetchall()

        # ヘッダー情報セット
        sex_map = {"colt": "牡", "filly": "牝", "horse": "牡", "mare": "牝", "gelding": "セ"}
        sex_str = sex_map.get(horse.sex.value if hasattr(horse.sex, "value") else horse.sex, "")
        surf_jp = "芝" if horse.surface_aptitude == "turf" else ("ダート" if horse.surface_aptitude == "dirt" else "芝・ダート兼用")
        mstn_str = horse.mstn_type.value if hasattr(horse.mstn_type, "value") else str(horse.mstn_type)

        self.lbl_name.setText(f"{horse.name} ({sex_str}{horse.age}歳・{mstn_str})")
        self.lbl_trainer.setText(f"所属厩舎: {trainer_name}")
        self.lbl_breeder.setText(f"生産牧場: {breeder_name}")
        self.lbl_owner.setText(f"馬主: {owner_name}")
        self.lbl_jockey.setText(f"主戦騎手: {jockey_name}")
        self.lbl_aptitude.setText(f"適性: {surf_jp} / {horse.apt_distance_min}m〜{horse.apt_distance_max}m (幅{horse.apt_distance_range}m)")
        self.lbl_earnings.setText(f"生涯獲得賞金: {horse.prize_money // 10000:,} 万円")

        # 1. 履歴テーブルの反映
        self.table_history.setRowCount(len(results))
        for idx, r in enumerate(results):
            y_w = f"{r['year']}年 {((r['week']-1)%4)+1}週"
            track = r["track_id"]
            r_name = r["race_name"]
            grade = r["grade"]
            surf = "芝" if r["surface"] == "turf" else "ダート"
            dist = f"{r['distance']}m"
            starters = f"{r['full_gate']}頭"
            pos = f"{r['finish_position']}着"
            f_time = format_finish_time(r["finish_time"])
            l_3f = f"{r['last_3f']:.1f}" if r["last_3f"] else "-"
            prz = f"{r['prize_awarded'] // 10000:,}万" if r["prize_awarded"] else "0"

            items = [
                QTableWidgetItem(y_w), QTableWidgetItem(track), QTableWidgetItem(r_name),
                QTableWidgetItem(grade), QTableWidgetItem(surf), QTableWidgetItem(dist),
                QTableWidgetItem(starters), QTableWidgetItem(pos), QTableWidgetItem(f_time),
                QTableWidgetItem(l_3f), QTableWidgetItem(prz)
            ]
            for c, itm in enumerate(items):
                itm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if r["finish_position"] == 1:
                    itm.setForeground(Qt.GlobalColor.yellow)
                self.table_history.setItem(idx, c, itm)

        # 2. 血統表の描画
        ancestors_tree = self.pedigree_builder.get_ancestors_tree(self.horse_id, depth=5)
        if ancestors_tree:
            self.pedigree_widget.set_tree_data(ancestors_tree)

        # 3. 成績集計
        self._calculate_stats_summary(results, horse)

    def _calculate_stats_summary(self, results: List[Any], horse: Horse) -> None:
        total_starts = len(results)
        c_1st = sum(1 for r in results if r["finish_position"] == 1)
        c_2nd = sum(1 for r in results if r["finish_position"] == 2)
        c_3rd = sum(1 for r in results if r["finish_position"] == 3)
        c_out = total_starts - (c_1st + c_2nd + c_3rd)

        self.lbl_record_overall.setText(
            f"通算成績: {total_starts}戦 {c_1st}勝 [{c_1st} - {c_2nd} - {c_3rd} - {c_out}]"
        )

        # 重賞内訳
        def count_pos_for_grade(g_name: str) -> str:
            g_runs = [r for r in results if r["grade"] == g_name]
            p1 = sum(1 for r in g_runs if r["finish_position"] == 1)
            p2 = sum(1 for r in g_runs if r["finish_position"] == 2)
            p3 = sum(1 for r in g_runs if r["finish_position"] == 3)
            po = len(g_runs) - (p1 + p2 + p3)
            return f"{p1}-{p2}-{p3}-{po}"

        g1_str = count_pos_for_grade("G1")
        g2_str = count_pos_for_grade("G2")
        g3_str = count_pos_for_grade("G3")
        op_runs = [r for r in results if r["grade"] in ("OP", "L")]
        op_p1 = sum(1 for r in op_runs if r["finish_position"] == 1)
        op_p2 = sum(1 for r in op_runs if r["finish_position"] == 2)
        op_p3 = sum(1 for r in op_runs if r["finish_position"] == 3)
        op_po = len(op_runs) - (op_p1 + op_p2 + op_p3)
        op_str = f"{op_p1}-{op_p2}-{op_p3}-{op_po}"

        self.lbl_record_graded.setText(
            f"G1: [{g1_str}] | G2: [{g2_str}] | G3: [{g3_str}] | OP/L: [{op_str}]"
        )

        # 芝・ダート別
        def count_surface(s_name: str) -> str:
            s_runs = [r for r in results if r["surface"] == s_name]
            p1 = sum(1 for r in s_runs if r["finish_position"] == 1)
            p2 = sum(1 for r in s_runs if r["finish_position"] == 2)
            p3 = sum(1 for r in s_runs if r["finish_position"] == 3)
            po = len(s_runs) - (p1 + p2 + p3)
            return f"{len(s_runs)}戦 [{p1}-{p2}-{p3}-{po}]"

        self.lbl_record_surface.setText(
            f"芝: {count_surface('turf')}    |    ダート: {count_surface('dirt')}"
        )

        # 距離別
        dist_cats = [
            ("短距離 (1000〜1400m)", lambda d: d <= 1400),
            ("マイル (1500〜1600m)", lambda d: 1500 <= d <= 1600),
            ("中距離 (1700〜2200m)", lambda d: 1700 <= d <= 2200),
            ("長距離 (2300m以上)", lambda d: d >= 2300),
        ]
        dist_texts = []
        for cat_name, fn in dist_cats:
            d_runs = [r for r in results if fn(r["distance"])]
            p1 = sum(1 for r in d_runs if r["finish_position"] == 1)
            p2 = sum(1 for r in d_runs if r["finish_position"] == 2)
            p3 = sum(1 for r in d_runs if r["finish_position"] == 3)
            po = len(d_runs) - (p1 + p2 + p3)
            dist_texts.append(f"• {cat_name}: {len(d_runs)}戦 [{p1}-{p2}-{p3}-{po}]")

        self.lbl_record_distance.setText("\n".join(dist_texts))

        # 競馬場別
        tracks_set = sorted(set(r["track_id"] for r in results))
        track_texts = []
        for t in tracks_set:
            t_runs = [r for r in results if r["track_id"] == t]
            p1 = sum(1 for r in t_runs if r["finish_position"] == 1)
            p2 = sum(1 for r in t_runs if r["finish_position"] == 2)
            p3 = sum(1 for r in t_runs if r["finish_position"] == 3)
            po = len(t_runs) - (p1 + p2 + p3)
            track_texts.append(f"{t}: {len(t_runs)}戦 [{p1}-{p2}-{p3}-{po}]")
        self.lbl_record_track.setText("  /  ".join(track_texts) if track_texts else "出走なし")

    def _on_ancestor_clicked(self, ancestor_id: int) -> None:
        """祖先馬クリック時にその馬の詳細へ切り替え"""
        if ancestor_id and ancestor_id != self.horse_id:
            self.horse_id = ancestor_id
            self._load_horse_data()
