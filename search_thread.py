# search_thread.py
import os
import threading
from PyQt5.QtCore import QThread, pyqtSignal
from concurrent.futures import ThreadPoolExecutor

class FileSearchThread(QThread):
    results_batch_found = pyqtSignal(list)
    search_finished = pyqtSignal()

    # 硬编码的黑洞目录，提升扫描效率
    IGNORED_DIRS = {
        'node_modules', '.git', '.svn', '.hg', 'venv', '.venv', 
        '__pycache__', '.idea', '.vscode', 'Library', 'tmp'
    }

    # 系统级排除路径
    SYSTEM_EXCLUDE_PATHS = [
        "/System", "/private", "/dev", "/net",
        "/Volumes", "/cores", "/var", "/tmp"
    ]

    def __init__(self, query, paths, manager, batch_size=50):
        super().__init__()
        self.query = query.strip().lower()
        self.paths = paths
        self.manager = manager
        self.batch_size = batch_size
        self.stop_flag = False
        self.lock = threading.Lock()
        self.seen = set()
        self.buffer = []
        # 根据查询是否为空，决定并发策略，简单的查询可以少用点线程
        self.pool = ThreadPoolExecutor(max_workers=min(os.cpu_count() + 2, 8))

    def stop(self):
        self.stop_flag = True
        self.pool.shutdown(wait=False)

    def _should_stop(self):
        return self.stop_flag

    def run(self):
        futures = []
        for path in self.paths:
            if self._should_stop():
                break
            if os.path.exists(path):
                futures.append(self.pool.submit(self._walk, path, 0))
        
        # 等待所有任务完成
        for f in futures:
            if self._should_stop(): 
                break
            try:
                f.result()
            except Exception:
                pass
                
        self._flush()
        self.search_finished.emit()

    def _walk(self, path, depth):
        if self._should_stop() or depth > self.manager.search_depth:
            return

        # 顶层系统目录检查
        if depth == 0 and any(path.startswith(p) for p in self.SYSTEM_EXCLUDE_PATHS):
            return

        try:
            # 使用 scandir 获取更好的性能
            with os.scandir(path) as it:
                entries = list(it) # 转换为列表以防止迭代器锁定
                
                # 分离文件和目录
                dirs = []
                files = []
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in self.IGNORED_DIRS and not entry.name.startswith('.'):
                            dirs.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        files.append(entry)

                # 处理文件
                for f in files:
                    if self._should_stop(): return
                    self._handle(f.path, f.name, f.stat().st_mtime)

                # 递归处理目录
                for d in dirs:
                    if self._should_stop(): return
                    # 不将子目录放入线程池，防止递归爆炸，直接在当前线程递归
                    self._walk(d.path, depth + 1)

        except PermissionError:
            pass
        except Exception:
            pass

    def _handle(self, path, name, mtime):
        if not self.manager.should_include_file(name):
            return
        
        with self.lock:
            if path in self.seen:
                return
            self.seen.add(path)
            
        self.buffer.append({"name": name, "path": path, "mtime": mtime})
        if len(self.buffer) >= self.batch_size:
            self._flush()

    def _flush(self):
        with self.lock:
            if self.buffer:
                # 按时间倒序
                sorted_buffer = sorted(self.buffer, key=lambda x: -x["mtime"])
                self.results_batch_found.emit(sorted_buffer)
                self.buffer.clear()