# -*- coding: utf-8 -*-
"""
================================================================================
PS1 PLUGIN - PlayStation 1
================================================================================
Plugin for PS1 ROMs/ISOs with:
- u32 LE pointers
- ISO9660 filesystem extraction
- Per-file text extraction
- Shift-JIS encoding priority
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


class PS1Plugin(BaseConsolePlugin):
    """
    PlayStation 1 plugin.

    Handles ISO images and EXE files with Shift-JIS priority.
    Relies heavily on runtime mode due to distributed text storage.
    """

    PSX_EXE_MAGIC = b'PS-X EXE'
    ISO_MAGIC = b'CD001'
    SECTOR_SIZE = 2048

    @property
    def console_spec(self) -> ConsoleSpec:
        return ConsoleSpec(
            name="PlayStation 1",
            console_type=ConsoleType.PS1,
            endianness="little",
            pointer_sizes=[4],     # u32
            ram_size=2097152,      # 2MB main RAM
            ram_start=0x80000000,
            default_encodings=["shift_jis", "ascii"],  # Shift-JIS priority!
            address_mapper="ps1_exe",
            has_banking=False,
            bank_size=0,
            compression_common=["LZSS", "LZ77"],
            vram_size=1048576,     # 1MB VRAM
            vram_start=0x00000000,
            tile_bpp=[4, 8, 16],

            # Higher threshold for Japanese text
            min_text_len=3,
            language_score_threshold=0.75,
            pointer_run_min=8,
            pointer_resolve_ratio=0.60,
            text_score_min=0.60,
        )

    @property
    def capabilities(self) -> Set[PluginCapability]:
        return {
            PluginCapability.POINTER_HUNTING,
            PluginCapability.COMPRESSION,
            PluginCapability.CONTAINER_EXTRACT,  # ISO extraction
            PluginCapability.SCRIPT_OPCODE,
            PluginCapability.RUNTIME_CAPTURE,  # Essential for PS1
        }

    def should_use_runtime_mode(self) -> bool:
        """PS1 should always use runtime mode."""
        return True

    def detect_rom(self, rom_data: bytes) -> bool:
        """Detect if this is a PS1 ROM/ISO."""
        # Check for PS-X EXE header
        if rom_data[:8] == self.PSX_EXE_MAGIC:
            return True

        # Check for ISO9660 header (primary volume descriptor at sector 16)
        iso_offset = 16 * self.SECTOR_SIZE
        if len(rom_data) > iso_offset + 6:
            if rom_data[iso_offset + 1:iso_offset + 6] == self.ISO_MAGIC:
                return True

        # Check raw sector format
        raw_iso_offset = 16 * 2352 + 16  # Raw sector with sync header
        if len(rom_data) > raw_iso_offset + 6:
            if rom_data[raw_iso_offset + 1:raw_iso_offset + 6] == self.ISO_MAGIC:
                return True

        return False

    def _is_iso(self, rom_data: bytes) -> bool:
        """Check if data is an ISO image."""
        iso_offset = 16 * self.SECTOR_SIZE
        if len(rom_data) > iso_offset + 6:
            if rom_data[iso_offset + 1:iso_offset + 6] == self.ISO_MAGIC:
                return True

        raw_iso_offset = 16 * 2352 + 16
        if len(rom_data) > raw_iso_offset + 6:
            if rom_data[raw_iso_offset + 1:raw_iso_offset + 6] == self.ISO_MAGIC:
                return True

        return False

    def _is_exe(self, rom_data: bytes) -> bool:
        """Check if data is a PS-X EXE."""
        return rom_data[:8] == self.PSX_EXE_MAGIC

    def get_rom_header_info(self, rom_data: bytes) -> ROMHeaderInfo:
        """Parse PS1 ROM header."""
        if self._is_exe(rom_data):
            return self._parse_exe_header(rom_data)
        elif self._is_iso(rom_data):
            return self._parse_iso_header(rom_data)
        return ROMHeaderInfo()

    def _parse_exe_header(self, rom_data: bytes) -> ROMHeaderInfo:
        """Parse PS-X EXE header."""
        if len(rom_data) < 0x800:
            return ROMHeaderInfo()

        # Text section info
        text_addr = struct.unpack('<I', rom_data[0x18:0x1C])[0]
        text_size = struct.unpack('<I', rom_data[0x1C:0x20])[0]

        # Initial PC and GP
        pc = struct.unpack('<I', rom_data[0x10:0x14])[0]
        gp = struct.unpack('<I', rom_data[0x14:0x18])[0]

        # Stack pointer
        sp = struct.unpack('<I', rom_data[0x30:0x34])[0]

        return ROMHeaderInfo(
            title="PS-X Executable",
            rom_size=len(rom_data),
            extra={
                'type': 'exe',
                'text_addr': text_addr,
                'text_size': text_size,
                'entry_point': pc,
                'gp': gp,
                'sp': sp,
            }
        )

    def _parse_iso_header(self, rom_data: bytes) -> ROMHeaderInfo:
        """Parse ISO9660 header."""
        # Find primary volume descriptor
        iso_offset = 16 * self.SECTOR_SIZE

        if len(rom_data) <= iso_offset + 0x28:
            return ROMHeaderInfo()

        # Volume identifier at offset 40 (32 bytes)
        vol_id = rom_data[iso_offset + 40:iso_offset + 72]
        title = vol_id.decode('ascii', errors='replace').strip()

        # Volume size at offset 80 (little-endian)
        vol_size = struct.unpack('<I', rom_data[iso_offset + 80:iso_offset + 84])[0]

        return ROMHeaderInfo(
            title=title,
            rom_size=vol_size * self.SECTOR_SIZE,
            extra={
                'type': 'iso',
                'volume_size_sectors': vol_size,
            }
        )

    def get_text_banks(self, rom_data: bytes) -> List[TextBank]:
        """Find text-likely regions in PS1 ROM."""
        banks = []

        if self._is_exe(rom_data):
            # Scan EXE data section
            header_info = self.get_rom_header_info(rom_data)
            text_size = header_info.extra.get('text_size', len(rom_data) - 0x800)

            block_size = 0x10000  # 64KB
            for offset in range(0x800, min(0x800 + text_size, len(rom_data)), block_size):
                block_end = min(offset + block_size, len(rom_data))
                block_data = rom_data[offset:block_end]

                score = self.calculate_text_score(block_data)
                sjis_score = self._calculate_sjis_score(block_data)
                combined = max(score, sjis_score)

                if combined >= 0.25:
                    banks.append(TextBank(
                        start=offset,
                        end=block_end,
                        score=combined,
                        method="heuristic",
                        notes="sjis" if sjis_score > score else "ascii",
                    ))

        return sorted(banks, key=lambda b: b.score, reverse=True)

    def _calculate_sjis_score(self, data: bytes) -> float:
        """Calculate Shift-JIS text likelihood score."""
        if len(data) < 4:
            return 0.0

        sjis_chars = 0
        total = 0
        i = 0

        while i < len(data):
            b = data[i]

            # Single-byte ASCII
            if 0x20 <= b <= 0x7E:
                sjis_chars += 1
                total += 1
                i += 1
                continue

            # SJIS double-byte
            if i + 1 < len(data):
                b2 = data[i + 1]

                # SJIS first byte ranges
                if (0x81 <= b <= 0x9F) or (0xE0 <= b <= 0xFC):
                    # SJIS second byte ranges
                    if (0x40 <= b2 <= 0x7E) or (0x80 <= b2 <= 0xFC):
                        sjis_chars += 2
                        total += 2
                        i += 2
                        continue

            # Half-width katakana
            if 0xA1 <= b <= 0xDF:
                sjis_chars += 1
                total += 1
                i += 1
                continue

            total += 1
            i += 1

        if total == 0:
            return 0.0

        return sjis_chars / total

    def map_address(self, mips_addr: int, rom_data: bytes) -> AddressMapping:
        """
        Map MIPS address to file offset.

        PS1 Memory Map:
        $00000000-$001FFFFF: Main RAM (2MB)
        $1F000000-$1F00FFFF: Expansion 1
        $1F800000-$1F8003FF: Scratchpad (1KB)
        $80000000-$801FFFFF: Main RAM (cached mirror)
        $A0000000-$A01FFFFF: Main RAM (uncached mirror)
        """
        if not self._is_exe(rom_data):
            return AddressMapping(
                file_offset=-1,
                is_valid=False,
                mapping_type="iso"
            )

        header_info = self.get_rom_header_info(rom_data)
        text_addr = header_info.extra.get('text_addr', 0x80010000)

        # Convert to physical address
        phys_addr = mips_addr & 0x1FFFFFFF

        # Check if in text section range
        text_base = text_addr & 0x1FFFFFFF
        text_size = header_info.extra.get('text_size', len(rom_data) - 0x800)

        if text_base <= phys_addr < text_base + text_size:
            file_offset = 0x800 + (phys_addr - text_base)
            return AddressMapping(
                file_offset=file_offset,
                is_valid=file_offset < len(rom_data),
                mapping_type="exe_text"
            )

        return AddressMapping(
            file_offset=-1,
            is_ram=phys_addr < 0x200000,
            is_valid=False,
            mapping_type="ram" if phys_addr < 0x200000 else "unknown"
        )

    def map_offset_to_address(self, file_offset: int, rom_data: bytes) -> int:
        """Map file offset to MIPS address."""
        if not self._is_exe(rom_data):
            return file_offset

        header_info = self.get_rom_header_info(rom_data)
        text_addr = header_info.extra.get('text_addr', 0x80010000)

        if file_offset >= 0x800:
            return text_addr + (file_offset - 0x800)

        return 0

    def get_pointer_config(self) -> Dict[str, Any]:
        """Get PS1-specific pointer configuration."""
        return {
            "sizes": [4],  # u32
            "endianness": ["little"],
            "min_run": 8,
            "resolve_ratio": 0.60,
            "text_score_min": 0.60,
        }

    def get_encoding_priority(self) -> List[str]:
        """PS1 games often use Shift-JIS."""
        return ["shift_jis", "euc-jp", "ascii", "utf-8"]

    def get_compression_config(self) -> Dict[str, Any]:
        """Get PS1-specific compression configuration."""
        return {
            "algorithms": ["LZSS", "LZ77"],
            "aggressive": True,
        }

    def validate_pointer_target(self, target_offset: int, rom_data: bytes) -> Tuple[bool, float]:
        """Validate PS1 pointer target."""
        if target_offset < 0 or target_offset >= len(rom_data):
            return False, 0.0

        # Skip header
        if target_offset < 0x800:
            return False, 0.0

        sample = rom_data[target_offset:target_offset + 64]
        if not sample:
            return False, 0.0

        # Try both ASCII and Shift-JIS
        ascii_score = self.calculate_text_score(sample)
        sjis_score = self._calculate_sjis_score(sample)
        score = max(ascii_score, sjis_score)

        return score >= 0.5, score
