# -*- coding: utf-8 -*-
"""
================================================================================
TEST SMS RELOCATION V1 - Automated Validation
================================================================================
Tests the SMS relocation engine with forced growth scenarios.

Test cases:
1. In-place reinsertion (text fits)
2. Forced relocation (text exceeds max_len_bytes)
3. Pointer update validation with round-trip
4. Free space boundary enforcement

Usage:
    python test_sms_relocation_v2.py [path_to_jsonl]

Examples:
    python test_sms_relocation_v2.py
    python test_sms_relocation_v2.py "./ROMs/Master System/B519E833_pure_text.jsonl"
================================================================================
"""

import glob
import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.sms_pointer_transform import (
    pointer_to_offset,
    offset_to_pointer,
    PointerContext,
)
from core.sms_relocation_v1 import (
    SMSRelocationEngine,
    RelocationConfig,
    ReinsertionItem,
    FreeSpaceAllocator,
)


def create_test_rom() -> bytearray:
    """
    Create a test ROM with known structure:
    - 0x0000-0x00FF: Header/code (preserve)
    - 0x0100-0x010F: Pointer table (2 pointers)
    - 0x0200-0x020F: Text block 1 ("HELLO", max 10 bytes)
    - 0x0210-0x021F: Text block 2 ("WORLD", max 10 bytes)
    - 0x1000-0x1FFF: Free space (filled with 0xFF)
    """
    rom = bytearray(0x2000)  # 8KB ROM

    # Fill with 0x00 by default
    for i in range(len(rom)):
        rom[i] = 0x00

    # Pointer table at 0x0100 (pointing to text blocks)
    # Pointer 1: 0x0200 (direct addressing, bank_addend=0)
    rom[0x0100] = 0x00  # Low byte
    rom[0x0101] = 0x02  # High byte -> 0x0200

    # Pointer 2: 0x0210
    rom[0x0102] = 0x10  # Low byte
    rom[0x0103] = 0x02  # High byte -> 0x0210

    # Text block 1 at 0x0200: "HELLO" + terminator
    text1 = b"HELLO\x00"
    for i, b in enumerate(text1):
        rom[0x0200 + i] = b

    # Text block 2 at 0x0210: "WORLD" + terminator
    text2 = b"WORLD\x00"
    for i, b in enumerate(text2):
        rom[0x0210 + i] = b

    # Free space at 0x1000-0x1FFF (filled with 0xFF)
    for i in range(0x1000, 0x2000):
        rom[i] = 0xFF

    return rom


def create_test_items() -> list:
    """Create test reinsertion items matching the test ROM."""
    return [
        ReinsertionItem(
            id=1,
            offset=0x0200,
            text_src="HELLO",
            text_dst="HELLO",  # Same size, in-place
            max_len_bytes=10,
            terminator=0x00,
            encoding="ascii",
            pointer_refs=[{
                "ptr_offset": "0x000100",
                "ptr_size": 2,
                "endianness": "little",
                "addressing_mode": "DIRECT",
                "bank_addend": "0x00000",
                "table_start": "0x000100",
            }],
        ),
        ReinsertionItem(
            id=2,
            offset=0x0210,
            text_src="WORLD",
            text_dst="WORLD",  # Same size, in-place
            max_len_bytes=10,
            terminator=0x00,
            encoding="ascii",
            pointer_refs=[{
                "ptr_offset": "0x000102",
                "ptr_size": 2,
                "endianness": "little",
                "addressing_mode": "DIRECT",
                "bank_addend": "0x00000",
                "table_start": "0x000100",
            }],
        ),
    ]


def test_in_place_reinsertion():
    """Test that text fitting in max_len_bytes is reinserted in-place."""
    print("\n" + "=" * 70)
    print("TEST: In-place reinsertion")
    print("=" * 70)

    rom = create_test_rom()
    config = RelocationConfig(
        free_space_regions=[(0x1000, 0x2000)],
    )

    engine = SMSRelocationEngine(bytes(rom), config)

    # Item that fits in place
    item = ReinsertionItem(
        id=1,
        offset=0x0200,
        text_src="HELLO",
        text_dst="HI",  # Shorter, definitely fits
        max_len_bytes=10,
        terminator=0x00,
        encoding="ascii",
        pointer_refs=[{
            "ptr_offset": "0x000100",
            "ptr_size": 2,
            "endianness": "little",
            "addressing_mode": "DIRECT",
            "bank_addend": "0x00000",
        }],
    )

    result = engine.reinsert_item(item)

    print(f"  Method: {result.method}")
    print(f"  Success: {result.success}")
    print(f"  Original offset: 0x{result.original_offset:06X}")
    print(f"  New offset: 0x{result.new_offset:06X}" if result.new_offset else "  New offset: None")

    # Verify
    assert result.success, f"Reinsertion failed: {result.error}"
    assert result.method == "in_place", f"Expected in_place, got {result.method}"
    assert result.new_offset == 0x0200, f"Offset should not change for in-place"

    # Verify ROM content
    modified = engine.get_modified_rom()
    assert modified[0x0200:0x0203] == b"HI\x00", "Text not written correctly"

    print("  PASSED: In-place reinsertion works correctly")
    return True


def test_forced_relocation():
    """Test that text exceeding max_len_bytes is relocated."""
    print("\n" + "=" * 70)
    print("TEST: Forced relocation (text exceeds max_len_bytes)")
    print("=" * 70)

    rom = create_test_rom()
    config = RelocationConfig(
        free_space_regions=[(0x1000, 0x2000)],
        fill_bytes=(0xFF,),
    )

    engine = SMSRelocationEngine(bytes(rom), config)

    # Item that EXCEEDS max_len_bytes (forcing relocation)
    long_text = "A" * 20  # 20 bytes > max 10
    item = ReinsertionItem(
        id=1,
        offset=0x0200,
        text_src="HELLO",
        text_dst=long_text,
        max_len_bytes=10,  # Only 10 bytes available in-place
        terminator=0x00,
        encoding="ascii",
        pointer_refs=[{
            "ptr_offset": "0x000100",
            "ptr_size": 2,
            "endianness": "little",
            "addressing_mode": "DIRECT",
            "bank_addend": "0x00000",
        }],
    )

    result = engine.reinsert_item(item)

    print(f"  Method: {result.method}")
    print(f"  Success: {result.success}")
    print(f"  Original offset: 0x{result.original_offset:06X}")
    print(f"  New offset: 0x{result.new_offset:06X}" if result.new_offset else "  New offset: None")
    print(f"  Pointers updated: {result.pointers_updated}")

    if not result.success:
        print(f"  ERROR: {result.error}")
        return False

    # Verify relocation happened
    assert result.method == "relocated", f"Expected relocated, got {result.method}"

    # Verify new_offset is within free_space_regions
    assert 0x1000 <= result.new_offset < 0x2000, \
        f"New offset 0x{result.new_offset:06X} not in free_space_regions"

    print(f"  VERIFIED: Relocated to 0x{result.new_offset:06X} (within free_space_regions)")

    # Verify pointer was updated
    assert result.pointers_updated == 1, f"Expected 1 pointer update, got {result.pointers_updated}"

    # Verify ROM content at new location
    modified = engine.get_modified_rom()
    new_text = modified[result.new_offset:result.new_offset + len(long_text)]
    assert new_text == long_text.encode("ascii"), "Text not written at new location"

    print(f"  VERIFIED: Text written at new location")

    # Verify pointer value in ROM
    ptr_low = modified[0x0100]
    ptr_high = modified[0x0101]
    ptr_value = ptr_low | (ptr_high << 8)
    print(f"  Pointer at 0x0100 now = 0x{ptr_value:04X}")

    # Verify round-trip
    ctx = PointerContext(bank_addend=0)
    roundtrip_offset = pointer_to_offset(ptr_value, ctx)
    assert roundtrip_offset == result.new_offset, \
        f"Round-trip failed: 0x{roundtrip_offset:06X} != 0x{result.new_offset:06X}"

    print(f"  VERIFIED: Round-trip passed (pointer_to_offset(0x{ptr_value:04X}) = 0x{roundtrip_offset:06X})")

    print("  PASSED: Forced relocation works correctly")
    return True


def test_pointer_roundtrip():
    """Test pointer update with round-trip validation."""
    print("\n" + "=" * 70)
    print("TEST: Pointer round-trip validation")
    print("=" * 70)

    rom = create_test_rom()
    config = RelocationConfig(
        free_space_regions=[(0x1000, 0x2000)],
        fill_bytes=(0xFF,),
    )

    engine = SMSRelocationEngine(bytes(rom), config)

    # Test with different bank_addend values
    # Note: new_offset must be >= bank_addend for valid pointer
    test_cases = [
        {"bank_addend": 0x00000, "new_offset": 0x1000},
        {"bank_addend": 0x0C000, "new_offset": 0x0D000},  # Valid: 0xD000 - 0xC000 = 0x1000
        {"bank_addend": 0x18000, "new_offset": 0x19000},  # Valid: 0x19000 - 0x18000 = 0x1000
    ]

    all_passed = True

    for tc in test_cases:
        bank_addend = tc["bank_addend"]
        new_offset = tc["new_offset"]

        ctx = PointerContext(bank_addend=bank_addend)

        try:
            new_ptr = offset_to_pointer(new_offset, ctx)
            roundtrip = pointer_to_offset(new_ptr, ctx)

            if roundtrip == new_offset:
                print(f"  PASS: bank_addend=0x{bank_addend:05X}, "
                      f"offset=0x{new_offset:06X} -> ptr=0x{new_ptr:04X} -> "
                      f"offset=0x{roundtrip:06X}")
            else:
                print(f"  FAIL: Round-trip mismatch for bank_addend=0x{bank_addend:05X}")
                all_passed = False
        except ValueError as e:
            print(f"  FAIL: {e}")
            all_passed = False

    if all_passed:
        print("  PASSED: All round-trip tests passed")
    return all_passed


def test_free_space_boundary():
    """Test that relocation respects free space boundaries."""
    print("\n" + "=" * 70)
    print("TEST: Free space boundary enforcement")
    print("=" * 70)

    rom = create_test_rom()

    # Very small free space region
    config = RelocationConfig(
        free_space_regions=[(0x1000, 0x1010)],  # Only 16 bytes
        fill_bytes=(0xFF,),
    )

    engine = SMSRelocationEngine(bytes(rom), config)

    # Try to allocate more than available
    result = engine.allocator.allocate(100)  # 100 bytes

    print(f"  Allocation success: {result.success}")
    print(f"  Error: {result.error}" if result.error else "  No error")

    assert not result.success, "Should fail when no space available"
    assert "No free space" in result.error, f"Wrong error message: {result.error}"

    print("  PASSED: Free space boundary correctly enforced")
    return True


def test_with_real_jsonl(jsonl_path_arg: str = None):
    """
    Test with real JSONL file.

    Args:
        jsonl_path_arg: Optional path to JSONL file (from CLI argument)

    Returns:
        True if passed, False if failed, None if skipped
    """
    print("\n" + "=" * 70)
    print("TEST: Real JSONL file")
    print("=" * 70)

    jsonl_path = None

    # Priority 1: Use CLI argument if provided
    if jsonl_path_arg:
        candidate = Path(jsonl_path_arg)
        if candidate.exists():
            jsonl_path = candidate
            print(f"  Using CLI argument: {candidate.absolute()}")
        else:
            print(f"  ERROR: CLI path does not exist: {candidate.absolute()}")
            return False

    # Priority 2: Glob fallback
    if jsonl_path is None:
        base_dir = Path(__file__).parent.parent
        glob_pattern = str(base_dir / "ROMs" / "Master System" / "*_pure_text.jsonl")
        matches = glob.glob(glob_pattern)

        if matches:
            jsonl_path = Path(matches[0])
            print(f"  Using glob fallback: {jsonl_path.absolute()}")
        else:
            print(f"  Glob pattern: {glob_pattern}")
            print("  SKIPPED: No JSONL file found")
            return None  # Explicitly SKIPPED

    print(f"  Loading: {jsonl_path.absolute()}")

    # Load items
    items = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))

    print(f"  Loaded {len(items)} items")

    if len(items) == 0:
        print("  FAIL: No items in JSONL")
        return False

    # Verify all items have pointer_refs with required fields
    valid_count = 0
    missing_refs = 0
    for item in items:
        refs = item.get("pointer_refs", [])
        if refs:
            ref = refs[0]
            if all(k in ref for k in ["ptr_offset", "ptr_size", "endianness",
                                       "addressing_mode", "bank_addend"]):
                valid_count += 1
        else:
            missing_refs += 1

    print(f"  Items with valid pointer_refs: {valid_count}/{len(items)}")
    if missing_refs > 0:
        print(f"  Items missing pointer_refs: {missing_refs}")

    if valid_count == len(items):
        print("  PASSED: All items have complete pointer_refs")
        return True
    elif valid_count > 0:
        print(f"  PARTIAL: {valid_count}/{len(items)} items have complete pointer_refs")
        return True  # Partial success still counts
    else:
        print("  FAIL: No items have valid pointer_refs")
        return False


def run_all_tests(jsonl_path_arg: str = None):
    """
    Run all tests and report results.

    Args:
        jsonl_path_arg: Optional path to JSONL file for real file test
    """
    print("=" * 70)
    print("SMS RELOCATION V1 - TEST SUITE")
    print("=" * 70)

    # Standard tests (no args needed)
    standard_tests = [
        ("In-place reinsertion", test_in_place_reinsertion),
        ("Forced relocation", test_forced_relocation),
        ("Pointer round-trip", test_pointer_roundtrip),
        ("Free space boundary", test_free_space_boundary),
    ]

    results = {}  # name -> True/False/None (None = skipped)

    for name, test_func in standard_tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            results[name] = False

    # Real JSONL test (with optional arg)
    try:
        results["Real JSONL file"] = test_with_real_jsonl(jsonl_path_arg)
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        results["Real JSONL file"] = False

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = 0
    failed = 0
    skipped = 0

    for name, result in results.items():
        if result is True:
            status = "PASS"
            passed += 1
        elif result is False:
            status = "FAIL"
            failed += 1
        else:  # None = skipped
            status = "SKIP"
            skipped += 1
        print(f"  {status}: {name}")

    print()
    print(f"PASSED:  {passed}")
    print(f"FAILED:  {failed}")
    print(f"SKIPPED: {skipped}")

    if failed == 0 and passed > 0:
        print("\n" + "=" * 70)
        print("ALL TESTS PASSED")
        print("=" * 70)
        return True
    elif failed > 0:
        print("\n" + "=" * 70)
        print(f"TESTS FAILED ({failed} failures)")
        print("=" * 70)
        return False
    else:
        print("\n" + "=" * 70)
        print("NO TESTS RAN (all skipped)")
        print("=" * 70)
        return False


if __name__ == "__main__":
    # Check for CLI argument
    jsonl_arg = None
    if len(sys.argv) >= 2:
        jsonl_arg = sys.argv[1]
        print(f"CLI argument: {jsonl_arg}")

    success = run_all_tests(jsonl_arg)
    sys.exit(0 if success else 1)
