# -*- coding: utf-8 -*-
"""
DTE INTEGRATION - Integra compressao DTE no pipeline de reinsercao
===================================================================
Tenta comprimir texto traduzido via DTE antes de recorrer a
realocacao ou truncamento.

Autor: ROM Translation Framework v6.0
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from core.dte_encoder import DTEEncoder, DTEDictionary

logger = logging.getLogger(__name__)


class DTEReinsertionHelper:
    """
    Helper que integra DTE ao pipeline de reinsercao.

    Uso tipico:
        helper = DTEReinsertionHelper()
        helper.build_dictionary(all_encoded_texts)
        compressed = helper.try_dte_compression(encoded_text, max_length)
        if compressed is not None:
            # Cabe! Usar compressed no lugar de encoded_text
    """

    def __init__(self, code_start: int = 0x80, code_end: int = 0xFF):
        self.encoder = DTEEncoder(code_start, code_end)
        self.dictionary: Optional[DTEDictionary] = None
        self._stats = {
            'texts_compressed': 0,
            'texts_failed': 0,
            'bytes_saved': 0,
        }

    def build_dictionary(self, all_texts: List[bytes]):
        """
        Constroi dicionario DTE a partir de todos os textos traduzidos.
        Deve ser chamado UMA VEZ antes de comprimir textos individuais.

        Args:
            all_texts: Lista de todos os textos codificados (bytes)
        """
        self.dictionary = self.encoder.analyze(all_texts)
        logger.info(
            f"DTE dictionary built: {len(self.dictionary.entries)} entries, "
            f"estimated savings: {self.dictionary.total_savings} bytes"
        )

    def try_dte_compression(self, encoded: bytes,
                            max_length: int) -> Optional[bytes]:
        """
        Tenta comprimir texto via DTE para caber no espaco disponivel.

        Args:
            encoded: Texto codificado (bytes) que nao cabe
            max_length: Tamanho maximo em bytes

        Returns:
            Bytes comprimidos se couber, None se ainda nao couber
        """
        if not self.dictionary or not self.dictionary.entries:
            return None

        if len(encoded) <= max_length:
            return encoded

        compressed = self.encoder.compress(encoded, self.dictionary)

        if len(compressed) <= max_length:
            saved = len(encoded) - len(compressed)
            self._stats['texts_compressed'] += 1
            self._stats['bytes_saved'] += saved
            logger.info(
                f"DTE compressed: {len(encoded)} -> {len(compressed)} bytes "
                f"(saved {saved}, max={max_length})"
            )
            return compressed

        self._stats['texts_failed'] += 1
        logger.debug(
            f"DTE insufficient: {len(encoded)} -> {len(compressed)} bytes "
            f"(needed {max_length})"
        )
        return None

    def get_dictionary_binary(self) -> bytes:
        """Retorna tabela binaria do dicionario para injetar na ROM."""
        if not self.dictionary:
            return b''
        return self.encoder.export_dictionary_as_binary(self.dictionary)

    def get_stats(self) -> Dict:
        """Retorna estatisticas de compressao."""
        return dict(self._stats)

    def generate_report(self, texts: List[bytes]) -> str:
        """
        Gera relatorio legivel de analise DTE.

        Args:
            texts: Textos para analisar

        Returns:
            String com relatorio formatado
        """
        stats = self.encoder.estimate_savings(texts)

        lines = [
            "=" * 50,
            "RELATORIO DTE (Dual Tile Encoding)",
            "=" * 50,
            f"Textos analisados: {len(texts)}",
            f"Tamanho original:  {stats['original_bytes']} bytes",
            f"Tamanho comprimido: {stats['compressed_bytes']} bytes",
            f"Economia: {stats['savings_bytes']} bytes "
            f"({stats['savings_percent']}%)",
            f"Entradas no dicionario: {stats['dictionary_entries']}",
            "",
            "Top 10 pares mais frequentes:",
            "-" * 40,
        ]

        for i, pair_info in enumerate(stats['top_10_pairs']):
            lines.append(
                f"  {i+1:2d}. {pair_info['code']} = "
                f"\"{pair_info['pair_ascii']}\" "
                f"(hex: {pair_info['pair']}) "
                f"x{pair_info['frequency']} = "
                f"-{pair_info['savings']} bytes"
            )

        lines.extend([
            "",
            "NOTA: Para usar DTE na ROM, o jogo precisa de um",
            "decoder DTE em sua rotina de renderizacao de texto.",
            "Sem patch ASM especifico, esta e apenas uma analise.",
            "=" * 50,
        ])

        return "\n".join(lines)
