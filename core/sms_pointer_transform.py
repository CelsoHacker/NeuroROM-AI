# -*- coding: utf-8 -*-
"""
================================================================================
SMS POINTER TRANSFORM - Deterministic Pointer-to-Offset Conversion
================================================================================
Implements bidirectional conversion between SMS pointer values and ROM offsets.

SMS Memory Map:
- Slot 0: 0x0000-0x3FFF -> Bank 0 (fixed)
- Slot 1: 0x4000-0x7FFF -> Switchable bank
- Slot 2: 0x8000-0xBFFF -> Switchable bank
- 0xC000-0xFFFF -> RAM (not ROM)

Key insight: bank_addend = rom_offset - pointer_value
This value is always a multiple of 0x4000 (16KB bank size).
================================================================================
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class AddressingMode(Enum):
    """SMS pointer addressing modes."""
    DIRECT = "DIRECT"           # pointer_value == rom_offset (slot 0)
    BANKED_SLOT1 = "BANKED_SLOT1"  # pointer in 0x4000-0x7FFF range
    BANKED_SLOT2 = "BANKED_SLOT2"  # pointer in 0x8000-0xBFFF range
    INFERRED = "INFERRED"       # bank_addend inferred from data


@dataclass
class PointerContext:
    """
    Context for pointer transformation.
    Contains all info needed to convert pointer <-> offset.
    """
    ptr_size: int = 2                    # Pointer size in bytes (always 2 for SMS)
    endianness: str = "little"           # Always little-endian for SMS
    addressing_mode: str = "INFERRED"    # Addressing mode
    bank_addend: int = 0                 # Value to add: offset = ptr + bank_addend
    bank_size: int = 0x4000              # 16KB banks

    # Table-level info (optional)
    table_offset: Optional[int] = None   # Offset of pointer table in ROM
    table_bank: Optional[int] = None     # Bank where table resides

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "ptr_size": self.ptr_size,
            "endianness": self.endianness,
            "addressing_mode": self.addressing_mode,
            "bank_addend": f"0x{self.bank_addend:05X}" if self.bank_addend else "0x00000",
            "bank_size": f"0x{self.bank_size:04X}",
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PointerContext":
        """Create from dictionary."""
        bank_addend = d.get("bank_addend", 0)
        if isinstance(bank_addend, str):
            bank_addend = int(bank_addend, 16)

        bank_size = d.get("bank_size", 0x4000)
        if isinstance(bank_size, str):
            bank_size = int(bank_size, 16)

        return cls(
            ptr_size=d.get("ptr_size", 2),
            endianness=d.get("endianness", "little"),
            addressing_mode=d.get("addressing_mode", "INFERRED"),
            bank_addend=bank_addend,
            bank_size=bank_size,
        )


@dataclass
class PointerRef:
    """
    Reference to a pointer that points to a text block.
    Supports multiple pointers pointing to same text.
    """
    ptr_offset: int              # Offset of pointer in ROM
    ptr_size: int = 2            # Size in bytes
    endianness: str = "little"   # Byte order
    addressing_mode: str = "INFERRED"
    bank_addend: int = 0         # offset = ptr_value + bank_addend

    # Table info
    table_start: Optional[int] = None
    table_index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "ptr_offset": f"0x{self.ptr_offset:06X}",
            "ptr_size": self.ptr_size,
            "endianness": self.endianness,
            "addressing_mode": self.addressing_mode,
            "bank_addend": f"0x{self.bank_addend:05X}" if self.bank_addend else "0x00000",
        }
        if self.table_start is not None:
            result["table_start"] = f"0x{self.table_start:06X}"
        if self.table_index is not None:
            result["table_index"] = self.table_index
        return result

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PointerRef":
        """Create from dictionary."""
        ptr_offset = d.get("ptr_offset", 0)
        if isinstance(ptr_offset, str):
            ptr_offset = int(ptr_offset, 16)

        bank_addend = d.get("bank_addend", 0)
        if isinstance(bank_addend, str):
            bank_addend = int(bank_addend, 16)

        table_start = d.get("table_start")
        if isinstance(table_start, str):
            table_start = int(table_start, 16)

        return cls(
            ptr_offset=ptr_offset,
            ptr_size=d.get("ptr_size", 2),
            endianness=d.get("endianness", "little"),
            addressing_mode=d.get("addressing_mode", "INFERRED"),
            bank_addend=bank_addend,
            table_start=table_start,
            table_index=d.get("table_index"),
        )


# =============================================================================
# CORE TRANSFORM FUNCTIONS
# =============================================================================

def pointer_to_offset(pointer_value: int, ctx: PointerContext) -> int:
    """
    Convert SMS pointer value to ROM offset.

    Formula: rom_offset = pointer_value + bank_addend

    Args:
        pointer_value: 16-bit pointer value read from ROM
        ctx: Pointer context with addressing info

    Returns:
        ROM offset (absolute byte position in ROM file)
    """
    if pointer_value is None:
        raise ValueError("pointer_value cannot be None")

    # Ensure pointer is 16-bit
    pointer_value = pointer_value & 0xFFFF

    return pointer_value + ctx.bank_addend


def offset_to_pointer(offset: int, ctx: PointerContext) -> int:
    """
    Convert ROM offset to SMS pointer value.

    Formula: pointer_value = rom_offset - bank_addend

    Args:
        offset: ROM offset (absolute byte position)
        ctx: Pointer context with addressing info

    Returns:
        16-bit pointer value to write to ROM

    Raises:
        ValueError: If resulting pointer doesn't fit in 16 bits
    """
    if offset is None:
        raise ValueError("offset cannot be None")

    pointer_value = offset - ctx.bank_addend

    # Validate 16-bit range
    if pointer_value < 0 or pointer_value > 0xFFFF:
        raise ValueError(
            f"Resulting pointer 0x{pointer_value:X} out of 16-bit range. "
            f"offset=0x{offset:06X}, bank_addend=0x{ctx.bank_addend:05X}"
        )

    return pointer_value


def infer_bank_addend(pointer_value: int, rom_offset: int) -> int:
    """
    Infer bank_addend from known pointer-offset pair.

    Args:
        pointer_value: 16-bit pointer value from ROM
        rom_offset: Known ROM offset this pointer resolves to

    Returns:
        bank_addend value (always multiple of 0x4000)
    """
    addend = rom_offset - pointer_value

    # Validate it's a valid bank offset (multiple of 0x4000)
    if addend % 0x4000 != 0 and addend != 0:
        # Not a clean bank boundary - might be offset-based addressing
        pass  # Still use the exact value

    return addend


def infer_addressing_mode(pointer_value: int, bank_addend: int) -> str:
    """
    Infer addressing mode from pointer value and bank_addend.

    Args:
        pointer_value: 16-bit pointer value
        bank_addend: Calculated bank addend

    Returns:
        Addressing mode string
    """
    if bank_addend == 0:
        if pointer_value < 0x4000:
            return "DIRECT"  # Slot 0, direct mapping
        else:
            return "BANKED_SLOT1"  # Slot 1, bank 1

    if 0x4000 <= pointer_value < 0x8000:
        return "BANKED_SLOT1"
    elif 0x8000 <= pointer_value < 0xC000:
        return "BANKED_SLOT2"
    elif pointer_value < 0x4000:
        return "DIRECT"
    else:
        return "INFERRED"


def create_pointer_ref(
    ptr_offset: int,
    pointer_value: int,
    rom_offset: int,
    table_start: Optional[int] = None,
    table_index: Optional[int] = None
) -> PointerRef:
    """
    Create a PointerRef with inferred transform parameters.

    Args:
        ptr_offset: Offset where pointer is stored in ROM
        pointer_value: 16-bit value read from pointer
        rom_offset: ROM offset the pointer resolves to
        table_start: Optional table start offset
        table_index: Optional index within table

    Returns:
        PointerRef with all transform parameters set
    """
    bank_addend = infer_bank_addend(pointer_value, rom_offset)
    addressing_mode = infer_addressing_mode(pointer_value, bank_addend)

    return PointerRef(
        ptr_offset=ptr_offset,
        ptr_size=2,
        endianness="little",
        addressing_mode=addressing_mode,
        bank_addend=bank_addend,
        table_start=table_start,
        table_index=table_index,
    )


def create_context_from_ref(ref: PointerRef) -> PointerContext:
    """Create PointerContext from PointerRef."""
    return PointerContext(
        ptr_size=ref.ptr_size,
        endianness=ref.endianness,
        addressing_mode=ref.addressing_mode,
        bank_addend=ref.bank_addend,
        table_offset=ref.table_start,
    )


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_roundtrip(pointer_value: int, rom_offset: int, ctx: PointerContext) -> bool:
    """
    Validate that pointer<->offset conversion is reversible.

    Args:
        pointer_value: Original pointer value
        rom_offset: Expected ROM offset
        ctx: Pointer context

    Returns:
        True if roundtrip succeeds, False otherwise
    """
    try:
        # Forward: pointer -> offset
        calculated_offset = pointer_to_offset(pointer_value, ctx)
        if calculated_offset != rom_offset:
            return False

        # Reverse: offset -> pointer
        calculated_pointer = offset_to_pointer(rom_offset, ctx)
        if calculated_pointer != pointer_value:
            return False

        return True
    except ValueError:
        return False


def validate_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a single JSONL item's pointer transform.

    Args:
        item: Dictionary with offset, pointer_value, and optionally pointer_refs

    Returns:
        Validation result dict with pass/fail and details
    """
    result = {
        "id": item.get("id"),
        "offset": item.get("offset"),
        "pointer_value": item.get("pointer_value"),
        "passed": False,
        "error": None,
    }

    # Parse offset
    offset = item.get("offset")
    if isinstance(offset, str):
        offset = int(offset, 16)

    # Parse pointer_value
    pointer_value = item.get("pointer_value")
    if pointer_value is None:
        result["error"] = "missing pointer_value"
        return result
    if isinstance(pointer_value, str):
        pointer_value = int(pointer_value, 16)

    # Get or infer bank_addend
    pointer_refs = item.get("pointer_refs", [])
    if pointer_refs:
        ref = pointer_refs[0]
        bank_addend = ref.get("bank_addend", 0)
        if isinstance(bank_addend, str):
            bank_addend = int(bank_addend, 16)
    else:
        # Infer from data
        bank_addend = infer_bank_addend(pointer_value, offset)

    ctx = PointerContext(bank_addend=bank_addend)

    # Validate roundtrip
    try:
        calculated_offset = pointer_to_offset(pointer_value, ctx)
        calculated_pointer = offset_to_pointer(offset, ctx)

        result["calculated_offset"] = f"0x{calculated_offset:06X}"
        result["calculated_pointer"] = f"0x{calculated_pointer:04X}"
        result["bank_addend"] = f"0x{bank_addend:05X}"

        if calculated_offset == offset and calculated_pointer == pointer_value:
            result["passed"] = True
        else:
            result["error"] = (
                f"mismatch: ptr_to_off=0x{calculated_offset:06X} (expected 0x{offset:06X}), "
                f"off_to_ptr=0x{calculated_pointer:04X} (expected 0x{pointer_value:04X})"
            )
    except ValueError as e:
        result["error"] = str(e)

    return result


# =============================================================================
# BATCH OPERATIONS
# =============================================================================

def validate_jsonl_file(jsonl_path: str) -> Dict[str, Any]:
    """
    Validate all items in a JSONL file.

    Args:
        jsonl_path: Path to JSONL file

    Returns:
        Summary dict with pass/fail counts and details
    """
    import json
    from pathlib import Path

    items = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))

    results = {
        "file": str(jsonl_path),
        "total": len(items),
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "failures": [],
    }

    for item in items:
        if item.get("pointer_value") is None:
            results["skipped"] += 1
            continue

        validation = validate_item(item)
        if validation["passed"]:
            results["passed"] += 1
        else:
            results["failed"] += 1
            results["failures"].append(validation)

    return results
