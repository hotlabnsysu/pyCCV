import multiprocessing
import sys

from PySide6.QtWidgets import QApplication

from ui.app import PyCCVMainWindow
from ui.style import apply_theme


def main():
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    apply_theme(app)
    window = PyCCVMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
