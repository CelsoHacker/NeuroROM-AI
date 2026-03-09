# -*- coding: utf-8 -*-
"""
================================================================================
BASE PLUGIN - Abstract Base Class for Console Plugins
================================================================================
Defines the contract that all console plugins must implement.
Provides console specifications and common utilities.
================================================================================
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import struct


class ConsoleType(Enum):
    """Supported console types."""
    NES = "nes"
    SMS = "sms"
    MD = "md"
    SNES = "snes"
    GBA = "gba"
    N64 = "n64"
    PS1 = "ps1"


class PluginCapability(Enum):
    """Plugin capabilities."""
    POINTER_HUNTING = auto()
    COMPRESSION = auto()
    TILE_TEXT = auto()
    SCRIPT_OPCODE = auto()
    CONTAINER_EXTRACT = auto()
    RUNTIME_CAPTURE = auto()


@dataclass
class ConsoleSpec:
    """
    Console-specific specifications.
    Defines hardware characteristics that affect text extraction.
    """
    name: str
    console_type: ConsoleType
    endianness: str  # "little" or "big"
    pointer_sizes: List[int]  # e.g., [2, 3] for SNES (u16, u24)
    ram_size: int
    ram_start: int
    default_encodings: List[str]
    address_mapper: Optional[str] = None  # e.g., "lorom", "hirom", "linear"
    has_banking: bool = False
    bank_size: int = 0
    compression_common: List[str] = field(default_factory=list)
    vram_size: int = 0
    vram_start: int = 0
    tile_bpp: List[int] = field(default_factory=lambda: [2])  # bits per pixel

    # Thresholds for validation
    min_text_len: int = 3
    language_score_threshold: float = 0.70
    pointer_run_min: int = 8
    pointer_resolve_ratio: float = 0.60
    text_score_min: float = 0.60


@dataclass
class AddressMapping:
    """Result of address mapping operation."""
    file_offset: int
    bank: Optional[int] = None
    is_ram: bool = False
    is_valid: bool = True
    mapping_type: str = "direct"


@dataclass
class ROMHeaderInfo:
    """Parsed ROM header information."""
    title: str = ""
    region: str = ""
    version: int = 0
    checksum: int = 0
    rom_size: int = 0
    ram_size: int = 0
    mapper: int = 0
    has_battery: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TextBank:
    """Represents a text-likely region in ROM."""
    start: int
    end: int
    score: float = 0.0
    bank_number: Optional[int] = None
    method: str = "heuristic"
    notes: str = ""


class BaseConsolePlugin(ABC):
    """
    Abstract base class for all console plugins.

    Each plugin must implement console-specific logic for:
    - ROM detection
    - Address mapping
    - Text region identification
    - Pointer configuration
    """

    def __init__(self):
        self._rom_data: Optional[bytes] = None
        self._header_info: Optional[ROMHeaderInfo] = None
        self._cached_mapping_type: Optional[str] = None

    @property
    @abstractmethod
    def console_spec(self) -> ConsoleSpec:
        """Return console specifications."""
        pass

    @property
    def capabilities(self) -> Set[PluginCapability]:
        """Return plugin capabilities. Override to customize."""
        return {
            PluginCapability.POINTER_HUNTING,
            PluginCapability.TILE_TEXT,
        }

    def set_rom_data(self, rom_data: bytes) -> None:
        """Set ROM data for analysis."""
        self._rom_data = rom_data
        self._header_info = None
        self._cached_mapping_type = None

    @abstractmethod
    def detect_rom(self, rom_data: bytes) -> bool:
        """
        Returns True if ROM matches this console.

        Args:
            rom_data: Raw ROM bytes

        Returns:
            True if this plugin can handle the ROM
        """
        pass

    @abstractmethod
    def get_rom_header_info(self, rom_data: bytes) -> ROMHeaderInfo:
        """
        Parse and return ROM header information.

        Args:
            rom_data: Raw ROM bytes

        Returns:
            Parsed header information
        """
        pass

    @abstractmethod
    def get_text_banks(self, rom_data: bytes) -> List[TextBank]:
        """
        Return list of text-likely regions in ROM.

        Args:
            rom_data: Raw ROM bytes

        Returns:
            List of TextBank objects ordered by likelihood score
        """
        pass

    @abstractmethod
    def map_address(self, rom_addr: int, rom_data: bytes) -> AddressMapping:
        """
        Map ROM/CPU address to file offset.

        Args:
            rom_addr: Address as seen by CPU
            rom_data: Raw ROM bytes

        Returns:
            AddressMapping with file offset and metadata
        """
        pass

    @abstractmethod
    def map_offset_to_address(self, file_offset: int, rom_data: bytes) -> int:
        """
        Map file offset to ROM/CPU address (for pointer generation).

        Args:
            file_offset: Offset in ROM file
            rom_data: Raw ROM bytes

        Returns:
            CPU address that would point to this offset
        """
        pass

    # =========================================================================
    # Optional overrides with sensible defaults
    # =========================================================================

    def get_pointer_config(self) -> Dict[str, Any]:
        """
        Return pointer scanning configuration.
        Override for console-specific settings.
        """
        return {
            "sizes": self.console_spec.pointer_sizes,
            "endianness": [self.console_spec.endianness],
            "min_run": self.console_spec.pointer_run_min,
            "resolve_ratio": self.console_spec.pointer_resolve_ratio,
            "text_score_min": self.console_spec.text_score_min,
        }

    def get_compression_config(self) -> Dict[str, Any]:
        """
        Return compression detection configuration.
        Override for console-specific algorithms.
        """
        return {
            "algorithms": self.console_spec.compression_common,
            "aggressive": False,
        }

    def get_tile_config(self) -> Dict[str, Any]:
        """
        Return tile text configuration.
        Override for console-specific tile formats.
        """
        return {
            "bpp_modes": self.console_spec.tile_bpp,
            "tile_width": 8,
            "tile_height": 8,
        }

    def get_encoding_priority(self) -> List[str]:
        """
        Return encoding detection priority.
        Override to customize (e.g., PS1 prioritizes Shift-JIS).
        """
        return self.console_spec.default_encodings

    def should_use_runtime_mode(self) -> bool:
        """
        Return True if runtime mode should be used by default.
        N64 and PS1 return True due to complex text storage.
        """
        return False

    def post_extract_hook(self, items: List[Any]) -> List[Any]:
        """
        Optional post-processing hook for extracted items.
        Override to apply console-specific filtering/transformation.

        Args:
            items: List of TextItem objects

        Returns:
            Processed list of TextItem objects
        """
        return items

    def validate_pointer_target(self, target_offset: int, rom_data: bytes) -> Tuple[bool, float]:
        """
        Validate if a pointer target looks like text.
        Override for console-specific validation.

        Args:
            target_offset: File offset being pointed to
            rom_data: Raw ROM bytes

        Returns:
            Tuple of (is_valid, confidence)
        """
        if target_offset < 0 or target_offset >= len(rom_data):
            return False, 0.0

        # Check for printable ASCII sequence
        sample = rom_data[target_offset:target_offset + 32]
        if not sample:
            return False, 0.0

        printable = sum(1 for b in sample if 0x20 <= b <= 0x7E or b in (0x00, 0x0A, 0x0D))
        ratio = printable / len(sample)

        return ratio >= 0.5, ratio

    # =========================================================================
    # Utility methods
    # =========================================================================

    def read_u16(self, data: bytes, offset: int, big_endian: bool = None) -> Optional[int]:
        """Read 16-bit value with console endianness."""
        if offset < 0 or offset + 2 > len(data):
            return None
        be = big_endian if big_endian is not None else (self.console_spec.endianness == "big")
        fmt = '>H' if be else '<H'
        return struct.unpack_from(fmt, data, offset)[0]

    def read_u24(self, data: bytes, offset: int, big_endian: bool = None) -> Optional[int]:
        """Read 24-bit value with console endianness."""
        if offset < 0 or offset + 3 > len(data):
            return None
        be = big_endian if big_endian is not None else (self.console_spec.endianness == "big")
        if be:
            return (data[offset] << 16) | (data[offset + 1] << 8) | data[offset + 2]
        else:
            return data[offset] | (data[offset + 1] << 8) | (data[offset + 2] << 16)

    def read_u32(self, data: bytes, offset: int, big_endian: bool = None) -> Optional[int]:
        """Read 32-bit value with console endianness."""
        if offset < 0 or offset + 4 > len(data):
            return None
        be = big_endian if big_endian is not None else (self.console_spec.endianness == "big")
        fmt = '>I' if be else '<I'
        return struct.unpack_from(fmt, data, offset)[0]

    def write_u16(self, value: int, big_endian: bool = None) -> bytes:
        """Write 16-bit value with console endianness."""
        be = big_endian if big_endian is not None else (self.console_spec.endianness == "big")
        fmt = '>H' if be else '<H'
        return struct.pack(fmt, value & 0xFFFF)

    def write_u24(self, value: int, big_endian: bool = None) -> bytes:
        """Write 24-bit value with console endianness."""
        be = big_endian if big_endian is not None else (self.console_spec.endianness == "big")
        value = value & 0xFFFFFF
        if be:
            return bytes([(value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF])
        else:
            return bytes([value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF])

    def write_u32(self, value: int, big_endian: bool = None) -> bytes:
        """Write 32-bit value with console endianness."""
        be = big_endian if big_endian is not None else (self.console_spec.endianness == "big")
        fmt = '>I' if be else '<I'
        return struct.pack(fmt, value & 0xFFFFFFFF)

    def calculate_text_score(self, data: bytes) -> float:
        """
        Calculate text likelihood score for a byte sequence.

        Returns:
            Score between 0.0 (not text) and 1.0 (definitely text)
        """
        if not data:
            return 0.0

        # Count character categories
        printable = 0
        letters = 0
        spaces = 0
        terminators = 0
        control = 0

        for b in data:
            if b == 0x00:
                terminators += 1
            elif b == 0x20:
                spaces += 1
                printable += 1
            elif 0x41 <= b <= 0x5A or 0x61 <= b <= 0x7A:  # A-Z, a-z
                letters += 1
                printable += 1
            elif 0x20 <= b <= 0x7E:
                printable += 1
            elif b < 0x20:
                control += 1

        n = len(data)

        # Calculate component scores
        printable_ratio = printable / n
        letter_ratio = letters / n if n > 0 else 0
        space_ratio = spaces / n if n > 0 else 0

        # Good text has:
        # - High printable ratio
        # - Reasonable letter ratio
        # - Some spaces (for prose)
        # - Not too many control chars

        score = 0.0
        score += printable_ratio * 0.4
        score += min(letter_ratio * 2, 0.3)  # Cap at 0.3
        score += min(space_ratio * 5, 0.2) if space_ratio < 0.25 else 0.1
        score += 0.1 if terminators > 0 else 0.0

        # Penalty for excessive control characters
        if control / n > 0.1:
            score *= 0.5

        return min(1.0, max(0.0, score))

    def detect_text_regions_heuristic(self, rom_data: bytes,
                                       block_size: int = 4096,
                                       min_score: float = 0.5) -> List[TextBank]:
        """
        Detect text regions using heuristic scoring.

        Args:
            rom_data: Raw ROM bytes
            block_size: Size of blocks to analyze
            min_score: Minimum score to consider as text

        Returns:
            List of TextBank objects
        """
        regions = []

        for offset in range(0, len(rom_data), block_size):
            block = rom_data[offset:offset + block_size]
            score = self.calculate_text_score(block)

            if score >= min_score:
                regions.append(TextBank(
                    start=offset,
                    end=min(offset + block_size, len(rom_data)),
                    score=score,
                    method="heuristic"
                ))

        # Merge adjacent regions
        merged = []
        for region in sorted(regions, key=lambda r: r.start):
            if merged and region.start <= merged[-1].end:
                # Merge
                merged[-1].end = max(merged[-1].end, region.end)
                merged[-1].score = max(merged[-1].score, region.score)
            else:
                merged.append(region)

        return sorted(merged, key=lambda r: r.score, reverse=True)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} console={self.console_spec.console_type.value}>"
