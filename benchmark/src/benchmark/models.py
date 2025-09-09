from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from ..scenarios.models import TestCase
from ..providers.base import ModelResponse


class BenchmarkStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TestResult(BaseModel):
    test_case_id: str = Field(..., description="ID of the test case")
    model_id: str = Field(..., description="ID of the model being tested")
    scenario_type: str = Field(..., description="Type of scenario (correct/incorrect/malicious)")
    user_query: str = Field(..., description="User's query")
    model_response: ModelResponse = Field(..., description="Model's response")
    tool_calls_made: List[Dict[str, Any]] = Field(default_factory=list, description="Tool calls made by model")
    tool_results: List[Dict[str, Any]] = Field(default_factory=list, description="Results from tool calls")
    execution_time_ms: float = Field(..., description="Total execution time in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.now, description="When the test was executed")
    error: Optional[str] = Field(None, description="Error message if test failed")


class ModelBenchmarkResults(BaseModel):
    model_id: str = Field(..., description="Model identifier")
    model_name: str = Field(..., description="Human-readable model name")
    provider: str = Field(..., description="Provider name")
    test_results: List[TestResult] = Field(default_factory=list, description="All test results for this model")
    summary_stats: Dict[str, Any] = Field(default_factory=dict, description="Summary statistics")
    status: BenchmarkStatus = Field(BenchmarkStatus.PENDING, description="Benchmark status")
    start_time: Optional[datetime] = Field(None, description="When benchmark started")
    end_time: Optional[datetime] = Field(None, description="When benchmark completed")
    total_duration_ms: Optional[float] = Field(None, description="Total benchmark duration in milliseconds")


class BenchmarkRun(BaseModel):
    run_id: str = Field(..., description="Unique run identifier")
    name: str = Field(..., description="Human-readable run name")
    description: Optional[str] = Field(None, description="Run description")
    test_cases: List[TestCase] = Field(..., description="Test cases to run")
    models_to_test: List[str] = Field(..., description="Model IDs to test")
    model_results: List[ModelBenchmarkResults] = Field(default_factory=list, description="Results for each model")
    status: BenchmarkStatus = Field(BenchmarkStatus.PENDING, description="Overall run status")
    start_time: Optional[datetime] = Field(None, description="When run started")
    end_time: Optional[datetime] = Field(None, description="When run completed")
    total_duration_ms: Optional[float] = Field(None, description="Total run duration in milliseconds")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Benchmark configuration")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class BenchmarkConfig(BaseModel):
    concurrent_models: int = Field(3, ge=1, le=10, description="Number of models to test concurrently")
    timeout_per_test: int = Field(60, ge=10, description="Timeout per test case in seconds")
    retry_failed_tests: bool = Field(True, description="Whether to retry failed tests")
    max_retries: int = Field(2, ge=0, description="Maximum number of retries for failed tests")
    save_intermediate_results: bool = Field(True, description="Save results after each model completes")
    output_directory: str = Field("results", description="Directory to save results")
    include_tool_execution: bool = Field(True, description="Whether to execute tool calls")
    mcp_server_url: str = Field("http://localhost:8000", description="MCP server URL for tool execution")


class BenchmarkProgress(BaseModel):
    run_id: str
    total_tests: int
    completed_tests: int
    failed_tests: int
    current_model: Optional[str] = None
    current_test_case: Optional[str] = None
    estimated_completion: Optional[datetime] = None
    progress_percentage: float = Field(ge=0.0, le=100.0)