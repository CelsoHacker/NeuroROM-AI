#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HYBRID EXTRACTOR PRO - ROM TRANSLATION FRAMEWORK
=================================================

Sistema híbrido que combina múltiplos métodos de extração para
maximizar cobertura e minimizar falsos positivos.

MÉTODOS IMPLEMENTADOS:
1. Auto-descoberta de múltiplos charsets (análise estatística)
2. Seguidor de ponteiros (pointer tables)
3. Análise de padrões contextuais
4. Validação por dicionário expandido
5. Correção automática de fragmentação
"""

import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import Counter, defaultdict
import json
import re


class CharsetAutoDiscovery:
    """Auto-descoberta de múltiplos charsets na ROM."""

    def __init__(self, rom_data: bytes):
        self.rom_data = rom_data
        self.discovered_charsets = []

    def find_text_regions(self, min_entropy: float = 4.0,
                         max_entropy: float = 6.0,
                         min_size: int = 256) -> List[Tuple[int, int]]:
        """
        Identifica regiões com entropia típica de texto.

        Texto tem entropia moderada (4-6 bits) vs código (>7) ou dados comprimidos (<3).
        """
        regions = []
        chunk_size = 512

        for offset in range(0, len(self.rom_data) - chunk_size, chunk_size):
            chunk = self.rom_data[offset:offset + chunk_size]
            entropy = self._calculate_entropy(chunk)

            if min_entropy <= entropy <= max_entropy:
                # Expande região encontrando limites
                start = offset
                end = offset + chunk_size

                # Tenta expandir para trás
                while start > 0:
                    prev_chunk = self.rom_data[max(0, start - 256):start]
                    if self._calculate_entropy(prev_chunk) < min_entropy:
                        break
                    start -= 256

                # Tenta expandir para frente
                while end < len(self.rom_data):
                    next_chunk = self.rom_data[end:min(len(self.rom_data), end + 256)]
                    if self._calculate_entropy(next_chunk) < min_entropy:
                        break
                    end += 256

                if end - start >= min_size:
                    regions.append((start, end))

        # Mescla regiões sobrepostas
        return self._merge_overlapping_regions(regions)

    def _calculate_entropy(self, data: bytes) -> float:
        """Calcula entropia de Shannon."""
        if len(data) == 0:
            return 0.0

        counter = Counter(data)
        total = len(data)
        entropy = 0.0

        for count in counter.values():
            p = count / total
            if p > 0:
                entropy -= p * np.log2(p)

        return entropy

    def _merge_overlapping_regions(self, regions: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Mescla regiões sobrepostas."""
        if not regions:
            return []

        regions = sorted(regions)
        merged = [regions[0]]

        for current in regions[1:]:
            last = merged[-1]

            # Se sobrepõe ou está próximo (< 512 bytes)
            if current[0] <= last[1] + 512:
                # Mescla
                merged[-1] = (last[0], max(last[1], current[1]))
            else:
                merged.append(current)

        return merged

    def analyze_byte_patterns(self, region_data: bytes) -> Dict[str, any]:
        """
        Analisa padrões de bytes para descobrir características do charset.

        Returns:
            {
                'likely_charset_type': 'sequential' | 'mapped' | 'compressed',
                'common_values': [list of common byte values],
                'spacing_pattern': detected spacing byte,
                'terminator_pattern': detected terminator byte
            }
        """
        freq = Counter(region_data)
        total = len(region_data)

        # Identifica bytes mais comuns (candidatos a espaço)
        most_common = freq.most_common(10)

        # Calcula variação dos bytes
        byte_values = list(freq.keys())
        if len(byte_values) > 1:
            byte_range = max(byte_values) - min(byte_values)
            is_sequential = byte_range < 128  # Charset compacto
        else:
            is_sequential = False

        # Identifica possível espaço (byte muito frequente, não no início)
        space_candidate = None
        for byte_val, count in most_common:
            if count / total > 0.05 and byte_val not in [0x00, 0xFF]:  # >5% de frequência
                space_candidate = byte_val
                break

        # Identifica possível terminador (bytes raros em fim de strings)
        terminator_candidates = [b for b, c in freq.items() if c / total < 0.01]

        return {
            'likely_charset_type': 'sequential' if is_sequential else 'mapped',
            'common_values': [b for b, _ in most_common[:26]],  # Top 26 (A-Z)
            'spacing_pattern': space_candidate,
            'terminator_candidates': terminator_candidates[:5],
            'byte_range': (min(byte_values), max(byte_values)) if byte_values else (0, 0)
        }

    def discover_charsets(self) -> List[Dict[int, str]]:
        """
        Descobre múltiplos charsets possíveis na ROM.

        Returns:
            Lista de charsets descobertos, cada um é um dict {byte: char}
        """
        print("🔍 Auto-descobrindo charsets...")

        # 1. Encontra regiões de texto prováveis
        text_regions = self.find_text_regions()
        print(f"   Encontradas {len(text_regions)} regiões de texto")

        if not text_regions:
            return []

        discovered = []

        # 2. Analisa cada região
        for i, (start, end) in enumerate(text_regions[:5]):  # Limita a 5 regiões
            region_data = self.rom_data[start:end]
            patterns = self.analyze_byte_patterns(region_data)

            # 3. Tenta criar charset baseado em padrões
            charset = self._build_charset_from_patterns(patterns)

            if charset and len(charset) >= 20:  # Mínimo 20 caracteres mapeados
                discovered.append(charset)
                print(f"   ✅ Charset {i+1}: {len(charset)} mapeamentos descobertos")

        self.discovered_charsets = discovered
        return discovered

    def _build_charset_from_patterns(self, patterns: Dict) -> Dict[int, str]:
        """Constrói charset baseado em padrões detectados."""
        charset = {}

        # Estratégia 1: Charset sequencial (0x00='A', 0x01='B', etc)
        if patterns['likely_charset_type'] == 'sequential':
            start_byte, end_byte = patterns['byte_range']

            # Tenta várias possibilidades de início
            for offset in [0, 1, -1]:
                test_charset = {}
                for i, byte_val in enumerate(patterns['common_values'][:26]):
                    if i < 26:
                        test_charset[byte_val] = chr(ord('A') + i + offset)

                if len(test_charset) >= 20:
                    charset.update(test_charset)
                    break

        # Estratégia 2: Charset mapeado (análise de frequência)
        else:
            # Mapeia bytes mais comuns para letras mais comuns em inglês
            common_letters = 'ETAOINSHRDLCUMWFGYPBVKJXQZ'
            for i, byte_val in enumerate(patterns['common_values'][:26]):
                if i < len(common_letters):
                    charset[byte_val] = common_letters[i]

        # Adiciona espaço
        if patterns['spacing_pattern']:
            charset[patterns['spacing_pattern']] = ' '

        # Adiciona possíveis terminadores
        for term in patterns['terminator_candidates'][:2]:
            if term not in charset:
                charset[term] = '[END]'

        return charset


class PointerFollower:
    """Segue ponteiros para encontrar tabelas de texto."""

    def __init__(self, rom_data: bytes):
        self.rom_data = rom_data
        self.found_tables = []

    def find_pointer_tables(self, min_table_size: int = 10) -> List[Tuple[int, List[int]]]:
        """
        Procura tabelas de ponteiros na ROM.

        Ponteiros são comuns em ROMs para referenciar strings.
        Formato típico: sequência de endereços de 2 ou 3 bytes.

        Returns:
            Lista de (offset_da_tabela, [lista_de_ponteiros])
        """
        print("\n🔗 Procurando tabelas de ponteiros...")

        tables = []

        # Procura sequências de valores que parecem ponteiros
        for offset in range(0, len(self.rom_data) - 100, 2):
            # Lê possível ponteiro (little-endian, 2 bytes)
            ptr1 = self.rom_data[offset] | (self.rom_data[offset + 1] << 8)
            ptr2 = self.rom_data[offset + 2] | (self.rom_data[offset + 3] << 8)

            # Ponteiros válidos geralmente:
            # 1. Estão dentro do tamanho da ROM
            # 2. Aumentam sequencialmente
            # 3. Diferença razoável entre eles (<4KB)

            if not (0x8000 <= ptr1 < 0xFFFF and 0x8000 <= ptr2 < 0xFFFF):
                continue

            if not (0 < ptr2 - ptr1 < 4096):
                continue

            # Tenta ler mais ponteiros
            pointers = [ptr1]
            current_offset = offset + 2

            for _ in range(100):  # Máximo 100 ponteiros
                if current_offset + 2 > len(self.rom_data):
                    break

                next_ptr = self.rom_data[current_offset] | (self.rom_data[current_offset + 1] << 8)

                # Valida se parece parte da mesma tabela
                if 0x8000 <= next_ptr < 0xFFFF and 0 < next_ptr - pointers[-1] < 4096:
                    pointers.append(next_ptr)
                    current_offset += 2
                else:
                    break

            if len(pointers) >= min_table_size:
                tables.append((offset, pointers))
                print(f"   ✅ Tabela em 0x{offset:06X}: {len(pointers)} ponteiros")

        self.found_tables = tables
        return tables

    def extract_from_pointers(self, pointers: List[int], charset: Dict[int, str],
                            max_string_len: int = 200) -> List[str]:
        """Extrai strings seguindo ponteiros."""
        texts = []

        for ptr in pointers:
            # Converte ponteiro SNES para offset ROM
            # SNES usa banco:offset, normalmente 0x8000-0xFFFF é ROM
            rom_offset = ptr - 0x8000 if ptr >= 0x8000 else ptr

            if rom_offset < 0 or rom_offset >= len(self.rom_data):
                continue

            # Extrai string
            text = []
            pos = rom_offset

            while pos < len(self.rom_data) and len(text) < max_string_len:
                byte = self.rom_data[pos]

                if byte in charset:
                    char = charset[byte]
                    if char == '[END]':
                        break
                    text.append(char)
                    pos += 1
                else:
                    break

            if len(text) >= 4:
                texts.append(''.join(text))

        return texts


class ContextualValidator:
    """Validador inteligente que usa contexto e padrões."""

    # Dicionário expandido com palavras comuns em jogos SNES
    GAME_VOCABULARY = {
        # Ações
        'PRESS', 'PUSH', 'PULL', 'JUMP', 'RUN', 'WALK', 'CLIMB', 'SWIM', 'DIVE',
        'ATTACK', 'DEFEND', 'DODGE', 'BLOCK', 'STRIKE', 'SHOOT', 'THROW', 'CATCH',
        'OPEN', 'CLOSE', 'ENTER', 'EXIT', 'TAKE', 'USE', 'DROP', 'GIVE',

        # Status/Sistema
        'START', 'SELECT', 'PAUSE', 'CONTINUE', 'SAVE', 'LOAD', 'QUIT', 'RESET',
        'GAME', 'OVER', 'WIN', 'LOSE', 'VICTORY', 'DEFEAT', 'SCORE', 'POINTS',
        'LIVES', 'LIFE', 'HEALTH', 'POWER', 'MAGIC', 'ENERGY', 'TIME', 'BONUS',

        # Direções
        'UP', 'DOWN', 'LEFT', 'RIGHT', 'NORTH', 'SOUTH', 'EAST', 'WEST',
        'FORWARD', 'BACK', 'NEXT', 'PREVIOUS', 'ABOVE', 'BELOW',

        # Items comuns
        'KEY', 'SWORD', 'SHIELD', 'ARMOR', 'HELMET', 'BOOTS', 'RING', 'AMULET',
        'POTION', 'ELIXIR', 'HERB', 'FOOD', 'WATER', 'GOLD', 'COIN', 'GEM',
        'MAP', 'COMPASS', 'TORCH', 'ROPE', 'BOMB', 'ARROW', 'BOW',

        # Personagens/Inimigos
        'HERO', 'WARRIOR', 'KNIGHT', 'MAGE', 'WIZARD', 'PRIEST', 'THIEF', 'RANGER',
        'DRAGON', 'GOBLIN', 'ORC', 'SKELETON', 'ZOMBIE', 'GHOST', 'DEMON', 'BEAST',
        'KING', 'QUEEN', 'PRINCE', 'PRINCESS', 'LORD', 'LADY', 'GUARD', 'SOLDIER',

        # Locais
        'TOWN', 'CITY', 'VILLAGE', 'CASTLE', 'FORTRESS', 'TOWER', 'DUNGEON', 'CAVE',
        'FOREST', 'DESERT', 'MOUNTAIN', 'LAKE', 'RIVER', 'OCEAN', 'ISLAND', 'BRIDGE',
        'HOUSE', 'INN', 'SHOP', 'TEMPLE', 'CHURCH', 'SHRINE', 'GATE', 'DOOR',

        # Palavras conectivas comuns
        'THE', 'AND', 'OR', 'BUT', 'FOR', 'WITH', 'FROM', 'INTO', 'ONTO', 'OVER',
        'YOU', 'YOUR', 'HIS', 'HER', 'THEY', 'THEIR', 'THIS', 'THAT', 'THESE', 'THOSE',
        'CAN', 'WILL', 'MUST', 'MAY', 'SHOULD', 'WOULD', 'COULD', 'MIGHT',
        'HAVE', 'HAS', 'HAD', 'ARE', 'WAS', 'WERE', 'BEEN', 'BEING',

        # Números e quantidades
        'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT', 'NINE', 'TEN',
        'FIRST', 'SECOND', 'THIRD', 'LAST', 'ALL', 'SOME', 'MANY', 'FEW', 'MUCH',

        # Outros comuns
        'HELP', 'PLEASE', 'THANK', 'THANKS', 'SORRY', 'WELCOME', 'GOODBYE', 'HELLO',
        'YES', 'NO', 'OK', 'OKAY', 'SURE', 'FINE', 'GOOD', 'BAD', 'GREAT', 'NICE',
        'NEW', 'OLD', 'BIG', 'SMALL', 'LONG', 'SHORT', 'HIGH', 'LOW', 'FAST', 'SLOW',
        'STRONG', 'WEAK', 'LIGHT', 'DARK', 'HOT', 'COLD', 'FULL', 'EMPTY',
    }

    @classmethod
    def is_valid_game_text(cls, text: str) -> bool:
        """Validação contextual inteligente."""
        # Remove hífens para análise
        text_clean = text.replace('-', ' ').strip()

        if len(text_clean) < 3:
            return False

        # Pelo menos 50% alfabético
        alpha_ratio = sum(1 for c in text_clean if c.isalpha()) / len(text_clean)
        if alpha_ratio < 0.5:
            return False

        # Verifica se contém palavra do vocabulário
        words = text_clean.upper().split()
        for word in words:
            if word in cls.GAME_VOCABULARY:
                return True

        # Verifica substrings para palavras compostas
        text_upper = text_clean.upper()
        for vocab_word in cls.GAME_VOCABULARY:
            if len(vocab_word) >= 4 and vocab_word in text_upper:
                return True

        # Validações adicionais para textos sem palavras conhecidas
        # Mas que parecem texto real

        # Tem vogais suficientes?
        vowels = sum(1 for c in text_clean if c.upper() in 'AEIOU')
        if vowels < len(text_clean) * 0.2:  # Mínimo 20% vogais
            return False

        # Não é repetitivo?
        if len(set(text_clean.replace(' ', ''))) < 4:
            return False

        # Se chegou aqui e tem >10 caracteres alfabéticos, aprova
        return sum(1 for c in text_clean if c.isalpha()) >= 10


class FragmentMerger:
    """Mescla fragmentos de texto que foram cortados incorretamente."""

    @staticmethod
    def merge_fragments(texts: List[str]) -> List[str]:
        """Identifica e mescla fragmentos que pertencem ao mesmo texto."""
        if not texts:
            return []

        # Ordena por tamanho (maiores primeiro)
        sorted_texts = sorted(texts, key=len, reverse=True)

        merged = []
        used = set()

        for text in sorted_texts:
            if text in used:
                continue

            # Procura fragmentos que podem completar este texto
            extended = text

            for other in sorted_texts:
                if other in used or other == text:
                    continue

                # Se 'other' completa o final de 'extended'
                if extended.endswith(other[:5]) and len(other) > 5:
                    # Possível continuação
                    overlap = FragmentMerger._find_overlap(extended, other)
                    if overlap > 0:
                        extended = extended + other[overlap:]
                        used.add(other)

                # Se 'other' completa o início de 'extended'
                elif extended.startswith(other[-5:]) and len(other) > 5:
                    overlap = FragmentMerger._find_overlap(other, extended)
                    if overlap > 0:
                        extended = other + extended[overlap:]
                        used.add(other)

            merged.append(extended)
            used.add(text)

        return merged

    @staticmethod
    def _find_overlap(text1: str, text2: str, min_overlap: int = 3) -> int:
        """Encontra sobreposição entre final de text1 e início de text2."""
        max_overlap = min(len(text1), len(text2))

        for i in range(max_overlap, min_overlap - 1, -1):
            if text1[-i:] == text2[:i]:
                return i

        return 0


class HybridExtractorPro:
    """Extrator híbrido profissional que combina múltiplos métodos."""

    def __init__(self, rom_path: str):
        self.rom_path = Path(rom_path)
        self.rom_data = None

        self.charset_discovery = None
        self.pointer_follower = None

        self.all_texts = set()
        self.extraction_stats = defaultdict(int)

    def load_rom(self):
        """Carrega ROM."""
        print(f"📂 Carregando ROM: {self.rom_path.name}")
        with open(self.rom_path, 'rb') as f:
            self.rom_data = f.read()
        print(f"✅ {len(self.rom_data):,} bytes carregados")

    def extract_all(self) -> List[str]:
        """Pipeline completo de extração híbrida."""
        print("\n" + "=" * 80)
        print("🚀 HYBRID EXTRACTOR PRO - EXTRAÇÃO INTELIGENTE")
        print("=" * 80)

        self.load_rom()

        # MÉTODO 1: Auto-descoberta de charsets
        print("\n" + "=" * 80)
        print("MÉTODO 1: AUTO-DESCOBERTA DE CHARSETS")
        print("=" * 80)

        self.charset_discovery = CharsetAutoDiscovery(self.rom_data)
        charsets = self.charset_discovery.discover_charsets()

        if charsets:
            for i, charset in enumerate(charsets):
                texts = self._extract_with_charset(charset)
                self.all_texts.update(texts)
                self.extraction_stats[f'charset_{i+1}'] = len(texts)
                print(f"   Charset {i+1}: {len(texts)} textos extraídos")

        # MÉTODO 2: Seguir ponteiros
        print("\n" + "=" * 80)
        print("MÉTODO 2: SEGUIR PONTEIROS")
        print("=" * 80)

        self.pointer_follower = PointerFollower(self.rom_data)
        pointer_tables = self.pointer_follower.find_pointer_tables()

        if pointer_tables and charsets:
            for table_offset, pointers in pointer_tables:
                for charset in charsets:
                    texts = self.pointer_follower.extract_from_pointers(pointers, charset)
                    self.all_texts.update(texts)
                    self.extraction_stats['pointer_following'] += len(texts)
                print(f"   Tabela 0x{table_offset:06X}: +{len(texts)} textos")

        # MÉTODO 3: Validação contextual
        print("\n" + "=" * 80)
        print("MÉTODO 3: VALIDAÇÃO CONTEXTUAL")
        print("=" * 80)

        validated_texts = [t for t in self.all_texts if ContextualValidator.is_valid_game_text(t)]
        print(f"   {len(validated_texts)} de {len(self.all_texts)} textos passaram na validação")

        # MÉTODO 4: Mesclagem de fragmentos
        print("\n" + "=" * 80)
        print("MÉTODO 4: CORREÇÃO DE FRAGMENTAÇÃO")
        print("=" * 80)

        merged_texts = FragmentMerger.merge_fragments(validated_texts)
        print(f"   {len(validated_texts)} → {len(merged_texts)} após mesclagem")

        # Remove duplicatas e ordena
        final_texts = sorted(list(set(merged_texts)), key=lambda x: (-len(x), x.upper()))

        return final_texts

    def _extract_with_charset(self, charset: Dict[int, str]) -> List[str]:
        """Extrai textos usando um charset específico."""
        texts = []
        current_text = []

        for byte in self.rom_data:
            if byte in charset:
                char = charset[byte]
                if char == '[END]':
                    if len(current_text) >= 4:
                        texts.append(''.join(current_text))
                    current_text = []
                else:
                    current_text.append(char)
            else:
                if len(current_text) >= 4:
                    texts.append(''.join(current_text))
                current_text = []

        return texts

    def print_stats(self):
        """Mostra estatísticas de extração."""
        print("\n" + "=" * 80)
        print("📊 ESTATÍSTICAS DE EXTRAÇÃO")
        print("=" * 80)

        for method, count in sorted(self.extraction_stats.items()):
            print(f"   {method}: {count} textos")

        print(f"\n   TOTAL ÚNICO: {len(self.all_texts)} textos")

    def save_results(self, output_path: str):
        """Salva resultados."""
        output_file = Path(output_path)

        with open(output_file, 'w', encoding='utf-8') as f:
            for text in sorted(self.all_texts, key=lambda x: (-len(x), x.upper())):
                f.write(f"{text}\n")

        print(f"\n💾 {len(self.all_texts)} textos salvos em: {output_file.name}")


def main():
    """Função principal."""

    rom_path = r"C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework\ROMs\Super Nintedo\Super Mario World.smc"

    if not Path(rom_path).exists():
        print(f"❌ ROM não encontrada: {rom_path}")
        return

    # Cria extrator híbrido
    extractor = HybridExtractorPro(rom_path)

    # Executa extração
    texts = extractor.extract_all()

    # Estatísticas
    extractor.print_stats()

    # Preview
    print("\n" + "=" * 80)
    print("📝 PREVIEW DOS TEXTOS EXTRAÍDOS (PRIMEIROS 100):")
    print("=" * 80)

    for i, text in enumerate(texts[:100], 1):
        print(f"{i:3d}. {text}")

    if len(texts) > 100:
        print(f"\n... e mais {len(texts) - 100} textos")

    # Salva
    output_path = rom_path.replace('.smc', '_HYBRID_PRO.txt')
    extractor.save_results(output_path)

    # Comparação
    print("\n" + "=" * 80)
    print("📊 COMPARAÇÃO COM MÉTODO ANTERIOR:")
    print("=" * 80)
    print(f"   Método Dual Charset: 72 textos válidos")
    print(f"   Método Híbrido Pro: {len(texts)} textos")

    improvement = ((len(texts) - 72) / 72 * 100) if len(texts) > 72 else 0
    print(f"   Melhoria: +{improvement:.1f}%")
    print("=" * 80)


if __name__ == '__main__':
    main()
