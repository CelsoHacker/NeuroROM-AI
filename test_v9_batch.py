#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste Comparativo V9.0 - Execução em Lote
Roda o extrator V9.0 em múltiplas ROMs e gera relatório comparativo
"""

import sys
import time
from pathlib import Path
from datetime import datetime

# Adiciona o diretório do framework ao path
sys.path.insert(0, str(Path(__file__).parent / "rom-translation-framework"))

from core.ultimate_extractor_v9 import UltimateExtractorV9

def test_rom(rom_path, output_dir):
    """
    Testa uma ROM com o V9.0

    Args:
        rom_path: Caminho da ROM
        output_dir: Diretório de saída

    Returns:
        dict: Estatísticas da extração
    """
    print(f"\n{'='*80}")
    print(f"🎮 Testando: {rom_path.name}")
    print(f"{'='*80}\n")

    inicio = time.time()

    try:
        # Cria extrator
        extrator = UltimateExtractorV9(str(rom_path))

        # Executa extração
        resultado = extrator.extract_with_protection()

        tempo_decorrido = time.time() - inicio

        # Coleta estatísticas
        stats = {
            'nome': rom_path.name,
            'tamanho': rom_path.stat().st_size,
            'tempo': tempo_decorrido,
            'sucesso': True,
            'strings_principais': resultado.get('strings_principais', 0),
            'strings_recuperadas': resultado.get('strings_recuperadas', 0),
            'strings_dte_mte': resultado.get('strings_dte_mte', 0),
            'total': resultado.get('total', 0),
            'dte_mte_ativo': resultado.get('dte_mte_solver', 'NÃO'),
            'tipo_compressao': resultado.get('tipo_compressao', 'N/A'),
            'erro': None
        }

        print(f"\n✅ Extração concluída em {tempo_decorrido:.2f}s")
        print(f"📊 Total de strings: {stats['total']}")

        return stats

    except Exception as e:
        tempo_decorrido = time.time() - inicio

        print(f"\n❌ ERRO: {str(e)}")

        return {
            'nome': rom_path.name,
            'tamanho': rom_path.stat().st_size,
            'tempo': tempo_decorrido,
            'sucesso': False,
            'strings_principais': 0,
            'strings_recuperadas': 0,
            'strings_dte_mte': 0,
            'total': 0,
            'dte_mte_ativo': 'N/A',
            'tipo_compressao': 'N/A',
            'erro': str(e)
        }

def gerar_relatorio_comparativo(resultados, output_path):
    """
    Gera relatório comparativo em texto

    Args:
        resultados: Lista de dicts com estatísticas
        output_path: Caminho do arquivo de saída
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("RELATÓRIO COMPARATIVO - EXTRATOR V9.0\n")
        f.write(f"Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")

        # Tabela resumo
        f.write("RESUMO GERAL\n")
        f.write("-"*80 + "\n\n")

        f.write(f"{'ROM':<40} {'Total':<8} {'DTE/MTE':<10} {'Tempo':<10} {'Status':<10}\n")
        f.write("-"*80 + "\n")

        for r in resultados:
            nome_curto = r['nome'][:38]
            status = "✅ OK" if r['sucesso'] else "❌ ERRO"
            f.write(f"{nome_curto:<40} {r['total']:<8} {r['dte_mte_ativo']:<10} {r['tempo']:<10.2f}s {status:<10}\n")

        f.write("\n\n")

        # Detalhes por ROM
        f.write("DETALHES POR ROM\n")
        f.write("="*80 + "\n\n")

        for i, r in enumerate(resultados, 1):
            f.write(f"{i}. {r['nome']}\n")
            f.write("-"*80 + "\n")
            f.write(f"   Tamanho do arquivo: {r['tamanho']:,} bytes ({r['tamanho']/1024/1024:.2f} MB)\n")
            f.write(f"   Tempo de processamento: {r['tempo']:.2f}s\n")
            f.write(f"   Status: {'Sucesso' if r['sucesso'] else 'Falha'}\n\n")

            if r['sucesso']:
                f.write(f"   📊 ESTATÍSTICAS:\n")
                f.write(f"      • Strings principais: {r['strings_principais']}\n")
                f.write(f"      • Strings recuperadas: {r['strings_recuperadas']}\n")
                f.write(f"      • Strings DTE/MTE: {r['strings_dte_mte']}\n")
                f.write(f"      • TOTAL: {r['total']}\n\n")
                f.write(f"   🔧 TÉCNICO:\n")
                f.write(f"      • DTE/MTE Solver: {r['dte_mte_ativo']}\n")
                f.write(f"      • Tipo de compressão: {r['tipo_compressao']}\n")
            else:
                f.write(f"   ❌ ERRO: {r['erro']}\n")

            f.write("\n\n")

        # Estatísticas gerais
        f.write("ESTATÍSTICAS GERAIS\n")
        f.write("="*80 + "\n\n")

        total_roms = len(resultados)
        roms_sucesso = sum(1 for r in resultados if r['sucesso'])
        roms_com_dte = sum(1 for r in resultados if r['sucesso'] and r['dte_mte_ativo'] != 'NÃO')

        f.write(f"Total de ROMs testadas: {total_roms}\n")
        f.write(f"Extrações bem-sucedidas: {roms_sucesso} ({roms_sucesso/total_roms*100:.1f}%)\n")
        f.write(f"ROMs com DTE/MTE detectado: {roms_com_dte}\n\n")

        if roms_sucesso > 0:
            media_strings = sum(r['total'] for r in resultados if r['sucesso']) / roms_sucesso
            media_tempo = sum(r['tempo'] for r in resultados if r['sucesso']) / roms_sucesso

            f.write(f"Média de strings extraídas: {media_strings:.0f}\n")
            f.write(f"Tempo médio de processamento: {media_tempo:.2f}s\n\n")

        # Ranking
        f.write("\nRANKING POR QUANTIDADE DE STRINGS\n")
        f.write("-"*80 + "\n")

        ranking = sorted([r for r in resultados if r['sucesso']], key=lambda x: x['total'], reverse=True)
        for i, r in enumerate(ranking, 1):
            f.write(f"{i}. {r['nome']}: {r['total']} strings\n")

def main():
    """Função principal"""

    print("\n" + "="*80)
    print("🧪 TESTE COMPARATIVO V9.0 - Execução em Lote")
    print("="*80 + "\n")

    # Configuração
    base_dir = Path(__file__).parent
    rom_dir = base_dir / "rom-translation-framework" / "ROMs"
    output_dir = base_dir / "resultados_v8_comparativo"
    output_dir.mkdir(exist_ok=True)

    # Busca ROMs em todas as subpastas
    print("🔍 Procurando ROMs...\n")

    extensoes = ['.smc', '.sfc', '.nes', '.gba', '.gbc', '.gb', '.bin']
    roms_encontradas = []

    for ext in extensoes:
        roms_encontradas.extend(rom_dir.rglob(f'*{ext}'))

    # Remove ROMs traduzidas ou de teste
    roms_filtradas = [
        rom for rom in roms_encontradas
        if not any(x in rom.name.lower() for x in ['traduz', 'translated', 'test', 'dummy'])
    ]

    if not roms_filtradas:
        print("❌ Nenhuma ROM encontrada!")
        print(f"📂 Procurado em: {rom_dir}")
        return 1

    print(f"✅ {len(roms_filtradas)} ROMs encontradas:\n")
    for i, rom in enumerate(roms_filtradas, 1):
        tamanho_mb = rom.stat().st_size / 1024 / 1024
        print(f"   {i}. {rom.name} ({tamanho_mb:.2f} MB)")

    print(f"\n{'='*80}")
    resposta = input("\n🚀 Deseja processar todas essas ROMs? (s/n): ").strip().lower()

    if resposta != 's':
        print("\n❌ Operação cancelada pelo usuário.")
        return 0

    # Processa ROMs
    print(f"\n{'='*80}")
    print("🔥 INICIANDO PROCESSAMENTO EM LOTE")
    print(f"{'='*80}\n")

    resultados = []
    inicio_total = time.time()

    for i, rom_path in enumerate(roms_filtradas, 1):
        print(f"\n📊 Progresso: {i}/{len(roms_filtradas)}")
        resultado = test_rom(rom_path, output_dir)
        resultados.append(resultado)

        # Pequena pausa entre ROMs
        time.sleep(0.5)

    tempo_total = time.time() - inicio_total

    # Gera relatório
    print(f"\n{'='*80}")
    print("📝 GERANDO RELATÓRIO COMPARATIVO")
    print(f"{'='*80}\n")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    relatorio_path = output_dir / f"relatorio_comparativo_v9_{timestamp}.txt"

    gerar_relatorio_comparativo(resultados, relatorio_path)

    # Resumo final
    print(f"\n{'='*80}")
    print("✅ PROCESSAMENTO CONCLUÍDO!")
    print(f"{'='*80}\n")

    roms_sucesso = sum(1 for r in resultados if r['sucesso'])

    print(f"⏱️  Tempo total: {tempo_total:.2f}s")
    print(f"📊 ROMs processadas: {len(resultados)}")
    print(f"✅ Sucessos: {roms_sucesso}")
    print(f"❌ Falhas: {len(resultados) - roms_sucesso}")
    print(f"\n📂 Relatório salvo em:")
    print(f"   {relatorio_path}\n")

    # Mostra top 3
    ranking = sorted([r for r in resultados if r['sucesso']], key=lambda x: x['total'], reverse=True)
    if ranking:
        print("\n🏆 TOP 3 - Mais strings extraídas:")
        for i, r in enumerate(ranking[:3], 1):
            print(f"   {i}. {r['nome']}: {r['total']} strings")

    print()

    return 0

if __name__ == "__main__":
    sys.exit(main())
