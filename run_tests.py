"""
run_tests.py — Run the test suite for Gold Trading Agent.

Usage (from project root, with venv activated):
    python -m pytest Src/tests/ -v --tb=short

Or run this script directly:
    python run_tests.py
"""

import sys
import os

if __name__ == "__main__":
    root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root)
    sys.path.insert(0, os.path.join(root, "Src"))
    sys.path.insert(0, os.path.join(root, "Src", "data_engine"))

    import pytest

    sys.exit(
        pytest.main(
            [
                os.path.join(root, "Src", "tests"),
                "-v",
                "--tb=short",
            ]
        )
    )
