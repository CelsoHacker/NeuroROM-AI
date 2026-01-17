#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generic PC Game Text Extractor - Windows Platform
==================================================
Universal text extraction tool for PC game executables (.exe, .dll).

FILTROS AGRESSIVOS PARA EVITAR LIXO BINÁRIO:
✓ Rejeita APIs do Windows (kernel32.dll, CreateFileA, etc.)
✓ Rejeita identificadores de código (aleatórios como qZYa, xIQw)
✓ Aceita apenas texto humano real (frases, diálogos, mensagens)

Legal Notice & Best Practices:
- This tool is for PERSONAL USE ONLY
- Users must own original copies of games
- For backup and translation of legally owned software
- Not for piracy or copyright infringement

⚠️ IMPORTANT - Translation Quality:
- BEST RESULTS: Original, unmodified game files (English version recommended)
- WORKS BUT RISKY: Cracked/pirated versions may cause errors or crashes after translation
- The tool translates ANY executable, but stability is guaranteed only with originals

Author: ROM Translation Framework
License: MIT
"""

import sys
import os
import re
from pathlib import Path


# ============================================================================
# BLACKLIST DE APIs E IDENTIFICADORES DO WINDOWS
# ============================================================================
WINDOWS_API_BLACKLIST = {
    # DLLs comuns
    'kernel32.dll', 'user32.dll', 'gdi32.dll', 'advapi32.dll',
    'shell32.dll', 'ole32.dll', 'winmm.dll', 'msvcrt.dll',
    'ntdll.dll', 'd3d9.dll', 'd3d8.dll', 'opengl32.dll',
    'ws2_32.dll', 'comctl32.dll', 'comdlg32.dll',

    # Funções comuns (100+ mais usadas)
    'GetProcAddress', 'LoadLibrary', 'VirtualAlloc', 'VirtualFree',
    'CreateFile', 'CreateFileA', 'CreateFileW', 'ReadFile', 'WriteFile',
    'CloseHandle', 'GetModuleHandle', 'GetLastError', 'ExitProcess',
    'MessageBox', 'MessageBoxA', 'MessageBoxW', 'RegisterClass',
    'CreateWindow', 'ShowWindow', 'UpdateWindow', 'GetMessage',
    'DispatchMessage', 'DefWindowProc', 'PostQuitMessage',
    'malloc', 'free', 'printf', 'sprintf', 'strlen', 'strcpy',
    'memcpy', 'memset', 'fopen', 'fclose', 'fread', 'fwrite',

    # Mensagens de erro técnicas
    'Runtime error', 'Access violation', 'Stack overflow',
    'Heap corruption', 'Pure virtual function call',
    'Assertion failed', 'Debug Error', 'Unhandled exception',
}


def is_windows_api_or_identifier(text: str) -> bool:
    """
    Detecta se é API do Windows ou identificador técnico.

    Returns:
        True se for lixo técnico (deve ser descartado)
    """
    # Blacklist exata
    if text in WINDOWS_API_BLACKLIST:
        return True

    # Padrões de APIs (.dll, Func, etc.)
    if re.match(r'^[a-z0-9_]+\.(dll|exe|sys)$', text, re.IGNORECASE):
        return True

    # Funções tipo: FuncName, GetSomething, CreateSomething
    if re.match(r'^[A-Z][a-z]+[A-Z][a-zA-Z0-9]*$', text):
        return True

    # Identificadores aleatórios (tipo qZYa, xIQw, uPMOkL)
    # Padrão: letras maiúsculas/minúsculas misturadas sem sentido
    if len(text) >= 3 and text.isalpha():
        upper_count = sum(1 for c in text if c.isupper())
        lower_count = sum(1 for c in text if c.islower())
        # Se tem maiúsculas e minúsculas muito misturadas (>40% cada)
        if upper_count > 0 and lower_count > 0:
            ratio = min(upper_count, lower_count) / len(text)
            if ratio > 0.3 and not ' ' in text:
                return True

    return False


def is_human_readable_text(text: str) -> bool:
    """
    Valida se é texto humano legível (diálogos, mensagens, interface).

    OTIMIZADO PARA JOGOS GRANDES (1GB+):
    - Aceita strings curtas (3+ chars)
    - Aceita palavras únicas
    - Menos restritivo para capturar mais texto

    Returns:
        True se for texto humano útil
    """
    # Tamanho mínimo/máximo (REDUZIDO para jogos grandes)
    if len(text) < 3 or len(text) > 1000:
        return False

    # Aceita palavras únicas se tiverem 3+ caracteres
    if ' ' not in text and len(text) < 3:
        return False

    # Deve ter vogais (texto humano sempre tem)
    vowel_count = sum(1 for c in text.lower() if c in 'aeiouáéíóúâêîôûãõ')
    if vowel_count < 1:  # Reduzido de 2 para 1
        return False

    # Não pode ser só números ou símbolos
    if text.replace(' ', '').isdigit():
        return False

    # Deve ter letras (pelo menos 50%)
    letter_count = sum(1 for c in text if c.isalpha())
    if letter_count / len(text) < 0.5:
        return False

    return True


def has_text_density(text: str, min_consecutive_alnum: int = 3) -> bool:
    """
    Verifica densidade de texto (evita lixo gráfico).
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


def extract_pc_game_texts(exe_path: str, output_path: str = None):
    """
    Extrai textos de jogos PC (.exe, .dll) com filtros AGRESSIVOS.

    FILTROS APLICADOS (em ordem):
    1. Text Density: Mínimo 3 chars alfanuméricos consecutivos
    2. Windows API Filter: Remove APIs e funções do sistema
    3. Human Readable Filter: Aceita apenas texto com vogais, espaços, estrutura de frase

    Args:
        exe_path: Caminho do arquivo .exe
        output_path: Caminho do arquivo de saída

    Returns:
        bool: True se sucesso
    """
    print(f"[INFO] Loading PC game executable...")

    # Validate input
    if not os.path.exists(exe_path):
        print(f"[ERROR] File not found: {exe_path}")
        return False

    # Load binary data
    try:
        with open(exe_path, 'rb') as f:
            binary_data = f.read()
        print(f"[OK] Executable loaded: {len(binary_data):,} bytes")
    except Exception as e:
        print(f"[ERROR] Failed to load file: {e}")
        return False

    # Extract ASCII text strings
    print(f"[INFO] Scanning for human-readable text strings...")
    texts = []
    current_text = bytearray()
    text_start_offset = None

    # Estatísticas
    total_extracted = 0
    filtered_density = 0
    filtered_api = 0
    filtered_not_human = 0

    for offset in range(len(binary_data)):
        byte = binary_data[offset]

        # ASCII printable range (space to tilde: 0x20-0x7E)
        if 0x20 <= byte <= 0x7E:
            if text_start_offset is None:
                text_start_offset = offset
            current_text.append(byte)
        else:
            # End of string detected
            if len(current_text) >= 5:  # Minimum 5 chars
                try:
                    decoded_text = current_text.decode('ascii')
                    total_extracted += 1

                    # FILTRO 1: Text Density
                    if not has_text_density(decoded_text, min_consecutive_alnum=3):
                        filtered_density += 1
                    # FILTRO 2: Windows API / Identifiers
                    elif is_windows_api_or_identifier(decoded_text):
                        filtered_api += 1
                    # FILTRO 3: Human Readable Text
                    elif not is_human_readable_text(decoded_text):
                        filtered_not_human += 1
                    else:
                        # PASSOU EM TODOS OS FILTROS: Texto humano útil!
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
    total_garbage = filtered_density + filtered_api + filtered_not_human
    print(f"\n{'='*60}")
    print(f"🔍 RELATÓRIO DE EXTRAÇÃO - PC GAME")
    print(f"{'='*60}")
    print(f"📊 Strings brutas extraídas:     {total_extracted:,}")
    print(f"")
    print(f"🗑️  LIXO DETECTADO E DESCARTADO:")
    print(f"  • Sem densidade textual:       {filtered_density:,}")
    print(f"  • APIs/Identificadores Windows: {filtered_api:,}")
    print(f"  • Não é texto humano legível:  {filtered_not_human:,}")
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
        exe_file = Path(exe_path)
        output_path = exe_file.parent / f"{exe_file.stem}_extracted_texts.txt"

    # Save extracted texts
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# PC Game Text Extraction Results\n")
            f.write("# ================================\n")
            f.write(f"# Source File: {Path(exe_path).name}\n")
            f.write(f"# Total strings found: {len(unique_texts)}\n")
            f.write(f"# Extraction method: ASCII scan + Aggressive Filtering (PC Game Mode)\n")
            f.write(f"#\n")
            f.write(f"# Quality Report:\n")
            f.write(f"#   - Lixo Binário Descartado: {total_garbage:,} linhas\n")
            f.write(f"#   - Texto Útil Preservado: {len(unique_texts):,} linhas\n")
            f.write(f"#   - Taxa de limpeza: {(total_garbage / total_extracted * 100) if total_extracted > 0 else 0:.1f}%\n")
            f.write(f"#\n")
            f.write("# Format: [offset] text_content\n")
            f.write("# ================================\n\n")

            for i, item in enumerate(unique_texts, 1):
                f.write(f"[{item['offset']}] {item['text']}\n")

        print(f"[OK] Texts saved to: {output_path}")
        print(f"\n[INFO] Next steps:")
        print(f"  1. Review extracted texts")
        print(f"  2. Run 'Optimize Data' to clean further")
        print(f"  3. Translate using AI")

        return True

    except Exception as e:
        print(f"[ERROR] Failed to save output: {e}")
        return False


def main():
    """Command-line interface."""
    print("=" * 60)
    print("  Generic PC Game Text Extractor (Windows)")
    print("  For personal backup and translation use only")
    print("=" * 60)
    print()

    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  python {Path(__file__).name} <game.exe> [output.txt]")
        print()
        print("Examples:")
        print(f'  python {Path(__file__).name} mygame.exe')
        print(f'  python {Path(__file__).name} darkstone.exe custom_output.txt')
        print()
        sys.exit(1)

    exe_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    success = extract_pc_game_texts(exe_path, output_path)

    if success:
        print("\n[SUCCESS] Extraction completed!")
    else:
        print("\n[FAILED] Extraction failed. Check errors above.")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
