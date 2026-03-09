# -*- coding: utf-8 -*-
"""Console Memory Model - defines ROM/RAM constraints per console."""

from __future__ import annotations
from typing import Dict, Tuple

# ROM size limits per console (max typical ROM size in bytes)
_CONSOLE_LIMITS: Dict[str, Tuple[int, int]] = {
    # (min_writable_offset, max_rom_size)
    "SMS":     (0x0000, 0x80000),    # 512 KB
    "GG":      (0x0000, 0x80000),    # 512 KB
    "NES":     (0x0010, 0x80000),    # 512 KB (skip 16-byte header)
    "SNES":    (0x0000, 0x400000),   # 4 MB
    "MD":      (0x0000, 0x400000),   # 4 MB
    "GENESIS": (0x0000, 0x400000),   # 4 MB
    "GBA":     (0x0000, 0x2000000),  # 32 MB
    "N64":     (0x0000, 0x4000000),  # 64 MB
    "PS1":     (0x0000, 0x40000000), # 1 GB (ISO)
    "PC":      (0x0000, 0x40000000), # 1 GB
}


class ConsoleMemoryModel:
    """Minimal memory constraint model for a given console type."""

    def __init__(self, console_type: str):
        self.console_type = str(console_type or "SMS").upper()
        limits = _CONSOLE_LIMITS.get(self.console_type, (0, 0x400000))
        self.min_offset = limits[0]
        self.max_size = limits[1]

    def validate_write(self, offset: int, size: int) -> bool:
        """Check if a write at (offset, size) is within valid ROM bounds."""
        if offset < self.min_offset:
            return False
        if offset + size > self.max_size:
            return False
        return True
