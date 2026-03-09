# -*- coding: utf-8 -*-
"""
================================================================================
RUNTIME - Emulator-Based Text Capture Mode
================================================================================
Runtime text capture using Libretro backend for 100% text coverage.
No OCR - uses tilemap/VRAM reading or glyph learning.

Essential for N64 and PS1 where static extraction is insufficient.
================================================================================
"""

from .emulator_runtime_host import EmulatorRuntimeHost
from .runtime_text_harvester import RuntimeTextHarvester
from .auto_explorer import AutoExplorer
from .screen_change_detector import ScreenChangeDetector
from .origin_tracker import OriginTracker

__all__ = [
    'EmulatorRuntimeHost',
    'RuntimeTextHarvester',
    'AutoExplorer',
    'ScreenChangeDetector',
    'OriginTracker',
]
