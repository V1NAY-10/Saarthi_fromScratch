"""Standalone test runner for planner engine (no external test dependency required)."""
import sys
import traceback
from datetime import date

# Add backend directory to sys.path
sys.path.insert(0, ".")

from tests import test_planner

test_funcs = [getattr(test_planner, f) for f in dir(test_planner) if f.startswith("test_")]

passed = 0
failed = 0

print(f"Running {len(test_funcs)} planner engine test cases...\n")

for fn in test_funcs:
    name = fn.__name__
    try:
        fn()
        passed += 1
        print(f"  [PASS] {name}")
    except Exception as e:
        failed += 1
        print(f"  [FAIL] {name}: {e}")
        traceback.print_exc()

print(f"\nResult: {passed} passed, {failed} failed out of {len(test_funcs)} tests.")
if failed > 0:
    sys.exit(1)
