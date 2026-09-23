"""
各種リーディング & 生産牧場・馬主規模推移ビュー (PyQt6)
- 騎手、調教師、馬主、生産牧場、サイアーのランキング表示 (当年/通算)
- 騎手・調教師: 年数表示（○年目）、新人騎手・新人調教師に緑字 [新]
- 調教師・馬主・生産牧場: 持ち馬数・勝ち馬数クリックで詳細馬ダイアログ表示
- サイアーリーディング: [新]、[外] 表記 & 産駒一覧ダイアログ連携
- 各リーディングの年度別順位推移グラフ表示 (RankingHistoryDialog)
- 牧場・馬主の動的分化・規模階層（資金・頭数）一覧
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.db.database import Database
from src.gui.views.entity_horses_dialog import EntityHorsesDialog
from src.gui.views.progeny_dialog import ProgenyListDialog
from src.gui.views.ranking_history_dialog import RankingHistoryDialog
from src.race.rankings import RankingManager


class RankingsView(QWidget):
    """各種リーディング & 牧場・馬主規模推移画面"""

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.rank_mgr = RankingManager(db)
        self.current_category = "jockey"
        self.is_career = False
        self.sire_age_filter: Optional[int] = None
        self.row_entities: List[Dict[str, Any]] = []
        self._init_ui()
        self.refresh_data()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. ナビゲーションバー
        nav_frame = QFrame()
        nav_frame.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 8px;")
        nav_layout = QHBoxLayout(nav_frame)
        nav_layout.setContentsMargins(12, 8, 12, 8)
        nav_layout.setSpacing(12)

        cat_group = QButtonGroup(self)
        categories = [
            ("騎手リーディング", "jockey"),
            ("調教師リーディング", "trainer"),
            ("馬主リーディング", "owner"),
            ("生産牧場リーディング", "breeder"),
            ("サイアーリーディング", "sire"),
        ]
        self.cat_buttons = {}
        for idx, (label, cat_key) in enumerate(categories):
            btn = QPushButton(label)
            btn.setCheckable(True)
            if idx == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, k=cat_key: self._change_category(k))
            cat_group.addButton(btn)
            self.cat_buttons[cat_key] = btn
            nav_layout.addWidget(btn)

        # サイアー用世代フィルター
        self.sire_filter_frame = QFrame()
        sire_f_layout = QHBoxLayout(self.sire_filter_frame)
        sire_f_layout.setContentsMargins(8, 0, 8, 0)
        sire_f_layout.setSpacing(6)
        sire_f_layout.addWidget(QLabel("世代:"))

        self.combo_sire_age = QComboBox()
        self.combo_sire_age.addItem("総合 (全世代)", None)
        self.combo_sire_age.addItem("2歳馬リーディング", 2)
        self.combo_sire_age.addItem("3歳馬リーディング", 3)
        self.combo_sire_age.currentIndexChanged.connect(self._on_sire_age_changed)
        sire_f_layout.addWidget(self.combo_sire_age)
        self.sire_filter_frame.setVisible(False)
        nav_layout.addWidget(self.sire_filter_frame)

        nav_layout.addStretch()

        self.rb_year = QRadioButton("当年成績")
        self.rb_year.setChecked(True)
        self.rb_year.toggled.connect(self._on_term_changed)
        self.rb_career = QRadioButton("通算成績")
        self.rb_career.toggled.connect(self._on_term_changed)

        nav_layout.addWidget(self.rb_year)
        nav_layout.addWidget(self.rb_career)

        main_layout.addWidget(nav_frame)

        # 2. メインタブ
        tabs = QTabWidget()

        rank_container = QWidget()
        rank_layout = QVBoxLayout(rank_container)
        rank_layout.setContentsMargins(8, 8, 8, 8)
        rank_layout.setSpacing(8)

        self.rank_hint_lbl = QLabel("💡 名前をクリックすると【年度別順位推移グラフ】、持ち馬数・勝ち馬数をクリックすると【所属馬一覧】が表示されます。")
        self.rank_hint_lbl.setStyleSheet("color: #38bdf8; font-size: 11px;")
        rank_layout.addWidget(self.rank_hint_lbl)

        self.rank_table = QTableWidget()
        self.rank_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.rank_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.rank_table.setAlternatingRowColors(True)
        self.rank_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.rank_table.cellClicked.connect(self._on_rank_cell_clicked)
        rank_layout.addWidget(self.rank_table)

        tabs.addTab(rank_container, "リーディングランキング TOP 30")

        tier_widget = QWidget()
        tier_layout = QVBoxLayout(tier_widget)
        tier_layout.setContentsMargins(8, 8, 8, 8)

        tier_sub_lbl = QLabel("シミュレーションに伴い自然発生した大手（メガファーム・大馬主）と中小の格差一覧")
        tier_sub_lbl.setObjectName("subText")
        tier_layout.addWidget(tier_sub_lbl)

        self.tier_table = QTableWidget()
        self.tier_table.setColumnCount(7)
        self.tier_table.setHorizontalHeaderLabels([
            "ID", "名称", "地域/冠名", "階層ランク", "所有/繋養数", "資金残高", "通算獲得賞金"
        ])
        self.tier_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tier_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tier_layout.addWidget(self.tier_table)

        tabs.addTab(tier_widget, "生産牧場・馬主の規模階層 (動的分化)")

        main_layout.addWidget(tabs)

    def _change_category(self, cat_key: str) -> None:
        self.current_category = cat_key
        self.sire_filter_frame.setVisible(cat_key == "sire")
        if cat_key == "sire":
            self.rank_hint_lbl.setText("💡 種牡馬名クリックで【順位推移グラフ】、産駒数クリックで【産駒一覧】が表示されます。")
        elif cat_key in ("trainer", "owner", "breeder"):
            self.rank_hint_lbl.setText("💡 名前クリックで【順位推移グラフ】、頭数・勝馬数クリックで【馬一覧】が表示されます。")
        else:
            self.rank_hint_lbl.setText("💡 名前をクリックすると【年度別順位推移グラフ】が表示されます。")
        self.refresh_data()

    def _on_sire_age_changed(self) -> None:
        self.sire_age_filter = self.combo_sire_age.currentData()
        self.refresh_data()

    def _on_term_changed(self) -> None:
        self.is_career = self.rb_career.isChecked()
        self.refresh_data()

    def refresh_data(self) -> None:
        self._load_ranking_table()
        self._load_tier_table()

    def _load_ranking_table(self) -> None:
        is_career = self.is_career
        cat = self.current_category
        self.row_entities.clear()

        # 最新年度取得
        with self.db.session() as conn:
            cur_y_row = conn.execute("SELECT MAX(year) FROM races").fetchone()
            cur_year = cur_y_row[0] if cur_y_row and cur_y_row[0] else 1

        if cat == "jockey":
            rows = self.rank_mgr.get_jockey_rankings(is_career=is_career, limit=30)
            headers = ["順位", "騎手名 (推移グラフ)", "年齢", "所属", "区分", "戦績 (1-2-3-外)", "勝率", "重賞 (G1-G2-G3)", "獲得賞金", "代表乗鞍"]
            self.rank_table.setColumnCount(len(headers))
            self.rank_table.setHorizontalHeaderLabels(headers)
            self.rank_table.setRowCount(len(rows))

            for idx, r in enumerate(rows):
                self.row_entities.append({
                    "id": r.get("jockey_id", 0),
                    "name": r.get("name", ""),
                    "category": "jockey",
                })
                # 年数算出
                debut_y = r.get("debut_year", 1) or 1
                career_years = max(1, cur_year - debut_y + 1)
                is_rookie = (career_years == 1 or r.get("is_rookie") == 1)

                age_val = r.get("age", 20)
                age_str = f"{age_val}歳 ({career_years}年目)"
                free_str = "フリー" if r.get("is_free", 0) == 1 else "所属"
                w1 = r.get("win_1", 0)
                w2 = r.get("win_2", 0)
                w3 = r.get("win_3", 0)
                w_out = r.get("win_out", 0)
                record_str = f"{w1}-{w2}-{w3}-{w_out}"

                g1 = r.get("g1_cnt", 0)
                g2 = r.get("g2_cnt", 0)
                g3 = r.get("g3_cnt", 0)
                graded_str = f"{g1}-{g2}-{g3}"

                win_rate = f"{(r.get('win_rate', 0.0) * 100):.1f}%"
                earn = r.get("total_earnings", 0)
                earn_str = f"{earn // 10000:,}万円" if earn >= 10000 else f"{earn:,}円"

                rep_horses = r.get("representative_horses", [])
                rep_str = ", ".join(rep_horses) if rep_horses else "-"

                self.rank_table.setItem(idx, 0, QTableWidgetItem(f"{idx+1}位"))

                display_name = f"📈 {r.get('name', '')}"
                if is_rookie:
                    display_name += " [新]"
                name_item = QTableWidgetItem(display_name)
                name_item.setForeground(QColor("#22c55e") if is_rookie else QColor("#38bdf8"))
                self.rank_table.setItem(idx, 1, name_item)

                self.rank_table.setItem(idx, 2, QTableWidgetItem(age_str))
                self.rank_table.setItem(idx, 3, QTableWidgetItem(r.get("location", "")))
                self.rank_table.setItem(idx, 4, QTableWidgetItem(free_str))
                self.rank_table.setItem(idx, 5, QTableWidgetItem(record_str))
                self.rank_table.setItem(idx, 6, QTableWidgetItem(win_rate))
                self.rank_table.setItem(idx, 7, QTableWidgetItem(graded_str))
                self.rank_table.setItem(idx, 8, QTableWidgetItem(earn_str))
                self.rank_table.setItem(idx, 9, QTableWidgetItem(rep_str))

        elif cat == "trainer":
            rows = self.rank_mgr.get_trainer_rankings(is_career=is_career, limit=30)
            headers = ["順位", "厩舎名 (推移グラフ)", "年齢", "所属", "得意分野", "持ち馬数", "勝ち馬数", "戦績 (1-2-3-外)", "勝率", "重賞 (G1-G2-G3)", "獲得賞金", "代表持ち馬"]
            self.rank_table.setColumnCount(len(headers))
            self.rank_table.setHorizontalHeaderLabels(headers)
            self.rank_table.setRowCount(len(rows))

            for idx, r in enumerate(rows):
                self.row_entities.append({
                    "id": r.get("trainer_id", 0),
                    "name": r.get("name", ""),
                    "category": "trainer",
                })
                debut_y = r.get("debut_year", 1) or 1
                career_years = max(1, cur_year - debut_y + 1)
                is_rookie = (career_years == 1 or r.get("is_rookie") == 1)

                age_val = r.get("age", 40)
                age_str = f"{age_val}歳 ({career_years}年目)"
                h_cnt_str = f"📋 {r.get('horse_count', 0)}頭"
                w_cnt_str = f"🏆 {r.get('winner_count', 0)}頭"
                w1 = r.get("win_1", 0)
                w2 = r.get("win_2", 0)
                w3 = r.get("win_3", 0)
                w_out = r.get("win_out", 0)
                record_str = f"{w1}-{w2}-{w3}-{w_out}"

                g1 = r.get("g1_cnt", 0)
                g2 = r.get("g2_cnt", 0)
                g3 = r.get("g3_cnt", 0)
                graded_str = f"{g1}-{g2}-{g3}"

                win_rate = f"{(r.get('win_rate', 0.0) * 100):.1f}%"
                earn = r.get("total_earnings", 0)
                earn_str = f"{earn // 10000:,}万円" if earn >= 10000 else f"{earn:,}円"

                rep_horses = r.get("representative_horses", [])
                rep_str = ", ".join(rep_horses) if rep_horses else "-"

                self.rank_table.setItem(idx, 0, QTableWidgetItem(f"{idx+1}位"))

                display_name = f"📈 {r.get('name', '')}"
                if is_rookie:
                    display_name += " [新]"
                name_item = QTableWidgetItem(display_name)
                name_item.setForeground(QColor("#22c55e") if is_rookie else QColor("#38bdf8"))
                self.rank_table.setItem(idx, 1, name_item)

                self.rank_table.setItem(idx, 2, QTableWidgetItem(age_str))
                self.rank_table.setItem(idx, 3, QTableWidgetItem(r.get("location", "")))
                self.rank_table.setItem(idx, 4, QTableWidgetItem(r.get("specialty", "")))

                # 持ち馬数・勝ち馬数はクリッカブル
                h_item = QTableWidgetItem(h_cnt_str)
                h_item.setForeground(QColor("#38bdf8"))
                self.rank_table.setItem(idx, 5, h_item)

                w_item = QTableWidgetItem(w_cnt_str)
                w_item.setForeground(QColor("#facc15"))
                self.rank_table.setItem(idx, 6, w_item)

                self.rank_table.setItem(idx, 7, QTableWidgetItem(record_str))
                self.rank_table.setItem(idx, 8, QTableWidgetItem(win_rate))
                self.rank_table.setItem(idx, 9, QTableWidgetItem(graded_str))
                self.rank_table.setItem(idx, 10, QTableWidgetItem(earn_str))
                self.rank_table.setItem(idx, 11, QTableWidgetItem(rep_str))

        elif cat == "owner":
            rows = self.rank_mgr.get_owner_rankings(is_career=is_career, limit=30)
            headers = ["順位", "馬主名 (推移グラフ)", "冠名", "持ち馬数", "勝ち馬数", "戦績 (1-2-3-外)", "重賞 (G1-G2-G3)", "資金残高", "獲得賞金", "代表持ち馬"]
            self.rank_table.setColumnCount(len(headers))
            self.rank_table.setHorizontalHeaderLabels(headers)
            self.rank_table.setRowCount(len(rows))

            for idx, r in enumerate(rows):
                self.row_entities.append({
                    "id": r.get("owner_id", 0),
                    "name": r.get("name", ""),
                    "category": "owner",
                })
                h_cnt_str = f"📋 {r.get('horse_count', 0)}頭"
                w_cnt_str = f"🏆 {r.get('winner_count', 0)}頭"
                w1 = r.get("win_1", 0)
                w2 = r.get("win_2", 0)
                w3 = r.get("win_3", 0)
                w_out = r.get("win_out", 0)
                record_str = f"{w1}-{w2}-{w3}-{w_out}"

                g1 = r.get("g1_cnt", 0)
                g2 = r.get("g2_cnt", 0)
                g3 = r.get("g3_cnt", 0)
                graded_str = f"{g1}-{g2}-{g3}"

                earn = r.get("total_earnings", 0)
                funds = r.get("funds", 0)
                earn_str = f"{earn // 10000:,}万円"
                funds_str = f"{funds // 10000:,}万円"

                rep_horses = r.get("representative_horses", [])
                rep_str = ", ".join(rep_horses) if rep_horses else "-"

                self.rank_table.setItem(idx, 0, QTableWidgetItem(f"{idx+1}位"))

                name_item = QTableWidgetItem(f"📈 {r.get('name', '')}")
                name_item.setForeground(QColor("#38bdf8"))
                self.rank_table.setItem(idx, 1, name_item)

                self.rank_table.setItem(idx, 2, QTableWidgetItem(r.get("prefix", "")))

                h_item = QTableWidgetItem(h_cnt_str)
                h_item.setForeground(QColor("#38bdf8"))
                self.rank_table.setItem(idx, 3, h_item)

                w_item = QTableWidgetItem(w_cnt_str)
                w_item.setForeground(QColor("#facc15"))
                self.rank_table.setItem(idx, 4, w_item)

                self.rank_table.setItem(idx, 5, QTableWidgetItem(record_str))
                self.rank_table.setItem(idx, 6, QTableWidgetItem(graded_str))
                self.rank_table.setItem(idx, 7, QTableWidgetItem(funds_str))
                self.rank_table.setItem(idx, 8, QTableWidgetItem(earn_str))
                self.rank_table.setItem(idx, 9, QTableWidgetItem(rep_str))

        elif cat == "breeder":
            rows = self.rank_mgr.get_breeder_rankings(is_career=is_career, limit=30)
            headers = ["順位", "牧場名 (推移グラフ)", "地域", "種牡馬", "繁殖牝馬", "生産頭数", "勝ち馬数", "戦績 (1-2-3-外)", "重賞 (G1-G2-G3)", "資金残高", "生産賞金", "代表産駒"]
            self.rank_table.setColumnCount(len(headers))
            self.rank_table.setHorizontalHeaderLabels(headers)
            self.rank_table.setRowCount(len(rows))

            for idx, r in enumerate(rows):
                self.row_entities.append({
                    "id": r.get("breeder_id", 0),
                    "name": r.get("name", ""),
                    "category": "breeder",
                })
                sire_cnt_str = f"{r.get('sire_count', 0)}頭"
                dam_cnt_str = f"{r.get('dam_count', 0)}頭"
                h_cnt_str = f"📋 {r.get('horse_count', 0)}頭"
                w_cnt_str = f"🏆 {r.get('winner_count', 0)}頭"
                w1 = r.get("win_1", 0)
                w2 = r.get("win_2", 0)
                w3 = r.get("win_3", 0)
                w_out = r.get("win_out", 0)
                record_str = f"{w1}-{w2}-{w3}-{w_out}"

                g1 = r.get("g1_cnt", 0)
                g2 = r.get("g2_cnt", 0)
                g3 = r.get("g3_cnt", 0)
                graded_str = f"{g1}-{g2}-{g3}"

                earn = r.get("total_earnings", 0)
                funds = r.get("funds", 0)
                earn_str = f"{earn // 10000:,}万円"
                funds_str = f"{funds // 10000:,}万円"

                rep_horses = r.get("representative_horses", [])
                rep_str = ", ".join(rep_horses) if rep_horses else "-"

                self.rank_table.setItem(idx, 0, QTableWidgetItem(f"{idx+1}位"))

                name_item = QTableWidgetItem(f"📈 {r.get('name', '')}")
                name_item.setForeground(QColor("#38bdf8"))
                self.rank_table.setItem(idx, 1, name_item)

                self.rank_table.setItem(idx, 2, QTableWidgetItem(r.get("region", "")))
                self.rank_table.setItem(idx, 3, QTableWidgetItem(sire_cnt_str))
                self.rank_table.setItem(idx, 4, QTableWidgetItem(dam_cnt_str))

                h_item = QTableWidgetItem(h_cnt_str)
                h_item.setForeground(QColor("#38bdf8"))
                self.rank_table.setItem(idx, 5, h_item)

                w_item = QTableWidgetItem(w_cnt_str)
                w_item.setForeground(QColor("#facc15"))
                self.rank_table.setItem(idx, 6, w_item)

                self.rank_table.setItem(idx, 7, QTableWidgetItem(record_str))
                self.rank_table.setItem(idx, 8, QTableWidgetItem(graded_str))
                self.rank_table.setItem(idx, 9, QTableWidgetItem(funds_str))
                self.rank_table.setItem(idx, 10, QTableWidgetItem(earn_str))
                self.rank_table.setItem(idx, 11, QTableWidgetItem(rep_str))

        elif cat == "sire":
            rows = self.rank_mgr.get_sire_rankings(
                is_career=is_career, limit=30, age_filter=self.sire_age_filter
            )
            headers = ["順位", "種牡馬名 (推移グラフ)", "サイアーライン", "種付料", "現役産駒", "戦績 (1-2-3-外)", "重賞 (G1-G2-G3)", "AEI", "獲得賞金", "代表産駒"]
            self.rank_table.setColumnCount(len(headers))
            self.rank_table.setHorizontalHeaderLabels(headers)
            self.rank_table.setRowCount(len(rows))

            for idx, r in enumerate(rows):
                sire_name = r.get("sire_name", r.get("name", ""))
                sire_hid = r.get("sire_horse_id", 0)
                sire_id = r.get("sire_id", 0)

                self.row_entities.append({
                    "id": sire_id,
                    "horse_id": sire_hid,
                    "name": sire_name,
                    "category": "sire",
                })

                sire_line = r.get("sire_line", "")
                stud_fee = r.get("stud_fee", 0)
                stud_fee_str = f"{stud_fee // 10000:,}万円" if stud_fee >= 10000 else f"{stud_fee:,}円"
                active_progeny = f"🐴 {r.get('active_progeny_count', 0)}頭"

                w1 = r.get("win_1", 0)
                w2 = r.get("win_2", 0)
                w3 = r.get("win_3", 0)
                w_out = r.get("win_out", 0)
                record_str = f"{w1}-{w2}-{w3}-{w_out}"

                g1 = r.get("g1_cnt", 0)
                g2 = r.get("g2_cnt", 0)
                g3 = r.get("g3_cnt", 0)
                graded_str = f"{g1}-{g2}-{g3}"

                earn = r.get("total_earnings", 0)
                earn_str = f"{earn // 10000:,}万円"
                aei_val = r.get("aei")
                aei_str = f"{aei_val:.2f}" if aei_val is not None else "-"

                rep_horses = r.get("representative_horses", [])
                rep_str = ", ".join(rep_horses) if rep_horses else "-"

                is_foreign = r.get("is_foreign", 0) == 1
                is_new = r.get("is_new", 0) == 1
                display_name = f"📈 {sire_name}"
                if is_foreign:
                    display_name += " [外]"
                elif is_new:
                    display_name += " [新]"

                self.rank_table.setItem(idx, 0, QTableWidgetItem(f"{idx+1}位"))

                sire_item = QTableWidgetItem(display_name)
                if is_foreign:
                    sire_item.setForeground(QColor("#ef4444"))
                elif is_new:
                    sire_item.setForeground(QColor("#22c55e"))
                else:
                    sire_item.setForeground(QColor("#38bdf8"))
                self.rank_table.setItem(idx, 1, sire_item)

                self.rank_table.setItem(idx, 2, QTableWidgetItem(sire_line))
                self.rank_table.setItem(idx, 3, QTableWidgetItem(stud_fee_str))

                progeny_item = QTableWidgetItem(active_progeny)
                progeny_item.setForeground(QColor("#facc15"))
                self.rank_table.setItem(idx, 4, progeny_item)

                self.rank_table.setItem(idx, 5, QTableWidgetItem(record_str))
                self.rank_table.setItem(idx, 6, QTableWidgetItem(graded_str))
                self.rank_table.setItem(idx, 7, QTableWidgetItem(aei_str))
                self.rank_table.setItem(idx, 8, QTableWidgetItem(earn_str))
                self.rank_table.setItem(idx, 9, QTableWidgetItem(rep_str))

    def _on_rank_cell_clicked(self, row: int, col: int) -> None:
        if not (0 <= row < len(self.row_entities)):
            return

        ent = self.row_entities[row]
        cat = ent.get("category", "")
        ent_id = ent.get("id", 0)
        ent_name = ent.get("name", "")

        # サイアーリーディングで産駒数列 (col=4)
        if cat == "sire" and col == 4:
            if ent_id > 0:
                dlg = ProgenyListDialog(self.db, ent_id, is_sire=True, parent=self)
                dlg.exec()
                return

        # 調教師: 持ち馬数(col=5), 勝ち馬数(col=6)
        if cat == "trainer" and col in (5, 6):
            dlg = EntityHorsesDialog(
                self.db, "trainer", ent_id, ent_name, only_winners=(col == 6), parent=self
            )
            dlg.exec()
            return

        # 馬主: 持ち馬数(col=3), 勝ち馬数(col=4)
        if cat == "owner" and col in (3, 4):
            dlg = EntityHorsesDialog(
                self.db, "owner", ent_id, ent_name, only_winners=(col == 4), parent=self
            )
            dlg.exec()
            return

        # 生産牧場: 生産頭数(col=5), 勝ち馬数(col=6)
        if cat == "breeder" and col in (5, 6):
            dlg = EntityHorsesDialog(
                self.db, "breeder", ent_id, ent_name, only_winners=(col == 6), parent=self
            )
            dlg.exec()
            return

        # それ以外は推移グラフ
        if ent_id > 0:
            dlg = RankingHistoryDialog(self.db, cat, ent_id, ent_name, parent=self)
            dlg.exec()

    def _load_tier_table(self) -> None:
        with self.db.session() as conn:
            b_rows = conn.execute(
                """
                SELECT breeder_id as id, name, region as extra, '牧場' as type,
                       horse_capacity as cap, reputation as rep, funds, career_earnings
                FROM breeders
                ORDER BY funds DESC LIMIT 30
                """
            ).fetchall()

            o_rows = conn.execute(
                """
                SELECT owner_id as id, name, prefix as extra, '馬主' as type,
                       horse_capacity as cap, 0.0 as rep, funds, career_earnings
                FROM owners
                ORDER BY funds DESC LIMIT 30
                """
            ).fetchall()

        all_rows = list(b_rows) + list(o_rows)
        all_rows.sort(key=lambda x: x["funds"], reverse=True)

        self.tier_table.setRowCount(len(all_rows))
        for idx, r in enumerate(all_rows):
            funds = r["funds"]
            if funds >= 2_000_000_000:
                tier = "【S】超大手"
            elif funds >= 1_000_000_000:
                tier = "【A】大手"
            elif funds >= 500_000_000:
                tier = "【B】中堅"
            else:
                tier = "【C】一般"

            self.tier_table.setItem(idx, 0, QTableWidgetItem(f"{r['type']}{r['id']}"))
            self.tier_table.setItem(idx, 1, QTableWidgetItem(r["name"]))
            self.tier_table.setItem(idx, 2, QTableWidgetItem(r["extra"]))
            self.tier_table.setItem(idx, 3, QTableWidgetItem(tier))
            self.tier_table.setItem(idx, 4, QTableWidgetItem(f"上限{r['cap']}頭"))
            self.tier_table.setItem(idx, 5, QTableWidgetItem(f"{funds // 10000:,}万円"))
            self.tier_table.setItem(idx, 6, QTableWidgetItem(f"{r['career_earnings'] // 10000:,}万円"))
