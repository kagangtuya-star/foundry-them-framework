from __future__ import annotations

import sys
from PyQt6 import QtWidgets

try:
    from .gui import ThemeInstallerWindow
except ImportError:  # 打包为独立可执行时使用绝对导入
    from installer_app.gui import ThemeInstallerWindow


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = ThemeInstallerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
