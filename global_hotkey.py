# global_hotkey.py
from AppKit import NSEvent, NSKeyDownMask, NSCommandKeyMask, NSAlternateKeyMask, NSShiftKeyMask, NSControlKeyMask
from PyQt5.QtCore import QThread, pyqtSignal

# 热键修饰符映射
MODIFIER_MAP = {
    "cmd": NSCommandKeyMask,
    "option": NSAlternateKeyMask,
    "alt": NSAlternateKeyMask,
    "shift": NSShiftKeyMask,
    "ctrl": NSControlKeyMask,
    "control": NSControlKeyMask
}

class GlobalHotKey(QThread):
    # 定义一个信号，用于安全地跨线程通知 UI
    triggered = pyqtSignal()

    def __init__(self, hotkey: str, callback):
        super().__init__()
        # 解析热键（如 "option+space" -> (NSAlternateKeyMask, " ")）
        self.modifier, self.key = self._parse_hotkey(hotkey.lower())
        self.running = True
        self.triggered.connect(callback)
    def _parse_hotkey(self, hotkey):
        """解析热键字符串，返回 (修饰符掩码, 按键字符)"""
        parts = hotkey.split("+")
        if len(parts) < 2:
            # 默认 fallback 为 option+space
            return NSAlternateKeyMask, " "
        
        modifiers = parts[:-1]
        key = parts[-1].strip()
        
        # 计算修饰符掩码
        mask = 0
        for mod in modifiers:
            mask |= MODIFIER_MAP.get(mod, 0)
        
        # 特殊按键映射（如 space -> 空格字符）
        if key == "space":
            key = " "
        return mask, key

    def run(self):
        mask = NSKeyDownMask

        def handler(event):
            if not self.running:
                return event

            if self._match(event):
                # ✅ 发射信号，而不是直接调用 callback
                self.triggered.emit()
                return None  # 吞掉事件，防止触发系统默认行为

            return event

        # 注册全局监听器
        NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            mask, handler
        )

        # 开启事件循环，保持线程运行
        self.exec_()

    def stop(self):
        self.running = False
        self.quit()

    def _match(self, event) -> bool:
        """匹配按下的按键是否为目标热键"""
        # 获取修饰符
        flags = event.modifierFlags()
        # 获取按键字符（忽略修饰符）
        key = event.charactersIgnoringModifiers() or ""
        
        # 匹配修饰符 + 按键
        return (flags & self.modifier) == self.modifier and key == self.key