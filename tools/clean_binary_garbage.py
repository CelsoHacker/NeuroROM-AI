#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clean Binary Garbage - Remove lixo binário de arquivos extraídos
=================================================================
Remove linhas com símbolos de ponteiros/lixo binário: | } { ] [ \
"""

import sys
import re
from pathlib import Path


def has_binary_garbage(text: str) -> bool:
    """Detecta se linha tem lixo binário (>30% símbolos ruins)"""
    garbage_chars = set('|}{][\\`')

    # Remove [0x...] do começo
    text_clean = re.sub(r'^\[0x[0-9a-fA-F]+\]\s*', '', text)

    if not text_clean:
        return False

    garbage_count = sum(1 for c in text_clean if c in garbage_chars)

    # Se >30% são símbolos de lixo, remove
    if garbage_count / len(text_clean) > 0.3:
        return True

    return False


def clean_file(input_file: str, output_file: str = None):
    """
    Limpa arquivo removendo lixo binário

    Args:
        input_file: Arquivo de entrada
        output_file: Arquivo de saída (opcional)
    """
    input_path = Path(input_file)

    if not input_path.exists():
        print(f"❌ Arquivo não encontrado: {input_file}")
        return False

    # Define output
    if output_file is None:
        output_path = input_path.parent / f"{input_path.stem}_CLEANED{input_path.suffix}"
    else:
        output_path = Path(output_file)

    print(f"📂 Processando: {input_path.name}")

    # Lê arquivo
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Filtra linhas
    cleaned_lines = []
    removed_count = 0

    for line in lines:
        # Mantém comentários
        if line.startswith('#'):
            cleaned_lines.append(line)
            continue

        # Remove lixo binário
        if has_binary_garbage(line):
            removed_count += 1
            print(f"🗑️  Removido: {line.strip()[:80]}...")
            continue

        cleaned_lines.append(line)

    # Salva arquivo limpo
    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(cleaned_lines)

    print(f"\n{'='*70}")
    print(f"✅ LIMPEZA CONCLUÍDA!")
    print(f"{'='*70}")
    print(f"📊 Linhas originais: {len(lines)}")
    print(f"🗑️  Lixo removido: {removed_count}")
    print(f"✅ Linhas limpas: {len(cleaned_lines)}")
    print(f"💾 Arquivo salvo: {output_path}")
    print(f"{'='*70}\n")

    return True


def main():
    """CLI Interface"""

    if len(sys.argv) < 2:
        print("="*70)
        print("  Clean Binary Garbage - Remove lixo binário")
        print("="*70)
        print()
        print("Uso:")
        print(f"  python {Path(__file__).name} <arquivo.txt> [saida.txt]")
        print()
        print("Exemplos:")
        print(f"  python {Path(__file__).name} extracted.txt")
        print(f"  python {Path(__file__).name} extracted.txt clean.txt")
        print()
        return 1

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    success = clean_file(input_file, output_file)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
