#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRANSLATION PREP LAYER v2.1
Professional ROM Text Extraction & Translation Pipeline

Identity: CRC32 only. No game names, no hardware marketing, no profile names.
Output: Clean, context-aware translation units ready for AI/human translation.

v2.0 Changes:
- EncoderRegistry for byte-based validation
- wrap_hint (max_cols, max_lines)
- Terminator/padding metadata
- TokenProtector turbo (printf, brace, escapes, tags, order_sensitive)
- Merge guardrails with merged_from tracking
- Dedupe groups with dup_group_id
- Strict validator with multiset token validation
- Auditable report with top 20 statistics

v2.1 Changes:
- EncodingGuesser for per-item/cluster encoding detection with confidence
- round_trip_check: encode→decode validation with token preservation
- Cluster-based WrapHint/FieldConstraints with outlier detection
- StrictPunctuationValidator for structural patterns (lists/menus/key:value)
- CRC32_glossary.json optional export based on dup_group_id
- two_pass_translate with automatic retry for needs_shortening units
"""

import os
import sys
import re
import json
import struct
import math
import zlib
import hashlib
from typing import List, Dict, Tuple, Optional, Set, Any, Callable
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import Counter
from enum import Enum


# =============================================================================
# ENCODER REGISTRY - Byte-based validation
# =============================================================================

class EncoderRegistry:
    """
    Registry of text encoders for byte-accurate length validation.
    Supports custom ROM-specific character tables.
    """

    def __init__(self):
        self._encoders: Dict[str, Callable[[str], bytes]] = {}
        self._decoders: Dict[str, Callable[[bytes], str]] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register standard encodings."""
        # UTF-8
        self.register('utf8', lambda t: t.encode('utf-8', errors='replace'),
                      lambda b: b.decode('utf-8', errors='replace'))

        # ASCII
        self.register('ascii', lambda t: t.encode('ascii', errors='replace'),
                      lambda b: b.decode('ascii', errors='replace'))

        # Shift-JIS
        self.register('shiftjis', lambda t: t.encode('shift_jis', errors='replace'),
                      lambda b: b.decode('shift_jis', errors='replace'))

        # Latin-1
        self.register('latin1', lambda t: t.encode('latin-1', errors='replace'),
                      lambda b: b.decode('latin-1', errors='replace'))

    def register(self, name: str, encoder: Callable[[str], bytes],
                 decoder: Callable[[bytes], str] = None):
        """Register a custom encoder."""
        self._encoders[name.lower()] = encoder
        if decoder:
            self._decoders[name.lower()] = decoder

    def register_char_table(self, name: str, char_to_byte: Dict[str, int],
                            default_byte: int = 0x3F):
        """
        Register encoding from character table mapping.

        Args:
            name: Encoder name
            char_to_byte: Mapping of character -> byte value
            default_byte: Byte to use for unknown characters (default: '?')
        """
        byte_to_char = {v: k for k, v in char_to_byte.items()}

        def encoder(text: str) -> bytes:
            result = []
            for char in text:
                if char in char_to_byte:
                    result.append(char_to_byte[char])
                else:
                    result.append(default_byte)
            return bytes(result)

        def decoder(data: bytes) -> str:
            result = []
            for byte in data:
                if byte in byte_to_char:
                    result.append(byte_to_char[byte])
                else:
                    result.append(f'[{byte:02X}]')
            return ''.join(result)

        self.register(name, encoder, decoder)

    def encode(self, text: str, encoding: str = 'utf8') -> bytes:
        """Encode text to bytes using specified encoding."""
        enc = encoding.lower()
        if enc not in self._encoders:
            raise ValueError(f"Unknown encoding: {encoding}")
        return self._encoders[enc](text)

    def decode(self, data: bytes, encoding: str = 'utf8') -> str:
        """Decode bytes to text using specified encoding."""
        enc = encoding.lower()
        if enc not in self._decoders:
            raise ValueError(f"Unknown encoding: {encoding}")
        return self._decoders[enc](data)

    def byte_length(self, text: str, encoding: str = 'utf8') -> int:
        """Get byte length of text in specified encoding."""
        return len(self.encode(text, encoding))

    def round_trip_check(
        self,
        text: str,
        encoding: str = 'utf8',
        token_pattern: str = r'<[A-Z_0-9]+(?:_\d+)?>'
    ) -> Tuple[bool, str, List[str]]:
        """
        v2.1: Round-trip validation - encode→decode→compare.

        Validates that:
        1. Text survives encoding round-trip
        2. Placeholders are preserved exactly
        3. Line breaks are preserved

        Args:
            text: Text to validate
            encoding: Encoding to test
            token_pattern: Regex pattern for tokens to check

        Returns:
            Tuple of (success, round_tripped_text, list of errors)
        """
        errors = []

        try:
            # Step 1: Encode
            encoded = self.encode(text, encoding)

            # Step 2: Decode
            decoded = self.decode(encoded, encoding)

            # Step 3: Compare tokens
            src_tokens = re.findall(token_pattern, text)
            dst_tokens = re.findall(token_pattern, decoded)

            if src_tokens != dst_tokens:
                errors.append(f"Token mismatch: src={src_tokens} dst={dst_tokens}")

            # Step 4: Compare line breaks
            src_lines = text.count('\n') + text.count('[NEWLINE]')
            dst_lines = decoded.count('\n') + decoded.count('[NEWLINE]')

            if src_lines != dst_lines:
                errors.append(f"Line break count changed: {src_lines} → {dst_lines}")

            # Step 5: Check for replacement characters
            if '?' in decoded and '?' not in text:
                count = decoded.count('?') - text.count('?')
                if count > 0:
                    errors.append(f"Encoding produced {count} replacement characters")

            if '\ufffd' in decoded:
                errors.append("Encoding produced Unicode replacement characters")

            # Step 6: Length preservation (for fixed-width encodings)
            if encoding.lower() in ('ascii', 'latin1'):
                if len(text) != len(decoded):
                    errors.append(f"Length changed: {len(text)} → {len(decoded)}")

            return (len(errors) == 0, decoded, errors)

        except Exception as e:
            errors.append(f"Round-trip failed: {str(e)}")
            return (False, "", errors)


# Global encoder registry instance
ENCODER_REGISTRY = EncoderRegistry()


# =============================================================================
# v2.1: ENCODING GUESSER - Per-item/cluster encoding detection
# =============================================================================

@dataclass
class EncodingGuess:
    """Result of encoding detection."""
    encoding: str               # Detected encoding name
    confidence: float           # Confidence score 0.0-1.0
    heuristic_used: str         # Which heuristic matched
    byte_patterns: Dict[str, int] = field(default_factory=dict)  # Pattern counts


class EncodingGuesser:
    """
    Infers encoding per item/cluster when extractor doesn't know.

    Heuristics:
    - Many alternating 0x00 → UTF-16LE/BE
    - Bytes 0x81-0x9F or 0xE0-0xEF → Shift-JIS probable
    - Only 0x20-0x7E → ASCII
    - Mixed with 0x80+ but not Shift-JIS patterns → Latin-1 or custom
    """

    def __init__(self, encoder_registry: EncoderRegistry = None):
        self.encoder = encoder_registry or ENCODER_REGISTRY

    def guess_encoding(self, raw_bytes: bytes) -> EncodingGuess:
        """
        Guess encoding from raw bytes.

        Args:
            raw_bytes: Raw byte data to analyze

        Returns:
            EncodingGuess with encoding, confidence, and heuristic info
        """
        if not raw_bytes:
            return EncodingGuess('ascii', 0.0, 'empty_data')

        patterns = self._analyze_byte_patterns(raw_bytes)

        # Check UTF-16 (alternating 0x00)
        if patterns['null_alternating_ratio'] > 0.3:
            # Determine endianness
            if patterns['null_even_positions'] > patterns['null_odd_positions']:
                return EncodingGuess('utf16le', 0.85, 'null_alternating', patterns)
            else:
                return EncodingGuess('utf16be', 0.85, 'null_alternating', patterns)

        # Check Shift-JIS patterns (0x81-0x9F, 0xE0-0xEF lead bytes)
        if patterns['shiftjis_lead_bytes'] > 0:
            sjis_ratio = patterns['shiftjis_lead_bytes'] / len(raw_bytes)
            if sjis_ratio > 0.05:
                confidence = min(0.90, 0.60 + sjis_ratio * 2)
                return EncodingGuess('shiftjis', confidence, 'shiftjis_lead_bytes', patterns)

        # Check pure ASCII (only 0x20-0x7E + common control)
        if patterns['ascii_ratio'] > 0.95:
            return EncodingGuess('ascii', 0.95, 'pure_ascii', patterns)

        # Check if high bytes present but not Shift-JIS
        if patterns['high_bytes'] > 0:
            high_ratio = patterns['high_bytes'] / len(raw_bytes)
            if high_ratio < 0.3:
                # Likely Latin-1 or custom encoding
                return EncodingGuess('latin1', 0.60, 'high_bytes_non_sjis', patterns)
            else:
                # Could be custom ROM encoding
                return EncodingGuess('custom', 0.40, 'unknown_high_bytes', patterns)

        # Default to UTF-8 for mixed content
        return EncodingGuess('utf8', 0.70, 'default_mixed', patterns)

    def guess_encoding_from_hex(self, hex_string: str) -> EncodingGuess:
        """Guess encoding from hex string (e.g., "48 65 6C 6C 6F")."""
        if not hex_string:
            return EncodingGuess('ascii', 0.0, 'empty_data')

        try:
            raw_bytes = bytes.fromhex(hex_string.replace(' ', ''))
            return self.guess_encoding(raw_bytes)
        except ValueError:
            return EncodingGuess('ascii', 0.0, 'invalid_hex')

    def guess_cluster_encoding(self, items: List[Dict]) -> EncodingGuess:
        """
        Guess encoding for a cluster of items.
        Uses majority voting with confidence weighting.

        Args:
            items: List of items with 'raw_hex' field

        Returns:
            EncodingGuess representing cluster consensus
        """
        if not items:
            return EncodingGuess('ascii', 0.0, 'empty_cluster')

        encoding_votes: Dict[str, float] = {}

        for item in items:
            hex_str = item.get('raw_hex', '')
            if hex_str:
                guess = self.guess_encoding_from_hex(hex_str)
                encoding_votes[guess.encoding] = \
                    encoding_votes.get(guess.encoding, 0) + guess.confidence

        if not encoding_votes:
            return EncodingGuess('utf8', 0.50, 'no_valid_samples')

        # Find winner
        winner = max(encoding_votes.items(), key=lambda x: x[1])
        total_votes = sum(encoding_votes.values())
        confidence = winner[1] / total_votes if total_votes > 0 else 0.0

        return EncodingGuess(
            winner[0],
            min(0.95, confidence),
            'cluster_voting',
            {'votes': encoding_votes, 'sample_count': len(items)}
        )

    def _analyze_byte_patterns(self, data: bytes) -> Dict[str, Any]:
        """Analyze byte patterns for encoding detection."""
        patterns = {
            'null_alternating_ratio': 0.0,
            'null_even_positions': 0,
            'null_odd_positions': 0,
            'shiftjis_lead_bytes': 0,
            'ascii_ratio': 0.0,
            'high_bytes': 0,
            'total_bytes': len(data)
        }

        ascii_count = 0

        for i, byte in enumerate(data):
            # Count nulls by position
            if byte == 0x00:
                if i % 2 == 0:
                    patterns['null_even_positions'] += 1
                else:
                    patterns['null_odd_positions'] += 1

            # Count Shift-JIS lead bytes
            if 0x81 <= byte <= 0x9F or 0xE0 <= byte <= 0xEF:
                patterns['shiftjis_lead_bytes'] += 1

            # Count ASCII printable + common control
            if 0x20 <= byte <= 0x7E or byte in (0x09, 0x0A, 0x0D):
                ascii_count += 1

            # Count high bytes
            if byte >= 0x80:
                patterns['high_bytes'] += 1

        # Calculate ratios
        if len(data) > 1:
            total_nulls = patterns['null_even_positions'] + patterns['null_odd_positions']
            patterns['null_alternating_ratio'] = total_nulls / len(data)

        patterns['ascii_ratio'] = ascii_count / len(data) if len(data) > 0 else 0

        return patterns


# Global encoding guesser instance
ENCODING_GUESSER = EncodingGuesser()


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class WrapHint:
    """Text box wrapping constraints."""
    max_cols: int = 0           # Maximum columns per line (0 = no limit)
    max_lines: int = 0          # Maximum lines (0 = no limit)
    inferred: bool = False      # True if heuristically detected


@dataclass
class FieldConstraints:
    """Binary field constraints for reinsertion."""
    max_len_bytes: int = 0          # Maximum byte length
    terminator_byte: int = 0x7F     # Terminator byte value
    pad_byte: Optional[int] = None  # Padding byte (None if variable length)
    fixed_field_len: Optional[int] = None  # Fixed field length (None if variable)


@dataclass
class TokenInfo:
    """Information about a protected token."""
    placeholder: str            # Standardized placeholder (e.g., <COLOR>)
    original: str               # Original text (e.g., [COLOR])
    position: int               # Position in source text
    order_sensitive: bool       # Must maintain order during translation
    category: str               # Category: control, printf, brace, escape, tag, byte


@dataclass
class TranslationUnit:
    """A single translation unit with full context and metadata."""
    id: str
    offset: int
    method: str
    index: int
    text_src: str
    text_normalized: str
    context_prev: List[str] = field(default_factory=list)
    context_next: List[str] = field(default_factory=list)
    placeholders: Dict[str, str] = field(default_factory=dict)
    token_info: List[TokenInfo] = field(default_factory=list)
    constraints: FieldConstraints = field(default_factory=FieldConstraints)
    wrap_hint: WrapHint = field(default_factory=WrapHint)
    raw_hex: str = ""
    notes: str = ""
    status: str = "pending"  # pending, approved, blocked
    block_reasons: List[str] = field(default_factory=list)
    checksum: str = ""
    dup_group_id: str = ""          # SHA1 of normalized text without tokens
    merged_from: List[str] = field(default_factory=list)  # IDs of merged units
    # v2.1 additions
    encoding_detected: str = ""             # Detected encoding for this unit
    encoding_confidence: float = 0.0        # Confidence of encoding detection
    cluster_id: str = ""                    # Cluster this unit belongs to
    is_cluster_outlier: bool = False        # True if constraints differ from cluster
    structural_pattern: str = ""            # Detected pattern: list, menu, key_value, etc
    needs_shortening: bool = False          # True if translation exceeded limits
    round_trip_valid: bool = True           # True if passed round-trip check


@dataclass
class ExtractionStats:
    """Statistics for extraction report."""
    crc32_full: str = ""
    crc32_no_header: str = ""
    rom_size: int = 0
    total_strings: int = 0
    method_counts: Dict[str, int] = field(default_factory=dict)
    approved_units: int = 0
    blocked_units: int = 0
    block_reasons_summary: Dict[str, int] = field(default_factory=dict)
    # v2.0 additions
    units_with_tokens: int = 0
    units_merged: int = 0
    token_counts: Dict[str, int] = field(default_factory=dict)
    dup_groups: int = 0


# =============================================================================
# TOKEN PROTECTION SYSTEM - TURBO
# =============================================================================

class TokenCategory(Enum):
    """Token categories for classification."""
    CONTROL = "control"     # [NEWLINE], [END], [WAIT], etc.
    PRINTF = "printf"       # %s, %d, %02X, etc.
    BRACE = "brace"         # {0}, {name}, {player}, etc.
    ESCAPE = "escape"       # \xNN, 0xNN, \\n, etc.
    TAG = "tag"             # <PLAYER>, <ITEM_03>, etc.
    BYTE = "byte"           # [XX] unknown bytes


class TokenProtector:
    """
    Handles protection and restoration of control codes/tokens in text.
    Ensures translators cannot accidentally modify game control sequences.

    v2.0: Extended to handle printf, brace, escapes, and tags.
          Tracks order_sensitive flag per token.
    """

    # Token patterns by category with order sensitivity
    # Format: (pattern, replacement_template, order_sensitive)
    TOKEN_PATTERNS = {
        TokenCategory.CONTROL: [
            (r'\[NEWLINE\]', '<NEWLINE>', False),
            (r'\[END\]', '<END>', True),  # END must not move
            (r'\[WAIT\]', '<WAIT>', True),
            (r'\[WAIT_BTN\]', '<WAIT_BTN>', True),
            (r'\[WAIT_INPUT\]', '<WAIT_INPUT>', True),
            (r'\[WAIT_FRAME\]', '<WAIT_FRAME>', True),
            (r'\[SCROLL\]', '<SCROLL>', True),
            (r'\[COLOR\]', '<COLOR>', True),
            (r'\[SPEED\]', '<SPEED>', True),
            (r'\[CHOOSE\]', '<CHOOSE>', True),
            (r'\[CHOOSE2\]', '<CHOOSE2>', True),
            (r'\[CHOOSE3\]', '<CHOOSE3>', True),
            (r'__PROTECTED__\[COLOR\]__', '<COLOR>', True),
            (r'\[NAME\d*\]', '<NAME>', True),
            (r'\[ITEM\d*\]', '<ITEM>', True),
            (r'\[PLACE\d*\]', '<PLACE>', True),
            (r'\[CURRENCY\]', '<CURRENCY>', True),
            (r'\[CMD:([0-9A-Fa-f]{2})\]', r'<CMD_\1>', True),
        ],
        TokenCategory.PRINTF: [
            (r'%[-+0 #]*\d*\.?\d*[hlL]?[diouxXeEfFgGaAcspn%]', None, True),  # Full printf
            (r'%[sd]', None, True),      # Simple %s, %d
            (r'%\d+\$[sd]', None, True), # Positional %1$s
            (r'%0?\d*[xX]', None, True), # Hex %02X
        ],
        TokenCategory.BRACE: [
            (r'\{(\d+)\}', None, True),           # {0}, {1}
            (r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', None, True),  # {name}, {player}
        ],
        TokenCategory.ESCAPE: [
            (r'\\x[0-9A-Fa-f]{2}', None, True),   # \x0A
            (r'0x[0-9A-Fa-f]{2,4}', None, True),  # 0xFF
            (r'\\[nrt\\]', None, False),          # \n, \r, \t, \\
        ],
        TokenCategory.TAG: [
            (r'<([A-Z][A-Z0-9_]*)>', None, True),      # <PLAYER>, <ITEM>
            (r'<([A-Z][A-Z0-9_]*_\d+)>', None, True),  # <ITEM_03>
        ],
        TokenCategory.BYTE: [
            (r'\[([0-9A-Fa-f]{2})\]', r'<BYTE_\1>', True),  # Unknown bytes
        ],
    }

    def __init__(self):
        self._compiled_patterns = {}
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        for category, patterns in self.TOKEN_PATTERNS.items():
            self._compiled_patterns[category] = [
                (re.compile(p), r, o) for p, r, o in patterns
            ]

    def protect_tokens(self, text: str) -> Tuple[str, Dict[str, str], List[TokenInfo]]:
        """
        Replace all control codes with standardized placeholders.

        Args:
            text: Source text with control codes

        Returns:
            Tuple of (protected_text, token_map, token_info_list)
        """
        protected = text
        token_map = {}
        token_info = []
        token_counter = Counter()

        # Process each category in priority order
        for category in TokenCategory:
            if category not in self._compiled_patterns:
                continue

            for pattern, replacement, order_sensitive in self._compiled_patterns[category]:
                for match in list(pattern.finditer(protected)):
                    original = match.group(0)
                    position = match.start()

                    # Generate placeholder
                    if replacement and '\\1' in replacement:
                        base_token = pattern.sub(replacement, original)
                    elif replacement:
                        base_token = replacement
                    else:
                        # Auto-generate placeholder from match
                        clean_name = re.sub(r'[^A-Z0-9]', '', original.upper())
                        if not clean_name:
                            clean_name = "TOKEN"
                        base_token = f'<{clean_name}>'

                    # Make unique
                    token_type = base_token.strip('<>')
                    token_counter[token_type] += 1

                    if token_counter[token_type] > 1:
                        unique_token = f'<{token_type}_{token_counter[token_type]}>'
                    else:
                        unique_token = base_token

                    # Store mapping and info
                    token_map[unique_token] = original
                    token_info.append(TokenInfo(
                        placeholder=unique_token,
                        original=original,
                        position=position,
                        order_sensitive=order_sensitive,
                        category=category.value
                    ))

                    protected = protected.replace(original, unique_token, 1)

        # Sort token_info by position
        token_info.sort(key=lambda x: x.position)

        return protected, token_map, token_info

    def unprotect_tokens(
        self,
        translated: str,
        token_map: Dict[str, str],
        terminator_byte: int = 0x7F,
        pad_byte: Optional[int] = None,
        fixed_len: Optional[int] = None
    ) -> Tuple[str, List[str]]:
        """
        Restore original control codes from placeholders.
        Ensures terminator is preserved and handles padding.

        Args:
            translated: Translated text with placeholders
            token_map: Map of placeholder -> original token
            terminator_byte: Terminator byte to ensure present
            pad_byte: Padding byte for fixed-length fields
            fixed_len: Fixed field length (if applicable)

        Returns:
            Tuple of (restored_text, list of errors/warnings)
        """
        errors = []
        restored = translated

        # Check all tokens are present and restore
        for placeholder, original in token_map.items():
            if placeholder not in restored:
                errors.append(f"Missing token: {placeholder} (original: {original})")
            else:
                restored = restored.replace(placeholder, original, 1)

        # Check for orphan placeholders
        orphan_pattern = r'<[A-Z_0-9]+(?:_\d+)?>'
        orphans = re.findall(orphan_pattern, restored)
        for orphan in orphans:
            if orphan not in token_map:
                errors.append(f"Unknown/modified token: {orphan}")

        # Ensure terminator
        terminator_str = f'[END]' if terminator_byte == 0x7F else f'[{terminator_byte:02X}]'
        if '[END]' in str(token_map.values()) and terminator_str not in restored:
            # Terminator was in original but missing now
            if not any('[END]' in restored or terminator_str in restored for _ in [1]):
                errors.append(f"Terminator missing: {terminator_str}")

        return restored, errors


# =============================================================================
# TEXT NORMALIZER
# =============================================================================

class TextNormalizer:
    """
    Normalizes text for consistent translation while preserving semantics.
    """

    def normalize_for_translation(self, text: str) -> str:
        """
        Normalize text for translation processing.

        Args:
            text: Raw extracted text

        Returns:
            Normalized text
        """
        if not text:
            return ""

        normalized = text

        # Normalize newline markers to consistent format
        normalized = re.sub(r'\[NEWLINE\]', '\n', normalized)
        normalized = re.sub(r'\\n', '\n', normalized)

        # Collapse multiple spaces (but preserve intentional spacing)
        normalized = re.sub(r'[ \t]+', ' ', normalized)

        # Collapse multiple newlines (max 2)
        normalized = re.sub(r'\n{3,}', '\n\n', normalized)

        # Normalize quotes
        normalized = normalized.replace('``', '"')
        normalized = normalized.replace("''", '"')

        # Normalize dashes
        normalized = normalized.replace('--', '—')

        # Trim whitespace from edges (preserve punctuation)
        normalized = normalized.strip()

        # Remove control characters except newlines
        normalized = ''.join(
            c for c in normalized
            if c == '\n' or (ord(c) >= 32 and ord(c) != 127)
        )

        return normalized

    def restore_newline_format(self, text: str) -> str:
        """Convert normalized newlines back to [NEWLINE] format."""
        return text.replace('\n', '[NEWLINE]')

    def strip_tokens_for_hash(self, text: str) -> str:
        """
        Strip all tokens from text for deduplication hashing.

        Args:
            text: Text with tokens

        Returns:
            Text with all <TOKEN> placeholders removed
        """
        stripped = re.sub(r'<[A-Z_0-9]+(?:_\d+)?>', '', text)
        stripped = re.sub(r'\s+', ' ', stripped).strip()
        return stripped


# =============================================================================
# TRANSLATION UNIT BUILDER
# =============================================================================

class TranslationUnitBuilder:
    """
    Builds context-aware translation units from extracted text items.
    v2.0: Enhanced with merge guardrails and dedupe groups.
    """

    # Patterns that should NOT be merged
    LABEL_PATTERNS = [
        r'^[A-Z][a-z]*:',           # "Label:"
        r'^[A-Z]+$',                # "MENU"
        r'^\d+\.',                  # "1."
        r'^[-*]',                   # "- item"
    ]

    MENU_KEYWORDS = [
        'yes', 'no', 'ok', 'cancel', 'back', 'exit', 'save', 'load',
        'start', 'continue', 'quit', 'end', 'new', 'options', 'settings'
    ]

    def __init__(self, crc32: str, encoder_registry: EncoderRegistry = None):
        self.crc32 = crc32
        self.protector = TokenProtector()
        self.normalizer = TextNormalizer()
        self.encoder = encoder_registry or ENCODER_REGISTRY
        # v2.1 additions
        self.encoding_guesser = ENCODING_GUESSER
        self.punctuation_validator = StrictPunctuationValidator()
        self.cluster_inferrer = ClusterConstraintInferrer()

    def build_translation_units(self, items: List[Dict]) -> List[TranslationUnit]:
        """
        Build translation units with context from extracted items.
        """
        if not items:
            return []

        # Sort by offset
        sorted_items = sorted(items, key=lambda x: x.get('offset', 0))

        # Generate clusters based on offset proximity
        clusters = self._cluster_by_proximity(sorted_items, max_gap=0x1000)

        # Build units with context
        units = []
        global_index = 0

        for cluster in clusters:
            cluster_units = self._build_cluster_units(cluster, global_index)
            units.extend(cluster_units)
            global_index += len(cluster_units)

        # Merge fragmented strings with guardrails
        units = self._merge_fragments_guarded(units)

        # Assign stable IDs and compute hashes
        for i, unit in enumerate(units):
            unit.id = f"{self.crc32}:{unit.offset:06X}:{unit.method}:{i:04d}"
            unit.checksum = self._compute_unit_checksum(unit)
            unit.dup_group_id = self._compute_dup_group_id(unit)

        return units

    def _cluster_by_proximity(self, items: List[Dict], max_gap: int = 0x1000) -> List[List[Dict]]:
        """Group items into clusters based on offset proximity."""
        if not items:
            return []

        clusters = []
        current_cluster = [items[0]]

        for item in items[1:]:
            prev_offset = current_cluster[-1].get('offset', 0)
            curr_offset = item.get('offset', 0)
            prev_source = current_cluster[-1].get('source', '')
            curr_source = item.get('source', '')

            if (curr_offset - prev_offset <= max_gap and
                self._same_method_family(prev_source, curr_source)):
                current_cluster.append(item)
            else:
                if current_cluster:
                    clusters.append(current_cluster)
                current_cluster = [item]

        if current_cluster:
            clusters.append(current_cluster)

        return clusters

    def _same_method_family(self, source1: str, source2: str) -> bool:
        """Check if two sources belong to the same extraction method."""
        def get_family(source: str) -> str:
            if 'pointer_table' in source:
                return 'pointer'
            if 'script_crawler' in source:
                return 'script'
            if 'entropy' in source:
                return 'entropy'
            if 'block' in source.lower():
                return 'block'
            return 'other'

        return get_family(source1) == get_family(source2)

    def _build_cluster_units(self, cluster: List[Dict], start_index: int) -> List[TranslationUnit]:
        """Build translation units from a cluster with context."""
        units = []

        for i, item in enumerate(cluster):
            source = item.get('source', 'unknown')
            method = self._extract_method(source)

            raw_text = item.get('text', '')
            normalized = self.normalizer.normalize_for_translation(raw_text)

            # Protect tokens with full info
            protected, token_map, token_info = self.protector.protect_tokens(normalized)

            # Build context
            context_prev = []
            context_next = []

            if i > 0:
                prev_text = cluster[i-1].get('text', '')[:100]
                if prev_text:
                    context_prev.append(self.normalizer.normalize_for_translation(prev_text))
            if i > 1:
                prev_text = cluster[i-2].get('text', '')[:100]
                if prev_text:
                    context_prev.insert(0, self.normalizer.normalize_for_translation(prev_text))

            if i < len(cluster) - 1:
                next_text = cluster[i+1].get('text', '')[:100]
                if next_text:
                    context_next.append(self.normalizer.normalize_for_translation(next_text))
            if i < len(cluster) - 2:
                next_text = cluster[i+2].get('text', '')[:100]
                if next_text:
                    context_next.append(self.normalizer.normalize_for_translation(next_text))

            # Infer text type and wrap hints
            notes = self._infer_text_type(raw_text)
            wrap_hint = self._infer_wrap_hint(raw_text)

            # Estimate field constraints
            raw_hex = item.get('raw_hex', '')
            constraints = self._estimate_field_constraints(raw_text, raw_hex)

            # v2.1: Detect encoding
            encoding_guess = self.encoding_guesser.guess_encoding_from_hex(raw_hex)

            # v2.1: Detect structural pattern
            pattern_name, _ = self.punctuation_validator.detect_structural_pattern(
                protected
            )

            unit = TranslationUnit(
                id="",
                offset=item.get('offset', 0),
                method=method,
                index=start_index + i,
                text_src=raw_text,
                text_normalized=protected,
                context_prev=context_prev,
                context_next=context_next,
                placeholders=token_map,
                token_info=token_info,
                constraints=constraints,
                wrap_hint=wrap_hint,
                raw_hex=raw_hex,
                notes=notes,
                status="pending",
                # v2.1 fields
                encoding_detected=encoding_guess.encoding,
                encoding_confidence=encoding_guess.confidence,
                structural_pattern=pattern_name
            )

            units.append(unit)

        return units

    def _extract_method(self, source: str) -> str:
        """Extract clean method name from source string."""
        if 'pointer_table' in source:
            return 'pointer'
        if 'script_crawler' in source:
            return 'script'
        if 'entropy' in source:
            return 'entropy'
        if 'block_1' in source.lower() or 'block1' in source.lower():
            return 'block1'
        if 'block_2' in source.lower() or 'block2' in source.lower():
            return 'block2'
        if 'shift_jis' in source:
            return 'shiftjis'
        return 'generic'

    def _infer_text_type(self, text: str) -> str:
        """Infer the type of text using heuristics."""
        text_lower = text.lower()

        if any(word in text_lower for word in ['yes', 'no', 'ok', 'cancel', 'back', 'exit', 'save', 'load']):
            if len(text) < 20:
                return "menu_option"

        if any(word in text_lower for word in ['error', 'warning', 'saved', 'loaded', 'game over']):
            return "system_msg"

        if ':' in text and len(text) > 20:
            return "dialog"

        if len(text) < 25 and text.count(' ') <= 2:
            if any(word in text_lower for word in ['sword', 'shield', 'armor', 'potion', 'ring', 'staff']):
                return "item_name"

        if len(text) > 100 and '"' not in text and ':' not in text:
            return "narration"

        if len(text) > 30:
            return "dialog"

        return "text"

    def _infer_wrap_hint(self, text: str) -> WrapHint:
        """
        Infer text box wrapping constraints from text structure.
        """
        lines = text.replace('[NEWLINE]', '\n').split('\n')
        if not lines:
            return WrapHint()

        # Analyze line lengths
        max_line_len = max(len(line) for line in lines if line.strip())
        num_lines = len([l for l in lines if l.strip()])

        # Common text box sizes
        if max_line_len <= 32 and num_lines <= 4:
            return WrapHint(max_cols=32, max_lines=4, inferred=True)
        elif max_line_len <= 24 and num_lines <= 3:
            return WrapHint(max_cols=24, max_lines=3, inferred=True)
        elif max_line_len <= 16:
            return WrapHint(max_cols=16, max_lines=2, inferred=True)

        return WrapHint(max_cols=max_line_len + 4, max_lines=0, inferred=True)

    def _estimate_field_constraints(self, text: str, raw_hex: str) -> FieldConstraints:
        """Estimate binary field constraints."""
        # Count raw bytes
        raw_bytes = raw_hex.split() if raw_hex else []
        raw_len = len(raw_bytes)

        # Detect terminator
        terminator = 0x7F  # Default
        if raw_bytes:
            last_byte = int(raw_bytes[-1], 16) if raw_bytes[-1] else 0x7F
            if last_byte in [0x00, 0x7F, 0xFF]:
                terminator = last_byte

        # Detect fixed field (all same length in region would indicate this)
        # For now, assume variable length
        fixed_len = None
        pad_byte = None

        # Check if text appears padded
        if text.endswith('   ') or text.endswith('\x00\x00'):
            pad_byte = 0x00 if '\x00' in text else 0x20

        return FieldConstraints(
            max_len_bytes=max(raw_len, len(text) + 10),
            terminator_byte=terminator,
            pad_byte=pad_byte,
            fixed_field_len=fixed_len
        )

    def _merge_fragments_guarded(self, units: List[TranslationUnit]) -> List[TranslationUnit]:
        """
        Merge fragmented strings with guardrails.

        Guardrails:
        - Both must pass _post_filter_text
        - Neither can be label/menu pattern
        - Neither can be "key: value" format
        """
        if len(units) < 2:
            return units

        merged = []
        skip_next = False

        for i, unit in enumerate(units):
            if skip_next:
                skip_next = False
                continue

            if i < len(units) - 1:
                next_unit = units[i + 1]

                # Apply guardrails
                if (self._should_merge_guarded(unit, next_unit)):
                    # Merge units
                    merged_text = unit.text_normalized + ' ' + next_unit.text_normalized
                    unit.text_normalized = merged_text.replace('  ', ' ')
                    unit.text_src = unit.text_src + ' ' + next_unit.text_src
                    unit.context_next = next_unit.context_next
                    unit.placeholders.update(next_unit.placeholders)
                    unit.token_info.extend(next_unit.token_info)
                    unit.constraints.max_len_bytes += next_unit.constraints.max_len_bytes
                    unit.notes = f"merged: {unit.notes}"
                    unit.merged_from = [unit.id, next_unit.id] if unit.id else ['pre_id', 'pre_id']
                    skip_next = True

            merged.append(unit)

        return merged

    def _should_merge_guarded(self, unit1: TranslationUnit, unit2: TranslationUnit) -> bool:
        """Determine if two units should be merged with guardrails."""
        text1 = unit1.text_normalized
        text2 = unit2.text_normalized

        if not text1 or not text2:
            return False

        # Guardrail 1: Both must pass post-filter
        if not self._post_filter_text(text1) or not self._post_filter_text(text2):
            return False

        # Guardrail 2: No label patterns
        for pattern in self.LABEL_PATTERNS:
            if re.match(pattern, text1.strip()) or re.match(pattern, text2.strip()):
                return False

        # Guardrail 3: No menu keywords as standalone
        text1_lower = text1.lower().strip()
        text2_lower = text2.lower().strip()
        if text1_lower in self.MENU_KEYWORDS or text2_lower in self.MENU_KEYWORDS:
            return False

        # Guardrail 4: No "key: value" format
        if re.match(r'^[A-Za-z]+:\s', text1) or re.match(r'^[A-Za-z]+:\s', text2):
            return False

        # Standard merge logic
        text1_clean = text1.rstrip()
        text2_clean = text2.lstrip()

        if len(text1_clean) < 3 or len(text2_clean) < 3:
            return False

        if text2_clean[0].isupper():
            return False

        if text1_clean[-1] not in '.!?':
            if text2_clean[0].islower():
                return True

        if text1_clean[-1] == ',':
            return True

        return False

    def _post_filter_text(self, text: str) -> bool:
        """Post-filter validation for merge candidates."""
        if not text or len(text.strip()) < 2:
            return False

        # Too many tokens
        token_count = text.count('<')
        if token_count > len(text) * 0.5:
            return False

        # Must have some readable content
        alpha_count = sum(1 for c in text if c.isalpha())
        if alpha_count < 2:
            return False

        return True

    def _compute_unit_checksum(self, unit: TranslationUnit) -> str:
        """Compute checksum for drift detection."""
        data = f"{unit.offset}:{unit.text_src}:{unit.method}"
        return hashlib.md5(data.encode()).hexdigest()[:8]

    def _compute_dup_group_id(self, unit: TranslationUnit) -> str:
        """
        Compute dedupe group ID from normalized text without tokens.
        Units with same dup_group_id should have consistent translations.
        """
        stripped = self.normalizer.strip_tokens_for_hash(unit.text_normalized)
        if not stripped:
            return ""
        return hashlib.sha1(stripped.encode()).hexdigest()[:12]


# =============================================================================
# TRANSLATION VALIDATOR - STRICT
# =============================================================================

class TranslationValidator:
    """
    Validates translated text before reinsertion.
    v2.0: Strict validation with multiset tokens and order checking.
    """

    def __init__(self, protector: TokenProtector, encoder: EncoderRegistry = None):
        self.protector = protector
        self.encoder = encoder or ENCODER_REGISTRY

    def validate_translation(
        self,
        src: str,
        dst: str,
        token_map: Dict[str, str],
        token_info: List[TokenInfo] = None,
        constraints: FieldConstraints = None,
        wrap_hint: WrapHint = None,
        encoding: str = 'utf8'
    ) -> Tuple[bool, List[str]]:
        """
        Strict validation of translated text.

        Checks:
        - Tokens preserved as multiset (same count)
        - Order preserved for order_sensitive tokens
        - No new <...> tokens inserted
        - No broken brackets
        - Byte length within max_len_bytes
        - Wrap constraints (optional warning)

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        warnings = []

        # Build token multisets
        src_tokens = Counter(re.findall(r'<[A-Z_0-9]+(?:_\d+)?>', src))
        dst_tokens = Counter(re.findall(r'<[A-Z_0-9]+(?:_\d+)?>', dst))

        # Check multiset equality
        missing = src_tokens - dst_tokens
        extra = dst_tokens - src_tokens

        for token, count in missing.items():
            errors.append(f"Missing token: {token} (count: {count})")

        for token, count in extra.items():
            if token in token_map:
                errors.append(f"Extra token: {token} (count: {count})")
            else:
                errors.append(f"New token inserted: {token}")

        # Check order for order_sensitive tokens
        if token_info:
            order_sensitive_src = [t.placeholder for t in token_info if t.order_sensitive]
            dst_token_positions = []
            for token in order_sensitive_src:
                pos = dst.find(token)
                if pos >= 0:
                    dst_token_positions.append((pos, token))

            dst_token_positions.sort()
            dst_order = [t for _, t in dst_token_positions]

            if dst_order != order_sensitive_src[:len(dst_order)]:
                errors.append("Order-sensitive tokens reordered")

        # Check for broken brackets
        broken_patterns = [
            r'\[\s*\]',           # Empty brackets
            r'\[\s+[^\]]+',       # Space after [
            r'[^\[]+\s+\]',       # Space before ]
            r'<\s*>',             # Empty angle brackets
            r'<\s+[^>]+',         # Space after <
            r'[^<]+\s+>',         # Space before >
        ]
        for pattern in broken_patterns:
            matches = re.findall(pattern, dst)
            for match in matches:
                errors.append(f"Broken bracket: {match[:20]}")

        # Check byte length
        if constraints and constraints.max_len_bytes > 0:
            try:
                byte_len = self.encoder.byte_length(dst, encoding)
                if byte_len > constraints.max_len_bytes:
                    errors.append(f"Byte length exceeded: {byte_len} > {constraints.max_len_bytes}")
            except Exception as e:
                errors.append(f"Encoding error: {str(e)}")

        # Check wrap constraints (warning only)
        if wrap_hint and wrap_hint.max_cols > 0:
            lines = dst.replace('<NEWLINE>', '\n').split('\n')
            for i, line in enumerate(lines):
                if len(line) > wrap_hint.max_cols:
                    warnings.append(f"Line {i+1} exceeds max_cols: {len(line)} > {wrap_hint.max_cols}")

            if wrap_hint.max_lines > 0 and len(lines) > wrap_hint.max_lines:
                warnings.append(f"Line count exceeds max_lines: {len(lines)} > {wrap_hint.max_lines}")

        # Critical: END token
        if '<END>' in src and '<END>' not in dst:
            errors.append("Critical: <END> token removed")

        return (len(errors) == 0, errors + warnings)

    def validate_batch(
        self,
        translations: List[Dict[str, Any]]
    ) -> Tuple[List[Dict], List[Dict], Dict[str, int]]:
        """Validate a batch of translations."""
        approved = []
        blocked = []
        reason_summary = {}

        for item in translations:
            constraints = FieldConstraints(
                max_len_bytes=item.get('max_len_bytes', 0)
            )

            is_valid, errors = self.validate_translation(
                src=item.get('src', ''),
                dst=item.get('dst', ''),
                token_map=item.get('token_map', {}),
                constraints=constraints
            )

            if is_valid:
                item['status'] = 'approved'
                approved.append(item)
            else:
                item['status'] = 'blocked'
                item['errors'] = errors
                blocked.append(item)

                for error in errors:
                    reason_key = error.split(':')[0]
                    reason_summary[reason_key] = reason_summary.get(reason_key, 0) + 1

        return approved, blocked, reason_summary


# =============================================================================
# v2.1: STRICT PUNCTUATION VALIDATOR
# =============================================================================

class StrictPunctuationValidator:
    """
    v2.1: Validates that structural punctuation is preserved in translations.

    Protects against AI translations that:
    - Replace : with - in "key: value" patterns
    - Remove ... ellipsis
    - Change quote styles
    - Remove list prefixes (>, -, *, 1.)
    """

    # Structural patterns to detect and preserve
    PATTERNS = {
        'key_value': re.compile(r'^([A-Za-z_][A-Za-z0-9_\s]*)\s*:\s*(.+)$'),
        'numbered_list': re.compile(r'^(\d+)\.\s+(.+)$'),
        'bullet_dash': re.compile(r'^-\s+(.+)$'),
        'bullet_star': re.compile(r'^\*\s+(.+)$'),
        'arrow_prefix': re.compile(r'^>\s*(.+)$'),
        'ellipsis': re.compile(r'\.{3}|…'),
    }

    def detect_structural_pattern(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """
        Detect structural patterns in source text.

        Returns:
            Tuple of (pattern_name, pattern_details)
        """
        text_stripped = text.strip()

        # Check key:value pattern
        match = self.PATTERNS['key_value'].match(text_stripped)
        if match:
            return ('key_value', {
                'key': match.group(1),
                'value': match.group(2),
                'colon_count': text.count(':')
            })

        # Check numbered list
        match = self.PATTERNS['numbered_list'].match(text_stripped)
        if match:
            return ('numbered_list', {
                'number': match.group(1),
                'content': match.group(2)
            })

        # Check bullet patterns
        if self.PATTERNS['bullet_dash'].match(text_stripped):
            return ('bullet_list', {'prefix': '-'})

        if self.PATTERNS['bullet_star'].match(text_stripped):
            return ('bullet_list', {'prefix': '*'})

        if self.PATTERNS['arrow_prefix'].match(text_stripped):
            return ('menu_item', {'prefix': '>'})

        # Check for ellipsis
        if self.PATTERNS['ellipsis'].search(text):
            return ('has_ellipsis', {
                'count': len(self.PATTERNS['ellipsis'].findall(text))
            })

        return ('none', {})

    def validate_punctuation(
        self,
        src: str,
        dst: str,
        strict_mode: bool = True
    ) -> Tuple[bool, List[str]]:
        """
        Validate that structural punctuation is preserved.

        Args:
            src: Source text
            dst: Translated text
            strict_mode: If True, errors block; if False, warnings only

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []
        pattern_name, pattern_info = self.detect_structural_pattern(src)

        if pattern_name == 'key_value':
            # Check colon count preserved
            src_colons = src.count(':')
            dst_colons = dst.count(':')
            if dst_colons < src_colons:
                issues.append(
                    f"Colon count reduced: {src_colons} → {dst_colons} "
                    f"(key:value pattern detected)"
                )

        elif pattern_name == 'numbered_list':
            # Check number prefix preserved
            number = pattern_info['number']
            if not re.match(rf'^{number}\.\s', dst.strip()):
                issues.append(
                    f"Numbered list prefix '{number}.' not preserved"
                )

        elif pattern_name == 'bullet_list':
            prefix = pattern_info['prefix']
            if not dst.strip().startswith(prefix):
                issues.append(
                    f"Bullet prefix '{prefix}' not preserved"
                )

        elif pattern_name == 'menu_item':
            if not dst.strip().startswith('>'):
                issues.append("Menu prefix '>' not preserved")

        elif pattern_name == 'has_ellipsis':
            src_ellipsis = len(self.PATTERNS['ellipsis'].findall(src))
            dst_ellipsis = len(self.PATTERNS['ellipsis'].findall(dst))
            # Also count ... as valid ellipsis in dst
            dst_dots = dst.count('...')
            if dst_ellipsis + dst_dots < src_ellipsis:
                issues.append(
                    f"Ellipsis count reduced: {src_ellipsis} → {dst_ellipsis}"
                )

        # General punctuation checks
        # Check quote balance
        src_quotes = src.count('"') + src.count("'")
        dst_quotes = dst.count('"') + dst.count("'")
        if src_quotes > 0 and dst_quotes == 0:
            issues.append("All quotes removed from translation")

        is_valid = len(issues) == 0 if strict_mode else True
        return (is_valid, issues)


# =============================================================================
# v2.1: CLUSTER CONSTRAINT INFERRER
# =============================================================================

@dataclass
class ClusterConstraints:
    """Aggregated constraints for a cluster of translation units."""
    cluster_id: str
    avg_max_cols: float = 0.0
    avg_max_lines: float = 0.0
    common_max_cols: int = 0      # Most common value
    common_max_lines: int = 0
    avg_max_len_bytes: float = 0.0
    common_encoding: str = 'utf8'
    unit_count: int = 0
    outlier_ids: List[str] = field(default_factory=list)


class ClusterConstraintInferrer:
    """
    v2.1: Infers WrapHint and FieldConstraints at cluster level.

    Instead of per-item inference that can vary wildly, this:
    1. Groups items by cluster
    2. Computes aggregate constraints
    3. Applies cluster defaults to items
    4. Marks outliers that deviate significantly
    """

    def __init__(self, outlier_threshold: float = 0.3):
        """
        Args:
            outlier_threshold: Fraction deviation to mark as outlier (0.3 = 30%)
        """
        self.outlier_threshold = outlier_threshold

    def infer_cluster_constraints(
        self,
        units: List[TranslationUnit],
        cluster_id: str
    ) -> ClusterConstraints:
        """
        Infer constraints for a cluster of units.

        Args:
            units: List of translation units in the cluster
            cluster_id: Identifier for this cluster

        Returns:
            ClusterConstraints with aggregated values
        """
        if not units:
            return ClusterConstraints(cluster_id=cluster_id)

        # Collect values
        max_cols_list = [u.wrap_hint.max_cols for u in units if u.wrap_hint.max_cols > 0]
        max_lines_list = [u.wrap_hint.max_lines for u in units if u.wrap_hint.max_lines > 0]
        max_bytes_list = [u.constraints.max_len_bytes for u in units
                         if u.constraints.max_len_bytes > 0]
        encodings = [u.encoding_detected for u in units if u.encoding_detected]

        constraints = ClusterConstraints(
            cluster_id=cluster_id,
            unit_count=len(units)
        )

        # Compute averages and most common
        if max_cols_list:
            constraints.avg_max_cols = sum(max_cols_list) / len(max_cols_list)
            constraints.common_max_cols = Counter(max_cols_list).most_common(1)[0][0]

        if max_lines_list:
            constraints.avg_max_lines = sum(max_lines_list) / len(max_lines_list)
            constraints.common_max_lines = Counter(max_lines_list).most_common(1)[0][0]

        if max_bytes_list:
            constraints.avg_max_len_bytes = sum(max_bytes_list) / len(max_bytes_list)

        if encodings:
            constraints.common_encoding = Counter(encodings).most_common(1)[0][0]

        return constraints

    def apply_cluster_constraints(
        self,
        units: List[TranslationUnit],
        cluster_constraints: ClusterConstraints
    ) -> List[TranslationUnit]:
        """
        Apply cluster constraints to units and mark outliers.

        Args:
            units: List of translation units
            cluster_constraints: Aggregated cluster constraints

        Returns:
            Modified units with cluster_id and outlier flags
        """
        for unit in units:
            unit.cluster_id = cluster_constraints.cluster_id

            # Check if outlier on max_cols
            if (cluster_constraints.common_max_cols > 0 and
                unit.wrap_hint.max_cols > 0):
                deviation = abs(unit.wrap_hint.max_cols -
                              cluster_constraints.common_max_cols)
                if deviation / cluster_constraints.common_max_cols > self.outlier_threshold:
                    unit.is_cluster_outlier = True
                    cluster_constraints.outlier_ids.append(unit.id)

            # Check if outlier on max_len_bytes
            if (cluster_constraints.avg_max_len_bytes > 0 and
                unit.constraints.max_len_bytes > 0):
                deviation = abs(unit.constraints.max_len_bytes -
                              cluster_constraints.avg_max_len_bytes)
                if deviation / cluster_constraints.avg_max_len_bytes > self.outlier_threshold:
                    unit.is_cluster_outlier = True
                    if unit.id not in cluster_constraints.outlier_ids:
                        cluster_constraints.outlier_ids.append(unit.id)

            # Apply cluster defaults for items without values
            if unit.wrap_hint.max_cols == 0 and cluster_constraints.common_max_cols > 0:
                unit.wrap_hint.max_cols = cluster_constraints.common_max_cols
                unit.wrap_hint.inferred = True

            if unit.wrap_hint.max_lines == 0 and cluster_constraints.common_max_lines > 0:
                unit.wrap_hint.max_lines = cluster_constraints.common_max_lines
                unit.wrap_hint.inferred = True

            if not unit.encoding_detected and cluster_constraints.common_encoding:
                unit.encoding_detected = cluster_constraints.common_encoding

        return units


# =============================================================================
# v2.1: CRC32 GLOSSARY BUILDER
# =============================================================================

@dataclass
class GlossaryEntry:
    """Entry in the CRC32 glossary."""
    term_crc32: str              # CRC32 of the normalized term
    term_text: str               # Original term text
    first_translation: str       # "First translation wins"
    occurrences: int             # Number of times this term appears
    unit_ids: List[str] = field(default_factory=list)  # Units containing this term
    dup_group_id: str = ""       # Link to dup_group_id if applicable


class GlossaryBuilder:
    """
    v2.1: Builds CRC32_glossary.json from extracted units.

    Detects repeated entities (names, items, actions) and suggests
    consistent translations using "first translation wins" approach.
    """

    # Patterns for entity detection
    ENTITY_PATTERNS = [
        # Proper nouns (capitalized words)
        (r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', 'proper_noun'),
        # ALL CAPS words (likely important)
        (r'\b[A-Z]{2,}\b', 'acronym'),
        # Quoted terms
        (r'"([^"]+)"', 'quoted'),
        (r"'([^']+)'", 'quoted'),
    ]

    def __init__(self):
        self._compiled_patterns = [
            (re.compile(p), cat) for p, cat in self.ENTITY_PATTERNS
        ]

    def extract_entities(self, text: str) -> List[Tuple[str, str]]:
        """
        Extract potential entities from text.

        Returns:
            List of (entity_text, category) tuples
        """
        entities = []

        for pattern, category in self._compiled_patterns:
            matches = pattern.findall(text)
            for match in matches:
                # Skip very short or very long matches
                if 2 <= len(match) <= 50:
                    entities.append((match, category))

        return entities

    def build_glossary(
        self,
        units: List[TranslationUnit],
        min_occurrences: int = 2
    ) -> Dict[str, GlossaryEntry]:
        """
        Build glossary from translation units.

        Args:
            units: List of translation units
            min_occurrences: Minimum occurrences to include in glossary

        Returns:
            Dict mapping term_crc32 to GlossaryEntry
        """
        # First pass: count entities
        entity_counts: Dict[str, Dict] = {}

        for unit in units:
            entities = self.extract_entities(unit.text_normalized)

            for entity_text, category in entities:
                # Normalize for matching
                normalized = entity_text.strip().lower()
                term_crc = format(zlib.crc32(normalized.encode()) & 0xFFFFFFFF, '08X')

                if term_crc not in entity_counts:
                    entity_counts[term_crc] = {
                        'text': entity_text,  # Keep first occurrence's casing
                        'category': category,
                        'count': 0,
                        'unit_ids': []
                    }

                entity_counts[term_crc]['count'] += 1
                if unit.id not in entity_counts[term_crc]['unit_ids']:
                    entity_counts[term_crc]['unit_ids'].append(unit.id)

        # Build glossary with entries meeting threshold
        glossary = {}

        for term_crc, data in entity_counts.items():
            if data['count'] >= min_occurrences:
                glossary[term_crc] = GlossaryEntry(
                    term_crc32=term_crc,
                    term_text=data['text'],
                    first_translation="",  # To be filled during translation
                    occurrences=data['count'],
                    unit_ids=data['unit_ids']
                )

        return glossary

    def build_glossary_from_dup_groups(
        self,
        units: List[TranslationUnit]
    ) -> Dict[str, List[str]]:
        """
        Build glossary mapping from dup_group_id to unit IDs.

        This allows "first translation wins" for identical strings.

        Returns:
            Dict mapping dup_group_id to list of unit IDs
        """
        dup_groups: Dict[str, List[str]] = {}

        for unit in units:
            if unit.dup_group_id:
                if unit.dup_group_id not in dup_groups:
                    dup_groups[unit.dup_group_id] = []
                dup_groups[unit.dup_group_id].append(unit.id)

        # Only keep groups with 2+ members
        return {k: v for k, v in dup_groups.items() if len(v) >= 2}

    def export_glossary(
        self,
        glossary: Dict[str, GlossaryEntry],
        dup_groups: Dict[str, List[str]],
        output_path: str
    ):
        """Export glossary to JSON file."""
        data = {
            'version': '2.1',
            'generated': datetime.now().isoformat(),
            'entities': {
                crc: {
                    'term_crc32': entry.term_crc32,
                    'term_text': entry.term_text,
                    'first_translation': entry.first_translation,
                    'occurrences': entry.occurrences,
                    'unit_ids': entry.unit_ids
                }
                for crc, entry in glossary.items()
            },
            'dup_groups': dup_groups,
            'instructions': (
                "Use 'first_translation' field to maintain consistency. "
                "When translating a term for the first time, record it. "
                "For subsequent occurrences, use the recorded translation."
            )
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# =============================================================================
# v2.1: TWO-PASS TRANSLATOR
# =============================================================================

@dataclass
class TwoPassResult:
    """Result of two-pass translation."""
    unit_id: str
    text_pass1: str              # First pass translation
    text_pass2: str              # Second pass (shortened) if needed
    pass1_valid: bool
    pass2_needed: bool
    pass2_valid: bool
    final_text: str
    shortening_applied: bool


class TwoPassTranslator:
    """
    v2.1: Two-pass translation for quality + length compliance.

    Pass 1: Free translation with placeholder preservation
    Pass 2: Compression/shortening only for units that exceed limits

    This reduces blocking without sacrificing quality.
    """

    def __init__(
        self,
        encoder: EncoderRegistry = None,
        validator: TranslationValidator = None
    ):
        self.encoder = encoder or ENCODER_REGISTRY
        self.validator = validator

    def check_needs_shortening(
        self,
        translated: str,
        constraints: FieldConstraints,
        wrap_hint: WrapHint,
        encoding: str = 'utf8'
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if translation needs shortening.

        Returns:
            Tuple of (needs_shortening, details)
        """
        details = {
            'byte_length': 0,
            'max_bytes': constraints.max_len_bytes,
            'bytes_over': 0,
            'line_lengths': [],
            'max_cols': wrap_hint.max_cols if wrap_hint else 0,
            'cols_over': 0
        }

        needs_shortening = False

        # Check byte length
        try:
            byte_len = self.encoder.byte_length(translated, encoding)
            details['byte_length'] = byte_len

            if constraints.max_len_bytes > 0 and byte_len > constraints.max_len_bytes:
                details['bytes_over'] = byte_len - constraints.max_len_bytes
                needs_shortening = True
        except Exception:
            pass

        # Check wrap constraints
        if wrap_hint and wrap_hint.max_cols > 0:
            lines = translated.replace('<NEWLINE>', '\n').split('\n')
            details['line_lengths'] = [len(line) for line in lines]

            max_line = max(details['line_lengths']) if details['line_lengths'] else 0
            if max_line > wrap_hint.max_cols:
                details['cols_over'] = max_line - wrap_hint.max_cols
                needs_shortening = True

        return needs_shortening, details

    def prepare_shortening_prompt(
        self,
        original: str,
        translated: str,
        shortening_details: Dict[str, Any]
    ) -> str:
        """
        Prepare a prompt for the AI to shorten the translation.

        Returns:
            Prompt string for second-pass shortening
        """
        prompt_parts = [
            "Shorten this translation while preserving meaning and all <PLACEHOLDERS>:",
            "",
            f"Original: {original}",
            f"Translation: {translated}",
            ""
        ]

        if shortening_details['bytes_over'] > 0:
            prompt_parts.append(
                f"Need to reduce by ~{shortening_details['bytes_over']} bytes "
                f"(current: {shortening_details['byte_length']}, "
                f"max: {shortening_details['max_bytes']})"
            )

        if shortening_details['cols_over'] > 0:
            prompt_parts.append(
                f"Lines too long. Max {shortening_details['max_cols']} chars per line. "
                f"Current max: {max(shortening_details['line_lengths'])}"
            )

        prompt_parts.extend([
            "",
            "Rules:",
            "- Keep all <PLACEHOLDER> tokens exactly as-is",
            "- Preserve line breaks where possible",
            "- Use shorter synonyms",
            "- Remove filler words",
            "- Abbreviate if appropriate for game context"
        ])

        return '\n'.join(prompt_parts)

    def mark_needs_shortening(
        self,
        units: List[TranslationUnit],
        translations: Dict[str, str],
        encoding: str = 'utf8'
    ) -> List[TranslationUnit]:
        """
        Mark units that need shortening after first-pass translation.

        Args:
            units: Original translation units
            translations: Dict mapping unit_id to first-pass translation
            encoding: Encoding to use for byte length check

        Returns:
            Units with needs_shortening flag updated
        """
        for unit in units:
            if unit.id in translations:
                translated = translations[unit.id]
                needs_short, _ = self.check_needs_shortening(
                    translated,
                    unit.constraints,
                    unit.wrap_hint,
                    encoding
                )
                unit.needs_shortening = needs_short

        return units

    def get_units_needing_shortening(
        self,
        units: List[TranslationUnit]
    ) -> List[TranslationUnit]:
        """Get list of units flagged as needing shortening."""
        return [u for u in units if u.needs_shortening]


# =============================================================================
# CORE EXTRACTOR (Neutral Implementation)
# =============================================================================

class TranslationPrepExtractor:
    """
    Core text extractor with neutral output.
    Identity: CRC32 only. No game names, no hardware marketing.
    """

    # Character tables (neutral naming)
    MAIN_CHAR_TABLE = {
        0x00: 'A', 0x01: 'B', 0x02: 'C', 0x03: 'D', 0x04: 'E', 0x05: 'F',
        0x06: 'G', 0x07: 'H', 0x08: 'I', 0x09: 'J', 0x0A: 'K', 0x0B: 'L',
        0x0C: 'M', 0x0D: 'N', 0x0E: 'O', 0x0F: 'P', 0x10: 'Q', 0x11: 'R',
        0x12: 'S', 0x13: 'T', 0x14: 'U', 0x15: 'V', 0x16: 'W', 0x17: 'X',
        0x18: 'Y', 0x19: 'Z', 0x1A: 'a', 0x1B: 'b', 0x1C: 'c', 0x1D: 'd',
        0x1E: 'e', 0x1F: 'f', 0x20: 'g', 0x21: 'h', 0x22: 'i', 0x23: 'j',
        0x24: 'k', 0x25: 'l', 0x26: 'm', 0x27: 'n', 0x28: 'o', 0x29: 'p',
        0x2A: 'q', 0x2B: 'r', 0x2C: 's', 0x2D: 't', 0x2E: 'u', 0x2F: 'v',
        0x30: 'w', 0x31: 'x', 0x32: 'y', 0x33: 'z', 0x34: '0', 0x35: '1',
        0x36: '2', 0x37: '3', 0x38: '4', 0x39: '5', 0x3A: '6', 0x3B: '7',
        0x3C: '8', 0x3D: '9', 0x3E: '!', 0x3F: '?', 0x40: ',', 0x41: '.',
        0x42: '-', 0x43: '...', 0x44: '>', 0x45: '(', 0x46: ')', 0x47: ' ',
        0x48: 'A', 0x49: 'B', 0x4A: 'X', 0x4B: 'Y', 0x4C: 'L', 0x4D: 'R',
        0x4E: '^', 0x4F: 'v', 0x50: '>', 0x51: '<', 0x52: "'", 0x53: '"',
        0x54: '<', 0x55: ':', 0x56: ';', 0x57: '*', 0x58: '/', 0x59: '\\',
        0x5A: '+', 0x5B: '=', 0x5C: '&', 0x5D: '%', 0x5E: '$', 0x5F: '#',
        0x60: '@', 0x61: '!',
        # Control codes
        0x75: '[WAIT_BTN]', 0x76: '[SCROLL]', 0x77: '[COLOR]',
        0x78: '[SPEED]', 0x79: '[CHOOSE2]', 0x7A: '[CHOOSE3]', 0x7B: '[CHOOSE]',
        0x7C: '[WAIT_FRAME]', 0x7D: '[WAIT_INPUT]', 0x7E: '[NEWLINE]', 0x7F: '[END]'
    }

    # Composite tokens
    COMPOSITE_TOKENS = {
        0x88: 'the ', 0x89: 'you ', 0x8A: 'I ', 0x8B: 'to ', 0x8C: 'and ',
        0x8D: 'a ', 0x8E: 'is ', 0x8F: 'it ', 0x90: 'and', 0x91: 'you',
        0x92: 'of ', 0x93: 'have ', 0x94: '[NAME1]', 0x95: '[NAME2]',
        0x96: '[NAME3]', 0x97: '[PLACE1]', 0x98: '[ITEM1]', 0x99: '[NAME4]',
        0x9A: 'your ', 0x9B: 'are ', 0x9C: 'be ', 0x9D: 'not ', 0x9E: 'this ',
        0x9F: 'what ', 0xA0: 'will ', 0xA1: 'can ', 0xA2: 'from ', 0xA3: 'with ',
        0xA4: 'but ', 0xA5: 'his ', 0xA6: 'for ', 0xA7: 'was ', 0xA8: 'has ',
        0xA9: 'by ', 0xAA: 'one ', 0xAB: 'all ', 0xAC: 'were ', 0xAD: 'they ',
        0xAE: 'there ', 0xAF: 'been ', 0xB0: 'their ', 0xB1: 'would ',
        0xB2: 'who ', 0xB3: 'him ', 0xB4: 'she ', 0xB5: 'her ', 0xB6: 'me ',
        0xB7: 'my ', 0xB8: 'out ', 0xB9: 'up ', 0xBA: 'if ', 0xBB: 'no ',
        0xBC: 'so ', 0xBD: 'when ', 0xBE: 'which ', 0xBF: 'them ', 0xC0: 'some ',
        0xC1: 'could ', 0xC2: 'time ', 0xC3: 'very ', 0xC4: 'then ', 0xC5: 'now ',
        0xC6: 'only ', 0xC7: 'its ', 0xC8: 'may ', 0xC9: 'over ', 0xCA: 'any ',
        0xCB: 'where ', 0xCC: 'much ', 0xCD: 'through ', 0xCE: 'back ',
        0xCF: 'good ', 0xD0: 'how ', 0xD1: 'our ', 0xD2: 'well ', 0xD3: 'down ',
        0xD4: 'should ', 0xD5: 'because ', 0xD6: 'each ', 0xD7: 'just ',
        0xD8: 'those ', 0xD9: 'people ', 0xDA: 'take ', 0xDB: 'day ',
        0xDC: 'into ', 0xDD: 'two ', 0xDE: 'see ', 0xDF: 'than ', 0xE0: 'come ',
        0xE1: 'more ', 0xE2: 'also ', 0xE3: 'before ', 0xE4: 'after ',
        0xE5: 'other ', 0xE6: 'The ', 0xE7: '[ITEM2]', 0xE8: '[CURRENCY]'
    }

    def __init__(self, rom_path: str):
        self.rom_path = rom_path
        self.rom_data = None
        self.rom_size = 0
        self.has_header = False
        self.memory_map = 0

        # CRC32 identifiers
        self.crc32_full = ""
        self.crc32_no_header = ""

        # Processing components
        self.encoder = ENCODER_REGISTRY
        self.protector = TokenProtector()
        self.normalizer = TextNormalizer()
        self.validator = TranslationValidator(self.protector, self.encoder)

        # Load ROM
        self._load_rom()
        self._compute_identity()
        self._detect_memory_layout()
        self._register_rom_encoding()

    def _load_rom(self):
        """Load ROM data."""
        with open(self.rom_path, 'rb') as f:
            self.rom_data = bytearray(f.read())
        self.rom_size = len(self.rom_data)

        if self.rom_size % 1024 == 512:
            self.has_header = True

    def _compute_identity(self):
        """Compute CRC32 identifiers."""
        self.crc32_full = format(zlib.crc32(self.rom_data) & 0xFFFFFFFF, '08X')

        if self.has_header:
            self.crc32_no_header = format(
                zlib.crc32(self.rom_data[512:]) & 0xFFFFFFFF, '08X'
            )
        else:
            self.crc32_no_header = self.crc32_full

    def _detect_memory_layout(self):
        """Detect memory mapping type (internal use only)."""
        try:
            offset = 0x7FD5 + (0x200 if self.has_header else 0)
            if offset < len(self.rom_data):
                map_byte = self.rom_data[offset]
                if map_byte in [0x21, 0x31]:
                    self.memory_map = 1
                else:
                    self.memory_map = 0
        except:
            self.memory_map = 0

    def _register_rom_encoding(self):
        """Register ROM-specific encoding based on character tables."""
        # Build reverse mapping
        char_to_byte = {}
        for byte_val, char in self.MAIN_CHAR_TABLE.items():
            if not char.startswith('['):
                if char not in char_to_byte:
                    char_to_byte[char] = byte_val

        self.encoder.register_char_table(f'rom_{self.crc32_no_header}', char_to_byte)

    def _decode_text(self, offset: int, max_length: int = 250) -> Tuple[str, str]:
        """Decode text from offset using character tables."""
        if offset >= len(self.rom_data):
            return "", ""

        text = []
        raw_bytes = []

        for i in range(max_length):
            if offset + i >= len(self.rom_data):
                break

            byte = self.rom_data[offset + i]
            raw_bytes.append(byte)

            if byte == 0x7F:
                text.append('[END]')
                break

            if byte in self.COMPOSITE_TOKENS:
                text.append(self.COMPOSITE_TOKENS[byte])
                continue

            if byte in self.MAIN_CHAR_TABLE:
                text.append(self.MAIN_CHAR_TABLE[byte])
                continue

            text.append(f'[{byte:02X}]')

        decoded = ''.join(text)
        raw_hex = ' '.join(f'{b:02X}' for b in raw_bytes)

        return decoded, raw_hex

    def extract_from_pointer_region(
        self,
        region_offset: int,
        pointer_count: int,
        method_name: str = "region"
    ) -> List[Dict]:
        """Extract texts from a pointer table region."""
        results = []
        base_offset = region_offset
        if self.has_header:
            base_offset += 0x200

        if base_offset >= len(self.rom_data):
            return results

        for i in range(pointer_count):
            ptr_addr = base_offset + (i * 2)
            if ptr_addr + 1 >= len(self.rom_data):
                break

            low = self.rom_data[ptr_addr]
            high = self.rom_data[ptr_addr + 1]
            pointer = (high << 8) | low

            text_offset = base_offset + pointer
            if text_offset >= len(self.rom_data):
                continue

            text, raw_hex = self._decode_text(text_offset, max_length=250)

            if len(text) >= 3 and self._is_valid_text(text):
                results.append({
                    'offset': text_offset,
                    'text': text,
                    'raw_hex': raw_hex,
                    'source': f'{method_name}_{i}',
                    'pointer_index': i
                })

        return results

    def extract_via_entropy_scan(
        self,
        start_offset: int = 0x8000,
        min_length: int = 10
    ) -> List[Dict]:
        """Scan for text regions using entropy analysis."""
        results = []
        window_size = 100
        step = 50

        if self.has_header:
            start_offset += 0x200

        for offset in range(start_offset, len(self.rom_data) - window_size, step):
            window = self.rom_data[offset:offset + window_size]
            entropy = self._calculate_entropy(window)

            if 3.0 <= entropy <= 4.8:
                text, raw_hex = self._decode_text(offset, max_length=100)

                if len(text) >= min_length and self._is_valid_text(text):
                    results.append({
                        'offset': offset,
                        'text': text,
                        'raw_hex': raw_hex,
                        'source': 'entropy_scan',
                        'entropy': round(entropy, 2)
                    })

        return results

    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of data."""
        if not data:
            return 0.0

        freq = Counter(data)
        entropy = 0.0
        data_len = len(data)

        for count in freq.values():
            if count > 0:
                probability = count / data_len
                entropy -= probability * math.log2(probability)

        return entropy

    def _is_valid_text(self, text: str) -> bool:
        """Check if extracted text is likely valid human-readable text."""
        if not text:
            return False

        unknown_count = text.count('[') - text.count('[END]') - text.count('[NEWLINE]')
        unknown_count -= text.count('[WAIT') + text.count('[SCROLL]') + text.count('[COLOR]')
        unknown_count -= text.count('[SPEED]') + text.count('[CHOOSE')
        unknown_count -= text.count('[NAME') + text.count('[ITEM') + text.count('[PLACE')
        unknown_count -= text.count('[CURRENCY]')

        if unknown_count > len(text) * 0.3:
            return False

        alpha_count = sum(1 for c in text if c.isalpha())
        if alpha_count < 3:
            return False

        return True

    def extract_all(self, output_dir: str) -> ExtractionStats:
        """Execute full extraction and export translation package."""
        stats = ExtractionStats(
            crc32_full=self.crc32_full,
            crc32_no_header=self.crc32_no_header,
            rom_size=self.rom_size
        )

        all_items = []

        # Method 1: Primary region
        region1_items = self.extract_from_pointer_region(0x70000, 1000, "region1")
        stats.method_counts['region1'] = len(region1_items)
        all_items.extend(region1_items)

        # Method 2: Secondary region
        region2_items = self.extract_from_pointer_region(0xE0000, 500, "region2")
        stats.method_counts['region2'] = len(region2_items)
        all_items.extend(region2_items)

        # Method 3: Entropy scan
        entropy_items = self.extract_via_entropy_scan(start_offset=0x8000, min_length=10)
        stats.method_counts['entropy'] = len(entropy_items)
        all_items.extend(entropy_items)

        # Deduplicate by offset
        unique_items = {}
        for item in all_items:
            offset = item['offset']
            if offset not in unique_items:
                unique_items[offset] = item

        all_items = list(unique_items.values())
        stats.total_strings = len(all_items)

        # Build translation units
        builder = TranslationUnitBuilder(self.crc32_no_header, self.encoder)
        units = builder.build_translation_units(all_items)

        # v2.1: Apply cluster constraints and detect outliers
        cluster_inferrer = ClusterConstraintInferrer()
        cluster_constraints = cluster_inferrer.infer_cluster_constraints(
            units, f"cluster_{self.crc32_no_header}"
        )
        units = cluster_inferrer.apply_cluster_constraints(units, cluster_constraints)

        # Validate and categorize
        approved_units = []
        blocked_units = []

        # Track statistics
        dup_groups = set()
        outlier_count = 0

        for unit in units:
            if self._validate_unit(unit):
                unit.status = "pending"
                approved_units.append(unit)

                # Count tokens
                if unit.token_info:
                    stats.units_with_tokens += 1
                    for token in unit.token_info:
                        stats.token_counts[token.category] = \
                            stats.token_counts.get(token.category, 0) + 1

                # Track merged
                if unit.merged_from:
                    stats.units_merged += 1

                # Track dup groups
                if unit.dup_group_id:
                    dup_groups.add(unit.dup_group_id)

                # v2.1: Track outliers
                if unit.is_cluster_outlier:
                    outlier_count += 1
            else:
                unit.status = "blocked"
                blocked_units.append(unit)
                for reason in unit.block_reasons:
                    stats.block_reasons_summary[reason] = \
                        stats.block_reasons_summary.get(reason, 0) + 1

        stats.approved_units = len(approved_units)
        stats.blocked_units = len(blocked_units)
        stats.dup_groups = len(dup_groups)

        # Export translation package
        self.export_translation_package(
            output_dir, approved_units, blocked_units, stats,
            cluster_constraints, outlier_count
        )

        return stats

    def _validate_unit(self, unit: TranslationUnit) -> bool:
        """Pre-validation of extraction unit."""
        errors = []

        if not unit.text_normalized.strip():
            errors.append("empty_text")

        unknown_count = unit.text_normalized.count('<BYTE_')
        if unknown_count > len(unit.text_normalized) * 0.4:
            errors.append("too_many_unknowns")

        unit.block_reasons = errors
        return len(errors) == 0

    def export_translation_package(
        self,
        output_dir: str,
        approved_units: List[TranslationUnit],
        blocked_units: List[TranslationUnit],
        stats: ExtractionStats,
        cluster_constraints: ClusterConstraints = None,
        outlier_count: int = 0
    ):
        """Export the professional output files including v2.1 additions."""
        os.makedirs(output_dir, exist_ok=True)
        crc = self.crc32_no_header

        TRANSLATION_INSTRUCTIONS = (
            "Do not translate placeholders <...>. "
            "Preserve line breaks. "
            "Maintain tone consistent with context. "
            "Keep byte length within max_len_bytes."
        )

        # =================================================================
        # File 1: JSONL for AI translation
        # =================================================================
        jsonl_path = os.path.join(output_dir, f"{crc}_translate.jsonl")
        with open(jsonl_path, 'w', encoding='utf-8') as f:
            for unit in approved_units:
                record = {
                    "id": unit.id,
                    "offset": unit.offset,
                    "method": unit.method,
                    "max_len_bytes": unit.constraints.max_len_bytes,
                    "text_src": unit.text_normalized,
                    "context_prev": unit.context_prev,
                    "context_next": unit.context_next,
                    "placeholders": list(unit.placeholders.keys()),
                    "dup_group_id": unit.dup_group_id,
                    "wrap_hint": {
                        "max_cols": unit.wrap_hint.max_cols,
                        "max_lines": unit.wrap_hint.max_lines
                    } if unit.wrap_hint.max_cols > 0 else None,
                    "notes": unit.notes,
                    "translation_instructions": TRANSLATION_INSTRUCTIONS,
                    # v2.1 additions
                    "encoding_detected": unit.encoding_detected,
                    "encoding_confidence": unit.encoding_confidence,
                    "structural_pattern": unit.structural_pattern,
                    "is_cluster_outlier": unit.is_cluster_outlier
                }
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        # =================================================================
        # File 2: Human-friendly TXT
        # =================================================================
        txt_path = os.path.join(output_dir, f"{crc}_translate.txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"# Translation Package\n")
            f.write(f"# CRC32: {crc}\n")
            f.write(f"# Units: {len(approved_units)}\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write(f"#\n")
            f.write(f"# Instructions: {TRANSLATION_INSTRUCTIONS}\n")
            f.write(f"#\n\n")

            for unit in approved_units:
                f.write(f"{'='*60}\n")
                f.write(f"=== UNIT {unit.id} ===\n")
                f.write(f"{'='*60}\n")

                if unit.context_prev:
                    f.write(f"CONTEXT_PREV:\n")
                    for ctx in unit.context_prev:
                        f.write(f"  | {ctx[:80]}\n")

                f.write(f"\nSOURCE:\n")
                f.write(f"  {unit.text_normalized}\n")

                f.write(f"\nTEXT (translate below):\n")
                f.write(f"  {unit.text_normalized}\n")

                if unit.context_next:
                    f.write(f"\nCONTEXT_NEXT:\n")
                    for ctx in unit.context_next:
                        f.write(f"  | {ctx[:80]}\n")

                if unit.placeholders:
                    f.write(f"\nTOKENS: {' '.join(unit.placeholders.keys())}\n")

                f.write(f"MAX_LEN_BYTES: {unit.constraints.max_len_bytes}\n")

                if unit.wrap_hint.max_cols > 0:
                    f.write(f"WRAP: max_cols={unit.wrap_hint.max_cols}")
                    if unit.wrap_hint.max_lines > 0:
                        f.write(f", max_lines={unit.wrap_hint.max_lines}")
                    f.write(f"\n")

                if unit.dup_group_id:
                    f.write(f"DUP_GROUP: {unit.dup_group_id}\n")

                if unit.notes:
                    f.write(f"NOTES: {unit.notes}\n")

                f.write(f"\n")

        # =================================================================
        # File 3: Reinsertion mapping JSON
        # =================================================================
        mapping_path = os.path.join(output_dir, f"{crc}_reinsertion_mapping.json")
        mapping_data = {
            "crc32": crc,
            "rom_size": self.rom_size,
            "has_header": self.has_header,
            "generated": datetime.now().isoformat(),
            "units": []
        }

        for unit in approved_units:
            # Serialize token_info
            token_info_serialized = [
                {
                    "placeholder": t.placeholder,
                    "original": t.original,
                    "position": t.position,
                    "order_sensitive": t.order_sensitive,
                    "category": t.category
                }
                for t in unit.token_info
            ]

            unit_mapping = {
                "id": unit.id,
                "offset": unit.offset,
                "raw_hex": unit.raw_hex,
                "max_len_bytes": unit.constraints.max_len_bytes,
                "terminator_byte": unit.constraints.terminator_byte,
                "pad_byte": unit.constraints.pad_byte,
                "fixed_field_len": unit.constraints.fixed_field_len,
                "token_map": unit.placeholders,
                "token_info": token_info_serialized,
                "method": unit.method,
                "checksum": unit.checksum,
                "dup_group_id": unit.dup_group_id,
                "merged_from": unit.merged_from,
                "wrap_hint": {
                    "max_cols": unit.wrap_hint.max_cols,
                    "max_lines": unit.wrap_hint.max_lines
                }
            }
            mapping_data["units"].append(unit_mapping)

        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump(mapping_data, f, indent=2, ensure_ascii=False)

        # =================================================================
        # File 4: Auditable Report
        # =================================================================
        report_path = os.path.join(output_dir, f"{crc}_report.txt")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"EXTRACTION REPORT\n")
            f.write(f"{'='*60}\n\n")

            # Identity
            f.write(f"CRC32_FULL: {stats.crc32_full}\n")
            f.write(f"CRC32_NO_HEADER: {stats.crc32_no_header}\n")
            f.write(f"ROM_SIZE: {stats.rom_size}\n")
            f.write(f"TOTAL_STRINGS: {stats.total_strings}\n\n")

            # Method counts
            f.write(f"METHOD COUNTS:\n")
            f.write(f"{'-'*40}\n")
            for method, count in sorted(stats.method_counts.items(), key=lambda x: -x[1]):
                f.write(f"  {method}: {count}\n")
            f.write(f"\n")

            # Unit status
            f.write(f"UNIT STATUS:\n")
            f.write(f"{'-'*40}\n")
            f.write(f"  Approved: {stats.approved_units}\n")
            f.write(f"  Blocked: {stats.blocked_units}\n")
            f.write(f"  With tokens: {stats.units_with_tokens}\n")
            f.write(f"  Merged: {stats.units_merged}\n")
            f.write(f"  Unique dup groups: {stats.dup_groups}\n")
            f.write(f"\n")

            # Top 20 block reasons
            if stats.block_reasons_summary:
                f.write(f"TOP 20 BLOCK REASONS:\n")
                f.write(f"{'-'*40}\n")
                sorted_reasons = sorted(
                    stats.block_reasons_summary.items(),
                    key=lambda x: -x[1]
                )[:20]
                for reason, count in sorted_reasons:
                    f.write(f"  {reason}: {count}\n")
                f.write(f"\n")

            # Top 20 token categories
            if stats.token_counts:
                f.write(f"TOP 20 TOKEN CATEGORIES:\n")
                f.write(f"{'-'*40}\n")
                sorted_tokens = sorted(
                    stats.token_counts.items(),
                    key=lambda x: -x[1]
                )[:20]
                for category, count in sorted_tokens:
                    f.write(f"  {category}: {count}\n")
                f.write(f"\n")

            # Individual token frequency from approved units
            token_freq = Counter()
            for unit in approved_units:
                for token in unit.placeholders.keys():
                    token_freq[token] += 1

            if token_freq:
                f.write("TOP 20 INDIVIDUAL TOKENS:\n")
                f.write(f"{'-'*40}\n")
                for token, count in token_freq.most_common(20):
                    f.write(f"  {token}: {count}\n")

            # v2.1: Cluster and outlier info
            f.write("\n")
            f.write("v2.1 STATISTICS:\n")
            f.write(f"{'-'*40}\n")
            f.write(f"  Cluster outliers: {outlier_count}\n")
            if cluster_constraints:
                f.write(f"  Cluster avg_max_cols: {cluster_constraints.avg_max_cols:.1f}\n")
                f.write(f"  Cluster common_max_cols: {cluster_constraints.common_max_cols}\n")
                f.write(f"  Cluster common_encoding: {cluster_constraints.common_encoding}\n")

        # =================================================================
        # v2.1: File 5: CRC32 Glossary
        # =================================================================
        glossary_builder = GlossaryBuilder()
        glossary = glossary_builder.build_glossary(approved_units, min_occurrences=2)
        dup_groups = glossary_builder.build_glossary_from_dup_groups(approved_units)

        if glossary or dup_groups:
            glossary_path = os.path.join(output_dir, f"{crc}_glossary.json")
            glossary_builder.export_glossary(glossary, dup_groups, glossary_path)


# =============================================================================
# TRANSLATION IMPORT/VALIDATION
# =============================================================================

class TranslationImporter:
    """Import and validate translations from AI or human translators."""

    def __init__(self, mapping_path: str):
        with open(mapping_path, 'r', encoding='utf-8') as f:
            self.mapping = json.load(f)

        self.crc32 = self.mapping['crc32']
        self.encoder = ENCODER_REGISTRY
        self.protector = TokenProtector()
        self.validator = TranslationValidator(self.protector, self.encoder)
        # v2.1 additions
        self.punctuation_validator = StrictPunctuationValidator()
        self.two_pass = TwoPassTranslator(self.encoder, self.validator)

        self.unit_lookup = {
            unit['id']: unit
            for unit in self.mapping['units']
        }

    def import_translations(self, translations_path: str) -> Tuple[List[Dict], List[Dict], Dict]:
        """Import translations from JSONL file and validate."""
        approved = []
        blocked = []
        summary = {
            'total': 0,
            'approved': 0,
            'blocked': 0,
            'reasons': {}
        }

        with open(translations_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                summary['total'] += 1

                unit_id = record.get('id', '')
                text_dst = record.get('text_dst', '')

                if unit_id not in self.unit_lookup:
                    blocked.append({
                        'id': unit_id,
                        'error': 'Unit ID not found'
                    })
                    summary['blocked'] += 1
                    summary['reasons']['id_not_found'] = \
                        summary['reasons'].get('id_not_found', 0) + 1
                    continue

                unit = self.unit_lookup[unit_id]
                token_map = unit.get('token_map', {})
                max_len_bytes = unit.get('max_len_bytes', 0)

                # Reconstruct token_info
                token_info = []
                for t in unit.get('token_info', []):
                    token_info.append(TokenInfo(
                        placeholder=t['placeholder'],
                        original=t['original'],
                        position=t['position'],
                        order_sensitive=t['order_sensitive'],
                        category=t['category']
                    ))

                constraints = FieldConstraints(
                    max_len_bytes=max_len_bytes,
                    terminator_byte=unit.get('terminator_byte', 0x7F),
                    pad_byte=unit.get('pad_byte'),
                    fixed_field_len=unit.get('fixed_field_len')
                )

                # Need source text for full validation
                # This should be in the original translate.jsonl
                src_text = record.get('text_src', '')

                is_valid, errors = self.validator.validate_translation(
                    src=src_text,
                    dst=text_dst,
                    token_map=token_map,
                    token_info=token_info,
                    constraints=constraints
                )

                # v2.1: Punctuation validation
                punct_valid, punct_issues = self.punctuation_validator.validate_punctuation(
                    src_text, text_dst, strict_mode=False
                )
                if punct_issues:
                    errors.extend([f"Punctuation: {issue}" for issue in punct_issues])

                # v2.1: Check if needs shortening
                wrap_hint = WrapHint(
                    max_cols=unit.get('wrap_hint', {}).get('max_cols', 0),
                    max_lines=unit.get('wrap_hint', {}).get('max_lines', 0)
                )
                needs_short, short_details = self.two_pass.check_needs_shortening(
                    text_dst, constraints, wrap_hint
                )

                result = {
                    'id': unit_id,
                    'offset': unit['offset'],
                    'text_dst': text_dst,
                    'token_map': token_map,
                    'max_len_bytes': max_len_bytes,
                    'raw_hex': unit.get('raw_hex', ''),
                    'checksum': unit.get('checksum', ''),
                    # v2.1 additions
                    'needs_shortening': needs_short,
                    'shortening_details': short_details if needs_short else None
                }

                if is_valid and not needs_short:
                    result['status'] = 'approved'
                    approved.append(result)
                    summary['approved'] += 1
                elif is_valid and needs_short:
                    # Approved but needs second pass
                    result['status'] = 'needs_shortening'
                    result['shortening_prompt'] = self.two_pass.prepare_shortening_prompt(
                        src_text, text_dst, short_details
                    )
                    approved.append(result)
                    summary['approved'] += 1
                else:
                    result['status'] = 'blocked'
                    result['errors'] = errors
                    blocked.append(result)
                    summary['blocked'] += 1

                    for error in errors:
                        reason = error.split(':')[0]
                        summary['reasons'][reason] = \
                            summary['reasons'].get(reason, 0) + 1

        return approved, blocked, summary

    def export_validated(
        self,
        approved: List[Dict],
        blocked: List[Dict],
        summary: Dict,
        output_dir: str
    ):
        """Export validation results."""
        os.makedirs(output_dir, exist_ok=True)

        approved_path = os.path.join(output_dir, f"{self.crc32}_approved.jsonl")
        with open(approved_path, 'w', encoding='utf-8') as f:
            for item in approved:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

        blocked_path = os.path.join(output_dir, f"{self.crc32}_blocked.jsonl")
        with open(blocked_path, 'w', encoding='utf-8') as f:
            for item in blocked:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

        report_path = os.path.join(output_dir, f"{self.crc32}_validation_report.txt")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"TRANSLATION VALIDATION REPORT\n")
            f.write(f"{'='*60}\n\n")
            f.write(f"CRC32: {self.crc32}\n")
            f.write(f"Total: {summary['total']}\n")
            f.write(f"Approved: {summary['approved']}\n")
            f.write(f"Blocked: {summary['blocked']}\n\n")

            if summary['reasons']:
                f.write(f"BLOCK REASONS:\n")
                f.write(f"{'-'*40}\n")
                for reason, count in sorted(
                    summary['reasons'].items(),
                    key=lambda x: -x[1]
                ):
                    f.write(f"  {reason}: {count}\n")


# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("TRANSLATION PREP LAYER v2.1")
        print("=" * 40)
        print()
        print("Usage:")
        print("  Extract:  python TRANSLATION_PREP_LAYER.py extract <rom_path> [output_dir]")
        print("  Validate: python TRANSLATION_PREP_LAYER.py validate <mapping.json> <translations.jsonl> [output_dir]")
        print()
        print("Output is identified by CRC32 only. No game names in output.")
        print()
        print("v2.0 Features:")
        print("  - Byte-based validation (EncoderRegistry)")
        print("  - Wrap hints (max_cols, max_lines)")
        print("  - Terminator/padding metadata")
        print("  - Extended token protection (printf, brace, escapes)")
        print("  - Merge guardrails with tracking")
        print("  - Dedupe groups (dup_group_id)")
        print("  - Strict token validation")
        print("  - Auditable reports")
        print()
        print("v2.1 Features:")
        print("  - EncodingGuesser: auto-detect encoding per item/cluster")
        print("  - round_trip_check: encode->decode validation")
        print("  - Cluster-based WrapHint/FieldConstraints with outliers")
        print("  - StrictPunctuationValidator: protect structural patterns")
        print("  - CRC32_glossary.json: entity/term glossary export")
        print("  - two_pass_translate: automatic shortening for exceeded limits")
        return 1

    command = sys.argv[1].lower()

    if command == 'extract':
        if len(sys.argv) < 3:
            print("Error: ROM path required")
            return 1

        rom_path = sys.argv[2]
        output_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.dirname(rom_path)

        if not os.path.exists(rom_path):
            print(f"Error: File not found: {rom_path}")
            return 1

        extractor = TranslationPrepExtractor(rom_path)
        print(f"CRC32: {extractor.crc32_no_header}")
        print(f"Size: {extractor.rom_size}")
        print()

        stats = extractor.extract_all(output_dir)

        print()
        print("EXTRACTION COMPLETE")
        print("=" * 40)
        print(f"CRC32_FULL: {stats.crc32_full}")
        print(f"CRC32_NO_HEADER: {stats.crc32_no_header}")
        print(f"ROM_SIZE: {stats.rom_size}")
        print(f"TOTAL_STRINGS: {stats.total_strings}")
        print()
        print("Method counts:")
        for method, count in stats.method_counts.items():
            print(f"  {method}: {count}")
        print()
        print(f"Approved units: {stats.approved_units}")
        print(f"Blocked units: {stats.blocked_units}")
        print(f"With tokens: {stats.units_with_tokens}")
        print(f"Merged: {stats.units_merged}")
        print(f"Dup groups: {stats.dup_groups}")

        if stats.block_reasons_summary:
            print()
            print("Block reasons:")
            for reason, count in list(stats.block_reasons_summary.items())[:10]:
                print(f"  {reason}: {count}")

        print()
        print(f"Output: {output_dir}")

    elif command == 'validate':
        if len(sys.argv) < 4:
            print("Error: mapping.json and translations.jsonl required")
            return 1

        mapping_path = sys.argv[2]
        translations_path = sys.argv[3]
        output_dir = sys.argv[4] if len(sys.argv) > 4 else os.path.dirname(mapping_path)

        importer = TranslationImporter(mapping_path)
        approved, blocked, summary = importer.import_translations(translations_path)
        importer.export_validated(approved, blocked, summary, output_dir)

        print()
        print("VALIDATION COMPLETE")
        print("=" * 40)
        print(f"CRC32: {importer.crc32}")
        print(f"Total: {summary['total']}")
        print(f"Approved: {summary['approved']}")
        print(f"Blocked: {summary['blocked']}")

        if summary['reasons']:
            print()
            print("Block reasons:")
            for reason, count in list(summary['reasons'].items())[:10]:
                print(f"  {reason}: {count}")

        print()
        print(f"Output: {output_dir}")

    else:
        print(f"Unknown command: {command}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
