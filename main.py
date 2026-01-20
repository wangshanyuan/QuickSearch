#main.py
import sys
import os
import time
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit, 
    QFrame, QSizeGrip, QHBoxLayout, QLabel, 
    QGraphicsDropShadowEffect, QDialog
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QEvent
from PyQt5.QtGui import QColor

# 导入自定义模块
from window_behavior import FramelessWindowMixin
from ui_widgets import SearchResultWidget, SearchResultItem
from search_manager import SearchManager
from global_hotkey import GlobalHotKey
from status_bar import StatusBar
from config_manager import ConfigManager
from index_manager import IndexManager
from settings_ui import SettingsDialog

class IndexSearchWorker(QThread):
    """异步搜索线程：从 SQLite 索引查询"""
    res_signal = pyqtSignal(list)

    def __init__(self, index_mgr, search_mgr):
        super().__init__()
        self.index_mgr = index_mgr
        self.search_mgr = search_mgr
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        all_raw_results = []
        seen_paths = set()
        
        # 1. 构建查询列表
        # 如果是 OR 模式，查询列表就是 or_kws；如果是 AND，就用第一个词
        search_targets = []
        if self.search_mgr.or_kws:
            search_targets = self.search_mgr.or_kws
        elif self.search_mgr.and_kws:
            search_targets = [self.search_mgr.and_kws[0]]
        else:
            # 没关键词时，捞取最近更新的 1000 条（SQL 默认逻辑）
            search_targets = [""]

        # 2. 循环执行 SQL 捞取并去重
        for kw in search_targets:
            if self._stop: break
            # 每个关键词去库里捞 1000 条
            res = self.index_mgr.search_name(kw, max_results=1000)
            for item in res:
                if item['path'] not in seen_paths:
                    all_raw_results.append(item)
                    seen_paths.add(item['path'])

        # 3. 在 Python 端进行最终的逻辑精筛（处理 NOT、EXT 等）
        batch = []
        for item in all_raw_results:
            if self._stop: break
            if self.search_mgr.is_match(item["name"]):
                batch.append(item)
                if len(batch) >= 50:
                    self.res_signal.emit(batch)
                    batch = []
        
        if batch and not self._stop:
            self.res_signal.emit(batch)

class SearchApp(QWidget, FramelessWindowMixin):
    def __init__(self):
        super().__init__()
        # 1. 配置管理
        self.config_mgr = ConfigManager()
        self.config = self.config_mgr.load_config()
        
        # 2. 核心逻辑 (确保只在此处初始化一次)
        self.mgr = SearchManager()
        self.index_mgr = IndexManager(
            search_paths=self.config.get("search_paths", [os.path.expanduser("~")]),
            show_hidden=self.config.get("show_hidden", False)
        )
        self.index_mgr.start_monitoring()

        # 3. UI 布局与行为
        self._init_window_behavior()
        self._setup_ui()
        
        # 4. 线程管理
        self.worker = None
        self.rebuild_thread = None
        
        # 5. 全局热键
        hotkey_str = self.config.get("hotkey", "option+space")
        self.hotkey_thread = GlobalHotKey(hotkey_str, self.toggle_window)
        self.hotkey_thread.start()

        # 6. 搜索防抖
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._start_search)

        # 窗口属性
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def _setup_ui(self):
        """初始化界面布局"""
        self.resize(700, 450)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        self.container = QFrame()
        self.container.setStyleSheet("QFrame { background: white; border-radius: 12px; border: 1px solid #d0d0d0; }")
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setYOffset(10)
        self.container.setGraphicsEffect(shadow)
        main_layout.addWidget(self.container)
        
        v = QVBoxLayout(self.container)
        self.input = QLineEdit()
        self.input.setPlaceholderText("输入文件名，支持 !排除 .后缀 |或者...")
        self.input.setStyleSheet("QLineEdit { font-size: 18px; border: none; padding: 15px; background: transparent; }")
        self.input.textChanged.connect(lambda: self.search_timer.start(250))
        self.input.installEventFilter(self)
        v.addWidget(self.input)
        
        self.results = SearchResultWidget()
        self.results.open_signal.connect(lambda p: subprocess.run(["open", p]))
        self.results.finder_signal.connect(lambda p: subprocess.run(["open", "-R", p]))
        v.addWidget(self.results)
        
        b = QHBoxLayout()
        self.status_label = QLabel("已加载索引")
        self.status_label.setStyleSheet("color: #888; font-size: 11px; padding: 5px;")
        b.addWidget(self.status_label)
        b.addStretch()
        self.grip = QSizeGrip(self.container)
        b.addWidget(self.grip)
        v.addLayout(b)

    def toggle_window(self):
        if self.isVisible():
            self.hide()
        else:
            self.show_and_focus()

    def show_and_focus(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()
        self.input.selectAll()

    def _start_search(self):
        query = self.input.text().strip()
        
        # 停止旧线程，防止结果串扰
        if self.worker and self.worker.isRunning():
            self.worker.res_signal.disconnect()
            self.worker.stop()

        self.results.clear()
        if not query:
            self.status_label.setText("Ready")
            return
        
        self.status_label.setText("搜索中...")
        self.mgr.set_query(query)
        self.worker = IndexSearchWorker(self.index_mgr, self.mgr)
        self.worker.res_signal.connect(self._add_res_batch)
        self.worker.start()

    def _add_res_batch(self, items):
        # 1. 暂时关闭排序，提高插入效率并防止列表跳动
        self.results.setSortingEnabled(False)
        
        for i in items:
            sz = self._fmt_size(i['size'])
            tm = time.strftime("%Y-%m-%d", time.localtime(i['mtime']))
            pd = os.path.dirname(i['path']).replace(os.path.expanduser("~"), "~")
            item = SearchResultItem(i['name'], sz, tm, pd, i['path'], i['mtime'])
            self.results.addTopLevelItem(item)
            
        # 2. 重新开启排序，并指定按第 2 列（mtime 隐藏列，索引从 0 开始）降序
        # 注意：在 SearchResultItem 中，我们重写了 __lt__，它会根据数值进行逻辑排序
        self.results.setSortingEnabled(True)
        self.results.sortItems(0, Qt.DescendingOrder) # 这里排第 0 列其实是调用 item 的 __lt__
        
        self.status_label.setText(f"找到 {self.results.topLevelItemCount()} 个结果")

    def _fmt_size(self, s):
        for u in ['B','K','M','G']:
            if s < 1024: return f"{int(s)}{u}"
            s /= 1024
        return f"{s:.1f}T"

    def trigger_rebuild(self):
        """异步重建索引"""
        if self.rebuild_thread and self.rebuild_thread.isRunning():
            return
            
        self.status_label.setText("正在全量扫描磁盘...")
        self.rebuild_thread = QThread()
        # 这里的逻辑建议封装进 IndexManager
        self.rebuild_thread.run = self.index_mgr.rebuild_index
        self.rebuild_thread.finished.connect(lambda: self.status_label.setText("索引更新完成"))
        self.rebuild_thread.start()

    def safe_quit(self):
        print("清理资源退出...")
        self.index_mgr.stop_monitoring()
        if self.hotkey_thread:
            self.hotkey_thread.stop()
        QApplication.quit()

    def eventFilter(self, obj, event):
        if obj == self.input and event.type() == QEvent.KeyPress:
            key = event.key()
            mods = event.modifiers()
            
            # 适配 macOS：Meta 对应 Cmd，Control 有时也会映射到 Cmd
            is_cmd = bool(mods & Qt.MetaModifier) or bool(mods & Qt.ControlModifier)

            # 拦截复制
            if is_cmd and key == Qt.Key_C:
                selected = self.results.selectedItems()
                if selected:
                    # 关键：先让列表执行复制逻辑
                    self.results._copy_batch_to_clipboard()
                    # 然后更新状态栏，并返回 True 彻底截断该事件
                    self.status_label.setText(f"已复制 {len(selected)} 个文件实体")
                    return True 
            
            # 拦截删除 (Cmd+Backspace)
            if is_cmd and key == Qt.Key_Backspace:
                if self.results.selectedItems():
                    self.results._trash_batch()
                    return True

            # 方向键下移焦点
            if key == Qt.Key_Down:
                if self.results.topLevelItemCount() > 0:
                    self.results.setFocus()
                    if not self.results.selectedItems():
                        self.results.setCurrentItem(self.results.topLevelItem(0))
                    return True
                    
        return super().eventFilter(obj, event)

    def changeEvent(self, event):
        if event.type() == QEvent.ActivationChange and not self.isActiveWindow():
            self.hide()
        super().changeEvent(event)
    def open_settings(self):
        from settings_ui import SettingsDialog
        # 传入当前配置打开对话框
        dialog = SettingsDialog(self.config, self)
        if dialog.exec_() == QDialog.Accepted:
            new_config = dialog.get_config()
            
            # 1. 检查是否有变动
            if new_config == self.config:
                return

            # 2. 保存到本地文件
            self.config_mgr.save_config(new_config)
            
            # 3. 如果路径变了，提示用户并重启监控
            if new_config["search_paths"] != self.config["search_paths"]:
                self.index_mgr.stop_monitoring()
                self.index_mgr.search_paths = new_config["search_paths"]
                self.index_mgr.start_monitoring()
                # 自动触发一次增量/全量扫描
                self.trigger_rebuild()

            # 4. 如果快捷键变了，重启热键线程
            if new_config["hotkey"] != self.config["hotkey"]:
                self.hotkey_thread.stop()
                self.hotkey_thread = GlobalHotKey(new_config["hotkey"], self.toggle_window)
                self.hotkey_thread.start()

            # 更新内存中的配置
            self.config = new_config
            self.status_label.setText("设置已保存，正在更新索引...")

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    window = SearchApp()
    
    # 传入 window 实例，让托盘能拿到系统图标样式
    status_bar = StatusBar(window) 
    
    # 连接信号
    status_bar.show_window.connect(window.show_and_focus)
    status_bar.show_settings.connect(window.open_settings)
    status_bar.rebuild_index.connect(window.trigger_rebuild)
    status_bar.quit_app.connect(window.safe_quit)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()