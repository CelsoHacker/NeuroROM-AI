# -*- coding: utf-8 -*-
"""
================================================================================
REINSERTION VALIDATOR - Validates Safe Text Reinsertion
================================================================================
REINSERTION_SAFE=true only when:
1. Validator strict passes
2. Round-trip encoding works
3. Constraints are respected
================================================================================
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .text_unifier import UnifiedTextItem


@dataclass
class ValidationResult:
    """Result of reinsertion validation."""
    is_safe: bool
    reasons: List[str]
    constraints_ok: bool = True
    roundtrip_ok: bool = True
    validator_ok: bool = True


class ReinsertionValidator:
    """
    Validates reinsertion safety for unified text items.

    Strict validation criteria:
    1. Text must pass quality validator
    2. Encoding round-trip must succeed
    3. Size constraints must be respected
    """

    # Characters that indicate garbage/binary
    FORBIDDEN_SHORT = set('~#|^_')

    # Minimum length for validation
    MIN_LENGTH = 3

    def __init__(self, rom_data: bytes, char_table: Optional[Dict[int, str]] = None):
        """
        Initialize validator.

        Args:
            rom_data: ROM data for constraint checking
            char_table: Character table for encoding
        """
        self.rom_data = rom_data
        self.char_table = char_table or {}
        self._reverse_table = {v: k for k, v in self.char_table.items()}

    def validate(self, item: UnifiedTextItem) -> ValidationResult:
        """
        Validate reinsertion safety for an item.

        Args:
            item: Unified text item to validate

        Returns:
            ValidationResult with detailed reasons
        """
        reasons = []
        validator_ok = True
        roundtrip_ok = True
        constraints_ok = True

        text = item.text_src

        # Check 1: Basic validation
        valid, reason = self._validate_text(text)
        if not valid:
            reasons.append(f"VALIDATOR: {reason}")
            validator_ok = False

        # Check 2: Must have static origin for safe reinsertion
        if item.source == "runtime" and item.origin_offset is None:
            reasons.append("NO_STATIC_ORIGIN")
            validator_ok = False

        # Check 3: Round-trip encoding
        if item.static_item and item.static_item.raw_bytes:
            rt_ok, rt_reason = self._check_roundtrip(
                text,
                item.static_item.raw_bytes,
                item.static_item.encoding
            )
            if not rt_ok:
                reasons.append(f"ROUNDTRIP: {rt_reason}")
                roundtrip_ok = False

        # Check 4: Size constraints
        if item.static_offset is not None:
            const_ok, const_reason = self._check_constraints(
                text,
                item.static_offset
            )
            if not const_ok:
                reasons.append(f"CONSTRAINT: {const_reason}")
                constraints_ok = False

        # Check 5: Tilemap-specific constraints
        if hasattr(item, 'kind') and item.kind == "UI_TILEMAP_LABEL":
            tm_ok, tm_reason = self._check_tilemap_constraints(item, text)
            if not tm_ok:
                reasons.append(f"TILEMAP: {tm_reason}")
                constraints_ok = False

        # Overall safety
        is_safe = validator_ok and roundtrip_ok and constraints_ok

        return ValidationResult(
            is_safe=is_safe,
            reasons=reasons,
            constraints_ok=constraints_ok,
            roundtrip_ok=roundtrip_ok,
            validator_ok=validator_ok,
        )

    def _validate_text(self, text: str) -> Tuple[bool, str]:
        """Basic text quality validation."""
        # Empty check
        if not text or not text.strip():
            return False, "EMPTY"

        # Too short with forbidden symbols
        if len(text) < self.MIN_LENGTH:
            if any(c in self.FORBIDDEN_SHORT for c in text):
                return False, "SHORT_WITH_FORBIDDEN_SYMBOLS"

        # Printable check
        printable = sum(1 for c in text if c.isprintable() or c in '\n\r\t')
        if printable / len(text) < 0.8:
            return False, "LOW_PRINTABLE_RATIO"

        # Letter check (for non-tokenized)
        if '<' not in text:
            letters = sum(1 for c in text if c.isalpha())
            if len(text) >= 5 and letters / len(text) < 0.3:
                return False, "LOW_LETTER_RATIO"

        return True, "OK"

    def _check_roundtrip(self, text: str, original_bytes: bytes,
                         encoding: str) -> Tuple[bool, str]:
        """Check if text survives encoding round-trip."""
        try:
            # Try to encode back
            if encoding.lower() in ('ascii', 'utf-8', 'shift_jis'):
                encoded = text.encode(encoding, errors='strict')
                decoded = encoded.decode(encoding)

                if decoded != text:
                    return False, "DECODE_MISMATCH"

            elif self._reverse_table:
                # Use custom char table
                encoded = bytearray()
                for char in text:
                    if char in self._reverse_table:
                        encoded.append(self._reverse_table[char])
                    elif char.startswith('<') and char.endswith('>'):
                        continue  # Skip tokens
                    else:
                        return False, f"UNKNOWN_CHAR:{ord(char)}"

            return True, "OK"

        except Exception as e:
            return False, f"ENCODE_ERROR:{str(e)}"

    def _check_constraints(self, text: str, offset: int) -> Tuple[bool, str]:
        """Check size constraints at offset."""
        if offset >= len(self.rom_data):
            return False, "INVALID_OFFSET"

        # Find original string length at offset
        original_len = 0
        pos = offset
        while pos < len(self.rom_data) and self.rom_data[pos] != 0:
            original_len += 1
            pos += 1

        # Estimate new length
        if self._reverse_table:
            new_len = sum(1 for c in text if c in self._reverse_table)
        else:
            new_len = len(text.encode('utf-8', errors='ignore'))

        # Check if new text fits
        if new_len > original_len:
            return False, f"TOO_LONG:{new_len}>{original_len}"

        return True, "OK"

    def _check_tilemap_constraints(self, item: 'UnifiedTextItem',
                                    translated_text: str) -> Tuple[bool, str]:
        """
        Check tilemap-specific constraints.

        Args:
            item: UnifiedTextItem with kind="UI_TILEMAP_LABEL"
            translated_text: The translated text to validate

        Returns:
            (is_valid, reason_string)
        """
        import re

        constraints = getattr(item, 'constraints', None) or {}
        max_bytes = constraints.get('max_bytes', 0)

        if not max_bytes:
            return True, "OK"  # No constraint defined

        # Count encoded length:
        # - <TILE:XX> tokens = 1 byte each
        # - Plain characters = 1 byte each
        token_pattern = r'<TILE:[0-9A-Fa-f]{2}>'
        token_count = len(re.findall(token_pattern, translated_text))
        text_without_tokens = re.sub(token_pattern, '', translated_text)
        char_count = len(text_without_tokens)

        total = token_count + char_count

        if total > max_bytes:
            return False, f"OVERFLOW:{total}>{max_bytes}"

        return True, "OK"

    def validate_all(self, items: List[UnifiedTextItem]) -> List[Tuple[UnifiedTextItem, ValidationResult]]:
        """Validate all items and return results."""
        results = []
        for item in items:
            result = self.validate(item)
            item.reinsertion_safe = result.is_safe
            item.reason_codes.extend(result.reasons)
            results.append((item, result))
        return results

    def get_safe_items(self, items: List[UnifiedTextItem]) -> List[UnifiedTextItem]:
        """Get only items that are safe for reinsertion."""
        self.validate_all(items)
        return [item for item in items if item.reinsertion_safe]

    def get_validation_stats(self, items: List[UnifiedTextItem]) -> Dict[str, Any]:
        """Get validation statistics."""
        results = self.validate_all(items)

        total = len(results)
        safe = sum(1 for _, r in results if r.is_safe)
        validator_fail = sum(1 for _, r in results if not r.validator_ok)
        roundtrip_fail = sum(1 for _, r in results if not r.roundtrip_ok)
        constraint_fail = sum(1 for _, r in results if not r.constraints_ok)

        return {
            "total": total,
            "safe": safe,
            "safe_ratio": safe / total if total > 0 else 0,
            "validator_failures": validator_fail,
            "roundtrip_failures": roundtrip_fail,
            "constraint_failures": constraint_fail,
        }
