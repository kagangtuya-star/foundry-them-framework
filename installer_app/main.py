from __future__ import annotations

import sys
from PyQt6 import QtWidgets

from .gui import ThemeInstallerWindow


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = ThemeInstallerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
