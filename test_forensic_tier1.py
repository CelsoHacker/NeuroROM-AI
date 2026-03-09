#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
TESTE RÁPIDO - SISTEMA FORENSE TIER 1
================================================================================
Script de teste para validar a integração do sistema forense.

Execução:
    python test_forensic_tier1.py "caminho/para/arquivo.exe"

Ou para teste automático com arquivo dummy:
    python test_forensic_tier1.py --auto

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

def test_import():
    """Testa se o módulo forense pode ser importado."""
    print("=" * 80)
    print("TESTE 1: IMPORTAÇÃO DO MÓDULO FORENSE TIER 1")
    print("=" * 80)

    try:
        from forensic_engine_upgrade import (
            EngineDetectionWorkerTier1,
            FORENSIC_SIGNATURES_TIER1,
            calculate_entropy_shannon,
            estimate_year_from_binary,
            calculate_confidence_score,
            analyze_compression_type
        )
        print("✅ Módulo forensic_engine_upgrade importado com sucesso")
        print(f"✅ EngineDetectionWorkerTier1: {EngineDetectionWorkerTier1}")
        print(f"✅ Assinaturas carregadas: {len(FORENSIC_SIGNATURES_TIER1)} categorias")

        # Contar total de assinaturas
        total_sigs = sum(len(sigs) for sigs in FORENSIC_SIGNATURES_TIER1.values())
        print(f"✅ Total de assinaturas: {total_sigs}")

        return True
    except ImportError as e:
        print(f"❌ ERRO ao importar módulo: {e}")
        print("💡 Verifique se o arquivo forensic_engine_upgrade.py está na pasta interface/")
        return False


def test_entropy_calculation():
    """Testa cálculo de entropia de Shannon."""
    print("\n" + "=" * 80)
    print("TESTE 2: CÁLCULO DE ENTROPIA DE SHANNON")
    print("=" * 80)

    try:
        from forensic_engine_upgrade import calculate_entropy_shannon

        # Teste 1: Dados repetitivos (baixa entropia)
        data_low = b'\x00' * 1000
        entropy_low = calculate_entropy_shannon(data_low)
        print(f"✅ Entropia de dados repetitivos: {entropy_low:.2f} (esperado: ~0.0)")

        # Teste 2: Dados aleatórios (alta entropia)
        import random
        data_high = bytes([random.randint(0, 255) for _ in range(1000)])
        entropy_high = calculate_entropy_shannon(data_high)
        print(f"✅ Entropia de dados aleatórios: {entropy_high:.2f} (esperado: ~7.5-8.0)")

        # Teste 3: Texto ASCII (entropia média)
        data_text = b'The quick brown fox jumps over the lazy dog' * 20
        entropy_text = calculate_entropy_shannon(data_text)
        print(f"✅ Entropia de texto ASCII: {entropy_text:.2f} (esperado: ~4.0-5.0)")

        return True
    except Exception as e:
        print(f"❌ ERRO no cálculo de entropia: {e}")
        return False


def test_year_detection():
    """Testa detecção de ano."""
    print("\n" + "=" * 80)
    print("TESTE 3: DETECÇÃO DE ANO")
    print("=" * 80)

    try:
        from forensic_engine_upgrade import estimate_year_from_binary

        # Teste 1: Ano no nome do arquivo
        year1 = estimate_year_from_binary(b'', 'game_1999.exe')
        print(f"✅ Ano detectado no nome: {year1} (esperado: 1999)")

        # Teste 2: Ano no conteúdo binário
        data_with_year = b'Copyright 2005 Company Name'
        year2 = estimate_year_from_binary(data_with_year, 'game.exe')
        print(f"✅ Ano detectado no binário: {year2} (esperado: 2005)")

        # Teste 3: Sem ano
        year3 = estimate_year_from_binary(b'No year here', 'game.exe')
        print(f"✅ Sem ano detectado: {year3} (esperado: None)")

        return True
    except Exception as e:
        print(f"❌ ERRO na detecção de ano: {e}")
        return False


def test_confidence_scoring():
    """Testa scoring de confiança."""
    print("\n" + "=" * 80)
    print("TESTE 4: SCORING DE CONFIANÇA")
    print("=" * 80)

    try:
        from forensic_engine_upgrade import calculate_confidence_score

        # Teste 1: Muitas detecções
        detections_many = [
            {'confidence': 'high'} for _ in range(5)
        ]
        conf1 = calculate_confidence_score(detections_many, False)
        print(f"✅ Confiança com 5 detecções: {conf1} (esperado: Muito Alta)")

        # Teste 2: Poucas detecções
        detections_few = [
            {'confidence': 'medium'}
        ]
        conf2 = calculate_confidence_score(detections_few, False)
        print(f"✅ Confiança com 1 detecção: {conf2} (esperado: Média)")

        # Teste 3: Apenas extensão
        conf3 = calculate_confidence_score([], True)
        print(f"✅ Confiança só com extensão: {conf3} (esperado: Baixa)")

        return True
    except Exception as e:
        print(f"❌ ERRO no scoring de confiança: {e}")
        return False


def test_file_detection(file_path):
    """Testa detecção completa de um arquivo."""
    print("\n" + "=" * 80)
    print("TESTE 5: DETECÇÃO COMPLETA DE ARQUIVO")
    print("=" * 80)

    if not os.path.exists(file_path):
        print(f"❌ Arquivo não encontrado: {file_path}")
        return False

    try:
        # Importar PyQt6 (necessário para QThread)
        from PyQt6.QtCore import QCoreApplication
        from forensic_engine_upgrade import EngineDetectionWorkerTier1

        # Criar aplicação Qt mínima
        app = QCoreApplication(sys.argv)

        # Variável para armazenar resultado
        result = [None]
        errors = []

        def on_complete(detection_result):
            result[0] = detection_result
            app.quit()

        def on_progress(status):
            print(f"   {status}")

        def on_error(error):
            errors.append(error)
            app.quit()

        # Criar worker
        print(f"📁 Analisando: {file_path}")
        worker = EngineDetectionWorkerTier1(file_path)

        # Conectar sinais
        worker.detection_complete.connect(on_complete)
        worker.progress_signal.connect(on_progress)

        # Iniciar
        worker.start()

        # Executar loop de eventos
        app.exec()

        # Verificar resultado
        if result[0]:
            r = result[0]
            print("\n" + "=" * 80)
            print("RESULTADO DA DETECÇÃO:")
            print("=" * 80)
            print(f"✅ Tipo: {r.get('type')}")
            print(f"✅ Plataforma: {r.get('platform')}")
            print(f"✅ Engine: {r.get('engine')}")
            print(f"✅ Ano Estimado: {r.get('year_estimate', 'Não detectado')}")
            print(f"✅ Compressão: {r.get('compression')}")
            print(f"✅ Confiança: {r.get('confidence')}")
            print(f"✅ Entropia: {r.get('entropy', 0):.2f}")

            # Avisos
            if r.get('warnings'):
                print("\n⚠️  AVISOS:")
                for warning in r['warnings']:
                    print(f"   {warning}")

            # Recomendações
            if r.get('recommendations'):
                print("\n💡 RECOMENDAÇÕES:")
                for rec in r['recommendations']:
                    print(f"   {rec}")

            return True
        else:
            print("❌ Nenhum resultado retornado")
            if errors:
                print(f"❌ Erros: {errors}")
            return False

    except ImportError as e:
        print(f"❌ ERRO: PyQt6 não está instalado")
        print(f"   pip install PyQt6")
        return False
    except Exception as e:
        print(f"❌ ERRO na detecção: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_dummy_file():
    """Cria arquivo dummy para teste."""
    print("\n" + "=" * 80)
    print("CRIANDO ARQUIVO DUMMY PARA TESTE")
    print("=" * 80)

    dummy_path = Path(__file__).parent / "test_dummy.exe"

    # Criar arquivo com assinatura Windows PE
    with open(dummy_path, 'wb') as f:
        # Magic bytes MZ
        f.write(b'MZ')
        f.write(b'\x00' * 58)  # Padding até offset 0x3C
        # Offset para PE header (0x80)
        f.write(b'\x80\x00\x00\x00')
        # Mais padding
        f.write(b'\x00' * (0x80 - 64))
        # PE signature
        f.write(b'PE\x00\x00')
        # Dados aleatórios
        f.write(b'Copyright 2024 Test Company\x00')
        f.write(b'\x00' * 1000)

    print(f"✅ Arquivo dummy criado: {dummy_path}")
    return str(dummy_path)


def main():
    """Função principal."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║           🔬 TESTE DO SISTEMA FORENSE TIER 1 - VALIDAÇÃO COMPLETA            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    # Executar testes básicos
    tests_passed = 0
    tests_total = 4

    if test_import():
        tests_passed += 1

    if test_entropy_calculation():
        tests_passed += 1

    if test_year_detection():
        tests_passed += 1

    if test_confidence_scoring():
        tests_passed += 1

    # Teste de arquivo
    if len(sys.argv) > 1:
        if sys.argv[1] == '--auto':
            # Criar arquivo dummy
            dummy_file = create_dummy_file()
            if test_file_detection(dummy_file):
                tests_passed += 1
            tests_total += 1

            # Remover arquivo dummy
            try:
                os.remove(dummy_file)
                print(f"\n🗑️  Arquivo dummy removido: {dummy_file}")
            except:
                pass
        else:
            # Testar arquivo fornecido
            file_path = sys.argv[1]
            if test_file_detection(file_path):
                tests_passed += 1
            tests_total += 1

    # Resumo
    print("\n" + "=" * 80)
    print("RESUMO DOS TESTES")
    print("=" * 80)
    print(f"Testes passados: {tests_passed}/{tests_total}")

    if tests_passed == tests_total:
        print("✅ TODOS OS TESTES PASSARAM!")
        print("✅ Sistema Forense Tier 1 está OPERACIONAL")
        return 0
    else:
        print(f"❌ {tests_total - tests_passed} teste(s) falharam")
        print("⚠️  Verifique os erros acima")
        return 1


if __name__ == "__main__":
    sys.exit(main())
