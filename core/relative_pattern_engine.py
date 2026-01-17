# -*- coding: utf-8 -*-
"""
RELATIVE PATTERN ENGINE - Quebrador de Tabela Matemático V7.0
===============================================================
Detecta tabelas customizadas usando vetores de distância matemáticos.

Técnica inovadora:
1. Converte palavras conhecidas em vetores de diferença
2. Busca padrões matemáticos na ROM (não bytes fixos)
3. Gera tabela automaticamente a partir dos matches

Exemplo:
"ABC" tem vetor [+1, +1]
Se encontrar bytes [04, 05, 06] com vetor [+1, +1] → 04='A'

Autor: Sistema V7.0 ULTIMATE
Data: 2026-01
"""

import struct
import math
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import Counter


class RelativePatternEngine:
    """
    Motor de detecção de tabelas usando análise matemática de padrões.
    """

    def __init__(self, rom_data: bytes):
        self.rom_data = rom_data
        self.detected_table: Dict[int, str] = {}

        # Keywords obrigatórias (nomes comuns em jogos)
        self.keywords = [
            "NINTENDO",
            "CAPCOM",
            "KONAMI",
            "START",
            "SELECT",
            "GAME",
            "OVER",
            "PLAYER",
            "CONTINUE",
            "PAUSE",
            "SCORE",
            "TIME",
            "LEVEL",
            "STAGE",
            "BONUS",
            "PRESS",
        ]

    def calculate_shannon_entropy(self) -> float:
        """
        Calcula entropia de Shannon do arquivo.

        Entropia < 3.8 = Sem compressão pesada (boa para detecção)
        Entropia > 7.0 = Muito comprimido (difícil de detectar)
        """
        if not self.rom_data:
            return 0.0

        # Conta frequência de cada byte
        byte_counts = Counter(self.rom_data)

        # Calcula entropia
        entropy = 0.0
        length = len(self.rom_data)

        for count in byte_counts.values():
            probability = count / length
            if probability > 0:
                entropy -= probability * math.log2(probability)

        return entropy

    def should_activate(self, ascii_valid_count: int) -> bool:
        """
        Verifica se o motor deve ser ativado.

        Critérios:
        1. Extração ASCII retornou < 100 linhas válidas
        2. Entropia < 3.8 (sem compressão pesada)
        """
        entropy = self.calculate_shannon_entropy()

        print(f"\n🔬 RELATIVE PATTERN ENGINE - Diagnóstico:")
        print(f"   📊 Strings ASCII válidas: {ascii_valid_count}")
        print(f"   🧮 Entropia de Shannon: {entropy:.2f}")

        activate = ascii_valid_count < 100 and entropy < 3.8

        if activate:
            print(f"   ✅ ATIVADO - ROM candidata a tabela customizada")
        else:
            print(f"   ⏭️  DESATIVADO - ROM não precisa de detecção avançada")

        return activate

    def word_to_delta_vector(self, word: str) -> List[int]:
        """
        Converte palavra em vetor de diferenças.

        Exemplo:
        "ABC" → [+1, +1]  (B-A=1, C-B=1)
        "ACE" → [+2, +2]  (C-A=2, E-C=2)
        """
        if len(word) < 2:
            return []

        deltas = []
        for i in range(len(word) - 1):
            delta = ord(word[i+1]) - ord(word[i])
            deltas.append(delta)

        return deltas

    def find_pattern_matches(self, delta_vector: List[int], max_results: int = 10) -> List[Tuple[int, List[int]]]:
        """
        Busca sequências de bytes que satisfaçam o vetor de diferenças.

        Args:
            delta_vector: Vetor de diferenças esperado
            max_results: Máximo de matches a retornar

        Returns:
            Lista de (offset, [bytes]) que satisfazem o padrão
        """
        matches = []
        vector_length = len(delta_vector)

        if vector_length < 1:
            return matches

        # Varre ROM procurando sequências com mesmo padrão de deltas
        for offset in range(len(self.rom_data) - vector_length - 1):
            # Extrai bytes candidatos
            candidate_bytes = self.rom_data[offset:offset + vector_length + 1]

            # Calcula deltas dos bytes
            byte_deltas = []
            for i in range(len(candidate_bytes) - 1):
                delta = candidate_bytes[i+1] - candidate_bytes[i]
                byte_deltas.append(delta)

            # Verifica se deltas batem
            if byte_deltas == delta_vector:
                matches.append((offset, list(candidate_bytes)))

                if len(matches) >= max_results:
                    break

        return matches

    def build_table_from_keyword(self, keyword: str, byte_sequence: List[int]) -> Dict[int, str]:
        """
        Gera tabela completa a partir de um match de keyword.

        Args:
            keyword: Palavra encontrada (ex: "NINTENDO")
            byte_sequence: Bytes correspondentes

        Returns:
            Tabela de caracteres deduzida
        """
        if len(keyword) != len(byte_sequence):
            return {}

        table = {}

        # Mapeia bytes conhecidos
        for i, char in enumerate(keyword):
            byte_val = byte_sequence[i]
            table[byte_val] = char

        # Deduz resto do alfabeto usando diferenças
        # Se 'A' está em byte X, então 'B' provavelmente está em X+1

        # Encontra bytes de letras maiúsculas conhecidas
        uppercase_mappings = {}
        for byte_val, char in table.items():
            if char.isupper() and 'A' <= char <= 'Z':
                uppercase_mappings[char] = byte_val

        if 'A' in uppercase_mappings:
            # Deduz A-Z
            base_byte = uppercase_mappings['A']
            for i in range(26):
                char = chr(ord('A') + i)
                if char not in uppercase_mappings:
                    table[base_byte + i] = char

        # Deduz a-z (geralmente logo após A-Z)
        if 'A' in uppercase_mappings:
            lowercase_base = uppercase_mappings['A'] + 26
            for i in range(26):
                char = chr(ord('a') + i)
                table[lowercase_base + i] = char

        # Números (geralmente antes de A)
        if 'A' in uppercase_mappings:
            number_base = uppercase_mappings['A'] - 10
            if number_base >= 0:
                for i in range(10):
                    table[number_base + i] = str(i)

        # Espaço e pontuação (heurísticas comuns)
        table[0x00] = '\n'  # NULL = fim de string
        table[0xFF] = ' '   # FF = espaço (muito comum)
        table[0xFE] = ' '   # FE = espaço alternativo

        return table

    def validate_table(self, table: Dict[int, str], sample_size: int = 1024) -> Tuple[bool, float]:
        """
        Valida tabela extraindo uma amostra e verificando score linguístico.

        Returns:
            (is_valid, score)
        """
        from super_text_filter import SuperTextFilter

        filter = SuperTextFilter()

        # Extrai strings de amostra
        sample_strings = []
        offset = 0

        while offset < min(len(self.rom_data), sample_size * 100) and len(sample_strings) < 50:
            byte = self.rom_data[offset]

            if byte in table:
                # Tenta extrair string
                text = []
                for i in range(200):
                    if offset + i >= len(self.rom_data):
                        break

                    current_byte = self.rom_data[offset + i]

                    if current_byte in [0x00, 0xFF]:
                        break

                    if current_byte in table:
                        text.append(table[current_byte])
                    else:
                        break

                if len(text) >= 4:
                    sample_strings.append(''.join(text))
                    offset += len(text)
                else:
                    offset += 1
            else:
                offset += 1

        if not sample_strings:
            return False, 0.0

        # Valida com filtro
        valid_count = 0
        for text in sample_strings:
            is_valid, _ = filter.is_valid_text(text)
            if is_valid:
                valid_count += 1

        score = valid_count / len(sample_strings)

        return score > 0.7, score

    def detect_table(self) -> Optional[Dict[int, str]]:
        """
        Executa detecção completa de tabela usando padrões matemáticos.

        Returns:
            Tabela detectada ou None
        """
        print("\n" + "="*80)
        print("🔬 RELATIVE PATTERN ENGINE - Detecção Matemática de Tabela")
        print("="*80)

        # Tenta cada keyword
        for keyword in self.keywords:
            print(f"\n🔍 Testando padrão: {keyword}")

            # Converte para vetor
            delta_vector = self.word_to_delta_vector(keyword)
            print(f"   📐 Vetor de diferenças: {delta_vector}")

            # Busca matches
            matches = self.find_pattern_matches(delta_vector, max_results=5)

            if matches:
                print(f"   ✅ {len(matches)} matches encontrados")

                # Testa cada match
                for idx, (offset, byte_sequence) in enumerate(matches, 1):
                    print(f"\n   🧪 Testando match {idx} no offset 0x{offset:X}")
                    print(f"      Bytes: {[f'{b:02X}' for b in byte_sequence]}")

                    # Gera tabela
                    table = self.build_table_from_keyword(keyword, byte_sequence)

                    if not table:
                        continue

                    print(f"      📋 Tabela gerada: {len(table)} caracteres")

                    # Valida
                    is_valid, score = self.validate_table(table)
                    print(f"      📊 Score de validação: {score:.2%}")

                    if is_valid:
                        print(f"\n   🎉 TABELA VÁLIDA DETECTADA!")
                        print(f"      Keyword: {keyword}")
                        print(f"      Offset: 0x{offset:X}")
                        print(f"      Score: {score:.2%}")

                        self.detected_table = table
                        return table

        print("\n   ❌ Nenhuma tabela válida detectada")
        return None

    def save_detected_table(self, output_path: str):
        """Salva tabela detectada em formato .tbl"""
        if not self.detected_table:
            return

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Tabela detectada automaticamente\n")
            f.write("# RELATIVE PATTERN ENGINE V7.0\n")
            f.write("# Formato: HEX=CHAR\n\n")

            for byte_val in sorted(self.detected_table.keys()):
                char = self.detected_table[byte_val]
                if char == '\n':
                    char = '\\n'
                f.write(f"{byte_val:02X}={char}\n")

        print(f"\n💾 Tabela salva: {output_path}")


def detect_custom_table(rom_path: str, ascii_valid_count: int = 0) -> Optional[Dict[int, str]]:
    """
    Função principal de detecção.

    Args:
        rom_path: Caminho da ROM
        ascii_valid_count: Número de strings válidas da extração ASCII

    Returns:
        Tabela detectada ou None
    """
    rom_path_obj = Path(rom_path)

    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    engine = RelativePatternEngine(rom_data)

    # Verifica se deve ativar
    if not engine.should_activate(ascii_valid_count):
        return None

    # Detecta tabela
    table = engine.detect_table()

    if table:
        # Salva tabela
        output_tbl = rom_path_obj.parent / f"{rom_path_obj.stem}_DETECTED.tbl"
        engine.save_detected_table(str(output_tbl))

    return table


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        rom_path = sys.argv[1]
        detect_custom_table(rom_path)
    else:
        print("Uso: python relative_pattern_engine.py <rom_path>")
