#!/usr/bin/env python3

import sys
import os
import subprocess
from pathlib import Path

def main():
    benchmark_dir = Path(__file__).parent.absolute()
    
    env = os.environ.copy()
    pythonpath = env.get('PYTHONPATH', '')
    if pythonpath:
        env['PYTHONPATH'] = f"{benchmark_dir}:{pythonpath}"
    else:
        env['PYTHONPATH'] = str(benchmark_dir)
    
    cmd = [
        sys.executable, 
        "-m", "src.benchmark.executor"
    ] + sys.argv[1:]
    
    print(f"Running: {' '.join(cmd)}")
    print(f"From directory: {benchmark_dir}")
    print(f"PYTHONPATH: {env.get('PYTHONPATH')}")
    print()
    
    try:
        result = subprocess.run(cmd, cwd=benchmark_dir, env=env, check=True)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        return e.returncode
    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user")
        return 1

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("🇵🇱 Polish LLM Customer Service Benchmark")
        print("=" * 50)
        print()
        print("Usage examples:")
        print()
        print("1. Quick test with Llama 4 Scout (rate-limited):")
        print("   python run_benchmark.py --scenarios scenarios_polish_100.json --models llama_4_scout --rate-limit 3.0")
        print()
        print("2. Test with Ministral 3B:")
        print("   python run_benchmark.py --scenarios scenarios_polish_100.json --models ministral_3b --rate-limit 2.0")
        print()
        print("3. Multiple models (will run sequentially):")
        print("   python run_benchmark.py --scenarios scenarios_polish_100.json --models llama_4_scout ministral_3b --rate-limit 3.0")
        print()
        print("4. Custom name and faster rate:")
        print('   python run_benchmark.py --scenarios scenarios_polish_100.json --models llama_4_scout --rate-limit 2.0 --name "Fast Polish Test"')
        print()
        print("Available options:")
        print("  --scenarios FILE    Polish scenario file (required)")
        print("  --models MODEL...   Model IDs to test")  
        print("  --rate-limit SECS   Delay between requests (default: 2.0)")
        print("  --timeout SECS      Timeout per test (default: 60)")
        print("  --name TEXT         Benchmark run name")
        print("  --output DIR        Output directory (default: current)")
        print()
        print("📁 Results will be saved as:")
        print("   benchmark_{model_name}_{timestamp}.json")
        print("   model_results_{model_name}_{timestamp}.json")
        print()
        sys.exit(1)
    
    sys.exit(main())