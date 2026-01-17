# -*- coding: utf-8 -*-
"""
================================================================================
RUNTIME TEXT CAPTURE ENGINE (RTCE)
================================================================================
Módulo de captura de textos em tempo de execução via leitura externa de memória.

Características:
- Leitura não-invasiva de processos em execução
- Heurística linguística para detecção de texto real
- Suporte multi-plataforma (SNES, NES, Mega Drive, PS1, N64)
- Integração com pipeline OCR existente
- Classificação automática: letras, palavras, frases
- Deduplicação e scoring de confiança

Author: Celso
Date: 2026-01-12
License: Proprietary
================================================================================
"""

__version__ = "1.0.0"
__author__ = "Celso"

from .memory_scanner import MemoryScanner
from .text_heuristics import TextHeuristics
from .platform_profiles import PlatformProfiles
from .rtce_engine import RTCEEngine
from .orchestrator import TextCaptureOrchestrator

__all__ = [
    'MemoryScanner',
    'TextHeuristics',
    'PlatformProfiles',
    'RTCEEngine',
    'TextCaptureOrchestrator'
]
