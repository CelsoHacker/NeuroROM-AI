# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT OPCODE MINER - Script Command Detection for ROM Text
================================================================================
Detects and parses script command patterns in ROMs to find text that is
embedded in scripting systems rather than simple pointer tables.

Promotes opcodes when success_rate >= 0.60 and run >= 16.
================================================================================
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import Counter, defaultdict
from enum import Enum


class OpcodeType(Enum):
    """Types of script opcodes."""
    TEXT_START = "text_start"      # Indicates text follows
    TEXT_END = "text_end"          # Indicates end of text
    CHOICE = "choice"              # Player choice/menu
    WAIT = "wait"                  # Wait for input
    NEWLINE = "newline"            # Line break
    CLEAR = "clear"                # Clear text box
    NAME = "name"                  # Character name reference
    VARIABLE = "variable"          # Variable insertion
    CONTROL = "control"            # Generic control code
    UNKNOWN = "unknown"


@dataclass
class OpcodePattern:
    """A detected opcode pattern."""
    opcode: int
    opcode_type: OpcodeType
    has_arg: bool = False
    arg_size: int = 0              # Size of argument in bytes
    success_rate: float = 0.0      # Rate of successful text extraction after opcode
    occurrence_count: int = 0
    confidence: float = 0.0
    text_follows: bool = False     # True if text follows this opcode
    terminates_text: bool = False  # True if this ends a text block

    def __repr__(self) -> str:
        return (f"<Opcode 0x{self.opcode:02X} type={self.opcode_type.value} "
                f"rate={self.success_rate:.2f} n={self.occurrence_count}>")


@dataclass
class ScriptBlock:
    """A detected script block with text."""
    offset: int
    end_offset: int
    opcodes: List[Tuple[int, int, OpcodePattern]]  # (offset, value, pattern)
    text_segments: List[Tuple[int, bytes]]  # (offset, text_bytes)
    confidence: float = 0.0


class ScriptOpcodeMiner:
    """
    Mines script opcodes from ROM data to find text in scripted systems.

    Many games use custom scripting systems where text is embedded between
    control codes. This miner detects those patterns without prior knowledge.
    """

    # Promotion thresholds
    MIN_SUCCESS_RATE = 0.60
    MIN_OCCURRENCES = 16

    def __init__(self, rom_data: bytes):
        self.rom_data = rom_data
        self._candidate_opcodes: Dict[int, OpcodePattern] = {}
        self._promoted_opcodes: Dict[int, OpcodePattern] = {}
        self._script_blocks: List[ScriptBlock] = []

    def mine(self,
             scan_regions: Optional[List[Tuple[int, int]]] = None,
             text_validator: Optional[callable] = None) -> List[OpcodePattern]:
        """
        Mine for script opcodes in ROM.

        Args:
            scan_regions: Optional list of (start, end) regions to scan
            text_validator: Optional function to validate text quality

        Returns:
            List of promoted OpcodePattern
        """
        regions = scan_regions or [(0, len(self.rom_data))]

        # Phase 1: Find candidate opcodes
        self._find_candidates(regions)

        # Phase 2: Analyze candidates for text patterns
        self._analyze_candidates(regions, text_validator)

        # Phase 3: Promote high-confidence opcodes
        self._promote_candidates()

        return list(self._promoted_opcodes.values())

    def _find_candidates(self, regions: List[Tuple[int, int]]) -> None:
        """Find candidate opcode bytes based on frequency patterns."""
        byte_contexts: Dict[int, List[Tuple[int, bytes]]] = defaultdict(list)

        for start, end in regions:
            for offset in range(start, min(end, len(self.rom_data) - 4)):
                byte_val = self.rom_data[offset]

                # Skip common ASCII range for text
                if 0x20 <= byte_val <= 0x7E:
                    continue

                # Store context around this byte
                context_start = max(0, offset - 2)
                context_end = min(len(self.rom_data), offset + 10)
                context = self.rom_data[context_start:context_end]
                byte_contexts[byte_val].append((offset, context))

        # Bytes that appear often in specific patterns are candidate opcodes
        for byte_val, contexts in byte_contexts.items():
            if len(contexts) >= self.MIN_OCCURRENCES:
                self._candidate_opcodes[byte_val] = OpcodePattern(
                    opcode=byte_val,
                    opcode_type=OpcodeType.UNKNOWN,
                    occurrence_count=len(contexts),
                )

    def _analyze_candidates(self,
                            regions: List[Tuple[int, int]],
                            text_validator: Optional[callable]) -> None:
        """Analyze candidates for text-related patterns."""
        for opcode, pattern in self._candidate_opcodes.items():
            text_success = 0
            text_attempts = 0
            terminates = 0
            has_text_after = 0

            for start, end in regions:
                for offset in range(start, min(end, len(self.rom_data) - 32)):
                    if self.rom_data[offset] != opcode:
                        continue

                    # Check if text follows this opcode
                    text_start = offset + 1

                    # Skip potential argument bytes
                    arg_offset = text_start
                    while arg_offset < min(offset + 4, len(self.rom_data)):
                        if 0x20 <= self.rom_data[arg_offset] <= 0x7E:
                            break
                        arg_offset += 1

                    # Try to extract text
                    text_bytes = self._extract_text_after(arg_offset, 64)
                    if text_bytes:
                        text_attempts += 1

                        # Validate text quality
                        is_valid = True
                        if text_validator:
                            is_valid = text_validator(text_bytes)
                        else:
                            is_valid = self._basic_text_check(text_bytes)

                        if is_valid:
                            text_success += 1
                            has_text_after += 1

                    # Check if this might terminate text
                    if offset > 0:
                        prev_text = self._extract_text_before(offset, 32)
                        if prev_text and self._basic_text_check(prev_text):
                            terminates += 1

            # Update pattern statistics
            if text_attempts > 0:
                pattern.success_rate = text_success / text_attempts
                pattern.text_follows = has_text_after > text_attempts * 0.5
                pattern.terminates_text = terminates > pattern.occurrence_count * 0.3

            # Classify opcode type
            pattern.opcode_type = self._classify_opcode(pattern)

    def _extract_text_after(self, offset: int, max_len: int) -> Optional[bytes]:
        """Extract text bytes after offset."""
        if offset >= len(self.rom_data):
            return None

        text = bytearray()
        pos = offset

        while pos < min(offset + max_len, len(self.rom_data)):
            byte = self.rom_data[pos]

            if byte == 0x00:  # Null terminator
                break
            elif 0x20 <= byte <= 0x7E:  # Printable ASCII
                text.append(byte)
            elif byte in (0x0A, 0x0D):  # Newlines
                text.append(byte)
            else:
                # Non-text byte
                if len(text) >= 3:
                    break
                else:
                    return None

            pos += 1

        return bytes(text) if len(text) >= 3 else None

    def _extract_text_before(self, offset: int, max_len: int) -> Optional[bytes]:
        """Extract text bytes before offset."""
        if offset <= 0:
            return None

        text = bytearray()
        pos = offset - 1

        while pos >= max(0, offset - max_len):
            byte = self.rom_data[pos]

            if byte == 0x00:
                break
            elif 0x20 <= byte <= 0x7E:
                text.insert(0, byte)
            elif byte in (0x0A, 0x0D):
                text.insert(0, byte)
            else:
                if len(text) >= 3:
                    break
                else:
                    return None

            pos -= 1

        return bytes(text) if len(text) >= 3 else None

    def _basic_text_check(self, data: bytes) -> bool:
        """Basic check if data looks like text."""
        if len(data) < 3:
            return False

        printable = sum(1 for b in data if 0x20 <= b <= 0x7E or b in (0x0A, 0x0D))
        letters = sum(1 for b in data if 0x41 <= b <= 0x5A or 0x61 <= b <= 0x7A)

        printable_ratio = printable / len(data)
        letter_ratio = letters / len(data)

        return printable_ratio >= 0.8 and letter_ratio >= 0.3

    def _classify_opcode(self, pattern: OpcodePattern) -> OpcodeType:
        """Classify opcode based on observed behavior."""
        if pattern.text_follows and pattern.success_rate >= 0.7:
            return OpcodeType.TEXT_START
        elif pattern.terminates_text:
            return OpcodeType.TEXT_END
        elif pattern.opcode in (0x0A, 0x0D):
            return OpcodeType.NEWLINE
        elif pattern.opcode == 0x00:
            return OpcodeType.TEXT_END
        else:
            return OpcodeType.CONTROL

    def _promote_candidates(self) -> None:
        """Promote high-confidence candidates to active opcodes."""
        for opcode, pattern in self._candidate_opcodes.items():
            if (pattern.success_rate >= self.MIN_SUCCESS_RATE and
                pattern.occurrence_count >= self.MIN_OCCURRENCES):

                pattern.confidence = pattern.success_rate
                self._promoted_opcodes[opcode] = pattern

    def extract_script_blocks(self,
                               regions: Optional[List[Tuple[int, int]]] = None
                               ) -> List[ScriptBlock]:
        """
        Extract script blocks using promoted opcodes.

        Args:
            regions: Optional regions to scan

        Returns:
            List of ScriptBlock with text segments
        """
        if not self._promoted_opcodes:
            self.mine(regions)

        blocks = []
        regions = regions or [(0, len(self.rom_data))]

        text_start_opcodes = {
            op for op, pat in self._promoted_opcodes.items()
            if pat.opcode_type == OpcodeType.TEXT_START
        }

        text_end_opcodes = {
            op for op, pat in self._promoted_opcodes.items()
            if pat.opcode_type == OpcodeType.TEXT_END
        }
        text_end_opcodes.add(0x00)  # Always include null terminator

        for start, end in regions:
            offset = start
            while offset < end:
                byte = self.rom_data[offset]

                if byte in text_start_opcodes:
                    # Found potential script block start
                    block = self._parse_script_block(
                        offset, end, text_end_opcodes
                    )
                    if block and block.text_segments:
                        blocks.append(block)
                        offset = block.end_offset
                        continue

                offset += 1

        self._script_blocks = blocks
        return blocks

    def _parse_script_block(self,
                            start: int,
                            max_end: int,
                            end_opcodes: Set[int]) -> Optional[ScriptBlock]:
        """Parse a script block starting at offset."""
        opcodes = []
        text_segments = []
        offset = start

        while offset < min(max_end, start + 4096):  # Max block size
            byte = self.rom_data[offset]

            if byte in self._promoted_opcodes:
                pattern = self._promoted_opcodes[byte]
                opcodes.append((offset, byte, pattern))

                if byte in end_opcodes:
                    break

                offset += 1 + pattern.arg_size
            elif 0x20 <= byte <= 0x7E or byte in (0x0A, 0x0D):
                # Text data
                text_start = offset
                while offset < min(max_end, start + 4096):
                    b = self.rom_data[offset]
                    if not (0x20 <= b <= 0x7E or b in (0x0A, 0x0D)):
                        break
                    offset += 1

                if offset > text_start:
                    text_bytes = self.rom_data[text_start:offset]
                    if len(text_bytes) >= 3:
                        text_segments.append((text_start, text_bytes))
            else:
                offset += 1

        if not text_segments:
            return None

        # Calculate confidence based on text quality
        total_len = sum(len(t) for _, t in text_segments)
        avg_quality = sum(
            self._basic_text_check(t) for _, t in text_segments
        ) / len(text_segments)

        return ScriptBlock(
            offset=start,
            end_offset=offset,
            opcodes=opcodes,
            text_segments=text_segments,
            confidence=avg_quality,
        )

    def get_text_from_blocks(self) -> List[Tuple[int, str]]:
        """
        Get all extracted text from script blocks.

        Returns:
            List of (offset, text_string) tuples
        """
        results = []

        for block in self._script_blocks:
            for offset, text_bytes in block.text_segments:
                try:
                    text = text_bytes.decode('ascii', errors='replace')
                    results.append((offset, text))
                except:
                    pass

        return results


def mine_opcodes(rom_data: bytes,
                 regions: Optional[List[Tuple[int, int]]] = None
                 ) -> Tuple[List[OpcodePattern], List[ScriptBlock]]:
    """
    Convenience function to mine opcodes and extract script blocks.

    Args:
        rom_data: ROM data
        regions: Optional regions to scan

    Returns:
        Tuple of (promoted_opcodes, script_blocks)
    """
    miner = ScriptOpcodeMiner(rom_data)
    opcodes = miner.mine(regions)
    blocks = miner.extract_script_blocks(regions)
    return opcodes, blocks
