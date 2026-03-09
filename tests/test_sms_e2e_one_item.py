# -*- coding: utf-8 -*-
"""
================================================================================
TEST SMS E2E ONE ITEM - End-to-End Single Item Reinsertion
================================================================================
Tests the complete SMS reinsertion pipeline with a single item:
1. Open a real SMS ROM
2. Load extraction data from B519E833_pure_text.jsonl
3. Pick one item and replace with larger text (forcing relocation)
4. Run real reinsertion (writing output ROM)
5. Validate pointer(s) and that new text bytes exist at new_offset
6. Generate validation_report.txt and proof.json

Usage:
    python test_sms_e2e_one_item.py

================================================================================
"""

import hashlib
import json
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.sms_pointer_transform import (
    pointer_to_offset,
    PointerContext,
)
from core.sms_relocation_v1 import (
    SMSRelocationEngine,
    RelocationConfig,
    ReinsertionItem,
)


# =============================================================================
# CONSTANTS
# =============================================================================

# Test item ID to use (id=2 has "aabqqqr" with max_len_bytes=7)
TEST_ITEM_ID = 2

# Larger text to force relocation (must exceed max_len_bytes=7)
LARGER_TEXT = "THIS_IS_A_MUCH_LARGER_TEXT_FOR_RELOCATION_TEST"


# =============================================================================
# FREE SPACE FINDER
# =============================================================================

def calculate_valid_offset_range(ptr_ref: Dict[str, Any]) -> Tuple[int, int]:
    """
    Calculate the valid ROM offset range for a given pointer reference.

    For SMS BANKED_SLOT2, pointers are in range 0x8000-0xBFFF.
    So valid ROM offset = pointer_value + bank_addend, where 0x8000 <= pointer_value <= 0xBFFF.

    Returns:
        Tuple of (min_offset, max_offset) that can be addressed by this pointer context.
    """
    bank_addend = ptr_ref.get("bank_addend", 0)
    if isinstance(bank_addend, str):
        bank_addend = int(bank_addend, 16)

    addressing_mode = ptr_ref.get("addressing_mode", "INFERRED")

    # Determine pointer value range based on addressing mode
    if addressing_mode == "DIRECT":
        # Slot 0: 0x0000-0x3FFF
        ptr_min, ptr_max = 0x0000, 0x3FFF
    elif addressing_mode == "BANKED_SLOT1":
        # Slot 1: 0x4000-0x7FFF
        ptr_min, ptr_max = 0x4000, 0x7FFF
    elif addressing_mode == "BANKED_SLOT2":
        # Slot 2: 0x8000-0xBFFF
        ptr_min, ptr_max = 0x8000, 0xBFFF
    else:
        # INFERRED: use full 16-bit range but prefer slot ranges
        ptr_min, ptr_max = 0x0000, 0xFFFF

    # Valid ROM offset range
    min_offset = ptr_min + bank_addend
    max_offset = ptr_max + bank_addend

    return (min_offset, max_offset)


def find_free_space_in_range(
    rom_data: bytes,
    min_offset: int,
    max_offset: int,
    size_needed: int,
    fill_bytes: Tuple[int, ...] = (0xFF, 0x00),
) -> Optional[Tuple[int, int]]:
    """
    Find a run of free space (fill bytes) within the specified offset range.

    Returns:
        Tuple of (start_offset, end_offset) if found, None otherwise.
    """
    rom_size = len(rom_data)

    # Clamp to ROM bounds
    min_offset = max(0, min_offset)
    max_offset = min(rom_size, max_offset)

    if max_offset - min_offset < size_needed:
        return None

    # Search for a run of fill bytes
    run_start = None
    run_length = 0

    for offset in range(min_offset, max_offset):
        if rom_data[offset] in fill_bytes:
            if run_start is None:
                run_start = offset
            run_length += 1

            if run_length >= size_needed:
                return (run_start, run_start + size_needed)
        else:
            run_start = None
            run_length = 0

    return None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_crc32(data: bytes) -> str:
    """Calculate CRC32 checksum as uppercase hex string."""
    return f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"


def calculate_sha256(data: bytes) -> str:
    """Calculate SHA256 hash as lowercase hex string."""
    return hashlib.sha256(data).hexdigest()


def find_rom_path() -> Optional[Path]:
    """Find the Sonic SMS ROM file."""
    base_dir = Path(__file__).parent.parent
    rom_dir = base_dir / "ROMs" / "Master System"

    # Look for Sonic ROM (CRC32: B519E833)
    candidates = [
        rom_dir / "Sonic The Hedgehog (USA, Europe).sms",
    ]

    for path in candidates:
        if path.exists():
            return path

    # Fallback: glob for any .sms file
    sms_files = list(rom_dir.glob("*.sms"))
    if sms_files:
        return sms_files[0]

    return None


def find_jsonl_path() -> Optional[Path]:
    """Find the B519E833_pure_text.jsonl file."""
    base_dir = Path(__file__).parent.parent
    jsonl_path = base_dir / "ROMs" / "Master System" / "B519E833_pure_text.jsonl"

    if jsonl_path.exists():
        return jsonl_path

    return None


def load_item_by_id(jsonl_path: Path, item_id: int) -> Optional[Dict[str, Any]]:
    """Load a specific item from JSONL by ID."""
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                if entry.get("id") == item_id:
                    return entry
    return None


def write_validation_report(
    output_path: Path,
    item: Dict[str, Any],
    result: Any,
    rom_path: Path,
    output_rom_path: Path,
    validations: Dict[str, Any],
) -> None:
    """Write detailed validation report."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("SMS E2E ONE ITEM - VALIDATION REPORT\n")
        f.write("=" * 70 + "\n\n")

        f.write("TEST CONFIGURATION\n")
        f.write("-" * 40 + "\n")
        f.write(f"  Source ROM: {rom_path.name}\n")
        f.write(f"  Output ROM: {output_rom_path.name}\n")
        f.write(f"  Test Item ID: {item.get('id')}\n")
        f.write(f"  Original Text: \"{item.get('text_src')}\"\n")
        f.write(f"  Replacement Text: \"{LARGER_TEXT}\"\n")
        f.write(f"  Max Len Bytes: {item.get('max_len_bytes')}\n")
        f.write(f"  Replacement Size: {len(LARGER_TEXT) + 1} (text + terminator)\n\n")

        f.write("REINSERTION RESULT\n")
        f.write("-" * 40 + "\n")
        f.write(f"  Success: {result.success}\n")
        f.write(f"  Method: {result.method}\n")
        f.write(f"  Original Offset: 0x{result.original_offset:06X}\n")
        if result.new_offset is not None:
            f.write(f"  New Offset: 0x{result.new_offset:06X}\n")
        f.write(f"  Bytes Written: {result.bytes_written}\n")
        f.write(f"  Pointers Updated: {result.pointers_updated}\n")
        if result.error:
            f.write(f"  Error: {result.error}\n")
        f.write("\n")

        if result.pointer_updates:
            f.write("POINTER UPDATES\n")
            f.write("-" * 40 + "\n")
            for pu in result.pointer_updates:
                f.write(f"  ptr_offset: {pu.get('ptr_ref', {}).get('ptr_offset')}\n")
                f.write(f"  new_ptr: {pu.get('new_ptr')}\n")
                f.write(f"  new_offset: {pu.get('new_offset')}\n")
                f.write(f"  roundtrip_passed: {pu.get('roundtrip_passed', False)}\n")
                f.write(f"  success: {pu.get('success', False)}\n")
                if pu.get("error"):
                    f.write(f"  error: {pu.get('error')}\n")
                f.write("\n")

        f.write("VALIDATIONS\n")
        f.write("-" * 40 + "\n")
        for name, val in validations.items():
            status = "PASS" if val.get("passed") else "FAIL"
            f.write(f"  [{status}] {name}\n")
            if val.get("details"):
                f.write(f"         {val.get('details')}\n")
        f.write("\n")

        all_passed = all(v.get("passed") for v in validations.values())
        f.write("=" * 70 + "\n")
        if all_passed:
            f.write("ALL VALIDATIONS PASSED\n")
        else:
            f.write("SOME VALIDATIONS FAILED\n")
        f.write("=" * 70 + "\n")


def write_proof_json(
    output_path: Path,
    rom_path: Path,
    output_rom_path: Path,
    item: Dict[str, Any],
    result: Any,
    validations: Dict[str, Any],
    generated_files: List[Path],
) -> None:
    """Write proof.json with checksums and validation results."""
    rom_data = rom_path.read_bytes()
    output_rom_data = output_rom_path.read_bytes()

    proof = {
        "schema": "e2e_reinsertion_proof.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "console_type": "SMS",
        "test_type": "single_item_relocation",

        "source_rom": {
            "name": rom_path.name,
            "crc32": calculate_crc32(rom_data),
            "sha256": calculate_sha256(rom_data),
            "size": len(rom_data),
        },

        "output_rom": {
            "name": output_rom_path.name,
            "crc32": calculate_crc32(output_rom_data),
            "sha256": calculate_sha256(output_rom_data),
            "size": len(output_rom_data),
        },

        "test_item": {
            "id": item.get("id"),
            "original_offset": item.get("offset"),
            "text_src": item.get("text_src"),
            "text_dst": LARGER_TEXT,
            "max_len_bytes": item.get("max_len_bytes"),
            "pointer_refs": item.get("pointer_refs", []),
        },

        "reinsertion_result": {
            "success": result.success,
            "method": result.method,
            "original_offset": f"0x{result.original_offset:06X}",
            "new_offset": f"0x{result.new_offset:06X}" if result.new_offset else None,
            "bytes_written": result.bytes_written,
            "pointers_updated": result.pointers_updated,
            "pointer_updates": result.pointer_updates,
        },

        "validations": {
            name: {
                "passed": val.get("passed"),
                "details": val.get("details"),
            }
            for name, val in validations.items()
        },

        "all_validations_passed": all(v.get("passed") for v in validations.values()),

        "file_proofs": [
            {
                "name": fp.name,
                "sha256": calculate_sha256(fp.read_bytes()),
                "size": fp.stat().st_size,
            }
            for fp in generated_files if fp.exists()
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(proof, f, indent=2, ensure_ascii=False)


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_text_at_offset(
    rom_data: bytes,
    offset: int,
    expected_text: str,
    encoding: str = "ascii",
) -> Dict[str, Any]:
    """Validate that expected text exists at offset in ROM."""
    try:
        encoded = expected_text.encode(encoding)
        actual = rom_data[offset:offset + len(encoded)]

        if actual == encoded:
            return {
                "passed": True,
                "details": f"Text found at 0x{offset:06X}: \"{expected_text[:20]}...\"",
            }
        else:
            return {
                "passed": False,
                "details": f"Text mismatch at 0x{offset:06X}: expected {encoded.hex()}, got {actual.hex()}",
            }
    except Exception as e:
        return {
            "passed": False,
            "details": f"Error: {e}",
        }


def validate_pointer_value(
    rom_data: bytes,
    ptr_offset: int,
    expected_target_offset: int,
    ptr_ref: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate that pointer at ptr_offset points to expected target."""
    try:
        ptr_size = ptr_ref.get("ptr_size", 2)
        endianness = ptr_ref.get("endianness", "little")

        bank_addend = ptr_ref.get("bank_addend", 0)
        if isinstance(bank_addend, str):
            bank_addend = int(bank_addend, 16)

        # Read pointer value from ROM
        if ptr_size == 2:
            if endianness == "little":
                ptr_value = rom_data[ptr_offset] | (rom_data[ptr_offset + 1] << 8)
            else:
                ptr_value = (rom_data[ptr_offset] << 8) | rom_data[ptr_offset + 1]
        else:
            return {
                "passed": False,
                "details": f"Unsupported ptr_size: {ptr_size}",
            }

        # Create context for conversion
        ctx = PointerContext(
            ptr_size=ptr_size,
            endianness=endianness,
            addressing_mode=ptr_ref.get("addressing_mode", "INFERRED"),
            bank_addend=bank_addend,
        )

        # Convert pointer to offset
        actual_offset = pointer_to_offset(ptr_value, ctx)

        if actual_offset == expected_target_offset:
            return {
                "passed": True,
                "details": f"Pointer at 0x{ptr_offset:06X} = 0x{ptr_value:04X} -> 0x{actual_offset:06X}",
            }
        else:
            return {
                "passed": False,
                "details": f"Pointer mismatch: 0x{ptr_value:04X} -> 0x{actual_offset:06X}, expected 0x{expected_target_offset:06X}",
            }
    except Exception as e:
        return {
            "passed": False,
            "details": f"Error: {e}",
        }


def validate_terminator(
    rom_data: bytes,
    offset: int,
    text_length: int,
    expected_terminator: int = 0x00,
) -> Dict[str, Any]:
    """Validate that terminator byte exists after text."""
    try:
        term_offset = offset + text_length
        actual = rom_data[term_offset]

        if actual == expected_terminator:
            return {
                "passed": True,
                "details": f"Terminator 0x{expected_terminator:02X} at 0x{term_offset:06X}",
            }
        else:
            return {
                "passed": False,
                "details": f"Wrong terminator at 0x{term_offset:06X}: expected 0x{expected_terminator:02X}, got 0x{actual:02X}",
            }
    except Exception as e:
        return {
            "passed": False,
            "details": f"Error: {e}",
        }


# =============================================================================
# MAIN TEST
# =============================================================================

def run_e2e_test() -> bool:
    """
    Run the complete E2E test.

    Returns:
        True if all validations pass, False otherwise.
    """
    print("=" * 70)
    print("SMS E2E ONE ITEM - END-TO-END SINGLE ITEM REINSERTION TEST")
    print("=" * 70)
    print()

    # -------------------------------------------------------------------------
    # Step 1: Find required files
    # -------------------------------------------------------------------------
    print("STEP 1: Locating files")
    print("-" * 40)

    rom_path = find_rom_path()
    if rom_path is None:
        print("  ERROR: Could not find SMS ROM file")
        return False
    print(f"  ROM: {rom_path}")

    jsonl_path = find_jsonl_path()
    if jsonl_path is None:
        print("  ERROR: Could not find B519E833_pure_text.jsonl")
        return False
    print(f"  JSONL: {jsonl_path}")

    # Verify ROM CRC32
    rom_data = rom_path.read_bytes()
    rom_crc = calculate_crc32(rom_data)
    print(f"  ROM CRC32: {rom_crc}")

    if rom_crc != "B519E833":
        print(f"  WARNING: ROM CRC32 mismatch (expected B519E833)")

    print()

    # -------------------------------------------------------------------------
    # Step 2: Load test item
    # -------------------------------------------------------------------------
    print("STEP 2: Loading test item")
    print("-" * 40)

    item = load_item_by_id(jsonl_path, TEST_ITEM_ID)
    if item is None:
        print(f"  ERROR: Could not find item with id={TEST_ITEM_ID}")
        return False

    print(f"  Item ID: {item.get('id')}")
    print(f"  Offset: {item.get('offset')}")
    print(f"  Text: \"{item.get('text_src')}\"")
    print(f"  Max Len Bytes: {item.get('max_len_bytes')}")
    print(f"  Pointer Refs: {len(item.get('pointer_refs', []))}")
    print()

    # -------------------------------------------------------------------------
    # Step 3: Create reinsertion item with larger text
    # -------------------------------------------------------------------------
    print("STEP 3: Creating reinsertion item")
    print("-" * 40)

    print(f"  Original text: \"{item.get('text_src')}\" ({len(item.get('text_src'))} bytes)")
    print(f"  Replacement: \"{LARGER_TEXT}\" ({len(LARGER_TEXT)} bytes)")
    print(f"  Max available: {item.get('max_len_bytes')} bytes")
    print(f"  Relocation required: YES (text exceeds max_len_bytes)")

    reinsertion_item = ReinsertionItem.from_jsonl_entry(item, LARGER_TEXT)
    print()

    # -------------------------------------------------------------------------
    # Step 4: Find compatible free space region
    # -------------------------------------------------------------------------
    print("STEP 4: Finding compatible free space")
    print("-" * 40)

    # Get the pointer reference to calculate valid offset range
    ptr_refs = item.get("pointer_refs", [])
    if not ptr_refs:
        print("  ERROR: Item has no pointer_refs")
        return False

    ptr_ref = ptr_refs[0]
    min_offset, max_offset = calculate_valid_offset_range(ptr_ref)
    print(f"  Valid offset range: 0x{min_offset:06X} - 0x{max_offset:06X}")

    # Size needed for relocation (text + terminator)
    size_needed = len(LARGER_TEXT) + 1
    print(f"  Size needed: {size_needed} bytes")

    # Find free space within valid range
    free_space = find_free_space_in_range(
        rom_data, min_offset, max_offset, size_needed
    )

    if free_space is None:
        print(f"  ERROR: No free space of {size_needed} bytes found in range")
        return False

    free_start, free_end = free_space
    print(f"  Free space found: 0x{free_start:06X} - 0x{free_end:06X}")

    # -------------------------------------------------------------------------
    # Step 5: Configure and run relocation engine
    # -------------------------------------------------------------------------
    print()
    print("STEP 5: Running relocation engine")
    print("-" * 40)

    config = RelocationConfig(
        free_space_regions=[(free_start, max_offset)],
        fill_bytes=(0xFF, 0x00),
        alignment=1,
    )

    print(f"  Free space region: 0x{free_start:06X} - 0x{max_offset:06X}")

    engine = SMSRelocationEngine(rom_data, config)
    result = engine.reinsert_item(reinsertion_item)

    print(f"  Success: {result.success}")
    print(f"  Method: {result.method}")
    print(f"  Original offset: 0x{result.original_offset:06X}")
    if result.new_offset is not None:
        print(f"  New offset: 0x{result.new_offset:06X}")
    print(f"  Bytes written: {result.bytes_written}")
    print(f"  Pointers updated: {result.pointers_updated}")

    if result.error:
        print(f"  ERROR: {result.error}")
        return False

    print()

    # -------------------------------------------------------------------------
    # Step 6: Write output ROM
    # -------------------------------------------------------------------------
    print("STEP 6: Writing output ROM")
    print("-" * 40)

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    output_rom_path = output_dir / f"{rom_crc}_e2e_one_item.sms"
    modified_rom = engine.get_modified_rom()
    output_rom_path.write_bytes(modified_rom)

    print(f"  Output ROM: {output_rom_path}")
    print(f"  Size: {len(modified_rom)} bytes")
    print(f"  CRC32: {calculate_crc32(modified_rom)}")
    print()

    # -------------------------------------------------------------------------
    # Step 7: Validate results
    # -------------------------------------------------------------------------
    print("STEP 7: Validating results")
    print("-" * 40)

    validations = {}

    # Validation 1: Text exists at new offset
    if result.new_offset is not None:
        validations["text_at_new_offset"] = validate_text_at_offset(
            modified_rom,
            result.new_offset,
            LARGER_TEXT,
            item.get("encoding", "ascii"),
        )
    else:
        validations["text_at_new_offset"] = {
            "passed": False,
            "details": "No new_offset returned",
        }

    # Validation 2: Terminator after text
    if result.new_offset is not None:
        validations["terminator_present"] = validate_terminator(
            modified_rom,
            result.new_offset,
            len(LARGER_TEXT),
            0x00,
        )

    # Validation 3: Pointer(s) updated correctly
    for i, ptr_ref in enumerate(item.get("pointer_refs", [])):
        ptr_offset = ptr_ref.get("ptr_offset", 0)
        if isinstance(ptr_offset, str):
            ptr_offset = int(ptr_offset, 16)

        if result.new_offset is not None:
            validations[f"pointer_{i}_updated"] = validate_pointer_value(
                modified_rom,
                ptr_offset,
                result.new_offset,
                ptr_ref,
            )

    # Validation 4: Method is "relocated" (as expected for larger text)
    validations["method_is_relocated"] = {
        "passed": result.method == "relocated",
        "details": f"Method: {result.method}",
    }

    # Validation 5: All pointer updates succeeded
    if result.pointer_updates:
        all_ptr_ok = all(pu.get("success") for pu in result.pointer_updates)
        validations["all_pointer_updates_success"] = {
            "passed": all_ptr_ok,
            "details": f"{sum(1 for pu in result.pointer_updates if pu.get('success'))}/{len(result.pointer_updates)} pointers updated",
        }

    # Print validation results
    for name, val in validations.items():
        status = "PASS" if val.get("passed") else "FAIL"
        print(f"  [{status}] {name}")
        if val.get("details"):
            print(f"         {val.get('details')}")

    print()

    # -------------------------------------------------------------------------
    # Step 8: Generate reports
    # -------------------------------------------------------------------------
    print("STEP 8: Generating reports")
    print("-" * 40)

    report_path = output_dir / f"{rom_crc}_e2e_one_item_validation_report.txt"
    proof_path = output_dir / f"{rom_crc}_e2e_one_item_proof.json"

    write_validation_report(
        report_path,
        item,
        result,
        rom_path,
        output_rom_path,
        validations,
    )
    print(f"  Validation report: {report_path}")

    write_proof_json(
        proof_path,
        rom_path,
        output_rom_path,
        item,
        result,
        validations,
        [output_rom_path, report_path],
    )
    print(f"  Proof JSON: {proof_path}")
    print()

    # -------------------------------------------------------------------------
    # Final summary
    # -------------------------------------------------------------------------
    all_passed = all(v.get("passed") for v in validations.values())

    print("=" * 70)
    if all_passed:
        print("ALL VALIDATIONS PASSED")
    else:
        failed = [k for k, v in validations.items() if not v.get("passed")]
        print(f"SOME VALIDATIONS FAILED: {failed}")
    print("=" * 70)

    return all_passed


if __name__ == "__main__":
    success = run_e2e_test()
    sys.exit(0 if success else 1)
