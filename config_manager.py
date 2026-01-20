# config_manager.py
import json
import os

class ConfigManager:
    PATH = os.path.expanduser("~/.mac_search_config.json")

    DEFAULT_CONFIG = {
        "hotkey": "option+space",
        "search_paths": [os.path.expanduser("~")],
        "exclude_rules": "",
        "show_hidden": False
    }

    def load_config(self):
        if not os.path.exists(self.PATH):
            return self.DEFAULT_CONFIG.copy()
        try:
            with open(self.PATH, "r") as f:
                cfg = json.load(f)
            # 补全缺失字段
            for k, v in self.DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
        except Exception:
            return self.DEFAULT_CONFIG.copy()

    def save_config(self, cfg):
        try:
            with open(self.PATH, "w") as f:
                json.dump(cfg, f, indent=2)
        except Exception as e:
            print(f"[ConfigManager] 保存配置失败: {e}")
