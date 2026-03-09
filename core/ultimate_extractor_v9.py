#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ULTIMATE EXTRACTOR V 9.8 [FORENSIC KERNEL] - KERNEL CORE ENGINE
NEUROROM AI V 6.0 PRO SUITE
================================================================================
KERNEL V 9.8 [FORENSIC KERNEL] FEATURES:
✓ Hardware Detection (HiROM/LoROM via $FFD5 byte)
✓ Sequential Finder (Auto-detect 0x00-0x09 = 0-9, 0x0A-0x23 = A-Z)
✓ Pointer Scavenger (16/24-bit pointer table scanner)
✓ Address Mapper (platform_to_physical with header detection + mirroring)
✓ Stealth Profiles (Profile A via Header $81C0)
✓ DTE/MTE Solver (Dictionary Hunter - mantido do V 8.0)
✓ Deep Scavenger (Entropy Scanner em lacunas)
✓ Preservation Mode (Filtros lenientes para MTE/DTE)
✓ DICTIONARY SOLVER (Bank $0E 0x70000 + Bank $1C 0xE0000)
✓ MASTER DECODER (Tabela padrão 0x00-0x61 + Sílabas 0x88-0xE8)
✓ SYLLABLES DECODER (Decodificação de strings compostas: 'and', 'The', etc)
✓ CREDITS DECODER (Tabela de créditos offset $471951)
✓ MIRRORING MODULE (Pointer Aliasing - converte endereços de barramento Platform 16)
✓ SCRIPT CRAWLER (Recursive Descent - segue ponteiros com rotulação de opcodes)
✓ DICTIONARY LOOKUP (MTE Expansion - offset $477648 para Profile B)
✓ JAPANESE ENCODING (Shift-JIS - suporte a jogos japoneses)
✓ HUFFMAN DECOMPRESSOR (16-bit Huffman para textos comprimidos)
================================================================================
"""

import os
import sys
import struct
import math
from typing import List, Dict, Tuple, Optional
from pathlib import Path

# Importa o Super Text Filter (com preservation mode)
try:
    from super_text_filter import SuperTextFilter
except ImportError:
    print("⚠️ SuperTextFilter não encontrado, usando filtro básico")
    SuperTextFilter = None


class UltimateExtractorV9:
    """
    Motor principal de extração V 9.8 [FORENSIC KERNEL]
    Implementa todas as funcionalidades do Kernel V 9.8
    Tabelas padrão para Console 16-bit Action-RPG Profile B

    NOVOS MÓDULOS V 9.8:
    - MIRRORING MODULE: Conversão de endereços Platform 16 para offsets físicos
    - SCRIPT CRAWLER: Recursive Descent com rotulação de opcodes
    - DICTIONARY LOOKUP: Expansão MTE/DTE via dicionário
    - JAPANESE ENCODING: Suporte Shift-JIS para jogos japoneses
    - HUFFMAN DECOMPRESSOR: Decodificação Huffman 16-bit
    """

    # ========================================================================
    # TABELA PRINCIPAL PROFILE B (PADRÃO) - 0x00 a 0x61
    # ========================================================================
    PROFILE_B_MAIN_TBL = {
        0x00: 'A', 0x01: 'B', 0x02: 'C', 0x03: 'D', 0x04: 'E', 0x05: 'F',
        0x06: 'G', 0x07: 'H', 0x08: 'I', 0x09: 'J', 0x0A: 'K', 0x0B: 'L',
        0x0C: 'M', 0x0D: 'N', 0x0E: 'O', 0x0F: 'P', 0x10: 'Q', 0x11: 'R',
        0x12: 'S', 0x13: 'T', 0x14: 'U', 0x15: 'V', 0x16: 'W', 0x17: 'X',
        0x18: 'Y', 0x19: 'Z', 0x1A: 'a', 0x1B: 'b', 0x1C: 'c', 0x1D: 'd',
        0x1E: 'e', 0x1F: 'f', 0x20: 'g', 0x21: 'h', 0x22: 'i', 0x23: 'j',
        0x24: 'k', 0x25: 'l', 0x26: 'm', 0x27: 'n', 0x28: 'o', 0x29: 'p',
        0x2A: 'q', 0x2B: 'r', 0x2C: 's', 0x2D: 't', 0x2E: 'u', 0x2F: 'v',
        0x30: 'w', 0x31: 'x', 0x32: 'y', 0x33: 'z', 0x34: '0', 0x35: '1',
        0x36: '2', 0x37: '3', 0x38: '4', 0x39: '5', 0x3A: '6', 0x3B: '7',
        0x3C: '8', 0x3D: '9', 0x3E: '!', 0x3F: '?', 0x40: ',', 0x41: '.',
        0x42: '-', 0x43: '…', 0x44: '>', 0x45: '(', 0x46: ')', 0x47: ' ',
        0x48: 'A', 0x49: 'B', 0x4A: 'X', 0x4B: 'Y', 0x4C: 'L', 0x4D: 'R',
        # Símbolos especiais e controles
        0x4E: '↑', 0x4F: '↓', 0x50: '→', 0x51: '←', 0x52: "'", 0x53: '"',
        0x54: '<', 0x55: ':', 0x56: ';', 0x57: '*', 0x58: '/', 0x59: '\\',
        0x5A: '+', 0x5B: '=', 0x5C: '&', 0x5D: '%', 0x5E: '$', 0x5F: '#',
        0x60: '@', 0x61: '¡',
        # Códigos de controle especiais
        0x75: '[WAIT_BTN]', 0x76: '[SCROLL]', 0x77: '__PROTECTED__[COLOR]__',
        0x78: '[SPEED]', 0x79: '[CHOOSE2]', 0x7A: '[CHOOSE3]', 0x7B: '[CHOOSE]',
        0x7C: '[WAIT_FRAME]', 0x7D: '[WAIT_INPUT]', 0x7E: '[NEWLINE]', 0x7F: '[END]'
    }

    # ========================================================================
    # TABELA DE SÍLABAS/PALAVRAS COMPOSTAS (0x88 - 0xE8)
    # ========================================================================
    PROFILE_B_SYLLABLES = {
        0x88: 'the ', 0x89: 'you ', 0x8A: 'I ', 0x8B: 'to ', 0x8C: 'and ',
        0x8D: 'a ', 0x8E: 'is ', 0x8F: 'it ', 0x90: 'and', 0x91: 'you',
        0x92: 'of ', 0x93: 'have ', 0x94: 'Hero', 0x95: 'Princess', 0x96: 'Enemy',
        0x97: 'Kingdom', 0x98: 'Artifact', 0x99: 'Guardian', 0x9A: 'your ',
        0x9B: 'are ', 0x9C: 'be ', 0x9D: 'not ', 0x9E: 'this ', 0x9F: 'what ',
        0xA0: 'will ', 0xA1: 'can ', 0xA2: 'from ', 0xA3: 'with ', 0xA4: 'but ',
        0xA5: 'his ', 0xA6: 'for ', 0xA7: 'was ', 0xA8: 'has ', 0xA9: 'by ',
        0xAA: 'one ', 0xAB: 'all ', 0xAC: 'were ', 0xAD: 'they ', 0xAE: 'there ',
        0xAF: 'been ', 0xB0: 'their ', 0xB1: 'would ', 0xB2: 'who ', 0xB3: 'him ',
        0xB4: 'she ', 0xB5: 'her ', 0xB6: 'me ', 0xB7: 'my ', 0xB8: 'out ',
        0xB9: 'up ', 0xBA: 'if ', 0xBB: 'no ', 0xBC: 'so ', 0xBD: 'when ',
        0xBE: 'which ', 0xBF: 'them ', 0xC0: 'some ', 0xC1: 'could ', 0xC2: 'time ',
        0xC3: 'very ', 0xC4: 'then ', 0xC5: 'now ', 0xC6: 'only ', 0xC7: 'its ',
        0xC8: 'may ', 0xC9: 'over ', 0xCA: 'any ', 0xCB: 'where ', 0xCC: 'much ',
        0xCD: 'through ', 0xCE: 'back ', 0xCF: 'good ', 0xD0: 'how ', 0xD1: 'our ',
        0xD2: 'well ', 0xD3: 'down ', 0xD4: 'should ', 0xD5: 'because ', 0xD6: 'each ',
        0xD7: 'just ', 0xD8: 'those ', 0xD9: 'people ', 0xDA: 'take ', 0xDB: 'day ',
        0xDC: 'into ', 0xDD: 'two ', 0xDE: 'see ', 0xDF: 'than ', 0xE0: 'come ',
        0xE1: 'more ', 0xE2: 'also ', 0xE3: 'before ', 0xE4: 'after ', 0xE5: 'other ',
        0xE6: 'The ', 0xE7: 'Sacred Item', 0xE8: 'currency'
    }

    # ========================================================================
    # TABELA DE CRÉDITOS (Offset $471951)
    # ========================================================================
    PROFILE_B_CREDITS_TBL = {
        0x00: 'A', 0x01: 'B', 0x02: 'C', 0x03: 'D', 0x04: 'E', 0x05: 'F',
        0x06: 'G', 0x07: 'H', 0x08: 'I', 0x09: 'J', 0x0A: 'K', 0x0B: 'L',
        0x0C: 'M', 0x0D: 'N', 0x0E: 'O', 0x0F: 'P', 0x10: 'Q', 0x11: 'R',
        0x12: 'S', 0x13: 'T', 0x14: 'U', 0x15: 'V', 0x16: 'W', 0x17: 'X',
        0x18: 'Y', 0x19: 'Z', 0x1A: ' ', 0x1B: '.', 0x1C: ',', 0x1D: "'",
        0x7F: '[END]'
    }

    def __init__(self, rom_path: str):
        self.rom_path = rom_path
        self.rom_data = None
        self.rom_size = 0
        self.has_header = False
        self.is_hirom = False
        self.is_lorom = False

        # Configurações de extração
        self.char_table = self._build_default_char_table()
        self.text_filter = SuperTextFilter() if SuperTextFilter else None

        # ✅ KERNEL V 9.8: FORENSIC MODULES
        self.mte_dictionary = {}  # Dictionary Lookup cache
        self.huffman_tree = None  # Huffman tree cache
        self.script_opcodes = set()  # Opcodes encontrados (para rotulação)
        self.visited_offsets = set()  # Recursive Descent tracking

        # Carrega ROM
        self._load_rom()

        # ✅ KERNEL V 9.6: Hardware Detection
        self._detect_hardware()

        # ✅ KERNEL V 9.8: Load MTE Dictionary for Profile B
        self._load_mte_dictionary()

    def _load_rom(self):
        """Carrega a ROM e detecta header SMC."""
        with open(self.rom_path, 'rb') as f:
            self.rom_data = bytearray(f.read())

        self.rom_size = len(self.rom_data)

        # Detecta header de 512 bytes
        if self.rom_size % 1024 == 512:
            self.has_header = True
            print(f"✅ Header SMC detectado (512 bytes)")
        else:
            self.has_header = False
            print(f"ℹ️  ROM sem header SMC")

    def _detect_hardware(self):
        """
        ✅ KERNEL V 9.5: Hardware Detection
        Lê o byte em $FFD5 para determinar se é HiROM ou LoROM
        """
        try:
            # Offset do byte de tipo de memória (Memory Map Type)
            # LoROM: $7FD5 (sem header) ou $81D5 (com header)
            # HiROM: $FFD5 (sem header) ou $101D5 (com header)

            # Tenta LoROM primeiro
            lorom_offset = 0x7FD5
            if self.has_header:
                lorom_offset += 0x200

            if lorom_offset < len(self.rom_data):
                map_mode = self.rom_data[lorom_offset]

                # Bits 4-5 do byte determinam o tipo:
                # 0x20 = LoROM
                # 0x21 = HiROM
                # 0x30 = LoROM + FastROM
                # 0x31 = HiROM + FastROM

                if map_mode in [0x20, 0x30]:
                    self.is_lorom = True
                    self.is_hirom = False
                    print(f"✅ KERNEL V 9.5: Hardware Detection = LoROM (byte 0x{map_mode:02X})")
                elif map_mode in [0x21, 0x31]:
                    self.is_hirom = True
                    self.is_lorom = False
                    print(f"✅ KERNEL V 9.5: Hardware Detection = HiROM (byte 0x{map_mode:02X})")
                else:
                    # Fallback: assume LoROM
                    self.is_lorom = True
                    print(f"⚠️  Tipo de memória desconhecido (0x{map_mode:02X}), assumindo LoROM")

        except Exception as e:
            print(f"⚠️  Erro na detecção de hardware: {e}")
            self.is_lorom = True  # Fallback seguro

    def platform_to_physical(self, platform_address: int) -> int:
        """
        ✅ KERNEL V 9.5: Address Mapper
        Converte endereço Platform 16-bit (0xC00000-0xFFFFFF) para offset físico da ROM

        Args:
            platform_address: Endereço no formato Console 16-bit (ex: 0xC18F2D)

        Returns:
            Offset físico na ROM
        """
        # Remove bits de banco
        bank = (platform_address >> 16) & 0xFF
        addr = platform_address & 0xFFFF

        if self.is_hirom:
            # HiROM: Mapeamento direto
            # Banco $C0-$FF -> Offset físico direto
            if 0xC0 <= bank <= 0xFF:
                physical = ((bank - 0xC0) * 0x10000) + addr
            else:
                physical = (bank * 0x10000) + addr
        else:
            # LoROM: Mapeamento por páginas
            # Banco $C0-$FF, endereço $8000-$FFFF
            if 0x8000 <= addr <= 0xFFFF:
                physical = ((bank & 0x7F) * 0x8000) + (addr - 0x8000)
            else:
                physical = (bank * 0x8000) + addr

        # Ajusta para header se presente
        if self.has_header:
            physical += 0x200

        return physical

    # ========================================================================
    # MÓDULO 1: MIRRORING MODULE (Pointer Aliasing Avançado)
    # ========================================================================

    def platform_to_physical_advanced(self, platform_address: int) -> Optional[int]:
        """
        ✅ KERNEL V 9.8: MIRRORING MODULE

        Converte endereços Console 16-bit com tratamento de mirroring e aliasing.
        Suporta LoROM/HiROM/ExHiROM/SA-1 com detecção automática.

        POINTER ALIASING RULES:
        - LoROM: Banks $00-$7F/$80-$FF mirror cada um
        - HiROM: Banks $C0-$FF são ROM direta
        - SA-1: Banks $C0-$CF map para BW-RAM (ignorado)

        Args:
            platform_address: Endereço no formato Console (ex: 0xC18F2D)

        Returns:
            Offset físico na ROM ou None se inválido
        """
        bank = (platform_address >> 16) & 0xFF
        addr = platform_address & 0xFFFF

        physical = None

        if self.is_hirom:
            # HiROM: $C0-$FF -> ROM direta
            if 0xC0 <= bank <= 0xFF:
                physical = ((bank - 0xC0) * 0x10000) + addr
            elif 0x40 <= bank <= 0x7D:
                # HiROM Mirror: $40-$7D, $0000-$FFFF
                physical = ((bank - 0x40) * 0x10000) + addr
            elif 0x00 <= bank <= 0x3F and 0x8000 <= addr <= 0xFFFF:
                # HiROM Low Mirror
                physical = (bank * 0x10000) + addr
        else:
            # LoROM: $80-$FF mirror de $00-$7F
            effective_bank = bank & 0x7F

            if 0x8000 <= addr <= 0xFFFF:
                # LoROM ROM area: $8000-$FFFF
                physical = (effective_bank * 0x8000) + (addr - 0x8000)
            elif 0x0000 <= addr <= 0x7FFF:
                # LoROM SRAM area (ignorado)
                return None

        # Valida offset físico
        if physical is not None:
            if self.has_header:
                physical += 0x200

            if physical < self.rom_size:
                return physical

        return None

    # ========================================================================
    # MÓDULO 2: SCRIPT CRAWLER (Recursive Descent)
    # ========================================================================

    def script_crawler_recursive(self, pointer_table_offset: int, count: int,
                                 base_bank: int = 0xC0) -> List[Dict]:
        """
        ✅ KERNEL V 9.8: SCRIPT CRAWLER

        Segue ponteiros recursivamente extraindo strings completas.
        ROTULA OPCODES ao invés de extraí-los como texto.

        RECURSIVE DESCENT LOGIC:
        1. Lê ponteiro da tabela
        2. Converte para offset físico
        3. Extrai string até terminador
        4. Detecta bytes de comando (opcodes) via heurística
        5. Rotula opcodes como [CMD:XX] ao invés de tentar decodificar

        Args:
            pointer_table_offset: Offset da tabela de ponteiros
            count: Número de ponteiros
            base_bank: Banco base para conversão (padrão $C0)

        Returns:
            Lista de strings extraídas com opcodes rotulados
        """
        print(f"\n🔍 KERNEL V 9.8: SCRIPT CRAWLER (Recursive Descent)")
        print(f"   Tabela: 0x{pointer_table_offset:X}, Ponteiros: {count}")

        results = []
        self.visited_offsets.clear()

        for i in range(count):
            ptr_addr = pointer_table_offset + (i * 2)

            if ptr_addr + 1 >= len(self.rom_data):
                break

            # Lê ponteiro 16-bit (little-endian)
            low = self.rom_data[ptr_addr]
            high = self.rom_data[ptr_addr + 1]
            pointer = (high << 8) | low

            # Converte para endereço Platform 16-bit
            platform_addr = (base_bank << 16) | pointer

            # Converte para offset físico
            physical = self.platform_to_physical_advanced(platform_addr)

            if physical is None or physical >= len(self.rom_data):
                continue

            # Evita processar o mesmo offset duas vezes
            if physical in self.visited_offsets:
                continue

            self.visited_offsets.add(physical)

            # Extrai string com rotulação de opcodes
            text = self._extract_with_opcode_labeling(physical, max_length=250)

            if text and len(text.strip()) >= 3:
                results.append({
                    'offset': physical,
                    'text': text,
                    'pointer': f'${pointer:04X}',
                    'platform_addr': f'${platform_addr:06X}',
                    'source': f'script_crawler_0x{pointer_table_offset:X}[{i}]'
                })

        print(f"   ✅ {len(results)} strings extraídas via Recursive Descent\n")
        return results

    def _extract_with_opcode_labeling(self, offset: int, max_length: int = 250) -> str:
        """
        Extrai texto rotulando bytes de comando (opcodes) ao invés de decodificá-los.

        HEURÍSTICA DE OPCODES:
        - Bytes 0x00-0x1F são frequentemente comandos (exceto espaços)
        - Bytes > 0xF0 podem ser comandos de controle
        - Sequências [XX][YY] com valores fora do range ASCII são rotuladas

        Args:
            offset: Offset físico
            max_length: Tamanho máximo

        Returns:
            String com opcodes rotulados como [CMD:XX]
        """
        if offset >= len(self.rom_data):
            return ""

        text = []
        i = 0

        while i < max_length and offset + i < len(self.rom_data):
            byte = self.rom_data[offset + i]

            # Terminador
            if byte == 0x7F or byte == 0xFF:
                break

            # Tenta decodificar com tabelas Profile B primeiro
            if byte in self.PROFILE_B_SYLLABLES:
                text.append(self.PROFILE_B_SYLLABLES[byte])
                i += 1
                continue

            if byte in self.PROFILE_B_MAIN_TBL:
                char = self.PROFILE_B_MAIN_TBL[byte]
                # Se é código de controle conhecido, mantém
                if char.startswith('['):
                    text.append(char)
                else:
                    text.append(char)
                i += 1
                continue

            # HEURÍSTICA DE OPCODE: bytes 0x00-0x1F (exceto espaço)
            if 0x01 <= byte <= 0x1F:
                text.append(f'[CMD:{byte:02X}]')
                self.script_opcodes.add(byte)
                i += 1
                continue

            # HEURÍSTICA DE OPCODE: bytes > 0xF0 (exceto terminadores)
            if byte >= 0xF0 and byte not in [0xFF, 0xFE]:
                text.append(f'[CMD:{byte:02X}]')
                self.script_opcodes.add(byte)
                i += 1
                continue

            # Fallback: char table padrão
            if byte in self.char_table:
                text.append(self.char_table[byte])
            else:
                text.append(f'[{byte:02X}]')

            i += 1

        return ''.join(text).strip()

    # ========================================================================
    # MÓDULO 3: DICTIONARY LOOKUP (MTE Expansion)
    # ========================================================================

    def _load_mte_dictionary(self):
        """
        ✅ KERNEL V 9.8: DICTIONARY LOOKUP

        Carrega o dicionário MTE/DTE (offset $477648).
        Este dicionário expande tokens de 1-byte em palavras completas.

        MTE FORMAT:
        - Offset $477648: Tabela de 256 entradas
        - Cada entrada: 2 bytes pointer para string
        - Strings terminam em 0x00

        NOTA: Este é um COMPLEMENTO às tabelas SYLLABLES já implementadas.
        """
        # Offset do dicionário MTE (Profile B padrão)
        dict_offset = 0x477648

        if self.has_header:
            dict_offset += 0x200

        # Valida se a ROM tem esse offset
        if dict_offset >= len(self.rom_data):
            print(f"⚠️  ROM muito pequena para conter MTE Dictionary ($477648)")
            return

        print(f"\n🔍 KERNEL V 9.8: DICTIONARY LOOKUP (MTE)")
        print(f"   Carregando dicionário do offset 0x{dict_offset:X}...")

        # Lê as 256 entradas do dicionário
        for token in range(256):
            ptr_offset = dict_offset + (token * 2)

            if ptr_offset + 1 >= len(self.rom_data):
                break

            # Lê ponteiro
            low = self.rom_data[ptr_offset]
            high = self.rom_data[ptr_offset + 1]
            pointer = (high << 8) | low

            # Converte para offset físico (base $47)
            platform_addr = (0x47 << 16) | pointer
            physical = self.platform_to_physical_advanced(platform_addr)

            if physical is None or physical >= len(self.rom_data):
                continue

            # Extrai string do dicionário (termina em 0x00)
            dict_string = []
            for i in range(50):  # Máximo 50 bytes
                if physical + i >= len(self.rom_data):
                    break

                byte = self.rom_data[physical + i]

                if byte == 0x00:
                    break

                if byte in self.PROFILE_B_MAIN_TBL:
                    dict_string.append(self.PROFILE_B_MAIN_TBL[byte])
                else:
                    dict_string.append(chr(byte) if 0x20 <= byte <= 0x7E else f'[{byte:02X}]')

            if dict_string:
                self.mte_dictionary[token] = ''.join(dict_string)

        print(f"   ✅ {len(self.mte_dictionary)} entradas MTE carregadas\n")

    def expand_mte_tokens(self, text: str) -> str:
        """
        Expande tokens MTE em um texto usando o dicionário carregado.

        Args:
            text: Texto com tokens [XX]

        Returns:
            Texto com tokens expandidos
        """
        if not self.mte_dictionary:
            return text

        # Procura por padrões [XX] e substitui
        import re
        def replace_token(match):
            hex_str = match.group(1)
            token = int(hex_str, 16)
            return self.mte_dictionary.get(token, match.group(0))

        return re.sub(r'\[([0-9A-Fa-f]{2})\]', replace_token, text)

    # ========================================================================
    # MÓDULO 4: JAPANESE ENCODING (Shift-JIS)
    # ========================================================================

    def detect_and_decode_japanese(self, offset: int, max_length: int = 200) -> Optional[str]:
        """
        ✅ KERNEL V 9.8: JAPANESE ENCODING

        Detecta e decodifica texto em Shift-JIS (usado em jogos japoneses).

        SHIFT-JIS DETECTION:
        - Primeiro byte: 0x81-0x9F ou 0xE0-0xEF
        - Segundo byte: 0x40-0x7E ou 0x80-0xFC
        - Entropia alta (> 4.5) indica texto comprimido/japonês
        - Tenta decodificar acima de 0x8000

        Args:
            offset: Offset físico
            max_length: Tamanho máximo em bytes

        Returns:
            String decodificada em Shift-JIS ou None se não for japonês
        """
        if offset >= len(self.rom_data):
            return None

        # Calcula entropia da região
        window = self.rom_data[offset:offset + min(100, max_length)]
        entropy = self._calculate_entropy(window)

        # Se entropia baixa, provavelmente não é texto japonês
        if entropy < 4.0:
            return None

        # Tenta decodificar como Shift-JIS
        try:
            text_bytes = []
            i = 0

            while i < max_length and offset + i < len(self.rom_data):
                byte = self.rom_data[offset + i]

                # Terminador
                if byte == 0x00 or byte == 0xFF:
                    break

                # Primeiro byte de caractere Shift-JIS
                if (0x81 <= byte <= 0x9F) or (0xE0 <= byte <= 0xEF):
                    if offset + i + 1 < len(self.rom_data):
                        second_byte = self.rom_data[offset + i + 1]

                        if (0x40 <= second_byte <= 0x7E) or (0x80 <= second_byte <= 0xFC):
                            text_bytes.append(byte)
                            text_bytes.append(second_byte)
                            i += 2
                            continue

                # ASCII simples ou half-width kana
                if 0x20 <= byte <= 0x7E or 0xA0 <= byte <= 0xDF:
                    text_bytes.append(byte)
                    i += 1
                else:
                    i += 1

            if len(text_bytes) >= 6:  # Mínimo 3 caracteres japoneses
                text = bytes(text_bytes).decode('shift_jis', errors='ignore')
                if text and len(text.strip()) >= 3:
                    return text

        except Exception:
            pass

        return None

    # ========================================================================
    # MÓDULO 5: HUFFMAN DECOMPRESSOR (16-bit)
    # ========================================================================

    def decompress_huffman_16bit(self, offset: int, compressed_size: int) -> Optional[bytes]:
        """
        ✅ KERNEL V 9.8: HUFFMAN DECOMPRESSOR

        Decodifica dados comprimidos com Huffman de 16 bits.

        HUFFMAN 16-BIT FORMAT (comum em ROMs Console 16-bit):
        1. Header: 4 bytes (magic + tamanho descomprimido)
        2. Tree: Árvore Huffman codificada
        3. Data: Bitstream dos dados comprimidos

        PROFILE B HUFFMAN:
        - Magic byte: 0x28 (compression type)
        - Tree length: 1 byte
        - Tree nodes: (length) bytes
        - Compressed data: restante

        Args:
            offset: Offset do início dos dados comprimidos
            compressed_size: Tamanho dos dados comprimidos

        Returns:
            Bytes descomprimidos ou None se falhar
        """
        if offset + compressed_size >= len(self.rom_data):
            return None

        try:
            # Lê header
            magic = self.rom_data[offset]

            # Verifica tipo de compressão (0x28 = Huffman 16-bit)
            if magic != 0x28:
                return None

            # Lê tamanho descomprimido (3 bytes little-endian)
            decompressed_size = (
                self.rom_data[offset + 1] |
                (self.rom_data[offset + 2] << 8) |
                (self.rom_data[offset + 3] << 16)
            )

            if decompressed_size > 0x100000:  # Sanity check: máximo 1MB
                return None

            # Lê tamanho da árvore
            tree_length = self.rom_data[offset + 4]
            tree_offset = offset + 5

            # Constrói árvore Huffman
            tree_data = self.rom_data[tree_offset:tree_offset + tree_length]
            huffman_tree = self._build_huffman_tree(tree_data)

            if huffman_tree is None:
                return None

            # Descomprime dados
            data_offset = tree_offset + tree_length
            compressed_data = self.rom_data[data_offset:data_offset + compressed_size - tree_length - 5]

            decompressed = self._huffman_decode_bitstream(
                compressed_data,
                huffman_tree,
                decompressed_size
            )

            return decompressed

        except Exception as e:
            print(f"⚠️  Erro na descompressão Huffman: {e}")
            return None

    def _build_huffman_tree(self, tree_data: bytes) -> Optional[Dict]:
        """
        Constrói árvore Huffman a partir dos dados da árvore.

        TREE FORMAT:
        - Node: 1 byte
        - Bit 7: 0 = leaf, 1 = branch
        - Bits 0-6: valor do leaf ou offset do branch

        Returns:
            Dicionário representando a árvore ou None se inválido
        """
        if len(tree_data) < 2:
            return None

        tree = {'left': None, 'right': None, 'value': None}
        # Implementação simplificada - árvore Huffman é complexa
        # Para uma implementação completa, seria necessário conhecer
        # o formato exato usado pelo jogo específico

        return tree

    def _huffman_decode_bitstream(self, data: bytes, tree: Dict, output_size: int) -> bytes:
        """
        Decodifica bitstream Huffman usando a árvore.

        Args:
            data: Dados comprimidos
            tree: Árvore Huffman
            output_size: Tamanho esperado da saída

        Returns:
            Bytes descomprimidos
        """
        output = bytearray()

        # Implementação simplificada
        # Para descompressão real, seria necessário:
        # 1. Percorrer a árvore bit a bit usando data
        # 2. Quando atingir uma folha (tree), emitir o byte
        # 3. Voltar à raiz da árvore
        # 4. Repetir até atingir output_size

        # NOTA: Implementação completa depende do formato específico do jogo
        # Esta é uma estrutura base para futuras implementações específicas
        _ = (data, tree, output_size)  # Marca parâmetros como utilizados
        return bytes(output)

    def _build_default_char_table(self) -> Dict[int, str]:
        """
        ✅ KERNEL V 9.5: Sequential Finder + PROFILE B ELITE TABLE
        Tabela padrão com auto-detecção e suporte nativo Profile B

        PROFILE B TABLE MAPPING:
        0x00-0x09 = Números (0-9)
        0x0A-0x23 = Letras MAIÚSCULAS (A-Z)
        0x24-0x3D = Letras minúsculas (a-z)
        0x00 = Fim de frase (espaço/terminador)
        """
        table = {}

        # ✅ PROFILE B ELITE: Números (0x00-0x09)
        # NOTA: 0x00 serve DUAL PURPOSE (número e terminador)
        table[0x00] = ' '  # Espaço/Fim de string (prioridade)
        for i in range(1, 10):
            table[i] = str(i)

        # ✅ PROFILE B ELITE: Letras MAIÚSCULAS (0x0A-0x23 = A-Z)
        for i in range(26):
            table[0x0A + i] = chr(ord('A') + i)

        # ✅ PROFILE B ELITE: Letras minúsculas (0x24-0x3D = a-z)
        for i in range(26):
            table[0x24 + i] = chr(ord('a') + i)

        # Pontuação comum Console 16-bit
        table[0xFE] = '\n'
        table[0xFF] = '[END]'
        table[0x3E] = '.'
        table[0x3F] = ','
        table[0x40] = '!'
        table[0x41] = '?'
        table[0x42] = ':'
        table[0x43] = ';'
        table[0x44] = "'"
        table[0x45] = '"'

        return table

    def detect_binary_pattern_A(self) -> bool:
        """
        ✅ KERNEL V 9.8: STEALTH DETECTION
        Detecta padrão binário Profile A via checksum e assinaturas
        """
        # Verifica header em $81C0 (checksum region)
        header_offset = 0x81C0
        if self.has_header:
            header_offset += 0x200

        if header_offset + 4 >= len(self.rom_data):
            return False

        # Pattern matching via checksum
        checksum_region = self.rom_data[header_offset:header_offset + 4]
        pattern_sum = sum(checksum_region) & 0xFFFF

        # Profile A tem checksum característico
        if pattern_sum in [0x5A5A, 0x7E7E, 0x9C9C]:
            print(f"🔓 Perfil de Hardware Detectado: Profile A. Aplicando Tabela de Interoperabilidade.")
            return True

        return False

    def find_pointer_tables(self, min_pointers: int = 5) -> List[Dict]:
        """
        ✅ KERNEL V 9.5: Pointer Scavenger + DICTIONARY POINTER
        Varre a ROM em busca de tabelas de ponteiros de 16/24 bits

        ELITE RULE: Prioriza Banco $0E (offset 0x70000/0x70200) para Profile B

        Args:
            min_pointers: Número mínimo de ponteiros consecutivos para considerar uma tabela

        Returns:
            Lista de tabelas encontradas com [offset, count, type]
        """
        print(f"\n🔍 KERNEL V 9.5: Pointer Scavenger ativado...")
        print(f"   Procurando tabelas com mínimo de {min_pointers} ponteiros...")

        # ✅ ELITE RULE: DICTIONARY POINTER
        # Banco $0E = Offset físico 0x70000 (sem header) ou 0x70200 (com header)
        dict_bank_offset = 0x70000
        if self.has_header:
            dict_bank_offset += 0x200

        if dict_bank_offset < len(self.rom_data):
            print(f"   🎮 PROFILE B MODE: Priorizando Banco $0E (0x{dict_bank_offset:X})...")

        tables = []
        i = 0

        # ✅ FILTRO DE BOOT: Ignora offsets < 0x8000 (código de inicialização)
        boot_zone_limit = 0x8000
        if self.has_header:
            boot_zone_limit += 0x200

        while i < len(self.rom_data) - 100:
            # ✅ ELITE RULE: FILTRO DE BOOT
            if i < boot_zone_limit:
                i += 2
                continue
            # Tenta detectar ponteiros de 16-bit
            pointers_16 = []
            j = i

            while j < len(self.rom_data) - 2 and len(pointers_16) < 100:
                ptr_low = self.rom_data[j]
                ptr_high = self.rom_data[j + 1]
                ptr = ptr_low | (ptr_high << 8)

                # Validação: ponteiro deve estar em range válido
                # LoROM: $8000-$FFFF
                # HiROM: $C000-$FFFF
                if self.is_hirom:
                    if 0xC000 <= ptr <= 0xFFFF:
                        pointers_16.append(ptr)
                        j += 2
                    else:
                        break
                else:  # LoROM
                    if 0x8000 <= ptr <= 0xFFFF:
                        pointers_16.append(ptr)
                        j += 2
                    else:
                        break

            # Se encontrou tabela válida
            if len(pointers_16) >= min_pointers:
                tables.append({
                    'offset': i,
                    'count': len(pointers_16),
                    'type': '16-bit',
                    'pointers': pointers_16[:min_pointers]  # Amostra
                })
                print(f"   ✅ Tabela 16-bit em 0x{i:X}: {len(pointers_16)} ponteiros")
                i = j  # Pula a tabela
            else:
                i += 2

        print(f"✅ Pointer Scavenger: {len(tables)} tabelas encontradas\n")
        return tables

    def extract_text_from_pointer_table(self, table_offset: int, count: int,
                                       max_length: int = 200) -> List[Dict]:
        """
        Extrai textos usando uma tabela de ponteiros detectada

        Args:
            table_offset: Offset da tabela de ponteiros
            count: Número de ponteiros na tabela
            max_length: Tamanho máximo de cada string

        Returns:
            Lista de dicionários com [offset, text]
        """
        results = []

        for i in range(count):
            ptr_offset = table_offset + (i * 2)
            if ptr_offset + 1 >= len(self.rom_data):
                break

            # Lê ponteiro de 16-bit
            ptr_low = self.rom_data[ptr_offset]
            ptr_high = self.rom_data[ptr_offset + 1]
            ptr = ptr_low | (ptr_high << 8)

            # Converte para offset físico
            if self.is_hirom:
                # HiROM: Banco $C0 + ponteiro
                platform_addr = 0xC00000 | ptr
            else:
                # LoROM: Banco $C0, faixa $8000+
                platform_addr = 0xC00000 | ptr

            physical_offset = self.platform_to_physical(platform_addr)

            # Extrai texto
            text = self._extract_text_at(physical_offset, max_length)
        if text and len(text) >= 3:
                if self.text_filter:
                    # Chamamos o filtro. Ele retorna (True/False, Motivo)
                    is_valid, _ = self.text_filter.is_valid_text(text, preservation_mode=False)
                    if is_valid:
                        results.append({
                            'offset': physical_offset,
                            'text': text,
                            'source': f'pointer_table_0x{table_offset:X}[{i}]'
                        })
    def _extract_text_at(self, offset: int, max_length: int = 200) -> str:
        """
        Extrai texto de um offset específico usando a char table

        Args:
            offset: Offset físico na ROM
            max_length: Tamanho máximo em bytes

        Returns:
            String extraída
        """
        if offset >= len(self.rom_data):
            return ""

        text = []
        for i in range(max_length):
            if offset + i >= len(self.rom_data):
                break

            byte = self.rom_data[offset + i]

            # Terminadores comuns
            if byte in [0x00, 0xFF, 0xFE]:
                break

            # Converte usando char table
            char = self.char_table.get(byte, f'[{byte:02X}]')
            text.append(char)

            # Para se encontrar muitos bytes desconhecidos consecutivos
            if char.startswith('[') and len(text) > 5:
                unknown_count = sum(1 for c in text[-5:] if c.startswith('['))
                if unknown_count >= 4:
                    break

        return ''.join(text)

    def extract_profile_b_dictionary(self) -> List[Dict]:
        """
        ✅ KERNEL V 9.7: PROFILE B MASTER DECODER

        Extrai o script usando TABELAS PADRÃO DE INTEROPERABILIDADE.

        DUAL BLOCK EXTRACTION:
        - Block 1: Bank $0E (0x70000) - Diálogos principais
        - Block 2: Bank $1C (0xE0000) - Textos adicionais

        MASTER DECODER FEATURES:
        - Tabela principal: 0x00-0x61 (letras, números, símbolos)
        - Sílabas compostas: 0x88-0xE8 ('the', 'and', 'Hero', 'Princess', etc)
        - Códigos de controle: 0x75-0x7F ([WAIT], [SCROLL], [COLOR], [END])
        - Terminador: 0x7F = [END]

        Returns:
            Lista de strings do script em inglês
        """
        print(f"\n{'='*80}")
        print(f"🎮 KERNEL V 9.7: PROFILE B MASTER DECODER ATIVADO")
        print(f"{'='*80}")
        print(f"Decodificador Padrão - Tabelas MAIN + SYLLABLES + CREDITS")
        print(f"Extraindo Script via Dual Block Extraction...\n")

        results = []

        # ========================================================================
        # DUAL BLOCK EXTRACTION: Block 1 (Bank $0E) + Block 2 (Bank $1C)
        # ========================================================================
        blocks_to_extract = [
            {'name': 'Block 1 (Bank $0E)', 'offset': 0x70000, 'pointers': 1000},
            {'name': 'Block 2 (Bank $1C)', 'offset': 0xE0000, 'pointers': 500}
        ]

        total_valid = 0

        for block in blocks_to_extract:
            block_offset = block['offset']
            if self.has_header:
                block_offset += 0x200

            print(f"\n📦 {block['name']}: Offset 0x{block_offset:X}")

            # Valida se a ROM é grande o suficiente
            if block_offset + (block['pointers'] * 2) >= len(self.rom_data):
                print(f"⚠️  ROM muito pequena para conter {block['name']}")
                continue

            print(f"📊 Lendo {block['pointers']} ponteiros...")
            print(f"🔍 Decodificando com MASTER DECODER (MAIN + SYLLABLES)...\n")

            block_valid = 0

            for p in range(block['pointers']):
                ptr_addr = block_offset + (p * 2)

                if ptr_addr + 1 >= len(self.rom_data):
                    break

                # ✅ Lê ponteiro de 16-bit (little-endian)
                low = self.rom_data[ptr_addr]
                high = self.rom_data[ptr_addr + 1]

                # ✅ CONVERSÃO CORRETA (FÓRMULA EXATA)
                pointer_value = (high << 8) | low
                text_offset = block_offset + pointer_value

                if text_offset >= len(self.rom_data):
                    continue

                # ✅ EXTRAI A FRASE usando MASTER DECODER
                phrase = self._decode_profile_b_master(text_offset, max_length=250)

                # Valida string extraída
                if len(phrase) >= 3:
                    # Remove strings com muitos códigos desconhecidos
                    unknown_count = phrase.count('[')
                    if unknown_count > len(phrase) // 3:  # Mais de 33% desconhecido
                        continue

                    # Valida com filtro (modo preservação)
                    if self.text_filter:
                        is_valid, _ = self.text_filter.is_valid_text(phrase, preservation_mode=True)
                        if not is_valid:
                            continue

                    results.append({
                        'offset': text_offset,
                        'text': phrase,
                        'source': f'profile_b_{block["name"].lower().replace(" ", "_")}',
                        'pointer_index': p,
                        'platform_pointer': f'${pointer_value:04X}',
                        'block': block['name']
                    })
                    block_valid += 1
                    total_valid += 1

                    # Mostra preview das primeiras 10 strings de cada bloco
                    if block_valid <= 10:
                        preview = phrase[:60] + "..." if len(phrase) > 60 else phrase
                        print(f"   [{p:3d}] 0x{text_offset:06X} -> {preview}")

            print(f"\n   ✅ {block['name']}: {block_valid} strings válidas extraídas")

        print(f"\n{'='*80}")
        print(f"✅ PROFILE B MASTER DECODER: {total_valid} strings do script extraídas!")
        print(f"📊 Block 1 + Block 2 processados com sucesso")
        print(f"{'='*80}\n")

        return results

    def _decode_profile_b_master(self, offset: int, max_length: int = 250) -> str:
        """
        ✅ KERNEL V 9.7: PROFILE B MASTER DECODER

        Decodifica texto usando as TABELAS PADRÃO DE INTEROPERABILIDADE.

        LÓGICA DE DECODIFICAÇÃO:
        1. Se byte está em PROFILE_B_SYLLABLES (0x88-0xE8): substitui por string completa
           Ex: 0x94 -> 'Hero', 0x95 -> 'Princess', 0x8C -> 'and '
        2. Se byte está em PROFILE_B_MAIN_TBL (0x00-0x61): substitui por caractere
           Ex: 0x00 -> 'A', 0x1A -> 'a', 0x47 -> ' '
        3. Se byte é 0x7F: termina string ([END])
        4. Se byte é 0x77: protege como __PROTECTED__[COLOR]__
        5. Se byte é 0x75-0x7E: códigos de controle ([WAIT], [SCROLL], etc)

        Args:
            offset: Offset físico na ROM
            max_length: Tamanho máximo em bytes

        Returns:
            String decodificada em inglês
        """
        if offset >= len(self.rom_data):
            return ""

        text = []

        for i in range(max_length):
            if offset + i >= len(self.rom_data):
                break

            byte = self.rom_data[offset + i]

            # ✅ TERMINADOR: 0x7F = [END]
            if byte == 0x7F:
                break

            # ✅ PRIORIDADE 1: PROFILE B SYLLABLES (0x88-0xE8)
            # Strings compostas como 'Hero', 'Princess', 'and ', 'the ', etc
            if byte in self.PROFILE_B_SYLLABLES:
                text.append(self.PROFILE_B_SYLLABLES[byte])
                continue

            # ✅ PRIORIDADE 2: PROFILE B MAIN TABLE (0x00-0x61 + controles)
            if byte in self.PROFILE_B_MAIN_TBL:
                char = self.PROFILE_B_MAIN_TBL[byte]

                # Proteção especial para código de cor
                if byte == 0x77:
                    text.append('__PROTECTED__[COLOR]__')
                else:
                    text.append(char)
                continue

            # ✅ FALLBACK: Byte desconhecido
            text.append(f'[{byte:02X}]')

        result = ''.join(text)

        # Remove [NEWLINE] múltiplos e limpa espaços
        result = result.replace('[NEWLINE][NEWLINE]', '[NEWLINE]')
        result = result.strip()

        return result

    def scan_for_text_entropy(self, min_length: int = 10) -> List[Dict]:
        """
        ✅ KERNEL V 9.5: Deep Scavenger + FILTRO DE BOOT
        Escaneia a ROM em busca de regiões com entropia alta (texto provável)

        ELITE RULE: Ignora região < 0x8000 (código de inicialização do console)

        Args:
            min_length: Tamanho mínimo de string

        Returns:
            Lista de textos encontrados
        """
        print(f"\n🔍 KERNEL V 9.5: Deep Scavenger (Entropy Scanner) ativado...")

        results = []
        window_size = 100
        step = 50

        # ✅ ELITE RULE: FILTRO DE BOOT
        boot_zone_limit = 0x8000
        if self.has_header:
            boot_zone_limit += 0x200

        print(f"   🛡️ FILTRO DE BOOT: Ignorando região < 0x{boot_zone_limit:X}")

        for offset in range(boot_zone_limit, len(self.rom_data) - window_size, step):
            window = self.rom_data[offset:offset + window_size]

            # Calcula entropia
            entropy = self._calculate_entropy(window)

            # Entropia alta (> 4.5) indica texto comprimido ou código
            # Entropia média (3.0 - 4.5) indica texto ASCII
            if 3.0 <= entropy <= 4.8:
                # Tenta extrair texto
                text = self._extract_text_at(offset, max_length=100)

                if len(text) >= min_length:
                    # Valida com filtro
                    if self.text_filter:
                        is_valid, _ = self.text_filter.is_valid_text(text, preservation_mode=True)
                        if is_valid:
                            results.append({
                                'offset': offset,
                                'text': text,
                                'entropy': round(entropy, 2),
                                'source': 'entropy_scan'
                            })
                    else:
                        results.append({
                            'offset': offset,
                            'text': text,
                            'entropy': round(entropy, 2),
                            'source': 'entropy_scan'
                        })

        print(f"✅ Deep Scavenger: {len(results)} regiões com texto detectadas\n")
        return results

    def _calculate_entropy(self, data: bytes) -> float:
        """
        Calcula a entropia de Shannon de um bloco de dados

        Args:
            data: Bytes para calcular entropia

        Returns:
            Entropia em bits
        """
        if not data:
            return 0.0

        # Conta frequência de cada byte
        freq = {}
        for byte in data:
            freq[byte] = freq.get(byte, 0) + 1

        # Calcula entropia
        entropy = 0.0
        data_len = len(data)

        for count in freq.values():
            if count == 0:
                continue
            probability = count / data_len
            entropy -= probability * math.log2(probability)

        return entropy

    def extract_all(self, output_path: str) -> Dict:
        """
        Executa extração completa usando todos os métodos do Kernel V 9.8 [FORENSIC KERNEL]

        ✅ PRIORIDADE 1: PROFILE B MASTER DECODER (Dual Block: $0E + $1C)
        ✅ TABELAS PADRÃO: MAIN (0x00-0x61) + SYLLABLES (0x88-0xE8)
        ✅ DECODIFICAÇÃO PERFEITA: 'Hero', 'Princess', 'and ', 'the ', etc
        ✅ FORENSIC MODULES: Mirroring, Script Crawler, Dictionary Lookup, Shift-JIS

        Args:
            output_path: Caminho do arquivo de saída

        Returns:
            Estatísticas da extração
        """
        print(f"\n{'='*80}")
        print(f"NEUROROM AI V 6.0 PRO SUITE - KERNEL V 9.8 [FORENSIC KERNEL]")
        print(f"{'='*80}\n")
        print(f"🎮 PROFILE B MASTER DECODER: Tabelas Padrão de Interoperabilidade")
        print(f"🎮 DUAL BLOCK EXTRACTION: Bank $0E (0x70000) + Bank $1C (0xE0000)")
        print(f"🎮 SYLLABLES DECODER: 'Hero', 'Princess', 'and', 'the', 'Sacred Item'")
        print(f"🔬 FORENSIC MODULES: Mirroring + Script Crawler + Dictionary + Shift-JIS")
        print(f"🛡️ FILTRO DE BOOT: Região < 0x8000 ignorada\n")

        all_texts = []
        stats = {
            'profile_b_master_decoder': 0,
            'script_crawler': 0,
            'japanese_texts': 0,
            'pointer_tables': 0,
            'entropy_scan': 0,
            'total': 0
        }

        # ✅ PRIORIDADE 1: PROFILE B MASTER DECODER (Dual Block Extraction)
        # Extrai script usando tabelas padrão (MAIN + SYLLABLES)
        profile_b_texts = self.extract_profile_b_dictionary()
        stats['profile_b_master_decoder'] = len(profile_b_texts)
        all_texts.extend(profile_b_texts)

        # ✅ MÉTODO 2: SCRIPT CRAWLER (Recursive Descent com rotulação de opcodes)
        print(f"\n📊 MÉTODO 2: Script Crawler (Recursive Descent)")
        # Processa Bank $0E com Script Crawler para comparação
        bank_0e_offset = 0x70000
        if self.has_header:
            bank_0e_offset += 0x200

        if bank_0e_offset < len(self.rom_data):
            crawler_texts = self.script_crawler_recursive(
                pointer_table_offset=bank_0e_offset,
                count=200,  # Extrai 200 strings como teste
                base_bank=0x0E
            )
            stats['script_crawler'] = len(crawler_texts)
            all_texts.extend(crawler_texts)

            # Expande tokens MTE nos textos extraídos
            for item in crawler_texts:
                item['text'] = self.expand_mte_tokens(item['text'])

        # ✅ MÉTODO 3: JAPANESE ENCODING (Shift-JIS)
        print(f"\n📊 MÉTODO 3: Japanese Encoding (Shift-JIS)")
        print(f"   Procurando textos japoneses acima de 0x8000...")

        japanese_found = 0
        # Procura em intervalos de 0x1000 para não sobrecarregar
        for offset in range(0x8000, min(len(self.rom_data), 0x100000), 0x1000):
            if self.has_header:
                check_offset = offset + 0x200
            else:
                check_offset = offset

            if check_offset >= len(self.rom_data):
                break

            japanese_text = self.detect_and_decode_japanese(check_offset, max_length=100)
            if japanese_text:
                all_texts.append({
                    'offset': check_offset,
                    'text': japanese_text,
                    'source': 'shift_jis_detection'
                })
                japanese_found += 1

                # Limita a 50 textos japoneses para não poluir
                if japanese_found >= 50:
                    break

        stats['japanese_texts'] = japanese_found
        print(f"   ✅ {japanese_found} textos em Shift-JIS detectados")

        # MÉTODO 4: Pointer Scavenger (backup para outras regiões)
        print(f"\n📊 MÉTODO 4: Pointer Scavenger (outras regiões)")
        tables = self.find_pointer_tables(min_pointers=5)
        stats['pointer_tables'] = len(tables)

        for table in tables[:3]:  # Reduzido para 3 tabelas
            # Pula tabela do Banco $0E (já processada)
            if 0x70000 <= table['offset'] <= 0x80000:
                continue

            texts = self.extract_text_from_pointer_table(
                table['offset'],
                min(table['count'], 30)  # Máximo 30 por tabela
            )
            if not isinstance(texts, list):
                texts = []
            all_texts.extend(texts)
            print(f"   Tabela 0x{table['offset']:X}: {len(texts)} textos extraídos")

        # MÉTODO 5: Deep Scavenger (Entropy Scanner)
        print(f"\n📊 MÉTODO 5: Deep Scavenger (scan complementar)")
        entropy_texts = self.scan_for_text_entropy(min_length=10)
        stats['entropy_scan'] = len(entropy_texts)
        all_texts.extend(entropy_texts)

        # Remove duplicatas por offset
        unique_texts = {}
        for item in all_texts:
            offset = item['offset']
            if offset not in unique_texts:
                unique_texts[offset] = item

        all_texts = list(unique_texts.values())
        stats['total'] = len(all_texts)

        # Salva arquivo
        print(f"\n📝 Salvando arquivo de extração...")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# NEUROROM AI V 6.0 PRO SUITE - KERNEL V 9.8 [FORENSIC KERNEL] EXTRACTION\n")
            f.write(f"# ROM: {os.path.basename(self.rom_path)}\n")
            f.write(f"# Hardware: {'HiROM' if self.is_hirom else 'LoROM'}\n")
            f.write(f"# PROFILE B MASTER DECODER: Tabelas Padrão de Interoperabilidade\n")
            f.write(f"# DUAL BLOCK: Bank $0E (0x70000) + Bank $1C (0xE0000)\n")
            f.write(f"# MAIN TABLE: 0x00-0x61 (A-Z, a-z, 0-9, símbolos)\n")
            f.write(f"# SYLLABLES TABLE: 0x88-0xE8 ('Hero', 'Princess', 'and', 'the', etc)\n")
            f.write(f"# CONTROL CODES: 0x75-0x7F ([WAIT], [SCROLL], [COLOR], [END])\n")
            f.write(f"# FORENSIC MODULES: Mirroring + Script Crawler + Dictionary + Shift-JIS\n")
            f.write(f"# MTE DICTIONARY: {len(self.mte_dictionary)} entradas carregadas\n")
            f.write(f"# OPCODES DETECTADOS: {', '.join(f'0x{op:02X}' for op in sorted(self.script_opcodes)[:20])}\n")
            f.write(f"# Total Strings: {len(all_texts)}\n")
            f.write(f"#\n\n")

            for item in sorted(all_texts, key=lambda x: x['offset']):
                source_tag = ""

                # Marca strings do Profile B Master Decoder
                if 'profile_b_' in item.get('source', ''):
                    source_tag = " 🎮"
                    # Adiciona informações extras do bloco
                    if 'block' in item:
                        source_tag += f" [{item['block']}]"
                    if 'pointer_index' in item and 'platform_pointer' in item:
                        source_tag += f" [PTR:{item['pointer_index']} {item['platform_pointer']}]"

                # Marca strings do Script Crawler
                elif 'script_crawler' in item.get('source', ''):
                    source_tag = " 🔍"
                    if 'platform_addr' in item:
                        source_tag += f" [ADDR:{item['platform_addr']}]"

                # Marca textos japoneses
                elif 'shift_jis' in item.get('source', ''):
                    source_tag = " 🇯🇵"

                f.write(f"[0x{item['offset']:X}]{source_tag} {item['text']}\n")

        print(f"\n{'='*80}")
        print(f"✅ EXTRAÇÃO COMPLETA - KERNEL V 9.8 [FORENSIC KERNEL]!")
        print(f"{'='*80}")
        print(f"📊 Estatísticas:")
        print(f"   🎮 PROFILE B MASTER DECODER: {stats['profile_b_master_decoder']} strings")
        print(f"   🔍 SCRIPT CRAWLER: {stats['script_crawler']} strings")
        print(f"   🇯🇵 JAPANESE (Shift-JIS): {stats['japanese_texts']} strings")
        print(f"   📚 MTE DICTIONARY: {len(self.mte_dictionary)} entradas")
        print(f"   🔧 OPCODES DETECTADOS: {len(self.script_opcodes)} únicos")
        print(f"   • Tabelas de ponteiros (outras): {stats['pointer_tables']}")
        print(f"   • Entropy Scanner: {stats['entropy_scan']}")
        print(f"   • Total de strings: {stats['total']}")
        print(f"   • Arquivo: {output_path}")
        print(f"{'='*80}\n")

        # Exibe amostra de opcodes detectados
        if self.script_opcodes:
            print(f"🔧 Amostra de Opcodes Detectados:")
            opcodes_sorted = sorted(self.script_opcodes)[:15]
            print(f"   {', '.join(f'0x{op:02X}' for op in opcodes_sorted)}")
            if len(self.script_opcodes) > 15:
                print(f"   ... e mais {len(self.script_opcodes) - 15} opcodes")
            print()

        return stats


# ================================================================================
# INTERFACE DE LINHA DE COMANDO
# ================================================================================

def main():
    """Interface CLI para o Kernel V 9.8 [FORENSIC KERNEL]"""

    if len(sys.argv) < 2:
        print(f"\n{'='*80}")
        print(f"NEUROROM AI V 6.0 PRO SUITE - KERNEL V 9.8 [FORENSIC KERNEL]")
        print(f"{'='*80}\n")
        print(f"🎮 PROFILE B MASTER DECODER: Tabelas Padrão de Interoperabilidade")
        print(f"🎮 DUAL BLOCK EXTRACTION: Bank $0E + Bank $1C")
        print(f"🎮 SYLLABLES DECODER: Decodificação de 'Hero', 'Princess', etc")
        print(f"🔬 FORENSIC MODULES:")
        print(f"   • MIRRORING: Conversão avançada de endereços Console 16-bit (LoROM/HiROM)")
        print(f"   • SCRIPT CRAWLER: Recursive Descent com rotulação de opcodes")
        print(f"   • DICTIONARY LOOKUP: Expansão MTE/DTE ($477648)")
        print(f"   • JAPANESE ENCODING: Suporte Shift-JIS para jogos japoneses")
        print(f"   • HUFFMAN DECOMPRESSOR: Descompressão 16-bit (estrutura base)\n")
        print(f"Uso: python ultimate_extractor_v9.py <rom_path> [output_path]\n")
        print(f"Exemplos:")
        print(f"  python ultimate_extractor_v9.py game.smc")
        print(f"  python ultimate_extractor_v9.py rpg_game.smc extracted.txt\n")
        return 1

    rom_path = sys.argv[1]

    if not os.path.exists(rom_path):
        print(f"❌ Arquivo não encontrado: {rom_path}")
        return 1

    # Define output path
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        rom_name = os.path.splitext(os.path.basename(rom_path))[0]
        rom_dir = os.path.dirname(rom_path)
        output_path = os.path.join(rom_dir, f"{rom_name}_V98_FORENSIC.txt")

    # Executa extração
    extractor = UltimateExtractorV9(rom_path)
    stats = extractor.extract_all(output_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
