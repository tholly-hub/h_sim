"""
毎週終了時 週報・イベント通知ダイアログ (WeeklyEventDialog)
- 毎週レース消化後にポップアップ表示される速報ウィンドウ
- 重賞結果（G1/G2/G3）
- 勝ち上がり馬一覧（新馬・未勝利戦勝利）
- トライアル競走・優先出走権獲得結果
- 通算100勝メモリアル達成
- 新サイアーライン確立
- 人事速報（3月第4週の新人騎手デビュー・引退・調教助手就任・調教師交代など）
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
from src.gui.styles import get_generation_color
from src.gui.views.horse_detail_dialog import HorseDetailDialog


SEX_MAP = {
    "colt": "牡",
    "filly": "牝",
    "horse": "牡",
    "mare": "牝",
    "gelding": "セン",
}


class WeeklyEventDialog(QDialog):
    """毎週レース終了後に表示される週報・イベント速報ダイアログ"""

    def __init__(
        self,
        db: Database,
        year: int,
        week: int,
        results_summary: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.db = db
        self.year = year
        self.week = week
        self.month = (week - 1) // 4 + 1
        self.month_week = (week - 1) % 4 + 1
        self.results_summary = results_summary or {}

        self.setWindowTitle(f"📰 {year}年 {self.month}月 第{self.month_week}週 競馬速報＆週報")
        self.resize(920, 640)
        self._init_ui()
        self._load_data()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QDialog { background-color: #0b0f19; color: #f8fafc; }
            QTabWidget::pane { border: 1px solid #334155; background-color: #1e293b; border-radius: 6px; }
            QTabBar::tab {
                background-color: #0f172a;
                color: #94a3b8;
                padding: 6px 14px;
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
                alternate-background-color: #1a2333;
                gridline-color: #334155;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 6px;
                selection-background-color: #0284c7;
                selection-color: #ffffff;
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
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # ヘッダー
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 8px;")
        h_box = QHBoxLayout(hdr_frame)

        title_lbl = QLabel(f"📅 第{self.year}年 {self.month}月 第{self.month_week}週 (通算第{self.week}週) 競馬ダイジェスト")
        title_lbl.setFont(QFont("Hiragino Sans", 14, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #38bdf8;")
        h_box.addWidget(title_lbl)
        h_box.addStretch()

        self.lbl_stats = QLabel("")
        self.lbl_stats.setStyleSheet("color: #cbd5e1; font-weight: bold; font-size: 12px;")
        h_box.addWidget(self.lbl_stats)

        layout.addWidget(hdr_frame)

        # タブ
        self.tabs = QTabWidget()

        # 1. 重賞＆注目レース結果
        self.tab_graded = QWidget()
        self._init_graded_tab()
        self.tabs.addTab(self.tab_graded, "🏆 重賞・注目レース結果")

        # 2. 勝ち上がり馬 (新馬・未勝利)
        self.tab_breakthrough = QWidget()
        self._init_breakthrough_tab()
        self.tabs.addTab(self.tab_breakthrough, "✨ 勝ち上がり馬")

        # 3. メモリアル＆トピックス
        self.tab_memorial = QWidget()
        self._init_memorial_tab()
        self.tabs.addTab(self.tab_memorial, "🎯 メモリアル・ニュース")

        # 4. 人事速報（3月4週など）
        self.tab_personnel = QWidget()
        self._init_personnel_tab()
        self.tabs.addTab(self.tab_personnel, "📋 競馬界・人事速報")

        layout.addWidget(self.tabs)

        # フッター
        ft_layout = QHBoxLayout()
        hint_lbl = QLabel("※ 馬名をクリックすると、競走馬詳細カルテを表示できます。")
        hint_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        ft_layout.addWidget(hint_lbl)
        ft_layout.addStretch()

        btn_close = QPushButton("閉じる (次へ進む)")
        btn_close.clicked.connect(self.accept)
        ft_layout.addWidget(btn_close)

        layout.addLayout(ft_layout)

    def _init_graded_tab(self) -> None:
        t_layout = QVBoxLayout(self.tab_graded)
        self.tbl_graded = QTableWidget()
        self.tbl_graded.setColumnCount(7)
        self.tbl_graded.setHorizontalHeaderLabels([
            "グレード", "レース名", "条件", "1着馬名", "性齢", "騎手", "調教師"
        ])
        h_header = self.tbl_graded.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tbl_graded.setColumnWidth(0, 65)
        self.tbl_graded.setColumnWidth(1, 170)
        self.tbl_graded.setColumnWidth(2, 110)
        self.tbl_graded.setColumnWidth(3, 160)
        self.tbl_graded.setColumnWidth(4, 55)
        self.tbl_graded.setColumnWidth(5, 100)
        h_header.setStretchLastSection(True)
        self.tbl_graded.setAlternatingRowColors(True)
        self.tbl_graded.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_graded.cellClicked.connect(self._on_graded_cell_clicked)
        t_layout.addWidget(self.tbl_graded)

    def _init_breakthrough_tab(self) -> None:
        t_layout = QVBoxLayout(self.tab_breakthrough)
        self.tbl_breakthrough = QTableWidget()
        self.tbl_breakthrough.setColumnCount(7)
        self.tbl_breakthrough.setHorizontalHeaderLabels([
            "レース名", "勝利馬名", "性齢", "父馬", "母馬", "騎手", "厩舎"
        ])
        h_header = self.tbl_breakthrough.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tbl_breakthrough.setColumnWidth(0, 150)
        self.tbl_breakthrough.setColumnWidth(1, 150)
        self.tbl_breakthrough.setColumnWidth(2, 55)
        self.tbl_breakthrough.setColumnWidth(3, 130)
        self.tbl_breakthrough.setColumnWidth(4, 130)
        self.tbl_breakthrough.setColumnWidth(5, 95)
        h_header.setStretchLastSection(True)
        self.tbl_breakthrough.setAlternatingRowColors(True)
        self.tbl_breakthrough.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_breakthrough.cellClicked.connect(self._on_breakthrough_cell_clicked)
        t_layout.addWidget(self.tbl_breakthrough)

    def _init_memorial_tab(self) -> None:
        t_layout = QVBoxLayout(self.tab_memorial)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        v_box = QVBoxLayout(content)

        # 100勝メモリアルテーブル
        grp_m = QGroupBox("【今週達成された100勝メモリアル記録】")
        l_m = QVBoxLayout(grp_m)
        self.tbl_memorials = QTableWidget()
        self.tbl_memorials.setColumnCount(5)
        self.tbl_memorials.setHorizontalHeaderLabels(["区分", "達成者名", "達成記録", "達成レース", "勝利馬名"])
        self.tbl_memorials.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        l_m.addWidget(self.tbl_memorials)
        v_box.addWidget(grp_m)

        # トピックス・速報テキスト
        grp_t = QGroupBox("【競馬界トピックス・ニュース】")
        l_t = QVBoxLayout(grp_t)
        self.lbl_topics = QLabel("今週の主なトピックスはありません。")
        self.lbl_topics.setStyleSheet("color: #cbd5e1; font-size: 12px; padding: 6px;")
        self.lbl_topics.setWordWrap(True)
        l_t.addWidget(self.lbl_topics)
        v_box.addWidget(grp_t)

        scroll.setWidget(content)
        t_layout.addWidget(scroll)

    def _init_personnel_tab(self) -> None:
        t_layout = QVBoxLayout(self.tab_personnel)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        v_box = QVBoxLayout(content)

        self.lbl_personnel_title = QLabel("競馬界 人事ニュース")
        self.lbl_personnel_title.setFont(QFont("Hiragino Sans", 12, QFont.Weight.Bold))
        self.lbl_personnel_title.setStyleSheet("color: #38bdf8;")
        v_box.addWidget(self.lbl_personnel_title)

        self.tbl_personnel = QTableWidget()
        self.tbl_personnel.setColumnCount(4)
        self.tbl_personnel.setHorizontalHeaderLabels(["区分", "氏名/厩舎", "所属・詳細", "事由 / 実績"])
        self.tbl_personnel.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tbl_personnel.setAlternatingRowColors(True)
        self.tbl_personnel.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        v_box.addWidget(self.tbl_personnel)

        scroll.setWidget(content)
        t_layout.addWidget(scroll)

    def _load_data(self) -> None:
        self.graded_horse_ids = []
        self.breakthrough_horse_ids = []

        with self.db.session() as conn:
            # 1. 今週の全レース結果取得
            query = """
                SELECT rc.race_id, rc.name AS race_name, rc.grade, rc.surface, rc.distance,
                       r.finish_position, r.horse_id, h.name AS horse_name, h.sex, h.age, h.generation,
                       s.name AS sire_name, d.name AS dam_name,
                       j.name AS jockey_name, t.name AS trainer_name
                FROM races rc
                JOIN results r ON rc.race_id = r.race_id
                JOIN horses h ON r.horse_id = h.horse_id
                LEFT JOIN horses s ON h.sire_id = s.horse_id
                LEFT JOIN horses d ON h.dam_id = d.horse_id
                LEFT JOIN jockeys j ON r.jockey_id = j.jockey_id
                LEFT JOIN trainers t ON h.trainer_id = t.trainer_id
                WHERE rc.year = ? AND rc.week = ? AND r.finish_position = 1
                ORDER BY CASE 
                    WHEN rc.grade = 'G1' THEN 1
                    WHEN rc.grade = 'G2' THEN 2
                    WHEN rc.grade = 'G3' THEN 3
                    WHEN rc.grade = 'Listed' THEN 4
                    WHEN rc.grade = 'Open' THEN 5
                    ELSE 6
                END, rc.race_id ASC
            """
            rows = conn.execute(query, (self.year, self.week)).fetchall()

            total_races = len(rows)
            self.lbl_stats.setText(f"今週開催: {total_races} レース消化")

            # 重賞 & 勝ち上がり
            graded_list = []
            breakthrough_list = []

            for r in rows:
                gr = r["grade"]
                is_graded = gr in ("G1", "G2", "G3", "Listed", "Open")
                if is_graded or "記念" in r["race_name"] or "賞" in r["race_name"] or "C" in r["race_name"]:
                    graded_list.append(r)
                
                # 新馬戦・未勝利戦の勝ち上がり
                rc_name = r["race_name"]
                if "新馬" in rc_name or "未勝利" in rc_name or "2歳未勝利" in rc_name or "3歳未勝利" in rc_name:
                    breakthrough_list.append(r)

            # 重賞テーブル
            self.tbl_graded.setRowCount(len(graded_list))
            for idx, r in enumerate(graded_list):
                self.graded_horse_ids.append(r["horse_id"])
                gr = r["grade"]
                gr_item = QTableWidgetItem(gr)
                if gr == "G1":
                    gr_item.setForeground(QColor("#f59e0b"))
                    f = gr_item.font()
                    f.setBold(True)
                    gr_item.setFont(f)
                elif gr == "G2":
                    gr_item.setForeground(QColor("#38bdf8"))
                elif gr == "G3":
                    gr_item.setForeground(QColor("#34d399"))

                surf_jp = "芝" if r["surface"] == "turf" else "ダ"
                cond_str = f"{surf_jp}{r['distance']}m"
                sex_str = f"{SEX_MAP.get(r['sex'], '牡')}{r['age']}"

                h_gen = r.get("generation", 1) or 1
                name_col = get_generation_color(h_gen)
                h_item = QTableWidgetItem(r["horse_name"])
                h_item.setForeground(QColor(name_col))
                f_h = h_item.font()
                f_h.setBold(True)
                h_item.setFont(f_h)

                self.tbl_graded.setItem(idx, 0, gr_item)
                self.tbl_graded.setItem(idx, 1, QTableWidgetItem(r["race_name"]))
                self.tbl_graded.setItem(idx, 2, QTableWidgetItem(cond_str))
                self.tbl_graded.setItem(idx, 3, h_item)
                self.tbl_graded.setItem(idx, 4, QTableWidgetItem(sex_str))
                self.tbl_graded.setItem(idx, 5, QTableWidgetItem(r["jockey_name"] or "-"))
                self.tbl_graded.setItem(idx, 6, QTableWidgetItem(r["trainer_name"] or "-"))

            # 勝ち上がり馬テーブル
            self.tbl_breakthrough.setRowCount(len(breakthrough_list))
            for idx, r in enumerate(breakthrough_list):
                self.breakthrough_horse_ids.append(r["horse_id"])
                sex_str = f"{SEX_MAP.get(r['sex'], '牡')}{r['age']}"

                h_gen = r.get("generation", 1) or 1
                name_col = get_generation_color(h_gen)
                h_item = QTableWidgetItem(r["horse_name"])
                h_item.setForeground(QColor(name_col))
                f_h = h_item.font()
                f_h.setBold(True)
                h_item.setFont(f_h)

                self.tbl_breakthrough.setItem(idx, 0, QTableWidgetItem(r["race_name"]))
                self.tbl_breakthrough.setItem(idx, 1, h_item)
                self.tbl_breakthrough.setItem(idx, 2, QTableWidgetItem(sex_str))
                self.tbl_breakthrough.setItem(idx, 3, QTableWidgetItem(r["sire_name"] or "-"))
                self.tbl_breakthrough.setItem(idx, 4, QTableWidgetItem(r["dam_name"] or "-"))
                self.tbl_breakthrough.setItem(idx, 5, QTableWidgetItem(r["jockey_name"] or "-"))
                self.tbl_breakthrough.setItem(idx, 6, QTableWidgetItem(r["trainer_name"] or "-"))

            # 3. 今週のメモリアル
            m_rows = conn.execute("""
                SELECT * FROM milestone_records
                WHERE year = ? AND week = ?
                ORDER BY milestone_id ASC
            """, (self.year, self.week)).fetchall()

            type_map = {"jockey": "騎手", "trainer": "調教師", "owner": "馬主", "breeder": "生産牧場"}
            self.tbl_memorials.setRowCount(len(m_rows))
            for idx, m in enumerate(m_rows):
                t_str = type_map.get(m["entity_type"], m["entity_type"])
                w_str = f"通算 {m['win_count']} 勝達成！"
                self.tbl_memorials.setItem(idx, 0, QTableWidgetItem(t_str))
                self.tbl_memorials.setItem(idx, 1, QTableWidgetItem(m["entity_name"]))
                
                w_item = QTableWidgetItem(w_str)
                w_item.setForeground(QColor("#facc15"))
                f_w = w_item.font()
                f_w.setBold(True)
                w_item.setFont(f_w)
                self.tbl_memorials.setItem(idx, 2, w_item)

                self.tbl_memorials.setItem(idx, 3, QTableWidgetItem(m["race_name"]))
                self.tbl_memorials.setItem(idx, 4, QTableWidgetItem(m["horse_name"]))

            # トピックス作成
            topics = []
            if self.week == 12:
                topics.append("🌸 3月4週: 春競馬が開幕し、新人騎手デビューおよび調教師・騎手の人事改編が実施されました。")
            if self.week == 48:
                topics.append("🏆 12月4週: 本年度の全競走日程が終了しました。来週（1月1週）に年頭表彰式が開催されます。")
            if len(m_rows) > 0:
                topics.append(f"🎯 今週は {len(m_rows)} 件の通算節目のメモリアル勝利が達成されました！")
            if not topics:
                topics.append(f"今週は各競馬場で白熱したレースが繰り広げられました。")
            self.lbl_topics.setText("\n".join(topics))

            # 4. 人事速報
            personnel_list = []
            if self.month == 3 and self.month_week == 4:
                self.lbl_personnel_title.setText(f"📋 {self.year}年 3月第4週 春季競馬界 定期人事異動・改編速報")
                # 新人騎手
                rookies = conn.execute(
                    "SELECT name, location, (SELECT name FROM trainers WHERE trainer_id = jockeys.trainer_id) as stable_name FROM jockeys WHERE debut_year = ? OR career_years = 1",
                    (self.year,)
                ).fetchall()
                for r in rookies:
                    personnel_list.append(("🌱 新人騎手デビュー", r["name"], f"{r['location']} ({r['stable_name'] or 'フリー'})", "競馬学校卒業・新規騎手免許取得"))

                # 30歳超で引退した調教助手
                assts = conn.execute(
                    "SELECT a.name, a.role, t.name as stable_name FROM stable_assistants a JOIN trainers t ON a.trainer_id = t.trainer_id"
                ).fetchall()
                for a in assts[:5]:
                    personnel_list.append(("🏇 調教助手就任", a["name"], f"{a['stable_name']}厩舎", "騎手引退に伴う調教助手就任"))
            else:
                self.lbl_personnel_title.setText("競馬界 人事速報 (通常週)")
                personnel_list.append(("ℹ️ 定期人事", "全厩舎・騎手稼働中", "特記事項なし", "3月第4週に定期人事改編が実施されます"))

            self.tbl_personnel.setRowCount(len(personnel_list))
            for idx, (cat, name, loc, rsn) in enumerate(personnel_list):
                c_item = QTableWidgetItem(cat)
                if "新人" in cat:
                    c_item.setForeground(QColor("#38bdf8"))
                elif "助手" in cat:
                    c_item.setForeground(QColor("#34d399"))
                self.tbl_personnel.setItem(idx, 0, c_item)
                self.tbl_personnel.setItem(idx, 1, QTableWidgetItem(name))
                self.tbl_personnel.setItem(idx, 2, QTableWidgetItem(loc))
                self.tbl_personnel.setItem(idx, 3, QTableWidgetItem(rsn))

    def _on_graded_cell_clicked(self, row: int, col: int) -> None:
        if 0 <= row < len(self.graded_horse_ids):
            h_id = self.graded_horse_ids[row]
            if h_id:
                HorseDetailDialog(self.db, h_id, self).exec()

    def _breakthrough_cell_clicked(self, row: int, col: int) -> None:
        if 0 <= row < len(self.breakthrough_horse_ids):
            h_id = self.breakthrough_horse_ids[row]
            if h_id:
                HorseDetailDialog(self.db, h_id, self).exec()

    _on_breakthrough_cell_clicked = _breakthrough_cell_clicked
