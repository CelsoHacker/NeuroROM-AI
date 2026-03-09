# -*- coding: utf-8 -*-
"""
DTE ENCODER - Dual Tile Encoding / Byte-Pair Compression
=========================================================
Comprime texto traduzido substituindo pares de bytes frequentes
por codigos single-byte no range 0x80-0xFF.

Uso: quando o texto traduzido PT-BR e mais longo que o original,
DTE pode comprimir para caber no mesmo espaco.

NOTA: Para funcionar na ROM, o jogo precisa de um decoder DTE
em sua rotina de renderizacao de texto. Sem patch ASM especifico,
esta ferramenta serve como ANALISE (mostra economia potencial).

Autor: ROM Translation Framework v6.0
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class DTEEntry:
    """Uma entrada no dicionario DTE."""
    code: int        # Byte code (0x80-0xFF)
    pair: bytes      # Par de bytes original (2 bytes)
    frequency: int   # Quantas vezes aparece nos textos
    savings: int     # Bytes economizados (frequency * 1)


@dataclass
class DTEDictionary:
    """Dicionario DTE completo."""
    entries: List[DTEEntry] = field(default_factory=list)
    code_range: Tuple[int, int] = (0x80, 0xFF)
    total_savings: int = 0

    @property
    def max_entries(self) -> int:
        return self.code_range[1] - self.code_range[0] + 1

    def get_pair_for_code(self, code: int) -> Optional[bytes]:
        for entry in self.entries:
            if entry.code == code:
                return entry.pair
        return None

    def get_code_for_pair(self, pair: bytes) -> Optional[int]:
        for entry in self.entries:
            if entry.pair == pair:
                return entry.code
        return None


class DTEEncoder:
    """
    Encoder DTE (Dual Tile Encoding).

    Algoritmo:
    1. Conta todos os pares de bytes adjacentes nos textos
    2. Ordena por frequencia (mais comum primeiro)
    3. Atribui codigos 0x80-0xFF aos pares mais frequentes
    4. Substitui pares por codigos single-byte

    Cada substituicao economiza 1 byte por ocorrencia.
    """

    def __init__(self, code_start: int = 0x80, code_end: int = 0xFF):
        self.code_start = code_start
        self.code_end = code_end
        self.dictionary: Optional[DTEDictionary] = None

    def analyze(self, texts: List[bytes]) -> DTEDictionary:
        """
        Analisa textos e cria dicionario DTE otimo.

        Args:
            texts: Lista de textos codificados como bytes

        Returns:
            DTEDictionary com as melhores substituicoes
        """
        # Conta pares de bytes
        pair_counts: Counter = Counter()
        for text in texts:
            for i in range(len(text) - 1):
                pair = bytes(text[i:i + 2])
                # Ignora pares que contem bytes no range de codigos DTE
                if all(b < self.code_start for b in pair):
                    pair_counts[pair] += 1

        # Ordena por frequencia
        sorted_pairs = pair_counts.most_common()

        # Cria entradas
        max_entries = self.code_end - self.code_start + 1
        entries: List[DTEEntry] = []
        total_savings = 0

        for i, (pair, count) in enumerate(sorted_pairs):
            if i >= max_entries:
                break
            if count < 2:
                break  # Nao vale a pena para pares que aparecem 1x

            code = self.code_start + i
            savings = count  # Cada substituicao economiza 1 byte
            entries.append(DTEEntry(
                code=code,
                pair=pair,
                frequency=count,
                savings=savings,
            ))
            total_savings += savings

        self.dictionary = DTEDictionary(
            entries=entries,
            code_range=(self.code_start, self.code_end),
            total_savings=total_savings,
        )
        return self.dictionary

    def compress(self, data: bytes,
                 dictionary: Optional[DTEDictionary] = None) -> bytes:
        """
        Comprime dados usando dicionario DTE.

        Args:
            data: Bytes para comprimir
            dictionary: Dicionario DTE (usa self.dictionary se None)

        Returns:
            Bytes comprimidos
        """
        dic = dictionary or self.dictionary
        if not dic or not dic.entries:
            return data

        # Cria lookup rapido pair -> code
        pair_to_code: Dict[bytes, int] = {}
        for entry in dic.entries:
            pair_to_code[entry.pair] = entry.code

        result = bytearray()
        i = 0
        while i < len(data):
            if i + 1 < len(data):
                pair = bytes(data[i:i + 2])
                code = pair_to_code.get(pair)
                if code is not None:
                    result.append(code)
                    i += 2
                    continue
            result.append(data[i])
            i += 1

        return bytes(result)

    def decompress(self, data: bytes,
                   dictionary: Optional[DTEDictionary] = None) -> bytes:
        """
        Descomprime dados DTE de volta ao original.
        """
        dic = dictionary or self.dictionary
        if not dic or not dic.entries:
            return data

        code_to_pair: Dict[int, bytes] = {}
        for entry in dic.entries:
            code_to_pair[entry.code] = entry.pair

        result = bytearray()
        for b in data:
            pair = code_to_pair.get(b)
            if pair:
                result.extend(pair)
            else:
                result.append(b)

        return bytes(result)

    def estimate_savings(self, texts: List[bytes]) -> Dict:
        """
        Estima economia sem comprimir.

        Returns:
            Dict com estatisticas detalhadas
        """
        dic = self.analyze(texts)

        original_size = sum(len(t) for t in texts)
        compressed_sizes = []
        for text in texts:
            compressed = self.compress(text, dic)
            compressed_sizes.append(len(compressed))

        compressed_total = sum(compressed_sizes)
        savings = original_size - compressed_total
        ratio = (savings / original_size * 100) if original_size > 0 else 0

        return {
            'original_bytes': original_size,
            'compressed_bytes': compressed_total,
            'savings_bytes': savings,
            'savings_percent': round(ratio, 1),
            'dictionary_entries': len(dic.entries),
            'top_10_pairs': [
                {
                    'pair': entry.pair.hex(),
                    'pair_ascii': _safe_ascii(entry.pair),
                    'code': f'0x{entry.code:02X}',
                    'frequency': entry.frequency,
                    'savings': entry.savings,
                }
                for entry in dic.entries[:10]
            ],
        }

    def export_dictionary_as_binary(self,
                                    dictionary: Optional[DTEDictionary] = None
                                    ) -> bytes:
        """
        Exporta dicionario como tabela binaria para injetar na ROM.

        Formato: 128 entradas de 2 bytes cada (256 bytes total).
        Indice = code - 0x80, valor = par de bytes.
        """
        dic = dictionary or self.dictionary
        if not dic:
            return b'\x00' * 256

        table = bytearray(256)
        for entry in dic.entries:
            idx = (entry.code - dic.code_range[0]) * 2
            if idx + 1 < len(table):
                table[idx] = entry.pair[0]
                table[idx + 1] = entry.pair[1]

        return bytes(table)

    def export_dictionary_as_asm(self,
                                 dictionary: Optional[DTEDictionary] = None,
                                 cpu: str = 'z80') -> str:
        """
        Exporta dicionario como source assembly.

        Args:
            dictionary: Dicionario DTE
            cpu: 'z80' para SMS/GG, '65816' para SNES
        """
        dic = dictionary or self.dictionary
        if not dic:
            return "; Empty DTE dictionary\n"

        lines = [
            f"; DTE Dictionary - {len(dic.entries)} entries",
            f"; Total savings: {dic.total_savings} bytes",
            f"; Code range: 0x{dic.code_range[0]:02X}-"
            f"0x{dic.code_range[0] + len(dic.entries) - 1:02X}",
            "",
        ]

        if cpu == 'z80':
            lines.append("DTE_Table:")
            for entry in dic.entries:
                ascii_repr = _safe_ascii(entry.pair)
                lines.append(
                    f"  .db ${entry.pair[0]:02X}, ${entry.pair[1]:02X}"
                    f"  ; 0x{entry.code:02X} = \"{ascii_repr}\""
                    f" (x{entry.frequency})"
                )
        elif cpu == '65816':
            lines.append("DTE_Table:")
            for entry in dic.entries:
                ascii_repr = _safe_ascii(entry.pair)
                lines.append(
                    f"  .db ${entry.pair[0]:02X}, ${entry.pair[1]:02X}"
                    f"  ; ${entry.code:02X} = \"{ascii_repr}\""
                    f" (x{entry.frequency})"
                )

        return "\n".join(lines) + "\n"


def _safe_ascii(data: bytes) -> str:
    """Converte bytes para representacao ASCII segura."""
    result = []
    for b in data:
        if 0x20 <= b < 0x7F:
            result.append(chr(b))
        else:
            result.append(f"\\x{b:02X}")
    return "".join(result)
