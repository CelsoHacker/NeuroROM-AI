# -*- coding: utf-8 -*-
"""
================================================================================
SNES PLUGIN - Super Nintendo Entertainment System
================================================================================
Plugin for SNES/Super Famicom ROMs with:
- u24 LE pointers
- LoROM/HiROM detection and address mapping
- DTE (Dual Tile Encoding) support
- 2bpp/4bpp tile text extraction
================================================================================
"""

from typing import Any, Dict, List, Optional, Set, Tuple
import struct

from .base_plugin import (
    BaseConsolePlugin,
    ConsoleSpec,
    ConsoleType,
    PluginCapability,
    AddressMapping,
    ROMHeaderInfo,
    TextBank,
)


class SNESPlugin(BaseConsolePlugin):
    """
    SNES/Super Famicom plugin.

    Handles LoROM and HiROM address mapping with u24 pointers.
    """

    # ROM type detection offsets
    LOROM_HEADER = 0x7FC0
    HIROM_HEADER = 0xFFC0

    # Header field offsets (from header start)
    TITLE_OFFSET = 0x00
    TITLE_LENGTH = 21
    MAP_MODE_OFFSET = 0x15
    ROM_TYPE_OFFSET = 0x16
    ROM_SIZE_OFFSET = 0x17
    RAM_SIZE_OFFSET = 0x18
    REGION_OFFSET = 0x19
    DEVELOPER_OFFSET = 0x1A
    VERSION_OFFSET = 0x1B
    CHECKSUM_COMP_OFFSET = 0x1C
    CHECKSUM_OFFSET = 0x1E

    @property
    def console_spec(self) -> ConsoleSpec:
        return ConsoleSpec(
            name="Super Nintendo Entertainment System",
            console_type=ConsoleType.SNES,
            endianness="little",
            pointer_sizes=[2, 3],  # u16 and u24
            ram_size=131072,       # 128KB WRAM
            ram_start=0x7E0000,
            default_encodings=["ascii", "shift_jis"],
            address_mapper=None,   # Detected per-ROM
            has_banking=True,
            bank_size=0x8000,      # 32KB for LoROM
            compression_common=["LZSS", "LZ77", "RLE"],
            vram_size=65536,       # 64KB VRAM
            vram_start=0x0000,
            tile_bpp=[2, 4],

            # Thresholds
            min_text_len=3,
            language_score_threshold=0.70,
            pointer_run_min=8,
            pointer_resolve_ratio=0.60,
            text_score_min=0.60,
        )

    @property
    def capabilities(self) -> Set[PluginCapability]:
        return {
            PluginCapability.POINTER_HUNTING,
            PluginCapability.COMPRESSION,
            PluginCapability.TILE_TEXT,
            PluginCapability.SCRIPT_OPCODE,
        }

    def detect_rom(self, rom_data: bytes) -> bool:
        """Detect if this is a SNES ROM."""
        if len(rom_data) < 0x8000:
            return False

        # Check for valid header at LoROM or HiROM location
        lorom_score = self._score_header(rom_data, self.LOROM_HEADER)
        hirom_score = self._score_header(rom_data, self.HIROM_HEADER)

        # Also check with 512-byte copier header
        if len(rom_data) >= 0x8200:
            lorom_score_h = self._score_header(rom_data, self.LOROM_HEADER + 512)
            hirom_score_h = self._score_header(rom_data, self.HIROM_HEADER + 512)
            lorom_score = max(lorom_score, lorom_score_h)
            hirom_score = max(hirom_score, hirom_score_h)

        return max(lorom_score, hirom_score) >= 5

    def _score_header(self, rom_data: bytes, offset: int) -> int:
        """Score header validity (higher = more likely valid)."""
        if offset + 32 > len(rom_data):
            return 0

        score = 0

        # Check checksum complement
        try:
            checksum = self.read_u16(rom_data, offset + self.CHECKSUM_OFFSET)
            complement = self.read_u16(rom_data, offset + self.CHECKSUM_COMP_OFFSET)
            if checksum is not None and complement is not None:
                if checksum ^ complement == 0xFFFF:
                    score += 4
        except:
            pass

        # Check map mode byte
        map_mode = rom_data[offset + self.MAP_MODE_OFFSET]
        if map_mode in (0x20, 0x21, 0x23, 0x25, 0x30, 0x31, 0x32, 0x35):
            score += 2

        # Check ROM size
        rom_size = rom_data[offset + self.ROM_SIZE_OFFSET]
        if 0x08 <= rom_size <= 0x0D:  # 256KB to 8MB
            score += 1

        # Check RAM size
        ram_size = rom_data[offset + self.RAM_SIZE_OFFSET]
        if ram_size <= 0x08:  # Up to 256KB
            score += 1

        # Check region code
        region = rom_data[offset + self.REGION_OFFSET]
        if region <= 0x0F:
            score += 1

        # Check title for printable ASCII
        title = rom_data[offset:offset + self.TITLE_LENGTH]
        printable = sum(1 for b in title if 0x20 <= b <= 0x7E)
        if printable >= 10:
            score += 2

        return score

    def _has_copier_header(self, rom_data: bytes) -> bool:
        """Check if ROM has 512-byte copier header."""
        if len(rom_data) < 0x8200:
            return False

        # Score both with and without header
        score_without = max(
            self._score_header(rom_data, self.LOROM_HEADER),
            self._score_header(rom_data, self.HIROM_HEADER)
        )
        score_with = max(
            self._score_header(rom_data, self.LOROM_HEADER + 512),
            self._score_header(rom_data, self.HIROM_HEADER + 512)
        )

        return score_with > score_without

    def _get_header_offset(self, rom_data: bytes) -> int:
        """Get the actual header offset."""
        base = 512 if self._has_copier_header(rom_data) else 0

        lorom_score = self._score_header(rom_data, self.LOROM_HEADER + base)
        hirom_score = self._score_header(rom_data, self.HIROM_HEADER + base)

        if hirom_score > lorom_score:
            return self.HIROM_HEADER + base
        return self.LOROM_HEADER + base

    def _detect_rom_type(self, rom_data: bytes) -> str:
        """Detect LoROM vs HiROM."""
        base = 512 if self._has_copier_header(rom_data) else 0

        lorom_score = self._score_header(rom_data, self.LOROM_HEADER + base)
        hirom_score = self._score_header(rom_data, self.HIROM_HEADER + base)

        return "hirom" if hirom_score > lorom_score else "lorom"

    def get_rom_header_info(self, rom_data: bytes) -> ROMHeaderInfo:
        """Parse SNES ROM header."""
        header_offset = self._get_header_offset(rom_data)
        rom_type = self._detect_rom_type(rom_data)

        title_bytes = rom_data[header_offset:header_offset + self.TITLE_LENGTH]
        title = title_bytes.decode('ascii', errors='replace').strip()

        map_mode = rom_data[header_offset + self.MAP_MODE_OFFSET]
        rom_size_code = rom_data[header_offset + self.ROM_SIZE_OFFSET]
        ram_size_code = rom_data[header_offset + self.RAM_SIZE_OFFSET]
        region = rom_data[header_offset + self.REGION_OFFSET]
        version = rom_data[header_offset + self.VERSION_OFFSET]
        checksum = self.read_u16(rom_data, header_offset + self.CHECKSUM_OFFSET) or 0

        return ROMHeaderInfo(
            title=title,
            region=self._region_name(region),
            version=version,
            checksum=checksum,
            rom_size=1024 << rom_size_code if rom_size_code < 16 else 0,
            ram_size=1024 << ram_size_code if ram_size_code > 0 else 0,
            mapper=map_mode,
            has_battery=bool(rom_data[header_offset + self.ROM_TYPE_OFFSET] & 0x02),
            extra={
                'rom_type': rom_type,
                'has_copier_header': self._has_copier_header(rom_data),
                'header_offset': header_offset,
            }
        )

    def _region_name(self, code: int) -> str:
        """Convert region code to name."""
        regions = {
            0x00: "Japan",
            0x01: "USA",
            0x02: "Europe",
            0x03: "Sweden",
            0x04: "Finland",
            0x05: "Denmark",
            0x06: "France",
            0x07: "Netherlands",
            0x08: "Spain",
            0x09: "Germany",
            0x0A: "Italy",
            0x0B: "China",
            0x0C: "Indonesia",
            0x0D: "South Korea",
        }
        return regions.get(code, f"Unknown ({code:02X})")

    def get_text_banks(self, rom_data: bytes) -> List[TextBank]:
        """Find text-likely regions in SNES ROM."""
        banks = []
        base = 512 if self._has_copier_header(rom_data) else 0
        rom_type = self._detect_rom_type(rom_data)

        if rom_type == "lorom":
            bank_size = 0x8000  # 32KB
        else:
            bank_size = 0x10000  # 64KB

        # Scan each bank
        num_banks = (len(rom_data) - base) // bank_size

        for bank_num in range(num_banks):
            bank_start = base + (bank_num * bank_size)
            bank_end = bank_start + bank_size

            if bank_end > len(rom_data):
                break

            bank_data = rom_data[bank_start:bank_end]
            score = self.calculate_text_score(bank_data)

            if score >= 0.3:  # Reasonable text likelihood
                banks.append(TextBank(
                    start=bank_start,
                    end=bank_end,
                    score=score,
                    bank_number=bank_num,
                    method="heuristic",
                ))

        return sorted(banks, key=lambda b: b.score, reverse=True)

    def map_address(self, snes_addr: int, rom_data: bytes) -> AddressMapping:
        """
        Map SNES address to file offset.

        LoROM:
            Banks $00-$7D, $80-$FF: offset = (bank * 0x8000) + (addr & 0x7FFF)
            Only upper half of each bank ($8000-$FFFF) maps to ROM

        HiROM:
            Banks $C0-$FF: offset = ((bank - 0xC0) * 0x10000) + addr
            Banks $40-$7D: mirror of $C0-$FD
        """
        rom_type = self._detect_rom_type(rom_data)
        base = 512 if self._has_copier_header(rom_data) else 0

        bank = (snes_addr >> 16) & 0xFF
        addr = snes_addr & 0xFFFF

        if rom_type == "lorom":
            # LoROM mapping
            if bank >= 0x80:
                bank -= 0x80

            if addr < 0x8000:
                # Lower half is usually RAM/registers
                return AddressMapping(
                    file_offset=-1,
                    bank=bank,
                    is_ram=True,
                    is_valid=False,
                    mapping_type="lorom"
                )

            file_offset = base + (bank * 0x8000) + (addr - 0x8000)

        else:  # HiROM
            if bank >= 0xC0:
                bank -= 0xC0
            elif bank >= 0x40:
                bank -= 0x40
            else:
                bank = bank & 0x3F

            file_offset = base + (bank * 0x10000) + addr

        # Validate offset
        if file_offset < 0 or file_offset >= len(rom_data):
            return AddressMapping(
                file_offset=file_offset,
                bank=bank,
                is_valid=False,
                mapping_type=rom_type
            )

        return AddressMapping(
            file_offset=file_offset,
            bank=bank,
            is_valid=True,
            mapping_type=rom_type
        )

    def map_offset_to_address(self, file_offset: int, rom_data: bytes) -> int:
        """Map file offset to SNES address."""
        rom_type = self._detect_rom_type(rom_data)
        base = 512 if self._has_copier_header(rom_data) else 0

        offset = file_offset - base

        if rom_type == "lorom":
            bank = offset // 0x8000
            addr = 0x8000 + (offset % 0x8000)
            return (bank << 16) | addr

        else:  # HiROM
            bank = 0xC0 + (offset // 0x10000)
            addr = offset % 0x10000
            return (bank << 16) | addr

    def get_pointer_config(self) -> Dict[str, Any]:
        """Get SNES-specific pointer configuration."""
        return {
            "sizes": [2, 3],  # u16 and u24
            "endianness": ["little"],
            "min_run": 8,
            "resolve_ratio": 0.60,
            "text_score_min": 0.60,
            "use_address_mapping": True,
        }

    def get_compression_config(self) -> Dict[str, Any]:
        """Get SNES-specific compression configuration."""
        return {
            "algorithms": ["LZSS", "LZ77", "RLE"],
            "aggressive": False,
        }

    def validate_pointer_target(self, target_offset: int, rom_data: bytes) -> Tuple[bool, float]:
        """Validate SNES pointer target."""
        base = 512 if self._has_copier_header(rom_data) else 0

        if target_offset < base or target_offset >= len(rom_data):
            return False, 0.0

        # Check for text
        sample = rom_data[target_offset:target_offset + 64]
        if not sample:
            return False, 0.0

        score = self.calculate_text_score(sample)
        return score >= 0.5, score

    def detect_dte(self, rom_data: bytes) -> Optional[Dict[int, str]]:
        """
        Detect DTE (Dual Tile Encoding) tables.

        DTE uses single bytes to represent common character pairs.
        """
        # Common DTE indicators: high bytes (0x80+) that decode to char pairs
        # This is heuristic-based; real detection needs context

        # Look for DTE table patterns
        # Usually a block of paired ASCII characters
        dte_table = {}

        for offset in range(0, len(rom_data) - 512, 256):
            candidate = rom_data[offset:offset + 512]

            # Check if it looks like paired ASCII
            pairs = 0
            for i in range(0, 512, 2):
                c1, c2 = candidate[i], candidate[i + 1]
                if 0x20 <= c1 <= 0x7E and 0x20 <= c2 <= 0x7E:
                    pairs += 1

            if pairs >= 100:  # At least 100 valid pairs
                for i in range(0, min(256, pairs) * 2, 2):
                    dte_byte = 0x80 + (i // 2)
                    char1 = chr(candidate[i])
                    char2 = chr(candidate[i + 1])
                    dte_table[dte_byte] = char1 + char2

                return dte_table

        return None
