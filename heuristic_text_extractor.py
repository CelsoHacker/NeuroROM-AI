#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EXTRATOR HEURÍSTICO DE TEXTO - ROM TRANSLATION FRAMEWORK
=========================================================

Sistema inteligente que:
1. Analisa frequência de bytes para descobrir charset automaticamente
2. Usa Tile Sniffer para distinguir texto de gráficos/mapas
3. Gera Tabela Virtual sem necessidade de TBL manual
"""

import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import Counter
import json


class FrequencyAnalyzer:
    """Análise de frequência para descobrir charset automaticamente."""

    # Frequências esperadas de letras em inglês (%)
    # Fonte: análise de corpora
    ENGLISH_FREQ = {
        'E': 12.70, 'T': 9.06, 'A': 8.17, 'O': 7.51, 'I': 6.97,
        'N': 6.75, 'S': 6.33, 'H': 6.09, 'R': 5.99, 'D': 4.25,
        'L': 4.03, 'C': 2.78, 'U': 2.76, 'M': 2.41, 'W': 2.36,
        'F': 2.23, 'G': 2.02, 'Y': 1.97, 'P': 1.93, 'B': 1.29,
        'V': 0.98, 'K': 0.77, 'J': 0.15, 'X': 0.15, 'Q': 0.10, 'Z': 0.07
    }

    # Frequências em português (%)
    PORTUGUESE_FREQ = {
        'A': 14.63, 'E': 12.57, 'O': 10.73, 'S': 7.81, 'R': 6.53,
        'I': 6.18, 'N': 5.05, 'D': 4.99, 'M': 4.74, 'U': 4.63,
        'T': 4.34, 'C': 3.88, 'L': 2.78, 'P': 2.52, 'V': 1.67,
        'G': 1.30, 'H': 1.28, 'Q': 1.20, 'B': 1.04, 'F': 1.02,
        'Z': 0.47, 'J': 0.40, 'X': 0.21, 'K': 0.02, 'W': 0.01, 'Y': 0.01
    }

    def __init__(self, language='english'):
        """Inicializa com idioma de referência."""
        self.language = language
        self.reference_freq = (self.ENGLISH_FREQ if language == 'english'
                              else self.PORTUGUESE_FREQ)

    def analyze_byte_frequency(self, data: bytes, offset: int = 0,
                               length: int = None) -> Dict[int, float]:
        """
        Analisa frequência de bytes em região da ROM.

        Returns:
            {byte_value: frequency_percentage}
        """
        if length is None:
            length = len(data) - offset

        region = data[offset:offset + length]
        counter = Counter(region)
        total = len(region)

        # Converte para percentuais
        freq_dict = {byte: (count / total * 100)
                     for byte, count in counter.items()}

        return freq_dict

    def map_bytes_to_letters(self, byte_freq: Dict[int, float]) -> Dict[int, str]:
        """
        Mapeia bytes para letras baseado em frequência.

        Algoritmo:
        1. Ordena bytes por frequência (mais frequente primeiro)
        2. Ordena letras por frequência esperada
        3. Mapeia byte[i] → letra[i]
        """
        # Ordena bytes por frequência descendente
        sorted_bytes = sorted(byte_freq.items(), key=lambda x: x[1], reverse=True)

        # Ordena letras de referência por frequência
        sorted_letters = sorted(self.reference_freq.items(),
                               key=lambda x: x[1], reverse=True)

        # Cria mapeamento
        charset = {}
        for i, (byte_val, _) in enumerate(sorted_bytes[:26]):  # Top 26 bytes → A-Z
            if i < len(sorted_letters):
                charset[byte_val] = sorted_letters[i][0]

        return charset

    def calculate_chi_square(self, observed_freq: Dict[int, float],
                            charset: Dict[int, str]) -> float:
        """
        Calcula chi-quadrado para validar qualidade do mapeamento.

        Menor chi² = melhor ajuste
        """
        chi_square = 0.0

        for byte_val, obs_freq in observed_freq.items():
            if byte_val in charset:
                letter = charset[byte_val]
                expected_freq = self.reference_freq.get(letter, 0.1)

                # Chi² = Σ((observado - esperado)² / esperado)
                chi_square += ((obs_freq - expected_freq) ** 2) / expected_freq

        return chi_square


class TileSniffer:
    """Detector de regiões: texto vs gráficos vs mapas."""

    @staticmethod
    def calculate_entropy(data: bytes) -> float:
        """
        Calcula entropia de Shannon.

        Texto: entropia moderada (4-6 bits)
        Gráficos: entropia alta (7-8 bits)
        Código/mapas: entropia baixa (2-4 bits)
        """
        if len(data) == 0:
            return 0.0

        counter = Counter(data)
        total = len(data)

        entropy = 0.0
        for count in counter.values():
            p = count / total
            if p > 0:
                entropy -= p * np.log2(p)

        return entropy

    @staticmethod
    def detect_repetitive_patterns(data: bytes, pattern_size: int = 8) -> float:
        """
        Detecta padrões repetitivos (tiles gráficos).

        Returns:
            Razão de repetição (0.0 = sem repetição, 1.0 = muito repetitivo)
        """
        if len(data) < pattern_size * 2:
            return 0.0

        patterns = {}
        for i in range(len(data) - pattern_size):
            pattern = data[i:i + pattern_size]
            patterns[pattern] = patterns.get(pattern, 0) + 1

        # Quantos padrões aparecem 2+ vezes?
        repeated = sum(1 for count in patterns.values() if count >= 2)
        total_patterns = len(patterns)

        return repeated / total_patterns if total_patterns > 0 else 0.0

    @staticmethod
    def analyze_byte_distribution(data: bytes) -> Dict[str, float]:
        """Analisa distribuição de bytes (printable vs control vs high)."""
        if len(data) == 0:
            return {'printable': 0, 'control': 0, 'high': 0}

        printable = sum(1 for b in data if 0x20 <= b <= 0x7E)  # ASCII printable
        control = sum(1 for b in data if b < 0x20)  # Control chars
        high = sum(1 for b in data if b >= 0x7F)  # High bytes

        total = len(data)
        return {
            'printable': printable / total,
            'control': control / total,
            'high': high / total
        }

    @classmethod
    def classify_region(cls, data: bytes, offset: int, size: int = 512) -> str:
        """
        Classifica região da ROM.

        Returns:
            'text', 'graphics', 'map', 'code', ou 'unknown'
        """
        region = data[offset:offset + size]

        # Calcula métricas
        entropy = cls.calculate_entropy(region)
        repetition = cls.detect_repetitive_patterns(region)
        distribution = cls.analyze_byte_distribution(region)

        # Heurísticas de classificação
        # TEXTO: entropia moderada, poucos bytes de controle, não repetitivo
        if (4.0 <= entropy <= 6.0 and
            distribution['control'] < 0.3 and
            repetition < 0.5):
            return 'text'

        # GRÁFICOS: alta repetição de padrões, entropia alta
        elif repetition > 0.6 or entropy > 7.0:
            return 'graphics'

        # MAPAS: entropia baixa, valores pequenos
        elif entropy < 3.0 and distribution['high'] < 0.3:
            return 'map'

        # CÓDIGO: alta entropia, muitos bytes altos
        elif entropy > 6.5 and distribution['high'] > 0.5:
            return 'code'

        else:
            return 'unknown'


class HeuristicTextExtractor:
    """Extrator inteligente que combina análise de frequência e tile sniffer."""

    def __init__(self, rom_path: str, language='english'):
        self.rom_path = Path(rom_path)
        self.rom_data = None
        self.language = language

        self.frequency_analyzer = FrequencyAnalyzer(language)
        self.tile_sniffer = TileSniffer()

        self.virtual_charset = {}
        self.text_regions = []
        self.extracted_texts = []

    def load_rom(self):
        """Carrega ROM."""
        print(f"📂 Carregando ROM: {self.rom_path.name}")
        with open(self.rom_path, 'rb') as f:
            self.rom_data = f.read()
        print(f"✅ {len(self.rom_data):,} bytes carregados")

    def scan_regions(self, chunk_size: int = 512):
        """Varre ROM identificando regiões de texto."""
        print("\n🔍 Tile Sniffer: Detectando regiões...")

        region_stats = {
            'text': 0,
            'graphics': 0,
            'map': 0,
            'code': 0,
            'unknown': 0
        }

        for offset in range(0, len(self.rom_data), chunk_size):
            region_type = self.tile_sniffer.classify_region(
                self.rom_data, offset, chunk_size
            )

            region_stats[region_type] += 1

            if region_type == 'text':
                self.text_regions.append((offset, chunk_size))

        # Mostra estatísticas
        total_regions = sum(region_stats.values())
        print(f"\n📊 Análise de {total_regions:,} regiões:")
        for region_type, count in region_stats.items():
            pct = (count / total_regions * 100) if total_regions > 0 else 0
            icon = {'text': '📝', 'graphics': '🎨', 'map': '🗺️',
                   'code': '💻', 'unknown': '❓'}[region_type]
            print(f"  {icon} {region_type.capitalize()}: {count:,} ({pct:.1f}%)")

        print(f"\n✅ {len(self.text_regions):,} regiões de texto identificadas")

    def build_virtual_charset(self):
        """Constrói tabela virtual baseada em análise de frequência."""
        print("\n🧮 Analisando frequência de bytes nas regiões de texto...")

        # Concatena todas as regiões de texto
        text_data = b''
        for offset, size in self.text_regions:
            text_data += self.rom_data[offset:offset + size]

        if len(text_data) == 0:
            print("❌ Nenhum dado de texto encontrado")
            return

        # Analisa frequência
        byte_freq = self.frequency_analyzer.analyze_byte_frequency(text_data)

        # Mapeia bytes → letras
        self.virtual_charset = self.frequency_analyzer.map_bytes_to_letters(byte_freq)

        # Adiciona caracteres comuns
        # Tenta identificar espaço (byte mais frequente após letras)
        remaining_bytes = sorted(
            [(b, f) for b, f in byte_freq.items() if b not in self.virtual_charset],
            key=lambda x: x[1], reverse=True
        )

        if remaining_bytes:
            self.virtual_charset[remaining_bytes[0][0]] = ' '  # Espaço

        # Calcula chi-quadrado
        chi_square = self.frequency_analyzer.calculate_chi_square(
            byte_freq, self.virtual_charset
        )

        print(f"✅ Tabela virtual construída: {len(self.virtual_charset)} mapeamentos")
        print(f"   Chi-quadrado: {chi_square:.2f} (menor = melhor)")

    def extract_text_from_region(self, offset: int, size: int) -> List[str]:
        """Extrai texto de região usando charset virtual."""
        texts = []
        current_text = []
        pos = offset

        while pos < offset + size and pos < len(self.rom_data):
            byte = self.rom_data[pos]

            if byte in self.virtual_charset:
                char = self.virtual_charset[byte]
                current_text.append(char)
            else:
                # Byte desconhecido = fim de string
                if len(current_text) >= 4:  # Mínimo 4 caracteres
                    text = ''.join(current_text).strip()
                    if self.is_valid_text(text):
                        texts.append(text)
                current_text = []

            pos += 1

        # Finaliza texto pendente
        if len(current_text) >= 4:
            text = ''.join(current_text).strip()
            if self.is_valid_text(text):
                texts.append(text)

        return texts

    def is_valid_text(self, text: str) -> bool:
        """Valida se texto parece real."""
        if len(text) < 4:
            return False

        # Pelo menos 50% alfabético
        alpha_count = sum(1 for c in text if c.isalpha())
        if alpha_count < len(text) * 0.5:
            return False

        # Pelo menos 1 vogal
        vowels = set('AEIOUaeiou')
        if not any(c in vowels for c in text):
            return False

        # Não só repetições
        if len(set(text.replace(' ', ''))) < 3:
            return False

        return True

    def extract_all(self):
        """Pipeline completo de extração."""
        print("=" * 80)
        print("🤖 EXTRATOR HEURÍSTICO INTELIGENTE")
        print("=" * 80)

        # 1. Carrega ROM
        self.load_rom()

        # 2. Detecta regiões
        self.scan_regions()

        if not self.text_regions:
            print("\n❌ Nenhuma região de texto detectada!")
            return []

        # 3. Constrói charset virtual
        self.build_virtual_charset()

        if not self.virtual_charset:
            print("\n❌ Falha ao construir charset virtual!")
            return []

        # 4. Extrai textos das regiões identificadas
        print("\n📝 Extraindo textos das regiões identificadas...")

        all_texts = set()
        for offset, size in self.text_regions:
            texts = self.extract_text_from_region(offset, size)
            all_texts.update(texts)

        self.extracted_texts = sorted(list(all_texts),
                                     key=lambda x: (-len(x), x.upper()))

        print(f"✅ {len(self.extracted_texts):,} textos únicos extraídos")

        return self.extracted_texts

    def save_results(self, output_dir: str = None):
        """Salva resultados."""
        if output_dir is None:
            output_dir = self.rom_path.parent

        output_dir = Path(output_dir)

        # Salva textos extraídos
        texts_file = output_dir / f"{self.rom_path.stem}_HEURISTIC.txt"
        with open(texts_file, 'w', encoding='utf-8') as f:
            for text in self.extracted_texts:
                f.write(f"{text}\n")

        print(f"\n💾 Textos salvos em: {texts_file.name}")

        # Salva charset virtual
        charset_file = output_dir / f"{self.rom_path.stem}_virtual_charset.json"
        charset_serializable = {f"0x{k:02X}": v for k, v in self.virtual_charset.items()}

        with open(charset_file, 'w', encoding='utf-8') as f:
            json.dump(charset_serializable, f, indent=2, ensure_ascii=False)

        print(f"💾 Charset virtual salvo em: {charset_file.name}")

    def print_preview(self, limit: int = 50):
        """Mostra preview dos textos."""
        print("\n" + "=" * 80)
        print(f"📝 PREVIEW DOS PRIMEIROS {limit} TEXTOS:")
        print("=" * 80)

        for i, text in enumerate(self.extracted_texts[:limit], 1):
            print(f"{i:3d}. {text}")

        if len(self.extracted_texts) > limit:
            print(f"\n... e mais {len(self.extracted_texts) - limit} textos")


def main():
    """Função principal."""

    # Caminho da ROM
    rom_path = r"C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework\ROMs\Super Nintedo\Super Mario World.smc"

    if not Path(rom_path).exists():
        print(f"❌ ROM não encontrada: {rom_path}")
        return

    # Cria extrator heurístico
    extractor = HeuristicTextExtractor(rom_path, language='english')

    # Executa extração
    texts = extractor.extract_all()

    # Preview
    extractor.print_preview(limit=100)

    # Salva resultados
    extractor.save_results()

    # Estatísticas finais
    print("\n" + "=" * 80)
    print("✅ EXTRAÇÃO CONCLUÍDA")
    print("=" * 80)
    print(f"📊 Total de textos: {len(texts):,}")
    print(f"🧮 Charset virtual: {len(extractor.virtual_charset)} mapeamentos")
    print(f"📝 Regiões de texto: {len(extractor.text_regions):,}")
    print("=" * 80)


if __name__ == '__main__':
    main()
