# -*- coding: utf-8 -*-
"""
================================================================================
SIMILARITY MATCHER - Fuzzy Text Matching
================================================================================
Compares text strings using edit distance and other metrics.
Used by TextUnifier to match static and runtime texts.
================================================================================
"""

from typing import List, Tuple


class SimilarityMatcher:
    """
    Fuzzy text similarity matching using multiple metrics.
    """

    def __init__(self, threshold: float = 0.85):
        """
        Initialize matcher.

        Args:
            threshold: Default similarity threshold
        """
        self.threshold = threshold

    def similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts.

        Returns:
            Similarity score between 0 (different) and 1 (identical)
        """
        if text1 == text2:
            return 1.0

        if not text1 or not text2:
            return 0.0

        # Normalize
        t1 = self._normalize(text1)
        t2 = self._normalize(text2)

        if t1 == t2:
            return 0.99  # Very similar but not exact

        # Calculate metrics
        edit_sim = self._edit_similarity(t1, t2)
        token_sim = self._token_similarity(t1, t2)

        # Weighted combination
        return edit_sim * 0.6 + token_sim * 0.4

    def _normalize(self, text: str) -> str:
        """Normalize text for comparison."""
        # Lowercase
        text = text.lower()

        # Remove token placeholders
        import re
        text = re.sub(r'<[^>]+>', '', text)

        # Normalize whitespace
        text = ' '.join(text.split())

        return text.strip()

    def _edit_similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity based on edit distance."""
        distance = self._edit_distance(s1, s2)
        max_len = max(len(s1), len(s2))

        if max_len == 0:
            return 1.0

        return 1.0 - (distance / max_len)

    def _edit_distance(self, s1: str, s2: str) -> int:
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

    def _token_similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity based on shared tokens (words)."""
        tokens1 = set(s1.split())
        tokens2 = set(s2.split())

        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        return intersection / union if union > 0 else 0.0

    def find_best_match(self, query: str,
                        candidates: List[str]) -> Tuple[int, float]:
        """
        Find best matching candidate for a query.

        Args:
            query: Text to match
            candidates: List of candidate texts

        Returns:
            Tuple of (best_index, similarity_score)
        """
        best_idx = -1
        best_score = 0.0

        for i, candidate in enumerate(candidates):
            score = self.similarity(query, candidate)
            if score > best_score:
                best_score = score
                best_idx = i

        return best_idx, best_score

    def find_matches(self, query: str,
                     candidates: List[str],
                     threshold: float = None) -> List[Tuple[int, float]]:
        """
        Find all matching candidates above threshold.

        Args:
            query: Text to match
            candidates: List of candidate texts
            threshold: Minimum similarity (default: self.threshold)

        Returns:
            List of (index, similarity) tuples, sorted by similarity
        """
        thresh = threshold if threshold is not None else self.threshold
        matches = []

        for i, candidate in enumerate(candidates):
            score = self.similarity(query, candidate)
            if score >= thresh:
                matches.append((i, score))

        return sorted(matches, key=lambda x: x[1], reverse=True)
