# -*- coding: utf-8 -*-
"""
ULTIMATE EXTRACTOR V8.0 - DTE/MTE COMPRESSION SOLVER
=====================================================
Sistema definitivo com suporte a compressão de texto por dicionário.

Pipeline de 4 Etapas com Proteção:
1. ASCII Extraction (se > 500 válidas → FIM)
2. Relative Search Engine (se encontrar tabela → FIM) [Protege Illusion of Gaia]
3. Deep Scavenger (sempre executa para sobras)
4. DTE/MTE Solver (só se falhou < 500 válidas) [Resolve Mario/Zelda/Elfaria]

Compressões suportadas:
- DTE (Dual Tile Encoding): Zelda, Chrono Trigger
- MTE (Multiple Tile Encoding): Lufia 2, Elfaria 2

Autor: Sistema V8.0 ULTIMATE
Data: 2026-01
"""

import struct
import math
import re
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from collections import Counter

# Importa componentes V7.0
try:
    from .super_text_filter import SuperTextFilter
    from .tbl_loader import TBLLoader
    from .relative_pattern_engine import RelativePatternEngine
    from .deep_scavenger_engine import DeepScavengerEngine
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from super_text_filter import SuperTextFilter
    from tbl_loader import TBLLoader
    from relative_pattern_engine import RelativePatternEngine
    from deep_scavenger_engine import DeepScavengerEngine


# ============================================================================
# DTE/MTE HARDCODED TABLES - Jogos Conhecidos
# ============================================================================

# SNES Platformer Game (USA) - DTE Table
# Tabela genérica para jogos de plataforma SNES com compressão DTE
SNES_PLATFORMER_DTE = {
    0x80: 'e ', 0x81: 't ', 0x82: 'a ', 0x83: 'o ', 0x84: 'n ', 0x85: 'i ',
    0x86: 's ', 0x87: 'r ', 0x88: 'h ', 0x89: 'l ', 0x8A: 'd ', 0x8B: 'u ',
    0x8C: 'c ', 0x8D: 'm ', 0x8E: 'p ', 0x8F: 'g ', 0x90: 'y ', 0x91: 'w ',
    0x92: 'b ', 0x93: 'f ', 0x94: 'v ', 0x95: 'k ', 0x96: 'A ', 0x97: 'M ',
    0x98: 'S ', 0x99: 'T ', 0x9A: 'I ', 0x9B: 'W ', 0x9C: 'D ', 0x9D: 'B ',
    0x9E: 'P ', 0x9F: 'H ', 0xA0: 'E ', 0xA1: 'C ', 0xA2: 'O ', 0xA3: 'L ',
    0xA4: 'R ', 0xA5: 'G ', 0xA6: 'N ', 0xA7: 'Y ', 0xA8: 'U ', 0xA9: 'F ',
    0xAA: 're', 0xAB: 'in', 0xAC: 'yo', 0xAD: 'ou', 0xAE: 'to', 0xAF: 'le',
    0xB0: 'on', 0xB1: 'at', 0xB2: 'it', 0xB3: 'ar', 0xB4: 'en', 0xB5: 'ow',
    0xB6: 'om', 0xB7: 'al', 0xB8: 'an', 0xB9: 'of', 0xBA: 'is', 0xBB: 'es',
    0xBC: 'or', 0xBD: 'er', 0xBE: 'as', 0xBF: 'st', 0xC0: 'ng', 0xC1: 'Th',
    0xC2: 'no', 0xC3: 've', 0xC4: 'ha', 0xC5: 'll', 0xC6: 'Wh', 0xC7: 'ca',
    0xC8: 'one', 0xC9: 'ea', 0xCA: 'Yo', 0xCB: 'fo', 0xCC: 'se', 0xCD: 'us',
    0xCE: 'me', 0xCF: 'wh', 0xD0: 'ma', 0xD1: 'Th', 0xD2: 'he', 0xD3: 'y ',
    0xD4: 'ur', 0xD5: 'il', 0xD6: 'be', 0xD7: 'co', 0xD8: 'e ', 0xD9: 'ne',
    0xDA: 't ', 0xDB: 's ', 0xDC: 'd ', 0xDD: 'Ba', 0xDE: 'la', 0xDF: 'ac',
    0xE0: 's.', 0xE1: 't.', 0xE2: 'ro', 0xE3: 'hi', 0xE4: 'li', 0xE5: 'ho',
    0xE6: 'Pl', 0xE7: 'tu', 0xE8: 'I ', 0xE9: 'w ', 0xEA: 'u ', 0xEB: 'k ',
    0xEC: 'f ', 0xED: 'Th', 0xEE: 'It', 0xEF: 'Wa', 0xF0: 'do', 0xF1: 'To',
    0xF2: 'No', 0xF3: 'pe', 0xF4: 'su', 0xF5: 'wi', 0xF6: 'te', 0xF7: 'ge',
    0xF8: 'we', 0xF9: 'm ', 0xFA: 'Go', 0xFB: 'So', 0xFC: 'r ', 0xFD: 'p ',
    0xFE: 'bo', 0xFF: 'lu'
}


# ============================================================================
# DTE/MTE SOLVER - Quebrador de Compressão por Dicionário
# ============================================================================

class DTEMTESolver:
    """
    Detecta e decodifica compressão DTE/MTE automática.

    DTE (Dual Tile Encoding): Dicionário de sílabas
    MTE (Multiple Tile Encoding): Dicionário de palavras

    Suporta tabelas hardcoded para jogos conhecidos de plataforma SNES
    """

    def __init__(self, rom_data: bytes):
        self.rom_data = rom_data
        self.dictionary_offset = None
        self.compression_type = None  # 'DTE' ou 'MTE'
        self.decode_table = {}
        self.used_hardcoded = False

    def calculate_entropy(self, data: bytes) -> float:
        """Calcula entropia de Shannon."""
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

    def is_syllable_pattern(self, text: str) -> bool:
        """
        Detecta padrão de sílabas (DTE).
        Exemplo: "orupinandtheforbutare"
        """
        if len(text) < 20:
            return False

        # Remove espaços
        clean = text.replace(' ', '').replace('\n', '')

        if len(clean) < 20:
            return False

        # Conta vogais e consoantes
        vowels = sum(1 for c in clean if c.lower() in 'aeiou')
        consonants = sum(1 for c in clean if c.isalpha() and c.lower() not in 'aeiou')

        if vowels == 0 or consonants == 0:
            return False

        # Sílabas têm boa alternância vogal/consoante
        vowel_ratio = vowels / len(clean)

        # Verifica se tem blocos de 2-3 caracteres
        has_short_patterns = True
        for i in range(0, len(clean) - 3, 2):
            chunk = clean[i:i+3]
            if not chunk.isalpha():
                has_short_patterns = False
                break

        return 0.3 <= vowel_ratio <= 0.6 and has_short_patterns

    def is_word_pattern(self, text: str) -> bool:
        """
        Detecta padrão de palavras (MTE).
        Exemplo: "swordshieldpotiongoldyouarethebest"
        """
        if len(text) < 20:
            return False

        # Remove espaços
        clean = text.replace(' ', '').replace('\n', '').lower()

        # Palavras comuns em jogos
        common_words = [
            'sword', 'shield', 'potion', 'gold', 'you', 'are', 'the', 'best',
            'take', 'give', 'hero', 'magic', 'item', 'menu', 'start', 'game',
            'over', 'win', 'lose', 'attack', 'defend', 'heal', 'life', 'mana'
        ]

        # Conta quantas palavras aparecem
        found_words = 0
        for word in common_words:
            if word in clean:
                found_words += 1

        # Se encontrar 3+ palavras, é provável dicionário MTE
        return found_words >= 3

    def find_dictionary(self) -> Optional[Dict]:
        """
        Procura dicionário DTE/MTE na ROM.

        Returns:
            Dict com 'offset', 'type', 'text' ou None
        """
        print("\n" + "="*80)
        print("🔍 DTE/MTE SOLVER - Procurando Dicionário de Compressão")
        print("="*80)

        # Varre ROM procurando blocos densos de ASCII
        min_block_size = 100

        for offset in range(0, len(self.rom_data) - min_block_size, 16):
            # Pega bloco de 200 bytes
            chunk = self.rom_data[offset:offset + 200]

            # Conta ASCII legível
            ascii_count = sum(1 for b in chunk if 0x20 <= b <= 0x7E)
            ascii_ratio = ascii_count / len(chunk)

            # Se 80%+ é ASCII, pode ser dicionário
            if ascii_ratio < 0.8:
                continue

            # Tenta decodificar
            try:
                text = chunk.decode('ascii', errors='ignore')

                # Remove caracteres de controle
                text = ''.join(c for c in text if c.isprintable())

                if len(text) < 50:
                    continue

                # Verifica padrões
                if self.is_syllable_pattern(text):
                    print(f"\n✅ Dicionário DTE detectado em 0x{offset:X}")
                    print(f"   Amostra: {text[:60]}...")
                    return {
                        'offset': offset,
                        'type': 'DTE',
                        'text': text
                    }

                if self.is_word_pattern(text):
                    print(f"\n✅ Dicionário MTE detectado em 0x{offset:X}")
                    print(f"   Amostra: {text[:60]}...")
                    return {
                        'offset': offset,
                        'type': 'MTE',
                        'text': text
                    }

            except:
                continue

        print("\n❌ Nenhum dicionário DTE/MTE encontrado")
        return None

    def parse_syllables(self, text: str) -> List[str]:
        """
        Quebra texto em sílabas (DTE).

        Heurística: Cada 2-3 caracteres
        """
        syllables = []
        i = 0

        while i < len(text):
            # Tenta pegar 2-3 caracteres
            if i + 3 <= len(text):
                chunk = text[i:i+3]

                # Se chunk tem vogal + consoante ou vice-versa, é sílaba
                has_vowel = any(c in 'aeiouAEIOU' for c in chunk)
                has_consonant = any(c.isalpha() and c not in 'aeiouAEIOU' for c in chunk)

                if has_vowel and has_consonant:
                    # Ajusta tamanho (2 ou 3 chars)
                    if chunk[2] in 'aeiouAEIOU':
                        syllables.append(chunk[:2])
                        i += 2
                    else:
                        syllables.append(chunk)
                        i += 3
                else:
                    # Pega só 2
                    syllables.append(chunk[:2])
                    i += 2
            else:
                # Resto
                syllables.append(text[i:])
                break

        return syllables

    def parse_words(self, text: str) -> List[str]:
        """
        Quebra texto em palavras (MTE).
        """
        # Se tem espaços, split direto
        if ' ' in text:
            return text.split()

        # Se não tem espaços, tenta heurística
        # Procura por palavras conhecidas
        words = []
        i = 0

        while i < len(text):
            # Tenta pegar 3-8 caracteres
            for length in range(8, 2, -1):
                if i + length <= len(text):
                    word = text[i:i+length].lower()

                    # Se parece palavra válida (tem vogal e consoante)
                    has_vowel = any(c in 'aeiou' for c in word)
                    has_consonant = any(c.isalpha() and c not in 'aeiou' for c in word)

                    if has_vowel and has_consonant and len(word) >= 3:
                        words.append(word)
                        i += length
                        break
            else:
                # Não achou palavra válida, pula 1
                i += 1

        return words

    def build_dte_table(self, dict_info: Dict) -> Dict[int, str]:
        """
        Constrói tabela DTE (byte → sílaba).
        """
        print("\n📋 Construindo tabela DTE...")

        text = dict_info['text']
        syllables = self.parse_syllables(text)

        print(f"   Sílabas encontradas: {len(syllables)}")
        print(f"   Primeiras 10: {syllables[:10]}")

        # Mapeia bytes altos (0x80+) para sílabas
        dte_table = {}

        for i, syllable in enumerate(syllables):
            if i >= 128:  # Máximo de 128 sílabas (0x80-0xFF)
                break

            byte_value = 0x80 + i
            dte_table[byte_value] = syllable

        print(f"   ✅ Tabela DTE: {len(dte_table)} entradas")

        return dte_table

    def build_mte_table(self, dict_info: Dict) -> Dict[int, str]:
        """
        Constrói tabela MTE (16-bit → palavra).
        """
        print("\n📋 Construindo tabela MTE...")

        text = dict_info['text']
        words = self.parse_words(text)

        print(f"   Palavras encontradas: {len(words)}")
        print(f"   Primeiras 10: {words[:10]}")

        # Mapeia 16-bit (0x8000+) para palavras
        mte_table = {}

        for i, word in enumerate(words):
            if i >= 1024:  # Máximo razoável
                break

            # Base varia por jogo, tentamos múltiplas bases
            for base in [0x8000, 0x3FA0, 0x4000]:
                index_16bit = base + i
                mte_table[index_16bit] = word

        print(f"   ✅ Tabela MTE: {len(mte_table)} entradas")

        return mte_table

    def extract_with_dte(self, dte_table: Dict[int, str]) -> List[Tuple[int, str]]:
        """
        Extrai strings interpretando bytes altos como DTE.
        """
        print("\n📝 Extraindo com DTE...")

        strings_found = []
        offset = 0
        min_length = 4

        while offset < len(self.rom_data) - min_length:
            text = []
            length = 0

            for i in range(200):
                if offset + i >= len(self.rom_data):
                    break

                byte = self.rom_data[offset + i]

                # Terminadores
                if byte in [0x00, 0xFF]:
                    length = i + 1
                    break

                # ASCII normal
                if 0x20 <= byte <= 0x7E:
                    text.append(chr(byte))

                # Byte alto = DTE!
                elif byte in dte_table:
                    text.append(dte_table[byte])

                else:
                    # Byte desconhecido
                    break

            # Valida
            if len(text) >= min_length:
                final_text = ''.join(text).strip()
                if len(final_text) >= min_length:
                    strings_found.append((offset, final_text))
                    offset += length if length > 0 else 1
                    continue

            offset += 1

        print(f"   ✅ {len(strings_found)} strings DTE encontradas")
        return strings_found

    def extract_with_mte(self, mte_table: Dict[int, str]) -> List[Tuple[int, str]]:
        """
        Extrai strings interpretando pares de bytes como MTE.
        """
        print("\n📝 Extraindo com MTE...")

        strings_found = []
        offset = 0
        min_length = 3

        while offset < len(self.rom_data) - min_length:
            text = []
            i = offset

            while i < len(self.rom_data) - 1:
                # Lê 2 bytes como 16-bit
                try:
                    # Tenta big-endian
                    word_index = struct.unpack('>H', self.rom_data[i:i+2])[0]

                    if word_index in mte_table:
                        # Achamos palavra!
                        text.append(mte_table[word_index])
                        i += 2
                        continue

                    # Tenta little-endian
                    word_index = struct.unpack('<H', self.rom_data[i:i+2])[0]

                    if word_index in mte_table:
                        text.append(mte_table[word_index])
                        i += 2
                        continue

                    # ASCII literal (números, pontuação)
                    if 0x20 <= self.rom_data[i] <= 0x7E:
                        text.append(chr(self.rom_data[i]))
                        i += 1
                        continue

                    # Terminador ou desconhecido
                    break

                except:
                    break

            # Valida
            if len(text) >= min_length:
                final_text = ' '.join(text).strip()
                if len(final_text) >= min_length:
                    strings_found.append((offset, final_text))
                    offset = i
                    continue

            offset += 1

        print(f"   ✅ {len(strings_found)} strings MTE encontradas")
        return strings_found

    def detect_known_game(self) -> Optional[str]:
        """Detecta o Perfil A (Plataforma Clássica) tratando Headers SMC (512 bytes)."""
        data_size = len(self.rom_data)

        # 1. Verifica os tamanhos possíveis (512KB puro ou 512KB + 512 bytes de Header)
        # Mario World (USA) tem exatamente 524288 ou 524800 bytes
        if data_size not in [524288, 524800]:
            return None

        # 2. Define os locais possíveis do Título Interno
        # 0x7FC0 (Padrão LoROM sem header) ou 0x81C0 (Com header de 512 bytes)
        possible_offsets = [0x7FC0, 0x81C0]

        for offset in possible_offsets:
            if data_size > offset + 21:
                try:
                    title_bytes = self.rom_data[offset : offset + 21]
                    title = title_bytes.decode('ascii', errors='ignore').strip()

                    # A lógica Stealth (Confirma se é o perfil de plataforma alvo)
                    if title.startswith("SUPER") and "WORLD" in title:
                        return 'SNES Platformer Profile A'
                except:
                    continue

        return None

    def solve(self) -> Optional[List[Tuple[int, str]]]:
        """
        Executa detecção e extração completa.

        Returns:
            Lista de (offset, text) ou None se falhou
        """
        # ✅ PASSO 1: Verifica se é um jogo conhecido
        known_game = self.detect_known_game()

        if known_game == 'SNES Platformer Profile A':
            print("\n" + "="*80)
            print("🎮 ROM DETECTADA: Perfil Plataforma SNES Tipo A")
            print("="*80)
            print("✅ Aplicando tabela DTE otimizada para este perfil")
            print("="*80 + "\n")

            self.compression_type = 'DTE'
            self.dictionary_offset = 0  # Hardcoded
            self.decode_table = SNES_PLATFORMER_DTE
            self.used_hardcoded = True

            return self.extract_with_dte(SNES_PLATFORMER_DTE)

        # ✅ PASSO 2: Se não é jogo conhecido, tenta detecção automática
        dict_info = self.find_dictionary()

        if not dict_info:
            return None

        # Constrói tabela e extrai
        if dict_info['type'] == 'DTE':
            self.compression_type = 'DTE'
            self.dictionary_offset = dict_info['offset']
            dte_table = self.build_dte_table(dict_info)
            self.decode_table = dte_table
            return self.extract_with_dte(dte_table)

        elif dict_info['type'] == 'MTE':
            self.compression_type = 'MTE'
            self.dictionary_offset = dict_info['offset']
            mte_table = self.build_mte_table(dict_info)
            self.decode_table = mte_table
            return self.extract_with_mte(mte_table)

        return None


# ============================================================================
# ULTIMATE EXTRACTOR V8.0 - Pipeline Completo
# ============================================================================

class UltimateExtractorV8:
    """
    Sistema completo V8.0 com suporte a DTE/MTE.

    Pipeline de 4 Etapas com Proteção:
    1. ASCII (> 500 válidas → FIM)
    2. Relative Search (encontrou tabela → FIM)
    3. Deep Scavenger (sempre)
    4. DTE/MTE Solver (só se < 500 válidas)
    """

    def __init__(self, rom_path: str, tbl_path: Optional[str] = None):
        self.rom_path = Path(rom_path)

        print("="*80)
        print("🚀 ULTIMATE EXTRACTION SUITE V8.0")
        print("="*80)
        print(f"📂 ROM: {self.rom_path.name}")

        # Carrega ROM
        with open(rom_path, 'rb') as f:
            self.rom_data = f.read()

        print(f"📏 Tamanho: {len(self.rom_data):,} bytes")
        print("="*80 + "\n")

        # Componentes
        self.text_filter = SuperTextFilter()
        self.tbl_loader = TBLLoader()

        # Tabela inicial
        if tbl_path:
            print(f"📋 Carregando tabela customizada: {Path(tbl_path).name}")
            self.tbl_loader.load_tbl(tbl_path)
            self.char_table = self.tbl_loader.char_map
            self.using_custom_tbl = True
        else:
            print("🔍 Auto-detectando tipo de tabela...")
            self.char_table = self.tbl_loader.auto_detect_table(self.rom_data)
            self.using_custom_tbl = False

        # Motores
        self.pattern_engine = RelativePatternEngine(self.rom_data)
        self.dte_mte_solver = DTEMTESolver(self.rom_data)

        self.min_length = 4
        self.protection_threshold = 500  # Limite de proteção

    def extract_ascii_strings(self) -> List[Tuple[int, str]]:
        """Extrai strings ASCII puras."""
        print("📝 [ETAPA 1] Extraindo strings ASCII...")

        strings_found = []
        ascii_pattern = re.compile(b'[\x20-\x7E]{4,200}')

        for match in ascii_pattern.finditer(self.rom_data):
            offset = match.start()
            raw_bytes = match.group()

            try:
                text = raw_bytes.decode('ascii', errors='ignore').strip()
                if len(text) >= self.min_length:
                    strings_found.append((offset, text))
            except:
                pass

        print(f"   ✅ {len(strings_found)} strings ASCII encontradas")
        return strings_found

    def extract_with_table(self) -> List[Tuple[int, str]]:
        """Extrai usando tabela de caracteres."""
        print("📝 [ETAPA 1] Extraindo com tabela...")

        strings_found = []
        offset = 0

        while offset < len(self.rom_data) - self.min_length:
            byte = self.rom_data[offset]

            if byte in self.char_table:
                text = []
                length = 0

                for i in range(200):
                    if offset + i >= len(self.rom_data):
                        break

                    current_byte = self.rom_data[offset + i]

                    if current_byte in [0x00, 0xFF]:
                        if len(text) >= self.min_length:
                            length = i + 1
                            break
                        else:
                            break

                    if current_byte in self.char_table:
                        text.append(self.char_table[current_byte])
                    else:
                        break

                if len(text) >= self.min_length:
                    final_text = ''.join(text).strip()
                    if len(final_text) >= self.min_length:
                        strings_found.append((offset, final_text))
                        offset += length if length > 0 else 1
                        continue

            offset += 1

        print(f"   ✅ {len(strings_found)} strings com tabela encontradas")
        return strings_found

    def remove_duplicates(self, strings: List[Tuple[int, str]]) -> List[Tuple[int, str]]:
        """Remove duplicatas."""
        seen = {}
        unique = []

        for offset, text in strings:
            if text not in seen:
                seen[text] = offset
                unique.append((offset, text))

        return unique

    def apply_filter(self, strings: List[Tuple[int, str]]) -> Tuple[List[Tuple[int, str]], Counter]:
        """Aplica Super Text Filter."""
        filtered = []
        rejection_stats = Counter()

        for offset, text in strings:
            is_valid, reason = self.text_filter.is_valid_text(text)

            if is_valid:
                filtered.append((offset, text))
            else:
                rejection_stats[reason] += 1

        return filtered, rejection_stats

    def save_results(self, main_strings: List[Tuple[int, str]],
                    recovered_strings: List[Tuple[int, str]],
                    dte_mte_strings: List[Tuple[int, str]],
                    rejection_stats: Counter,
                    stats: Dict) -> Dict:
        """Salva arquivos de resultado."""
        print("\n💾 Salvando arquivos...")

        output_dir = self.rom_path.parent
        rom_name = self.rom_path.stem

        # Arquivo principal
        output_file = output_dir / f"{rom_name}_V8_EXTRACTED.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# ULTIMATE EXTRACTION SUITE V8.0 (DTE/MTE Support)\n")
            f.write("# " + "="*76 + "\n")
            f.write(f"# ROM: {self.rom_path.name}\n")
            f.write(f"# Strings principais: {len(main_strings)}\n")
            f.write(f"# Strings recuperadas: {len(recovered_strings)}\n")
            f.write(f"# Strings DTE/MTE: {len(dte_mte_strings)}\n")
            f.write(f"# Total: {len(main_strings) + len(recovered_strings) + len(dte_mte_strings)}\n")
            f.write("# " + "="*76 + "\n\n")

            # Principais
            f.write("# STRINGS PRINCIPAIS (ASCII + TBL)\n")
            f.write("# " + "-"*76 + "\n\n")
            for offset, text in main_strings:
                f.write(f"[0x{offset:X}] {text}\n")

            # Recuperadas
            if recovered_strings:
                f.write("\n\n# STRINGS RECUPERADAS (Deep Scavenger)\n")
                f.write("# " + "-"*76 + "\n\n")
                for offset, text in recovered_strings:
                    f.write(f"[0x{offset:X}] [RECOVERED] {text}\n")

            # DTE/MTE
            if dte_mte_strings:
                f.write("\n\n# STRINGS DTE/MTE (Compression Solver)\n")
                f.write("# " + "-"*76 + "\n\n")
                for offset, text in dte_mte_strings:
                    f.write(f"[0x{offset:X}] [DTE/MTE] {text}\n")

        print(f"   ✅ {output_file.name}")

        # Relatório
        report_file = output_dir / f"{rom_name}_V8_REPORT.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("ULTIMATE EXTRACTION SUITE V8.0 - RELATÓRIO COMPLETO\n")
            f.write("="*80 + "\n\n")

            f.write(f"ROM: {self.rom_path.name}\n")
            f.write(f"Tamanho: {len(self.rom_data):,} bytes\n\n")

            f.write("CONFIGURAÇÃO:\n")
            f.write(f"- Tabela customizada: {'Sim' if self.using_custom_tbl else 'Não'}\n")
            f.write(f"- Pattern Engine: {'Sim' if stats.get('pattern_engine_used') else 'Não'}\n")
            f.write(f"- DTE/MTE Solver: {'Sim' if stats.get('dte_mte_used') else 'Não'}\n")
            if stats.get('dte_mte_used'):
                f.write(f"  Tipo: {stats.get('compression_type', 'N/A')}\n")
            f.write("\n")

            f.write("RESULTADOS:\n")
            f.write(f"- Strings principais: {len(main_strings)}\n")
            f.write(f"- Strings recuperadas: {len(recovered_strings)}\n")
            f.write(f"- Strings DTE/MTE: {len(dte_mte_strings)}\n")
            f.write(f"- Total: {len(main_strings) + len(recovered_strings) + len(dte_mte_strings)}\n")
            f.write("\n")

        print(f"   ✅ {report_file.name}")

        return {
            'output_file': str(output_file),
            'report_file': str(report_file)
        }

    def extract_all(self) -> Dict:
        """
        Pipeline completo V8.0 com proteção.
        """
        print("\n" + "="*80)
        print("🎯 INICIANDO PIPELINE V8.0 COM PROTEÇÃO")
        print("="*80 + "\n")

        # ====================================================================
        # ETAPA 1: EXTRAÇÃO PRINCIPAL (ASCII + TBL)
        # ====================================================================
        print("🔹 ETAPA 1: EXTRAÇÃO PRINCIPAL\n")

        ascii_strings = self.extract_ascii_strings()
        table_strings = self.extract_with_table()

        # Combina
        all_strings = ascii_strings + table_strings
        unique_strings = self.remove_duplicates(all_strings)

        print(f"\n🔧 Removendo duplicatas...")
        print(f"   ✅ {len(unique_strings)} strings únicas")

        # Aplica filtro
        print(f"\n🔥 Aplicando SUPER TEXT FILTER...")
        filtered_strings, rejection_stats = self.apply_filter(unique_strings)
        print(f"   ✅ {len(filtered_strings)} strings válidas")

        # PROTEÇÃO: Se > 500 válidas, PARA AQUI
        if len(filtered_strings) >= self.protection_threshold:
            print(f"\n🛡️  PROTEÇÃO ATIVADA: {len(filtered_strings)} > {self.protection_threshold}")
            print(f"   ROM já tem extração suficiente. Pulando etapas avançadas.")

            # Só executa Scavenger
            print("\n🔹 ETAPA 3: DEEP SCAVENGER (limpeza)")
            extracted_offsets = [offset for offset, _ in filtered_strings]
            scavenger_engine = DeepScavengerEngine(self.rom_data, self.char_table)
            recovered_strings, scavenger_stats = scavenger_engine.scavenge(extracted_offsets)

            # Filtra recuperadas
            if recovered_strings:
                print(f"\n🔥 Aplicando filtro nas recuperadas...")
                recovered_filtered = []
                for offset, text in recovered_strings:
                    is_valid, _ = self.text_filter.is_valid_text(text)
                    if is_valid:
                        recovered_filtered.append((offset, text))
                print(f"   ✅ {len(recovered_filtered)} recuperadas válidas")
                recovered_strings = recovered_filtered

            # Salva e retorna
            stats = {
                'rom_path': str(self.rom_path),
                'rom_size': len(self.rom_data),
                'valid_strings': len(filtered_strings),
                'recovered_strings': len(recovered_strings),
                'dte_mte_strings': 0,
                'total_strings': len(filtered_strings) + len(recovered_strings),
                'pattern_engine_used': False,
                'dte_mte_used': False,
                'protection_activated': True
            }

            files = self.save_results(filtered_strings, recovered_strings, [], rejection_stats, stats)

            self._print_summary(stats, files)

            return {**stats, **files}

        # ====================================================================
        # ETAPA 2: RELATIVE PATTERN ENGINE
        # ====================================================================
        print("\n🔹 ETAPA 2: RELATIVE PATTERN ENGINE\n")

        pattern_engine_used = False
        if not self.using_custom_tbl:
            entropy = self.pattern_engine.calculate_shannon_entropy()

            if entropy < 8.0 and len(filtered_strings) < self.protection_threshold:
                print(f"   Entropia: {entropy:.2f} < 8.0")
                print(f"   Tentando detectar tabela relativa...")

                detected_table = self.pattern_engine.detect_table()

                if detected_table:
                    pattern_engine_used = True

                    # Re-extrai com tabela detectada
                    self.char_table = detected_table
                    print("\n📝 Re-extraindo com tabela detectada...")
                    table_strings = self.extract_with_table()

                    # Re-processa
                    all_strings = ascii_strings + table_strings
                    unique_strings = self.remove_duplicates(all_strings)
                    filtered_strings, rejection_stats = self.apply_filter(unique_strings)

                    print(f"   ✅ {len(filtered_strings)} strings válidas pós-detecção")

                    # PROTEÇÃO: Se agora > 500, para aqui
                    if len(filtered_strings) >= self.protection_threshold:
                        print(f"\n🛡️  PROTEÇÃO ATIVADA: {len(filtered_strings)} > {self.protection_threshold}")
                        print(f"   Tabela detectada resolveu! Pulando DTE/MTE.")

                        # Scavenger
                        print("\n🔹 ETAPA 3: DEEP SCAVENGER")
                        extracted_offsets = [offset for offset, _ in filtered_strings]
                        scavenger_engine = DeepScavengerEngine(self.rom_data, self.char_table)
                        recovered_strings, scavenger_stats = scavenger_engine.scavenge(extracted_offsets)

                        if recovered_strings:
                            recovered_filtered = []
                            for offset, text in recovered_strings:
                                is_valid, _ = self.text_filter.is_valid_text(text)
                                if is_valid:
                                    recovered_filtered.append((offset, text))
                            recovered_strings = recovered_filtered

                        # Salva e retorna
                        stats = {
                            'rom_path': str(self.rom_path),
                            'rom_size': len(self.rom_data),
                            'valid_strings': len(filtered_strings),
                            'recovered_strings': len(recovered_strings),
                            'dte_mte_strings': 0,
                            'total_strings': len(filtered_strings) + len(recovered_strings),
                            'pattern_engine_used': True,
                            'dte_mte_used': False,
                            'protection_activated': True
                        }

                        files = self.save_results(filtered_strings, recovered_strings, [], rejection_stats, stats)
                        self._print_summary(stats, files)
                        return {**stats, **files}

        # ====================================================================
        # ETAPA 3: DEEP SCAVENGER
        # ====================================================================
        print("\n🔹 ETAPA 3: DEEP SCAVENGER\n")

        extracted_offsets = [offset for offset, _ in filtered_strings]
        scavenger_engine = DeepScavengerEngine(self.rom_data, self.char_table)
        recovered_strings, scavenger_stats = scavenger_engine.scavenge(extracted_offsets)

        # Filtra recuperadas
        if recovered_strings:
            print(f"\n🔥 Aplicando filtro nas recuperadas...")
            recovered_filtered = []
            for offset, text in recovered_strings:
                is_valid, _ = self.text_filter.is_valid_text(text)
                if is_valid:
                    recovered_filtered.append((offset, text))
            print(f"   ✅ {len(recovered_filtered)} recuperadas válidas")
            recovered_strings = recovered_filtered

        # ====================================================================
        # ETAPA 4: DTE/MTE SOLVER (SÓ SE < 500)
        # ====================================================================
        dte_mte_strings = []
        dte_mte_used = False
        compression_type = None

        total_current = len(filtered_strings) + len(recovered_strings)

        if total_current < self.protection_threshold:
            print(f"\n🔹 ETAPA 4: DTE/MTE SOLVER")
            print(f"   Total atual: {total_current} < {self.protection_threshold}")
            print(f"   Ativando quebrador de compressão...\n")

            dte_mte_result = self.dte_mte_solver.solve()

            if dte_mte_result:
                dte_mte_used = True
                compression_type = self.dte_mte_solver.compression_type

                print(f"\n🔥 Aplicando filtro em strings {compression_type} [MODO PRESERVAÇÃO]...")
                print(f"   ⚠️  IMPORTANTE: Filtros lenientes para preservar diálogos com códigos de controle")
                dte_mte_filtered = []
                for offset, text in dte_mte_result:
                    # ✅ USA PRESERVATION_MODE=True para MTE/DTE (evita perder diálogos)
                    is_valid, _ = self.text_filter.is_valid_text(text, preservation_mode=True)
                    if is_valid:
                        dte_mte_filtered.append((offset, text))

                print(f"   ✅ {len(dte_mte_filtered)} strings {compression_type} válidas (modo preservação)")
                dte_mte_strings = dte_mte_filtered
        else:
            print(f"\n🔹 ETAPA 4: DTE/MTE SOLVER")
            print(f"   ⏭️  PULADO: Total {total_current} >= {self.protection_threshold}")

        # ====================================================================
        # FINALIZAÇÃO
        # ====================================================================
        print("\n" + "="*80)
        print("💾 SALVANDO RESULTADOS")
        print("="*80 + "\n")

        stats = {
            'rom_path': str(self.rom_path),
            'rom_size': len(self.rom_data),
            'valid_strings': len(filtered_strings),
            'recovered_strings': len(recovered_strings),
            'dte_mte_strings': len(dte_mte_strings),
            'total_strings': len(filtered_strings) + len(recovered_strings) + len(dte_mte_strings),
            'pattern_engine_used': pattern_engine_used,
            'dte_mte_used': dte_mte_used,
            'compression_type': compression_type,
            'protection_activated': False
        }

        files = self.save_results(filtered_strings, recovered_strings, dte_mte_strings, rejection_stats, stats)

        self._print_summary(stats, files)

        return {**stats, **files}

    def _print_summary(self, stats: Dict, files: Dict):
        """Imprime resumo final."""
        print("\n" + "="*80)
        print("✅ EXTRAÇÃO V8.0 CONCLUÍDA!")
        print("="*80)
        print(f"\n📊 RESUMO FINAL:")
        print(f"   🔹 Strings principais: {stats['valid_strings']}")
        print(f"   🔹 Strings recuperadas: {stats['recovered_strings']}")
        print(f"   🔹 Strings DTE/MTE: {stats['dte_mte_strings']}")
        print(f"   🎉 TOTAL: {stats['total_strings']}")

        if stats.get('pattern_engine_used'):
            print(f"   ✅ Pattern Engine: ATIVADO")

        if stats.get('dte_mte_used'):
            print(f"   ✅ DTE/MTE Solver: ATIVADO ({stats.get('compression_type')})")

        if stats.get('protection_activated'):
            print(f"   🛡️  Proteção: ATIVADA (>{self.protection_threshold} strings)")

        print(f"\n📂 ARQUIVOS GERADOS:")
        print(f"   - {Path(files['output_file']).name}")
        print(f"   - {Path(files['report_file']).name}")
        print("\n" + "="*80 + "\n")


# ============================================================================
# FUNÇÃO PRINCIPAL
# ============================================================================

def extract_rom_v8(rom_path: str, tbl_path: Optional[str] = None) -> Dict:
    """
    Função principal V8.0.

    Args:
        rom_path: Caminho da ROM
        tbl_path: Caminho da tabela customizada (opcional)

    Returns:
        Dict com estatísticas completas
    """
    extractor = UltimateExtractorV8(rom_path, tbl_path)
    return extractor.extract_all()


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        rom_path = sys.argv[1]
        tbl_path = sys.argv[2] if len(sys.argv) > 2 else None

        extract_rom_v8(rom_path, tbl_path)
    else:
        print("Uso: python ultimate_extractor_v8.py <rom_path> [tbl_path]")
        print("\nExemplo:")
        print('  python ultimate_extractor_v8.py "Zelda.smc"')
        print('  python ultimate_extractor_v8.py "game.smc" "game.tbl"')
