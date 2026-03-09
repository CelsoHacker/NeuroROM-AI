# ============================================================================
# AUTO_LEARNING_ENGINE v1.0
# ============================================================================
# Sistema de aprendizado automatico para extracao de texto de ROMs
# 100% neutro (CRC32-only), sem nomes, sem DB externo
# ============================================================================

from __future__ import annotations

import hashlib
import json
import math
import re
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ============================================================================
# UTILITIES
# ============================================================================

def clamp01(x: float) -> float:
    """Clamp value to [0.0, 1.0]."""
    return max(0.0, min(1.0, x))


def sha1_hex(s: str) -> str:
    """SHA1 hash of string."""
    return hashlib.sha1(s.encode("utf-8", errors="ignore")).hexdigest()


def sha256_hex(data: bytes) -> str:
    """SHA256 hash of bytes."""
    return hashlib.sha256(data).hexdigest()


def crc32_hex(data: bytes) -> str:
    """CRC32 hash as uppercase hex."""
    return f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"


def u16le(data: bytes, off: int) -> Optional[int]:
    """Read 16-bit little-endian value."""
    if off < 0 or off + 2 > len(data):
        return None
    return data[off] | (data[off + 1] << 8)


def u16be(data: bytes, off: int) -> Optional[int]:
    """Read 16-bit big-endian value."""
    if off < 0 or off + 2 > len(data):
        return None
    return (data[off] << 8) | data[off + 1]


def u24le(data: bytes, off: int) -> Optional[int]:
    """Read 24-bit little-endian value."""
    if off < 0 or off + 3 > len(data):
        return None
    return data[off] | (data[off + 1] << 8) | (data[off + 2] << 16)


def edit_distance(s1: str, s2: str) -> int:
    """Levenshtein edit distance."""
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


def normalized_edit_distance(s1: str, s2: str) -> float:
    """Normalized edit distance [0..1]."""
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 0.0
    return edit_distance(s1, s2) / max_len


def shannon_entropy(s: str) -> float:
    """Shannon entropy of string characters."""
    if not s:
        return 0.0
    counter = Counter(s)
    n = len(s)
    ent = 0.0
    for count in counter.values():
        p = count / n
        ent -= p * math.log2(p)
    return ent


# ============================================================================
# ENUMS
# ============================================================================

class LearningMode(Enum):
    AUTO_FAST = "AUTO_FAST"
    AUTO_DEEP = "AUTO_DEEP"


class ExtractionMethod(Enum):
    POINTER_TABLE = "POINTER_TABLE"
    POINTER_INDIRECT = "POINTER_INDIRECT"
    SCRIPT_OPCODE = "SCRIPT_OPCODE"
    SEQUENTIAL_SCAN = "SEQUENTIAL_SCAN"
    COMPRESSION_RLE = "COMPRESSION_RLE"
    COMPRESSION_LZSS = "COMPRESSION_LZSS"
    TILE_STREAM = "TILE_STREAM"
    HEADER_ASCII = "HEADER_ASCII"
    CREDITS_ASCII = "CREDITS_ASCII"


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class EncodingGuess:
    """Encoding detection result."""
    encoding: str
    confidence: float
    heuristic_used: str


@dataclass
class WrapHint:
    """Text wrapping constraints."""
    max_cols: int = 0
    max_lines: int = 0
    inferred: bool = False


@dataclass
class FieldConstraints:
    """Field size and format constraints."""
    max_len_bytes: int
    terminator_byte: int = 0x00
    pad_byte: Optional[int] = None
    fixed_field_len: Optional[int] = None


@dataclass
class TokenInfo:
    """Token protection information."""
    token_map: Dict[str, str] = field(default_factory=dict)  # <TOKEN> -> original
    token_categories: Dict[str, str] = field(default_factory=dict)  # <TOKEN> -> category
    order_sensitive: Dict[str, bool] = field(default_factory=dict)  # <TOKEN> -> bool

    def get_tokens(self) -> Set[str]:
        """Get all token placeholders."""
        return set(self.token_map.keys())


@dataclass
class TextItem:
    """Extraction-level record (neutral)."""
    id: str
    source_ref: str  # "offset:0x123456" or "path:/..."
    offset: Optional[int]
    raw_bytes: bytes
    raw_bytes_hex: str
    decoded: str
    encoding: str
    terminator: Optional[int]
    method: str
    confidence: float
    context_group: str = ""
    notes: str = ""


@dataclass
class TranslationUnit:
    """Translation-ready unit with full metadata."""
    id: str
    offset: Optional[int]
    source_ref: str
    method: str
    confidence: float

    # Raw data for round-trip
    raw_bytes: bytes = field(default_factory=bytes)

    # Text content
    text_src: str = ""
    context_prev: str = ""
    context_next: str = ""

    # Constraints
    wrap_hint: WrapHint = field(default_factory=WrapHint)
    constraints: Optional[FieldConstraints] = None

    # Tokens
    token_info: TokenInfo = field(default_factory=TokenInfo)

    # Clustering / dedupe
    cluster_id: str = ""
    dup_group_id: str = ""
    merged_from: List[str] = field(default_factory=list)

    # Encoding detection
    encoding_detected: str = ""
    encoding_confidence: float = 0.0
    structural_pattern: str = ""
    needs_shortening: bool = False
    round_trip_valid: bool = False

    # Policy outputs
    is_tokenized: bool = False
    text_like: bool = True
    reason_codes: List[str] = field(default_factory=list)


@dataclass
class CharTableHypothesis:
    """Character table hypothesis for tile-based text."""
    mapping: Dict[int, str] = field(default_factory=dict)  # tile -> char
    confidence: Dict[int, float] = field(default_factory=dict)  # tile -> confidence
    unknown_tiles: Set[int] = field(default_factory=set)
    frozen_tiles: Set[int] = field(default_factory=set)  # high-confidence mappings


@dataclass
class DecompressHypothesis:
    """Decompression algorithm hypothesis."""
    algorithm: str  # "RLE", "LZSS", "LITERAL"
    params: Dict[str, Any] = field(default_factory=dict)
    success_rate: float = 0.0
    sample_offsets: List[int] = field(default_factory=list)


@dataclass
class OpcodeHypothesis:
    """Script opcode hypothesis."""
    opcode: int
    pattern: str  # "OP_U16_TEXT", "OP_U8_LEN_TEXT", etc.
    success_rate: float = 0.0
    occurrences: int = 0
    text_offsets: List[int] = field(default_factory=list)


@dataclass
class CandidateTextSet:
    """Produced per iteration by the engine."""
    crc32_full: str
    crc32_no512: str
    units: List[TranslationUnit]
    iteration: int = 0

    # Learned artifacts
    charset_hypothesis: Optional[CharTableHypothesis] = None
    decompress_hypotheses: List[DecompressHypothesis] = field(default_factory=list)
    opcode_hypotheses: List[OpcodeHypothesis] = field(default_factory=list)


@dataclass
class PerfectScoreBreakdown:
    """Detailed score breakdown."""
    roundtrip: float
    language: float
    consistency: float
    structure: float
    constraints: float
    total: float

    # Per-component details
    roundtrip_details: Dict[str, Any] = field(default_factory=dict)
    language_details: Dict[str, Any] = field(default_factory=dict)
    consistency_details: Dict[str, Any] = field(default_factory=dict)
    structure_details: Dict[str, Any] = field(default_factory=dict)
    constraints_details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "total": round(self.total, 6),
            "components": {
                "roundtrip": round(self.roundtrip, 6),
                "language": round(self.language, 6),
                "consistency": round(self.consistency, 6),
                "structure": round(self.structure, 6),
                "constraints": round(self.constraints, 6),
            },
            "weights": {
                "roundtrip": 0.30,
                "language": 0.25,
                "consistency": 0.20,
                "structure": 0.15,
                "constraints": 0.10,
            },
            "details": {
                "roundtrip": self.roundtrip_details,
                "language": self.language_details,
                "consistency": self.consistency_details,
                "structure": self.structure_details,
                "constraints": self.constraints_details,
            }
        }


# ============================================================================
# ENCODER REGISTRY
# ============================================================================

class EncoderRegistry:
    """
    Registry for encodings and character tables.
    Supports round-trip encoding/decoding verification.
    """

    VOWELS = set("aeiouAEIOUáàâãéêíóôõúüÁÀÂÃÉÊÍÓÔÕÚÜ")

    def __init__(self):
        self._char_tables: Dict[str, Dict[str, int]] = {}  # name -> char_to_byte
        self._byte_tables: Dict[str, Dict[int, str]] = {}  # name -> byte_to_char

    def register_char_table(self, name: str, char_to_byte: Dict[str, int]):
        """Register a custom character table."""
        self._char_tables[name] = dict(char_to_byte)
        self._byte_tables[name] = {v: k for k, v in char_to_byte.items()}

    def register_tile_table(self, name: str, tile_to_char: Dict[int, str]):
        """Register a tile-to-character table."""
        self._byte_tables[name] = dict(tile_to_char)
        self._char_tables[name] = {v: k for k, v in tile_to_char.items() if len(v) == 1}

    def encode(self, text: str, encoding: str) -> bytes:
        """Encode text to bytes using specified encoding."""
        # Custom table encoding
        if encoding.startswith("table:"):
            table_name = encoding[6:]
            if table_name not in self._char_tables:
                raise ValueError(f"Unknown character table: {table_name}")

            table = self._char_tables[table_name]
            result = bytearray()
            i = 0
            while i < len(text):
                found = False
                # Try longest match first (for multi-char sequences)
                for length in range(min(4, len(text) - i), 0, -1):
                    substr = text[i:i + length]
                    if substr in table:
                        result.append(table[substr])
                        i += length
                        found = True
                        break
                if not found:
                    # Fallback: use byte value if single char
                    result.append(ord(text[i]) & 0xFF)
                    i += 1
            return bytes(result)

        # Standard encodings
        encoding_map = {
            "ascii": "ascii",
            "utf-8": "utf-8",
            "utf-16-le": "utf-16-le",
            "utf-16-be": "utf-16-be",
            "latin-1": "latin-1",
            "iso-8859-1": "iso-8859-1",
            "cp1252": "cp1252",
            "shift_jis": "shift_jis",
            "shift-jis": "shift_jis",
            "sjis": "shift_jis",
        }

        std_enc = encoding_map.get(encoding.lower(), encoding)
        try:
            return text.encode(std_enc, errors="strict")
        except (UnicodeEncodeError, LookupError) as e:
            raise ValueError(f"Encoding error for '{encoding}': {e}")

    def decode(self, blob: bytes, encoding: str) -> str:
        """Decode bytes to text using specified encoding."""
        # Custom table decoding
        if encoding.startswith("table:"):
            table_name = encoding[6:]
            if table_name not in self._byte_tables:
                raise ValueError(f"Unknown byte table: {table_name}")

            table = self._byte_tables[table_name]
            result = []
            for b in blob:
                if b in table:
                    result.append(table[b])
                else:
                    result.append(f"<BYTE_{b:02X}>")
            return "".join(result)

        # Tile stream decoding
        if encoding == "tile_tokens":
            return "".join(f"<TILE_{b:02X}>" for b in blob)

        # Standard encodings
        encoding_map = {
            "ascii": "ascii",
            "utf-8": "utf-8",
            "utf-16-le": "utf-16-le",
            "utf-16-be": "utf-16-be",
            "latin-1": "latin-1",
            "iso-8859-1": "iso-8859-1",
            "cp1252": "cp1252",
            "shift_jis": "shift_jis",
            "shift-jis": "shift_jis",
            "sjis": "shift_jis",
        }

        std_enc = encoding_map.get(encoding.lower(), encoding)
        try:
            return blob.decode(std_enc, errors="strict")
        except (UnicodeDecodeError, LookupError):
            # Fallback to replace mode
            try:
                return blob.decode(std_enc, errors="replace")
            except LookupError:
                return blob.decode("latin-1", errors="replace")

    def byte_length(self, text: str, encoding: str) -> int:
        """Get byte length of encoded text."""
        return len(self.encode(text, encoding))

    def round_trip_check(
        self,
        text: str,
        raw: bytes,
        encoding: str,
        token_info: TokenInfo,
        allow_trim_terminator: bool = True,
        terminator: int = 0x00,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Round-trip verification.

        Returns:
            (success, details_dict)
        """
        details = {
            "text_len": len(text),
            "raw_len": len(raw),
            "encoding": encoding,
        }

        try:
            # Re-encode text
            reenc = self.encode(text, encoding)
            details["reenc_len"] = len(reenc)

            # Check byte equality
            byte_ok = (reenc == raw)

            # Allow trimmed terminator/padding
            if not byte_ok and allow_trim_terminator:
                # Trim trailing terminators from raw
                raw_trimmed = raw.rstrip(bytes([terminator]))
                byte_ok = (reenc == raw_trimmed)
                if byte_ok:
                    details["trimmed_terminator"] = True

            # Re-decode
            dec2 = self.decode(reenc, encoding)

            # Token comparison
            tokens_orig = self._extract_tokens(text)
            tokens_dec2 = self._extract_tokens(dec2)

            tokens_equal = (tokens_orig == tokens_dec2)
            details["tokens_equal"] = tokens_equal
            details["byte_ok"] = byte_ok

            # Check order-sensitive tokens
            order_ok = True
            for token, is_sensitive in token_info.order_sensitive.items():
                if is_sensitive:
                    pos_orig = [m.start() for m in re.finditer(re.escape(token), text)]
                    pos_dec2 = [m.start() for m in re.finditer(re.escape(token), dec2)]
                    if pos_orig != pos_dec2:
                        order_ok = False
                        break

            details["order_ok"] = order_ok

            success = tokens_equal and byte_ok and order_ok
            return success, details

        except Exception as e:
            details["error"] = str(e)
            return False, details

    def _extract_tokens(self, text: str) -> List[str]:
        """Extract all <TOKEN> placeholders from text."""
        return re.findall(r"<[^>]+>", text)


# ============================================================================
# TOKEN PROTECTOR
# ============================================================================

class TokenProtector:
    """
    Protects special tokens and control codes during processing.
    Converts game-specific formats to neutral <TOKEN> placeholders.
    """

    # Token patterns by category
    PATTERNS = {
        "CONTROL": [
            (r"\[END\]", "<END>"),
            (r"\[WAIT\]", "<WAIT>"),
            (r"\[CLEAR\]", "<CLEAR>"),
            (r"\[PAGE\]", "<PAGE>"),
            (r"\[PAUSE\]", "<PAUSE>"),
            (r"\x00", "<END>"),  # Null terminator
        ],
        "NEWLINE": [
            (r"\[NL\]", "<NL>"),
            (r"\[BR\]", "<NL>"),
            (r"\\n", "<NL>"),
            (r"\n", "<NL>"),
            (r"\r\n", "<NL>"),
            (r"\r", "<NL>"),
        ],
        "PRINTF": [
            (r"%[diouxXeEfFgGaAcspn%]", None),  # Keep as-is but mark
            (r"%[-+#0 ]*\d*\.?\d*[diouxXeEfFgGaAcspn]", None),
        ],
        "BRACE": [
            (r"\{[^}]+\}", None),  # {variable}
        ],
        "ESCAPE": [
            (r"\\x[0-9A-Fa-f]{2}", None),  # \xAB
            (r"\\u[0-9A-Fa-f]{4}", None),  # \uABCD
        ],
        "BYTE": [
            (r"\[([0-9A-Fa-f]{2})\]", r"<BYTE_\1>"),
        ],
    }

    def __init__(self):
        self._compiled_patterns: List[Tuple[re.Pattern, str, str, bool]] = []
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns."""
        counter = Counter()

        for category, patterns in self.PATTERNS.items():
            for pattern_tuple in patterns:
                pattern, replacement = pattern_tuple

                try:
                    compiled = re.compile(pattern)
                except re.error:
                    continue

                # Determine if order-sensitive
                order_sensitive = category in ("PRINTF", "BRACE")

                if replacement is None:
                    # Generate placeholder based on category
                    counter[category] += 1
                    replacement = f"<{category}_{counter[category]:02d}>"

                self._compiled_patterns.append(
                    (compiled, replacement, category, order_sensitive)
                )

    def protect(self, text: str) -> Tuple[str, TokenInfo]:
        """
        Protect tokens in text.

        Returns:
            (protected_text, token_info)
        """
        token_info = TokenInfo()
        result = text

        # Track replacements
        replacements: Dict[str, str] = {}  # placeholder -> original

        for compiled, replacement, category, order_sensitive in self._compiled_patterns:
            matches = list(compiled.finditer(result))

            for i, match in enumerate(reversed(matches)):
                original = match.group(0)

                # Generate unique placeholder if needed
                if replacement.endswith("_>"):
                    # Numbered placeholder
                    placeholder = replacement
                else:
                    placeholder = replacement

                # Check if already have this mapping
                if original not in replacements.values():
                    if placeholder in replacements:
                        # Generate unique placeholder
                        base = placeholder.rstrip(">")
                        idx = 1
                        while f"{base}_{idx}>" in replacements:
                            idx += 1
                        placeholder = f"{base}_{idx}>"

                    replacements[placeholder] = original
                    token_info.token_map[placeholder] = original
                    token_info.token_categories[placeholder] = category
                    token_info.order_sensitive[placeholder] = order_sensitive
                else:
                    # Find existing placeholder
                    for ph, orig in replacements.items():
                        if orig == original:
                            placeholder = ph
                            break

                # Replace in text
                start, end = match.span()
                result = result[:start] + placeholder + result[end:]

        return result, token_info

    def unprotect(self, translated: str, token_info: TokenInfo) -> str:
        """
        Restore original tokens from placeholders.

        Returns:
            unprotected_text
        """
        result = translated

        # Sort by placeholder length (longest first) to avoid partial replacements
        for placeholder in sorted(token_info.token_map.keys(), key=len, reverse=True):
            original = token_info.token_map[placeholder]
            result = result.replace(placeholder, original)

        return result

    def validate_tokens(
        self,
        original: str,
        translated: str,
        token_info: TokenInfo,
    ) -> Tuple[bool, List[str]]:
        """
        Validate that all tokens are preserved in translation.

        Returns:
            (valid, list_of_errors)
        """
        errors = []

        # Get token multisets
        orig_tokens = Counter(re.findall(r"<[^>]+>", original))
        trans_tokens = Counter(re.findall(r"<[^>]+>", translated))

        # Check multiset equality
        if orig_tokens != trans_tokens:
            missing = orig_tokens - trans_tokens
            extra = trans_tokens - orig_tokens

            if missing:
                errors.append(f"Missing tokens: {dict(missing)}")
            if extra:
                errors.append(f"Extra tokens: {dict(extra)}")

        # Check order-sensitive tokens
        for token, is_sensitive in token_info.order_sensitive.items():
            if not is_sensitive:
                continue

            orig_positions = [m.start() for m in re.finditer(re.escape(token), original)]
            trans_positions = [m.start() for m in re.finditer(re.escape(token), translated)]

            if len(orig_positions) != len(trans_positions):
                errors.append(f"Order-sensitive token count mismatch: {token}")

        # Check for broken brackets
        open_count = translated.count("<")
        close_count = translated.count(">")
        if open_count != close_count:
            errors.append(f"Unbalanced brackets: < = {open_count}, > = {close_count}")

        return len(errors) == 0, errors


# ============================================================================
# TEXT NORMALIZER
# ============================================================================

class TextNormalizer:
    """Normalizes text for consistent processing."""

    @staticmethod
    def normalize(text: str) -> str:
        """
        Normalize text:
        - Collapse multiple spaces
        - Normalize newlines
        - Strip leading/trailing whitespace per line
        """
        # Normalize newlines
        result = text.replace("\r\n", "\n").replace("\r", "\n")

        # Collapse multiple spaces (preserve single spaces)
        result = re.sub(r" +", " ", result)

        # Strip each line
        lines = result.split("\n")
        lines = [line.strip() for line in lines]

        # Rejoin
        result = "\n".join(lines)

        # Remove leading/trailing newlines
        result = result.strip("\n")

        return result

    @staticmethod
    def normalize_for_comparison(text: str) -> str:
        """
        Aggressive normalization for comparison.
        Removes all whitespace variations.
        """
        # Remove all token placeholders temporarily
        tokens = re.findall(r"<[^>]+>", text)
        temp = re.sub(r"<[^>]+>", "\x00", text)

        # Normalize
        temp = temp.lower()
        temp = re.sub(r"\s+", " ", temp)
        temp = temp.strip()

        # Restore tokens (simplified)
        for i, token in enumerate(tokens):
            temp = temp.replace("\x00", token.lower(), 1)

        return temp


# ============================================================================
# ENCODING GUESSER
# ============================================================================

class EncodingGuesser:
    """Guesses encoding from raw bytes using heuristics."""

    def guess_bytes(self, raw: bytes) -> EncodingGuess:
        """Guess encoding for a single byte sequence."""
        if not raw:
            return EncodingGuess("ascii", 0.5, "empty_input")

        # Check for UTF-16 BOM
        if raw[:2] == b"\xff\xfe":
            return EncodingGuess("utf-16-le", 0.99, "bom_utf16le")
        if raw[:2] == b"\xfe\xff":
            return EncodingGuess("utf-16-be", 0.99, "bom_utf16be")

        # Check for UTF-8 BOM
        if raw[:3] == b"\xef\xbb\xbf":
            return EncodingGuess("utf-8", 0.99, "bom_utf8")

        # Check for alternating null bytes (UTF-16)
        if len(raw) >= 4:
            null_even = sum(1 for i in range(0, len(raw), 2) if raw[i] == 0)
            null_odd = sum(1 for i in range(1, len(raw), 2) if raw[i] == 0)

            if null_odd > len(raw) * 0.3 and null_even < len(raw) * 0.1:
                return EncodingGuess("utf-16-le", 0.85, "alternating_nulls_le")
            if null_even > len(raw) * 0.3 and null_odd < len(raw) * 0.1:
                return EncodingGuess("utf-16-be", 0.85, "alternating_nulls_be")

        # Check ASCII range
        ascii_count = sum(1 for b in raw if 0x20 <= b <= 0x7E)
        ascii_ratio = ascii_count / len(raw)

        if ascii_ratio > 0.95:
            return EncodingGuess("ascii", 0.90, "high_ascii_ratio")

        # Check for Shift-JIS patterns
        sjis_score = self._check_sjis(raw)
        if sjis_score > 0.7:
            return EncodingGuess("shift_jis", sjis_score, "sjis_patterns")

        # Check for UTF-8 multibyte
        utf8_score = self._check_utf8(raw)
        if utf8_score > 0.8:
            return EncodingGuess("utf-8", utf8_score, "utf8_multibyte")

        # Default to Latin-1 (can encode any byte)
        if ascii_ratio > 0.6:
            return EncodingGuess("latin-1", 0.70, "extended_ascii")

        # Likely binary/tile data
        return EncodingGuess("tile_tokens", 0.50, "binary_data")

    def _check_sjis(self, raw: bytes) -> float:
        """Check for Shift-JIS patterns."""
        sjis_pairs = 0
        i = 0
        while i < len(raw) - 1:
            b1 = raw[i]
            b2 = raw[i + 1]

            # Shift-JIS lead byte ranges
            if (0x81 <= b1 <= 0x9F) or (0xE0 <= b1 <= 0xFC):
                # Valid trail byte range
                if (0x40 <= b2 <= 0x7E) or (0x80 <= b2 <= 0xFC):
                    sjis_pairs += 1
                    i += 2
                    continue
            i += 1

        if len(raw) < 2:
            return 0.0
        return min(1.0, sjis_pairs * 2 / len(raw))

    def _check_utf8(self, raw: bytes) -> float:
        """Check for valid UTF-8 multibyte sequences."""
        valid_multibyte = 0
        invalid = 0
        i = 0

        while i < len(raw):
            b = raw[i]

            if b < 0x80:
                i += 1
                continue

            # Determine expected length
            if (b & 0xE0) == 0xC0:
                length = 2
            elif (b & 0xF0) == 0xE0:
                length = 3
            elif (b & 0xF8) == 0xF0:
                length = 4
            else:
                invalid += 1
                i += 1
                continue

            # Check continuation bytes
            valid = True
            for j in range(1, length):
                if i + j >= len(raw) or (raw[i + j] & 0xC0) != 0x80:
                    valid = False
                    break

            if valid:
                valid_multibyte += 1
                i += length
            else:
                invalid += 1
                i += 1

        total = valid_multibyte + invalid
        if total == 0:
            return 0.5
        return valid_multibyte / total

    def guess_cluster_encoding(self, raw_list: List[bytes]) -> EncodingGuess:
        """Guess encoding for a cluster of byte sequences."""
        if not raw_list:
            return EncodingGuess("ascii", 0.5, "empty_cluster")

        guesses = [self.guess_bytes(raw) for raw in raw_list]

        # Vote by encoding
        encoding_votes: Counter = Counter()
        confidence_sum: Dict[str, float] = defaultdict(float)

        for guess in guesses:
            encoding_votes[guess.encoding] += 1
            confidence_sum[guess.encoding] += guess.confidence

        # Get winner
        winner, count = encoding_votes.most_common(1)[0]
        avg_confidence = confidence_sum[winner] / count

        return EncodingGuess(winner, avg_confidence, "cluster_vote")


# ============================================================================
# TEXT-LIKE DETECTOR
# ============================================================================

class TextLikeDetector:
    """Determines if a translation unit contains human-readable text."""

    def __init__(self):
        self.vowels = set("aeiouAEIOUáàâãéêíóôõúüÁÀÂÃÉÊÍÓÔÕÚÜ")
        self.consonants = set("bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ")

    def is_text_like(self, unit: TranslationUnit) -> Tuple[bool, float, List[str]]:
        """
        Determine if unit contains text-like content.

        Returns:
            (is_text_like, confidence, reason_codes)
        """
        text = unit.text_src
        reasons = []

        # Remove tokens for analysis
        cleaned = re.sub(r"<[^>]+>", "", text)

        if not cleaned.strip():
            # Only tokens - might be valid (menu item with just icon)
            if text.strip():
                return True, 0.6, ["TOKENS_ONLY"]
            return False, 0.0, ["EMPTY_AFTER_TOKEN_REMOVAL"]

        n = len(cleaned)

        # Calculate metrics
        alpha_count = sum(1 for c in cleaned if c.isalpha())
        alnum_count = sum(1 for c in cleaned if c.isalnum())
        vowel_count = sum(1 for c in cleaned if c in self.vowels)
        space_count = cleaned.count(" ")

        alpha_ratio = alpha_count / n if n > 0 else 0
        alnum_ratio = alnum_count / n if n > 0 else 0
        vowel_ratio = vowel_count / max(1, alpha_count)
        space_ratio = space_count / n if n > 0 else 0

        # Check for bad consonant runs
        bad_runs = len(re.findall(r"[bcdfghjklmnpqrstvwxyz]{6,}", cleaned.lower()))

        # Calculate confidence
        scores = []

        # Alphanumeric ratio
        if alnum_ratio >= 0.6:
            scores.append(1.0)
        elif alnum_ratio >= 0.4:
            scores.append(0.7)
            reasons.append("LOW_ALNUM_RATIO")
        else:
            scores.append(0.3)
            reasons.append("VERY_LOW_ALNUM_RATIO")

        # Vowel ratio (for alphabetic content)
        if alpha_ratio > 0.3:
            if vowel_ratio >= 0.25:
                scores.append(1.0)
            elif vowel_ratio >= 0.15:
                scores.append(0.6)
                reasons.append("LOW_VOWEL_RATIO")
            else:
                scores.append(0.2)
                reasons.append("VERY_LOW_VOWEL_RATIO")

        # Bad consonant runs
        if bad_runs == 0:
            scores.append(1.0)
        elif bad_runs == 1:
            scores.append(0.5)
            reasons.append("CONSONANT_RUN")
        else:
            scores.append(0.0)
            reasons.append("MULTIPLE_CONSONANT_RUNS")

        # Space ratio (should be reasonable for text)
        if 0.05 <= space_ratio <= 0.30:
            scores.append(1.0)
        elif space_ratio < 0.05 and n > 20:
            scores.append(0.5)
            reasons.append("FEW_SPACES")
        else:
            scores.append(0.8)

        # Overall confidence
        confidence = sum(scores) / len(scores) if scores else 0.5

        # High-confidence method bonuses
        if unit.method in ("POINTER_TABLE", "SCRIPT_OPCODE"):
            confidence = min(1.0, confidence + 0.1)

        is_text = confidence >= 0.5
        return is_text, confidence, reasons


# ============================================================================
# DETERMINISTIC TOKENIZER (FALLBACK)
# ============================================================================

class DeterministicTokenizer:
    """Creates deterministic token representation for non-text data."""

    # Common byte -> semantic token mappings
    COMMON_MAPPINGS = {
        0x00: "<END>",
        0x0A: "<NL>",
        0x0D: "<CR>",
        0x20: "<SPACE>",
    }

    def tokenize_bytes(self, raw: bytes, charset: Optional[CharTableHypothesis] = None) -> str:
        """
        Convert bytes to token stream.
        Uses charset hypothesis if available.
        """
        result = []

        for b in raw:
            # Check common mappings
            if b in self.COMMON_MAPPINGS:
                result.append(self.COMMON_MAPPINGS[b])
            # Check charset hypothesis
            elif charset and b in charset.mapping:
                char = charset.mapping[b]
                if char.startswith("<"):
                    result.append(char)
                else:
                    result.append(char)
            else:
                result.append(f"<BYTE_{b:02X}>")

        return "".join(result)

    def tokenize_tiles(
        self,
        indices: List[int],
        charset: Optional[CharTableHypothesis] = None,
    ) -> str:
        """
        Convert tile indices to token stream.
        Uses charset hypothesis if available.
        """
        result = []

        for tile in indices:
            if charset and tile in charset.mapping:
                char = charset.mapping[tile]
                if char.startswith("<"):
                    result.append(char)
                else:
                    result.append(char)
            else:
                result.append(f"<TILE_{tile:02X}>")

        return "".join(result)


# ============================================================================
# PERFECT SCORE CALCULATOR
# ============================================================================

class PerfectScoreCalculator:
    """
    Calculates PerfectScore (0..1) with formula:

    PerfectScore = clamp01(
        0.30 * RoundTripScore +
        0.25 * LanguageScore +
        0.20 * ConsistencyScore +
        0.15 * StructureScore +
        0.10 * ConstraintScore
    )
    """

    def __init__(self, encoder: EncoderRegistry):
        self.encoder = encoder
        self.vowels = set("aeiouAEIOUáàâãéêíóôõúüÁÀÂÃÉÊÍÓÔÕÚÜ")
        self.consonants = set("bcdfghjklmnpqrstvwxyz")

    def compute(self, candidate: CandidateTextSet) -> PerfectScoreBreakdown:
        """Compute full PerfectScore breakdown."""
        units = candidate.units

        if not units:
            return PerfectScoreBreakdown(
                roundtrip=0.0,
                language=0.0,
                consistency=0.0,
                structure=0.0,
                constraints=0.0,
                total=0.0,
            )

        # Compute each component
        roundtrip, rt_details = self._compute_roundtrip(units)
        language, lang_details = self._compute_language(units)
        consistency, cons_details = self._compute_consistency(units, candidate.charset_hypothesis)
        structure, struct_details = self._compute_structure(units)
        constraints, const_details = self._compute_constraints(units)

        # Weighted sum
        total = clamp01(
            0.30 * roundtrip +
            0.25 * language +
            0.20 * consistency +
            0.15 * structure +
            0.10 * constraints
        )

        return PerfectScoreBreakdown(
            roundtrip=roundtrip,
            language=language,
            consistency=consistency,
            structure=structure,
            constraints=constraints,
            total=total,
            roundtrip_details=rt_details,
            language_details=lang_details,
            consistency_details=cons_details,
            structure_details=struct_details,
            constraints_details=const_details,
        )

    def _compute_roundtrip(self, units: List[TranslationUnit]) -> Tuple[float, Dict]:
        """
        RoundTripScore (0..1) - proof of reversibility.

        For each item with raw_bytes:
        - reenc = encode(text)
        - dec2 = decode(reenc)
        - same_tokens = tokens preserved
        - byte_ok = bytes match (with terminator trim allowed)
        - rti = 1.0 if (same_tokens and byte_ok) else 0.0
        """
        scores = []
        details = {
            "total_checked": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
        }

        for unit in units:
            if not unit.raw_bytes:
                details["skipped"] += 1
                continue

            details["total_checked"] += 1

            try:
                encoding = unit.encoding_detected or "ascii"
                success, _ = self.encoder.round_trip_check(
                    unit.text_src,
                    unit.raw_bytes,
                    encoding,
                    unit.token_info,
                )

                if success:
                    scores.append(1.0)
                    details["passed"] += 1
                else:
                    scores.append(0.0)
                    details["failed"] += 1

            except Exception:
                scores.append(0.0)
                details["failed"] += 1

        score = sum(scores) / len(scores) if scores else 1.0
        return score, details

    def _compute_language(self, units: List[TranslationUnit]) -> Tuple[float, Dict]:
        """
        LanguageScore (0..1) - "looks like human language".

        For each text t (normalized, without tokens):
        - alpha, alnum, vowel, space, punct ratios
        - bad_runs (consonant runs >= 6)
        - entropy

        S1 = clamp01((alnum - 0.55) / 0.35)
        S2 = clamp01((vowel - 0.25) / 0.20)
        S3 = clamp01(1.0 - (bad_runs / 2.0))
        S4 = clamp01(1.0 - abs(space - 0.16) / 0.16)
        S5 = clamp01(1.0 - max(0, entropy - 4.3) / 1.2)

        LanguageItemScore = 0.30*S1 + 0.25*S2 + 0.20*S3 + 0.15*S4 + 0.10*S5
        """
        scores = []
        details = {
            "total_text_like": 0,
            "avg_alnum_ratio": 0.0,
            "avg_vowel_ratio": 0.0,
            "avg_entropy": 0.0,
        }

        alnum_ratios = []
        vowel_ratios = []
        entropies = []

        for unit in units:
            if not unit.text_like:
                continue

            details["total_text_like"] += 1

            # Remove tokens
            cleaned = re.sub(r"<[^>]+>", "", unit.text_src)
            cleaned = cleaned.replace("\n", " ")

            if not cleaned.strip():
                continue

            score = self._language_item_score(cleaned)
            scores.append(score)

            # Collect metrics for details
            n = len(cleaned)
            alnum_ratio = sum(1 for c in cleaned if c.isalnum()) / n
            alpha_count = sum(1 for c in cleaned if c.isalpha())
            vowel_ratio = sum(1 for c in cleaned if c in self.vowels) / max(1, alpha_count)
            entropy = shannon_entropy(cleaned)

            alnum_ratios.append(alnum_ratio)
            vowel_ratios.append(vowel_ratio)
            entropies.append(entropy)

        if alnum_ratios:
            details["avg_alnum_ratio"] = sum(alnum_ratios) / len(alnum_ratios)
            details["avg_vowel_ratio"] = sum(vowel_ratios) / len(vowel_ratios)
            details["avg_entropy"] = sum(entropies) / len(entropies)

        score = sum(scores) / len(scores) if scores else 0.0
        return score, details

    def _language_item_score(self, text: str) -> float:
        """Calculate language score for a single text item."""
        if not text:
            return 0.0

        n = len(text)

        # Calculate ratios
        alnum = sum(1 for c in text if c.isalnum()) / n
        alpha_count = sum(1 for c in text if c.isalpha())
        vowel = sum(1 for c in text if c in self.vowels) / max(1, alpha_count)
        space = text.count(" ") / n

        # Count bad consonant runs
        bad_runs = 0
        run = 0
        for c in text.lower():
            if c in self.consonants:
                run += 1
                if run >= 6:
                    bad_runs += 1
                    run = 0
            else:
                run = 0

        # Entropy
        ent = shannon_entropy(text)

        # Component scores
        S1 = clamp01((alnum - 0.55) / 0.35)
        S2 = clamp01((vowel - 0.25) / 0.20)
        S3 = clamp01(1.0 - (bad_runs / 2.0))
        S4 = clamp01(1.0 - abs(space - 0.16) / 0.16)
        S5 = clamp01(1.0 - max(0.0, ent - 4.3) / 1.2)

        return 0.30 * S1 + 0.25 * S2 + 0.20 * S3 + 0.15 * S4 + 0.10 * S5

    def _compute_consistency(
        self,
        units: List[TranslationUnit],
        charset: Optional[CharTableHypothesis],
    ) -> Tuple[float, Dict]:
        """
        ConsistencyScore (0..1) - stable tile/char mapping and tokens.

        A) TileConsistency: measure conflict per tile
        B) DupConsistency: same dup_group should produce coherent output
        C) TokenIntegrity: all tokens preserved

        ConsistencyScore = 0.55*TileConsistency + 0.25*DupConsistency + 0.20*TokenIntegrity
        """
        details = {
            "tile_consistency": 1.0,
            "dup_consistency": 1.0,
            "token_integrity": 1.0,
        }

        # A) Tile consistency
        if charset and charset.mapping:
            conflicts = []
            for tile, char in charset.mapping.items():
                conf = charset.confidence.get(tile, 0.5)
                conflict = 1.0 - conf
                conflicts.append(conflict)

            if conflicts:
                details["tile_consistency"] = 1.0 - (sum(conflicts) / len(conflicts))

        # B) Dup group consistency
        dup_groups: Dict[str, List[str]] = defaultdict(list)
        for unit in units:
            if unit.dup_group_id:
                normalized = TextNormalizer.normalize_for_comparison(unit.text_src)
                dup_groups[unit.dup_group_id].append(normalized)

        if dup_groups:
            group_variances = []
            for group_id, texts in dup_groups.items():
                if len(texts) < 2:
                    continue

                # Calculate average pairwise edit distance
                distances = []
                for i in range(len(texts)):
                    for j in range(i + 1, len(texts)):
                        distances.append(normalized_edit_distance(texts[i], texts[j]))

                if distances:
                    group_variances.append(sum(distances) / len(distances))

            if group_variances:
                details["dup_consistency"] = clamp01(1.0 - (sum(group_variances) / len(group_variances)))

        # C) Token integrity
        token_scores = []
        for unit in units:
            if not unit.token_info.token_map:
                token_scores.append(1.0)
                continue

            # Check all tokens present in text
            text_tokens = set(re.findall(r"<[^>]+>", unit.text_src))
            expected_tokens = set(unit.token_info.token_map.keys())

            if expected_tokens:
                present = len(expected_tokens & text_tokens)
                token_scores.append(present / len(expected_tokens))
            else:
                token_scores.append(1.0)

        if token_scores:
            details["token_integrity"] = sum(token_scores) / len(token_scores)

        # Combined score
        score = clamp01(
            0.55 * details["tile_consistency"] +
            0.25 * details["dup_consistency"] +
            0.20 * details["token_integrity"]
        )

        return score, details

    def _compute_structure(self, units: List[TranslationUnit]) -> Tuple[float, Dict]:
        """
        StructureScore (0..1) - message structure quality.

        Metrics:
        - median_len: median text length
        - short_ratio: percentage of texts with len < 4
        - end_punct_ratio: percentage ending with .!? or <END>
        - newline_reasonable: lines within wrap_hint.max_cols

        A = clamp01((median_len - 6) / 10)
        B = clamp01(1 - (short_ratio / 0.25))
        C = clamp01((end_punct_ratio - 0.20) / 0.50)
        D = clamp01(newline_reasonable)

        StructureScore = 0.35*A + 0.30*B + 0.20*C + 0.15*D
        """
        details = {
            "median_len": 0,
            "short_ratio": 0.0,
            "end_punct_ratio": 0.0,
            "newline_reasonable": 1.0,
        }

        text_like_units = [u for u in units if u.text_like]

        if not text_like_units:
            return 0.0, details

        # Calculate lengths (without tokens)
        lengths = []
        for unit in text_like_units:
            cleaned = re.sub(r"<[^>]+>", "", unit.text_src).strip()
            lengths.append(len(cleaned))

        # Median length
        lengths_sorted = sorted(lengths)
        median_len = lengths_sorted[len(lengths_sorted) // 2]
        details["median_len"] = median_len

        # Short ratio
        short_count = sum(1 for L in lengths if L < 4)
        short_ratio = short_count / len(lengths)
        details["short_ratio"] = short_ratio

        # End punctuation ratio
        end_punct_count = 0
        for unit in text_like_units:
            text = unit.text_src.rstrip()
            if text.endswith((".", "!", "?", "<END>", "<NL>")):
                end_punct_count += 1
        end_punct_ratio = end_punct_count / len(text_like_units)
        details["end_punct_ratio"] = end_punct_ratio

        # Newline reasonable
        newline_ok = 0
        newline_checked = 0
        for unit in text_like_units:
            if unit.wrap_hint.max_cols > 0:
                newline_checked += 1
                lines = unit.text_src.split("\n")
                all_ok = all(len(line) <= unit.wrap_hint.max_cols for line in lines)
                if all_ok:
                    newline_ok += 1

        if newline_checked > 0:
            details["newline_reasonable"] = newline_ok / newline_checked

        # Component scores
        A = clamp01((median_len - 6) / 10)
        B = clamp01(1 - (short_ratio / 0.25))
        C = clamp01((end_punct_ratio - 0.20) / 0.50)
        D = clamp01(details["newline_reasonable"])

        score = 0.35 * A + 0.30 * B + 0.20 * C + 0.15 * D

        return score, details

    def _compute_constraints(self, units: List[TranslationUnit]) -> Tuple[float, Dict]:
        """
        ConstraintScore (0..1) - bytes/wrap always ok.

        For each unit:
        - byte_ok = byte_length(text) <= max_len_bytes
        - wrap_ok = lines within max_cols/max_lines

        ConstraintScore = mean(1.0 if (byte_ok and wrap_ok) else 0.0)
        """
        details = {
            "total_checked": 0,
            "byte_violations": 0,
            "wrap_violations": 0,
        }

        scores = []

        for unit in units:
            if not unit.constraints:
                scores.append(1.0)
                continue

            details["total_checked"] += 1

            # Check byte length
            byte_ok = True
            if unit.constraints.max_len_bytes > 0:
                try:
                    encoding = unit.encoding_detected or "ascii"
                    byte_len = self.encoder.byte_length(unit.text_src, encoding)
                    if byte_len > unit.constraints.max_len_bytes:
                        byte_ok = False
                        details["byte_violations"] += 1
                except Exception:
                    byte_ok = False
                    details["byte_violations"] += 1

            # Check wrap constraints
            wrap_ok = True
            if unit.wrap_hint.max_cols > 0:
                lines = unit.text_src.split("\n")
                for line in lines:
                    # Remove tokens for length check
                    cleaned = re.sub(r"<[^>]+>", "", line)
                    if len(cleaned) > unit.wrap_hint.max_cols:
                        wrap_ok = False
                        details["wrap_violations"] += 1
                        break

            if unit.wrap_hint.max_lines > 0:
                line_count = unit.text_src.count("\n") + 1
                if line_count > unit.wrap_hint.max_lines:
                    wrap_ok = False
                    details["wrap_violations"] += 1

            scores.append(1.0 if (byte_ok and wrap_ok) else 0.0)

        score = sum(scores) / len(scores) if scores else 1.0
        return score, details


# ============================================================================
# AUTO CHAR TABLE SOLVER (TILE -> LETTER)
# ============================================================================

class AutoCharTableSolver:
    """
    Solves tile -> character mapping using beam search.

    1. Seed with high-confidence mappings (SPACE, END, digits)
    2. Iteratively test candidates for unknown tiles
    3. Score by LanguageScore + consistency
    4. Freeze mappings with confidence >= 0.98
    """

    # Common tile patterns
    COMMON_CHARS = list("ETAOINSRHLDC MWFGYPBVKJXQZ0123456789.,!?'-\"")

    def __init__(self):
        self.hypothesis = CharTableHypothesis()
        self.tile_occurrences: Dict[int, int] = Counter()
        self.tile_contexts: Dict[int, List[Tuple[int, int]]] = defaultdict(list)  # tile -> [(prev, next)]

    def seed(self, units: List[TranslationUnit]):
        """Seed with high-confidence initial mappings."""
        # Collect all tiles from tokenized units
        for unit in units:
            if not unit.is_tokenized:
                continue

            tiles = re.findall(r"<TILE_([0-9A-Fa-f]{2})>", unit.text_src)
            tile_indices = [int(t, 16) for t in tiles]

            for i, tile in enumerate(tile_indices):
                self.tile_occurrences[tile] += 1

                prev_tile = tile_indices[i - 1] if i > 0 else -1
                next_tile = tile_indices[i + 1] if i < len(tile_indices) - 1 else -1
                self.tile_contexts[tile].append((prev_tile, next_tile))

        if not self.tile_occurrences:
            return

        # Find most common tile (likely SPACE)
        most_common = self.tile_occurrences.most_common(10)

        # Heuristics for SPACE: very frequent, often between other tiles
        for tile, count in most_common:
            contexts = self.tile_contexts[tile]
            # If this tile appears frequently between non-space tiles
            between_count = sum(1 for p, n in contexts if p != tile and n != tile)
            if between_count / max(1, len(contexts)) > 0.7:
                self.hypothesis.mapping[tile] = " "
                self.hypothesis.confidence[tile] = 0.85
                self.hypothesis.frozen_tiles.add(tile)
                break

        # Find potential END tile (often at end, low frequency)
        for tile in self.tile_occurrences:
            contexts = self.tile_contexts[tile]
            end_contexts = sum(1 for p, n in contexts if n == -1)
            if end_contexts / max(1, len(contexts)) > 0.8:
                self.hypothesis.mapping[tile] = "<END>"
                self.hypothesis.confidence[tile] = 0.90
                self.hypothesis.frozen_tiles.add(tile)
                break

        # Mark unknown tiles
        for tile in self.tile_occurrences:
            if tile not in self.hypothesis.mapping:
                self.hypothesis.unknown_tiles.add(tile)

    def refine(
        self,
        units: List[TranslationUnit],
        beam_width: int = 64,
        max_tiles_per_iter: int = 5,
    ) -> CharTableHypothesis:
        """
        Refine character table using beam search.

        Returns updated hypothesis.
        """
        if not self.hypothesis.unknown_tiles:
            return self.hypothesis

        # Get most frequent unknown tiles
        unknown_sorted = sorted(
            self.hypothesis.unknown_tiles,
            key=lambda t: self.tile_occurrences.get(t, 0),
            reverse=True,
        )[:max_tiles_per_iter]

        # Beam search state: (mapping_dict, score)
        beam: List[Tuple[Dict[int, str], float]] = [
            (dict(self.hypothesis.mapping), 0.0)
        ]

        for tile in unknown_sorted:
            new_beam = []

            for mapping, current_score in beam:
                # Try each candidate character
                for char in self.COMMON_CHARS:
                    # Skip if char already assigned
                    if char in mapping.values() and char != " ":
                        continue

                    # Create new mapping
                    new_mapping = dict(mapping)
                    new_mapping[tile] = char

                    # Score this mapping
                    score = self._score_mapping(new_mapping, units)
                    new_beam.append((new_mapping, score))

            # Keep top beam_width
            new_beam.sort(key=lambda x: x[1], reverse=True)
            beam = new_beam[:beam_width]

        # Take best result
        if beam:
            best_mapping, best_score = beam[0]

            # Update hypothesis
            for tile, char in best_mapping.items():
                if tile not in self.hypothesis.frozen_tiles:
                    self.hypothesis.mapping[tile] = char
                    # Confidence based on score
                    self.hypothesis.confidence[tile] = min(0.95, best_score)

            # Update unknown tiles
            self.hypothesis.unknown_tiles = {
                t for t in self.tile_occurrences
                if t not in self.hypothesis.mapping
            }

            # Freeze high-confidence mappings
            for tile, conf in list(self.hypothesis.confidence.items()):
                if conf >= 0.98:
                    self.hypothesis.frozen_tiles.add(tile)

        return self.hypothesis

    def _score_mapping(self, mapping: Dict[int, str], units: List[TranslationUnit]) -> float:
        """Score a mapping by applying it and measuring language quality."""
        scores = []

        for unit in units:
            if not unit.is_tokenized:
                continue

            # Apply mapping
            text = unit.text_src
            for tile, char in mapping.items():
                text = text.replace(f"<TILE_{tile:02X}>", char)

            # Remove remaining tokens
            cleaned = re.sub(r"<[^>]+>", "", text)

            if not cleaned.strip():
                continue

            # Calculate language-like score
            n = len(cleaned)
            alnum = sum(1 for c in cleaned if c.isalnum()) / n
            alpha_count = sum(1 for c in cleaned if c.isalpha())
            vowels = set("aeiouAEIOU")
            vowel_ratio = sum(1 for c in cleaned if c in vowels) / max(1, alpha_count)

            # Simple score
            score = (alnum * 0.5) + (vowel_ratio * 0.3) + (0.2 if " " in cleaned else 0)
            scores.append(score)

        return sum(scores) / len(scores) if scores else 0.0


# ============================================================================
# AUTO DECOMPRESSOR SELECTOR
# ============================================================================

class AutoDecompressorSelector:
    """
    Selects and parameterizes decompression algorithms.
    Tests candidates and scores by output quality.
    """

    def __init__(self):
        self.decompressors: List[Callable[[bytes, Dict], Optional[bytes]]] = [
            self._decompress_rle,
            self._decompress_lzss,
        ]

    def _decompress_rle(self, data: bytes, params: Dict) -> Optional[bytes]:
        """Simple RLE decompression."""
        sentinel = params.get("sentinel", 0xFF)

        result = bytearray()
        i = 0

        while i < len(data):
            b = data[i]

            if b == sentinel and i + 2 < len(data):
                count = data[i + 1]
                value = data[i + 2]
                result.extend([value] * count)
                i += 3
            else:
                result.append(b)
                i += 1

        return bytes(result) if result else None

    def _decompress_lzss(self, data: bytes, params: Dict) -> Optional[bytes]:
        """Simple LZSS decompression."""
        window_size = params.get("window_size", 0x1000)

        result = bytearray()
        i = 0

        while i < len(data):
            flag_byte = data[i]
            i += 1

            for bit in range(8):
                if i >= len(data):
                    break

                if (flag_byte >> bit) & 1:
                    # Literal byte
                    result.append(data[i])
                    i += 1
                else:
                    # Back reference
                    if i + 1 >= len(data):
                        break

                    b1 = data[i]
                    b2 = data[i + 1]
                    i += 2

                    offset = ((b2 & 0xF0) << 4) | b1
                    length = (b2 & 0x0F) + 3

                    if offset == 0:
                        offset = 1

                    for _ in range(length):
                        if len(result) >= offset:
                            result.append(result[-offset])
                        else:
                            result.append(0)

        return bytes(result) if result else None

    def refine(
        self,
        rom_data: bytes,
        hypotheses: List[DecompressHypothesis],
        sample_offsets: Optional[List[int]] = None,
    ) -> List[DecompressHypothesis]:
        """
        Refine decompression hypotheses by testing variations.
        """
        if not sample_offsets:
            return hypotheses

        results = list(hypotheses)

        # Test RLE with different sentinels
        for sentinel in [0xFF, 0x00, 0x80]:
            params = {"sentinel": sentinel}
            success_count = 0

            for offset in sample_offsets[:10]:
                if offset + 256 > len(rom_data):
                    continue

                chunk = rom_data[offset:offset + 256]
                result = self._decompress_rle(chunk, params)

                if result and len(result) > len(chunk):
                    # Check if result looks like text
                    ascii_ratio = sum(1 for b in result if 0x20 <= b <= 0x7E) / len(result)
                    if ascii_ratio > 0.5:
                        success_count += 1

            if success_count > 0:
                results.append(DecompressHypothesis(
                    algorithm="RLE",
                    params=params,
                    success_rate=success_count / min(10, len(sample_offsets)),
                    sample_offsets=sample_offsets[:10],
                ))

        # Test LZSS with different window sizes
        for window_size in [0x400, 0x800, 0x1000, 0x2000]:
            params = {"window_size": window_size}
            success_count = 0

            for offset in sample_offsets[:10]:
                if offset + 256 > len(rom_data):
                    continue

                chunk = rom_data[offset:offset + 256]
                try:
                    result = self._decompress_lzss(chunk, params)

                    if result and len(result) > len(chunk) * 0.5:
                        ascii_ratio = sum(1 for b in result if 0x20 <= b <= 0x7E) / len(result)
                        if ascii_ratio > 0.4:
                            success_count += 1
                except Exception:
                    pass

            if success_count > 0:
                results.append(DecompressHypothesis(
                    algorithm="LZSS",
                    params=params,
                    success_rate=success_count / min(10, len(sample_offsets)),
                    sample_offsets=sample_offsets[:10],
                ))

        # Sort by success rate
        results.sort(key=lambda h: h.success_rate, reverse=True)

        return results[:5]  # Keep top 5


# ============================================================================
# OPCODE MINER REFINER
# ============================================================================

class OpcodeMinerRefiner:
    """
    Discovers script opcodes that reference text.
    Looks for patterns like: op, u16_pointer
    """

    def __init__(self):
        self.candidates: Dict[int, List[int]] = defaultdict(list)  # opcode -> [text_offsets]

    def refine(
        self,
        rom_data: bytes,
        hypotheses: List[OpcodeHypothesis],
        bank_size: int = 0x4000,
    ) -> List[OpcodeHypothesis]:
        """
        Refine opcode hypotheses by scanning for patterns.
        """
        results = list(hypotheses)
        rom_size = len(rom_data)
        num_banks = max(1, (rom_size + bank_size - 1) // bank_size)

        # Scan for op, u16 patterns
        opcode_pointers: Dict[int, List[int]] = defaultdict(list)

        for i in range(rom_size - 3):
            op = rom_data[i]

            # Skip common non-opcode values
            if op in (0x00, 0xFF, 0x20):
                continue

            # Read potential pointer
            ptr = u16le(rom_data, i + 1)
            if ptr is None:
                continue

            # Try to resolve pointer
            resolved = None

            # Direct address
            if ptr < rom_size:
                resolved = ptr
            # Banked address (slot 1: 0x4000-0x7FFF)
            elif 0x4000 <= ptr < 0x8000:
                local = ptr - 0x4000
                current_bank = i // bank_size
                resolved = current_bank * bank_size + local
            # Banked address (slot 2: 0x8000-0xBFFF)
            elif 0x8000 <= ptr < 0xC000:
                local = ptr - 0x8000
                current_bank = i // bank_size
                resolved = current_bank * bank_size + local

            if resolved is not None and 0 <= resolved < rom_size - 4:
                # Check if target looks like text
                target_data = rom_data[resolved:resolved + 32]
                ascii_count = sum(1 for b in target_data if 0x20 <= b <= 0x7E)

                if ascii_count >= 8:
                    opcode_pointers[op].append(resolved)

        # Analyze candidates
        for op, offsets in opcode_pointers.items():
            if len(offsets) < 16:
                continue

            # Calculate success rate (unique offsets pointing to text)
            unique_offsets = set(offsets)

            # Verify text at each offset
            text_count = 0
            for offset in list(unique_offsets)[:50]:
                data = rom_data[offset:offset + 64]
                ascii_count = sum(1 for b in data if 0x20 <= b <= 0x7E)
                if ascii_count / len(data) > 0.6:
                    text_count += 1

            success_rate = text_count / min(50, len(unique_offsets))

            if success_rate >= 0.6:
                results.append(OpcodeHypothesis(
                    opcode=op,
                    pattern="OP_U16_TEXT",
                    success_rate=success_rate,
                    occurrences=len(offsets),
                    text_offsets=list(unique_offsets)[:100],
                ))

        # Sort by success rate
        results.sort(key=lambda h: h.success_rate, reverse=True)

        return results[:10]  # Keep top 10


# ============================================================================
# TRANSLATION UNIT BUILDER
# ============================================================================

class TranslationUnitBuilder:
    """Converts TextItems to TranslationUnits with clustering and context."""

    def __init__(self, crc32_full: str):
        self.crc32_full = crc32_full
        self.normalizer = TextNormalizer()
        self.protector = TokenProtector()
        self.encoding_guesser = EncodingGuesser()

    def build(
        self,
        items: List[TextItem],
        max_gap: int = 0x1000,
    ) -> List[TranslationUnit]:
        """
        Build TranslationUnits from TextItems.

        1. Sort by offset
        2. Cluster by proximity (max_gap)
        3. Build context prev/next
        4. Assign stable IDs
        """
        if not items:
            return []

        # Sort by offset
        sorted_items = sorted(items, key=lambda x: x.offset or 0)

        # Cluster by offset proximity
        clusters: List[List[TextItem]] = []
        current_cluster: List[TextItem] = []

        for item in sorted_items:
            if not current_cluster:
                current_cluster.append(item)
            else:
                last_offset = current_cluster[-1].offset or 0
                curr_offset = item.offset or 0

                if curr_offset - last_offset <= max_gap:
                    current_cluster.append(item)
                else:
                    clusters.append(current_cluster)
                    current_cluster = [item]

        if current_cluster:
            clusters.append(current_cluster)

        # Build TranslationUnits
        units: List[TranslationUnit] = []

        for cluster_idx, cluster in enumerate(clusters):
            cluster_id = f"cluster_{cluster_idx:04d}"

            for item_idx, item in enumerate(cluster):
                # Generate stable ID
                offset_str = f"{item.offset:06X}" if item.offset is not None else "NOOFF"
                unit_id = f"{self.crc32_full}:{offset_str}:{item.method}:{item_idx:04d}"

                # Get context
                context_prev = ""
                context_next = ""

                if item_idx > 0:
                    context_prev = cluster[item_idx - 1].decoded[:50]
                if item_idx < len(cluster) - 1:
                    context_next = cluster[item_idx + 1].decoded[:50]

                # Protect tokens
                protected_text, token_info = self.protector.protect(item.decoded)

                # Guess encoding
                raw_bytes = bytes.fromhex(item.raw_bytes_hex) if item.raw_bytes_hex else b""
                encoding_guess = self.encoding_guesser.guess_bytes(raw_bytes)

                # Build unit
                unit = TranslationUnit(
                    id=unit_id,
                    offset=item.offset,
                    source_ref=item.source_ref,
                    method=item.method,
                    confidence=item.confidence,
                    raw_bytes=raw_bytes,
                    text_src=protected_text,
                    context_prev=context_prev,
                    context_next=context_next,
                    cluster_id=cluster_id,
                    token_info=token_info,
                    encoding_detected=encoding_guess.encoding,
                    encoding_confidence=encoding_guess.confidence,
                )

                units.append(unit)

        # Compute dup groups (identical text after normalization)
        text_to_units: Dict[str, List[TranslationUnit]] = defaultdict(list)

        for unit in units:
            normalized = self.normalizer.normalize_for_comparison(unit.text_src)
            text_to_units[normalized].append(unit)

        # Assign dup group IDs
        for group_idx, (text, group_units) in enumerate(text_to_units.items()):
            if len(group_units) > 1:
                dup_group_id = f"dup_{sha1_hex(text)[:12]}"
                for unit in group_units:
                    unit.dup_group_id = dup_group_id

        return units


# ============================================================================
# AUTO LEARNING ENGINE
# ============================================================================

class AutoLearningEngine:
    """
    Main auto-learning engine with hypothesis loop and PerfectScore.

    Loop:
    1. Generate/update hypotheses (compression, tiles, opcodes, banks)
    2. Decode with current hypotheses -> CandidateTextSet
    3. Calculate PerfectScore
    4. If score >= threshold -> ACCEPT and export
    5. Else -> refine hypotheses and repeat

    Stop conditions:
    - PerfectScore >= 0.995 (AUTO_DEEP) or >= 0.975 (AUTO_FAST)
    - Improvement < 0.002 for 2 consecutive iterations
    """

    VERSION = "1.0"

    # Thresholds by mode
    THRESHOLDS = {
        LearningMode.AUTO_DEEP: 0.995,
        LearningMode.AUTO_FAST: 0.975,
    }

    COMPONENT_THRESHOLDS = {
        LearningMode.AUTO_DEEP: {
            "roundtrip": 0.995,
            "language": 0.90,
            "consistency": 0.95,
            "structure": 0.85,
            "constraints": 0.99,
        },
        LearningMode.AUTO_FAST: {
            "roundtrip": 0.98,
            "language": 0.80,
            "consistency": 0.85,
            "structure": 0.75,
            "constraints": 0.95,
        },
    }

    def __init__(
        self,
        rom_data: bytes,
        crc32_full: Optional[str] = None,
        crc32_no512: Optional[str] = None,
    ):
        self.rom_data = rom_data
        # Neutralidade/V1: Scan ASCII sequencial (cego) é proibido por padrão.
        # Só habilite se você fornecer regiões explícitas em `self.ascii_scan_regions`.
        self.allow_ascii_scan = False
        self.ascii_scan_regions = []  # List[Tuple[int,int]]: ranges (start,end) para scan ASCII
        self.rom_size = len(rom_data)

        # Calculate CRCs if not provided
        self.crc32_full = crc32_full or crc32_hex(rom_data)
        self.crc32_no512 = crc32_no512 or crc32_hex(rom_data[512:]) if len(rom_data) > 512 else self.crc32_full

        # Components
        self.encoder = EncoderRegistry()
        self.score_calc = PerfectScoreCalculator(self.encoder)
        self.char_solver = AutoCharTableSolver()
        self.decompress_refiner = AutoDecompressorSelector()
        self.opcode_refiner = OpcodeMinerRefiner()
        self.tokenizer = DeterministicTokenizer()
        self.text_detector = TextLikeDetector()
        self.unit_builder = TranslationUnitBuilder(self.crc32_full)
        self.encoding_guesser = EncodingGuesser()

        # State
        self.best_candidate: Optional[CandidateTextSet] = None
        self.best_score: Optional[PerfectScoreBreakdown] = None
        self.iterations_used: int = 0
        self.perfection_reached: bool = False
        self.stop_reason: str = ""

    def discover_candidates(self) -> List[TextItem]:
        """
        Discover text candidates in ROM using multiple methods.

        Neutralidade V1:
        - ASCII scan sequencial (cego) é PROIBIDO por padrão.
        - Só roda se allow_ascii_scan=True E ascii_scan_regions não vazia.
        """
        items: List[TextItem] = []
        seen_offsets: Set[int] = set()

        # Method 1: ASCII scan (SOMENTE se habilitado E com regiões explícitas)
        if self.allow_ascii_scan and self.ascii_scan_regions:
            items.extend(self._scan_ascii_regions(seen_offsets, regions=self.ascii_scan_regions))

        # Method 2: Pointer table detection
        items.extend(self._find_pointer_tables(seen_offsets))

        # Method 3: Script opcode mining (if we have hypotheses)
        items.extend(self._mine_script_opcodes(seen_offsets))

        return items

    def _scan_ascii_regions(self, seen_offsets: Set[int], regions: Optional[List[Tuple[int, int]]] = None) -> List[TextItem]:
        """
        Scan for ASCII text regions.

        Neutralidade V1:
        - Se regions for None ou vazio: retorna [] (não varre ROM inteira).
        - Se regions existir: varre apenas dentro dos ranges fornecidos.
        """
        items: List[TextItem] = []

        # Neutralidade V1: sem regiões explícitas, não varre nada
        if not regions:
            return items

        for region_start, region_end in regions:
            # Limita aos bounds da ROM
            region_start = max(0, region_start)
            region_end = min(region_end, self.rom_size)

            i = region_start
            while i < region_end:
                # Check for printable ASCII
                if not (0x20 <= self.rom_data[i] <= 0x7E):
                    i += 1
                    continue

                # Find extent of ASCII region
                j = i
                while j < region_end and 0x20 <= self.rom_data[j] <= 0x7E:
                    j += 1

                length = j - i

                if length >= 4 and i not in seen_offsets:
                    raw = self.rom_data[i:j]
                    decoded = raw.decode("ascii", errors="ignore")

                    # Basic text validation
                    alnum_ratio = sum(1 for c in decoded if c.isalnum()) / max(1, len(decoded))

                    if alnum_ratio >= 0.5:
                        seen_offsets.add(i)

                        items.append(TextItem(
                            id=f"{self.crc32_full}:{i:06X}:SCAN",
                            source_ref=f"offset:0x{i:06X}",
                            offset=i,
                            raw_bytes=raw,
                            raw_bytes_hex=raw.hex().upper(),
                            decoded=decoded,
                            encoding="ascii",
                            terminator=self.rom_data[j] if j < self.rom_size else None,
                            method="SEQUENTIAL_SCAN",
                            confidence=0.6 + (alnum_ratio * 0.3),
                        ))

                i = j + 1

        return items

    def _find_pointer_tables(self, seen_offsets: Set[int]) -> List[TextItem]:
        """Find and extract from pointer tables."""
        items: List[TextItem] = []

        # Scan for potential pointer table regions
        bank_size = 0x4000
        num_banks = max(1, (self.rom_size + bank_size - 1) // bank_size)

        i = 0
        while i < self.rom_size - 16:
            # Look for sequence of pointers
            consecutive_valid = 0
            ptrs: List[int] = []

            for j in range(16):
                ptr_off = i + (j * 2)
                if ptr_off + 2 > self.rom_size:
                    break

                ptr = u16le(self.rom_data, ptr_off)
                if ptr is None:
                    break

                # Try to resolve
                resolved = None

                if ptr < self.rom_size:
                    resolved = ptr
                elif 0x4000 <= ptr < 0x8000:
                    local = ptr - 0x4000
                    for bank in range(num_banks):
                        addr = bank * bank_size + local
                        if 0 <= addr < self.rom_size:
                            resolved = addr
                            break

                if resolved is not None and 0 <= resolved < self.rom_size:
                    # Check if target has ASCII
                    target = self.rom_data[resolved:resolved + 8]
                    ascii_count = sum(1 for b in target if 0x20 <= b <= 0x7E)

                    if ascii_count >= 4:
                        consecutive_valid += 1
                        ptrs.append(resolved)
                    else:
                        break
                else:
                    break

            if consecutive_valid >= 8:
                # Valid pointer table found
                for ptr in ptrs:
                    if ptr in seen_offsets:
                        continue

                    # Extract text
                    end = ptr
                    while end < self.rom_size and self.rom_data[end] not in (0x00, 0xFF):
                        end += 1

                    if end > ptr:
                        raw = self.rom_data[ptr:end]
                        decoded = raw.decode("ascii", errors="replace")

                        seen_offsets.add(ptr)

                        items.append(TextItem(
                            id=f"{self.crc32_full}:{ptr:06X}:PTR",
                            source_ref=f"offset:0x{ptr:06X}",
                            offset=ptr,
                            raw_bytes=raw,
                            raw_bytes_hex=raw.hex().upper(),
                            decoded=decoded,
                            encoding="ascii",
                            terminator=self.rom_data[end] if end < self.rom_size else None,
                            method="POINTER_TABLE",
                            confidence=0.85,
                        ))

                i += consecutive_valid * 2
            else:
                i += 2

        return items

    def _mine_script_opcodes(self, seen_offsets: Set[int]) -> List[TextItem]:
        """Mine text from discovered script opcodes."""
        items: List[TextItem] = []

        # Get opcode hypotheses
        hypotheses = self.opcode_refiner.refine(self.rom_data, [])

        for hyp in hypotheses:
            if hyp.success_rate < 0.7:
                continue

            for offset in hyp.text_offsets:
                if offset in seen_offsets:
                    continue

                # Extract text
                end = offset
                while end < self.rom_size and self.rom_data[end] not in (0x00, 0xFF):
                    end += 1

                if end > offset:
                    raw = self.rom_data[offset:end]
                    decoded = raw.decode("ascii", errors="replace")

                    seen_offsets.add(offset)

                    items.append(TextItem(
                        id=f"{self.crc32_full}:{offset:06X}:OPCODE",
                        source_ref=f"offset:0x{offset:06X}",
                        offset=offset,
                        raw_bytes=raw,
                        raw_bytes_hex=raw.hex().upper(),
                        decoded=decoded,
                        encoding="ascii",
                        terminator=self.rom_data[end] if end < self.rom_size else None,
                        method="SCRIPT_OPCODE",
                        confidence=hyp.success_rate,
                    ))

        return items

    def build_candidate_set(self, items: List[TextItem]) -> CandidateTextSet:
        """Build CandidateTextSet from discovered items."""
        units = self.unit_builder.build(items)

        # Apply text-like detection
        for unit in units:
            is_text, conf, reasons = self.text_detector.is_text_like(unit)
            unit.text_like = is_text
            unit.confidence = conf
            unit.reason_codes.extend(reasons)

            # Apply tokenization fallback for non-text
            if not is_text and unit.raw_bytes:
                unit.text_src = self.tokenizer.tokenize_bytes(
                    unit.raw_bytes,
                    self.char_solver.hypothesis if self.char_solver.hypothesis.mapping else None,
                )
                unit.is_tokenized = True

        # Ensure no empty outputs
        for unit in units:
            if not unit.text_src.strip() and unit.raw_bytes:
                unit.text_src = self.tokenizer.tokenize_bytes(unit.raw_bytes)
                unit.is_tokenized = True
                unit.reason_codes.append("NO_EMPTY_OUTPUT")

        return CandidateTextSet(
            crc32_full=self.crc32_full,
            crc32_no512=self.crc32_no512,
            units=units,
            charset_hypothesis=self.char_solver.hypothesis,
            decompress_hypotheses=[],
            opcode_hypotheses=[],
        )

    def refine_hypotheses(self, candidate: CandidateTextSet, iteration: int):
        """Refine all hypotheses based on current results."""
        # Refine character table (for tokenized units)
        tokenized_units = [u for u in candidate.units if u.is_tokenized]
        if tokenized_units:
            self.char_solver.seed(tokenized_units)
            beam_width = 64 if iteration < 3 else 256
            self.char_solver.refine(tokenized_units, beam_width=beam_width)

        # Update candidate with new hypothesis
        candidate.charset_hypothesis = self.char_solver.hypothesis

    def run(
        self,
        max_iters: int = 10,
        mode: str = "AUTO_DEEP",
    ) -> Tuple[CandidateTextSet, PerfectScoreBreakdown]:
        """
        Run the auto-learning loop.

        Returns:
            (best_candidate, best_score)
        """
        learning_mode = LearningMode(mode)
        target = self.THRESHOLDS[learning_mode]

        last_total = 0.0
        stall_count = 0

        for iteration in range(max_iters):
            self.iterations_used = iteration + 1

            # 1. Discover candidates
            items = self.discover_candidates()

            # 2. Build candidate set
            candidate = self.build_candidate_set(items)
            candidate.iteration = iteration

            # 3. Calculate score
            score = self.score_calc.compute(candidate)

            # 4. Track best
            if self.best_score is None or score.total > self.best_score.total:
                self.best_candidate = candidate
                self.best_score = score

            # 5. Check for success
            if score.total >= target:
                self.perfection_reached = True
                self.stop_reason = f"PERFECTION_REACHED: {score.total:.6f} >= {target}"
                return candidate, score

            # 6. Check for stall
            improvement = score.total - last_total
            last_total = score.total

            if improvement < 0.002:
                stall_count += 1
            else:
                stall_count = 0

            if stall_count >= 2:
                self.stop_reason = f"STALLED: improvement < 0.002 for 2 iterations"
                break

            # 7. Refine hypotheses
            self.refine_hypotheses(candidate, iteration)

        # Return best found
        if self.best_candidate is None or self.best_score is None:
            # Shouldn't happen, but create empty result
            empty_candidate = CandidateTextSet(
                crc32_full=self.crc32_full,
                crc32_no512=self.crc32_no512,
                units=[],
            )
            empty_score = PerfectScoreBreakdown(
                roundtrip=0.0,
                language=0.0,
                consistency=0.0,
                structure=0.0,
                constraints=0.0,
                total=0.0,
            )
            return empty_candidate, empty_score

        if not self.stop_reason:
            self.stop_reason = f"MAX_ITERATIONS_REACHED: {max_iters}"

        return self.best_candidate, self.best_score


# ============================================================================
# EXPORTER
# ============================================================================

class AutoLearningExporter:
    """Exports results from AutoLearningEngine."""

    def __init__(self, engine: AutoLearningEngine):
        self.engine = engine
        self.output_files: Dict[str, str] = {}  # path -> sha256

    def export_all(
        self,
        output_dir: str | Path,
        candidate: CandidateTextSet,
        score: PerfectScoreBreakdown,
    ) -> Dict[str, str]:
        """Export all outputs."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        crc = self.engine.crc32_full

        # 1. Pure text JSONL
        jsonl_path = out_dir / f"{crc}_pure_text.jsonl"
        self._export_jsonl(jsonl_path, candidate)

        # 2. Clean TXT
        txt_path = out_dir / f"{crc}_clean.txt"
        self._export_txt(txt_path, candidate)

        # 3. Report
        report_path = out_dir / f"{crc}_report.json"
        self._export_report(report_path, candidate, score)

        # 4. Proof JSON
        proof_path = out_dir / f"{crc}_proof.json"
        self._export_proof(proof_path)

        return self.output_files

    def _register_output(self, path: Path):
        """Register output file with SHA256."""
        with open(path, "rb") as f:
            sha256 = hashlib.sha256(f.read()).hexdigest()
        self.output_files[str(path)] = sha256

    def _export_jsonl(self, path: Path, candidate: CandidateTextSet):
        """Export pure text JSONL."""
        with open(path, "w", encoding="utf-8") as f:
            for unit in candidate.units:
                entry = {
                    "id": unit.id,
                    "offset": f"0x{unit.offset:06X}" if unit.offset else None,
                    "text_src": unit.text_src,
                    "encoding": unit.encoding_detected,
                    "method": unit.method,
                    "confidence": round(unit.confidence, 4),
                    "is_tokenized": unit.is_tokenized,
                    "text_like": unit.text_like,
                    "cluster_id": unit.cluster_id,
                    "dup_group_id": unit.dup_group_id or None,
                    "reason_codes": unit.reason_codes,
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self._register_output(path)

    def _export_txt(self, path: Path, candidate: CandidateTextSet):
        """Export clean text TXT."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# AUTO_LEARNING_ENGINE v{AutoLearningEngine.VERSION}\n")
            f.write(f"# CRC32: {candidate.crc32_full}\n")
            f.write(f"# Units: {len(candidate.units)}\n")
            f.write(f"# Iteration: {candidate.iteration}\n")
            f.write("# " + "=" * 56 + "\n\n")

            current_cluster = None
            for unit in candidate.units:
                if unit.cluster_id != current_cluster:
                    current_cluster = unit.cluster_id
                    f.write(f"\n# ---- {current_cluster} ----\n\n")

                offset_str = f"0x{unit.offset:06X}" if unit.offset else "NO_OFFSET"
                f.write(f"[{offset_str}] {unit.method} conf={unit.confidence:.2f}")
                if unit.is_tokenized:
                    f.write(" [TOKENIZED]")
                f.write("\n")
                f.write(f"{unit.text_src}\n")
                f.write("-" * 40 + "\n")

        self._register_output(path)

    def _export_report(self, path: Path, candidate: CandidateTextSet, score: PerfectScoreBreakdown):
        """Export detailed report JSON."""
        # Calculate unknown tile ratio
        unknown_ratio = 0.0
        if candidate.charset_hypothesis:
            total_tiles = len(candidate.charset_hypothesis.mapping) + len(candidate.charset_hypothesis.unknown_tiles)
            if total_tiles > 0:
                unknown_ratio = len(candidate.charset_hypothesis.unknown_tiles) / total_tiles

        report = {
            "schema": "auto_learning_engine.report.v1",
            "version": AutoLearningEngine.VERSION,
            "crc32_full": candidate.crc32_full,
            "crc32_no512": candidate.crc32_no512,
            "timestamp": datetime.now(timezone.utc).isoformat(),

            "perfect_score": score.to_dict(),

            "perfection_reached": self.engine.perfection_reached,
            "stop_reason": self.engine.stop_reason,
            "iterations_used": self.engine.iterations_used,

            "unknown_tile_ratio": round(unknown_ratio, 4),

            "statistics": {
                "total_units": len(candidate.units),
                "text_like_units": sum(1 for u in candidate.units if u.text_like),
                "tokenized_units": sum(1 for u in candidate.units if u.is_tokenized),
                "units_by_method": dict(Counter(u.method for u in candidate.units)),
            },

            "charset_hypothesis": {
                "known_tiles": len(candidate.charset_hypothesis.mapping) if candidate.charset_hypothesis else 0,
                "unknown_tiles": len(candidate.charset_hypothesis.unknown_tiles) if candidate.charset_hypothesis else 0,
                "frozen_tiles": len(candidate.charset_hypothesis.frozen_tiles) if candidate.charset_hypothesis else 0,
            },
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        self._register_output(path)

    def _export_proof(self, path: Path):
        """Export proof JSON with SHA256 hashes."""
        proof = {
            "schema": "auto_learning_engine.proof.v1",
            "crc32": self.engine.crc32_full,
            "version": AutoLearningEngine.VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rom_sha256": sha256_hex(self.engine.rom_data),
            "outputs": dict(self.output_files),
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(proof, f, indent=2, ensure_ascii=False)

        # Add self-reference
        self._register_output(path)
        proof["outputs"][str(path)] = self.output_files[str(path)]

        with open(path, "w", encoding="utf-8") as f:
            json.dump(proof, f, indent=2, ensure_ascii=False)


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def run_auto_learning(
    rom_path: str | Path,
    output_dir: Optional[str | Path] = None,
    mode: str = "AUTO_DEEP",
    max_iters: int = 10,
) -> Tuple[CandidateTextSet, PerfectScoreBreakdown, Dict[str, str]]:
    """
    Convenience function to run auto-learning on a ROM.

    Args:
        rom_path: Path to ROM file
        output_dir: Output directory (default: same as ROM)
        mode: "AUTO_DEEP" or "AUTO_FAST"
        max_iters: Maximum iterations

    Returns:
        (candidate, score, output_files)
    """
    rom_path = Path(rom_path)

    if not rom_path.exists():
        raise FileNotFoundError(f"ROM not found: {rom_path}")

    rom_data = rom_path.read_bytes()

    if output_dir is None:
        output_dir = rom_path.parent

    # Create engine
    engine = AutoLearningEngine(rom_data)

    # Run
    candidate, score = engine.run(max_iters=max_iters, mode=mode)

    # Export
    exporter = AutoLearningExporter(engine)
    output_files = exporter.export_all(output_dir, candidate, score)

    return candidate, score, output_files
