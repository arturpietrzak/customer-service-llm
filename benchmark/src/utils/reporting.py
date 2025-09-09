import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

from ..benchmark.models import BenchmarkRun
from ..evaluation.models import BatchEvaluationResult, EvaluationResult

logger = logging.getLogger(__name__)


class BenchmarkReporter:
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
    
    def generate_full_report(
        self, 
        benchmark_run: BenchmarkRun,
        evaluation_results: Optional[BatchEvaluationResult] = None,
        report_name: str = "benchmark_report"
    ) -> Dict[str, str]:
        logger.info(f"Generating full benchmark report: {report_name}")
        
        report_dir = self.output_dir / report_name
        report_dir.mkdir(parents=True, exist_ok=True)
        
        generated_files = {}
        
        summary_file = self._generate_summary_report(benchmark_run, evaluation_results, report_dir)
        generated_files["summary"] = str(summary_file)
        
        if benchmark_run.model_results:
            perf_files = self._generate_performance_plots(benchmark_run, report_dir)
            generated_files.update(perf_files)
        
        if evaluation_results:
            eval_files = self._generate_evaluation_plots(evaluation_results, report_dir)
            generated_files.update(eval_files)
        
        data_files = self._export_detailed_data(benchmark_run, evaluation_results, report_dir)
        generated_files.update(data_files)
        
        html_file = self._generate_html_report(benchmark_run, evaluation_results, report_dir, generated_files)
        generated_files["html_report"] = str(html_file)
        
        logger.info(f"Generated {len(generated_files)} report files in {report_dir}")
        return generated_files
    
    def _generate_summary_report(
        self, 
        benchmark_run: BenchmarkRun, 
        evaluation_results: Optional[BatchEvaluationResult],
        output_dir: Path
    ) -> Path:
        summary_file = output_dir / "summary.md"
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(f"# Benchmark Report: {benchmark_run.name}\n\n")
            f.write(f"**Run ID:** {benchmark_run.run_id}\n")
            f.write(f"**Status:** {benchmark_run.status}\n")
            f.write(f"**Start Time:** {benchmark_run.start_time}\n")
            f.write(f"**Duration:** {benchmark_run.total_duration_ms/1000:.2f}s\n\n" if benchmark_run.total_duration_ms else "")
            
            if benchmark_run.description:
                f.write(f"**Description:** {benchmark_run.description}\n\n")
            
            f.write("## Test Overview\n\n")
            f.write(f"- **Total Test Cases:** {len(benchmark_run.test_cases)}\n")
            f.write(f"- **Models Tested:** {len(benchmark_run.models_to_test)}\n")
            f.write(f"- **Total Tests Executed:** {benchmark_run.metadata.get('total_tests_executed', 0)}\n")
            f.write(f"- **Overall Success Rate:** {benchmark_run.metadata.get('overall_success_rate', 0):.1%}\n\n")
            
            correct_tests = len([tc for tc in benchmark_run.test_cases if tc.scenario_type == "correct"])
            incorrect_tests = len([tc for tc in benchmark_run.test_cases if tc.scenario_type == "incorrect"])
            malicious_tests = len([tc for tc in benchmark_run.test_cases if tc.scenario_type == "malicious"])
            
            f.write("### Test Cases by Scenario Type\n\n")
            f.write(f"- **Correct Scenarios:** {correct_tests}\n")
            f.write(f"- **Incorrect Scenarios:** {incorrect_tests}\n")
            f.write(f"- **Malicious Scenarios:** {malicious_tests}\n\n")
            
            f.write("## Model Performance\n\n")
            for model_result in benchmark_run.model_results:
                f.write(f"### {model_result.model_name} ({model_result.provider})\n\n")
                f.write(f"- **Status:** {model_result.status}\n")
                f.write(f"- **Tests Completed:** {len(model_result.test_results)}\n")
                
                if model_result.summary_stats:
                    stats = model_result.summary_stats
                    f.write(f"- **Success Rate:** {stats.get('success_rate', 0):.1%}\n")
                    f.write(f"- **Avg Execution Time:** {stats.get('avg_execution_time_ms', 0):.0f}ms\n")
                    f.write(f"- **Total Tokens Used:** {stats.get('total_tokens_used', 0):,}\n")
                    f.write(f"- **Tool Calls Made:** {stats.get('total_tool_calls', 0)}\n")
                f.write("\n")
            
            if evaluation_results:
                f.write("## Evaluation Results\n\n")
                f.write(f"- **Judge Model:** {evaluation_results.config.judge_model}\n")
                f.write(f"- **Total Evaluations:** {evaluation_results.summary.get('total_evaluations', 0)}\n")
                f.write(f"- **Average Overall Score:** {evaluation_results.summary.get('average_overall_score', 0):.2f}/5.0\n\n")
                
                if 'by_model' in evaluation_results.summary:
                    f.write("### Model Rankings\n\n")
                    model_scores = []
                    for model_id, stats in evaluation_results.summary['by_model'].items():
                        model_scores.append((model_id, stats['average_score']))
                    
                    model_scores.sort(key=lambda x: x[1], reverse=True)
                    
                    for i, (model_id, score) in enumerate(model_scores, 1):
                        f.write(f"{i}. **{model_id}:** {score:.2f}/5.0\n")
                    f.write("\n")
        
        return summary_file
    
    def _generate_performance_plots(self, benchmark_run: BenchmarkRun, output_dir: Path) -> Dict[str, str]:
        files = {}
        
        # Prepare data
        model_data = []
        for model_result in benchmark_run.model_results:
            if model_result.summary_stats:
                model_data.append({
                    'model': model_result.model_name,
                    'success_rate': model_result.summary_stats.get('success_rate', 0),
                    'avg_time_ms': model_result.summary_stats.get('avg_execution_time_ms', 0),
                    'total_tokens': model_result.summary_stats.get('total_tokens_used', 0),
                    'tool_calls': model_result.summary_stats.get('total_tool_calls', 0)
                })
        
        if not model_data:
            return files
        
        df = pd.DataFrame(model_data)
        
        plt.figure(figsize=(10, 6))
        bars = plt.bar(df['model'], df['success_rate'])
        plt.title('Model Success Rate Comparison')
        plt.xlabel('Model')
        plt.ylabel('Success Rate')
        plt.xticks(rotation=45)
        plt.ylim(0, 1)
        
        for bar, rate in zip(bars, df['success_rate']):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01, 
                    f'{rate:.1%}', ha='center', va='bottom')
        
        plt.tight_layout()
        success_file = output_dir / "success_rate_comparison.png"
        plt.savefig(success_file, dpi=300, bbox_inches='tight')
        plt.close()
        files["success_rate_plot"] = str(success_file)
        
        plt.figure(figsize=(10, 6))
        bars = plt.bar(df['model'], df['avg_time_ms'])
        plt.title('Average Response Time Comparison')
        plt.xlabel('Model')
        plt.ylabel('Average Response Time (ms)')
        plt.xticks(rotation=45)
        
        for bar, time_ms in zip(bars, df['avg_time_ms']):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(df['avg_time_ms']) * 0.01,
                    f'{time_ms:.0f}ms', ha='center', va='bottom')
        
        plt.tight_layout()
        time_file = output_dir / "response_time_comparison.png"
        plt.savefig(time_file, dpi=300, bbox_inches='tight')
        plt.close()
        files["response_time_plot"] = str(time_file)
        
        if any(df['total_tokens'] > 0):
            plt.figure(figsize=(10, 6))
            bars = plt.bar(df['model'], df['total_tokens'])
            plt.title('Total Token Usage Comparison')
            plt.xlabel('Model')
            plt.ylabel('Total Tokens Used')
            plt.xticks(rotation=45)
            
            for bar, tokens in zip(bars, df['total_tokens']):
                plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(df['total_tokens']) * 0.01,
                        f'{tokens:,}', ha='center', va='bottom')
            
            plt.tight_layout()
            tokens_file = output_dir / "token_usage_comparison.png"
            plt.savefig(tokens_file, dpi=300, bbox_inches='tight')
            plt.close()
            files["token_usage_plot"] = str(tokens_file)
        
        return files
    
    def _generate_evaluation_plots(self, evaluation_results: BatchEvaluationResult, output_dir: Path) -> Dict[str, str]:
        files = {}
        
        if not evaluation_results.results:
            return files
        
        eval_data = []
        for result in evaluation_results.results:
            eval_data.append({
                'model': result.model_id,
                'scenario': result.scenario_type,
                'overall_score': result.overall_score,
                **{score.criteria.value: score.score_value for score in result.scores}
            })
        
        eval_df = pd.DataFrame(eval_data)
        
        plt.figure(figsize=(12, 6))
        models = eval_df['model'].unique()
        for model in models:
            model_scores = eval_df[eval_df['model'] == model]['overall_score']
            plt.hist(model_scores, alpha=0.6, label=model, bins=20)
        
        plt.title('Overall Score Distribution by Model')
        plt.xlabel('Overall Score')
        plt.ylabel('Frequency')
        plt.legend()
        plt.tight_layout()
        
        dist_file = output_dir / "score_distribution_by_model.png"
        plt.savefig(dist_file, dpi=300, bbox_inches='tight')
        plt.close()
        files["score_distribution_plot"] = str(dist_file)
        
        criteria_cols = ['accuracy', 'helpfulness', 'safety', 'tool_usage', 'response_quality']
        available_criteria = [col for col in criteria_cols if col in eval_df.columns]
        
        if available_criteria:
            criteria_means = eval_df[available_criteria].mean()
            
            plt.figure(figsize=(10, 6))
            bars = plt.bar(criteria_means.index, criteria_means.values)
            plt.title('Average Scores by Evaluation Criteria')
            plt.xlabel('Criteria')
            plt.ylabel('Average Score (1-5)')
            plt.xticks(rotation=45)
            plt.ylim(0, 5)
            
            for bar, score in zip(bars, criteria_means.values):
                plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                        f'{score:.2f}', ha='center', va='bottom')
            
            plt.tight_layout()
            criteria_file = output_dir / "criteria_scores.png"
            plt.savefig(criteria_file, dpi=300, bbox_inches='tight')
            plt.close()
            files["criteria_scores_plot"] = str(criteria_file)
        
        scenario_pivot = eval_df.pivot_table(values='overall_score', index='model', columns='scenario', aggfunc='mean')
        
        plt.figure(figsize=(8, 6))
        sns.heatmap(scenario_pivot, annot=True, cmap='RdYlGn', vmin=1, vmax=5, fmt='.2f')
        plt.title('Model Performance by Scenario Type')
        plt.tight_layout()
        
        heatmap_file = output_dir / "model_scenario_heatmap.png"
        plt.savefig(heatmap_file, dpi=300, bbox_inches='tight')
        plt.close()
        files["scenario_heatmap_plot"] = str(heatmap_file)
        
        return files
    
    def _export_detailed_data(
        self, 
        benchmark_run: BenchmarkRun, 
        evaluation_results: Optional[BatchEvaluationResult],
        output_dir: Path
    ) -> Dict[str, str]:
        """Export detailed data to CSV files."""
        files = {}
        
        test_data = []
        for model_result in benchmark_run.model_results:
            for test_result in model_result.test_results:
                test_data.append({
                    'test_case_id': test_result.test_case_id,
                    'model_id': test_result.model_id,
                    'scenario_type': test_result.scenario_type,
                    'user_query': test_result.user_query,
                    'model_response': test_result.model_response.content,
                    'execution_time_ms': test_result.execution_time_ms,
                    'error': test_result.error,
                    'tool_calls_made': len(test_result.tool_calls_made),
                    'timestamp': test_result.timestamp
                })
        
        if test_data:
            test_df = pd.DataFrame(test_data)
            test_file = output_dir / "detailed_test_results.csv"
            test_df.to_csv(test_file, index=False, encoding='utf-8')
            files["test_results_csv"] = str(test_file)
        
        if evaluation_results and evaluation_results.results:
            eval_data = []
            for result in evaluation_results.results:
                base_data = {
                    'test_case_id': result.test_case_id,
                    'model_id': result.model_id,
                    'scenario_type': result.scenario_type,
                    'user_query': result.user_query,
                    'model_response': result.model_response,
                    'overall_score': result.overall_score,
                    'judge_model': result.judge_model,
                    'evaluation_timestamp': result.evaluation_timestamp
                }
                
                for score in result.scores:
                    base_data[f'{score.criteria.value}_score'] = score.score_value
                    base_data[f'{score.criteria.value}_reasoning'] = score.reasoning
                
                eval_data.append(base_data)
            
            eval_df = pd.DataFrame(eval_data)
            eval_file = output_dir / "detailed_evaluation_results.csv"
            eval_df.to_csv(eval_file, index=False, encoding='utf-8')
            files["evaluation_results_csv"] = str(eval_file)
        
        return files
    
    def _generate_html_report(
        self,
        benchmark_run: BenchmarkRun,
        evaluation_results: Optional[BatchEvaluationResult],
        output_dir: Path,
        generated_files: Dict[str, str]
    ) -> Path:
        html_file = output_dir / "index.html"
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Benchmark Report: {benchmark_run.name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
        .header {{ background-color: #f4f4f4; padding: 20px; border-radius: 5px; margin-bottom: 30px; }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
        .metric-label {{ font-size: 14px; color: #7f8c8d; }}
        .section {{ margin: 30px 0; }}
        .plot {{ text-align: center; margin: 20px 0; }}
        .plot img {{ max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .download-links {{ background-color: #ecf0f1; padding: 15px; border-radius: 5px; }}
        .download-links a {{ margin: 0 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Benchmark Report: {benchmark_run.name}</h1>
        <p><strong>Run ID:</strong> {benchmark_run.run_id}</p>
        <p><strong>Status:</strong> {benchmark_run.status}</p>
        <p><strong>Duration:</strong> {benchmark_run.total_duration_ms/1000:.2f}s</p>
    </div>
    
    <div class="section">
        <h2>Overview</h2>
        <div class="metric">
            <div class="metric-value">{len(benchmark_run.test_cases)}</div>
            <div class="metric-label">Test Cases</div>
        </div>
        <div class="metric">
            <div class="metric-value">{len(benchmark_run.models_to_test)}</div>
            <div class="metric-label">Models Tested</div>
        </div>
        <div class="metric">
            <div class="metric-value">{benchmark_run.metadata.get('total_tests_executed', 0)}</div>
            <div class="metric-label">Total Tests</div>
        </div>
        <div class="metric">
            <div class="metric-value">{benchmark_run.metadata.get('overall_success_rate', 0):.1%}</div>
            <div class="metric-label">Success Rate</div>
        </div>
    </div>
        """
        
        if 'success_rate_plot' in generated_files:
            html_content += f"""
    <div class="section">
        <h2>Performance Analysis</h2>
        <div class="plot">
            <h3>Success Rate Comparison</h3>
            <img src="{Path(generated_files['success_rate_plot']).name}" alt="Success Rate Comparison">
        </div>
            """
        
        if 'response_time_plot' in generated_files:
            html_content += f"""
        <div class="plot">
            <h3>Response Time Comparison</h3>
            <img src="{Path(generated_files['response_time_plot']).name}" alt="Response Time Comparison">
        </div>
            """
        
        if 'token_usage_plot' in generated_files:
            html_content += f"""
        <div class="plot">
            <h3>Token Usage Comparison</h3>
            <img src="{Path(generated_files['token_usage_plot']).name}" alt="Token Usage Comparison">
        </div>
    </div>
            """
        
        if evaluation_results and 'score_distribution_plot' in generated_files:
            html_content += f"""
    <div class="section">
        <h2>Evaluation Results</h2>
        <div class="metric">
            <div class="metric-value">{evaluation_results.summary.get('average_overall_score', 0):.2f}</div>
            <div class="metric-label">Avg Overall Score</div>
        </div>
        <div class="plot">
            <h3>Score Distribution</h3>
            <img src="{Path(generated_files['score_distribution_plot']).name}" alt="Score Distribution">
        </div>
            """
            
        if 'criteria_scores_plot' in generated_files:
            html_content += f"""
        <div class="plot">
            <h3>Criteria Scores</h3>
            <img src="{Path(generated_files['criteria_scores_plot']).name}" alt="Criteria Scores">
        </div>
            """
        
        if 'scenario_heatmap_plot' in generated_files:
            html_content += f"""
        <div class="plot">
            <h3>Model vs Scenario Performance</h3>
            <img src="{Path(generated_files['scenario_heatmap_plot']).name}" alt="Scenario Heatmap">
        </div>
    </div>
            """
        
        html_content += """
    <div class="section">
        <h2>Downloads</h2>
        <div class="download-links">
            <p>Download detailed data:</p>
        """
        
        if 'test_results_csv' in generated_files:
            html_content += f'<a href="{Path(generated_files["test_results_csv"]).name}">Test Results (CSV)</a>'
        
        if 'evaluation_results_csv' in generated_files:
            html_content += f'<a href="{Path(generated_files["evaluation_results_csv"]).name}">Evaluation Results (CSV)</a>'
        
        if 'summary' in generated_files:
            html_content += f'<a href="{Path(generated_files["summary"]).name}">Summary Report (Markdown)</a>'
        
        html_content += """
        </div>
    </div>
    
</body>
</html>
        """
        
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return html_file


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate benchmark report")
    parser.add_argument("--benchmark", required=True, help="Path to benchmark results JSON")
    parser.add_argument("--evaluation", help="Path to evaluation results JSON")
    parser.add_argument("--output", default="reports", help="Output directory")
    parser.add_argument("--name", default="benchmark_report", help="Report name")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    logger.info(f"Loading benchmark results from {args.benchmark}")
    with open(args.benchmark, 'r', encoding='utf-8') as f:
        benchmark_data = json.load(f)
    
    benchmark_run = BenchmarkRun(**benchmark_data)
    
    evaluation_results = None
    if args.evaluation:
        logger.info(f"Loading evaluation results from {args.evaluation}")
        with open(args.evaluation, 'r', encoding='utf-8') as f:
            eval_data = json.load(f)
        evaluation_results = BatchEvaluationResult(**eval_data)
    
    reporter = BenchmarkReporter(args.output)
    generated_files = reporter.generate_full_report(
        benchmark_run=benchmark_run,
        evaluation_results=evaluation_results,
        report_name=args.name
    )
    
    print(f"\nGenerated benchmark report '{args.name}':")
    for file_type, file_path in generated_files.items():
        print(f"  - {file_type}: {file_path}")
    
    print(f"\nOpen {generated_files.get('html_report', 'N/A')} in your browser to view the report.")


if __name__ == "__main__":
    main()