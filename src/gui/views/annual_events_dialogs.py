"""
年次イベント・発表用ダイアログモジュール
- 9月4週: 未勝利引退馬一覧ダイアログ (UnvictoryRetirementDialog)
- 12月4週: 年度末総合表彰・発表ダイアログ (YearEndAwardsDialog)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
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

from src.db.database import Database
from src.gui.views.horse_detail_dialog import HorseDetailDialog
from src.race.rankings import RankingManager


SEX_MAP = {
    "colt": "牡",
    "filly": "牝",
    "horse": "牡",
    "mare": "牝",
    "gelding": "セン",
}


class UnvictoryRetirementDialog(QDialog):
    """9月第4週 3歳未勝利引退馬発表ダイアログ"""

    def __init__(self, db: Database, year: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.year = year

        self.setWindowTitle(f"📋 {year}年 9月第4週 3歳未勝利馬 引退発表一覧")
        self.resize(850, 560)
        self._init_ui()
        self._load_data()

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
                padding: 6px;
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
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ヘッダー説明
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 10px;")
        h_box = QHBoxLayout(hdr_frame)

        title_lbl = QLabel(f"⚠️ 9月未勝利戦全日程終了に伴う {self.year}年度 3歳未勝利引退馬一覧 (9月第4週発表)")
        title_lbl.setFont(QFont("Hiragino Sans", 13, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #fbbf24;")
        h_box.addWidget(title_lbl)

        h_box.addStretch()

        self.lbl_count = QLabel("引退頭数: 0頭")
        self.lbl_count.setStyleSheet("color: #cbd5e1; font-weight: bold;")
        h_box.addWidget(self.lbl_count)

        layout.addWidget(hdr_frame)

        # テーブル
        self.table = QTableWidget()
        headers = ["馬名", "性齢", "父馬", "母馬", "毛色", "通算成績(1-2-3-着外)"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.cellDoubleClicked.connect(self._on_cell_clicked)
        layout.addWidget(self.table)

        # フッター
        ft_box = QHBoxLayout()
        hint_lbl = QLabel("※ 馬名をクリックすると競走馬の詳細カルテを表示します。")
        hint_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        ft_box.addWidget(hint_lbl)

        ft_box.addStretch()

        btn_close = QPushButton("確認・閉じる")
        btn_close.clicked.connect(self.accept)
        ft_box.addWidget(btn_close)

        layout.addLayout(ft_box)

    def _load_data(self) -> None:
        self.horse_ids = []
        with self.db.session() as conn:
            # 当年（self.year）に3歳で未勝利引退となった馬を抽出
            sql = """
                SELECT h.horse_id, h.name, h.sex, h.age, h.coat_color,
                       s.name AS sire_name, d.name AS dam_name
                FROM horses h
                LEFT JOIN horses s ON h.sire_id = s.horse_id
                LEFT JOIN horses d ON h.dam_id = d.horse_id
                WHERE h.retired_year = ? AND h.age = 3 AND h.career_wins = 0
                ORDER BY h.career_starts DESC, h.prize_money DESC
            """
            rows = conn.execute(sql, (self.year,)).fetchall()

            self.table.setRowCount(len(rows))
            self.lbl_count.setText(f"3歳未勝利引退頭数: {len(rows)}頭")

            for r_idx, r in enumerate(rows):
                h_id = r["horse_id"]
                self.horse_ids.append(h_id)

                # 通算成績 (1-2-3-着外) 取得
                res_rows = conn.execute(
                    "SELECT finish_position FROM results WHERE horse_id = ?", (h_id,)
                ).fetchall()
                w1 = sum(1 for x in res_rows if x["finish_position"] == 1)
                w2 = sum(1 for x in res_rows if x["finish_position"] == 2)
                w3 = sum(1 for x in res_rows if x["finish_position"] == 3)
                unp = sum(1 for x in res_rows if x["finish_position"] > 3)
                rec_str = f"{w1}-{w2}-{w3}-{unp}"

                sex_str = SEX_MAP.get(r["sex"], "牡")

                item_name = QTableWidgetItem(r["name"])
                item_name.setForeground(QColor("#38bdf8"))
                item_name.setFont(QFont("Hiragino Sans", 10, QFont.Weight.Bold))

                self.table.setItem(r_idx, 0, item_name)
                self.table.setItem(r_idx, 1, QTableWidgetItem(f"{sex_str}{r['age']}歳"))
                self.table.setItem(r_idx, 2, QTableWidgetItem(r["sire_name"] or "-"))
                self.table.setItem(r_idx, 3, QTableWidgetItem(r["dam_name"] or "-"))
                self.table.setItem(r_idx, 4, QTableWidgetItem(r["coat_color"] or "鹿毛"))
                self.table.setItem(r_idx, 5, QTableWidgetItem(rec_str))

    def _on_cell_clicked(self, row: int, col: int) -> None:
        if 0 <= row < len(self.horse_ids):
            h_id = self.horse_ids[row]
            dlg = HorseDetailDialog(self.db, h_id, self)
            dlg.exec()


class YearEndAwardsDialog(QDialog):
    """1月第1週 年頭各種表彰 & 新シーズン体制総合発表ダイアログ"""

    def __init__(self, db: Database, year: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.year = year  # 前年（表彰対象年）
        self.next_year = year + 1  # 開幕する新年度
        self.rank_mgr = RankingManager(db)

        self.setWindowTitle(f"🏆 {self.next_year}年 1月第1週 JRA表彰式 & 新シーズン開幕総合発表")
        self.resize(1050, 750)
        self._init_ui()
        self._load_awards_and_data()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QDialog { background-color: #0b0f19; color: #f8fafc; }
            QTabWidget::pane { border: 1px solid #334155; background-color: #1e293b; border-radius: 6px; }
            QTabBar::tab {
                background-color: #0f172a;
                color: #94a3b8;
                padding: 8px 16px;
                font-weight: bold;
                border: 1px solid #334155;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background-color: #1e293b;
                color: #38bdf8;
                border-bottom: 2px solid #38bdf8;
            }
            QTableWidget {
                background-color: #0f172a;
                gridline-color: #334155;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #1e293b;
                color: #fbbf24;
                font-weight: bold;
                border: 1px solid #334155;
                padding: 5px;
            }
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 6px 18px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        # メインタイトル
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px;")
        h_box = QHBoxLayout(hdr_frame)

        lbl_title = QLabel(f"🌟 {self.year}年度 JRA賞表彰式 & {self.next_year}年度 新シーズン体制（引退・新規発表）")
        lbl_title.setFont(QFont("Hiragino Sans", 15, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #f59e0b;")
        h_box.addWidget(lbl_title)
        layout.addWidget(hdr_frame)

        # タブウィジェット
        self.tabs = QTabWidget()

        # 1. 表彰馬・顕彰・特別功労
        self.tab_awards = QWidget()
        self._init_awards_tab()
        self.tabs.addTab(self.tab_awards, "👑 年度代表馬・各種表彰")

        # 2. リーディングTOP5
        self.tab_leadings = QWidget()
        self._init_leadings_tab()
        self.tabs.addTab(self.tab_leadings, "🏅 4大部門リーディング TOP5")

        # 3. 引退競走馬一覧
        self.tab_retire_horses = QWidget()
        self._init_retire_horses_tab()
        self.tabs.addTab(self.tab_retire_horses, "🐎 引退競走馬一覧")

        # 4. 種牡馬（引退＆新規）
        self.tab_sires = QWidget()
        self._init_sires_tab()
        self.tabs.addTab(self.tab_sires, "🐎 種牡馬 (引退 & 新種牡馬)")

        # 5. 繁殖牝馬（引退＆新規）
        self.tab_dams = QWidget()
        self._init_dams_tab()
        self.tabs.addTab(self.tab_dams, "🐴 繁殖牝馬 (引退 & 新繁殖)")

        layout.addWidget(self.tabs)

        # 閉じるボタン
        ft_layout = QHBoxLayout()
        hint_lbl = QLabel("※ 各テーブルの馬名をクリックすると、競走馬詳細カルテが表示されます。")
        hint_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        ft_layout.addWidget(hint_lbl)
        ft_layout.addStretch()

        btn_close = QPushButton("確認・新シーズンを開始する")
        btn_close.clicked.connect(self.accept)
        ft_layout.addWidget(btn_close)

        layout.addLayout(ft_layout)

    # ------------------------------------------------------------------------
    # タブ初期化
    # ------------------------------------------------------------------------
    def _init_awards_tab(self) -> None:
        t_layout = QVBoxLayout(self.tab_awards)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        v_box = QVBoxLayout(content)

        # 1-1. 本年度表彰馬テーブル
        grp1 = QGroupBox("【本年度表彰馬 (部門賞)】")
        l1 = QVBoxLayout(grp1)
        self.tbl_awards = QTableWidget()
        self.tbl_awards.setColumnCount(4)
        self.tbl_awards.setHorizontalHeaderLabels(["賞名", "受賞馬名", "性齢", "本年度戦績 / 主な勝ち鞍"])
        self.tbl_awards.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.tbl_awards.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.tbl_awards.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tbl_awards.cellClicked.connect(self._on_award_horse_clicked)
        l1.addWidget(self.tbl_awards)
        v_box.addWidget(grp1)

        # 1-2. 功労馬 & 顕彰馬テーブル
        grp2 = QGroupBox("【功労馬 & 顕彰馬】")
        l2 = QVBoxLayout(grp2)
        self.tbl_hall_horses = QTableWidget()
        self.tbl_hall_horses.setColumnCount(4)
        self.tbl_hall_horses.setHorizontalHeaderLabels(["区分", "馬名", "成績 (G1勝利数)", "選考・殿堂理由"])
        self.tbl_hall_horses.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tbl_hall_horses.cellClicked.connect(self._on_hall_horse_clicked)
        l2.addWidget(self.tbl_hall_horses)
        v_box.addWidget(grp2)

        # 1-3. 関係者表彰 (特別功労・殿堂・メモリアル)
        grp3 = QGroupBox("【騎手・調教師 特別功労 & 殿堂入り】")
        l3 = QVBoxLayout(grp3)
        self.tbl_people_awards = QTableWidget()
        self.tbl_people_awards.setColumnCount(4)
        self.tbl_people_awards.setHorizontalHeaderLabels(["表彰区分", "氏名 (区分)", "通算成績 / G1勝利数", "表彰基準"])
        self.tbl_people_awards.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        l3.addWidget(self.tbl_people_awards)
        v_box.addWidget(grp3)

        scroll.setWidget(content)
        t_layout.addWidget(scroll)

    def _init_leadings_tab(self) -> None:
        l_layout = QVBoxLayout(self.tab_leadings)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        v_box = QVBoxLayout(content)

        for cat_key, cat_name in [
            ("jockey", "騎手リーディング (トップ5)"),
            ("trainer", "調教師リーディング (トップ5)"),
            ("owner", "馬主リーディング (トップ5)"),
            ("breeder", "生産牧場リーディング (トップ5)"),
        ]:
            grp = QGroupBox(f"【{cat_name}】")
            ly = QVBoxLayout(grp)
            tbl = QTableWidget()
            tbl.setColumnCount(5)
            tbl.setHorizontalHeaderLabels(["順位", "氏名/名称", "成績(1着-2着-3着-着外)", "勝率 / 連対率", "主な代表重賞成績"])
            tbl.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
            ly.addWidget(tbl)
            v_box.addWidget(grp)
            setattr(self, f"tbl_lead_{cat_key}", tbl)

        scroll.setWidget(content)
        l_layout.addWidget(scroll)

    def _init_retire_horses_tab(self) -> None:
        r_layout = QVBoxLayout(self.tab_retire_horses)
        self.tbl_retire_horses = QTableWidget()
        self.tbl_retire_horses.setColumnCount(6)
        self.tbl_retire_horses.setHorizontalHeaderLabels(["馬名", "性齢", "父馬", "母馬", "通算成績", "主な重賞勝ち鞍"])
        self.tbl_retire_horses.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.tbl_retire_horses.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.tbl_retire_horses.cellClicked.connect(self._on_retire_horse_clicked)
        r_layout.addWidget(self.tbl_retire_horses)

    def _init_sires_tab(self) -> None:
        s_layout = QVBoxLayout(self.tab_sires)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        v_box = QVBoxLayout(content)

        grp1 = QGroupBox("【本年引退種牡馬】")
        l1 = QVBoxLayout(grp1)
        self.tbl_retire_sires = QTableWidget()
        self.tbl_retire_sires.setColumnCount(7)
        self.tbl_retire_sires.setHorizontalHeaderLabels(["馬名", "サイアーライン", "父", "母", "競走成績", "生産頭数", "勝ち馬頭数"])
        self.tbl_retire_sires.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        l1.addWidget(self.tbl_retire_sires)
        v_box.addWidget(grp1)

        grp2 = QGroupBox("【本年新種牡馬 (種牡馬入り)】")
        l2 = QVBoxLayout(grp2)
        self.tbl_new_sires = QTableWidget()
        self.tbl_new_sires.setColumnCount(7)
        self.tbl_new_sires.setHorizontalHeaderLabels(["馬名", "サイアーライン", "父", "母", "競走成績", "主な勝ち鞍", "初年度種付料"])
        self.tbl_new_sires.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        l2.addWidget(self.tbl_new_sires)
        v_box.addWidget(grp2)

        scroll.setWidget(content)
        s_layout.addWidget(scroll)

    def _init_dams_tab(self) -> None:
        d_layout = QVBoxLayout(self.tab_dams)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        v_box = QVBoxLayout(content)

        grp1 = QGroupBox("【本年引退繁殖牝馬】")
        l1 = QVBoxLayout(grp1)
        self.tbl_retire_dams = QTableWidget()
        self.tbl_retire_dams.setColumnCount(7)
        self.tbl_retire_dams.setHorizontalHeaderLabels(["馬名", "父系系統", "父", "母", "競走成績", "生産頭数", "勝ち馬頭数"])
        self.tbl_retire_dams.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        l1.addWidget(self.tbl_retire_dams)
        v_box.addWidget(grp1)

        grp2 = QGroupBox("【本年新繁殖牝馬 (繁殖入り)】")
        l2 = QVBoxLayout(grp2)
        self.tbl_new_dams = QTableWidget()
        self.tbl_new_dams.setColumnCount(6)
        self.tbl_new_dams.setHorizontalHeaderLabels(["馬名", "父", "母", "競走成績", "主な勝ち鞍", "繋養牧場"])
        self.tbl_new_dams.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        l2.addWidget(self.tbl_new_dams)
        v_box.addWidget(grp2)

        scroll.setWidget(content)
        d_layout.addWidget(scroll)

    # ------------------------------------------------------------------------
    # データ読み込み処理
    # ------------------------------------------------------------------------
    def _load_awards_and_data(self) -> None:
        with self.db.session() as conn:
            # 1. 表彰馬
            awards_rows = conn.execute(
                "SELECT * FROM annual_awards WHERE year = ?", (self.year,)
            ).fetchall()

            self.award_horse_ids = []
            self.tbl_awards.setRowCount(len(awards_rows))
            for idx, a in enumerate(awards_rows):
                cat = a["category"]
                h_id = a["horse_id"]
                h_name = a["horse_name"]
                self.award_horse_ids.append(h_id)

                # 馬情報
                h_row = conn.execute("SELECT sex, age, major_wins FROM horses WHERE horse_id = ?", (h_id,)).fetchone()
                sex_age = f"{SEX_MAP.get(h_row['sex'], '牡') if h_row else ''}{h_row['age'] if h_row else ''}歳"
                major = h_row["major_wins"] if (h_row and h_row["major_wins"]) else "-"

                self.tbl_awards.setItem(idx, 0, QTableWidgetItem(cat))
                item_h = QTableWidgetItem(h_name)
                item_h.setForeground(QColor("#38bdf8"))
                item_h.setFont(QFont("Hiragino Sans", 10, QFont.Weight.Bold))
                self.tbl_awards.setItem(idx, 1, item_h)
                self.tbl_awards.setItem(idx, 2, QTableWidgetItem(sex_age))
                self.tbl_awards.setItem(idx, 3, QTableWidgetItem(major))

            # 2. 功労馬・顕彰馬
            hall_rows = conn.execute("""
                SELECT h.horse_id, h.name, h.g1_wins, h.career_starts, h.career_wins
                FROM horses h
                WHERE h.g1_wins >= 3 OR (h.age >= 10 AND h.g1_wins >= 1)
                ORDER BY h.g1_wins DESC, h.prize_money DESC
                LIMIT 10
            """).fetchall()

            self.hall_horse_ids = []
            self.tbl_hall_horses.setRowCount(len(hall_rows))
            for idx, h in enumerate(hall_rows):
                self.hall_horse_ids.append(h["horse_id"])
                lbl_type = "🏆 殿堂・顕彰馬" if h["g1_wins"] >= 5 else "🎖 功労馬"
                reason = "G1通算5勝以上殿堂入り" if h["g1_wins"] >= 5 else "名馬・長寿功労"

                self.tbl_hall_horses.setItem(idx, 0, QTableWidgetItem(lbl_type))
                item_h = QTableWidgetItem(h["name"])
                item_h.setForeground(QColor("#facc15"))
                item_h.setFont(QFont("Hiragino Sans", 10, QFont.Weight.Bold))
                self.tbl_hall_horses.setItem(idx, 1, item_h)
                self.tbl_hall_horses.setItem(idx, 2, QTableWidgetItem(f"{h['career_starts']}戦{h['career_wins']}勝 (G1:{h['g1_wins']}勝)"))
                self.tbl_hall_horses.setItem(idx, 3, QTableWidgetItem(reason))

            # 3. 関係者表彰 (特別功労・殿堂)
            # 騎手: 500勝+G1 20勝(特別功労), 1000勝+G1 30勝(殿堂)
            # 調教師: 250勝+G1 10勝(特別功労), 500勝+G1 15勝(殿堂)
            people_awards = []
            j_rows = conn.execute("SELECT name, career_wins, g1_wins FROM jockeys WHERE career_wins >= 500 ORDER BY career_wins DESC").fetchall()
            for j in j_rows:
                if j["career_wins"] >= 1000 and j["g1_wins"] >= 30:
                    people_awards.append(("🏆 殿堂入り騎手", f"{j['name']} (騎手)", f"通算{j['career_wins']}勝 (G1:{j['g1_wins']}勝)", "通算1000勝 & G1 30勝達成"))
                elif j["career_wins"] >= 500 and j["g1_wins"] >= 20:
                    people_awards.append(("🎖 特別功労騎手", f"{j['name']} (騎手)", f"通算{j['career_wins']}勝 (G1:{j['g1_wins']}勝)", "通算500勝 & G1 20勝達成"))

            t_rows = conn.execute("SELECT name, career_wins, g1_wins FROM trainers WHERE career_wins >= 250 ORDER BY career_wins DESC").fetchall()
            for t in t_rows:
                if t["career_wins"] >= 500 and t["g1_wins"] >= 15:
                    people_awards.append(("🏆 殿堂入り調教師", f"{t['name']} (調教師)", f"通算{t['career_wins']}勝 (G1:{t['g1_wins']}勝)", "通算500勝 & G1 15勝達成"))
                elif t["career_wins"] >= 250 and t["g1_wins"] >= 10:
                    people_awards.append(("🎖 特別功労調教師", f"{t['name']} (調教師)", f"通算{t['career_wins']}勝 (G1:{t['g1_wins']}勝)", "通算250勝 & G1 10勝達成"))

            self.tbl_people_awards.setRowCount(len(people_awards))
            for idx, (cat, name, rec, crt) in enumerate(people_awards):
                self.tbl_people_awards.setItem(idx, 0, QTableWidgetItem(cat))
                self.tbl_people_awards.setItem(idx, 1, QTableWidgetItem(name))
                self.tbl_people_awards.setItem(idx, 2, QTableWidgetItem(rec))
                self.tbl_people_awards.setItem(idx, 3, QTableWidgetItem(crt))

            # 4. リーディングTOP5
            rank_funcs = {
                "jockey": self.rank_mgr.get_jockey_rankings,
                "trainer": self.rank_mgr.get_trainer_rankings,
                "owner": self.rank_mgr.get_owner_rankings,
                "breeder": self.rank_mgr.get_breeder_rankings,
            }
            for cat_key, fetch_fn in rank_funcs.items():
                tbl: QTableWidget = getattr(self, f"tbl_lead_{cat_key}")
                rank_list = fetch_fn(is_career=False, limit=5)
                tbl.setRowCount(len(rank_list))
                for r_idx, r in enumerate(rank_list):
                    rank_str = f"第{r_idx + 1}位"
                    name_str = r.get("name", "-")
                    w1 = r.get("win_1", 0)
                    w2 = r.get("win_2", 0)
                    w3 = r.get("win_3", 0)
                    unp = r.get("win_out", 0)
                    rec_str = f"{w1}-{w2}-{w3}-{unp}"

                    starts = w1 + w2 + w3 + unp
                    win_rate = (w1 / starts * 100) if starts > 0 else 0.0
                    top2_rate = ((w1 + w2) / starts * 100) if starts > 0 else 0.0
                    rate_str = f"{win_rate:.1f}% / {top2_rate:.1f}%"
                    rep_list = r.get("representative_horses", [])
                    major_str = ", ".join(rep_list) if rep_list else "-"

                    tbl.setItem(r_idx, 0, QTableWidgetItem(rank_str))
                    tbl.setItem(r_idx, 1, QTableWidgetItem(name_str))
                    tbl.setItem(r_idx, 2, QTableWidgetItem(rec_str))
                    tbl.setItem(r_idx, 3, QTableWidgetItem(rate_str))
                    tbl.setItem(r_idx, 4, QTableWidgetItem(major_str))

            # 5. 本年引退競走馬一覧
            retire_rows = conn.execute("""
                SELECT h.horse_id, h.name, h.sex, h.age, h.career_starts, h.career_wins, h.g1_wins, h.g2_wins, h.g3_wins, h.major_wins,
                       s.name AS sire_name, d.name AS dam_name
                FROM horses h
                LEFT JOIN horses s ON h.sire_id = s.horse_id
                LEFT JOIN horses d ON h.dam_id = d.horse_id
                WHERE h.retired_year = ? AND h.is_sire = 0 AND h.is_dam = 0 AND h.is_dead = 0
                ORDER BY h.prize_money DESC
            """, (self.year,)).fetchall()

            self.retire_horse_ids = []
            self.tbl_retire_horses.setRowCount(len(retire_rows))
            for idx, r in enumerate(retire_rows):
                self.retire_horse_ids.append(r["horse_id"])
                sex_str = f"{SEX_MAP.get(r['sex'], '牡')}{r['age']}歳"
                rec_str = f"{r['career_starts']}戦{r['career_wins']}勝"
                major = r["major_wins"] or ("重賞未勝利" if (r["g1_wins"] + r["g2_wins"] + r["g3_wins"] == 0) else "-")

                item_h = QTableWidgetItem(r["name"])
                item_h.setForeground(QColor("#38bdf8"))
                item_h.setFont(QFont("Hiragino Sans", 10, QFont.Weight.Bold))

                self.tbl_retire_horses.setItem(idx, 0, item_h)
                self.tbl_retire_horses.setItem(idx, 1, QTableWidgetItem(sex_str))
                self.tbl_retire_horses.setItem(idx, 2, QTableWidgetItem(r["sire_name"] or "-"))
                self.tbl_retire_horses.setItem(idx, 3, QTableWidgetItem(r["dam_name"] or "-"))
                self.tbl_retire_horses.setItem(idx, 4, QTableWidgetItem(rec_str))
                self.tbl_retire_horses.setItem(idx, 5, QTableWidgetItem(major))

            # 6. 種牡馬 (引退 & 新種牡馬)
            # 引退種牡馬
            r_sire_rows = conn.execute("""
                SELECT h.name, s.sire_line, h.career_starts, h.career_wins,
                       ps.name AS sire_name, pd.name AS dam_name,
                       (SELECT COUNT(*) FROM horses WHERE sire_id = h.horse_id) AS progeny_cnt,
                       (SELECT COUNT(*) FROM horses WHERE sire_id = h.horse_id AND career_wins > 0) AS winner_cnt
                FROM sires s
                JOIN horses h ON s.horse_id = h.horse_id
                LEFT JOIN horses ps ON h.sire_id = ps.horse_id
                LEFT JOIN horses pd ON h.dam_id = pd.horse_id
                WHERE s.is_active = 0
            """).fetchall()

            self.tbl_retire_sires.setRowCount(len(r_sire_rows))
            for idx, r in enumerate(r_sire_rows):
                self.tbl_retire_sires.setItem(idx, 0, QTableWidgetItem(r["name"]))
                self.tbl_retire_sires.setItem(idx, 1, QTableWidgetItem(r["sire_line"] or "-"))
                self.tbl_retire_sires.setItem(idx, 2, QTableWidgetItem(r["sire_name"] or "-"))
                self.tbl_retire_sires.setItem(idx, 3, QTableWidgetItem(r["dam_name"] or "-"))
                self.tbl_retire_sires.setItem(idx, 4, QTableWidgetItem(f"{r['career_starts']}戦{r['career_wins']}勝"))
                self.tbl_retire_sires.setItem(idx, 5, QTableWidgetItem(f"{r['progeny_cnt']}頭"))
                self.tbl_retire_sires.setItem(idx, 6, QTableWidgetItem(f"{r['winner_cnt']}頭"))

            # 新種牡馬 (当年に現役引退して種牡馬入りした馬)
            n_sire_rows = conn.execute("""
                SELECT h.name, s.sire_line, s.stud_fee, h.career_starts, h.career_wins, h.major_wins,
                       ps.name AS sire_name, pd.name AS dam_name
                FROM sires s
                JOIN horses h ON s.horse_id = h.horse_id
                LEFT JOIN horses ps ON h.sire_id = ps.horse_id
                LEFT JOIN horses pd ON h.dam_id = pd.horse_id
                WHERE h.is_sire = 1 AND h.retired_year = ? AND s.is_active = 1
                ORDER BY h.prize_money DESC
            """, (self.year,)).fetchall()

            self.tbl_new_sires.setRowCount(len(n_sire_rows))
            for idx, r in enumerate(n_sire_rows):
                self.tbl_new_sires.setItem(idx, 0, QTableWidgetItem(r["name"]))
                self.tbl_new_sires.setItem(idx, 1, QTableWidgetItem(r["sire_line"] or "-"))
                self.tbl_new_sires.setItem(idx, 2, QTableWidgetItem(r["sire_name"] or "-"))
                self.tbl_new_sires.setItem(idx, 3, QTableWidgetItem(r["dam_name"] or "-"))
                self.tbl_new_sires.setItem(idx, 4, QTableWidgetItem(f"{r['career_starts']}戦{r['career_wins']}勝"))
                self.tbl_new_sires.setItem(idx, 5, QTableWidgetItem(r["major_wins"] or "-"))
                self.tbl_new_sires.setItem(idx, 6, QTableWidgetItem(f"{r['stud_fee'] // 10000:,}万円"))

            # 7. 繁殖牝馬 (引退 & 新繁殖)
            # 引退繁殖牝馬
            r_dam_rows = conn.execute("""
                SELECT h.name, h.career_starts, h.career_wins,
                       ps.name AS sire_name, pd.name AS dam_name,
                       (SELECT COUNT(*) FROM horses WHERE dam_id = h.horse_id) AS progeny_cnt,
                       (SELECT COUNT(*) FROM horses WHERE dam_id = h.horse_id AND career_wins > 0) AS winner_cnt
                FROM dams d
                JOIN horses h ON d.horse_id = h.horse_id
                LEFT JOIN horses ps ON h.sire_id = ps.horse_id
                LEFT JOIN horses pd ON h.dam_id = pd.horse_id
                WHERE d.is_active = 0
            """).fetchall()

            self.tbl_retire_dams.setRowCount(len(r_dam_rows))
            for idx, r in enumerate(r_dam_rows):
                self.tbl_retire_dams.setItem(idx, 0, QTableWidgetItem(r["name"]))
                self.tbl_retire_dams.setItem(idx, 1, QTableWidgetItem(r["sire_name"] or "-"))
                self.tbl_retire_dams.setItem(idx, 2, QTableWidgetItem(r["sire_name"] or "-"))
                self.tbl_retire_dams.setItem(idx, 3, QTableWidgetItem(r["dam_name"] or "-"))
                self.tbl_retire_dams.setItem(idx, 4, QTableWidgetItem(f"{r['career_starts']}戦{r['career_wins']}勝"))
                self.tbl_retire_dams.setItem(idx, 5, QTableWidgetItem(f"{r['progeny_cnt']}頭"))
                self.tbl_retire_dams.setItem(idx, 6, QTableWidgetItem(f"{r['winner_cnt']}頭"))

            # 新繁殖牝馬 (当年に現役引退して繁殖牝馬入りした馬)
            n_dam_rows = conn.execute("""
                SELECT h.name, h.career_starts, h.career_wins, h.major_wins,
                       ps.name AS sire_name, pd.name AS dam_name, b.name AS breeder_name
                FROM dams d
                JOIN horses h ON d.horse_id = h.horse_id
                LEFT JOIN horses ps ON h.sire_id = ps.horse_id
                LEFT JOIN horses pd ON h.dam_id = pd.horse_id
                LEFT JOIN breeders b ON d.breeder_id = b.breeder_id
                WHERE h.is_dam = 1 AND h.retired_year = ? AND d.is_active = 1
                ORDER BY h.prize_money DESC
            """, (self.year,)).fetchall()

            self.tbl_new_dams.setRowCount(len(n_dam_rows))
            for idx, r in enumerate(n_dam_rows):
                self.tbl_new_dams.setItem(idx, 0, QTableWidgetItem(r["name"]))
                self.tbl_new_dams.setItem(idx, 1, QTableWidgetItem(r["sire_name"] or "-"))
                self.tbl_new_dams.setItem(idx, 2, QTableWidgetItem(r["dam_name"] or "-"))
                self.tbl_new_dams.setItem(idx, 3, QTableWidgetItem(f"{r['career_starts']}戦{r['career_wins']}勝"))
                self.tbl_new_dams.setItem(idx, 4, QTableWidgetItem(r["major_wins"] or "-"))
                self.tbl_new_dams.setItem(idx, 5, QTableWidgetItem(r["breeder_name"] or "-"))

    # ------------------------------------------------------------------------
    # クリックイベント
    # ------------------------------------------------------------------------
    def _on_award_horse_clicked(self, row: int, col: int) -> None:
        if 0 <= row < len(self.award_horse_ids):
            h_id = self.award_horse_ids[row]
            if h_id:
                HorseDetailDialog(self.db, h_id, self).exec()

    def _on_hall_horse_clicked(self, row: int, col: int) -> None:
        if 0 <= row < len(self.hall_horse_ids):
            h_id = self.hall_horse_ids[row]
            if h_id:
                HorseDetailDialog(self.db, h_id, self).exec()

    def _on_retire_horse_clicked(self, row: int, col: int) -> None:
        if 0 <= row < len(self.retire_horse_ids):
            h_id = self.retire_horse_ids[row]
            if h_id:
                HorseDetailDialog(self.db, h_id, self).exec()


class SpringFoalingDialog(QDialog):
    """3月第1週 春季当歳馬（0歳）誕生・出産発表ダイアログ"""

    def __init__(self, db: Database, year: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.year = year
        self.horse_ids: List[int] = []

        self.setWindowTitle(f"🐴 {year}年 3月第1週 春季当歳馬（0歳）誕生・スタッドブック登録")
        self.resize(880, 560)
        self._init_ui()
        self._load_data()

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
                padding: 6px;
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
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 10px;")
        h_box = QHBoxLayout(hdr_frame)

        title_lbl = QLabel(f"🌱 {self.year}年度 春季当歳馬（0歳仔馬）誕生発表 (3月第1週)")
        title_lbl.setFont(QFont("Hiragino Sans", 13, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #38bdf8;")
        h_box.addWidget(title_lbl)

        h_box.addStretch()

        self.lbl_count = QLabel("誕生頭数: 0頭 (牡0頭 / 牝0頭)")
        self.lbl_count.setStyleSheet("color: #cbd5e1; font-weight: bold;")
        h_box.addWidget(self.lbl_count)

        layout.addWidget(hdr_frame)

        desc_lbl = QLabel("※ 生まれた仔馬（0歳）は各牧場で2年間育成され、2年後（引退した親馬からは3年後）の1月に厩舎へ入厩し6月に新馬戦デビューします。")
        desc_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(desc_lbl)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "馬名", "性別", "父馬", "母馬", "生産牧場", "馬主", "血統適性", "毛色"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, 55)
        self.table.setColumnWidth(2, 140)
        self.table.setColumnWidth(3, 140)
        self.table.setColumnWidth(4, 110)
        self.table.setColumnWidth(5, 110)
        self.table.setColumnWidth(6, 75)
        header.setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._on_cell_clicked)
        layout.addWidget(self.table)

        btn_box = QHBoxLayout()
        hint = QLabel("※ 行をダブルクリックすると詳細血統・カルテを表示します")
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        btn_box.addWidget(hint)
        btn_box.addStretch()

        btn_close = QPushButton("確認して閉じる")
        btn_close.clicked.connect(self.close)
        btn_box.addWidget(btn_close)

        layout.addLayout(btn_box)

    def _load_data(self) -> None:
        with self.db.session() as conn:
            rows = conn.execute(
                """
                SELECT h.horse_id, h.name, h.sex, h.coat_color, h.mstn_type,
                       s.name AS sire_name, d.name AS dam_name,
                       b.name AS breeder_name, o.name AS owner_name
                FROM horses h
                LEFT JOIN horses s ON h.sire_id = s.horse_id
                LEFT JOIN horses d ON h.dam_id = d.horse_id
                LEFT JOIN breeders b ON h.breeder_id = b.breeder_id
                LEFT JOIN owners o ON h.owner_id = o.owner_id
                WHERE h.birth_year = ? AND h.age = 0
                ORDER BY h.horse_id ASC
                """,
                (self.year,),
            ).fetchall()

            colt_cnt = sum(1 for r in rows if r["sex"] in ("colt", "horse"))
            filly_cnt = len(rows) - colt_cnt
            self.lbl_count.setText(f"誕生頭数: {len(rows)}頭 (牡{colt_cnt}頭 / 牝{filly_cnt}頭)")

            self.horse_ids = [r["horse_id"] for r in rows]
            self.table.setRowCount(len(rows))

            for idx, r in enumerate(rows):
                sex_str = SEX_MAP.get(r["sex"], r["sex"])
                self.table.setItem(idx, 0, QTableWidgetItem(r["name"]))
                self.table.setItem(idx, 1, QTableWidgetItem(sex_str))
                self.table.setItem(idx, 2, QTableWidgetItem(r["sire_name"] or "-"))
                self.table.setItem(idx, 3, QTableWidgetItem(r["dam_name"] or "-"))
                self.table.setItem(idx, 4, QTableWidgetItem(r["breeder_name"] or "-"))
                self.table.setItem(idx, 5, QTableWidgetItem(r["owner_name"] or "-"))
                self.table.setItem(idx, 6, QTableWidgetItem(r["mstn_type"] or "-"))
                self.table.setItem(idx, 7, QTableWidgetItem(r["coat_color"] or "-"))

    def _on_cell_clicked(self, row: int, col: int) -> None:
        if 0 <= row < len(self.horse_ids):
            h_id = self.horse_ids[row]
            if h_id:
                HorseDetailDialog(self.db, h_id, self).exec()


class SpringBreedingDialog(QDialog):
    """4月第1週 春季種付け交配イベント発表ダイアログ"""

    def __init__(self, db: Database, year: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.year = year
        self.sire_ids: List[int] = []

        self.setWindowTitle(f"🧬 {year}年 4月第1週 春季種付け交配発表")
        self.resize(880, 560)
        self._init_ui()
        self._load_data()

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
                padding: 6px;
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
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 10px;")
        h_box = QHBoxLayout(hdr_frame)

        title_lbl = QLabel(f"🧬 {self.year}年度 春季種付け交配発表 (4月第1週)")
        title_lbl.setFont(QFont("Hiragino Sans", 13, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #ec4899;")
        h_box.addWidget(title_lbl)

        h_box.addStretch()

        self.lbl_count = QLabel("総種付け頭数: 0頭")
        self.lbl_count.setStyleSheet("color: #cbd5e1; font-weight: bold;")
        h_box.addWidget(self.lbl_count)

        layout.addWidget(hdr_frame)

        desc_lbl = QLabel("※ 1月に新種牡馬・新繁殖牝馬となった馬も今月から交配を開始しました。来年3月に子供（0歳）が生まれます。")
        desc_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(desc_lbl)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "種牡馬名", "サイアーライン", "種付け料", "今年種付け頭数", "繋養牧場", "ニックス交配数", "主要配合牝馬"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, 140)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 110)
        self.table.setColumnWidth(5, 95)
        header.setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._on_cell_clicked)
        layout.addWidget(self.table)

        btn_box = QHBoxLayout()
        hint = QLabel("※ 種牡馬名をダブルクリックすると詳細カルテを表示します")
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        btn_box.addWidget(hint)
        btn_box.addStretch()

        btn_close = QPushButton("確認して閉じる")
        btn_close.clicked.connect(self.close)
        btn_box.addWidget(btn_close)

        layout.addLayout(btn_box)

    def _load_data(self) -> None:
        with self.db.session() as conn:
            from src.core.breeding import BreedingEngine
            BreedingEngine(self.db)._ensure_matings_table(conn)

            # 当年の種付け集計
            rows = conn.execute(
                """
                SELECT s.horse_id, h.name AS sire_name, s.sire_line, s.stud_fee, b.name AS breeder_name,
                       COUNT(m.mating_id) AS mating_count,
                       SUM(CASE WHEN m.is_nicks = 1 THEN 1 ELSE 0 END) AS nicks_count
                FROM sires s
                JOIN horses h ON s.horse_id = h.horse_id
                LEFT JOIN breeders b ON s.breeder_id = b.breeder_id
                LEFT JOIN matings m ON s.horse_id = m.sire_id AND m.mating_year = ?
                WHERE s.is_active = 1
                GROUP BY s.horse_id
                ORDER BY mating_count DESC, s.stud_fee DESC
                """,
                (self.year,),
            ).fetchall()

            total_mated = sum(r["mating_count"] for r in rows)
            self.lbl_count.setText(f"総種付け頭数: {total_mated}頭（稼働種牡馬: {len(rows)}頭）")

            self.sire_ids = [r["horse_id"] for r in rows]
            self.table.setRowCount(len(rows))

            for idx, r in enumerate(rows):
                s_id = r["horse_id"]
                # 主要配合牝馬の取得 (G1勝利繁殖牝馬など上位2頭)
                dam_names_rows = conn.execute(
                    """
                    SELECT d_h.name
                    FROM matings m
                    JOIN horses d_h ON m.dam_id = d_h.horse_id
                    WHERE m.sire_id = ? AND m.mating_year = ?
                    ORDER BY d_h.prize_money DESC
                    LIMIT 2
                    """,
                    (s_id, self.year)
                ).fetchall()
                dam_names = "、".join(dr["name"] for dr in dam_names_rows) if dam_names_rows else "-"

                fee_str = f"{r['stud_fee'] // 10000}万円" if r["stud_fee"] else "無料"
                self.table.setItem(idx, 0, QTableWidgetItem(r["sire_name"]))
                self.table.setItem(idx, 1, QTableWidgetItem(r["sire_line"]))
                self.table.setItem(idx, 2, QTableWidgetItem(fee_str))
                self.table.setItem(idx, 3, QTableWidgetItem(f"{r['mating_count']}頭"))
                self.table.setItem(idx, 4, QTableWidgetItem(r["breeder_name"] or "-"))
                self.table.setItem(idx, 5, QTableWidgetItem(f"{r['nicks_count']}頭"))
                self.table.setItem(idx, 6, QTableWidgetItem(dam_names))

    def _on_cell_clicked(self, row: int, col: int) -> None:
        if 0 <= row < len(self.sire_ids):
            h_id = self.sire_ids[row]
            if h_id:
                HorseDetailDialog(self.db, h_id, self).exec()

