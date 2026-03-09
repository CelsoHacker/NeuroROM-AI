#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cria Whitelist de Textos Válidos - Validação POSITIVA
Ao invés de bloquear lixo, ACEITA apenas textos que parecem reais
"""

import re
from pathlib import Path

def is_likely_game_text(text: str) -> tuple[bool, str]:
    """
    Validação POSITIVA: texto parece ser de um jogo real?

    Returns:
        (is_valid, reason)
    """
    # REGRA 1: Deve ter 4+ caracteres
    if len(text) < 4:
        return False, "Muito curto"

    # REGRA 2: Deve ter APENAS letras maiúsculas (padrão SNES com char table)
    # Super Mario World usa TUDO em maiúsculas
    if not re.match(r'^[A-Z\s]+$', text):
        # Exceção: se tiver espaços e parecer frase
        if ' ' in text and len(text.split()) >= 2:
            pass  # Permitir frases
        else:
            return False, "Não é padrão SNES maiúsculas"

    # REGRA 3: Deve ter pelo menos 2 vogais (texto real tem vogais)
    vowel_count = sum(1 for c in text if c in 'AEIOU')
    if vowel_count < 2:
        return False, "Poucas vogais (< 2)"

    # REGRA 4: Não pode ter padrões estranhos
    # Bloqueia: IJIJIJ, XYXYXY, etc.
    if re.search(r'(.{2,3})\1{2,}', text):
        return False, "Padrão repetitivo"

    # REGRA 5: Não pode ter números
    if re.search(r'\d', text):
        return False, "Contém números"

    # REGRA 6: Não pode ter mais de 1 caractere especial
    special_count = sum(1 for c in text if c in '!@#$%^&*()_+-=[]{}|;:,.<>?/~`\\"\'')
    if special_count > 1:
        return False, "Muitos caracteres especiais"

    # REGRA 7: Deve ter consonantes E vogais em proporção razoável
    consonants = sum(1 for c in text if c.isalpha() and c not in 'AEIOU')
    if consonants > 0 and vowel_count > 0:
        ratio = vowel_count / consonants
        if ratio < 0.2 or ratio > 5.0:  # Muito fora do padrão
            return False, "Proporção vogais/consoantes anormal"

    # REGRA 8: Não pode ter cluster de consoantes muito longo (>4)
    if re.search(r'[^AEIOU\s]{5,}', text):
        return False, "Cluster de consoantes muito longo"

    # REGRA 9: Para strings curtas (<8), deve ser tudo maiúsculas
    if len(text) < 8:
        if not text.replace(' ', '').isupper():
            return False, "String curta deve ser maiúsculas"

    # REGRA 10: Verificação final - parece ser palavra inglesa comum?
    # Palavras comuns de jogos SNES
    common_patterns = [
        r'\bMARIO\b', r'\bWORLD\b', r'\bSUPER\b', r'\bSTAR\b',
        r'\bPOWER\b', r'\bPRESS\b', r'\bSTART\b', r'\bGAME\b',
        r'\bBONUS\b', r'\bCOIN\b', r'\bLIVES\b', r'\bSCORE\b',
        r'\bTIME\b', r'\bOVER\b', r'\bPLAYER\b', r'\bFRIEND\b',
        r'\bBLOCK\b', r'\bJUMP\b', r'\bSPIN\b', r'\bHELP\b',
        r'ED$', r'ING$', r'S$',  # Sufixos comuns
    ]

    # Se bater em algum padrão comum, é MUITO provável ser válido
    for pattern in common_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True, "Palavra comum de jogo"

    # REGRA 11: Se passou todas as verificações e tem 6+ caracteres, aceitar
    if len(text) >= 6:
        # Última verificação: não pode ter padrões muito estranhos
        if not re.search(r'[A-Z]{3}[^AEIOU\s]{3}', text):  # Não pode ter 3+ letras + 3+ não-vogais
            return True, "Passou validação (6+ chars)"

    return False, "Não passou validação final"


def create_whitelist(input_file: str):
    """Cria whitelist usando validação positiva"""
    print("=" * 70)
    print("✅ VALIDAÇÃO POSITIVA - Aceita apenas textos REAIS")
    print("=" * 70)

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    print(f"📊 Total de linhas: {len(lines)}\n")

    valid_texts = []
    rejected = {}

    for text in lines:
        is_valid, reason = is_likely_game_text(text)

        if is_valid:
            valid_texts.append(text)
        else:
            if reason not in rejected:
                rejected[reason] = []
            rejected[reason].append(text)

    print("=" * 70)
    print("📈 RESULTADOS:")
    print("=" * 70)
    print(f"✅ Textos VÁLIDOS: {len(valid_texts):,}")
    print(f"❌ Textos REJEITADOS: {len(lines) - len(valid_texts):,}")
    print(f"📊 Taxa de precisão: {len(valid_texts)/len(lines)*100:.1f}%\n")

    print("=" * 70)
    print("📋 MOTIVOS DE REJEIÇÃO:")
    print("=" * 70)
    for reason, texts in sorted(rejected.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"\n• {reason}: {len(texts):,} itens")
        for ex in texts[:3]:
            print(f"  └─ '{ex}'")
        if len(texts) > 3:
            print(f"  └─ ... e mais {len(texts)-3}")

    print("\n" + "=" * 70)
    print("✅ TEXTOS VÁLIDOS ACEITOS:")
    print("=" * 70)
    for i, text in enumerate(valid_texts, 1):
        print(f"{i:3d}. {text}")

    # Salva whitelist
    output_file = str(Path(input_file).with_stem(Path(input_file).stem + "_WHITELIST"))
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(valid_texts))

    print("\n" + "=" * 70)
    print(f"💾 Whitelist salva: {Path(output_file).name}")
    print("=" * 70)


if __name__ == "__main__":
    test_file = r"C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework\ROMs\Super Nintedo\Super Mario World_optimized.txt"

    if Path(test_file).exists():
        create_whitelist(test_file)
    else:
        print(f"❌ Arquivo não encontrado: {test_file}")
