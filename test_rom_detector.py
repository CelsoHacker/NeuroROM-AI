#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Teste do ROM Detector
================================

Testa o detector com ROMs reais e gera relatório de precisão.
"""

import os
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from core.rom_detector import ROMDetector


def test_with_real_roms():
    """Testa o detector com ROMs reais do usuário."""

    detector = ROMDetector()

    # ROMs para testar (ADICIONE OS CAMINHOS REAIS AQUI)
    test_roms = [
        # Formato: (caminho, tipo_esperado)
        (r"C:\caminho\para\Super Mario World.smc", "SNES"),
        (r"C:\caminho\para\Final Fantasy VII.bin", "PS1"),
        (r"C:\caminho\para\The Legend of Zelda.n64", "N64"),
        (r"C:\caminho\para\Sonic.gen", "GENESIS"),
        (r"C:\caminho\para\Metroid Fusion.gba", "GBA"),
        (r"C:\caminho\para\Mario Kart Wii.iso", "WII"),
        (r"C:\caminho\para\God of War.iso", "PS2"),
        (r"C:\caminho\para\Halo.xbe", "XBOX"),
        (r"C:\caminho\para\Pokemon Red.gb", "GB"),
        (r"C:\caminho\para\Castlevania.nes", "NES"),
    ]

    print("=" * 80)
    print("🧪 TESTE DE DETECÇÃO DE ROMs - FASE 1")
    print("=" * 80)
    print()

    results = {
        'total': 0,
        'corretos': 0,
        'incorretos': 0,
        'nao_encontrados': 0,
        'detalhes': []
    }

    for filepath, expected_type in test_roms:
        results['total'] += 1

        if not os.path.exists(filepath):
            print(f"❌ ARQUIVO NÃO ENCONTRADO: {os.path.basename(filepath)}")
            results['nao_encontrados'] += 1
            results['detalhes'].append({
                'arquivo': os.path.basename(filepath),
                'esperado': expected_type,
                'obtido': 'FILE_NOT_FOUND',
                'confianca': 0.0,
                'status': 'NOT_FOUND'
            })
            continue

        # Detecta o tipo
        detected_type, confidence = detector.detect(filepath)
        category = detector.get_category(detected_type)

        # Verifica se acertou
        is_correct = (detected_type == expected_type)

        if is_correct:
            results['corretos'] += 1
            status = '✅ CORRETO'
        else:
            results['incorretos'] += 1
            status = '❌ INCORRETO'

        # Mostra resultado
        print(f"{status}")
        print(f"  Arquivo: {os.path.basename(filepath)}")
        print(f"  Esperado: {expected_type}")
        print(f"  Detectado: {detected_type} (confiança: {confidence*100:.1f}%)")
        print(f"  Categoria: {category}")
        print()

        results['detalhes'].append({
            'arquivo': os.path.basename(filepath),
            'esperado': expected_type,
            'obtido': detected_type,
            'confianca': confidence,
            'categoria': category,
            'status': 'CORRECT' if is_correct else 'INCORRECT'
        })

    # Relatório final
    print("=" * 80)
    print("📊 RELATÓRIO FINAL")
    print("=" * 80)

    arquivos_testados = results['total'] - results['nao_encontrados']
    if arquivos_testados > 0:
        precisao = (results['corretos'] / arquivos_testados) * 100
    else:
        precisao = 0.0

    print(f"Total de ROMs testadas: {results['total']}")
    print(f"  ✅ Corretos: {results['corretos']}")
    print(f"  ❌ Incorretos: {results['incorretos']}")
    print(f"  🔍 Não encontrados: {results['nao_encontrados']}")
    print()
    print(f"📈 PRECISÃO: {precisao:.1f}%")
    print()

    # Recomendações
    if precisao >= 90:
        print("✅ EXCELENTE! Sistema funcionando muito bem.")
    elif precisao >= 70:
        print("⚠️ BOM, mas precisa melhorias.")
    else:
        print("❌ CRÍTICO! Sistema precisa de correções.")

    print()
    print("=" * 80)

    # Salva relatório em arquivo
    save_report(results, precisao)

    return results, precisao


def save_report(results, precisao):
    """Salva relatório detalhado em arquivo."""

    report_path = Path(__file__).parent / "rom_detector_report.txt"

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("RELATÓRIO DE TESTE - ROM DETECTOR\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Total testado: {results['total']}\n")
        f.write(f"Corretos: {results['corretos']}\n")
        f.write(f"Incorretos: {results['incorretos']}\n")
        f.write(f"Não encontrados: {results['nao_encontrados']}\n")
        f.write(f"Precisão: {precisao:.1f}%\n\n")

        f.write("DETALHES:\n")
        f.write("-" * 80 + "\n")

        for detail in results['detalhes']:
            f.write(f"\nArquivo: {detail['arquivo']}\n")
            f.write(f"  Esperado: {detail['esperado']}\n")
            f.write(f"  Obtido: {detail['obtido']}\n")
            f.write(f"  Confiança: {detail['confianca']*100:.1f}%\n")
            f.write(f"  Status: {detail['status']}\n")

    print(f"💾 Relatório salvo em: {report_path}")


def test_interactive():
    """Modo interativo: testa um arquivo por vez."""

    detector = ROMDetector()

    print("=" * 80)
    print("🎮 MODO INTERATIVO - Teste Individual")
    print("=" * 80)
    print()

    while True:
        filepath = input("Digite o caminho da ROM (ou 'q' para sair): ").strip()

        if filepath.lower() == 'q':
            break

        # Remove aspas se o usuário colou com aspas
        filepath = filepath.strip('"\'')

        if not os.path.exists(filepath):
            print("❌ Arquivo não encontrado!")
            print()
            continue

        # Detecta
        detected_type, confidence = detector.detect(filepath)
        category = detector.get_category(detected_type)

        print()
        print(f"📁 Arquivo: {os.path.basename(filepath)}")
        print(f"🎯 Tipo detectado: {detected_type}")
        print(f"📊 Confiança: {confidence*100:.1f}%")
        print(f"📂 Categoria: {category}")
        print()


def main():
    """Função principal."""

    print("\n🎮 ROM DETECTOR - SISTEMA DE TESTES\n")
    print("Escolha o modo:")
    print("1. Teste com lista de ROMs (automático)")
    print("2. Teste interativo (um arquivo por vez)")
    print("3. Sair")
    print()

    choice = input("Opção: ").strip()

    if choice == '1':
        test_with_real_roms()
    elif choice == '2':
        test_interactive()
    elif choice == '3':
        print("👋 Até logo!")
    else:
        print("❌ Opção inválida!")


if __name__ == '__main__':
    main()
