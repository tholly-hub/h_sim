"""
繁殖牝馬カルテ・詳細情報ダイアログ (DamDetailDialog)
- 基本情報（繁殖牝馬名、サイヤーライン、父・母、適応距離、獲得賞金、主な戦績、繋養開始年など）
- タブ1: 5代血統表 (PedigreeWidget)
- タブ2: 産駒一覧 (産駒名、性別、戦績、重賞成績、主な勝ち鞍、獲得賞金、詳細ボタン)
- タブ3: 繁殖牝馬の能力グラフ (レーダーチャート & バーグラフ)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog,
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

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

# 日本語フォント設定
plt.rcParams["font.sans-serif"] = ["Hiragino Sans", "Hiragino Kaku Gothic ProN", "Yu Gothic", "Meiryo", "DejaVu Sans", "sans-serif"]
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.unicode_minus"] = False

from src.db.database import Database
from src.gui.styles import get_generation_color
from src.gui.views.horse_detail_dialog import HorseDetailDialog, GRADE_COLOR_MAP, HTMLDelegate
from src.gui.views.race_dialogs import RaceResultDialog
from src.gui.views.records_view import format_finish_time
from src.gui.widgets.pedigree_widget import PedigreeWidget
from src.models.horse import Horse
from src.race.engine import clean_race_name
from src.views.pedigree_builder import PedigreeBuilder


class DamDetailDialog(QDialog):
    """繁殖牝馬カルテ・詳細情報ダイアログ"""

    def __init__(
        self,
        db: Database,
        dam_horse_id: int,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.db = db
        self.dam_horse_id = dam_horse_id
        self.pedigree_builder = PedigreeBuilder(db)

        self.setWindowTitle("🌸 繁殖牝馬カルテ・詳細情報")
        self.resize(1000, 720)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
            }
            QLabel {
                color: #f8fafc;
            }
            QTableWidget {
                background-color: #1e293b;
                alternate-background-color: #111827;
                color: #f8fafc;
                gridline-color: #334155;
                border: 1px solid #334155;
                border-radius: 6px;
                selection-background-color: #db2777;
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #0f172a;
                color: #94a3b8;
                padding: 6px;
                border: 1px solid #334155;
                font-weight: bold;
            }
            QTabWidget::pane {
                border: 1px solid #334155;
                background-color: #0f172a;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #1e293b;
                color: #94a3b8;
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #db2777;
                color: #ffffff;
            }
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)

        self._init_ui()
        self._load_data()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. ヘッダーカード: 基本情報
        self.profile_card = QFrame()
        self.profile_card.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
            }
        """)
        card_layout = QVBoxLayout(self.profile_card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(6)

        # 繁殖牝馬名（大見出し）
        self.lbl_name = QLabel("-")
        self.lbl_name.setStyleSheet("font-size: 20px; font-weight: bold; color: #f472b6;")
        card_layout.addWidget(self.lbl_name)

        # 基本諸元グリッド
        grid_info = QGridLayout()
        grid_info.setHorizontalSpacing(24)
        grid_info.setVerticalSpacing(4)

        self.lbl_sire_line = QLabel("系統: -")
        self.lbl_parents = QLabel("血統: 父 - / 母 -")
        self.lbl_distance = QLabel("適性距離: -")
        self.lbl_earnings = QLabel("獲得賞金: -")
        self.lbl_start_year = QLabel("繋養開始: -")
        self.lbl_major_wins = QLabel("主な戦績: -")

        for lbl in (
            self.lbl_sire_line, self.lbl_parents, self.lbl_distance,
            self.lbl_earnings, self.lbl_start_year, self.lbl_major_wins
        ):
            lbl.setStyleSheet("font-size: 13px; color: #cbd5e1;")

        grid_info.addWidget(self.lbl_sire_line, 0, 0)
        grid_info.addWidget(self.lbl_parents, 0, 1)
        grid_info.addWidget(self.lbl_distance, 0, 2)
        grid_info.addWidget(self.lbl_earnings, 1, 0)
        grid_info.addWidget(self.lbl_start_year, 1, 1)
        grid_info.addWidget(self.lbl_major_wins, 1, 2)

        card_layout.addLayout(grid_info)
        main_layout.addWidget(self.profile_card)

        # 2. タブウィジェット
        self.tabs = QTabWidget()

        # タブ1: 5代血統表
        self.pedigree_tab = QWidget()
        ped_layout = QVBoxLayout(self.pedigree_tab)
        self.pedigree_widget = PedigreeWidget()
        self.pedigree_widget.horse_selected.connect(self._on_ancestor_clicked)
        ped_layout.addWidget(self.pedigree_widget)
        self.tabs.addTab(self.pedigree_tab, "🌳 5代血統表")

        # タブ2: 産駒一覧
        self.progeny_tab = QWidget()
        prog_layout = QVBoxLayout(self.progeny_tab)
        self.table_progeny = QTableWidget()
        self.table_progeny.setColumnCount(9)
        self.table_progeny.setHorizontalHeaderLabels([
            "産駒名", "父馬", "性齢", "状態", "戦績 (1-2-3-外)", "重賞成績 (G1-G2-G3)", "主な勝ち鞍", "獲得賞金", "詳細"
        ])
        prog_header = self.table_progeny.horizontalHeader()
        prog_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_progeny.setColumnWidth(0, 150)
        self.table_progeny.setColumnWidth(1, 130)
        self.table_progeny.setColumnWidth(2, 55)
        self.table_progeny.setColumnWidth(3, 60)
        self.table_progeny.setColumnWidth(4, 110)
        self.table_progeny.setColumnWidth(5, 130)
        prog_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table_progeny.setColumnWidth(7, 100)
        self.table_progeny.setColumnWidth(8, 65)

        self.table_progeny.setAlternatingRowColors(True)
        self.table_progeny.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_progeny.cellDoubleClicked.connect(self._on_progeny_row_double_clicked)
        prog_layout.addWidget(self.table_progeny)
        self.tabs.addTab(self.progeny_tab, "🐎 産駒一覧")

        # タブ3: 競走成績
        self.history_tab = QWidget()
        hist_layout = QVBoxLayout(self.history_tab)
        self.table_history = QTableWidget()
        self.table_history.setColumnCount(13)
        self.table_history.setHorizontalHeaderLabels([
            "日付", "競馬場", "レース名", "グレード", "馬場", "距離",
            "頭数", "人気", "着順", "タイム", "上り3F", "賞金", "結果"
        ])
        h_header = self.table_history.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_history.setColumnWidth(0, 85)
        self.table_history.setColumnWidth(1, 70)
        h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_history.setColumnWidth(3, 60)
        self.table_history.setColumnWidth(4, 45)
        self.table_history.setColumnWidth(5, 60)
        self.table_history.setColumnWidth(6, 45)
        self.table_history.setColumnWidth(7, 45)
        self.table_history.setColumnWidth(8, 45)
        self.table_history.setColumnWidth(9, 80)
        self.table_history.setColumnWidth(10, 55)
        self.table_history.setColumnWidth(11, 75)
        self.table_history.setColumnWidth(12, 60)
        self.table_history.setItemDelegateForColumn(9, HTMLDelegate(self.table_history))
        h_header.setStretchLastSection(False)

        self.table_history.setAlternatingRowColors(True)
        self.table_history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        hist_layout.addWidget(self.table_history)
        self.tabs.addTab(self.history_tab, "📋 競走成績")

        # タブ4: 能力グラフ
        self.ability_tab = QWidget()
        ab_layout = QHBoxLayout(self.ability_tab)
        self.fig_ability = Figure(figsize=(7, 4), facecolor="#1e293b")
        self.canvas_ability = FigureCanvas(self.fig_ability)
        ab_layout.addWidget(self.canvas_ability)
        self.tabs.addTab(self.ability_tab, "📊 能力グラフ")

        main_layout.addWidget(self.tabs)

        # 3. フッター (閉じるボタン)
        footer = QHBoxLayout()
        footer.addStretch()
        btn_close = QPushButton("閉じる")
        btn_close.clicked.connect(self.accept)
        footer.addWidget(btn_close)
        main_layout.addLayout(footer)

    def _load_data(self) -> None:
        """繁殖牝馬および産駒データをロード"""
        with self.db.session() as conn:
            # 1. 繁殖牝馬 & 馬情報
            dam_row = conn.execute("""
                SELECT d.dam_id, d.horse_id, d.start_year,
                       h.name, h.sex, h.age, h.birth_year, h.retired_year, h.prize_money, h.major_wins,
                       h.speed, h.stamina, h.acceleration, h.temperament, h.durability, h.maternal_vitality,
                       h.mstn_type, h.career_starts, h.career_wins, h.g1_wins, h.g2_wins, h.g3_wins,
                       h.sire_id as f_id, h.dam_id as m_id,
                       (SELECT name FROM horses WHERE horse_id = h.sire_id) as sire_name,
                       (SELECT name FROM horses WHERE horse_id = h.dam_id) as dam_name,
                       (SELECT sire_line FROM sires WHERE horse_id = h.sire_id) as sire_line
                FROM dams d
                JOIN horses h ON d.horse_id = h.horse_id
                WHERE d.horse_id = ?
            """, (self.dam_horse_id,)).fetchone()

            if not dam_row:
                h_row = conn.execute("SELECT * FROM horses WHERE horse_id = ?", (self.dam_horse_id,)).fetchone()
                if not h_row:
                    return
                d_dict = dict(h_row)
                d_dict["start_year"] = 1
                d_dict["sire_name"] = "-"
                d_dict["dam_name"] = "-"
                d_dict["sire_line"] = "不明"
                dam_data = d_dict
            else:
                dam_data = dict(dam_row)

            # 現在年度
            max_y_row = conn.execute("SELECT MAX(year) as max_year FROM races").fetchone()
            cur_year = (max_y_row["max_year"] or 1) if max_y_row else 1

            # 2. 産駒一覧（1-2-3-着外の集計を含む）
            progeny_rows = conn.execute("""
                SELECT ph.horse_id, ph.name, ph.sex, ph.age, ph.is_active, ph.prize_money, ph.major_wins,
                       ph.career_starts, ph.career_wins, ph.g1_wins, ph.g2_wins, ph.g3_wins, ph.birth_year, ph.generation,
                       (SELECT name FROM horses WHERE horse_id = ph.sire_id) as sire_name,
                       COALESCE(SUM(CASE WHEN res.finish_position = 1 THEN 1 ELSE 0 END), 0) as pos1,
                       COALESCE(SUM(CASE WHEN res.finish_position = 2 THEN 1 ELSE 0 END), 0) as pos2,
                       COALESCE(SUM(CASE WHEN res.finish_position = 3 THEN 1 ELSE 0 END), 0) as pos3,
                       COALESCE(SUM(CASE WHEN res.finish_position > 3 THEN 1 ELSE 0 END), 0) as pos_out
                FROM horses ph
                LEFT JOIN results res ON ph.horse_id = res.horse_id
                WHERE ph.dam_id = ?
                GROUP BY ph.horse_id
                ORDER BY ph.prize_money DESC, ph.career_wins DESC, ph.horse_id ASC
            """, (self.dam_horse_id,)).fetchall()

            prog_total_prize = sum(pr["prize_money"] or 0 for pr in progeny_rows)

            # 3. G1勝利レースのみを抽出するヘルパー
            def get_g1_wins_str(h_id: int, orig_maj: Optional[str], g1_cnt: int) -> str:
                rows = conn.execute("""
                    SELECT rc.name FROM results res
                    JOIN races rc ON res.race_id = rc.race_id
                    WHERE res.horse_id = ? AND res.finish_position = 1 AND rc.grade = 'G1'
                    ORDER BY rc.year ASC, rc.week ASC
                """, (h_id,)).fetchall()
                if rows:
                    return "、".join(r["name"] for r in rows)
                if (g1_cnt or 0) > 0 and orig_maj:
                    return orig_maj
                return "-"

            # --- ヘッダー設定 ---
            d_name = dam_data["name"]
            self.lbl_name.setText(f"🌸 {d_name}（繁殖牝馬）")
            self.lbl_sire_line.setText(f"系統: {dam_data.get('sire_line') or '不明'}")
            
            f_name = dam_data.get("sire_name") or "不明"
            m_name = dam_data.get("dam_name") or "不明"
            self.lbl_parents.setText(f"血統: 父 {f_name} / 母 {m_name}")

            # 適性距離計算 (Horseモデルから)
            try:
                horse_obj = Horse.from_row(dam_data)
                d_min = horse_obj.apt_distance_min
                d_max = horse_obj.apt_distance_max
                surf = "芝" if horse_obj.surface_aptitude == "turf" else ("ダート" if horse_obj.surface_aptitude == "dirt" else "芝・ダート兼用")
                self.lbl_distance.setText(f"適応: {surf} {d_min}m〜{d_max}m")
            except Exception:
                self.lbl_distance.setText("適応: 不明")

            own_prz = (dam_data.get("prize_money") or 0) // 10000
            prog_prz = prog_total_prize // 10000
            self.lbl_earnings.setText(f"獲得賞金: 自身 {own_prz:,}万 / 産駒 {prog_prz:,}万 (産駒 {len(progeny_rows)}頭)")
            
            st_yr = dam_data.get("start_year", 1)
            self.lbl_start_year.setText(f"繋養開始: {st_yr}年目 (現在 {max(1, cur_year - st_yr + 1)}年目)")
            
            # 主な戦績（G1レースのみに限定）
            maj_wins = get_g1_wins_str(self.dam_horse_id, dam_data.get("major_wins"), dam_data.get("g1_wins", 0))
            self.lbl_major_wins.setText(f"主な戦績(G1): {maj_wins}")

            # --- タブ1: 5代血統表 ---
            tree = self.pedigree_builder.get_ancestors_tree(self.dam_horse_id, depth=5, conn=conn)
            self.pedigree_widget.set_tree_data(tree)

            # --- タブ2: 産駒一覧 ---
            sex_map = {"colt": "牡", "filly": "牝", "horse": "牡", "mare": "牝", "gelding": "セ"}
            self.table_progeny.setRowCount(len(progeny_rows))
            
            for idx, pr in enumerate(progeny_rows):
                p_dict = dict(pr)
                p_name = p_dict["name"]
                s_name = p_dict["sire_name"] or "-"
                sa = f"{sex_map.get(p_dict['sex'], '')}{p_dict['age']}"
                c_starts = p_dict["career_starts"] or 0
                c_wins = p_dict["career_wins"] or 0

                # 状態の適正判定 (0歳: 当歳, 1歳: 1歳幼駒, 2歳以上: 未出走/現役/種牡馬/繁殖牝馬/引退)
                if p_dict["age"] == 0:
                    st = "当歳"
                elif p_dict["age"] == 1:
                    st = "1歳幼駒"
                elif p_dict.get("is_sire"):
                    st = "種牡馬"
                elif p_dict.get("is_dam"):
                    st = "繁殖牝馬"
                elif p_dict["is_active"]:
                    st = "未出走" if c_starts == 0 else "現役"
                else:
                    st = "引退"
                
                # 通算成績: 1-2-3-着外
                p1 = p_dict["pos1"]
                p2 = p_dict["pos2"]
                p3 = p_dict["pos3"]
                p_out = p_dict["pos_out"]
                rec_str = f"{p1}-{p2}-{p3}-{p_out}"
                
                # 重賞成績: G1-G2-G3
                g1 = p_dict["g1_wins"] or 0
                g2 = p_dict["g2_wins"] or 0
                g3 = p_dict["g3_wins"] or 0
                g_str = f"{g1}-{g2}-{g3}"

                # 主な勝ち鞍: G1限定
                maj = get_g1_wins_str(p_dict["horse_id"], p_dict["major_wins"], g1)
                prz = f"{(p_dict['prize_money'] // 10000):,}万円"

                gen = p_dict.get("generation", 1) or 1
                name_col = get_generation_color(gen)

                name_item = QTableWidgetItem(p_name)
                name_item.setData(Qt.ItemDataRole.UserRole, p_dict["horse_id"])
                name_item.setForeground(QColor(name_col))
                f = name_item.font()
                f.setBold(True)
                name_item.setFont(f)

                items = [
                    name_item,
                    QTableWidgetItem(s_name),
                    QTableWidgetItem(sa),
                    QTableWidgetItem(st),
                    QTableWidgetItem(rec_str),
                    QTableWidgetItem(g_str),
                    QTableWidgetItem(maj),
                    QTableWidgetItem(prz),
                ]

                for c_idx, item in enumerate(items):
                    if c_idx not in (0, 1, 6):
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    else:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                    self.table_progeny.setItem(idx, c_idx, item)

                hid = p_dict["horse_id"]
                btn_det = QPushButton("詳細")
                btn_det.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 11px; padding: 2px 6px; border: 1px solid #0284c7; border-radius: 3px;")
                btn_det.clicked.connect(lambda checked, h_id=hid: self._open_horse_detail(h_id))
                self.table_progeny.setCellWidget(idx, 8, btn_det)

            # --- タブ3: 競走成績 ---
            select_cols = """
                r.race_id, r.year, r.week, r.track_id, r.name AS race_name, r.grade, r.surface, r.distance, r.full_gate,
                res.finish_position, res.finish_time, res.last_3f, res.prize_awarded, res.odds,
                (
                    SELECT COUNT(*) + 1
                    FROM results res_pop
                    WHERE res_pop.race_id = res.race_id 
                      AND (res_pop.odds < res.odds OR (res_pop.odds = res.odds AND res_pop.gate_number < res.gate_number))
                ) AS popularity,
                (
                    SELECT MIN(res_prev.finish_time)
                    FROM results res_prev
                    JOIN races r_prev ON res_prev.race_id = r_prev.race_id
                    WHERE r_prev.track_id = r.track_id 
                      AND r_prev.surface = r.surface 
                      AND r_prev.distance = r.distance
                      AND res_prev.finish_position = 1
                      AND res_prev.finish_time > 0
                      AND (
                          r_prev.year < r.year
                          OR (r_prev.year = r.year AND r_prev.week < r.week)
                          OR (r_prev.year = r.year AND r_prev.week = r.week AND r_prev.race_id < r.race_id)
                      )
                ) AS past_record_time
            """
            race_results = conn.execute(
                f"""
                SELECT {select_cols}
                FROM results res
                JOIN races r ON res.race_id = r.race_id
                WHERE res.horse_id = ?
                ORDER BY r.year DESC, r.week DESC, r.race_id DESC
                """,
                (self.dam_horse_id,),
            ).fetchall()

        self.table_history.setRowCount(len(race_results))
        for idx, r in enumerate(race_results):
            m_num = ((r['week'] - 1) // 4) + 1
            w_in_m = ((r['week'] - 1) % 4) + 1
            y_w = f"{r['year']}年{m_num}月{w_in_m}週"
            track = r["track_id"]
            r_name = clean_race_name(r["race_name"])
            grade = r["grade"]
            surf = "芝" if r["surface"] == "turf" else "ダート"
            dist = f"{r['distance']}m"
            starters = f"{r['full_gate']}頭"
            pop_str = f"{r['popularity']}人" if r["popularity"] else "-"
            pos = f"{r['finish_position']}着"

            is_rec = False
            if r["finish_position"] == 1 and r["finish_time"] and float(r["finish_time"]) > 0:
                past_rec = r["past_record_time"]
                if past_rec is None or float(r["finish_time"]) < float(past_rec) - 0.001:
                    is_rec = True

            raw_f_time = format_finish_time(r["finish_time"])
            if is_rec:
                f_time_display = f"<span style='color: #ef4444; font-weight: bold;'>R</span> <span style='color: #facc15; font-weight: bold;'>{raw_f_time}</span>"
            elif r["finish_position"] == 1:
                f_time_display = f"<span style='color: #facc15; font-weight: bold;'>{raw_f_time}</span>"
            else:
                f_time_display = raw_f_time

            l_3f = f"{r['last_3f']:.1f}" if r["last_3f"] else "-"
            prz = f"{r['prize_awarded'] // 10000:,}万" if r["prize_awarded"] else "0"

            bg_col, fg_col = GRADE_COLOR_MAP.get(grade, ("#334155", "#ffffff"))
            grade_item = QTableWidgetItem(grade)
            grade_item.setBackground(QColor(bg_col))
            grade_item.setForeground(QColor(fg_col))

            time_item = QTableWidgetItem(f_time_display)

            items = [
                QTableWidgetItem(y_w), QTableWidgetItem(track), QTableWidgetItem(r_name),
                grade_item, QTableWidgetItem(surf), QTableWidgetItem(dist),
                QTableWidgetItem(starters), QTableWidgetItem(pop_str), QTableWidgetItem(pos), time_item,
                QTableWidgetItem(l_3f), QTableWidgetItem(prz)
            ]
            for c, itm in enumerate(items):
                itm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if r["finish_position"] == 1 and c not in (3, 9):
                    itm.setForeground(Qt.GlobalColor.yellow)
                self.table_history.setItem(idx, c, itm)

            r_id = r["race_id"]
            btn_res = QPushButton("🏁 結果")
            btn_res.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 11px; font-weight: bold; padding: 2px 4px; border: 1px solid #0284c7; border-radius: 3px;")
            btn_res.clicked.connect(lambda checked, rid=r_id: self._open_race_result(rid))
            self.table_history.setCellWidget(idx, 12, btn_res)

        # --- タブ4: 能力グラフ ---
        self._plot_abilities(dam_data)

    def _plot_abilities(self, dam_data: Dict[str, Any]) -> None:
        """能力レーダーチャート & バーチャートの描画"""
        self.fig_ability.clear()

        # 2つのサブプロット (左: レーダーチャート, 右: 水平バーグラフ)
        ax_radar = self.fig_ability.add_subplot(121, polar=True)
        ax_radar.set_facecolor("#1e293b")

        categories = ["最高速度", "持久力", "瞬発力", "気性", "耐久力", "母性活力"]
        values = [
            float(dam_data.get("speed", 50.0)),
            float(dam_data.get("stamina", 50.0)),
            float(dam_data.get("acceleration", 50.0)),
            float(dam_data.get("temperament", 50.0)),
            float(dam_data.get("durability", 50.0)),
            float(dam_data.get("maternal_vitality", 50.0)),
        ]

        N = len(categories)
        angles = [n / float(N) * 2 * math.pi for n in range(N)]
        values_closed = values + values[:1]
        angles_closed = angles + angles[:1]

        ax_radar.plot(angles_closed, values_closed, color="#f472b6", linewidth=2, linestyle="solid")
        ax_radar.fill(angles_closed, values_closed, color="#f472b6", alpha=0.35)

        ax_radar.set_xticks(angles)
        ax_radar.set_xticklabels(categories, color="#cbd5e1", fontsize=10, fontweight="bold")
        ax_radar.set_ylim(0, 100)
        ax_radar.tick_params(colors="#94a3b8", labelsize=8)
        ax_radar.grid(color="#475569", linestyle="--", alpha=0.6)

        # 右側: バーチャート
        ax_bar = self.fig_ability.add_subplot(122)
        ax_bar.set_facecolor("#1e293b")

        y_pos = np.arange(len(categories))
        colors = ["#f87171", "#fbbf24", "#34d399", "#60a5fa", "#a78bfa", "#f472b6"]

        bars = ax_bar.barh(y_pos, values, color=colors, height=0.55, edgecolor="#ffffff", linewidth=0.5)
        ax_bar.set_yticks(y_pos)
        ax_bar.set_yticklabels(categories, color="#cbd5e1", fontsize=10, fontweight="bold")
        ax_bar.invert_yaxis()
        ax_bar.set_xlim(0, 110)
        ax_bar.set_xlabel("能力値 (0〜100)", color="#94a3b8", fontsize=10)
        ax_bar.tick_params(colors="#94a3b8")
        ax_bar.grid(axis="x", color="#475569", linestyle="--", alpha=0.5)

        for bar in bars:
            w = bar.get_width()
            ax_bar.text(w + 2, bar.get_y() + bar.get_height() / 2, f"{w:.1f}", va="center", color="#f8fafc", fontweight="bold", fontsize=9)

        self.fig_ability.tight_layout()
        self.canvas_ability.draw()

    def _open_race_result(self, race_id: int) -> None:
        """レース結果ダイアログを開く"""
        if race_id:
            dlg = RaceResultDialog(self.db, race_id, parent=self)
            dlg.exec()

    def _open_horse_detail(self, horse_id: int) -> None:
        """競走馬詳細カルテを開く"""
        dialog = HorseDetailDialog(self.db, horse_id, self)
        dialog.exec()

    def _on_progeny_row_double_clicked(self, row: int, col: int) -> None:
        """産駒一覧行ダブルクリック"""
        item = self.table_progeny.item(row, 0)
        if item:
            hid = item.data(Qt.ItemDataRole.UserRole)
            if hid:
                self._open_horse_detail(hid)

    def _on_ancestor_clicked(self, horse_id: int) -> None:
        """祖先馬クリック"""
        self._open_horse_detail(horse_id)
