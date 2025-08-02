#!/usr/bin/env python3
"""
Test runner for K2Edit Agentic System

This script provides a simple way to run all tests for the agentic system
including unit tests, integration tests, and performance tests.
"""

import asyncio
import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, cwd=None):
    """Run a command and return the result."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def print_header(title):
    """Print a formatted header."""
    print("\n" + "="*60)
    print(f" {title} ")
    print("="*60)


def print_result(returncode, stdout, stderr, test_type):
    """Print test results."""
    if returncode == 0:
        print(f"✅ {test_type} tests passed!")
    else:
        print(f"❌ {test_type} tests failed!")
        print("STDOUT:", stdout)
        print("STDERR:", stderr)


def main():
    """Main test runner."""
    project_root = Path(__file__).parent
    tests_dir = project_root / "tests"
    
    if not tests_dir.exists():
        print(f"❌ Tests directory not found: {tests_dir}")
        return 1
    
    print("🚀 Starting K2Edit Agentic System Test Suite")
    
    # Check if pytest is available
    returncode, stdout, stderr = run_command("python -m pytest --version")
    if returncode != 0:
        print("❌ pytest not found. Installing test dependencies...")
        
        # Install test dependencies
        returncode, stdout, stderr = run_command("pip install -r agent/requirements.txt")
        if returncode != 0:
            print("❌ Failed to install dependencies")
            print(stderr)
            return 1
    
    # Run all tests
    print_header("Running All Tests")
    cmd = f"python -m pytest {tests_dir} -v --tb=short"
    returncode, stdout, stderr = run_command(cmd)
    print_result(returncode, stdout, stderr, "All")
    
    # Run unit tests only
    print_header("Running Unit Tests")
    cmd = f"python -m pytest {tests_dir} -v -m unit"
    returncode, stdout, stderr = run_command(cmd)
    print_result(returncode, stdout, stderr, "Unit")
    
    # Run integration tests only
    print_header("Running Integration Tests")
    cmd = f"python -m pytest {tests_dir} -v -m integration"
    returncode, stdout, stderr = run_command(cmd)
    print_result(returncode, stdout, stderr, "Integration")
    
    # Run with coverage
    print_header("Running Tests with Coverage")
    cmd = f"python -m pytest {tests_dir} --cov=agent --cov-report=term-missing"
    returncode, stdout, stderr = run_command(cmd)
    print_result(returncode, stdout, stderr, "Coverage")
    
    # Generate coverage report
    print_header("Generating Coverage Report")
    coverage_dir = project_root / "htmlcov"
    if coverage_dir.exists():
        print(f"📊 Coverage report generated at: file://{coverage_dir}/index.html")
    
    print("\n" + "="*60)
    print("🎉 Test suite completed!")
    print("="*60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())