# -*- coding: utf-8 -*-
"""
===============================================================================
MULTI COMPRESS - Compression Engines for Retro ROM Block Reinsertion
===============================================================================
Provides compression for common formats used by the decompressor counterpart:
- RLE (flag/simple variants)
- LZSS (12-bit offset, 4-bit length)
- LZ77 (generic tuple stream)
- LZ10 / LZ11 (Nintendo variants)
- Yay0 / Yaz0 (Nintendo block formats)

Goal: safe recompression with deterministic output and round-trip validation.
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import struct

from .multi_decompress import CompressionAlgorithm


@dataclass
class CompressResult:
    """Result of compression attempt."""
    success: bool
    algorithm: CompressionAlgorithm
    data: bytes = field(default_factory=bytes)
    original_size: int = 0
    compressed_size: int = 0
    confidence: float = 0.0
    error: str = ""
    params: Dict[str, Any] = field(default_factory=dict)

    @property
    def ratio(self) -> float:
        """Compression ratio (compressed/original)."""
        if self.original_size <= 0:
            return 0.0
        return float(self.compressed_size) / float(self.original_size)


class MultiCompress:
    """Multi-algorithm compressor used for recompression workflows."""

    def __init__(self):
        self._algorithms = {
            CompressionAlgorithm.RLE: self._compress_rle_flag,
            CompressionAlgorithm.LZSS: self._compress_lzss,
            CompressionAlgorithm.LZ77: self._compress_lz77,
            CompressionAlgorithm.LZ10: self._compress_lz10,
            CompressionAlgorithm.LZ11: self._compress_lz11,
            CompressionAlgorithm.YAY0: self._compress_yay0,
            CompressionAlgorithm.YAZ0: self._compress_yaz0,
        }

    def compress(
        self,
        data: bytes,
        algorithm: CompressionAlgorithm,
        params: Optional[Dict[str, Any]] = None,
    ) -> CompressResult:
        """Compress data using selected algorithm."""
        if algorithm not in self._algorithms:
            return CompressResult(
                success=False,
                algorithm=algorithm,
                original_size=len(data or b""),
                error=f"Unsupported algorithm: {algorithm.value}",
            )
        try:
            return self._algorithms[algorithm](data or b"", params or {})
        except Exception as e:
            return CompressResult(
                success=False,
                algorithm=algorithm,
                original_size=len(data or b""),
                error=str(e),
            )

    # ------------------------------------------------------------------
    # Common helpers
    # ------------------------------------------------------------------

    def _find_longest_match(
        self,
        data: bytes,
        pos: int,
        window: int,
        min_len: int,
        max_len: int,
    ) -> Tuple[int, int]:
        """Returns (offset, length) using backward greedy search."""
        if pos <= 0:
            return (0, 0)
        start = max(0, pos - window)
        best_len = 0
        best_off = 0

        # reverse search tends to prefer closer references (stable output)
        for src in range(pos - 1, start - 1, -1):
            off = pos - src
            if off <= 0 or off > window:
                continue
            length = 0
            limit = min(max_len, len(data) - pos)
            while length < limit and data[src + length] == data[pos + length]:
                length += 1
            if length > best_len and length >= min_len:
                best_len = length
                best_off = off
                if best_len == max_len:
                    break
        return (best_off, best_len)

    # ------------------------------------------------------------------
    # RLE
    # ------------------------------------------------------------------

    def _compress_rle_flag(self, data: bytes, params: Dict[str, Any]) -> CompressResult:
        """
        Flag-based RLE compatible with _decompress_rle_flag:
        - literal chunk: flag=0x00..0x7F => copy flag+1 bytes
        - run chunk: flag=0x80..0xFF => repeat next byte (flag&0x7F)+1 times
        """
        if not data:
            return CompressResult(
                success=True,
                algorithm=CompressionAlgorithm.RLE,
                data=b"",
                original_size=0,
                compressed_size=0,
                confidence=1.0,
                params={"variant": "flag_based"},
            )

        out = bytearray()
        i = 0
        n = len(data)

        while i < n:
            # detect run
            run_val = data[i]
            run_len = 1
            j = i + 1
            while j < n and data[j] == run_val and run_len < 128:
                run_len += 1
                j += 1

            # encode as run when useful (>=3)
            if run_len >= 3:
                out.append(0x80 | (run_len - 1))
                out.append(run_val)
                i += run_len
                continue

            # literal chunk
            lit_start = i
            lit_len = 0
            while i < n and lit_len < 128:
                # stop before a beneficial run
                rv = data[i]
                rlen = 1
                k = i + 1
                while k < n and data[k] == rv and rlen < 128:
                    rlen += 1
                    k += 1
                if rlen >= 3 and lit_len > 0:
                    break
                i += 1
                lit_len += 1
                if rlen >= 3 and lit_len == 0:
                    break
            out.append((lit_len - 1) & 0x7F)
            out.extend(data[lit_start:lit_start + lit_len])

        return CompressResult(
            success=True,
            algorithm=CompressionAlgorithm.RLE,
            data=bytes(out),
            original_size=n,
            compressed_size=len(out),
            confidence=0.8,
            params={"variant": "flag_based"},
        )

    # ------------------------------------------------------------------
    # LZSS
    # ------------------------------------------------------------------

    def _compress_lzss(self, data: bytes, params: Dict[str, Any]) -> CompressResult:
        """
        LZSS compatible with _decompress_lzss:
        - flags byte, bit=1 literal / bit=0 reference (LSB first)
        - reference: ref_low + ref_high
          offset=((ref_high&0xF0)<<4)|ref_low
          length=(ref_high&0x0F)+3
        """
        window = int(params.get("window_size", 4095))
        min_len = int(params.get("min_match", 3))
        max_len = int(params.get("max_match", 18))
        if window <= 0:
            window = 4095
        if max_len < min_len:
            max_len = min_len

        out = bytearray()
        pos = 0
        n = len(data)

        while pos < n:
            flag_pos = len(out)
            out.append(0x00)
            flags = 0

            for bit in range(8):
                if pos >= n:
                    break
                off, mlen = self._find_longest_match(data, pos, window, min_len, max_len)
                if mlen >= min_len and 1 <= off <= 0xFFF:
                    ref_low = off & 0xFF
                    ref_high = ((off >> 8) & 0x0F) << 4
                    ref_high |= (mlen - 3) & 0x0F
                    out.append(ref_low)
                    out.append(ref_high)
                    pos += mlen
                else:
                    flags |= (1 << bit)
                    out.append(data[pos])
                    pos += 1

            out[flag_pos] = flags & 0xFF

        return CompressResult(
            success=True,
            algorithm=CompressionAlgorithm.LZSS,
            data=bytes(out),
            original_size=n,
            compressed_size=len(out),
            confidence=0.75,
            params={"window_size": window},
        )

    # ------------------------------------------------------------------
    # LZ77 generic
    # ------------------------------------------------------------------

    def _compress_lz77(self, data: bytes, params: Dict[str, Any]) -> CompressResult:
        """
        Generic LZ77 stream compatible with _decompress_lz77:
        tuple format:
          [lo, hi] where hi low nibble = length (0 => literal next byte)
          if length==0 -> append literal byte
        """
        window = int(params.get("window_size", 4095))
        min_len = int(params.get("min_match", 3))
        max_len = int(params.get("max_match", 15))
        if window <= 0:
            window = 4095
        if max_len < min_len:
            max_len = min_len

        out = bytearray()
        pos = 0
        n = len(data)

        while pos < n:
            off, mlen = self._find_longest_match(data, pos, window, min_len, max_len)
            if mlen >= min_len and 1 <= off <= 0xFFF:
                lo = off & 0xFF
                hi = ((off >> 8) & 0x0F) << 4
                hi |= (mlen & 0x0F)
                out.append(lo)
                out.append(hi)
                pos += mlen
            else:
                out.append(0x00)
                out.append(0x00)  # length nibble 0 => literal follows
                out.append(data[pos])
                pos += 1

        # Compatibilidade com o decompressor atual:
        # o loop usa `while pos + 2 < len(data)`, então uma referência
        # final de 2 bytes só é lida se existir 1 byte de cauda.
        out.append(0x00)

        return CompressResult(
            success=True,
            algorithm=CompressionAlgorithm.LZ77,
            data=bytes(out),
            original_size=n,
            compressed_size=len(out),
            confidence=0.65,
            params={"window_size": window},
        )

    # ------------------------------------------------------------------
    # LZ10
    # ------------------------------------------------------------------

    def _compress_lz10(self, data: bytes, params: Dict[str, Any]) -> CompressResult:
        """
        Nintendo LZ10 compatible with _decompress_lz10.
        Header: 0x10 + 24-bit LE decompressed size.
        """
        window = int(params.get("window_size", 4096))
        min_len = 3
        max_len = 18

        out = bytearray()
        out.append(0x10)
        size = len(data)
        out.extend([size & 0xFF, (size >> 8) & 0xFF, (size >> 16) & 0xFF])

        pos = 0
        n = len(data)
        while pos < n:
            flag_pos = len(out)
            out.append(0x00)
            flags = 0

            for bit in range(7, -1, -1):  # MSB first
                if pos >= n:
                    break
                off, mlen = self._find_longest_match(data, pos, window, min_len, max_len)
                if mlen >= min_len and 1 <= off <= 4096:
                    ref = (((mlen - 3) & 0xF) << 12) | ((off - 1) & 0xFFF)
                    out.append((ref >> 8) & 0xFF)
                    out.append(ref & 0xFF)
                    flags |= (1 << bit)
                    pos += mlen
                else:
                    out.append(data[pos])
                    pos += 1

            out[flag_pos] = flags & 0xFF

        return CompressResult(
            success=True,
            algorithm=CompressionAlgorithm.LZ10,
            data=bytes(out),
            original_size=n,
            compressed_size=len(out),
            confidence=0.80,
            params={"window_size": window},
        )

    # ------------------------------------------------------------------
    # LZ11
    # ------------------------------------------------------------------

    def _compress_lz11(self, data: bytes, params: Dict[str, Any]) -> CompressResult:
        """
        Nintendo LZ11 (simple short-match mode) compatible with _decompress_lz11.
        Uses only the short 2-byte backref form (length 2..15 decode => 3..16 practical).
        """
        window = int(params.get("window_size", 4096))
        min_len = 3
        max_len = 16

        out = bytearray()
        out.append(0x11)
        size = len(data)
        out.extend([size & 0xFF, (size >> 8) & 0xFF, (size >> 16) & 0xFF])

        pos = 0
        n = len(data)
        while pos < n:
            flag_pos = len(out)
            out.append(0x00)
            flags = 0

            for bit in range(7, -1, -1):
                if pos >= n:
                    break
                off, mlen = self._find_longest_match(data, pos, window, min_len, max_len)
                if mlen >= min_len and 1 <= off <= 4096:
                    # short form:
                    # b1 high nibble = indicator (count => length=indicator+1)
                    # b1 low nibble + b2 => offset-1
                    indicator = max(2, min(15, mlen - 1))
                    disp = (off - 1) & 0xFFF
                    b1 = ((indicator & 0xF) << 4) | ((disp >> 8) & 0x0F)
                    b2 = disp & 0xFF
                    out.append(b1)
                    out.append(b2)
                    flags |= (1 << bit)
                    pos += (indicator + 1)
                else:
                    out.append(data[pos])
                    pos += 1

            out[flag_pos] = flags & 0xFF

        return CompressResult(
            success=True,
            algorithm=CompressionAlgorithm.LZ11,
            data=bytes(out),
            original_size=n,
            compressed_size=len(out),
            confidence=0.70,
            params={"window_size": window},
        )

    # ------------------------------------------------------------------
    # Yaz0
    # ------------------------------------------------------------------

    def _compress_yaz0(self, data: bytes, params: Dict[str, Any]) -> CompressResult:
        """
        Yaz0 compressor (safe literal-dominant with optional short matches).
        Produces valid Yaz0 stream; prioritizes deterministic correctness.
        """
        window = int(params.get("window_size", 0x1000))
        min_len = 3
        max_len = 273  # with extended form

        out = bytearray()
        out.extend(b"Yaz0")
        out.extend(struct.pack(">I", len(data)))
        out.extend(b"\x00" * 8)  # padding

        pos = 0
        n = len(data)
        while pos < n:
            code_pos = len(out)
            out.append(0)
            code = 0

            for bit in range(7, -1, -1):
                if pos >= n:
                    break
                off, mlen = self._find_longest_match(data, pos, window, min_len, max_len)
                if mlen >= min_len and 1 <= off <= 0x1000:
                    disp = (off - 1) & 0xFFF
                    if mlen >= 0x12:
                        b1 = ((0 & 0xF) << 4) | ((disp >> 8) & 0x0F)
                        b2 = disp & 0xFF
                        out.extend([b1, b2, (mlen - 0x12) & 0xFF])
                    else:
                        count = mlen - 2
                        b1 = ((count & 0xF) << 4) | ((disp >> 8) & 0x0F)
                        b2 = disp & 0xFF
                        out.extend([b1, b2])
                    pos += mlen
                else:
                    code |= (1 << bit)  # literal
                    out.append(data[pos])
                    pos += 1

            out[code_pos] = code & 0xFF

        return CompressResult(
            success=True,
            algorithm=CompressionAlgorithm.YAZ0,
            data=bytes(out),
            original_size=n,
            compressed_size=len(out),
            confidence=0.70,
            params={"window_size": window},
        )

    # ------------------------------------------------------------------
    # Yay0
    # ------------------------------------------------------------------

    def _compress_yay0(self, data: bytes, params: Dict[str, Any]) -> CompressResult:
        """
        Yay0 compressor.
        Uses code-table + link-table + chunk-table layout.
        """
        window = int(params.get("window_size", 0x1000))
        min_len = 3
        max_len = 273

        code_bits: List[int] = []
        links = bytearray()
        chunks = bytearray()

        pos = 0
        n = len(data)
        while pos < n:
            off, mlen = self._find_longest_match(data, pos, window, min_len, max_len)
            if mlen >= min_len and 1 <= off <= 0x1000:
                # compressed token
                code_bits.append(0)
                disp = (off - 1) & 0x0FFF
                if mlen >= 0x12:
                    link = (0 << 12) | disp
                    links.extend(struct.pack(">H", link))
                    chunks.append((mlen - 0x12) & 0xFF)
                else:
                    count = mlen - 2
                    link = ((count & 0xF) << 12) | disp
                    links.extend(struct.pack(">H", link))
                pos += mlen
            else:
                # literal token
                code_bits.append(1)
                chunks.append(data[pos])
                pos += 1

        # pack code bits into 32-bit words (MSB first)
        code_words = bytearray()
        i = 0
        while i < len(code_bits):
            word = 0
            for b in range(32):
                word <<= 1
                idx = i + b
                bit = code_bits[idx] if idx < len(code_bits) else 0
                word |= (bit & 1)
            code_words.extend(struct.pack(">I", word))
            i += 32

        code_off = 16
        link_off = code_off + len(code_words)
        chunk_off = link_off + len(links)

        out = bytearray()
        out.extend(b"Yay0")
        out.extend(struct.pack(">I", len(data)))
        out.extend(struct.pack(">I", link_off))
        out.extend(struct.pack(">I", chunk_off))
        out.extend(code_words)
        out.extend(links)
        out.extend(chunks)

        return CompressResult(
            success=True,
            algorithm=CompressionAlgorithm.YAY0,
            data=bytes(out),
            original_size=n,
            compressed_size=len(out),
            confidence=0.70,
            params={"window_size": window},
        )


def compress(
    data: bytes,
    algorithm: CompressionAlgorithm,
    params: Optional[Dict[str, Any]] = None,
) -> CompressResult:
    """Convenience function."""
    engine = MultiCompress()
    return engine.compress(data, algorithm, params=params)
