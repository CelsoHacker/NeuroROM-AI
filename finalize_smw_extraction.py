#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FINALIZAÇÃO DA EXTRAÇÃO DO SUPER MARIO WORLD
=============================================

Script final que:
1. Decodifica character table customizada
2. Aplica filtros ultra-rigorosos
3. Valida palavras reais do jogo
4. Gera lista limpa de textos prontos para tradução
"""

import re
from pathlib import Path
from typing import List, Tuple


def decode_char_table(text: str, shift: int = -1) -> str:
    """
    Decodifica texto com character table shift.
    Super Mario World usa shift de -1: @ = A, A = B, etc.
    """
    decoded = []
    for char in text:
        if 'A' <= char <= 'Z':
            new_char = chr((ord(char) - ord('A') - shift) % 26 + ord('A'))
            decoded.append(new_char)
        elif 'a' <= char <= 'z':
            new_char = chr((ord(char) - ord('a') - shift) % 26 + ord('a'))
            decoded.append(new_char)
        elif char == '@':
            decoded.append('A')
        else:
            decoded.append(char)
    return ''.join(decoded)


def is_valid_smw_text(text: str, decoded_text: str) -> Tuple[bool, str]:
    """
    Valida se é texto real do Super Mario World.

    Returns:
        (is_valid, reason)
    """
    # Lista de palavras conhecidas do SMW (inglês)
    smw_keywords = {
        'MARIO', 'LUIGI', 'YOSHI', 'BOWSER', 'PEACH', 'TOAD',
        'SUPER', 'WORLD', 'STAR', 'POWER', 'FIRE', 'CAPE',
        'JUMP', 'RUN', 'SPIN', 'STOMP', 'SWIM', 'CLIMB',
        'COIN', 'MUSHROOM', 'FLOWER', 'FEATHER', 'SHELL',
        'GOOMBA', 'KOOPA', 'PIRANHA', 'THWOMP', 'BOB-OMB',
        'LEVEL', 'CASTLE', 'GHOST', 'HOUSE', 'FORTRESS',
        'SWITCH', 'BLOCK', 'BONUS', 'SECRET', 'HIDDEN',
        'LIVES', 'TIME', 'SCORE', 'GAME', 'OVER', 'START',
        'PRESS', 'BUTTON', 'CONTINUE', 'SAVE', 'OPTION',
        'FRIEND', 'FRIENDS', 'POSSIBLE', 'FILL', 'PICK',
        'PUSH', 'PUSHED', 'RESCUE', 'TRAPPED', 'HELP',
        'DEFEAT', 'ENEMY', 'POINT', 'POINTS', 'BREAK',
        'FENCE', 'POOL', 'WATER', 'LAVA', 'DIFFERENT',
        'PLACE', 'PLACES', 'FURTHER', 'BETWEEN', 'TOWARD',
        'COMPLETE', 'EXPLORE', 'FIND', 'FOUND', 'LOST',
        'LEFT', 'RIGHT', 'DOWN', 'JUST', 'MIDDLE',
        'PRESSING', 'JUMPING', 'BALANCE', 'ABLE', 'SPECIAL'
    }

    # Testa texto original
    text_upper = text.upper()
    for keyword in smw_keywords:
        if keyword in text_upper:
            return True, f"Palavra-chave encontrada: {keyword}"

    # Testa texto decodificado
    decoded_upper = decoded_text.upper()
    for keyword in smw_keywords:
        if keyword in decoded_upper:
            return True, f"Palavra-chave (decodificada): {keyword}"

    # Verifica padrões de texto válido do SMW
    # 1. Deve ter pelo menos 4 caracteres
    if len(decoded_text) < 4:
        return False, "Muito curto"

    # 2. Não pode ter números misturados
    if re.search(r'[A-Za-z]+[0-9]{2,}', decoded_text):
        return False, "Números misturados"

    # 3. Não pode ter caracteres repetidos 4+
    if re.search(r'(.)\1{3,}', decoded_text):
        return False, "Caracteres repetidos"

    # 4. Deve ter pelo menos 2 vogais
    vowel_count = sum(1 for c in decoded_text if c.upper() in 'AEIOU')
    if vowel_count < 2:
        return False, "Poucas vogais"

    # 5. Deve ser principalmente letras
    letter_count = sum(1 for c in decoded_text if c.isalpha())
    if letter_count < len(decoded_text) * 0.7:
        return False, "Poucos caracteres alfabéticos"

    # 6. Não pode ter muitos símbolos estranhos
    strange_chars = sum(1 for c in decoded_text if c in '@#$%^&*()[]{}\\|<>')
    if strange_chars > 2:
        return False, "Muitos símbolos estranhos"

    # 7. Padrões comuns de texto do SMW
    # SMW usa principalmente MAIÚSCULAS
    upper_count = sum(1 for c in decoded_text if c.isupper())
    lower_count = sum(1 for c in decoded_text if c.islower())

    # Se tem mix muito balanceado, provável lixo
    if lower_count > 0 and upper_count > 0:
        if abs(lower_count - upper_count) <= 2 and len(decoded_text) < 10:
            return False, "Mix suspeito maiúsc/minúsc"

    # Se passou todas as verificações mas não tem palavra-chave,
    # é provável que seja lixo
    return False, "Não contém palavras conhecidas do SMW"


def finalize_smw_extraction(input_file: str):
    """
    Finaliza a extração do Super Mario World.

    Processa o arquivo otimizado e gera lista final limpa.
    """
    print("=" * 80)
    print("🎮 FINALIZAÇÃO DA EXTRAÇÃO - SUPER MARIO WORLD")
    print("=" * 80)
    print()

    # Lê arquivo otimizado atual
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    print(f"📂 Arquivo de entrada: {Path(input_file).name}")
    print(f"📊 Total de linhas: {len(lines)}")
    print()

    valid_texts = []
    stats = {
        'total': len(lines),
        'valid_original': 0,
        'valid_decoded': 0,
        'rejected': 0,
        'reasons': {}
    }

    print("🔍 Processando textos...")
    print()

    # Processa cada linha
    for text in lines:
        # Tenta validar o texto original
        is_valid_orig, reason_orig = is_valid_smw_text(text, text)

        if is_valid_orig:
            valid_texts.append((text, text, reason_orig))
            stats['valid_original'] += 1
            continue

        # Tenta decodificar com shift -1
        decoded = decode_char_table(text, shift=-1)
        is_valid_dec, reason_dec = is_valid_smw_text(text, decoded)

        if is_valid_dec:
            valid_texts.append((text, decoded, reason_dec))
            stats['valid_decoded'] += 1
            continue

        # Tenta outros shifts
        found = False
        for shift in [1, -2, 2]:
            decoded_alt = decode_char_table(text, shift=shift)
            is_valid_alt, reason_alt = is_valid_smw_text(text, decoded_alt)

            if is_valid_alt:
                valid_texts.append((text, decoded_alt, reason_alt))
                stats['valid_decoded'] += 1
                found = True
                break

        if not found:
            stats['rejected'] += 1
            if reason_dec not in stats['reasons']:
                stats['reasons'][reason_dec] = 0
            stats['reasons'][reason_dec] += 1

    # Relatório
    print("=" * 80)
    print("📈 RESULTADOS:")
    print("=" * 80)
    print(f"Total processado: {stats['total']:,}")
    print(f"  ✅ Válidos (original): {stats['valid_original']:,}")
    print(f"  ✅ Válidos (decodificados): {stats['valid_decoded']:,}")
    print(f"  📊 Total válidos: {len(valid_texts):,}")
    print(f"  ❌ Rejeitados: {stats['rejected']:,}")
    print()

    # Taxa de limpeza
    if stats['total'] > 0:
        clean_rate = (len(valid_texts) / stats['total']) * 100
        print(f"📊 Taxa de aprovação: {clean_rate:.1f}%")
        print(f"🧹 Taxa de limpeza: {(stats['rejected'] / stats['total']) * 100:.1f}%")
    print()

    # Motivos de rejeição (top 5)
    if stats['reasons']:
        print("🔍 Top 5 motivos de rejeição:")
        sorted_reasons = sorted(stats['reasons'].items(), key=lambda x: x[1], reverse=True)
        for reason, count in sorted_reasons[:5]:
            print(f"  • {reason}: {count:,}")
        print()

    # Mostra textos válidos
    print("=" * 80)
    print("✅ TEXTOS VÁLIDOS DO SUPER MARIO WORLD:")
    print("=" * 80)
    print()

    for i, (original, decoded, reason) in enumerate(valid_texts, 1):
        if original == decoded:
            print(f"{i:3d}. {original}")
        else:
            print(f"{i:3d}. {original:30s} → {decoded}")

    print()

    # Salva resultados
    output_file = str(Path(input_file).with_stem(Path(input_file).stem + "_FINAL"))
    output_file_decoded = str(Path(input_file).with_stem(Path(input_file).stem + "_FINAL_DECODED"))

    # Salva versão original
    with open(output_file, 'w', encoding='utf-8') as f:
        for original, _, _ in valid_texts:
            f.write(f"{original}\n")

    # Salva versão decodificada (pronta para tradução)
    with open(output_file_decoded, 'w', encoding='utf-8') as f:
        for _, decoded, _ in valid_texts:
            f.write(f"{decoded}\n")

    print("=" * 80)
    print("💾 ARQUIVOS SALVOS:")
    print("=" * 80)
    print(f"  📄 Original: {Path(output_file).name}")
    print(f"  📄 Decodificado: {Path(output_file_decoded).name}")
    print()

    # Estatísticas finais
    print("=" * 80)
    print("✅ EXTRAÇÃO FINALIZADA!")
    print("=" * 80)
    print()
    print(f"🎮 {len(valid_texts)} textos do Super Mario World prontos para tradução!")
    print()

    return valid_texts


def main():
    """Função principal."""

    # Arquivo de entrada (gerado anteriormente)
    input_file = r"C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework\ROMs\Super Nintedo\Super Mario World_REFINED.txt"

    if not Path(input_file).exists():
        print(f"❌ Arquivo não encontrado: {input_file}")
        print()
        print("Verifique o caminho e tente novamente.")
        return

    # Executa finalização
    valid_texts = finalize_smw_extraction(input_file)

    # Mensagem final
    if len(valid_texts) > 20:
        print("✅ SUCESSO! Extração completa e validada.")
    elif len(valid_texts) > 10:
        print("⚠️ ATENÇÃO! Poucos textos extraídos. Revise os resultados.")
    else:
        print("❌ PROBLEMA! Muito poucos textos válidos encontrados.")

    print()


if __name__ == '__main__':
    main()
