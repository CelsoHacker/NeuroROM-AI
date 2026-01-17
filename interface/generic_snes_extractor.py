#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generic ROM Text Extractor - SNES Platform
===========================================
Universal text extraction tool for SNES ROM files.
NO copyrighted game names or references.

Legal Notice & Best Practices:
- This tool is for PERSONAL USE ONLY
- Users must own original copies of games
- For backup and translation of legally owned software
- Not for piracy or copyright infringement

⚠️ IMPORTANT - Translation Quality:
- BEST RESULTS: Original, unmodified ROM dumps (USA/Japan versions recommended)
- WORKS BUT RISKY: Hacked/cracked ROMs may cause errors or game crashes after translation
- The tool works with any ROM, but stability is guaranteed only with originals

Author: ROM Translation Framework
License: MIT
"""

import sys
import os
from pathlib import Path


def has_text_density(text: str, min_consecutive_alnum: int = 3) -> bool:
    """
    FILTRO DE DENSIDADE: Verifica se há 3+ caracteres alfanuméricos consecutivos.

    Evita extrair lixo gráfico, ponteiros, ou caracteres soltos.

    Args:
        text: String a verificar
        min_consecutive_alnum: Mínimo de chars alfanuméricos consecutivos

    Returns:
        True se tem densidade suficiente
    """
    consecutive_count = 0
    max_consecutive = 0

    for char in text:
        if char.isalnum():
            consecutive_count += 1
            max_consecutive = max(max_consecutive, consecutive_count)
        else:
            consecutive_count = 0

    return max_consecutive >= min_consecutive_alnum


def has_graphic_garbage(text: str) -> bool:
    """
    FILTRO DE LIXO GRÁFICO: Detecta caracteres raros de box-drawing e tiles.

    Chars suspeitos: |, -, +, =, _, <, >, [, ], {, }, etc.
    Se >50% são símbolos gráficos, é provável que seja lixo.

    Args:
        text: String a verificar

    Returns:
        True se parece ser lixo gráfico
    """
    graphic_chars = set('|-+=_<>[]{}\\/@#$%^&*~`')
    graphic_count = sum(1 for c in text if c in graphic_chars)

    # Se >50% são caracteres gráficos, é provável lixo
    if len(text) > 0 and graphic_count / len(text) > 0.5:
        return True

    return False


def is_pointer_table_pattern(text: str) -> bool:
    """
    FILTRO DE PONTEIROS: Detecta padrões típicos de tabelas de ponteiros.

    Pointer tables tendem a ter padrões repetitivos de valores hexadecimais.
    Exemplo: "@@@@", "    ", "0000", etc.

    Args:
        text: String a verificar

    Returns:
        True se parece ser ponteiro/lixo
    """
    # Muito repetitivo (>70% é o mesmo char)
    if len(text) >= 3:
        most_common = max(set(text), key=text.count)
        repetition_ratio = text.count(most_common) / len(text)
        if repetition_ratio > 0.7:
            return True

    # Apenas espaços
    if text.strip() == '':
        return True

    return False


def extract_snes_ascii_texts(rom_path: str, output_path: str = None):
    """
    Extract ASCII text strings from SNES ROM files.

    Generic extraction method that works with most SNES games
    that use standard ASCII encoding (0x20-0x7E).

    MELHORADO COM FILTROS AGRESSIVOS:
    - Text Density: Requer 3+ chars alfanuméricos consecutivos
    - Graphic Filter: Remove lixo de box-drawing
    - Pointer Filter: Remove padrões repetitivos de ponteiros

    Args:
        rom_path: Path to input ROM file (.smc, .sfc)
        output_path: Path to output text file (default: auto-generated)

    Returns:
        bool: True if successful, False otherwise
    """
    print(f"[INFO] Loading ROM file...")

    # Validate input
    if not os.path.exists(rom_path):
        print(f"[ERROR] File not found: {rom_path}")
        return False

    # Load ROM data
    try:
        with open(rom_path, 'rb') as f:
            rom_data = f.read()
        print(f"[OK] ROM loaded: {len(rom_data):,} bytes")
    except Exception as e:
        print(f"[ERROR] Failed to load ROM: {e}")
        return False

    # Extract ASCII text strings
    print(f"[INFO] Scanning for ASCII text strings (with aggressive filtering)...")
    texts = []
    current_text = bytearray()
    text_start_offset = None

    # Estatísticas
    total_extracted = 0
    filtered_density = 0
    filtered_graphic = 0
    filtered_pointer = 0

    for offset in range(len(rom_data)):
        byte = rom_data[offset]

        # ASCII printable range (space to tilde: 0x20-0x7E)
        if 0x20 <= byte <= 0x7E:
            if text_start_offset is None:
                text_start_offset = offset
            current_text.append(byte)
        else:
            # End of string detected
            if len(current_text) >= 3:  # Minimum 3 chars to avoid noise
                try:
                    decoded_text = current_text.decode('ascii')
                    total_extracted += 1

                    # FILTRO 1: Text Density (3+ chars alfanuméricos consecutivos)
                    if not has_text_density(decoded_text, min_consecutive_alnum=3):
                        filtered_density += 1
                    # FILTRO 2: Graphic Garbage (box-drawing, tiles)
                    elif has_graphic_garbage(decoded_text):
                        filtered_graphic += 1
                    # FILTRO 3: Pointer Table Pattern (repetitivo)
                    elif is_pointer_table_pattern(decoded_text):
                        filtered_pointer += 1
                    else:
                        # PASSOU EM TODOS OS FILTROS: Texto útil!
                        texts.append({
                            'offset': hex(text_start_offset),
                            'text': decoded_text
                        })
                except UnicodeDecodeError:
                    pass  # Skip invalid sequences

            # Reset for next string
            current_text = bytearray()
            text_start_offset = None
    
    # Remove exact duplicates while preserving order
    unique_texts = []
    seen = set()
    for item in texts:
        text = item['text']
        if text not in seen:
            seen.add(text)
            unique_texts.append(item)

    # Relatório de qualidade
    total_garbage = filtered_density + filtered_graphic + filtered_pointer
    print(f"\n{'='*60}")
    print(f"🔍 RELATÓRIO DE EXTRAÇÃO - QUALIDADE")
    print(f"{'='*60}")
    print(f"📊 Strings brutas extraídas:     {total_extracted:,}")
    print(f"")
    print(f"🗑️  LIXO DETECTADO E DESCARTADO:")
    print(f"  • Sem densidade textual:       {filtered_density:,}")
    print(f"  • Lixo gráfico (box-drawing):  {filtered_graphic:,}")
    print(f"  • Padrões de ponteiros:        {filtered_pointer:,}")
    print(f"  • TOTAL lixo descartado:       {total_garbage:,}")
    print(f"")
    print(f"✅ TEXTO ÚTIL PRESERVADO:")
    print(f"  • Strings válidas (com duplicatas): {len(texts):,}")
    print(f"  • Strings únicas finais:            {len(unique_texts):,}")
    print(f"")
    print(f"📈 Taxa de limpeza: {(total_garbage / total_extracted * 100) if total_extracted > 0 else 0:.1f}% de lixo removido")
    print(f"{'='*60}\n")

    # Generate output filename if not provided
    if output_path is None:
        rom_file = Path(rom_path)
        output_path = rom_file.parent / f"{rom_file.stem}_extracted_texts.txt"

    # Save extracted texts
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# ROM Text Extraction Results\n")
            f.write("# ===========================\n")
            f.write(f"# Source ROM: {Path(rom_path).name}\n")
            f.write(f"# Total strings found: {len(unique_texts)}\n")
            f.write(f"# Extraction method: ASCII scan (0x20-0x7E) + Aggressive Filtering\n")
            f.write(f"#\n")
            f.write(f"# Quality Report:\n")
            f.write(f"#   - Lixo Binário Descartado: {total_garbage:,} linhas\n")
            f.write(f"#   - Texto Útil Preservado: {len(unique_texts):,} linhas\n")
            f.write(f"#   - Taxa de limpeza: {(total_garbage / total_extracted * 100) if total_extracted > 0 else 0:.1f}%\n")
            f.write(f"#\n")
            f.write("# Format: [offset] text_content\n")
            f.write("# ===========================\n\n")

            for i, item in enumerate(unique_texts, 1):
                f.write(f"[{item['offset']}] {item['text']}\n")

        print(f"[OK] Texts saved to: {output_path}")
        print(f"\n[INFO] Next steps:")
        print(f"  1. Review extracted texts")
        print(f"  2. Remove unwanted entries (optional)")
        print(f"  3. Translate using your preferred method")

        return True

    except Exception as e:
        print(f"[ERROR] Failed to save output: {e}")
        return False


def main():
    """Command-line interface."""
    print("=" * 60)
    print("  Generic SNES ROM Text Extractor")
    print("  For personal backup and translation use only")
    print("=" * 60)
    print()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  python {Path(__file__).name} <rom_file.smc> [output.txt]")
        print()
        print("Examples:")
        print(f'  python {Path(__file__).name} game_backup.smc')
        print(f'  python {Path(__file__).name} game_backup.smc custom_output.txt')
        print()
        sys.exit(1)
    
    rom_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = extract_snes_ascii_texts(rom_path, output_path)
    
    if success:
        print("\n[SUCCESS] Extraction completed!")
    else:
        print("\n[FAILED] Extraction failed. Check errors above.")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
