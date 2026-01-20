# ui_widgets.py
import os
from PyQt5.QtWidgets import (QTreeWidget, QTreeWidgetItem, QHeaderView, 
                             QStyledItemDelegate, QMenu, QApplication, QStyle, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal, QUrl, QMimeData, QRectF
from PyQt5.QtGui import QColor, QPainter, QPainterPath
from Foundation import NSFileManager, NSURL

class ModernDelegate(QStyledItemDelegate):
    """美化版委托：实现圆角高亮和中间省略"""
    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. 绘制背景
        if option.state & QStyle.State_Selected:
            # 焦点在列表时为蓝色，失焦时为灰色
            bg_color = QColor(0, 122, 255, 50) if option.state & QStyle.State_Active else QColor(200, 200, 200, 60)
            painter.setPen(Qt.NoPen)
            painter.setBrush(bg_color)
            
            # 绘制圆角矩形背景
            rect = QRectF(option.rect).adjusted(4, 2, -4, -2)
            painter.drawRoundedRect(rect, 6, 6)
            text_color = QColor("#007AFF") if option.state & QStyle.State_Active else QColor("#333")
        else:
            text_color = QColor("#333")

        # 2. 绘制文本内容
        if index.column() == 0:
            full_name = index.data(Qt.UserRole) or ""
            fm = option.fontMetrics
            display_text = fm.elidedText(full_name, Qt.ElideMiddle, option.rect.width() - 20)
            painter.setPen(text_color)
            painter.drawText(option.rect.adjusted(12, 0, 0, 0), Qt.AlignVCenter, display_text)
        else:
            text = str(index.data(Qt.DisplayRole))
            painter.setPen(QColor("#888") if not (option.state & QStyle.State_Selected) else text_color)
            painter.drawText(option.rect, Qt.AlignVCenter, text)

        painter.restore()

# ✅ 确保这个类存在，main.py 才能导入它
class SearchResultItem(QTreeWidgetItem):
    def __init__(self, name, size, time_str, pdir, full_path, mtime):
        # 这里的顺序对应列：0:名称, 1:大小, 2:修改时间, 3:路径
        super().__init__(["", size, time_str, pdir])
        self.full_path = full_path
        self.mtime = mtime  # 存储原始时间戳（数值）
        self.setData(0, Qt.UserRole, name)

    def __lt__(self, other):
        # QTreeWidgetItem 的排序依据。
        # 返回 self.mtime < other.mtime。
        # 当我们在 main.py 调用 DescendingOrder（降序）时，最大的 mtime (最新的) 会排在最上面。
        return self.mtime < other.mtime

class SearchResultWidget(QTreeWidget):
    open_signal = pyqtSignal(str)
    finder_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        # 开启多选
        self.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.setColumnCount(4)
        self.setHeaderHidden(True)
        self.setIndentation(0)
        self.setUniformRowHeights(True)
        
        self.delegate = ModernDelegate()
        self.setItemDelegate(self.delegate)
        
        self.setStyleSheet("QTreeWidget { background:transparent; border:none; outline:none; }")
        
        h = self.header()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Fixed)
        h.resizeSection(2, 110)
        h.setSectionResizeMode(3, QHeaderView.Stretch)
        
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        # ✅ 新增：连接双击信号
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
    def _on_item_double_clicked(self, item, column):
        """
        根据双击的列执行不同操作：
        Column 0: 文件名 -> 打开文件
        Column 3: 路径   -> 在 Finder 中定位
        """
        if not item: return
        
        # 如果双击的是第一列（文件名列）
        if column == 0:
            self.open_signal.emit(item.full_path)
        
        # 如果双击的是最后一列（路径列）
        elif column == 3:
            self.finder_signal.emit(item.full_path)
        
        # 其他列（大小、日期）默认执行打开操作，或者你可以自定义
        else:
            self.open_signal.emit(item.full_path)

    def _get_selected_paths(self):
        return [item.full_path for item in self.selectedItems()]

    def _menu(self, pos):
        items = self.selectedItems()
        if not items: return
        
        m = QMenu()
        if len(items) == 1:
            m.addAction("打开文件", lambda: self.open_signal.emit(items[0].full_path))
            m.addAction("在 Finder 中显示", lambda: self.finder_signal.emit(items[0].full_path))
        else:
            m.addAction(f"批量打开 {len(items)} 个文件", self._batch_open)

        m.addSeparator()
        m.addAction(f"复制 ({len(items)})", self._copy_batch_to_clipboard)
        m.addAction(f"移至废纸篓 ({len(items)})", self._trash_batch)
        m.exec_(self.viewport().mapToGlobal(pos))

    def _batch_open(self):
        for path in self._get_selected_paths():
            self.open_signal.emit(path)

    def _copy_batch_to_clipboard(self):
        paths = self._get_selected_paths()
        if not paths: return
        
        # --- 核心修复：使用 macOS 原生接口写入剪贴板 ---
        try:
            from AppKit import NSPasteboard, NSFilenamesPboardType
            pb = NSPasteboard.generalPasteboard()
            pb.clearContents()
            # 写入路径列表，Finder 识别这个格式才能执行“粘贴文件”
            pb.setPropertyList_forType_(paths, NSFilenamesPboardType)
        except ImportError:
            # 备选方案：如果没装 pyobjc，使用标准的 Qt 逻辑
            urls = [QUrl.fromLocalFile(p) for p in paths]
            mime = QMimeData()
            mime.setUrls(urls)
            mime.setText("\n".join(paths))
            QApplication.clipboard().setMimeData(mime)

    def _trash_batch(self):
        items = self.selectedItems()
        if not items: return
        
        if QMessageBox.question(self, '确认删除', f'确定要将选中的 {len(items)} 个文件移至废纸篓吗？',
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            fm = NSFileManager.defaultManager()
            for item in items:
                url = NSURL.fileURLWithPath_(item.full_path)
                success, _, _ = fm.trashItemAtURL_resultingItemURL_error_(url, None, None)
                if success:
                    self.takeTopLevelItem(self.indexOfTopLevelItem(item))

    def keyPressEvent(self, event):
        items = self.selectedItems()
        if not items:
            super().keyPressEvent(event)
            return

        # 同样使用双重判断
        is_cmd = (event.modifiers() & Qt.MetaModifier) or (event.modifiers() & Qt.ControlModifier)
        
        if is_cmd and event.key() == Qt.Key_C:
            self._copy_batch_to_clipboard()
            event.accept()
        elif is_cmd and event.key() == Qt.Key_Backspace:
            self._trash_batch()
            event.accept()
        else:
            super().keyPressEvent(event)