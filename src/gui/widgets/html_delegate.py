"""
HTMLリッチテキスト描画用デリゲート (HTMLDelegate)
- QTableWidgetなどで特定文字（レコードRマーク等）のみを赤字や装飾して描画する汎用デリゲート
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextDocument, QAbstractTextDocumentLayout
from PyQt6.QtWidgets import QStyledItemDelegate, QStyle


class HTMLDelegate(QStyledItemDelegate):
    """HTML装飾テキスト（赤字Rマークやカラータグ等）を描画するデリゲート"""

    def paint(self, painter, option, index):
        options = option
        self.initStyleOption(options, index)
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if text and ("<span" in text or "<font" in text or "<b>" in text):
            painter.save()
            # 背景色の描画（選択時またはセル背景）
            if options.state & QStyle.StateFlag.State_Selected:
                painter.fillRect(options.rect, options.palette.highlight())
            elif options.backgroundBrush.style() != Qt.BrushStyle.NoBrush:
                painter.fillRect(options.rect, options.backgroundBrush)

            doc = QTextDocument()
            doc.setDefaultFont(options.font)
            doc.setHtml(text)

            painter.translate(options.rect.topLeft())
            # 垂直中央揃え
            y_offset = max(0.0, (options.rect.height() - doc.size().height()) / 2.0)
            painter.translate(4.0, y_offset)  # 少しインセット

            ctx = QAbstractTextDocumentLayout.PaintContext()
            doc.documentLayout().draw(painter, ctx)
            painter.restore()
        else:
            super().paint(painter, option, index)
