#!/usr/bin/env python3
"""
Test runner for test1.csv validation suite
Runs all 30+ test cases and generates a comprehensive report
"""
import sys
import subprocess
from pathlib import Path


def run_csv_tests():
    """Run the CSV validation test suite"""
    
    print("=" * 80)
    print("TEST1.CSV VALIDATION SUITE")
    print("=" * 80)
    print("\nRunning comprehensive validation tests...\n")
    
    # Run pytest with verbose output
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_csv_validation.py",
        "-v",  # Verbose
        "--tb=short",  # Short traceback
        "-s",  # Show print statements
        "--color=yes"
    ]
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    
    print("\n" + "=" * 80)
    if result.returncode == 0:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 80)
    
    return result.returncode


def run_quick_validation():
    """Run only the quick 5-question validation"""
    
    print("=" * 80)
    print("QUICK VALIDATION (5 Questions)")
    print("=" * 80)
    print("\nRunning quick validation tests...\n")
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_csv_validation.py::TestQuickValidation",
        "-v",
        "--tb=short",
        "--color=yes"
    ]
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    
    print("\n" + "=" * 80)
    if result.returncode == 0:
        print("✅ QUICK VALIDATION PASSED")
    else:
        print("❌ QUICK VALIDATION FAILED")
    print("=" * 80)
    
    return result.returncode


def run_hallucination_tests():
    """Run only hallucination detection tests"""
    
    print("=" * 80)
    print("HALLUCINATION DETECTION TESTS")
    print("=" * 80)
    print("\nRunning hallucination detection...\n")
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_csv_validation.py::TestHallucinationDetection",
        "-v",
        "--tb=short",
        "--color=yes"
    ]
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    
    print("\n" + "=" * 80)
    if result.returncode == 0:
        print("✅ NO HALLUCINATIONS DETECTED")
    else:
        print("❌ HALLUCINATION ISSUES FOUND")
    print("=" * 80)
    
    return result.returncode


if __name__ == "__main__":
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        
        if mode == "quick":
            exit_code = run_quick_validation()
        elif mode == "hallucination":
            exit_code = run_hallucination_tests()
        elif mode == "full":
            exit_code = run_csv_tests()
        else:
            print(f"Unknown mode: {mode}")
            print("\nUsage:")
            print("  python run_csv_tests.py           # Run all tests")
            print("  python run_csv_tests.py quick     # Run 5 quick tests")
            print("  python run_csv_tests.py hallucination  # Run hallucination tests only")
            print("  python run_csv_tests.py full      # Run full test suite")
            exit_code = 1
    else:
        # Default: run all tests
        exit_code = run_csv_tests()
    
    sys.exit(exit_code)
