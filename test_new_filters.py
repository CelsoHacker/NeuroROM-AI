#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Teste: Valida os Novos Filtros Implementados
Aplica os mesmos filtros do interface_tradutor_final.py no arquivo atual
"""

import re
from pathlib import Path

def apply_new_filters(text: str) -> tuple[bool, str]:
    """
    Aplica TODOS os novos filtros implementados

    Returns:
        (is_garbage, reason) - True se for lixo, False se for válido
    """
    # FILTRO 3: TAMANHO MÍNIMO (4 caracteres)
    if len(text) < 4:
        return True, "Muito curto (< 4 chars)"

    # FILTRO 4: VERIFICAR VOGAIS
    if not re.search(r'[aeiouAEIOU]', text):
        return True, "Sem vogais"

    # FILTRO 5: REJEITAR CÓDIGOS
    if any(char in text for char in ['{', '}', '\\', '/']):
        return True, "Caracteres de código"

    # ========== FILTROS 6.1 a 6.13 ==========

    # 6.1: Endereços hexadecimais e padrões numéricos
    if re.search(r'(0x[0-9A-Fa-f]+|\$[0-9A-Fa-f]{2,}|^[0-9A-F]{4,}$|[0-9]{2,}[><@#\-\+][0-9])', text):
        return True, "Lixo binário: endereços hex"

    # 6.2: Padrões hexadecimais com símbolos
    if re.search(r'[!@#$%^&*`][A-Z]{2,}', text):
        return True, "Lixo binário: símbolos + maiúsculas"
    if re.search(r'[A-Z]{2,}[\$&\*\^%#][A-Z&\$\*]', text):
        return True, "Lixo binário: letras + símbolos"
    if re.search(r'[0-9][A-F]{3,}', text):
        return True, "Lixo binário: números + hex"

    # 6.3: Sequências minúsculas/maiúsculas curtas
    if re.match(r'^[a-z`]{4,}$', text):
        return True, "Lixo binário: minúsculas consecutivas"
    if re.match(r'^[A-Z]{4,8}$', text) and not re.search(r'[AEIOU]', text):
        return True, "Lixo binário: maiúsculas sem vogais"

    # 6.4: Sequências aleatórias (gibberish)
    if re.search(r'[A-Z][a-z][A-Z]\(|[A-Z]:[A-Z]|[A-Z][a-z][A-Z]\)', text):
        return True, "Lixo binário: padrões caóticos"
    if len(text) >= 4:
        case_changes = sum(1 for i in range(len(text)-1)
                          if text[i].isupper() != text[i+1].isupper())
        if case_changes > len(text) * 0.6:
            return True, "Lixo binário: alternâncias maiúsc/minúsc"

    # 6.5: Caracteres especiais excessivos (>25%)
    special_chars = set('!@#$%^&*()_+-=[]{}|;:,.<>?/~`\\')
    special_count = sum(1 for char in text if char in special_chars)
    if len(text) > 0 and special_count / len(text) > 0.25:
        return True, "Lixo binário: muitos caracteres especiais"

    # 6.6: Repetição excessiva
    if len(text) > 5:
        unique_chars = len(set(text))
        if unique_chars < len(text) * 0.3:
            return True, "Lixo binário: poucos caracteres únicos"

    # 6.7: Sequências com números misturados
    if len(text) >= 6:
        num_letter_transitions = sum(1 for i in range(len(text)-2)
                                    if text[i].isdigit()
                                    and text[i+1].isalpha()
                                    and text[i+2].isdigit())
        if num_letter_transitions >= 2:
            return True, "Lixo binário: números misturados"

    # 6.8: Sequências longas sem espaços
    if len(text) > 15 and ' ' not in text:
        return True, "Lixo binário: muito longo sem espaços"

    # 6.9: Ratio de vogais/consoantes muito baixo
    if len(text) >= 4:
        vowel_count = sum(1 for c in text if c.lower() in 'aeiou')
        consonant_count = sum(1 for c in text if c.isalpha() and c.lower() not in 'aeiou')
        if consonant_count > 0 and vowel_count > 0 and (vowel_count / consonant_count) < 0.15:
            return True, "Lixo binário: ratio vogais/consoantes baixo"

    # 6.10: Caracteres repetidos consecutivos
    if re.search(r'(.)\1{3,}', text):
        return True, "Lixo binário: caracteres repetidos (4+)"

    # 6.11: Começar com símbolos especiais/números
    if re.match(r'^[@#$%^&*`0-9\[\]\(\)]', text):
        return True, "Lixo binário: inicia com símbolo/número"

    # 6.12: Strings curtas (4-6 chars) com caracteres especiais
    if 4 <= len(text) <= 6:
        special_chars = set('!@#$%^&*()_+-=[]{}|;:,.<>?/~`\\0123456789')
        if any(c in special_chars for c in text):
            return True, "Lixo binário: string curta + símbolos"

    # 6.13: Padrões de tiles/gráficos
    if len(text) >= 5:
        lower_count = sum(1 for c in text if c.islower())
        upper_count = sum(1 for c in text if c.isupper())
        if lower_count > 0 and upper_count > 0:
            if abs(lower_count - upper_count) <= 2:
                special_chars = set('!@#$%^&*()_+-=[]{}|;:,.<>?/~`\\0123456789')
                if any(c in special_chars for c in text):
                    return True, "Lixo binário: mix maiúsc/minúsc + símbolos"

    # 6.14: Sequências com números no meio
    if len(text) >= 6:
        if re.search(r'[A-Za-z]+[0-9]{3,}[A-Za-z]+', text):
            return True, "Lixo binário: números no meio de letras"

    # 6.15: Repetições de padrões de 2-3 caracteres
    if len(text) >= 6:
        for pattern_len in [2, 3]:
            for i in range(len(text) - pattern_len * 2):
                pattern = text[i:i+pattern_len]
                next_part = text[i+pattern_len:i+pattern_len*2]
                if pattern == next_part and pattern.isalpha():
                    return True, f"Lixo binário: padrão repetido ({pattern})"

    # 6.16: Strings curtas (<8) com mix maiúsc/minúsc
    if 4 <= len(text) < 8 and ' ' not in text:
        lower_count = sum(1 for c in text if c.islower())
        upper_count = sum(1 for c in text if c.isupper())
        if lower_count >= 1 and upper_count >= 1:
            if not text.isalpha():
                return True, "Lixo binário: string curta com mix"

    # 6.17: Termina com símbolos estranhos
    if re.search(r'["\]\)\|`]$', text):
        return True, "Lixo binário: termina com símbolo"

    # EXCEÇÕES: Palavras de jogos
    game_words = ['mario', 'world', 'super', 'player', 'start', 'pause', 'game', 'over',
                 'score', 'time', 'level', 'stage', 'lives', 'coin', 'press', 'continue',
                 'menu', 'option', 'sound', 'music', 'jump', 'run', 'fire', 'bonus',
                 'yoshi', 'power', 'star', 'shell', 'switch', 'button', 'special', 'secret',
                 'enemy', 'boss', 'castle', 'exit', 'save', 'load', 'reset', 'friend',
                 'rescue', 'princess', 'bowser', 'luigi', 'peach', 'trapped', 'help',
                 'blocks', 'complete', 'explore', 'different', 'places', 'defeat', 'points',
                 'stomp', 'pressing', 'jumping', 'fence', 'pool', 'balance', 'further',
                 'between', 'left', 'right', 'down', 'pick', 'towards', 'spin', 'break']

    if any(word in text.lower() for word in game_words):
        return False, "Válido: palavra de jogo"

    # EXCEÇÃO 2: Textos longos com espaços
    if ' ' in text and len(text.split()) >= 2:
        return False, "Válido: frase com espaços"

    return False, "Válido"


def test_filters_on_file(input_file: str):
    """Testa os filtros no arquivo atual"""
    print("=" * 70)
    print("🧪 TESTE DOS NOVOS FILTROS")
    print("=" * 70)
    print(f"📂 Arquivo: {Path(input_file).name}\n")

    # Lê o arquivo
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    print(f"📊 Total de linhas no arquivo: {len(lines)}\n")

    # Aplica filtros
    valid_texts = []
    garbage_texts = []
    reasons = {}

    for text in lines:
        is_garbage, reason = apply_new_filters(text)

        if is_garbage:
            garbage_texts.append(text)
            if reason not in reasons:
                reasons[reason] = []
            reasons[reason].append(text)
        else:
            valid_texts.append(text)

    # Relatório
    print("=" * 70)
    print("📈 RESULTADOS:")
    print("=" * 70)
    print(f"✅ Textos válidos mantidos: {len(valid_texts):,}")
    print(f"❌ Lixo removido: {len(garbage_texts):,}")
    print(f"📊 Taxa de limpeza: {len(garbage_texts)/len(lines)*100:.1f}%\n")

    print("=" * 70)
    print("📋 DETALHAMENTO DAS REMOÇÕES:")
    print("=" * 70)
    for reason, texts in sorted(reasons.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"\n• {reason}: {len(texts):,} itens")
        # Mostra alguns exemplos
        for example in texts[:3]:
            print(f"  └─ '{example}'")
        if len(texts) > 3:
            print(f"  └─ ... e mais {len(texts)-3} itens")

    print("\n" + "=" * 70)
    print("✅ TEXTOS VÁLIDOS PRESERVADOS:")
    print("=" * 70)
    for i, text in enumerate(valid_texts, 1):
        print(f"{i:3d}. {text}")

    # Salva arquivo limpo
    output_file = str(Path(input_file).with_stem(Path(input_file).stem + "_ULTRA_CLEAN"))
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(valid_texts))

    print("\n" + "=" * 70)
    print(f"💾 Arquivo limpo salvo: {Path(output_file).name}")
    print("=" * 70)


if __name__ == "__main__":
    # Testa no arquivo atual
    test_file = r"C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework\ROMs\Super Nintedo\Super Mario World_optimized.txt"

    if Path(test_file).exists():
        test_filters_on_file(test_file)
    else:
        print(f"❌ Arquivo não encontrado: {test_file}")
        print("Por favor, ajuste o caminho no script.")
