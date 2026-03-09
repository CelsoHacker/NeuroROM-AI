# -*- coding: utf-8 -*-
"""
================================================================================
RUNTIME TEXT HARVESTER - Extracts Text from Running Emulator
================================================================================
Harvests text from emulator state using two approaches:
- Plan A: Direct tilemap/VRAM reading (preferred)
- Plan B: Glyph learning from framebuffer (NO OCR)

Deduplicates text by normalized hash.
================================================================================
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
import hashlib

from .emulator_runtime_host import EmulatorRuntimeHost, FrameBuffer


@dataclass
class RuntimeTextItem:
    """Text item captured at runtime."""
    id: str
    screen_id: str                    # Hash of screen where captured
    text: str                         # Decoded text
    tile_indices: List[int] = field(default_factory=list)
    tilemap_offset: int = 0
    frame_captured: int = 0
    confidence: float = 0.0
    method: str = "tilemap"           # tilemap or glyph_learning
    is_tokenized: bool = False
    raw_hash: str = ""                # For deduplication


class RuntimeTextHarvester:
    """
    Harvests text from running emulator.

    NO OCR - uses direct memory reading or glyph learning.
    """

    def __init__(self, host: EmulatorRuntimeHost,
                 char_table: Optional[Dict[int, str]] = None):
        """
        Initialize harvester.

        Args:
            host: Emulator runtime host
            char_table: Optional character table for decoding
        """
        self.host = host
        self.char_table = char_table or {}

        self._captured_texts: List[RuntimeTextItem] = []
        self._text_hashes: Set[str] = set()
        self._glyph_cache: Dict[str, str] = {}  # tile_hash -> character
        self._item_counter = 0

    def harvest_plan_a(self, screen_id: str) -> List[RuntimeTextItem]:
        """
        Plan A: Direct tilemap/VRAM reading.

        Reads tile indices from VRAM/nametable and decodes using char_table.
        """
        items = []

        # Get VRAM data
        vram = self.host.get_vram()
        if not vram:
            return items

        # Get RAM for tilemap data (console-specific)
        ram = self.host.get_ram()

        # Try to find text in tilemap regions
        # This is console-specific; here's a generic approach

        # Look for sequences of valid tile indices
        text_regions = self._find_text_regions(vram, ram)

        for region in text_regions:
            offset, indices = region

            # Decode using char table
            text, is_tokenized = self._decode_indices(indices)

            if text.strip():
                text_hash = self._compute_text_hash(text)

                if text_hash not in self._text_hashes:
                    self._text_hashes.add(text_hash)
                    self._item_counter += 1

                    item = RuntimeTextItem(
                        id=f"RT_{self._item_counter:05d}",
                        screen_id=screen_id,
                        text=text,
                        tile_indices=indices,
                        tilemap_offset=offset,
                        frame_captured=self.host.get_frame_count(),
                        confidence=0.8 if not is_tokenized else 0.5,
                        method="tilemap",
                        is_tokenized=is_tokenized,
                        raw_hash=text_hash,
                    )
                    items.append(item)
                    self._captured_texts.append(item)

        return items

    def harvest_plan_b(self, screen_id: str, frame: FrameBuffer) -> List[RuntimeTextItem]:
        """
        Plan B: Glyph learning from framebuffer.

        Learns character mappings from rendered tiles.
        """
        items = []

        if not frame or not frame.data:
            return items

        # Extract tile images from frame
        tile_size = 8  # Typical tile size
        tiles = self._extract_tiles_from_frame(frame, tile_size)

        # Build text from recognized tiles
        current_text = []
        current_indices = []
        current_offset = 0

        for i, (tile_hash, tile_data) in enumerate(tiles):
            if tile_hash in self._glyph_cache:
                char = self._glyph_cache[tile_hash]
                current_text.append(char)
                current_indices.append(i)
            elif self._is_likely_text_tile(tile_data):
                # Unknown tile that looks like text
                current_text.append(f"<GLYPH_{tile_hash[:4]}>")
                current_indices.append(i)

        text = ''.join(current_text)

        if text.strip() and len(text) >= 3:
            text_hash = self._compute_text_hash(text)

            if text_hash not in self._text_hashes:
                self._text_hashes.add(text_hash)
                self._item_counter += 1

                item = RuntimeTextItem(
                    id=f"RT_{self._item_counter:05d}",
                    screen_id=screen_id,
                    text=text,
                    tile_indices=current_indices,
                    tilemap_offset=0,
                    frame_captured=self.host.get_frame_count(),
                    confidence=0.4,
                    method="glyph_learning",
                    is_tokenized=True,
                    raw_hash=text_hash,
                )
                items.append(item)
                self._captured_texts.append(item)

        return items

    def _find_text_regions(self, vram: bytes, ram: bytes) -> List[Tuple[int, List[int]]]:
        """Find potential text regions in memory."""
        regions = []

        # Generic approach: look for sequences of likely text tile indices
        # Most text tiles are in the 0x00-0x7F range

        data = ram if len(ram) > len(vram) else vram

        i = 0
        while i < len(data) - 4:
            # Look for start of text sequence
            if self._is_likely_text_byte(data[i]):
                start = i
                indices = []

                while i < len(data) and len(indices) < 256:
                    b = data[i]

                    if b == 0x00:  # Null terminator
                        break
                    elif self._is_likely_text_byte(b) or b in self.char_table:
                        indices.append(b)
                        i += 1
                    else:
                        break

                if len(indices) >= 3:
                    regions.append((start, indices))

            i += 1

        return regions

    def _is_likely_text_byte(self, b: int) -> bool:
        """Check if byte is likely a text tile index."""
        # Common patterns for text
        if 0x20 <= b <= 0x7E:  # ASCII range
            return True
        if b in self.char_table:
            return True
        return False

    def _decode_indices(self, indices: List[int]) -> Tuple[str, bool]:
        """Decode tile indices to text."""
        text = []
        is_tokenized = False

        for idx in indices:
            if idx in self.char_table:
                text.append(self.char_table[idx])
            else:
                text.append(f"<TILE_{idx:02X}>")
                is_tokenized = True

        return ''.join(text), is_tokenized

    def _compute_text_hash(self, text: str) -> str:
        """Compute hash for text deduplication."""
        # Normalize text before hashing
        normalized = text.lower().strip()
        # Remove token placeholders for comparison
        normalized = ''.join(c for c in normalized if not c.startswith('<'))
        return hashlib.md5(normalized.encode()).hexdigest()[:12]

    def _extract_tiles_from_frame(self, frame: FrameBuffer,
                                   tile_size: int) -> List[Tuple[str, bytes]]:
        """Extract tile images from framebuffer."""
        tiles = []

        if not frame.data:
            return tiles

        bytes_per_pixel = 2  # Assuming RGB565
        row_bytes = frame.pitch

        tiles_x = frame.width // tile_size
        tiles_y = frame.height // tile_size

        for ty in range(tiles_y):
            for tx in range(tiles_x):
                tile_data = bytearray()

                for py in range(tile_size):
                    y = ty * tile_size + py
                    for px in range(tile_size):
                        x = tx * tile_size + px
                        offset = y * row_bytes + x * bytes_per_pixel

                        if offset + 1 < len(frame.data):
                            tile_data.extend(frame.data[offset:offset + 2])

                tile_hash = hashlib.md5(bytes(tile_data)).hexdigest()[:8]
                tiles.append((tile_hash, bytes(tile_data)))

        return tiles

    def _is_likely_text_tile(self, tile_data: bytes) -> bool:
        """Check if tile looks like text (not blank/solid)."""
        if not tile_data:
            return False

        unique = len(set(tile_data))
        return 2 <= unique <= 16  # Some structure but not noise

    def learn_glyph(self, tile_hash: str, character: str) -> None:
        """Learn a glyph mapping."""
        self._glyph_cache[tile_hash] = character

    def set_char_table(self, char_table: Dict[int, str]) -> None:
        """Update character table."""
        self.char_table = char_table

    def get_all_captured(self) -> List[RuntimeTextItem]:
        """Get all captured text items."""
        return self._captured_texts.copy()

    def get_unique_count(self) -> int:
        """Get count of unique texts captured."""
        return len(self._text_hashes)

    def clear(self) -> None:
        """Clear captured texts."""
        self._captured_texts.clear()
        self._text_hashes.clear()
        self._item_counter = 0
