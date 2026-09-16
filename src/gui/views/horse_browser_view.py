"""
馬情報検索・一覧・詳細・5代血統表ブラウザ (PyQt6)
- 多条件フィルター（現役/種牡馬/繁殖牝馬/引退、年齢、性別、MSTN、テキスト検索）
- 馬詳細情報（ポリジーン能力値バー、戦績、獲得賞金、主な勝ち鞍）
- インタラクティブ5代血統表（祖先馬クリックで即座に血統ジャンプ）
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.db.database import Database
from src.gui.widgets.pedigree_widget import PedigreeWidget
from src.views.pedigree_builder import PedigreeBuilder


class StatBar(QWidget):
    """能力値プログレスバー（0.0〜100.0）"""

    def __init__(self, label: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        lbl = QLabel(label)
        lbl.setFixedWidth(60)
        lbl.setStyleSheet("color: #94a3b8; font-weight: bold;")
        layout.addWidget(lbl)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setFixedHeight(12)
        self.bar.setTextVisible(False)
        layout.addWidget(self.bar)

        self.val_lbl = QLabel("0.0")
        self.val_lbl.setFixedWidth(40)
        self.val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.val_lbl.setStyleSheet("font-weight: bold; color: #f8fafc;")
        layout.addWidget(self.val_lbl)

    def set_val(self, val: float, color: str = "#38bdf8") -> None:
        int_val = int(round(val))
        self.bar.setValue(int_val)
        self.val_lbl.setText(f"{val:.1f}")
        self.bar.setStyleSheet(f"""
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 4px;
            }}
        """)


class HorseBrowserView(QWidget):
    """馬情報ブラウザ画面"""

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.pedigree_builder = PedigreeBuilder(db)
        self.current_horse_id: Optional[int] = None
        self._init_ui()
        self.search_horses()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. フィルター・検索バー
        filter_frame = QFrame()
        filter_frame.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 8px;")
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(12, 8, 12, 8)
        filter_layout.setSpacing(10)

        # 区分フィルター
        filter_layout.addWidget(QLabel("区分:"))
        self.combo_status = QComboBox()
        self.combo_status.addItems(["現役競走馬", "種牡馬", "繁殖牝馬", "当歳・1歳馬", "引退馬", "全競走馬"])
        self.combo_status.currentIndexChanged.connect(self.search_horses)
        filter_layout.addWidget(self.combo_status)

        # 性別フィルター
        filter_layout.addWidget(QLabel("性別:"))
        self.combo_sex = QComboBox()
        self.combo_sex.addItems(["すべて", "牡馬", "牝馬"])
        self.combo_sex.currentIndexChanged.connect(self.search_horses)
        filter_layout.addWidget(self.combo_sex)

        # MSTN
        filter_layout.addWidget(QLabel("MSTN:"))
        self.combo_mstn = QComboBox()
        self.combo_mstn.addItems(["すべて", "C/C (短距離)", "C/T (万能)", "T/T (長距離)"])
        self.combo_mstn.currentIndexChanged.connect(self.search_horses)
        filter_layout.addWidget(self.combo_mstn)

        # テキスト検索
        filter_layout.addWidget(QLabel("馬名検索:"))
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("馬名の一部を入力...")
        self.txt_search.textChanged.connect(self.search_horses)
        filter_layout.addWidget(self.txt_search)

        self.btn_refresh = QPushButton("更新")
        self.btn_refresh.clicked.connect(self.search_horses)
        filter_layout.addWidget(self.btn_refresh)

        main_layout.addWidget(filter_frame)

        # 2. スプリッター（左: テーブル一覧、右: 詳細＆血統）
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左側: テーブル
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "ID", "馬名", "性齢", "MSTN", "脚質", "速度", "持久", "瞬発", "戦績", "重賞勝", "獲得賞金"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_horse_selected)
        left_layout.addWidget(self.table)

        self.lbl_count = QLabel("表示中: 0 頭")
        self.lbl_count.setStyleSheet("color: #94a3b8; font-size: 11px;")
        left_layout.addWidget(self.lbl_count)

        splitter.addWidget(left_widget)

        # 右側: 詳細パネル & 5代血統表タブ
        right_tab = QTabWidget()

        # 詳細タブ
        detail_tab = QWidget()
        detail_layout = QVBoxLayout(detail_tab)
        detail_layout.setContentsMargins(12, 12, 12, 12)

        # 基本プロファイル
        prof_box = QGroupBox("基本情報")
        prof_layout = QFormLayout(prof_box)
        self.lbl_d_name = QLabel("-")
        self.lbl_d_name.setStyleSheet("font-size: 18px; font-weight: 800; color: #38bdf8;")
        self.lbl_d_profile = QLabel("-")
        self.lbl_d_owner_breeder = QLabel("-")
        self.lbl_d_trainer_jockey = QLabel("-")
        self.lbl_d_record = QLabel("-")
        self.lbl_d_prize = QLabel("-")
        self.lbl_d_major = QLabel("-")
        self.lbl_d_major.setStyleSheet("color: #f59e0b; font-weight: bold;")

        prof_layout.addRow("馬名:", self.lbl_d_name)
        prof_layout.addRow("性齢・遺伝:", self.lbl_d_profile)
        prof_layout.addRow("馬主/牧場:", self.lbl_d_owner_breeder)
        prof_layout.addRow("厩舎/主戦:", self.lbl_d_trainer_jockey)
        prof_layout.addRow("通算戦績:", self.lbl_d_record)
        prof_layout.addRow("獲得賞金:", self.lbl_d_prize)
        prof_layout.addRow("主な勝鞍:", self.lbl_d_major)
        detail_layout.addWidget(prof_box)

        # 能力値バー
        ability_box = QGroupBox("遺伝・ポリジーン能力値")
        ability_layout = QVBoxLayout(ability_box)
        self.bar_spd = StatBar("最高速度")
        self.bar_sta = StatBar("持久力")
        self.bar_acc = StatBar("瞬発力")
        self.bar_tem = StatBar("気性")
        self.bar_dur = StatBar("耐久力")
        self.bar_vit = StatBar("母性活力")

        ability_layout.addWidget(self.bar_spd)
        ability_layout.addWidget(self.bar_sta)
        ability_layout.addWidget(self.bar_acc)
        ability_layout.addWidget(self.bar_tem)
        ability_layout.addWidget(self.bar_dur)
        ability_layout.addWidget(self.bar_vit)
        detail_layout.addWidget(ability_box)

        detail_layout.addStretch()
        right_tab.addTab(detail_tab, "詳細ステータス")

        # 5代血統表タブ
        self.pedigree_widget = PedigreeWidget()
        self.pedigree_widget.horse_selected.connect(self.select_horse_by_id)
        right_tab.addTab(self.pedigree_widget, "5代血統表")

        splitter.addWidget(right_tab)
        splitter.setSizes([550, 450])

        main_layout.addWidget(splitter)

    def search_horses(self) -> None:
        """条件に基づき馬一覧を検索・表示"""
        status_idx = self.combo_status.currentIndex()
        sex_idx = self.combo_sex.currentIndex()
        mstn_idx = self.combo_mstn.currentIndex()
        keyword = self.txt_search.text().strip()

        query = """
            SELECT h.horse_id, h.name, h.sex, h.age, h.mstn_type, h.running_style,
                   h.speed, h.stamina, h.acceleration,
                   h.career_starts, h.career_wins, h.g1_wins, h.g2_wins, h.g3_wins,
                   h.prize_money,
                   o.name as owner_name, b.name as breeder_name
            FROM horses h
            LEFT JOIN owners o ON h.owner_id = o.owner_id
            LEFT JOIN breeders b ON h.breeder_id = b.breeder_id
            WHERE 1=1
        """
        params = []

        if status_idx == 0:  # 現役
            query += " AND h.is_active = 1"
        elif status_idx == 1:  # 種牡馬
            query += " AND h.is_sire = 1"
        elif status_idx == 2:  # 繁殖牝馬
            query += " AND h.is_dam = 1"
        elif status_idx == 3:  # 当歳・1歳
            query += " AND h.age < 2 AND h.is_active = 0 AND h.is_sire = 0 AND h.is_dam = 0"
        elif status_idx == 4:  # 引退馬
            query += " AND h.age >= 2 AND h.is_active = 0 AND h.is_sire = 0 AND h.is_dam = 0"

        if sex_idx == 1:
            query += " AND h.sex IN ('colt', 'horse')"
        elif sex_idx == 2:
            query += " AND h.sex IN ('filly', 'mare')"

        if mstn_idx == 1:
            query += " AND h.mstn_type = 'C/C'"
        elif mstn_idx == 2:
            query += " AND h.mstn_type = 'C/T'"
        elif mstn_idx == 3:
            query += " AND h.mstn_type = 'T/T'"

        if keyword:
            query += " AND h.name LIKE ?"
            params.append(f"%{keyword}%")

        query += " ORDER BY h.prize_money DESC, h.horse_id ASC LIMIT 100"

        with self.db.session() as conn:
            rows = conn.execute(query, params).fetchall()

        self.table.setRowCount(len(rows))
        sex_map = {"colt": "牡", "filly": "牝", "horse": "牡", "mare": "牝", "gelding": "騸"}
        style_map = {"escape": "逃げ", "leading": "先行", "between": "差し", "closing": "追込"}

        for row_idx, r in enumerate(rows):
            sex_str = f"{sex_map.get(r['sex'], r['sex'])}{r['age']}"
            style_str = style_map.get(r['running_style'], "-")
            rec_str = f"{r['career_starts']}戦{r['career_wins']}勝"
            graded_str = f"{r['g1_wins']}/{r['g2_wins']}/{r['g3_wins']}"

            self.table.setItem(row_idx, 0, QTableWidgetItem(str(r["horse_id"])))
            self.table.setItem(row_idx, 1, QTableWidgetItem(r["name"]))
            self.table.setItem(row_idx, 2, QTableWidgetItem(sex_str))
            self.table.setItem(row_idx, 3, QTableWidgetItem(r["mstn_type"]))
            self.table.setItem(row_idx, 4, QTableWidgetItem(style_str))
            self.table.setItem(row_idx, 5, QTableWidgetItem(f"{r['speed']:.1f}"))
            self.table.setItem(row_idx, 6, QTableWidgetItem(f"{r['stamina']:.1f}"))
            self.table.setItem(row_idx, 7, QTableWidgetItem(f"{r['acceleration']:.1f}"))
            self.table.setItem(row_idx, 8, QTableWidgetItem(rec_str))
            self.table.setItem(row_idx, 9, QTableWidgetItem(graded_str))
            self.table.setItem(row_idx, 10, QTableWidgetItem(f"{r['prize_money']:,}円"))

        self.lbl_count.setText(f"表示中: {len(rows)} 頭 (上限100頭)")
        if rows:
            self.table.selectRow(0)

    def _on_horse_selected(self) -> None:
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            row_idx = selected_rows[0].row()
            h_id_item = self.table.item(row_idx, 0)
            if h_id_item:
                h_id = int(h_id_item.text())
                self.select_horse_by_id(h_id)

    def select_horse_by_id(self, horse_id: int) -> None:
        """指定IDの馬詳細および血統表を表示"""
        self.current_horse_id = horse_id
        with self.db.session() as conn:
            r = conn.execute(
                """
                SELECT h.*, o.name as owner_name, b.name as breeder_name,
                       t.name as trainer_name, j.name as jockey_name
                FROM horses h
                LEFT JOIN owners o ON h.owner_id = o.owner_id
                LEFT JOIN breeders b ON h.breeder_id = b.breeder_id
                LEFT JOIN trainers t ON h.trainer_id = t.trainer_id
                LEFT JOIN jockeys j ON h.jockey_id = j.jockey_id
                WHERE h.horse_id = ?
                """,
                (horse_id,),
            ).fetchone()

        if not r:
            return

        sex_map = {"colt": "牡", "filly": "牝", "horse": "牡", "mare": "牝", "gelding": "騸"}
        growth_map = {"early": "早熟", "normal": "普通", "late": "晩成"}
        style_map = {"escape": "逃げ", "leading": "先行", "between": "差し", "closing": "追込"}

        self.lbl_d_name.setText(f"{r['name']} (ID: {r['horse_id']})")
        self.lbl_d_profile.setText(
            f"{sex_map.get(r['sex'], r['sex'])} {r['age']}歳 / MSTN: {r['mstn_type']} / "
            f"成長: {growth_map.get(r['growth_type'], r['growth_type'])} / 脚質: {style_map.get(r['running_style'], '-')}"
        )
        self.lbl_d_owner_breeder.setText(f"馬主: {r['owner_name'] or '―'} / 生産: {r['breeder_name'] or '―'}")
        self.lbl_d_trainer_jockey.setText(f"厩舎: {r['trainer_name'] or '―'} / 主戦: {r['jockey_name'] or '―'}")
        self.lbl_d_record.setText(
            f"{r['career_starts']}戦 {r['career_wins']}勝 (G1: {r['g1_wins']}勝 / G2: {r['g2_wins']}勝 / G3: {r['g3_wins']}勝)"
        )
        self.lbl_d_prize.setText(f"{r['prize_money']:,} 円")
        self.lbl_d_major.setText(r["major_wins"] or "なし")

        # 能力値バー
        self.bar_spd.set_val(r["speed"], "#38bdf8")
        self.bar_sta.set_val(r["stamina"], "#10b981")
        self.bar_acc.set_val(r["acceleration"], "#f59e0b")
        self.bar_tem.set_val(r["temperament"], "#a855f7")
        self.bar_dur.set_val(r["durability"], "#ec4899")
        self.bar_vit.set_val(r["maternal_vitality"], "#06b6d4")

        # 5代血統表の更新
        tree = self.pedigree_builder.get_ancestors_tree(horse_id, depth=5)
        self.pedigree_widget.set_tree_data(tree)
