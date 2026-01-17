#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sega Extractor - Master System & Mega Drive/Genesis
====================================================
Extrator especializado para plataformas Sega com ASCII puro.

Plataformas Suportadas:
- Sega Master System (.sms)
- Sega Mega Drive/Genesis (.gen, .md, .smd, .bin)

Características:
- ASCII direto (0x20-0x7E)
- Big-Endian (Motorola 68000)
- Sem compressão custom (maioria dos jogos)
- Tiles fixos 8x8

Author: NeuroROM AI
License: MIT
"""

import os
import struct
from pathlib import Path
from typing import List, Dict, Tuple, Optional


class SegaExtractor:
    """Extrator especializado para plataformas Sega"""

    # Configurações por plataforma
    PLATFORM_CONFIG = {
        'MASTER_SYSTEM': {
            'name': 'Sega Master System',
            'extensions': ['.sms'],
            'header_offset': 0x7FF0,
            'header_size': 16,
            'ram_start': 0xC000,
            'ram_size': 8192,
            'endian': 'little'
        },
        'GENESIS': {
            'name': 'Sega Genesis / Mega Drive',
            'extensions': ['.gen', '.md', '.bin'],
            'header_offset': 0x100,
            'header_size': 256,
            'ram_start': 0xFF0000,
            'ram_size': 65536,
            'endian': 'big'
        },
        'SMD': {
            'name': 'Sega Mega Drive (Interleaved)',
            'extensions': ['.smd'],
            'header_offset': 0x200,  # SMD tem header de 512 bytes
            'header_size': 256,
            'ram_start': 0xFF0000,
            'ram_size': 65536,
            'endian': 'big',
            'interleaved': True
        }
    }

    def __init__(self, rom_path: str):
        """
        Inicializa extrator Sega

        Args:
            rom_path: Caminho da ROM
        """
        self.rom_path = Path(rom_path)
        self.rom_data = None
        self.platform = None
        self.config = None

        if not self.rom_path.exists():
            raise FileNotFoundError(f"ROM não encontrada: {rom_path}")

        # Carrega ROM
        with open(self.rom_path, 'rb') as f:
            self.rom_data = bytearray(f.read())

        # Detecta plataforma
        self._detect_platform()

        # Decodifica SMD se necessário
        if self.config.get('interleaved'):
            self._decode_smd()

    def _detect_platform(self):
        """Detecta plataforma Sega automaticamente"""
        ext = self.rom_path.suffix.lower()

        # Por extensão
        for platform, config in self.PLATFORM_CONFIG.items():
            if ext in config['extensions']:
                self.platform = platform
                self.config = config
                return

        # Fallback: tenta detectar por tamanho
        size = len(self.rom_data)

        if size <= 512 * 1024:  # <= 512KB
            self.platform = 'MASTER_SYSTEM'
        else:
            self.platform = 'GENESIS'

        self.config = self.PLATFORM_CONFIG[self.platform]

    def _decode_smd(self):
        """
        Decodifica formato SMD interleaved para binário linear

        SMD Format:
        - Header de 512 bytes
        - Dados em blocos de 16KB interleaved (odd/even bytes)
        """
        if len(self.rom_data) < 512:
            return

        # Remove header SMD (512 bytes)
        smd_data = self.rom_data[512:]
        decoded = bytearray()

        # Decodifica blocos de 16KB
        block_size = 16384
        for offset in range(0, len(smd_data), block_size):
            block = smd_data[offset:offset + block_size]

            if len(block) < block_size:
                # Último bloco incompleto
                decoded.extend(block)
                break

            # Separa odd/even
            half = block_size // 2
            odd_bytes = block[:half]
            even_bytes = block[half:]

            # Intercala: even, odd, even, odd...
            for i in range(half):
                decoded.append(even_bytes[i])
                decoded.append(odd_bytes[i])

        self.rom_data = decoded

    def extract_texts(self, min_length: int = 4) -> List[Dict]:
        """
        Extrai textos ASCII da ROM com 4 filtros restritivos

        Args:
            min_length: Tamanho mínimo da string

        Returns:
            Lista de dicts com offset e texto
        """
        texts = []
        current_text = bytearray()
        text_start = None

        # Stats detalhados
        total_extracted = 0
        filtered_sequence = 0    # Filtro 1: Sequências alfabéticas
        filtered_symbols = 0     # Filtro 2: Repetição de símbolos
        filtered_vowels = 0      # Filtro 3: Sem vogais
        filtered_caps = 0        # Filtro 4: Capitalização estranha
        filtered_other = 0       # Outros filtros

        for offset in range(len(self.rom_data)):
            byte = self.rom_data[offset]

            # ASCII printable (0x20-0x7E)
            if 0x20 <= byte <= 0x7E:
                if text_start is None:
                    text_start = offset
                current_text.append(byte)
            else:
                # Fim da string
                if len(current_text) >= min_length:
                    try:
                        decoded = current_text.decode('ascii')
                        total_extracted += 1

                        # Aplica os 4 filtros restritivos em ordem
                        if self._is_alphabet_sequence(decoded):
                            filtered_sequence += 1
                        elif self._has_symbol_repetition(decoded):
                            filtered_symbols += 1
                        elif self._lacks_vowels(decoded):
                            filtered_vowels += 1
                        elif self._has_weird_capitalization(decoded):
                            filtered_caps += 1
                        elif not self._is_valid_game_text(decoded):
                            filtered_other += 1
                        else:
                            # Texto válido - passou em todos os filtros!
                            texts.append({
                                'offset': text_start,
                                'offset_hex': hex(text_start),
                                'text': decoded,
                                'length': len(decoded)
                            })
                    except UnicodeDecodeError:
                        pass

                # Reset
                current_text = bytearray()
                text_start = None

        # Remove duplicatas exatas
        unique_texts = []
        seen = set()
        for item in texts:
            if item['text'] not in seen:
                seen.add(item['text'])
                unique_texts.append(item)

        # Stats
        total_garbage = filtered_sequence + filtered_symbols + filtered_vowels + filtered_caps + filtered_other

        print(f"\n{'='*70}")
        print(f"🎮 {self.config['name']}")
        print(f"{'='*70}")
        print(f"📊 Strings brutas encontradas: {total_extracted:,}")
        print(f"🗑️  Lixo binário removido: {total_garbage:,}")
        print(f"   • Sequências alfabéticas (fontes): {filtered_sequence:,}")
        print(f"   • Repetição de símbolos (tiles): {filtered_symbols:,}")
        print(f"   • Sem vogais (consoantes): {filtered_vowels:,}")
        print(f"   • Capitalização estranha: {filtered_caps:,}")
        print(f"   • Outros filtros: {filtered_other:,}")
        print(f"✅ Textos de jogo válidos: {len(unique_texts):,}")
        print(f"📈 Taxa de limpeza: {(total_garbage/total_extracted*100) if total_extracted > 0 else 0:.1f}%")
        print(f"{'='*70}\n")

        return unique_texts

    def _is_alphabet_sequence(self, text: str) -> bool:
        """
        FILTRO 1: Sequências alfabéticas/numéricas (definições de fonte)
        Remove: 'abcdefg', 'ABCDEFGH', '0123456', 'ghijklmn', etc.
        """
        text_lower = text.lower()

        # Checa sequências alfabéticas de 4+ chars consecutivos
        alphabet = 'abcdefghijklmnopqrstuvwxyz'
        for i in range(len(alphabet) - 3):
            seq = alphabet[i:i+4]
            if seq in text_lower:
                return True

        # Checa sequências numéricas de 4+ chars consecutivos
        numbers = '0123456789'
        for i in range(len(numbers) - 3):
            seq = numbers[i:i+4]
            if seq in text:
                return True

        return False

    def _has_symbol_repetition(self, text: str) -> bool:
        """
        FILTRO 2: Entropia simbólica (gradientes de tiles)
        Remove: '((<<<PPPP', '!!!!', '@@@', etc.
        """
        # Lista de símbolos gráficos
        symbols = set('!@#$%^&*()_+-=[]{}|;:\'",.<>?/\\`~')

        # Conta símbolos
        symbol_count = sum(1 for c in text if c in symbols)

        # >40% símbolos = provavelmente lixo gráfico
        if len(text) > 0 and symbol_count / len(text) > 0.4:
            return True

        # Detecta repetição excessiva de qualquer caractere (3+ seguidos)
        prev_char = ''
        repeat_count = 0
        for char in text:
            if char == prev_char:
                repeat_count += 1
                if repeat_count >= 3:
                    return True
            else:
                repeat_count = 1
                prev_char = char

        return False

    def _lacks_vowels(self, text: str) -> bool:
        """
        FILTRO 3: Legibilidade humana (precisa de vogais)
        Remove: 'ptvx', 'RTVX', 'bdf', 'DPDb4C7' etc.
        Mantém: palavras com pelo menos 1 vogal
        """
        vowels = set('aeiouAEIOU')

        # Extrai apenas letras
        letters_only = ''.join(c for c in text if c.isalpha())

        # Se tem letras, precisa ter pelo menos 1 vogal
        if len(letters_only) >= 3:
            vowel_count = sum(1 for c in letters_only if c in vowels)
            if vowel_count == 0:
                return True  # Sem vogais = lixo

            # Proporção mínima de vogais (pelo menos 15% para texto real)
            vowel_ratio = vowel_count / len(letters_only)
            if vowel_ratio < 0.10:
                return True  # Muito poucas vogais

        return False

    def _has_weird_capitalization(self, text: str) -> bool:
        """
        FILTRO 4: Capitalização estranha (mistura símbolos+letras sem sentido)
        Remove: '@BDFH', 'V98?:', '5b@7FD', 'FbDDQ', etc.
        """
        # Mistura de @ com letras maiúsculas = definição de fonte
        if '@' in text:
            letters_after_at = sum(1 for i, c in enumerate(text) if c == '@' and i+1 < len(text) and text[i+1].isupper())
            if letters_after_at > 0:
                return True

        # Padrão hexadecimal disfarçado (letras A-F + números)
        hex_chars = set('0123456789ABCDEFabcdef')
        if len(text) >= 4:
            hex_count = sum(1 for c in text if c in hex_chars)
            if hex_count == len(text):
                # Todos os chars são hexadecimais - provavelmente dado binário
                # Mas permite se parecer palavra real (tem vogais)
                vowels = set('aeiouAEIOU')
                if not any(c in vowels for c in text):
                    return True

        # Padrão: letra maiúscula seguida de minúscula seguida de maiúscula (CamelCase quebrado)
        # Ex: 'FbDDQ', 'PpTt' - isso é tile data
        weird_pattern = 0
        for i in range(len(text) - 2):
            if text[i].isupper() and text[i+1].islower() and text[i+2].isupper():
                weird_pattern += 1
        if weird_pattern >= 2:
            return True

        return False

    def _is_valid_game_text(self, text: str) -> bool:
        """
        Validação final RESTRITIVA: texto que um jogador veria na tela
        (Créditos, Menus, Nome das Zonas, Diálogos)
        """
        text = text.strip()

        # Muito curto
        if len(text) < 3:
            return False

        # FILTRO EXTRA 1: Strings muito curtas precisam ser 100% letras
        if len(text) <= 5:
            letters = sum(1 for c in text if c.isalpha())
            if letters < len(text) * 0.8:  # Menos de 80% letras = lixo
                return False

        # FILTRO EXTRA 2: Rejeita strings que começam com número ou símbolo
        # Texto de jogo real geralmente começa com letra
        if text[0].isdigit() or text[0] in '!@#$%^&*()_+-=[]{}|;:\'",.<>?/\\`~':
            # Exceção: números de score/level como "1-1" ou "100"
            if not text.replace('-', '').replace(' ', '').isdigit():
                return False

        # FILTRO EXTRA 3: Proporção mínima de letras (60%)
        letters = sum(1 for c in text if c.isalpha())
        if len(text) > 0 and letters / len(text) < 0.6:
            return False

        # FILTRO EXTRA 4: Rejeita mistura número+letra sem espaço
        # Ex: '6G4ap', '5b@7FD' - isso é dado binário
        import re
        if re.search(r'\d[A-Za-z]|[A-Za-z]\d', text):
            # Exceção para padrões válidos: "Zone 1", "Act 2", "1991", "1UP"
            valid_patterns = ['zone', 'act', 'level', 'stage', 'world', 'up', 'player']
            text_lower = text.lower()
            if not any(p in text_lower for p in valid_patterns):
                # Permite anos (1985-2025) e scores
                if not re.match(r'^(19|20)\d{2}$', text) and not text.replace(',', '').isdigit():
                    return False

        # FILTRO EXTRA 5: Pelo menos 2 vogais para strings longas
        vowels = set('aeiouAEIOU')
        vowel_count = sum(1 for c in text if c in vowels)
        if len(text) >= 6 and vowel_count < 2:
            return False

        # FILTRO EXTRA 6: Rejeita pontuação isolada ou no início/fim estranho
        if text.startswith(('?', '!', ',', '.', ';', ':')) and len(text) < 10:
            return False

        # Passou em todos os filtros!
        return True

    def save_texts(self, texts: List[Dict], output_path: Optional[str] = None) -> str:
        """
        Salva textos extraídos em arquivo

        Args:
            texts: Lista de textos
            output_path: Caminho de saída (opcional)

        Returns:
            Caminho do arquivo salvo
        """
        if output_path is None:
            output_path = self.rom_path.parent / f"{self.rom_path.stem}_extracted_sega.txt"
        else:
            output_path = Path(output_path)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# NeuroROM AI - Sega Text Extraction\n")
            f.write("# " + "="*68 + "\n")
            f.write(f"# Platform: {self.config['name']}\n")
            f.write(f"# ROM: {self.rom_path.name}\n")
            f.write(f"# Total strings: {len(texts)}\n")
            f.write(f"# Encoding: ASCII (0x20-0x7E)\n")
            f.write(f"# Endian: {self.config['endian']}\n")
            f.write("#\n")
            f.write("# Format: [offset_hex] text\n")
            f.write("# " + "="*68 + "\n\n")

            for item in texts:
                f.write(f"[{item['offset_hex']}] {item['text']}\n")

        print(f"💾 Arquivo salvo: {output_path}\n")
        return str(output_path)

    def extract_and_save(self, output_path: Optional[str] = None, min_length: int = 4) -> Tuple[List[Dict], str]:
        """
        Extrai e salva textos em uma única operação

        Args:
            output_path: Caminho de saída
            min_length: Tamanho mínimo da string

        Returns:
            Tupla (textos, caminho_arquivo)
        """
        texts = self.extract_texts(min_length=min_length)
        saved_path = self.save_texts(texts, output_path)
        return texts, saved_path


def main():
    """CLI Interface"""
    import sys

    print("="*70)
    print("  NeuroROM AI - Sega Text Extractor")
    print("  Master System + Mega Drive/Genesis")
    print("="*70)
    print()

    if len(sys.argv) < 2:
        print("Uso:")
        print(f"  python {Path(__file__).name} <rom_file> [output.txt]")
        print()
        print("Exemplos:")
        print(f"  python {Path(__file__).name} sonic.gen")
        print(f"  python {Path(__file__).name} alex_kidd.sms custom_output.txt")
        print()
        sys.exit(1)

    rom_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        extractor = SegaExtractor(rom_path)
        texts, saved_path = extractor.extract_and_save(output_path)

        print(f"✅ Extração concluída!")
        print(f"📊 {len(texts)} strings extraídas")
        print(f"💾 Arquivo: {saved_path}")

    except Exception as e:
        print(f"❌ ERRO: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
