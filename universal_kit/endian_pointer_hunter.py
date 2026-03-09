# -*- coding: utf-8 -*-
"""
================================================================================
ENDIAN POINTER HUNTER - Universal Pointer Detection with Plugin Support
================================================================================
Extends the core pointer_scanner with:
- Plugin-aware address mapping
- Multi-endian support (LE/BE)
- Multi-size support (u16/u24/u32)
- Validation thresholds per console
- Text region targeting
================================================================================
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from enum import Enum
import struct


class PointerSize(Enum):
    """Pointer sizes in bytes."""
    U16 = 2
    U24 = 3
    U32 = 4


class Endianness(Enum):
    """Byte order."""
    LITTLE = "little"
    BIG = "big"


@dataclass
class PointerCandidate:
    """A candidate pointer found during hunting."""
    offset: int                    # Location in ROM
    value: int                     # Raw pointer value
    target_offset: int             # Calculated file offset
    size: PointerSize
    endianness: Endianness
    points_to_text: bool = False
    text_score: float = 0.0
    confidence: float = 0.0
    mapping_type: str = "direct"   # direct, lorom, hirom, etc.
    bank: Optional[int] = None

    def __repr__(self) -> str:
        return (f"<Ptr @0x{self.offset:06X}=0x{self.value:08X}"
                f"→0x{self.target_offset:06X} "
                f"{self.size.name} {self.endianness.value} "
                f"conf={self.confidence:.2f}>")


@dataclass
class PointerTableResult:
    """A detected pointer table."""
    start_offset: int
    end_offset: int
    pointer_size: PointerSize
    endianness: Endianness
    pointers: List[PointerCandidate]
    confidence: float = 0.0
    text_pointing_ratio: float = 0.0
    mapping_type: str = "direct"

    @property
    def count(self) -> int:
        return len(self.pointers)

    def __repr__(self) -> str:
        return (f"<PtrTable @0x{self.start_offset:06X}-0x{self.end_offset:06X} "
                f"n={self.count} conf={self.confidence:.2f}>")


class EndianPointerHunter:
    """
    Universal pointer hunter with plugin-aware address mapping.

    Extends core/pointer_scanner.py functionality with:
    - Plugin integration for address mapping
    - Configurable validation thresholds
    - Multiple endianness support
    - Text region targeting
    """

    def __init__(self, rom_data: bytes, plugin: Optional[Any] = None):
        """
        Initialize pointer hunter.

        Args:
            rom_data: Raw ROM bytes
            plugin: Console plugin for address mapping (optional)
        """
        self.rom_data = rom_data
        self.plugin = plugin
        self.rom_size = len(rom_data)

        # Get config from plugin or use defaults
        if plugin:
            config = plugin.get_pointer_config()
            self.pointer_sizes = [PointerSize(s) for s in config.get("sizes", [2, 3])]
            self.endianness_modes = [
                Endianness(e) for e in config.get("endianness", ["little"])
            ]
            self.min_run = config.get("min_run", 8)
            self.resolve_ratio = config.get("resolve_ratio", 0.60)
            self.text_score_min = config.get("text_score_min", 0.60)
        else:
            self.pointer_sizes = [PointerSize.U16, PointerSize.U24]
            self.endianness_modes = [Endianness.LITTLE]
            self.min_run = 8
            self.resolve_ratio = 0.60
            self.text_score_min = 0.60

    def hunt(self,
             text_regions: Optional[List[Dict[str, Any]]] = None,
             pointer_sizes: Optional[List[PointerSize]] = None,
             endianness_modes: Optional[List[Endianness]] = None,
             scan_range: Optional[Tuple[int, int]] = None,
             address_mapper: Optional[Callable[[int], int]] = None
             ) -> List[PointerTableResult]:
        """
        Hunt for pointer tables in ROM.

        Args:
            text_regions: Known text regions for validation
            pointer_sizes: Override pointer sizes to test
            endianness_modes: Override endianness modes to test
            scan_range: Optional (start, end) range to scan
            address_mapper: Optional custom address mapping function

        Returns:
            List of PointerTableResult ordered by confidence
        """
        sizes = pointer_sizes or self.pointer_sizes
        endians = endianness_modes or self.endianness_modes

        # Build text offset set for fast lookup
        text_offsets = self._build_text_offset_set(text_regions)

        # Collect all candidates
        all_candidates: List[PointerCandidate] = []

        start = scan_range[0] if scan_range else 0
        end = scan_range[1] if scan_range else self.rom_size

        for size in sizes:
            for endian in endians:
                candidates = self._scan_pointers(
                    size, endian, start, end, text_offsets, address_mapper
                )
                all_candidates.extend(candidates)

        # Group into tables
        tables = self._group_into_tables(all_candidates)

        # Filter by thresholds
        valid_tables = self._filter_tables(tables)

        # Sort by confidence
        valid_tables.sort(key=lambda t: t.confidence, reverse=True)

        return valid_tables

    def _build_text_offset_set(self, text_regions: Optional[List[Dict]]) -> Set[int]:
        """Build set of offsets that are known to contain text."""
        offsets = set()
        if not text_regions:
            return offsets

        for region in text_regions:
            start = region.get('offset', region.get('start', 0))
            if isinstance(start, str):
                start = int(start, 16) if start.startswith('0x') else int(start)
            length = region.get('length', region.get('size', 64))
            offsets.update(range(start, start + length))

        return offsets

    def _scan_pointers(self,
                       size: PointerSize,
                       endian: Endianness,
                       start: int,
                       end: int,
                       text_offsets: Set[int],
                       address_mapper: Optional[Callable[[int], int]]
                       ) -> List[PointerCandidate]:
        """Scan for pointers of specific size and endianness."""
        candidates = []
        step = size.value

        for offset in range(start, end - step + 1, step):
            # Read pointer value
            value = self._read_pointer(offset, size, endian)
            if value is None:
                continue

            # Map to file offset
            target_offset = self._map_address(value, address_mapper)
            if target_offset is None or target_offset < 0 or target_offset >= self.rom_size:
                continue

            # Check if points to text
            points_to_text = target_offset in text_offsets
            text_score = 0.0

            if not points_to_text and self.plugin:
                # Try to validate target as text
                valid, score = self.plugin.validate_pointer_target(target_offset, self.rom_data)
                points_to_text = valid
                text_score = score
            elif not points_to_text:
                # Basic validation without plugin
                text_score = self._basic_text_score(target_offset)
                points_to_text = text_score >= self.text_score_min

            candidates.append(PointerCandidate(
                offset=offset,
                value=value,
                target_offset=target_offset,
                size=size,
                endianness=endian,
                points_to_text=points_to_text,
                text_score=text_score,
                confidence=0.0,  # Calculated later in table context
            ))

        return candidates

    def _read_pointer(self, offset: int, size: PointerSize, endian: Endianness) -> Optional[int]:
        """Read pointer value from ROM."""
        if offset + size.value > self.rom_size:
            return None

        data = self.rom_data[offset:offset + size.value]
        be = endian == Endianness.BIG

        if size == PointerSize.U16:
            return struct.unpack('>H' if be else '<H', data)[0]
        elif size == PointerSize.U24:
            if be:
                return (data[0] << 16) | (data[1] << 8) | data[2]
            else:
                return data[0] | (data[1] << 8) | (data[2] << 16)
        elif size == PointerSize.U32:
            return struct.unpack('>I' if be else '<I', data)[0]

        return None

    def _map_address(self, address: int, custom_mapper: Optional[Callable[[int], int]]) -> Optional[int]:
        """Map ROM address to file offset."""
        if custom_mapper:
            return custom_mapper(address)

        if self.plugin:
            mapping = self.plugin.map_address(address, self.rom_data)
            return mapping.file_offset if mapping.is_valid else None

        # Default: assume direct mapping
        return address if 0 <= address < self.rom_size else None

    def _basic_text_score(self, target_offset: int) -> float:
        """Calculate basic text likelihood score without plugin."""
        if target_offset >= self.rom_size:
            return 0.0

        sample = self.rom_data[target_offset:target_offset + 32]
        if not sample:
            return 0.0

        # Count printable ASCII
        printable = sum(1 for b in sample if 0x20 <= b <= 0x7E or b in (0x00, 0x0A, 0x0D))
        letters = sum(1 for b in sample if 0x41 <= b <= 0x5A or 0x61 <= b <= 0x7A)

        printable_ratio = printable / len(sample)
        letter_ratio = letters / len(sample)

        return (printable_ratio * 0.6 + letter_ratio * 0.4)

    def _group_into_tables(self, candidates: List[PointerCandidate]) -> List[PointerTableResult]:
        """Group consecutive pointer candidates into tables."""
        if not candidates:
            return []

        # Sort by offset
        candidates.sort(key=lambda c: (c.size.value, c.endianness.value, c.offset))

        tables = []

        # Group by size and endianness
        groups: Dict[Tuple[PointerSize, Endianness], List[PointerCandidate]] = {}
        for c in candidates:
            key = (c.size, c.endianness)
            if key not in groups:
                groups[key] = []
            groups[key].append(c)

        for (size, endian), group in groups.items():
            # Find consecutive runs
            current_table: List[PointerCandidate] = []

            for c in group:
                if not current_table:
                    current_table.append(c)
                else:
                    last = current_table[-1]
                    expected_gap = size.value

                    if c.offset - last.offset == expected_gap:
                        # Consecutive
                        current_table.append(c)
                    else:
                        # Gap - finalize current table if valid
                        if len(current_table) >= self.min_run:
                            tables.append(self._create_table(current_table, size, endian))
                        current_table = [c]

            # Don't forget last table
            if len(current_table) >= self.min_run:
                tables.append(self._create_table(current_table, size, endian))

        return tables

    def _create_table(self, pointers: List[PointerCandidate],
                      size: PointerSize, endian: Endianness) -> PointerTableResult:
        """Create a PointerTableResult from candidates."""
        # Calculate table confidence
        text_pointing = sum(1 for p in pointers if p.points_to_text)
        text_ratio = text_pointing / len(pointers) if pointers else 0

        # Check value ordering (ascending targets suggest valid table)
        values = [p.target_offset for p in pointers]
        ascending = sum(1 for i in range(len(values) - 1) if values[i + 1] > values[i])
        order_ratio = ascending / (len(values) - 1) if len(values) > 1 else 0.5

        # Average text score
        avg_text_score = sum(p.text_score for p in pointers) / len(pointers) if pointers else 0

        # Overall confidence
        confidence = (
            text_ratio * 0.50 +
            order_ratio * 0.25 +
            avg_text_score * 0.25
        )

        # Update pointer confidences
        for p in pointers:
            p.confidence = confidence

        return PointerTableResult(
            start_offset=pointers[0].offset,
            end_offset=pointers[-1].offset + size.value,
            pointer_size=size,
            endianness=endian,
            pointers=pointers,
            confidence=confidence,
            text_pointing_ratio=text_ratio,
        )

    def _filter_tables(self, tables: List[PointerTableResult]) -> List[PointerTableResult]:
        """Filter tables by validation thresholds."""
        valid = []

        for table in tables:
            # Must have minimum run length
            if table.count < self.min_run:
                continue

            # Must have minimum text resolution ratio
            if table.text_pointing_ratio < self.resolve_ratio:
                continue

            valid.append(table)

        return valid

    def hunt_in_regions(self,
                        regions: List[Tuple[int, int]],
                        text_regions: Optional[List[Dict[str, Any]]] = None
                        ) -> List[PointerTableResult]:
        """
        Hunt for pointers only in specified regions.

        Args:
            regions: List of (start, end) tuples to scan
            text_regions: Known text regions for validation

        Returns:
            List of PointerTableResult
        """
        all_tables = []

        for start, end in regions:
            tables = self.hunt(
                text_regions=text_regions,
                scan_range=(start, end)
            )
            all_tables.extend(tables)

        # Deduplicate overlapping tables
        all_tables.sort(key=lambda t: (t.start_offset, -t.confidence))
        deduped = []

        for table in all_tables:
            overlaps = False
            for existing in deduped:
                if (table.start_offset < existing.end_offset and
                    table.end_offset > existing.start_offset):
                    overlaps = True
                    break
            if not overlaps:
                deduped.append(table)

        return sorted(deduped, key=lambda t: t.confidence, reverse=True)

    def extract_text_from_table(self, table: PointerTableResult,
                                 terminator: int = 0x00,
                                 max_length: int = 256
                                 ) -> List[Tuple[PointerCandidate, bytes]]:
        """
        Extract text data from a pointer table.

        Args:
            table: Pointer table to extract from
            terminator: Byte value that terminates strings
            max_length: Maximum string length

        Returns:
            List of (pointer, text_bytes) tuples
        """
        results = []

        for ptr in table.pointers:
            if not ptr.points_to_text:
                continue

            offset = ptr.target_offset
            if offset >= self.rom_size:
                continue

            # Read until terminator or max length
            end = offset
            while end < min(offset + max_length, self.rom_size):
                if self.rom_data[end] == terminator:
                    break
                end += 1

            text_bytes = self.rom_data[offset:end]
            results.append((ptr, text_bytes))

        return results


# Convenience function
def hunt_pointers(rom_data: bytes,
                  plugin: Optional[Any] = None,
                  text_regions: Optional[List[Dict]] = None
                  ) -> List[PointerTableResult]:
    """
    Hunt for pointer tables in ROM data.

    Args:
        rom_data: Raw ROM bytes
        plugin: Console plugin for address mapping
        text_regions: Known text regions for validation

    Returns:
        List of PointerTableResult ordered by confidence
    """
    hunter = EndianPointerHunter(rom_data, plugin)
    return hunter.hunt(text_regions=text_regions)
