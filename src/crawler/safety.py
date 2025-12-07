import yaml
import os
from typing import List, Dict

class SafetyFilter:
    def __init__(self, config_path: str = "crawler_config.yaml"):
        self.blacklist = []
        self.max_depth = 1
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                    self.blacklist = [w.lower() for w in config.get("blacklist", [])]
                    self.max_depth = config.get("max_depth", 1)
            except Exception as e:
                print(f"Error loading safety config: {e}")
        else:
            print("Warning: crawler_config.yaml not found, using default safety rules.")
            self.blacklist = ["delete", "remove", "logout", "sign out", "删除", "注销", "退出"]

    def is_safe(self, element_data: Dict) -> bool:
        """
        Checks if an element is safe to interact with.
        """
        # Check text
        text = element_data.get("text", "").lower()
        if self._contains_blacklist(text):
            return False
            
        # Check name
        name = element_data.get("name", "").lower()
        if self._contains_blacklist(name):
            return False

        # Check attributes like data-testid or class if they are very suspicious
        # (Optional, maybe too aggressive)
        
        return True

    def _contains_blacklist(self, text: str) -> bool:
        for word in self.blacklist:
            if word in text:
                return True
        return False
