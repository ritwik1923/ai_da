#!/usr/bin/env python3
"""
Test Runner Script
Run all tests or specific test categories
"""
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and print results"""
    print(f"\n{'='*70}")
    print(f"  {description}")
    print(f"{'='*70}\n")
    
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Run tests for AI Data Analyst")
    parser.add_argument(
        "--category",
        choices=["all", "unit", "api", "llm", "agent", "quick"],
        default="all",
        help="Test category to run"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run with coverage report"
    )
    
    args = parser.parse_args()
    
    # Base pytest command
    base_cmd = "pytest"
    if args.verbose:
        base_cmd += " -v"
    if args.coverage:
        base_cmd += " --cov=app --cov-report=html --cov-report=term"
    
    success = True
    
    if args.category == "all":
        success = run_command(f"{base_cmd} tests/", "Running All Tests")
    
    elif args.category == "unit":
        success = run_command(
            f"{base_cmd} tests/test_code_executor.py",
            "Running Unit Tests"
        )
    
    elif args.category == "api":
        success = run_command(
            f"{base_cmd} tests/test_api_endpoints.py",
            "Running API Tests"
        )
    
    elif args.category == "llm":
        success = run_command(
            f"{base_cmd} tests/test_llm_providers.py",
            "Running LLM Provider Tests"
        )
    
    elif args.category == "agent":
        success = run_command(
            f"{base_cmd} tests/test_data_analyst.py",
            "Running Agent Tests"
        )
    
    elif args.category == "quick":
        # Run quick tests (no LLM API calls)
        success = run_command(
            f"{base_cmd} -m 'not slow' tests/",
            "Running Quick Tests"
        )
    
    # Print summary
    print(f"\n{'='*70}")
    if success:
        print("  ✅ All tests passed!")
    else:
        print("  ❌ Some tests failed")
    print(f"{'='*70}\n")
    
    if args.coverage:
        print("Coverage report generated in htmlcov/index.html")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
