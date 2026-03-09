# -*- coding: utf-8 -*-
"""
================================================================================
UNIFICATION - Merge Static and Runtime Text Extraction Results
================================================================================
Combines text from static ROM analysis and runtime capture.
Validates reinsertion safety with strict criteria.
================================================================================
"""

from .text_unifier import TextUnifier, UnifiedTextItem
from .similarity_matcher import SimilarityMatcher
from .reinsertion_validator import ReinsertionValidator

__all__ = [
    'TextUnifier',
    'UnifiedTextItem',
    'SimilarityMatcher',
    'ReinsertionValidator',
]
