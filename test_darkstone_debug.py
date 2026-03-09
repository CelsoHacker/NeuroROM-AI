#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DEBUG: Testar Deep Fingerprinting com DarkStone.exe
"""

import sys
from pathlib import Path

# Adicionar interface ao path
interface_dir = Path(__file__).parent / 'interface'
sys.path.insert(0, str(interface_dir))

def test_darkstone_deep_scan(file_path: str):
    """Testa deep scan com logging detalhado."""
    print("=" * 80)
    print("DEBUG: DEEP FINGERPRINTING - DarkStone.exe")
    print("=" * 80)

    from forensic_engine_upgrade import scan_inner_patterns
    import os

    if not os.path.exists(file_path):
        print(f"❌ Arquivo não encontrado: {file_path}")
        return

    file_size = os.path.getsize(file_path)
    print(f"\n📂 Arquivo: {file_path}")
    print(f"📊 Tamanho: {file_size / (1024*1024):.1f} MB")

    # Executar scan
    print("\n🔬 Executando deep scan...")
    result = scan_inner_patterns(file_path)

    # Mostrar resultados detalhados
    print("\n" + "=" * 80)
    print("RESULTADOS DO RAIO-X")
    print("=" * 80)

    print(f"\n📊 Padrões encontrados: {len(result['patterns_found'])}")
    print(f"📈 Contagens por categoria:")
    for category, count in result['pattern_counts'].items():
        print(f"  • {category}: {count} ocorrência(s)")

    print(f"\n🏗️  Arquiteturas inferidas: {len(result['architecture_hints'])}")
    for arch in result['architecture_hints']:
        print(f"  • {arch}")

    print(f"\n📅 Ano do jogo: {result['game_year']}")
    print(f"🎯 Confiança: {result['confidence']}")

    print(f"\n🎮 Features detectadas: {len(result['feature_icons'])}")
    for feature in result['feature_icons']:
        print(f"  {feature}")

    # Análise de seções
    print("\n" + "=" * 80)
    print("ANÁLISE DETALHADA DE SEÇÕES")
    print("=" * 80)

    # Manualmente ler algumas seções para debug
    with open(file_path, 'rb') as f:
        # Seção 1: Header (0-64KB)
        f.seek(0)
        header = f.read(65536)

        print("\n🔍 SEÇÃO 1 - Header (0-64KB):")
        # Buscar alguns padrões conhecidos
        test_patterns = [
            (b'new game', 'New Game (lowercase)'),
            (b'NEW GAME', 'New Game (UPPERCASE)'),
            (b'New Game', 'New Game (Title Case)'),
            (b'level', 'Level'),
            (b'LEVEL', 'LEVEL'),
            (b'experience', 'Experience'),
            (b'str\x00', 'STR attribute'),
            (b'STR\x00', 'STR (uppercase)'),
            (b'1999', '1999 year'),
            (b'2005', '2005 year'),
        ]

        for pattern, name in test_patterns:
            if pattern in header or pattern.lower() in header.lower():
                pos = header.lower().find(pattern.lower())
                print(f"  ✓ Encontrado: {name} @ 0x{pos:X}")

        # Seção 2: 128KB
        f.seek(131072)
        section_128k = f.read(65536)

        print("\n🔍 SEÇÃO 2 - 128KB offset:")
        for pattern, name in test_patterns:
            if pattern in section_128k or pattern.lower() in section_128k.lower():
                pos = section_128k.lower().find(pattern.lower())
                print(f"  ✓ Encontrado: {name} @ 0x{(131072 + pos):X}")

        # Buscar strings visíveis
        print("\n🔍 Strings ASCII visíveis (primeiros 1KB do header):")
        strings = []
        current = b''
        for byte in header[:1024]:
            if 32 <= byte <= 126:  # ASCII printable
                current += bytes([byte])
            else:
                if len(current) >= 4:
                    try:
                        strings.append(current.decode('ascii'))
                    except:
                        pass
                current = b''

        print(f"  Total de strings: {len(strings)}")
        for s in strings[:20]:  # Primeiras 20
            print(f"  • {s}")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    # Pedir caminho do arquivo
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        print("Digite o caminho completo para DarkStone.exe:")
        file_path = input("> ").strip().strip('"')

    test_darkstone_deep_scan(file_path)
