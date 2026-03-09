#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ENGENHARIA REVERSA DO CHARSET DO SUPER MARIO WORLD
===================================================

Usa os textos válidos já encontrados para descobrir o charset real.
"""

from pathlib import Path
from typing import Dict, List, Tuple


def find_pattern_in_rom(rom_data: bytes, pattern: str, known_charset: Dict[int, str]) -> List[Tuple[int, Dict[int, str]]]:
    """
    Procura um padrão de texto na ROM e tenta descobrir o charset correto.

    Args:
        rom_data: Dados da ROM
        pattern: Texto conhecido (ex: "SUNKEN-GHOST-SHIP")
        known_charset: Charset inicial para teste

    Returns:
        Lista de (offset, charset_descoberto)
    """
    results = []

    # Para cada possível offset na ROM
    for offset in range(len(rom_data) - len(pattern)):
        # Extrai bytes na posição
        bytes_at_offset = rom_data[offset:offset + len(pattern)]

        # Tenta criar charset que mapeia esses bytes para o padrão
        discovered_charset = {}
        valid = True

        for i, char in enumerate(pattern):
            byte_val = bytes_at_offset[i]

            # Se já temos mapeamento para este byte
            if byte_val in discovered_charset:
                # Verifica se é consistente
                if discovered_charset[byte_val] != char:
                    valid = False
                    break
            else:
                # Adiciona novo mapeamento
                discovered_charset[byte_val] = char

        if valid and len(discovered_charset) > 5:  # Pelo menos 5 chars únicos
            results.append((offset, discovered_charset))

    return results


def merge_charsets(charsets: List[Dict[int, str]]) -> Dict[int, str]:
    """Mescla múltiplos charsets encontrados, verificando consistência."""
    merged = {}
    conflicts = []

    for charset in charsets:
        for byte_val, char in charset.items():
            if byte_val in merged:
                if merged[byte_val] != char:
                    conflicts.append(f"0x{byte_val:02X}: '{merged[byte_val]}' vs '{char}'")
            else:
                merged[byte_val] = char

    return merged, conflicts


def main():
    """Função principal."""

    # Carrega ROM
    rom_path = Path(r"C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework\ROMs\Super Nintedo\Super Mario World.smc")

    print("=" * 80)
    print("🔧 ENGENHARIA REVERSA DO CHARSET - SUPER MARIO WORLD")
    print("=" * 80)
    print()

    print(f"📂 Carregando ROM: {rom_path.name}")
    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    print(f"✅ {len(rom_data):,} bytes carregados")
    print()

    # Textos conhecidos que foram extraídos com sucesso
    known_texts = [
        "SUNKEN-GHOST-SHIP",
        "OF-BOWSER",
        "FORTRESS",
        "SWITCH",
        "TOP-SECRET"
    ]

    print("🔍 Procurando padrões conhecidos na ROM...")
    print()

    all_charsets = []

    for text in known_texts:
        print(f"Buscando: '{text}'")

        # Procura o padrão na ROM
        matches = find_pattern_in_rom(rom_data, text, {})

        if matches:
            print(f"  ✅ {len(matches)} correspondência(s) encontrada(s)")

            for offset, charset in matches[:3]:  # Mostra primeiros 3 matches
                print(f"     Offset: 0x{offset:06X}")
                print(f"     Charset descoberto: {len(charset)} caracteres")

                # Mostra alguns bytes
                sample = list(charset.items())[:10]
                for byte_val, char in sample:
                    print(f"       0x{byte_val:02X} = '{char}'")

                all_charsets.append(charset)
                print()
        else:
            print(f"  ❌ Não encontrado")
            print()

    # Mescla todos os charsets descobertos
    if all_charsets:
        print("=" * 80)
        print("🧩 MESCLANDO CHARSETS DESCOBERTOS...")
        print("=" * 80)
        print()

        merged_charset, conflicts = merge_charsets(all_charsets)

        print(f"✅ Charset final: {len(merged_charset)} caracteres mapeados")
        print()

        if conflicts:
            print(f"⚠️  {len(conflicts)} conflito(s) detectado(s):")
            for conflict in conflicts[:10]:
                print(f"   {conflict}")
            print()

        # Mostra charset completo ordenado
        print("=" * 80)
        print("📋 CHARSET COMPLETO:")
        print("=" * 80)
        print()

        sorted_charset = sorted(merged_charset.items())

        for byte_val, char in sorted_charset:
            print(f"0x{byte_val:02X} = '{char}'")

        # Salva charset em formato .tbl
        output_file = rom_path.parent / "smw_discovered_charset.tbl"

        with open(output_file, 'w', encoding='utf-8') as f:
            for byte_val, char in sorted_charset:
                f.write(f"{byte_val:02X}={char}\n")

        print()
        print(f"💾 Charset salvo em: {output_file.name}")
        print()

        # Gera código Python para usar este charset
        print("=" * 80)
        print("🐍 CÓDIGO PYTHON PARA USAR ESTE CHARSET:")
        print("=" * 80)
        print()
        print("CHARSET = {")
        for byte_val, char in sorted_charset:
            print(f"    0x{byte_val:02X}: '{char}',")
        print("}")
        print()

    else:
        print("❌ Nenhum charset pôde ser descoberto.")
        print("   Verifique se os textos conhecidos estão corretos.")

    print("=" * 80)


if __name__ == '__main__':
    main()
