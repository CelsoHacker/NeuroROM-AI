# -*- coding: utf-8 -*-
"""
================================================================================
COMPRESSION HUNTER - Detection and Tracking of Compressed Data
================================================================================
Detects compressed regions in ROM and coordinates with MultiDecompress
for actual decompression. Rescans decompressed output for additional content.
================================================================================
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import struct
import math

from .multi_decompress import MultiDecompress, DecompressResult, CompressionAlgorithm


@dataclass
class CompressedCandidate:
    """A candidate compressed region."""
    offset: int
    size: int
    algorithm: CompressionAlgorithm
    confidence: float = 0.0
    entropy: float = 0.0
    magic: bytes = field(default_factory=bytes)
    decompressed: Optional[DecompressResult] = None

    def __repr__(self) -> str:
        return (f"<Compressed @0x{self.offset:06X} size={self.size} "
                f"algo={self.algorithm.value} conf={self.confidence:.2f}>")


class CompressionHunter:
    """
    Hunts for compressed data in ROM and coordinates decompression.

    Works with MultiDecompress to:
    1. Detect candidate compressed regions
    2. Attempt decompression
    3. Validate output quality
    4. Rescan decompressed data for text/pointers
    """

    # Known compression signatures
    SIGNATURES = {
        b'Yay0': CompressionAlgorithm.YAY0,
        b'Yaz0': CompressionAlgorithm.YAZ0,
        b'LZ77': CompressionAlgorithm.LZ77,
        b'\x1f\x8b': CompressionAlgorithm.LZ77,  # gzip
    }

    # Header byte signatures
    HEADER_SIGNATURES = {
        0x10: CompressionAlgorithm.LZ10,
        0x11: CompressionAlgorithm.LZ11,
    }

    def __init__(self, rom_data: bytes):
        self.rom_data = rom_data
        self.decompressor = MultiDecompress()
        self._candidates: List[CompressedCandidate] = []
        self._decompressed_cache: Dict[int, DecompressResult] = {}

    def hunt(self,
             algorithms: Optional[List[CompressionAlgorithm]] = None,
             min_size: int = 64,
             max_size: int = 256 * 1024,
             scan_regions: Optional[List[Tuple[int, int]]] = None
             ) -> List[CompressedCandidate]:
        """
        Hunt for compressed data in ROM.

        Args:
            algorithms: Algorithms to look for (None = all)
            min_size: Minimum compressed size
            max_size: Maximum compressed size
            scan_regions: Optional regions to scan

        Returns:
            List of CompressedCandidate sorted by confidence
        """
        regions = scan_regions or [(0, len(self.rom_data))]
        candidates = []

        # Phase 1: Scan for magic signatures
        for start, end in regions:
            sig_candidates = self._scan_signatures(start, end)
            candidates.extend(sig_candidates)

        # Phase 2: Scan for header byte signatures
        for start, end in regions:
            header_candidates = self._scan_headers(start, end)
            candidates.extend(header_candidates)

        # Phase 3: Entropy-based detection for RLE/LZSS without headers
        for start, end in regions:
            entropy_candidates = self._scan_entropy(start, end, min_size)
            candidates.extend(entropy_candidates)

        # Filter by algorithm if specified
        if algorithms:
            candidates = [c for c in candidates if c.algorithm in algorithms]

        # Attempt decompression to validate
        validated = []
        for candidate in candidates:
            result = self._try_decompress(candidate)
            if result and result.success:
                candidate.decompressed = result
                candidate.confidence = result.confidence
                validated.append(candidate)

        # Remove overlapping candidates, keep highest confidence
        validated = self._remove_overlaps(validated)

        self._candidates = validated
        return sorted(validated, key=lambda c: c.confidence, reverse=True)

    def _scan_signatures(self, start: int, end: int) -> List[CompressedCandidate]:
        """Scan for magic byte signatures."""
        candidates = []

        for sig, algo in self.SIGNATURES.items():
            pos = start
            while pos < end - len(sig):
                idx = self.rom_data.find(sig, pos, end)
                if idx == -1:
                    break

                # Estimate size from header if possible
                size = self._estimate_size(idx, algo)

                candidates.append(CompressedCandidate(
                    offset=idx,
                    size=size,
                    algorithm=algo,
                    confidence=0.8,
                    magic=sig,
                ))

                pos = idx + len(sig)

        return candidates

    def _scan_headers(self, start: int, end: int) -> List[CompressedCandidate]:
        """Scan for header byte signatures (Nintendo LZ formats)."""
        candidates = []

        for offset in range(start, end - 4):
            header_byte = self.rom_data[offset]

            if header_byte in self.HEADER_SIGNATURES:
                algo = self.HEADER_SIGNATURES[header_byte]

                # Read decompressed size (24-bit LE)
                decomp_size = (
                    self.rom_data[offset + 1] |
                    (self.rom_data[offset + 2] << 8) |
                    (self.rom_data[offset + 3] << 16)
                )

                # Validate size
                if 64 <= decomp_size <= 4 * 1024 * 1024:  # 64B to 4MB
                    # Estimate compressed size
                    comp_size = min(decomp_size, end - offset)

                    candidates.append(CompressedCandidate(
                        offset=offset,
                        size=comp_size,
                        algorithm=algo,
                        confidence=0.7,
                        magic=bytes([header_byte]),
                    ))

        return candidates

    def _scan_entropy(self, start: int, end: int,
                      block_size: int = 256) -> List[CompressedCandidate]:
        """Scan for high-entropy regions (potentially compressed)."""
        candidates = []

        for offset in range(start, end - block_size, block_size):
            block = self.rom_data[offset:offset + block_size]
            entropy = self._calculate_entropy(block)

            # High entropy suggests compression
            if 6.5 <= entropy <= 8.0:
                # Could be LZSS or RLE
                candidates.append(CompressedCandidate(
                    offset=offset,
                    size=block_size * 4,  # Estimate
                    algorithm=CompressionAlgorithm.LZSS,
                    confidence=0.3,
                    entropy=entropy,
                ))

            # Low entropy with patterns might be RLE
            elif 2.0 <= entropy <= 5.0:
                candidates.append(CompressedCandidate(
                    offset=offset,
                    size=block_size * 2,
                    algorithm=CompressionAlgorithm.RLE,
                    confidence=0.2,
                    entropy=entropy,
                ))

        return candidates

    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of data."""
        if not data:
            return 0.0

        from collections import Counter
        counter = Counter(data)
        n = len(data)
        entropy = 0.0

        for count in counter.values():
            if count > 0:
                p = count / n
                entropy -= p * math.log2(p)

        return entropy

    def _estimate_size(self, offset: int, algo: CompressionAlgorithm) -> int:
        """Estimate compressed data size from header."""
        if algo in (CompressionAlgorithm.YAY0, CompressionAlgorithm.YAZ0):
            if offset + 8 <= len(self.rom_data):
                # Decompressed size in header (big-endian)
                decomp_size = struct.unpack('>I', self.rom_data[offset + 4:offset + 8])[0]
                # Rough estimate: compressed is 30-70% of decompressed
                return min(decomp_size, len(self.rom_data) - offset)

        # Default estimate
        return min(16384, len(self.rom_data) - offset)

    def _try_decompress(self, candidate: CompressedCandidate) -> Optional[DecompressResult]:
        """Attempt to decompress a candidate."""
        if candidate.offset in self._decompressed_cache:
            return self._decompressed_cache[candidate.offset]

        data = self.rom_data[candidate.offset:candidate.offset + candidate.size]

        result = self.decompressor.decompress(data, candidate.algorithm)

        if result.success:
            self._decompressed_cache[candidate.offset] = result

        return result

    def _remove_overlaps(self, candidates: List[CompressedCandidate]
                         ) -> List[CompressedCandidate]:
        """Remove overlapping candidates, keeping highest confidence."""
        if not candidates:
            return []

        # Sort by offset
        candidates.sort(key=lambda c: c.offset)

        result = []
        for candidate in candidates:
            overlaps = False
            for existing in result:
                if (candidate.offset < existing.offset + existing.size and
                    candidate.offset + candidate.size > existing.offset):
                    # Overlap - keep higher confidence
                    if candidate.confidence > existing.confidence:
                        result.remove(existing)
                    else:
                        overlaps = True
                    break

            if not overlaps:
                result.append(candidate)

        return result

    def get_decompressed_data(self, offset: int) -> Optional[bytes]:
        """Get decompressed data for an offset."""
        if offset in self._decompressed_cache:
            return self._decompressed_cache[offset].data
        return None

    def rescan_decompressed(self, offset: int,
                            scanner_func: callable) -> Any:
        """
        Rescan decompressed data with provided scanner.

        Args:
            offset: Offset of compressed data
            scanner_func: Function to scan decompressed data

        Returns:
            Result from scanner_func
        """
        data = self.get_decompressed_data(offset)
        if data:
            return scanner_func(data)
        return None

    def decompress_all(self) -> Dict[int, bytes]:
        """
        Decompress all detected candidates.

        Returns:
            Dict mapping offset to decompressed data
        """
        result = {}

        for candidate in self._candidates:
            if candidate.decompressed and candidate.decompressed.success:
                result[candidate.offset] = candidate.decompressed.data

        return result


def hunt_compression(rom_data: bytes,
                     algorithms: Optional[List[CompressionAlgorithm]] = None
                     ) -> List[CompressedCandidate]:
    """
    Convenience function to hunt for compressed data.

    Args:
        rom_data: ROM data to scan
        algorithms: Optional list of algorithms to look for

    Returns:
        List of CompressedCandidate
    """
    hunter = CompressionHunter(rom_data)
    return hunter.hunt(algorithms)
