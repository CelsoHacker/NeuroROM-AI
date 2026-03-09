# -*- coding: utf-8 -*-
"""
================================================================================
AUTO EXPLORER - Deterministic Game Exploration Bot
================================================================================
Automatically explores games using deterministic input sequences.
Detects screen changes and captures text at each new screen.
================================================================================
"""

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Set
from enum import Enum

from .emulator_runtime_host import EmulatorRuntimeHost, RetroJoypad
from .screen_change_detector import ScreenChangeDetector
from .runtime_text_harvester import RuntimeTextHarvester, RuntimeTextItem


class ExplorationPhase(Enum):
    """Exploration phases."""
    TITLE = "title"
    MENU = "menu"
    GAMEPLAY = "gameplay"
    DIALOG = "dialog"


@dataclass
class ExplorationResult:
    """Result of exploration session."""
    screens_visited: int
    texts_captured: int
    frames_elapsed: int
    items: List[RuntimeTextItem] = field(default_factory=list)


class AutoExplorer:
    """
    Deterministic bot for automated game exploration.

    Uses fixed input sequences with screen change detection
    to explore games and capture text.
    """

    # Input sequences for different phases
    TITLE_SEQUENCE = [
        (RetroJoypad.START, 30),   # Press START, wait 30 frames
        (None, 60),                 # Wait 60 frames
        (RetroJoypad.START, 30),   # Press START again
        (None, 60),
    ]

    MENU_SEQUENCE = [
        (RetroJoypad.DOWN, 15),    # Navigate down
        (None, 30),
        (RetroJoypad.A, 15),       # Confirm
        (None, 45),
        (RetroJoypad.B, 15),       # Back
        (None, 30),
    ]

    DIALOG_SEQUENCE = [
        (RetroJoypad.A, 10),       # Advance dialog
        (None, 20),
    ]

    EXPLORATION_SEQUENCE = [
        (RetroJoypad.RIGHT, 30),
        (None, 15),
        (RetroJoypad.LEFT, 30),
        (None, 15),
        (RetroJoypad.UP, 30),
        (None, 15),
        (RetroJoypad.DOWN, 30),
        (None, 15),
        (RetroJoypad.A, 15),
        (None, 30),
    ]

    def __init__(self, host: EmulatorRuntimeHost,
                 screen_detector: ScreenChangeDetector,
                 harvester: RuntimeTextHarvester):
        """
        Initialize explorer.

        Args:
            host: Emulator runtime host
            screen_detector: Screen change detector
            harvester: Text harvester
        """
        self.host = host
        self.screen_detector = screen_detector
        self.harvester = harvester

        self._phase = ExplorationPhase.TITLE
        self._visited_screens: Set[str] = set()
        self._stuck_counter = 0
        self._max_stuck = 300  # Max frames without change before giving up

    def explore(self,
                max_screens: int = 100,
                max_frames: int = 18000,
                on_new_screen: Optional[Callable[[str], None]] = None
                ) -> ExplorationResult:
        """
        Explore the game automatically.

        Args:
            max_screens: Maximum unique screens to visit
            max_frames: Maximum frames to run (300 = 5 seconds at 60fps)
            on_new_screen: Callback when new screen is found

        Returns:
            ExplorationResult with captured items
        """
        all_items: List[RuntimeTextItem] = []
        start_frame = self.host.get_frame_count()

        # Start with title sequence
        self._execute_sequence(self.TITLE_SEQUENCE)

        while True:
            current_frame = self.host.get_frame_count() - start_frame

            # Check termination conditions
            if current_frame >= max_frames:
                break
            if len(self._visited_screens) >= max_screens:
                break

            # Get current frame and detect changes
            frame = self.host.get_frame()
            if frame:
                changed, is_new = self.screen_detector.process_frame(
                    frame.data, frame.width, frame.height, current_frame
                )

                if changed:
                    self._stuck_counter = 0
                    screen_id = self.screen_detector.get_current_screen_id()

                    if is_new:
                        self._visited_screens.add(screen_id)

                        if on_new_screen:
                            on_new_screen(screen_id)

                        # Harvest text from new screen
                        items = self._harvest_screen(screen_id)
                        all_items.extend(items)

                        # Detect phase from screen content
                        self._detect_phase(items)
                else:
                    self._stuck_counter += 1

            # Execute phase-appropriate inputs
            if self._stuck_counter > self._max_stuck:
                # Stuck - try random exploration
                self._execute_sequence(self.EXPLORATION_SEQUENCE)
                self._stuck_counter = 0
            else:
                self._execute_phase_inputs()

        return ExplorationResult(
            screens_visited=len(self._visited_screens),
            texts_captured=len(all_items),
            frames_elapsed=self.host.get_frame_count() - start_frame,
            items=all_items,
        )

    def _harvest_screen(self, screen_id: str) -> List[RuntimeTextItem]:
        """Harvest text from current screen."""
        # Wait for screen to stabilize
        for _ in range(30):
            self.host.step_frame()

        # Try Plan A first
        items = self.harvester.harvest_plan_a(screen_id)

        # If Plan A didn't find much, try Plan B
        if len(items) < 2:
            frame = self.host.get_frame()
            if frame:
                items.extend(self.harvester.harvest_plan_b(screen_id, frame))

        return items

    def _detect_phase(self, items: List[RuntimeTextItem]) -> None:
        """Detect exploration phase from captured text."""
        if not items:
            return

        # Simple heuristics
        all_text = ' '.join(item.text.lower() for item in items)

        if any(kw in all_text for kw in ['start', 'press', 'push', 'begin']):
            self._phase = ExplorationPhase.TITLE
        elif any(kw in all_text for kw in ['new game', 'continue', 'options', 'load']):
            self._phase = ExplorationPhase.MENU
        elif len(all_text) > 100 or any(kw in all_text for kw in ['...', '?', '!']):
            self._phase = ExplorationPhase.DIALOG
        else:
            self._phase = ExplorationPhase.GAMEPLAY

    def _execute_phase_inputs(self) -> None:
        """Execute inputs appropriate for current phase."""
        if self._phase == ExplorationPhase.TITLE:
            self._execute_sequence(self.TITLE_SEQUENCE[:2])
        elif self._phase == ExplorationPhase.MENU:
            self._execute_sequence(self.MENU_SEQUENCE[:4])
        elif self._phase == ExplorationPhase.DIALOG:
            self._execute_sequence(self.DIALOG_SEQUENCE)
        else:
            self._execute_sequence(self.EXPLORATION_SEQUENCE[:4])

    def _execute_sequence(self, sequence: List) -> None:
        """Execute an input sequence."""
        for item in sequence:
            button, frames = item

            if button is not None:
                self.host.press_button(button, 1)

            for _ in range(frames - 1):
                self.host.step_frame()

    def reset(self) -> None:
        """Reset explorer state."""
        self._phase = ExplorationPhase.TITLE
        self._visited_screens.clear()
        self._stuck_counter = 0
        self.screen_detector.reset()
        self.harvester.clear()
        self.host.reset()
