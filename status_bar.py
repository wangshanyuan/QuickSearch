from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QStyle
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QIcon

class StatusBar(QObject):
    show_window = pyqtSignal()
    show_settings = pyqtSignal()
    rebuild_index = pyqtSignal()
    quit_app = pyqtSignal()

    def __init__(self, app_instance):
        super().__init__()
        self.tray = QSystemTrayIcon(self)
        
        # 使用系统内置的标准“搜索/查看”图标，关联性强且稳定
        icon = app_instance.style().standardIcon(QStyle.SP_FileDialogContentsView)
        self.tray.setIcon(icon)
        self.tray.setToolTip("文件快速搜索")
        
        self._create_menu()
        self.tray.show()

    def _create_menu(self):
        menu = QMenu()
        
        show_action = menu.addAction("显示搜索窗口")
        show_action.triggered.connect(self.show_window.emit)
        
        menu.addSeparator()
        
        settings_action = menu.addAction("设置...")
        settings_action.triggered.connect(self.show_settings.emit)
        
        rebuild_action = menu.addAction("重新构建索引")
        rebuild_action.triggered.connect(self.rebuild_index.emit)
        
        menu.addSeparator()
        
        quit_action = menu.addAction("退出程序")
        quit_action.triggered.connect(self.quit_app.emit)
        
        self.tray.setContextMenu(menu)