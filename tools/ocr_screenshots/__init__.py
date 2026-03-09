# -*- coding: utf-8 -*-
"""
Ferramentas OCR por screenshots para complementar o Runtime Dyn.
"""

from .ocr_processor import process_screenshots_folder
from .glyph_matcher import run_ocr_screenshot_pipeline

__all__ = [
    "process_screenshots_folder",
    "run_ocr_screenshot_pipeline",
]

