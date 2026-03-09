# -*- coding: utf-8 -*-
"""
================================================================================
CONTAINER EXTRACTOR - Archive and Filesystem Extraction
================================================================================
Extracts files from container formats used in game ROMs:
- PS1 ISO (ISO9660 + CD-XA)
- N64 ROM segments
- Generic archive formats

Essential for PS1 games where text is spread across multiple files.
================================================================================
"""

from dataclasses import dataclass, field
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union
from pathlib import Path
import struct
import io


@dataclass
class ExtractedFile:
    """A file extracted from a container."""
    path: str                    # Virtual path in container
    offset: int                  # Offset in source
    size: int                    # File size
    data: bytes = field(default_factory=bytes)
    file_type: str = "unknown"   # Detected file type
    is_compressed: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"<File {self.path} size={self.size} type={self.file_type}>"


@dataclass
class ContainerInfo:
    """Information about a container."""
    format: str                  # iso9660, n64_rom, etc.
    file_count: int
    total_size: int
    files: List[ExtractedFile] = field(default_factory=list)


class ISO9660Extractor:
    """
    Extractor for ISO9660 filesystem (PS1 discs).

    Handles standard ISO9660 and some CD-XA extensions.
    """

    SECTOR_SIZE = 2048
    SECTOR_SIZE_RAW = 2352

    def __init__(self, data: Union[bytes, BinaryIO, str, Path]):
        if isinstance(data, (str, Path)):
            with open(data, 'rb') as f:
                self.data = f.read()
        elif isinstance(data, bytes):
            self.data = data
        else:
            self.data = data.read()

        self._is_raw = len(self.data) % self.SECTOR_SIZE_RAW == 0
        self._files: List[ExtractedFile] = []

    def _read_sector(self, sector_num: int) -> bytes:
        """Read a sector from the ISO."""
        if self._is_raw:
            # Raw sector: skip sync and header
            offset = sector_num * self.SECTOR_SIZE_RAW + 16
            return self.data[offset:offset + self.SECTOR_SIZE]
        else:
            offset = sector_num * self.SECTOR_SIZE
            return self.data[offset:offset + self.SECTOR_SIZE]

    def extract(self) -> ContainerInfo:
        """
        Extract all files from ISO.

        Returns:
            ContainerInfo with all extracted files
        """
        # Read primary volume descriptor (sector 16)
        pvd = self._read_sector(16)

        if pvd[0:1] != b'\x01' or pvd[1:6] != b'CD001':
            raise ValueError("Not a valid ISO9660 image")

        # Root directory record is at offset 156
        root_record = pvd[156:190]
        root_lba = struct.unpack('<I', root_record[2:6])[0]
        root_size = struct.unpack('<I', root_record[10:14])[0]

        # Parse directory tree
        self._parse_directory(root_lba, root_size, "")

        return ContainerInfo(
            format="iso9660",
            file_count=len(self._files),
            total_size=sum(f.size for f in self._files),
            files=self._files,
        )

    def _parse_directory(self, lba: int, size: int, path: str) -> None:
        """Parse a directory and its contents."""
        sectors_needed = (size + self.SECTOR_SIZE - 1) // self.SECTOR_SIZE
        data = b''

        for i in range(sectors_needed):
            data += self._read_sector(lba + i)

        offset = 0
        while offset < size:
            record_len = data[offset]
            if record_len == 0:
                # Padding at end of sector
                next_sector = ((offset // self.SECTOR_SIZE) + 1) * self.SECTOR_SIZE
                if next_sector >= size:
                    break
                offset = next_sector
                continue

            # Parse directory record
            file_lba = struct.unpack('<I', data[offset + 2:offset + 6])[0]
            file_size = struct.unpack('<I', data[offset + 10:offset + 14])[0]
            flags = data[offset + 25]
            name_len = data[offset + 32]
            name = data[offset + 33:offset + 33 + name_len].decode('ascii', errors='replace')

            # Clean up name
            if ';' in name:
                name = name.split(';')[0]

            is_directory = bool(flags & 0x02)

            if name not in ('.', '..', '\x00', '\x01'):
                full_path = f"{path}/{name}" if path else name

                if is_directory:
                    self._parse_directory(file_lba, file_size, full_path)
                else:
                    file_data = self._read_file(file_lba, file_size)
                    file_type = self._detect_file_type(file_data, name)

                    self._files.append(ExtractedFile(
                        path=full_path,
                        offset=file_lba * self.SECTOR_SIZE,
                        size=file_size,
                        data=file_data,
                        file_type=file_type,
                    ))

            offset += record_len

    def _read_file(self, lba: int, size: int) -> bytes:
        """Read file data from sectors."""
        sectors_needed = (size + self.SECTOR_SIZE - 1) // self.SECTOR_SIZE
        data = b''

        for i in range(sectors_needed):
            data += self._read_sector(lba + i)

        return data[:size]

    def _detect_file_type(self, data: bytes, name: str) -> str:
        """Detect file type from data and name."""
        name_lower = name.lower()

        # By extension
        if name_lower.endswith('.exe') or name_lower.endswith('.bin'):
            if data[:8] == b'PS-X EXE':
                return 'ps1_exe'
            return 'executable'
        elif name_lower.endswith('.tim'):
            return 'tim_image'
        elif name_lower.endswith('.vab') or name_lower.endswith('.vh'):
            return 'audio'
        elif name_lower.endswith('.seq'):
            return 'sequence'
        elif name_lower.endswith('.dat') or name_lower.endswith('.bin'):
            return 'data'

        # By magic
        if len(data) >= 4:
            if data[:4] == b'\x10\x00\x00\x00':
                return 'tim_image'
            elif data[:8] == b'PS-X EXE':
                return 'ps1_exe'

        return 'unknown'


class N64SegmentExtractor:
    """
    Extractor for N64 ROM segments.

    N64 ROMs often have segment tables that define loadable regions.
    """

    def __init__(self, data: bytes):
        self.data = data
        self._segments: List[ExtractedFile] = []
        self._endian = self._detect_endian()

    def _detect_endian(self) -> str:
        """Detect ROM byte order."""
        if len(self.data) < 4:
            return 'big'

        magic = struct.unpack('>I', self.data[:4])[0]

        if magic == 0x80371240:
            return 'big'
        elif magic == 0x40123780:
            return 'little'  # Byteswapped
        elif magic == 0x12408037:
            return 'mixed'   # Wordswapped

        return 'big'

    def _fix_endian(self, data: bytes) -> bytes:
        """Fix byte order if needed."""
        if self._endian == 'big':
            return data
        elif self._endian == 'little':
            # Swap bytes
            result = bytearray(len(data))
            for i in range(0, len(data) - 1, 2):
                result[i] = data[i + 1]
                result[i + 1] = data[i]
            return bytes(result)
        elif self._endian == 'mixed':
            # Swap words
            result = bytearray(len(data))
            for i in range(0, len(data) - 3, 4):
                result[i:i + 2] = data[i + 2:i + 4]
                result[i + 2:i + 4] = data[i:i + 2]
            return bytes(result)

        return data

    def extract(self) -> ContainerInfo:
        """
        Extract segments from N64 ROM.

        Returns:
            ContainerInfo with segments
        """
        # Fix endianness first
        fixed_data = self._fix_endian(self.data)

        # Look for segment tables
        # Common locations: after header, at specific offsets
        self._scan_for_segments(fixed_data)

        # Also extract compressed blocks
        self._scan_for_compressed(fixed_data)

        return ContainerInfo(
            format="n64_rom",
            file_count=len(self._segments),
            total_size=sum(s.size for s in self._segments),
            files=self._segments,
        )

    def _scan_for_segments(self, data: bytes) -> None:
        """Scan for segment table entries."""
        # Typical segment entry: ROM offset (4), VRAM address (4), size (4)

        for offset in range(0x1000, min(len(data) - 12, 0x10000), 4):
            rom_offset = struct.unpack('>I', data[offset:offset + 4])[0]
            vram_addr = struct.unpack('>I', data[offset + 4:offset + 8])[0]
            size = struct.unpack('>I', data[offset + 8:offset + 12])[0]

            # Validate segment entry
            if (rom_offset > 0 and rom_offset < len(data) and
                0x80000000 <= vram_addr <= 0x807FFFFF and
                0 < size < 0x800000 and
                rom_offset + size <= len(data)):

                segment_data = data[rom_offset:rom_offset + size]

                self._segments.append(ExtractedFile(
                    path=f"segment_{offset:06X}",
                    offset=rom_offset,
                    size=size,
                    data=segment_data,
                    file_type='segment',
                    extra={'vram': vram_addr},
                ))

    def _scan_for_compressed(self, data: bytes) -> None:
        """Scan for compressed blocks (Yay0, Yaz0)."""
        for magic, name in [(b'Yay0', 'yay0'), (b'Yaz0', 'yaz0')]:
            offset = 0
            while True:
                idx = data.find(magic, offset)
                if idx == -1:
                    break

                if idx + 16 <= len(data):
                    decomp_size = struct.unpack('>I', data[idx + 4:idx + 8])[0]

                    if decomp_size > 0 and decomp_size < 0x1000000:
                        # Estimate compressed size
                        comp_size = min(decomp_size, len(data) - idx)

                        self._segments.append(ExtractedFile(
                            path=f"{name}_{idx:06X}",
                            offset=idx,
                            size=comp_size,
                            data=data[idx:idx + comp_size],
                            file_type=name,
                            is_compressed=True,
                            extra={'decomp_size': decomp_size},
                        ))

                offset = idx + 4


class ContainerExtractor:
    """
    Universal container extractor.

    Auto-detects container format and extracts files.
    """

    def __init__(self, data: Union[bytes, BinaryIO, str, Path]):
        if isinstance(data, (str, Path)):
            with open(data, 'rb') as f:
                self.data = f.read()
        elif isinstance(data, bytes):
            self.data = data
        else:
            self.data = data.read()

    def detect_format(self) -> str:
        """Detect container format."""
        # Check for ISO9660
        if len(self.data) >= 32768 + 6:
            # Primary volume descriptor at sector 16
            offset = 16 * 2048
            if self.data[offset + 1:offset + 6] == b'CD001':
                return 'iso9660'

            # Check raw sector format
            offset = 16 * 2352 + 16
            if offset + 6 <= len(self.data):
                if self.data[offset + 1:offset + 6] == b'CD001':
                    return 'iso9660_raw'

        # Check for N64 ROM
        if len(self.data) >= 4:
            magic = struct.unpack('>I', self.data[:4])[0]
            if magic in (0x80371240, 0x40123780, 0x12408037):
                return 'n64_rom'

        return 'unknown'

    def extract(self) -> ContainerInfo:
        """
        Extract files from container.

        Returns:
            ContainerInfo with all extracted files
        """
        format_type = self.detect_format()

        if format_type in ('iso9660', 'iso9660_raw'):
            extractor = ISO9660Extractor(self.data)
            return extractor.extract()

        elif format_type == 'n64_rom':
            extractor = N64SegmentExtractor(self.data)
            return extractor.extract()

        else:
            return ContainerInfo(
                format='unknown',
                file_count=0,
                total_size=len(self.data),
                files=[],
            )

    def get_file(self, path: str) -> Optional[ExtractedFile]:
        """Get a specific file by path."""
        info = self.extract()
        for f in info.files:
            if f.path == path or f.path.endswith(path):
                return f
        return None

    def get_files_by_type(self, file_type: str) -> List[ExtractedFile]:
        """Get all files of a specific type."""
        info = self.extract()
        return [f for f in info.files if f.file_type == file_type]

    def get_text_candidates(self) -> List[ExtractedFile]:
        """Get files likely to contain text."""
        info = self.extract()
        text_types = {'data', 'unknown', 'executable', 'ps1_exe'}
        return [f for f in info.files
                if f.file_type in text_types and f.size >= 64]


def extract_container(data: Union[bytes, str, Path]) -> ContainerInfo:
    """
    Convenience function to extract a container.

    Args:
        data: Container data, file path, or Path object

    Returns:
        ContainerInfo with extracted files
    """
    extractor = ContainerExtractor(data)
    return extractor.extract()
