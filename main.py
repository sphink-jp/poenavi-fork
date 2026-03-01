import sys
import os
import logging

# srcディレクトリへのパスを通す (VSCodeなどで実行した際のパスずれ対策)
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# exe実行時はログをファイルに出力
if getattr(sys, 'frozen', False):
    log_path = os.path.join(os.path.dirname(sys.executable), "poenavi.log")
else:
    log_path = os.path.join(current_dir, "poenavi.log")

logging.basicConfig(
    filename=log_path,
    level=logging.DEBUG,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
    encoding="utf-8",
)

# printをログファイルにもリダイレクト
class _LogWriter:
    def __init__(self, original):
        self._orig = original
    def write(self, msg):
        if msg.strip():
            logging.info(msg.rstrip())
        if self._orig:
            self._orig.write(msg)
    def flush(self):
        if self._orig:
            self._orig.flush()

sys.stdout = _LogWriter(sys.stdout)
sys.stderr = _LogWriter(sys.stderr)

from PySide6.QtWidgets import QApplication
from src.ui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
