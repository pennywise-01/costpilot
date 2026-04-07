"""Code complexity analysis script.

This script analyzes Python code complexity metrics including:
- Function length
- Cyclomatic complexity
- Nesting depth

Usage:
    python scripts/analyze_complexity.py backend/app
"""

import ast
import sys
import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
from collections import defaultdict


@dataclass
class ComplexityMetrics:
    """Complexity metrics for a function."""
    filename: str
    function_name: str
    lines: int
    cyclomatic_complexity: int
    nesting_depth: int
    args_count: int


class ComplexityAnalyzer(ast.NodeVisitor):
    """Analyze Python code complexity."""

    def __init__(self, filename: str):
        self.filename = filename
        self.functions: List[ComplexityMetrics] = []
        self.current_function: Optional[str] = None
        self.current_complexity = 0
        self.current_depth = 0
        self.max_depth = 0
        self.current_args = 0

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._analyze_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._analyze_function(node)

    def _analyze_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        """Analyze a function definition."""
        # Save current state
        old_function = self.current_function
        old_complexity = self.current_complexity
        old_depth = self.current_depth
        old_max_depth = self.max_depth
        old_args = self.current_args

        # Set new state
        self.current_function = node.name
        self.current_complexity = 1  # Base complexity
        self.current_depth = 0
        self.max_depth = 0
        self.current_args = len(node.args.args) + len(node.args.kwonlyargs)
        if node.args.vararg:
            self.current_args += 1
        if node.args.kwarg:
            self.current_args += 1

        # Count lines
        lines = node.end_lineno - node.lineno if node.end_lineno else 0

        # Visit function body
        for item in node.body:
            self.visit(item)

        # Store metrics
        self.functions.append(ComplexityMetrics(
            filename=self.filename,
            function_name=self.current_function,
            lines=lines,
            cyclomatic_complexity=self.current_complexity,
            nesting_depth=self.max_depth,
            args_count=self.current_args
        ))

        # Restore state
        self.current_function = old_function
        self.current_complexity = old_complexity
        self.current_depth = old_depth
        self.max_depth = old_max_depth
        self.current_args = old_args

    def visit_If(self, node: ast.If):
        self.current_complexity += 1
        self._visit_nested(node)

    def visit_For(self, node: ast.For):
        self.current_complexity += 1
        self._visit_nested(node)

    def visit_While(self, node: ast.While):
        self.current_complexity += 1
        self._visit_nested(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        self.current_complexity += 1
        self._visit_nested(node)

    def visit_With(self, node: ast.With):
        self._visit_nested(node)

    def visit_Try(self, node: ast.Try):
        self._visit_nested(node)

    def visit_TryStar(self, node: ast.TryStar):
        self._visit_nested(node)

    def _visit_nested(self, node: ast.AST):
        """Visit a nested block."""
        self.current_depth += 1
        self.max_depth = max(self.max_depth, self.current_depth)
        self.generic_visit(node)
        self.current_depth -= 1


def analyze_file(filepath: Path) -> List[ComplexityMetrics]:
    """Analyze a single Python file.

    Args:
        filepath: Path to Python file

    Returns:
        List of complexity metrics for functions in the file
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())

        analyzer = ComplexityAnalyzer(str(filepath))
        analyzer.visit(tree)
        return analyzer.functions
    except SyntaxError as e:
        print(f"Syntax error in {filepath}: {e}")
        return []
    except Exception as e:
        print(f"Error analyzing {filepath}: {e}")
        return []


def analyze_project(project_path: str) -> List[ComplexityMetrics]:
    """Analyze all Python files in a project.

    Args:
        project_path: Path to project directory

    Returns:
        List of complexity metrics for all functions
    """
    all_metrics = []
    path = Path(project_path)

    for py_file in path.rglob("*.py"):
        # Skip common directories
        if any(part.startswith('.') or part in ['venv', '__pycache__', 'node_modules']
               for part in py_file.parts):
            continue

        metrics = analyze_file(py_file)
        all_metrics.extend(metrics)

    return all_metrics


def print_complexity_report(metrics: List[ComplexityMetrics]):
    """Print complexity analysis report.

    Args:
        metrics: List of complexity metrics
    """
    if not metrics:
        print("No functions found to analyze.")
        return

    # Sort by different metrics
    by_complexity = sorted(metrics, key=lambda x: x.cyclomatic_complexity, reverse=True)
    by_lines = sorted(metrics, key=lambda x: x.lines, reverse=True)
    by_depth = sorted(metrics, key=lambda x: x.nesting_depth, reverse=True)

    print("=" * 80)
    print("CODE COMPLEXITY ANALYSIS REPORT")
    print("=" * 80)

    print("\n📊 TOP 10 MOST COMPLEX FUNCTIONS (Cyclomatic Complexity)")
    print("-" * 80)
    for i, m in enumerate(by_complexity[:10], 1):
        print(f"  {i}. {m.cyclomatic_complexity} complexity: {m.filename}::{m.function_name}")

    print("\n📏 TOP 10 LONGEST FUNCTIONS")
    print("-" * 80)
    for i, m in enumerate(by_lines[:10], 1):
        status = "⚠️ " if m.lines > 50 else "  "
        print(f"  {i}. {status}{m.lines} lines: {m.filename}::{m.function_name}")

    print("\n🔀 TOP 10 DEEPLY NESTED FUNCTIONS")
    print("-" * 80)
    for i, m in enumerate(by_depth[:10], 1):
        status = "⚠️ " if m.nesting_depth > 4 else "  "
        print(f"  {i}. {status}depth {m.nesting_depth}: {m.filename}::{m.function_name}")

    # Summary statistics
    print("\n📈 SUMMARY STATISTICS")
    print("-" * 80)
    print(f"  Total functions analyzed: {len(metrics)}")
    print(f"  High complexity (>10): {sum(1 for m in metrics if m.cyclomatic_complexity > 10)}")
    print(f"  Long functions (>50 lines): {sum(1 for m in metrics if m.lines > 50)}")
    print(f"  Deep nesting (>4): {sum(1 for m in metrics if m.nesting_depth > 4)}")
    print(f"  Many args (>5): {sum(1 for m in metrics if m.args_count > 5)}")

    # Averages
    avg_complexity = sum(m.cyclomatic_complexity for m in metrics) / len(metrics)
    avg_lines = sum(m.lines for m in metrics) / len(metrics)
    print(f"\n  Average cyclomatic complexity: {avg_complexity:.2f}")
    print(f"  Average function length: {avg_lines:.2f} lines")

    # Files with most issues
    print("\n📁 FILES WITH MOST COMPLEXITY ISSUES")
    print("-" * 80)
    file_issues = defaultdict(lambda: {"high_complexity": 0, "long_functions": 0, "deep_nesting": 0})
    for m in metrics:
        if m.cyclomatic_complexity > 10:
            file_issues[m.filename]["high_complexity"] += 1
        if m.lines > 50:
            file_issues[m.filename]["long_functions"] += 1
        if m.nesting_depth > 4:
            file_issues[m.filename]["deep_nesting"] += 1

    # Sort by total issues
    sorted_files = sorted(
        file_issues.items(),
        key=lambda x: sum(x[1].values()),
        reverse=True
    )[:10]

    for filepath, issues in sorted_files:
        total = sum(issues.values())
        print(f"  {filepath}: {total} issues")
        if issues["high_complexity"]:
            print(f"    - High complexity: {issues['high_complexity']}")
        if issues["long_functions"]:
            print(f"    - Long functions: {issues['long_functions']}")
        if issues["deep_nesting"]:
            print(f"    - Deep nesting: {issues['deep_nesting']}")

    # Recommendations
    print("\n💡 RECOMMENDATIONS")
    print("-" * 80)
    recommendations = []

    if avg_complexity > 8:
        recommendations.append("Consider refactoring high-complexity functions (>10)")
    if avg_lines > 30:
        recommendations.append("Consider breaking down long functions (>50 lines)")
    if any(m.nesting_depth > 4 for m in metrics):
        recommendations.append("Reduce nesting depth by extracting helper functions")
    if any(m.args_count > 5 for m in metrics):
        recommendations.append("Consider using dataclasses for functions with many arguments")

    if recommendations:
        for rec in recommendations:
            print(f"  • {rec}")
    else:
        print("  ✓ Code complexity looks good!")

    print("\n" + "=" * 80)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python analyze_complexity.py <project_path>")
        print("Example: python analyze_complexity.py backend/app")
        sys.exit(1)

    project_path = sys.argv[1]

    if not os.path.exists(project_path):
        print(f"Error: Path '{project_path}' does not exist.")
        sys.exit(1)

    print(f"Analyzing complexity in: {project_path}\n")
    metrics = analyze_project(project_path)
    print_complexity_report(metrics)


if __name__ == "__main__":
    main()
