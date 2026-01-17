#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V8.0 + Compression Analyzer Integration
Integração do analisador de compressão com o extrator V8.0
"""

from typing import List, Dict
from compression_analyzer import CompressionAnalyzer, CompressionPattern

class V8CompressionEngine:
    """
    Motor de expansão de compressão para V8.0
    Usa análise automática de CompPointTable
    """

    def __init__(self, rom_data: bytes):
        self.rom_data = rom_data
        self.analyzer = CompressionAnalyzer(rom_data)
        self.patterns: List[CompressionPattern] = []
        self.active_pattern: CompressionPattern = None

    def analyze_and_prepare(self) -> bool:
        """
        Analisa ROM e prepara padrões de compressão

        Returns:
            True se encontrou padrões
        """
        print("\n🔧 Iniciando análise de compressão avançada...")

        self.patterns = self.analyzer.analyze()

        if self.patterns:
            self.active_pattern = self.patterns[0]  # Usa primeiro padrão
            print(f"✅ Compressão detectada: {len(self.patterns)} padrão(ões)")
            print(f"   • Usando padrão em 0x{self.active_pattern.offset:X}")
            print(f"   • Dicionário: {self.active_pattern.dictionary_size} palavras\n")
            return True
        else:
            print("ℹ️  Nenhuma compressão de dicionário detectada\n")
            return False

    def expand_text(self, offset: int) -> str:
        """
        Expande texto comprimido em um offset

        Args:
            offset: Offset do texto

        Returns:
            Texto expandido
        """
        if not self.active_pattern:
            return None

        return self.analyzer.expand_compressed_text(offset, self.active_pattern)

    def is_compressed_byte(self, byte: int) -> bool:
        """
        Verifica se byte é de controle de compressão

        Args:
            byte: Byte a verificar

        Returns:
            True se for byte de controle
        """
        if not self.active_pattern:
            return False

        return byte == self.active_pattern.control_byte

    def get_dictionary_word(self, index: int) -> bytes:
        """
        Obtém palavra do dicionário

        Args:
            index: Índice da palavra

        Returns:
            Bytes da palavra ou None
        """
        if not self.active_pattern:
            return None

        return self.active_pattern.entries.get(index)

    def get_all_dictionary_words(self) -> List[str]:
        """
        Retorna todas as palavras do dicionário

        Returns:
            Lista de palavras
        """
        if not self.active_pattern:
            return []

        words = []
        for idx, word_bytes in self.active_pattern.entries.items():
            try:
                word = word_bytes.decode('ascii')
                words.append(word)
            except:
                pass

        return words

    def export_dictionary(self, output_path: str):
        """
        Exporta dicionário para arquivo

        Args:
            output_path: Caminho do arquivo
        """
        if not self.active_pattern:
            return

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("DICIONÁRIO DE COMPRESSÃO EXTRAÍDO\n")
            f.write("="*80 + "\n\n")

            f.write(f"Offset da Rotina: 0x{self.active_pattern.offset:X}\n")
            f.write(f"Control Byte: 0x{self.active_pattern.control_byte:02X}\n")
            f.write(f"Total de Palavras: {self.active_pattern.dictionary_size}\n\n")

            f.write("PALAVRAS:\n")
            f.write("-"*80 + "\n")

            for idx, word_bytes in sorted(self.active_pattern.entries.items()):
                try:
                    word = word_bytes.decode('ascii')
                except:
                    word = f"<binary: {word_bytes.hex()}>"

                f.write(f"[0x{idx:02X}] = \"{word}\"\n")

        print(f"✅ Dicionário exportado: {output_path}\n")


def integrate_compression_to_v8(rom_data: bytes, extracted_strings: List[Dict]) -> List[Dict]:
    """
    Integra expansão de compressão nas strings extraídas pelo V8.0

    Args:
        rom_data: Dados da ROM
        extracted_strings: Strings extraídas pelo V8.0

    Returns:
        Strings expandidas
    """
    print("\n" + "="*80)
    print("🔧 INTEGRAÇÃO V8.0 + COMPRESSION ANALYZER")
    print("="*80)

    # Inicializa engine
    engine = V8CompressionEngine(rom_data)

    if not engine.analyze_and_prepare():
        print("ℹ️  Modo normal: sem expansão de compressão\n")
        return extracted_strings

    # Expande strings comprimidas
    expanded_strings = []
    expanded_count = 0

    print("🔄 Expandindo strings comprimidas...")

    for string_data in extracted_strings:
        offset = string_data.get('offset')
        text = string_data.get('text', '')

        # Tenta expandir
        expanded_text = engine.expand_text(offset)

        if expanded_text and len(expanded_text) > len(text):
            # Texto foi expandido com sucesso
            string_data['text'] = expanded_text
            string_data['was_compressed'] = True
            expanded_count += 1

        expanded_strings.append(string_data)

    print(f"✅ {expanded_count} strings expandidas com sucesso!\n")

    return expanded_strings


# Exemplo de uso
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python v8_compression_integration.py <rom_path>")
        sys.exit(1)

    rom_path = sys.argv[1]

    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    # Testa engine
    engine = V8CompressionEngine(rom_data)
    engine.analyze_and_prepare()

    # Exporta dicionário
    if engine.active_pattern:
        dict_path = rom_path.replace('.smc', '_DICTIONARY.txt')
        engine.export_dictionary(dict_path)
