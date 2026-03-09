#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste de validação - ROM Hacking Manual Implementation
Valida CONSOLE_PROFILES e funções de endianness
"""

import sys
sys.path.insert(0, 'interface/gui_tabs')

from extraction_tab import (
    CONSOLE_PROFILES,
    rom_offset_to_pointer_bytes,
    pointer_bytes_to_rom_offset
)

def test_console_profiles():
    """Testa dicionário de profiles"""
    print("="*70)
    print("TESTE 1: CONSOLE_PROFILES")
    print("="*70)

    for console, profile in CONSOLE_PROFILES.items():
        print(f"✓ {console:12} | Header: {profile['header_offset']:5} | "
              f"Bytes: {profile['pointer_bytes']} | Endian: {profile['endian']}")
    print()

def test_snes_conversion():
    """Testa conversão SNES LoROM"""
    print("="*70)
    print("TESTE 2: SNES LoROM Conversion")
    print("="*70)

    test_cases = [
        0x012345,
        0x018000,
        0x020000,
        0x1F234
    ]

    for offset in test_cases:
        pointer_bytes = rom_offset_to_pointer_bytes(offset, 'SNES_LOROM')
        reverse_offset = pointer_bytes_to_rom_offset(pointer_bytes, 'SNES_LOROM')

        status = "✓" if reverse_offset == offset else "✗"
        print(f"{status} Offset: 0x{offset:06X} -> Bytes: [{' '.join(f'{b:02X}' for b in pointer_bytes)}] -> Reverse: 0x{reverse_offset:06X}")
    print()

def test_nes_conversion():
    """Testa conversão NES"""
    print("="*70)
    print("TESTE 3: NES Little-Endian Conversion")
    print("="*70)

    test_cases = [
        0x1234,
        0x8010,
        0xFFFF,
    ]

    for offset in test_cases:
        pointer_bytes = rom_offset_to_pointer_bytes(offset, 'NES', 'little')
        reverse_offset = pointer_bytes_to_rom_offset(pointer_bytes, 'NES')

        status = "✓" if reverse_offset == offset else "✗"
        print(f"{status} Offset: 0x{offset:04X} -> Bytes: [{' '.join(f'{b:02X}' for b in pointer_bytes)}] -> Reverse: 0x{reverse_offset:04X}")
    print()

def test_endianness_example():
    """Exemplo de inversão de endianness"""
    print("="*70)
    print("TESTE 4: Exemplo Prático de Endianness")
    print("="*70)

    print("SNES LoROM - Offset 0x012345:")
    print("  1. ROM Offset: 0x012345")
    print("  2. Bank: (0x012345 >> 15) & 0x7F = 0x02")
    print("  3. Addr: (0x012345 & 0x7FFF) | 0x8000 = 0xA345")
    print("  4. SNES Addr: (0x02 << 16) | 0xA345 = 0x02A345")
    print("  5. Little-Endian: [45 A3 02]")

    pointer_bytes = rom_offset_to_pointer_bytes(0x012345, 'SNES_LOROM')
    print(f"  6. Resultado: [{' '.join(f'{b:02X}' for b in pointer_bytes)}]")

    if pointer_bytes == bytes([0x45, 0xA3, 0x02]):
        print("  ✓ CORRETO!")
    else:
        print("  ✗ ERRO!")
    print()

if __name__ == "__main__":
    print("\n" + "="*70)
    print("ROM HACKING MANUAL - VALIDAÇÃO DE IMPLEMENTAÇÃO")
    print("ENGINE RETRO-A - 02/Janeiro/2026")
    print("="*70 + "\n")

    test_console_profiles()
    test_snes_conversion()
    test_nes_conversion()
    test_endianness_example()

    print("="*70)
    print("✅ TODOS OS TESTES CONCLUÍDOS")
    print("="*70)
