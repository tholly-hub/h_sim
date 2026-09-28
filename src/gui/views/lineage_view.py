"""
系統樹ビュー (LineageView)
- 競馬データベースの後ろに配置される系統樹管理・閲覧画面
- サブタブ:
  1. 🐴 種牡馬（サイヤーライン: [系]）
  2. 🌸 繁殖牝馬（ファミリーナンバー: [族]）※将来拡張用プレースホルダー
- 種牡馬画面の構成:
  - 左右2列表示 (QSplitter)
  - 左列: サイヤーラインメニュー (上下2段: 存続系列 / 断絶系列)
    - 始祖馬から段下げした階層形式で系統名を表示
    - 系統選択で右列に系統樹を表示（子系統クリック時はその馬を起点とした系統樹のみを表示）
  - 右列: 系統樹キャンバス (QScrollArea + カスタムQPainter描画)
    - サイヤーライン名（青色・大フォント）
    - 始祖馬の表記
    - 生まれた子供で種牡馬となった馬を1行ずつ罫線で接続
    - 馬名(生誕年) 通算成績 G1勝利数 適性馬場 適性距離
    - さらに2世代の種牡馬が生まれた時点で新たなサイヤーライン成立（馬の上部に系名を表示）
"""

from __future__ import annotations

import math
import sys
import traceback
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from PyQt6.QtCore import QPoint, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.db.database import Database, get_db
from src.gui.views.dam_detail_dialog import DamDetailDialog
from src.gui.views.horse_detail_dialog import HorseDetailDialog
from src.gui.views.sire_detail_dialog import SireDetailDialog
from src.models.horse import Horse


@dataclass
class SireTreeNode:
    """系統樹の各馬ノード"""
    horse_id: int
    name: str
    birth_year: int
    career_starts: int
    career_wins: int
    g1_wins: int
    surface_str: str          # "芝", "ダート", "芝/ダ"
    dist_min: int
    dist_max: int
    is_active: bool           # 現役種牡馬か
    is_root: bool             # 起点馬（始祖）か
    is_new_line: bool         # 新サイヤーラインか（後継深さ >= 2）
    line_name: str            # 系統名（例: "ユゲプレナイト系"）
    depth_from_root: int      # 選択された起点からの世代深さ
    max_descendant_depth: int # この馬からの後継種牡馬世代深さ
    children: List[SireTreeNode] = field(default_factory=list)

    # レイアウト用座標・サイズ
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    subtree_height: float = 0.0
    header_height: float = 0.0   # 新サイヤーライン名ラベルの高さ
    card_rect: QRectF = field(default_factory=QRectF)


@dataclass
class DamTreeNode:
    """繁殖牝馬系統樹の各馬ノード"""
    horse_id: int
    name: str
    birth_year: int
    career_starts: int
    career_wins: int
    g1_wins: int
    surface_str: str          # "芝", "ダート", "芝/ダ"
    dist_min: int
    dist_max: int
    is_active: bool           # 現役繁殖牝馬か (dams.is_active == 1)
    is_root: bool             # 起点馬（始祖牝馬）か
    family_name: str          # 族名（例: "ハタノユキヤナギ族"）
    depth_from_root: int      # 選択された起点からの世代深さ
    progeny_dams_count: int   # 産駒の繁殖牝馬数
    children: List[DamTreeNode] = field(default_factory=list)

    # レイアウト用座標・サイズ
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    subtree_height: float = 0.0
    card_rect: QRectF = field(default_factory=QRectF)


class SireTreeCanvasWidget(QWidget):
    """
    系統樹描画キャンバスウィジェット
    QPainterによる高精細な樹形図・罫線・新サイヤーラインヘッダーの描画
    """
    node_clicked = pyqtSignal(int)  # horse_id

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.root_node: Optional[SireTreeNode] = None
        self.hovered_node: Optional[SireTreeNode] = None
        self.node_rect_map: List[Tuple[QRectF, SireTreeNode]] = []

        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #0f172a;")

        # フォント設定
        font_family = "Hiragino Sans, Hiragino Kaku Gothic ProN, Yu Gothic, Meiryo, sans-serif"
        self.font_title = QFont(font_family, 15, QFont.Weight.Bold)
        self.font_line_header = QFont(font_family, 12, QFont.Weight.Bold)
        self.font_root_name = QFont(font_family, 12, QFont.Weight.Bold)
        self.font_node_text = QFont(font_family, 11)
        self.font_node_bold = QFont(font_family, 11, QFont.Weight.Bold)
        self.font_badge = QFont(font_family, 9, QFont.Weight.Bold)

    def set_tree_root(self, root_node: Optional[SireTreeNode]) -> None:
        """表示する系統樹のルートノードを設定しレイアウトを再計算"""
        self.root_node = root_node
        self.hovered_node = None
        self._calculate_layout()
        self.update()

    def _calculate_layout(self) -> None:
        """全ノードの座標とキャンバス必要サイズを再帰的に計算"""
        self.node_rect_map.clear()
        if not self.root_node:
            self.resize(800, 600)
            self.setMinimumSize(800, 600)
            return

        try:
            # 1. 各ノードのテキスト幅・高さを計算
            fm_text = QFontMetrics(self.font_node_text)
            fm_bold = QFontMetrics(self.font_node_bold)
            fm_root = QFontMetrics(self.font_root_name)
            fm_badge = QFontMetrics(self.font_badge)
            fm_header = QFontMetrics(self.font_line_header)

            def measure_node(node: SireTreeNode):
                # 左マージン
                total_w = 14.0

                # 1. 馬名部分
                if node.is_root:
                    name_txt = f"{node.name}（始祖）"
                    total_w += fm_root.horizontalAdvance(name_txt) + 14.0
                else:
                    name_txt = f"{node.name}({node.birth_year})"
                    total_w += fm_bold.horizontalAdvance(name_txt) + 14.0

                # 2. 成績
                starts = node.career_starts
                wins = node.career_wins
                if starts > 0 or wins > 0 or not node.is_root:
                    rec_txt = f"{starts}-{wins}"
                    total_w += fm_text.horizontalAdvance(rec_txt) + 12.0

                # 3. G1勝利数
                if node.g1_wins > 0:
                    g1_txt = f"G1:{node.g1_wins}"
                    total_w += fm_bold.horizontalAdvance(g1_txt) + 12.0

                # 4. 適性馬場 & 距離
                surf_txt = node.surface_str
                dist_txt = f"{node.dist_min}-{node.dist_max}m" if node.dist_min > 0 else ""
                apt_txt = f"{surf_txt} {dist_txt}".strip()
                if apt_txt:
                    total_w += fm_text.horizontalAdvance(apt_txt) + 12.0

                # 5. 供用中バッジ
                if node.is_active:
                    badge_txt = "[供用中]"
                    total_w += fm_badge.horizontalAdvance(badge_txt) + 14.0

                # 右パディング追加
                total_w += 16.0

                # 新サイヤーラインラベルがある場合（始祖以外で後継深さ >= 2）
                header_h = 0.0
                if node.is_new_line and not node.is_root:
                    header_h = float(fm_header.height() + 8)
                    line_title_w = fm_header.horizontalAdvance(f"◆ {node.name}系") + 28.0
                    total_w = max(total_w, line_title_w)

                node.width = max(260.0, float(math.ceil(total_w)))
                node.height = 32.0 + header_h
                node.header_height = header_h

                for child in node.children:
                    measure_node(child)

            measure_node(self.root_node)

            # 2. 世代列ごとの最大幅を計算
            col_widths: Dict[int, float] = defaultdict(lambda: 260.0)

            def calc_col_widths(node: SireTreeNode, depth: int):
                col_widths[depth] = max(col_widths[depth], node.width)
                for child in node.children:
                    calc_col_widths(child, depth + 1)

            calc_col_widths(self.root_node, 0)

            # 3. サブツリーの高さをボトムアップで計算
            item_v_margin = 12.0  # ノード間の垂直余白

            def calc_subtree_height(node: SireTreeNode) -> float:
                if not node.children:
                    node.subtree_height = node.height
                    return node.subtree_height

                children_total_h = sum(calc_subtree_height(c) for c in node.children)
                children_total_h += item_v_margin * (len(node.children) - 1)
                node.subtree_height = max(node.height, children_total_h)
                return node.subtree_height

            calc_subtree_height(self.root_node)

            # 4. ノードの (X, Y) 座標をトップダウンで配置
            margin_x = 40.0
            margin_y = 70.0  # 上部タイトル用スペース
            branch_line_gap = 45.0  # 親と子の列間マージン

            col_x_map: Dict[int, float] = {}
            curr_x = margin_x
            for d in sorted(col_widths.keys()):
                col_x_map[d] = curr_x
                curr_x += col_widths[d] + branch_line_gap

            def place_nodes(node: SireTreeNode, depth: int, top_y: float):
                node.x = col_x_map.get(depth, margin_x + depth * 300.0)
                # 親ノードを最上部（top_y）に配置（子供達は親と同じ高さかそれより下に並ぶ）
                node.y = top_y

                if node.children:
                    child_curr_y = top_y
                    for child in node.children:
                        place_nodes(child, depth + 1, child_curr_y)
                        child_curr_y += child.subtree_height + item_v_margin

                # NaN/Inf防御
                if math.isnan(node.x) or math.isinf(node.x):
                    node.x = 40.0
                if math.isnan(node.y) or math.isinf(node.y):
                    node.y = top_y

                node.card_rect = QRectF(node.x, node.y, node.width, node.height)
                self.node_rect_map.append((node.card_rect, node))

            place_nodes(self.root_node, 0, margin_y)

            # 5. キャンバスの全体サイズを決定 (安全な整数化)
            if self.node_rect_map:
                max_x = max(node.x + node.width for _, node in self.node_rect_map) + 60.0
                max_y = max(node.y + node.height for _, node in self.node_rect_map) + 60.0
                canvas_w = max(int(round(max_x)), 900)
                canvas_h = max(int(round(max_y)), 650)
            else:
                canvas_w, canvas_h = 900, 650

            # 最大サイズ制限 (Qtの32767pxオーバーフロー防止)
            canvas_w = min(canvas_w, 30000)
            canvas_h = min(canvas_h, 30000)

            self.setFixedSize(canvas_w, canvas_h)
        except Exception as e:
            print(f"⚠️ [SireTreeCanvasWidget] レイアウト計算エラー: {e}", file=sys.stderr)
            traceback.print_exc()

    def paintEvent(self, event) -> None:
        """樹形図を描画"""
        painter = QPainter()
        if not painter.begin(self):
            return
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

            # 背景塗りつぶし
            painter.fillRect(self.rect(), QColor("#0f172a"))

            if not self.root_node:
                painter.setPen(QColor("#64748b"))
                painter.setFont(self.font_node_text)
                painter.drawText(
                    self.rect(),
                    Qt.AlignmentFlag.AlignCenter,
                    "左側のメニューから系統（サイヤーライン）を選択してください。",
                )
                return

            # 1. 系統名タイトル（最上部）
            painter.setFont(self.font_title)
            painter.setPen(QColor("#38bdf8"))  # スカイブルー
            title_text = f"{self.root_node.line_name}"
            painter.drawText(40, 42, title_text)

            # 2. 罫線の描画（ノードの背面に描画）
            pen_line = QPen(QColor("#475569"), 1.8)
            pen_line.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen_line.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen_line)

            visited_lines: Set[int] = set()

            def draw_branch_lines(node: SireTreeNode):
                if not node.children or node.horse_id in visited_lines:
                    return
                visited_lines.add(node.horse_id)

                parent_cy = node.y + node.header_height + (node.height - node.header_height) / 2.0
                parent_rx = node.x + node.width
                branch_mid_x = parent_rx + 20.0

                # 親から分岐縦線への水平線
                painter.drawLine(
                    int(round(parent_rx)), int(round(parent_cy)),
                    int(round(branch_mid_x)), int(round(parent_cy))
                )

                child_center_ys = []
                for child in node.children:
                    child_cy = child.y + child.header_height + (child.height - child.header_height) / 2.0
                    child_lx = child.x
                    child_center_ys.append(child_cy)

                    # 分岐縦線から子ノードへの水平線
                    painter.drawLine(
                        int(round(branch_mid_x)), int(round(child_cy)),
                        int(round(child_lx)), int(round(child_cy))
                    )

                    # 再帰的に子のブランチも描画
                    draw_branch_lines(child)

                # 子ノードたちを結ぶ垂直線（親と同じ高さから最下段の子まで）
                if child_center_ys:
                    top_y = min(min(child_center_ys), parent_cy)
                    bot_y = max(max(child_center_ys), parent_cy)
                    painter.drawLine(
                        int(round(branch_mid_x)), int(round(top_y)),
                        int(round(branch_mid_x)), int(round(bot_y))
                    )

            draw_branch_lines(self.root_node)

            # 3. 各ノードの描画
            for rect, node in self.node_rect_map:
                self._draw_node(painter, node)
        except Exception as e:
            print(f"⚠️ [SireTreeCanvasWidget] 描画エラー: {e}", file=sys.stderr)
            traceback.print_exc()
        finally:
            if painter.isActive():
                painter.end()

    def _draw_node(self, painter: QPainter, node: SireTreeNode) -> None:
        """単一の馬ノード（および新サイヤーラインヘッダー）を描画"""
        is_hovered = (node == self.hovered_node)

        body_y = node.y + node.header_height
        body_h = node.height - node.header_height
        body_rect = QRectF(node.x, body_y, node.width, body_h)

        # 新サイヤーラインヘッダーの描画（始祖以外で新サイヤーライン成立時）
        if node.is_new_line and not node.is_root and node.header_height > 0:
            header_rect = QRectF(node.x, node.y, node.width, node.header_height)
            painter.setFont(self.font_line_header)
            painter.setPen(QColor("#38bdf8"))
            painter.drawText(
                header_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"◆ {node.name}系",
            )

        # 馬本体の背景カード
        if is_hovered:
            painter.setPen(QPen(QColor("#38bdf8"), 1.5))
            painter.setBrush(QBrush(QColor("#1e293b")))
        else:
            painter.setPen(QPen(QColor("#334155"), 1.0))
            painter.setBrush(QBrush(QColor("#161e2e")))

        painter.drawRoundedRect(body_rect, 6.0, 6.0)

        # テキストの描画
        text_x = node.x + 12.0
        cy = body_y + body_h / 2.0

        fm_text = QFontMetrics(self.font_node_text)
        fm_bold = QFontMetrics(self.font_node_bold)
        fm_root = QFontMetrics(self.font_root_name)

        # 始祖 / 通常ノードの表示分け
        if node.is_root:
            painter.setFont(self.font_root_name)
            painter.setPen(QColor("#f8fafc"))
            name_txt = f"{node.name}（始祖）"
            painter.drawText(int(round(text_x)), int(round(cy + 4)), name_txt)
            text_x += fm_root.horizontalAdvance(name_txt) + 14.0
        else:
            painter.setFont(self.font_node_bold)
            painter.setPen(QColor("#f8fafc") if node.is_active else QColor("#e2e8f0"))

            name_txt = f"{node.name}({node.birth_year})"
            painter.drawText(int(round(text_x)), int(round(cy + 4)), name_txt)
            text_x += fm_bold.horizontalAdvance(name_txt) + 14.0

        # 成績
        starts = node.career_starts
        wins = node.career_wins
        if starts > 0 or wins > 0 or not node.is_root:
            painter.setFont(self.font_node_text)
            painter.setPen(QColor("#94a3b8"))
            record_txt = f"{starts}-{wins}"
            painter.drawText(int(round(text_x)), int(round(cy + 4)), record_txt)
            text_x += fm_text.horizontalAdvance(record_txt) + 12.0

        # G1勝利数
        if node.g1_wins > 0:
            painter.setFont(self.font_node_bold)
            painter.setPen(QColor("#fbbf24"))  # ゴールド
            g1_txt = f"G1:{node.g1_wins}"
            painter.drawText(int(round(text_x)), int(round(cy + 4)), g1_txt)
            text_x += fm_bold.horizontalAdvance(g1_txt) + 12.0

        # 適性馬場 & 距離
        painter.setFont(self.font_node_text)
        painter.setPen(QColor("#a5f3fc"))  # シアン系
        surf_txt = node.surface_str
        dist_txt = f"{node.dist_min}-{node.dist_max}m" if node.dist_min > 0 else ""
        apt_txt = f"{surf_txt} {dist_txt}".strip()
        if apt_txt:
            painter.drawText(int(round(text_x)), int(round(cy + 4)), apt_txt)
            text_x += fm_text.horizontalAdvance(apt_txt) + 12.0

        # 供用中バッジ
        if node.is_active:
            painter.setFont(self.font_badge)
            painter.setPen(QColor("#10b981"))  # グリーン
            painter.drawText(int(round(text_x)), int(round(cy + 4)), "[供用中]")

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        found_node = None
        for rect, node in self.node_rect_map:
            if rect.contains(pos):
                found_node = node
                break

        if found_node != self.hovered_node:
            self.hovered_node = found_node
            if found_node:
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                status = "供用中種牡馬" if found_node.is_active else "引退/非供用"
                g1_str = f"G1 {found_node.g1_wins}勝" if found_node.g1_wins > 0 else "G1未勝利"
                tooltip = (
                    f"【{found_node.name}】 ({status})\n"
                    f"生誕年: {found_node.birth_year}年\n"
                    f"戦績: {found_node.career_starts}戦{found_node.career_wins}勝 ({g1_str})\n"
                    f"適性: {found_node.surface_str} ({found_node.dist_min}m〜{found_node.dist_max}m)\n"
                    f"クリック: 詳細カルテを表示"
                )
                self.setToolTip(tooltip)
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
                self.setToolTip("")
            self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            for rect, node in self.node_rect_map:
                if rect.contains(pos):
                    self.node_clicked.emit(node.horse_id)
                    break


class SireLineageWidget(QWidget):
    """
    種牡馬サイヤーライン系統樹タブウィジェット
    - 左列: 上下2段のメニューツリー（存続系列 / 断絶系列）
    - 右列: 系統樹描画キャンバス（スクロール可能）
    """

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db

        # キャッシュデータ
        self.horses_map: Dict[int, Dict[str, Any]] = {}
        self.sires_map: Dict[int, Dict[str, Any]] = {}
        self.sire_sons_map: Dict[int, List[int]] = defaultdict(list)
        self.depth_cache: Dict[int, int] = {}
        self.root_sire_ids: List[int] = []

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---------------------------
        # 左列: メニューパネル (上下2段)
        # ---------------------------
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(8)

        # 検索バー
        search_box = QHBoxLayout()
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("🔍 サイヤーライン / 馬名検索...")
        self.edit_search.textChanged.connect(self._on_search_text_changed)
        search_box.addWidget(self.edit_search)
        left_layout.addLayout(search_box)

        # 左列の上下2段スプリッター
        left_splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. 上段: 存続系列
        active_box = QWidget()
        active_layout = QVBoxLayout(active_box)
        active_layout.setContentsMargins(0, 0, 0, 0)
        active_layout.setSpacing(4)

        self.lbl_active_header = QLabel("🟢 存続系列")
        self.lbl_active_header.setStyleSheet("""
            font-weight: bold;
            font-size: 13px;
            color: #10b981;
            padding: 4px;
            background-color: #13271f;
            border-radius: 4px;
        """)
        active_layout.addWidget(self.lbl_active_header)

        self.tree_active = QTreeWidget()
        self.tree_active.setHeaderLabels(["サイヤーライン (系)", "後継/現役"])
        self.tree_active.setHeaderHidden(True)
        self.tree_active.setAlternatingRowColors(False)
        self.tree_active.setRootIsDecorated(True)
        self.tree_active.setAnimated(True)
        self.tree_active.setStyleSheet("""
            QTreeWidget {
                background-color: #161b26;
                color: #f8fafc;
                border: 1px solid #1e293b;
                border-radius: 6px;
                font-size: 13px;
            }
            QTreeWidget::item {
                padding: 6px 4px;
                background-color: #161b26;
                color: #f8fafc;
            }
            QTreeWidget::item:hover {
                background-color: #1e293b;
                color: #38bdf8;
            }
            QTreeWidget::item:selected {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
            }
        """)
        header_act = self.tree_active.header()
        header_act.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_act.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree_active.itemClicked.connect(self._on_tree_item_clicked)
        active_layout.addWidget(self.tree_active)
        left_splitter.addWidget(active_box)

        # 2. 下段: 断絶系列
        extinct_box = QWidget()
        extinct_layout = QVBoxLayout(extinct_box)
        extinct_layout.setContentsMargins(0, 0, 0, 0)
        extinct_layout.setSpacing(4)

        self.lbl_extinct_header = QLabel("⚪ 断絶系列")
        self.lbl_extinct_header.setStyleSheet("""
            font-weight: bold;
            font-size: 13px;
            color: #94a3b8;
            padding: 4px;
            background-color: #1e293b;
            border-radius: 4px;
        """)
        extinct_layout.addWidget(self.lbl_extinct_header)

        self.tree_extinct = QTreeWidget()
        self.tree_extinct.setHeaderLabels(["サイヤーライン (系)", "後継"])
        self.tree_extinct.setHeaderHidden(True)
        self.tree_extinct.setAlternatingRowColors(False)
        self.tree_extinct.setRootIsDecorated(True)
        self.tree_extinct.setAnimated(True)
        self.tree_extinct.setStyleSheet("""
            QTreeWidget {
                background-color: #161b26;
                color: #94a3b8;
                border: 1px solid #1e293b;
                border-radius: 6px;
                font-size: 13px;
            }
            QTreeWidget::item {
                padding: 6px 4px;
                background-color: #161b26;
                color: #94a3b8;
            }
            QTreeWidget::item:hover {
                background-color: #1e293b;
                color: #e2e8f0;
            }
            QTreeWidget::item:selected {
                background-color: #475569;
                color: #ffffff;
                font-weight: bold;
            }
        """)
        header_ext = self.tree_extinct.header()
        header_ext.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_ext.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree_extinct.itemClicked.connect(self._on_tree_item_clicked)
        extinct_layout.addWidget(self.tree_extinct)
        left_splitter.addWidget(extinct_box)

        left_splitter.setSizes([380, 260])
        left_layout.addWidget(left_splitter)

        left_panel.setMinimumWidth(300)
        left_panel.setMaximumWidth(450)
        splitter.addWidget(left_panel)

        # ---------------------------
        # 右列: 系統樹キャンバスパネル
        # ---------------------------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(6)

        # 操作ツールバー
        toolbar = QHBoxLayout()
        self.lbl_current_title = QLabel("サイヤーライン系統樹")
        self.lbl_current_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #38bdf8;")
        toolbar.addWidget(self.lbl_current_title)
        toolbar.addStretch()

        self.btn_open_carte = QPushButton("📋 種牡馬カルテを開く")
        self.btn_open_carte.setEnabled(False)
        self.btn_open_carte.clicked.connect(self._on_open_current_carte_clicked)
        toolbar.addWidget(self.btn_open_carte)

        right_layout.addLayout(toolbar)

        # スクロールエリア
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 6px;
            }
        """)

        self.canvas_widget = SireTreeCanvasWidget()
        self.canvas_widget.node_clicked.connect(self._on_canvas_node_clicked)
        self.scroll_area.setWidget(self.canvas_widget)

        right_layout.addWidget(self.scroll_area)
        splitter.addWidget(right_panel)

        splitter.setSizes([320, 960])
        main_layout.addWidget(splitter)

        self.current_selected_horse_id: Optional[int] = None

    @property
    def canvas(self) -> SireTreeCanvasWidget:
        return self.canvas_widget

    def refresh_data(self) -> None:
        """データベースから全種牡馬・血統情報を安全に読み込みツリーを再構築"""
        try:
            conn = self.db.get_connection()
            try:
                # 1. 全競走馬データ
                h_rows = conn.execute("SELECT * FROM horses").fetchall()
                if h_rows:
                    col_names = [d[0] for d in conn.execute("SELECT * FROM horses LIMIT 1").description]
                    self.horses_map = {row[col_names.index("horse_id")]: dict(zip(col_names, row)) for row in h_rows}
                else:
                    self.horses_map = {}

                # 2. 全種牡馬データ
                s_rows = conn.execute("SELECT * FROM sires").fetchall()
                if s_rows:
                    s_cols = [d[0] for d in conn.execute("SELECT * FROM sires LIMIT 1").description]
                    self.sires_map = {row[s_cols.index("horse_id")]: dict(zip(s_cols, row)) for row in s_rows}
                else:
                    self.sires_map = {}
            finally:
                conn.close()

            # 3. 種牡馬の父子マップ (father_id -> list of son_ids where son is sire)
            self.sire_sons_map.clear()
            for h_id in self.sires_map:
                h = self.horses_map.get(h_id)
                if h and h.get("sire_id") and h["sire_id"] in self.sires_map:
                    self.sire_sons_map[h["sire_id"]].append(h_id)

            # 生誕年順にソート
            for f_id in self.sire_sons_map:
                self.sire_sons_map[f_id].sort(
                    key=lambda x: (
                        self.horses_map.get(x, {}).get("birth_year", 0),
                        -self.horses_map.get(x, {}).get("prize_money", 0),
                        x
                    )
                )

            # 4. 後継世代深さの計算 (循環参照防止ガード付き)
            self.depth_cache.clear()
            visited_depth: Set[int] = set()

            def calc_depth(hid: int) -> int:
                if hid in self.depth_cache:
                    return self.depth_cache[hid]
                if hid in visited_depth:
                    return 0
                visited_depth.add(hid)
                sons = self.sire_sons_map.get(hid, [])
                if not sons:
                    self.depth_cache[hid] = 0
                    return 0
                d = 1 + max(calc_depth(sid) for sid in sons)
                self.depth_cache[hid] = d
                return d

            for hid in list(self.sires_map.keys()):
                visited_depth.clear()
                calc_depth(hid)

            # 5. 始祖（Root Sires）の抽出
            self.root_sire_ids = [
                hid for hid in self.sires_map
                if not self.horses_map.get(hid, {}).get("sire_id") or self.horses_map[hid]["sire_id"] not in self.sires_map
            ]
            self.root_sire_ids.sort(
                key=lambda x: (
                    self.horses_map.get(x, {}).get("birth_year", 0),
                    self.horses_map.get(x, {}).get("name", "")
                )
            )

            # 6. メニューツリーの更新
            self._populate_menu_trees()
        except Exception as e:
            print(f"⚠️ [SireLineageWidget] データ読み込みエラー: {e}", file=sys.stderr)
            traceback.print_exc()

    def _has_active_descendant(self, hid: int, visited: Optional[Set[int]] = None) -> bool:
        """その種牡馬またはその子孫種牡馬に1頭でも現役種牡馬が存在するか判定 (循環防止付き)"""
        if visited is None:
            visited = set()
        if hid in visited:
            return False
        visited.add(hid)

        s = self.sires_map.get(hid)
        if s and s.get("is_active"):
            return True
        for son_id in self.sire_sons_map.get(hid, []):
            if self._has_active_descendant(son_id, visited):
                return True
        return False

    def _populate_menu_trees(self, filter_text: str = "") -> None:
        """左列の存続系列・断絶系列ツリーを構築"""
        self.tree_active.clear()
        self.tree_extinct.clear()

        active_count = 0
        extinct_count = 0
        filter_text = filter_text.strip().lower()

        for root_id in self.root_sire_ids:
            h = self.horses_map.get(root_id)
            if not h:
                continue

            root_name = h.get("name", "不明")
            is_active_line = self._has_active_descendant(root_id)
            target_tree = self.tree_active if is_active_line else self.tree_extinct

            root_item = QTreeWidgetItem()
            root_item.setText(0, f"{root_name}系")
            root_item.setData(0, Qt.ItemDataRole.UserRole, root_id)

            depth = self.depth_cache.get(root_id, 0)
            sons_cnt = len(self.sire_sons_map.get(root_id, []))
            root_item.setText(1, f"深さ:{depth} (直仔:{sons_cnt})")

            # 子サイヤーライン（自身からさらに2世代の種牡馬が生まれた馬 = depth >= 2）の再帰的追加
            visited_sub: Set[int] = set()

            def add_child_lines(parent_item: QTreeWidgetItem, parent_hid: int):
                def find_next_lines(curr_hid: int) -> List[int]:
                    lines = []
                    for son_id in self.sire_sons_map.get(curr_hid, []):
                        if son_id in visited_sub:
                            continue
                        visited_sub.add(son_id)
                        if self.depth_cache.get(son_id, 0) >= 2:
                            lines.append(son_id)
                        else:
                            lines.extend(find_next_lines(son_id))
                    return lines

                sub_line_ids = find_next_lines(parent_hid)
                for sub_id in sub_line_ids:
                    sub_h = self.horses_map.get(sub_id)
                    if not sub_h:
                        continue
                    sub_item = QTreeWidgetItem(parent_item)
                    sub_item.setText(0, f"└ {sub_h.get('name', '')}系")
                    sub_item.setData(0, Qt.ItemDataRole.UserRole, sub_id)
                    sub_depth = self.depth_cache.get(sub_id, 0)
                    sub_sons = len(self.sire_sons_map.get(sub_id, []))
                    sub_item.setText(1, f"深さ:{sub_depth} (直仔:{sub_sons})")

                    add_child_lines(sub_item, sub_id)

            add_child_lines(root_item, root_id)

            # フィルター処理
            if filter_text:
                def matches_filter(item: QTreeWidgetItem) -> bool:
                    t0 = item.text(0).lower()
                    if filter_text in t0:
                        return True
                    for i in range(item.childCount()):
                        if matches_filter(item.child(i)):
                            return True
                    return False

                if not matches_filter(root_item):
                    continue

            target_tree.addTopLevelItem(root_item)
            root_item.setExpanded(True)

            if is_active_line:
                active_count += 1
            else:
                extinct_count += 1

        self.lbl_active_header.setText(f"🟢 存続系列 ({active_count}系統)")
        self.lbl_extinct_header.setText(f"⚪ 断絶系列 ({extinct_count}系統)")

        # 初回選択
        if not self.current_selected_horse_id:
            if self.tree_active.topLevelItemCount() > 0:
                first_item = self.tree_active.topLevelItem(0)
                self.tree_active.setCurrentItem(first_item)
                hid = first_item.data(0, Qt.ItemDataRole.UserRole)
                if hid:
                    self._select_sire_line(hid)
            elif self.tree_extinct.topLevelItemCount() > 0:
                first_item = self.tree_extinct.topLevelItem(0)
                self.tree_extinct.setCurrentItem(first_item)
                hid = first_item.data(0, Qt.ItemDataRole.UserRole)
                if hid:
                    self._select_sire_line(hid)

    def _on_search_text_changed(self, text: str) -> None:
        self._populate_menu_trees(text)

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        hid = item.data(0, Qt.ItemDataRole.UserRole)
        if hid:
            self._select_sire_line(hid)

    def _select_sire_line(self, horse_id: int) -> None:
        """選択された馬を起点とする系統樹ツリーを構築しキャンバスに表示"""
        try:
            self.current_selected_horse_id = horse_id
            self.btn_open_carte.setEnabled(True)

            h_info = self.horses_map.get(horse_id)
            if not h_info:
                return

            line_name = f"{h_info.get('name', '不明')}系"
            self.lbl_current_title.setText(f"サイヤーライン系統樹: {line_name}")

            visited_tree: Set[int] = set()
            root_node = self._build_tree_node(
                horse_id,
                depth=0,
                is_root=True,
                root_line_name=line_name,
                visited=visited_tree,
            )
            self.canvas_widget.set_tree_root(root_node)
            self.scroll_area.horizontalScrollBar().setValue(0)
            self.scroll_area.verticalScrollBar().setValue(0)
        except Exception as e:
            print(f"⚠️ [SireLineageWidget] 系統樹選択エラー: {e}", file=sys.stderr)
            traceback.print_exc()

    def _build_tree_node(
        self,
        hid: int,
        depth: int,
        is_root: bool,
        root_line_name: str,
        visited: Optional[Set[int]] = None,
    ) -> SireTreeNode:
        """指定した種牡馬から再帰的にSireTreeNodeツリーを構築 (循環参照防止付き)"""
        if visited is None:
            visited = set()
        visited.add(hid)

        h_data = self.horses_map.get(hid, {})
        s_data = self.sires_map.get(hid, {})

        # 馬場・距離適性の安全な算出
        surface_str = "芝"
        dist_min = 1600
        dist_max = 2400
        if h_data:
            try:
                h_obj = Horse.from_row(h_data)
                surf_val = h_obj.surface_aptitude
                surface_str = "芝" if surf_val == "turf" else ("ダート" if surf_val == "dirt" else "芝/ダ")
                dist_min, dist_max = h_obj.get_distance_aptitude()
            except Exception:
                pass

        is_active = bool(s_data.get("is_active", 0))
        desc_depth = self.depth_cache.get(hid, 0)
        is_new_line = (desc_depth >= 2)
        h_name = h_data.get("name", "不明")
        line_name = f"{h_name}系"

        node = SireTreeNode(
            horse_id=hid,
            name=h_name,
            birth_year=h_data.get("birth_year", 0),
            career_starts=h_data.get("career_starts", 0),
            career_wins=h_data.get("career_wins", 0),
            g1_wins=h_data.get("g1_wins", 0),
            surface_str=surface_str,
            dist_min=dist_min,
            dist_max=dist_max,
            is_active=is_active,
            is_root=is_root,
            is_new_line=is_new_line,
            line_name=root_line_name if is_root else line_name,
            depth_from_root=depth,
            max_descendant_depth=desc_depth,
        )

        for son_id in self.sire_sons_map.get(hid, []):
            if son_id in visited or son_id not in self.horses_map:
                continue
            child_node = self._build_tree_node(
                son_id,
                depth=depth + 1,
                is_root=False,
                root_line_name=root_line_name,
                visited=visited,
            )
            node.children.append(child_node)

        return node

    def _on_canvas_node_clicked(self, horse_id: int) -> None:
        """キャンバス内の馬をクリックした際に種牡馬カルテを開く"""
        self._open_sire_detail(horse_id)

    def _on_open_current_carte_clicked(self) -> None:
        if self.current_selected_horse_id:
            self._open_sire_detail(self.current_selected_horse_id)

    def _open_sire_detail(self, horse_id: int) -> None:
        """種牡馬カルテ（または競走馬詳細）ダイアログを表示"""
        try:
            dlg = SireDetailDialog(self.db, sire_horse_id=horse_id, parent=self)
            dlg.exec()
        except Exception:
            try:
                dlg = HorseDetailDialog(self.db, horse_id=horse_id, parent=self)
                dlg.exec()
            except Exception as e2:
                print(f"⚠️ [SireLineageWidget] ダイアログ表示エラー: {e2}", file=sys.stderr)


class DamTreeCanvasWidget(QWidget):
    """
    繁殖牝馬ファミリーナンバー [族] 系統樹描画キャンバスウィジェット
    QPainterによる樹形図・接続線・供用中バッジの描画
    """
    node_clicked = pyqtSignal(int)  # horse_id

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.root_node: Optional[DamTreeNode] = None
        self.hovered_node: Optional[DamTreeNode] = None
        self.node_rect_map: List[Tuple[QRectF, DamTreeNode]] = []

        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #0f172a;")

        # フォント設定
        font_family = "Hiragino Sans, Hiragino Kaku Gothic ProN, Yu Gothic, Meiryo, sans-serif"
        self.font_title = QFont(font_family, 15, QFont.Weight.Bold)
        self.font_root_name = QFont(font_family, 12, QFont.Weight.Bold)
        self.font_node_text = QFont(font_family, 11)
        self.font_node_bold = QFont(font_family, 11, QFont.Weight.Bold)
        self.font_badge = QFont(font_family, 9, QFont.Weight.Bold)

    def set_tree_root(self, root_node: Optional[DamTreeNode]) -> None:
        """表示する系統樹のルートノードを設定しレイアウトを再計算"""
        self.root_node = root_node
        self.hovered_node = None
        self._calculate_layout()
        self.update()

    def _calculate_layout(self) -> None:
        """全ノードの座標とキャンバス必要サイズを再帰的に計算"""
        self.node_rect_map.clear()
        if not self.root_node:
            self.resize(800, 600)
            self.setMinimumSize(800, 600)
            return

        try:
            # 1. 各ノードのテキスト幅・高さを計算
            fm_text = QFontMetrics(self.font_node_text)
            fm_bold = QFontMetrics(self.font_node_bold)
            fm_root = QFontMetrics(self.font_root_name)
            fm_badge = QFontMetrics(self.font_badge)

            def measure_node(node: DamTreeNode):
                # 左マージン
                total_w = 14.0

                # 1. 馬名部分
                if node.is_root:
                    name_txt = f"{node.name}（始祖）"
                    total_w += fm_root.horizontalAdvance(name_txt) + 14.0
                else:
                    name_txt = f"{node.name}({node.birth_year})"
                    total_w += fm_bold.horizontalAdvance(name_txt) + 14.0

                # 2. 成績
                starts = node.career_starts
                wins = node.career_wins
                if starts > 0 or wins > 0 or not node.is_root:
                    rec_txt = f"{starts}-{wins}"
                    total_w += fm_text.horizontalAdvance(rec_txt) + 12.0

                # 3. G1勝利数
                if node.g1_wins > 0:
                    g1_txt = f"G1:{node.g1_wins}"
                    total_w += fm_bold.horizontalAdvance(g1_txt) + 12.0

                # 4. 適性馬場 & 距離
                surf_txt = node.surface_str
                dist_txt = f"{node.dist_min}-{node.dist_max}m" if node.dist_min > 0 else ""
                apt_txt = f"{surf_txt} {dist_txt}".strip()
                if apt_txt:
                    total_w += fm_text.horizontalAdvance(apt_txt) + 12.0

                # 5. 供用中バッジ
                if node.is_active:
                    badge_txt = "[供用中]"
                    total_w += fm_badge.horizontalAdvance(badge_txt) + 14.0

                # 右パディング追加
                total_w += 16.0

                node.width = max(260.0, float(math.ceil(total_w)))
                node.height = 32.0

                for child in node.children:
                    measure_node(child)

            measure_node(self.root_node)

            # 2. 世代列ごとの最大幅を計算
            col_widths: Dict[int, float] = defaultdict(lambda: 260.0)

            def calc_col_widths(node: DamTreeNode, depth: int):
                col_widths[depth] = max(col_widths[depth], node.width)
                for child in node.children:
                    calc_col_widths(child, depth + 1)

            calc_col_widths(self.root_node, 0)

            # 3. サブツリーの高さをボトムアップで計算
            item_v_margin = 12.0  # ノード間の垂直余白

            def calc_subtree_height(node: DamTreeNode) -> float:
                if not node.children:
                    node.subtree_height = node.height
                    return node.subtree_height

                children_total_h = sum(calc_subtree_height(c) for c in node.children)
                children_total_h += item_v_margin * (len(node.children) - 1)
                node.subtree_height = max(node.height, children_total_h)
                return node.subtree_height

            calc_subtree_height(self.root_node)

            # 4. ノードの (X, Y) 座標をトップダウンで配置（トップアライン）
            margin_x = 40.0
            margin_y = 70.0  # 上部タイトル用スペース
            branch_line_gap = 45.0  # 親と子の列間マージン

            col_x_map: Dict[int, float] = {}
            curr_x = margin_x
            for d in sorted(col_widths.keys()):
                col_x_map[d] = curr_x
                curr_x += col_widths[d] + branch_line_gap

            def place_nodes(node: DamTreeNode, depth: int, top_y: float):
                node.x = col_x_map.get(depth, margin_x + depth * 300.0)
                # 親ノードを最上部（top_y）に配置（子供達は親と同じ高さかそれより下に並ぶ）
                node.y = top_y

                if node.children:
                    child_curr_y = top_y
                    for child in node.children:
                        place_nodes(child, depth + 1, child_curr_y)
                        child_curr_y += child.subtree_height + item_v_margin

                # NaN/Inf防御
                if math.isnan(node.x) or math.isinf(node.x):
                    node.x = 40.0
                if math.isnan(node.y) or math.isinf(node.y):
                    node.y = top_y

                node.card_rect = QRectF(node.x, node.y, node.width, node.height)
                self.node_rect_map.append((node.card_rect, node))

            place_nodes(self.root_node, 0, margin_y)

            # 5. キャンバス全体のサイズを更新
            max_r = max((node.x + node.width for _, node in self.node_rect_map), default=800.0)
            max_b = max((node.y + node.height for _, node in self.node_rect_map), default=600.0)

            total_w = min(max(800, int(math.ceil(max_r + 60.0))), 30000)
            total_h = min(max(600, int(math.ceil(max_b + 60.0))), 30000)

            self.setFixedSize(total_w, total_h)

        except Exception as e:
            print(f"⚠️ [DamTreeCanvas] レイアウト計算エラー: {e}", file=sys.stderr)
            traceback.print_exc()

    def paintEvent(self, event) -> None:
        painter = QPainter()
        if not painter.begin(self):
            return
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

            # 背景塗りつぶし
            painter.fillRect(self.rect(), QColor("#0f172a"))

            if not self.root_node:
                painter.setPen(QColor("#64748b"))
                painter.setFont(self.font_node_text)
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "左側のメニューからファミリーナンバー（族）を選択してください")
                return

            # 1. 系統樹ヘッダータイトル描画
            family_title = f"🌸 ◆ {self.root_node.family_name}"
            painter.setFont(self.font_title)
            painter.setPen(QColor("#f472b6"))  # ピンク系タイトル
            painter.drawText(40, 42, family_title)

            # 2. 罫線の描画（ノードの背面に描画）
            pen_line = QPen(QColor("#db2777"), 1.8)
            pen_line.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen_line.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen_line)

            def draw_branch_lines(node: DamTreeNode, visited: Set[int]):
                if not node.children or node.horse_id in visited:
                    return
                visited.add(node.horse_id)

                parent_cy = node.y + (node.height / 2.0)
                parent_rx = node.x + node.width
                branch_mid_x = parent_rx + 20.0

                # 親から分岐縦線への水平線
                painter.drawLine(
                    int(round(parent_rx)), int(round(parent_cy)),
                    int(round(branch_mid_x)), int(round(parent_cy))
                )

                child_center_ys = []
                for child in node.children:
                    child_cy = child.y + (child.height / 2.0)
                    child_lx = child.x
                    child_center_ys.append(child_cy)

                    # 分岐縦線から子ノードへの水平線
                    painter.drawLine(
                        int(round(branch_mid_x)), int(round(child_cy)),
                        int(round(child_lx)), int(round(child_cy))
                    )

                    # 再帰的に子のブランチも描画
                    draw_branch_lines(child, visited)

                # 子ノードたちを結ぶ垂直線（親と同じ高さから最下段の子まで）
                if child_center_ys:
                    top_y = min(min(child_center_ys), parent_cy)
                    bot_y = max(max(child_center_ys), parent_cy)
                    painter.drawLine(
                        int(round(branch_mid_x)), int(round(top_y)),
                        int(round(branch_mid_x)), int(round(bot_y))
                    )

            draw_branch_lines(self.root_node, set())

            # 3. ノードカードの描画
            for card_rect, node in self.node_rect_map:
                self._paint_node(painter, node)

        except Exception as e:
            print(f"⚠️ [DamTreeCanvasWidget] 描画例外: {e}", file=sys.stderr)
            traceback.print_exc()
        finally:
            if painter.isActive():
                painter.end()

    def _paint_node(self, painter: QPainter, node: DamTreeNode) -> None:
        """個別馬ノードカードの描画"""
        is_hover = (node == self.hovered_node)
        card_r = node.card_rect

        # 1. カード背景と枠線
        if node.is_root:
            # 始祖馬: ピンク系アクセント枠＋ダークローズ背景
            bg_col = QColor("#2a1220") if not is_hover else QColor("#3b172d")
            border_col = QColor("#f472b6") if not is_hover else QColor("#fb7185")
            border_w = 2.0
        else:
            # 後継繁殖牝馬
            if is_hover:
                bg_col = QColor("#1e293b")
                border_col = QColor("#f472b6")
                border_w = 1.8
            else:
                bg_col = QColor("#161b26")
                border_col = QColor("#334155")
                border_w = 1.0

        painter.setPen(QPen(border_col, border_w))
        painter.setBrush(QBrush(bg_col))
        painter.drawRoundedRect(card_r, 5.0, 5.0)

        # 2. テキスト描画
        fm_text = QFontMetrics(self.font_node_text)
        fm_bold = QFontMetrics(self.font_node_bold)
        fm_root = QFontMetrics(self.font_root_name)
        fm_badge = QFontMetrics(self.font_badge)

        cur_x = card_r.x() + 10.0
        cy = card_r.y() + (card_r.height() / 2.0)

        # A. 馬名
        if node.is_root:
            name_txt = f"{node.name}（始祖）"
            painter.setFont(self.font_root_name)
            painter.setPen(QColor("#fdf2f8"))
            painter.drawText(int(round(cur_x)), int(round(cy + 4)), name_txt)
            cur_x += fm_root.horizontalAdvance(name_txt) + 14.0
        else:
            name_txt = f"{node.name}({node.birth_year})"
            painter.setFont(self.font_node_bold)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(int(round(cur_x)), int(round(cy + 4)), name_txt)
            cur_x += fm_bold.horizontalAdvance(name_txt) + 14.0

        # B. 通算成績 (戦-勝)
        starts = node.career_starts
        wins = node.career_wins
        if starts > 0 or wins > 0 or not node.is_root:
            rec_txt = f"{starts}-{wins}"
            painter.setFont(self.font_node_text)
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(int(round(cur_x)), int(round(cy + 4)), rec_txt)
            cur_x += fm_text.horizontalAdvance(rec_txt) + 12.0

        # C. G1勝利数
        if node.g1_wins > 0:
            g1_txt = f"G1:{node.g1_wins}"
            painter.setFont(self.font_node_bold)
            painter.setPen(QColor("#facc15"))  # ゴールド
            painter.drawText(int(round(cur_x)), int(round(cy + 4)), g1_txt)
            cur_x += fm_bold.horizontalAdvance(g1_txt) + 12.0

        # D. 適性馬場 & 距離
        surf_txt = node.surface_str
        dist_txt = f"{node.dist_min}-{node.dist_max}m" if node.dist_min > 0 else ""
        apt_txt = f"{surf_txt} {dist_txt}".strip()
        if apt_txt:
            painter.setFont(self.font_node_text)
            painter.setPen(QColor("#38bdf8"))  # スカイブルー
            painter.drawText(int(round(cur_x)), int(round(cy + 4)), apt_txt)
            cur_x += fm_text.horizontalAdvance(apt_txt) + 12.0

        # E. 供用中バッジ
        if node.is_active:
            badge_txt = "[供用中]"
            bw = fm_badge.horizontalAdvance(badge_txt) + 8.0
            bh = 18.0
            by = card_r.y() + (card_r.height() - bh) / 2.0
            badge_r = QRectF(cur_x, by, bw, bh)

            painter.setPen(QPen(QColor("#f472b6"), 1.0))
            painter.setBrush(QBrush(QColor("#831843")))
            painter.drawRoundedRect(badge_r, 3.0, 3.0)

            painter.setFont(self.font_badge)
            painter.setPen(QColor("#fdf2f8"))
            painter.drawText(badge_r, Qt.AlignmentFlag.AlignCenter, badge_txt)

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        hovered = None
        for rect, node in self.node_rect_map:
            if rect.contains(pos):
                hovered = node
                break

        if hovered != self.hovered_node:
            self.hovered_node = hovered
            if hovered:
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                status = "供用中繁殖牝馬" if hovered.is_active else "引退/非供用"
                g1_str = f"G1 {hovered.g1_wins}勝" if hovered.g1_wins > 0 else "G1未勝利"
                tooltip = (
                    f"【{hovered.name}】 ({status})\n"
                    f"生誕年: {hovered.birth_year}年\n"
                    f"戦績: {hovered.career_starts}戦{hovered.career_wins}勝 ({g1_str})\n"
                    f"適性: {hovered.surface_str} ({hovered.dist_min}m〜{hovered.dist_max}m)\n"
                    f"クリック: 繁殖牝馬カルテを表示"
                )
                self.setToolTip(tooltip)
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
                self.setToolTip("")
            self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            for rect, node in self.node_rect_map:
                if rect.contains(pos):
                    self.node_clicked.emit(node.horse_id)
                    return
        super().mousePressEvent(event)


class DamLineageWidget(QWidget):
    """
    繁殖牝馬（ファミリーナンバー [族]）タブ
    左右2列表示:
      左列: ファミリーナンバーメニュー（上下2段: 存続族 / 断絶族）
      右列: 系統樹キャンバス
    """

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db

        # キャッシュデータ
        self.horses_map: Dict[int, Dict[str, Any]] = {}
        self.dams_map: Dict[int, Dict[str, Any]] = {}
        self.dam_daughters_map: Dict[int, List[int]] = defaultdict(list)
        self.depth_cache: Dict[int, int] = {}
        self.root_dam_ids: List[int] = []
        self.dam_to_root_map: Dict[int, int] = {}
        self.current_selected_horse_id: Optional[int] = None

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---------------------------
        # 左列: メニューパネル (上下2段)
        # ---------------------------
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(8)

        # 検索バー
        search_box = QHBoxLayout()
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("🔍 ファミリーナンバー / 馬名検索...")
        self.edit_search.textChanged.connect(self._on_search_text_changed)
        search_box.addWidget(self.edit_search)
        left_layout.addLayout(search_box)

        # 左列の上下2段スプリッター
        left_splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. 上段: 存続族
        active_box = QWidget()
        active_layout = QVBoxLayout(active_box)
        active_layout.setContentsMargins(0, 0, 0, 0)
        active_layout.setSpacing(4)

        self.lbl_active_header = QLabel("🌸 存続族")
        self.lbl_active_header.setStyleSheet("""
            font-weight: bold;
            font-size: 13px;
            color: #f472b6;
            padding: 4px;
            background-color: #2a1220;
            border-radius: 4px;
        """)
        active_layout.addWidget(self.lbl_active_header)

        self.tree_active = QTreeWidget()
        self.tree_active.setHeaderLabels(["ファミリーナンバー (族)", "後継/現役"])
        self.tree_active.setHeaderHidden(True)
        self.tree_active.setAlternatingRowColors(False)
        self.tree_active.setRootIsDecorated(True)
        self.tree_active.setAnimated(True)
        self.tree_active.setStyleSheet("""
            QTreeWidget {
                background-color: #161b26;
                color: #f8fafc;
                border: 1px solid #1e293b;
                border-radius: 6px;
                font-size: 13px;
            }
            QTreeWidget::item {
                padding: 6px 4px;
                background-color: #161b26;
                color: #f8fafc;
            }
            QTreeWidget::item:hover {
                background-color: #1e293b;
                color: #f472b6;
            }
            QTreeWidget::item:selected {
                background-color: #be185d;
                color: #ffffff;
                font-weight: bold;
            }
        """)
        header_act = self.tree_active.header()
        header_act.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_act.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree_active.itemClicked.connect(self._on_tree_item_clicked)
        active_layout.addWidget(self.tree_active)
        left_splitter.addWidget(active_box)

        # 2. 下段: 断絶族
        extinct_box = QWidget()
        extinct_layout = QVBoxLayout(extinct_box)
        extinct_layout.setContentsMargins(0, 0, 0, 0)
        extinct_layout.setSpacing(4)

        self.lbl_extinct_header = QLabel("⚪ 断絶族")
        self.lbl_extinct_header.setStyleSheet("""
            font-weight: bold;
            font-size: 13px;
            color: #94a3b8;
            padding: 4px;
            background-color: #1e293b;
            border-radius: 4px;
        """)
        extinct_layout.addWidget(self.lbl_extinct_header)

        self.tree_extinct = QTreeWidget()
        self.tree_extinct.setHeaderLabels(["ファミリーナンバー (族)", "後継"])
        self.tree_extinct.setHeaderHidden(True)
        self.tree_extinct.setAlternatingRowColors(False)
        self.tree_extinct.setRootIsDecorated(True)
        self.tree_extinct.setAnimated(True)
        self.tree_extinct.setStyleSheet("""
            QTreeWidget {
                background-color: #161b26;
                color: #94a3b8;
                border: 1px solid #1e293b;
                border-radius: 6px;
                font-size: 13px;
            }
            QTreeWidget::item {
                padding: 6px 4px;
                background-color: #161b26;
                color: #94a3b8;
            }
            QTreeWidget::item:hover {
                background-color: #1e293b;
                color: #cbd5e1;
            }
            QTreeWidget::item:selected {
                background-color: #475569;
                color: #ffffff;
                font-weight: bold;
            }
        """)
        header_ext = self.tree_extinct.header()
        header_ext.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_ext.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree_extinct.itemClicked.connect(self._on_tree_item_clicked)
        extinct_layout.addWidget(self.tree_extinct)
        left_splitter.addWidget(extinct_box)

        left_splitter.setSizes([380, 260])
        left_layout.addWidget(left_splitter)

        left_panel.setMinimumWidth(300)
        left_panel.setMaximumWidth(450)
        splitter.addWidget(left_panel)

        # ---------------------------
        # 右列: 系統樹キャンバスパネル
        # ---------------------------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(6)

        # 操作ツールバー
        toolbar = QHBoxLayout()
        self.lbl_current_title = QLabel("🌸 ファミリーナンバー系統樹")
        self.lbl_current_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #f472b6;")
        toolbar.addWidget(self.lbl_current_title)
        toolbar.addStretch()

        self.btn_open_carte = QPushButton("🌸 繁殖牝馬カルテを開く")
        self.btn_open_carte.setEnabled(False)
        self.btn_open_carte.setStyleSheet("""
            QPushButton {
                background-color: #be185d; color: #ffffff;
                font-weight: bold; font-size: 12px;
                padding: 6px 14px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #db2777; }
        """)
        self.btn_open_carte.clicked.connect(self._on_open_current_carte_clicked)
        toolbar.addWidget(self.btn_open_carte)

        right_layout.addLayout(toolbar)

        # スクロールエリア
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 6px;
            }
        """)

        self.canvas_widget = DamTreeCanvasWidget()
        self.canvas_widget.node_clicked.connect(self._on_canvas_node_clicked)
        self.scroll_area.setWidget(self.canvas_widget)

        right_layout.addWidget(self.scroll_area)
        splitter.addWidget(right_panel)

        splitter.setSizes([320, 960])
        main_layout.addWidget(splitter)

    @property
    def canvas(self) -> DamTreeCanvasWidget:
        return self.canvas_widget

    def refresh_data(self) -> None:
        """データベースから全繁殖牝馬・血統情報を安全に読み込みツリーを再構築"""
        try:
            conn = self.db.get_connection()
            try:
                # 1. 全競走馬データ
                h_rows = conn.execute("SELECT * FROM horses").fetchall()
                if h_rows:
                    col_names = [d[0] for d in conn.execute("SELECT * FROM horses LIMIT 1").description]
                    self.horses_map = {row[col_names.index("horse_id")]: dict(zip(col_names, row)) for row in h_rows}
                else:
                    self.horses_map = {}

                # 2. 全繁殖牝馬データ
                d_rows = conn.execute("SELECT * FROM dams").fetchall()
                if d_rows:
                    d_cols = [d[0] for d in conn.execute("SELECT * FROM dams LIMIT 1").description]
                    self.dams_map = {row[d_cols.index("horse_id")]: dict(zip(d_cols, row)) for row in d_rows}
                else:
                    self.dams_map = {}
            finally:
                conn.close()

            # 3. 繁殖牝馬間の親子マップ構築（繁殖牝馬となった娘馬のみ）
            self.dam_daughters_map.clear()
            self.root_dam_ids.clear()
            self.dam_to_root_map.clear()

            for hid, d_info in self.dams_map.items():
                h = self.horses_map.get(hid)
                if not h:
                    continue
                mid = h.get("dam_id")
                if mid and mid in self.dams_map:
                    self.dam_daughters_map[mid].append(hid)

            # 4. 深さキャッシュの安全な計算 (循環参照防止ガード付き)
            self.depth_cache.clear()
            visited_depth: Set[int] = set()

            def calc_depth(hid: int) -> int:
                if hid in self.depth_cache:
                    return self.depth_cache[hid]
                if hid in visited_depth:
                    return 0
                visited_depth.add(hid)

                daughters = self.dam_daughters_map.get(hid, [])
                if not daughters:
                    self.depth_cache[hid] = 0
                    visited_depth.remove(hid)
                    return 0

                max_d = 0
                for did in daughters:
                    if did in self.dams_map:
                        max_d = max(max_d, 1 + calc_depth(did))

                self.depth_cache[hid] = max_d
                visited_depth.remove(hid)
                return max_d

            for hid in self.dams_map:
                calc_depth(hid)

            # 5. 祖先を遡って始祖繁殖牝馬（Root Dam）を特定
            for hid in self.dams_map:
                curr = hid
                visited_anc: Set[int] = set()
                while curr in self.dams_map and curr not in visited_anc:
                    visited_anc.add(curr)
                    h = self.horses_map.get(curr)
                    if not h:
                        break
                    mid = h.get("dam_id")
                    if mid and mid in self.dams_map:
                        curr = mid
                    else:
                        break
                self.dam_to_root_map[hid] = curr

            # 始祖リストの確定
            root_set = set(self.dam_to_root_map.values())
            self.root_dam_ids = sorted(
                list(root_set),
                key=lambda x: (
                    self.horses_map.get(x, {}).get("birth_year", 9999),
                    self.horses_map.get(x, {}).get("name", "")
                )
            )

            # 6. メニューツリーの構築
            self._populate_menu_trees()

        except Exception as e:
            print(f"⚠️ [DamLineageWidget] refresh_data エラー: {e}", file=sys.stderr)
            traceback.print_exc()

    def _has_active_descendant(self, hid: int, visited: Optional[Set[int]] = None) -> bool:
        """指定した繁殖牝馬またはその子孫繁殖牝馬が現役（供用中）か判定"""
        if visited is None:
            visited = set()
        if hid in visited:
            return False
        visited.add(hid)

        d_info = self.dams_map.get(hid)
        if d_info and bool(d_info.get("is_active", 0)):
            return True

        for did in self.dam_daughters_map.get(hid, []):
            if self._has_active_descendant(did, visited):
                return True
        return False

    def _populate_menu_trees(self, filter_text: str = "") -> None:
        """左列の存続族・断絶族ツリーを構築"""
        self.tree_active.clear()
        self.tree_extinct.clear()

        active_count = 0
        extinct_count = 0
        filter_text = filter_text.strip().lower()

        for root_id in self.root_dam_ids:
            h = self.horses_map.get(root_id)
            if not h:
                continue

            root_name = h.get("name", "不明")
            is_active_fam = self._has_active_descendant(root_id)
            target_tree = self.tree_active if is_active_fam else self.tree_extinct

            root_item = QTreeWidgetItem()
            root_item.setText(0, f"{root_name}族")
            root_item.setData(0, Qt.ItemDataRole.UserRole, root_id)

            depth = self.depth_cache.get(root_id, 0)
            daughters_cnt = len(self.dam_daughters_map.get(root_id, []))
            is_root_active = bool(self.dams_map.get(root_id, {}).get("is_active", 0))
            active_badge = " [供用中]" if is_root_active else ""
            root_item.setText(1, f"深さ:{depth} (直仔:{daughters_cnt}){active_badge}")

            # 後継繁殖牝馬の再帰的追加（ファミリーナンバーなので始祖の傘下のまま階層展開）
            visited_sub: Set[int] = set()

            def add_child_dams(parent_item: QTreeWidgetItem, parent_hid: int):
                for did in self.dam_daughters_map.get(parent_hid, []):
                    if did in visited_sub:
                        continue
                    visited_sub.add(did)
                    dh = self.horses_map.get(did)
                    if not dh:
                        continue
                    d_item = QTreeWidgetItem(parent_item)
                    d_name = dh.get("name", "不明")
                    d_item.setText(0, f"└ {d_name}")
                    d_item.setData(0, Qt.ItemDataRole.UserRole, did)
                    d_depth = self.depth_cache.get(did, 0)
                    d_cnt = len(self.dam_daughters_map.get(did, []))
                    d_act = " [供用中]" if bool(self.dams_map.get(did, {}).get("is_active", 0)) else ""
                    d_item.setText(1, f"深さ:{d_depth} (直仔:{d_cnt}){d_act}")

                    add_child_dams(d_item, did)

            add_child_dams(root_item, root_id)

            # フィルター処理
            if filter_text:
                def matches_filter(item: QTreeWidgetItem) -> bool:
                    t0 = item.text(0).lower()
                    if filter_text in t0:
                        return True
                    for i in range(item.childCount()):
                        if matches_filter(item.child(i)):
                            return True
                    return False

                if not matches_filter(root_item):
                    continue

            target_tree.addTopLevelItem(root_item)
            root_item.setExpanded(True)

            if is_active_fam:
                active_count += 1
            else:
                extinct_count += 1

        self.lbl_active_header.setText(f"🌸 存続族 ({active_count}族)")
        self.lbl_extinct_header.setText(f"⚪ 断絶族 ({extinct_count}族)")

        # 初回選択
        if not self.current_selected_horse_id:
            if self.tree_active.topLevelItemCount() > 0:
                first_item = self.tree_active.topLevelItem(0)
                self.tree_active.setCurrentItem(first_item)
                hid = first_item.data(0, Qt.ItemDataRole.UserRole)
                if hid:
                    self._select_dam_family(hid)
            elif self.tree_extinct.topLevelItemCount() > 0:
                first_item = self.tree_extinct.topLevelItem(0)
                self.tree_extinct.setCurrentItem(first_item)
                hid = first_item.data(0, Qt.ItemDataRole.UserRole)
                if hid:
                    self._select_dam_family(hid)

    def _on_search_text_changed(self, text: str) -> None:
        self._populate_menu_trees(text)

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        if not item:
            return
        hid = item.data(0, Qt.ItemDataRole.UserRole)
        if hid:
            self._select_dam_family(hid)

    def _select_dam_family(self, horse_id: int) -> None:
        """選択された繁殖牝馬を起点とする系統樹ツリーを構築しキャンバスに表示"""
        try:
            self.current_selected_horse_id = horse_id
            self.btn_open_carte.setEnabled(True)

            h_info = self.horses_map.get(horse_id)
            if not h_info:
                return

            # 始祖馬と族名の特定
            root_hid = self.dam_to_root_map.get(horse_id, horse_id)
            root_horse = self.horses_map.get(root_hid, {})
            root_name = root_horse.get("name", h_info.get("name", "不明"))
            family_name = f"{root_name}族"

            self.lbl_current_title.setText(f"🌸 ファミリーナンバー系統樹: {family_name}")

            visited_tree: Set[int] = set()
            root_node = self._build_tree_node(
                horse_id,
                depth=0,
                is_root=(horse_id == root_hid),
                family_name=family_name,
                visited=visited_tree,
            )
            self.canvas_widget.set_tree_root(root_node)
            self.scroll_area.horizontalScrollBar().setValue(0)
            self.scroll_area.verticalScrollBar().setValue(0)
        except Exception as e:
            print(f"⚠️ [DamLineageWidget] 系統樹選択エラー: {e}", file=sys.stderr)
            traceback.print_exc()

    def _build_tree_node(
        self,
        hid: int,
        depth: int,
        is_root: bool,
        family_name: str,
        visited: Optional[Set[int]] = None,
    ) -> DamTreeNode:
        """指定した繁殖牝馬から再帰的にDamTreeNodeツリーを構築 (循環参照防止付き)"""
        if visited is None:
            visited = set()
        visited.add(hid)

        h_data = self.horses_map.get(hid, {})
        d_data = self.dams_map.get(hid, {})

        # 馬場・距離適性の安全な算出
        surface_str = "芝"
        dist_min = 1200
        dist_max = 2400
        if h_data:
            try:
                h_obj = Horse.from_row(h_data)
                surf_val = h_obj.surface_aptitude
                surface_str = "芝" if surf_val == "turf" else ("ダート" if surf_val == "dirt" else "芝/ダ")
                dist_min, dist_max = h_obj.get_distance_aptitude()
            except Exception:
                pass

        is_active = bool(d_data.get("is_active", 0))
        h_name = h_data.get("name", "不明")

        daughters_cnt = len(self.dam_daughters_map.get(hid, []))

        node = DamTreeNode(
            horse_id=hid,
            name=h_name,
            birth_year=h_data.get("birth_year", 0),
            career_starts=h_data.get("career_starts", 0),
            career_wins=h_data.get("career_wins", 0),
            g1_wins=h_data.get("g1_wins", 0),
            surface_str=surface_str,
            dist_min=dist_min,
            dist_max=dist_max,
            is_active=is_active,
            is_root=is_root,
            family_name=family_name,
            depth_from_root=depth,
            progeny_dams_count=daughters_cnt,
        )

        for daughter_id in self.dam_daughters_map.get(hid, []):
            if daughter_id in visited or daughter_id not in self.horses_map:
                continue
            child_node = self._build_tree_node(
                daughter_id,
                depth=depth + 1,
                is_root=False,
                family_name=family_name,
                visited=visited,
            )
            node.children.append(child_node)

        return node

    def _on_canvas_node_clicked(self, horse_id: int) -> None:
        """キャンバス内の馬をクリックした際に繁殖牝馬カルテを開く"""
        self._open_dam_detail(horse_id)

    def _on_open_current_carte_clicked(self) -> None:
        if self.current_selected_horse_id:
            self._open_dam_detail(self.current_selected_horse_id)

    def _open_dam_detail(self, horse_id: int) -> None:
        """繁殖牝馬カルテ（または競走馬詳細）ダイアログを表示"""
        try:
            dlg = DamDetailDialog(self.db, dam_horse_id=horse_id, parent=self)
            dlg.exec()
        except Exception:
            try:
                dlg = HorseDetailDialog(self.db, horse_id=horse_id, parent=self)
                dlg.exec()
            except Exception as e2:
                print(f"⚠️ [DamLineageWidget] ダイアログ表示エラー: {e2}", file=sys.stderr)


class LineageView(QWidget):
    """
    系統樹総合ビュー
    - 上部サブタブ:
      1. 🐴 種牡馬（サイヤーライン [系]）
      2. 🌸 繁殖牝馬（ファミリーナンバー [族]）
    """

    def __init__(self, db: Optional[Database] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db or get_db()
        self._loaded = False
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
                padding: 7px 16px;
            }
        """)

        # 1. 種牡馬タブ（サイヤーライン）
        self.tab_sires = SireLineageWidget(self.db, parent=self)
        self.main_tabs.addTab(self.tab_sires, "🐴 種牡馬 (サイヤーライン [系])")

        # 2. 繁殖牝馬タブ（ファミリーナンバー [族]）
        self.tab_dams = DamLineageWidget(self.db, parent=self)
        self.main_tabs.addTab(self.tab_dams, "🌸 繁殖牝馬 (ファミリーナンバー [族])")

        self.main_tabs.currentChanged.connect(self._on_subtab_changed)

        main_layout.addWidget(self.main_tabs)

    def _on_subtab_changed(self, index: int) -> None:
        """サブタブ切り替え時のリフレッシュ"""
        try:
            if index == 0:
                if not self.tab_sires.root_sire_ids:
                    self.tab_sires.refresh_data()
            elif index == 1:
                if not self.tab_dams.root_dam_ids:
                    self.tab_dams.refresh_data()
        except Exception as e:
            print(f"⚠️ [LineageView] サブタブ切り替えエラー index={index}: {e}", file=sys.stderr)
            traceback.print_exc()

    def ensure_loaded(self) -> None:
        """タブ表示時の遅延ロード"""
        if not self._loaded:
            self.refresh_all()
            self._loaded = True

    def refresh_all(self) -> None:
        """全データの更新"""
        try:
            self.tab_sires.refresh_data()
        except Exception as e:
            print(f"⚠️ [LineageView] tab_sires refresh エラー: {e}", file=sys.stderr)
            traceback.print_exc()

        try:
            self.tab_dams.refresh_data()
        except Exception as e:
            print(f"⚠️ [LineageView] tab_dams refresh エラー: {e}", file=sys.stderr)
            traceback.print_exc()

