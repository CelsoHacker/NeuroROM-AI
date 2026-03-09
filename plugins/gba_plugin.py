# -*- coding: utf-8 -*-
"""
================================================================================
GBA PLUGIN - Game Boy Advance
================================================================================
Plugin for GBA ROMs with:
- u32 LE pointers
- 0x08000000 address offset mapping
- Aggressive LZ77/LZSS decompression
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


class GBAPlugin(BaseConsolePlugin):
    """
    Game Boy Advance plugin.

    Handles ARM7TDMI addressing with ROM at 0x08000000.
    """

    ROM_BASE = 0x08000000
    HEADER_OFFSET = 0x00

    @property
    def console_spec(self) -> ConsoleSpec:
        return ConsoleSpec(
            name="Game Boy Advance",
            console_type=ConsoleType.GBA,
            endianness="little",
            pointer_sizes=[4],    # u32 only
            ram_size=262144,      # 256KB IWRAM + EWRAM
            ram_start=0x02000000,
            default_encodings=["ascii", "shift_jis"],
            address_mapper="gba_linear",
            has_banking=False,
            bank_size=0,
            compression_common=["LZ77", "LZSS", "RLE", "Huffman"],
            vram_size=98304,      # 96KB VRAM
            vram_start=0x06000000,
            tile_bpp=[4, 8],      # GBA uses 4bpp and 8bpp

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
            PluginCapability.COMPRESSION,
            PluginCapability.TILE_TEXT,
            PluginCapability.SCRIPT_OPCODE,
        }

    def detect_rom(self, rom_data: bytes) -> bool:
        """Detect if this is a GBA ROM."""
        if len(rom_data) < 0xC0:
            return False

        # Check for fixed value at 0xB2
        if rom_data[0xB2] == 0x96:
            return True

        # Check for valid ARM entry point
        entry = int.from_bytes(rom_data[0:4], 'little')
        if (entry & 0xFF000000) == 0xEA000000:  # ARM branch instruction
            return True

        return False

    def get_rom_header_info(self, rom_data: bytes) -> ROMHeaderInfo:
        """Parse GBA ROM header."""
        if len(rom_data) < 0xC0:
            return ROMHeaderInfo()

        # Game title at 0xA0-0xAB (12 bytes)
        title = rom_data[0xA0:0xAC].decode('ascii', errors='replace').strip('\x00')

        # Game code at 0xAC-0xAF (4 bytes)
        game_code = rom_data[0xAC:0xB0].decode('ascii', errors='replace')

        # Maker code at 0xB0-0xB1 (2 bytes)
        maker_code = rom_data[0xB0:0xB2].decode('ascii', errors='replace')

        # Version at 0xBC
        version = rom_data[0xBC]

        # Header checksum at 0xBD
        checksum = rom_data[0xBD]

        # Determine region from game code
        region = "Unknown"
        if len(game_code) >= 4:
            region_char = game_code[3]
            regions = {'J': 'Japan', 'E': 'USA', 'P': 'Europe', 'F': 'France',
                       'D': 'Germany', 'S': 'Spain', 'I': 'Italy'}
            region = regions.get(region_char, region_char)

        return ROMHeaderInfo(
            title=title,
            region=region,
            version=version,
            checksum=checksum,
            rom_size=len(rom_data),
            mapper=0,
            extra={
                'game_code': game_code,
                'maker_code': maker_code,
            }
        )

    def get_text_banks(self, rom_data: bytes) -> List[TextBank]:
        """Find text-likely regions in GBA ROM."""
        banks = []
        block_size = 0x10000  # 64KB blocks

        for offset in range(0, len(rom_data), block_size):
            block_end = min(offset + block_size, len(rom_data))
            block_data = rom_data[offset:block_end]

            score = self.calculate_text_score(block_data)

            # Header area less likely to have text
            if offset == 0:
                score *= 0.6

            if score >= 0.25:
                banks.append(TextBank(
                    start=offset,
                    end=block_end,
                    score=score,
                    method="heuristic",
                ))

        return sorted(banks, key=lambda b: b.score, reverse=True)

    def map_address(self, arm_addr: int, rom_data: bytes) -> AddressMapping:
        """
        Map ARM address to file offset.

        GBA Memory Map:
        $00000000-$00003FFF: BIOS
        $02000000-$0203FFFF: EWRAM (256KB)
        $03000000-$03007FFF: IWRAM (32KB)
        $04000000-$040003FF: I/O
        $05000000-$050003FF: Palette
        $06000000-$06017FFF: VRAM (96KB)
        $07000000-$070003FF: OAM
        $08000000-$09FFFFFF: ROM (Wait State 0)
        $0A000000-$0BFFFFFF: ROM (Wait State 1)
        $0C000000-$0DFFFFFF: ROM (Wait State 2)
        $0E000000-$0E00FFFF: SRAM
        """
        # ROM mirrors
        if 0x08000000 <= arm_addr < 0x0E000000:
            file_offset = (arm_addr - 0x08000000) % len(rom_data)
            return AddressMapping(
                file_offset=file_offset,
                is_valid=True,
                mapping_type="rom"
            )

        # RAM areas
        if 0x02000000 <= arm_addr < 0x03000000:
            return AddressMapping(
                file_offset=-1,
                is_ram=True,
                is_valid=False,
                mapping_type="ewram"
            )

        if 0x03000000 <= arm_addr < 0x04000000:
            return AddressMapping(
                file_offset=-1,
                is_ram=True,
                is_valid=False,
                mapping_type="iwram"
            )

        return AddressMapping(
            file_offset=-1,
            is_valid=False,
            mapping_type="unknown"
        )

    def map_offset_to_address(self, file_offset: int, rom_data: bytes) -> int:
        """Map file offset to ARM address."""
        return self.ROM_BASE + file_offset

    def get_pointer_config(self) -> Dict[str, Any]:
        """Get GBA-specific pointer configuration."""
        return {
            "sizes": [4],  # u32 only
            "endianness": ["little"],
            "min_run": 8,
            "resolve_ratio": 0.60,
            "text_score_min": 0.60,
            "address_base": self.ROM_BASE,
        }

    def get_compression_config(self) -> Dict[str, Any]:
        """Get GBA-specific compression configuration."""
        return {
            "algorithms": ["LZ10", "LZ11", "LZ77", "RLE", "Huffman"],
            "aggressive": True,  # GBA games use compression heavily
            "scan_for_lz_headers": True,
        }

    def scan_for_compressed(self, rom_data: bytes) -> List[Tuple[int, str]]:
        """
        Scan for LZ compressed blocks.

        Returns list of (offset, algorithm) tuples.
        """
        compressed = []

        for offset in range(0, len(rom_data) - 4):
            header = rom_data[offset]

            if header == 0x10:
                # LZ10 header
                size = (rom_data[offset + 1] |
                        (rom_data[offset + 2] << 8) |
                        (rom_data[offset + 3] << 16))
                if 64 <= size <= 0x100000:  # Reasonable size
                    compressed.append((offset, "LZ10"))

            elif header == 0x11:
                # LZ11 header
                size = (rom_data[offset + 1] |
                        (rom_data[offset + 2] << 8) |
                        (rom_data[offset + 3] << 16))
                if 64 <= size <= 0x100000:
                    compressed.append((offset, "LZ11"))

        return compressed

    def validate_pointer_target(self, target_offset: int, rom_data: bytes) -> Tuple[bool, float]:
        """Validate GBA pointer target."""
        if target_offset < 0 or target_offset >= len(rom_data):
            return False, 0.0

        # Skip header area
        if target_offset < 0xC0:
            return False, 0.0

        sample = rom_data[target_offset:target_offset + 64]
        if not sample:
            return False, 0.0

        score = self.calculate_text_score(sample)
        return score >= 0.5, score
