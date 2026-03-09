# -*- coding: utf-8 -*-
"""
================================================================================
NES PLUGIN - Nintendo Entertainment System / Famicom
================================================================================
Plugin for NES/Famicom ROMs with:
- u16 LE pointers
- Mapper/banking inference heuristics
- Strong tile text extraction (primary method)
- 1bpp/2bpp CHR-ROM font detection
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


class NESPlugin(BaseConsolePlugin):
    """
    NES/Famicom plugin.

    Uses tile text as primary extraction method due to limited RAM (2KB).
    Handles iNES/NES 2.0 headers and common mappers.
    """

    INES_MAGIC = b'NES\x1A'
    PRG_BANK_SIZE = 16384  # 16KB
    CHR_BANK_SIZE = 8192   # 8KB

    @property
    def console_spec(self) -> ConsoleSpec:
        return ConsoleSpec(
            name="Nintendo Entertainment System",
            console_type=ConsoleType.NES,
            endianness="little",
            pointer_sizes=[2],    # u16 only
            ram_size=2048,        # 2KB internal RAM
            ram_start=0x0000,
            default_encodings=["ascii"],
            address_mapper="ines_mapper",
            has_banking=True,
            bank_size=0x4000,     # 16KB PRG banks
            compression_common=["RLE"],
            vram_size=2048,       # 2KB VRAM (nametables)
            vram_start=0x2000,
            tile_bpp=[1, 2],      # CHR uses 2bpp

            # Thresholds - higher for NES due to limited text
            min_text_len=3,
            language_score_threshold=0.75,
            pointer_run_min=8,
            pointer_resolve_ratio=0.60,
            text_score_min=0.65,
        )

    @property
    def capabilities(self) -> Set[PluginCapability]:
        return {
            PluginCapability.POINTER_HUNTING,
            PluginCapability.TILE_TEXT,
            PluginCapability.RUNTIME_CAPTURE,  # Important for NES
        }

    def detect_rom(self, rom_data: bytes) -> bool:
        """Detect if this is an iNES ROM."""
        if len(rom_data) < 16:
            return False
        return rom_data[:4] == self.INES_MAGIC

    def get_rom_header_info(self, rom_data: bytes) -> ROMHeaderInfo:
        """Parse iNES/NES 2.0 header."""
        if not self.detect_rom(rom_data):
            return ROMHeaderInfo()

        prg_banks = rom_data[4]
        chr_banks = rom_data[5]
        flags6 = rom_data[6]
        flags7 = rom_data[7]

        mapper = (flags7 & 0xF0) | (flags6 >> 4)
        has_trainer = bool(flags6 & 0x04)
        has_battery = bool(flags6 & 0x02)

        # Check for NES 2.0
        is_nes20 = (flags7 & 0x0C) == 0x08

        prg_size = prg_banks * self.PRG_BANK_SIZE
        chr_size = chr_banks * self.CHR_BANK_SIZE

        return ROMHeaderInfo(
            title="",  # NES ROMs don't have title in header
                        region="",
            version=0,
            checksum=0,
            rom_size=prg_size,
            ram_size=chr_size,
            mapper=mapper,
            has_battery=has_battery,
            extra={
                'prg_banks': prg_banks,
                'chr_banks': chr_banks,
                'has_trainer': has_trainer,
                'is_nes20': is_nes20,
                'mirroring': 'vertical' if (flags6 & 0x01) else 'horizontal',
            }
        )

    def _get_prg_start(self, rom_data: bytes) -> int:
        """Get start offset of PRG-ROM."""
        header = self.get_rom_header_info(rom_data)
        base = 16  # Header size
        if header.extra.get('has_trainer', False):
            base += 512
        return base

    def _get_chr_start(self, rom_data: bytes) -> int:
        """Get start offset of CHR-ROM."""
        header = self.get_rom_header_info(rom_data)
        prg_start = self._get_prg_start(rom_data)
        return prg_start + header.rom_size

    def get_text_banks(self, rom_data: bytes) -> List[TextBank]:
        """Find text-likely regions in NES ROM."""
        banks = []
        header = self.get_rom_header_info(rom_data)
        prg_start = self._get_prg_start(rom_data)

        # NES text is usually in the last PRG bank (fixed bank)
        prg_banks = header.extra.get('prg_banks', 1)

        for bank_num in range(prg_banks):
            bank_start = prg_start + (bank_num * self.PRG_BANK_SIZE)
            bank_end = bank_start + self.PRG_BANK_SIZE

            if bank_end > len(rom_data):
                break

            bank_data = rom_data[bank_start:bank_end]
            score = self.calculate_text_score(bank_data)

            # Last bank usually has more text
            if bank_num == prg_banks - 1:
                score *= 1.2

            if score >= 0.25:
                banks.append(TextBank(
                    start=bank_start,
                    end=bank_end,
                    score=min(1.0, score),
                    bank_number=bank_num,
                    method="heuristic",
                    notes="last_bank" if bank_num == prg_banks - 1 else "",
                ))

        return sorted(banks, key=lambda b: b.score, reverse=True)

    def map_address(self, cpu_addr: int, rom_data: bytes) -> AddressMapping:
        """
        Map NES CPU address to file offset.

        NES memory map:
        $0000-$07FF: Internal RAM (2KB)
        $2000-$2007: PPU registers
        $4000-$401F: APU/IO registers
        $6000-$7FFF: PRG-RAM (if present)
        $8000-$BFFF: PRG-ROM (lower bank, switchable)
        $C000-$FFFF: PRG-ROM (upper bank, often fixed)
        """
        header = self.get_rom_header_info(rom_data)
        prg_start = self._get_prg_start(rom_data)
        prg_banks = header.extra.get('prg_banks', 1)
        mapper = header.mapper

        if cpu_addr < 0x8000:
            # Not PRG-ROM
            return AddressMapping(
                file_offset=-1,
                is_ram=cpu_addr < 0x2000 or (0x6000 <= cpu_addr < 0x8000),
                is_valid=False,
                mapping_type="ram"
            )

        # Simple mapper handling
        if mapper == 0:  # NROM
            if prg_banks == 1:
                # 16KB ROM mirrored
                offset = prg_start + ((cpu_addr - 0x8000) & 0x3FFF)
            else:
                # 32KB ROM
                offset = prg_start + (cpu_addr - 0x8000)

        elif mapper in (1, 2, 3, 7):  # Common mappers
            # Assume last bank at $C000-$FFFF
            if cpu_addr >= 0xC000:
                # Fixed last bank
                last_bank_start = prg_start + ((prg_banks - 1) * self.PRG_BANK_SIZE)
                offset = last_bank_start + (cpu_addr - 0xC000)
            else:
                # Switchable bank - assume bank 0 for static analysis
                offset = prg_start + (cpu_addr - 0x8000)
        else:
            # Default mapping
            offset = prg_start + (cpu_addr - 0x8000)

        if offset < 0 or offset >= len(rom_data):
            return AddressMapping(
                file_offset=offset,
                is_valid=False,
                mapping_type=f"mapper_{mapper}"
            )

        return AddressMapping(
            file_offset=offset,
            bank=None,  # Bank switching makes this complex
            is_valid=True,
            mapping_type=f"mapper_{mapper}"
        )

    def map_offset_to_address(self, file_offset: int, rom_data: bytes) -> int:
        """Map file offset to NES CPU address."""
        header = self.get_rom_header_info(rom_data)
        prg_start = self._get_prg_start(rom_data)
        prg_banks = header.extra.get('prg_banks', 1)

        if file_offset < prg_start:
            return 0  # In header

        prg_offset = file_offset - prg_start

        if prg_banks == 1:
            # 16KB mirrored
            return 0x8000 + (prg_offset & 0x3FFF)
        else:
            # Determine bank
            bank = prg_offset // self.PRG_BANK_SIZE
            offset_in_bank = prg_offset % self.PRG_BANK_SIZE

            if bank == prg_banks - 1:
                # Last bank at $C000
                return 0xC000 + offset_in_bank
            else:
                return 0x8000 + offset_in_bank

    def get_pointer_config(self) -> Dict[str, Any]:
        """Get NES-specific pointer configuration."""
        return {
            "sizes": [2],  # u16 only
            "endianness": ["little"],
            "min_run": 8,
            "resolve_ratio": 0.50,  # Lower due to banking
            "text_score_min": 0.65,
            "use_address_mapping": True,
        }

    def get_tile_config(self) -> Dict[str, Any]:
        """Get NES-specific tile configuration."""
        return {
            "bpp_modes": [2],  # NES CHR is 2bpp
            "tile_width": 8,
            "tile_height": 8,
            "is_primary_method": True,  # Tile text is primary for NES
        }

    def scan_chr_for_font(self, rom_data: bytes) -> List[Tuple[int, int]]:
        """
        Scan CHR-ROM for font tiles.

        Returns list of (start_offset, tile_count) for potential fonts.
        """
        header = self.get_rom_header_info(rom_data)
        chr_banks = header.extra.get('chr_banks', 0)

        if chr_banks == 0:
            return []  # CHR-RAM, no CHR-ROM

        fonts = []
        chr_start = self._get_chr_start(rom_data)
        chr_size = chr_banks * self.CHR_BANK_SIZE
        chr_end = chr_start + chr_size

        # Each tile is 16 bytes in 2bpp
        tile_size = 16

        offset = chr_start
        while offset + 256 * tile_size <= chr_end:
            # Check if this could be a font (32-96 tiles of letters)
            font_tiles = 0
            for i in range(96):  # Check 96 potential character tiles
                tile_offset = offset + (i * tile_size)
                if tile_offset + tile_size > chr_end:
                    break

                tile = rom_data[tile_offset:tile_offset + tile_size]
                if self._is_font_like_tile(tile):
                    font_tiles += 1

            if font_tiles >= 26:  # At least alphabet
                fonts.append((offset, min(96, font_tiles)))

            offset += tile_size * 64  # Skip ahead

        return fonts

    def _is_font_like_tile(self, tile_data: bytes) -> bool:
        """Check if 2bpp tile looks like a font character."""
        if len(tile_data) != 16:
            return False

        # Empty or solid tiles aren't fonts
        if all(b == 0 for b in tile_data):
            return False
        if all(b == 0xFF for b in tile_data):
            return False

        # Font tiles typically have some structure
        unique_bytes = len(set(tile_data))
        return 2 <= unique_bytes <= 10

    def validate_pointer_target(self, target_offset: int, rom_data: bytes) -> Tuple[bool, float]:
        """Validate NES pointer target."""
        prg_start = self._get_prg_start(rom_data)

        if target_offset < prg_start or target_offset >= len(rom_data):
            return False, 0.0

        sample = rom_data[target_offset:target_offset + 32]
        if not sample:
            return False, 0.0

        score = self.calculate_text_score(sample)
        return score >= 0.5, score
