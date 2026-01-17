# -*- coding: utf-8 -*-
"""
================================================================================
COMPRESSION DETECTOR - Detecção Heurística de Algoritmos de Compressão
================================================================================
Identifica regiões comprimidas e infere algoritmo usado através de:
- Análise de entropia (alta = comprimido)
- Assinaturas de algoritmos (LZSS, LZ77, Huffman, RLE)
- Padrões de header
- Análise estatística de bytes

NÃO descomprime automaticamente - apenas identifica e marca regiões
================================================================================
"""

from typing import Dict, List, Tuple, Optional
from collections import Counter
import struct


class CompressionSignature:
    """Assinatura de um algoritmo de compressão."""

    def __init__(self, name: str, patterns: List[bytes], entropy_range: Tuple[float, float]):
        self.name = name
        self.patterns = patterns
        self.min_entropy, self.max_entropy = entropy_range

    def __repr__(self):
        return f"<CompressionSignature {self.name}>"


class CompressedRegion:
    """Representa uma região comprimida detectada."""

    def __init__(self, offset: int, size: int, algorithm: str, confidence: float):
        self.offset = offset
        self.size = size
        self.algorithm = algorithm
        self.confidence = confidence
        self.entropy = 0.0
        self.properties = {}

    def __repr__(self):
        return (f"<CompressedRegion @0x{self.offset:06X} size={self.size} "
                f"algo={self.algorithm} conf={self.confidence:.2f}>")


class CompressionDetector:
    """
    Detector universal de compressão em ROMs.
    Identifica algoritmos sem conhecimento prévio do jogo.
    """

    # Assinaturas conhecidas de algoritmos
    SIGNATURES = [
        # LZSS (comum em jogos SNES/PS1)
        CompressionSignature(
            name="LZSS",
            patterns=[
                b'\x10',  # Tipo 0x10 (Nintendo)
                b'\x11',  # Tipo 0x11 (Nintendo)
            ],
            entropy_range=(6.5, 8.0)
        ),

        # LZ77 (variantes)
        CompressionSignature(
            name="LZ77",
            patterns=[
                b'LZ77',
                b'\x1F\x8B',  # gzip magic
            ],
            entropy_range=(6.0, 8.0)
        ),

        # Huffman (comum em imagens/audio)
        CompressionSignature(
            name="Huffman",
            patterns=[
                b'HUFF',
            ],
            entropy_range=(7.0, 8.0)
        ),

        # RLE (Run-Length Encoding - mais simples)
        CompressionSignature(
            name="RLE",
            patterns=[],  # Sem magic number, detecta por padrão
            entropy_range=(3.0, 6.0)
        ),

        # Yay0 (Nintendo 64)
        CompressionSignature(
            name="Yay0",
            patterns=[b'Yay0'],
            entropy_range=(6.5, 8.0)
        ),

        # Yaz0 (Nintendo GameCube/Wii)
        CompressionSignature(
            name="Yaz0",
            patterns=[b'Yaz0'],
            entropy_range=(6.5, 8.0)
        ),
    ]

    def __init__(self, rom_data: bytes, entropy_map: Optional[List[Dict]] = None):
        """
        Args:
            rom_data: Dados brutos da ROM
            entropy_map: Mapa de entropia do ROMAnalyzer (opcional)
        """
        self.rom_data = rom_data
        self.entropy_map = entropy_map or []
        self.compressed_regions: List[CompressedRegion] = []

    def detect(self, block_size: int = 4096) -> List[CompressedRegion]:
        """
        Executa detecção completa de regiões comprimidas.

        Args:
            block_size: Tamanho de bloco para análise

        Returns:
            Lista de regiões comprimidas detectadas
        """
        print(f"\n🗜️  COMPRESSION DETECTOR - Identifying Compressed Data")
        print(f"{'='*70}")

        # Fase 1: Detecta por assinatura (magic numbers)
        print("[1/3] Scanning for compression signatures...")
        self._scan_signatures()

        # Fase 2: Detecta por entropia alta
        print("[2/3] Analyzing entropy patterns...")
        self._scan_entropy(block_size)

        # Fase 3: Detecta padrões específicos (RLE, etc)
        print("[3/3] Detecting algorithm-specific patterns...")
        self._scan_patterns()

        # Ordena por confiança
        self.compressed_regions.sort(key=lambda r: r.confidence, reverse=True)

        print(f"\n✅ Detected {len(self.compressed_regions)} compressed regions")
        print(f"{'='*70}\n")

        return self.compressed_regions

    def _scan_signatures(self):
        """Procura por magic numbers de algoritmos conhecidos."""
        for signature in self.SIGNATURES:
            if not signature.patterns:
                continue

            for pattern in signature.patterns:
                offset = 0
                while True:
                    # Busca próxima ocorrência
                    offset = self.rom_data.find(pattern, offset)
                    if offset == -1:
                        break

                    # Tenta determinar tamanho da região comprimida
                    size = self._estimate_compressed_size(offset)

                    # Cria região
                    region = CompressedRegion(
                        offset=offset,
                        size=size,
                        algorithm=signature.name,
                        confidence=0.9  # Alta confiança quando há magic number
                    )

                    region.properties['detection_method'] = 'signature'
                    region.properties['signature'] = pattern.hex()

                    self.compressed_regions.append(region)

                    offset += 1

    def _estimate_compressed_size(self, offset: int) -> int:
        """
        Tenta estimar tamanho da região comprimida.

        Heurísticas:
        - Se há header com tamanho, usa ele
        - Senão, procura até encontrar entropia baixa novamente
        """
        # Muitos formatos têm tamanho nos primeiros 4 bytes
        if offset + 8 < len(self.rom_data):
            # Tenta ler como little-endian 32-bit
            potential_size = struct.unpack('<I', self.rom_data[offset+4:offset+8])[0]

            # Verifica se é plausível (< 10MB e > 16 bytes)
            if 16 < potential_size < 10 * 1024 * 1024:
                return potential_size

        # Fallback: busca até entropia cair
        max_scan = min(offset + 65536, len(self.rom_data))  # Max 64KB
        block_size = 1024

        for end in range(offset + block_size, max_scan, block_size):
            block = self.rom_data[end:end + block_size]
            entropy = self._calculate_entropy(block)

            if entropy < 5.0:  # Entropia caiu, provavelmente fim
                return end - offset

        return 4096  # Default

    def _scan_entropy(self, block_size: int):
        """Detecta regiões comprimidas por entropia alta."""
        if not self.entropy_map:
            # Calcula entropia se não foi fornecida
            self._calculate_entropy_map(block_size)

        # Procura por blocos consecutivos com entropia > 7.0
        high_entropy_blocks = []

        for block_info in self.entropy_map:
            if block_info.get('entropy', 0) > 7.0:
                offset = block_info.get('offset_dec', block_info.get('offset', 0))
                if isinstance(offset, str):
                    offset = int(offset, 16)
                high_entropy_blocks.append(offset)

        # Agrupa blocos consecutivos
        if not high_entropy_blocks:
            return

        current_start = high_entropy_blocks[0]
        current_end = current_start + block_size

        for offset in high_entropy_blocks[1:]:
            if offset == current_end:  # Consecutivo
                current_end = offset + block_size
            else:
                # Finaliza região anterior
                size = current_end - current_start
                if size >= block_size * 2:  # Mínimo 2 blocos
                    region = CompressedRegion(
                        offset=current_start,
                        size=size,
                        algorithm="UNKNOWN_COMPRESSED",
                        confidence=0.7  # Média confiança (só por entropia)
                    )
                    region.properties['detection_method'] = 'entropy'

                    # Verifica se não sobrepõe com região já detectada
                    if not self._overlaps_existing(current_start, size):
                        self.compressed_regions.append(region)

                # Inicia nova região
                current_start = offset
                current_end = offset + block_size

        # Adiciona última região
        size = current_end - current_start
        if size >= block_size * 2:
            region = CompressedRegion(
                offset=current_start,
                size=size,
                algorithm="UNKNOWN_COMPRESSED",
                confidence=0.7
            )
            region.properties['detection_method'] = 'entropy'

            if not self._overlaps_existing(current_start, size):
                self.compressed_regions.append(region)

    def _scan_patterns(self):
        """Detecta padrões específicos de algoritmos."""
        # RLE: padrões de repetição (count + byte)
        self._detect_rle()

    def _detect_rle(self):
        """
        Detecta RLE (Run-Length Encoding) por padrões.

        RLE típico: [count][byte] ou [byte][count]
        Exemplo: 0x05 0xFF = cinco bytes 0xFF
        """
        offset = 0
        min_run_length = 4  # Mínimo de repetições para considerar RLE

        while offset < len(self.rom_data) - 16:
            # Tenta decodificar como RLE
            count = self.rom_data[offset]
            if count == 0 or count > 128:  # Valores implausíveis
                offset += 1
                continue

            byte_value = self.rom_data[offset + 1]

            # Verifica se próximos bytes realmente repetem o padrão
            # (seria esperado se fosse RLE real)
            is_rle = True
            rle_size = 2  # count + byte

            # RLE pode ter múltiplos runs consecutivos
            consecutive_runs = 0
            scan_offset = offset

            while scan_offset < len(self.rom_data) - 2 and consecutive_runs < 10:
                run_count = self.rom_data[scan_offset]
                run_byte = self.rom_data[scan_offset + 1]

                # Valida run
                if run_count == 0 or run_count > 128:
                    break

                consecutive_runs += 1
                scan_offset += 2

            # Se encontrou vários runs consecutivos, provavelmente é RLE
            if consecutive_runs >= 3:
                # Estima tamanho total da região RLE
                estimated_size = consecutive_runs * 2

                region = CompressedRegion(
                    offset=offset,
                    size=estimated_size,
                    algorithm="RLE",
                    confidence=0.6  # Média-baixa (pode ser falso positivo)
                )
                region.properties['detection_method'] = 'pattern'
                region.properties['run_count'] = consecutive_runs

                if not self._overlaps_existing(offset, estimated_size):
                    self.compressed_regions.append(region)

                offset += estimated_size
            else:
                offset += 1

    def _calculate_entropy_map(self, block_size: int):
        """Calcula mapa de entropia se não foi fornecido."""
        for offset in range(0, len(self.rom_data), block_size):
            block = self.rom_data[offset:offset + block_size]
            if len(block) < block_size // 2:
                continue

            entropy = self._calculate_entropy(block)

            self.entropy_map.append({
                'offset': hex(offset),
                'offset_dec': offset,
                'entropy': entropy
            })

    def _calculate_entropy(self, data: bytes) -> float:
        """Calcula entropia de Shannon (0-8 bits)."""
        if not data:
            return 0.0

        counter = Counter(data)
        length = len(data)

        entropy = 0.0
        for count in counter.values():
            probability = count / length
            if probability > 0:
                import math
                entropy -= probability * math.log2(probability)

        return entropy

    def _overlaps_existing(self, offset: int, size: int) -> bool:
        """Verifica se região sobrepõe com alguma já detectada."""
        for existing in self.compressed_regions:
            # Verifica overlap
            if (offset < existing.offset + existing.size and
                offset + size > existing.offset):
                return True
        return False

    def export_report(self, output_path: str):
        """Exporta relatório de compressão para JSON."""
        import json
        from datetime import datetime

        report = {
            'scan_timestamp': datetime.now().isoformat(),
            'total_regions': len(self.compressed_regions),
            'algorithms_detected': list(set(r.algorithm for r in self.compressed_regions)),
            'compressed_regions': []
        }

        for region in self.compressed_regions:
            report['compressed_regions'].append({
                'offset': hex(region.offset),
                'offset_dec': region.offset,
                'size': region.size,
                'algorithm': region.algorithm,
                'confidence': round(region.confidence, 3),
                'entropy': round(region.entropy, 2),
                'properties': region.properties
            })

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)

        print(f"✅ Exported compression report to: {output_path}")

    def print_summary(self):
        """Exibe resumo das regiões comprimidas."""
        print(f"\n🗜️  COMPRESSION SUMMARY")
        print(f"{'='*70}")

        if not self.compressed_regions:
            print("No compressed regions detected.")
            print(f"{'='*70}\n")
            return

        # Agrupa por algoritmo
        by_algorithm = {}
        for region in self.compressed_regions:
            if region.algorithm not in by_algorithm:
                by_algorithm[region.algorithm] = []
            by_algorithm[region.algorithm].append(region)

        for algo, regions in by_algorithm.items():
            total_size = sum(r.size for r in regions)
            avg_conf = sum(r.confidence for r in regions) / len(regions)

            print(f"\n{algo}:")
            print(f"  Regions: {len(regions)}")
            print(f"  Total size: {total_size:,} bytes ({total_size/1024:.1f} KB)")
            print(f"  Avg confidence: {avg_conf:.3f}")

            # Mostra top 3 regiões
            print(f"  Top regions:")
            for i, region in enumerate(sorted(regions, key=lambda r: r.size, reverse=True)[:3], 1):
                print(f"    {i}. 0x{region.offset:06X}: {region.size:,} bytes (conf={region.confidence:.2f})")

        print(f"\n{'='*70}\n")


def detect_compression_in_rom(rom_path: str, entropy_map: Optional[List[Dict]] = None) -> CompressionDetector:
    """
    Função de conveniência para detecção direta.

    Args:
        rom_path: Caminho da ROM
        entropy_map: Mapa de entropia do ROMAnalyzer (opcional)

    Returns:
        CompressionDetector com regiões identificadas
    """
    with open(rom_path, 'rb') as f:
        data = f.read()
        # Remove SMC header se presente
        if len(data) % 1024 == 512:
            data = data[512:]

    detector = CompressionDetector(data, entropy_map)
    detector.detect(block_size=4096)
    detector.print_summary()

    # Exporta
    import os
    output_path = os.path.splitext(rom_path)[0] + '_compression_report.json'
    detector.export_report(output_path)

    return detector


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python compression_detector.py <rom_file>")
        sys.exit(1)

    rom_file = sys.argv[1]
    detect_compression_in_rom(rom_file)
