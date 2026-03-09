#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EXTRATOR SUPER MARIO WORLD - DUAL CHARSET
==========================================

Usa os 2 sistemas de texto documentados no Data Crystal:
1. Message Box/Overworld: Letras começam em 0x00
2. Title Screen/Status Bar: Números em 0x00-0x09, letras em 0x0A+
"""

from pathlib import Path
from typing import List, Tuple, Dict


class SMWDualCharset:
    """Dois charsets diferentes usados no Super Mario World."""

    # CHARSET 1: Message Box e Overworld Text
    # Fonte: https://datacrystal.tcrf.net/wiki/Super_Mario_World_(SNES)/TBL
    MESSAGE_CHARSET = {
        **{i: chr(ord('A') + i) for i in range(26)},  # 0x00-0x19 = A-Z
        0x1A: ' ',
        0x1B: '!',
        0x1C: '?',
        0x1D: '.',
        0x1E: ',',
        0x1F: '-',
        0x20: "'",
        0x21: '"',
        # Números começam em 0x22
        0x22: '0',
        0x23: '1',
        0x24: '2',
        0x25: '3',
        0x26: '4',
        0x27: '5',
        0x28: '6',
        0x29: '7',
        0x2A: '8',
        0x2B: '9',
        # Letras minúsculas começam em 0x40
        **{i + 0x40: chr(ord('a') + i) for i in range(26)},  # 0x40-0x59 = a-z
        0xFE: '[END]',  # Terminador
        0xFF: '[BREAK]',  # Line break
    }

    # CHARSET 2: Title Screen e Status Bar
    TITLE_CHARSET = {
        # Números de 0-9 em 0x00-0x09
        **{i: str(i) for i in range(10)},
        # Letras começam em 0x0A
        **{i + 0x0A: chr(ord('A') + i) for i in range(26)},  # 0x0A-0x23 = A-Z
        0x24: ' ',
        0x25: '-',
        0x26: ',',
        0x27: '.',
        0xFE: '[END]',
    }

    @classmethod
    def decode_message(cls, data: bytes, offset: int, max_len: int = 200) -> Tuple[str, int]:
        """Decodifica texto usando Message Charset."""
        text = []
        pos = offset

        while pos < len(data) and len(text) < max_len:
            byte = data[pos]

            if byte == 0xFE:  # Terminador
                break

            if byte in cls.MESSAGE_CHARSET:
                char = cls.MESSAGE_CHARSET[byte]
                if char != '[END]' and char != '[BREAK]':
                    text.append(char)
                pos += 1
            else:
                break  # Byte inválido

        return ''.join(text), pos - offset

    @classmethod
    def decode_title(cls, data: bytes, offset: int, max_len: int = 200) -> Tuple[str, int]:
        """Decodifica texto usando Title Charset."""
        text = []
        pos = offset

        while pos < len(data) and len(text) < max_len:
            byte = data[pos]

            if byte == 0xFE:  # Terminador
                break

            if byte in cls.TITLE_CHARSET:
                char = cls.TITLE_CHARSET[byte]
                if char != '[END]':
                    text.append(char)
                pos += 1
            else:
                break  # Byte inválido

        return ''.join(text), pos - offset


class SMWDualExtractor:
    """Extrator que usa ambos os charsets."""

    def __init__(self, rom_path: str):
        self.rom_path = Path(rom_path)
        self.rom_data = None
        self.texts = []

    def load_rom(self):
        """Carrega ROM."""
        print(f"📂 Carregando: {self.rom_path.name}")
        with open(self.rom_path, 'rb') as f:
            self.rom_data = f.read()
        print(f"✅ {len(self.rom_data):,} bytes")

    def is_valid_text(self, text: str) -> bool:
        """Valida se texto parece real."""
        if len(text) < 4:
            return False

        # Pelo menos 50% alfabético
        alpha_count = sum(1 for c in text if c.isalpha())
        if alpha_count < len(text) * 0.5:
            return False

        # Pelo menos 1 vogal
        vowels = set('AEIOUaeiou')
        if not any(c in vowels for c in text):
            return False

        # Não só repetições
        if len(set(text.replace(' ', ''))) < 3:
            return False

        return True

    def extract_all(self) -> List[str]:
        """Extrai textos usando ambos os charsets."""
        print("\n" + "=" * 80)
        print("🎮 EXTRAÇÃO DUAL CHARSET - SUPER MARIO WORLD")
        print("=" * 80)

        self.load_rom()

        found_texts = set()

        # Tenta com Message Charset
        print("\n🔍 Charset 1: Message Box/Overworld...")
        for i in range(len(self.rom_data)):
            text, length = SMWDualCharset.decode_message(self.rom_data, i)

            if text and self.is_valid_text(text):
                found_texts.add(text)

        print(f"   ✅ {len(found_texts)} textos encontrados")

        initial_count = len(found_texts)

        # Tenta com Title Charset
        print("\n🔍 Charset 2: Title Screen/Status Bar...")
        for i in range(len(self.rom_data)):
            text, length = SMWDualCharset.decode_title(self.rom_data, i)

            if text and self.is_valid_text(text):
                found_texts.add(text)

        print(f"   ✅ {len(found_texts) - initial_count} textos novos encontrados")

        # Remove duplicatas e ordena
        self.texts = sorted(list(found_texts), key=lambda x: (-len(x), x.upper()))

        return self.texts

    def filter_by_keywords(self) -> List[str]:
        """Filtra textos que contêm palavras conhecidas do SMW."""
        smw_keywords = {
            'MARIO', 'LUIGI', 'YOSHI', 'BOWSER', 'PEACH', 'TOAD',
            'WORLD', 'STAR', 'POWER', 'FIRE', 'CAPE', 'FEATHER',
            'JUMP', 'RUN', 'SPIN', 'STOMP', 'SWIM', 'CLIMB',
            'COIN', 'MUSHROOM', 'FLOWER', 'SHELL',
            'GOOMBA', 'KOOPA', 'PIRANHA', 'THWOMP',
            'LEVEL', 'CASTLE', 'GHOST', 'HOUSE', 'FORTRESS',
            'SWITCH', 'PALACE', 'BLOCK', 'BONUS', 'SECRET',
            'LIVES', 'TIME', 'SCORE', 'GAME', 'OVER', 'START',
            'PRESS', 'BUTTON', 'CONTINUE', 'SAVE', 'EXIT',
            'SPECIAL', 'STAR', 'WORLD', 'DONUT', 'VANILLA',
            'TWIN', 'BRIDGE', 'FOREST', 'CHOCOLATE', 'VALLEY',
            'SUNKEN', 'SHIP', 'TOP', 'SODA', 'LAKE',
            'PLAINS', 'ISLAND', 'DOME'
        }

        filtered = []

        for text in self.texts:
            text_upper = text.upper()
            for keyword in smw_keywords:
                if keyword in text_upper:
                    filtered.append(text)
                    break

        return filtered

    def save_results(self, output_path: str):
        """Salva resultados."""
        output_file = Path(output_path)

        with open(output_file, 'w', encoding='utf-8') as f:
            for text in self.texts:
                f.write(f"{text}\n")

        print(f"\n💾 {len(self.texts):,} textos salvos em: {output_file.name}")

    def print_preview(self, limit: int = 100):
        """Mostra preview."""
        print("\n" + "=" * 80)
        print(f"📝 PRIMEIROS {limit} TEXTOS:")
        print("=" * 80)

        for i, text in enumerate(self.texts[:limit], 1):
            print(f"{i:3d}. {text}")

        if len(self.texts) > limit:
            print(f"\n... e mais {len(self.texts) - limit} textos")


def main():
    """Função principal."""

    rom_path = r"C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework\ROMs\Super Nintedo\Super Mario World.smc"

    if not Path(rom_path).exists():
        print(f"❌ ROM não encontrada: {rom_path}")
        return

    # Cria extrator
    extractor = SMWDualExtractor(rom_path)

    # Extrai textos
    texts = extractor.extract_all()

    print("\n" + "=" * 80)
    print(f"📊 TOTAL: {len(texts):,} textos únicos extraídos")
    print("=" * 80)

    # Filtra por palavras-chave
    print("\n🎮 Filtrando por palavras-chave do SMW...")
    filtered = extractor.filter_by_keywords()
    print(f"   ✅ {len(filtered)} textos com palavras-chave conhecidas")

    # Preview de todos os textos
    extractor.print_preview(limit=200)

    # Salva resultado
    output_path = rom_path.replace('.smc', '_DUAL_CHARSET.txt')
    extractor.save_results(output_path)

    # Salva também a versão filtrada
    if filtered:
        filtered_path = rom_path.replace('.smc', '_DUAL_CHARSET_FILTERED.txt')
        with open(filtered_path, 'w', encoding='utf-8') as f:
            for text in filtered:
                f.write(f"{text}\n")
        print(f"💾 {len(filtered)} textos filtrados salvos em: {Path(filtered_path).name}")

    print("\n" + "=" * 80)
    if len(texts) >= 200:
        print(f"🎉 EXCELENTE! {len(texts)} textos extraídos (meta 200+ atingida)")
    elif len(texts) >= 100:
        print(f"✅ BOM! {len(texts)} textos (próximo da meta)")
    else:
        print(f"⚠️  {len(texts)} textos (menos que o esperado)")
    print("=" * 80)


if __name__ == '__main__':
    main()
