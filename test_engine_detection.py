# -*- coding: utf-8 -*-
"""
Script de Teste - Detecção de Engine
Testa o módulo engine_detector com vários tipos de arquivo
"""

import os
import sys
from pathlib import Path

# Adicionar o diretório raiz ao path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from core.engine_detector import detect_game_engine, EngineDetector


def print_detection_result(file_path):
    """Imprime o resultado da detecção de forma formatada."""
    print("\n" + "="*70)
    print(f"📂 Arquivo: {os.path.basename(file_path)}")
    print("="*70)

    if not os.path.exists(file_path):
        print(f"❌ Arquivo não existe: {file_path}")
        return

    # Detectar
    result = detect_game_engine(file_path)

    # Exibir resultado
    print(f"🎯 Tipo: {result['type']}")
    print(f"🎮 Plataforma: {result['platform']}")
    print(f"⚙️ Engine: {result['engine']}")
    print(f"📏 Extensão: {result['extension']}")
    print(f"✅ Válido: {'Sim' if result['valid'] else 'Não'}")
    print(f"🔄 Conversor necessário: {'Sim' if result['converter_needed'] else 'Não'}")

    if result['converter_suggestion']:
        print(f"💡 Conversor sugerido: {result['converter_suggestion']}")

    print(f"\n📋 Abas suportadas: {result['tabs_supported']}")
    print(f"📥 Reinserção automática: {'✅ Sim' if result['reinsertion_supported'] else '❌ Não'}")
    print(f"🎨 Lab Gráfico: {'✅ Sim' if result['graphics_lab_supported'] else '❌ Não'}")

    print(f"\n📝 Notas: {result['notes']}")

    # Workflow
    detector = EngineDetector()
    workflow = detector.get_recommended_workflow(result)

    print("\n" + "-"*70)
    print("📋 WORKFLOW RECOMENDADO:")
    print("-"*70)
    for step in workflow:
        print(step)
    print("="*70)


def test_all_extensions():
    """Testa detecção com vários tipos de extensão."""

    print("\n\n")
    print("🔬 TESTE DE DETECÇÃO DE ENGINE")
    print("="*70)
    print("Testando detecção automática com vários tipos de arquivo...")
    print("="*70)

    # Lista de arquivos de teste (simulados)
    test_cases = [
        # ROMs de console
        {"name": "super_mario_world.smc", "should_detect": "SNES ROM"},
        {"name": "zelda.sfc", "should_detect": "SNES ROM"},
        {"name": "super_mario.nes", "should_detect": "NES ROM"},
        {"name": "pokemon_fire_red.gba", "should_detect": "Game Boy Advance ROM"},
        {"name": "tetris.gb", "should_detect": "Game Boy ROM"},
        {"name": "mario64.z64", "should_detect": "Nintendo 64 ROM"},

        # Jogos de PC
        {"name": "doom.wad", "should_detect": "Doom WAD"},
        {"name": "quake.pak", "should_detect": "PAK Archive"},
        {"name": "game.exe", "should_detect": "PC Executable"},
        {"name": "data.assets", "should_detect": "Unity Assets"},
        {"name": "script.rpy", "should_detect": "RenPy Script"},
        {"name": "items.json", "should_detect": "JSON Data"},

        # Desconhecidos
        {"name": "unknown.xyz", "should_detect": "Unknown"},
    ]

    # Criar diretório temporário para testes
    test_dir = Path("test_files_temp")
    test_dir.mkdir(exist_ok=True)

    results_summary = []

    for test_case in test_cases:
        file_name = test_case['name']
        expected = test_case['should_detect']
        file_path = test_dir / file_name

        # Criar arquivo vazio para teste
        try:
            with open(file_path, 'wb') as f:
                # Adicionar headers específicos para alguns tipos
                if file_name.endswith('.nes'):
                    f.write(b'NES\x1a')  # Header NES válido
                elif file_name.endswith('.wad'):
                    f.write(b'IWAD')  # Header Doom WAD
                elif file_name.endswith('.pak'):
                    f.write(b'PACK')  # Header Quake PAK
                else:
                    f.write(b'\x00' * 1024)  # Arquivo genérico

            # Detectar
            result = detect_game_engine(str(file_path))

            # Verificar se detectou corretamente
            detected_platform = result['platform']
            success = expected.lower() in detected_platform.lower()

            results_summary.append({
                'file': file_name,
                'expected': expected,
                'detected': detected_platform,
                'success': success,
                'type': result['type']
            })

            # Exibir resultado detalhado
            print_detection_result(str(file_path))

        except Exception as e:
            print(f"\n❌ Erro ao testar {file_name}: {e}")
            results_summary.append({
                'file': file_name,
                'expected': expected,
                'detected': f"ERRO: {e}",
                'success': False,
                'type': 'ERROR'
            })

    # Limpar arquivos de teste
    import shutil
    shutil.rmtree(test_dir, ignore_errors=True)

    # Resumo final
    print("\n\n")
    print("="*70)
    print("📊 RESUMO DOS TESTES")
    print("="*70)

    total = len(results_summary)
    success_count = sum(1 for r in results_summary if r['success'])

    print(f"\nTotal de testes: {total}")
    print(f"✅ Sucessos: {success_count}")
    print(f"❌ Falhas: {total - success_count}")
    print(f"📈 Taxa de acerto: {(success_count/total)*100:.1f}%")

    print("\n" + "-"*70)
    print("Detalhes:")
    print("-"*70)

    for r in results_summary:
        status = "✅" if r['success'] else "❌"
        print(f"{status} {r['file']:25} | Esperado: {r['expected']:20} | Detectado: {r['detected']}")

    print("="*70)


def test_specific_file(file_path):
    """Testa detecção com um arquivo específico."""
    if os.path.exists(file_path):
        print_detection_result(file_path)
    else:
        print(f"❌ Arquivo não encontrado: {file_path}")
        print("\nUso: python test_engine_detection.py [caminho_do_arquivo]")
        print("Ou execute sem argumentos para testar todos os tipos de extensão.")


if __name__ == '__main__':
    print("🚀 Iniciando testes de detecção de engine...")

    if len(sys.argv) > 1:
        # Testar arquivo específico passado como argumento
        test_specific_file(sys.argv[1])
    else:
        # Testar todas as extensões
        test_all_extensions()

    print("\n✅ Testes concluídos!\n")
