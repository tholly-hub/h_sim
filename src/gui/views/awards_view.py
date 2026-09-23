"""
表彰ビュー (AwardsView)
- 独立メインタブ「👑 表彰」
- サブタブ構成:
  1. 👑 JRA賞・年度代表馬＆部門賞 (8大部門カード & 歴代推移一覧)
  2. 🥇 最多勝・最優秀タイトル (最多勝騎手、調教師、馬主、生産牧場、新人騎手、新人調教師)
  3. 🏆 顕彰馬・殿堂・メモリアル (顕彰馬、特別功労、殿堂、メモリアル)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
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
from src.gui.views.horse_detail_dialog import HorseDetailDialog
from src.race.awards import AwardsManager


class AwardsView(QWidget):
    """表彰総合ビュー"""

    def __init__(self, db: Optional[Database] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db or get_db()
        self.awards_mgr = AwardsManager(self.db)
        self._init_ui()
        self.refresh_all()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                font-weight: bold;
                font-size: 13px;
                padding: 7px 16px;
            }
        """)

        # 1. 年度代表馬・各部門賞
        self.tab_horse_awards = self._create_horse_awards_tab()
        self.tabs.addTab(self.tab_horse_awards, "👑 年度代表馬・各部門賞")

        # 2. リーディング・タイトル表彰
        self.tab_leading_awards = self._create_leading_awards_tab()
        self.tabs.addTab(self.tab_leading_awards, "🥇 各種リーディング表彰")

        # 3. 顕彰馬・殿堂・メモリアル
        self.tab_hall_of_fame = self._create_hall_of_fame_tab()
        self.tabs.addTab(self.tab_hall_of_fame, "🏆 顕彰・殿堂・メモリアル")

        main_layout.addWidget(self.tabs)

    def refresh_all(self) -> None:
        """全タブを更新"""
        self._refresh_horse_awards_years()
        self.refresh_horse_awards()
        self._refresh_leading_awards_years()
        self.refresh_leading_awards()
        self.refresh_hall_of_fame()

    # ==========================================
    # 1. 年度代表馬・各部門賞
    # ==========================================
    def _create_horse_awards_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 6px;")
        t_layout = QHBoxLayout(top_bar)
        t_layout.setContentsMargins(10, 6, 10, 6)
        t_layout.setSpacing(12)

        t_layout.addWidget(QLabel("表彰年度:"))
        self.combo_horse_awards_year = QComboBox()
        self.combo_horse_awards_year.currentIndexChanged.connect(self.refresh_horse_awards)
        t_layout.addWidget(self.combo_horse_awards_year)

        t_layout.addStretch()
        layout.addWidget(top_bar)

        # 8部門カード
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(280)
        scroll.setMaximumHeight(320)
        card_container = QWidget()
        self.horse_awards_grid = QGridLayout(card_container)
        self.horse_awards_grid.setContentsMargins(6, 6, 6, 6)
        self.horse_awards_grid.setSpacing(8)
        scroll.setWidget(card_container)
        layout.addWidget(scroll)

        # 歴代推移一覧
        lbl_hist = QLabel("📜 歴代JRA賞・年度代表馬＆各部門賞 推移一覧")
        lbl_hist.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px; margin-top: 4px;")
        layout.addWidget(lbl_hist)

        self.table_horse_awards_hist = QTableWidget()
        self.table_horse_awards_hist.setColumnCount(9)
        self.table_horse_awards_hist.setHorizontalHeaderLabels([
            "年度", "年度代表馬", "最優秀芝馬", "最優秀ダート馬", "最優秀中長距離", "最優秀マイル短距離", "最優秀古馬牝馬", "最優秀2歳牡馬", "最優秀2歳牝馬"
        ])
        h_header = self.table_horse_awards_hist.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_horse_awards_hist.setColumnWidth(0, 55)
        for c in range(1, 9):
            self.table_horse_awards_hist.setColumnWidth(c, 115)
        h_header.setStretchLastSection(True)
        self.table_horse_awards_hist.setAlternatingRowColors(True)
        self.table_horse_awards_hist.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table_horse_awards_hist)

        return widget

    def _refresh_horse_awards_years(self) -> None:
        with self.db.session() as conn:
            rows = conn.execute("SELECT DISTINCT year FROM annual_awards ORDER BY year ASC").fetchall()
            race_years = conn.execute("SELECT DISTINCT year FROM races ORDER BY year ASC").fetchall()

        all_years = sorted(list(set([r["year"] for r in rows] + [r["year"] for r in race_years])), reverse=False)

        cur_year = self.combo_horse_awards_year.currentData()
        self.combo_horse_awards_year.blockSignals(True)
        self.combo_horse_awards_year.clear()
        for y in all_years:
            self.combo_horse_awards_year.addItem(f"{y}年度", y)
        if cur_year is not None:
            idx = self.combo_horse_awards_year.findData(cur_year)
            if idx >= 0:
                self.combo_horse_awards_year.setCurrentIndex(idx)
        elif all_years:
            self.combo_horse_awards_year.setCurrentIndex(len(all_years) - 1)
        self.combo_horse_awards_year.blockSignals(False)

    def refresh_horse_awards(self) -> None:
        sel_year = self.combo_horse_awards_year.currentData()
        if sel_year is None:
            return

        while self.horse_awards_grid.count():
            item = self.horse_awards_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        awards = self.awards_mgr.get_awards_by_year(sel_year)
        award_dict = {a["category"]: a for a in awards}

        cat_order = [
            ("horse_of_the_year", "👑 年度代表馬", "#dc2626"),
            ("best_turf_horse", "🌿 最優秀芝馬", "#16a34a"),
            ("best_dirt_horse", "🏜 最優秀ダート馬", "#d97706"),
            ("best_intermediate_long", "🏇 最優秀中長距離馬", "#2563eb"),
            ("best_sprinter_miler", "⚡ 最優秀マイル・短距離馬", "#0891b2"),
            ("best_older_female", "🌸 最優秀古馬牝馬", "#e11d48"),
            ("best_2yo_colt", "👦 最優秀2歳牡馬", "#4f46e5"),
            ("best_2yo_filly", "👧 最優秀2歳牝馬", "#db2777"),
        ]

        for i, (cat_id, cat_title, border_col) in enumerate(cat_order):
            a_data = award_dict.get(cat_id)
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: #1e293b;
                    border: 2px solid {border_col};
                    border-radius: 8px;
                    padding: 6px;
                }}
            """)
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(6, 4, 6, 4)
            c_lay.setSpacing(2)

            lbl_cat = QLabel(cat_title)
            lbl_cat.setStyleSheet(f"color: {border_col}; font-weight: bold; font-size: 12px;")
            c_lay.addWidget(lbl_cat)

            if a_data:
                h_name = a_data["horse_name"]
                g1_w = a_data["g1_wins"]
                prz = a_data["year_prize"] // 10000
                lbl_name = QLabel(f"🏆 {h_name}")
                lbl_name.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold;")
                c_lay.addWidget(lbl_name)

                lbl_info = QLabel(f"G1: {g1_w}勝 | 賞金: {prz:,}万円")
                lbl_info.setStyleSheet("color: #94a3b8; font-size: 11px;")
                c_lay.addWidget(lbl_info)

                hid = a_data["horse_id"]
                btn_d = QPushButton("馬カルテ")
                btn_d.setStyleSheet("background-color: #334155; color: #38bdf8; font-size: 10px; padding: 2px 4px; border-radius: 3px;")
                btn_d.clicked.connect(lambda checked, h=hid: self._open_horse_detail(h))
                c_lay.addWidget(btn_d, alignment=Qt.AlignmentFlag.AlignRight)
            else:
                lbl_none = QLabel("（選考前 / 該当なし）")
                lbl_none.setStyleSheet("color: #64748b; font-size: 11px;")
                c_lay.addWidget(lbl_none)

            row = i // 4
            col = i % 4
            self.horse_awards_grid.addWidget(card, row, col)

        # 歴代推移
        all_awards = self.awards_mgr.get_horse_of_the_year_history()
        years_map: Dict[int, Dict[str, str]] = {}
        for a in all_awards:
            y = a["year"]
            if y not in years_map:
                years_map[y] = {}
            years_map[y][a["category"]] = a["horse_name"]

        sorted_years = sorted(years_map.keys(), reverse=False)
        self.table_horse_awards_hist.setRowCount(len(sorted_years))

        cat_keys = [
            "horse_of_the_year", "best_turf_horse", "best_dirt_horse",
            "best_intermediate_long", "best_sprinter_miler", "best_older_female",
            "best_2yo_colt", "best_2yo_filly"
        ]

        for r_idx, y in enumerate(sorted_years):
            y_item = QTableWidgetItem(f"{y}年")
            y_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_horse_awards_hist.setItem(r_idx, 0, y_item)

            c_data = years_map[y]
            for c_idx, c_key in enumerate(cat_keys, start=1):
                name = c_data.get(c_key, "-")
                itm = QTableWidgetItem(name)
                itm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if c_key == "horse_of_the_year" and name != "-":
                    itm.setForeground(QColor("#facc15"))
                    f = itm.font()
                    f.setBold(True)
                    itm.setFont(f)
                self.table_horse_awards_hist.setItem(r_idx, c_idx, itm)

    # ==========================================
    # 2. 各種リーディング・タイトル表彰
    # ==========================================
    def _create_leading_awards_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 6px;")
        t_layout = QHBoxLayout(top_bar)
        t_layout.setContentsMargins(10, 6, 10, 6)
        t_layout.setSpacing(12)

        t_layout.addWidget(QLabel("表彰年度:"))
        self.combo_leading_awards_year = QComboBox()
        self.combo_leading_awards_year.currentIndexChanged.connect(self.refresh_leading_awards)
        t_layout.addWidget(self.combo_leading_awards_year)

        t_layout.addStretch()
        layout.addWidget(top_bar)

        # 6大リーディングカード (2行 × 3列)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(240)
        scroll.setMaximumHeight(270)
        card_container = QWidget()
        self.leading_awards_grid = QGridLayout(card_container)
        self.leading_awards_grid.setContentsMargins(6, 6, 6, 6)
        self.leading_awards_grid.setSpacing(8)
        scroll.setWidget(card_container)
        layout.addWidget(scroll)

        # 歴代リーディング推移一覧
        lbl_hist = QLabel("📜 歴代 各部門リーディング＆新人賞 推移一覧")
        lbl_hist.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px; margin-top: 4px;")
        layout.addWidget(lbl_hist)

        self.table_leading_hist = QTableWidget()
        self.table_leading_hist.setColumnCount(7)
        self.table_leading_hist.setHorizontalHeaderLabels([
            "年度", "最多勝騎手", "最多勝調教師", "最多勝馬主", "最多勝生産牧場", "最多勝新人騎手", "最多勝新人調教師"
        ])
        h_header = self.table_leading_hist.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_leading_hist.setColumnWidth(0, 60)
        for c in range(1, 7):
            self.table_leading_hist.setColumnWidth(c, 130)
        h_header.setStretchLastSection(True)
        self.table_leading_hist.setAlternatingRowColors(True)
        self.table_leading_hist.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table_leading_hist)

        return widget

    def _refresh_leading_awards_years(self) -> None:
        with self.db.session() as conn:
            rows = conn.execute("SELECT DISTINCT year FROM races ORDER BY year ASC").fetchall()
        years = [r["year"] for r in rows]

        cur_year = self.combo_leading_awards_year.currentData()
        self.combo_leading_awards_year.blockSignals(True)
        self.combo_leading_awards_year.clear()
        for y in years:
            self.combo_leading_awards_year.addItem(f"{y}年度", y)
        if cur_year is not None:
            idx = self.combo_leading_awards_year.findData(cur_year)
            if idx >= 0:
                self.combo_leading_awards_year.setCurrentIndex(idx)
        elif years:
            self.combo_leading_awards_year.setCurrentIndex(len(years) - 1)
        self.combo_leading_awards_year.blockSignals(False)

    def refresh_leading_awards(self) -> None:
        sel_year = self.combo_leading_awards_year.currentData()
        if sel_year is None:
            return

        while self.leading_awards_grid.count():
            item = self.leading_awards_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # 当該年度の各リーディング1位・新人賞を算出
        leaders = self._calc_annual_leaders(sel_year)

        card_defs = [
            ("jockey", "🏇 最多勝騎手", leaders.get("jockey"), "#3b82f6"),
            ("trainer", "📋 最多勝調教師", leaders.get("trainer"), "#10b981"),
            ("owner", "👑 最多勝馬主", leaders.get("owner"), "#f59e0b"),
            ("breeder", "🏡 最多勝生産牧場", leaders.get("breeder"), "#8b5cf6"),
            ("rookie_jockey", "🌱 最多勝新人騎手", leaders.get("rookie_jockey"), "#06b6d4"),
            ("rookie_trainer", "🌱 最多勝新人調教師", leaders.get("rookie_trainer"), "#ec4899"),
        ]

        for i, (key, title, data, col) in enumerate(card_defs):
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: #1e293b;
                    border: 2px solid {col};
                    border-radius: 8px;
                    padding: 6px;
                }}
            """)
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(6, 4, 6, 4)
            c_lay.setSpacing(2)

            lbl_t = QLabel(title)
            lbl_t.setStyleSheet(f"color: {col}; font-weight: bold; font-size: 12px;")
            c_lay.addWidget(lbl_t)

            if data:
                lbl_name = QLabel(f"🏆 {data['name']}")
                lbl_name.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold;")
                c_lay.addWidget(lbl_name)

                lbl_info = QLabel(f"{data['wins']}勝 | 賞金: {data['prize'] // 10000:,}万円")
                lbl_info.setStyleSheet("color: #94a3b8; font-size: 11px;")
                c_lay.addWidget(lbl_info)
            else:
                lbl_none = QLabel("（該当なし）")
                lbl_none.setStyleSheet("color: #64748b; font-size: 11px;")
                c_lay.addWidget(lbl_none)

            row = i // 3
            col_idx = i % 3
            self.leading_awards_grid.addWidget(card, row, col_idx)

        # 歴代推移
        with self.db.session() as conn:
            years = [r["year"] for r in conn.execute("SELECT DISTINCT year FROM races ORDER BY year ASC").fetchall()]

        self.table_leading_hist.setRowCount(len(years))
        for r_idx, y in enumerate(years):
            y_leaders = self._calc_annual_leaders(y)
            self.table_leading_hist.setItem(r_idx, 0, QTableWidgetItem(f"{y}年"))

            keys = ["jockey", "trainer", "owner", "breeder", "rookie_jockey", "rookie_trainer"]
            for c_idx, k in enumerate(keys, start=1):
                ld = y_leaders.get(k)
                txt = f"{ld['name']} ({ld['wins']}勝)" if ld else "-"
                itm = QTableWidgetItem(txt)
                itm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_leading_hist.setItem(r_idx, c_idx, itm)

    def _calc_annual_leaders(self, year: int) -> Dict[str, Optional[Dict[str, Any]]]:
        """指定年度の各リーディング1位および新人賞を算出"""
        res = {}
        with self.db.session() as conn:
            # 騎手
            j_row = conn.execute("""
                SELECT j.name, COUNT(r.result_id) as starts,
                       SUM(CASE WHEN r.finish_position = 1 THEN 1 ELSE 0 END) as wins,
                       SUM(r.prize_awarded) as prize
                FROM results r
                JOIN races rc ON r.race_id = rc.race_id
                JOIN jockeys j ON r.jockey_id = j.jockey_id
                WHERE rc.year = ?
                GROUP BY j.jockey_id
                ORDER BY wins DESC, prize DESC
                LIMIT 1
            """, (year,)).fetchone()
            res["jockey"] = dict(j_row) if j_row and j_row["wins"] > 0 else None

            # 調教師
            t_row = conn.execute("""
                SELECT t.name, COUNT(r.result_id) as starts,
                       SUM(CASE WHEN r.finish_position = 1 THEN 1 ELSE 0 END) as wins,
                       SUM(r.prize_awarded) as prize
                FROM results r
                JOIN races rc ON r.race_id = rc.race_id
                JOIN horses h ON r.horse_id = h.horse_id
                JOIN trainers t ON h.trainer_id = t.trainer_id
                WHERE rc.year = ?
                GROUP BY t.trainer_id
                ORDER BY wins DESC, prize DESC
                LIMIT 1
            """, (year,)).fetchone()
            res["trainer"] = dict(t_row) if t_row and t_row["wins"] > 0 else None

            # 馬主
            o_row = conn.execute("""
                SELECT o.name, COUNT(r.result_id) as starts,
                       SUM(CASE WHEN r.finish_position = 1 THEN 1 ELSE 0 END) as wins,
                       SUM(r.prize_awarded) as prize
                FROM results r
                JOIN races rc ON r.race_id = rc.race_id
                JOIN horses h ON r.horse_id = h.horse_id
                JOIN owners o ON h.owner_id = o.owner_id
                WHERE rc.year = ?
                GROUP BY o.owner_id
                ORDER BY wins DESC, prize DESC
                LIMIT 1
            """, (year,)).fetchone()
            res["owner"] = dict(o_row) if o_row and o_row["wins"] > 0 else None

            # 生産牧場
            b_row = conn.execute("""
                SELECT b.name, COUNT(r.result_id) as starts,
                       SUM(CASE WHEN r.finish_position = 1 THEN 1 ELSE 0 END) as wins,
                       SUM(r.prize_awarded) as prize
                FROM results r
                JOIN races rc ON r.race_id = rc.race_id
                JOIN horses h ON r.horse_id = h.horse_id
                JOIN breeders b ON h.breeder_id = b.breeder_id
                WHERE rc.year = ?
                GROUP BY b.breeder_id
                ORDER BY wins DESC, prize DESC
                LIMIT 1
            """, (year,)).fetchone()
            res["breeder"] = dict(b_row) if b_row and b_row["wins"] > 0 else None

            # 新人騎手 (デビュー1年目: debut_year == year または career_years == 1)
            rj_row = conn.execute("""
                SELECT j.name, COUNT(r.result_id) as starts,
                       SUM(CASE WHEN r.finish_position = 1 THEN 1 ELSE 0 END) as wins,
                       SUM(r.prize_awarded) as prize
                FROM results r
                JOIN races rc ON r.race_id = rc.race_id
                JOIN jockeys j ON r.jockey_id = j.jockey_id
                WHERE rc.year = ? AND (j.debut_year = ? OR j.career_years = 1)
                GROUP BY j.jockey_id
                ORDER BY wins DESC, prize DESC
                LIMIT 1
            """, (year, year)).fetchone()
            res["rookie_jockey"] = dict(rj_row) if rj_row and rj_row["wins"] > 0 else None

            # 新人調教師 (開業1年目: created_year == year または trainer_years == 1)
            rt_row = conn.execute("""
                SELECT t.name, COUNT(r.result_id) as starts,
                       SUM(CASE WHEN r.finish_position = 1 THEN 1 ELSE 0 END) as wins,
                       SUM(r.prize_awarded) as prize
                FROM results r
                JOIN races rc ON r.race_id = rc.race_id
                JOIN horses h ON r.horse_id = h.horse_id
                JOIN trainers t ON h.trainer_id = t.trainer_id
                WHERE rc.year = ? AND (t.created_year = ? OR t.trainer_years = 1)
                GROUP BY t.trainer_id
                ORDER BY wins DESC, prize DESC
                LIMIT 1
            """, (year, year)).fetchone()
            res["rookie_trainer"] = dict(rt_row) if rt_row and rt_row["wins"] > 0 else None

        return res

    # ==========================================
    # 3. 顕彰馬・殿堂・メモリアル
    # ==========================================
    def _create_hall_of_fame_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        lbl_hall = QLabel("🏆 JRA顕彰馬 (Hall of Fame) - G1通算4勝以上を達成した伝説的名馬")
        lbl_hall.setStyleSheet("color: #facc15; font-weight: bold; font-size: 14px;")
        layout.addWidget(lbl_hall)

        self.table_hall = QTableWidget()
        self.table_hall.setColumnCount(8)
        self.table_hall.setHorizontalHeaderLabels([
            "選出年", "顕彰馬名", "性齢", "通算成績", "G1勝数", "総獲得賞金", "主な勝鞍", "詳細"
        ])
        h_header = self.table_hall.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_hall.setColumnWidth(0, 65)
        self.table_hall.setColumnWidth(1, 150)
        self.table_hall.setColumnWidth(2, 60)
        self.table_hall.setColumnWidth(3, 90)
        self.table_hall.setColumnWidth(4, 70)
        self.table_hall.setColumnWidth(5, 110)
        h_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table_hall.setColumnWidth(7, 60)
        self.table_hall.setAlternatingRowColors(True)
        self.table_hall.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table_hall)

        return widget

    def refresh_hall_of_fame(self) -> None:
        """G1を4勝以上した顕彰馬をロード"""
        with self.db.session() as conn:
            rows = conn.execute("""
                SELECT h.horse_id, h.name, h.sex, h.age, h.g1_wins, h.prize_money, h.major_wins,
                       COUNT(r.result_id) as total_starts,
                       SUM(CASE WHEN r.finish_position = 1 THEN 1 ELSE 0 END) as total_wins,
                       MAX(rc.year) as last_active_year
                FROM horses h
                JOIN results r ON h.horse_id = r.horse_id
                JOIN races rc ON r.race_id = rc.race_id
                WHERE h.g1_wins >= 4
                GROUP BY h.horse_id
                ORDER BY last_active_year ASC, h.g1_wins DESC, h.prize_money DESC
            """).fetchall()

        sex_map = {"colt": "牡", "filly": "牝", "horse": "牡", "mare": "牝", "gelding": "セ"}
        self.table_hall.setRowCount(len(rows))

        for idx, r in enumerate(rows):
            y_str = f"{r['last_active_year']}年"
            h_name = r["name"]
            sex_age = f"{sex_map.get(r['sex'], '')}{r['age']}"
            rec_str = f"{r['total_starts']}戦{r['total_wins']}勝"
            g1_str = f"{r['g1_wins']}勝"
            prz_str = f"{(r['prize_money'] or 0) // 10000:,} 万円"
            maj_str = r["major_wins"] or "G1多数制覇"

            name_item = QTableWidgetItem(h_name)
            name_item.setForeground(QColor("#facc15"))
            f = name_item.font()
            f.setBold(True)
            name_item.setFont(f)

            items = [
                QTableWidgetItem(y_str),
                name_item,
                QTableWidgetItem(sex_age),
                QTableWidgetItem(rec_str),
                QTableWidgetItem(g1_str),
                QTableWidgetItem(prz_str),
                QTableWidgetItem(maj_str),
            ]

            for c, itm in enumerate(items):
                if c not in (1, 6):
                    itm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_hall.setItem(idx, c, itm)

            hid = r["horse_id"]
            btn_d = QPushButton("詳細")
            btn_d.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 11px; padding: 2px 6px; border: 1px solid #0284c7; border-radius: 3px;")
            btn_d.clicked.connect(lambda checked, h=hid: self._open_horse_detail(h))
            self.table_hall.setCellWidget(idx, 7, btn_d)

    def _open_horse_detail(self, horse_id: int) -> None:
        dlg = HorseDetailDialog(self.db, horse_id, parent=self)
        dlg.exec()
