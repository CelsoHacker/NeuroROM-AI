#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compression Analyzer V1.0
Analisador avançado de compressão para ROMs SNES
Baseado em técnicas de Stealth Translations (2001)
"""

import struct
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

@dataclass
class CompressionPattern:
    """Padrão de compressão detectado"""
    offset: int
    control_byte: int
    table_offset: int
    bank: int
    dictionary_size: int
    entries: Dict[int, bytes]

class CompressionAnalyzer:
    """
    Analisador de compressão de dicionário em ROMs SNES
    Detecta e extrai CompPointTable automaticamente
    """

    def __init__(self, rom_data: bytes):
        self.rom_data = rom_data
        self.rom_size = len(rom_data)

        # Padrões Assembly comuns de compressão
        self.asm_patterns = {
            # CMP #$01 / BEQ = Compressão tipo 1
            'cmp_beq_01': bytes([0xC9, 0x01, 0xF0]),
            # CMP #$02 / BEQ = Reset compressão
            'cmp_beq_02': bytes([0xC9, 0x02, 0xF0]),
            # LDA $xxxx,X = Leitura de tabela
            'lda_table': bytes([0xBD]),
            # JSR $xxxx = Chamada de rotina
            'jsr_routine': bytes([0x20]),
        }

        self.detected_patterns: List[CompressionPattern] = []

    def analyze(self) -> List[CompressionPattern]:
        """
        Analisa ROM procurando padrões de compressão

        Returns:
            Lista de padrões de compressão encontrados
        """
        print("\n" + "="*80)
        print("🔍 COMPRESSION ANALYZER V1.0")
        print("="*80 + "\n")

        # 1. Procura por rotinas de compressão
        compression_routines = self._find_compression_routines()
        print(f"✅ {len(compression_routines)} rotinas de compressão encontradas\n")

        # 2. Extrai tabelas de ponteiros
        for routine_offset in compression_routines:
            pattern = self._extract_compression_table(routine_offset)
            if pattern:
                self.detected_patterns.append(pattern)
                print(f"📊 Padrão detectado em 0x{routine_offset:X}")
                print(f"   • Control Byte: 0x{pattern.control_byte:02X}")
                print(f"   • Tabela: 0x{pattern.table_offset:X}")
                print(f"   • Banco: 0x{pattern.bank:02X}")
                print(f"   • Entradas: {pattern.dictionary_size}\n")

        return self.detected_patterns

    def _find_compression_routines(self) -> List[int]:
        """
        Procura por rotinas Assembly de compressão

        Returns:
            Lista de offsets onde rotinas foram encontradas
        """
        routines = []

        # Procura padrão: CMP #$01 / BEQ
        pattern = self.asm_patterns['cmp_beq_01']
        offset = 0

        while offset < self.rom_size - len(pattern):
            if self.rom_data[offset:offset+len(pattern)] == pattern:
                routines.append(offset)
                offset += len(pattern)
            else:
                offset += 1

        return routines

    def _extract_compression_table(self, routine_offset: int) -> Optional[CompressionPattern]:
        """
        Extrai CompPointTable de uma rotina de compressão

        Args:
            routine_offset: Offset da rotina Assembly

        Returns:
            CompressionPattern ou None se não encontrar
        """
        # Procura por LDA $xxxx,X (carrega ponteiro da tabela)
        search_range = min(routine_offset + 100, self.rom_size)

        for i in range(routine_offset, search_range):
            if i + 2 < self.rom_size and self.rom_data[i] == 0xBD:
                # Encontrou LDA $xxxx,X
                table_addr = struct.unpack('<H', self.rom_data[i+1:i+3])[0]

                # Converte endereço SNES para offset ROM
                table_offset = self._snes_to_rom(table_addr)

                if table_offset and table_offset < self.rom_size:
                    # Tenta extrair dicionário
                    entries = self._extract_dictionary(table_offset)

                    if entries:
                        return CompressionPattern(
                            offset=routine_offset,
                            control_byte=0x01,  # Padrão comum
                            table_offset=table_offset,
                            bank=0xC0,  # Banco típico de SNES
                            dictionary_size=len(entries),
                            entries=entries
                        )

        return None

    def _extract_dictionary(self, table_offset: int, max_entries: int = 256) -> Dict[int, bytes]:
        """
        Extrai dicionário de palavras comprimidas

        Args:
            table_offset: Offset da tabela de ponteiros
            max_entries: Máximo de entradas para ler

        Returns:
            Dicionário {índice: palavra}
        """
        dictionary = {}

        for i in range(max_entries):
            ptr_offset = table_offset + (i * 2)

            if ptr_offset + 2 > self.rom_size:
                break

            # Lê ponteiro
            word_addr = struct.unpack('<H', self.rom_data[ptr_offset:ptr_offset+2])[0]

            # Converte para offset ROM
            word_offset = self._snes_to_rom(word_addr)

            if not word_offset or word_offset >= self.rom_size:
                break

            # Extrai palavra (até byte terminador ou 32 bytes)
            word = self._extract_word(word_offset)

            if word:
                dictionary[i] = word
            else:
                break

        return dictionary

    def _extract_word(self, offset: int, max_len: int = 32) -> Optional[bytes]:
        """
        Extrai palavra do dicionário

        Args:
            offset: Offset da palavra
            max_len: Tamanho máximo

        Returns:
            Bytes da palavra ou None
        """
        word = bytearray()

        for i in range(max_len):
            if offset + i >= self.rom_size:
                break

            byte = self.rom_data[offset + i]

            # Bytes terminadores comuns
            if byte in [0x00, 0xFF, 0x02]:
                break

            # Apenas bytes imprimíveis
            if 0x20 <= byte <= 0x7E or byte in [0x40, 0x5C]:
                word.append(byte)
            else:
                break

        return bytes(word) if len(word) >= 2 else None

    def _snes_to_rom(self, snes_addr: int) -> Optional[int]:
        """
        Converte endereço SNES para offset ROM

        Args:
            snes_addr: Endereço SNES ($xxxx)

        Returns:
            Offset ROM ou None
        """
        # LoROM
        if 0x8000 <= snes_addr <= 0xFFFF:
            return (snes_addr - 0x8000) % 0x8000

        # HiROM
        if 0xC00000 <= snes_addr <= 0xFFFFFF:
            return snes_addr - 0xC00000

        return None

    def expand_compressed_text(self, text_offset: int, pattern: CompressionPattern) -> str:
        """
        Expande texto comprimido usando dicionário

        Args:
            text_offset: Offset do texto comprimido
            pattern: Padrão de compressão a usar

        Returns:
            Texto expandido
        """
        result = []
        i = text_offset

        while i < self.rom_size:
            byte = self.rom_data[i]

            # Byte de controle de compressão
            if byte == pattern.control_byte:
                i += 1
                if i >= self.rom_size:
                    break

                # Próximo byte é índice do dicionário
                dict_index = self.rom_data[i]

                if dict_index in pattern.entries:
                    word = pattern.entries[dict_index]
                    try:
                        result.append(word.decode('ascii'))
                    except:
                        result.append(word.hex())

                i += 1

            # Byte de reset
            elif byte == 0x02:
                break

            # Byte normal
            elif 0x20 <= byte <= 0x7E:
                result.append(chr(byte))
                i += 1

            # Byte terminador
            elif byte == 0x00:
                break

            else:
                i += 1

        return ''.join(result)

    def generate_report(self, output_path: str):
        """
        Gera relatório detalhado da análise

        Args:
            output_path: Caminho do arquivo de saída
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("COMPRESSION ANALYZER - RELATÓRIO DETALHADO\n")
            f.write("="*80 + "\n\n")

            f.write(f"ROM Size: {self.rom_size:,} bytes\n")
            f.write(f"Padrões Detectados: {len(self.detected_patterns)}\n\n")

            for idx, pattern in enumerate(self.detected_patterns, 1):
                f.write(f"\n{'='*80}\n")
                f.write(f"PADRÃO {idx}\n")
                f.write(f"{'='*80}\n\n")

                f.write(f"Offset da Rotina: 0x{pattern.offset:X}\n")
                f.write(f"Control Byte: 0x{pattern.control_byte:02X}\n")
                f.write(f"Tabela de Ponteiros: 0x{pattern.table_offset:X}\n")
                f.write(f"Banco: 0x{pattern.bank:02X}\n")
                f.write(f"Tamanho do Dicionário: {pattern.dictionary_size} entradas\n\n")

                f.write("DICIONÁRIO:\n")
                f.write("-"*80 + "\n")

                for dict_idx, word in sorted(pattern.entries.items()):
                    try:
                        word_str = word.decode('ascii')
                    except:
                        word_str = word.hex()

                    f.write(f"[0x{dict_idx:02X}] {word_str}\n")

                f.write("\n")

        print(f"✅ Relatório salvo: {output_path}\n")


def analyze_rom_compression(rom_path: str, output_path: str = None):
    """
    Função principal para analisar compressão de uma ROM

    Args:
        rom_path: Caminho da ROM
        output_path: Caminho do relatório (opcional)
    """
    # Lê ROM
    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    # Analisa
    analyzer = CompressionAnalyzer(rom_data)
    patterns = analyzer.analyze()

    # Gera relatório
    if output_path:
        analyzer.generate_report(output_path)

    print(f"{'='*80}")
    print(f"✅ Análise concluída: {len(patterns)} padrões encontrados")
    print(f"{'='*80}\n")

    return patterns


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python compression_analyzer.py <rom_path> [output_report]")
        sys.exit(1)

    rom_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    analyze_rom_compression(rom_path, output_path)
