#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
TESTE DO SISTEMA DE FINGERPRINTING CONTEXTUAL - TIER 1 ADVANCED
================================================================================
Script de teste para validar a detecção de padrões contextuais.

Execução:
    python test_contextual_patterns.py

Desenvolvido por: Celso
Data: 2026-01-06
================================================================================
"""

import sys
import os
from pathlib import Path

# Adicionar diretório da interface ao path
interface_dir = Path(__file__).parent / 'interface'
sys.path.insert(0, str(interface_dir))

def test_pattern_detection():
    """Testa detecção de padrões contextuais."""
    print("=" * 80)
    print("TESTE: DETECÇÃO DE PADRÕES CONTEXTUAIS")
    print("=" * 80)

    try:
        from forensic_engine_upgrade import scan_contextual_patterns, DETECTION_PATTERNS

        print(f"✅ Módulo importado com sucesso")
        print(f"✅ Total de padrões disponíveis: {len(DETECTION_PATTERNS)}")

        # Criar dados de teste com múltiplos padrões
        test_data = b''

        # Adicionar padrão de menu
        test_data += b'New Game\x00Load a Game\x00Configuration\x00Credits\x00Exit Game'
        test_data += b'\x00' * 100  # Padding

        # Adicionar padrão de áudio
        test_data += b'Master Volume\x00SFX\x00Music\x00Voices'
        test_data += b'\x00' * 100  # Padding

        # Adicionar padrão de vídeo
        test_data += b'800x600\x0016-bit\x0032-bit'
        test_data += b'\x00' * 100  # Padding

        # Adicionar padrão de copyright
        test_data += b'Copyright 1999'
        test_data += b'\x00' * 100  # Padding

        # Escanear padrões
        print("\n🔍 Escaneando padrões em dados de teste...")
        matches = scan_contextual_patterns(test_data)

        if matches:
            print(f"\n✅ Encontrados {len(matches)} padrões!")
            print("\nDetalhes dos padrões encontrados:")
            print("-" * 80)

            for i, match in enumerate(matches, 1):
                print(f"\n{i}. Padrão: {match['pattern_code']}")
                print(f"   Descrição: {match['description']}")
                print(f"   Posição: 0x{match['position']:X}")
                print(f"   Confiança: {match['confidence']}")

                # Mostrar arquitetura se disponível
                if match.get('architecture'):
                    print(f"   🏗️  Arquitetura: {match['architecture']}")
                    print(f"   📊 Tipo: {match['game_type']}")
                    print(f"   📅 Período: {match['year_range']}")
                    print(f"   Características:")
                    for char in match.get('characteristics', []):
                        print(f"      • {char}")

            return True
        else:
            print("❌ Nenhum padrão detectado")
            return False

    except ImportError as e:
        print(f"❌ ERRO ao importar módulo: {e}")
        return False
    except Exception as e:
        print(f"❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pattern_architecture_mapping():
    """Testa mapeamento de arquitetura."""
    print("\n" + "=" * 80)
    print("TESTE: MAPEAMENTO DE ARQUITETURA")
    print("=" * 80)

    try:
        from forensic_engine_upgrade import PATTERN_ARCHITECTURE_MAP

        print(f"✅ Arquiteturas mapeadas: {len(PATTERN_ARCHITECTURE_MAP)}")
        print("\nLista de arquiteturas disponíveis:")
        print("-" * 80)

        for pattern_code, arch_info in PATTERN_ARCHITECTURE_MAP.items():
            print(f"\n📋 {pattern_code}")
            print(f"   Arquitetura: {arch_info['architecture']}")
            print(f"   Tipo: {arch_info['type']}")
            print(f"   Período: {arch_info['year_range']}")
            print(f"   Características: {len(arch_info['characteristics'])} itens")

        return True

    except ImportError as e:
        print(f"❌ ERRO ao importar módulo: {e}")
        return False
    except Exception as e:
        print(f"❌ ERRO: {e}")
        return False


def test_full_detection_with_patterns():
    """Testa detecção completa com padrões contextuais."""
    print("\n" + "=" * 80)
    print("TESTE: DETECÇÃO COMPLETA COM WORKER")
    print("=" * 80)

    try:
        from PyQt6.QtCore import QCoreApplication
        from forensic_engine_upgrade import EngineDetectionWorkerTier1

        # Criar arquivo de teste
        test_file = Path(__file__).parent / "test_contextual_game.exe"

        print(f"📁 Criando arquivo de teste: {test_file}")

        with open(test_file, 'wb') as f:
            # Magic bytes Windows PE
            f.write(b'MZ')
            f.write(b'\x00' * 58)
            f.write(b'\x80\x00\x00\x00')  # PE offset
            f.write(b'\x00' * (0x80 - 64))

            # PE signature
            f.write(b'PE\x00\x00')

            # Copyright
            f.write(b'Copyright 1999 Test Company\x00')
            f.write(b'\x00' * 500)

            # Padrões contextuais
            f.write(b'New Game\x00Load a Game\x00Configuration\x00Credits\x00Exit Game\x00')
            f.write(b'\x00' * 200)

            f.write(b'Master Volume\x00SFX\x00Music\x00Voices\x00')
            f.write(b'\x00' * 200)

            f.write(b'800x600\x0016-bit\x0032-bit\x00')
            f.write(b'\x00' * 200)

            f.write(b'Inventory\x00Equipment\x00Use\x00Drop\x00')
            f.write(b'\x00' * 200)

            # Dados aleatórios
            f.write(b'\x00' * 10000)

        print("✅ Arquivo de teste criado")

        # Criar aplicação Qt
        app = QCoreApplication(sys.argv)

        # Variável para resultado
        result = [None]

        def on_complete(detection_result):
            result[0] = detection_result
            app.quit()

        def on_progress(status):
            print(f"   {status}")

        # Criar worker
        print(f"\n🔬 Analisando arquivo de teste...")
        worker = EngineDetectionWorkerTier1(str(test_file))

        # Conectar sinais
        worker.detection_complete.connect(on_complete)
        worker.progress_signal.connect(on_progress)

        # Iniciar
        worker.start()

        # Executar
        app.exec()

        # Verificar resultado
        if result[0]:
            r = result[0]
            print("\n" + "=" * 80)
            print("RESULTADO DA DETECÇÃO COMPLETA:")
            print("=" * 80)
            print(f"✅ Tipo: {r.get('type')}")
            print(f"✅ Plataforma: {r.get('platform')}")
            print(f"✅ Engine: {r.get('engine')}")
            print(f"✅ Ano: {r.get('year_estimate', 'N/A')}")
            print(f"✅ Compressão: {r.get('compression')}")
            print(f"✅ Confiança: {r.get('confidence')}")

            # Arquitetura inferida
            arch_inf = r.get('architecture_inference')
            if arch_inf:
                print("\n🏗️  ARQUITETURA INFERIDA:")
                print(f"   Arquitetura: {arch_inf['architecture']}")
                print(f"   Tipo de Jogo: {arch_inf['game_type']}")
                print(f"   Período: {arch_inf['year_range']}")
                print(f"   Baseado em: {arch_inf['based_on']}")

            # Padrões contextuais
            patterns = r.get('contextual_patterns', [])
            if patterns:
                print(f"\n🎯 PADRÕES CONTEXTUAIS: {len(patterns)} encontrados")
                for pattern in patterns:
                    print(f"   • {pattern['description']}")
                    if pattern.get('architecture'):
                        print(f"     → Arquitetura: {pattern['architecture']}")

            # Remover arquivo de teste
            try:
                os.remove(test_file)
                print(f"\n🗑️  Arquivo de teste removido")
            except:
                pass

            return True
        else:
            print("❌ Nenhum resultado retornado")
            return False

    except ImportError as e:
        print(f"❌ ERRO: PyQt6 não está instalado")
        print(f"   pip install PyQt6")
        return False
    except Exception as e:
        print(f"❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Função principal."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║      🎯 TESTE DO SISTEMA DE FINGERPRINTING CONTEXTUAL - TIER 1 ADVANCED      ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    tests_passed = 0
    tests_total = 3

    # Teste 1: Detecção de padrões
    if test_pattern_detection():
        tests_passed += 1

    # Teste 2: Mapeamento de arquitetura
    if test_pattern_architecture_mapping():
        tests_passed += 1

    # Teste 3: Detecção completa
    if test_full_detection_with_patterns():
        tests_passed += 1

    # Resumo
    print("\n" + "=" * 80)
    print("RESUMO DOS TESTES")
    print("=" * 80)
    print(f"Testes passados: {tests_passed}/{tests_total}")

    if tests_passed == tests_total:
        print("\n✅ TODOS OS TESTES PASSARAM!")
        print("✅ Sistema de Fingerprinting Contextual está OPERACIONAL")
        print("\n🎉 Parabéns! O sistema está pronto para uso!")
        return 0
    else:
        print(f"\n❌ {tests_total - tests_passed} teste(s) falharam")
        print("⚠️  Verifique os erros acima")
        return 1


if __name__ == "__main__":
    sys.exit(main())
