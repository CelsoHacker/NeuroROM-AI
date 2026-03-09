# -*- coding: utf-8 -*-
"""
================================================================================
TEST SMS POINTER TRANSFORM - Automated Validation
================================================================================
Validates that pointer_to_offset() and offset_to_pointer() are deterministic
and correctly reversible for all items in a JSONL file.

Usage:
    python test_sms_pointer_transform.py [path_to_jsonl]

Default: tests against 953F42E1_pure_text.jsonl
================================================================================
"""

import json
import sys
from pathlib import Path

import pytest

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.sms_pointer_transform import (
    pointer_to_offset,
    offset_to_pointer,
    infer_bank_addend,
    PointerContext,
    validate_item,
    validate_jsonl_file,
)


def parse_hex(value):
    """Parse hex string or return int as-is."""
    if isinstance(value, str):
        return int(value, 16)
    return value


def _test_single_item(item: dict) -> dict:
    """
    Test a single JSONL item.

    Returns dict with:
        - id: item id
        - passed: bool
        - details: str with test details
    """
    item_id = item.get("id", "?")
    offset_str = item.get("offset", "0x0")
    ptr_str = item.get("pointer_value")

    if ptr_str is None:
        return {
            "id": item_id,
            "passed": None,  # skipped
            "details": "SKIP: no pointer_value",
        }

    offset = parse_hex(offset_str)
    ptr_value = parse_hex(ptr_str)

    # Infer bank_addend from the data
    bank_addend = infer_bank_addend(ptr_value, offset)
    ctx = PointerContext(bank_addend=bank_addend)

    # Test pointer_to_offset
    try:
        calc_offset = pointer_to_offset(ptr_value, ctx)
    except Exception as e:
        return {
            "id": item_id,
            "passed": False,
            "details": f"FAIL: pointer_to_offset raised {e}",
        }

    # Test offset_to_pointer
    try:
        calc_ptr = offset_to_pointer(offset, ctx)
    except Exception as e:
        return {
            "id": item_id,
            "passed": False,
            "details": f"FAIL: offset_to_pointer raised {e}",
        }

    # Validate roundtrip
    if calc_offset != offset:
        return {
            "id": item_id,
            "passed": False,
            "details": (
                f"FAIL: pointer_to_offset({ptr_str}, bank_addend=0x{bank_addend:05X}) "
                f"= 0x{calc_offset:06X}, expected {offset_str}"
            ),
        }

    if calc_ptr != ptr_value:
        return {
            "id": item_id,
            "passed": False,
            "details": (
                f"FAIL: offset_to_pointer({offset_str}, bank_addend=0x{bank_addend:05X}) "
                f"= 0x{calc_ptr:04X}, expected {ptr_str}"
            ),
        }

    return {
        "id": item_id,
        "passed": True,
        "details": (
            f"PASS: ptr=0x{ptr_value:04X} <-> offset=0x{offset:06X} "
            f"(bank_addend=0x{bank_addend:05X})"
        ),
    }


def run_tests(jsonl_path: str, verbose: bool = False) -> dict:
    """
    Run all tests on a JSONL file.

    Returns summary dict.
    """
    print(f"=" * 70)
    print(f"SMS POINTER TRANSFORM TEST")
    print(f"=" * 70)
    print(f"File: {jsonl_path}")
    print()

    # Load items
    items = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))

    print(f"Total items: {len(items)}")
    print("-" * 70)

    passed = 0
    failed = 0
    skipped = 0
    failures = []

    for item in items:
        result = _test_single_item(item)

        if result["passed"] is None:
            skipped += 1
            if verbose:
                print(f"  [{result['id']:3}] {result['details']}")
        elif result["passed"]:
            passed += 1
            if verbose:
                print(f"  [{result['id']:3}] {result['details']}")
        else:
            failed += 1
            failures.append(result)
            print(f"  [{result['id']:3}] {result['details']}")

    print("-" * 70)
    print()
    print(f"RESULTS:")
    print(f"  PASSED:  {passed}")
    print(f"  FAILED:  {failed}")
    print(f"  SKIPPED: {skipped}")
    print()

    if failed == 0 and passed > 0:
        print("=" * 70)
        print("ALL TESTS PASSED")
        print("=" * 70)
        status = "PASS"
    elif failed > 0:
        print("=" * 70)
        print(f"TESTS FAILED ({failed} failures)")
        print("=" * 70)
        status = "FAIL"
    else:
        print("=" * 70)
        print("NO TESTS RUN (all skipped)")
        print("=" * 70)
        status = "SKIP"

    return {
        "status": status,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "failures": failures,
    }


def _run_known_values() -> bool:
    """Executa o teste de valores conhecidos no modo CLI."""
    test_cases = [
        # (pointer_value, expected_offset, description)
        (0x4645, 0x004645, "Item 1: direct mapping"),
        (0x6A69, 0x012A69, "Item 3: bank_addend=0xC000"),
        (0xB986, 0x017986, "Item 8: slot 2, bank_addend=0xC000"),
        (0xBC19, 0x023C19, "Item 10: bank_addend=0x18000"),
        (0xA000, 0x026000, "Item 15: bank_addend=0x1C000"),
        (0x5E60, 0x029E60, "Item 17: bank_addend=0x24000"),
    ]

    all_passed = True
    for ptr_value, expected_offset, _desc in test_cases:
        bank_addend = infer_bank_addend(ptr_value, expected_offset)
        ctx = PointerContext(bank_addend=bank_addend)
        calc_offset = pointer_to_offset(ptr_value, ctx)
        calc_ptr = offset_to_pointer(expected_offset, ctx)
        if not (calc_offset == expected_offset and calc_ptr == ptr_value):
            all_passed = False
    return all_passed


@pytest.mark.parametrize(
    "ptr_value,expected_offset",
    [
        (0x4645, 0x004645),
        (0x6A69, 0x012A69),
        (0xB986, 0x017986),
        (0xBC19, 0x023C19),
        (0xA000, 0x026000),
        (0x5E60, 0x029E60),
    ],
)
def test_known_values(ptr_value, expected_offset):
    bank_addend = infer_bank_addend(ptr_value, expected_offset)
    ctx = PointerContext(bank_addend=bank_addend)
    assert pointer_to_offset(ptr_value, ctx) == expected_offset
    assert offset_to_pointer(expected_offset, ctx) == ptr_value


if __name__ == "__main__":
    # Test known values first
    known_ok = _run_known_values()

    # Then test JSONL file
    if len(sys.argv) > 1:
        jsonl_path = sys.argv[1]
    else:
        # Default path
        default_paths = [
            Path(__file__).parent.parent / "ROMs" / "Master System" / "953F42E1_pure_text.jsonl",
            Path(__file__).parent.parent / "953F42E1_pure_text.jsonl",
        ]
        jsonl_path = None
        for p in default_paths:
            if p.exists():
                jsonl_path = str(p)
                break

        if jsonl_path is None:
            print("\nNo JSONL file found. Skipping file-based tests.")
            print("Usage: python test_sms_pointer_transform.py [path_to_jsonl]")
            sys.exit(0 if known_ok else 1)

    print()
    results = run_tests(jsonl_path, verbose=False)

    # Exit code
    if results["status"] == "PASS" and known_ok:
        sys.exit(0)
    else:
        sys.exit(1)
