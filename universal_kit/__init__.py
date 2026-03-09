# -*- coding: utf-8 -*-
"""
================================================================================
UNIVERSAL KIT - Shared Tools for All Console Plugins
================================================================================
Provides universal extraction tools that work across all consoles:
- EndianPointerHunter: Multi-size, multi-endian pointer detection
- MultiDecompress: Actual decompression for various algorithms
- TileTextEngine: Tile-to-text conversion
- AutoCharTableSolver: Automatic character table discovery
- ScriptOpcodeMiner: Script command detection
- ContainerExtractor: Archive/filesystem extraction
================================================================================
"""

from .endian_pointer_hunter import (
    EndianPointerHunter,
    PointerCandidate,
    PointerTableResult,
)
from .multi_decompress import (
    MultiDecompress,
    DecompressResult,
    CompressionAlgorithm,
)
from .multi_compress import (
    MultiCompress,
    CompressResult,
)
from .tile_text_engine import TileTextEngine
from .auto_char_table_solver import AutoCharTableSolver, CharTableHypothesis
from .script_opcode_miner import ScriptOpcodeMiner, OpcodePattern
from .compression_hunter import CompressionHunter
from .container_extractor import ContainerExtractor

__all__ = [
    'EndianPointerHunter',
    'PointerCandidate',
    'PointerTableResult',
    'MultiDecompress',
    'DecompressResult',
    'CompressionAlgorithm',
    'MultiCompress',
    'CompressResult',
    'TileTextEngine',
    'AutoCharTableSolver',
    'CharTableHypothesis',
    'ScriptOpcodeMiner',
    'OpcodePattern',
    'CompressionHunter',
    'ContainerExtractor',
]
