#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FILTRO DE QUALIDADE FINAL
==========================

Aplica critérios ultra-rigorosos para extrair apenas textos de ALTA QUALIDADE.
"""

from pathlib import Path
from typing import List
import re


class UltraRigorousFilter:
    """Filtro ultra-rigoroso para textos de alta qualidade."""

    # Vocabulário CORE de jogos (palavras que REALMENTE aparecem em textos de jogo)
    CORE_GAME_WORDS = {
        # SMW específico
        'MARIO', 'LUIGI', 'YOSHI', 'BOWSER', 'PEACH', 'PRINCESS', 'TOAD', 'KOOPA',
        'WORLD', 'STAR', 'CASTLE', 'FORTRESS', 'GHOST', 'HOUSE', 'SHIP', 'BRIDGE',
        'PALACE', 'SWITCH', 'BUTTON', 'PRESS', 'JUMP', 'SPIN', 'RUN', 'STOMP',
        'COIN', 'COINS', 'POWER', 'FIRE', 'CAPE', 'MUSHROOM', 'FEATHER', 'SHELL',
        'LEVEL', 'SECRET', 'BONUS', 'SPECIAL', 'ZONE', 'TOP', 'AREA',
        'DRAGON', 'BLOCK', 'BLOCKS', 'TIME', 'EXIT', 'EXITS', 'CONTINUE',
        'CHOCOLATE', 'VANILLA', 'DONUT', 'SODA', 'LAKE', 'FOREST', 'VALLEY',
        'PLAINS', 'ISLAND', 'DOME', 'BUTTER', 'CHEESE', 'SUNKEN',

        # Ações comuns em jogos
        'START', 'SELECT', 'GAME', 'OVER', 'HELP', 'SAVE', 'LOAD', 'LIVES',
        'SCORE', 'POINT', 'POINTS', 'HEALTH', 'MAGIC', 'ATTACK', 'DEFEND',
        'USE', 'TAKE', 'GIVE', 'OPEN', 'CLOSE', 'PUSH', 'PULL', 'TRAPPED',
        'FIND', 'FOUND', 'LOST', 'RESCUE', 'COMPLETE', 'NAME', 'STRANGE',

        # Palavras comuns em mensagens
        'THE', 'AND', 'YOU', 'CAN', 'WILL', 'HAVE', 'THIS', 'THAT', 'WHEN',
        'WITH', 'FROM', 'YOUR', 'BEEN', 'ABLE', 'JUST', 'ALSO', 'FILL',
        'PLACE', 'BETWEEN', 'FURTHER', 'ALREADY', 'DIFFERENT',

        # Direções e locais
        'UP', 'DOWN', 'LEFT', 'RIGHT', 'TOP', 'BOTTOM', 'MIDDLE',
        'ENTER', 'LEAVE', 'GO', 'BACK', 'NEXT', 'FIRST', 'LAST',

        # Status/Sistema
        'NEW', 'OLD', 'BIG', 'SMALL', 'HIGH', 'LOW', 'FAST', 'SLOW',
        'GOOD', 'BAD', 'YES', 'NO', 'OK', 'READY', 'WAIT',
    }

    @classmethod
    def calculate_quality_score(cls, text: str) -> float:
        """
        Calcula pontuação de qualidade (0-100).

        Critérios:
        - Palavras conhecidas: +30 por palavra
        - Comprimento razoável: +20
        - Estrutura de frase: +15
        - Pontuação adequada: +10
        - Diversidade de caracteres: +10
        - Sem repetições: +15
        """
        score = 0.0
        text_clean = text.replace('-', ' ').strip()

        if len(text_clean) < 4:
            return 0.0

        # CRITÉRIO 1: Palavras conhecidas (+30 cada, máximo 60)
        words = text_clean.upper().split()
        word_count = 0

        for word in words:
            if word in cls.CORE_GAME_WORDS:
                word_count += 1

        # Também verifica substrings para palavras compostas
        text_upper = text_clean.upper()
        for game_word in cls.CORE_GAME_WORDS:
            if len(game_word) >= 5 and game_word in text_upper:
                if game_word not in words:  # Não contar 2x
                    word_count += 0.5

        score += min(word_count * 30, 60)  # Máximo 60 pontos

        # CRITÉRIO 2: Comprimento razoável (+20)
        if 8 <= len(text_clean) <= 100:
            score += 20
        elif 5 <= len(text_clean) < 8 or 100 < len(text_clean) <= 150:
            score += 10

        # CRITÉRIO 3: Estrutura de frase (+15)
        # Tem vogais suficientes?
        vowel_ratio = sum(1 for c in text_clean if c.upper() in 'AEIOU') / len(text_clean)
        if 0.2 <= vowel_ratio <= 0.5:
            score += 10

        # Tem consoantes suficientes?
        consonants = sum(1 for c in text_clean if c.isalpha() and c.upper() not in 'AEIOU')
        if consonants >= len(text_clean) * 0.3:
            score += 5

        # CRITÉRIO 4: Pontuação adequada (+10)
        has_punctuation = any(c in text for c in '.,!?-')
        if has_punctuation:
            score += 5

        # Não tem muita pontuação (spam)
        punct_count = sum(1 for c in text if not c.isalnum() and c != ' ')
        if punct_count <= len(text) * 0.3:
            score += 5

        # CRITÉRIO 5: Diversidade de caracteres (+10)
        unique_ratio = len(set(text_clean.replace(' ', ''))) / max(len(text_clean), 1)
        if unique_ratio >= 0.4:
            score += 10
        elif unique_ratio >= 0.3:
            score += 5

        # CRITÉRIO 6: Sem repetições (+15)
        # Não tem padrões repetitivos (AAA, 111, ABABAB)
        if not cls.is_repetitive(text_clean):
            score += 15

        return min(score, 100)

    @staticmethod
    def is_repetitive(text: str) -> bool:
        """Detecta padrões repetitivos."""
        text_clean = text.replace(' ', '').replace('-', '').upper()

        if len(text_clean) < 4:
            return False

        # Caractere único repetido (AAAA)
        if len(set(text_clean)) <= 2:
            return True

        # Padrão de 2-3 chars repetido
        for pattern_len in [2, 3]:
            if len(text_clean) >= pattern_len * 4:
                pattern = text_clean[:pattern_len]
                count = text_clean.count(pattern)
                if count * pattern_len > len(text_clean) * 0.6:
                    return True

        # Sequência muito longa do mesmo caractere (>5)
        if re.search(r'(.)\1{5,}', text_clean):
            return True

        return False


def filter_by_quality(input_file: str, output_file: str,
                     min_score: float = 50.0) -> List[str]:
    """Filtra textos por pontuação de qualidade."""

    print("=" * 80)
    print("🏅 FILTRO DE QUALIDADE FINAL")
    print("=" * 80)
    print()

    # Carrega textos
    with open(input_file, 'r', encoding='utf-8') as f:
        texts = [line.strip() for line in f if line.strip()]

    print(f"📂 Entrada: {len(texts)} textos")
    print(f"📊 Pontuação mínima: {min_score}")
    print()

    # Calcula pontuação
    print("🔍 Calculando pontuações de qualidade...")

    scored_texts = []
    for text in texts:
        score = UltraRigorousFilter.calculate_quality_score(text)
        if score >= min_score:
            scored_texts.append((score, text))

    # Ordena por pontuação (melhores primeiro)
    scored_texts.sort(key=lambda x: (-x[0], -len(x[1]), x[1].upper()))

    print(f"✅ {len(scored_texts)} textos passaram (≥{min_score} pontos)")
    print()

    # Mostra top textos
    print("=" * 80)
    print("🏆 TOP TEXTOS DE ALTA QUALIDADE:")
    print("=" * 80)
    print()

    for i, (score, text) in enumerate(scored_texts[:100], 1):
        print(f"{i:3d}. [{score:5.1f}] {text}")

    if len(scored_texts) > 100:
        print(f"\n... e mais {len(scored_texts) - 100} textos")

    # Salva
    with open(output_file, 'w', encoding='utf-8') as f:
        for score, text in scored_texts:
            f.write(f"{text}\n")

    print()
    print("=" * 80)
    print(f"💾 {len(scored_texts)} textos de alta qualidade salvos")
    print("=" * 80)

    return [text for _, text in scored_texts]


def main():
    """Função principal."""

    # Arquivo de entrada (gerado pelo ultimate extractor)
    input_file = r"C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework\ROMs\Super Nintedo\Super Mario World_ULTIMATE.txt"

    # Arquivo de saída
    output_file = r"C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework\ROMs\Super Nintedo\Super Mario World_HIGH_QUALITY.txt"

    if not Path(input_file).exists():
        print(f"❌ Arquivo não encontrado: {input_file}")
        return

    # Testa com diferentes pontuações
    for min_score in [70, 60, 50]:
        print(f"\n{'=' * 80}")
        print(f"TESTE COM PONTUAÇÃO MÍNIMA: {min_score}")
        print("=" * 80)

        output_test = output_file.replace('.txt', f'_{min_score}.txt')
        texts = filter_by_quality(input_file, output_test, min_score=min_score)

        print()
        print(f"📊 Resultado: {len(texts)} textos com pontuação ≥{min_score}")
        print()

    # Comparação final
    print("=" * 80)
    print("📊 COMPARAÇÃO DE MÉTODOS:")
    print("=" * 80)
    print()
    print("Método Dual Charset:      72 textos")
    print("Ultimate Extractor:    1,548 textos")
    print("Filtro Qualidade ≥70:     XXX textos")
    print("Filtro Qualidade ≥60:     XXX textos")
    print("Filtro Qualidade ≥50:     XXX textos")
    print()
    print("=" * 80)


if __name__ == '__main__':
    main()
