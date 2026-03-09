#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CONSOLIDAÇÃO DE TEXTOS DO SUPER MARIO WORLD
============================================

Consolida fragmentos sobrepostos em textos completos únicos.
"""

from pathlib import Path
from typing import List, Set


def is_substring_of_any(text: str, text_list: List[str]) -> bool:
    """Verifica se texto é substring de algum outro na lista."""
    for other in text_list:
        if text != other and text in other:
            return True
    return False


def consolidate_texts(texts: List[str]) -> List[str]:
    """Consolida textos removendo fragmentos que são substrings de outros."""
    # Remove duplicatas
    unique_texts = list(set(texts))

    # Ordena por tamanho (maiores primeiro)
    unique_texts.sort(key=len, reverse=True)

    # Remove fragmentos
    consolidated = []

    for text in unique_texts:
        # Se texto NÃO é substring de nenhum outro já adicionado
        if not is_substring_of_any(text, consolidated):
            consolidated.append(text)

    return consolidated


def clean_text(text: str) -> str:
    """Limpa texto removendo ruído."""
    # Remove espaços extras no início/fim
    text = text.strip()

    # Substitui múltiplos espaços/hifens por um único
    import re
    text = re.sub(r'-{2,}', '-', text)  # -- → -
    text = re.sub(r'\s{2,}', ' ', text)  # múltiplos espaços → 1

    return text


def categorize_texts(texts: List[str]) -> dict:
    """Categoriza textos por tipo."""
    categories = {
        'level_names': [],
        'world_names': [],
        'messages': [],
        'system': [],
        'other': []
    }

    # Palavras-chave de nomes de níveis
    level_keywords = ['GHOST', 'SHIP', 'HOUSE', 'FORTRESS', 'CASTLE',
                      'BRIDGE', 'LAKE', 'PALACE', 'SECRET', 'BOWSER', 'ZONE']

    # Palavras-chave de mundos
    world_keywords = ['CHOCOLATE', 'VANILLA', 'DONUT', 'PLAINS', 'FOREST',
                     'ISLAND', 'VALLEY', 'DOME', 'WORLD', 'STAR']

    # System keywords
    system_keywords = ['START', 'BUTTON', 'SELECT', 'PRESS', 'EXTRA']

    for text in texts:
        text_upper = text.upper()

        # Verifica categoria
        if any(kw in text_upper for kw in level_keywords):
            categories['level_names'].append(text)
        elif any(kw in text_upper for kw in world_keywords):
            categories['world_names'].append(text)
        elif any(kw in text_upper for kw in system_keywords):
            categories['system'].append(text)
        elif len(text) > 15 and any(c.islower() for c in text):  # Provável mensagem
            categories['messages'].append(text)
        else:
            categories['other'].append(text)

    return categories


def main():
    """Função principal."""

    # Arquivo de entrada
    input_file = Path(r"C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework\ROMs\Super Nintedo\Super Mario World_DUAL_CHARSET_FILTERED.txt")

    print("=" * 80)
    print("🧩 CONSOLIDAÇÃO DE TEXTOS - SUPER MARIO WORLD")
    print("=" * 80)
    print()

    # Carrega textos
    print(f"📂 Carregando: {input_file.name}")
    with open(input_file, 'r', encoding='utf-8') as f:
        texts = [line.strip() for line in f if line.strip()]

    print(f"✅ {len(texts)} textos carregados")
    print()

    # Limpa textos
    print("🧹 Limpando textos...")
    cleaned = [clean_text(t) for t in texts]
    cleaned = [t for t in cleaned if len(t) >= 4]  # Mínimo 4 caracteres

    # Consolida
    print("🔗 Consolidando fragmentos sobrepostos...")
    consolidated = consolidate_texts(cleaned)

    print(f"✅ {len(texts)} → {len(consolidated)} textos únicos")
    print()

    # Categoriza
    print("📋 Categorizando...")
    categories = categorize_texts(consolidated)

    # Estatísticas
    print("=" * 80)
    print("📊 CATEGORIAS:")
    print("=" * 80)
    print(f"  🏰 Nomes de Níveis: {len(categories['level_names'])}")
    print(f"  🌍 Nomes de Mundos: {len(categories['world_names'])}")
    print(f"  💬 Mensagens: {len(categories['messages'])}")
    print(f"  ⚙️  Sistema: {len(categories['system'])}")
    print(f"  📦 Outros: {len(categories['other'])}")
    print(f"  📊 TOTAL: {len(consolidated)}")
    print()

    # Mostra textos por categoria
    print("=" * 80)
    print("✅ TEXTOS CONSOLIDADOS DO SUPER MARIO WORLD:")
    print("=" * 80)
    print()

    if categories['level_names']:
        print("🏰 NOMES DE NÍVEIS:")
        print("-" * 80)
        for text in sorted(categories['level_names'], key=str.upper):
            print(f"  • {text}")
        print()

    if categories['world_names']:
        print("🌍 NOMES DE MUNDOS:")
        print("-" * 80)
        for text in sorted(categories['world_names'], key=str.upper):
            print(f"  • {text}")
        print()

    if categories['messages']:
        print("💬 MENSAGENS DO JOGO:")
        print("-" * 80)
        for text in sorted(categories['messages'], key=lambda x: (-len(x), x.upper()))[:30]:
            print(f"  • {text}")
        if len(categories['messages']) > 30:
            print(f"  ... e mais {len(categories['messages']) - 30} mensagens")
        print()

    if categories['system']:
        print("⚙️  TEXTOS DE SISTEMA:")
        print("-" * 80)
        for text in sorted(categories['system'], key=str.upper):
            print(f"  • {text}")
        print()

    # Salva resultado consolidado
    output_file = input_file.parent / "Super Mario World_CONSOLIDATED.txt"

    with open(output_file, 'w', encoding='utf-8') as f:
        for text in sorted(consolidated, key=lambda x: (-len(x), x.upper())):
            f.write(f"{text}\n")

    print("=" * 80)
    print(f"💾 {len(consolidated)} textos consolidados salvos em:")
    print(f"   {output_file.name}")
    print("=" * 80)
    print()

    # Avaliação final
    if len(consolidated) >= 100:
        print("🎉 EXCELENTE! Mais de 100 textos únicos extraídos!")
    elif len(consolidated) >= 50:
        print("✅ BOM! Mais de 50 textos únicos extraídos!")
    else:
        print(f"⚠️  {len(consolidated)} textos únicos (meta: 100+)")

    print()


if __name__ == '__main__':
    main()
