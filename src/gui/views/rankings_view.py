"""
5大リーディング & 生産牧場・馬主規模推移ビュー (PyQt6)
- 騎手、調教師、馬主、生産牧場、サイアーのランキング表示 (年間/通算)
- 牧場・馬主の動的分化・規模階層（資金・頭数）一覧
"""

from __future__ import annotations

from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.db.database import Database
from src.race.rankings import RankingManager


class RankingsView(QWidget):
    """5大リーディング & 牧場・馬主規模推移画面"""

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.rank_mgr = RankingManager(db)
        self.current_category = "jockey"
        self.is_career = False
        self._init_ui()
        self.refresh_data()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. ナビゲーションバー（カテゴリ選択 & 年間/通算トグル）
        nav_frame = QFrame()
        nav_frame.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 8px;")
        nav_layout = QHBoxLayout(nav_frame)
        nav_layout.setContentsMargins(12, 8, 12, 8)

        # カテゴリ切り替えボタン
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

        nav_layout.addStretch()

        # 年間 / 通算
        self.rb_year = QRadioButton("当年成績")
        self.rb_year.setChecked(True)
        self.rb_year.toggled.connect(self._on_term_changed)
        self.rb_career = QRadioButton("通算成績")
        self.rb_career.toggled.connect(self._on_term_changed)

        nav_layout.addWidget(self.rb_year)
        nav_layout.addWidget(self.rb_career)

        main_layout.addWidget(nav_frame)

        # 2. メインタブ（ランキング一覧 & 牧場・馬主規模階層）
        tabs = QTabWidget()

        # リーディングランキングテーブル
        self.rank_table = QTableWidget()
        self.rank_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.rank_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        tabs.addTab(self.rank_table, "リーディングランキング TOP 20")

        # 規模階層テーブル（牧場・馬主の動的分化）
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
        self.refresh_data()

    def _on_term_changed(self) -> None:
        self.is_career = self.rb_career.isChecked()
        self.refresh_data()

    def refresh_data(self) -> None:
        """ランキングテーブルと規模階層テーブルを更新"""
        self._load_ranking_table()
        self._load_tier_table()

    def _load_ranking_table(self) -> None:
        """指定カテゴリのリーディングランキングを読み込み"""
        is_career = self.is_career
        cat = self.current_category

        if cat == "jockey":
            rows = self.rank_mgr.get_jockey_rankings(limit=20)
            headers = ["順位", "騎手名", "所属", "区分", "戦績", "勝率", "重賞(G1/G2/G3)", "獲得賞金"]
            self.rank_table.setColumnCount(len(headers))
            self.rank_table.setHorizontalHeaderLabels(headers)
            self.rank_table.setRowCount(len(rows))

            for idx, r in enumerate(rows):
                free_str = "フリー" if r.get("is_free", 0) == 1 else "所属"
                starts = r.get("career_starts", 0) if is_career else r.get("current_year_starts", r.get("career_starts", 0))
                wins = r.get("career_wins", 0) if is_career else r.get("current_year_wins", r.get("career_wins", 0))
                rec_str = f"{starts}戦{wins}勝"
                win_rate = f"{(wins / starts * 100):.1f}%" if starts > 0 else "0.0%"
                g1 = r.get("g1_wins", 0) if is_career else r.get("current_year_g1", r.get("g1_wins", 0))
                g2 = r.get("g2_wins", 0) if is_career else r.get("current_year_g2", r.get("g2_wins", 0))
                g3 = r.get("g3_wins", 0) if is_career else r.get("current_year_g3", r.get("g3_wins", 0))
                earn = r.get("career_earnings", 0) if is_career else r.get("current_year_earnings", r.get("career_earnings", 0))

                self.rank_table.setItem(idx, 0, QTableWidgetItem(f"{idx+1}位"))
                self.rank_table.setItem(idx, 1, QTableWidgetItem(r.get("name", "")))
                self.rank_table.setItem(idx, 2, QTableWidgetItem(r.get("location", "")))
                self.rank_table.setItem(idx, 3, QTableWidgetItem(free_str))
                self.rank_table.setItem(idx, 4, QTableWidgetItem(rec_str))
                self.rank_table.setItem(idx, 5, QTableWidgetItem(win_rate))
                self.rank_table.setItem(idx, 6, QTableWidgetItem(f"{g1}/{g2}/{g3}"))
                self.rank_table.setItem(idx, 7, QTableWidgetItem(f"{earn:,}円"))

        elif cat == "trainer":
            rows = self.rank_mgr.get_trainer_rankings(limit=20)
            headers = ["順位", "厩舎名", "所属", "得意分野", "所属頭数", "スキル", "戦績", "重賞(G1/G2/G3)", "獲得賞金"]
            self.rank_table.setColumnCount(len(headers))
            self.rank_table.setHorizontalHeaderLabels(headers)
            self.rank_table.setRowCount(len(rows))

            for idx, r in enumerate(rows):
                starts = r.get("career_starts", 0)
                wins = r.get("career_wins", 0)
                g1 = r.get("g1_wins", 0)
                g2 = r.get("g2_wins", 0)
                g3 = r.get("g3_wins", 0)
                earn = r.get("prize_money", 0)
                skill = r.get("skill_level", 50.0)

                self.rank_table.setItem(idx, 0, QTableWidgetItem(f"{idx+1}位"))
                self.rank_table.setItem(idx, 1, QTableWidgetItem(r.get("name", "")))
                self.rank_table.setItem(idx, 2, QTableWidgetItem(r.get("location", "")))
                self.rank_table.setItem(idx, 3, QTableWidgetItem(r.get("specialty", "")))
                self.rank_table.setItem(idx, 4, QTableWidgetItem("-"))
                self.rank_table.setItem(idx, 5, QTableWidgetItem(f"{skill:.1f}"))
                self.rank_table.setItem(idx, 6, QTableWidgetItem(f"{starts}戦{wins}勝"))
                self.rank_table.setItem(idx, 7, QTableWidgetItem(f"{g1}/{g2}/{g3}"))
                self.rank_table.setItem(idx, 8, QTableWidgetItem(f"{earn:,}円"))

        elif cat == "owner":
            rows = self.rank_mgr.get_owner_rankings(limit=20)
            headers = ["順位", "馬主名", "冠名", "勝数", "G1勝", "資金残高", "獲得賞金"]
            self.rank_table.setColumnCount(len(headers))
            self.rank_table.setHorizontalHeaderLabels(headers)
            self.rank_table.setRowCount(len(rows))

            for idx, r in enumerate(rows):
                wins = r.get("career_wins", 0)
                earn = r.get("total_prize_money", 0)
                funds = r.get("funds", 0)
                g1 = r.get("g1_wins", 0)

                self.rank_table.setItem(idx, 0, QTableWidgetItem(f"{idx+1}位"))
                self.rank_table.setItem(idx, 1, QTableWidgetItem(r.get("name", "")))
                self.rank_table.setItem(idx, 2, QTableWidgetItem(r.get("prefix", "")))
                self.rank_table.setItem(idx, 3, QTableWidgetItem(f"{wins}勝"))
                self.rank_table.setItem(idx, 4, QTableWidgetItem(f"{g1}勝"))
                self.rank_table.setItem(idx, 5, QTableWidgetItem(f"{funds:,}円"))
                self.rank_table.setItem(idx, 6, QTableWidgetItem(f"{earn:,}円"))

        elif cat == "breeder":
            rows = self.rank_mgr.get_breeder_rankings(limit=20)
            headers = ["順位", "牧場名", "地方", "勝数", "G1勝", "資金残高", "生産賞金"]
            self.rank_table.setColumnCount(len(headers))
            self.rank_table.setHorizontalHeaderLabels(headers)
            self.rank_table.setRowCount(len(rows))

            for idx, r in enumerate(rows):
                wins = r.get("career_wins", 0)
                earn = r.get("total_prize_money", 0)
                funds = r.get("funds", 0)
                g1 = r.get("g1_wins", 0)

                self.rank_table.setItem(idx, 0, QTableWidgetItem(f"{idx+1}位"))
                self.rank_table.setItem(idx, 1, QTableWidgetItem(r.get("name", "")))
                self.rank_table.setItem(idx, 2, QTableWidgetItem(r.get("region", "")))
                self.rank_table.setItem(idx, 3, QTableWidgetItem(f"{wins}勝"))
                self.rank_table.setItem(idx, 4, QTableWidgetItem(f"{g1}勝"))
                self.rank_table.setItem(idx, 5, QTableWidgetItem(f"{funds:,}円"))
                self.rank_table.setItem(idx, 6, QTableWidgetItem(f"{earn:,}円"))

        elif cat == "sire":
            rows = self.rank_mgr.get_sire_rankings(limit=20)
            headers = ["順位", "種牡馬名", "サイアーライン", "種付料", "産駒数", "勝数", "G1勝", "AEI", "獲得賞金"]
            self.rank_table.setColumnCount(len(headers))
            self.rank_table.setHorizontalHeaderLabels(headers)
            self.rank_table.setRowCount(len(rows))

            for idx, r in enumerate(rows):
                sire_name = r.get("sire_name", r.get("name", ""))
                sire_line = r.get("sire_line", "")
                stud_fee = r.get("stud_fee", 0)
                p_count = r.get("progeny_count", 0)
                wins = r.get("progeny_wins", r.get("career_wins", 0))
                g1_wins = r.get("progeny_g1_wins", r.get("g1_wins", 0))
                earn = r.get("progeny_prize_money", r.get("career_earnings", 0))
                aei_val = r.get("aei")
                aei_str = f"{aei_val:.2f}" if aei_val is not None else "-"

                self.rank_table.setItem(idx, 0, QTableWidgetItem(f"{idx+1}位"))
                self.rank_table.setItem(idx, 1, QTableWidgetItem(sire_name))
                self.rank_table.setItem(idx, 2, QTableWidgetItem(sire_line))
                self.rank_table.setItem(idx, 3, QTableWidgetItem(f"{stud_fee:,}円"))
                self.rank_table.setItem(idx, 4, QTableWidgetItem(f"{p_count}頭"))
                self.rank_table.setItem(idx, 5, QTableWidgetItem(f"{wins}勝"))
                self.rank_table.setItem(idx, 6, QTableWidgetItem(f"{g1_wins}勝"))
                self.rank_table.setItem(idx, 7, QTableWidgetItem(aei_str))
                self.rank_table.setItem(idx, 8, QTableWidgetItem(f"{earn:,}円"))

    def _load_tier_table(self) -> None:
        """生産牧場および馬主の規模階層データを読み込み"""
        with self.db.session() as conn:
            # 上位牧場と上位馬主を抽出
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
            # 規模階層ランク（S: 超大手, A: 大手, B: 中堅, C: 一般）
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
            self.tier_table.setItem(idx, 5, QTableWidgetItem(f"{funds:,}円"))
            self.tier_table.setItem(idx, 6, QTableWidgetItem(f"{r['career_earnings']:,}円"))
