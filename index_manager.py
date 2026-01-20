import os
import sqlite3
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class IndexManager:
    # 强制忽略的高频变动或无意义目录
    IGNORED_DIRS = {
        'Library', 'node_modules', '.git', '.svn', 'Containers', 
        'Cache', 'Caches', 'Logs', 'tmp', 'Pictures/Photos Library.photoslibrary'
    }

    def __init__(self, search_paths, db_path=None, show_hidden=False):
        self.search_paths = [str(Path(p).expanduser()) for p in search_paths]
        self.db_path = db_path or str(Path.home() / ".mac_search_index.db")
        self.show_hidden = show_hidden
        self.search_depth = 100
        
        # 数据库与线程锁
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.lock = threading.Lock()
        
        self._observer = None
        self._is_monitoring = False
        self._init_db()

    def _init_db(self):
        with self.lock:
            cursor = self.conn.cursor()
            # 开启 WAL 模式可以显著提高并发读写性能
            cursor.execute('PRAGMA journal_mode=WAL')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS file_index (
                    path TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    mtime REAL NOT NULL,
                    size INTEGER NOT NULL
                )
            ''')
            # 建立索引：加快模糊搜索速度
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_name ON file_index(name)')
            self.conn.commit()

    def _batch_insert(self, batch):
        """核心优化：批量写入数据"""
        if not batch: return
        try:
            with self.lock:
                cursor = self.conn.cursor()
                cursor.executemany('''
                    INSERT OR REPLACE INTO file_index (path, name, mtime, size) 
                    VALUES (?, ?, ?, ?)
                ''', batch)
                self.conn.commit()
        except Exception as e:
            print(f"[IndexManager] 批量写入失败: {e}")

    def rebuild_index(self):
        """全量重建索引"""
        print("开始重建索引...")
        with self.lock:
            self.conn.execute('DELETE FROM file_index')
            self.conn.commit()
        
        for root_path in self.search_paths:
            if not os.path.exists(root_path): continue
            
            batch = []
            for root, dirs, files in os.walk(root_path, topdown=True):
                # 1. 过滤忽略目录
                dirs[:] = [d for d in dirs if d not in self.IGNORED_DIRS and 
                          (self.show_hidden or not d.startswith('.'))]
                
                # 2. 深度控制
                depth = root[len(root_path):].count(os.sep)
                if depth >= self.search_depth:
                    dirs[:] = []
                    continue

                for f in files:
                    if not self.show_hidden and f.startswith('.'):
                        continue
                    
                    fp = os.path.join(root, f)
                    try:
                        st = os.stat(fp)
                        batch.append((fp, f, st.st_mtime, st.st_size))
                        
                        # 每 1000 个文件提交一次事务
                        if len(batch) >= 1000:
                            self._batch_insert(batch)
                            batch = []
                    except (PermissionError, FileNotFoundError):
                        continue
            
            # 提交剩余部分
            self._batch_insert(batch)
        print("索引重建完成！")

    def start_monitoring(self):
        """启动监听，增加严格的单例保护"""
        if self._is_monitoring or self._observer is not None:
            print("[IndexManager] 监控已在运行中，跳过重复启动")
            return
        
        # 内部类定义保持不变...
        class FileChangeHandler(FileSystemEventHandler):
            def __init__(self, mgr): self.mgr = mgr
            def _is_ignored(self, path):
                parts = Path(path).parts
                return any(p in self.mgr.IGNORED_DIRS for p in parts)
            def on_created(self, event):
                if not event.is_directory and not self._is_ignored(event.src_path):
                    self.mgr._update_file_async(event.src_path)
            def on_modified(self, event):
                if not event.is_directory and not self._is_ignored(event.src_path):
                    self.mgr._update_file_async(event.src_path)
            def on_deleted(self, event):
                if not event.is_directory: self.mgr.remove_file(event.src_path)
            def on_moved(self, event):
                if not event.is_directory:
                    self.mgr.remove_file(event.src_path)
                    if not self._is_ignored(event.dest_path):
                        self.mgr._update_file_async(event.dest_path)

        try:
            self._observer = Observer()
            handler = FileChangeHandler(self)
            for path in self.search_paths:
                if os.path.exists(path):
                    # 确保只 schedule 一次
                    self._observer.schedule(handler, path, recursive=True)
            self._observer.start()
            self._is_monitoring = True
            print(f"[IndexManager] 成功启动监控: {self.search_paths}")
        except Exception as e:
            print(f"[IndexManager] 启动监控失败: {e}")
            self._observer = None
            self._is_monitoring = False

    def _update_file_async(self, file_path):
        """单文件增量更新"""
        try:
            st = os.stat(file_path)
            with self.lock:
                self.conn.execute('''
                    INSERT OR REPLACE INTO file_index (path, name, mtime, size) 
                    VALUES (?, ?, ?, ?)
                ''', (file_path, os.path.basename(file_path), st.st_mtime, st.st_size))
                self.conn.commit()
        except: pass

    def remove_file(self, file_path):
        with self.lock:
            self.conn.execute('DELETE FROM file_index WHERE path = ?', (file_path,))
            self.conn.commit()

    def search_name(self, query, max_results=1000):
        if not query: return []
        with self.lock:
            cursor = self.conn.cursor()
            # 关键：在数据库层面先进行降序排列
            cursor.execute('''
                SELECT path, name, mtime, size FROM file_index 
                WHERE name LIKE ? 
                ORDER BY mtime DESC 
                LIMIT ?
            ''', (f'%{query}%', max_results))
            return [{"path": r[0], "name": r[1], "mtime": r[2], "size": r[3]} for r in cursor.fetchall()]
    def stop_monitoring(self):
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._is_monitoring = False