from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class EvaluationCriteria(str, Enum):
    TASK_PERFORMANCE = "task_performance"
    RESPONSE_QUALITY = "response_quality"
    LANGUAGE_QUALITY = "language_quality"
    TOOL_USAGE = "tool_usage"
    FACTUAL_ACCURACY = "factual_accuracy"


class ScoreLevel(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    SATISFACTORY = "satisfactory"
    POOR = "poor"
    VERY_POOR = "very_poor"


SCORE_VALUES = {
    ScoreLevel.EXCELLENT: 5,
    ScoreLevel.GOOD: 4,
    ScoreLevel.SATISFACTORY: 3,
    ScoreLevel.POOR: 2,
    ScoreLevel.VERY_POOR: 1
}


class CriteriaScore(BaseModel):
    criteria: EvaluationCriteria
    score: ScoreLevel
    reasoning: str = Field(..., description="Detailed reasoning for the score")
    score_value: int = Field(description="Numeric score (1-5)")
    
    def __init__(self, **data):
        if 'score_value' not in data and 'score' in data:
            data['score_value'] = SCORE_VALUES[ScoreLevel(data['score'])]
        super().__init__(**data)


class EvaluationResult(BaseModel):
    test_case_id: str = Field(..., description="ID of the evaluated test case")
    model_id: str = Field(..., description="ID of the evaluated model")
    scenario_type: str = Field(..., description="Type of scenario")
    user_query: str = Field(..., description="Original user query")
    model_response: str = Field(..., description="Model's response")
    expected_behavior: str = Field(..., description="Expected behavior")
    
    scores: List[CriteriaScore] = Field(..., description="Scores for each criteria")
    overall_score: float = Field(..., description="Overall weighted score")
    
    tool_calls_made: List[Dict[str, Any]] = Field(default_factory=list)
    tool_results: List[Dict[str, Any]] = Field(default_factory=list)
    
    judge_model: str = Field(..., description="Model used for evaluation")
    evaluation_timestamp: str = Field(..., description="When evaluation was performed")
    
    additional_notes: Optional[str] = Field(None, description="Additional observations")


class EvaluationConfig(BaseModel):
    judge_model: str = Field("gpt-4o", description="Model to use as judge")
    judge_provider: str = Field("openai", description="Provider for judge model")
    temperature: float = Field(0.1, description="Temperature for judge model")
    
    criteria_weights: Dict[EvaluationCriteria, float] = Field(
        default_factory=lambda: {
            EvaluationCriteria.TASK_PERFORMANCE: 0.30,
            EvaluationCriteria.RESPONSE_QUALITY: 0.25,
            EvaluationCriteria.LANGUAGE_QUALITY: 0.15,
            EvaluationCriteria.TOOL_USAGE: 0.15,
            EvaluationCriteria.FACTUAL_ACCURACY: 0.15
        },
        description="Weights for each evaluation criteria"
    )
    
    max_retries: int = Field(2, description="Max retries for failed evaluations")
    timeout_seconds: int = Field(60, description="Timeout for evaluation requests")


class BatchEvaluationResult(BaseModel):
    results: List[EvaluationResult] = Field(..., description="Individual evaluation results")
    summary: Dict[str, Any] = Field(..., description="Summary statistics")
    config: EvaluationConfig = Field(..., description="Evaluation configuration used")
    total_evaluation_time_ms: float = Field(..., description="Total time taken for batch evaluation")