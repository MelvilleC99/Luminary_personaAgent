#!/usr/bin/env python3
"""
Test runner for LinkedIn Persona Builder

Run all tests or specific test categories
"""

import sys
import subprocess
import argparse


def run_tests(test_type="all", verbose=False, coverage=False):
    """Run tests based on type"""
    
    cmd = ["pytest"]
    
    # Add coverage if requested
    if coverage:
        cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term"])
    
    # Add verbose flag
    if verbose:
        cmd.append("-v")
    
    # Select test type
    if test_type == "unit":
        cmd.append("tests/unit")
    elif test_type == "integration":
        cmd.append("tests/integration")
    elif test_type == "all":
        cmd.append("tests/")
    else:
        print(f"Unknown test type: {test_type}")
        return 1
    
    # Run tests
    print(f"Running {test_type} tests...")
    print(f"Command: {' '.join(cmd)}")
    
    result = subprocess.run(cmd)
    return result.returncode


def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description="Run LinkedIn Persona Builder tests")
    parser.add_argument(
        "type",
        nargs="?",
        default="all",
        choices=["all", "unit", "integration"],
        help="Type of tests to run"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "-c", "--coverage",
        action="store_true",
        help="Generate coverage report"
    )
    
    args = parser.parse_args()
    
    # Run tests
    exit_code = run_tests(args.type, args.verbose, args.coverage)
    
    # Print summary
    if exit_code == 0:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
