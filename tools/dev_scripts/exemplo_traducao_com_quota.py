#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
EXEMPLO COMPLETO - Sistema de Tradução com Gerenciamento de Quota
================================================================================

Este script demonstra como usar o sistema avançado de tradução em lotes
com gerenciamento inteligente de quota da API Google Gemini.

Recursos demonstrados:
- ✅ Gerenciamento automático de quota (20 requisições/dia)
- ✅ Tradução em lotes otimizada (até 200 textos por requisição)
- ✅ Fila de prioridades com agendamento inteligente
- ✅ Salvamento automático de progresso
- ✅ Resumo de traduções interrompidas
- ✅ Monitoramento em tempo real

Autor: ROM Translation Framework v5.3
Data: 2025-12-19
================================================================================
"""

import sys
import os

# Adiciona diretório do framework ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'rom-translation-framework'))

import time
from typing import List

# Importações do framework
from interface.gemini_api import (
    translate_batch,
    get_quota_status,
    estimate_translation_quota,
    print_quota_estimate,
    get_quota_stats_message
)

from core.quota_manager import get_quota_manager
from core.batch_queue_manager import BatchQueueManager, Priority


def exemplo_1_traducao_simples():
    """
    Exemplo 1: Tradução simples com controle de quota
    ==================================================
    """
    print("\n" + "="*80)
    print("EXEMPLO 1: Tradução Simples com Controle de Quota")
    print("="*80 + "\n")

    # Textos para traduzir
    textos = [
        "Welcome to the game!",
        "Press START to begin",
        "Game Over",
        "Continue?",
        "New Game"
    ]

    # Sua API key do Google Gemini
    API_KEY = input("Digite sua API Key do Google Gemini: ").strip()

    if not API_KEY:
        print("❌ API Key não fornecida. Abortando.")
        return

    print(f"\n📝 Traduzindo {len(textos)} textos...")
    print(f"📊 Status da quota: {get_quota_stats_message()}\n")

    # Traduz com controle automático de quota
    traducoes, sucesso, erro = translate_batch(
        textos,
        API_KEY,
        target_language="Portuguese (Brazil)"
    )

    if sucesso:
        print("\n✅ Tradução completa!\n")
        print("RESULTADO:")
        print("-" * 80)
        for original, traduzido in zip(textos, traducoes):
            print(f"  {original:40} → {traduzido.strip()}")
        print("-" * 80)
    else:
        print(f"\n❌ Erro na tradução: {erro}")

    # Mostra status final da quota
    print(f"\n📊 Status final: {get_quota_stats_message()}\n")


def exemplo_2_estimativa_quota():
    """
    Exemplo 2: Estimativa de Quota antes de traduzir
    =================================================
    """
    print("\n" + "="*80)
    print("EXEMPLO 2: Estimativa de Quota")
    print("="*80 + "\n")

    # Simula um jogo com muitos textos
    total_textos = 5000

    print(f"🎮 Jogo possui {total_textos:,} textos para traduzir\n")

    # Estima quota necessária
    print_quota_estimate(total_textos, batch_size=200)

    # Pega estimativa programaticamente
    estimativa = estimate_translation_quota(total_textos, batch_size=200)

    if estimativa.get('can_complete_today'):
        print("✅ Você pode completar a tradução HOJE!")
    else:
        print(f"⚠️ Tradução será dividida em 2 dias:")
        print(f"   - Hoje: {estimativa['texts_today']:,} textos")
        print(f"   - Amanhã: {estimativa['texts_tomorrow']:,} textos")


def exemplo_3_fila_de_prioridades():
    """
    Exemplo 3: Sistema de Fila com Prioridades
    ===========================================
    """
    print("\n" + "="*80)
    print("EXEMPLO 3: Fila de Prioridades")
    print("="*80 + "\n")

    # Sua API key
    API_KEY = input("Digite sua API Key do Google Gemini: ").strip()

    if not API_KEY:
        print("❌ API Key não fornecida. Abortando.")
        return

    # Textos com diferentes prioridades
    textos_criticos = [
        "Error: Save file corrupted",
        "Warning: Low battery",
        "Confirm deletion?"
    ]

    textos_importantes = [
        "Quest: Find the lost sword",
        "Boss battle incoming!",
        "Level up!"
    ]

    textos_normais = [
        "Description of item",
        "Flavor text for NPC",
        "Background story"
    ]

    # Cria gerenciador de fila
    queue_mgr = BatchQueueManager(
        progress_file="fila_traducao.json",
        auto_save_interval=5
    )

    # Adiciona batches com prioridades
    print("📦 Adicionando textos à fila...\n")

    queue_mgr.add_batch(textos_criticos, Priority.CRITICAL, {'tipo': 'UI/Erros'})
    queue_mgr.add_batch(textos_importantes, Priority.HIGH, {'tipo': 'Gameplay'})
    queue_mgr.add_batch(textos_normais, Priority.NORMAL, {'tipo': 'Flavor'})

    print(f"✅ {queue_mgr.get_stats()['total_batches']} batches na fila")
    print(f"📊 Status: {queue_mgr.get_status_message()}\n")

    # Define função de tradução
    def traduzir_batch(textos: List[str]):
        traducoes, sucesso, erro = translate_batch(
            textos,
            API_KEY,
            target_language="Portuguese (Brazil)"
        )
        return traducoes, sucesso, erro

    # Callbacks
    def on_batch_complete(batch):
        print(f"✅ Batch #{batch.batch_id} completo ({batch.metadata.get('tipo', 'N/A')})")

    def on_batch_error(batch):
        print(f"❌ Batch #{batch.batch_id} falhou: {batch.error}")

    def on_queue_complete():
        print("\n🎉 FILA COMPLETA!")

    def on_quota_exceeded(batch):
        print(f"\n⛔ Quota excedida - salvando progresso...")
        print(f"   Batch #{batch.batch_id} será retomado amanhã")

    queue_mgr.on_batch_complete = on_batch_complete
    queue_mgr.on_batch_error = on_batch_error
    queue_mgr.on_queue_complete = on_queue_complete
    queue_mgr.on_quota_exceeded = on_quota_exceeded

    # Inicia processamento
    print("🚀 Iniciando processamento...\n")

    quota_mgr = get_quota_manager()
    queue_mgr.start_processing(traduzir_batch, quota_mgr)

    # Aguarda conclusão (ou Ctrl+C para parar)
    try:
        while queue_mgr.is_running:
            time.sleep(1)
            # Mostra progresso a cada 5 segundos
            if int(time.time()) % 5 == 0:
                print(f"\r{queue_mgr.get_status_message()}", end='', flush=True)

    except KeyboardInterrupt:
        print("\n\n⏸️ Interrompido pelo usuário")
        queue_mgr.stop()

    # Mostra resultados
    print("\n\n" + "="*80)
    print("RESULTADOS FINAIS")
    print("="*80)

    stats = queue_mgr.get_stats()
    print(f"Total de batches: {stats['total_batches']}")
    print(f"Processados: {stats['batches_processed']}")
    print(f"Falhas: {stats['batches_failed']}")
    print(f"Pendentes: {stats['batches_pending']}")
    print(f"Taxa de sucesso: {stats['success_rate']:.1f}%")
    print(f"Textos traduzidos: {stats['texts_translated']:,}/{stats['total_texts']:,}")

    # Pega todas as traduções
    todas_traducoes = queue_mgr.get_all_translations()

    print("\n📝 TRADUÇÕES:")
    print("-" * 80)
    for i, traducao in enumerate(todas_traducoes, 1):
        print(f"{i:3}. {traducao.strip()}")
    print("-" * 80)


def exemplo_4_traducao_massiva():
    """
    Exemplo 4: Tradução Massiva com Salvamento Automático
    ======================================================
    """
    print("\n" + "="*80)
    print("EXEMPLO 4: Tradução Massiva (Simulação)")
    print("="*80 + "\n")

    # Simula um jogo grande
    total_textos = 3000

    print(f"🎮 Simulando jogo com {total_textos:,} textos\n")

    # Mostra estimativa
    print_quota_estimate(total_textos, batch_size=200)

    estimativa = estimate_translation_quota(total_textos, batch_size=200)

    # Pergunta se quer continuar
    if not estimativa.get('can_complete_today'):
        print("\n⚠️ Esta tradução levará mais de 1 dia.")
        resposta = input("Deseja continuar? (s/n): ").strip().lower()

        if resposta != 's':
            print("❌ Tradução cancelada pelo usuário")
            return

    print("\n💡 DICA: Use o sistema de fila (Exemplo 3) para traduções grandes!")
    print("   - Salvamento automático de progresso")
    print("   - Pausa automática quando quota esgotar")
    print("   - Retoma automaticamente no dia seguinte")


def exemplo_5_monitoramento_quota():
    """
    Exemplo 5: Monitoramento de Quota em Tempo Real
    ================================================
    """
    print("\n" + "="*80)
    print("EXEMPLO 5: Monitoramento de Quota")
    print("="*80 + "\n")

    # Pega status da quota
    status = get_quota_status()

    if not status.get('available'):
        print("❌ Sistema de quota não disponível")
        return

    print("📊 STATUS ATUAL DA QUOTA\n")
    print("-" * 80)
    print(f"Requisições usadas hoje: {status['daily_used']}/{status['daily_limit']}")
    print(f"Requisições restantes: {status['daily_remaining']}")
    print(f"Uso: {status['usage_percent']:.1f}%")
    print(f"Reset em: {status['hours_until_reset']:.1f} horas")
    print(f"Taxa de sucesso (última hora): {status['success_rate_last_hour']:.0f}%")

    if status['last_request']:
        from datetime import datetime
        dt = datetime.fromisoformat(status['last_request'])
        print(f"Última requisição: {dt.strftime('%d/%m/%Y %H:%M:%S')}")
    else:
        print("Última requisição: Nunca")

    print("-" * 80)

    # Indicador visual
    percent = status['usage_percent']
    bar_length = 50
    filled = int(bar_length * percent / 100)
    bar = "█" * filled + "░" * (bar_length - filled)

    if percent < 50:
        color = "🟢"
    elif percent < 80:
        color = "🟡"
    else:
        color = "🔴"

    print(f"\n{color} [{bar}] {percent:.0f}%\n")


def menu_principal():
    """Menu principal de exemplos"""
    while True:
        print("\n" + "="*80)
        print("SISTEMA DE TRADUÇÃO COM GERENCIAMENTO DE QUOTA")
        print("="*80)
        print("\nEscolha um exemplo:")
        print("  1. Tradução Simples com Controle de Quota")
        print("  2. Estimativa de Quota antes de Traduzir")
        print("  3. Sistema de Fila com Prioridades (RECOMENDADO)")
        print("  4. Tradução Massiva (Simulação)")
        print("  5. Monitoramento de Quota em Tempo Real")
        print("  0. Sair")
        print("-" * 80)

        escolha = input("\nOpção: ").strip()

        if escolha == '1':
            exemplo_1_traducao_simples()
        elif escolha == '2':
            exemplo_2_estimativa_quota()
        elif escolha == '3':
            exemplo_3_fila_de_prioridades()
        elif escolha == '4':
            exemplo_4_traducao_massiva()
        elif escolha == '5':
            exemplo_5_monitoramento_quota()
        elif escolha == '0':
            print("\n👋 Até logo!\n")
            break
        else:
            print("\n❌ Opção inválida")

        input("\nPressione ENTER para continuar...")


if __name__ == "__main__":
    # Configura logging
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    print("""
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                                                                       ║
    ║   SISTEMA AVANÇADO DE TRADUÇÃO COM GERENCIAMENTO DE QUOTA            ║
    ║   ROM Translation Framework v5.3                                     ║
    ║                                                                       ║
    ║   Recursos:                                                          ║
    ║   ✅ Controle automático de quota (20 req/dia free tier)             ║
    ║   ✅ Tradução em lotes otimizada (até 200 textos/requisição)         ║
    ║   ✅ Fila de prioridades com salvamento automático                   ║
    ║   ✅ Pausa/retomada automática quando quota esgotar                  ║
    ║   ✅ Monitoramento em tempo real                                     ║
    ║                                                                       ║
    ╚═══════════════════════════════════════════════════════════════════════╝
    """)

    try:
        menu_principal()
    except KeyboardInterrupt:
        print("\n\n👋 Interrompido pelo usuário. Até logo!\n")
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
