#!/usr/bin/env python3

import sys
import os
import argparse
import asyncio
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Evaluate benchmark results using different judge systems")
    parser.add_argument("benchmark_file", help="Path to benchmark results JSON file")
    parser.add_argument("--judge", choices=["llm-judge", "deepeval", "hybrid"], default="llm-judge", 
                       help="Type of judge to use (default: llm-judge)")
    parser.add_argument("--judge-model", default="gpt_4o_mini_judge",
                       help="Judge model to use (default: gpt_4o_mini_judge)")
    parser.add_argument("--output", help="Output file path (auto-generated if not provided)")
    parser.add_argument("--compare", action="store_true", help="Save detailed comparison results for hybrid evaluation")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.benchmark_file):
        print(f"❌ Benchmark file not found: {args.benchmark_file}")
        print()
        print("Available benchmark files:")
        
        results_dir = Path(".")
        benchmark_files = list(results_dir.glob("**/benchmark_*.json"))
        
        if benchmark_files:
            for i, filepath in enumerate(benchmark_files, 1):
                print(f"  {i}. {filepath}")
        else:
            print("  No benchmark files found!")
        
        print()
        print("Example usage:")
        print(f"  python {sys.argv[0]} results/benchmark_gpt_5.json --judge deepeval")
        print(f"  python {sys.argv[0]} results/benchmark_gpt_5.json --judge hybrid --compare")
        return 1
    
    benchmark_file = args.benchmark_file
    judge_type = args.judge
    judge_model = args.judge_model
    
    if "model_results_" in Path(benchmark_file).name:
        print(f"❌ Error: You're using a model_results_*.json file.")
        print(f"   Evaluation needs a benchmark_*.json file instead.")
        print(f"   Try using: results/benchmark_{Path(benchmark_file).name.replace('model_results_', '')}")
        return 1
    
    print(f"🤖 EVALUATION STARTING - {judge_type.upper()}")
    print("=" * 50)
    print()
    
    benchmark_path = Path(benchmark_file)
    if args.output:
        output_file = args.output
    else:
        if benchmark_path.name.startswith("benchmark_"):
            name_without_prefix = benchmark_path.stem[10:]
            parts = name_without_prefix.split("_")
            if len(parts) >= 2:
                model_name = "_".join(parts[:-1])
                timestamp = parts[-1]
                judge_prefix = judge_type.replace("-", "_")
                output_file = f"evaluations/{judge_prefix}_evaluation_{model_name}_{timestamp}.json"
            else:
                model_name = parts[0] if parts else "unknown"
                judge_prefix = judge_type.replace("-", "_")
                output_file = f"evaluations/{judge_prefix}_evaluation_{model_name}.json"
        else:
            judge_prefix = judge_type.replace("-", "_")
            output_file = f"evaluations/{judge_prefix}_evaluation.json"
    
    print(f"🎯 Evaluating: {benchmark_file}")
    print(f"📄 Output: {output_file}")
    print(f"🤖 Judge Type: {judge_type}")
    print(f"🤖 Judge Model: {judge_model}")
    if args.compare and judge_type == "hybrid":
        comparison_file = output_file.replace(".json", "_comparison.json")
        print(f"📊 Comparison Output: {comparison_file}")
    print()
    
    benchmark_dir = Path(__file__).parent.absolute()
    
    sys.path.insert(0, str(benchmark_dir))
    
    try:
        return asyncio.run(run_evaluation(
            benchmark_file, judge_type, judge_model, output_file, 
            comparison_file if args.compare and judge_type == "hybrid" else None
        ))
        
    except Exception as e:
        print(f"❌ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


async def run_evaluation(benchmark_file: str, judge_type: str, judge_model: str, output_file: str, comparison_file: str = None):
    try:
        from src.providers.provider_factory import ProviderFactory
        from src.evaluation.models import EvaluationConfig
        from src.evaluation.hybrid_evaluator import EvaluatorFactory
        from src.benchmark.models import BenchmarkRun
        
        print("Loading benchmark results...")
        
        with open(benchmark_file, 'r', encoding='utf-8') as f:
            results_data = json.load(f)
        
        benchmark_run = BenchmarkRun(**results_data)
        print(f"✅ Loaded {len(benchmark_run.model_results)} model results")
        
        provider_factory = ProviderFactory("config/models_openrouter.yaml")
        eval_config = EvaluationConfig(
            judge_model=judge_model,
            judge_provider="openrouter",
            temperature=0.1
        )
        
        print(f"Creating {judge_type} evaluator...")
        
        evaluator = EvaluatorFactory.create_evaluator(judge_type, eval_config, provider_factory)
        
        print("Running evaluation...")
        
        if judge_type == "hybrid":
            batch_result, comparison_results = await evaluator.evaluate_benchmark_run_hybrid(benchmark_run)
            
            if comparison_file:
                print(f"Saving comparison results to {comparison_file}")
                evaluator.save_comparison_results(comparison_results, comparison_file)
        else:
            batch_result = await evaluator.evaluate_benchmark_run(benchmark_run)
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"Saving evaluation results to {output_file}")
        with open(output_file, 'w', encoding='utf-8') as f:
            output_data = {
                "results": [result.dict() for result in batch_result.results],
                "summary": batch_result.summary,
                "config": batch_result.config.dict(),
                "total_evaluation_time_ms": batch_result.total_evaluation_time_ms,
                "evaluation_framework": judge_type,
                "generation_timestamp": batch_result.results[0].evaluation_timestamp if batch_result.results else None
            }
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print()
        print("✅ Evaluation completed successfully!")
        print(f"📊 Summary:")
        print(f"   • Total evaluations: {batch_result.summary.get('total_evaluations', 0)}")
        print(f"   • Overall mean score: {batch_result.summary.get('overall_mean_score', 0):.2f}")
        print(f"   • Evaluation time: {batch_result.total_evaluation_time_ms/1000:.1f} seconds")
        
        if judge_type == "hybrid" and comparison_file:
            print(f"   • Agreement analysis saved to: {comparison_file}")
        
        return 0
        
    except ImportError as e:
        print(f"❌ Import error - missing dependencies: {e}")
        print("   Make sure to install requirements: pip install -r requirements.txt")
        return 1
    except Exception as e:
        print(f"❌ Evaluation error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def show_usage():
    print()
    print("📖 Usage Examples:")
    print("=" * 30)
    print()
    print("# Use traditional LLM judge (Gemini)")
    print("python evaluate_results_new.py results/benchmark_gpt_5.json")
    print()
    print("# Use DeepEval framework")
    print("python evaluate_results_new.py results/benchmark_gpt_5.json --judge deepeval")
    print()
    print("# Compare both judges with detailed analysis")
    print("python evaluate_results_new.py results/benchmark_gpt_5.json --judge hybrid --compare")
    print()
    print("# Use different judge model")
    print("python evaluate_results_new.py results/benchmark_gpt_5.json --judge-model gpt_4o_mini_judge")
    print()
    print("# Custom output location")
    print("python evaluate_results_new.py results/benchmark_gpt_5.json --output my_eval.json")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        show_usage()
        sys.exit(1)
    
    sys.exit(main())