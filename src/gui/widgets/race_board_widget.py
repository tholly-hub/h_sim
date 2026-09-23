"""
競馬場LED電光着順掲示板ウィジェット (RaceBoardWidget)
添付実写掲示板スタイル:
- 競馬場名・レース番号・「確定」ランプ
- 1〜5着 (ローマ数字/着順丸マーク・馬番・着差)
- 馬場（芝/ダート・良/稍/重/不良）
- 走破タイム (レコード時は赤文字「R」)
- 上がり4F・3Fタイム
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class RaceBoardWidget(QFrame):
    """競馬場本馬場LED電光着順掲示板ウィジェット"""

    ROMAN_NUMS = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ"]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #0b111e;
                border: 3px solid #1e293b;
                border-radius: 8px;
            }
        """)
        self.setFixedWidth(280)
        self.setMinimumHeight(440)
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(6)

        # 1. 最上段: 競馬場名 + レース番号 + 「確定」枠
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.lbl_track = QLabel("東京")
        self.lbl_track.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: 500; font-family: 'Helvetica Neue', 'Arial', 'Hiragino Sans', sans-serif;")
        top_bar.addWidget(self.lbl_track)

        self.lbl_race_num = QLabel("9R")
        self.lbl_race_num.setStyleSheet("color: #fbbf24; font-size: 22px; font-weight: normal; font-family: 'Helvetica Neue', 'Arial', 'Hiragino Sans', sans-serif;")
        top_bar.addWidget(self.lbl_race_num)

        top_bar.addStretch()

        self.lbl_kakutei = QLabel(" 確 定 ")
        self.lbl_kakutei.setStyleSheet("""
            color: #64748b;
            background-color: #1e293b;
            border: 2px solid #334155;
            border-radius: 4px;
            font-size: 15px;
            font-weight: bold;
            font-family: 'Helvetica Neue', 'Arial', 'Hiragino Sans', sans-serif;
            padding: 2px 6px;
        """)
        top_bar.addWidget(self.lbl_kakutei)

        main_layout.addLayout(top_bar)

        # 区切り線
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("border-top: 1px solid #1e293b;")
        main_layout.addWidget(sep1)

        # 2. 1〜5着の行表示
        self.rows_orders: List[Dict[str, QLabel]] = []
        for i in range(5):
            r_layout = QHBoxLayout()
            r_layout.setContentsMargins(2, 2, 2, 2)
            r_layout.setSpacing(8)

            # ローマ数字サークル (Ⅰ〜Ⅴ)
            lbl_pos = QLabel(self.ROMAN_NUMS[i])
            lbl_pos.setFixedSize(28, 28)
            lbl_pos.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_pos.setStyleSheet("""
                color: #ffffff;
                background-color: #2563eb;
                border-radius: 14px;
                font-weight: normal;
                font-size: 13px;
                font-family: 'Helvetica Neue', 'Arial', 'Hiragino Sans', sans-serif;
            """)
            r_layout.addWidget(lbl_pos)

            # 馬番 (黄色LEDフォント風 + 暗緑グレースロット)
            lbl_gate = QLabel("--")
            lbl_gate.setFixedWidth(50)
            lbl_gate.setFixedHeight(30)
            lbl_gate.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_gate.setStyleSheet("""
                color: #ffd43b;
                background-color: #18262a;
                border: 1px solid #24363c;
                border-radius: 3px;
                font-size: 19px;
                font-weight: normal;
                font-family: 'Helvetica Neue', 'Arial', 'Hiragino Sans', sans-serif;
            """)
            r_layout.addWidget(lbl_gate)

            # 着差記号 '>'
            lbl_gt = QLabel(">" if i > 0 else " ")
            lbl_gt.setStyleSheet("color: #38bdf8; font-size: 15px; font-weight: normal; font-family: 'Helvetica Neue', 'Arial', 'Hiragino Sans', sans-serif;")
            lbl_gt.setFixedWidth(14)
            lbl_gt.setAlignment(Qt.AlignmentFlag.AlignCenter)
            r_layout.addWidget(lbl_gt)

            # 着差 (黄色テキスト + 暗緑グレースロット)
            lbl_margin = QLabel("-" if i > 0 else "")
            lbl_margin.setFixedHeight(30)
            lbl_margin.setStyleSheet("""
                color: #ffd43b;
                background-color: #18262a;
                border: 1px solid #24363c;
                border-radius: 3px;
                font-size: 13px;
                font-weight: normal;
                font-family: 'Helvetica Neue', 'Arial', 'Hiragino Sans', sans-serif;
                padding-left: 4px;
            """)
            lbl_margin.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            r_layout.addWidget(lbl_margin, stretch=1)

            main_layout.addLayout(r_layout)
            self.rows_orders.append({
                "pos": lbl_pos,
                "gate": lbl_gate,
                "gt": lbl_gt,
                "margin": lbl_margin,
            })

        # 区切り線
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("border-top: 1px solid #1e293b;")
        main_layout.addWidget(sep2)

        # 3. 馬場・天候情報
        cond_layout = QHBoxLayout()
        cond_layout.setSpacing(8)

        self.lbl_surface = QLabel("芝")
        self.lbl_surface.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: 500; font-family: 'Helvetica Neue', 'Arial', 'Hiragino Sans', sans-serif;")
        cond_layout.addWidget(self.lbl_surface)

        self.lbl_condition = QLabel(" 良 ")
        self.lbl_condition.setStyleSheet("""
            color: #ffd43b;
            background-color: #18262a;
            border: 1px solid #24363c;
            border-radius: 3px;
            font-size: 15px;
            font-weight: normal;
            font-family: 'Helvetica Neue', 'Arial', 'Hiragino Sans', sans-serif;
            padding: 1px 6px;
        """)
        cond_layout.addWidget(self.lbl_condition)

        cond_layout.addStretch()
        main_layout.addLayout(cond_layout)

        # 4. 走破タイム (レコード時は赤文字「R」)
        time_layout = QHBoxLayout()
        lbl_time_tag = QLabel("タイム")
        lbl_time_tag.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 500; font-family: 'Helvetica Neue', 'Arial', 'Hiragino Sans', sans-serif;")
        time_layout.addWidget(lbl_time_tag)

        self.lbl_record_mark = QLabel("R")
        self.lbl_record_mark.setStyleSheet("""
            color: #ef4444;
            background-color: #450a0a;
            border: 1px solid #ef4444;
            border-radius: 3px;
            font-size: 15px;
            font-weight: bold;
            font-family: 'Arial', sans-serif;
            padding: 1px 5px;
            margin-right: 2px;
        """)
        self.lbl_record_mark.setVisible(False)
        time_layout.addWidget(self.lbl_record_mark)

        self.lbl_time_val = QLabel("--:--.-")
        self.lbl_time_val.setStyleSheet("""
            color: #ffd43b;
            background-color: #18262a;
            border: 1px solid #24363c;
            border-radius: 3px;
            font-size: 19px;
            font-weight: normal;
            font-family: 'Helvetica Neue', 'Arial', 'Hiragino Sans', sans-serif;
            padding: 2px 6px;
        """)
        time_layout.addWidget(self.lbl_time_val)
        time_layout.addStretch()
        main_layout.addLayout(time_layout)

        # 5. 上がり4F / 3F
        f4_layout = QHBoxLayout()
        lbl_f4_tag = QLabel("4F")
        lbl_f4_tag.setFixedWidth(40)
        lbl_f4_tag.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 500; font-family: 'Helvetica Neue', 'Arial', 'Hiragino Sans', sans-serif;")
        f4_layout.addWidget(lbl_f4_tag)

        self.lbl_f4_val = QLabel("--.-")
        self.lbl_f4_val.setStyleSheet("""
            color: #ffd43b;
            background-color: #18262a;
            border: 1px solid #24363c;
            border-radius: 3px;
            font-size: 16px;
            font-weight: normal;
            font-family: 'Helvetica Neue', 'Arial', 'Hiragino Sans', sans-serif;
            padding: 1px 6px;
        """)
        f4_layout.addWidget(self.lbl_f4_val)
        f4_layout.addStretch()
        main_layout.addLayout(f4_layout)

        f3_layout = QHBoxLayout()
        lbl_f3_tag = QLabel("3F")
        lbl_f3_tag.setFixedWidth(40)
        lbl_f3_tag.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 500; font-family: 'Helvetica Neue', 'Arial', 'Hiragino Sans', sans-serif;")
        f3_layout.addWidget(lbl_f3_tag)

        self.lbl_f3_val = QLabel("--.-")
        self.lbl_f3_val.setStyleSheet("""
            color: #ffd43b;
            background-color: #18262a;
            border: 1px solid #24363c;
            border-radius: 3px;
            font-size: 16px;
            font-weight: normal;
            font-family: 'Helvetica Neue', 'Arial', 'Hiragino Sans', sans-serif;
            padding: 1px 6px;
        """)
        f3_layout.addWidget(self.lbl_f3_val)
        f3_layout.addStretch()
        main_layout.addLayout(f3_layout)

    def set_confirmed(self, confirmed: bool) -> None:
        """確定ランプの点灯・消灯を切り替え"""
        if confirmed:
            self.lbl_kakutei.setText(" 確 定 ")
            self.lbl_kakutei.setStyleSheet("""
                color: #ffffff;
                background-color: #dc2626;
                border: 2px solid #ef4444;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
                padding: 2px 6px;
            """)
        else:
            self.lbl_kakutei.setText(" 確 定 ")
            self.lbl_kakutei.setStyleSheet("""
                color: #64748b;
                background-color: #1e293b;
                border: 2px solid #334155;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
                padding: 2px 6px;
            """)

    def reset_board(self, track_name: str, race_number: int, surface_jp: str) -> None:
        """着順掲示板をレース前・ゴール前の初期化状態（着順・タイム未表示）にする"""
        self.set_race_board_data(
            track_name=track_name,
            race_number=race_number,
            surface_jp=surface_jp,
            top5_horses=[],
            finish_time=0.0,
            is_record=False,
            f3_time=None,
            f4_time=None,
            is_confirmed=False,
        )

    def set_race_board_data(
        self,
        track_name: str,
        race_number: int,
        surface_jp: str,
        top5_horses: List[Dict[str, Any]],
        finish_time: float,
        is_record: bool = False,
        f3_time: Optional[float] = None,
        f4_time: Optional[float] = None,
        is_confirmed: bool = True,
    ) -> None:
        """着順掲示板のデータを更新（is_confirmed=Falseの場合はレース中の未確定・未表示ブランク）"""
        self.lbl_track.setText(track_name[:2])
        self.lbl_race_num.setText(f"{race_number}R")
        self.lbl_surface.setText(surface_jp)
        self.set_confirmed(is_confirmed)

        # 走破タイムフォーマット (確定時のみ表示)
        if is_confirmed and finish_time > 0:
            m = int(finish_time // 60)
            s = finish_time - (m * 60)
            self.lbl_time_val.setText(f"{m}.{s:04.1f}" if m > 0 else f"{s:04.1f}")
            self.lbl_record_mark.setVisible(is_record)
        else:
            self.lbl_time_val.setText("--:--.-")
            self.lbl_record_mark.setVisible(False)

        # 上がり4F / 3F (確定時のみ表示)
        if is_confirmed and f3_time and f3_time > 0:
            self.lbl_f3_val.setText(f"{f3_time:.1f}")
        else:
            self.lbl_f3_val.setText("--.-")

        if is_confirmed and f4_time and f4_time > 0:
            self.lbl_f4_val.setText(f"{f4_time:.1f}")
        elif is_confirmed and f3_time and f3_time > 0:
            self.lbl_f4_val.setText(f"{f3_time + 12.1:.1f}")
        else:
            self.lbl_f4_val.setText("--.-")

        # 1〜5着 (確定時のみ馬番・着差を表示、未確定時はブランク--)
        for i in range(5):
            row_widgets = self.rows_orders[i]
            if is_confirmed and i < len(top5_horses):
                h = top5_horses[i]
                gate_num = h.get("gate_number", i + 1)
                margin_str = h.get("margin", "")
                if i == 0:
                    margin_str = ""  # 1着は着差なし
                row_widgets["gate"].setText(str(gate_num))
                row_widgets["margin"].setText(margin_str)
                row_widgets["gt"].setText(">" if (i > 0 and margin_str) else " ")
            else:
                row_widgets["gate"].setText("--")
                row_widgets["margin"].setText("-")
                row_widgets["gt"].setText(" ")
