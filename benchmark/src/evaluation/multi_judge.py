import asyncio
import json
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
import traceback

from ..providers.base import BaseLLMProvider, ModelConfig, Message
from ..providers.provider_factory import ProviderFactory
from ..benchmark.models import TestResult, BenchmarkRun
from .models import (
    EvaluationResult, EvaluationConfig, CriteriaScore, EvaluationCriteria, 
    ScoreLevel, BatchEvaluationResult, SCORE_VALUES
)
from .judge import LLMJudge

logger = logging.getLogger(__name__)


class MultiJudgeEvaluation:
    def __init__(self, judge_models: List[str], provider_factory: ProviderFactory, base_config: Optional[EvaluationConfig] = None):
        self.judge_models = judge_models
        self.provider_factory = provider_factory
        self.base_config = base_config or EvaluationConfig()
        
        self.judges = {}
        for model_id in judge_models:
            config = EvaluationConfig(
                judge_model=model_id,
                temperature=self.base_config.temperature,
                criteria_weights=self.base_config.criteria_weights,
                max_retries=self.base_config.max_retries,
                timeout_seconds=self.base_config.timeout_seconds
            )
            self.judges[model_id] = LLMJudge(config, provider_factory)
    
    async def evaluate_test_result_multi(
        self, 
        test_result: TestResult, 
        test_case_context: Dict[str, Any]
    ) -> Dict[str, EvaluationResult]:
        logger.info(f"Multi-judge evaluation for test {test_result.test_case_id} using {len(self.judges)} judges")
        
        evaluation_tasks = {}
        for judge_model, judge in self.judges.items():
            task = asyncio.create_task(
                judge.evaluate_test_result(test_result, test_case_context)
            )
            evaluation_tasks[judge_model] = task
        
        judge_evaluations = {}
        for judge_model, task in evaluation_tasks.items():
            try:
                evaluation = await task
                judge_evaluations[judge_model] = evaluation
                logger.debug(f"Judge {judge_model} completed evaluation")
            except Exception as e:
                logger.error(f"Judge {judge_model} failed: {e}")
                judge_evaluations[judge_model] = self._create_fallback_evaluation(
                    test_result, test_case_context, judge_model, str(e)
                )
        
        return judge_evaluations
    
    async def evaluate_benchmark_run_multi(self, benchmark_run: BenchmarkRun) -> Dict[str, BatchEvaluationResult]:
        start_time = time.time()
        
        logger.info(f"Starting multi-judge evaluation with {len(self.judges)} judges")
        logger.info(f"Total test results to evaluate: {len([r for mr in benchmark_run.model_results for r in mr.test_results])}")
        
        judge_tasks = {}
        for judge_model, judge in self.judges.items():
            task = asyncio.create_task(
                judge.evaluate_benchmark_run(benchmark_run)
            )
            judge_tasks[judge_model] = task
        
        judge_results = {}
        for judge_model, task in judge_tasks.items():
            try:
                result = await task
                judge_results[judge_model] = result
                logger.info(f"Judge {judge_model} completed {len(result.results)} evaluations")
            except Exception as e:
                logger.error(f"Judge {judge_model} failed completely: {e}")
                judge_results[judge_model] = BatchEvaluationResult(
                    results=[],
                    summary={"error": str(e), "total_evaluations": 0},
                    config=EvaluationConfig(judge_model=judge_model),
                    total_evaluation_time_ms=0
                )
        
        total_time = (time.time() - start_time) * 1000
        logger.info(f"Multi-judge evaluation completed in {total_time/1000:.2f}s")
        
        return judge_results
    
    def create_consensus_evaluation(
        self, 
        judge_evaluations: Dict[str, List[EvaluationResult]]
    ) -> List[EvaluationResult]:
        logger.info("Creating consensus evaluations from multiple judges")
        test_evaluations = {}
        for judge_model, evaluations in judge_evaluations.items():
            for eval_result in evaluations:
                test_id = eval_result.test_case_id
                if test_id not in test_evaluations:
                    test_evaluations[test_id] = {}
                test_evaluations[test_id][judge_model] = eval_result
        
        consensus_evaluations = []
        
        for test_id, judge_evals in test_evaluations.items():
            consensus = self._create_consensus_for_test(test_id, judge_evals)
            consensus_evaluations.append(consensus)
        
        logger.info(f"Created {len(consensus_evaluations)} consensus evaluations")
        return consensus_evaluations
    
    def _create_consensus_for_test(
        self, 
        test_id: str, 
        judge_evaluations: Dict[str, EvaluationResult]
    ) -> EvaluationResult:
        if not judge_evaluations:
            raise ValueError(f"No evaluations found for test {test_id}")
        first_eval = next(iter(judge_evaluations.values()))
        
        consensus_scores = []
        
        for criteria in EvaluationCriteria:
            criteria_scores = []
            criteria_reasonings = []
            
            for judge_model, evaluation in judge_evaluations.items():
                for score in evaluation.scores:
                    if score.criteria == criteria:
                        criteria_scores.append(score.score_value)
                        criteria_reasonings.append(f"{judge_model}: {score.reasoning}")
                        break
            
            if criteria_scores:
                consensus_score_value = round(sum(criteria_scores) / len(criteria_scores))
                consensus_score_value = max(1, min(5, consensus_score_value))  # Clamp to 1-5
                
                score_level_map = {v: k for k, v in SCORE_VALUES.items()}
                consensus_score_level = score_level_map[consensus_score_value]
                
                combined_reasoning = f"Consensus from {len(criteria_scores)} judges (scores: {criteria_scores}). " + "; ".join(criteria_reasonings)
                
                consensus_scores.append(CriteriaScore(
                    criteria=criteria,
                    score=consensus_score_level,
                    reasoning=combined_reasoning
                ))
        
        overall_scores = [eval.overall_score for eval in judge_evaluations.values()]
        consensus_overall = sum(overall_scores) / len(overall_scores)
        
        additional_notes = []
        for judge_model, evaluation in judge_evaluations.items():
            if evaluation.additional_notes:
                additional_notes.append(f"{judge_model}: {evaluation.additional_notes}")
        
        combined_notes = "; ".join(additional_notes) if additional_notes else None
        
        return EvaluationResult(
            test_case_id=first_eval.test_case_id,
            model_id=first_eval.model_id,
            scenario_type=first_eval.scenario_type,
            user_query=first_eval.user_query,
            model_response=first_eval.model_response,
            expected_behavior=first_eval.expected_behavior,
            scores=consensus_scores,
            overall_score=consensus_overall,
            tool_calls_made=first_eval.tool_calls_made,
            tool_results=first_eval.tool_results,
            judge_model=f"consensus_of_{len(judge_evaluations)}_judges",
            evaluation_timestamp=datetime.now().isoformat(),
            additional_notes=combined_notes
        )
    
    def _create_fallback_evaluation(
        self, 
        test_result: TestResult, 
        test_case_context: Dict[str, Any],
        judge_model: str,
        error_msg: str
    ) -> EvaluationResult:
        scores = []
        for criteria in EvaluationCriteria:
            scores.append(CriteriaScore(
                criteria=criteria,
                score=ScoreLevel.SATISFACTORY,
                reasoning=f"Judge {judge_model} failed: {error_msg}"
            ))
        
        return EvaluationResult(
            test_case_id=test_result.test_case_id,
            model_id=test_result.model_id,
            scenario_type=test_result.scenario_type,
            user_query=test_result.user_query,
            model_response=test_result.model_response.content,
            expected_behavior=test_case_context.get("expected_behavior", ""),
            scores=scores,
            overall_score=3.0,
            tool_calls_made=test_result.tool_calls_made,
            tool_results=test_result.tool_results,
            judge_model=judge_model,
            evaluation_timestamp=datetime.now().isoformat(),
            additional_notes=f"Fallback evaluation due to judge failure: {error_msg}"
        )
    
    def analyze_judge_agreement(self, judge_evaluations: Dict[str, List[EvaluationResult]]) -> Dict[str, Any]:
        logger.info("Analyzing judge agreement")
        
        test_evaluations = {}
        for judge_model, evaluations in judge_evaluations.items():
            for eval_result in evaluations:
                test_id = eval_result.test_case_id
                if test_id not in test_evaluations:
                    test_evaluations[test_id] = {}
                test_evaluations[test_id][judge_model] = eval_result
        
        agreement_stats = {
            "total_comparisons": 0,
            "score_differences": [],
            "criteria_agreement": {criteria.value: [] for criteria in EvaluationCriteria},
            "judge_statistics": {judge: {"avg_score": 0, "total_evaluations": 0} for judge in self.judge_models}
        }
        
        for test_id, judge_evals in test_evaluations.items():
            judge_models = list(judge_evals.keys())
            
            for i, judge1 in enumerate(judge_models):
                for judge2 in judge_models[i+1:]:
                    eval1 = judge_evals[judge1]
                    eval2 = judge_evals[judge2]
                    
                    score_diff = abs(eval1.overall_score - eval2.overall_score)
                    agreement_stats["score_differences"].append(score_diff)
                    agreement_stats["total_comparisons"] += 1
                    
                    for criteria in EvaluationCriteria:
                        score1 = next((s.score_value for s in eval1.scores if s.criteria == criteria), 3)
                        score2 = next((s.score_value for s in eval2.scores if s.criteria == criteria), 3)
                        criteria_diff = abs(score1 - score2)
                        agreement_stats["criteria_agreement"][criteria.value].append(criteria_diff)
        
        for judge_model, evaluations in judge_evaluations.items():
            if evaluations:
                avg_score = sum(e.overall_score for e in evaluations) / len(evaluations)
                agreement_stats["judge_statistics"][judge_model] = {
                    "avg_score": avg_score,
                    "total_evaluations": len(evaluations)
                }
        
        if agreement_stats["score_differences"]:
            agreement_stats["avg_score_difference"] = sum(agreement_stats["score_differences"]) / len(agreement_stats["score_differences"])
            agreement_stats["max_score_difference"] = max(agreement_stats["score_differences"])
        
        for criteria, differences in agreement_stats["criteria_agreement"].items():
            if differences:
                agreement_stats["criteria_agreement"][criteria] = {
                    "avg_difference": sum(differences) / len(differences),
                    "max_difference": max(differences),
                    "agreements_within_1_point": sum(1 for d in differences if d <= 1) / len(differences)
                }
        
        return agreement_stats


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Multi-judge evaluation of benchmark results")
    parser.add_argument("--results", required=True, help="Path to benchmark results JSON file")
    parser.add_argument("--judges", nargs="+", default=["gemini_2_5_flash_lite", "gpt_5_mini"], 
                       help="Judge models to use")
    parser.add_argument("--output", help="Output file for evaluation results")
    parser.add_argument("--consensus", action="store_true", help="Create consensus evaluation")
    parser.add_argument("--config", help="Path to models config file")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    logger.info(f"Loading benchmark results from {args.results}")
    with open(args.results, 'r', encoding='utf-8') as f:
        results_data = json.load(f)
    
    benchmark_run = BenchmarkRun(**results_data)
    
    provider_factory = ProviderFactory(args.config) if args.config else ProviderFactory()
    
    multi_judge = MultiJudgeEvaluation(
        judge_models=args.judges,
        provider_factory=provider_factory
    )
    
    logger.info(f"Starting multi-judge evaluation with judges: {', '.join(args.judges)}")
    judge_results = await multi_judge.evaluate_benchmark_run_multi(benchmark_run)
    
    for judge_model, results in judge_results.items():
        output_file = args.output or f"evaluation_results_{judge_model}_{benchmark_run.run_id}.json"
        judge_output = output_file.replace(".json", f"_{judge_model}.json")
        
        with open(judge_output, 'w', encoding='utf-8') as f:
            json.dump(results.model_dump(), f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"Saved {judge_model} results to {judge_output}")
    
    if args.consensus:
        judge_evaluations = {judge: results.results for judge, results in judge_results.items()}
        consensus_evaluations = multi_judge.create_consensus_evaluation(judge_evaluations)
        
        agreement_analysis = multi_judge.analyze_judge_agreement(judge_evaluations)
        
        consensus_output = args.output or f"evaluation_consensus_{benchmark_run.run_id}.json"
        consensus_data = {
            "consensus_evaluations": [eval.model_dump() for eval in consensus_evaluations],
            "judge_agreement_analysis": agreement_analysis,
            "judges_used": args.judges,
            "evaluation_timestamp": datetime.now().isoformat()
        }
        
        with open(consensus_output, 'w', encoding='utf-8') as f:
            json.dump(consensus_data, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"Saved consensus results to {consensus_output}")
        
        print(f"\nMulti-Judge Evaluation Summary:")
        print(f"Judges used: {', '.join(args.judges)}")
        print(f"Total evaluations per judge: {len(consensus_evaluations)}")
        print(f"Average score difference between judges: {agreement_analysis.get('avg_score_difference', 0):.2f}")
        print(f"Maximum score difference: {agreement_analysis.get('max_score_difference', 0):.2f}")
        
        print(f"\nJudge Statistics:")
        for judge, stats in agreement_analysis.get('judge_statistics', {}).items():
            print(f"  {judge}: {stats['avg_score']:.2f} avg score ({stats['total_evaluations']} evaluations)")


if __name__ == "__main__":
    asyncio.run(main())