"""
ミニマップ領域のスクリーンキャプチャ
QScreen.grabWindow() でゲーム画面からミニマップ部分を切り出す。
WSL2環境ではWindows側のゲーム画面をキャプチャできないため、
クリップボード経由のフォールバックも用意。
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, QTimer, QRect, Signal
from PySide6.QtGui import QImage, QGuiApplication, QClipboard


def qimage_to_numpy(qimage: QImage):
    """QImage → numpy配列 (BGR) に変換"""
    qimage = qimage.convertToFormat(QImage.Format.Format_RGB32)
    width = qimage.width()
    height = qimage.height()
    if width == 0 or height == 0:
        return None

    ptr = qimage.bits()
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape((height, width, 4))
    # BGRA → BGR
    return arr[:, :, :3].copy()


class ScreenCapture(QObject):
    """ミニマップ領域をキャプチャしてnumpy配列として送出"""

    capture_ready = Signal(np.ndarray)  # BGR numpy配列

    def __init__(self, parent=None):
        super().__init__(parent)
        self._delay_timer = QTimer(self)
        self._delay_timer.setSingleShot(True)
        self._delay_timer.timeout.connect(self._do_capture)
        self._minimap_rect = QRect(0, 0, 300, 300)
        self._delay_ms = 3000

    def set_minimap_rect(self, x: int, y: int, w: int, h: int):
        """キャプチャするミニマップ領域を設定（画面上の絶対座標）"""
        self._minimap_rect = QRect(x, y, w, h)

    def set_delay(self, ms: int):
        """キャプチャ遅延を設定（ゾーン変更後の待ち時間）"""
        self._delay_ms = max(0, ms)

    def schedule_capture(self):
        """遅延付きキャプチャをスケジュール（既存のスケジュールはキャンセル）"""
        self._delay_timer.stop()
        if self._delay_ms > 0:
            self._delay_timer.start(self._delay_ms)
        else:
            self._do_capture()

    def cancel(self):
        """スケジュール済みのキャプチャをキャンセル"""
        self._delay_timer.stop()

    def _do_capture(self):
        """画面キャプチャを実行"""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        pixmap = screen.grabWindow(
            0,
            self._minimap_rect.x(),
            self._minimap_rect.y(),
            self._minimap_rect.width(),
            self._minimap_rect.height(),
        )

        if pixmap.isNull():
            return

        image = pixmap.toImage()
        arr = qimage_to_numpy(image)
        if arr is not None:
            self.capture_ready.emit(arr)

    def capture_from_clipboard(self):
        """クリップボードの画像からキャプチャ（WSL2フォールバック用）"""
        clipboard = QGuiApplication.clipboard()
        image = clipboard.image()
        if image.isNull():
            return

        arr = qimage_to_numpy(image)
        if arr is not None:
            self.capture_ready.emit(arr)
