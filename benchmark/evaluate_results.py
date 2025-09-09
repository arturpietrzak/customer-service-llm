#!/usr/bin/env python3

import sys
import os
import subprocess
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Evaluate benchmark results using different judge systems")
    parser.add_argument("benchmark_file", help="Path to benchmark results JSON file")
    parser.add_argument("--judge", choices=["llm-judge", "deepeval", "hybrid"], default="llm-judge", 
                       help="Type of judge to use (default: llm-judge)")
    parser.add_argument("--judge-model", default="gemini_2_5_flash_lite",
                       help="Judge model to use (default: gemini_2_5_flash_lite)")
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
        print("Example:")
        print("  python evaluate_results.py results/benchmark_ministral_3b_2025-08-30_00-07.json")
        print()
        print("This will create: gemini_evaluation_[model]_[timestamp].json")
        sys.exit(1)
    
    benchmark_file = sys.argv[1]
    
    if not Path(benchmark_file).exists():
        print(f"❌ Error: File not found: {benchmark_file}")
        sys.exit(1)
    
    if "model_results_" in Path(benchmark_file).name:
        print(f"❌ Error: You're using a model_results_*.json file.")
        print(f"   Evaluation needs a benchmark_*.json file instead.")
        print(f"   Try using: results/benchmark_{Path(benchmark_file).name.replace('model_results_', '')}")
        sys.exit(1)
    
    filename = Path(benchmark_file).name
    if "_" in filename:
        parts = filename.replace("benchmark_", "").replace(".json", "").split("_")
        if len(parts) >= 3:
            model_name = parts[0]
            timestamp = "_".join(parts[1:])
            output_file = f"evaluations/gemini_evaluation_{model_name}_{timestamp}.json"
        else:
            model_name = parts[0] if parts else "unknown"
            output_file = f"evaluations/gemini_evaluation_{model_name}.json"
    else:
        output_file = "evaluations/gemini_evaluation.json"
    
    print(f"🎯 Evaluating: {benchmark_file}")
    print(f"📄 Output: {output_file}")
    print(f"🤖 Judge: Gemini 1.5 Flash")
    print()
    
    benchmark_dir = Path(__file__).parent.absolute()
    
    env = os.environ.copy()
    pythonpath = env.get('PYTHONPATH', '')
    if pythonpath:
        env['PYTHONPATH'] = f"{benchmark_dir}:{pythonpath}"
    else:
        env['PYTHONPATH'] = str(benchmark_dir)
    
    cmd = [
        sys.executable,
        "-m", "src.evaluation.judge",
        "--results", benchmark_file,
        "--judge", "gemini_2_5_flash_lite",
        "--output", output_file
    ]
    
    print(f"Running evaluation...")
    
    try:
        import asyncio
        import json
        
        sys.path.insert(0, str(benchmark_dir))
        
        from src.providers.provider_factory import ProviderFactory
        from src.evaluation.models import EvaluationConfig
        from src.evaluation.judge import LLMJudge
        from src.benchmark.models import BenchmarkRun
        
        with open(benchmark_file, 'r', encoding='utf-8') as f:
            results_data = json.load(f)
        
        benchmark_run = BenchmarkRun(**results_data)
        
        provider_factory = ProviderFactory("config/models_openrouter.yaml")
        eval_config = EvaluationConfig(judge_model="gemini_2_5_flash_lite")  # Use Gemini via OpenRouter
        judge = LLMJudge(eval_config, provider_factory)
        
        async def run_eval():
            return await judge.evaluate_benchmark_run(benchmark_run)
        
        evaluation_results = asyncio.run(run_eval())
        
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(evaluation_results.model_dump(), f, indent=2, ensure_ascii=False, default=str)
        
        print("✅ Evaluation completed successfully!")
        print(f"📊 Results saved to: {output_file}")
        print()
        print("To view results:")
        print(f"  python view_specific_results.py {output_file}")
        
    except Exception as e:
        print(f"❌ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())