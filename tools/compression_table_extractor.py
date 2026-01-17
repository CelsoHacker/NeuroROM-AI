#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CompPointTable Extractor Tool
Ferramenta para extrair tabelas de compressão de ROMs SNES
"""

import sys
import os
from pathlib import Path

# Adiciona path do extraction
sys.path.insert(0, str(Path(__file__).parent.parent / "extraction"))

from compression_analyzer import CompressionAnalyzer, analyze_rom_compression

def main():
    """Interface CLI para extração de CompPointTable"""

    print("\n" + "="*80)
    print("🔧 COMPPOINTTABLE EXTRACTOR - Ferramenta de Extração")
    print("="*80 + "\n")

    if len(sys.argv) < 2:
        print("❌ Uso: python compression_table_extractor.py <rom_path>\n")
        print("Exemplos:")
        print("  python compression_table_extractor.py game.smc")
        print("  python compression_table_extractor.py \"C:/ROMs/Final Fantasy.smc\"\n")
        return 1

    rom_path = sys.argv[1]

    if not os.path.exists(rom_path):
        print(f"❌ Arquivo não encontrado: {rom_path}\n")
        return 1

    # Gera nome do relatório
    rom_name = os.path.splitext(os.path.basename(rom_path))[0]
    output_dir = os.path.dirname(rom_path)
    report_path = os.path.join(output_dir, f"{rom_name}_COMPRESSION_ANALYSIS.txt")

    print(f"📂 ROM: {os.path.basename(rom_path)}")
    print(f"📊 Relatório: {os.path.basename(report_path)}\n")

    # Analisa
    patterns = analyze_rom_compression(rom_path, report_path)

    if patterns:
        print(f"✅ SUCESSO! {len(patterns)} padrão(ões) de compressão encontrado(s)!")
        print(f"\n📖 Abra o relatório para ver detalhes:")
        print(f"   {report_path}\n")
    else:
        print("⚠️  Nenhum padrão de compressão detectado.")
        print("   Possíveis causas:")
        print("   • ROM não usa compressão de dicionário")
        print("   • Compressão é de tipo diferente")
        print("   • ROM está criptografada\n")

    return 0

if __name__ == "__main__":
    sys.exit(main())
