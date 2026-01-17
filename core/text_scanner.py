# -*- coding: utf-8 -*-
"""
================================================================================
TEXT SCANNER - Localizador de Strings de Texto em ROMs
================================================================================
Varredura heurística para localização de sequências de texto em arquivos binários.
Utiliza múltiplas estratégias:
- Detecção de padrões ASCII/UTF-8
- Análise de frequência de bytes
- Heurísticas de terminadores e delimitadores
- Scoring baseado em características linguísticas

Integra com CharsetInferenceEngine para descoberta automática de tabelas.
================================================================================
"""

from typing import List, Dict, Optional, Tuple, Set
from collections import Counter
from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass
class TextCandidate:
    """Representa uma sequência candidata a texto."""
    offset: int
    data: bytes
    length: int
    score: float = 0.0
    encoding_hints: List[str] = field(default_factory=list)

    def __repr__(self):
        preview = self.data[:20].hex() if len(self.data) > 20 else self.data.hex()
        return f"<TextCandidate offset=0x{self.offset:X} len={self.length} score={self.score:.2f}>"


class TextScanner:
    """
    Scanner de texto para ROMs e arquivos binários.

    Localiza sequências que provavelmente contêm texto baseado em:
    - Padrões de bytes (frequência, distribuição)
    - Terminadores conhecidos (0x00, 0xFF, etc.)
    - Características linguísticas (repetição, variação)
    """

    # Bytes que tipicamente terminam strings
    TERMINATOR_BYTES = {0x00, 0xFF, 0xFE, 0xFD}

    # Bytes de controle comuns em jogos
    CONTROL_BYTES = {
        0x00: 'NULL/END',
        0x01: 'NEWLINE',
        0x02: 'PAUSE',
        0x03: 'CLEAR',
        0x0A: 'LF',
        0x0D: 'CR',
        0xFE: 'WAIT',
        0xFF: 'END'
    }

    # Range ASCII imprimível
    ASCII_PRINTABLE = set(range(0x20, 0x7F))

    def __init__(self, data: bytes, text_regions: Optional[List[Dict]] = None):
        """
        Args:
            data: Bytes da ROM (sem header)
            text_regions: Regiões pré-identificadas como candidatas a texto
        """
        self.data = data
        self.text_regions = text_regions or []
        self.candidates: List[TextCandidate] = []

    def scan(self, min_length: int = 4, max_length: int = 256) -> List[TextCandidate]:
        """
        Executa varredura completa em busca de texto.

        Args:
            min_length: Tamanho mínimo de string
            max_length: Tamanho máximo de string

        Returns:
            Lista de TextCandidate ordenados por score
        """
        print(f"\n🔍 TEXT SCANNER - Binary Text Detection")
        print(f"{'='*70}")
        print(f"Data size: {len(self.data):,} bytes")
        print(f"Min length: {min_length}, Max length: {max_length}")

        self.candidates = []

        # Estratégia 1: Scan em regiões pré-identificadas
        if self.text_regions:
            print(f"[1/3] Scanning {len(self.text_regions)} pre-identified regions...")
            self._scan_regions(min_length, max_length)

        # Estratégia 2: Scan por padrões ASCII
        print("[2/3] Scanning for ASCII patterns...")
        self._scan_ascii_patterns(min_length, max_length)

        # Estratégia 3: Scan por terminadores
        print("[3/3] Scanning between terminators...")
        self._scan_between_terminators(min_length, max_length)

        # Remove duplicatas e ordena por score
        self._deduplicate()
        self.candidates.sort(key=lambda c: c.score, reverse=True)

        print(f"\n✅ Found {len(self.candidates)} text candidates")
        print(f"{'='*70}\n")

        return self.candidates

    def _scan_regions(self, min_length: int, max_length: int):
        """Escaneia regiões pré-identificadas."""
        for region in self.text_regions:
            start = region.get('start', 0)
            if isinstance(start, str):
                start = int(start, 16)

            end = region.get('end', start + region.get('size', 0))
            if isinstance(end, str):
                end = int(end, 16)

            # Scan dentro da região
            self._scan_range(start, end, min_length, max_length)

    def _scan_ascii_patterns(self, min_length: int, max_length: int):
        """Localiza sequências de bytes ASCII imprimíveis."""
        i = 0
        while i < len(self.data):
            # Procura início de sequência ASCII
            if self.data[i] in self.ASCII_PRINTABLE:
                start = i
                length = 0

                # Conta bytes consecutivos imprimíveis
                while i < len(self.data) and length < max_length:
                    byte = self.data[i]
                    if byte in self.ASCII_PRINTABLE or byte in self.CONTROL_BYTES:
                        length += 1
                        i += 1
                    else:
                        break

                # Se encontrou sequência válida
                if length >= min_length:
                    candidate_data = self.data[start:start + length]
                    score = self._calculate_score(candidate_data, 'ascii')

                    self.candidates.append(TextCandidate(
                        offset=start,
                        data=candidate_data,
                        length=length,
                        score=score,
                        encoding_hints=['ASCII']
                    ))
            else:
                i += 1

    def _scan_between_terminators(self, min_length: int, max_length: int):
        """Localiza texto entre bytes terminadores."""
        last_terminator = 0

        for i, byte in enumerate(self.data):
            if byte in self.TERMINATOR_BYTES:
                # Verifica região entre terminadores
                if i - last_terminator >= min_length:
                    candidate_data = self.data[last_terminator:i]

                    # Verifica se parece texto (não apenas bytes aleatórios)
                    if self._looks_like_text(candidate_data):
                        score = self._calculate_score(candidate_data, 'terminated')

                        self.candidates.append(TextCandidate(
                            offset=last_terminator,
                            data=candidate_data[:max_length],
                            length=min(len(candidate_data), max_length),
                            score=score,
                            encoding_hints=['TERMINATED']
                        ))

                last_terminator = i + 1

    def _scan_range(self, start: int, end: int, min_length: int, max_length: int):
        """Escaneia range específico."""
        end = min(end, len(self.data))

        i = start
        while i < end:
            # Procura início de sequência
            seq_start = i
            length = 0

            while i < end and length < max_length:
                byte = self.data[i]
                # Aceita bytes imprimíveis ou de controle conhecidos
                if byte in self.ASCII_PRINTABLE or byte in self.CONTROL_BYTES:
                    length += 1
                    i += 1
                elif byte in self.TERMINATOR_BYTES:
                    break
                else:
                    # Byte desconhecido - pode ser charset customizado
                    length += 1
                    i += 1

            if length >= min_length:
                candidate_data = self.data[seq_start:seq_start + length]
                score = self._calculate_score(candidate_data, 'region')

                self.candidates.append(TextCandidate(
                    offset=seq_start,
                    data=candidate_data,
                    length=length,
                    score=score,
                    encoding_hints=['REGION_SCAN']
                ))

            i += 1

    def _looks_like_text(self, data: bytes) -> bool:
        """Verifica se sequência de bytes parece texto."""
        if len(data) < 3:
            return False

        # Conta bytes em diferentes categorias
        printable = sum(1 for b in data if b in self.ASCII_PRINTABLE)
        control = sum(1 for b in data if b in self.CONTROL_BYTES)

        # Pelo menos 30% deve ser imprimível ou controle
        text_ratio = (printable + control) / len(data)
        if text_ratio < 0.3:
            return False

        # Verifica variação (texto real tem variação)
        unique_bytes = len(set(data))
        if unique_bytes < 3:
            return False

        return True

    def _calculate_score(self, data: bytes, source: str) -> float:
        """
        Calcula score de confiança para candidato.

        Score baseado em:
        - Proporção de bytes imprimíveis
        - Variação de bytes (entropia)
        - Presença de padrões linguísticos
        - Fonte da detecção
        """
        if not data:
            return 0.0

        score = 0.0

        # 1. Proporção de bytes imprimíveis (0-30 pontos)
        printable_count = sum(1 for b in data if b in self.ASCII_PRINTABLE)
        printable_ratio = printable_count / len(data)
        score += printable_ratio * 30

        # 2. Variação de bytes (0-20 pontos)
        unique_bytes = len(set(data))
        variation_ratio = unique_bytes / min(len(data), 50)
        score += min(variation_ratio, 1.0) * 20

        # 3. Presença de espaços (comum em texto) (0-15 pontos)
        space_count = data.count(0x20)
        if space_count > 0:
            space_ratio = space_count / len(data)
            if 0.05 <= space_ratio <= 0.25:  # 5-25% espaços é típico
                score += 15
            else:
                score += 5

        # 4. Tamanho razoável (0-15 pontos)
        if 10 <= len(data) <= 100:
            score += 15
        elif 5 <= len(data) <= 200:
            score += 10
        else:
            score += 5

        # 5. Bônus por fonte confiável (0-20 pontos)
        source_bonus = {
            'ascii': 20,
            'region': 15,
            'terminated': 10
        }
        score += source_bonus.get(source, 5)

        return min(score, 100.0)

    def _deduplicate(self):
        """Remove candidatos duplicados ou sobrepostos."""
        if not self.candidates:
            return

        # Ordena por offset
        self.candidates.sort(key=lambda c: c.offset)

        # Remove sobreposições mantendo maior score
        unique = []
        for candidate in self.candidates:
            # Verifica sobreposição com último adicionado
            if unique:
                last = unique[-1]
                # Se sobrepõe
                if candidate.offset < last.offset + last.length:
                    # Mantém o de maior score
                    if candidate.score > last.score:
                        unique[-1] = candidate
                    continue

            unique.append(candidate)

        self.candidates = unique

    def print_top_candidates(self, n: int = 10):
        """Exibe os N melhores candidatos."""
        print(f"\n📋 TOP {n} TEXT CANDIDATES")
        print(f"{'='*70}")

        for i, candidate in enumerate(self.candidates[:n], 1):
            # Tenta decodificar como ASCII
            try:
                text_preview = candidate.data[:40].decode('ascii', errors='replace')
            except:
                text_preview = candidate.data[:40].hex()

            print(f"\n{i}. Offset: 0x{candidate.offset:06X} | Length: {candidate.length}")
            print(f"   Score: {candidate.score:.1f} | Hints: {candidate.encoding_hints}")
            print(f"   Preview: {text_preview}")

        print(f"\n{'='*70}\n")

    def export_candidates(self, output_path: str, top_n: int = 100):
        """Exporta candidatos para JSON."""
        export_data = {
            'total_candidates': len(self.candidates),
            'exported': min(top_n, len(self.candidates)),
            'candidates': []
        }

        for candidate in self.candidates[:top_n]:
            export_data['candidates'].append({
                'offset_hex': f'0x{candidate.offset:06X}',
                'offset_dec': candidate.offset,
                'length': candidate.length,
                'score': round(candidate.score, 2),
                'encoding_hints': candidate.encoding_hints,
                'raw_hex': candidate.data.hex(),
                'ascii_preview': candidate.data.decode('ascii', errors='replace')[:100]
            })

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Exported {len(export_data['candidates'])} candidates to: {output_path}")


def scan_text_in_rom(rom_path: str, min_length: int = 4, max_length: int = 256) -> TextScanner:
    """
    Função de conveniência para scan de texto em ROM.

    Args:
        rom_path: Caminho para arquivo ROM
        min_length: Tamanho mínimo de string
        max_length: Tamanho máximo de string

    Returns:
        TextScanner com candidatos encontrados
    """
    print(f"\n🔍 Scanning ROM for text: {rom_path}")

    # Carrega ROM
    with open(rom_path, 'rb') as f:
        data = f.read()

    # Remove header SMC se presente
    if len(data) % 1024 == 512:
        print(f"[INFO] Removing 512-byte SMC header...")
        data = data[512:]

    # Cria scanner e executa
    scanner = TextScanner(data)
    scanner.scan(min_length, max_length)
    scanner.print_top_candidates(10)

    return scanner


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python text_scanner.py <rom_file>")
        sys.exit(1)

    rom_file = sys.argv[1]
    scanner = scan_text_in_rom(rom_file)

    # Exporta resultados
    output_path = str(Path(rom_file).with_suffix('')) + '_text_candidates.json'
    scanner.export_candidates(output_path)
