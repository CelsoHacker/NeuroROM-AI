# -*- coding: utf-8 -*-
"""
================================================================================
EXEMPLO DE USO - SISTEMA FORENSE CORRIGIDO
================================================================================
Demonstra o uso correto do ForensicScannerReal com assinaturas reais.

Este exemplo mostra:
1. Como escanear arquivos com assinaturas reais
2. Como extrair texto de diferentes tipos de arquivo
3. Como usar o sistema de métricas honesto
4. Casos de teste para validação

Autor: Celso - Sistema Forense Corrigido
Data: 2026-01-06
================================================================================
"""

import os
import sys
from pathlib import Path

# Adiciona o diretório core ao path
sys.path.insert(0, str(Path(__file__).parent.parent / 'core'))

from forensic_scanner import (
    ForensicScannerReal,
    GameTextExtractorCorrected,
    HonestMetrics,
    FileType,
    scan_file,
    extract_text_from_file
)


def exemplo_1_scan_simples():
    """Exemplo 1: Scan simples de um arquivo."""
    print("\n" + "=" * 80)
    print("EXEMPLO 1: SCAN SIMPLES DE ARQUIVO")
    print("=" * 80)

    # Cria scanner
    scanner = ForensicScannerReal()

    # Lista de arquivos para testar (você pode adicionar seus próprios)
    test_files = [
        "C:\\Games\\MeuJogo\\game.exe",
        "C:\\Games\\MeuJogo\\data.pak",
        "installer.exe",
    ]

    print("\n💡 NOTA: Adicione caminhos reais de arquivos para teste")
    print("         Os exemplos abaixo são apenas demonstrativos\n")

    for file_path in test_files:
        if not os.path.exists(file_path):
            print(f"⏭️  Pulando (não existe): {file_path}")
            continue

        print(f"\n📁 Analisando: {file_path}")
        print("-" * 80)

        result = scanner.scan_file(file_path)

        if 'error' in result:
            print(f"❌ Erro: {result['error']}")
            continue

        print(f"📊 Tamanho: {result['file_size']:,} bytes")

        if result['detections']:
            print(f"🔍 Detecções ({len(result['detections'])}):")
            for detection in result['detections']:
                print(f"   • {detection.description}")
                print(f"     Tipo: {detection.type.value}")
                print(f"     Assinatura: {detection.signature}")
                print(f"     Confiança: {detection.confidence}")
                if detection.warning:
                    print(f"     ⚠️  {detection.warning}")
        else:
            print("   Nenhuma assinatura conhecida detectada")


def exemplo_2_extracao_texto():
    """Exemplo 2: Extração de texto com fluxo correto."""
    print("\n" + "=" * 80)
    print("EXEMPLO 2: EXTRAÇÃO DE TEXTO COM FLUXO CORRETO")
    print("=" * 80)

    # Cria extrator
    extractor = GameTextExtractorCorrected()

    # Arquivo para processar
    file_path = "C:\\Games\\MeuJogo\\game.exe"

    if not os.path.exists(file_path):
        print(f"\n💡 Arquivo de exemplo não existe: {file_path}")
        print("   Substitua pelo caminho de um arquivo real")
        return

    # Processa arquivo (usa fluxo: Forense → Extração → Processamento)
    result = extractor.process_file(file_path)

    if result.get('success'):
        print(f"\n✅ Processamento bem-sucedido!")
        print(f"   Tipo: {result.get('type')}")
        print(f"   Mensagem: {result.get('message')}")

        if 'recommendation' in result:
            print(f"\n💡 RECOMENDAÇÃO:")
            print(f"   {result['recommendation']}")

        if 'texts' in result and result['texts']:
            print(f"\n📝 Textos extraídos: {len(result['texts'])}")

            # Salva em arquivo
            output_dir = Path(__file__).parent / "output"
            output_dir.mkdir(exist_ok=True)

            output_file = output_dir / "textos_extraidos_exemplo.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"Arquivo analisado: {file_path}\n")
                f.write(f"Tipo detectado: {result.get('type')}\n")
                f.write(f"Total de textos: {len(result['texts'])}\n")
                f.write("\n" + "=" * 80 + "\n\n")

                for i, text in enumerate(result['texts'], 1):
                    f.write(f"{i}. {text}\n")

            print(f"💾 Salvo em: {output_file}")

            # Mostra amostra
            print(f"\n📄 AMOSTRA (primeiras 5 strings):")
            for i, text in enumerate(result['texts'][:5], 1):
                preview = text[:70] + "..." if len(text) > 70 else text
                print(f"   {i}. {preview}")
    else:
        print(f"\n❌ Erro no processamento: {result.get('error')}")


def exemplo_3_metricas_honestas():
    """Exemplo 3: Sistema de métricas honesto (sem invenção de estatísticas)."""
    print("\n" + "=" * 80)
    print("EXEMPLO 3: SISTEMA DE MÉTRICAS HONESTO")
    print("=" * 80)

    # Cria scanner e sistema de métricas
    scanner = ForensicScannerReal()
    metrics = HonestMetrics()

    print("\n💡 SISTEMA DE MÉTRICAS HONESTO:")
    print("   - Não inventa porcentagens")
    print("   - Só reporta métricas baseadas em testes REAIS")
    print("   - Requer arquivos de teste com ground truth\n")

    # Adiciona casos de teste
    # IMPORTANTE: Você precisa fornecer arquivos REAIS e especificar o que espera detectar
    test_cases = [
        # (arquivo, tipos esperados)
        ("C:\\Games\\Unity\\data.unity3d", [FileType.UNITY_ASSET_BUNDLE]),
        ("C:\\Games\\Unreal\\data.pak", [FileType.UNREAL_PAK_V4]),
        ("C:\\Downloads\\setup.exe", [FileType.INNO_SETUP, FileType.WINDOWS_EXE]),
        ("C:\\Games\\archive.zip", [FileType.ZIP_ARCHIVE]),
    ]

    print("📋 CASOS DE TESTE:")
    for file_path, expected in test_cases:
        metrics.add_test_case(file_path, expected)
        exists = "✅" if os.path.exists(file_path) else "❌"
        print(f"   {exists} {file_path}")
        print(f"      Esperado: {[t.value for t in expected]}")

    print("\n💡 NOTA: Adicione arquivos reais para obter métricas válidas")
    print("   Os exemplos acima são apenas demonstrativos\n")

    # Executa testes
    results = metrics.run_tests(scanner)

    if results.get('total_tests', 0) > 0:
        print("\n📊 MÉTRICAS CALCULADAS:")
        print(f"   Precisão: {results['precision']:.1%}")
        print(f"   Recall:   {results['recall']:.1%}")
        print(f"   F1-Score: {results.get('f1_score', 0):.1%}")
        print(f"\n   Baseado em {results['total_tests']} testes reais")
    else:
        print("\n⚠️  Nenhum teste executado (arquivos não encontrados)")


def exemplo_4_funcoes_conveniencia():
    """Exemplo 4: Usando funções de conveniência."""
    print("\n" + "=" * 80)
    print("EXEMPLO 4: FUNÇÕES DE CONVENIÊNCIA")
    print("=" * 80)

    file_path = "C:\\Games\\MeuJogo\\game.exe"

    if not os.path.exists(file_path):
        print(f"\n💡 Arquivo de exemplo não existe: {file_path}")
        print("   Substitua pelo caminho de um arquivo real")
        return

    # Método 1: Só escanear (análise forense)
    print("\n📍 Método 1: scan_file() - Apenas análise forense")
    print("-" * 80)
    scan_result = scan_file(file_path)

    if scan_result.get('detections'):
        for detection in scan_result['detections']:
            print(f"   • {detection.description}")

    # Método 2: Escanear + extrair texto (pipeline completo)
    print("\n📍 Método 2: extract_text_from_file() - Pipeline completo")
    print("-" * 80)
    extract_result = extract_text_from_file(file_path)

    if extract_result.get('success'):
        print(f"   ✅ {extract_result.get('message')}")
        print(f"   Textos: {len(extract_result.get('texts', []))}")


def exemplo_5_assinaturas_disponiveis():
    """Exemplo 5: Lista todas as assinaturas disponíveis."""
    print("\n" + "=" * 80)
    print("EXEMPLO 5: ASSINATURAS DISPONÍVEIS NO SISTEMA")
    print("=" * 80)

    scanner = ForensicScannerReal()

    print("\n🔬 ASSINATURAS REAIS IMPLEMENTADAS:")
    print("-" * 80)

    # Agrupa por categoria
    signatures_by_category = {}

    for signature, info in scanner.signatures.items():
        category = info.type.name.split('_')[0]  # Pega primeira parte (UNITY, UNREAL, etc)

        if category not in signatures_by_category:
            signatures_by_category[category] = []

        signatures_by_category[category].append({
            'signature': signature,
            'info': info
        })

    for category, sigs in sorted(signatures_by_category.items()):
        print(f"\n📁 {category}:")
        for sig_data in sigs:
            sig = sig_data['signature']
            info = sig_data['info']

            # Mostra hex ou ASCII
            if all(32 <= b <= 126 for b in sig):
                sig_display = sig.decode('ascii')
            else:
                sig_display = sig.hex()

            print(f"   • {info.type.value}")
            print(f"     Assinatura: {sig_display}")
            print(f"     Descrição: {info.description}")
            if info.warning:
                print(f"     ⚠️  {info.warning}")

    print(f"\n📊 Total: {len(scanner.signatures)} assinaturas reais")


def main():
    """Função principal com menu de exemplos."""
    print("""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║               🔬 SISTEMA FORENSE CORRIGIDO - EXEMPLOS DE USO                  ║
║                                                                               ║
║  Sistema profissional com assinaturas REAIS e métricas HONESTAS             ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
""")

    print("📚 EXEMPLOS DISPONÍVEIS:\n")
    print("   1. Scan simples de arquivo (análise forense)")
    print("   2. Extração de texto com fluxo correto")
    print("   3. Sistema de métricas honesto")
    print("   4. Funções de conveniência")
    print("   5. Lista de assinaturas disponíveis")
    print("   6. Executar todos os exemplos")
    print("   0. Sair\n")

    escolha = input("Digite o número do exemplo (ou Enter para exemplo 5): ").strip()

    if not escolha:
        escolha = "5"

    exemplos = {
        "1": exemplo_1_scan_simples,
        "2": exemplo_2_extracao_texto,
        "3": exemplo_3_metricas_honestas,
        "4": exemplo_4_funcoes_conveniencia,
        "5": exemplo_5_assinaturas_disponiveis,
    }

    if escolha == "6":
        for func in exemplos.values():
            func()
    elif escolha in exemplos:
        exemplos[escolha]()
    elif escolha == "0":
        print("\n👋 Até logo!")
        return
    else:
        print(f"\n❌ Opção inválida: {escolha}")
        return

    print("\n" + "=" * 80)
    print("✅ Exemplo concluído!")
    print("=" * 80)


if __name__ == "__main__":
    main()
