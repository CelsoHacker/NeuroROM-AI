# -*- coding: utf-8 -*-
"""
================================================================================
TILE TEXT ENGINE - Tile-to-Text Conversion for Retro Consoles
================================================================================
Extracts text from tile-based graphics systems used in retro consoles.
Supports 1bpp (NES), 2bpp (SNES/GB), 4bpp (SNES/MD), 8bpp (PS1/GBA).

Integrates with AutoCharTableSolver for automatic character mapping.
================================================================================
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
import hashlib


class TileFormat(Enum):
    """Tile bit depth formats."""
    BPP1 = 1   # 1 bit per pixel (NES basic, Game Boy basic)
    BPP2 = 2   # 2 bits per pixel (SNES 4-color, Game Boy Color)
    BPP4 = 4   # 4 bits per pixel (SNES 16-color, Mega Drive)
    BPP8 = 8   # 8 bits per pixel (PS1, GBA)


@dataclass
class TileInfo:
    """Information about a detected tile."""
    offset: int
    index: int
    format: TileFormat
    width: int = 8
    height: int = 8
    data: bytes = field(default_factory=bytes)
    hash: str = ""  # For deduplication
    is_font_tile: bool = False
    estimated_char: str = ""
    confidence: float = 0.0


@dataclass
class FontRegion:
    """A detected font region in ROM."""
    start_offset: int
    end_offset: int
    tile_format: TileFormat
    tile_count: int
    tile_width: int = 8
    tile_height: int = 8
    confidence: float = 0.0
    char_table: Dict[int, str] = field(default_factory=dict)
    notes: str = ""


@dataclass
class TileTextResult:
    """Result of tile text extraction."""
    offset: int
    tile_indices: List[int]
    decoded_text: str
    raw_indices_hex: str
    confidence: float = 0.0
    is_tokenized: bool = False
    method: str = "tile_stream"


class TileTextEngine:
    """
    Engine for converting tile-based graphics to text.

    Handles tile decoding, font detection, and character mapping
    across different console tile formats.
    """

    def __init__(self, rom_data: bytes, default_format: TileFormat = TileFormat.BPP2):
        self.rom_data = rom_data
        self.default_format = default_format
        self._tile_cache: Dict[Tuple[int, TileFormat], TileInfo] = {}
        self._font_regions: List[FontRegion] = []

    @property
    def tile_size(self) -> Dict[TileFormat, int]:
        """Get tile size in bytes for each format."""
        return {
            TileFormat.BPP1: 8,    # 8x8 * 1bpp = 8 bytes
            TileFormat.BPP2: 16,   # 8x8 * 2bpp = 16 bytes (planar)
            TileFormat.BPP4: 32,   # 8x8 * 4bpp = 32 bytes (planar)
            TileFormat.BPP8: 64,   # 8x8 * 8bpp = 64 bytes
        }

    def decode_tile(self, offset: int, format: TileFormat = None) -> Optional[TileInfo]:
        """
        Decode a single tile from ROM.

        Args:
            offset: Offset in ROM
            format: Tile format (default: self.default_format)

        Returns:
            TileInfo or None if invalid
        """
        fmt = format or self.default_format
        size = self.tile_size[fmt]

        if offset < 0 or offset + size > len(self.rom_data):
            return None

        cache_key = (offset, fmt)
        if cache_key in self._tile_cache:
            return self._tile_cache[cache_key]

        tile_data = self.rom_data[offset:offset + size]

        # Compute hash for deduplication
        tile_hash = hashlib.md5(tile_data).hexdigest()[:8]

        # Check if likely font tile
        is_font = self._is_font_tile(tile_data, fmt)

        tile = TileInfo(
            offset=offset,
            index=offset // size,
            format=fmt,
            data=tile_data,
            hash=tile_hash,
            is_font_tile=is_font,
        )

        self._tile_cache[cache_key] = tile
        return tile

    def _is_font_tile(self, tile_data: bytes, format: TileFormat) -> bool:
        """
        Heuristic to check if tile looks like a font glyph.

        Font tiles typically have:
        - Not too many unique pixels (limited colors)
        - Some structure (not random noise)
        - Not blank or solid
        """
        if all(b == 0 for b in tile_data):
            return False  # Blank
        if all(b == 0xFF for b in tile_data):
            return False  # Solid

        # Count unique bytes (simple measure of complexity)
        unique = len(set(tile_data))

        # Font tiles typically have 2-6 unique byte patterns
        return 2 <= unique <= 8

    def scan_for_fonts(self, format: TileFormat = None,
                       min_tiles: int = 32,
                       max_tiles: int = 256,
                       min_font_ratio: float = 0.5) -> List[FontRegion]:
        """
        Scan ROM for font regions.

        Args:
            format: Tile format to scan for
            min_tiles: Minimum tiles in a font region
            max_tiles: Maximum tiles to check per region
            min_font_ratio: Minimum ratio of font-like tiles

        Returns:
            List of FontRegion sorted by confidence
        """
        fmt = format or self.default_format
        size = self.tile_size[fmt]
        regions = []

        # Scan in chunks
        offset = 0
        while offset + (min_tiles * size) <= len(self.rom_data):
            font_count = 0
            tiles = []

            for i in range(max_tiles):
                tile_offset = offset + (i * size)
                if tile_offset + size > len(self.rom_data):
                    break

                tile = self.decode_tile(tile_offset, fmt)
                if tile:
                    tiles.append(tile)
                    if tile.is_font_tile:
                        font_count += 1

            if len(tiles) >= min_tiles:
                font_ratio = font_count / len(tiles)

                if font_ratio >= min_font_ratio:
                    region = FontRegion(
                        start_offset=offset,
                        end_offset=offset + (len(tiles) * size),
                        tile_format=fmt,
                        tile_count=len(tiles),
                        confidence=font_ratio,
                    )
                    regions.append(region)
                    offset = region.end_offset
                    continue

            offset += size * 8  # Skip ahead

        regions.sort(key=lambda r: r.confidence, reverse=True)
        return regions

    def extract_tile_stream(self, offset: int,
                            char_table: Dict[int, str],
                            terminator: int = 0x00,
                            max_length: int = 256) -> TileTextResult:
        """
        Extract text from a tile index stream.

        Args:
            offset: Start offset of tile index stream
            char_table: Mapping of tile index to character
            terminator: Terminator byte value
            max_length: Maximum stream length

        Returns:
            TileTextResult with decoded text
        """
        indices = []
        text = []
        is_tokenized = False
        pos = offset

        while pos < min(offset + max_length, len(self.rom_data)):
            idx = self.rom_data[pos]

            if idx == terminator:
                break

            indices.append(idx)

            if idx in char_table:
                text.append(char_table[idx])
            else:
                # Tokenize unknown tiles
                text.append(f"<TILE_{idx:02X}>")
                is_tokenized = True

            pos += 1

        decoded = ''.join(text)
        raw_hex = ' '.join(f'{i:02X}' for i in indices)

        # Calculate confidence
        known_count = sum(1 for i in indices if i in char_table)
        confidence = known_count / len(indices) if indices else 0.0

        return TileTextResult(
            offset=offset,
            tile_indices=indices,
            decoded_text=decoded,
            raw_indices_hex=raw_hex,
            confidence=confidence,
            is_tokenized=is_tokenized,
        )

    def extract_tilemap_region(self, tilemap_offset: int,
                               width: int, height: int,
                               char_table: Dict[int, str],
                               terminator: int = 0x00) -> List[TileTextResult]:
        """
        Extract text from a 2D tilemap region.

        Args:
            tilemap_offset: Start of tilemap data
            width: Tilemap width in tiles
            height: Tilemap height in tiles
            char_table: Character mapping
            terminator: Line terminator

        Returns:
            List of TileTextResult, one per row
        """
        results = []

        for row in range(height):
            row_offset = tilemap_offset + (row * width)
            result = self.extract_tile_stream(
                row_offset, char_table, terminator, width
            )
            if result.decoded_text.strip():
                results.append(result)

        return results

    def build_default_ascii_table(self, base_tile: int = 0x00) -> Dict[int, str]:
        """
        Build a default ASCII character table.

        Many games use sequential tile indices for ASCII.

        Args:
            base_tile: Tile index for first printable char (space)

        Returns:
            Mapping of tile index to ASCII character
        """
        table = {}

        # Space through tilde (0x20 - 0x7E)
        for i, char_code in enumerate(range(0x20, 0x7F)):
            table[base_tile + i] = chr(char_code)

        return table

    def build_uppercase_table(self, base_tile: int = 0x00) -> Dict[int, str]:
        """
        Build uppercase-only table (common in older games).

        Args:
            base_tile: Tile index for 'A'

        Returns:
            Mapping of tile index to character
        """
        table = {}

        # A-Z
        for i in range(26):
            table[base_tile + i] = chr(ord('A') + i)

        # Common extras
        if base_tile > 0:
            table[base_tile - 1] = ' '  # Space before letters
        table[base_tile + 26] = '!'
        table[base_tile + 27] = '?'
        table[base_tile + 28] = '.'
        table[base_tile + 29] = ','
        table[base_tile + 30] = '-'

        return table

    def infer_space_tile(self, sample_data: bytes,
                          candidate_tiles: Set[int] = None) -> Optional[int]:
        """
        Infer which tile index represents space.

        Space is typically the most common tile in text.

        Args:
            sample_data: Sample of tile index data
            candidate_tiles: Optional set of valid tile indices

        Returns:
            Likely space tile index or None
        """
        from collections import Counter

        # Count occurrences
        counter = Counter(sample_data)

        # Space should be common but not the terminator (often 0x00)
        for tile_idx, count in counter.most_common(10):
            if tile_idx == 0x00:
                continue  # Skip likely terminator
            if candidate_tiles and tile_idx not in candidate_tiles:
                continue
            # Space should be at least 5% of text
            if count / len(sample_data) >= 0.05:
                return tile_idx

        return None

    def infer_newline_tile(self, sample_data: bytes,
                            line_width: int = 32) -> Optional[int]:
        """
        Infer which tile index represents newline.

        Args:
            sample_data: Sample of tile index data
            line_width: Expected line width

        Returns:
            Likely newline tile index or None
        """
        from collections import Counter

        # Newlines often appear at regular intervals
        candidates = Counter()

        for i in range(line_width, len(sample_data), line_width):
            if i < len(sample_data):
                candidates[sample_data[i]] += 1

        if candidates:
            most_common = candidates.most_common(1)[0]
            if most_common[1] >= 3:  # At least 3 occurrences
                return most_common[0]

        return None

    def estimate_line_width(self, tilemap_data: bytes,
                             space_tile: Optional[int] = None) -> int:
        """
        Estimate line width from tilemap data.

        Args:
            tilemap_data: Tilemap data to analyze
            space_tile: Known space tile (optional)

        Returns:
            Estimated line width (common values: 20, 24, 28, 32)
        """
        common_widths = [20, 24, 28, 30, 32, 40]

        if space_tile is not None:
            # Look for repeating patterns of space
            for width in common_widths:
                matches = 0
                for i in range(width, len(tilemap_data), width):
                    if tilemap_data[i - 1] == space_tile:
                        matches += 1
                if matches >= 3:
                    return width

        # Default to 32 (common SNES/NES value)
        return 32

    def get_tile_visual_hash(self, tile: TileInfo) -> str:
        """
        Get a visual hash for tile comparison.

        Useful for matching tiles with different indices but same appearance.
        """
        return tile.hash

    def find_similar_tiles(self, reference: TileInfo,
                            threshold: float = 0.9) -> List[TileInfo]:
        """
        Find tiles visually similar to reference.

        Args:
            reference: Reference tile
            threshold: Similarity threshold (0-1)

        Returns:
            List of similar tiles from cache
        """
        similar = []
        ref_hash = reference.hash

        for tile in self._tile_cache.values():
            if tile.hash == ref_hash:
                similar.append(tile)

        return similar
