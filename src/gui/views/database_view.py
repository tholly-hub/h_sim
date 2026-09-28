"""
競馬データベース総合ビュー (DatabaseView)
- 競走馬リーディング（2歳/3歳/古馬 × 総合/牡/牝 9区分賞金ランキング）
- 世代・クラス別競走馬名鑑（世代・クラス別頭数集計、獲得賞金順名鑑、未出走・未勝利一覧）
- 主要レース路線タブ（3歳牡馬/牝馬/ダート3冠、古馬短距離/マイル/中距離/長距離/牝馬/グランプリ/ダート2冠の歴代マトリクス）
- 種牡馬リストタブ（現役/全世代、[新][外]表記、産駒一覧ダイアログ連携）
- 繁殖牝馬リストタブ（現役600頭/全世代、産駒一覧ダイアログ連携）
- 過去の重賞レースデータベース（歴代G1/G2/G3結果・動画ボタン完備）
- コースレコード一覧（競馬場別タブ・芝ダート短距離昇順・父母表示・結果動画ボタン完備）
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.db.database import Database, get_db
from src.gui.styles import get_generation_color
from src.gui.views.dam_detail_dialog import DamDetailDialog
from src.gui.views.horse_detail_dialog import HorseDetailDialog, GRADE_COLOR_MAP
from src.gui.views.progeny_dialog import ProgenyListDialog
from src.gui.views.race_dialogs import RaceResultDialog, RaceViewDialog
from src.gui.views.records_view import RecordsView, format_finish_time
from src.gui.views.sire_detail_dialog import SireDetailDialog
from src.race.engine import clean_race_name


MAJOR_ROUTES = [
    {
        "id": "classic_colt",
        "name": "👑 3歳牡馬3冠",
        "races": ["皐月賞", "東京優駿（日本ダービー）", "菊花賞"],
        "labels": ["第1冠: 皐月賞", "第2冠: 東京優駿（日本ダービー）", "第3冠: 菊花賞"],
    },
    {
        "id": "triple_tiara",
        "name": "🌸 3歳牝馬3冠 (トリプルティアラ)",
        "races": ["桜花賞", "優駿牝馬（オークス）", "秋華賞"],
        "labels": ["第1冠: 桜花賞", "第2冠: 優駿牝馬（オークス）", "第3冠: 秋華賞"],
    },
    {
        "id": "dirt_3yo",
        "name": "🏜 3歳ダート3冠",
        "races": ["羽田盃", "東京ダービー", "ジャパンダートクラシック"],
        "labels": ["第1冠: 羽田盃", "第2冠: 東京ダービー", "第3冠: JDC"],
    },
    {
        "id": "sprint",
        "name": "⚡ 古馬短距離2冠",
        "races": ["高松宮記念", "スプリンターズS"],
        "labels": ["春: 高松宮記念", "秋: スプリンターズS"],
    },
    {
        "id": "mile",
        "name": "🔥 古ママイル2冠",
        "races": ["安田記念", "マイルチャンピオンシップ"],
        "labels": ["春: 安田記念", "秋: マイルCS"],
    },
    {
        "id": "intermediate",
        "name": "🏆 古馬中距離2冠",
        "races": ["大阪杯", "天皇賞（秋）"],
        "labels": ["春: 大阪杯", "秋: 天皇賞(秋)"],
    },
    {
        "id": "long",
        "name": "🏇 古馬長距離2冠 (王道・世界)",
        "races": ["天皇賞（春）", "ジャパンカップ"],
        "labels": ["春: 天皇賞(春)", "秋: ジャパンC"],
    },
    {
        "id": "older_female",
        "name": "🌸 古馬牝馬2冠 (マイル・中距離)",
        "races": ["ヴィクトリアマイル", "エリザベス女王杯"],
        "labels": ["春: ヴィクトリアM", "秋: エリザベス女王杯"],
    },
    {
        "id": "dirt_older",
        "name": "🏜 ダート王道路線",
        "races": ["フェブラリーS", "チャンピオンズカップ", "東京大賞典"],
        "labels": ["春: フェブラリーS", "秋: チャンピオンズC", "冬: 東京大賞典"],
    },
    {
        "id": "grand_prix",
        "name": "⭐ グランプリ2冠 (春・秋/冬)",
        "races": ["宝塚記念", "有馬記念"],
        "labels": ["春: 宝塚記念", "冬: 有馬記念"],
    },
]

# 主要レース路線の表記揺れ吸収用エイリアスマップ
ROUTE_RACE_ALIASES: Dict[str, str] = {
    "日本ダービー": "東京優駿（日本ダービー）",
    "東京優駿": "東京優駿（日本ダービー）",
    "東京優駿(日本ダービー)": "東京優駿（日本ダービー）",
    "オークス": "優駿牝馬（オークス）",
    "優駿牝馬": "優駿牝馬（オークス）",
    "優駿牝馬(オークス)": "優駿牝馬（オークス）",
    "スプリンターズステークス": "スプリンターズS",
    "フェブラリーステークス": "フェブラリーS",
    "マイルCS": "マイルチャンピオンシップ",
    "チャンピオンズC": "チャンピオンズカップ",
    "JDC": "ジャパンダートクラシック",
    "ジャパンC": "ジャパンカップ",
}


class DatabaseView(QWidget):
    """競馬データベース総合ビュー"""

    def __init__(self, db: Optional[Database] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db or get_db()
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(6)

        self.main_tabs = QTabWidget()
        self.main_tabs.setStyleSheet("""
            QTabBar::tab {
                font-weight: bold;
                font-size: 13px;
                padding: 7px 14px;
            }
        """)

        # 1. 競走馬リーディング
        self.tab_leading = self._create_leading_tab()
        self.main_tabs.addTab(self.tab_leading, "🥇 競走馬リーディング")

        # 2. 世代・クラス別名鑑
        self.tab_cohort = self._create_cohort_class_tab()
        self.main_tabs.addTab(self.tab_cohort, "📊 世代・クラス別名鑑")

        # 3. 主要レース路線 (新設)
        self.tab_routes = self._create_major_routes_tab()
        self.main_tabs.addTab(self.tab_routes, "🏆 主要レース路線")

        # 4. 種牡馬リスト (新設)
        self.tab_sires = self._create_sires_list_tab()
        self.main_tabs.addTab(self.tab_sires, "🐴 種牡馬リスト")

        # 5. 繁殖牝馬リスト (新設)
        self.tab_broodmares = self._create_broodmares_list_tab()
        self.main_tabs.addTab(self.tab_broodmares, "🌸 繁殖牝馬リスト")

        # 6. 過去の重賞レースDB
        self.tab_graded = self._create_graded_tab()
        self.main_tabs.addTab(self.tab_graded, "🎖 重賞レースDB")

        # 7. コースレコード一覧
        self.tab_records = RecordsView(self.db, parent=self)
        self.main_tabs.addTab(self.tab_records, "⏱ コースレコード")

        main_layout.addWidget(self.main_tabs)

        # サブタブ切り替え時の遅延ロード接続
        self.main_tabs.currentChanged.connect(self._on_tab_changed)

        # 初回はアクティブな第1タブ（競走馬リーディング）のみ読み込み
        self._refresh_leading_filters()
        self.refresh_leading()

    def _on_tab_changed(self, index: int) -> None:
        """タブが選択された時に該当タブのデータを最新化（遅延ロード）"""
        if index == 0:
            self._refresh_leading_filters()
            self.refresh_leading()
        elif index == 1:
            self._refresh_cohort_filters()
            self.refresh_cohort_class()
        elif index == 2:
            self.refresh_major_routes()
        elif index == 3:
            self._on_sires_subtab_changed(self.sires_sub_tabs.currentIndex())
        elif index == 4:
            self._on_dams_subtab_changed(self.dams_sub_tabs.currentIndex())
        elif index == 5:
            self._refresh_graded_years()
            self.refresh_graded()
        elif index == 6:
            if hasattr(self.tab_records, "refresh_records"):
                self.tab_records.refresh_records()

    def refresh_all(self) -> None:
        """現在表示中のサブタブのデータを最新化"""
        self._on_tab_changed(self.main_tabs.currentIndex())

    # ==========================================
    # 1. 競走馬リーディング
    # ==========================================
    def _create_leading_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        filter_bar = QFrame()
        filter_bar.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 6px;")
        f_layout = QHBoxLayout(filter_bar)
        f_layout.setContentsMargins(10, 6, 10, 6)
        f_layout.setSpacing(12)

        f_layout.addWidget(QLabel("集計期間:"))
        self.combo_lead_period = QComboBox()
        self.combo_lead_period.currentIndexChanged.connect(self.refresh_leading)
        f_layout.addWidget(self.combo_lead_period)

        f_layout.addWidget(QLabel("区分:"))
        self.combo_lead_category = QComboBox()
        self.combo_lead_category.addItem("全馬総合", "all_all")
        self.combo_lead_category.addItem("現役馬総合", "active_all")
        self.combo_lead_category.addItem("現役古馬総合", "active_older_all")
        self.combo_lead_category.addItem("現役古馬牡馬", "active_older_colt")
        self.combo_lead_category.addItem("現役古馬牝馬", "active_older_filly")
        self.combo_lead_category.addItem("現役３歳馬総合", "active_3yo_all")
        self.combo_lead_category.addItem("現役３歳牡馬", "active_3yo_colt")
        self.combo_lead_category.addItem("現役３歳牝馬", "active_3yo_filly")
        self.combo_lead_category.addItem("現役２歳馬", "active_2yo_all")
        self.combo_lead_category.currentIndexChanged.connect(self.refresh_leading)
        f_layout.addWidget(self.combo_lead_category)

        btn_ref = QPushButton("🔄 更新")
        btn_ref.setStyleSheet("background-color: #0284c7; color: #ffffff; font-weight: bold; padding: 4px 12px; border-radius: 4px;")
        btn_ref.clicked.connect(self.refresh_leading)
        f_layout.addWidget(btn_ref)

        f_layout.addStretch()
        layout.addWidget(filter_bar)

        self.table_leading = QTableWidget()
        self.table_leading.setColumnCount(11)
        self.table_leading.setHorizontalHeaderLabels([
            "順位", "競走馬名", "性齢", "サイアー", "母馬", "厩舎", "出走数", "勝数", "重賞勝数", "獲得賞金", "詳細"
        ])
        h_header = self.table_leading.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_leading.setColumnWidth(0, 50)
        self.table_leading.setColumnWidth(1, 160)
        self.table_leading.setColumnWidth(2, 55)
        self.table_leading.setColumnWidth(3, 130)
        self.table_leading.setColumnWidth(4, 130)
        self.table_leading.setColumnWidth(5, 95)
        self.table_leading.setColumnWidth(6, 60)
        self.table_leading.setColumnWidth(7, 50)
        self.table_leading.setColumnWidth(8, 70)
        self.table_leading.setColumnWidth(9, 110)
        self.table_leading.setColumnWidth(10, 60)
        h_header.setStretchLastSection(False)

        self.table_leading.setAlternatingRowColors(True)
        self.table_leading.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_leading.cellDoubleClicked.connect(self._on_leading_double_clicked)
        layout.addWidget(self.table_leading)

        return widget

    def _refresh_leading_filters(self) -> None:
        with self.db.session() as conn:
            rows = conn.execute("SELECT DISTINCT year FROM races ORDER BY year DESC").fetchall()
        years = [r["year"] for r in rows]

        cur_period = self.combo_lead_period.currentData()
        self.combo_lead_period.blockSignals(True)
        self.combo_lead_period.clear()
        self.combo_lead_period.addItem("🌟 通算獲得賞金", "career")
        for y in years:
            self.combo_lead_period.addItem(f"📅 第 {y} 年間", y)
        if cur_period is not None:
            idx = self.combo_lead_period.findData(cur_period)
            if idx >= 0:
                self.combo_lead_period.setCurrentIndex(idx)
        self.combo_lead_period.blockSignals(False)

    def refresh_leading(self) -> None:
        period = self.combo_lead_period.currentData()
        cat = self.combo_lead_category.currentData() or "all_all"

        if period == "career" or period is None:
            query = """
                SELECT 
                    h.horse_id,
                    h.name AS horse_name,
                    h.sex,
                    h.age,
                    h.is_active,
                    h.career_starts AS total_starts,
                    h.career_wins AS total_wins,
                    (h.g1_wins + h.g2_wins + h.g3_wins) AS graded_wins,
                    h.prize_money AS total_prize,
                    h.generation,
                    sire.name AS sire_name,
                    dam.name AS dam_name,
                    t.name AS trainer_name
                FROM horses h
                LEFT JOIN horses sire ON h.sire_id = sire.horse_id
                LEFT JOIN horses dam ON h.dam_id = dam.horse_id
                LEFT JOIN trainers t ON h.trainer_id = t.trainer_id
                WHERE 1=1
            """
            params: list[Any] = []
            if cat == "active_all":
                query += " AND h.is_active = 1"
            elif cat == "active_older_all":
                query += " AND h.is_active = 1 AND h.age >= 4"
            elif cat == "active_older_colt":
                query += " AND h.is_active = 1 AND h.age >= 4 AND h.sex IN ('colt', 'horse', 'gelding')"
            elif cat == "active_older_filly":
                query += " AND h.is_active = 1 AND h.age >= 4 AND h.sex IN ('filly', 'mare')"
            elif cat == "active_3yo_all":
                query += " AND h.is_active = 1 AND h.age = 3"
            elif cat == "active_3yo_colt":
                query += " AND h.is_active = 1 AND h.age = 3 AND h.sex IN ('colt', 'horse', 'gelding')"
            elif cat == "active_3yo_filly":
                query += " AND h.is_active = 1 AND h.age = 3 AND h.sex IN ('filly', 'mare')"
            elif cat == "active_2yo_all":
                query += " AND h.is_active = 1 AND h.age = 2"

            query += " ORDER BY h.prize_money DESC, h.career_wins DESC"
        else:
            year = int(period)
            query = """
                SELECT 
                    h.horse_id,
                    h.name AS horse_name,
                    h.sex,
                    h.age,
                    h.is_active,
                    h.generation,
                    COUNT(res.result_id) AS total_starts,
                    SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END) AS total_wins,
                    SUM(CASE WHEN res.finish_position = 1 AND r.grade IN ('G1', 'G2', 'G3') THEN 1 ELSE 0 END) AS graded_wins,
                    SUM(res.prize_awarded) AS total_prize,
                    sire.name AS sire_name,
                    dam.name AS dam_name,
                    t.name AS trainer_name
                FROM results res
                JOIN races r ON res.race_id = r.race_id
                JOIN horses h ON res.horse_id = h.horse_id
                LEFT JOIN horses sire ON h.sire_id = sire.horse_id
                LEFT JOIN horses dam ON h.dam_id = dam.horse_id
                LEFT JOIN trainers t ON h.trainer_id = t.trainer_id
                WHERE r.year = ?
            """
            params = [year]
            if cat == "active_all":
                query += " AND h.is_active = 1"
            elif cat == "active_older_all":
                query += " AND h.is_active = 1 AND h.age >= 4"
            elif cat == "active_older_colt":
                query += " AND h.is_active = 1 AND h.age >= 4 AND h.sex IN ('colt', 'horse', 'gelding')"
            elif cat == "active_older_filly":
                query += " AND h.is_active = 1 AND h.age >= 4 AND h.sex IN ('filly', 'mare')"
            elif cat == "active_3yo_all":
                query += " AND h.is_active = 1 AND h.age = 3"
            elif cat == "active_3yo_colt":
                query += " AND h.is_active = 1 AND h.age = 3 AND h.sex IN ('colt', 'horse', 'gelding')"
            elif cat == "active_3yo_filly":
                query += " AND h.is_active = 1 AND h.age = 3 AND h.sex IN ('filly', 'mare')"
            elif cat == "active_2yo_all":
                query += " AND h.is_active = 1 AND h.age = 2"

            query += " GROUP BY h.horse_id ORDER BY total_prize DESC, total_wins DESC"

        with self.db.session() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()

        self.table_leading.setRowCount(len(rows))
        sex_map = {"colt": "牡", "filly": "牝", "horse": "牡", "mare": "牝", "gelding": "セ"}

        for idx, r in enumerate(rows):
            rank_str = f"{idx + 1}"
            h_name = r["horse_name"]
            gen = dict(r).get("generation", 1) or 1
            name_col = get_generation_color(gen)
            if not r["is_active"]:
                sex_age = "引退"
            else:
                sex_age = f"{sex_map.get(r['sex'], '')}{r['age']}"
            s_name = r["sire_name"] or "-"
            d_name = r["dam_name"] or "-"
            tr_name = r["trainer_name"] or "未定"
            starts_str = str(r["total_starts"] or 0)
            wins_str = str(r["total_wins"] or 0)
            g_wins_str = str(r["graded_wins"] or 0)
            prz_val = (r["total_prize"] or 0) // 10000
            prz_str = f"{prz_val:,} 万円"

            items = [
                QTableWidgetItem(rank_str),
                QTableWidgetItem(h_name),
                QTableWidgetItem(sex_age),
                QTableWidgetItem(s_name),
                QTableWidgetItem(d_name),
                QTableWidgetItem(tr_name),
                QTableWidgetItem(starts_str),
                QTableWidgetItem(wins_str),
                QTableWidgetItem(g_wins_str),
                QTableWidgetItem(prz_str),
            ]
            items[1].setData(Qt.ItemDataRole.UserRole, r["horse_id"])

            for c_idx, item in enumerate(items):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if c_idx == 1:
                    item.setForeground(QColor(name_col))
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
                if c_idx == 8 and (r["graded_wins"] or 0) > 0:
                    item.setForeground(QColor("#facc15"))
                self.table_leading.setItem(idx, c_idx, item)

            hid = r["horse_id"]
            btn_det = QPushButton("詳細")
            btn_det.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 11px; padding: 2px 6px; border: 1px solid #0284c7; border-radius: 3px;")
            btn_det.clicked.connect(lambda checked, h_id=hid: self._open_horse_detail(h_id))
            self.table_leading.setCellWidget(idx, 10, btn_det)

    def _on_leading_double_clicked(self, row: int, col: int) -> None:
        item = self.table_leading.item(row, 1)
        if item:
            hid = item.data(Qt.ItemDataRole.UserRole)
            if hid:
                self._open_horse_detail(hid)

    # ==========================================
    # 2. 世代・クラス別名鑑
    # ==========================================
    def _create_cohort_class_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        summary_bar = QFrame()
        summary_bar.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 6px;")
        s_layout = QHBoxLayout(summary_bar)
        s_layout.setContentsMargins(10, 6, 10, 6)
        s_layout.setSpacing(14)

        self.lbl_sum_total = QLabel("全頭数: 0頭")
        self.lbl_sum_total.setStyleSheet("color: #f8fafc; font-weight: bold; font-size: 13px;")
        s_layout.addWidget(self.lbl_sum_total)

        self.lbl_sum_unraced = QLabel("未出走: 0頭")
        self.lbl_sum_unraced.setStyleSheet("color: #94a3b8; font-size: 12px;")
        s_layout.addWidget(self.lbl_sum_unraced)

        self.lbl_sum_maiden = QLabel("未勝利: 0頭")
        self.lbl_sum_maiden.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        s_layout.addWidget(self.lbl_sum_maiden)

        self.lbl_sum_1w = QLabel("1勝: 0頭")
        self.lbl_sum_1w.setStyleSheet("color: #38bdf8; font-size: 12px;")
        s_layout.addWidget(self.lbl_sum_1w)

        self.lbl_sum_2w = QLabel("2勝: 0頭")
        self.lbl_sum_2w.setStyleSheet("color: #4ade80; font-size: 12px;")
        s_layout.addWidget(self.lbl_sum_2w)

        self.lbl_sum_3w = QLabel("3勝: 0頭")
        self.lbl_sum_3w.setStyleSheet("color: #c084fc; font-size: 12px;")
        s_layout.addWidget(self.lbl_sum_3w)

        self.lbl_sum_op = QLabel("オープン: 0頭")
        self.lbl_sum_op.setStyleSheet("color: #facc15; font-weight: bold; font-size: 12px;")
        s_layout.addWidget(self.lbl_sum_op)

        s_layout.addStretch()
        layout.addWidget(summary_bar)

        filter_bar = QFrame()
        filter_bar.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 6px;")
        f_layout = QHBoxLayout(filter_bar)
        f_layout.setContentsMargins(10, 6, 10, 6)
        f_layout.setSpacing(12)

        f_layout.addWidget(QLabel("馬齢世代:"))
        self.combo_cohort_age = QComboBox()
        self.combo_cohort_age.addItem("全世代 (2歳〜古馬)", None)
        self.combo_cohort_age.addItem("当歳馬 (0歳 / 入厩前)", 0)
        self.combo_cohort_age.addItem("1歳馬 (幼駒 / 入厩前)", 1)
        self.combo_cohort_age.addItem("2歳馬 (新世代)", 2)
        self.combo_cohort_age.addItem("3歳馬 (クラシック)", 3)
        self.combo_cohort_age.addItem("4歳馬 (古馬初期)", 4)
        self.combo_cohort_age.addItem("5歳以上 (古馬・ベテラン)", "5plus")
        self.combo_cohort_age.setCurrentIndex(2)  # デフォルトは2歳馬
        self.combo_cohort_age.currentIndexChanged.connect(self.refresh_cohort_class)
        f_layout.addWidget(self.combo_cohort_age)

        f_layout.addWidget(QLabel("状態:"))
        self.combo_cohort_status = QComboBox()
        self.combo_cohort_status.addItem("現役・育成中 (入厩前含む)", "active")
        self.combo_cohort_status.addItem("全馬 (引退馬含む)", "all")
        self.combo_cohort_status.currentIndexChanged.connect(self.refresh_cohort_class)
        f_layout.addWidget(self.combo_cohort_status)

        f_layout.addWidget(QLabel("クラス絞込:"))
        self.combo_cohort_class = QComboBox()
        self.combo_cohort_class.addItem("全クラス", None)
        self.combo_cohort_class.addItem("🏆 オープン (OP/重賞)", "op")
        self.combo_cohort_class.addItem("🟣 3勝クラス", "3w")
        self.combo_cohort_class.addItem("🟢 2勝クラス", "2w")
        self.combo_cohort_class.addItem("🔵 1勝クラス", "1w")
        self.combo_cohort_class.addItem("⚪ 未勝利馬", "maiden")
        self.combo_cohort_class.addItem("🌱 未出走馬 (2歳以上)", "unraced")
        self.combo_cohort_class.addItem("🍼 入厩前 (当歳・1歳)", "pre_stable")
        self.combo_cohort_class.currentIndexChanged.connect(self.refresh_cohort_class)
        f_layout.addWidget(self.combo_cohort_class)

        btn_ref = QPushButton("🔄 更新")
        btn_ref.setStyleSheet("background-color: #0284c7; color: #ffffff; font-weight: bold; padding: 4px 12px; border-radius: 4px;")
        btn_ref.clicked.connect(self.refresh_cohort_class)
        f_layout.addWidget(btn_ref)

        f_layout.addStretch()
        layout.addWidget(filter_bar)

        self.table_cohort = QTableWidget()
        self.table_cohort.setColumnCount(11)
        self.table_cohort.setHorizontalHeaderLabels([
            "順位", "競走馬名", "性齢", "クラス", "サイアー", "母馬", "厩舎", "通算成績", "総賞金", "主な勝鞍", "詳細"
        ])
        h_header = self.table_cohort.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_cohort.setColumnWidth(0, 45)
        self.table_cohort.setColumnWidth(1, 150)
        self.table_cohort.setColumnWidth(2, 55)
        self.table_cohort.setColumnWidth(3, 85)
        self.table_cohort.setColumnWidth(4, 120)
        self.table_cohort.setColumnWidth(5, 120)
        self.table_cohort.setColumnWidth(6, 95)
        self.table_cohort.setColumnWidth(7, 85)
        self.table_cohort.setColumnWidth(8, 100)
        h_header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        self.table_cohort.setColumnWidth(10, 60)

        self.table_cohort.setAlternatingRowColors(True)
        self.table_cohort.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_cohort.cellDoubleClicked.connect(self._on_cohort_double_clicked)
        layout.addWidget(self.table_cohort)

        return widget

    def _refresh_cohort_filters(self) -> None:
        pass

    def refresh_cohort_class(self) -> None:
        age_filter = self.combo_cohort_age.currentData()
        status_filter = self.combo_cohort_status.currentData()
        class_filter = self.combo_cohort_class.currentData()

        query = """
            SELECT 
                h.horse_id,
                h.name AS horse_name,
                h.sex,
                h.age,
                h.generation,
                h.career_starts,
                h.career_wins,
                h.g1_wins,
                h.g2_wins,
                h.g3_wins,
                h.prize_money,
                h.condition_prize_money,
                h.is_active,
                h.major_wins,
                sire.name AS sire_name,
                dam.name AS dam_name,
                t.name AS trainer_name
            FROM horses h
            LEFT JOIN horses sire ON h.sire_id = sire.horse_id
            LEFT JOIN horses dam ON h.dam_id = dam.horse_id
            LEFT JOIN trainers t ON h.trainer_id = t.trainer_id
            WHERE 1=1
        """
        params: list[Any] = []
        if status_filter == "active":
            query += " AND (h.is_active = 1 OR h.age <= 1) AND h.is_dead = 0 AND h.is_sire = 0 AND h.is_dam = 0"

        if age_filter == 0:
            query += " AND h.age = 0"
        elif age_filter == 1:
            query += " AND h.age = 1"
        elif age_filter == 2:
            query += " AND h.age = 2"
        elif age_filter == 3:
            query += " AND h.age = 3"
        elif age_filter == 4:
            query += " AND h.age = 4"
        elif age_filter == "5plus":
            query += " AND h.age >= 5"

        query += " ORDER BY h.prize_money DESC, h.career_wins DESC, h.horse_id ASC"

        with self.db.session() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()

        cnt_pre_stable = 0
        cnt_unraced = 0
        cnt_maiden = 0
        cnt_1w = 0
        cnt_2w = 0
        cnt_3w = 0
        cnt_op = 0

        classified_rows: list[dict[str, Any]] = []

        for r in rows:
            h_age = r["age"] or 0
            starts = r["career_starts"] or 0
            wins = r["career_wins"] or 0
            g_wins = (r["g1_wins"] or 0) + (r["g2_wins"] or 0) + (r["g3_wins"] or 0)
            cond_prz = r["condition_prize_money"] or 0

            if h_age <= 1:
                cls_code = "pre_stable"
                cls_label = "入厩前"
                cls_col = "#38bdf8"
                cnt_pre_stable += 1
            elif starts == 0:
                cls_code = "unraced"
                cls_label = "未出走"
                cls_col = "#64748b"
                cnt_unraced += 1
            elif wins == 0:
                cls_code = "maiden"
                cls_label = "未勝利"
                cls_col = "#94a3b8"
                cnt_maiden += 1
            elif g_wins > 0 or wins >= 4 or cond_prz >= 16000000:
                cls_code = "op"
                cls_label = "オープン"
                cls_col = "#facc15"
                cnt_op += 1
            elif wins == 3:
                cls_code = "3w"
                cls_label = "3勝クラス"
                cls_col = "#c084fc"
                cnt_3w += 1
            elif wins == 2:
                cls_code = "2w"
                cls_label = "2勝クラス"
                cls_col = "#4ade80"
                cnt_2w += 1
            elif wins == 1:
                cls_code = "1w"
                cls_label = "1勝クラス"
                cls_col = "#38bdf8"
                cnt_1w += 1
            else:
                cls_code = "maiden"
                cls_label = "未勝利"
                cls_col = "#94a3b8"
                cnt_maiden += 1

            row_dict = dict(r)
            row_dict["cls_code"] = cls_code
            row_dict["cls_label"] = cls_label
            row_dict["cls_col"] = cls_col

            if class_filter is None or class_filter == cls_code:
                classified_rows.append(row_dict)

        total_cnt = len(rows)
        if cnt_pre_stable > 0:
            self.lbl_sum_unraced.setText(f"🍼 入厩前: {cnt_pre_stable:,}頭 | 🌱 未出走: {cnt_unraced:,}頭")
        else:
            self.lbl_sum_unraced.setText(f"🌱 未出走: {cnt_unraced:,}頭")
        self.lbl_sum_total.setText(f"全頭数: {total_cnt:,}頭")
        self.lbl_sum_maiden.setText(f"⚪ 未勝利: {cnt_maiden:,}頭")
        self.lbl_sum_1w.setText(f"🔵 1勝: {cnt_1w:,}頭")
        self.lbl_sum_2w.setText(f"🟢 2勝: {cnt_2w:,}頭")
        self.lbl_sum_3w.setText(f"🟣 3勝: {cnt_3w:,}頭")
        self.lbl_sum_op.setText(f"🏆 オープン: {cnt_op:,}頭")

        self.table_cohort.setRowCount(len(classified_rows))
        sex_map = {"colt": "牡", "filly": "牝", "horse": "牡", "mare": "牝", "gelding": "セ"}

        for idx, r in enumerate(classified_rows):
            rank_str = f"{idx + 1}"
            h_name = r["horse_name"]
            gen = r.get("generation", 1) or 1
            name_col = get_generation_color(gen)
            sex_age = f"{sex_map.get(r['sex'], '')}{r['age']}"
            cls_str = r["cls_label"]
            s_name = r["sire_name"] or "-"
            d_name = r["dam_name"] or "-"
            tr_name = r["trainer_name"] or "未定"
            rec_str = f"{r['career_starts']}戦{r['career_wins']}勝"
            prz_str = f"{(r['prize_money'] or 0) // 10000:,} 万円"
            major_str = r["major_wins"] or "-"

            name_item = QTableWidgetItem(h_name)
            name_item.setForeground(QColor(name_col))
            f_name = name_item.font()
            f_name.setBold(True)
            name_item.setFont(f_name)
            name_item.setData(Qt.ItemDataRole.UserRole, r["horse_id"])

            cls_item = QTableWidgetItem(cls_str)
            cls_item.setForeground(QColor(r["cls_col"]))
            f = cls_item.font()
            f.setBold(True)
            cls_item.setFont(f)

            items = [
                QTableWidgetItem(rank_str),
                name_item,
                QTableWidgetItem(sex_age),
                cls_item,
                QTableWidgetItem(s_name),
                QTableWidgetItem(d_name),
                QTableWidgetItem(tr_name),
                QTableWidgetItem(rec_str),
                QTableWidgetItem(prz_str),
                QTableWidgetItem(major_str),
            ]
            items[1].setData(Qt.ItemDataRole.UserRole, r["horse_id"])

            for c_idx, item in enumerate(items):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_cohort.setItem(idx, c_idx, item)

            hid = r["horse_id"]
            btn_det = QPushButton("詳細")
            btn_det.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 11px; padding: 2px 6px; border: 1px solid #0284c7; border-radius: 3px;")
            btn_det.clicked.connect(lambda checked, hid=hid: self._open_horse_detail(hid))
            self.table_cohort.setCellWidget(idx, 10, btn_det)

    def _on_cohort_double_clicked(self, row: int, col: int) -> None:
        item = self.table_cohort.item(row, 1)
        if item:
            hid = item.data(Qt.ItemDataRole.UserRole)
            if hid:
                self._open_horse_detail(hid)

    # ==========================================
    # 3. 主要レース路線タブ (新設)
    # ==========================================
    def _create_major_routes_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        filter_bar = QFrame()
        filter_bar.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 6px;")
        f_layout = QHBoxLayout(filter_bar)
        f_layout.setContentsMargins(10, 6, 10, 6)
        f_layout.setSpacing(12)

        f_layout.addWidget(QLabel("主要路線:"))
        self.combo_route_select = QComboBox()
        for r_def in MAJOR_ROUTES:
            self.combo_route_select.addItem(r_def["name"], r_def["id"])
        self.combo_route_select.currentIndexChanged.connect(self.refresh_major_routes)
        f_layout.addWidget(self.combo_route_select)

        btn_ref = QPushButton("🔄 更新")
        btn_ref.setStyleSheet("background-color: #0284c7; color: #ffffff; font-weight: bold; padding: 4px 12px; border-radius: 4px;")
        btn_ref.clicked.connect(self.refresh_major_routes)
        f_layout.addWidget(btn_ref)

        f_layout.addStretch()
        layout.addWidget(filter_bar)

        self.table_major_routes = QTableWidget()
        self.table_major_routes.setAlternatingRowColors(True)
        self.table_major_routes.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_major_routes.cellClicked.connect(self._on_route_cell_clicked)
        layout.addWidget(self.table_major_routes)

        return widget

    def refresh_major_routes(self) -> None:
        """選択された路線の歴代勝ち馬マトリクスを描画"""
        route_id = self.combo_route_select.currentData()
        route_def = next((r for r in MAJOR_ROUTES if r["id"] == route_id), MAJOR_ROUTES[0])

        r_names = route_def["races"]
        r_labels = route_def["labels"]
        num_races = len(r_names)

        col_labels = ["年度"] + r_labels + ["制覇タイトル"]
        self.table_major_routes.setColumnCount(len(col_labels))
        self.table_major_routes.setHorizontalHeaderLabels(col_labels)

        header = self.table_major_routes.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_major_routes.setColumnWidth(0, 60)
        for c in range(1, num_races + 1):
            self.table_major_routes.setColumnWidth(c, 180)
        header.setSectionResizeMode(num_races + 1, QHeaderView.ResizeMode.Stretch)

        with self.db.session() as conn:
            all_years = [r["year"] for r in conn.execute("SELECT DISTINCT year FROM races ORDER BY year ASC").fetchall()]

            # 各年度・各レースの勝ち馬格納用マップを初期化
            race_winners: Dict[int, Dict[str, Dict[str, Any]]] = {y: {} for y in all_years}

            # 表記揺れ（別称）を含めた検索対象レース名セットを作成
            search_names = set(r_names)
            for alias_name, canonical in ROUTE_RACE_ALIASES.items():
                if canonical in r_names:
                    search_names.add(alias_name)

            placeholders = ",".join(["?"] * len(search_names))
            w_rows = conn.execute(f"""
                SELECT rc.year, rc.name as race_name, h.horse_id, h.name as horse_name
                FROM results res
                JOIN races rc ON res.race_id = rc.race_id
                JOIN horses h ON res.horse_id = h.horse_id
                WHERE res.finish_position = 1 AND rc.name IN ({placeholders})
                ORDER BY rc.year ASC
            """, tuple(search_names)).fetchall()

            for r in w_rows:
                y = r["year"]
                if y in race_winners:
                    raw_name = clean_race_name(r["race_name"])
                    canonical_name = ROUTE_RACE_ALIASES.get(raw_name, raw_name)
                    if canonical_name in r_names:
                        race_winners[y][canonical_name] = {
                            "horse_id": r["horse_id"],
                            "horse_name": r["horse_name"],
                        }

        self.table_major_routes.setRowCount(len(all_years))

        for r_idx, y in enumerate(all_years):
            self.table_major_routes.setItem(r_idx, 0, QTableWidgetItem(f"{y}年"))

            y_winners = race_winners.get(y, {})
            h_ids_in_route = []

            for c_idx, r_name in enumerate(r_names, start=1):
                w_data = y_winners.get(r_name)
                if w_data:
                    itm = QTableWidgetItem(f"🏆 {w_data['horse_name']}")
                    itm.setData(Qt.ItemDataRole.UserRole, w_data["horse_id"])
                    itm.setForeground(QColor("#38bdf8"))
                    h_ids_in_route.append(w_data["horse_id"])
                else:
                    itm = QTableWidgetItem("-")
                    itm.setForeground(QColor("#64748b"))
                itm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_major_routes.setItem(r_idx, c_idx, itm)

            # 制覇状況
            title_str = "-"
            title_col = "#94a3b8"
            if len(h_ids_in_route) == num_races and len(set(h_ids_in_route)) == 1:
                # 全冠制覇！
                if num_races == 3:
                    title_str = "👑 3冠達成 (Triple Crown)"
                else:
                    title_str = "👑 2冠達成 (Double Crown)"
                title_col = "#facc15"
            elif num_races == 3 and len(h_ids_in_route) >= 2:
                # 3冠中2冠
                from collections import Counter
                cnt = Counter(h_ids_in_route)
                for hid, count in cnt.items():
                    if count == 2:
                        title_str = "🥈 2冠制覇"
                        title_col = "#38bdf8"
                        break

            t_item = QTableWidgetItem(title_str)
            t_item.setForeground(QColor(title_col))
            f = t_item.font()
            f.setBold(True)
            t_item.setFont(f)
            t_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_major_routes.setItem(r_idx, num_races + 1, t_item)

    def _on_route_cell_clicked(self, row: int, col: int) -> None:
        item = self.table_major_routes.item(row, col)
        if item:
            hid = item.data(Qt.ItemDataRole.UserRole)
            if hid:
                self._open_horse_detail(hid)

    # ==========================================
    # 4. 種牡馬データベース・サイアーラインタブ (新設・大幅拡張)
    # ==========================================
    def _create_sires_list_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self.sires_sub_tabs = QTabWidget()
        self.sires_sub_tabs.setStyleSheet("""
            QTabBar::tab {
                font-weight: bold;
                font-size: 12px;
                padding: 6px 14px;
            }
        """)

        # サブタブ1: 全種牡馬一覧
        self.tab_sires_all = self._create_sire_all_list_subtab()
        self.sires_sub_tabs.addTab(self.tab_sires_all, "🐴 全種牡馬一覧")

        # サブタブ2: サイアーライン別 競走馬リスト
        self.tab_lineage_horses = self._create_lineage_horses_subtab()
        self.sires_sub_tabs.addTab(self.tab_lineage_horses, "🐎 サイアーライン別 競走馬")

        # サブタブ3: サイアーライン別 種牡馬リスト
        self.tab_lineage_sires = self._create_lineage_sires_subtab()
        self.sires_sub_tabs.addTab(self.tab_lineage_sires, "🧬 サイアーライン別 種牡馬")

        layout.addWidget(self.sires_sub_tabs)
        self.sires_sub_tabs.currentChanged.connect(self._on_sires_subtab_changed)

        return widget

    def _on_sires_subtab_changed(self, index: int) -> None:
        if index == 0:
            self.refresh_sires_list()
        elif index == 1:
            self.refresh_lineage_horses()
        elif index == 2:
            self.refresh_lineage_sires()

    # 4-1. 全種牡馬一覧 サブタブ
    def _create_sire_all_list_subtab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        filter_bar = QFrame()
        filter_bar.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 6px;")
        f_layout = QHBoxLayout(filter_bar)
        f_layout.setContentsMargins(10, 6, 10, 6)
        f_layout.setSpacing(12)

        f_layout.addWidget(QLabel("状態:"))
        self.combo_sire_status = QComboBox()
        self.combo_sire_status.addItem("供用中のみ", "active")
        self.combo_sire_status.addItem("全種牡馬 (引退含む)", "all")
        self.combo_sire_status.currentIndexChanged.connect(self.refresh_sires_list)
        f_layout.addWidget(self.combo_sire_status)

        f_layout.addWidget(QLabel("並び順:"))
        self.combo_sire_sort = QComboBox()
        self.combo_sire_sort.addItem("産駒頭数（降順）", "progeny_desc")
        self.combo_sire_sort.addItem("馬名（50音順）", "name_asc")
        self.combo_sire_sort.addItem("繋養年数（降順）", "years_desc")
        self.combo_sire_sort.addItem("勝ち馬数（降順）", "winners_desc")
        self.combo_sire_sort.addItem("勝ち上がり率（降順）", "rate_desc")
        self.combo_sire_sort.addItem("重賞勝利数（降順）", "graded_desc")
        self.combo_sire_sort.currentIndexChanged.connect(self.refresh_sires_list)
        f_layout.addWidget(self.combo_sire_sort)

        btn_ref = QPushButton("🔄 更新")
        btn_ref.setStyleSheet("background-color: #0284c7; color: #ffffff; font-weight: bold; padding: 4px 12px; border-radius: 4px;")
        btn_ref.clicked.connect(self.refresh_sires_list)
        f_layout.addWidget(btn_ref)

        f_layout.addStretch()
        layout.addWidget(filter_bar)

        self.table_sires = QTableWidget()
        self.table_sires.setColumnCount(12)
        self.table_sires.setHorizontalHeaderLabels([
            "種牡馬名", "年齢", "繋養開始", "繋養年数", "系統", "産駒頭数", "勝馬数", "勝ち上がり率", "重賞勝数", "代表産駒", "カルテ", "産駒一覧"
        ])
        header = self.table_sires.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_sires.setColumnWidth(0, 160)
        self.table_sires.setColumnWidth(1, 50)
        self.table_sires.setColumnWidth(2, 65)
        self.table_sires.setColumnWidth(3, 65)
        self.table_sires.setColumnWidth(4, 100)
        self.table_sires.setColumnWidth(5, 65)
        self.table_sires.setColumnWidth(6, 65)
        self.table_sires.setColumnWidth(7, 85)
        self.table_sires.setColumnWidth(8, 65)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        self.table_sires.setColumnWidth(10, 60)
        self.table_sires.setColumnWidth(11, 75)

        self.table_sires.setAlternatingRowColors(True)
        self.table_sires.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_sires.cellClicked.connect(self._on_sire_cell_clicked)
        layout.addWidget(self.table_sires)

        return widget

    # 4-2. サイアーライン別 競走馬 サブタブ
    def _create_lineage_horses_subtab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # 上部: 系統別競走馬集計ツリー (初代種牡馬から段下げ)
        top_box = QGroupBox("🐎 現在のサイアーライン別 競走馬数・構成割合 (行を選択して下部一覧を表示)")
        top_layout = QVBoxLayout(top_box)
        top_layout.setContentsMargins(6, 6, 6, 6)

        self.tree_lineage_horses = QTreeWidget()
        self.tree_lineage_horses.setHeaderLabels([
            "サイアーライン (父系)", "現役頭数", "構成割合", "通算勝数", "G1勝", "重賞勝", "獲得賞金"
        ])
        self.tree_lineage_horses.setAlternatingRowColors(True)
        self.tree_lineage_horses.setRootIsDecorated(True)
        self.tree_lineage_horses.setAnimated(True)
        self.tree_lineage_horses.setStyleSheet("""
            QTreeWidget {
                background-color: #12161f;
                alternate-background-color: #1a202c;
                color: #f8fafc;
                border: 1px solid #242c3d;
                border-radius: 6px;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 5px 2px;
                background-color: transparent;
            }
            QTreeWidget::item:hover {
                background-color: #1e293b;
            }
            QTreeWidget::item:selected {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
            }
            QHeaderView::section {
                background-color: #0b0f17;
                color: #cbd5e1;
                padding: 6px 4px;
                border: none;
                border-bottom: 2px solid #334155;
                border-right: 1px solid #1e293b;
                font-weight: 700;
            }
        """)
        h_tree = self.tree_lineage_horses.header()
        h_tree.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 7):
            h_tree.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.tree_lineage_horses.itemClicked.connect(self._on_lineage_horses_tree_clicked)
        top_layout.addWidget(self.tree_lineage_horses)
        layout.addWidget(top_box, stretch=1)

        # 下部: 選択された系統の所属競走馬一覧
        bot_box = QGroupBox("🐎 所属現役競走馬一覧 (行をクリックして選択)")
        bot_layout = QVBoxLayout(bot_box)
        bot_layout.setContentsMargins(6, 6, 6, 6)

        self.table_lineage_horses_detail = QTableWidget()
        self.table_lineage_horses_detail.setColumnCount(9)
        self.table_lineage_horses_detail.setHorizontalHeaderLabels([
            "馬名", "性齢", "世代", "クラス", "父馬", "母馬", "通算成績", "獲得賞金", "詳細"
        ])
        b_hdr = self.table_lineage_horses_detail.horizontalHeader()
        b_hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_lineage_horses_detail.setColumnWidth(0, 160)
        self.table_lineage_horses_detail.setColumnWidth(1, 55)
        self.table_lineage_horses_detail.setColumnWidth(2, 55)
        self.table_lineage_horses_detail.setColumnWidth(3, 85)
        self.table_lineage_horses_detail.setColumnWidth(4, 130)
        self.table_lineage_horses_detail.setColumnWidth(5, 130)
        self.table_lineage_horses_detail.setColumnWidth(6, 90)
        b_hdr.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.table_lineage_horses_detail.setColumnWidth(8, 60)

        self.table_lineage_horses_detail.setAlternatingRowColors(True)
        self.table_lineage_horses_detail.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_lineage_horses_detail.cellDoubleClicked.connect(self._on_lineage_horses_detail_double_clicked)
        bot_layout.addWidget(self.table_lineage_horses_detail)
        layout.addWidget(bot_box, stretch=1)

        return widget

    # 4-3. サイアーライン別 種牡馬 サブタブ
    def _create_lineage_sires_subtab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # 上部: 系統別種牡馬集計ツリー (初代種牡馬から段下げ)
        top_box = QGroupBox("🐴 現在のサイアーライン別 種牡馬数・構成割合 (行を選択して下部一覧を表示)")
        top_layout = QVBoxLayout(top_box)
        top_layout.setContentsMargins(6, 6, 6, 6)

        self.tree_lineage_sires = QTreeWidget()
        self.tree_lineage_sires.setHeaderLabels([
            "サイアーライン", "供用中頭数", "構成割合", "自身重賞勝", "産駒重賞勝", "産駒通算勝数"
        ])
        self.tree_lineage_sires.setAlternatingRowColors(True)
        self.tree_lineage_sires.setRootIsDecorated(True)
        self.tree_lineage_sires.setAnimated(True)
        self.tree_lineage_sires.setStyleSheet("""
            QTreeWidget {
                background-color: #12161f;
                alternate-background-color: #1a202c;
                color: #f8fafc;
                border: 1px solid #242c3d;
                border-radius: 6px;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 5px 2px;
                background-color: transparent;
            }
            QTreeWidget::item:hover {
                background-color: #1e293b;
            }
            QTreeWidget::item:selected {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
            }
            QHeaderView::section {
                background-color: #0b0f17;
                color: #cbd5e1;
                padding: 6px 4px;
                border: none;
                border-bottom: 2px solid #334155;
                border-right: 1px solid #1e293b;
                font-weight: 700;
            }
        """)
        h_tree = self.tree_lineage_sires.header()
        h_tree.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 6):
            h_tree.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.tree_lineage_sires.itemClicked.connect(self._on_lineage_sires_tree_clicked)
        top_layout.addWidget(self.tree_lineage_sires)
        layout.addWidget(top_box, stretch=1)

        # 下部: 選択された系統の所属種牡馬一覧
        bot_box = QGroupBox("🐴 所属種牡馬一覧 (行をクリックして選択)")
        bot_layout = QVBoxLayout(bot_box)
        bot_layout.setContentsMargins(6, 6, 6, 6)

        self.table_lineage_sires_detail = QTableWidget()
        self.table_lineage_sires_detail.setColumnCount(9)
        self.table_lineage_sires_detail.setHorizontalHeaderLabels([
            "種牡馬名", "年齢", "世代", "繋養年数", "種付け料", "産駒数", "勝馬数", "重賞勝数", "カルテ"
        ])
        b_hdr = self.table_lineage_sires_detail.horizontalHeader()
        b_hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_lineage_sires_detail.setColumnWidth(0, 160)
        self.table_lineage_sires_detail.setColumnWidth(1, 55)
        self.table_lineage_sires_detail.setColumnWidth(2, 55)
        self.table_lineage_sires_detail.setColumnWidth(3, 75)
        self.table_lineage_sires_detail.setColumnWidth(4, 95)
        self.table_lineage_sires_detail.setColumnWidth(5, 65)
        self.table_lineage_sires_detail.setColumnWidth(6, 65)
        b_hdr.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.table_lineage_sires_detail.setColumnWidth(8, 60)

        self.table_lineage_sires_detail.setAlternatingRowColors(True)
        self.table_lineage_sires_detail.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        bot_layout.addWidget(self.table_lineage_sires_detail)
        layout.addWidget(bot_box, stretch=1)

        return widget

    # 4-4. サイアーライン別 繁殖牝馬 サブタブ
    def _create_lineage_dams_subtab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # 上部: 系統別繁殖牝馬集計ツリー (初代種牡馬から段下げ)
        top_box = QGroupBox("🌸 現在のサイアーライン (父系) 別 繁殖牝馬数・構成割合 (行を選択して下部一覧を表示)")
        top_layout = QVBoxLayout(top_box)
        top_layout.setContentsMargins(6, 6, 6, 6)

        self.tree_lineage_dams = QTreeWidget()
        self.tree_lineage_dams.setHeaderLabels([
            "サイアーライン (父系)", "繁殖牝馬数", "構成割合", "産駒総勝利数", "勝馬数", "勝ち上がり率", "代表繁殖牝馬"
        ])
        self.tree_lineage_dams.setAlternatingRowColors(True)
        self.tree_lineage_dams.setRootIsDecorated(True)
        self.tree_lineage_dams.setAnimated(True)
        self.tree_lineage_dams.setStyleSheet("""
            QTreeWidget {
                background-color: #12161f;
                alternate-background-color: #1a202c;
                color: #f8fafc;
                border: 1px solid #242c3d;
                border-radius: 6px;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 5px 2px;
                background-color: transparent;
            }
            QTreeWidget::item:hover {
                background-color: #1e293b;
            }
            QTreeWidget::item:selected {
                background-color: #be185d;
                color: #ffffff;
                font-weight: bold;
            }
            QHeaderView::section {
                background-color: #0b0f17;
                color: #cbd5e1;
                padding: 6px 4px;
                border: none;
                border-bottom: 2px solid #334155;
                border-right: 1px solid #1e293b;
                font-weight: 700;
            }
        """)
        h_tree = self.tree_lineage_dams.header()
        h_tree.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 6):
            h_tree.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        h_tree.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.tree_lineage_dams.itemClicked.connect(self._on_lineage_dams_tree_clicked)
        top_layout.addWidget(self.tree_lineage_dams)
        layout.addWidget(top_box, stretch=1)

        # 下部: 選択された系統の所属繁殖牝馬一覧
        bot_box = QGroupBox("🌸 所属繁殖牝馬一覧 (行をクリックして選択)")
        bot_layout = QVBoxLayout(bot_box)
        bot_layout.setContentsMargins(6, 6, 6, 6)

        self.table_lineage_dams_detail = QTableWidget()
        self.table_lineage_dams_detail.setColumnCount(9)
        self.table_lineage_dams_detail.setHorizontalHeaderLabels([
            "牝馬名", "年齢", "世代", "父馬", "母馬", "産駒数", "勝馬数", "勝ち上がり率", "カルテ"
        ])
        b_hdr = self.table_lineage_dams_detail.horizontalHeader()
        b_hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_lineage_dams_detail.setColumnWidth(0, 160)
        self.table_lineage_dams_detail.setColumnWidth(1, 55)
        self.table_lineage_dams_detail.setColumnWidth(2, 55)
        self.table_lineage_dams_detail.setColumnWidth(3, 130)
        self.table_lineage_dams_detail.setColumnWidth(4, 130)
        self.table_lineage_dams_detail.setColumnWidth(5, 65)
        self.table_lineage_dams_detail.setColumnWidth(6, 65)
        b_hdr.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.table_lineage_dams_detail.setColumnWidth(8, 60)

        self.table_lineage_dams_detail.setAlternatingRowColors(True)
        self.table_lineage_dams_detail.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        bot_layout.addWidget(self.table_lineage_dams_detail)
        layout.addWidget(bot_box, stretch=1)

        return widget

    def refresh_sires_list(self) -> None:
        """種牡馬一覧をロード"""
        status_filter = self.combo_sire_status.currentData()
        sort_mode = self.combo_sire_sort.currentData() or "progeny_desc"

        with self.db.session() as conn:
            # 現在年度を取得
            max_y_row = conn.execute("SELECT MAX(year) as max_year FROM races").fetchone()
            cur_year = (max_y_row["max_year"] or 1) if max_y_row else 1

            query = """
                SELECT s.sire_id, s.horse_id, s.sire_line, s.start_year, s.is_active, s.is_foreign, s.is_new,
                       s.generation as s_generation,
                       sh.name as name, sh.age as age, sh.birth_year, sh.retired_year, sh.generation as h_generation,
                       COUNT(DISTINCT ph.horse_id) as progeny_count,
                       COUNT(DISTINCT CASE WHEN ph.is_active = 1 THEN ph.horse_id END) as active_progeny_count,
                       SUM(CASE WHEN (ph.is_active = 1 AND ph.career_wins > 0) THEN 1 ELSE 0 END) as winners_count,
                       SUM(CASE WHEN (ph.career_wins > 0) THEN 1 ELSE 0 END) as total_winners_count,
                       SUM(ph.g1_wins + ph.g2_wins + ph.g3_wins) as graded_wins,
                       MAX(ph.prize_money) as max_prize
                FROM sires s
                JOIN horses sh ON s.horse_id = sh.horse_id
                LEFT JOIN horses ph ON s.horse_id = ph.sire_id
                WHERE 1=1
            """
            if status_filter == "active":
                query += " AND s.is_active = 1"
            query += " GROUP BY s.sire_id"

            rows = conn.execute(query).fetchall()

            # 各行の加工と繋養年数の算出
            processed_rows = []
            for r in rows:
                p_dict = dict(r)
                p_cnt = p_dict["progeny_count"] or 0
                act_cnt = p_dict["active_progeny_count"] or 0
                w_cnt = p_dict["winners_count"] or 0  # 現役馬での勝馬頭数
                p_dict["win_rate_val"] = (w_cnt / act_cnt) if act_cnt > 0 else 0.0
                p_dict["graded_wins"] = p_dict["graded_wins"] or 0

                st_yr = p_dict.get("start_year", 1) or 1
                p_dict["start_year_val"] = st_yr
                p_dict["years_in_service"] = max(1, cur_year - st_yr + 1)
                processed_rows.append(p_dict)

            # ソート適用
            if sort_mode == "name_asc":
                processed_rows.sort(key=lambda x: (not x["is_active"], x["name"]))
            elif sort_mode == "years_desc":
                processed_rows.sort(key=lambda x: (not x["is_active"], -x["years_in_service"], -x["progeny_count"], x["name"]))
            elif sort_mode == "winners_desc":
                processed_rows.sort(key=lambda x: (not x["is_active"], -x["winners_count"], -x["progeny_count"], x["name"]))
            elif sort_mode == "rate_desc":
                processed_rows.sort(key=lambda x: (not x["is_active"], -x["win_rate_val"], -x["progeny_count"], x["name"]))
            elif sort_mode == "graded_desc":
                processed_rows.sort(key=lambda x: (not x["is_active"], -x["graded_wins"], -x["progeny_count"], x["name"]))
            else:  # progeny_desc (デフォルト)
                processed_rows.sort(key=lambda x: (not x["is_active"], -x["progeny_count"], -x["winners_count"], x["name"]))

            # 代表産駒を一括取得 (N+1解消)
            top_prog_map = {}
            top_prog_rows = conn.execute("""
                SELECT horse_id, sire_id, name, prize_money, generation
                FROM horses
                WHERE sire_id IS NOT NULL AND prize_money > 0
                ORDER BY prize_money DESC
            """).fetchall()
            for pr in top_prog_rows:
                sid = pr["sire_id"]
                if sid not in top_prog_map:
                    top_prog_map[sid] = {
                        "name": f"{pr['name']} ({(pr['prize_money'] // 10000):,}万円)",
                        "horse_id": pr["horse_id"],
                        "generation": pr["generation"] or 1
                    }

        self.table_sires.setRowCount(len(processed_rows))

        for idx, r in enumerate(processed_rows):
            s_name = r["name"]
            is_foreign = bool(r.get("is_foreign", 0))
            is_new = bool(r.get("is_new", 0))
            gen = r.get("s_generation") or r.get("h_generation") or 1

            if is_foreign:
                s_name_display = f"🔍 {s_name}(外)"
                name_col = "#ef4444"  # 海外種牡馬: 赤
            else:
                s_name_display = f"🔍 {s_name}"
                name_col = get_generation_color(gen, is_breeding=True, start_year=r.get("start_year_val"))

            age_str = f"{r['age']}歳" if r["age"] else "-"
            st_yr_str = f"{r['start_year_val']}年"
            years_str = f"{r['years_in_service']}年目"
            lineage = r["sire_line"] or "-"
            p_cnt = r["progeny_count"] or 0
            w_cnt = r["winners_count"] or 0
            win_rate = f"{(r['win_rate_val'] * 100):.1f}%" if p_cnt > 0 else "0.0%"
            g_wins = r["graded_wins"] or 0
            
            top_prog_info = top_prog_map.get(r["horse_id"], {})
            top_prog_name = top_prog_info.get("name", "-")
            top_prog_hid = top_prog_info.get("horse_id")
            top_prog_gen = top_prog_info.get("generation", 1)

            name_item = QTableWidgetItem(s_name_display)
            name_item.setForeground(QColor(name_col))
            f = name_item.font()
            f.setBold(True)
            name_item.setFont(f)
            name_item.setData(Qt.ItemDataRole.UserRole, r["horse_id"])

            rep_item = QTableWidgetItem(top_prog_name)
            if top_prog_hid:
                prog_color = get_generation_color(top_prog_gen)
                rep_item.setForeground(QColor(prog_color))
                rep_item.setData(Qt.ItemDataRole.UserRole, top_prog_hid)

            items = [
                name_item,
                QTableWidgetItem(age_str),
                QTableWidgetItem(st_yr_str),
                QTableWidgetItem(years_str),
                QTableWidgetItem(lineage),
                QTableWidgetItem(str(p_cnt)),
                QTableWidgetItem(str(w_cnt)),
                QTableWidgetItem(win_rate),
                QTableWidgetItem(str(g_wins)),
                rep_item,
            ]

            for c_idx, item in enumerate(items):
                if c_idx not in (0, 9):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_sires.setItem(idx, c_idx, item)

            hid = r["horse_id"]
            # カルテ詳細ボタン
            btn_karte = QPushButton("カルテ")
            btn_karte.setStyleSheet("background-color: #0284c7; color: #ffffff; font-size: 11px; padding: 2px 4px; border-radius: 3px; font-weight: bold;")
            btn_karte.clicked.connect(lambda checked, h_id=hid: self._open_sire_detail(h_id))
            self.table_sires.setCellWidget(idx, 10, btn_karte)

            # 産駒一覧ボタン
            btn_prog = QPushButton("産駒一覧")
            btn_prog.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 11px; padding: 2px 4px; border: 1px solid #0284c7; border-radius: 3px;")
            btn_prog.clicked.connect(lambda checked, h_id=hid: self._open_progeny_dialog(h_id, is_sire=True))
            self.table_sires.setCellWidget(idx, 11, btn_prog)

    # ==========================================
    # サイアーライン別 競走馬・種牡馬・繁殖牝馬 集計ロード処理
    # ==========================================
    def refresh_lineage_horses(self) -> None:
        """現在のサイアーライン別 競走馬集計ロード (初代種牡馬から段下げ階層ツリー)"""
        with self.db.session() as conn:
            h_rows = conn.execute("SELECT * FROM horses").fetchall()
            h_cols = [d[0] for d in conn.execute("SELECT * FROM horses LIMIT 1").description]
            horses_map = {r[h_cols.index("horse_id")]: dict(zip(h_cols, r)) for r in h_rows}

            s_rows = conn.execute("SELECT * FROM sires").fetchall()
            if s_rows:
                s_cols = [d[0] for d in conn.execute("SELECT * FROM sires LIMIT 1").description]
                sires_map = {r[s_cols.index("horse_id")]: dict(zip(s_cols, r)) for r in s_rows}
            else:
                sires_map = {}

        # 1. 親子マップと深さ
        sire_sons_map = defaultdict(list)
        for hid in sires_map:
            h = horses_map.get(hid)
            if h and h.get("sire_id") and h["sire_id"] in sires_map:
                sire_sons_map[h["sire_id"]].append(hid)

        depth_cache = {}
        visited_depth = set()
        def calc_depth(hid):
            if hid in depth_cache: return depth_cache[hid]
            if hid in visited_depth: return 0
            visited_depth.add(hid)
            sons = sire_sons_map.get(hid, [])
            if not sons:
                depth_cache[hid] = 0
                return 0
            d = 1 + max(calc_depth(sid) for sid in sons)
            depth_cache[hid] = d
            return d

        for hid in sires_map:
            visited_depth.clear()
            calc_depth(hid)

        # 始祖
        root_sires = [
            hid for hid in sires_map
            if not horses_map.get(hid, {}).get("sire_id") or horses_map[hid]["sire_id"] not in sires_map
        ]
        root_sires.sort(key=lambda x: (horses_map.get(x, {}).get("birth_year", 0), horses_map.get(x, {}).get("name", "")))

        # 2. 現役競走馬の集計
        active_horses = [h for h in horses_map.values() if h.get("is_active") == 1 and h.get("age", 0) >= 2]
        total_active_horses = len(active_horses) or 1

        def get_all_sub_sire_ids(target_hid: int) -> Set[int]:
            res = {target_hid}
            for sid in sire_sons_map.get(target_hid, []):
                res.update(get_all_sub_sire_ids(sid))
            return res

        self._lineage_horses_sub_sires_map = {hid: get_all_sub_sire_ids(hid) for hid in sires_map}
        self._lineage_horses_data_cache = defaultdict(list)
        for h in active_horses:
            f_id = h.get("sire_id")
            if f_id:
                for target_hid, sub_ids in self._lineage_horses_sub_sires_map.items():
                    if f_id in sub_ids:
                        self._lineage_horses_data_cache[target_hid].append(h)

        self._lineage_horses_root_sires = root_sires
        self._lineage_horses_horses_map = horses_map
        self._lineage_horses_depth_cache = depth_cache
        self._lineage_horses_sire_sons_map = sire_sons_map
        self._lineage_horses_total_cnt = total_active_horses

        self.tree_lineage_horses.clear()

        for root_id in root_sires:
            h = horses_map.get(root_id)
            if not h: continue

            root_name = h.get("name", "不明")
            h_list = self._lineage_horses_data_cache.get(root_id, [])
            cnt = len(h_list)
            # 断絶（所属現役競走馬が0頭）の系統は表示しない
            if cnt == 0:
                continue

            share_pct = f"{(cnt / total_active_horses * 100):.1f}%"
            wins = sum(x.get("career_wins", 0) for x in h_list)
            g1 = sum(x.get("g1_wins", 0) for x in h_list)
            graded = sum((x.get("g1_wins", 0) + x.get("g2_wins", 0) + x.get("g3_wins", 0)) for x in h_list)
            prz_str = f"{(sum(x.get('prize_money', 0) for x in h_list) // 10000):,}万円"

            root_item = QTreeWidgetItem()
            root_item.setText(0, f"🧬 {root_name}系")
            root_item.setText(1, f"{cnt:,}頭")
            root_item.setText(2, share_pct)
            root_item.setText(3, f"{wins}勝")
            root_item.setText(4, f"{g1}勝")
            root_item.setText(5, f"{graded}勝")
            root_item.setText(6, prz_str)
            root_item.setData(0, Qt.ItemDataRole.UserRole, root_id)

            for col in range(1, 7):
                root_item.setTextAlignment(col, Qt.AlignmentFlag.AlignCenter)

            visited_sub = set()
            def add_child_lines(parent_item, parent_hid):
                def find_next_lines(curr_hid):
                    lines = []
                    for son_id in sire_sons_map.get(curr_hid, []):
                        if son_id in visited_sub: continue
                        visited_sub.add(son_id)
                        if depth_cache.get(son_id, 0) >= 2:
                            lines.append(son_id)
                        else:
                            lines.extend(find_next_lines(son_id))
                    return lines

                sub_line_ids = find_next_lines(parent_hid)
                for sub_id in sub_line_ids:
                    sub_h = horses_map.get(sub_id)
                    if not sub_h: continue
                    sub_list = self._lineage_horses_data_cache.get(sub_id, [])
                    sub_cnt = len(sub_list)
                    # 断絶（所属頭数0頭）の子系統は表示しない
                    if sub_cnt == 0:
                        continue

                    sub_share = f"{(sub_cnt / total_active_horses * 100):.1f}%"
                    sub_wins = sum(x.get("career_wins", 0) for x in sub_list)
                    sub_g1 = sum(x.get("g1_wins", 0) for x in sub_list)
                    sub_graded = sum((x.get("g1_wins", 0) + x.get("g2_wins", 0) + x.get("g3_wins", 0)) for x in sub_list)
                    sub_prz = f"{(sum(x.get('prize_money', 0) for x in sub_list) // 10000):,}万円"

                    sub_item = QTreeWidgetItem(parent_item)
                    sub_item.setText(0, f"└ {sub_h.get('name', '')}系")
                    sub_item.setText(1, f"{sub_cnt:,}頭")
                    sub_item.setText(2, sub_share)
                    sub_item.setText(3, f"{sub_wins}勝")
                    sub_item.setText(4, f"{sub_g1}勝")
                    sub_item.setText(5, f"{sub_graded}勝")
                    sub_item.setText(6, sub_prz)
                    sub_item.setData(0, Qt.ItemDataRole.UserRole, sub_id)

                    for col in range(1, 7):
                        sub_item.setTextAlignment(col, Qt.AlignmentFlag.AlignCenter)

                    add_child_lines(sub_item, sub_id)

            add_child_lines(root_item, root_id)
            self.tree_lineage_horses.addTopLevelItem(root_item)
            root_item.setExpanded(True)

        if self.tree_lineage_horses.topLevelItemCount() > 0:
            first_it = self.tree_lineage_horses.topLevelItem(0)
            self.tree_lineage_horses.setCurrentItem(first_it)
            hid = first_it.data(0, Qt.ItemDataRole.UserRole)
            if hid: self._load_lineage_horses_by_hid(hid)

    def _on_lineage_horses_tree_clicked(self, item: QTreeWidgetItem, col: int) -> None:
        hid = item.data(0, Qt.ItemDataRole.UserRole)
        if hid:
            self._load_lineage_horses_by_hid(hid)

    def _load_lineage_horses_by_hid(self, hid: int) -> None:
        """選択された系統の所属現役競走馬一覧を表示"""
        h_info = getattr(self, "_lineage_horses_horses_map", {}).get(hid, {})
        line_name = f"{h_info.get('name', '不明')}系"

        horses_list = getattr(self, "_lineage_horses_data_cache", {}).get(hid, [])
        horses_list = sorted(horses_list, key=lambda x: (-(x.get("prize_money") or 0), -(x.get("career_wins") or 0)))

        sex_map = {"colt": "牡", "filly": "牝", "horse": "牡", "mare": "牝", "gelding": "セ"}
        self.table_lineage_horses_detail.setRowCount(len(horses_list))

        for idx, r in enumerate(horses_list):
            h_name = r.get("name", "")
            gen = r.get("generation", 1) or 1
            name_col = get_generation_color(gen)
            sex_age = f"{sex_map.get(r.get('sex'), '')}{r.get('age', '')}"
            gen_str = f"第{gen}世代"

            wins = r.get("career_wins", 0) or 0
            cond_prz = r.get("condition_prize_money", 0) or 0
            if (r.get("g1_wins") or 0) > 0 or (r.get("g2_wins") or 0) > 0 or (r.get("g3_wins") or 0) > 0 or wins >= 4 or cond_prz >= 16_000_000:
                cls_str = "オープン"
                cls_col = "#facc15"
            elif wins >= 3 or cond_prz >= 10_000_000:
                cls_str = "3勝クラス"
                cls_col = "#c084fc"
            elif wins >= 2 or cond_prz >= 5_000_000:
                cls_str = "2勝クラス"
                cls_col = "#4ade80"
            elif wins >= 1:
                cls_str = "1勝クラス"
                cls_col = "#60a5fa"
            else:
                cls_str = "未勝利"
                cls_col = "#94a3b8"

            s_id = r.get("sire_id")
            s_name = self._lineage_horses_horses_map.get(s_id, {}).get("name", "-") if s_id else "-"
            d_id = r.get("dam_id")
            d_name = self._lineage_horses_horses_map.get(d_id, {}).get("name", "-") if d_id else "-"
            rec_str = f"{r.get('career_starts', 0)}戦{wins}勝"
            prize_str = f"{(r.get('prize_money', 0) or 0) // 10000:,} 万円"

            name_item = QTableWidgetItem(h_name)
            name_item.setForeground(QColor(name_col))
            f = name_item.font()
            f.setBold(True)
            name_item.setFont(f)
            name_item.setData(Qt.ItemDataRole.UserRole, r.get("horse_id"))

            cls_item = QTableWidgetItem(cls_str)
            cls_item.setForeground(QColor(cls_col))
            f_c = cls_item.font()
            f_c.setBold(True)
            cls_item.setFont(f_c)

            items = [
                name_item,
                QTableWidgetItem(sex_age),
                QTableWidgetItem(gen_str),
                cls_item,
                QTableWidgetItem(s_name),
                QTableWidgetItem(d_name),
                QTableWidgetItem(rec_str),
                QTableWidgetItem(prize_str),
            ]
            for c_idx, it in enumerate(items):
                if c_idx not in (0, 4, 5):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_lineage_horses_detail.setItem(idx, c_idx, it)

            hid_target = r.get("horse_id")
            btn_det = QPushButton("詳細")
            btn_det.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 11px; padding: 2px 6px; border: 1px solid #0284c7; border-radius: 3px;")
            btn_det.clicked.connect(lambda checked, h_id=hid_target: self._open_horse_detail(h_id))
            self.table_lineage_horses_detail.setCellWidget(idx, 8, btn_det)

    def _on_lineage_horses_detail_double_clicked(self, row: int, col: int) -> None:
        item = self.table_lineage_horses_detail.item(row, 0)
        if item:
            hid = item.data(Qt.ItemDataRole.UserRole)
            if hid:
                self._open_horse_detail(hid)

    def refresh_lineage_sires(self) -> None:
        """現在のサイアーライン別 種牡馬集計ロード (初代種牡馬から段下げ階層ツリー)"""
        with self.db.session() as conn:
            h_rows = conn.execute("SELECT * FROM horses").fetchall()
            h_cols = [d[0] for d in conn.execute("SELECT * FROM horses LIMIT 1").description]
            horses_map = {r[h_cols.index("horse_id")]: dict(zip(h_cols, r)) for r in h_rows}

            s_rows = conn.execute("SELECT * FROM sires").fetchall()
            if s_rows:
                s_cols = [d[0] for d in conn.execute("SELECT * FROM sires LIMIT 1").description]
                sires_map = {r[s_cols.index("horse_id")]: dict(zip(s_cols, r)) for r in s_rows}
            else:
                sires_map = {}

            prog_stat_rows = conn.execute("""
                SELECT sire_id,
                       COUNT(DISTINCT horse_id) as progeny_count,
                       SUM(CASE WHEN career_wins > 0 THEN 1 ELSE 0 END) as winners_count,
                       SUM(career_wins) as p_wins,
                       SUM(g1_wins + g2_wins + g3_wins) as graded_wins
                FROM horses
                WHERE sire_id IS NOT NULL
                GROUP BY sire_id
            """).fetchall()
            prog_map = {r["sire_id"]: dict(r) for r in prog_stat_rows}

        # 1. 親子マップと深さ
        sire_sons_map = defaultdict(list)
        for hid in sires_map:
            h = horses_map.get(hid)
            if h and h.get("sire_id") and h["sire_id"] in sires_map:
                sire_sons_map[h["sire_id"]].append(hid)

        depth_cache = {}
        visited_depth = set()
        def calc_depth(hid):
            if hid in depth_cache: return depth_cache[hid]
            if hid in visited_depth: return 0
            visited_depth.add(hid)
            sons = sire_sons_map.get(hid, [])
            if not sons:
                depth_cache[hid] = 0
                return 0
            d = 1 + max(calc_depth(sid) for sid in sons)
            depth_cache[hid] = d
            return d

        for hid in sires_map:
            visited_depth.clear()
            calc_depth(hid)

        root_sires = [
            hid for hid in sires_map
            if not horses_map.get(hid, {}).get("sire_id") or horses_map[hid]["sire_id"] not in sires_map
        ]
        root_sires.sort(key=lambda x: (horses_map.get(x, {}).get("birth_year", 0), horses_map.get(x, {}).get("name", "")))

        def get_all_sub_sire_ids(target_hid: int) -> Set[int]:
            res = {target_hid}
            for sid in sire_sons_map.get(target_hid, []):
                res.update(get_all_sub_sire_ids(sid))
            return res

        self._lineage_sires_sub_sires_map = {hid: get_all_sub_sire_ids(hid) for hid in sires_map}
        self._lineage_sires_data_cache = defaultdict(list)
        for hid, s in sires_map.items():
            if s.get("is_active"):
                for target_hid, sub_ids in self._lineage_sires_sub_sires_map.items():
                    if hid in sub_ids:
                        h_data = horses_map.get(hid, {})
                        p_info = prog_map.get(hid, {})
                        self._lineage_sires_data_cache[target_hid].append({
                            **h_data, **s,
                            "p_cnt": p_info.get("progeny_count", 0),
                            "w_cnt": p_info.get("winners_count", 0),
                            "p_wins": p_info.get("p_wins", 0),
                            "p_graded": p_info.get("graded_wins", 0),
                        })

        active_sires_total = sum(1 for s in sires_map.values() if s.get("is_active")) or 1

        self._lineage_sires_root_sires = root_sires
        self._lineage_sires_sires_map = sires_map
        self._lineage_sires_horses_map = horses_map
        self._lineage_sires_depth_cache = depth_cache
        self._lineage_sires_sire_sons_map = sire_sons_map
        self._lineage_sires_total_cnt = active_sires_total

        self.tree_lineage_sires.clear()

        for root_id in root_sires:
            h = horses_map.get(root_id)
            if not h: continue

            root_name = h.get("name", "不明")
            s_list = self._lineage_sires_data_cache.get(root_id, [])
            cnt = len(s_list)
            # 断絶（供用中種牡馬が0頭）の系統は表示しない
            if cnt == 0:
                continue

            share_pct = f"{(cnt / active_sires_total * 100):.1f}%"
            self_g = sum((x.get("g1_wins", 0) + x.get("g2_wins", 0) + x.get("g3_wins", 0)) for x in s_list)
            p_g = sum(x.get("p_graded", 0) for x in s_list)
            p_wins = sum(x.get("p_wins", 0) for x in s_list)

            root_item = QTreeWidgetItem()
            root_item.setText(0, f"🐴 {root_name}系")
            root_item.setText(1, f"{cnt:,}頭")
            root_item.setText(2, share_pct)
            root_item.setText(3, f"{self_g}勝")
            root_item.setText(4, f"{p_g}勝")
            root_item.setText(5, f"{p_wins}勝")
            root_item.setData(0, Qt.ItemDataRole.UserRole, root_id)

            for col in range(1, 6):
                root_item.setTextAlignment(col, Qt.AlignmentFlag.AlignCenter)

            visited_sub = set()
            def add_child_lines(parent_item, parent_hid):
                def find_next_lines(curr_hid):
                    lines = []
                    for son_id in sire_sons_map.get(curr_hid, []):
                        if son_id in visited_sub: continue
                        visited_sub.add(son_id)
                        if depth_cache.get(son_id, 0) >= 2:
                            lines.append(son_id)
                        else:
                            lines.extend(find_next_lines(son_id))
                    return lines

                sub_line_ids = find_next_lines(parent_hid)
                for sub_id in sub_line_ids:
                    sub_h = horses_map.get(sub_id)
                    if not sub_h: continue
                    sub_list = self._lineage_sires_data_cache.get(sub_id, [])
                    sub_cnt = len(sub_list)
                    # 断絶（供用中種牡馬が0頭）の子系統は表示しない
                    if sub_cnt == 0:
                        continue

                    sub_share = f"{(sub_cnt / active_sires_total * 100):.1f}%"
                    sub_self_g = sum((x.get("g1_wins", 0) + x.get("g2_wins", 0) + x.get("g3_wins", 0)) for x in sub_list)
                    sub_p_g = sum(x.get("p_graded", 0) for x in sub_list)
                    sub_p_wins = sum(x.get("p_wins", 0) for x in sub_list)

                    sub_item = QTreeWidgetItem(parent_item)
                    sub_item.setText(0, f"└ {sub_h.get('name', '')}系")
                    sub_item.setText(1, f"{sub_cnt:,}頭")
                    sub_item.setText(2, sub_share)
                    sub_item.setText(3, f"{sub_self_g}勝")
                    sub_item.setText(4, f"{sub_p_g}勝")
                    sub_item.setText(5, f"{sub_p_wins}勝")
                    sub_item.setData(0, Qt.ItemDataRole.UserRole, sub_id)

                    for col in range(1, 6):
                        sub_item.setTextAlignment(col, Qt.AlignmentFlag.AlignCenter)

                    add_child_lines(sub_item, sub_id)

            add_child_lines(root_item, root_id)
            self.tree_lineage_sires.addTopLevelItem(root_item)
            root_item.setExpanded(True)

        if self.tree_lineage_sires.topLevelItemCount() > 0:
            first_it = self.tree_lineage_sires.topLevelItem(0)
            self.tree_lineage_sires.setCurrentItem(first_it)
            hid = first_it.data(0, Qt.ItemDataRole.UserRole)
            if hid: self._load_lineage_sires_by_hid(hid)

    def _on_lineage_sires_tree_clicked(self, item: QTreeWidgetItem, col: int) -> None:
        hid = item.data(0, Qt.ItemDataRole.UserRole)
        if hid:
            self._load_lineage_sires_by_hid(hid)

    def _load_lineage_sires_by_hid(self, hid: int) -> None:
        """選択された系統の所属種牡馬一覧を表示"""
        h_info = getattr(self, "_lineage_sires_horses_map", {}).get(hid, {})
        line_name = f"{h_info.get('name', '不明')}系"

        sires_list = getattr(self, "_lineage_sires_data_cache", {}).get(hid, [])
        sires_list = sorted(sires_list, key=lambda x: -(x.get("stud_fee") or 0))

        with self.db.session() as conn:
            max_y_row = conn.execute("SELECT MAX(year) as max_year FROM races").fetchone()
            cur_year = (max_y_row["max_year"] or 1) if max_y_row else 1

        self.table_lineage_sires_detail.setRowCount(len(sires_list))
        for idx, r in enumerate(sires_list):
            s_name = r.get("name", "")
            gen = r.get("generation", 1) or 1
            st_yr = r.get("start_year", 1) or 1
            name_col = get_generation_color(gen, is_breeding=True, start_year=st_yr)
            age_str = f"{r.get('age')}歳" if r.get("age") else "-"
            gen_str = f"第{gen}世代"
            years_str = f"{max(1, cur_year - st_yr + 1)}年目"
            fee_str = f"{(r.get('stud_fee') or 0) // 10000:,} 万円"
            p_cnt = str(r.get("p_cnt", 0))
            w_cnt = str(r.get("w_cnt", 0))
            g_wins = str(r.get("p_graded", 0))

            name_item = QTableWidgetItem(f"🐴 {s_name}")
            name_item.setForeground(QColor(name_col))
            f = name_item.font()
            f.setBold(True)
            name_item.setFont(f)
            name_item.setData(Qt.ItemDataRole.UserRole, r.get("horse_id"))

            items = [
                name_item,
                QTableWidgetItem(age_str),
                QTableWidgetItem(gen_str),
                QTableWidgetItem(years_str),
                QTableWidgetItem(fee_str),
                QTableWidgetItem(p_cnt),
                QTableWidgetItem(w_cnt),
                QTableWidgetItem(g_wins),
            ]
            for c_idx, it in enumerate(items):
                if c_idx != 0:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_lineage_sires_detail.setItem(idx, c_idx, it)

            hid_target = r.get("horse_id")
            btn_karte = QPushButton("カルテ")
            btn_karte.setStyleSheet("background-color: #0284c7; color: #ffffff; font-size: 11px; padding: 2px 4px; border-radius: 3px; font-weight: bold;")
            btn_karte.clicked.connect(lambda checked, h_id=hid_target: self._open_sire_detail(h_id))
            self.table_lineage_sires_detail.setCellWidget(idx, 8, btn_karte)

    def refresh_lineage_dams(self) -> None:
        """現在のサイアーライン別 繁殖牝馬集計ロード (初代種牡馬から段下げ階層ツリー)"""
        with self.db.session() as conn:
            h_rows = conn.execute("SELECT * FROM horses").fetchall()
            h_cols = [d[0] for d in conn.execute("SELECT * FROM horses LIMIT 1").description]
            horses_map = {r[h_cols.index("horse_id")]: dict(zip(h_cols, r)) for r in h_rows}

            s_rows = conn.execute("SELECT * FROM sires").fetchall()
            sires_map = {r["horse_id"]: dict(r) for r in s_rows} if s_rows else {}

            d_rows = conn.execute("SELECT * FROM dams WHERE is_active = 1").fetchall()
            dams_list = [dict(r) for r in d_rows] if d_rows else []

            # 産駒成績の集計
            prog_stat_rows = conn.execute("""
                SELECT dam_id,
                       COUNT(horse_id) as p_count,
                       COUNT(CASE WHEN is_active = 1 THEN horse_id END) as p_active_count,
                       SUM(career_wins) as p_wins,
                       SUM(CASE WHEN is_active = 1 AND career_wins > 0 THEN 1 ELSE 0 END) as p_winners
                FROM horses
                WHERE dam_id IS NOT NULL
                GROUP BY dam_id
            """).fetchall()
            prog_map = {r["dam_id"]: dict(r) for r in prog_stat_rows}

        # 1. 親子マップと深さ
        sire_sons_map = defaultdict(list)
        for hid in sires_map:
            h = horses_map.get(hid)
            if h and h.get("sire_id") and h["sire_id"] in sires_map:
                sire_sons_map[h["sire_id"]].append(hid)

        depth_cache = {}
        visited_depth = set()
        def calc_depth(hid):
            if hid in depth_cache: return depth_cache[hid]
            if hid in visited_depth: return 0
            visited_depth.add(hid)
            sons = sire_sons_map.get(hid, [])
            if not sons:
                depth_cache[hid] = 0
                return 0
            d = 1 + max(calc_depth(sid) for sid in sons)
            depth_cache[hid] = d
            return d

        for hid in sires_map:
            visited_depth.clear()
            calc_depth(hid)

        root_sires = [
            hid for hid in sires_map
            if not horses_map.get(hid, {}).get("sire_id") or horses_map[hid]["sire_id"] not in sires_map
        ]
        root_sires.sort(key=lambda x: (horses_map.get(x, {}).get("birth_year", 0), horses_map.get(x, {}).get("name", "")))

        def get_all_sub_sire_ids(target_hid: int) -> Set[int]:
            res = {target_hid}
            for sid in sire_sons_map.get(target_hid, []):
                res.update(get_all_sub_sire_ids(sid))
            return res

        self._lineage_dams_sub_sires_map = {hid: get_all_sub_sire_ids(hid) for hid in sires_map}
        self._lineage_dams_data_cache = defaultdict(list)

        for d in dams_list:
            dh = horses_map.get(d["horse_id"], {})
            f_id = dh.get("sire_id")
            p_info = prog_map.get(d["horse_id"], {})
            dam_entry = {
                **dh, **d,
                "p_cnt": p_info.get("p_count", 0),
                "act_p_cnt": p_info.get("p_active_count", 0),
                "p_wins": p_info.get("p_wins", 0),
                "w_cnt": p_info.get("p_winners", 0),
            }
            if f_id:
                for target_hid, sub_ids in self._lineage_dams_sub_sires_map.items():
                    if f_id in sub_ids:
                        self._lineage_dams_data_cache[target_hid].append(dam_entry)

        total_active_dams = len(dams_list) or 1
        self._lineage_dams_root_sires = root_sires
        self._lineage_dams_horses_map = horses_map
        self._lineage_dams_depth_cache = depth_cache
        self._lineage_dams_sire_sons_map = sire_sons_map
        self._lineage_dams_total_cnt = total_active_dams

        self.tree_lineage_dams.clear()

        for root_id in root_sires:
            h = horses_map.get(root_id)
            if not h: continue

            root_name = h.get("name", "不明")
            d_list = self._lineage_dams_data_cache.get(root_id, [])
            cnt = len(d_list)
            # 断絶（供用中繁殖牝馬が0頭）の系統は表示しない
            if cnt == 0:
                continue

            share_pct = f"{(cnt / total_active_dams * 100):.1f}%"
            p_wins = sum(x.get("p_wins", 0) for x in d_list)
            w_cnt = sum(x.get("w_cnt", 0) for x in d_list)
            act_p_cnt = sum(x.get("act_p_cnt", 0) for x in d_list)
            win_rate = f"{(w_cnt / act_p_cnt * 100):.1f}%" if act_p_cnt > 0 else "0.0%"

            rep_dam_str = "-"
            if d_list:
                rep_dam = max(d_list, key=lambda x: (x.get("p_wins", 0), x.get("p_cnt", 0)))
                rep_dam_str = f"{rep_dam.get('name', '')} (産駒{rep_dam.get('p_wins', 0)}勝)"

            root_item = QTreeWidgetItem()
            root_item.setText(0, f"🌸 {root_name}系")
            root_item.setText(1, f"{cnt:,}頭")
            root_item.setText(2, share_pct)
            root_item.setText(3, f"{p_wins}勝")
            root_item.setText(4, f"{w_cnt}頭")
            root_item.setText(5, win_rate)
            root_item.setText(6, rep_dam_str)
            root_item.setData(0, Qt.ItemDataRole.UserRole, root_id)

            for col in range(1, 6):
                root_item.setTextAlignment(col, Qt.AlignmentFlag.AlignCenter)

            visited_sub = set()
            def add_child_lines(parent_item, parent_hid):
                def find_next_lines(curr_hid):
                    lines = []
                    for son_id in sire_sons_map.get(curr_hid, []):
                        if son_id in visited_sub: continue
                        visited_sub.add(son_id)
                        if depth_cache.get(son_id, 0) >= 2:
                            lines.append(son_id)
                        else:
                            lines.extend(find_next_lines(son_id))
                    return lines

                sub_line_ids = find_next_lines(parent_hid)
                for sub_id in sub_line_ids:
                    sub_h = horses_map.get(sub_id)
                    if not sub_h: continue
                    sub_list = self._lineage_dams_data_cache.get(sub_id, [])
                    sub_cnt = len(sub_list)
                    # 断絶（供用中繁殖牝馬が0頭）の子系統は表示しない
                    if sub_cnt == 0:
                        continue

                    sub_share = f"{(sub_cnt / total_active_dams * 100):.1f}%"
                    sub_p_wins = sum(x.get("p_wins", 0) for x in sub_list)
                    sub_w_cnt = sum(x.get("w_cnt", 0) for x in sub_list)
                    sub_act_p = sum(x.get("act_p_cnt", 0) for x in sub_list)
                    sub_win_rate = f"{(sub_w_cnt / sub_act_p * 100):.1f}%" if sub_act_p > 0 else "0.0%"

                    sub_rep = "-"
                    if sub_list:
                        rep_d = max(sub_list, key=lambda x: (x.get("p_wins", 0), x.get("p_cnt", 0)))
                        sub_rep = f"{rep_d.get('name', '')} (産駒{rep_d.get('p_wins', 0)}勝)"

                    sub_item = QTreeWidgetItem(parent_item)
                    sub_item.setText(0, f"└ {sub_h.get('name', '')}系")
                    sub_item.setText(1, f"{sub_cnt:,}頭")
                    sub_item.setText(2, sub_share)
                    sub_item.setText(3, f"{sub_p_wins}勝")
                    sub_item.setText(4, f"{sub_w_cnt}頭")
                    sub_item.setText(5, sub_win_rate)
                    sub_item.setText(6, sub_rep)
                    sub_item.setData(0, Qt.ItemDataRole.UserRole, sub_id)

                    for col in range(1, 6):
                        sub_item.setTextAlignment(col, Qt.AlignmentFlag.AlignCenter)

                    add_child_lines(sub_item, sub_id)

            add_child_lines(root_item, root_id)
            self.tree_lineage_dams.addTopLevelItem(root_item)
            root_item.setExpanded(True)

        if self.tree_lineage_dams.topLevelItemCount() > 0:
            first_it = self.tree_lineage_dams.topLevelItem(0)
            self.tree_lineage_dams.setCurrentItem(first_it)
            hid = first_it.data(0, Qt.ItemDataRole.UserRole)
            if hid: self._load_lineage_dams_by_hid(hid)

    def _on_lineage_dams_tree_clicked(self, item: QTreeWidgetItem, col: int) -> None:
        hid = item.data(0, Qt.ItemDataRole.UserRole)
        if hid:
            self._load_lineage_dams_by_hid(hid)

    def _load_lineage_dams_by_hid(self, hid: int) -> None:
        """選択された系統の所属繁殖牝馬一覧を表示"""
        dams_list = getattr(self, "_lineage_dams_data_cache", {}).get(hid, [])
        dams_list = sorted(dams_list, key=lambda x: (-(x.get("p_wins") or 0), -(x.get("p_cnt") or 0)))

        self.table_lineage_dams_detail.setRowCount(len(dams_list))
        for idx, r in enumerate(dams_list):
            d_name = r.get("name", "")
            gen = r.get("d_generation") or r.get("generation") or 1
            st_yr = r.get("start_year") or 1
            name_col = get_generation_color(gen, is_breeding=True, start_year=st_yr)
            age_str = f"{r.get('age')}歳" if r.get("age") else "-"
            gen_str = f"第{gen}世代"

            s_id = r.get("sire_id")
            s_name = self._lineage_dams_horses_map.get(s_id, {}).get("name", "-") if s_id else "-"
            d_id = r.get("dam_id")
            dam_mother_name = self._lineage_dams_horses_map.get(d_id, {}).get("name", "-") if d_id else "-"

            p_cnt = r.get("p_cnt", 0)
            w_cnt = r.get("w_cnt", 0)
            act_cnt = r.get("act_p_cnt", 0)
            win_rate = f"{(w_cnt / act_cnt * 100):.1f}%" if act_cnt > 0 else "0.0%"

            name_item = QTableWidgetItem(f"🌸 {d_name}")
            name_item.setForeground(QColor(name_col))
            f = name_item.font()
            f.setBold(True)
            name_item.setFont(f)
            name_item.setData(Qt.ItemDataRole.UserRole, r.get("horse_id"))

            items = [
                name_item,
                QTableWidgetItem(age_str),
                QTableWidgetItem(gen_str),
                QTableWidgetItem(s_name),
                QTableWidgetItem(dam_mother_name),
                QTableWidgetItem(str(p_cnt)),
                QTableWidgetItem(str(w_cnt)),
                QTableWidgetItem(win_rate),
            ]
            for c_idx, it in enumerate(items):
                if c_idx not in (0, 3, 4):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_lineage_dams_detail.setItem(idx, c_idx, it)

            hid_target = r.get("horse_id")
            btn_karte = QPushButton("カルテ")
            btn_karte.setStyleSheet("background-color: #db2777; color: #ffffff; font-size: 11px; padding: 2px 4px; border-radius: 3px; font-weight: bold;")
            btn_karte.clicked.connect(lambda checked, h_id=hid_target: self._open_dam_detail(h_id))
            self.table_lineage_dams_detail.setCellWidget(idx, 8, btn_karte)

    # ==========================================
    # 5-3. ファミリーナンバー別 繁殖牝馬 サブタブ & 集計処理 (新設)
    # ==========================================
    def _create_family_dams_subtab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # 上部: ファミリーナンバー(族)別 繁殖牝馬集計ツリー (始祖馬が族名)
        top_box = QGroupBox("🌸 現在のファミリーナンバー (族) 別 繁殖牝馬数・構成割合 (行を選択して下部一覧を表示)")
        top_layout = QVBoxLayout(top_box)
        top_layout.setContentsMargins(6, 6, 6, 6)

        self.tree_family_dams = QTreeWidget()
        self.tree_family_dams.setHeaderLabels([
            "ファミリーナンバー (族)", "繁殖牝馬数", "構成割合", "深さ(世代)", "産駒総勝利数", "勝馬数", "勝ち上がり率", "代表繁殖牝馬"
        ])
        self.tree_family_dams.setAlternatingRowColors(True)
        self.tree_family_dams.setRootIsDecorated(True)
        self.tree_family_dams.setAnimated(True)
        self.tree_family_dams.setStyleSheet("""
            QTreeWidget {
                background-color: #12161f;
                alternate-background-color: #1a202c;
                color: #f8fafc;
                border: 1px solid #242c3d;
                border-radius: 6px;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 5px 2px;
                background-color: transparent;
            }
            QTreeWidget::item:hover {
                background-color: #1e293b;
            }
            QTreeWidget::item:selected {
                background-color: #be185d;
                color: #ffffff;
                font-weight: bold;
            }
            QHeaderView::section {
                background-color: #0b0f17;
                color: #cbd5e1;
                padding: 6px 4px;
                border: none;
                border-bottom: 2px solid #334155;
                border-right: 1px solid #1e293b;
                font-weight: 700;
            }
        """)
        h_tree = self.tree_family_dams.header()
        h_tree.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 7):
            h_tree.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        h_tree.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.tree_family_dams.itemClicked.connect(self._on_family_dams_tree_clicked)
        top_layout.addWidget(self.tree_family_dams)
        layout.addWidget(top_box, stretch=1)

        # 下部: 選択された族の所属繁殖牝馬一覧
        bot_box = QGroupBox("🌸 所属繁殖牝馬一覧 (行をクリックして選択)")
        bot_layout = QVBoxLayout(bot_box)
        bot_layout.setContentsMargins(6, 6, 6, 6)

        self.table_family_dams_detail = QTableWidget()
        self.table_family_dams_detail.setColumnCount(9)
        self.table_family_dams_detail.setHorizontalHeaderLabels([
            "牝馬名", "年齢", "世代", "父馬", "母馬", "産駒数", "勝馬数", "勝ち上がり率", "カルテ"
        ])
        b_hdr = self.table_family_dams_detail.horizontalHeader()
        b_hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_family_dams_detail.setColumnWidth(0, 160)
        self.table_family_dams_detail.setColumnWidth(1, 55)
        self.table_family_dams_detail.setColumnWidth(2, 55)
        self.table_family_dams_detail.setColumnWidth(3, 130)
        self.table_family_dams_detail.setColumnWidth(4, 130)
        self.table_family_dams_detail.setColumnWidth(5, 65)
        self.table_family_dams_detail.setColumnWidth(6, 65)
        b_hdr.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.table_family_dams_detail.setColumnWidth(8, 60)

        self.table_family_dams_detail.setAlternatingRowColors(True)
        self.table_family_dams_detail.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        bot_layout.addWidget(self.table_family_dams_detail)
        layout.addWidget(bot_box, stretch=1)

        return widget

    def refresh_family_dams(self) -> None:
        """現在のファミリーナンバー別 繁殖牝馬集計ロード"""
        with self.db.session() as conn:
            h_rows = conn.execute("SELECT * FROM horses").fetchall()
            h_cols = [d[0] for d in conn.execute("SELECT * FROM horses LIMIT 1").description]
            horses_map = {r[h_cols.index("horse_id")]: dict(zip(h_cols, r)) for r in h_rows}

            d_all_rows = conn.execute("SELECT * FROM dams").fetchall()
            d_cols = [d[0] for d in conn.execute("SELECT * FROM dams LIMIT 1").description]
            dams_map = {r[d_cols.index("horse_id")]: dict(zip(d_cols, r)) for r in d_all_rows}

            # 産駒成績の集計
            prog_stat_rows = conn.execute("""
                SELECT dam_id,
                       COUNT(horse_id) as p_count,
                       COUNT(CASE WHEN is_active = 1 THEN horse_id END) as p_active_count,
                       SUM(career_wins) as p_wins,
                       SUM(CASE WHEN is_active = 1 AND career_wins > 0 THEN 1 ELSE 0 END) as p_winners
                FROM horses
                WHERE dam_id IS NOT NULL
                GROUP BY dam_id
            """).fetchall()
            prog_map = {r["dam_id"]: dict(r) for r in prog_stat_rows}

        # 1. 繁殖牝馬間の親子マップ構築
        dam_daughters_map = defaultdict(list)
        for hid in dams_map:
            h = horses_map.get(hid)
            if not h: continue
            mid = h.get("dam_id")
            if mid and mid in dams_map:
                dam_daughters_map[mid].append(hid)

        # 2. 深さキャッシュ
        depth_cache = {}
        visited_depth = set()
        def calc_depth(hid):
            if hid in depth_cache: return depth_cache[hid]
            if hid in visited_depth: return 0
            visited_depth.add(hid)
            daughters = dam_daughters_map.get(hid, [])
            if not daughters:
                depth_cache[hid] = 0
                return 0
            d = 1 + max(calc_depth(did) for did in daughters)
            depth_cache[hid] = d
            return d

        for hid in dams_map:
            visited_depth.clear()
            calc_depth(hid)

        # 3. 祖先を遡って始祖（Root Dam）特定
        dam_to_root_map = {}
        for hid in dams_map:
            curr = hid
            visited_anc = set()
            while curr in dams_map and curr not in visited_anc:
                visited_anc.add(curr)
                h = horses_map.get(curr)
                if not h: break
                mid = h.get("dam_id")
                if mid and mid in dams_map:
                    curr = mid
                else:
                    break
            dam_to_root_map[hid] = curr

        root_dams = sorted(
            list(set(dam_to_root_map.values())),
            key=lambda x: (horses_map.get(x, {}).get("birth_year", 9999), horses_map.get(x, {}).get("name", ""))
        )

        # 4. 各族に属する現役繁殖牝馬のマッピング
        self._family_dams_data_cache = defaultdict(list)
        for hid, d in dams_map.items():
            if d.get("is_active"):
                root_id = dam_to_root_map.get(hid, hid)
                dh = horses_map.get(hid, {})
                p_info = prog_map.get(hid, {})
                self._family_dams_data_cache[root_id].append({
                    **dh, **d,
                    "p_cnt": p_info.get("p_count", 0),
                    "act_p_cnt": p_info.get("p_active_count", 0),
                    "p_wins": p_info.get("p_wins", 0),
                    "w_cnt": p_info.get("p_winners", 0),
                })

        total_active_dams = sum(1 for d in dams_map.values() if d.get("is_active")) or 1
        self._family_dams_horses_map = horses_map
        self._family_dams_dams_map = dams_map
        self._family_dams_dam_daughters_map = dam_daughters_map
        self._family_dams_depth_cache = depth_cache

        self.tree_family_dams.clear()

        for root_id in root_dams:
            h = horses_map.get(root_id)
            if not h: continue

            d_list = self._family_dams_data_cache.get(root_id, [])
            cnt = len(d_list)
            # 断絶（現在供用中の繁殖牝馬が0頭）の族は表示しない
            if cnt == 0:
                continue

            share_pct = f"{(cnt / total_active_dams * 100):.1f}%"
            depth = depth_cache.get(root_id, 0)
            p_wins = sum(x.get("p_wins", 0) for x in d_list)
            w_cnt = sum(x.get("w_cnt", 0) for x in d_list)
            act_p_cnt = sum(x.get("act_p_cnt", 0) for x in d_list)
            win_rate = f"{(w_cnt / act_p_cnt * 100):.1f}%" if act_p_cnt > 0 else "0.0%"

            rep_dam_str = "-"
            if d_list:
                rep_dam = max(d_list, key=lambda x: (x.get("p_wins", 0), x.get("p_cnt", 0)))
                rep_dam_str = f"{rep_dam.get('name', '')} (産駒{rep_dam.get('p_wins', 0)}勝)"

            root_name = h.get("name", "始祖牝馬")
            root_item = QTreeWidgetItem()
            root_item.setText(0, f"🌸 {root_name}族")
            root_item.setText(1, f"{cnt:,}頭")
            root_item.setText(2, share_pct)
            root_item.setText(3, f"世代:{depth}")
            root_item.setText(4, f"{p_wins}勝")
            root_item.setText(5, f"{w_cnt}頭")
            root_item.setText(6, win_rate)
            root_item.setText(7, rep_dam_str)
            root_item.setData(0, Qt.ItemDataRole.UserRole, root_id)

            for col in range(1, 7):
                root_item.setTextAlignment(col, Qt.AlignmentFlag.AlignCenter)

            # 後継繁殖牝馬の階層展開（自身または子孫に供用中牝馬がいる枝のみ）
            visited_sub = set()
            active_descendant_cache = {}

            def has_active_descendant(target_did: int) -> bool:
                if target_did in active_descendant_cache:
                    return active_descendant_cache[target_did]
                if bool(dams_map.get(target_did, {}).get("is_active", 0)):
                    active_descendant_cache[target_did] = True
                    return True
                for child_did in dam_daughters_map.get(target_did, []):
                    if has_active_descendant(child_did):
                        active_descendant_cache[target_did] = True
                        return True
                active_descendant_cache[target_did] = False
                return False

            def add_child_dams(parent_item, parent_hid):
                for did in dam_daughters_map.get(parent_hid, []):
                    if did in visited_sub: continue
                    visited_sub.add(did)
                    # 自身または子孫に供用中牝馬がいない枝は除外
                    if not has_active_descendant(did):
                        continue
                    dh = horses_map.get(did)
                    if not dh: continue
                    d_item = QTreeWidgetItem(parent_item)
                    d_name = dh.get("name", "不明")
                    d_depth = depth_cache.get(did, 0)
                    p_info = prog_map.get(did, {})
                    d_wins = p_info.get("p_wins", 0)
                    d_winners = p_info.get("p_winners", 0)
                    d_act_p = p_info.get("p_active_count", 0)
                    d_win_rate = f"{(d_winners / d_act_p * 100):.1f}%" if d_act_p > 0 else "0.0%"
                    d_act_badge = " [供用中]" if bool(dams_map.get(did, {}).get("is_active", 0)) else ""

                    d_item.setText(0, f"└ {d_name}{d_act_badge}")
                    d_item.setText(3, f"世代:{d_depth}")
                    d_item.setText(4, f"{d_wins}勝")
                    d_item.setText(5, f"{d_winners}頭")
                    d_item.setText(6, d_win_rate)
                    d_item.setData(0, Qt.ItemDataRole.UserRole, root_id)

                    for col in range(1, 7):
                        d_item.setTextAlignment(col, Qt.AlignmentFlag.AlignCenter)

                    add_child_dams(d_item, did)

            add_child_dams(root_item, root_id)
            self.tree_family_dams.addTopLevelItem(root_item)

        if self.tree_family_dams.topLevelItemCount() > 0:
            first_it = self.tree_family_dams.topLevelItem(0)
            self.tree_family_dams.setCurrentItem(first_it)
            hid = first_it.data(0, Qt.ItemDataRole.UserRole)
            if hid: self._load_family_dams_by_hid(hid)

    def _on_family_dams_tree_clicked(self, item: QTreeWidgetItem, col: int) -> None:
        root_id = item.data(0, Qt.ItemDataRole.UserRole)
        if root_id:
            self._load_family_dams_by_hid(root_id)

    def _load_family_dams_by_hid(self, root_id: int) -> None:
        """選択された族の所属繁殖牝馬一覧を表示"""
        dams_list = getattr(self, "_family_dams_data_cache", {}).get(root_id, [])
        dams_list = sorted(dams_list, key=lambda x: (-(x.get("p_wins") or 0), -(x.get("p_cnt") or 0)))

        self.table_family_dams_detail.setRowCount(len(dams_list))
        for idx, r in enumerate(dams_list):
            d_name = r.get("name", "")
            gen = r.get("d_generation") or r.get("generation") or 1
            st_yr = r.get("start_year") or 1
            name_col = get_generation_color(gen, is_breeding=True, start_year=st_yr)
            age_str = f"{r.get('age')}歳" if r.get("age") else "-"
            gen_str = f"第{gen}世代"

            s_id = r.get("sire_id")
            s_name = self._family_dams_horses_map.get(s_id, {}).get("name", "-") if s_id else "-"
            d_id = r.get("dam_id")
            dam_mother_name = self._family_dams_horses_map.get(d_id, {}).get("name", "-") if d_id else "-"

            p_cnt = r.get("p_cnt", 0)
            w_cnt = r.get("w_cnt", 0)
            act_cnt = r.get("act_p_cnt", 0)
            win_rate = f"{(w_cnt / act_cnt * 100):.1f}%" if act_cnt > 0 else "0.0%"

            name_item = QTableWidgetItem(f"🌸 {d_name}")
            name_item.setForeground(QColor(name_col))
            f = name_item.font()
            f.setBold(True)
            name_item.setFont(f)
            name_item.setData(Qt.ItemDataRole.UserRole, r.get("horse_id"))

            items = [
                name_item,
                QTableWidgetItem(age_str),
                QTableWidgetItem(gen_str),
                QTableWidgetItem(s_name),
                QTableWidgetItem(dam_mother_name),
                QTableWidgetItem(str(p_cnt)),
                QTableWidgetItem(str(w_cnt)),
                QTableWidgetItem(win_rate),
            ]
            for c_idx, it in enumerate(items):
                if c_idx not in (0, 3, 4):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_family_dams_detail.setItem(idx, c_idx, it)

            hid_target = r.get("horse_id")
            btn_karte = QPushButton("カルテ")
            btn_karte.setStyleSheet("background-color: #db2777; color: #ffffff; font-size: 11px; padding: 2px 4px; border-radius: 3px; font-weight: bold;")
            btn_karte.clicked.connect(lambda checked, h_id=hid_target: self._open_dam_detail(h_id))
            self.table_family_dams_detail.setCellWidget(idx, 8, btn_karte)

    def _on_sire_cell_clicked(self, row: int, col: int) -> None:
        """種牡馬リストセルクリック"""
        if col == 0:
            item = self.table_sires.item(row, 0)
            if item:
                hid = item.data(Qt.ItemDataRole.UserRole)
                if hid:
                    self._open_sire_detail(hid)
        elif col == 9:  # 代表産駒
            item = self.table_sires.item(row, 9)
            if item:
                hid = item.data(Qt.ItemDataRole.UserRole)
                if hid:
                    self._open_horse_detail(hid)

    def _open_sire_detail(self, sire_horse_id: int) -> None:
        """種牡馬カルテ表示"""
        dlg = SireDetailDialog(self.db, sire_horse_id, parent=self)
        dlg.exec()

    def _open_dam_detail(self, dam_horse_id: int) -> None:
        """繁殖牝馬カルテ表示"""
        dlg = DamDetailDialog(self.db, dam_horse_id, parent=self)
        dlg.exec()

    # ==========================================
    # 5. 繁殖牝馬リストタブ
    # ==========================================
    def _create_broodmares_list_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self.dams_sub_tabs = QTabWidget()
        self.dams_sub_tabs.setStyleSheet("""
            QTabBar::tab {
                font-weight: bold;
                font-size: 12px;
                padding: 6px 14px;
            }
        """)

        # サブタブ1: 全繁殖牝馬一覧
        self.tab_dams_all = self._create_dam_all_list_subtab()
        self.dams_sub_tabs.addTab(self.tab_dams_all, "🌸 全繁殖牝馬一覧")

        # サブタブ2: サイアーライン別 繁殖牝馬リスト
        self.tab_lineage_dams = self._create_lineage_dams_subtab()
        self.dams_sub_tabs.addTab(self.tab_lineage_dams, "🌸 サイアーライン別 繁殖牝馬")

        # サブタブ3: ファミリーナンバー別 繁殖牝馬リスト (新設！)
        self.tab_family_dams = self._create_family_dams_subtab()
        self.dams_sub_tabs.addTab(self.tab_family_dams, "🌸 ファミリーナンバー別 繁殖牝馬")

        layout.addWidget(self.dams_sub_tabs)
        self.dams_sub_tabs.currentChanged.connect(self._on_dams_subtab_changed)

        return widget

    def _on_dams_subtab_changed(self, index: int) -> None:
        if index == 0:
            self.refresh_broodmares_list()
        elif index == 1:
            self.refresh_lineage_dams()
        elif index == 2:
            self.refresh_family_dams()

    # 5-1. 全繁殖牝馬一覧 サブタブ
    def _create_dam_all_list_subtab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        filter_bar = QFrame()
        filter_bar.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 6px;")
        f_layout = QHBoxLayout(filter_bar)
        f_layout.setContentsMargins(10, 6, 10, 6)
        f_layout.setSpacing(12)

        f_layout.addWidget(QLabel("状態:"))
        self.combo_dam_status = QComboBox()
        self.combo_dam_status.addItem("供用中のみ", "active")
        self.combo_dam_status.addItem("全繁殖牝馬 (引退含む)", "all")
        self.combo_dam_status.currentIndexChanged.connect(self.refresh_broodmares_list)
        f_layout.addWidget(self.combo_dam_status)

        f_layout.addWidget(QLabel("並び順:"))
        self.combo_dam_sort = QComboBox()
        self.combo_dam_sort.addItem("産駒頭数（降順）", "progeny_desc")
        self.combo_dam_sort.addItem("馬名（50音順）", "name_asc")
        self.combo_dam_sort.addItem("繋養年数（降順）", "years_desc")
        self.combo_dam_sort.addItem("勝ち馬数（降順）", "winners_desc")
        self.combo_dam_sort.addItem("勝ち上がり率（降順）", "rate_desc")
        self.combo_dam_sort.currentIndexChanged.connect(self.refresh_broodmares_list)
        f_layout.addWidget(self.combo_dam_sort)

        btn_ref = QPushButton("🔄 更新")
        btn_ref.setStyleSheet("background-color: #0284c7; color: #ffffff; font-weight: bold; padding: 4px 12px; border-radius: 4px;")
        btn_ref.clicked.connect(self.refresh_broodmares_list)
        f_layout.addWidget(btn_ref)

        f_layout.addStretch()
        layout.addWidget(filter_bar)

        self.table_dams = QTableWidget()
        self.table_dams.setColumnCount(11)
        self.table_dams.setHorizontalHeaderLabels([
            "繁殖牝馬名", "年齢", "繋養開始", "繋養年数", "父馬 (サイヤー)", "産駒頭数", "勝馬数", "勝ち上がり率", "代表産駒", "カルテ", "産駒一覧"
        ])
        header = self.table_dams.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_dams.setColumnWidth(0, 160)
        self.table_dams.setColumnWidth(1, 50)
        self.table_dams.setColumnWidth(2, 65)
        self.table_dams.setColumnWidth(3, 65)
        self.table_dams.setColumnWidth(4, 120)
        self.table_dams.setColumnWidth(5, 65)
        self.table_dams.setColumnWidth(6, 65)
        self.table_dams.setColumnWidth(7, 85)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        self.table_dams.setColumnWidth(9, 60)
        self.table_dams.setColumnWidth(10, 75)

        self.table_dams.setAlternatingRowColors(True)
        self.table_dams.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_dams.cellClicked.connect(self._on_dam_cell_clicked)
        layout.addWidget(self.table_dams)

        return widget

    def refresh_broodmares_list(self) -> None:
        """繁殖牝馬一覧をロード"""
        status_filter = self.combo_dam_status.currentData()
        sort_mode = self.combo_dam_sort.currentData() or "progeny_desc"

        with self.db.session() as conn:
            # 現在年度を取得
            max_y_row = conn.execute("SELECT MAX(year) as max_year FROM races").fetchone()
            cur_year = (max_y_row["max_year"] or 1) if max_y_row else 1

            query = """
                SELECT d.dam_id, d.horse_id, d.start_year, d.is_active,
                       d.generation as d_generation,
                       dh.name as name, dh.age as age, dh.birth_year, dh.retired_year,
                       dh.generation as h_generation,
                       sh.name as sire_name,
                       COUNT(DISTINCT ph.horse_id) as progeny_count,
                       COUNT(DISTINCT CASE WHEN ph.is_active = 1 THEN ph.horse_id END) as active_progeny_count,
                       SUM(CASE WHEN (ph.is_active = 1 AND ph.career_wins > 0) THEN 1 ELSE 0 END) as winners_count,
                       SUM(CASE WHEN (ph.career_wins > 0) THEN 1 ELSE 0 END) as total_winners_count
                FROM dams d
                JOIN horses dh ON d.horse_id = dh.horse_id
                LEFT JOIN horses sh ON dh.sire_id = sh.horse_id
                LEFT JOIN horses ph ON d.horse_id = ph.dam_id
                WHERE 1=1
            """
            if status_filter == "active":
                query += " AND d.is_active = 1"
            query += " GROUP BY d.dam_id"

            rows = conn.execute(query).fetchall()

            # 代表産駒を一括取得 (N+1解消)
            top_prog_map = {}
            top_prog_rows = conn.execute("""
                SELECT horse_id, dam_id, name, prize_money, generation
                FROM horses
                WHERE dam_id IS NOT NULL AND prize_money > 0
                ORDER BY prize_money DESC
            """).fetchall()
            for pr in top_prog_rows:
                did = pr["dam_id"]
                if did not in top_prog_map:
                    top_prog_map[did] = {
                        "name": f"{pr['name']} ({(pr['prize_money'] // 10000):,}万円)",
                        "horse_id": pr["horse_id"],
                        "generation": pr["generation"] or 1
                    }

            # 各行の加工と繋養年数の算出
            processed_rows = []
            for r in rows:
                p_dict = dict(r)
                p_cnt = p_dict["progeny_count"] or 0
                act_cnt = p_dict["active_progeny_count"] or 0
                w_cnt = p_dict["winners_count"] or 0  # 現役馬での勝馬頭数
                p_dict["win_rate_val"] = (w_cnt / act_cnt) if act_cnt > 0 else 0.0

                st_yr = p_dict.get("start_year", 1) or 1
                p_dict["start_year_val"] = st_yr
                p_dict["years_in_service"] = max(1, cur_year - st_yr + 1)
                processed_rows.append(p_dict)

            # ソート適用
            if sort_mode == "name_asc":
                processed_rows.sort(key=lambda x: (not x["is_active"], x["name"]))
            elif sort_mode == "years_desc":
                processed_rows.sort(key=lambda x: (not x["is_active"], -x["years_in_service"], -x["progeny_count"], x["name"]))
            elif sort_mode == "winners_desc":
                processed_rows.sort(key=lambda x: (not x["is_active"], -x["winners_count"], -x["progeny_count"], x["name"]))
            elif sort_mode == "rate_desc":
                processed_rows.sort(key=lambda x: (not x["is_active"], -x["win_rate_val"], -x["progeny_count"], x["name"]))
            else:  # progeny_desc (デフォルト)
                processed_rows.sort(key=lambda x: (not x["is_active"], -x["progeny_count"], -x["winners_count"], x["name"]))

        self.table_dams.setRowCount(len(processed_rows))

        for idx, r in enumerate(processed_rows):
            d_name = r["name"]
            gen = r.get("d_generation") or r.get("h_generation") or 1
            name_col = get_generation_color(gen, is_breeding=True, start_year=r.get("start_year_val"))

            age_str = f"{r['age']}歳" if r["age"] else "-"
            st_yr_str = f"{r['start_year_val']}年"
            years_str = f"{r['years_in_service']}年目"
            s_name = r["sire_name"] or "-"
            p_cnt = r["progeny_count"] or 0
            w_cnt = r["winners_count"] or 0
            win_rate = f"{(r['win_rate_val'] * 100):.1f}%" if p_cnt > 0 else "0.0%"

            top_prog_info = top_prog_map.get(r["horse_id"], {})
            top_prog_name = top_prog_info.get("name", "-")
            top_prog_hid = top_prog_info.get("horse_id")
            top_prog_gen = top_prog_info.get("generation", 1)

            name_item = QTableWidgetItem(f"🌸 {d_name}")
            name_item.setForeground(QColor(name_col))
            f = name_item.font()
            f.setBold(True)
            name_item.setFont(f)
            name_item.setData(Qt.ItemDataRole.UserRole, r["horse_id"])

            rep_item = QTableWidgetItem(top_prog_name)
            if top_prog_hid:
                prog_color = get_generation_color(top_prog_gen)
                rep_item.setForeground(QColor(prog_color))
                rep_item.setData(Qt.ItemDataRole.UserRole, top_prog_hid)

            items = [
                name_item,
                QTableWidgetItem(age_str),
                QTableWidgetItem(st_yr_str),
                QTableWidgetItem(years_str),
                QTableWidgetItem(s_name),
                QTableWidgetItem(str(p_cnt)),
                QTableWidgetItem(str(w_cnt)),
                QTableWidgetItem(win_rate),
                rep_item,
            ]

            for c_idx, item in enumerate(items):
                if c_idx not in (0, 8):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_dams.setItem(idx, c_idx, item)

            hid = r["horse_id"]
            # カルテ詳細ボタン
            btn_karte = QPushButton("カルテ")
            btn_karte.setStyleSheet("background-color: #db2777; color: #ffffff; font-size: 11px; padding: 2px 4px; border-radius: 3px; font-weight: bold;")
            btn_karte.clicked.connect(lambda checked, h_id=hid: self._open_dam_detail(h_id))
            self.table_dams.setCellWidget(idx, 9, btn_karte)

            # 産駒一覧ボタン
            btn_prog = QPushButton("産駒一覧")
            btn_prog.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 11px; padding: 2px 4px; border: 1px solid #0284c7; border-radius: 3px;")
            btn_prog.clicked.connect(lambda checked, h_id=hid: self._open_progeny_dialog(h_id, is_sire=False))
            self.table_dams.setCellWidget(idx, 10, btn_prog)

    def _on_dam_cell_clicked(self, row: int, col: int) -> None:
        """繁殖牝馬リストセルクリック"""
        if col == 0:
            item = self.table_dams.item(row, 0)
            if item:
                hid = item.data(Qt.ItemDataRole.UserRole)
                if hid:
                    self._open_dam_detail(hid)
        elif col == 8:  # 代表産駒
            item = self.table_dams.item(row, 8)
            if item:
                hid = item.data(Qt.ItemDataRole.UserRole)
                if hid:
                    self._open_horse_detail(hid)

    def _open_progeny_dialog(self, parent_id: int, is_sire: bool = True) -> None:
        dlg = ProgenyListDialog(self.db, parent_id, is_sire=is_sire, parent=self)
        dlg.exec()

    # ==========================================
    # 6. 過去の重賞レースデータベース
    # ==========================================
    def _create_graded_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        filter_bar = QFrame()
        filter_bar.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 6px;")
        f_layout = QHBoxLayout(filter_bar)
        f_layout.setContentsMargins(10, 6, 10, 6)
        f_layout.setSpacing(12)

        f_layout.addWidget(QLabel("年度:"))
        self.combo_graded_year = QComboBox()
        self.combo_graded_year.addItem("全年度", None)
        self.combo_graded_year.currentIndexChanged.connect(self.refresh_graded)
        f_layout.addWidget(self.combo_graded_year)

        f_layout.addWidget(QLabel("グレード:"))
        self.combo_graded_grade = QComboBox()
        self.combo_graded_grade.addItem("全重賞 (G1-G3)", None)
        self.combo_graded_grade.addItem("🏆 G1 のみ", "G1")
        self.combo_graded_grade.addItem("🥈 G2 のみ", "G2")
        self.combo_graded_grade.addItem("🥉 G3 のみ", "G3")
        self.combo_graded_grade.currentIndexChanged.connect(self.refresh_graded)
        f_layout.addWidget(self.combo_graded_grade)

        f_layout.addWidget(QLabel("競馬場:"))
        self.combo_graded_track = QComboBox()
        self.combo_graded_track.addItem("全競馬場", None)
        tracks = ["TOKYO", "NAKAYAMA", "HANSHIN", "KYOTO", "CHUKYO", "NIIGATA", "FUKUSHIMA", "KOKURA", "OI", "KAWASAKI", "FUNABASHI", "MORIOKA"]
        for t in tracks:
            self.combo_graded_track.addItem(t, t)
        self.combo_graded_track.currentIndexChanged.connect(self.refresh_graded)
        f_layout.addWidget(self.combo_graded_track)

        f_layout.addWidget(QLabel("レース名:"))
        self.combo_graded_name = QComboBox()
        self.combo_graded_name.addItem("全レース", None)
        self.combo_graded_name.currentIndexChanged.connect(self.refresh_graded)
        f_layout.addWidget(self.combo_graded_name)

        btn_ref = QPushButton("🔄 更新")
        btn_ref.setStyleSheet("background-color: #0284c7; color: #ffffff; font-weight: bold; padding: 4px 12px; border-radius: 4px;")
        btn_ref.clicked.connect(self.refresh_graded)
        f_layout.addWidget(btn_ref)

        f_layout.addStretch()
        layout.addWidget(filter_bar)

        self.table_graded = QTableWidget()
        self.table_graded.setColumnCount(12)
        self.table_graded.setHorizontalHeaderLabels([
            "年度", "週", "レース名", "グレード", "競馬場", "距離", "馬場", "優勝馬", "タイム", "騎手", "結果", "動画"
        ])
        h_header = self.table_graded.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_graded.setColumnWidth(0, 55)
        self.table_graded.setColumnWidth(1, 45)
        self.table_graded.setColumnWidth(2, 160)
        self.table_graded.setColumnWidth(3, 70)
        self.table_graded.setColumnWidth(4, 75)
        self.table_graded.setColumnWidth(5, 60)
        self.table_graded.setColumnWidth(6, 50)
        self.table_graded.setColumnWidth(7, 140)
        self.table_graded.setColumnWidth(8, 75)
        self.table_graded.setColumnWidth(9, 80)
        self.table_graded.setColumnWidth(10, 65)
        self.table_graded.setColumnWidth(11, 65)
        h_header.setStretchLastSection(False)

        self.table_graded.setAlternatingRowColors(True)
        self.table_graded.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table_graded)

        return widget

    def _refresh_graded_years(self) -> None:
        with self.db.session() as conn:
            rows = conn.execute("SELECT DISTINCT year FROM races WHERE grade IN ('G1', 'G2', 'G3') ORDER BY year ASC").fetchall()
            name_rows = conn.execute("SELECT DISTINCT name FROM races WHERE grade IN ('G1', 'G2', 'G3') ORDER BY name ASC").fetchall()

        cur_year = self.combo_graded_year.currentData()
        self.combo_graded_year.blockSignals(True)
        self.combo_graded_year.clear()
        self.combo_graded_year.addItem("全年度", None)
        for r in rows:
            self.combo_graded_year.addItem(f"{r['year']}年", r["year"])
        if cur_year is not None:
            idx = self.combo_graded_year.findData(cur_year)
            if idx >= 0:
                self.combo_graded_year.setCurrentIndex(idx)
        self.combo_graded_year.blockSignals(False)

        cur_name = self.combo_graded_name.currentData()
        self.combo_graded_name.blockSignals(True)
        self.combo_graded_name.clear()
        self.combo_graded_name.addItem("全レース", None)
        for r in name_rows:
            self.combo_graded_name.addItem(clean_race_name(r["name"]), r["name"])
        if cur_name is not None:
            idx = self.combo_graded_name.findData(cur_name)
            if idx >= 0:
                self.combo_graded_name.setCurrentIndex(idx)
        self.combo_graded_name.blockSignals(False)

    def refresh_graded(self) -> None:
        year_filter = self.combo_graded_year.currentData()
        grade_filter = self.combo_graded_grade.currentData()
        track_filter = self.combo_graded_track.currentData()
        name_filter = self.combo_graded_name.currentData()

        query = """
            SELECT 
                r.race_id,
                r.year,
                r.week,
                r.name AS race_name,
                r.grade,
                r.track_id,
                r.distance,
                r.surface,
                res.finish_time,
                h.horse_id,
                h.name AS winner_name,
                j.name AS jockey_name
            FROM results res
            JOIN races r ON res.race_id = r.race_id
            JOIN horses h ON res.horse_id = h.horse_id
            LEFT JOIN jockeys j ON res.jockey_id = j.jockey_id
            WHERE res.finish_position = 1 AND r.grade IN ('G1', 'G2', 'G3')
        """
        params = []
        if year_filter is not None:
            query += " AND r.year = ?"
            params.append(year_filter)
        if grade_filter is not None:
            query += " AND r.grade = ?"
            params.append(grade_filter)
        if track_filter is not None:
            query += " AND r.track_id = ?"
            params.append(track_filter)
        if name_filter is not None:
            query += " AND r.name = ?"
            params.append(name_filter)

        query += " ORDER BY r.year ASC, r.week ASC, r.race_id ASC LIMIT 500"

        with self.db.session() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()

        self.table_graded.setRowCount(len(rows))

        for idx, r in enumerate(rows):
            year_str = f"{r['year']}年"
            w_str = f"{r['week']}週"
            r_name = clean_race_name(r["race_name"])
            grade = r["grade"]
            track = r["track_id"]
            dist_str = f"{r['distance']}m"
            surf_str = "芝" if r["surface"] == "turf" else "ダート"
            winner = r["winner_name"] or "-"
            f_time = format_finish_time(r["finish_time"])
            jk_name = r["jockey_name"] or "-"

            bg_col, fg_col = GRADE_COLOR_MAP.get(grade, ("#334155", "#ffffff"))
            grade_item = QTableWidgetItem(grade)
            grade_item.setBackground(QColor(bg_col))
            grade_item.setForeground(QColor(fg_col))

            items = [
                QTableWidgetItem(year_str),
                QTableWidgetItem(w_str),
                QTableWidgetItem(r_name),
                grade_item,
                QTableWidgetItem(track),
                QTableWidgetItem(dist_str),
                QTableWidgetItem(surf_str),
                QTableWidgetItem(winner),
                QTableWidgetItem(f_time),
                QTableWidgetItem(jk_name),
            ]
            for c_idx, item in enumerate(items):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if c_idx == 7:
                    item.setForeground(QColor("#facc15"))
                self.table_graded.setItem(idx, c_idx, item)

            race_id = r["race_id"]
            btn_res = QPushButton("🏁 結果")
            btn_res.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 11px; font-weight: bold; padding: 2px 4px; border: 1px solid #0284c7; border-radius: 3px;")
            btn_res.clicked.connect(lambda checked, rid=race_id: self._open_race_result(rid))
            self.table_graded.setCellWidget(idx, 10, btn_res)

            btn_replay = QPushButton("🎬 動画")
            btn_replay.setStyleSheet("background-color: #1e293b; color: #c084fc; font-size: 11px; font-weight: bold; padding: 2px 4px; border: 1px solid #9333ea; border-radius: 3px;")
            btn_replay.clicked.connect(lambda checked, rid=race_id: self._open_race_replay(rid))
            self.table_graded.setCellWidget(idx, 11, btn_replay)

    def _open_horse_detail(self, horse_id: int) -> None:
        dlg = HorseDetailDialog(self.db, horse_id, parent=self)
        dlg.exec()

    def _open_race_result(self, race_id: int) -> None:
        dlg = RaceResultDialog(self.db, race_id, parent=self)
        dlg.exec()

    def _open_race_replay(self, race_id: int) -> None:
        dlg = RaceViewDialog(self.db, race_id, parent=self)
        dlg.exec()
