# -*- coding: utf-8 -*-
"""
================================================================================
POLICY ENFORCER - Extraction Quality Policies
================================================================================
Enforces mandatory extraction quality policies:

1. NoEmptyOutputPolicy: text_like=True → text_src not empty
2. No blind ASCII scan as primary method
3. No strings <3 chars with ~ # | ^ _
4. No game names/marketing text
5. Deterministic output (seed = CRC32)

All policies are MANDATORY and violations are rejected.
================================================================================
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from ..unification.text_unifier import UnifiedTextItem


@dataclass
class PolicyViolation:
    """A policy violation record."""
    policy_name: str
    item_uid: str
    reason: str
    severity: str = "error"  # error, warning
    auto_fixed: bool = False


@dataclass
class PolicyResult:
    """Result of policy enforcement."""
    passed: bool
    violations: List[PolicyViolation]
    items_removed: int
    items_modified: int


class BasePolicy(ABC):
    """Abstract base class for policies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Policy name."""
        pass

    @abstractmethod
    def check(self, item: UnifiedTextItem) -> Optional[PolicyViolation]:
        """
        Check if item violates this policy.

        Returns:
            PolicyViolation if violated, None if passed
        """
        pass

    def can_fix(self, item: UnifiedTextItem) -> bool:
        """Check if violation can be auto-fixed."""
        return False

    def fix(self, item: UnifiedTextItem) -> UnifiedTextItem:
        """Attempt to fix violation. Override in subclass."""
        return item


class NoEmptyOutputPolicy(BasePolicy):
    """
    MANDATORY: Items marked as text_like must have non-empty text_src.

    This is the core policy ensuring COVERAGE=1.0.
    If text_like_score > 0, text_src MUST contain actual text or tokens.
    """

    @property
    def name(self) -> str:
        return "NoEmptyOutputPolicy"

    def check(self, item: UnifiedTextItem) -> Optional[PolicyViolation]:
        # If marked as text-like, must have content
        if item.text_like_score > 0:
            if not item.text_src or not item.text_src.strip():
                return PolicyViolation(
                    policy_name=self.name,
                    item_uid=item.uid,
                    reason="text_like=True but text_src is empty",
                    severity="error",
                )

        return None


class NoShortGarbagePolicy(BasePolicy):
    """
    MANDATORY: No strings <3 chars containing garbage symbols.

    Forbidden in short strings: ~ # | ^ _
    These often indicate binary data misinterpreted as text.
    """

    FORBIDDEN_SYMBOLS = set('~#|^_')
    MIN_LENGTH = 3

    @property
    def name(self) -> str:
        return "NoShortGarbagePolicy"

    def check(self, item: UnifiedTextItem) -> Optional[PolicyViolation]:
        text = item.text_src

        if len(text) < self.MIN_LENGTH:
            if any(c in self.FORBIDDEN_SYMBOLS for c in text):
                return PolicyViolation(
                    policy_name=self.name,
                    item_uid=item.uid,
                    reason=f"Short string with forbidden symbols: {text!r}",
                    severity="error",
                )

        return None


class NoBlindAsciiScanPolicy(BasePolicy):
    """
    MANDATORY: Blind ASCII scan cannot be the primary extraction method.

    Items extracted via blind_ascii must have supporting evidence:
    - Pointer reference
    - Compression origin
    - Runtime confirmation
    - High text score (>0.8)
    """

    ALLOWED_METHODS = {
        'pointer_table', 'compressed_', 'tile_text', 'runtime',
        'container_', 'script_opcode', 'region_scan'
    }

    @property
    def name(self) -> str:
        return "NoBlindAsciiScanPolicy"

    def check(self, item: UnifiedTextItem) -> Optional[PolicyViolation]:
        # Check source method
        method = ""
        if item.static_item:
            method = getattr(item.static_item, 'source_method', '') or ''

        # Blind ASCII is suspicious without other evidence
        if 'blind_ascii' in method.lower() or method == 'ascii_scan':
            # Must have high score or other confirmation
            if item.text_like_score < 0.8:
                if item.source != 'hybrid':  # Not runtime-confirmed
                    return PolicyViolation(
                        policy_name=self.name,
                        item_uid=item.uid,
                        reason=f"Blind ASCII scan without supporting evidence: {method}",
                        severity="error",
                    )

        return None


class NoGameNamesPolicy(BasePolicy):
    """
    MANDATORY: No game names or marketing text in output.

    File naming uses CRC32 only. Text content should not include:
    - Copyright notices (can be included but not required)
    - Marketing slogans
    - Version strings in isolation
    """

    # Patterns that suggest marketing/meta content
    MARKETING_PATTERNS = [
        r'^©\s*\d{4}\s+[A-Z]',  # Copyright lines
        r'^ALL RIGHTS RESERVED',
        r'^LICENSED BY',
        r'^PRESENTED BY',
        r'^PRODUCED BY',
        r'^TM\s*$',
        r'^®\s*$',
    ]

    @property
    def name(self) -> str:
        return "NoGameNamesPolicy"

    def check(self, item: UnifiedTextItem) -> Optional[PolicyViolation]:
        text = item.text_src.strip().upper()

        # Very short copyright/trademark only strings
        if len(text) <= 5:
            if text in ('TM', '®', '©', 'C', 'R'):
                return PolicyViolation(
                    policy_name=self.name,
                    item_uid=item.uid,
                    reason=f"Isolated trademark/copyright symbol: {item.text_src!r}",
                    severity="warning",
                )

        # Check patterns
        for pattern in self.MARKETING_PATTERNS:
            if re.match(pattern, text):
                # This is a warning, not an error - copyright notices are valid text
                return PolicyViolation(
                    policy_name=self.name,
                    item_uid=item.uid,
                    reason=f"Marketing/meta text detected: {item.text_src[:50]}",
                    severity="warning",
                )

        return None


class NoDuplicateOutputPolicy(BasePolicy):
    """
    MANDATORY: No exact duplicate text items in output.

    Duplicates by (text_src, offset) are rejected.
    Same text at different offsets is allowed (repeated dialogue).
    """

    def __init__(self):
        self._seen: Set[Tuple[str, Optional[int]]] = set()

    @property
    def name(self) -> str:
        return "NoDuplicateOutputPolicy"

    def check(self, item: UnifiedTextItem) -> Optional[PolicyViolation]:
        key = (item.text_src, item.static_offset)

        if key in self._seen:
            return PolicyViolation(
                policy_name=self.name,
                item_uid=item.uid,
                reason=f"Duplicate text at same offset",
                severity="error",
            )

        self._seen.add(key)
        return None

    def reset(self) -> None:
        """Reset seen items for new extraction."""
        self._seen.clear()


class MinimumQualityPolicy(BasePolicy):
    """
    MANDATORY: Minimum quality threshold for text items.

    Items must meet basic quality criteria:
    - Printable ratio > 0.7
    - At least one letter if length >= 3
    """

    MIN_PRINTABLE_RATIO = 0.7

    @property
    def name(self) -> str:
        return "MinimumQualityPolicy"

    def check(self, item: UnifiedTextItem) -> Optional[PolicyViolation]:
        text = item.text_src

        if not text:
            return None  # Empty handled by NoEmptyOutputPolicy

        # Check printable ratio
        printable = sum(1 for c in text if c.isprintable() or c in '\n\r\t')
        ratio = printable / len(text)

        if ratio < self.MIN_PRINTABLE_RATIO:
            return PolicyViolation(
                policy_name=self.name,
                item_uid=item.uid,
                reason=f"Low printable ratio: {ratio:.2f}",
                severity="error",
            )

        # Check for at least one letter in longer strings
        if len(text) >= 3:
            # Skip if tokenized (contains <TILE_XX> etc)
            if '<TILE_' not in text and '<UNK_' not in text and '<BYTE_' not in text:
                if not any(c.isalpha() for c in text):
                    # Numbers-only strings might be valid (scores, etc)
                    if not text.replace(' ', '').replace('\n', '').isdigit():
                        return PolicyViolation(
                            policy_name=self.name,
                            item_uid=item.uid,
                            reason=f"No letters in text: {text!r}",
                            severity="warning",
                        )

        return None


class PolicyEnforcer:
    """
    Enforces all extraction policies.

    Policies are applied in order:
    1. NoEmptyOutputPolicy (most critical)
    2. NoShortGarbagePolicy
    3. NoBlindAsciiScanPolicy
    4. NoGameNamesPolicy
    5. NoDuplicateOutputPolicy
    6. MinimumQualityPolicy
    """

    def __init__(self, strict: bool = True):
        """
        Initialize policy enforcer.

        Args:
            strict: If True, errors cause item removal. If False, only log.
        """
        self.strict = strict
        self.policies: List[BasePolicy] = [
            NoEmptyOutputPolicy(),
            NoShortGarbagePolicy(),
            NoBlindAsciiScanPolicy(),
            NoGameNamesPolicy(),
            NoDuplicateOutputPolicy(),
            MinimumQualityPolicy(),
        ]
        self.violations: List[PolicyViolation] = []

    def enforce_all(self, items: List[UnifiedTextItem]) -> List[UnifiedTextItem]:
        """
        Enforce all policies on items.

        Args:
            items: List of unified text items

        Returns:
            Filtered list with violating items removed (if strict)
        """
        self.violations = []
        valid_items = []
        removed = 0
        modified = 0

        # Reset stateful policies
        for policy in self.policies:
            if hasattr(policy, 'reset'):
                policy.reset()

        for item in items:
            item_valid = True
            item_violations = []

            for policy in self.policies:
                violation = policy.check(item)

                if violation:
                    item_violations.append(violation)
                    self.violations.append(violation)

                    if violation.severity == "error":
                        # Try to fix
                        if policy.can_fix(item):
                            item = policy.fix(item)
                            violation.auto_fixed = True
                            modified += 1
                        elif self.strict:
                            item_valid = False

            # Add reason codes to item
            for v in item_violations:
                if v.severity == "error" and not v.auto_fixed:
                    item.reason_codes.append(f"POLICY:{v.policy_name}")

            if item_valid:
                valid_items.append(item)
            else:
                removed += 1

        return valid_items

    def get_result(self) -> PolicyResult:
        """Get enforcement result."""
        errors = [v for v in self.violations if v.severity == "error"]
        return PolicyResult(
            passed=len(errors) == 0,
            violations=self.violations,
            items_removed=sum(1 for v in errors if not v.auto_fixed),
            items_modified=sum(1 for v in self.violations if v.auto_fixed),
        )

    def get_violation_summary(self) -> Dict[str, int]:
        """Get summary of violations by policy."""
        summary: Dict[str, int] = {}
        for v in self.violations:
            summary[v.policy_name] = summary.get(v.policy_name, 0) + 1
        return summary

    def add_policy(self, policy: BasePolicy) -> None:
        """Add a custom policy."""
        self.policies.append(policy)

    def remove_policy(self, policy_name: str) -> bool:
        """Remove a policy by name."""
        for i, policy in enumerate(self.policies):
            if policy.name == policy_name:
                self.policies.pop(i)
                return True
        return False


def enforce_policies(items: List[UnifiedTextItem],
                     strict: bool = True) -> Tuple[List[UnifiedTextItem], PolicyResult]:
    """
    Convenience function to enforce all policies.

    Args:
        items: List of unified text items
        strict: Remove violating items if True

    Returns:
        Tuple of (filtered_items, policy_result)
    """
    enforcer = PolicyEnforcer(strict=strict)
    filtered = enforcer.enforce_all(items)
    result = enforcer.get_result()
    return filtered, result
