# -*- coding: utf-8 -*-
"""
RTCE Engine - Motor principal de captura de texto runtime
Orquestra scanner, heurística e perfis de plataforma
"""

from typing import List, Dict, Optional, Set
from dataclasses import dataclass, asdict
import time

from .memory_scanner import MemoryScanner, MemoryRegion
from .text_heuristics import TextHeuristics, TextCandidate, TextType
from .platform_profiles import PlatformProfiles, PlatformProfile


@dataclass
class RTCEResult:
    """Resultado de captura RTCE"""
    source: str  # "runtime"
    offset: str  # "0x7E1A20"
    text: str
    text_type: str  # "menu_string", "word", "phrase"
    confidence: float
    metrics: Dict
    timestamp: float


class RTCEEngine:
    """
    Runtime Text Capture Engine - Motor principal.

    Orquestra:
    - Memory Scanner (leitura de memória)
    - Text Heuristics (análise linguística)
    - Platform Profiles (configuração específica)
    - Deduplicação e tracking de mudanças
    """

    def __init__(self, platform: str = 'SNES', process_name: Optional[str] = None):
        """
        Inicializa o engine.

        Args:
            platform: Nome da plataforma (SNES, NES, PS1, etc)
            process_name: Nome do processo do emulador (opcional)
        """
        self.platform = platform.upper()
        self.profile = PlatformProfiles.get_profile(self.platform)

        if not self.profile:
            raise ValueError(f"Plataforma '{platform}' não suportada")

        self.scanner = MemoryScanner(process_name=process_name)
        self.heuristics = TextHeuristics()

        # Tracking state
        self._seen_texts: Set[str] = set()
        self._last_results: List[RTCEResult] = []
        self._running = False

    def attach_to_process(self, process_name: Optional[str] = None,
                         pid: Optional[int] = None) -> bool:
        """
        Anexa ao processo do emulador.

        Args:
            process_name: Nome do executável (ex: "snes9x.exe")
            pid: Process ID direto

        Returns:
            True se anexado com sucesso
        """
        if process_name:
            self.scanner.process_name = process_name
        if pid:
            self.scanner.pid = pid

        return self.scanner.attach()

    def detach_from_process(self):
        """Desanexa do processo"""
        self.scanner.detach()
        self._running = False

    def scan_once(self, deduplicate: bool = True) -> List[RTCEResult]:
        """
        Executa scan único da memória.

        Args:
            deduplicate: Remover textos já vistos

        Returns:
            Lista de resultados encontrados
        """
        if not self.scanner.handle:
            raise RuntimeError("Scanner não anexado a processo")

        results = []

        # Determinar range de memória a escanear
        start_addr = self.profile.ram_start
        end_addr = start_addr + self.profile.ram_size

        # Ler memória em regiões
        regions = self.scanner.scan_range(start_addr, end_addr, chunk_size=4096)

        # Analisar cada região
        for region in regions:
            # Testar cada encoding suportado
            for encoding in self.profile.encodings:
                candidates = self.heuristics.scan_memory_for_strings(
                    region.data,
                    region.base_address,
                    encoding
                )

                # Converter candidatos em resultados
                for candidate in candidates:
                    # Deduplicação
                    if deduplicate and candidate.text in self._seen_texts:
                        continue

                    result = RTCEResult(
                        source="runtime",
                        offset=f"0x{candidate.offset:X}",
                        text=candidate.text,
                        text_type=candidate.text_type.value,
                        confidence=candidate.confidence,
                        metrics=candidate.metrics,
                        timestamp=time.time()
                    )

                    results.append(result)
                    self._seen_texts.add(candidate.text)

        self._last_results = results
        return results

    def scan_continuous(self, interval: float = 1.0, max_iterations: int = 0,
                       callback: Optional[callable] = None):
        """
        Scan contínuo da memória com detecção de mudanças.

        Args:
            interval: Intervalo entre scans (segundos)
            max_iterations: Máximo de iterações (0 = infinito)
            callback: Função chamada a cada resultado novo
        """
        if not self.scanner.handle:
            raise RuntimeError("Scanner não anexado a processo")

        self._running = True
        iteration = 0

        while self._running:
            if max_iterations > 0 and iteration >= max_iterations:
                break

            # Executar scan
            results = self.scan_once(deduplicate=True)

            # Callback com resultados novos
            if results and callback:
                callback(results)

            iteration += 1
            time.sleep(interval)

    def stop_continuous_scan(self):
        """Para scan contínuo"""
        self._running = False

    def get_changed_texts(self) -> List[RTCEResult]:
        """
        Detecta textos que mudaram desde último scan.

        Returns:
            Lista de textos novos/mudados
        """
        if not self.scanner.handle:
            raise RuntimeError("Scanner não anexado a processo")

        results = []

        # Detectar mudanças de memória
        start_addr = self.profile.ram_start
        end_addr = start_addr + self.profile.ram_size

        changes = self.scanner.scan_changed_memory(start_addr, end_addr)

        # Analisar regiões mudadas
        for address, old_data, new_data in changes:
            for encoding in self.profile.encodings:
                # Analisar dados novos
                candidates = self.heuristics.scan_memory_for_strings(
                    new_data,
                    address,
                    encoding
                )

                for candidate in candidates:
                    result = RTCEResult(
                        source="runtime",
                        offset=f"0x{candidate.offset:X}",
                        text=candidate.text,
                        text_type=candidate.text_type.value,
                        confidence=candidate.confidence,
                        metrics=candidate.metrics,
                        timestamp=time.time()
                    )
                    results.append(result)

        return results

    def export_results(self, format: str = 'json') -> str:
        """
        Exporta resultados em formato específico.

        Args:
            format: 'json' ou 'csv'

        Returns:
            String formatada
        """
        if format == 'json':
            import json
            data = [asdict(r) for r in self._last_results]
            return json.dumps(data, indent=2, ensure_ascii=False)

        elif format == 'csv':
            import csv
            import io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=[
                'source', 'offset', 'text', 'text_type', 'confidence'
            ])
            writer.writeheader()
            for result in self._last_results:
                writer.writerow({
                    'source': result.source,
                    'offset': result.offset,
                    'text': result.text,
                    'text_type': result.text_type,
                    'confidence': result.confidence
                })
            return output.getvalue()

        else:
            raise ValueError(f"Formato '{format}' não suportado")

    def get_statistics(self) -> Dict:
        """
        Retorna estatísticas da captura.

        Returns:
            Dicionário com métricas
        """
        if not self._last_results:
            return {}

        total = len(self._last_results)
        by_type = {}
        avg_confidence = 0.0

        for result in self._last_results:
            by_type[result.text_type] = by_type.get(result.text_type, 0) + 1
            avg_confidence += result.confidence

        avg_confidence /= total if total > 0 else 1

        return {
            'total_texts': total,
            'unique_texts': len(self._seen_texts),
            'by_type': by_type,
            'avg_confidence': avg_confidence,
            'platform': self.platform
        }

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.detach_from_process()
