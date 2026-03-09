# -*- coding: utf-8 -*-
"""
================================================================================
N64 PLUGIN - Nintendo 64
================================================================================
Plugin for N64 ROMs with:
- BIG ENDIAN u32 pointers (MIPS R4300)
- Segment table parsing
- Yay0/Yaz0 decompression
- AUTO_DEEP mode by default
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


class N64Plugin(BaseConsolePlugin):
    """
    Nintendo 64 plugin.

    Uses BIG ENDIAN for MIPS R4300 processor.
    Relies heavily on runtime mode due to complex text storage.
    """

    # ROM byte order detection
    MAGIC_BE = 0x80371240  # Big-endian (native)
    MAGIC_BS = 0x37804012  # Byte-swapped
    MAGIC_LE = 0x40123780  # Little-endian

    @property
    def console_spec(self) -> ConsoleSpec:
        return ConsoleSpec(
            name="Nintendo 64",
            console_type=ConsoleType.N64,
            endianness="big",     # MIPS is big-endian
            pointer_sizes=[4],    # u32
            ram_size=4194304,     # 4MB (8MB with expansion)
            ram_start=0x80000000,
            default_encodings=["ascii", "shift_jis"],
            address_mapper="n64_segment",
            has_banking=False,
            bank_size=0,
            compression_common=["Yay0", "Yaz0", "LZSS"],
            vram_size=0,
            vram_start=0,
            tile_bpp=[4, 8, 16],

            # Lower thresholds - N64 is complex
            min_text_len=3,
            language_score_threshold=0.68,
            pointer_run_min=8,
            pointer_resolve_ratio=0.50,
            text_score_min=0.55,
        )

    @property
    def capabilities(self) -> Set[PluginCapability]:
        return {
            PluginCapability.POINTER_HUNTING,
            PluginCapability.COMPRESSION,
            PluginCapability.CONTAINER_EXTRACT,
            PluginCapability.RUNTIME_CAPTURE,  # Essential for N64
        }

    def should_use_runtime_mode(self) -> bool:
        """N64 should always use runtime mode."""
        return True

    def detect_rom(self, rom_data: bytes) -> bool:
        """Detect if this is an N64 ROM."""
        if len(rom_data) < 0x40:
            return False

        magic = struct.unpack('>I', rom_data[:4])[0]
        return magic in (self.MAGIC_BE, self.MAGIC_BS, self.MAGIC_LE)

    def _get_byte_order(self, rom_data: bytes) -> str:
        """Detect ROM byte order."""
        magic = struct.unpack('>I', rom_data[:4])[0]

        if magic == self.MAGIC_BE:
            return "big"
        elif magic == self.MAGIC_BS:
            return "byteswapped"
        elif magic == self.MAGIC_LE:
            return "little"
        return "big"

    def _fix_byte_order(self, rom_data: bytes) -> bytes:
        """Convert ROM to big-endian format."""
        order = self._get_byte_order(rom_data)

        if order == "big":
            return rom_data

        result = bytearray(len(rom_data))

        if order == "byteswapped":
            # Swap bytes within 16-bit words
            for i in range(0, len(rom_data) - 1, 2):
                result[i] = rom_data[i + 1]
                result[i + 1] = rom_data[i]

        elif order == "little":
            # Swap bytes within 32-bit words
            for i in range(0, len(rom_data) - 3, 4):
                result[i] = rom_data[i + 3]
                result[i + 1] = rom_data[i + 2]
                result[i + 2] = rom_data[i + 1]
                result[i + 3] = rom_data[i]

        return bytes(result)

    def get_rom_header_info(self, rom_data: bytes) -> ROMHeaderInfo:
        """Parse N64 ROM header."""
        data = self._fix_byte_order(rom_data)

        if len(data) < 0x40:
            return ROMHeaderInfo()

        # Game title at 0x20-0x33 (20 bytes)
        title = data[0x20:0x34].decode('ascii', errors='replace').strip('\x00 ')

        # Game code at 0x3B-0x3E (4 bytes)
        game_code = data[0x3B:0x3F].decode('ascii', errors='replace')

        # Version at 0x3F
        version = data[0x3F]

        # CRC1 and CRC2 at 0x10-0x17
        crc1 = struct.unpack('>I', data[0x10:0x14])[0]
        crc2 = struct.unpack('>I', data[0x14:0x18])[0]

        # Region from game code
        region = "Unknown"
        if len(game_code) >= 4:
            region_char = game_code[3]
            regions = {'J': 'Japan', 'E': 'USA', 'P': 'Europe', 'A': 'Asia'}
            region = regions.get(region_char, region_char)

        return ROMHeaderInfo(
            title=title,
            region=region,
            version=version,
            checksum=crc1,
            rom_size=len(rom_data),
            extra={
                'game_code': game_code,
                'crc1': crc1,
                'crc2': crc2,
                'byte_order': self._get_byte_order(rom_data),
            }
        )

    def get_text_banks(self, rom_data: bytes) -> List[TextBank]:
        """Find text-likely regions in N64 ROM."""
        data = self._fix_byte_order(rom_data)
        banks = []
        block_size = 0x20000  # 128KB blocks

        for offset in range(0, len(data), block_size):
            block_end = min(offset + block_size, len(data))
            block_data = data[offset:block_end]

            score = self.calculate_text_score(block_data)

            # Skip boot code area
            if offset < 0x1000:
                score *= 0.3

            if score >= 0.20:  # Lower threshold
                banks.append(TextBank(
                    start=offset,
                    end=block_end,
                    score=score,
                    method="heuristic",
                ))

        return sorted(banks, key=lambda b: b.score, reverse=True)

    def map_address(self, mips_addr: int, rom_data: bytes) -> AddressMapping:
        """
        Map MIPS address to file offset.

        N64 Memory Map:
        $80000000-$803FFFFF: RAM (cached)
        $A0000000-$A03FFFFF: RAM (uncached)
        $B0000000-$B0FFFFFF: ROM
        """
        # RAM areas
        if 0x80000000 <= mips_addr < 0x80400000:
            return AddressMapping(
                file_offset=-1,
                is_ram=True,
                is_valid=False,
                mapping_type="ram_cached"
            )

        if 0xA0000000 <= mips_addr < 0xA0400000:
            return AddressMapping(
                file_offset=-1,
                is_ram=True,
                is_valid=False,
                mapping_type="ram_uncached"
            )

        # ROM area
        if 0xB0000000 <= mips_addr < 0xB1000000:
            file_offset = mips_addr - 0xB0000000
            return AddressMapping(
                file_offset=file_offset,
                is_valid=file_offset < len(rom_data),
                mapping_type="rom"
            )

        # Direct offset interpretation
        if mips_addr < len(rom_data):
            return AddressMapping(
                file_offset=mips_addr,
                is_valid=True,
                mapping_type="direct"
            )

        return AddressMapping(
            file_offset=-1,
            is_valid=False,
            mapping_type="unknown"
        )

    def map_offset_to_address(self, file_offset: int, rom_data: bytes) -> int:
        """Map file offset to MIPS address."""
        return 0xB0000000 + file_offset

    def get_pointer_config(self) -> Dict[str, Any]:
        """Get N64-specific pointer configuration."""
        return {
            "sizes": [4],  # u32
            "endianness": ["big"],  # MIPS is big-endian!
            "min_run": 8,
            "resolve_ratio": 0.50,  # Lower due to complexity
            "text_score_min": 0.55,
        }

    def get_compression_config(self) -> Dict[str, Any]:
        """Get N64-specific compression configuration."""
        return {
            "algorithms": ["YAY0", "YAZ0", "LZSS"],
            "aggressive": True,
            "scan_for_magic": True,
        }

    def scan_for_compressed(self, rom_data: bytes) -> List[Tuple[int, str]]:
        """
        Scan for Yay0/Yaz0 compressed blocks.

        Returns list of (offset, algorithm) tuples.
        """
        data = self._fix_byte_order(rom_data)
        compressed = []

        for magic, name in [(b'Yay0', 'Yay0'), (b'Yaz0', 'Yaz0')]:
            offset = 0
            while True:
                idx = data.find(magic, offset)
                if idx == -1:
                    break

                if idx + 16 <= len(data):
                    decomp_size = struct.unpack('>I', data[idx + 4:idx + 8])[0]
                    if 0 < decomp_size < 0x1000000:  # Reasonable size
                        compressed.append((idx, name))

                offset = idx + 4

        return compressed

    def validate_pointer_target(self, target_offset: int, rom_data: bytes) -> Tuple[bool, float]:
        """Validate N64 pointer target."""
        data = self._fix_byte_order(rom_data)

        if target_offset < 0 or target_offset >= len(data):
            return False, 0.0

        # Skip header area
        if target_offset < 0x1000:
            return False, 0.0

        sample = data[target_offset:target_offset + 64]
        if not sample:
            return False, 0.0

        score = self.calculate_text_score(sample)
        return score >= 0.4, score
