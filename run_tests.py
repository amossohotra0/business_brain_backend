#!/usr/bin/env python3
"""
Test runner script for Gmail API tests.
Run this script to execute all Gmail API tests with proper configuration.
"""

import os
import sys
import subprocess
from pathlib import Path

def setup_test_environment():
    """Setup test environment variables."""
    test_env = os.environ.copy()
    
    # Use real environment variables for testing
    test_env.update({
        'TESTING': 'true'
    })
    
    return test_env

def run_gmail_tests():
    """Run Gmail API tests."""
    print("🧪 Running Gmail API Tests...")
    print("=" * 50)
    
    # Setup environment
    test_env = setup_test_environment()
    
    # Change to project directory
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # Run pytest with specific configuration
    cmd = [
        sys.executable, '-m', 'pytest',
        'tests/test_gmail_api.py',
        '-v',  # Verbose output
        '--tb=short',  # Short traceback format
        '--color=yes',  # Colored output
        '--durations=10',  # Show 10 slowest tests
        '--asyncio-mode=auto'  # Auto-detect async tests
    ]
    
    try:
        result = subprocess.run(cmd, env=test_env, check=False)
        
        if result.returncode == 0:
            print("\n✅ All Gmail API tests passed!")
        else:
            print(f"\n❌ Some tests failed (exit code: {result.returncode})")
            
        return result.returncode
        
    except FileNotFoundError:
        print("❌ pytest not found. Please install test dependencies:")
        print("   pip install -r requirements.txt")
        return 1
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1

def run_specific_test(test_name=None):
    """Run a specific test or test class."""
    if not test_name:
        return run_gmail_tests()
    
    print(f"🧪 Running specific test: {test_name}")
    print("=" * 50)
    
    test_env = setup_test_environment()
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    cmd = [
        sys.executable, '-m', 'pytest',
        f'tests/test_gmail_api.py::{test_name}',
        '-v',
        '--tb=short',
        '--color=yes',
        '--asyncio-mode=auto'
    ]
    
    try:
        result = subprocess.run(cmd, env=test_env, check=False)
        return result.returncode
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return 1

def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = ['pytest', 'pytest-asyncio', 'httpx']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required test dependencies:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\nInstall them with: pip install -r requirements.txt")
        return False
    
    return True

def main():
    """Main test runner function."""
    print("Gmail API Test Runner")
    print("=" * 30)
    
    # Check dependencies
    if not check_dependencies():
        return 1
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        return run_specific_test(test_name)
    else:
        return run_gmail_tests()

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)