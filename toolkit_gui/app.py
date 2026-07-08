'''toolkit_gui.app - entry point for the desktop GUI shell.'''

import sys

from PySide6.QtWidgets import QApplication

from toolkit_gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
