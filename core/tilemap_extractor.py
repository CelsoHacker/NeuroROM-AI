# -*- coding: utf-8 -*-
"""
================================================================================
TILEMAP EXTRACTOR - Guided UI/HUD Label Extraction
================================================================================
Extracts text from tilemap regions (SCORE, TIME, RINGS, etc.) based on
user-provided region definitions. No blind scanning.

Supports: NES, SMS, MD, SNES tilemaps with optional glyph_map decoding.
================================================================================
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import re

from ..unification.text_unifier import TilemapRegion, UnifiedTextItem


class TilemapExtractor:
    """
    Guided tilemap extraction for UI/HUD labels.

    Usage:
        extractor = TilemapExtractor(rom_data, crc32)
        items = extractor.extract_regions(regions)
    """

    def __init__(self, rom_data: bytes, crc32: str = ""):
        """
        Initialize extractor.

        Args:
            rom_data: Raw ROM bytes
            crc32: ROM CRC32 for identification (neutral)
        """
        self.rom_data = rom_data
        self.crc32 = crc32
        self._item_counter = 0

        # Stats
        self.stats = {
            "detected": 0,
            "translated": 0,
            "blocked_no_map": 0,
            "rejected_overflow": 0,
        }

    def extract_regions(self, regions: List[TilemapRegion]) -> List[UnifiedTextItem]:
        """
        Extract text from all specified tilemap regions.

        Args:
            regions: List of TilemapRegion specifications (user-provided)

        Returns:
            List of UnifiedTextItem with kind="UI_TILEMAP_LABEL"
        """
        items = []

        for region in regions:
            if region.kind == "tilemap":
                item = self._extract_tilemap(region)
                if item:
                    items.append(item)
                    self.stats["detected"] += 1
            # "font" regions are for building glyph maps, not extraction

        return items

    def _extract_tilemap(self, region: TilemapRegion) -> Optional[UnifiedTextItem]:
        """
        Extract single tilemap region.

        Args:
            region: TilemapRegion specification

        Returns:
            UnifiedTextItem or None if too short
        """
        # Validate bounds
        if region.offset + region.length > len(self.rom_data):
            return None

        # Read raw bytes
        raw = self.rom_data[region.offset:region.offset + region.length]

        # Filter: minimum 3 bytes
        if len(raw) < 3:
            return None

        self._item_counter += 1

        # Build raw tokens and decode text
        raw_tokens_parts = []
        text_parts = []
        glyph_map = region.glyph_map or {}

        for b in raw:
            tile_idx = b & region.tile_attrs_mask
            raw_tokens_parts.append(f"<TILE:{tile_idx:02X}>")

            if tile_idx in glyph_map:
                text_parts.append(glyph_map[tile_idx])
            # If not in map, don't add to text (will be tokenized)

        raw_tokens = ''.join(raw_tokens_parts)

        # Determine text_src and reinsertion_safe
        has_glyph_map = bool(glyph_map)

        if has_glyph_map and text_parts:
            # Partial decode: mix decoded chars with tokens for unknowns
            text_src = self._build_mixed_text(raw, glyph_map, region.tile_attrs_mask)
            # Safe only if ALL tiles are in glyph_map
            all_known = all((b & region.tile_attrs_mask) in glyph_map for b in raw)
            reinsertion_safe = all_known
            reason_codes = [] if all_known else ["PARTIAL_GLYPH_MAP"]
            self.stats["translated"] += 1 if all_known else 0
        else:
            # No glyph_map: export raw tokens only
            text_src = raw_tokens
            reinsertion_safe = False
            reason_codes = ["NO_GLYPH_MAP"]
            self.stats["blocked_no_map"] += 1

        return UnifiedTextItem(
            id=f"TM_{self._item_counter:05d}",
            text_src=text_src,
            source="static",
            static_offset=region.offset,
            static_item=None,
            origin_offset=region.offset,
            origin_method="tilemap_label",
            reinsertion_safe=reinsertion_safe,
            confidence=1.0 if reinsertion_safe else 0.5,
            reason_codes=reason_codes,
            is_tokenized=not reinsertion_safe,
            # Tilemap-specific fields
            kind="UI_TILEMAP_LABEL",
            raw_tokens=raw_tokens,
            constraints={"fixed_length": True, "max_bytes": region.length},
            encoding=f"tilemap_{region.console.lower()}",
        )

    def _build_mixed_text(self, raw: bytes, glyph_map: Dict[int, str],
                          mask: int) -> str:
        """
        Build text mixing decoded chars and tokens for unknown tiles.

        Args:
            raw: Raw bytes
            glyph_map: Tile index -> character map
            mask: Attribute mask

        Returns:
            Mixed text string
        """
        parts = []
        for b in raw:
            tile_idx = b & mask
            if tile_idx in glyph_map:
                parts.append(glyph_map[tile_idx])
            else:
                parts.append(f"<TILE:{tile_idx:02X}>")
        return ''.join(parts)

    def get_stats(self) -> Dict[str, int]:
        """Return extraction statistics."""
        return self.stats.copy()


def encode_tilemap_text(text: str, glyph_map: Dict[int, str],
                        max_bytes: int) -> Optional[bytes]:
    """
    Encode translated text back to tilemap bytes.

    Args:
        text: Translated text (may contain <TILE:XX> tokens)
        glyph_map: Original tile index -> character map
        max_bytes: Maximum allowed bytes (fixed_length constraint)

    Returns:
        Encoded bytes or None if overflow
    """
    # Build reverse map
    reverse_map = {v: k for k, v in glyph_map.items()}

    result = bytearray()
    i = 0

    while i < len(text):
        # Check for token pattern: <TILE:XX>
        match = re.match(r'<TILE:([0-9A-Fa-f]{2})>', text[i:])
        if match:
            tile_idx = int(match.group(1), 16)
            result.append(tile_idx)
            i += len(match.group(0))
            continue

        # Plain character
        char = text[i]
        if char in reverse_map:
            result.append(reverse_map[char])
        else:
            # Unknown character - cannot encode
            return None
        i += 1

    # Validate fixed_length constraint
    if len(result) > max_bytes:
        return None

    # Pad to exact length if needed
    while len(result) < max_bytes:
        # Use space or 0x00 as padding (configurable)
        result.append(0x00)

    return bytes(result)
