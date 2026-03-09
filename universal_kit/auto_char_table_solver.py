# -*- coding: utf-8 -*-
"""
================================================================================
AUTO CHAR TABLE SOLVER - Automatic Character Table Discovery
================================================================================
Uses beam search guided by PerfectScore to discover character mappings
for tile-based text in ROMs without external databases.

Learns SPACE/END/NEWLINE first, then expands to full alphabet.
Falls back to tokenized output when confidence is low.
================================================================================
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from collections import Counter
import math
import re


@dataclass
class CharTableHypothesis:
    """A hypothesis for character table mapping."""
    mapping: Dict[int, str] = field(default_factory=dict)
    confidence: Dict[int, float] = field(default_factory=dict)
    unknown_tiles: Set[int] = field(default_factory=set)
    frozen_tiles: Set[int] = field(default_factory=set)  # High-confidence mappings
    score: float = 0.0
    iteration: int = 0

    def get_char(self, tile_idx: int) -> str:
        """Get character for tile, or tokenized form."""
        if tile_idx in self.mapping:
            return self.mapping[tile_idx]
        return f"<TILE_{tile_idx:02X}>"

    def decode(self, indices: List[int]) -> str:
        """Decode tile indices to string."""
        return ''.join(self.get_char(i) for i in indices)

    def clone(self) -> 'CharTableHypothesis':
        """Create a deep copy."""
        return CharTableHypothesis(
            mapping=dict(self.mapping),
            confidence=dict(self.confidence),
            unknown_tiles=set(self.unknown_tiles),
            frozen_tiles=set(self.frozen_tiles),
            score=self.score,
            iteration=self.iteration,
        )


@dataclass
class SolverConfig:
    """Configuration for the solver."""
    beam_width: int = 10
    max_iterations: int = 1000
    min_confidence: float = 0.7
    freeze_threshold: float = 0.95
    language: str = "en"  # en, pt, ja, etc.


class LanguageModel:
    """Simple language model for scoring text."""

    # Letter frequencies by language
    FREQUENCIES = {
        "en": {
            'e': 0.127, 't': 0.091, 'a': 0.082, 'o': 0.075, 'i': 0.070,
            'n': 0.067, 's': 0.063, 'h': 0.061, 'r': 0.060, 'd': 0.043,
            'l': 0.040, 'c': 0.028, 'u': 0.028, 'm': 0.024, 'w': 0.024,
            'f': 0.022, 'g': 0.020, 'y': 0.020, 'p': 0.019, 'b': 0.015,
            'v': 0.010, 'k': 0.008, 'j': 0.002, 'x': 0.002, 'q': 0.001,
            'z': 0.001, ' ': 0.180,
        },
        "pt": {
            'a': 0.146, 'e': 0.127, 'o': 0.107, 's': 0.078, 'r': 0.065,
            'i': 0.062, 'n': 0.050, 'd': 0.050, 'm': 0.047, 'u': 0.046,
            't': 0.043, 'c': 0.039, 'l': 0.028, 'p': 0.025, 'v': 0.017,
            'g': 0.013, 'h': 0.013, 'q': 0.012, 'b': 0.010, 'f': 0.010,
            'z': 0.005, 'j': 0.004, 'x': 0.003, 'k': 0.001, 'w': 0.001,
            'y': 0.001, ' ': 0.170,
        },
        "ja": {
            # Hiragana frequencies (simplified)
            ' ': 0.15, 'の': 0.08, 'に': 0.06, 'を': 0.05, 'は': 0.05,
            'た': 0.04, 'が': 0.04, 'て': 0.04, 'い': 0.04, 'る': 0.04,
        }
    }

    # Common bigrams
    BIGRAMS = {
        "en": ['th', 'he', 'in', 'er', 'an', 'on', 're', 'ed', 'nd', 'ha',
               'at', 'en', 'es', 'of', 'or', 'nt', 'ea', 'ti', 'to', 'it'],
        "pt": ['de', 'os', 'ao', 'as', 'es', 'do', 'da', 'em', 'um', 'no',
               'qu', 'ão', 'se', 'te', 'ra', 'co', 'en', 'ta', 're', 'na'],
    }

    # Common trigrams
    TRIGRAMS = {
        "en": ['the', 'and', 'ing', 'ion', 'tio', 'ent', 'ati', 'for',
               'her', 'ter', 'hat', 'tha', 'ere', 'ate', 'his', 'con'],
        "pt": ['que', 'ent', 'ção', 'ade', 'com', 'est', 'ara', 'men',
               'ões', 'par', 'nte', 'res', 'ter', 'dos', 'ão ', 'sta'],
    }

    def __init__(self, language: str = "en"):
        self.language = language
        self.freqs = self.FREQUENCIES.get(language, self.FREQUENCIES["en"])
        self.bigrams = set(self.BIGRAMS.get(language, self.BIGRAMS["en"]))
        self.trigrams = set(self.TRIGRAMS.get(language, self.TRIGRAMS["en"]))

    def score_text(self, text: str) -> float:
        """
        Score text based on language model.

        Returns:
            Score between 0.0 (not language-like) and 1.0 (very language-like)
        """
        if not text or len(text) < 3:
            return 0.0

        text_lower = text.lower()

        # Score components
        freq_score = self._frequency_score(text_lower)
        bigram_score = self._bigram_score(text_lower)
        trigram_score = self._trigram_score(text_lower)
        structure_score = self._structure_score(text)

        # Weighted combination
        total = (
            freq_score * 0.30 +
            bigram_score * 0.25 +
            trigram_score * 0.25 +
            structure_score * 0.20
        )

        return min(1.0, max(0.0, total))

    def _frequency_score(self, text: str) -> float:
        """Score based on letter frequency correlation."""
        if not text:
            return 0.0

        observed = Counter(text)
        total = sum(observed.values())

        correlation = 0.0
        for char, expected_freq in self.freqs.items():
            observed_freq = observed.get(char, 0) / total
            # Penalize large deviations
            diff = abs(expected_freq - observed_freq)
            correlation += max(0, 1 - diff * 5)

        return correlation / len(self.freqs)

    def _bigram_score(self, text: str) -> float:
        """Score based on common bigrams."""
        if len(text) < 2:
            return 0.0

        found = 0
        for i in range(len(text) - 1):
            if text[i:i + 2] in self.bigrams:
                found += 1

        return min(1.0, found / (len(text) / 4))

    def _trigram_score(self, text: str) -> float:
        """Score based on common trigrams."""
        if len(text) < 3:
            return 0.0

        found = 0
        for i in range(len(text) - 2):
            if text[i:i + 3] in self.trigrams:
                found += 1

        return min(1.0, found / (len(text) / 6))

    def _structure_score(self, text: str) -> float:
        """Score based on text structure (words, punctuation)."""
        # Check for word-like patterns
        words = text.split()
        if not words:
            return 0.0

        # Good text has reasonable word lengths
        avg_word_len = sum(len(w) for w in words) / len(words)
        word_len_score = 1.0 if 3 <= avg_word_len <= 8 else 0.5

        # Good text has some punctuation but not too much
        punct = sum(1 for c in text if c in '.,!?;:')
        punct_ratio = punct / len(text) if text else 0
        punct_score = 1.0 if 0.01 <= punct_ratio <= 0.10 else 0.5

        return (word_len_score + punct_score) / 2


class AutoCharTableSolver:
    """
    Beam search solver for automatic character table discovery.
    Uses language model scoring to guide the search.
    """

    def __init__(self, rom_data: bytes, config: Optional[SolverConfig] = None):
        self.rom_data = rom_data
        self.config = config or SolverConfig()
        self.language_model = LanguageModel(self.config.language)

    def solve(self,
              text_samples: List[bytes],
              known_mappings: Optional[Dict[int, str]] = None,
              space_hint: Optional[int] = None,
              terminator_hint: Optional[int] = None) -> CharTableHypothesis:
        """
        Solve character table using beam search.

        Args:
            text_samples: Sample byte sequences known to be text
            known_mappings: Pre-known tile->char mappings
            space_hint: Suspected space tile index
            terminator_hint: Suspected terminator tile index

        Returns:
            Best CharTableHypothesis found
        """
        # Initialize with known mappings
        initial = CharTableHypothesis()
        if known_mappings:
            initial.mapping.update(known_mappings)
            for tile_idx in known_mappings:
                initial.confidence[tile_idx] = 1.0
                initial.frozen_tiles.add(tile_idx)

        # Collect all unique tiles from samples
        all_tiles: Set[int] = set()
        for sample in text_samples:
            all_tiles.update(sample)

        if terminator_hint is not None:
            all_tiles.discard(terminator_hint)

        initial.unknown_tiles = all_tiles - set(initial.mapping.keys())

        # Phase 1: Find space character (most common)
        if space_hint is not None and space_hint not in initial.mapping:
            initial.mapping[space_hint] = ' '
            initial.confidence[space_hint] = 0.9
        else:
            space_tile = self._find_space(text_samples, initial)
            if space_tile is not None and space_tile not in initial.mapping:
                initial.mapping[space_tile] = ' '
                initial.confidence[space_tile] = 0.8

        # Phase 2: Beam search for remaining characters
        beam = [initial]

        for iteration in range(self.config.max_iterations):
            if not beam:
                break

            # Check if all tiles are mapped
            if all(h.unknown_tiles == set() for h in beam):
                break

            new_beam = []

            for hypothesis in beam:
                if not hypothesis.unknown_tiles:
                    new_beam.append(hypothesis)
                    continue

                # Generate candidate expansions
                expansions = self._expand_hypothesis(hypothesis, text_samples)
                new_beam.extend(expansions)

            # Score and prune
            for h in new_beam:
                h.score = self._score_hypothesis(h, text_samples)
                h.iteration = iteration

            # Keep top beam_width
            new_beam.sort(key=lambda h: h.score, reverse=True)
            beam = new_beam[:self.config.beam_width]

            # Freeze high-confidence mappings
            for h in beam:
                for tile_idx, conf in list(h.confidence.items()):
                    if conf >= self.config.freeze_threshold:
                        h.frozen_tiles.add(tile_idx)

        # Return best hypothesis
        if beam:
            best = max(beam, key=lambda h: h.score)
            return best

        return initial

    def _find_space(self, samples: List[bytes],
                    hypothesis: CharTableHypothesis) -> Optional[int]:
        """Find the most likely space character."""
        counter = Counter()

        for sample in samples:
            for tile_idx in sample:
                if tile_idx not in hypothesis.mapping:
                    counter[tile_idx] += 1

        if not counter:
            return None

        # Space should be one of the most common
        most_common = counter.most_common(3)
        for tile_idx, count in most_common:
            # Skip if count is too low or too high (terminator)
            total = sum(counter.values())
            ratio = count / total
            if 0.05 <= ratio <= 0.30:
                return tile_idx

        return most_common[0][0] if most_common else None

    def _expand_hypothesis(self, hypothesis: CharTableHypothesis,
                           samples: List[bytes]) -> List[CharTableHypothesis]:
        """Generate candidate expansions for a hypothesis."""
        expansions = []

        if not hypothesis.unknown_tiles:
            return [hypothesis]

        # Pick most frequent unknown tile
        counter = Counter()
        for sample in samples:
            for tile_idx in sample:
                if tile_idx in hypothesis.unknown_tiles:
                    counter[tile_idx] += 1

        if not counter:
            return [hypothesis]

        target_tile = counter.most_common(1)[0][0]

        # Try common characters
        candidates = self._get_candidate_chars(hypothesis)

        for char in candidates[:5]:  # Limit expansions
            new_hyp = hypothesis.clone()
            new_hyp.mapping[target_tile] = char
            new_hyp.confidence[target_tile] = 0.5
            new_hyp.unknown_tiles.discard(target_tile)
            expansions.append(new_hyp)

        return expansions if expansions else [hypothesis]

    def _get_candidate_chars(self, hypothesis: CharTableHypothesis) -> List[str]:
        """Get characters not yet used in hypothesis."""
        used = set(hypothesis.mapping.values())

        # Priority order based on language frequency
        all_chars = list(self.language_model.freqs.keys())
        all_chars.sort(key=lambda c: self.language_model.freqs.get(c, 0), reverse=True)

        return [c for c in all_chars if c not in used]

    def _score_hypothesis(self, hypothesis: CharTableHypothesis,
                          samples: List[bytes]) -> float:
        """Score a hypothesis based on decoded text quality."""
        total_score = 0.0
        count = 0

        for sample in samples:
            indices = list(sample)
            decoded = hypothesis.decode(indices)

            # Skip if mostly tokenized
            if decoded.count('<TILE_') > len(decoded) / 10:
                continue

            # Score with language model
            text_score = self.language_model.score_text(decoded)
            total_score += text_score
            count += 1

        if count == 0:
            return 0.0

        avg_score = total_score / count

        # Bonus for mapping more tiles
        coverage = len(hypothesis.mapping) / max(1, len(hypothesis.mapping) + len(hypothesis.unknown_tiles))

        return avg_score * 0.7 + coverage * 0.3

    def solve_incremental(self,
                          new_sample: bytes,
                          current: CharTableHypothesis) -> CharTableHypothesis:
        """
        Incrementally improve hypothesis with new sample.

        Args:
            new_sample: New text sample
            current: Current hypothesis

        Returns:
            Updated hypothesis
        """
        # Check for new tiles
        new_tiles = set(new_sample) - set(current.mapping.keys()) - current.unknown_tiles
        current.unknown_tiles.update(new_tiles)

        # Run limited beam search
        old_iterations = self.config.max_iterations
        self.config.max_iterations = 100

        result = self.solve([new_sample], current.mapping)

        self.config.max_iterations = old_iterations
        return result


def solve_char_table(rom_data: bytes,
                     text_samples: List[bytes],
                     language: str = "en") -> CharTableHypothesis:
    """
    Convenience function to solve character table.

    Args:
        rom_data: ROM data
        text_samples: Known text byte sequences
        language: Target language (en, pt, ja)

    Returns:
        Best CharTableHypothesis
    """
    config = SolverConfig(language=language)
    solver = AutoCharTableSolver(rom_data, config)
    return solver.solve(text_samples)
