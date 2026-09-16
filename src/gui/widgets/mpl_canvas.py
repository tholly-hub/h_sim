"""
Matplotlib Canvas 埋め込みウィジェット
ダークテーマ対応、時系列推移・能力分布の描画
"""

from __future__ import annotations

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QSizePolicy, QWidget


class MplCanvas(FigureCanvas):
    """PyQt6 埋め込み用 Matplotlib キャンバス"""

    def __init__(self, parent: QWidget | None = None, width: float = 6.0, height: float = 4.0, dpi: int = 100):
        # 日本語フォント設定（Mac / Win / Linux 両対応）
        plt.rcParams["font.sans-serif"] = ["Hiragino Sans", "Hiragino Kaku Gothic ProN", "Yu Gothic", "Meiryo", "DejaVu Sans", "sans-serif"]
        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["axes.unicode_minus"] = False

        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor="#161b26")
        self.axes = self.fig.add_subplot(111)
        self.axes.set_facecolor("#12161f")

        # 軸やテキストの色をダークテーマ用に調整
        self._apply_dark_theme()

        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.updateGeometry()

    def _apply_dark_theme(self) -> None:
        """グラフの文字色・軸色をダークテーマへ調整"""
        self.axes.tick_params(colors="#94a3b8", labelsize=10)
        self.axes.xaxis.label.set_color("#cbd5e1")
        self.axes.yaxis.label.set_color("#cbd5e1")
        self.axes.title.set_color("#f8fafc")
        for spine in self.axes.spines.values():
            spine.set_color("#334155")
        self.axes.grid(True, linestyle="--", alpha=0.3, color="#475569")

    def clear(self) -> None:
        """グラフをクリアして再初期化"""
        self.axes.clear()
        self.axes.set_facecolor("#12161f")
        self._apply_dark_theme()
        self.draw()
