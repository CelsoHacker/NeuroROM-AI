# -*- coding: utf-8 -*-
"""
================================================================================
MULTI DECOMPRESS - Actual Decompression Engines for ROM Data
================================================================================
Provides decompression for common ROM compression algorithms:
- RLE (Run-Length Encoding) - NES/SMS/MD
- LZSS (Lempel-Ziv-Storer-Szymanski) - SNES/GBA
- LZ77 (GBA Nintendo format)
- Yay0/Yaz0 (N64/GameCube)

Each algorithm includes parametric variants for different implementations.
================================================================================
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import struct


class CompressionAlgorithm(Enum):
    """Supported compression algorithms."""
    RLE = "RLE"
    LZSS = "LZSS"
    LZ77 = "LZ77"
    LZ10 = "LZ10"  # Nintendo GBA variant
    LZ11 = "LZ11"  # Nintendo DS variant
    YAY0 = "Yay0"
    YAZ0 = "Yaz0"
    HUFFMAN = "Huffman"
    UNKNOWN = "Unknown"


@dataclass
class DecompressResult:
    """Result of decompression attempt."""
    success: bool
    algorithm: CompressionAlgorithm
    data: bytes = field(default_factory=bytes)
    original_size: int = 0
    decompressed_size: int = 0
    confidence: float = 0.0
    error: str = ""
    params: Dict[str, Any] = field(default_factory=dict)

    @property
    def ratio(self) -> float:
        """Compression ratio."""
        if self.original_size == 0:
            return 0.0
        return self.decompressed_size / self.original_size


class MultiDecompress:
    """
    Multi-algorithm decompression engine.

    Provides actual decompression (not just detection) for various
    algorithms used in retro game ROMs.
    """

    def __init__(self):
        self._algorithms = {
            CompressionAlgorithm.RLE: self._decompress_rle,
            CompressionAlgorithm.LZSS: self._decompress_lzss,
            CompressionAlgorithm.LZ77: self._decompress_lz77,
            CompressionAlgorithm.LZ10: self._decompress_lz10,
            CompressionAlgorithm.LZ11: self._decompress_lz11,
            CompressionAlgorithm.YAY0: self._decompress_yay0,
            CompressionAlgorithm.YAZ0: self._decompress_yaz0,
        }

    def decompress(self, data: bytes, algorithm: CompressionAlgorithm,
                   params: Optional[Dict[str, Any]] = None) -> DecompressResult:
        """
        Decompress data using specified algorithm.

        Args:
            data: Compressed data
            algorithm: Algorithm to use
            params: Optional algorithm-specific parameters

        Returns:
            DecompressResult with decompressed data
        """
        if algorithm not in self._algorithms:
            return DecompressResult(
                success=False,
                algorithm=algorithm,
                error=f"Unsupported algorithm: {algorithm.value}"
            )

        try:
            return self._algorithms[algorithm](data, params or {})
        except Exception as e:
            return DecompressResult(
                success=False,
                algorithm=algorithm,
                error=str(e)
            )

    def try_all(self, data: bytes,
                algorithms: Optional[List[CompressionAlgorithm]] = None
                ) -> List[DecompressResult]:
        """
        Try all algorithms and return successful results.

        Args:
            data: Potentially compressed data
            algorithms: Optional list of algorithms to try

        Returns:
            List of successful DecompressResult sorted by confidence
        """
        to_try = algorithms or list(self._algorithms.keys())
        results = []

        for algo in to_try:
            result = self.decompress(data, algo)
            if result.success and result.decompressed_size > 0:
                results.append(result)

        # Sort by confidence (higher is better)
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    def detect_and_decompress(self, data: bytes) -> Optional[DecompressResult]:
        """
        Auto-detect compression and decompress.

        Args:
            data: Potentially compressed data

        Returns:
            Best DecompressResult or None if no algorithm works
        """
        # Check for magic numbers first
        if len(data) >= 4:
            magic = data[:4]

            if magic == b'Yay0':
                return self.decompress(data, CompressionAlgorithm.YAY0)
            elif magic == b'Yaz0':
                return self.decompress(data, CompressionAlgorithm.YAZ0)
            elif data[0] == 0x10 and len(data) >= 4:
                # Nintendo LZ10 header
                return self.decompress(data, CompressionAlgorithm.LZ10)
            elif data[0] == 0x11 and len(data) >= 4:
                # Nintendo LZ11 header
                return self.decompress(data, CompressionAlgorithm.LZ11)

        # Try all and return best
        results = self.try_all(data)
        return results[0] if results else None

    # =========================================================================
    # RLE Decompression
    # =========================================================================

    def _decompress_rle(self, data: bytes, params: Dict) -> DecompressResult:
        """
        Decompress RLE (Run-Length Encoding).

        Common variants:
        - Simple RLE: [count, value] for runs, raw bytes otherwise
        - Flag-based RLE: high bit of count indicates run vs literal
        """
        if len(data) < 2:
            return DecompressResult(
                success=False,
                algorithm=CompressionAlgorithm.RLE,
                error="Data too short"
            )

        # Try flag-based RLE (most common)
        result = self._decompress_rle_flag(data, params)
        if result.success and result.confidence >= 0.5:
            return result

        # Try simple RLE
        result = self._decompress_rle_simple(data, params)
        return result

    def _decompress_rle_flag(self, data: bytes, params: Dict) -> DecompressResult:
        """Flag-based RLE where high bit indicates run."""
        output = bytearray()
        pos = 0
        max_output = params.get('max_output', 1024 * 1024)  # 1MB default

        try:
            while pos < len(data) and len(output) < max_output:
                flag = data[pos]
                pos += 1

                if flag & 0x80:
                    # Run: high bit set
                    count = (flag & 0x7F) + 1
                    if pos >= len(data):
                        break
                    value = data[pos]
                    pos += 1
                    output.extend([value] * count)
                else:
                    # Literal: copy next (flag + 1) bytes
                    count = flag + 1
                    if pos + count > len(data):
                        break
                    output.extend(data[pos:pos + count])
                    pos += count

            if len(output) == 0:
                return DecompressResult(
                    success=False,
                    algorithm=CompressionAlgorithm.RLE,
                    error="No output produced"
                )

            # Confidence based on expansion ratio
            confidence = min(1.0, len(output) / (pos + 1))

            return DecompressResult(
                success=True,
                algorithm=CompressionAlgorithm.RLE,
                data=bytes(output),
                original_size=pos,
                decompressed_size=len(output),
                confidence=confidence,
                params={"variant": "flag_based"}
            )

        except Exception as e:
            return DecompressResult(
                success=False,
                algorithm=CompressionAlgorithm.RLE,
                error=str(e)
            )

    def _decompress_rle_simple(self, data: bytes, params: Dict) -> DecompressResult:
        """Simple RLE with escape byte."""
        output = bytearray()
        pos = 0
        escape = params.get('escape', 0xFF)
        max_output = params.get('max_output', 1024 * 1024)

        try:
            while pos < len(data) and len(output) < max_output:
                b = data[pos]
                pos += 1

                if b == escape:
                    if pos + 2 > len(data):
                        break
                    count = data[pos]
                    value = data[pos + 1]
                    pos += 2
                    output.extend([value] * count)
                else:
                    output.append(b)

            confidence = 0.3 if len(output) > len(data) else 0.1

            return DecompressResult(
                success=len(output) > 0,
                algorithm=CompressionAlgorithm.RLE,
                data=bytes(output),
                original_size=pos,
                decompressed_size=len(output),
                confidence=confidence,
                params={"variant": "simple", "escape": escape}
            )

        except Exception as e:
            return DecompressResult(
                success=False,
                algorithm=CompressionAlgorithm.RLE,
                error=str(e)
            )

    # =========================================================================
    # LZSS Decompression
    # =========================================================================

    def _decompress_lzss(self, data: bytes, params: Dict) -> DecompressResult:
        """
        Decompress LZSS (Lempel-Ziv-Storer-Szymanski).

        Common in SNES games. Uses flag byte to indicate literal vs reference.
        """
        if len(data) < 3:
            return DecompressResult(
                success=False,
                algorithm=CompressionAlgorithm.LZSS,
                error="Data too short"
            )

        output = bytearray()
        pos = 0
        window_size = params.get('window_size', 4096)
        max_output = params.get('max_output', 1024 * 1024)

        try:
            while pos < len(data) and len(output) < max_output:
                flags = data[pos]
                pos += 1

                for bit in range(8):
                    if pos >= len(data) or len(output) >= max_output:
                        break

                    if flags & (1 << bit):
                        # Literal byte
                        output.append(data[pos])
                        pos += 1
                    else:
                        # Reference: offset + length
                        if pos + 2 > len(data):
                            break

                        ref_low = data[pos]
                        ref_high = data[pos + 1]
                        pos += 2

                        # Decode offset and length (12-bit offset, 4-bit length)
                        offset = ((ref_high & 0xF0) << 4) | ref_low
                        length = (ref_high & 0x0F) + 3

                        if offset == 0:
                            offset = window_size

                        # Copy from history
                        src_pos = len(output) - offset
                        if src_pos < 0:
                            # Invalid reference, likely end of data
                            break

                        for _ in range(length):
                            if src_pos < len(output):
                                output.append(output[src_pos])
                                src_pos += 1
                            else:
                                break

            if len(output) == 0:
                return DecompressResult(
                    success=False,
                    algorithm=CompressionAlgorithm.LZSS,
                    error="No output produced"
                )

            confidence = min(1.0, len(output) / (pos + 1) * 0.7)

            return DecompressResult(
                success=True,
                algorithm=CompressionAlgorithm.LZSS,
                data=bytes(output),
                original_size=pos,
                decompressed_size=len(output),
                confidence=confidence,
                params={"window_size": window_size}
            )

        except Exception as e:
            return DecompressResult(
                success=False,
                algorithm=CompressionAlgorithm.LZSS,
                error=str(e)
            )

    # =========================================================================
    # LZ77 Decompression
    # =========================================================================

    def _decompress_lz77(self, data: bytes, params: Dict) -> DecompressResult:
        """
        Decompress generic LZ77.

        Uses sliding window with (offset, length, next_char) triples.
        """
        if len(data) < 3:
            return DecompressResult(
                success=False,
                algorithm=CompressionAlgorithm.LZ77,
                error="Data too short"
            )

        output = bytearray()
        pos = 0
        window_size = params.get('window_size', 4096)
        max_output = params.get('max_output', 1024 * 1024)

        try:
            while pos + 2 < len(data) and len(output) < max_output:
                offset = data[pos] | ((data[pos + 1] & 0xF0) << 4)
                length = data[pos + 1] & 0x0F
                pos += 2

                if length == 0:
                    # Literal byte
                    if pos >= len(data):
                        break
                    output.append(data[pos])
                    pos += 1
                else:
                    # Copy from window
                    src = len(output) - offset
                    if src < 0:
                        break
                    for _ in range(length):
                        if src < len(output):
                            output.append(output[src])
                            src += 1

            confidence = 0.5 if len(output) > len(data) else 0.3

            return DecompressResult(
                success=len(output) > 0,
                algorithm=CompressionAlgorithm.LZ77,
                data=bytes(output),
                original_size=pos,
                decompressed_size=len(output),
                confidence=confidence
            )

        except Exception as e:
            return DecompressResult(
                success=False,
                algorithm=CompressionAlgorithm.LZ77,
                error=str(e)
            )

    # =========================================================================
    # Nintendo LZ10 (GBA) Decompression
    # =========================================================================

    def _decompress_lz10(self, data: bytes, params: Dict) -> DecompressResult:
        """
        Decompress Nintendo LZ10 format (GBA BIOS compression).

        Header: 0x10, followed by 24-bit decompressed size (little-endian).
        """
        if len(data) < 4 or data[0] != 0x10:
            return DecompressResult(
                success=False,
                algorithm=CompressionAlgorithm.LZ10,
                error="Invalid LZ10 header"
            )

        # Read decompressed size (24-bit LE)
        decomp_size = data[1] | (data[2] << 8) | (data[3] << 16)
        if decomp_size == 0 or decomp_size > 16 * 1024 * 1024:  # 16MB max
            return DecompressResult(
                success=False,
                algorithm=CompressionAlgorithm.LZ10,
                error=f"Invalid decompressed size: {decomp_size}"
            )

        output = bytearray()
        pos = 4

        try:
            while len(output) < decomp_size and pos < len(data):
                flags = data[pos]
                pos += 1

                for bit in range(7, -1, -1):  # MSB first
                    if len(output) >= decomp_size or pos >= len(data):
                        break

                    if flags & (1 << bit):
                        # Reference
                        if pos + 2 > len(data):
                            break

                        ref = (data[pos] << 8) | data[pos + 1]
                        pos += 2

                        length = ((ref >> 12) & 0xF) + 3
                        offset = (ref & 0xFFF) + 1

                        src = len(output) - offset
                        if src < 0:
                            break

                        for _ in range(length):
                            if len(output) >= decomp_size:
                                break
                            if src < len(output):
                                output.append(output[src])
                                src += 1
                    else:
                        # Literal
                        output.append(data[pos])
                        pos += 1

            success = len(output) == decomp_size
            confidence = 0.9 if success else 0.5

            return DecompressResult(
                success=success,
                algorithm=CompressionAlgorithm.LZ10,
                data=bytes(output),
                original_size=pos,
                decompressed_size=len(output),
                confidence=confidence,
                params={"expected_size": decomp_size}
            )

        except Exception as e:
            return DecompressResult(
                success=False,
                algorithm=CompressionAlgorithm.LZ10,
                error=str(e)
            )

    # =========================================================================
    # Nintendo LZ11 (DS) Decompression
    # =========================================================================

    def _decompress_lz11(self, data: bytes, params: Dict) -> DecompressResult:
        """
        Decompress Nintendo LZ11 format (DS extended LZ).

        Similar to LZ10 but with extended length encoding.
        """
        if len(data) < 4 or data[0] != 0x11:
            return DecompressResult(
                success=False,
                algorithm=CompressionAlgorithm.LZ11,
                error="Invalid LZ11 header"
            )

        decomp_size = data[1] | (data[2] << 8) | (data[3] << 16)
        if decomp_size == 0 or decomp_size > 16 * 1024 * 1024:
            return DecompressResult(
                success=False,
                algorithm=CompressionAlgorithm.LZ11,
                error=f"Invalid decompressed size: {decomp_size}"
            )

        output = bytearray()
        pos = 4

        try:
            while len(output) < decomp_size and pos < len(data):
                flags = data[pos]
                pos += 1

                for bit in range(7, -1, -1):
                    if len(output) >= decomp_size or pos >= len(data):
                        break

                    if flags & (1 << bit):
                        # Reference with extended length
                        if pos >= len(data):
                            break

                        indicator = data[pos] >> 4

                        if indicator == 0:
                            # 8-bit length
                            if pos + 3 > len(data):
                                break
                            length = ((data[pos] & 0xF) << 4) | (data[pos + 1] >> 4) + 0x11
                            offset = ((data[pos + 1] & 0xF) << 8) | data[pos + 2] + 1
                            pos += 3
                        elif indicator == 1:
                            # 16-bit length
                            if pos + 4 > len(data):
                                break
                            length = (((data[pos] & 0xF) << 12) |
                                     (data[pos + 1] << 4) |
                                     (data[pos + 2] >> 4)) + 0x111
                            offset = ((data[pos + 2] & 0xF) << 8) | data[pos + 3] + 1
                            pos += 4
                        else:
                            # 4-bit length
                            if pos + 2 > len(data):
                                break
                            length = indicator + 1
                            offset = ((data[pos] & 0xF) << 8) | data[pos + 1] + 1
                            pos += 2

                        src = len(output) - offset
                        if src < 0:
                            break

                        for _ in range(length):
                            if len(output) >= decomp_size:
                                break
                            if src < len(output):
                                output.append(output[src])
                                src += 1
                    else:
                        output.append(data[pos])
                        pos += 1

            success = len(output) == decomp_size
            confidence = 0.9 if success else 0.5

            return DecompressResult(
                success=success,
                algorithm=CompressionAlgorithm.LZ11,
                data=bytes(output),
                original_size=pos,
                decompressed_size=len(output),
                confidence=confidence,
                params={"expected_size": decomp_size}
            )

        except Exception as e:
            return DecompressResult(
                success=False,
                algorithm=CompressionAlgorithm.LZ11,
                error=str(e)
            )

    # =========================================================================
    # Yay0 (N64) Decompression
    # =========================================================================

    def _decompress_yay0(self, data: bytes, params: Dict) -> DecompressResult:
        """
        Decompress Nintendo Yay0 format (N64).

        Header: "Yay0" magic, decompressed size, link table offset, chunk table offset.
        """
        if len(data) < 16 or data[:4] != b'Yay0':
            return DecompressResult(
                success=False,
                algorithm=CompressionAlgorithm.YAY0,
                error="Invalid Yay0 header"
            )

        decomp_size = struct.unpack('>I', data[4:8])[0]
        link_offset = struct.unpack('>I', data[8:12])[0]
        chunk_offset = struct.unpack('>I', data[12:16])[0]

        if decomp_size > 16 * 1024 * 1024:
            return DecompressResult(
                success=False,
                algorithm=CompressionAlgorithm.YAY0,
                error=f"Invalid decompressed size: {decomp_size}"
            )

        output = bytearray()
        code_pos = 16
        link_pos = link_offset
        chunk_pos = chunk_offset
        bits_left = 0
        code = 0

        try:
            while len(output) < decomp_size:
                if bits_left == 0:
                    if code_pos + 4 > len(data):
                        break
                    code = struct.unpack('>I', data[code_pos:code_pos + 4])[0]
                    code_pos += 4
                    bits_left = 32

                if code & 0x80000000:
                    # Literal byte from chunk data
                    if chunk_pos >= len(data):
                        break
                    output.append(data[chunk_pos])
                    chunk_pos += 1
                else:
                    # Copy from link data
                    if link_pos + 2 > len(data):
                        break
                    link = struct.unpack('>H', data[link_pos:link_pos + 2])[0]
                    link_pos += 2

                    offset = (link & 0xFFF) + 1
                    count = (link >> 12)

                    if count == 0:
                        # Extended count from chunk data
                        if chunk_pos >= len(data):
                            break
                        count = data[chunk_pos] + 0x12
                        chunk_pos += 1
                    else:
                        count += 2

                    src = len(output) - offset
                    if src < 0:
                        break

                    for _ in range(count):
                        if len(output) >= decomp_size:
                            break
                        if src < len(output):
                            output.append(output[src])
                            src += 1

                code <<= 1
                bits_left -= 1

            success = len(output) == decomp_size
            confidence = 0.95 if success else 0.6

            return DecompressResult(
                success=success,
                algorithm=CompressionAlgorithm.YAY0,
                data=bytes(output),
                original_size=len(data),
                decompressed_size=len(output),
                confidence=confidence,
                params={"expected_size": decomp_size}
            )

        except Exception as e:
            return DecompressResult(
                success=False,
                algorithm=CompressionAlgorithm.YAY0,
                error=str(e)
            )

    # =========================================================================
    # Yaz0 (GameCube/Wii) Decompression
    # =========================================================================

    def _decompress_yaz0(self, data: bytes, params: Dict) -> DecompressResult:
        """
        Decompress Nintendo Yaz0 format (GameCube/Wii, also some N64).

        Header: "Yaz0" magic, decompressed size (BE), padding.
        """
        if len(data) < 16 or data[:4] != b'Yaz0':
            return DecompressResult(
                success=False,
                algorithm=CompressionAlgorithm.YAZ0,
                error="Invalid Yaz0 header"
            )

        decomp_size = struct.unpack('>I', data[4:8])[0]
        if decomp_size > 32 * 1024 * 1024:  # 32MB max
            return DecompressResult(
                success=False,
                algorithm=CompressionAlgorithm.YAZ0,
                error=f"Invalid decompressed size: {decomp_size}"
            )

        output = bytearray()
        pos = 16
        bits_left = 0
        code = 0

        try:
            while len(output) < decomp_size and pos < len(data):
                if bits_left == 0:
                    code = data[pos]
                    pos += 1
                    bits_left = 8

                if code & 0x80:
                    # Literal byte
                    if pos >= len(data):
                        break
                    output.append(data[pos])
                    pos += 1
                else:
                    # Reference
                    if pos + 2 > len(data):
                        break

                    b1 = data[pos]
                    b2 = data[pos + 1]
                    pos += 2

                    offset = ((b1 & 0x0F) << 8) | b2
                    offset += 1

                    count = b1 >> 4
                    if count == 0:
                        # Extended count
                        if pos >= len(data):
                            break
                        count = data[pos] + 0x12
                        pos += 1
                    else:
                        count += 2

                    src = len(output) - offset
                    if src < 0:
                        break

                    for _ in range(count):
                        if len(output) >= decomp_size:
                            break
                        if src < len(output):
                            output.append(output[src])
                            src += 1

                code <<= 1
                bits_left -= 1

            success = len(output) == decomp_size
            confidence = 0.95 if success else 0.6

            return DecompressResult(
                success=success,
                algorithm=CompressionAlgorithm.YAZ0,
                data=bytes(output),
                original_size=len(data),
                decompressed_size=len(output),
                confidence=confidence,
                params={"expected_size": decomp_size}
            )

        except Exception as e:
            return DecompressResult(
                success=False,
                algorithm=CompressionAlgorithm.YAZ0,
                error=str(e)
            )


# Convenience functions
def decompress(data: bytes, algorithm: CompressionAlgorithm,
               params: Optional[Dict] = None) -> DecompressResult:
    """Decompress data using specified algorithm."""
    engine = MultiDecompress()
    return engine.decompress(data, algorithm, params)


def auto_decompress(data: bytes) -> Optional[DecompressResult]:
    """Auto-detect and decompress."""
    engine = MultiDecompress()
    return engine.detect_and_decompress(data)
