# -*- coding: utf-8 -*-
"""
================================================================================
SMS RELOCATION V1 - Text Reinsertion with Pointer Relocation
================================================================================
Implements safe text reinsertion with automatic relocation when translated
text exceeds max_len_bytes.

Rules:
1. NO blind scan - only write within configured free_space_regions
2. If len(translated + terminator) <= max_len_bytes -> reinsert in-place
3. If larger -> relocate:
   - Find new_offset via first-fit in 0xFF/0x00 runs within allowed ranges
   - Respect alignment
   - Update all pointer_refs with new pointer value
   - Validate round-trip for each pointer update
================================================================================
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
from copy import deepcopy
from datetime import datetime, timezone

from .sms_pointer_transform import (
    pointer_to_offset,
    offset_to_pointer,
    PointerContext,
    PointerRef,
)
from utils.rom_io import (
    atomic_write_bytes,
    compute_checksums,
    ensure_parent_dir,
    make_backup,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class RelocationConfig:
    """Configuration for SMS relocation."""
    # Free space regions: list of (start, end) tuples
    # ONLY these regions can be used for relocation
    free_space_regions: List[Tuple[int, int]] = field(default_factory=list)

    # Alignment for relocated text (0 = no alignment)
    alignment: int = 1

    # Fill byte to search for (typically 0xFF or 0x00)
    fill_bytes: Tuple[int, ...] = (0xFF, 0x00)

    # Default terminator byte
    default_terminator: int = 0x00

    # Allowed addressing modes (whitelist)
    allowed_addressing_modes: Set[str] = field(default_factory=lambda: {
        "DIRECT", "BANKED_SLOT1", "BANKED_SLOT2", "INFERRED"
    })

    # Allowed bank_addend values (whitelist) - None means allow all
    allowed_bank_addends: Optional[Set[int]] = None

    # Encoding for text
    encoding: str = "ascii"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "free_space_regions": [
                {"start": f"0x{s:06X}", "end": f"0x{e:06X}"}
                for s, e in self.free_space_regions
            ],
            "alignment": self.alignment,
            "fill_bytes": list(self.fill_bytes),
            "default_terminator": self.default_terminator,
            "allowed_addressing_modes": list(self.allowed_addressing_modes),
            "encoding": self.encoding,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RelocationConfig":
        """Create from dictionary."""
        regions = []
        for r in d.get("free_space_regions", []):
            if isinstance(r, dict):
                start = r.get("start", 0)
                end = r.get("end", 0)
                if isinstance(start, str):
                    start = int(start, 16)
                if isinstance(end, str):
                    end = int(end, 16)
                regions.append((start, end))
            elif isinstance(r, (list, tuple)) and len(r) == 2:
                regions.append((r[0], r[1]))

        return cls(
            free_space_regions=regions,
            alignment=d.get("alignment", 1),
            fill_bytes=tuple(d.get("fill_bytes", [0xFF, 0x00])),
            default_terminator=d.get("default_terminator", 0x00),
            allowed_addressing_modes=set(d.get("allowed_addressing_modes", [
                "DIRECT", "BANKED_SLOT1", "BANKED_SLOT2", "INFERRED"
            ])),
            encoding=d.get("encoding", "ascii"),
        )


# =============================================================================
# FREE SPACE ALLOCATOR
# =============================================================================

@dataclass
class AllocationResult:
    """Result of space allocation."""
    success: bool
    offset: Optional[int] = None
    size: int = 0
    region_index: Optional[int] = None
    error: Optional[str] = None


class FreeSpaceAllocator:
    """
    Manages free space allocation within configured regions.
    Uses first-fit strategy, only allocates in runs of fill bytes.
    """

    def __init__(self, rom_data: bytearray, config: RelocationConfig):
        self.rom_data = rom_data
        self.config = config
        self.rom_size = len(rom_data)

        # Track allocations: offset -> size
        self.allocations: Dict[int, int] = {}

        # Track available space per region
        self.region_usage: Dict[int, int] = {}  # region_index -> bytes_used

    def find_free_run(self, size_needed: int) -> AllocationResult:
        """
        Find a contiguous run of fill bytes large enough for size_needed.
        Uses first-fit strategy within configured regions only.

        Args:
            size_needed: Number of bytes needed (including terminator)

        Returns:
            AllocationResult with offset if found, error otherwise
        """
        if not self.config.free_space_regions:
            return AllocationResult(
                success=False,
                error="No free_space_regions configured"
            )

        # Apply alignment
        aligned_size = size_needed
        if self.config.alignment > 1:
            aligned_size = ((size_needed + self.config.alignment - 1)
                           // self.config.alignment * self.config.alignment)

        for region_idx, (region_start, region_end) in enumerate(self.config.free_space_regions):
            # Validate region bounds
            if region_start >= self.rom_size or region_end > self.rom_size:
                continue
            if region_start >= region_end:
                continue

            # Search for free run within this region
            offset = self._find_run_in_region(
                region_start, region_end, aligned_size
            )

            if offset is not None:
                return AllocationResult(
                    success=True,
                    offset=offset,
                    size=aligned_size,
                    region_index=region_idx,
                )

        return AllocationResult(
            success=False,
            error=f"No free space found for {size_needed} bytes in configured regions"
        )

    def _find_run_in_region(self, start: int, end: int, size: int) -> Optional[int]:
        """
        Find a run of fill bytes within a specific region.
        Skips already allocated areas.
        """
        # Apply alignment to start
        if self.config.alignment > 1:
            aligned_start = ((start + self.config.alignment - 1)
                            // self.config.alignment * self.config.alignment)
        else:
            aligned_start = start

        pos = aligned_start
        while pos + size <= end:
            # Check if this position is already allocated
            if self._is_allocated(pos, size):
                pos += self.config.alignment if self.config.alignment > 1 else 1
                continue

            # Check if we have a run of fill bytes
            if self._is_fill_run(pos, size):
                return pos

            # Move to next aligned position
            pos += self.config.alignment if self.config.alignment > 1 else 1

        return None

    def _is_allocated(self, offset: int, size: int) -> bool:
        """Check if range overlaps with any existing allocation."""
        for alloc_offset, alloc_size in self.allocations.items():
            alloc_end = alloc_offset + alloc_size
            range_end = offset + size
            # Check for overlap
            if offset < alloc_end and range_end > alloc_offset:
                return True
        return False

    def _is_fill_run(self, offset: int, size: int) -> bool:
        """Check if range contains only fill bytes."""
        for i in range(size):
            if offset + i >= self.rom_size:
                return False
            if self.rom_data[offset + i] not in self.config.fill_bytes:
                return False
        return True

    def allocate(self, size_needed: int) -> AllocationResult:
        """
        Allocate space and mark it as used.

        Args:
            size_needed: Number of bytes needed

        Returns:
            AllocationResult with offset if successful
        """
        result = self.find_free_run(size_needed)
        if result.success and result.offset is not None:
            self.allocations[result.offset] = result.size
            if result.region_index is not None:
                self.region_usage[result.region_index] = (
                    self.region_usage.get(result.region_index, 0) + result.size
                )
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get allocation statistics."""
        total_free = sum(end - start for start, end in self.config.free_space_regions)
        total_used = sum(self.allocations.values())
        return {
            "total_free_space": total_free,
            "total_allocated": total_used,
            "remaining": total_free - total_used,
            "allocation_count": len(self.allocations),
            "region_usage": dict(self.region_usage),
        }


# =============================================================================
# RELOCATION ENGINE
# =============================================================================

@dataclass
class ReinsertionItem:
    """Item to be reinserted."""
    id: int
    offset: int  # Original offset
    text_src: str  # Original text
    text_dst: str  # Translated text
    max_len_bytes: int
    terminator: int
    encoding: str
    pointer_refs: List[Dict[str, Any]]

    @classmethod
    def from_jsonl_entry(cls, entry: Dict[str, Any], text_dst: str) -> "ReinsertionItem":
        """Create from JSONL entry with translated text."""
        offset = entry.get("offset", 0)
        if isinstance(offset, str):
            offset = int(offset, 16)

        terminator = entry.get("terminator", 0x00)
        if terminator is None:
            terminator = 0x00

        return cls(
            id=entry.get("id", 0),
            offset=offset,
            text_src=entry.get("text_src", ""),
            text_dst=text_dst,
            max_len_bytes=entry.get("max_len_bytes", 0),
            terminator=terminator,
            encoding=entry.get("encoding", "ascii"),
            pointer_refs=entry.get("pointer_refs", []),
        )


@dataclass
class ReinsertionResult:
    """Result of a single reinsertion."""
    id: int
    success: bool
    method: str  # "in_place" or "relocated"
    original_offset: int
    new_offset: Optional[int] = None
    bytes_written: int = 0
    pointers_updated: int = 0
    error: Optional[str] = None
    pointer_updates: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RelocationReport:
    """Full relocation report."""
    total_items: int = 0
    in_place_count: int = 0
    relocated_count: int = 0
    failed_count: int = 0
    pointers_updated: int = 0
    bytes_relocated: int = 0
    results: List[ReinsertionResult] = field(default_factory=list)
    failures: List[ReinsertionResult] = field(default_factory=list)
    allocator_stats: Dict[str, Any] = field(default_factory=dict)


class SMSRelocationEngine:
    """
    Main engine for SMS text reinsertion with relocation support.
    """

    def __init__(self, rom_data: bytes, config: RelocationConfig):
        """
        Initialize relocation engine.

        Args:
            rom_data: Original ROM data (will be copied)
            config: Relocation configuration
        """
        self.original_rom = rom_data
        self.rom_data = bytearray(rom_data)
        self.config = config
        self.allocator = FreeSpaceAllocator(self.rom_data, config)
        self.report = RelocationReport()

    def reinsert_item(self, item: ReinsertionItem) -> ReinsertionResult:
        """
        Reinsert a single translated item.

        Rules:
        1. If fits in original space -> in-place
        2. If larger -> relocate to free space and update pointers
        """
        # Validações críticas de segurança
        if item.offset < 0 or item.offset >= len(self.rom_data):
            return ReinsertionResult(
                id=item.id,
                success=False,
                method="none",
                original_offset=item.offset,
                error="offset fora do tamanho da ROM",
            )

        if item.max_len_bytes <= 0:
            return ReinsertionResult(
                id=item.id,
                success=False,
                method="none",
                original_offset=item.offset,
                error="max_len_bytes inválido (<= 0)",
            )

        if not (0 <= int(item.terminator) <= 255):
            return ReinsertionResult(
                id=item.id,
                success=False,
                method="none",
                original_offset=item.offset,
                error="terminator fora de 0-255",
            )

        max_total = item.max_len_bytes + 1
        if item.offset + max_total > len(self.rom_data):
            return ReinsertionResult(
                id=item.id,
                success=False,
                method="none",
                original_offset=item.offset,
                error="offset + max_len_bytes excede tamanho da ROM",
            )

        # Encode translated text
        try:
            encoded = item.text_dst.encode(item.encoding)
        except UnicodeEncodeError as e:
            return ReinsertionResult(
                id=item.id,
                success=False,
                method="none",
                original_offset=item.offset,
                error=f"Encoding error: {e}",
            )

        # Calculate size needed (text + terminator)
        size_needed = len(encoded) + 1  # +1 for terminator

        # Check if fits in original space
        if size_needed <= item.max_len_bytes:
            return self._reinsert_in_place(item, encoded)
        else:
            return self._reinsert_relocated(item, encoded)

    def _reinsert_in_place(self, item: ReinsertionItem, encoded: bytes) -> ReinsertionResult:
        """Reinsert text in original location."""
        offset = item.offset

        # Write text
        for i, byte in enumerate(encoded):
            if offset + i < len(self.rom_data):
                self.rom_data[offset + i] = byte

        # Write terminator
        term_offset = offset + len(encoded)
        if term_offset < len(self.rom_data):
            self.rom_data[term_offset] = item.terminator

        # Pad remaining space with terminator
        for i in range(len(encoded) + 1, item.max_len_bytes):
            pad_offset = offset + i
            if pad_offset < len(self.rom_data):
                self.rom_data[pad_offset] = item.terminator

        return ReinsertionResult(
            id=item.id,
            success=True,
            method="in_place",
            original_offset=offset,
            new_offset=offset,
            bytes_written=len(encoded) + 1,
        )

    def _reinsert_relocated(self, item: ReinsertionItem, encoded: bytes) -> ReinsertionResult:
        """Reinsert text in new location and update pointers."""
        size_needed = len(encoded) + 1

        # Allocate new space
        alloc_result = self.allocator.allocate(size_needed)
        if not alloc_result.success:
            return ReinsertionResult(
                id=item.id,
                success=False,
                method="relocated",
                original_offset=item.offset,
                error=alloc_result.error,
            )

        new_offset = alloc_result.offset

        # Write text at new location
        for i, byte in enumerate(encoded):
            if new_offset + i < len(self.rom_data):
                self.rom_data[new_offset + i] = byte

        # Write terminator
        term_offset = new_offset + len(encoded)
        if term_offset < len(self.rom_data):
            self.rom_data[term_offset] = item.terminator

        # Update pointers
        pointer_updates = []
        pointers_updated = 0

        for ptr_ref in item.pointer_refs:
            update_result = self._update_pointer(ptr_ref, new_offset)
            pointer_updates.append(update_result)
            if update_result.get("success"):
                pointers_updated += 1

        # Check if all pointer updates succeeded
        all_pointers_ok = all(u.get("success") for u in pointer_updates)
        if not all_pointers_ok:
            failed_updates = [u for u in pointer_updates if not u.get("success")]
            return ReinsertionResult(
                id=item.id,
                success=False,
                method="relocated",
                original_offset=item.offset,
                new_offset=new_offset,
                bytes_written=len(encoded) + 1,
                pointers_updated=pointers_updated,
                error=f"Pointer update failures: {failed_updates}",
                pointer_updates=pointer_updates,
            )

        return ReinsertionResult(
            id=item.id,
            success=True,
            method="relocated",
            original_offset=item.offset,
            new_offset=new_offset,
            bytes_written=len(encoded) + 1,
            pointers_updated=pointers_updated,
            pointer_updates=pointer_updates,
        )

    def _update_pointer(self, ptr_ref: Dict[str, Any], new_offset: int) -> Dict[str, Any]:
        """
        Update a single pointer to point to new_offset.

        Validates:
        1. addressing_mode is in whitelist
        2. bank_addend is in whitelist (if configured)
        3. Round-trip: pointer_to_offset(new_ptr, ctx) == new_offset
        """
        result = {
            "ptr_ref": ptr_ref,
            "new_offset": f"0x{new_offset:06X}",
            "success": False,
        }

        # Parse ptr_ref fields
        ptr_offset = ptr_ref.get("ptr_offset", 0)
        if isinstance(ptr_offset, str):
            ptr_offset = int(ptr_offset, 16)

        ptr_size = ptr_ref.get("ptr_size", 2)
        endianness = ptr_ref.get("endianness", "little")
        addressing_mode = ptr_ref.get("addressing_mode", "INFERRED")

        bank_addend = ptr_ref.get("bank_addend", 0)
        if isinstance(bank_addend, str):
            bank_addend = int(bank_addend, 16)

        # Validate addressing_mode
        if addressing_mode not in self.config.allowed_addressing_modes:
            result["error"] = f"addressing_mode '{addressing_mode}' not in whitelist"
            return result

        # Validate bank_addend (if whitelist configured)
        if self.config.allowed_bank_addends is not None:
            if bank_addend not in self.config.allowed_bank_addends:
                result["error"] = f"bank_addend 0x{bank_addend:05X} not in whitelist"
                return result

        # Create context and calculate new pointer value
        ctx = PointerContext(
            ptr_size=ptr_size,
            endianness=endianness,
            addressing_mode=addressing_mode,
            bank_addend=bank_addend,
        )

        try:
            new_ptr = offset_to_pointer(new_offset, ctx)
        except ValueError as e:
            result["error"] = f"offset_to_pointer failed: {e}"
            return result

        result["new_ptr"] = f"0x{new_ptr:04X}"

        # Validate round-trip
        try:
            roundtrip_offset = pointer_to_offset(new_ptr, ctx)
            if roundtrip_offset != new_offset:
                result["error"] = (
                    f"Round-trip failed: pointer_to_offset(0x{new_ptr:04X}) "
                    f"= 0x{roundtrip_offset:06X}, expected 0x{new_offset:06X}"
                )
                return result
        except ValueError as e:
            result["error"] = f"Round-trip pointer_to_offset failed: {e}"
            return result

        result["roundtrip_passed"] = True

        # Write new pointer value to ROM
        if ptr_size == 2:
            if endianness == "little":
                ptr_bytes = new_ptr.to_bytes(2, byteorder="little")
            else:
                ptr_bytes = new_ptr.to_bytes(2, byteorder="big")
        else:
            result["error"] = f"Unsupported ptr_size: {ptr_size}"
            return result

        # Write to ROM
        for i, byte in enumerate(ptr_bytes):
            if ptr_offset + i < len(self.rom_data):
                self.rom_data[ptr_offset + i] = byte

        result["success"] = True
        result["bytes_written"] = ptr_bytes.hex()
        return result

    def process_all(self, items: List[ReinsertionItem]) -> RelocationReport:
        """
        Process all reinsertion items.

        Args:
            items: List of items to reinsert

        Returns:
            RelocationReport with all results
        """
        self.report = RelocationReport(total_items=len(items))

        for item in items:
            result = self.reinsert_item(item)
            self.report.results.append(result)

            if result.success:
                if result.method == "in_place":
                    self.report.in_place_count += 1
                elif result.method == "relocated":
                    self.report.relocated_count += 1
                    self.report.bytes_relocated += result.bytes_written
                self.report.pointers_updated += result.pointers_updated
            else:
                self.report.failed_count += 1
                self.report.failures.append(result)

        self.report.allocator_stats = self.allocator.get_stats()
        return self.report

    def get_modified_rom(self) -> bytes:
        """Get the modified ROM data."""
        return bytes(self.rom_data)

    def write_report(self, path: Path) -> None:
        """Write relocation report to file."""
        with open(path, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("SMS RELOCATION REPORT V1\n")
            f.write("=" * 60 + "\n\n")

            f.write(f"TOTAL ITEMS: {self.report.total_items}\n")
            f.write(f"IN-PLACE: {self.report.in_place_count}\n")
            f.write(f"RELOCATED: {self.report.relocated_count}\n")
            f.write(f"FAILED: {self.report.failed_count}\n")
            f.write(f"POINTERS UPDATED: {self.report.pointers_updated}\n")
            f.write(f"BYTES RELOCATED: {self.report.bytes_relocated}\n\n")

            if self.report.relocated_count > 0:
                f.write("-" * 40 + "\n")
                f.write("RELOCATED ITEMS\n")
                f.write("-" * 40 + "\n")
                for r in self.report.results:
                    if r.method == "relocated" and r.success:
                        f.write(f"  ID {r.id}: 0x{r.original_offset:06X} -> 0x{r.new_offset:06X}\n")
                        for pu in r.pointer_updates:
                            if pu.get("success"):
                                f.write(f"    ptr @ {pu['ptr_ref'].get('ptr_offset')} "
                                       f"= {pu.get('new_ptr')}\n")
                f.write("\n")

            if self.report.failed_count > 0:
                f.write("-" * 40 + "\n")
                f.write("FAILURES\n")
                f.write("-" * 40 + "\n")
                for r in self.report.failures:
                    f.write(f"  ID {r.id}: {r.error}\n")
                f.write("\n")

            f.write("-" * 40 + "\n")
            f.write("ALLOCATOR STATS\n")
            f.write("-" * 40 + "\n")
            stats = self.report.allocator_stats
            f.write(f"  Total free space: {stats.get('total_free_space', 0)} bytes\n")
            f.write(f"  Total allocated: {stats.get('total_allocated', 0)} bytes\n")
            f.write(f"  Remaining: {stats.get('remaining', 0)} bytes\n")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def load_translations(jsonl_path: str, translations: Dict[int, str]) -> List[ReinsertionItem]:
    """
    Load items from JSONL and pair with translations.

    Args:
        jsonl_path: Path to pure_text.jsonl
        translations: Dict mapping id -> translated text

    Returns:
        List of ReinsertionItem
    """
    items = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            item_id = entry.get("id", 0)

            # Get translation or use original
            text_dst = translations.get(item_id, entry.get("text_src", ""))

            items.append(ReinsertionItem.from_jsonl_entry(entry, text_dst))

    return items


def run_relocation(
    rom_path: str,
    jsonl_path: str,
    translations: Dict[int, str],
    config: RelocationConfig,
    output_rom_path: str,
    output_report_path: Optional[str] = None,
    strict: bool = False,
    dry_run: bool = False,
    create_backup: bool = True,
    report_json_path: Optional[str] = None,
) -> RelocationReport:
    """
    Run full relocation process.

    Args:
        rom_path: Path to original ROM
        jsonl_path: Path to pure_text.jsonl
        translations: Dict mapping id -> translated text
        config: Relocation configuration
        output_rom_path: Path for modified ROM
        output_report_path: Optional path for report

    Returns:
        RelocationReport
    """
    # Load ROM
    rom_path = str(rom_path)
    rom_data = Path(rom_path).read_bytes()
    crc_before, sha_before = compute_checksums(rom_data)

    # Load items
    items = load_translations(jsonl_path, translations)

    # Run relocation
    engine = SMSRelocationEngine(rom_data, config)
    report = engine.process_all(items)

    if strict and report.failed_count > 0:
        raise ValueError(f"Relocation falhou para {report.failed_count} itens (strict=True)")

    # Save modified ROM
    output_rom_path = Path(output_rom_path)
    if create_backup and not dry_run:
        make_backup(Path(rom_path))

    if not dry_run:
        ensure_parent_dir(output_rom_path)
        atomic_write_bytes(output_rom_path, engine.get_modified_rom())

    crc_after, sha_after = compute_checksums(engine.get_modified_rom())

    # Save report
    if output_report_path:
        engine.write_report(Path(output_report_path))

    # Save JSON report (opcional)
    if report_json_path:
        report_json = {
            "rom_path": rom_path,
            "output_path": str(output_rom_path),
            "dry_run": dry_run,
            "strict": strict,
            "checksums": {
                "before": {"crc32": crc_before, "sha256": sha_before},
                "after": {"crc32": crc_after, "sha256": sha_after},
            },
            "summary": {
                "total_items": report.total_items,
                "in_place": report.in_place_count,
                "relocated": report.relocated_count,
                "failed": report.failed_count,
            },
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        Path(report_json_path).write_text(
            json.dumps(report_json, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return report
