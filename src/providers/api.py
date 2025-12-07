import json
import urllib.request
from typing import List, Dict
from src.providers.base import TestCaseProvider

class APIProvider(TestCaseProvider):
    def __init__(self, api_url: str):
        self.api_url = api_url

    def get_cases(self) -> List[Dict[str, str]]:
        try:
            print(f"Fetching cases from {self.api_url}...")
            with urllib.request.urlopen(self.api_url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP Error {response.status}")
                
                data = json.loads(response.read().decode('utf-8'))
                
                # Normalize data format
                cases = []
                if isinstance(data, list):
                    for item in data:
                        # Assume API returns list of objects. Adapter logic might be needed here.
                        # For now, expect fields 'prompt' or 'description'
                        prompt = item.get("prompt") or item.get("description") or item.get("title")
                        if prompt:
                            cases.append({
                                "id": str(item.get("id", "")),
                                "prompt": prompt
                            })
                return cases
                
        except Exception as e:
            print(f"Error fetching from API: {e}")
            return []
