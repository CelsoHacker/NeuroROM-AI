# -*- coding: utf-8 -*-
"""
Text Capture Orchestrator - Orquestra OCR + RTCE
Combina resultados de ambas fontes para máxima precisão
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class TextSource(Enum):
    """Fonte do texto"""
    OCR = "ocr"           # Texto gráfico (tiles/sprites)
    RUNTIME = "runtime"   # Texto string (memória)
    HYBRID = "hybrid"     # Confirmado por ambos


@dataclass
class UnifiedText:
    """Texto unificado de múltiplas fontes"""
    text: str
    source: TextSource
    confidence: float
    ocr_result: Optional[Dict] = None
    runtime_result: Optional[Dict] = None


class TextCaptureOrchestrator:
    """
    Orquestrador inteligente que combina OCR e RTCE.

    Estratégias:
    1. Se ambos detectarem texto similar → aumenta confiança (HYBRID)
    2. Se OCR detectar gráfico → marca como OCR
    3. Se RTCE detectar string → marca como RUNTIME
    4. Deduplicação inteligente
    """

    SIMILARITY_THRESHOLD = 0.85

    def __init__(self):
        self.ocr_results: List[Dict] = []
        self.runtime_results: List[Dict] = []
        self.unified_results: List[UnifiedText] = []

    def add_ocr_result(self, result: Dict):
        """Adiciona resultado do OCR"""
        self.ocr_results.append(result)

    def add_runtime_result(self, result: Dict):
        """Adiciona resultado do RTCE"""
        self.runtime_results.append(result)

    def unify_results(self) -> List[UnifiedText]:
        """
        Unifica resultados de ambas fontes.

        Returns:
            Lista de textos unificados
        """
        unified = []
        matched_runtime = set()

        # Processar OCR first
        for ocr in self.ocr_results:
            ocr_text = ocr.get('text', '')
            best_match = None
            best_score = 0.0

            # Tentar match com RTCE
            for i, runtime in enumerate(self.runtime_results):
                if i in matched_runtime:
                    continue

                runtime_text = runtime.get('text', '')
                similarity = self._calculate_similarity(ocr_text, runtime_text)

                if similarity > best_score and similarity >= self.SIMILARITY_THRESHOLD:
                    best_score = similarity
                    best_match = (i, runtime)

            # Decidir fonte
            if best_match:
                # HYBRID - confirmado por ambos
                matched_runtime.add(best_match[0])
                unified.append(UnifiedText(
                    text=ocr_text,
                    source=TextSource.HYBRID,
                    confidence=(ocr.get('confidence', 0) + best_match[1].get('confidence', 0)) / 2,
                    ocr_result=ocr,
                    runtime_result=best_match[1]
                ))
            else:
                # OCR only
                unified.append(UnifiedText(
                    text=ocr_text,
                    source=TextSource.OCR,
                    confidence=ocr.get('confidence', 0),
                    ocr_result=ocr
                ))

        # Adicionar RTCE não-matched
        for i, runtime in enumerate(self.runtime_results):
            if i not in matched_runtime:
                unified.append(UnifiedText(
                    text=runtime.get('text', ''),
                    source=TextSource.RUNTIME,
                    confidence=runtime.get('confidence', 0),
                    runtime_result=runtime
                ))

        self.unified_results = unified
        return unified

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calcula similaridade entre textos (0.0-1.0)"""
        if not text1 or not text2:
            return 0.0

        # Normalizar
        t1 = text1.lower().strip()
        t2 = text2.lower().strip()

        # Levenshtein distance simplificado
        if t1 == t2:
            return 1.0

        # Ratio de caracteres comuns
        common = sum(1 for a, b in zip(t1, t2) if a == b)
        max_len = max(len(t1), len(t2))

        return common / max_len if max_len > 0 else 0.0

    def get_by_source(self, source: TextSource) -> List[UnifiedText]:
        """Filtra por fonte"""
        return [r for r in self.unified_results if r.source == source]

    def export_unified(self) -> List[Dict]:
        """Exporta resultados unificados como dicionários"""
        return [
            {
                'text': r.text,
                'source': r.source.value,
                'confidence': r.confidence,
                'has_ocr': r.ocr_result is not None,
                'has_runtime': r.runtime_result is not None
            }
            for r in self.unified_results
        ]
