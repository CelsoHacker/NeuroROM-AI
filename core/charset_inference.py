# -*- coding: utf-8 -*-
"""
================================================================================
CHARSET INFERENCE - Descoberta Automática de Tabelas de Caracteres
================================================================================
Inferência estatística de mapeamento byte → caractere através de:
- Análise de frequência (comparação com idiomas conhecidos)
- Detecção de padrões (espaços, terminadores, pontuação)
- Machine learning de padrões linguísticos
- Refinamento iterativo

Gera tabelas candidatas sem conhecimento prévio do jogo
================================================================================
"""

from typing import Dict, List, Tuple, Optional, Set
from collections import Counter, defaultdict
import json
from pathlib import Path


class CharsetCandidate:
    """Representa uma tabela de caracteres candidata."""

    def __init__(self, name: str):
        self.name = name
        self.byte_to_char: Dict[int, str] = {}
        self.char_to_byte: Dict[str, int] = {}
        self.confidence = 0.0
        self.evidence = []

    def add_mapping(self, byte: int, char: str, evidence: str):
        """Adiciona mapeamento byte → char com evidência."""
        self.byte_to_char[byte] = char
        self.char_to_byte[char] = byte
        self.evidence.append({
            'byte': f'0x{byte:02X}',
            'char': char,
            'reason': evidence
        })

    def __repr__(self):
        return f"<CharsetCandidate '{self.name}' mappings={len(self.byte_to_char)} confidence={self.confidence:.2f}>"


class CharsetInferenceEngine:
    """
    Motor de inferência de tabelas de caracteres baseado em análise estatística.
    """

    # Frequências esperadas de letras em português (%)
    PT_LETTER_FREQ = {
        'a': 14.63, 'e': 12.57, 'o': 10.73, 's': 7.81, 'r': 6.53,
        'i': 6.18, 'n': 5.05, 'd': 4.99, 'm': 4.74, 'u': 4.63,
        't': 4.34, 'c': 3.88, 'l': 2.78, 'p': 2.52, 'v': 1.67
    }

    # Frequências em inglês (para comparação)
    EN_LETTER_FREQ = {
        'e': 12.70, 't': 9.06, 'a': 8.17, 'o': 7.51, 'i': 6.97,
        'n': 6.75, 's': 6.33, 'h': 6.09, 'r': 5.99, 'd': 4.25
    }

    # Bytes comuns para controle
    COMMON_CONTROL_BYTES = {
        0x00: '<NULL>',
        0x0A: '<LF>',
        0x0D: '<CR>',
        0xFF: '<END>',
        0xFE: '<WAIT>',
        0xFD: '<PAGE>'
    }

    def __init__(self, text_candidates: List):
        """
        Args:
            text_candidates: Lista de TextCandidate do TextScanner
        """
        self.text_candidates = text_candidates
        self.charset_candidates = []
        self.byte_frequency = Counter()
        self.byte_positions = defaultdict(list)  # byte → [posições na string]

    def infer_charsets(self) -> List[CharsetCandidate]:
        """
        Executa processo completo de inferência de tabelas.

        Returns:
            Lista de tabelas candidatas ordenadas por confiança
        """
        print(f"\n🔤 CHARSET INFERENCE - Automatic Character Table Discovery")
        print(f"{'='*70}")

        if not self.text_candidates:
            print("❌ No text candidates provided!")
            return []

        # Fase 1: Análise de frequência
        print("[1/5] Analyzing byte frequencies...")
        self._analyze_byte_patterns()

        # Fase 2: Detecta bytes especiais (espaço, terminadores)
        print("[2/5] Identifying control bytes...")
        space_byte, terminator_bytes = self._identify_special_bytes()

        # Fase 3: Inferência baseada em frequência linguística
        print("[3/5] Inferring character mappings...")
        charset_freq = self._infer_from_frequency(space_byte)

        # Fase 4: Inferência baseada em posição (primeira letra = maiúscula)
        print("[4/5] Refining with positional analysis...")
        charset_pos = self._infer_from_position(space_byte)

        # Fase 5: Combina evidências e gera tabelas finais
        print("[5/5] Generating candidate tables...")
        self.charset_candidates = self._generate_candidates(
            charset_freq, charset_pos, space_byte, terminator_bytes
        )

        # Ordena por confiança
        self.charset_candidates.sort(key=lambda c: c.confidence, reverse=True)

        print(f"\n✅ Generated {len(self.charset_candidates)} charset candidates")
        print(f"{'='*70}\n")

        return self.charset_candidates

    def _analyze_byte_patterns(self):
        """Analisa padrões de frequência e posição de bytes."""
        for candidate in self.text_candidates:
            for i, byte in enumerate(candidate.data):
                self.byte_frequency[byte] += 1
                self.byte_positions[byte].append(i)

    def _identify_special_bytes(self) -> Tuple[Optional[int], Set[int]]:
        """
        Identifica bytes especiais (espaço e terminadores) por heurística.

        Returns:
            (space_byte, terminator_bytes_set)
        """
        # Espaço: geralmente o byte mais frequente ou segundo mais frequente
        most_common = self.byte_frequency.most_common(10)

        space_candidates = []
        for byte, count in most_common:
            # Espaço tende a aparecer entre 5-20% do total
            frequency_ratio = count / sum(self.byte_frequency.values())
            if 0.05 <= frequency_ratio <= 0.20:
                space_candidates.append((byte, frequency_ratio))

        space_byte = space_candidates[0][0] if space_candidates else 0x20  # Default ASCII space

        # Terminadores: bytes que aparecem no final das strings
        terminator_candidates = Counter()
        for candidate in self.text_candidates:
            if candidate.data:
                last_byte = candidate.data[-1]
                terminator_candidates[last_byte] += 1

        # Terminadores mais comuns
        terminators = set()
        for byte, count in terminator_candidates.most_common(3):
            if count >= len(self.text_candidates) * 0.1:  # Pelo menos 10% das strings
                terminators.add(byte)

        print(f"   Identified space byte: 0x{space_byte:02X}")
        print(f"   Identified terminators: {[f'0x{b:02X}' for b in terminators]}")

        return space_byte, terminators

    def _infer_from_frequency(self, space_byte: int) -> CharsetCandidate:
        """
        Inferência baseada em frequência de letras.

        Compara frequência de bytes com frequência de letras em português/inglês.
        """
        charset = CharsetCandidate("frequency_based")

        # Remove bytes de controle e espaço
        filtered_freq = {
            byte: count for byte, count in self.byte_frequency.items()
            if byte not in self.COMMON_CONTROL_BYTES and byte != space_byte
        }

        # Ordena bytes por frequência (mais comum primeiro)
        sorted_bytes = sorted(filtered_freq.items(), key=lambda x: x[1], reverse=True)

        # Ordena letras portuguesas por frequência
        sorted_letters = sorted(self.PT_LETTER_FREQ.items(), key=lambda x: x[1], reverse=True)

        # Mapeia os N bytes mais comuns para as N letras mais comuns
        n = min(len(sorted_bytes), len(sorted_letters))

        for i in range(n):
            byte, byte_count = sorted_bytes[i]
            letter, letter_freq = sorted_letters[i]

            # Adiciona mapeamento
            charset.add_mapping(
                byte, letter,
                f"Frequency match: {byte_count} occurrences ≈ {letter_freq:.2f}%"
            )

        # Adiciona espaço
        charset.add_mapping(space_byte, ' ', "Identified as space byte")

        # Calcula confiança baseado na correlação de frequências
        charset.confidence = self._calculate_frequency_correlation(sorted_bytes[:n], sorted_letters[:n])

        return charset

    def _calculate_frequency_correlation(self, bytes_freq: List[Tuple], letters_freq: List[Tuple]) -> float:
        """
        Calcula correlação entre distribuições de bytes e letras.

        Usa coeficiente de correlação de Pearson simplificado.
        """
        if not bytes_freq or not letters_freq:
            return 0.0

        # Normaliza frequências
        total_bytes = sum(count for _, count in bytes_freq)
        total_letters = sum(freq for _, freq in letters_freq)

        byte_probs = [count / total_bytes for _, count in bytes_freq]
        letter_probs = [freq / total_letters for _, freq in letters_freq]

        # Correlação simples (quanto mais próximas as distribuições, melhor)
        n = min(len(byte_probs), len(letter_probs))
        correlation = sum(abs(byte_probs[i] - letter_probs[i]) for i in range(n)) / n

        # Inverte: menor diferença = maior confiança
        return max(0.0, 1.0 - correlation * 2)

    def _infer_from_position(self, space_byte: int) -> CharsetCandidate:
        """
        Inferência baseada em posição dos bytes.

        Heurística: Bytes após espaços tendem a ser letras minúsculas.
                    Bytes no início de strings tendem a ser maiúsculas.
        """
        charset = CharsetCandidate("position_based")

        # Analisa bytes que aparecem após espaços
        bytes_after_space = Counter()
        bytes_at_start = Counter()

        for candidate in self.text_candidates:
            data = candidate.data

            # Primeiro byte (pode ser maiúscula)
            if data:
                bytes_at_start[data[0]] += 1

            # Bytes após espaço (podem ser minúsculas)
            for i in range(len(data) - 1):
                if data[i] == space_byte:
                    bytes_after_space[data[i + 1]] += 1

        # Bytes mais comuns após espaço → minúsculas
        common_after_space = bytes_after_space.most_common(15)
        lowercase_letters = list('aeiousrndmtclpv')  # Mais comuns em português

        for i, (byte, count) in enumerate(common_after_space):
            if i < len(lowercase_letters):
                charset.add_mapping(
                    byte, lowercase_letters[i],
                    f"Common after space ({count} times)"
                )

        # Bytes comuns no início → maiúsculas
        common_at_start = bytes_at_start.most_common(15)
        uppercase_letters = list('AEIOUSRNDMTCLPV')

        for i, (byte, count) in enumerate(common_at_start):
            if i < len(uppercase_letters) and byte not in charset.byte_to_char:
                charset.add_mapping(
                    byte, uppercase_letters[i],
                    f"Common at string start ({count} times)"
                )

        charset.confidence = min(len(charset.byte_to_char) / 50.0, 1.0)  # Max 50 chars

        return charset

    def _generate_candidates(self, charset_freq: CharsetCandidate,
                            charset_pos: CharsetCandidate,
                            space_byte: int,
                            terminators: Set[int]) -> List[CharsetCandidate]:
        """
        Combina evidências de diferentes métodos para gerar tabelas finais.
        """
        candidates = []

        # Candidato 1: Baseado em frequência pura
        candidates.append(charset_freq)

        # Candidato 2: Baseado em posição
        candidates.append(charset_pos)

        # Candidato 3: Híbrido (combina os dois)
        hybrid = CharsetCandidate("hybrid")

        # Prioriza mapeamentos que aparecem em ambos
        for byte in set(charset_freq.byte_to_char.keys()) | set(charset_pos.byte_to_char.keys()):
            char_freq = charset_freq.byte_to_char.get(byte)
            char_pos = charset_pos.byte_to_char.get(byte)

            if char_freq == char_pos and char_freq:
                # Concordância total → alta confiança
                hybrid.add_mapping(byte, char_freq, "Agreement between methods")
            elif char_freq:
                # Apenas em frequência
                hybrid.add_mapping(byte, char_freq, "Frequency-based mapping")

        # Adiciona códigos de controle conhecidos
        for byte, symbol in self.COMMON_CONTROL_BYTES.items():
            if byte in terminators:
                hybrid.add_mapping(byte, symbol, "Identified terminator")

        # Adiciona espaço
        hybrid.add_mapping(space_byte, ' ', "Identified space")

        # Confiança do híbrido = média dos componentes
        hybrid.confidence = (charset_freq.confidence + charset_pos.confidence) / 2

        candidates.append(hybrid)

        return candidates

    def export_tables(self, output_dir: str):
        """Exporta tabelas candidatas como JSON."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for i, charset in enumerate(self.charset_candidates, 1):
            filename = output_path / f"charset_candidate_{i}_{charset.name}.json"

            # Converte para formato exportável
            table_data = {
                'name': charset.name,
                'confidence': round(charset.confidence, 3),
                'total_mappings': len(charset.byte_to_char),
                'byte_to_char': {
                    f'0x{byte:02X}': char
                    for byte, char in sorted(charset.byte_to_char.items())
                },
                'char_to_byte': {
                    char: f'0x{byte:02X}'
                    for char, byte in sorted(charset.char_to_byte.items())
                },
                'evidence': charset.evidence
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(table_data, f, indent=2, ensure_ascii=False)

            print(f"✅ Exported: {filename}")

    def test_charset(self, charset: CharsetCandidate, sample_data: bytes) -> str:
        """
        Testa uma tabela decodificando dados de amostra.

        Returns:
            String decodificada
        """
        result = []
        for byte in sample_data:
            char = charset.byte_to_char.get(byte, f'[{byte:02X}]')
            result.append(char)
        return ''.join(result)

    def print_candidates(self, n: int = 3):
        """Exibe resumo das N melhores tabelas."""
        print(f"\n📋 TOP {n} CHARSET CANDIDATES")
        print(f"{'='*70}")

        for i, charset in enumerate(self.charset_candidates[:n], 1):
            print(f"\n{i}. {charset.name.upper()}")
            print(f"   Confidence: {charset.confidence:.3f}")
            print(f"   Mappings:   {len(charset.byte_to_char)}")
            print(f"   Sample mappings:")

            # Exibe 10 primeiros mapeamentos
            for byte, char in list(charset.byte_to_char.items())[:10]:
                print(f"      0x{byte:02X} → '{char}'")

            # Testa com primeiro candidato de texto
            if self.text_candidates:
                sample = self.text_candidates[0].data[:50]
                decoded = self.test_charset(charset, sample)
                print(f"   Test decode: {decoded}")

        print(f"\n{'='*70}\n")


def infer_charset_from_rom(rom_path: str, text_candidates=None) -> CharsetInferenceEngine:
    """
    Função de conveniência para inferência completa.

    Args:
        rom_path: Caminho da ROM
        text_candidates: Candidatos do TextScanner (ou None para scan automático)

    Returns:
        CharsetInferenceEngine com tabelas geradas
    """
    if text_candidates is None:
        # Importa e executa TextScanner
        from .text_scanner import scan_text_in_rom
        scanner = scan_text_in_rom(rom_path)
        text_candidates = scanner.candidates

    engine = CharsetInferenceEngine(text_candidates)
    engine.infer_charsets()
    engine.print_candidates(3)

    # Exporta tabelas
    output_dir = Path(rom_path).parent / 'inferred_charsets'
    engine.export_tables(str(output_dir))

    return engine


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python charset_inference.py <rom_file>")
        sys.exit(1)

    rom_file = sys.argv[1]
    infer_charset_from_rom(rom_file)
