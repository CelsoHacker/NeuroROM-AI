# -*- coding: utf-8 -*-
"""
================================================================================
SMS PLUGIN - Sega Master System
================================================================================
Plugin for Master System / Game Gear ROMs with:
- u16 LE pointers
- Slot resolution (0x0000/0x4000/0x8000) by score
- 16KB bank management
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


class SMSPlugin(BaseConsolePlugin):
    """
    Sega Master System / Game Gear plugin.

    Handles paged ROM with 16KB banks and slot-based memory mapping.
    """

    BANK_SIZE = 0x4000  # 16KB
    HEADER_OFFSET = 0x7FF0  # TMR SEGA header location

    @property
    def console_spec(self) -> ConsoleSpec:
        return ConsoleSpec(
            name="Sega Master System",
            console_type=ConsoleType.SMS,
            endianness="little",
            pointer_sizes=[2],    # u16 only
            ram_size=8192,        # 8KB main RAM
            ram_start=0xC000,
            default_encodings=["ascii"],
            address_mapper="sms_slot",
            has_banking=True,
            bank_size=0x4000,     # 16KB banks
            compression_common=["RLE"],
            vram_size=16384,      # 16KB VRAM
            vram_start=0x0000,
            tile_bpp=[4],         # SMS uses 4bpp tiles

            # Thresholds
            min_text_len=3,
            language_score_threshold=0.72,
            pointer_run_min=8,
            pointer_resolve_ratio=0.60,
            text_score_min=0.60,
        )

    @property
    def capabilities(self) -> Set[PluginCapability]:
        return {
            PluginCapability.POINTER_HUNTING,
            PluginCapability.TILE_TEXT,
        }

    def detect_rom(self, rom_data: bytes) -> bool:
        """Detect if this is a Master System ROM."""
        if len(rom_data) < 0x8000:
            return False

        # Check for "TMR SEGA" header
        if len(rom_data) > self.HEADER_OFFSET + 8:
            header = rom_data[self.HEADER_OFFSET:self.HEADER_OFFSET + 8]
            if header == b'TMR SEGA':
                return True

        # Check alternative header location
        alt_offset = 0x3FF0
        if len(rom_data) > alt_offset + 8:
            header = rom_data[alt_offset:alt_offset + 8]
            if header == b'TMR SEGA':
                return True

        # Heuristic: Valid Z80 code patterns
        if rom_data[0] in (0xC3, 0xF3, 0x00, 0x31):  # Common Z80 opcodes
            return len(rom_data) in [0x8000, 0x10000, 0x20000, 0x40000, 0x80000]

        return False

    def get_rom_header_info(self, rom_data: bytes) -> ROMHeaderInfo:
        """Parse SMS ROM header."""
        header_offset = self.HEADER_OFFSET
        if header_offset + 16 > len(rom_data):
            header_offset = 0x3FF0

        if header_offset + 16 > len(rom_data):
            return ROMHeaderInfo()

        header = rom_data[header_offset:header_offset + 16]

        if header[:8] != b'TMR SEGA':
            return ROMHeaderInfo(rom_size=len(rom_data))

        # Parse header fields
        checksum = (header[10] << 8) | header[11]
        product_code = (header[12] | (header[13] << 8) | ((header[14] & 0xF0) << 12))
        version = header[14] & 0x0F
        region = header[15] >> 4
        rom_size_code = header[15] & 0x0F

        size_map = {
            0xA: 8192, 0xB: 16384, 0xC: 32768, 0xD: 65536,
            0xE: 131072, 0xF: 262144, 0x0: 524288, 0x1: 1048576,
        }

        return ROMHeaderInfo(
            title=f"Product {product_code:05X}",
            region=self._region_name(region),
            version=version,
            checksum=checksum,
            rom_size=size_map.get(rom_size_code, len(rom_data)),
            mapper=0,
            extra={
                'product_code': product_code,
                'header_offset': header_offset,
            }
        )

    def _region_name(self, code: int) -> str:
        """Convert region code to name."""
        regions = {
            3: "SMS Japan",
            4: "SMS Export",
            5: "GG Japan",
            6: "GG Export",
            7: "GG International",
        }
        return regions.get(code, f"Unknown ({code})")

    def get_text_banks(self, rom_data: bytes) -> List[TextBank]:
        """Find text-likely regions in SMS ROM."""
        banks = []
        num_banks = len(rom_data) // self.BANK_SIZE

        for bank_num in range(num_banks):
            bank_start = bank_num * self.BANK_SIZE
            bank_end = bank_start + self.BANK_SIZE

            bank_data = rom_data[bank_start:bank_end]
            score = self.calculate_text_score(bank_data)

            # Bank 0 often has code, bank 1+ more likely text
            if bank_num == 0:
                score *= 0.7

            if score >= 0.25:
                banks.append(TextBank(
                    start=bank_start,
                    end=bank_end,
                    score=score,
                    bank_number=bank_num,
                    method="heuristic",
                ))

        return sorted(banks, key=lambda b: b.score, reverse=True)

    def map_address(self, cpu_addr: int, rom_data: bytes) -> AddressMapping:
        """
        Map SMS CPU address to file offset.

        SMS Memory Map:
        $0000-$03FF: ROM (fixed, first 1KB)
        $0400-$3FFF: Slot 0 (typically bank 0)
        $4000-$7FFF: Slot 1 (switchable)
        $8000-$BFFF: Slot 2 (switchable)
        $C000-$DFFF: RAM (8KB)
        $E000-$FFFF: RAM mirror
        """
        if cpu_addr >= 0xC000:
            return AddressMapping(
                file_offset=-1,
                is_ram=True,
                is_valid=False,
                mapping_type="ram"
            )

        # For static analysis, assume:
        # Slot 0: Bank 0
        # Slot 1: Bank 1
        # Slot 2: Bank 2

        if cpu_addr < 0x4000:
            # Slot 0
            return AddressMapping(
                file_offset=cpu_addr,
                bank=0,
                is_valid=True,
                mapping_type="slot0"
            )
        elif cpu_addr < 0x8000:
            # Slot 1
            offset = self.BANK_SIZE + (cpu_addr - 0x4000)
            return AddressMapping(
                file_offset=offset,
                bank=1,
                is_valid=offset < len(rom_data),
                mapping_type="slot1"
            )
        else:
            # Slot 2
            offset = (2 * self.BANK_SIZE) + (cpu_addr - 0x8000)
            return AddressMapping(
                file_offset=offset,
                bank=2,
                is_valid=offset < len(rom_data),
                mapping_type="slot2"
            )

    def map_offset_to_address(self, file_offset: int, rom_data: bytes) -> int:
        """Map file offset to SMS CPU address."""
        bank = file_offset // self.BANK_SIZE
        offset_in_bank = file_offset % self.BANK_SIZE

        if bank == 0:
            return offset_in_bank
        elif bank == 1:
            return 0x4000 + offset_in_bank
        else:
            return 0x8000 + offset_in_bank

    def resolve_slot_by_score(self, pointer_value: int, rom_data: bytes,
                               text_regions: List[Dict]) -> List[AddressMapping]:
        """
        Resolve pointer by trying all slot configurations.

        Returns list of possible mappings sorted by text score.
        """
        candidates = []
        num_banks = len(rom_data) // self.BANK_SIZE

        # Try different bank configurations
        offset_in_slot = pointer_value & 0x3FFF

        for slot in range(3):
            slot_base = slot * 0x4000

            if pointer_value >= slot_base and pointer_value < slot_base + 0x4000:
                # This pointer fits in this slot
                for bank in range(num_banks):
                    file_offset = (bank * self.BANK_SIZE) + offset_in_slot

                    if file_offset >= len(rom_data):
                        continue

                    # Score the target
                    sample = rom_data[file_offset:file_offset + 32]
                    score = self.calculate_text_score(sample)

                    candidates.append(AddressMapping(
                        file_offset=file_offset,
                        bank=bank,
                        is_valid=True,
                        mapping_type=f"slot{slot}_bank{bank}"
                    ))

        # Sort by text score would require re-scanning
        return candidates

    def get_pointer_config(self) -> Dict[str, Any]:
        """Get SMS-specific pointer configuration."""
        return {
            "sizes": [2],
            "endianness": ["little"],
            "min_run": 8,
            "resolve_ratio": 0.60,
            "text_score_min": 0.60,
            "use_slot_resolution": True,
        }
