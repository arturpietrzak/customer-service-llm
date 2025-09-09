import asyncio
import time
import uuid
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
import traceback

from ..scenarios.models import TestCase, GeneratedScenarios
from ..providers.base import BaseLLMProvider, ModelConfig, ModelResponse, Message, ToolCall
from ..providers.provider_factory import ProviderFactory
from .models import (
    BenchmarkRun, BenchmarkConfig, BenchmarkStatus, ModelBenchmarkResults, 
    TestResult, BenchmarkProgress
)

logger = logging.getLogger(__name__)


def safe_json_loads(json_str: str) -> Any:
    if not isinstance(json_str, str):
        return json_str
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        if "Extra data" in str(e):
            try:
                decoder = json.JSONDecoder()
                obj, idx = decoder.raw_decode(json_str)
                logger.warning(f"Found extra data after JSON: '{json_str[idx:]}'")
                return obj
            except json.JSONDecodeError:
                json_pattern = r'\{.*?\}(?=\s*[^\}\s]|$)'
                match = re.search(json_pattern, json_str)
                if match:
                    try:
                        return json.loads(match.group())
                    except json.JSONDecodeError:
                        pass
        
        logger.error(f"Failed to parse JSON: {json_str}")
        raise e


class BenchmarkExecutor:
    """Executes benchmarks across multiple models and test cases."""
    
    def __init__(
        self, 
        config: BenchmarkConfig, 
        provider_factory: ProviderFactory,
        progress_callback: Optional[Callable[[BenchmarkProgress], None]] = None,
        rate_limit_delay: float = 1.0 
    ):
        self.config = config
        self.provider_factory = provider_factory
        self.progress_callback = progress_callback
        self.current_run: Optional[BenchmarkRun] = None
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time: Dict[str, float] = {} 
        
        Path(self.config.output_directory).mkdir(parents=True, exist_ok=True)
    
    async def run_benchmark(
        self, 
        test_cases: List[TestCase],
        model_ids: List[str],
        run_name: str = "Benchmark Run",
        description: Optional[str] = None
    ) -> BenchmarkRun:
        run_id = str(uuid.uuid4())
        
        self.current_run = BenchmarkRun(
            run_id=run_id,
            name=run_name,
            description=description,
            test_cases=test_cases,
            models_to_test=model_ids,
            status=BenchmarkStatus.RUNNING,
            start_time=datetime.now(),
            configuration=self.config.model_dump(),
            metadata={
                "total_test_cases": len(test_cases),
                "total_models": len(model_ids),
                "estimated_total_tests": len(test_cases) * len(model_ids)
            }
        )
        
        logger.info(f"Starting benchmark run {run_id} with {len(test_cases)} test cases across {len(model_ids)} models")
        
        try:
            for model_id in model_ids:
                model_config = self.provider_factory.get_model_config(model_id)
                self.current_run.model_results.append(
                    ModelBenchmarkResults(
                        model_id=model_id,
                        model_name=model_config.get("display_name", model_id) if model_config else model_id,
                        provider=model_config.get("provider", "unknown") if model_config else "unknown",
                        status=BenchmarkStatus.PENDING
                    )
                )
            
            semaphore = asyncio.Semaphore(self.config.concurrent_models)
            model_tasks = []
            
            for i, model_id in enumerate(model_ids):
                task = asyncio.create_task(
                    self._run_model_benchmark(model_id, test_cases, semaphore, i)
                )
                model_tasks.append(task)
            
            await asyncio.gather(*model_tasks, return_exceptions=True)
            
            self.current_run.status = BenchmarkStatus.COMPLETED
            self.current_run.end_time = datetime.now()
            if self.current_run.start_time:
                duration = self.current_run.end_time - self.current_run.start_time
                self.current_run.total_duration_ms = duration.total_seconds() * 1000
            
            self._calculate_run_summary()
            
            self._save_benchmark_results()
            
            logger.info(f"Benchmark run {run_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Benchmark run failed: {e}")
            logger.error(traceback.format_exc())
            self.current_run.status = BenchmarkStatus.FAILED
            self.current_run.end_time = datetime.now()
            
            self._save_benchmark_results()
        
        return self.current_run
    
    async def _run_model_benchmark(
        self, 
        model_id: str, 
        test_cases: List[TestCase], 
        semaphore: asyncio.Semaphore,
        model_index: int
    ) -> None:
        async with semaphore:
            model_result = self.current_run.model_results[model_index]
            
            try:
                logger.info(f"Starting benchmark for model {model_id}")
                model_result.status = BenchmarkStatus.RUNNING
                model_result.start_time = datetime.now()
                
                provider = self.provider_factory.get_provider(model_id)
                if not provider:
                    raise Exception(f"Could not create provider for model {model_id}")
                
                model_config_dict = self.provider_factory.get_model_config(model_id)
                if not model_config_dict:
                    raise Exception(f"Could not find configuration for model {model_id}")
                
                model_config = ModelConfig(
                    model_name=model_config_dict.get("model_name", model_id),
                    temperature=model_config_dict.get("temperature", 0.7),
                    max_tokens=model_config_dict.get("max_tokens", 1000)
                )
                
                test_results = []
                for i, test_case in enumerate(test_cases):
                    try:
                        await self._apply_rate_limit(model_id)
                        
                        result = await self._run_single_test(provider, model_config, test_case, model_id)
                        test_results.append(result)
                        
                        if self.progress_callback:
                            total_tests = len(test_cases) * len(self.current_run.models_to_test)
                            completed_tests = sum(len(mr.test_results) for mr in self.current_run.model_results) + len(test_results)
                            
                            progress = BenchmarkProgress(
                                run_id=self.current_run.run_id,
                                total_tests=total_tests,
                                completed_tests=completed_tests,
                                failed_tests=0,
                                current_model=model_id,
                                progress_percentage=(completed_tests / total_tests) * 100 if total_tests > 0 else 0
                            )
                            self.progress_callback(progress)
                        
                    except Exception as e:
                        logger.error(f"Test failed for model {model_id}: {e}")
                        test_results.append(e)
                
                for result in test_results:
                    if isinstance(result, TestResult):
                        model_result.test_results.append(result)
                    elif isinstance(result, Exception):
                        logger.error(f"Test failed for model {model_id}: {result}")
                
                model_result.summary_stats = self._calculate_model_summary(model_result)
                model_result.status = BenchmarkStatus.COMPLETED
                model_result.end_time = datetime.now()
                
                if model_result.start_time:
                    duration = model_result.end_time - model_result.start_time
                    model_result.total_duration_ms = duration.total_seconds() * 1000
                
                if self.config.save_intermediate_results:
                    self._save_model_results(model_result)
                
                logger.info(f"Completed benchmark for model {model_id}: {len(model_result.test_results)} tests")
                
                self._update_progress()
                
            except Exception as e:
                logger.error(f"Model benchmark failed for {model_id}: {e}")
                logger.error(traceback.format_exc())
                model_result.status = BenchmarkStatus.FAILED
                model_result.end_time = datetime.now()
    
    async def _apply_rate_limit(self, model_id: str):
        current_time = time.time()
        last_request = self.last_request_time.get(model_id, 0)
        
        time_since_last = current_time - last_request
        if time_since_last < self.rate_limit_delay:
            wait_time = self.rate_limit_delay - time_since_last
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s for model {model_id}")
            await asyncio.sleep(wait_time)
        
        self.last_request_time[model_id] = time.time()
    
    async def _run_single_test(
        self, 
        provider: BaseLLMProvider,
        model_config: ModelConfig,
        test_case: TestCase,
        model_id: str
    ) -> TestResult:
        start_time = time.time()
        
        try:
            messages = provider.format_messages_with_system_prompt(test_case.user_query)
            tools = provider.get_database_tools() if self.config.include_tool_execution else None
            response = await asyncio.wait_for(
                provider.generate_response(messages, model_config, tools),
                timeout=self.config.timeout_per_test
            )
            
            tool_calls_made = []
            tool_results = []
            
            if response.tool_calls and self.config.include_tool_execution:
                for tool_call_info in response.tool_calls:
                    try:
                        if "function" in tool_call_info:
                            func = tool_call_info["function"]
                            tool_call = ToolCall(
                                name=func["name"],
                                arguments=safe_json_loads(func["arguments"]) if isinstance(func["arguments"], str) else func["arguments"],
                                call_id=tool_call_info.get("id")
                            )
                        else:
                            tool_call = ToolCall(
                                name=tool_call_info["name"],
                                arguments=safe_json_loads(tool_call_info["arguments"]) if isinstance(tool_call_info["arguments"], str) else tool_call_info["arguments"],
                                call_id=tool_call_info.get("id")
                            )
                        
                        tool_result = await provider.execute_tool_call(tool_call)
                        tool_calls_made.append({
                            "name": tool_call.name,
                            "arguments": tool_call.arguments,
                            "id": tool_call.call_id
                        })
                        tool_results.append(tool_result)
                        
                        messages.append(Message(
                            role="assistant", 
                            content=response.content,
                            tool_calls=[tool_call]
                        ))
                        messages.append(Message(
                            role="tool",
                            content=json.dumps(tool_result, ensure_ascii=False),
                            tool_call_id=tool_call.call_id
                        ))
                        
                        messages[0] = Message(role="system", content=provider.get_response_formatting_prompt())
                        await self._apply_rate_limit(model_id)
                        
                        final_response = await asyncio.wait_for(
                            provider.generate_response(messages, model_config),
                            timeout=self.config.timeout_per_test
                        )
                        
                        response.content = final_response.content
                        if final_response.usage:
                            if response.usage:
                                response.usage["total_tokens"] = (response.usage.get("total_tokens", 0) + 
                                                                  final_response.usage.get("total_tokens", 0))
                            else:
                                response.usage = final_response.usage
                        
                    except Exception as tool_error:
                        logger.error(f"Tool execution error: {tool_error}")
                        tool_results.append({"error": str(tool_error)})
            
            execution_time = (time.time() - start_time) * 1000
            
            return TestResult(
                test_case_id=test_case.id,
                model_id=model_id,
                scenario_type=test_case.scenario_type,
                user_query=test_case.user_query,
                model_response=response,
                tool_calls_made=tool_calls_made,
                tool_results=tool_results,
                execution_time_ms=execution_time,
                timestamp=datetime.now()
            )
            
        except asyncio.TimeoutError:
            execution_time = (time.time() - start_time) * 1000
            return TestResult(
                test_case_id=test_case.id,
                model_id=model_id,
                scenario_type=test_case.scenario_type,
                user_query=test_case.user_query,
                model_response=ModelResponse(
                    content="",
                    model=model_config.model_name,
                    provider=provider.provider_name,
                    error="Timeout"
                ),
                tool_calls_made=[],
                tool_results=[],
                execution_time_ms=execution_time,
                timestamp=datetime.now(),
                error="Test timed out"
            )
        
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Test execution error: {e}")
            return TestResult(
                test_case_id=test_case.id,
                model_id=model_id,
                scenario_type=test_case.scenario_type,
                user_query=test_case.user_query,
                model_response=ModelResponse(
                    content="",
                    model=model_config.model_name,
                    provider=provider.provider_name,
                    error=str(e)
                ),
                tool_calls_made=[],
                tool_results=[],
                execution_time_ms=execution_time,
                timestamp=datetime.now(),
                error=str(e)
            )
    
    def _calculate_model_summary(self, model_result: ModelBenchmarkResults) -> Dict[str, Any]:
        results = model_result.test_results
        if not results:
            return {}
        
        total_tests = len(results)
        successful_tests = len([r for r in results if not r.error])
        failed_tests = total_tests - successful_tests
        
        by_scenario = {}
        for scenario_type in ["correct", "incorrect", "malicious"]:
            scenario_results = [r for r in results if r.scenario_type == scenario_type]
            by_scenario[scenario_type] = {
                "total": len(scenario_results),
                "successful": len([r for r in scenario_results if not r.error]),
                "failed": len([r for r in scenario_results if r.error])
            }
        
        execution_times = [r.execution_time_ms for r in results if not r.error]
        avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
        
        total_tokens = 0
        usage_count = 0
        for r in results:
            if r.model_response.usage and "total_tokens" in r.model_response.usage:
                total_tokens += r.model_response.usage["total_tokens"]
                usage_count += 1
        
        avg_tokens = total_tokens / usage_count if usage_count > 0 else 0
        
        total_tool_calls = sum(len(r.tool_calls_made) for r in results)
        successful_tool_calls = sum(
            len([tc for tc in r.tool_calls_made]) 
            for r in results 
            if not any("error" in tr for tr in r.tool_results)
        )
        
        return {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": failed_tests,
            "success_rate": successful_tests / total_tests if total_tests > 0 else 0,
            "by_scenario_type": by_scenario,
            "avg_execution_time_ms": avg_execution_time,
            "total_tokens_used": total_tokens,
            "avg_tokens_per_test": avg_tokens,
            "total_tool_calls": total_tool_calls,
            "successful_tool_calls": successful_tool_calls
        }
    
    def _calculate_run_summary(self) -> None:
        if not self.current_run:
            return
        
        all_results = []
        for model_result in self.current_run.model_results:
            all_results.extend(model_result.test_results)
        
        total_tests = len(all_results)
        successful_tests = len([r for r in all_results if not r.error])
        
        model_comparison = {}
        for model_result in self.current_run.model_results:
            model_comparison[model_result.model_id] = model_result.summary_stats
        
        self.current_run.metadata.update({
            "total_tests_executed": total_tests,
            "successful_tests": successful_tests,
            "overall_success_rate": successful_tests / total_tests if total_tests > 0 else 0,
            "model_comparison": model_comparison
        })
    
    def _update_progress(self) -> None:
        if not self.current_run or not self.progress_callback:
            return
        
        completed_tests = sum(len(mr.test_results) for mr in self.current_run.model_results)
        total_tests = self.current_run.metadata.get("estimated_total_tests", 0)
        failed_tests = sum(
            len([r for r in mr.test_results if r.error]) 
            for mr in self.current_run.model_results
        )
        
        progress = BenchmarkProgress(
            run_id=self.current_run.run_id,
            total_tests=total_tests,
            completed_tests=completed_tests,
            failed_tests=failed_tests,
            progress_percentage=min(100.0, (completed_tests / total_tests * 100) if total_tests > 0 else 0)
        )
        
        self.progress_callback(progress)
    
    def _save_benchmark_results(self) -> None:
        if not self.current_run:
            return
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        model_names = "_".join(self.current_run.models_to_test)
        if len(model_names) > 50:  # Truncate if too long
            model_names = f"{model_names[:47]}..."
        
        output_file = Path(self.config.output_directory) / f"benchmark_{model_names}_{timestamp}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.current_run.model_dump(), f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"Saved benchmark results to {output_file}")
    
    def _save_model_results(self, model_result: ModelBenchmarkResults) -> None:
        if not self.current_run:
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        output_file = (Path(self.config.output_directory) / 
                      f"model_results_{model_result.model_id}_{timestamp}.json")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(model_result.model_dump(), f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"Saved intermediate results for {model_result.model_id} to {output_file}")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Run LLM benchmark")
    parser.add_argument("--scenarios", required=True, help="Path to scenarios JSON file")
    parser.add_argument("--models", nargs="+", help="Model IDs to test")
    parser.add_argument("--config", help="Path to models config file")
    parser.add_argument("--output", default="results", help="Output directory")
    parser.add_argument("--concurrent", type=int, default=3, help="Concurrent models")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout per test")
    parser.add_argument("--rate-limit", type=float, default=2.0, help="Delay between requests in seconds (default: 2.0 for 30 req/min)")
    parser.add_argument("--name", default="CLI Benchmark", help="Benchmark run name")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    logger.info(f"Loading scenarios from {args.scenarios}")
    with open(args.scenarios, 'r', encoding='utf-8') as f:
        scenarios_data = json.load(f)
    
    generated_scenarios = GeneratedScenarios(**scenarios_data)
    test_cases = generated_scenarios.scenarios
    
    provider_factory = ProviderFactory(args.config) if args.config else ProviderFactory()
    
    if args.models:
        models_to_test = args.models
    else:
        available_models = provider_factory.list_available_models()
        models_to_test = ["mock"] if not available_models else list(available_models.keys())[:3]
    
    config = BenchmarkConfig(
        concurrent_models=args.concurrent,
        timeout_per_test=args.timeout,
        output_directory=args.output
    )
    
    def progress_callback(progress: BenchmarkProgress):
        print(f"Progress: {progress.progress_percentage:.1f}% "
              f"({progress.completed_tests}/{progress.total_tests} tests, "
              f"{progress.failed_tests} failed)")
    
    executor = BenchmarkExecutor(config, provider_factory, progress_callback, rate_limit_delay=args.rate_limit)
    
    logger.info(f"Starting benchmark with {len(test_cases)} scenarios across {len(models_to_test)} models")
    
    run = await executor.run_benchmark(
        test_cases=test_cases,
        model_ids=models_to_test,
        run_name=args.name,
        description=f"CLI benchmark run with {len(test_cases)} test cases"
    )
    
    print(f"\nBenchmark completed!")
    print(f"Run ID: {run.run_id}")
    print(f"Status: {run.status}")
    print(f"Duration: {run.total_duration_ms/1000:.1f}s" if run.total_duration_ms else "N/A")
    print(f"Total tests: {run.metadata.get('total_tests_executed', 0)}")
    print(f"Success rate: {run.metadata.get('overall_success_rate', 0):.1%}")


if __name__ == "__main__":
    asyncio.run(main())