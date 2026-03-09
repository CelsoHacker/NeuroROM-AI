#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VALIDADOR FINAL - SUPER MARIO WORLD
====================================

Aplica validação rigorosa baseada em:
1. Dicionário de palavras conhecidas do SMW
2. Padrões de texto real
3. Remoção de sequências repetitivas
"""

from pathlib import Path
from typing import List, Set
import re


class SMWTextValidator:
    """Validador rigoroso de textos do Super Mario World."""

    # Dicionário de palavras conhecidas do SMW (inglês)
    KNOWN_WORDS = {
        # Personagens
        'MARIO', 'LUIGI', 'YOSHI', 'BOWSER', 'PEACH', 'TOAD', 'KOOPA', 'IGGY',
        'PRINCESS', 'TOADSTOOL',

        # Mundos e níveis
        'WORLD', 'STAR', 'SPECIAL', 'DONUT', 'VANILLA', 'CHOCOLATE',
        'FOREST', 'VALLEY', 'ISLAND', 'PLAINS', 'DOME', 'SODA', 'LAKE',
        'BUTTER', 'CHEESE', 'BRIDGE', 'SUNKEN', 'GHOST', 'SHIP', 'HOUSE',
        'CASTLE', 'FORTRESS', 'PALACE', 'SWITCH', 'SECRET', 'TOP', 'AREA',

        # Itens e power-ups
        'COIN', 'COINS', 'STAR', 'STARS', 'MUSHROOM', 'FLOWER', 'FEATHER',
        'CAPE', 'FIRE', 'POWER', 'SHELL', 'BLOCK', 'BONUS', 'DRAGON',

        # Ações
        'JUMP', 'SPIN', 'RUN', 'PRESS', 'BUTTON', 'START', 'SELECT',
        'STOMP', 'HOLD', 'USE', 'CONTINUE', 'SAVE', 'EXIT',

        # Status
        'TIME', 'LIVES', 'SCORE', 'GAME', 'OVER', 'EXTRA',

        # Palavras comuns em mensagens
        'THE', 'AND', 'YOU', 'CAN', 'WILL', 'ARE', 'HAVE', 'NAME', 'THIS',
        'FIND', 'WHEN', 'THAT', 'FROM', 'WITH', 'YOUR', 'BEEN', 'ALSO',
        'PUSH', 'PULL', 'HELP', 'SAVE', 'TRAPPED', 'STRANGE', 'NEW',
        'BIG', 'HIGH', 'FAST', 'AIR', 'BOX', 'TOP'
    }

    @staticmethod
    def has_known_word(text: str) -> bool:
        """Verifica se texto contém palavra conhecida."""
        text_upper = text.upper().replace('-', ' ')
        words = text_upper.split()

        for word in words:
            # Remove pontuação
            word_clean = re.sub(r'[^A-Z]', '', word)
            if word_clean in SMWTextValidator.KNOWN_WORDS:
                return True

        # Verifica substrings para palavras compostas
        for known_word in SMWTextValidator.KNOWN_WORDS:
            if len(known_word) >= 4 and known_word in text_upper:
                return True

        return False

    @staticmethod
    def is_repetitive(text: str) -> bool:
        """Detecta padrões repetitivos."""
        # Remove espaços e hífens
        text_clean = text.replace(' ', '').replace('-', '').upper()

        if len(text_clean) < 6:
            return False

        # Detecta repetição de 2-4 caracteres
        for pattern_len in [2, 3, 4]:
            if len(text_clean) >= pattern_len * 3:
                pattern = text_clean[:pattern_len]
                # Verifica se >60% do texto é repetição desse padrão
                matches = text_clean.count(pattern)
                if matches * pattern_len > len(text_clean) * 0.6:
                    return True

        # Detecta caractere único repetido (AAAA, BBBB)
        if len(set(text_clean)) <= 2:
            return True

        return False

    @staticmethod
    def has_valid_structure(text: str) -> bool:
        """Valida estrutura de texto real."""
        # Pelo menos 4 caracteres
        if len(text) < 4:
            return False

        # Pelo menos 60% alfabético
        alpha_count = sum(1 for c in text if c.isalpha())
        if alpha_count < len(text) * 0.6:
            return False

        # Pelo menos 1 vogal
        vowels = set('AEIOUaeiou')
        if not any(c in vowels for c in text):
            return False

        # Não pode ter >40% de caracteres especiais
        special_count = sum(1 for c in text if not c.isalnum() and c not in ' -')
        if special_count > len(text) * 0.4:
            return False

        return True

    @classmethod
    def is_valid(cls, text: str) -> bool:
        """Validação completa."""
        # Rejeita se repetitivo
        if cls.is_repetitive(text):
            return False

        # Rejeita se estrutura inválida
        if not cls.has_valid_structure(text):
            return False

        # APROVADO se contém palavra conhecida
        if cls.has_known_word(text):
            return True

        # Caso contrário, rejeita
        return False


def validate_and_filter(input_file: str, output_file: str):
    """Valida e filtra textos."""
    print("=" * 80)
    print("✅ VALIDADOR FINAL - SUPER MARIO WORLD")
    print("=" * 80)
    print()

    # Carrega textos
    input_path = Path(input_file)
    print(f"📂 Carregando: {input_path.name}")

    with open(input_path, 'r', encoding='utf-8') as f:
        texts = [line.strip() for line in f if line.strip()]

    print(f"✅ {len(texts)} textos carregados")
    print()

    # Valida
    print("🔍 Aplicando validação rigorosa...")

    valid_texts = []
    rejected_repetitive = 0
    rejected_structure = 0
    rejected_no_keywords = 0

    validator = SMWTextValidator()

    for text in texts:
        if validator.is_repetitive(text):
            rejected_repetitive += 1
        elif not validator.has_valid_structure(text):
            rejected_structure += 1
        elif not validator.has_known_word(text):
            rejected_no_keywords += 1
        else:
            valid_texts.append(text)

    print(f"✅ {len(valid_texts)} textos válidos")
    print(f"❌ {rejected_repetitive} rejeitados (repetitivos)")
    print(f"❌ {rejected_structure} rejeitados (estrutura inválida)")
    print(f"❌ {rejected_no_keywords} rejeitados (sem palavras conhecidas)")
    print()

    # Remove duplicatas
    valid_texts = list(dict.fromkeys(valid_texts))

    # Ordena por tamanho
    valid_texts.sort(key=lambda x: (-len(x), x.upper()))

    # Salva
    output_path = Path(output_file)
    with open(output_path, 'w', encoding='utf-8') as f:
        for text in valid_texts:
            f.write(f"{text}\n")

    print("=" * 80)
    print("📝 TEXTOS VÁLIDOS DO SUPER MARIO WORLD:")
    print("=" * 80)
    print()

    for i, text in enumerate(valid_texts, 1):
        print(f"{i:3d}. {text}")

    print()
    print("=" * 80)
    print(f"💾 {len(valid_texts)} textos salvos em: {output_path.name}")
    print("=" * 80)

    return valid_texts


def main():
    """Função principal."""

    # Valida arquivo HEURISTIC
    heuristic_file = r"C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework\ROMs\Super Nintedo\Super Mario World_HEURISTIC.txt"
    heuristic_output = r"C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework\ROMs\Super Nintedo\Super Mario World_HEURISTIC_VALID.txt"

    if Path(heuristic_file).exists():
        print("🔍 Validando extração heurística...")
        print()
        valid_heuristic = validate_and_filter(heuristic_file, heuristic_output)
        print()

    # Valida arquivo CONSOLIDATED (melhor resultado)
    consolidated_file = r"C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework\ROMs\Super Nintedo\Super Mario World_CONSOLIDATED.txt"
    consolidated_output = r"C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework\ROMs\Super Nintedo\Super Mario World_FINAL.txt"

    if Path(consolidated_file).exists():
        print("\n" + "=" * 80)
        print("🔍 Validando extração consolidada (MELHOR RESULTADO)...")
        print("=" * 80)
        print()
        valid_consolidated = validate_and_filter(consolidated_file, consolidated_output)

        # Estatísticas finais
        print("\n" + "=" * 80)
        print("🎉 RESULTADO FINAL DA EXTRAÇÃO")
        print("=" * 80)
        print(f"📊 Total de textos válidos: {len(valid_consolidated)}")
        print(f"📝 Prontos para tradução!")
        print("=" * 80)


if __name__ == '__main__':
    main()
