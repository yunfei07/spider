from abc import ABC, abstractmethod
from typing import List, Dict

class TestCaseProvider(ABC):
    @abstractmethod
    def get_cases(self) -> List[Dict[str, str]]:
        """
        Returns a list of test cases.
        Each case should have at least 'prompt' and optionally 'id', 'name'.
        Example: [{"id": "1", "prompt": "Login and check title"}]
        """
        pass
