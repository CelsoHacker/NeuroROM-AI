#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Otimizador de Arquivo para Tradução
====================================

Remove duplicatas e otimiza arquivo antes de traduzir
Reduz drasticamente o tempo de tradução!
"""

import sys
from pathlib import Path
from collections import OrderedDict


def otimizar_arquivo(input_file: str):
    """
    Remove duplicatas mantendo ordem original

    Args:
        input_file: Arquivo _optimized.txt para otimizar
    """

    print("\n" + "="*70)
    print("🔧 OTIMIZADOR DE ARQUIVO PARA TRADUÇÃO")
    print("="*70 + "\n")

    # Lê arquivo
    print(f"📂 Lendo: {Path(input_file).name}")

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    total_original = len(lines)
    print(f"📊 Total de linhas: {total_original:,}")

    # Remove duplicatas mantendo ordem
    print(f"\n🔍 Removendo duplicatas...")

    seen = OrderedDict()
    unique_lines = []
    duplicates = 0

    for i, line in enumerate(lines, 1):
        # Progresso
        if i % 10000 == 0:
            print(f"   Processando: {i:,}/{total_original:,} ({i/total_original*100:.1f}%)")

        # Mantém linhas vazias
        if not line.strip():
            unique_lines.append(line)
            continue

        # Remove duplicata
        if line in seen:
            duplicates += 1
            continue

        seen[line] = True
        unique_lines.append(line)

    total_unique = len(unique_lines)
    reduction = (1 - total_unique / total_original) * 100

    print(f"\n📊 RESULTADO:")
    print(f"   Linhas originais: {total_original:,}")
    print(f"   Linhas únicas: {total_unique:,}")
    print(f"   Duplicatas removidas: {duplicates:,}")
    print(f"   Redução: {reduction:.1f}%")

    # Calcula economia de tempo
    tempo_original_horas = (total_original / 10 / 3) * 10 / 3600
    tempo_otimizado_horas = (total_unique / 10 / 3) * 10 / 3600
    economia_horas = tempo_original_horas - tempo_otimizado_horas

    print(f"\n⏱️ ECONOMIA DE TEMPO:")
    print(f"   Antes: ~{tempo_original_horas:.1f} horas")
    print(f"   Depois: ~{tempo_otimizado_horas:.1f} horas")
    print(f"   Economia: ~{economia_horas:.1f} horas ({economia_horas*60:.0f} minutos)")

    # Salva arquivo otimizado
    output_file = input_file.replace('_optimized.txt', '_optimized_unique.txt')
    if output_file == input_file:
        output_file = str(Path(input_file).with_suffix('')) + '_unique.txt'

    print(f"\n💾 Salvando: {Path(output_file).name}")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(unique_lines)

    print(f"✅ Arquivo otimizado salvo!")

    # Mostra estatísticas de duplicatas
    print(f"\n📈 TOP 10 TEXTOS MAIS REPETIDOS:")
    print("-" * 70)

    # Conta frequência
    freq = {}
    for line in lines:
        text = line.strip()
        if text:
            freq[text] = freq.get(text, 0) + 1

    # Ordena por frequência
    top_10 = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10]

    for i, (text, count) in enumerate(top_10, 1):
        preview = text[:50] + "..." if len(text) > 50 else text
        print(f"   {i:2}. [{count:5}x] {preview}")

    print("-" * 70)

    print(f"\n🎯 PRÓXIMO PASSO:")
    print(f"   Use o arquivo: {Path(output_file).name}")
    print(f"   Na interface, clique em 'Selecionar Arquivo'")
    print(f"   E escolha este arquivo otimizado!")
    print("\n" + "="*70 + "\n")

    return output_file


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\n❌ Uso: python otimizar_arquivo_traducao.py <arquivo_optimized.txt>")
        print("\nOu simplesmente arraste o arquivo sobre este script!\n")

        # Tenta encontrar arquivo automaticamente
        import glob
        arquivos = glob.glob("*_optimized.txt") + glob.glob("local_optimized.txt")

        if arquivos:
            print(f"📂 Arquivo encontrado automaticamente: {arquivos[0]}")
            resposta = input("Deseja otimizar este arquivo? (s/n): ").strip().lower()

            if resposta == 's':
                otimizar_arquivo(arquivos[0])

        sys.exit(1)

    arquivo = sys.argv[1]

    if not Path(arquivo).exists():
        print(f"\n❌ Arquivo não encontrado: {arquivo}\n")
        sys.exit(1)

    otimizar_arquivo(arquivo)
