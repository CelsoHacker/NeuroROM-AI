# -*- coding: utf-8 -*-
"""
================================================================================
TEXT UNIFIER - Merges Static and Runtime Text Items
================================================================================
Unifies text from different sources by similarity and context.
Produces a single consolidated output with origin tracking.
================================================================================
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
import hashlib

from .similarity_matcher import SimilarityMatcher


@dataclass
class StaticTextItem:
    """Static text item from ROM analysis."""
    id: str
    offset: int
    text: str
    raw_bytes: bytes = field(default_factory=bytes)
    method: str = ""
    confidence: float = 0.0
    encoding: str = "ascii"


@dataclass
class RuntimeTextItem:
    """Runtime text item from emulator capture."""
    id: str
    screen_id: str
    text: str
    tile_indices: List[int] = field(default_factory=list)
    frame_captured: int = 0
    confidence: float = 0.0


@dataclass
class UnifiedTextItem:
    """Unified text item combining static and runtime."""
    id: str
    text_src: str                    # Source text for translation
    source: str                       # "static", "runtime", "merged"

    # Static info
    static_offset: Optional[int] = None
    static_item: Optional[StaticTextItem] = None

    # Runtime info
    runtime_items: List[RuntimeTextItem] = field(default_factory=list)
    screen_ids: List[str] = field(default_factory=list)

    # Origin tracking
    origin_offset: Optional[int] = None
    origin_method: str = ""

    # Validation
    reinsertion_safe: bool = False
    confidence: float = 0.0
    reason_codes: List[str] = field(default_factory=list)

    # Metadata
    context_prev: str = ""
    context_next: str = ""
    is_tokenized: bool = False

    # UI/HUD Tilemap support
    kind: str = "text"                              # "text" | "UI_TILEMAP_LABEL"
    raw_tokens: str = ""                            # "<TILE:XX>..." sequence
    constraints: Optional[Dict[str, Any]] = None    # {"fixed_length": True, "max_bytes": N}
    encoding: str = ""                              # encoding hint


@dataclass
class TilemapRegion:
    """Region definition for UI/HUD tilemap extraction (guided input)."""
    offset: int
    length: int
    kind: str                                       # "tilemap" | "font"
    console: str                                    # "SMS" | "NES" | "SNES" | "MD"
    glyph_map: Optional[Dict[int, str]] = None      # tile index -> character
    tile_attrs_mask: int = 0xFF                     # bits to preserve
    name: str = ""                                  # optional label


class TextUnifier:
    """
    Unifies static and runtime text items.

    Merges by:
    1. Exact text match
    2. Fuzzy similarity (edit distance)
    3. Offset/screen context
    """

    def __init__(self, similarity_threshold: float = 0.85):
        """
        Initialize unifier.

        Args:
            similarity_threshold: Minimum similarity for matching (0-1)
        """
        self.similarity_threshold = similarity_threshold
        self.matcher = SimilarityMatcher(similarity_threshold)
        self._unified_items: List[UnifiedTextItem] = []
        self._item_counter = 0

    def unify(self,
              static_items: List[StaticTextItem],
              runtime_items: List[RuntimeTextItem]
              ) -> List[UnifiedTextItem]:
        """
        Unify static and runtime items.

        Args:
            static_items: Items from static ROM analysis
            runtime_items: Items from runtime capture

        Returns:
            List of UnifiedTextItem
        """
        self._unified_items = []
        self._item_counter = 0

        # Index runtime items by text hash for fast lookup
        runtime_by_hash: Dict[str, List[RuntimeTextItem]] = {}
        for item in runtime_items:
            h = self._text_hash(item.text)
            if h not in runtime_by_hash:
                runtime_by_hash[h] = []
            runtime_by_hash[h].append(item)

        used_runtime: Set[str] = set()

        # Phase 1: Match static items with runtime items
        for static in static_items:
            static_hash = self._text_hash(static.text)

            # Try exact match first
            if static_hash in runtime_by_hash:
                matches = runtime_by_hash[static_hash]
                unified = self._create_merged_item(static, matches)
                self._unified_items.append(unified)
                for m in matches:
                    used_runtime.add(m.id)
                continue

            # Try fuzzy match
            best_match = None
            best_score = 0.0

            for h, candidates in runtime_by_hash.items():
                for cand in candidates:
                    if cand.id in used_runtime:
                        continue

                    score = self.matcher.similarity(static.text, cand.text)
                    if score >= self.similarity_threshold and score > best_score:
                        best_match = cand
                        best_score = score

            if best_match:
                unified = self._create_merged_item(static, [best_match])
                unified.confidence = best_score
                self._unified_items.append(unified)
                used_runtime.add(best_match.id)
            else:
                # Static-only item
                unified = self._create_static_only(static)
                self._unified_items.append(unified)

        # Phase 2: Add runtime-only items
        for item in runtime_items:
            if item.id not in used_runtime:
                unified = self._create_runtime_only(item)
                self._unified_items.append(unified)

        # Add context
        self._add_context()

        return self._unified_items

    def _text_hash(self, text: str) -> str:
        """Compute normalized text hash."""
        normalized = text.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()[:12]

    def _create_merged_item(self,
                            static: StaticTextItem,
                            runtime: List[RuntimeTextItem]
                            ) -> UnifiedTextItem:
        """Create unified item from static and runtime."""
        self._item_counter += 1

        # Prefer static text as source (more reliable)
        text_src = static.text

        # Collect screen IDs
        screen_ids = list(set(r.screen_id for r in runtime))

        return UnifiedTextItem(
            id=f"U_{self._item_counter:05d}",
            text_src=text_src,
            source="merged",
            static_offset=static.offset,
            static_item=static,
            runtime_items=runtime,
            screen_ids=screen_ids,
            origin_offset=static.offset,
            origin_method=static.method,
            reinsertion_safe=True,  # Validated later
            confidence=max(static.confidence, max(r.confidence for r in runtime)),
            is_tokenized='<' in text_src and '>' in text_src,
        )

    def _create_static_only(self, static: StaticTextItem) -> UnifiedTextItem:
        """Create unified item from static only."""
        self._item_counter += 1

        return UnifiedTextItem(
            id=f"U_{self._item_counter:05d}",
            text_src=static.text,
            source="static",
            static_offset=static.offset,
            static_item=static,
            origin_offset=static.offset,
            origin_method=static.method,
            reinsertion_safe=True,
            confidence=static.confidence,
            reason_codes=["static_only"],
            is_tokenized='<' in static.text and '>' in static.text,
        )

    def _create_runtime_only(self, runtime: RuntimeTextItem) -> UnifiedTextItem:
        """Create unified item from runtime only."""
        self._item_counter += 1

        return UnifiedTextItem(
            id=f"U_{self._item_counter:05d}",
            text_src=runtime.text,
            source="runtime",
            runtime_items=[runtime],
            screen_ids=[runtime.screen_id],
            reinsertion_safe=False,  # No static origin
            confidence=runtime.confidence,
            reason_codes=["runtime_only", "no_static_origin"],
            is_tokenized='<' in runtime.text and '>' in runtime.text,
        )

    def _add_context(self) -> None:
        """Add context (previous/next text) to items."""
        for i, item in enumerate(self._unified_items):
            if i > 0:
                prev_text = self._unified_items[i - 1].text_src
                item.context_prev = prev_text[:50] if len(prev_text) > 50 else prev_text

            if i < len(self._unified_items) - 1:
                next_text = self._unified_items[i + 1].text_src
                item.context_next = next_text[:50] if len(next_text) > 50 else next_text

    def get_coverage_stats(self) -> Dict[str, Any]:
        """Get unification coverage statistics."""
        total = len(self._unified_items)
        if total == 0:
            return {"total": 0}

        merged = sum(1 for i in self._unified_items if i.source == "merged")
        static_only = sum(1 for i in self._unified_items if i.source == "static")
        runtime_only = sum(1 for i in self._unified_items if i.source == "runtime")
        safe = sum(1 for i in self._unified_items if i.reinsertion_safe)

        return {
            "total": total,
            "merged": merged,
            "static_only": static_only,
            "runtime_only": runtime_only,
            "reinsertion_safe": safe,
            "safe_ratio": safe / total if total > 0 else 0,
        }
