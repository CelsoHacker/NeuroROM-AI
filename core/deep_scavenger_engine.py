# -*- coding: utf-8 -*-
"""
DEEP SCAVENGER ENGINE - Varredura de Lacunas V7.0
==================================================
Encontra texto escondido em áreas não detectadas pela extração principal.

Técnica:
1. Identifica "buracos" entre strings extraídas (gaps)
2. Calcula entropia desses gaps (3.0-5.5 = assinatura de texto)
3. Extrai forçadamente com filtros relaxados
4. Marca strings recuperadas com [RECOVERED]

Uso: Execute SEMPRE após extração principal (ASCII ou TBL).

Autor: Sistema V7.0 ULTIMATE
Data: 2026-01
"""

import math
from pathlib import Path
from typing import List, Tuple, Dict
from collections import Counter


class DeepScavengerEngine:
    """
    Motor de recuperação de texto em áreas não detectadas.
    """

    def __init__(self, rom_data: bytes, char_table: Dict[int, str]):
        self.rom_data = rom_data
        self.char_table = char_table
        self.min_gap_size = 50
        self.min_string_length = 3  # Relaxado (normal = 4)
        self.max_string_length = 200

    def calculate_entropy(self, data: bytes) -> float:
        """
        Calcula entropia de Shannon de um bloco de bytes.

        Faixas:
        - 0.0 - 2.0: Muito repetitivo (zeros, padding)
        - 3.0 - 5.5: ASSINATURA DE TEXTO (boa diversidade)
        - 6.0 - 8.0: Alta entropia (comprimido ou binário)
        """
        if not data or len(data) < 10:
            return 0.0

        byte_counts = Counter(data)
        entropy = 0.0
        length = len(data)

        for count in byte_counts.values():
            probability = count / length
            if probability > 0:
                entropy -= probability * math.log2(probability)

        return entropy

    def find_gaps(self, extracted_offsets: List[int]) -> List[Tuple[int, int, int]]:
        """
        Identifica lacunas entre strings extraídas.

        Args:
            extracted_offsets: Lista de offsets já extraídos (ordenada)

        Returns:
            Lista de (offset_inicio, offset_fim, tamanho)
        """
        if not extracted_offsets:
            return [(0, len(self.rom_data), len(self.rom_data))]

        gaps = []
        sorted_offsets = sorted(set(extracted_offsets))

        # Gap antes da primeira string
        if sorted_offsets[0] > self.min_gap_size:
            gaps.append((0, sorted_offsets[0], sorted_offsets[0]))

        # Gaps entre strings
        for i in range(len(sorted_offsets) - 1):
            gap_start = sorted_offsets[i] + 1
            gap_end = sorted_offsets[i + 1]
            gap_size = gap_end - gap_start

            if gap_size >= self.min_gap_size:
                gaps.append((gap_start, gap_end, gap_size))

        # Gap após última string
        last_offset = sorted_offsets[-1]
        if len(self.rom_data) - last_offset > self.min_gap_size:
            gaps.append((last_offset + 1, len(self.rom_data), len(self.rom_data) - last_offset - 1))

        return gaps

    def analyze_gap(self, gap_start: int, gap_end: int) -> Tuple[bool, float]:
        """
        Analisa gap para determinar se contém texto.

        Returns:
            (is_text_candidate, entropy)
        """
        gap_data = self.rom_data[gap_start:gap_end]
        entropy = self.calculate_entropy(gap_data)

        # Assinatura de texto: entropia entre 3.0 e 5.5
        is_candidate = 3.0 <= entropy <= 5.5

        return is_candidate, entropy

    def extract_from_gap_relaxed(self, gap_start: int, gap_end: int) -> List[Tuple[int, str]]:
        """
        Extrai strings de um gap usando filtros RELAXADOS.

        Diferenças vs extração normal:
        - Aceita strings de 3+ caracteres (vs 4+)
        - Tolera 1 bad byte no meio da string
        - Não quebra em bytes desconhecidos imediatamente
        """
        strings_found = []
        offset = gap_start

        while offset < gap_end - self.min_string_length:
            byte = self.rom_data[offset]

            # Verifica se byte pode iniciar string
            if byte in self.char_table and byte not in [0x00, 0xFF, 0xFE]:
                text = []
                bad_bytes = 0
                length = 0

                for i in range(self.max_string_length):
                    if offset + i >= gap_end:
                        break

                    current_byte = self.rom_data[offset + i]

                    # Terminadores
                    if current_byte in [0x00, 0xFF]:
                        length = i + 1
                        break

                    # Byte mapeado
                    if current_byte in self.char_table:
                        char = self.char_table[current_byte]
                        text.append(char)
                    else:
                        # RELAXAMENTO: Tolera 1 bad byte
                        bad_bytes += 1
                        if bad_bytes > 1:
                            break
                        else:
                            text.append('?')  # Placeholder

                # Valida tamanho mínimo RELAXADO (3+)
                if len(text) >= self.min_string_length:
                    final_text = ''.join(text).strip()

                    # Remove strings só com '?'
                    if final_text.replace('?', ''):
                        if len(final_text) >= self.min_string_length:
                            strings_found.append((offset, final_text))
                            offset += length if length > 0 else len(text)
                            continue

            offset += 1

        return strings_found

    def scavenge(self, extracted_offsets: List[int]) -> Tuple[List[Tuple[int, str]], Dict]:
        """
        Executa varredura completa de lacunas.

        Args:
            extracted_offsets: Offsets já extraídos pela extração principal

        Returns:
            (recovered_strings, statistics)
        """
        print("\n" + "="*80)
        print("🔍 DEEP SCAVENGER ENGINE - Varredura de Lacunas")
        print("="*80)

        # ETAPA 1: Encontra gaps
        print("\n📊 Analisando lacunas...")
        gaps = self.find_gaps(extracted_offsets)
        print(f"   ✅ {len(gaps)} lacunas identificadas")

        # ETAPA 2: Analisa cada gap
        print("\n🔬 Verificando assinatura de texto...")
        text_candidates = []

        for gap_start, gap_end, gap_size in gaps:
            is_candidate, entropy = self.analyze_gap(gap_start, gap_end)

            if is_candidate:
                text_candidates.append((gap_start, gap_end, gap_size, entropy))
                print(f"   ✅ Gap [0x{gap_start:X} - 0x{gap_end:X}] "
                      f"({gap_size:,} bytes) - Entropia: {entropy:.2f}")

        print(f"\n   📍 {len(text_candidates)} áreas de interesse detectadas")

        # ETAPA 3: Extração forçada
        print("\n🔥 Iniciando extração forçada...")
        recovered_strings = []

        for gap_start, gap_end, gap_size, entropy in text_candidates:
            print(f"\n   🎣 Pescando em 0x{gap_start:X}...")

            gap_strings = self.extract_from_gap_relaxed(gap_start, gap_end)

            if gap_strings:
                print(f"      ✅ {len(gap_strings)} strings recuperadas")
                recovered_strings.extend(gap_strings)
            else:
                print(f"      ❌ Nenhuma string encontrada")

        # Estatísticas
        stats = {
            'total_gaps': len(gaps),
            'text_candidate_gaps': len(text_candidates),
            'recovered_strings': len(recovered_strings)
        }

        print(f"\n📊 RESUMO DA VARREDURA:")
        print(f"   📏 Lacunas totais: {stats['total_gaps']}")
        print(f"   🎯 Áreas de interesse: {stats['text_candidate_gaps']}")
        print(f"   ✅ Strings recuperadas: {stats['recovered_strings']}")
        print("="*80)

        return recovered_strings, stats


def scavenge_rom_gaps(rom_path: str, char_table: Dict[int, str],
                      extracted_offsets: List[int]) -> Tuple[List[Tuple[int, str]], Dict]:
    """
    Função principal de varredura.

    Args:
        rom_path: Caminho da ROM
        char_table: Tabela de caracteres usada
        extracted_offsets: Offsets já extraídos

    Returns:
        (recovered_strings, statistics)
    """
    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    engine = DeepScavengerEngine(rom_data, char_table)
    return engine.scavenge(extracted_offsets)


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        # Teste standalone
        rom_path = sys.argv[1]

        # Cria tabela de teste (ASCII)
        test_table = {}
        for i in range(0x20, 0x7F):
            test_table[i] = chr(i)

        # Simula alguns offsets extraídos
        test_offsets = [0, 100, 500, 1000, 5000]

        recovered, stats = scavenge_rom_gaps(rom_path, test_table, test_offsets)

        print(f"\n✅ Teste concluído!")
        print(f"   Strings recuperadas: {len(recovered)}")

        if recovered:
            print(f"\n📝 Primeiras 10 strings:")
            for offset, text in recovered[:10]:
                print(f"   [0x{offset:X}] {text[:50]}")

    else:
        print("Uso: python deep_scavenger_engine.py <rom_path>")
