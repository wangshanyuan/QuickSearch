#search_manager.py
import re

class SearchManager:
    def __init__(self):
        self.and_kws = []
        self.or_kws = []
        self.not_kws = []
        self.not_exts = []
        self.exact_exts = []

    def set_query(self, text):
        self.and_kws = []
        self.or_kws = []
        self.not_kws = []
        self.not_exts = []
        self.exact_exts = []
        
        if not text or not text.strip(): return

        # --- 核心修复：中英文全角符号标准化 ---
        # 将全角“！”替换为半角“!”，将全角“｜”替换为半角“|”
        text = text.replace('！', '!').replace('｜', '|')

        # 1. 提取排除逻辑 (现在 !pdf 和 ！pdf 都能被正则 !(\S+) 匹配到了)
        not_matches = re.findall(r'!(\S+)', text)
        for m in not_matches:
            low_m = m.lower()
            if low_m.startswith("."):
                self.not_exts.append(low_m)
            else:
                self.not_kws.append(low_m)
        # 清除文本中的排除项，注意这里也要处理替换后的 text
        text = re.sub(r'!\S+', '', text)

        # 2. 提取精准后缀 (例如 .pdf)
        ext_matches = re.findall(r'(?<!\S)\.\w+(?!\S)', text)
        self.exact_exts = [e.lower() for e in ext_matches]
        for ext in ext_matches:
            text = text.replace(ext, "")

        # 3. 处理 OR (|) 逻辑
        if '|' in text:
            parts = text.split('|')
            self.or_kws = [p.strip().lower() for p in parts if p.strip()]
        else:
            # 4. 普通多词 AND 逻辑
            self.and_kws = [w.lower() for w in text.split() if w]

    def is_match(self, filename):
        if not filename: return False
        fn = filename.lower()
        
        # A. 排除逻辑
        if any(kw in fn for kw in self.not_kws): return False
        if any(fn.endswith(ext) for ext in self.not_exts): return False
            
        # B. 必须包含的后缀
        if self.exact_exts:
            if not any(fn.endswith(ext) for ext in self.exact_exts):
                return False
        
        # C. 核心逻辑判断
        # 如果有 OR 条件，只要满足其中一个
        or_passed = True
        if self.or_kws:
            or_passed = any(ok in fn for ok in self.or_kws)
            
        # 如果有 AND 条件，必须全部满足
        and_passed = True
        if self.and_kws:
            and_passed = all(ak in fn for ak in self.and_kws)
            
        return or_passed and and_passed