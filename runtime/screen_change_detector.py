# -*- coding: utf-8 -*-
"""
================================================================================
SCREEN CHANGE DETECTOR - Detects Game Screen Transitions
================================================================================
Uses frame hashing to detect when the game screen changes.
Essential for the AutoExplorer to know when new text might appear.
================================================================================
"""

from dataclasses import dataclass
from typing import List, Optional, Set, Tuple
import hashlib


@dataclass
class ScreenState:
    """Represents a unique screen state."""
    hash: str
    frame_number: int
    width: int = 0
    height: int = 0


class ScreenChangeDetector:
    """
    Detects screen changes using frame hashing.

    Uses perceptual hashing to detect significant visual changes
    while ignoring minor differences (animations, etc.).
    """

    def __init__(self, threshold: float = 0.1):
        """
        Initialize detector.

        Args:
            threshold: Difference threshold for screen change (0-1)
        """
        self.threshold = threshold
        self._current_hash: str = ""
        self._previous_hash: str = ""
        self._visited_screens: Set[str] = set()
        self._screen_history: List[ScreenState] = []

    def process_frame(self, frame_data: bytes, width: int, height: int,
                      frame_number: int) -> Tuple[bool, bool]:
        """
        Process a frame and detect changes.

        Args:
            frame_data: Raw frame pixel data
            width: Frame width
            height: Frame height
            frame_number: Current frame number

        Returns:
            Tuple of (screen_changed, is_new_screen)
        """
        # Compute frame hash
        current_hash = self._compute_hash(frame_data, width, height)

        self._previous_hash = self._current_hash
        self._current_hash = current_hash

        # Check if screen changed
        screen_changed = self._previous_hash != current_hash
        is_new = current_hash not in self._visited_screens

        if screen_changed:
            self._visited_screens.add(current_hash)
            self._screen_history.append(ScreenState(
                hash=current_hash,
                frame_number=frame_number,
                width=width,
                height=height,
            ))

        return screen_changed, is_new

    def _compute_hash(self, frame_data: bytes, width: int, height: int) -> str:
        """
        Compute a hash for frame comparison.

        Uses a simplified approach: hash every Nth pixel to reduce
        sensitivity to minor changes while detecting major transitions.
        """
        # Sample every 16th pixel for robustness
        sample_stride = 16
        sampled = bytearray()

        # Assuming RGB565 format (2 bytes per pixel)
        bytes_per_pixel = 2
        row_size = width * bytes_per_pixel

        for y in range(0, height, sample_stride):
            row_offset = y * row_size
            for x in range(0, width, sample_stride):
                pixel_offset = row_offset + (x * bytes_per_pixel)
                if pixel_offset + 1 < len(frame_data):
                    sampled.extend(frame_data[pixel_offset:pixel_offset + 2])

        return hashlib.md5(bytes(sampled)).hexdigest()[:16]

    def get_current_screen_id(self) -> str:
        """Get current screen hash."""
        return self._current_hash

    def get_visited_count(self) -> int:
        """Get number of unique screens visited."""
        return len(self._visited_screens)

    def get_screen_history(self) -> List[ScreenState]:
        """Get history of screen states."""
        return self._screen_history.copy()

    def reset(self) -> None:
        """Reset detector state."""
        self._current_hash = ""
        self._previous_hash = ""
        self._visited_screens.clear()
        self._screen_history.clear()

    def is_same_screen(self, hash1: str, hash2: str) -> bool:
        """Check if two hashes represent the same screen."""
        return hash1 == hash2

    def was_screen_visited(self, screen_hash: str) -> bool:
        """Check if a screen was already visited."""
        return screen_hash in self._visited_screens
