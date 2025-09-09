from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ScenarioType(str, Enum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    MALICIOUS = "malicious"


class TestCase(BaseModel):
    id: str = Field(..., description="Unique test case identifier")
    scenario_type: ScenarioType = Field(..., description="Type of test scenario")
    user_query: str = Field(..., description="User's question/request")
    expected_behavior: str = Field(..., description="Expected model behavior")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context for evaluation")
    difficulty: int = Field(1, ge=1, le=5, description="Difficulty level (1-5)")
    category: Optional[str] = Field(None, description="Product category being tested")
    producer: Optional[str] = Field(None, description="Producer being tested")
    product_ids: List[int] = Field(default_factory=list, description="Relevant product IDs")
    
    class Config:
        use_enum_values = True


class ScenarioTemplate(BaseModel):
    template_id: str
    scenario_type: ScenarioType
    template: str
    variables: List[str]
    expected_behavior: str
    difficulty: int
    
    class Config:
        use_enum_values = True


class GeneratedScenarios(BaseModel):
    scenarios: List[TestCase]
    metadata: Dict[str, Any]
    generation_timestamp: str