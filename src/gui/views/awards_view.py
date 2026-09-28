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
        self._loaded = False
        self._init_ui()

    def ensure_loaded(self) -> None:
        """初回表示時のみデータをロード"""
        if not self._loaded:
            self.refresh_all()
            self._loaded = True

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
        lbl_hist = QLabel("📜 歴代表彰・年度代表馬＆各部門賞 推移一覧")
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
            rows = conn.execute("SELECT DISTINCT year FROM annual_awards ORDER BY year DESC").fetchall()
            if not rows:
                rows = conn.execute("SELECT DISTINCT year FROM races ORDER BY year DESC").fetchall()

        all_years = [r["year"] for r in rows]

        cur_year = self.combo_horse_awards_year.currentData()
        self.combo_horse_awards_year.blockSignals(True)
        self.combo_horse_awards_year.clear()
        for y in all_years:
            self.combo_horse_awards_year.addItem(f"{y}年度", y)
        if cur_year is not None and cur_year in all_years:
            idx = self.combo_horse_awards_year.findData(cur_year)
            if idx >= 0:
                self.combo_horse_awards_year.setCurrentIndex(idx)
        elif all_years:
            self.combo_horse_awards_year.setCurrentIndex(0)
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

        # 歴代推移 (降順: 最新年が上)
        all_awards = self.awards_mgr.get_horse_of_the_year_history()
        years_map: Dict[int, Dict[str, str]] = {}
        for a in all_awards:
            y = a["year"]
            if y not in years_map:
                years_map[y] = {}
            years_map[y][a["category"]] = a["horse_name"]

        sorted_years = sorted(years_map.keys(), reverse=True)
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

        # 5大リーディングカード (2行 × 3列)
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
        self.table_leading_hist.setColumnCount(6)
        self.table_leading_hist.setHorizontalHeaderLabels([
            "年度", "最多勝騎手", "最多勝調教師", "最多勝馬主", "最多勝生産牧場", "最多勝新人騎手"
        ])
        h_header = self.table_leading_hist.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_leading_hist.setColumnWidth(0, 60)
        for c in range(1, 6):
            self.table_leading_hist.setColumnWidth(c, 140)
        h_header.setStretchLastSection(True)
        self.table_leading_hist.setAlternatingRowColors(True)
        self.table_leading_hist.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table_leading_hist)

        return widget

    def _refresh_leading_awards_years(self) -> None:
        with self.db.session() as conn:
            rows = conn.execute("SELECT DISTINCT year FROM races ORDER BY year DESC").fetchall()
        years = [r["year"] for r in rows]

        cur_year = self.combo_leading_awards_year.currentData()
        self.combo_leading_awards_year.blockSignals(True)
        self.combo_leading_awards_year.clear()
        for y in years:
            self.combo_leading_awards_year.addItem(f"{y}年度", y)
        if cur_year is not None and cur_year in years:
            idx = self.combo_leading_awards_year.findData(cur_year)
            if idx >= 0:
                self.combo_leading_awards_year.setCurrentIndex(idx)
        elif years:
            self.combo_leading_awards_year.setCurrentIndex(0)
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

        # 歴代推移 (降順)
        with self.db.session() as conn:
            years = [r["year"] for r in conn.execute("SELECT DISTINCT year FROM races ORDER BY year DESC").fetchall()]

        self.table_leading_hist.setRowCount(len(years))
        for r_idx, y in enumerate(years):
            y_leaders = self._calc_annual_leaders(y)
            self.table_leading_hist.setItem(r_idx, 0, QTableWidgetItem(f"{y}年"))

            keys = ["jockey", "trainer", "owner", "breeder", "rookie_jockey"]
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

        return res

    # ==========================================
    # 3. 顕彰馬・功労馬・殿堂・メモリアル
    # ==========================================
    def _create_hall_of_fame_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        hall_sub_tabs = QTabWidget()
        hall_sub_tabs.setStyleSheet("""
            QTabBar::tab {
                font-weight: bold;
                font-size: 12px;
                padding: 5px 12px;
            }
        """)

        # ----------------------------------------------------
        # サブタブ1: 🏆 顕彰馬 & 🎖 功労馬一覧
        # ----------------------------------------------------
        w_horses = QWidget()
        l_horses = QVBoxLayout(w_horses)
        l_horses.setContentsMargins(6, 6, 6, 6)
        l_horses.setSpacing(6)

        # フィルターバー
        f_bar = QFrame()
        f_bar.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 6px;")
        fb_layout = QHBoxLayout(f_bar)
        fb_layout.setContentsMargins(8, 4, 8, 4)
        fb_layout.setSpacing(10)

        fb_layout.addWidget(QLabel("表彰区分:"))
        self.combo_hall_filter = QComboBox()
        self.combo_hall_filter.addItem("すべて (顕彰馬 & 功労馬)", "all")
        self.combo_hall_filter.addItem("🏆 顕彰馬のみ (G1 5勝/3冠/3連覇)", "hall")
        self.combo_hall_filter.addItem("🎖 功労馬のみ (G1複数/重賞多数/長寿)", "merit")
        self.combo_hall_filter.currentIndexChanged.connect(self.refresh_hall_of_fame_horses)
        fb_layout.addWidget(self.combo_hall_filter)

        fb_layout.addWidget(QLabel("現役/引退:"))
        self.combo_hall_active = QComboBox()
        self.combo_hall_active.addItem("すべて", "all")
        self.combo_hall_active.addItem("現役馬のみ", "active")
        self.combo_hall_active.addItem("引退馬のみ", "retired")
        self.combo_hall_active.currentIndexChanged.connect(self.refresh_hall_of_fame_horses)
        fb_layout.addWidget(self.combo_hall_active)

        fb_layout.addStretch()

        self.lbl_hall_count = QLabel("該当: 0頭")
        self.lbl_hall_count.setStyleSheet("color: #38bdf8; font-weight: bold;")
        fb_layout.addWidget(self.lbl_hall_count)

        l_horses.addWidget(f_bar)

        self.table_hall = QTableWidget()
        self.table_hall.setColumnCount(10)
        self.table_hall.setHorizontalHeaderLabels([
            "表彰区分", "馬名", "性齢", "状態", "通算成績", "G1勝数", "重賞勝数", "総獲得賞金", "選考・表彰理由", "詳細"
        ])
        h_header = self.table_hall.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_hall.setColumnWidth(0, 85)
        self.table_hall.setColumnWidth(1, 140)
        self.table_hall.setColumnWidth(2, 55)
        self.table_hall.setColumnWidth(3, 55)
        self.table_hall.setColumnWidth(4, 85)
        self.table_hall.setColumnWidth(5, 60)
        self.table_hall.setColumnWidth(6, 65)
        self.table_hall.setColumnWidth(7, 100)
        h_header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        self.table_hall.setColumnWidth(9, 55)
        self.table_hall.setAlternatingRowColors(True)
        self.table_hall.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        l_horses.addWidget(self.table_hall)

        hall_sub_tabs.addTab(w_horses, "🏆 顕彰馬 & 🎖 功労馬")

        # ----------------------------------------------------
        # サブタブ2: 🎖 関係者 特別功労 & 殿堂入り
        # ----------------------------------------------------
        w_people = QWidget()
        l_people = QVBoxLayout(w_people)
        l_people.setContentsMargins(6, 6, 6, 6)
        l_people.setSpacing(6)

        lbl_peop = QLabel("🎖 騎手・調教師 特別功労者＆殿堂入り (通算勝利数・G1制覇実績に基づく表彰)")
        lbl_peop.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 12px;")
        l_people.addWidget(lbl_peop)

        self.table_people_awards = QTableWidget()
        self.table_people_awards.setColumnCount(6)
        self.table_people_awards.setHorizontalHeaderLabels([
            "表彰区分", "対象者名 (区分)", "所属", "通算成績", "G1勝利数", "表彰基準・主な実績"
        ])
        p_header = self.table_people_awards.horizontalHeader()
        p_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_people_awards.setColumnWidth(0, 110)
        self.table_people_awards.setColumnWidth(1, 140)
        self.table_people_awards.setColumnWidth(2, 70)
        self.table_people_awards.setColumnWidth(3, 100)
        self.table_people_awards.setColumnWidth(4, 75)
        p_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table_people_awards.setAlternatingRowColors(True)
        self.table_people_awards.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        l_people.addWidget(self.table_people_awards)

        hall_sub_tabs.addTab(w_people, "🎖 関係者特別功労・殿堂")

        # ----------------------------------------------------
        # サブタブ3: 🎯 通算100勝メモリアル記録
        # ----------------------------------------------------
        w_mile = QWidget()
        l_mile = QVBoxLayout(w_mile)
        l_mile.setContentsMargins(6, 6, 6, 6)
        l_mile.setSpacing(6)

        m_bar = QFrame()
        m_bar.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 6px;")
        mb_layout = QHBoxLayout(m_bar)
        mb_layout.setContentsMargins(8, 4, 8, 4)
        mb_layout.setSpacing(10)

        mb_layout.addWidget(QLabel("主体区分:"))
        self.combo_mile_type = QComboBox()
        self.combo_mile_type.addItem("すべて", None)
        self.combo_mile_type.addItem("🏇 騎手", "jockey")
        self.combo_mile_type.addItem("📋 調教師", "trainer")
        self.combo_mile_type.addItem("👑 馬主", "owner")
        self.combo_mile_type.addItem("🏡 生産牧場", "breeder")
        self.combo_mile_type.currentIndexChanged.connect(self.refresh_milestone_records)
        mb_layout.addWidget(self.combo_mile_type)
        mb_layout.addStretch()

        l_mile.addWidget(m_bar)

        self.table_milestones = QTableWidget()
        self.table_milestones.setColumnCount(6)
        self.table_milestones.setHorizontalHeaderLabels([
            "達成時期", "区分", "達成者名", "達成節目", "達成レース", "達成騎乗/所有馬"
        ])
        m_header = self.table_milestones.horizontalHeader()
        m_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_milestones.setColumnWidth(0, 90)
        self.table_milestones.setColumnWidth(1, 80)
        self.table_milestones.setColumnWidth(2, 130)
        self.table_milestones.setColumnWidth(3, 90)
        self.table_milestones.setColumnWidth(4, 150)
        m_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table_milestones.setAlternatingRowColors(True)
        self.table_milestones.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        l_mile.addWidget(self.table_milestones)

        hall_sub_tabs.addTab(w_mile, "🎯 100勝メモリアル")

        layout.addWidget(hall_sub_tabs)
        return widget

    def refresh_hall_of_fame(self) -> None:
        """顕彰馬・功労馬・関係者表彰・メモリアルをすべて更新"""
        self.refresh_hall_of_fame_horses()
        self.refresh_people_awards()
        self.refresh_milestone_records()

    def refresh_hall_of_fame_horses(self) -> None:
        """顕彰馬 & 功労馬一覧をロード"""
        type_filter = self.combo_hall_filter.currentData()
        active_filter = self.combo_hall_active.currentData()

        f_type = None if type_filter == "all" else type_filter
        rows = self.awards_mgr.get_hall_and_merit_horses(filter_type=f_type)

        if active_filter == "active":
            rows = [r for r in rows if r.get("is_active", 0) == 1]
        elif active_filter == "retired":
            rows = [r for r in rows if r.get("is_active", 0) == 0]

        self.lbl_hall_count.setText(f"該当: {len(rows)}頭")

        sex_map = {"colt": "牡", "filly": "牝", "horse": "牡", "mare": "牝", "gelding": "セ"}
        self.table_hall.setRowCount(len(rows))

        for idx, r in enumerate(rows):
            is_hall = (r.get("award_type") == "hall")
            type_label = r.get("award_type_label", "🎖 功労馬")
            h_name = r.get("horse_name", r.get("name", ""))
            sex_age = f"{sex_map.get(r.get('sex', ''), '')}{r.get('age', '')}"
            act_str = "現役" if r.get("is_active") == 1 else "引退"
            rec_str = f"{r.get('career_starts', 0)}戦{r.get('career_wins', 0)}勝"
            g1_str = f"{r.get('g1_wins', 0)}勝"
            gr_str = f"{r.get('graded_wins_count', 0)}勝"
            prz_str = f"{(r.get('prize_money', 0) or 0) // 10000:,} 万円"
            reason_str = r.get("reason", "-")

            item_type = QTableWidgetItem(type_label)
            item_type.setForeground(QColor("#facc15") if is_hall else QColor("#34d399"))
            f_type = item_type.font()
            f_type.setBold(True)
            item_type.setFont(f_type)

            name_item = QTableWidgetItem(h_name)
            name_item.setForeground(QColor("#facc15") if is_hall else QColor("#38bdf8"))
            f = name_item.font()
            f.setBold(True)
            name_item.setFont(f)

            act_item = QTableWidgetItem(act_str)
            act_item.setForeground(QColor("#22c55e") if r.get("is_active") == 1 else QColor("#94a3b8"))

            items = [
                item_type,
                name_item,
                QTableWidgetItem(sex_age),
                act_item,
                QTableWidgetItem(rec_str),
                QTableWidgetItem(g1_str),
                QTableWidgetItem(gr_str),
                QTableWidgetItem(prz_str),
                QTableWidgetItem(reason_str),
            ]

            for c, itm in enumerate(items):
                if c not in (1, 8):
                    itm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_hall.setItem(idx, c, itm)

            hid = r["horse_id"]
            btn_d = QPushButton("詳細")
            btn_d.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 11px; padding: 2px 6px; border: 1px solid #0284c7; border-radius: 3px;")
            btn_d.clicked.connect(lambda checked, h=hid: self._open_horse_detail(h))
            self.table_hall.setCellWidget(idx, 9, btn_d)

    def refresh_people_awards(self) -> None:
        """関係者（騎手・調教師）特別功労＆殿堂入りをロード"""
        special = self.awards_mgr.get_special_merit_awards()
        legends = self.awards_mgr.get_hall_of_fame_legends()

        people_list = []

        # 殿堂騎手 (2000勝+G1 20勝)
        for j in legends.get("jockeys", []):
            people_list.append({
                "type": "🏆 殿堂入り騎手",
                "name": f"{j['name']} (騎手)",
                "loc": j.get("location", "-"),
                "rec": f"{j.get('career_starts', 0)}戦{j.get('career_wins', 0)}勝",
                "g1": f"{j.get('g1_wins', 0)}勝",
                "reason": f"通算2000勝 & G1 20勝達成 (獲得賞金: {j.get('career_earnings', 0)//10000:,}万円)",
                "color": "#facc15"
            })
        # 特別功労騎手 (1000勝+G1 10勝)
        legend_j_names = {j["name"] for j in legends.get("jockeys", [])}
        for j in special.get("jockeys", []):
            if j["name"] in legend_j_names:
                continue
            people_list.append({
                "type": "🎖 特別功労騎手",
                "name": f"{j['name']} (騎手)",
                "loc": j.get("location", "-"),
                "rec": f"{j.get('career_starts', 0)}戦{j.get('career_wins', 0)}勝",
                "g1": f"{j.get('g1_wins', 0)}勝",
                "reason": f"通算1000勝 & G1 10勝達成 (獲得賞金: {j.get('career_earnings', 0)//10000:,}万円)",
                "color": "#38bdf8"
            })

        # 殿堂調教師 (1000勝+G1馬10頭)
        for t in legends.get("trainers", []):
            people_list.append({
                "type": "🏆 殿堂入り調教師",
                "name": f"{t.get('stable_name', t['name'])} (調教師)",
                "loc": t.get("location", "-"),
                "rec": f"{t.get('total_starts', 0)}戦{t.get('total_wins', 0)}勝",
                "g1": f"{t.get('g1_wins', 0)}勝 (G1馬:{t.get('g1_horse_count', 0)}頭)",
                "reason": f"通算1000勝 & G1馬10頭輩出 (獲得賞金: {t.get('career_earnings', 0)//10000:,}万円)",
                "color": "#facc15"
            })
        # 特別功労調教師 (500勝+G1馬5頭)
        legend_t_names = {t["name"] for t in legends.get("trainers", [])}
        for t in special.get("trainers", []):
            if t["name"] in legend_t_names:
                continue
            people_list.append({
                "type": "🎖 特別功労調教師",
                "name": f"{t.get('stable_name', t['name'])} (調教師)",
                "loc": t.get("location", "-"),
                "rec": f"{t.get('total_starts', 0)}戦{t.get('total_wins', 0)}勝",
                "g1": f"{t.get('g1_wins', 0)}勝 (G1馬:{t.get('g1_horse_count', 0)}頭)",
                "reason": f"通算500勝 & G1馬5頭輩出 (獲得賞金: {t.get('career_earnings', 0)//10000:,}万円)",
                "color": "#38bdf8"
            })

        self.table_people_awards.setRowCount(len(people_list))
        for idx, p in enumerate(people_list):
            t_item = QTableWidgetItem(p["type"])
            t_item.setForeground(QColor(p["color"]))
            f = t_item.font()
            f.setBold(True)
            t_item.setFont(f)

            n_item = QTableWidgetItem(p["name"])
            n_item.setForeground(QColor(p["color"]))

            items = [
                t_item,
                n_item,
                QTableWidgetItem(p["loc"]),
                QTableWidgetItem(p["rec"]),
                QTableWidgetItem(p["g1"]),
                QTableWidgetItem(p["reason"]),
            ]
            for c, itm in enumerate(items):
                if c not in (1, 5):
                    itm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_people_awards.setItem(idx, c, itm)

    def refresh_milestone_records(self) -> None:
        """100勝メモリアル記録一覧をロード"""
        self.awards_mgr.sync_all_milestones()
        e_type = self.combo_mile_type.currentData()
        rows = self.awards_mgr.get_milestone_records(entity_type=e_type)

        type_map = {
            "jockey": "🏇 騎手",
            "trainer": "📋 調教師",
            "owner": "👑 馬主",
            "breeder": "🏡 生産牧場",
        }

        self.table_milestones.setRowCount(len(rows))
        for idx, r in enumerate(rows):
            t_str = f"{r['year']}年{r['month']}月{r['week']}週"
            cat_str = type_map.get(r["entity_type"], r["entity_type"])
            name_str = r["entity_name"]
            win_str = f"🎉 通算{r['win_count']}勝"
            race_str = r.get("race_name", "-")
            horse_str = r.get("horse_name", "-")

            win_item = QTableWidgetItem(win_str)
            win_item.setForeground(QColor("#facc15"))
            f = win_item.font()
            f.setBold(True)
            win_item.setFont(f)

            items = [
                QTableWidgetItem(t_str),
                QTableWidgetItem(cat_str),
                QTableWidgetItem(name_str),
                win_item,
                QTableWidgetItem(race_str),
                QTableWidgetItem(horse_str),
            ]
            for c, itm in enumerate(items):
                if c not in (2, 4, 5):
                    itm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_milestones.setItem(idx, c, itm)

    def _open_horse_detail(self, horse_id: int) -> None:
        dlg = HorseDetailDialog(self.db, horse_id, parent=self)
        dlg.exec()
