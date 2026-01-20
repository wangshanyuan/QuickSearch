import os
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QListWidget, QFileDialog, 
                             QFrame, QAbstractItemView)
from PyQt5.QtCore import Qt, pyqtSignal

class SettingsDialog(QDialog):
    def __init__(self, current_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setFixedWidth(450)
        self.config = current_config
        self.new_paths = list(self.config.get("search_paths", []))
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # --- 快捷键设置部分 ---
        hotkey_group = QVBoxLayout()
        hotkey_label = QLabel("唤起快捷键 (例如: option+space, cmd+f):")
        hotkey_label.setStyleSheet("font-weight: bold; color: #555;")
        self.hotkey_input = QLineEdit(self.config.get("hotkey", "option+space"))
        self.hotkey_input.setPlaceholderText("请输入快捷键组合...")
        self.hotkey_input.setStyleSheet("padding: 8px; border: 1px solid #ddd; border-radius: 4px;")
        hotkey_group.addWidget(hotkey_label)
        hotkey_group.addWidget(self.hotkey_input)
        layout.addLayout(hotkey_group)

        # --- 搜索路径管理部分 ---
        path_group = QVBoxLayout()
        path_label = QLabel("索引目录列表:")
        path_label.setStyleSheet("font-weight: bold; color: #555;")
        path_group.addWidget(path_label)

        self.path_list = QListWidget()
        self.path_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.path_list.addItems(self.new_paths)
        self.path_list.setStyleSheet("""
            QListWidget { border: 1px solid #ddd; border-radius: 4px; background: #f9f9f9; }
            QListWidget::item { padding: 5px; }
            QListWidget::item:selected { background: #007AFF; color: white; }
        """)
        path_group.addWidget(self.path_list)

        # 路径操作按钮
        path_btns = QHBoxLayout()
        add_btn = QPushButton("+ 添加目录")
        del_btn = QPushButton("- 删除选中")
        add_btn.clicked.connect(self._add_path)
        del_btn.clicked.connect(self._remove_path)
        path_btns.addWidget(add_btn)
        path_btns.addWidget(del_btn)
        path_btns.addStretch()
        path_group.addLayout(path_btns)
        
        layout.addLayout(path_group)

        # --- 分割线 ---
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # --- 底部确认按钮 ---
        bottom_btns = QHBoxLayout()
        save_btn = QPushButton("保存设置")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        
        bottom_btns.addStretch()
        bottom_btns.addWidget(cancel_btn)
        bottom_btns.addWidget(save_btn)
        layout.addLayout(bottom_btns)

    def _add_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择要索引的目录", os.path.expanduser("~"))
        if path and path not in self.new_paths:
            self.new_paths.append(path)
            self.path_list.addItem(path)

    def _remove_path(self):
        for item in self.path_list.selectedItems():
            path = item.text()
            if path in self.new_paths:
                self.new_paths.remove(path)
            self.path_list.takeItem(self.path_list.row(item))

    def get_config(self):
        """返回修改后的配置字典"""
        return {
            "hotkey": self.hotkey_input.text().strip().lower(),
            "search_paths": self.new_paths
        }