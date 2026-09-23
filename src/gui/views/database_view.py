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

from __future__ import annotations

from typing import Any, Dict, List, Optional
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
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.db.database import Database, get_db
from src.gui.views.horse_detail_dialog import HorseDetailDialog, GRADE_COLOR_MAP
from src.gui.views.progeny_dialog import ProgenyListDialog
from src.gui.views.race_dialogs import RaceResultDialog, RaceViewDialog
from src.gui.views.records_view import RecordsView, format_finish_time
from src.race.engine import clean_race_name


MAJOR_ROUTES = [
    {
        "id": "classic_colt",
        "name": "👑 3歳牡馬3冠",
        "races": ["皐月賞", "東京優駿", "菊花賞"],
        "labels": ["第1冠: 皐月賞", "第2冠: 日本ダービー", "第3冠: 菊花賞"],
    },
    {
        "id": "triple_tiara",
        "name": "🌸 3歳牝馬3冠 (トリプルティアラ)",
        "races": ["桜花賞", "優駿牝馬", "秋華賞"],
        "labels": ["第1冠: 桜花賞", "第2冠: オークス", "第3冠: 秋華賞"],
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
        "races": ["高松宮記念", "スプリンターズステークス"],
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
        "id": "grand_prix",
        "name": "⭐ グランプリ2冠 (春・冬)",
        "races": ["宝塚記念", "有馬記念"],
        "labels": ["春: 宝塚記念", "冬: 有馬記念"],
    },
    {
        "id": "dirt_older",
        "name": "🏜 ダート王道路線",
        "races": ["フェブラリーステークス", "チャンピオンズカップ", "東京大賞典"],
        "labels": ["春: フェブラリーS", "秋: チャンピオンズC", "冬: 東京大賞典"],
    },
]


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

        # 初回データ読み込み
        self.refresh_all()

    def refresh_all(self) -> None:
        """全サブタブのデータを最新化"""
        self._refresh_leading_filters()
        self.refresh_leading()
        self._refresh_cohort_filters()
        self.refresh_cohort_class()
        self.refresh_major_routes()
        self.refresh_sires_list()
        self.refresh_broodmares_list()
        self._refresh_graded_years()
        self.refresh_graded()
        if hasattr(self.tab_records, "refresh_records"):
            self.tab_records.refresh_records()

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

        f_layout.addWidget(QLabel("年齢区分:"))
        self.combo_lead_age = QComboBox()
        self.combo_lead_age.addItem("全年齢 (総合)", None)
        self.combo_lead_age.addItem("2歳馬", 2)
        self.combo_lead_age.addItem("3歳馬", 3)
        self.combo_lead_age.addItem("古馬 (4歳以上)", "older")
        self.combo_lead_age.currentIndexChanged.connect(self.refresh_leading)
        f_layout.addWidget(self.combo_lead_age)

        f_layout.addWidget(QLabel("性別区分:"))
        self.combo_lead_sex = QComboBox()
        self.combo_lead_sex.addItem("全性別 (総合)", None)
        self.combo_lead_sex.addItem("牡馬・セン馬", "male")
        self.combo_lead_sex.addItem("牝馬のみ", "female")
        self.combo_lead_sex.currentIndexChanged.connect(self.refresh_leading)
        f_layout.addWidget(self.combo_lead_sex)

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
        age_filter = self.combo_lead_age.currentData()
        sex_filter = self.combo_lead_sex.currentData()

        if period == "career" or period is None:
            query = """
                SELECT 
                    h.horse_id,
                    h.name AS horse_name,
                    h.sex,
                    h.age,
                    h.career_starts AS total_starts,
                    h.career_wins AS total_wins,
                    (h.g1_wins + h.g2_wins + h.g3_wins) AS graded_wins,
                    h.prize_money AS total_prize,
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
            if age_filter == 2:
                query += " AND h.age = 2"
            elif age_filter == 3:
                query += " AND h.age = 3"
            elif age_filter == "older":
                query += " AND h.age >= 4"

            if sex_filter == "male":
                query += " AND h.sex IN ('colt', 'horse', 'gelding')"
            elif sex_filter == "female":
                query += " AND h.sex IN ('filly', 'mare')"

            query += " ORDER BY h.prize_money DESC, h.career_wins DESC LIMIT 100"
        else:
            year = int(period)
            query = """
                SELECT 
                    h.horse_id,
                    h.name AS horse_name,
                    h.sex,
                    h.age,
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
            if age_filter == 2:
                query += " AND h.age = 2"
            elif age_filter == 3:
                query += " AND h.age = 3"
            elif age_filter == "older":
                query += " AND h.age >= 4"

            if sex_filter == "male":
                query += " AND h.sex IN ('colt', 'horse', 'gelding')"
            elif sex_filter == "female":
                query += " AND h.sex IN ('filly', 'mare')"

            query += " GROUP BY h.horse_id ORDER BY total_prize DESC, total_wins DESC LIMIT 100"

        with self.db.session() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()

        self.table_leading.setRowCount(len(rows))
        sex_map = {"colt": "牡", "filly": "牝", "horse": "牡", "mare": "牝", "gelding": "セ"}

        for idx, r in enumerate(rows):
            rank_str = f"{idx + 1}"
            h_name = r["horse_name"]
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
                    item.setForeground(QColor("#38bdf8"))
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
            sex_age = f"{sex_map.get(r['sex'], '')}{r['age']}"
            cls_str = r["cls_label"]
            s_name = r["sire_name"] or "-"
            d_name = r["dam_name"] or "-"
            tr_name = r["trainer_name"] or "未定"
            rec_str = f"{r['career_starts']}戦{r['career_wins']}勝"
            prz_str = f"{(r['prize_money'] or 0) // 10000:,} 万円"
            major_str = r["major_wins"] or "-"

            cls_item = QTableWidgetItem(cls_str)
            cls_item.setForeground(QColor(r["cls_col"]))
            f = cls_item.font()
            f.setBold(True)
            cls_item.setFont(f)

            items = [
                QTableWidgetItem(rank_str),
                QTableWidgetItem(h_name),
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

            # 各年度・各レースの勝ち馬を取得
            race_winners: Dict[int, Dict[str, Dict[str, Any]]] = {}
            for y in all_years:
                race_winners[y] = {}

            placeholders = ",".join(["?"] * len(r_names))
            w_rows = conn.execute(f"""
                SELECT rc.year, rc.name as race_name, h.horse_id, h.name as horse_name
                FROM results res
                JOIN races rc ON res.race_id = rc.race_id
                JOIN horses h ON res.horse_id = h.horse_id
                WHERE res.finish_position = 1 AND rc.name IN ({placeholders})
                ORDER BY rc.year ASC
            """, tuple(r_names)).fetchall()

            for r in w_rows:
                y = r["year"]
                if y in race_winners:
                    race_winners[y][r["race_name"]] = {
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
    # 4. 種牡馬リストタブ (新設)
    # ==========================================
    def _create_sires_list_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        filter_bar = QFrame()
        filter_bar.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 6px;")
        f_layout = QHBoxLayout(filter_bar)
        f_layout.setContentsMargins(10, 6, 10, 6)
        f_layout.setSpacing(12)

        f_layout.addWidget(QLabel("状態:"))
        self.combo_sire_status = QComboBox()
        self.combo_sire_status.addItem("現役種牡馬のみ", "active")
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
        self.table_sires.setColumnCount(10)
        self.table_sires.setHorizontalHeaderLabels([
            "種牡馬名", "年齢", "繋養年数", "系統", "産駒頭数", "勝馬数", "勝ち上がり率", "重賞勝数", "代表産駒", "産駒一覧"
        ])
        header = self.table_sires.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_sires.setColumnWidth(0, 170)
        self.table_sires.setColumnWidth(1, 55)
        self.table_sires.setColumnWidth(2, 75)
        self.table_sires.setColumnWidth(3, 110)
        self.table_sires.setColumnWidth(4, 70)
        self.table_sires.setColumnWidth(5, 70)
        self.table_sires.setColumnWidth(6, 90)
        self.table_sires.setColumnWidth(7, 70)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        self.table_sires.setColumnWidth(9, 85)

        self.table_sires.setAlternatingRowColors(True)
        self.table_sires.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table_sires)

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
                SELECT s.sire_id, s.horse_id, s.sire_line, s.is_active, s.is_foreign, s.is_new,
                       sh.name as name, sh.age as age, sh.birth_year, sh.retired_year,
                       COUNT(DISTINCT ph.horse_id) as progeny_count,
                       SUM(CASE WHEN (ph.career_wins > 0) THEN 1 ELSE 0 END) as winners_count,
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
                w_cnt = p_dict["winners_count"] or 0
                p_dict["win_rate_val"] = (w_cnt / p_cnt) if p_cnt > 0 else 0.0
                p_dict["graded_wins"] = p_dict["graded_wins"] or 0

                # 繋養年数計算 (debut_year または retired_year または age - 4)
                ret_year = p_dict.get("retired_year")
                if ret_year and ret_year > 0:
                    years_in_service = max(1, cur_year - ret_year + 1)
                else:
                    # 初期種牡馬: 年齢等から算出
                    years_in_service = max(1, cur_year)
                p_dict["years_in_service"] = years_in_service
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

        self.table_sires.setRowCount(len(processed_rows))

        for idx, r in enumerate(processed_rows):
            s_name = r["name"]
            if r["is_foreign"]:
                s_name_display = f"{s_name} [外]"
                name_col = "#ef4444"
            elif r["is_new"]:
                s_name_display = f"{s_name} [新]"
                name_col = "#22c55e"
            else:
                s_name_display = s_name
                name_col = "#f8fafc"

            age_str = f"{r['age']}歳" if r["age"] else "-"
            years_str = f"{r['years_in_service']}年目"
            lineage = r["sire_line"] or "-"
            p_cnt = r["progeny_count"] or 0
            w_cnt = r["winners_count"] or 0
            win_rate = f"{(r['win_rate_val'] * 100):.1f}%" if p_cnt > 0 else "0.0%"
            g_wins = r["graded_wins"] or 0

            # 代表産駒
            top_prog_name = "-"
            with self.db.session() as conn:
                top_prog = conn.execute("""
                    SELECT name, prize_money FROM horses
                    WHERE sire_id = ? ORDER BY prize_money DESC LIMIT 1
                """, (r["horse_id"],)).fetchone()
                if top_prog and top_prog["prize_money"] > 0:
                    top_prog_name = f"{top_prog['name']} ({(top_prog['prize_money'] // 10000):,}万円)"

            name_item = QTableWidgetItem(s_name_display)
            name_item.setForeground(QColor(name_col))
            f = name_item.font()
            f.setBold(True)
            name_item.setFont(f)

            items = [
                name_item,
                QTableWidgetItem(age_str),
                QTableWidgetItem(years_str),
                QTableWidgetItem(lineage),
                QTableWidgetItem(str(p_cnt)),
                QTableWidgetItem(str(w_cnt)),
                QTableWidgetItem(win_rate),
                QTableWidgetItem(str(g_wins)),
                QTableWidgetItem(top_prog_name),
            ]

            for c_idx, item in enumerate(items):
                if c_idx not in (0, 8):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_sires.setItem(idx, c_idx, item)

            hid = r["horse_id"]
            btn_prog = QPushButton("産駒一覧")
            btn_prog.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 11px; padding: 2px 6px; border: 1px solid #0284c7; border-radius: 3px;")
            btn_prog.clicked.connect(lambda checked, h_id=hid: self._open_progeny_dialog(h_id, is_sire=True))
            self.table_sires.setCellWidget(idx, 9, btn_prog)

    # ==========================================
    # 5. 繁殖牝馬リストタブ (新設)
    # ==========================================
    def _create_broodmares_list_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        filter_bar = QFrame()
        filter_bar.setStyleSheet("background-color: #161b26; border: 1px solid #242c3d; border-radius: 6px;")
        f_layout = QHBoxLayout(filter_bar)
        f_layout.setContentsMargins(10, 6, 10, 6)
        f_layout.setSpacing(12)

        f_layout.addWidget(QLabel("状態:"))
        self.combo_dam_status = QComboBox()
        self.combo_dam_status.addItem("現役繁殖牝馬のみ (600頭)", "active")
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
        self.table_dams.setColumnCount(9)
        self.table_dams.setHorizontalHeaderLabels([
            "繁殖牝馬名", "年齢", "繋養年数", "父馬 (サイヤー)", "産駒頭数", "勝馬数", "勝ち上がり率", "代表産駒", "産駒一覧"
        ])
        header = self.table_dams.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_dams.setColumnWidth(0, 170)
        self.table_dams.setColumnWidth(1, 55)
        self.table_dams.setColumnWidth(2, 75)
        self.table_dams.setColumnWidth(3, 130)
        self.table_dams.setColumnWidth(4, 70)
        self.table_dams.setColumnWidth(5, 70)
        self.table_dams.setColumnWidth(6, 90)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.table_dams.setColumnWidth(8, 85)

        self.table_dams.setAlternatingRowColors(True)
        self.table_dams.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
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
                SELECT d.dam_id, d.horse_id, d.is_active,
                       dh.name as name, dh.age as age, dh.birth_year, dh.retired_year,
                       sh.name as sire_name,
                       COUNT(DISTINCT ph.horse_id) as progeny_count,
                       SUM(CASE WHEN (ph.career_wins > 0) THEN 1 ELSE 0 END) as winners_count
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

            # 各行の加工と繋養年数の算出
            processed_rows = []
            for r in rows:
                p_dict = dict(r)
                p_cnt = p_dict["progeny_count"] or 0
                w_cnt = p_dict["winners_count"] or 0
                p_dict["win_rate_val"] = (w_cnt / p_cnt) if p_cnt > 0 else 0.0

                # 繋養年数計算 (debut_year または retired_year または 1)
                ret_year = p_dict.get("retired_year")
                if ret_year and ret_year > 0:
                    years_in_service = max(1, cur_year - ret_year + 1)
                else:
                    years_in_service = max(1, cur_year)
                p_dict["years_in_service"] = years_in_service
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
            age_str = f"{r['age']}歳" if r["age"] else "-"
            years_str = f"{r['years_in_service']}年目"
            s_name = r["sire_name"] or "-"
            p_cnt = r["progeny_count"] or 0
            w_cnt = r["winners_count"] or 0
            win_rate = f"{(r['win_rate_val'] * 100):.1f}%" if p_cnt > 0 else "0.0%"

            # 代表産駒
            top_prog_name = "-"
            with self.db.session() as conn:
                top_prog = conn.execute("""
                    SELECT name, prize_money FROM horses
                    WHERE dam_id = ? ORDER BY prize_money DESC LIMIT 1
                """, (r["horse_id"],)).fetchone()
                if top_prog and top_prog["prize_money"] > 0:
                    top_prog_name = f"{top_prog['name']} ({(top_prog['prize_money'] // 10000):,}万円)"

            name_item = QTableWidgetItem(d_name)
            name_item.setForeground(QColor("#f472b6"))

            items = [
                name_item,
                QTableWidgetItem(age_str),
                QTableWidgetItem(years_str),
                QTableWidgetItem(s_name),
                QTableWidgetItem(str(p_cnt)),
                QTableWidgetItem(str(w_cnt)),
                QTableWidgetItem(win_rate),
                QTableWidgetItem(top_prog_name),
            ]

            for c_idx, item in enumerate(items):
                if c_idx not in (0, 7):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_dams.setItem(idx, c_idx, item)

            hid = r["horse_id"]
            btn_prog = QPushButton("産駒一覧")
            btn_prog.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 11px; padding: 2px 6px; border: 1px solid #0284c7; border-radius: 3px;")
            btn_prog.clicked.connect(lambda checked, h_id=hid: self._open_progeny_dialog(h_id, is_sire=False))
            self.table_dams.setCellWidget(idx, 8, btn_prog)

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
