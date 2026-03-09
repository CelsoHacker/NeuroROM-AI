#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SUPER MARIO WORLD - EXTRATOR AGRESSIVO COMPLETO
================================================

Extrai TODOS os textos diretamente da ROM .smc usando:
1. Charset correto do SNES (shift -1)
2. Varredura byte-a-byte de toda a ROM
3. Heurísticas inteligentes
4. Meta: 200-300+ textos extraídos
"""

import sys
from pathlib import Path
from typing import List, Tuple, Set
import re


class SMWCharset:
    """Charset do Super Mario World (SNES)"""

    # Super Mario World usa shift -1: 0x00='@', 0x01='A', 0x02='B', etc.
    # Mapeamento completo de bytes para caracteres
    CHARSET = {
        # Letras maiúsculas (0x01-0x1A)
        **{i: chr(ord('A') + i - 1) for i in range(1, 27)},

        # Espaço e pontuação comum
        0x00: ' ',      # Espaço
        0x1B: '!',
        0x1C: '?',
        0x1D: '.',
        0x1E: ',',
        0x1F: '-',
        0x20: "'",

        # Números (0x30-0x39 como ASCII)
        **{i: chr(i) for i in range(0x30, 0x3A)},

        # Terminadores e controles
        0xFF: '\n',     # Line break
        0xFE: '[END]',  # String terminator
    }

    @classmethod
    def decode_byte(cls, byte: int) -> str:
        """Decodifica um byte usando charset SMW"""
        return cls.CHARSET.get(byte, None)

    @classmethod
    def is_valid_char(cls, byte: int) -> bool:
        """Verifica se byte é válido no charset"""
        return byte in cls.CHARSET


class SMWTextExtractor:
    """Extrator agressivo de textos do Super Mario World"""

    def __init__(self, rom_path: str):
        self.rom_path = Path(rom_path)
        self.rom_data = None
        self.extracted_texts: List[str] = []
        self.stats = {
            'total_bytes': 0,
            'text_regions': 0,
            'valid_texts': 0,
            'filtered': 0
        }

    def load_rom(self):
        """Carrega ROM em memória"""
        print(f"📂 Carregando ROM: {self.rom_path.name}")
        with open(self.rom_path, 'rb') as f:
            self.rom_data = f.read()

        self.stats['total_bytes'] = len(self.rom_data)
        print(f"✅ {len(self.rom_data):,} bytes carregados")

    def scan_for_text(self, min_length: int = 4, max_length: int = 200) -> List[Tuple[int, str]]:
        """
        Varre ROM procurando sequências de texto válido

        Args:
            min_length: Tamanho mínimo de texto válido
            max_length: Tamanho máximo de texto válido

        Returns:
            Lista de (offset, texto) encontrados
        """
        print("\n🔍 Varrendo ROM byte-a-byte...")
        print(f"   Min length: {min_length} | Max length: {max_length}")

        results = []
        i = 0

        while i < len(self.rom_data):
            # Tenta decodificar sequência começando em i
            text, length = self._extract_sequence(i, max_length)

            if text and len(text) >= min_length:
                # Valida se parece texto real
                if self._is_valid_text(text):
                    results.append((i, text))
                    self.stats['text_regions'] += 1

                    # Pula a região processada
                    i += length
                    continue

            i += 1

        print(f"✅ {len(results):,} regiões de texto encontradas")
        return results

    def _extract_sequence(self, offset: int, max_length: int) -> Tuple[str, int]:
        """
        Extrai sequência de texto começando em offset

        Returns:
            (texto_decodificado, bytes_consumidos)
        """
        text = []
        pos = offset
        length = 0

        while pos < len(self.rom_data) and length < max_length:
            byte = self.rom_data[pos]

            # Terminador de string
            if byte == 0xFE or byte == 0xFF:
                break

            # Byte inválido = fim da sequência
            if not SMWCharset.is_valid_char(byte):
                break

            # Decodifica byte
            char = SMWCharset.decode_byte(byte)
            if char:
                text.append(char)
                length += 1
                pos += 1
            else:
                break

        return ''.join(text), length

    def _is_valid_text(self, text: str) -> bool:
        """
        Valida se texto parece real (não lixo binário)

        Heurísticas:
        1. Pelo menos 50% caracteres alfabéticos
        2. Pelo menos 1 vogal
        3. Não só repetições (AAA, 111, etc)
        4. Contém palavras conhecidas do jogo (bonus)
        """
        text_clean = text.strip()

        if len(text_clean) < 4:
            return False

        # 1. Pelo menos 50% alfabético
        alpha_count = sum(1 for c in text_clean if c.isalpha())
        if alpha_count < len(text_clean) * 0.5:
            return False

        # 2. Pelo menos 1 vogal
        vowels = set('AEIOU')
        if not any(c in vowels for c in text_clean.upper()):
            return False

        # 3. Não só repetições
        if len(set(text_clean.replace(' ', ''))) < 3:
            return False

        # 4. Palavras conhecidas do SMW (BOOST!)
        smw_keywords = {
            'MARIO', 'LUIGI', 'YOSHI', 'WORLD', 'STAR', 'POWER',
            'COIN', 'TIME', 'BONUS', 'LIFE', 'GAME', 'OVER',
            'START', 'CONTINUE', 'CASTLE', 'GHOST', 'HOUSE'
        }

        text_upper = text_clean.upper()
        for keyword in smw_keywords:
            if keyword in text_upper:
                return True  # Auto-aprova se tem palavra conhecida

        return True

    def decode_with_shifts(self, text: str) -> List[str]:
        """
        Tenta decodificar texto com múltiplos shifts

        Super Mario World pode usar shifts diferentes em regiões diferentes
        """
        results = set()
        results.add(text)  # Original

        # Tenta shifts -2, -1, +1, +2
        for shift in [-2, -1, 1, 2]:
            decoded = self._apply_shift(text, shift)
            if decoded != text:
                results.add(decoded)

        return list(results)

    def _apply_shift(self, text: str, shift: int) -> str:
        """Aplica shift Caesar ao texto"""
        result = []
        for char in text:
            if 'A' <= char <= 'Z':
                new_char = chr((ord(char) - ord('A') + shift) % 26 + ord('A'))
                result.append(new_char)
            elif 'a' <= char <= 'z':
                new_char = chr((ord(char) - ord('a') + shift) % 26 + ord('a'))
                result.append(new_char)
            else:
                result.append(char)
        return ''.join(result)

    def deduplicate(self, texts: List[str]) -> List[str]:
        """Remove duplicatas mantendo ordem"""
        seen = set()
        unique = []

        for text in texts:
            normalized = text.strip().upper()
            if normalized not in seen and normalized:
                seen.add(normalized)
                unique.append(text)

        return unique

    def extract_all(self) -> List[str]:
        """
        Executa extração completa

        Returns:
            Lista de textos únicos extraídos
        """
        print("=" * 80)
        print("🎮 SUPER MARIO WORLD - EXTRAÇÃO AGRESSIVA")
        print("=" * 80)

        # 1. Carrega ROM
        self.load_rom()

        # 2. Varre ROM procurando texto
        raw_texts = self.scan_for_text(min_length=4, max_length=200)

        # 3. Decodifica com múltiplos shifts
        print("\n🔧 Aplicando múltiplos shifts...")
        all_variants = []
        for offset, text in raw_texts:
            variants = self.decode_with_shifts(text)
            all_variants.extend(variants)

        print(f"✅ {len(all_variants):,} variantes geradas")

        # 4. Filtra e deduplica
        print("\n🧹 Filtrando e deduplicando...")
        valid_texts = [t for t in all_variants if self._is_valid_text(t)]
        unique_texts = self.deduplicate(valid_texts)

        self.stats['valid_texts'] = len(unique_texts)
        self.stats['filtered'] = len(all_variants) - len(unique_texts)

        # 5. Ordena por tamanho (textos maiores primeiro)
        unique_texts.sort(key=len, reverse=True)

        self.extracted_texts = unique_texts
        return unique_texts

    def save_results(self, output_path: str):
        """Salva resultados em arquivo"""
        output_file = Path(output_path)

        with open(output_file, 'w', encoding='utf-8') as f:
            for i, text in enumerate(self.extracted_texts, 1):
                f.write(f"{text}\n")

        print(f"\n💾 Salvos {len(self.extracted_texts):,} textos em: {output_file.name}")

    def print_stats(self):
        """Mostra estatísticas da extração"""
        print("\n" + "=" * 80)
        print("📊 ESTATÍSTICAS")
        print("=" * 80)
        print(f"Total de bytes processados: {self.stats['total_bytes']:,}")
        print(f"Regiões de texto encontradas: {self.stats['text_regions']:,}")
        print(f"Textos válidos extraídos: {self.stats['valid_texts']:,}")
        print(f"Duplicatas/lixo removido: {self.stats['filtered']:,}")
        print("=" * 80)


def main():
    """Função principal"""

    # Caminho da ROM
    rom_path = r"C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework\ROMs\Super Nintedo\Super Mario World.smc"

    # Verifica se ROM existe
    if not Path(rom_path).exists():
        print(f"❌ ROM não encontrada: {rom_path}")
        print("\n💡 Edite o caminho da ROM no script e tente novamente.")
        return

    # Cria extrator
    extractor = SMWTextExtractor(rom_path)

    # Executa extração
    texts = extractor.extract_all()

    # Mostra primeiros 50 resultados
    print("\n" + "=" * 80)
    print("📝 PRIMEIROS 50 TEXTOS EXTRAÍDOS:")
    print("=" * 80)
    for i, text in enumerate(texts[:50], 1):
        print(f"{i:3d}. {text}")

    if len(texts) > 50:
        print(f"\n... e mais {len(texts) - 50} textos")

    # Estatísticas
    extractor.print_stats()

    # Salva resultados
    output_path = rom_path.replace('.smc', '_FULL_EXTRACTION.txt')
    extractor.save_results(output_path)

    # Avaliação
    print("\n" + "=" * 80)
    print("✅ AVALIAÇÃO:")
    print("=" * 80)
    if len(texts) >= 200:
        print("🎉 EXCELENTE! 200+ textos extraídos (meta atingida)")
    elif len(texts) >= 100:
        print("✅ BOM! 100+ textos extraídos (pode melhorar)")
    elif len(texts) >= 50:
        print("⚠️  REGULAR. 50+ textos (ajuste heurísticas)")
    else:
        print("❌ CRÍTICO! <50 textos (verifique charset/ROM)")
    print("=" * 80)


if __name__ == '__main__':
    main()
