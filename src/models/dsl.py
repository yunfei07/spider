from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class TestStep(BaseModel):
    action: str = Field(..., description="Action to perform, e.g., 'goto', 'fill', 'click', 'wait', 'assert'")
    target: Optional[str] = Field(None, description="Natural language description of the target element")
    value: Optional[str] = Field(None, description="Value to input or assert")
    page_context: Optional[str] = None # New: Logic page name (e.g. 'login', 'cart') for context-aware resolution
    selector: Optional[str] = Field(None, description="Concrete Playwright selector (filled by Resolver)")
    args: Dict[str, Any] = Field(default_factory=dict, description="Additional arguments")

class TestScenario(BaseModel):
    name: str
    description: Optional[str] = None
    steps: List[TestStep]
