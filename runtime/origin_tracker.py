# -*- coding: utf-8 -*-
"""
================================================================================
ORIGIN TRACKER - Maps Runtime Text to Static ROM Origins
================================================================================
Tracks where runtime-captured text originates in the ROM.
Essential for generating reinsertion patches.
================================================================================
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .runtime_text_harvester import RuntimeTextItem


@dataclass
class StaticOrigin:
    """Static ROM origin of runtime text."""
    rom_offset: int
    pointer_offset: Optional[int] = None
    compression_source: Optional[int] = None
    method: str = "direct"           # direct, pointer, decompressed
    confidence: float = 0.0
    match_type: str = "exact"        # exact, fuzzy, tile_sequence
    notes: str = ""


@dataclass
class TrackingResult:
    """Result of origin tracking."""
    runtime_item: RuntimeTextItem
    origin: Optional[StaticOrigin]
    reinsertion_safe: bool = False
    reason: str = ""


class OriginTracker:
    """
    Maps runtime text items to static ROM origins.

    Strategies:
    1. Exact byte sequence match
    2. Tile sequence match
    3. Pointer table reverse lookup
    4. Decompression source tracing
    """

    def __init__(self, rom_data: bytes, plugin: Any = None):
        """
        Initialize tracker.

        Args:
            rom_data: ROM data
            plugin: Console plugin for address mapping
        """
        self.rom_data = rom_data
        self.plugin = plugin

        self._char_table: Dict[int, str] = {}
        self._reverse_table: Dict[str, int] = {}
        self._pointer_cache: Dict[int, int] = {}
        self._decompressed_regions: Dict[int, bytes] = {}

    def set_char_table(self, char_table: Dict[int, str]) -> None:
        """Set character table and build reverse lookup."""
        self._char_table = char_table
        self._reverse_table = {v: k for k, v in char_table.items()}

    def set_pointer_cache(self, pointers: Dict[int, int]) -> None:
        """Set pointer cache (target -> pointer_offset)."""
        self._pointer_cache = pointers

    def set_decompressed_regions(self, regions: Dict[int, bytes]) -> None:
        """Set decompressed data regions."""
        self._decompressed_regions = regions

    def track_origin(self, runtime_item: RuntimeTextItem) -> TrackingResult:
        """
        Find static ROM origin for runtime text.

        Args:
            runtime_item: Runtime text item

        Returns:
            TrackingResult with origin info
        """
        # Strategy 1: Exact byte match
        origin = self._find_exact_match(runtime_item)
        if origin and origin.confidence >= 0.9:
            return TrackingResult(
                runtime_item=runtime_item,
                origin=origin,
                reinsertion_safe=True,
                reason="exact_match"
            )

        # Strategy 2: Tile sequence match
        if runtime_item.tile_indices:
            origin = self._find_tile_match(runtime_item)
            if origin and origin.confidence >= 0.8:
                return TrackingResult(
                    runtime_item=runtime_item,
                    origin=origin,
                    reinsertion_safe=True,
                    reason="tile_match"
                )

        # Strategy 3: Pointer reverse lookup
        origin = self._find_via_pointer(runtime_item)
        if origin:
            return TrackingResult(
                runtime_item=runtime_item,
                origin=origin,
                reinsertion_safe=origin.confidence >= 0.7,
                reason="pointer_match"
            )

        # Strategy 4: Decompressed region search
        origin = self._find_in_decompressed(runtime_item)
        if origin:
            return TrackingResult(
                runtime_item=runtime_item,
                origin=origin,
                reinsertion_safe=False,  # Compressed = harder to reinsert
                reason="decompressed_match"
            )

        # No origin found
        return TrackingResult(
            runtime_item=runtime_item,
            origin=None,
            reinsertion_safe=False,
            reason="no_match"
        )

    def _find_exact_match(self, item: RuntimeTextItem) -> Optional[StaticOrigin]:
        """Find exact byte sequence match in ROM."""
        # Convert text to bytes using reverse char table
        text_bytes = self._text_to_bytes(item.text)
        if not text_bytes or len(text_bytes) < 3:
            return None

        # Search in ROM
        offset = self.rom_data.find(text_bytes)
        if offset >= 0:
            return StaticOrigin(
                rom_offset=offset,
                method="direct",
                confidence=1.0,
                match_type="exact",
            )

        # Try ASCII encoding
        try:
            ascii_bytes = item.text.encode('ascii')
            offset = self.rom_data.find(ascii_bytes)
            if offset >= 0:
                return StaticOrigin(
                    rom_offset=offset,
                    method="direct",
                    confidence=0.95,
                    match_type="exact_ascii",
                )
        except:
            pass

        return None

    def _find_tile_match(self, item: RuntimeTextItem) -> Optional[StaticOrigin]:
        """Find tile index sequence match in ROM."""
        if not item.tile_indices or len(item.tile_indices) < 3:
            return None

        # Convert to bytes
        tile_bytes = bytes(item.tile_indices)

        # Search in ROM
        offset = self.rom_data.find(tile_bytes)
        if offset >= 0:
            return StaticOrigin(
                rom_offset=offset,
                method="direct",
                confidence=0.9,
                match_type="tile_sequence",
            )

        return None

    def _find_via_pointer(self, item: RuntimeTextItem) -> Optional[StaticOrigin]:
        """Find text via pointer table reverse lookup."""
        # First find the text
        text_bytes = self._text_to_bytes(item.text)
        if not text_bytes:
            return None

        offset = self.rom_data.find(text_bytes)
        if offset < 0:
            return None

        # Check if any pointer points to this offset
        for target, pointer_off in self._pointer_cache.items():
            if target == offset:
                return StaticOrigin(
                    rom_offset=offset,
                    pointer_offset=pointer_off,
                    method="pointer",
                    confidence=0.85,
                    match_type="pointer_target",
                )

        return StaticOrigin(
            rom_offset=offset,
            method="direct",
            confidence=0.7,
            match_type="no_pointer",
            notes="Found text but no pointer reference"
        )

    def _find_in_decompressed(self, item: RuntimeTextItem) -> Optional[StaticOrigin]:
        """Find text in decompressed regions."""
        text_bytes = self._text_to_bytes(item.text)
        if not text_bytes:
            # Try ASCII
            try:
                text_bytes = item.text.encode('ascii')
            except:
                return None

        for comp_offset, decomp_data in self._decompressed_regions.items():
            local_offset = decomp_data.find(text_bytes)
            if local_offset >= 0:
                return StaticOrigin(
                    rom_offset=local_offset,
                    compression_source=comp_offset,
                    method="decompressed",
                    confidence=0.6,
                    match_type="in_compressed",
                    notes=f"Found in decompressed data from 0x{comp_offset:06X}"
                )

        return None

    def _text_to_bytes(self, text: str) -> Optional[bytes]:
        """Convert text to bytes using char table."""
        if not self._reverse_table:
            return None

        result = bytearray()
        for char in text:
            if char in self._reverse_table:
                result.append(self._reverse_table[char])
            elif char.startswith('<') and char.endswith('>'):
                # Token - skip
                continue
            else:
                # Unknown character
                return None

        return bytes(result) if result else None

    def track_all(self, items: List[RuntimeTextItem]) -> List[TrackingResult]:
        """Track origins for all items."""
        return [self.track_origin(item) for item in items]

    def get_reinsertion_safe(self, results: List[TrackingResult]) -> List[TrackingResult]:
        """Get only reinsertion-safe results."""
        return [r for r in results if r.reinsertion_safe]

    def get_coverage_stats(self, results: List[TrackingResult]) -> Dict[str, Any]:
        """Get tracking coverage statistics."""
        total = len(results)
        if total == 0:
            return {"total": 0, "tracked": 0, "safe": 0}

        tracked = sum(1 for r in results if r.origin is not None)
        safe = sum(1 for r in results if r.reinsertion_safe)

        by_method = {}
        for r in results:
            if r.origin:
                method = r.origin.method
                by_method[method] = by_method.get(method, 0) + 1

        return {
            "total": total,
            "tracked": tracked,
            "tracked_ratio": tracked / total,
            "safe": safe,
            "safe_ratio": safe / total,
            "by_method": by_method,
        }
