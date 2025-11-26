from __future__ import annotations

from pathlib import Path
from typing import Dict

from PyQt6 import QtCore, QtGui, QtWidgets

from . import core


FRAMEWORK_THEMES: Dict[str, Dict[str, str]] = {}


class ThemeInstallerWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FVTT Join Theme Manager")
        self.resize(820, 560)

        self.resource_root = Path(__file__).parent / "resources"
        self.root_path = Path()
        self.config = core.load_tool_config()

        self._build_ui()
        icon_path = self.resource_root / "icon.png"
        if icon_path.exists():
            icon = QtGui.QIcon(str(icon_path))
            self.setWindowIcon(icon)
            app = QtWidgets.QApplication.instance()
            if app:
                app.setWindowIcon(icon)

    def _build_ui(self):
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # path chooser
        path_row = QtWidgets.QHBoxLayout()
        path_row.addWidget(QtWidgets.QLabel("FVTT 根目录:"))
        self.path_combo = QtWidgets.QComboBox()
        self.path_combo.setEditable(True)
        recent = self.config.get("recent_roots", [])
        for item in recent:
            self.path_combo.addItem(item)
        self.path_combo.currentIndexChanged.connect(self.on_recent_selected)
        self.path_combo.lineEdit().editingFinished.connect(self.on_recent_text_changed)
        if recent:
            self.root_path = Path(recent[0])
            self.path_combo.setCurrentText(recent[0])
            QtCore.QTimer.singleShot(0, self.refresh_theme_list)
        path_row.addWidget(self.path_combo, 1)
        browse_btn = QtWidgets.QPushButton("浏览…")
        browse_btn.clicked.connect(self.select_root)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        # buttons
        btn_row = QtWidgets.QHBoxLayout()
        install_btn = QtWidgets.QPushButton("安装框架")
        install_btn.clicked.connect(self.install_framework)
        btn_row.addWidget(install_btn)

        restore_btn = QtWidgets.QPushButton("恢复备份")
        restore_btn.clicked.connect(self.restore_framework)
        btn_row.addWidget(restore_btn)

        import_btn = QtWidgets.QPushButton("导入主题")
        import_btn.clicked.connect(self.import_theme)
        btn_row.addWidget(import_btn)

        export_btn = QtWidgets.QPushButton("导出主题")
        export_btn.clicked.connect(self.export_theme)
        btn_row.addWidget(export_btn)
        pack_btn = QtWidgets.QPushButton("打包主题目录")
        pack_btn.clicked.connect(self.pack_theme)
        btn_row.addWidget(pack_btn)
        video_btn = QtWidgets.QPushButton("附加背景视频")
        video_btn.clicked.connect(self.attach_background_video)
        btn_row.addWidget(video_btn)
        remove_btn = QtWidgets.QPushButton("删除主题")
        remove_btn.clicked.connect(self.remove_theme)
        btn_row.addWidget(remove_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.status_label = QtWidgets.QLabel("尚未选择目录")
        layout.addWidget(self.status_label)

        # theme list
        self.theme_list = QtWidgets.QListWidget()
        layout.addWidget(QtWidgets.QLabel("已安装主题:"))
        layout.addWidget(self.theme_list, 1)

        # log box
        layout.addWidget(QtWidgets.QLabel("操作日志:"))
        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box, 1)

        self.setCentralWidget(central)

    def log(self, message: str):
        self.log_box.appendPlainText(message)
        self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())

    def select_root(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "选择FVTT根目录")
        if not directory:
            return
        self.root_path = Path(directory)
        self.add_recent_path(directory)
        self.refresh_theme_list()
        self.update_marker_status()

    # Helpers
    def _require_root(self) -> Path | None:
        path = Path(self.path_combo.currentText().strip())
        if not path.exists():
            QtWidgets.QMessageBox.warning(self, "提示", "请选择正确的根目录。")
            return None
        self.root_path = path
        return path

    def refresh_theme_list(self):
        self.theme_list.clear()
        path = Path(self.path_combo.currentText().strip())
        if not path.exists():
            return
        mapping = core.discover_themes(path)
        for key, label in mapping.items():
            if key in ("default", "minimal"):
                continue
            item = QtWidgets.QListWidgetItem(f"{key}  —  {label}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, key)
            self.theme_list.addItem(item)
        self.update_marker_status()

    def update_marker_status(self):
        if not self.root_path or not self.root_path.exists():
            self.status_label.setText("尚未选择有效目录")
            return
        info = core.read_marker(self.root_path)
        if info:
            version = info.get("tool_version", "unknown")
            stamp = info.get("installed_at", "")
            self.status_label.setText(f"框架已安装 (版本 {version}) {stamp}")
        else:
            self.status_label.setText("框架未安装")

    def add_recent_path(self, new_path: str):
        if not new_path:
            return
        recent = self.config.setdefault("recent_roots", [])
        if new_path in recent:
            recent.remove(new_path)
        recent.insert(0, new_path)
        del recent[10:]
        self.path_combo.blockSignals(True)
        self.path_combo.clear()
        for item in recent:
            self.path_combo.addItem(item)
        self.path_combo.setCurrentText(new_path)
        self.path_combo.blockSignals(False)
        core.save_tool_config(self.config)

    def on_recent_selected(self, index: int):
        if index < 0:
            return
        text = self.path_combo.itemText(index).strip()
        if text:
            self.root_path = Path(text)
            self.refresh_theme_list()
            self.update_marker_status()
            self.add_recent_path(text)

    def on_recent_text_changed(self):
        text = self.path_combo.currentText().strip()
        if text:
            self.root_path = Path(text)
            self.refresh_theme_list()
            self.update_marker_status()

    def install_framework(self):
        root = self._require_root()
        if not root:
            return
        self.add_recent_path(str(root))
        try:
            core.ensure_simple_theme(root, self.resource_root)
            themes = dict(FRAMEWORK_THEMES)
            themes["simple"] = {"label": "Simple Join", "script": "joinmenu-so-nice/simple/joinmenu.js"}
            core.apply_patches(root, {k: v["label"] for k, v in themes.items()}, {k: v["script"] for k, v in themes.items()})
            self.log(f"框架安装完成 (工具版本 {self.config.get('version', 'unknown')}).")
            self.refresh_theme_list()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "错误", str(exc))
            self.log(f"安装失败: {exc}")

    def restore_framework(self):
        root = self._require_root()
        if not root:
            return
        self.add_recent_path(str(root))
        try:
            core.restore_backups(root)
            self.log("已尝试恢复备份文件。")
            self.refresh_theme_list()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "错误", str(exc))

    def import_theme(self):
        root = self._require_root()
        if not root:
            return
        self.add_recent_path(str(root))
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "选择主题压缩包", filter="ZIP Files (*.zip)")
        if not file_path:
            return
        try:
            core.import_theme(root, Path(file_path))
            self.log(f"已导入主题: {file_path}")
            self.refresh_theme_list()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "错误", str(exc))
            self.log(f"导入失败: {exc}")

    def export_theme(self):
        root = self._require_root()
        if not root:
            return
        self.add_recent_path(str(root))
        item = self.theme_list.currentItem()
        if not item:
            QtWidgets.QMessageBox.information(self, "提示", "请先选择一个主题。")
            return
        theme_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
        mapping = core.discover_themes(root)
        label = mapping.get(theme_id, theme_id)
        dest, _ = QtWidgets.QFileDialog.getSaveFileName(self, "导出为", filter="ZIP Files (*.zip)")
        if not dest:
            return
        try:
            core.export_theme(root, theme_id, label, Path(dest))
            self.log(f"已导出主题 {theme_id} -> {dest}")
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "错误", str(exc))
            self.log(f"导出失败: {exc}")

    def pack_theme(self):
        source_dir = QtWidgets.QFileDialog.getExistingDirectory(self, "选择主题目录")
        if not source_dir:
            return
        source = Path(source_dir)
        theme_id, ok = QtWidgets.QInputDialog.getText(self, "主题 ID", "请输入主题 ID：", text=source.name)
        if not ok or not theme_id.strip():
            return
        theme_id = theme_id.strip()
        dest, _ = QtWidgets.QFileDialog.getSaveFileName(self, "保存为", filter="ZIP Files (*.zip)")
        if not dest:
            return
        try:
            core.pack_external_theme(source, theme_id, Path(dest))
            self.log(f"已打包主题 {theme_id} -> {dest}")
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "错误", str(exc))
            self.log(f"打包失败: {exc}")

    def attach_background_video(self):
        root = self._require_root()
        if not root:
            return
        self.add_recent_path(str(root))
        item = self.theme_list.currentItem()
        if not item:
            QtWidgets.QMessageBox.information(self, "提示", "请先选择一个主题。")
            return
        theme_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "选择 WebM 视频", filter="WebM Files (*.webm)")
        if not file_path:
            return
        try:
            dest = core.set_theme_background_video(root, theme_id, Path(file_path))
            self.log(f"已为 {theme_id} 设置背景视频: {dest}")
            QtWidgets.QMessageBox.information(self, "完成", f"背景视频已复制到 {dest}")
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "错误", str(exc))
            self.log(f"背景视频设置失败: {exc}")

    def remove_theme(self):
        root = self._require_root()
        if not root:
            return
        self.add_recent_path(str(root))
        item = self.theme_list.currentItem()
        if not item:
            QtWidgets.QMessageBox.information(self, "提示", "请先选择一个主题。")
            return
        theme_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if QtWidgets.QMessageBox.question(self, "确认", f"是否删除主题 {theme_id}?") != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            core.remove_theme(root, theme_id)
            self.log(f"已删除主题 {theme_id}")
            self.refresh_theme_list()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "错误", str(exc))
            self.log(f"删除失败: {exc}")
