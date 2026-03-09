# -*- coding: utf-8 -*-
"""
================================================================================
MD PLUGIN - Sega Mega Drive / Genesis
================================================================================
Plugin for Mega Drive / Genesis ROMs with:
- BIG ENDIAN pointer hunting (M68000)
- u16/u32 BE pointers
- 4bpp tile text extraction
================================================================================
"""

from typing import Any, Dict, List, Optional, Set, Tuple

from .base_plugin import (
    BaseConsolePlugin,
    ConsoleSpec,
    ConsoleType,
    PluginCapability,
    AddressMapping,
    ROMHeaderInfo,
    TextBank,
)


class MDPlugin(BaseConsolePlugin):
    """
    Sega Mega Drive / Genesis plugin.

    Uses BIG ENDIAN byte order for the M68000 processor.
    """

    HEADER_OFFSET = 0x100  # Header starts at $000100

    @property
    def console_spec(self) -> ConsoleSpec:
        return ConsoleSpec(
            name="Sega Mega Drive / Genesis",
            console_type=ConsoleType.MD,
            endianness="big",     # M68000 is big-endian!
            pointer_sizes=[2, 4], # u16 and u32
            ram_size=65536,       # 64KB main RAM
            ram_start=0xFF0000,
            default_encodings=["ascii", "shift_jis"],
            address_mapper="linear",
            has_banking=False,    # Linear addressing (up to 4MB)
            bank_size=0,
            compression_common=["LZSS", "RLE", "Huffman"],
            vram_size=65536,      # 64KB VRAM
            vram_start=0x0000,
            tile_bpp=[4],         # MD uses 4bpp tiles

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
        """Detect if this is a Mega Drive ROM."""
        if len(rom_data) < 0x200:
            return False

        # Check for SEGA string in header
        header_area = rom_data[self.HEADER_OFFSET:self.HEADER_OFFSET + 16]
        if b'SEGA' in header_area:
            return True

        # Check for valid vector table (M68K vectors are big-endian)
        if len(rom_data) >= 8:
            # Initial SP should be in RAM range
            sp = int.from_bytes(rom_data[0:4], 'big')
            # Initial PC should be in ROM range
            pc = int.from_bytes(rom_data[4:8], 'big')

            if 0xFF0000 <= sp <= 0xFFFFFF and pc < len(rom_data):
                return True

        return False

    def get_rom_header_info(self, rom_data: bytes) -> ROMHeaderInfo:
        """Parse Mega Drive ROM header."""
        if len(rom_data) < 0x200:
            return ROMHeaderInfo()

        # Console name at $100-$10F
        console = rom_data[0x100:0x110].decode('ascii', errors='replace').strip()

        # Domestic name at $120-$14F
        domestic = rom_data[0x120:0x150].decode('ascii', errors='replace').strip()

        # Overseas name at $150-$17F
        overseas = rom_data[0x150:0x180].decode('ascii', errors='replace').strip()

        # ROM start/end at $1A0-$1A7
        rom_start = int.from_bytes(rom_data[0x1A0:0x1A4], 'big')
        rom_end = int.from_bytes(rom_data[0x1A4:0x1A8], 'big')

        # RAM info at $1A8-$1AF
        ram_start = int.from_bytes(rom_data[0x1A8:0x1AC], 'big')
        ram_end = int.from_bytes(rom_data[0x1AC:0x1B0], 'big')

        # Checksum at $18E-$18F
        checksum = int.from_bytes(rom_data[0x18E:0x190], 'big')

        # Region at $1F0-$1FF
        region = rom_data[0x1F0:0x1F3].decode('ascii', errors='replace').strip()

        return ROMHeaderInfo(
            title=overseas or domestic,
            region=region,
            version=0,
            checksum=checksum,
            rom_size=rom_end - rom_start + 1 if rom_end > rom_start else len(rom_data),
            ram_size=ram_end - ram_start + 1 if ram_end > ram_start else 0,
            mapper=0,
            has_battery=b'RA' in rom_data[0x1B0:0x1B4],
            extra={
                'console': console,
                'domestic_name': domestic,
                'overseas_name': overseas,
            }
        )

    def get_text_banks(self, rom_data: bytes) -> List[TextBank]:
        """Find text-likely regions in MD ROM."""
        banks = []
        block_size = 0x10000  # 64KB blocks

        for offset in range(0, len(rom_data), block_size):
            block_end = min(offset + block_size, len(rom_data))
            block_data = rom_data[offset:block_end]

            score = self.calculate_text_score(block_data)

            # Skip vector table area
            if offset == 0:
                score *= 0.5

            if score >= 0.25:
                banks.append(TextBank(
                    start=offset,
                    end=block_end,
                    score=score,
                    method="heuristic",
                ))

        return sorted(banks, key=lambda b: b.score, reverse=True)

    def map_address(self, m68k_addr: int, rom_data: bytes) -> AddressMapping:
        """
        Map M68K address to file offset.

        MD Memory Map:
        $000000-$3FFFFF: ROM (up to 4MB)
        $A00000-$A0FFFF: Z80 area
        $C00000-$C0001F: VDP ports
        $FF0000-$FFFFFF: RAM (64KB)
        """
        if m68k_addr >= 0xFF0000:
            return AddressMapping(
                file_offset=-1,
                is_ram=True,
                is_valid=False,
                mapping_type="ram"
            )

        if m68k_addr >= 0xA00000:
            return AddressMapping(
                file_offset=-1,
                is_valid=False,
                mapping_type="io"
            )

        # ROM area
        if m68k_addr < len(rom_data):
            return AddressMapping(
                file_offset=m68k_addr,
                is_valid=True,
                mapping_type="linear"
            )

        return AddressMapping(
            file_offset=m68k_addr,
            is_valid=False,
            mapping_type="linear"
        )

    def map_offset_to_address(self, file_offset: int, rom_data: bytes) -> int:
        """Map file offset to M68K address (direct for MD)."""
        return file_offset

    def get_pointer_config(self) -> Dict[str, Any]:
        """Get MD-specific pointer configuration."""
        return {
            "sizes": [2, 4],  # u16 and u32
            "endianness": ["big"],  # M68K is big-endian!
            "min_run": 8,
            "resolve_ratio": 0.60,
            "text_score_min": 0.60,
        }

    def get_compression_config(self) -> Dict[str, Any]:
        """Get MD-specific compression configuration."""
        return {
            "algorithms": ["LZSS", "RLE", "Huffman"],
            "aggressive": True,  # MD games often use compression
        }

    def validate_pointer_target(self, target_offset: int, rom_data: bytes) -> Tuple[bool, float]:
        """Validate MD pointer target."""
        if target_offset < 0 or target_offset >= len(rom_data):
            return False, 0.0

        # Skip vector table
        if target_offset < 0x200:
            return False, 0.0

        sample = rom_data[target_offset:target_offset + 64]
        if not sample:
            return False, 0.0

        score = self.calculate_text_score(sample)
        return score >= 0.5, score
