#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste rápido da função de análise de header SNES"""

import sys
import os

# Adicionar caminho do projeto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'interface'))

from interface.forensic_engine_upgrade import EngineDetectionWorkerTier1

# Caminho da ROM
rom_path = r"c:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework\ROMs\Super Nintedo\Super Mario World.smc"

print("=" * 80)
print("TESTE DE ANÁLISE DE HEADER SNES")
print("=" * 80)
print(f"ROM: {rom_path}")
print()

# Ler primeiros 128KB da ROM
with open(rom_path, 'rb') as f:
    header = f.read(131072)

# Criar worker (só para usar a função _analyze_snes_header)
worker = EngineDetectionWorkerTier1(rom_path)
snes_info = worker._analyze_snes_header(header)

if snes_info:
    print("✅ HEADER SNES DETECTADO COM SUCESSO!")
    print()
    print(f"📛 Título: {snes_info['title']}")
    print(f"🗺️  Tipo de Mapeamento: {snes_info['map_type']}")
    print(f"💾 Tipo de Cartucho: {snes_info['cart_type']}")
    print(f"📦 Tamanho da ROM: {snes_info['rom_size_kb']} KB ({snes_info['rom_size_kb']/1024:.2f} MB)")
    print(f"🌍 Region: {snes_info['region']}")
    print(f"📍 Header Offset: 0x{snes_info['header_offset']:X}")
else:
    print("❌ Falha ao detectar header SNES")

print()
print("=" * 80)
