#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOLUÇÃO FINAL: Decodificador + Validação
Decodifica character table customizada e valida se é texto real
"""

import re
from pathlib import Path
from typing import List, Tuple

def decode_char_table(text: str, shift: int = -1) -> str:
    """
    Decodifica texto com character table shift
    Super Mario World usa shift de -1: @ = A, A = B, B = C, etc.

    Args:
        text: Texto codificado
        shift: Valor do shift (negativo = volta, positivo = avança)

    Returns:
        Texto decodificado
    """
    decoded = []
    for char in text:
        if 'A' <= char <= 'Z':
            # Aplica shift circular no alfabeto
            new_char = chr((ord(char) - ord('A') - shift) % 26 + ord('A'))
            decoded.append(new_char)
        elif 'a' <= char <= 'z':
            new_char = chr((ord(char) - ord('a') - shift) % 26 + ord('a'))
            decoded.append(new_char)
        elif char == '@':
            # @ geralmente representa A
            decoded.append('A')
        else:
            decoded.append(char)

    return ''.join(decoded)


def is_real_english_word_pattern(text: str) -> bool:
    """
    Verifica se o texto parece ser palavras inglesas reais
    """
    # Palavras/padrões comuns em jogos
    game_words = [
        'MARIO', 'WORLD', 'SUPER', 'STAR', 'POWER', 'PRESS', 'START',
        'GAME', 'BONUS', 'COIN', 'LIVES', 'SCORE', 'TIME', 'OVER',
        'PLAYER', 'FRIEND', 'BLOCK', 'JUMP', 'SPIN', 'HELP', 'SAVE',
        'RESCUE', 'TRAP', 'ENEMY', 'BOSS', 'CASTLE', 'EXIT', 'PUSH',
        'PULL', 'PICK', 'THROW', 'CATCH', 'RUN', 'WALK', 'SWIM',
        'CLIMB', 'FALL', 'HURT', 'WIN', 'LOSE', 'TRY', 'AGAIN',
        'CONTINUE', 'PAUSE', 'MENU', 'OPTION', 'SOUND', 'MUSIC',
        'SWITCH', 'BUTTON', 'SPECIAL', 'SECRET', 'HIDDEN', 'FOUND',
        'COMPLETE', 'EXPLORE', 'DIFFERENT', 'PLACE', 'AREA', 'ZONE',
        'DEFEAT', 'POINT', 'STOMP', 'BREAK', 'HIT', 'MISS', 'GOOD',
        'GREAT', 'PERFECT', 'NICE', 'COOL', 'YEAH', 'WOW', 'READY',
        'GO', 'STOP', 'WAIT', 'YES', 'NO', 'OK', 'CANCEL', 'SELECT',
        'CONFIRM', 'BACK', 'NEXT', 'PREV', 'UP', 'DOWN', 'LEFT', 'RIGHT',
        'YOSHI', 'LUIGI', 'PEACH', 'BOWSER', 'KOOPA', 'GOOMBA',
        'SHELL', 'FIRE', 'FLOWER', 'MUSHROOM', 'CAPE', 'FEATHER',
        'PRINCESS', 'TRAPPED', 'POSSIBLE', 'IMPOSSIBLE', 'EASY', 'HARD',
        'BALANCE', 'FURTHER', 'BETWEEN', 'AROUND', 'THROUGH', 'ACROSS',
        'TOWARD', 'FENCE', 'POOL', 'WATER', 'LAVA', 'CLOUD', 'SKY',
        'GROUND', 'PIPE', 'DOOR', 'KEY', 'CHEST', 'TREASURE', 'ITEM',
        'FILL', 'EMPTY', 'FULL', 'HALF', 'WHOLE', 'PART', 'SOME', 'ALL',
        'MANY', 'FEW', 'MORE', 'LESS', 'MOST', 'LEAST', 'BEST', 'WORST',
    ]

    # Verifica se o texto contém alguma palavra conhecida
    for word in game_words:
        if word in text:
            return True

    # Verifica sufixos comuns
    if re.search(r'(ED|ING|S|LY|ER|EST|TION|NESS|MENT|ABLE|LESS)$', text):
        return True

    # Padrões de consoante-vogal comuns
    vowels = set('AEIOU')
    consonants = set('BCDFGHJKLMNPQRSTVWXYZ')

    # Conta sequências CV (consoante-vogal)
    cv_count = 0
    for i in range(len(text) - 1):
        if text[i] in consonants and text[i+1] in vowels:
            cv_count += 1

    # Texto real tem muitas sequências CV
    if len(text) >= 6 and cv_count >= len(text) * 0.3:
        return True

    return False


def extract_game_text(input_file: str) -> List[Tuple[str, str]]:
    """
    Extrai texto REAL do jogo usando decodificação + validação

    Returns:
        Lista de tuplas (texto_original, texto_decodificado)
    """
    print("=" * 70)
    print("🎮 EXTRATOR FINAL - Character Table + Validação")
    print("=" * 70)

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    print(f"📊 Total de linhas: {len(lines)}\n")

    valid_texts = []
    stats = {'decoded_valid': 0, 'original_valid': 0, 'rejected': 0}

    for text in lines:
        # Testa o texto original
        if is_real_english_word_pattern(text):
            valid_texts.append((text, text))
            stats['original_valid'] += 1
            continue

        # Testa com shift de -1 (padrão Super Mario World)
        decoded = decode_char_table(text, shift=-1)
        if is_real_english_word_pattern(decoded):
            valid_texts.append((text, decoded))
            stats['decoded_valid'] += 1
            continue

        # Testa outros shifts comuns
        for shift in [1, -2, 2]:
            decoded = decode_char_table(text, shift=shift)
            if is_real_english_word_pattern(decoded):
                valid_texts.append((text, decoded))
                stats['decoded_valid'] += 1
                break
        else:
            stats['rejected'] += 1

    return valid_texts, stats


def main():
    input_file = r"C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework\ROMs\Super Nintedo\Super Mario World_optimized.txt"

    if not Path(input_file).exists():
        print(f"❌ Arquivo não encontrado: {input_file}")
        return

    valid_texts, stats = extract_game_text(input_file)

    print("\n" + "=" * 70)
    print("📈 RESULTADOS:")
    print("=" * 70)
    print(f"✅ Textos válidos (original): {stats['original_valid']:,}")
    print(f"✅ Textos válidos (decodificados): {stats['decoded_valid']:,}")
    print(f"📊 Total válidos: {len(valid_texts):,}")
    print(f"❌ Rejeitados: {stats['rejected']:,}")

    print("\n" + "=" * 70)
    print("✅ TEXTOS EXTRAÍDOS (Original → Decodificado):")
    print("=" * 70)

    for i, (original, decoded) in enumerate(valid_texts, 1):
        if original == decoded:
            print(f"{i:3d}. {original}")
        else:
            print(f"{i:3d}. {original:30s} → {decoded}")

    # Salva resultado
    output_file = str(Path(input_file).with_stem(Path(input_file).stem + "_FINAL_CLEAN"))
    with open(output_file, 'w', encoding='utf-8') as f:
        for original, decoded in valid_texts:
            f.write(f"{decoded}\n")  # Salva versão decodificada

    print("\n" + "=" * 70)
    print(f"💾 Arquivo final salvo: {Path(output_file).name}")
    print("=" * 70)


if __name__ == "__main__":
    main()
