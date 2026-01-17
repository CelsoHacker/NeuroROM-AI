# -*- coding: utf-8 -*-
"""
================================================================================
ROM ANALYZER - Detecção Automática de Estrutura de ROM
================================================================================
Análise binária universal para identificação de:
- Tipo de console (SNES, PS1, GBA, etc)
- Mapeamento de memória (LoROM/HiROM)
- Regiões de código, gráficos, texto e dados comprimidos
- Entropia e padrões estatísticos

NÃO usa profiles hardcoded - análise puramente heurística
================================================================================
"""

import struct
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import Counter
import math


class ROMAnalyzer:
    """Analisador universal de ROMs baseado em heurísticas."""

    def __init__(self, rom_path: str):
        self.rom_path = Path(rom_path)
        self.rom_data = self._load_rom()
        self.analysis = {}

    def _load_rom(self) -> bytes:
        """Carrega ROM e remove headers conhecidos."""
        with open(self.rom_path, 'rb') as f:
            data = f.read()

        # Detecta e remove header SMC (512 bytes) se presente
        if len(data) % 1024 == 512:
            print(f"[ROM Analyzer] SMC header detected (512 bytes), stripping...")
            return data[512:]

        return data

    def analyze(self) -> Dict:
        """Executa análise completa da ROM."""
        print(f"\n{'='*70}")
        print(f"ROM ANALYZER - Automatic Structure Detection")
        print(f"{'='*70}")

        self.analysis = {
            'file_info': self._analyze_file_info(),
            'platform': self._detect_platform(),
            'memory_map': self._detect_memory_mapping(),
            'entropy_map': self._analyze_entropy(),
            'regions': self._identify_regions(),
            'statistics': self._calculate_statistics()
        }

        return self.analysis

    def _analyze_file_info(self) -> Dict:
        """Informações básicas do arquivo."""
        return {
            'filename': self.rom_path.name,
            'size_bytes': len(self.rom_data),
            'size_kb': len(self.rom_data) / 1024,
            'size_mb': len(self.rom_data) / (1024 * 1024),
            'md5': hashlib.md5(self.rom_data).hexdigest(),
            'sha1': hashlib.sha1(self.rom_data).hexdigest()
        }

    def _detect_platform(self) -> Dict:
        """Detecta plataforma baseado em assinaturas e estrutura."""
        size = len(self.rom_data)

        # SNES: 512KB - 6MB, potências de 2 comuns
        if 512 * 1024 <= size <= 6 * 1024 * 1024:
            # Verifica header interno SNES (LoROM: 0x7FC0, HiROM: 0xFFC0)
            if self._check_snes_header(0x7FC0):
                return {
                    'platform': 'SNES',
                    'confidence': 0.95,
                    'header_type': 'LoROM',
                    'header_offset': 0x7FC0
                }
            elif self._check_snes_header(0xFFC0):
                return {
                    'platform': 'SNES',
                    'confidence': 0.95,
                    'header_type': 'HiROM',
                    'header_offset': 0xFFC0
                }

        # PlayStation 1: geralmente ISO (2048 bytes/sector)
        if size > 10 * 1024 * 1024 and size % 2048 == 0:
            # Procura por assinatura "CD001" (ISO 9660)
            if b'CD001' in self.rom_data[:40000]:
                return {
                    'platform': 'PlayStation 1',
                    'confidence': 0.90,
                    'format': 'ISO 9660'
                }

        # Game Boy Advance: 8MB-32MB, logo Nintendo específica
        if 8 * 1024 * 1024 <= size <= 32 * 1024 * 1024:
            # Logo Nintendo em 0x04
            if self.rom_data[0x04:0x08] == b'\x24\xFF\xAE\x51':
                return {
                    'platform': 'Game Boy Advance',
                    'confidence': 0.98
                }

        # Nintendo 64: 8MB-64MB, big endian
        if 8 * 1024 * 1024 <= size <= 64 * 1024 * 1024:
            # Magic number: 0x80371240 (big endian)
            magic = struct.unpack('>I', self.rom_data[:4])[0]
            if magic == 0x80371240:
                return {
                    'platform': 'Nintendo 64',
                    'confidence': 0.98,
                    'endianness': 'big'
                }

        return {
            'platform': 'Unknown',
            'confidence': 0.0,
            'note': 'Unable to identify platform automatically'
        }

    def _check_snes_header(self, offset: int) -> bool:
        """Verifica se existe header SNES válido no offset."""
        if offset + 64 > len(self.rom_data):
            return False

        # Checksum deve ser complemento da soma inversa
        checksum_offset = offset + 0x1C
        checksum = struct.unpack('<H', self.rom_data[checksum_offset:checksum_offset+2])[0]
        checksum_complement = struct.unpack('<H', self.rom_data[checksum_offset+2:checksum_offset+4])[0]

        # Verifica se são complementos
        if (checksum ^ checksum_complement) != 0xFFFF:
            return False

        # ROM type byte deve estar em range válido
        rom_type = self.rom_data[offset + 0x15]
        if rom_type not in [0x00, 0x01, 0x02, 0x13, 0x20, 0x21, 0x22, 0x23, 0x30, 0x31]:
            return False

        return True

    def _detect_memory_mapping(self) -> Dict:
        """Detecta mapeamento de memória (para SNES principalmente)."""
        platform = self.analysis.get('platform', {}).get('platform', 'Unknown')

        if platform != 'SNES':
            return {'type': 'N/A', 'reason': 'Not SNES platform'}

        header_type = self.analysis['platform'].get('header_type', 'Unknown')

        if header_type == 'LoROM':
            return {
                'type': 'LoROM',
                'bank_size': 0x8000,
                'text_search_start': 0x8000,
                'description': 'Banks $00-$7F, ROM at $8000-$FFFF per bank'
            }
        elif header_type == 'HiROM':
            return {
                'type': 'HiROM',
                'bank_size': 0x10000,
                'text_search_start': 0x0000,
                'description': 'Banks $C0-$FF, ROM at $0000-$FFFF per bank'
            }

        return {'type': 'Unknown'}

    def _analyze_entropy(self, block_size: int = 4096) -> List[Dict]:
        """Calcula entropia de Shannon para cada bloco da ROM."""
        entropy_map = []

        for offset in range(0, len(self.rom_data), block_size):
            block = self.rom_data[offset:offset + block_size]

            if len(block) < block_size // 2:  # Ignora blocos pequenos no final
                continue

            entropy = self._calculate_entropy(block)

            # Classificação heurística
            if entropy < 2.0:
                classification = 'EMPTY/PADDING'
            elif entropy < 4.0:
                classification = 'CODE/STRUCTURED'
            elif entropy < 6.0:
                classification = 'TEXT/TABLES'
            elif entropy < 7.5:
                classification = 'GRAPHICS/MIXED'
            else:
                classification = 'COMPRESSED/ENCRYPTED'

            entropy_map.append({
                'offset': hex(offset),
                'offset_dec': offset,
                'entropy': round(entropy, 2),
                'classification': classification
            })

        return entropy_map

    def _calculate_entropy(self, data: bytes) -> float:
        """Calcula entropia de Shannon (0-8 bits)."""
        if not data:
            return 0.0

        # Conta frequência de cada byte
        counter = Counter(data)
        length = len(data)

        # Calcula entropia
        entropy = 0.0
        for count in counter.values():
            probability = count / length
            if probability > 0:
                entropy -= probability * math.log2(probability)

        return entropy

    def _identify_regions(self) -> Dict:
        """Identifica regiões prováveis baseado em entropia e padrões."""
        entropy_map = self.analysis.get('entropy_map', [])

        # Agrupa blocos consecutivos com mesma classificação
        regions = {
            'code': [],
            'text_candidates': [],
            'graphics': [],
            'compressed': [],
            'empty': []
        }

        current_region = None
        region_start = 0

        for block in entropy_map:
            classification = block['classification']
            offset = block['offset_dec']

            # Mapeia classificação para tipo de região
            if 'CODE' in classification:
                region_type = 'code'
            elif 'TEXT' in classification:
                region_type = 'text_candidates'
            elif 'GRAPHICS' in classification:
                region_type = 'graphics'
            elif 'COMPRESSED' in classification:
                region_type = 'compressed'
            else:
                region_type = 'empty'

            # Se mudou de tipo, salva região anterior
            if current_region != region_type:
                if current_region:
                    regions[current_region].append({
                        'start': hex(region_start),
                        'end': hex(offset),
                        'size': offset - region_start
                    })

                current_region = region_type
                region_start = offset

        # Adiciona última região
        if current_region:
            regions[current_region].append({
                'start': hex(region_start),
                'end': hex(len(self.rom_data)),
                'size': len(self.rom_data) - region_start
            })

        return regions

    def _calculate_statistics(self) -> Dict:
        """Estatísticas gerais da ROM."""
        # Conta bytes mais comuns
        byte_freq = Counter(self.rom_data)
        most_common = byte_freq.most_common(10)

        # Detecta padrões de padding
        padding_bytes = {0x00, 0xFF}
        padding_count = sum(byte_freq[b] for b in padding_bytes)
        padding_ratio = padding_count / len(self.rom_data)

        return {
            'most_common_bytes': [
                {'byte': f'0x{b:02X}', 'count': c, 'percentage': round(c/len(self.rom_data)*100, 2)}
                for b, c in most_common
            ],
            'padding_ratio': round(padding_ratio * 100, 2),
            'unique_bytes': len(byte_freq),
            'avg_entropy': round(sum(b['entropy'] for b in self.analysis.get('entropy_map', [])) /
                               max(len(self.analysis.get('entropy_map', [])), 1), 2)
        }

    def export_report(self, output_path: str):
        """Exporta relatório de análise em JSON."""
        import json
        from datetime import datetime

        report = {
            'analysis_timestamp': datetime.now().isoformat(),
            'rom_info': self.analysis.get('file_info', {}),
            'platform_detection': self.analysis.get('platform', {}),
            'memory_mapping': self.analysis.get('memory_map', {}),
            'identified_regions': self.analysis.get('regions', {}),
            'statistics': self.analysis.get('statistics', {}),
            'entropy_analysis': self.analysis.get('entropy_map', [])
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Analysis report saved to: {output_path}")

    def print_summary(self):
        """Exibe resumo da análise no console."""
        if not self.analysis:
            print("❌ No analysis data available. Run analyze() first.")
            return

        info = self.analysis.get('file_info', {})
        platform = self.analysis.get('platform', {})
        regions = self.analysis.get('regions', {})
        stats = self.analysis.get('statistics', {})

        print(f"\n📊 ANALYSIS SUMMARY")
        print(f"{'='*70}")
        print(f"File: {info.get('filename', 'Unknown')}")
        print(f"Size: {info.get('size_kb', 0):.1f} KB ({info.get('size_bytes', 0):,} bytes)")
        print(f"MD5:  {info.get('md5', 'N/A')}")
        print(f"\nPlatform: {platform.get('platform', 'Unknown')} "
              f"(confidence: {platform.get('confidence', 0)*100:.0f}%)")

        if platform.get('platform') == 'SNES':
            print(f"Mapping:  {platform.get('header_type', 'Unknown')}")

        print(f"\n📍 IDENTIFIED REGIONS:")
        for region_type, region_list in regions.items():
            if region_list:
                total_size = sum(r['size'] for r in region_list)
                print(f"  {region_type.upper():20s}: {len(region_list):3d} regions, "
                      f"{total_size:7,} bytes")

        print(f"\n📈 STATISTICS:")
        print(f"  Unique bytes: {stats.get('unique_bytes', 0)}")
        print(f"  Padding ratio: {stats.get('padding_ratio', 0):.1f}%")
        print(f"  Avg entropy: {stats.get('avg_entropy', 0):.2f}/8.0")
        print(f"{'='*70}\n")


# Função de conveniência para uso direto
def analyze_rom(rom_path: str, export_json: bool = True) -> Dict:
    """
    Analisa ROM e retorna estrutura de dados completa.

    Args:
        rom_path: Caminho para arquivo ROM
        export_json: Se True, salva relatório JSON automaticamente

    Returns:
        Dicionário com análise completa
    """
    analyzer = ROMAnalyzer(rom_path)
    analysis = analyzer.analyze()
    analyzer.print_summary()

    if export_json:
        output_path = str(Path(rom_path).with_suffix('')) + '_analysis.json'
        analyzer.export_report(output_path)

    return analysis


if __name__ == "__main__":
    # Teste standalone
    import sys

    if len(sys.argv) < 2:
        print("Usage: python rom_analyzer.py <rom_file>")
        sys.exit(1)

    rom_file = sys.argv[1]
    analyze_rom(rom_file, export_json=True)
