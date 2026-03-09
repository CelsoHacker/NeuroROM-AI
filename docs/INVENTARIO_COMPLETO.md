# Inventário Completo do Projeto

Documento interno para organização do sistema. Não contém instruções de pirataria nem bypass de licença.
Nomes de jogos/ROMs foram omitidos por privacidade.

## Fluxo geral de uso (resumo)

- ROMs de console: Extração → Tradução → Reinserção (guias detalhados ficam no menu Ajuda da interface).
- Jogos de PC: Extração → Conversor específico → Tradução → Reinserção (ver MANUAL_JOGOS_PC.md).

## Pastas principais (raiz)

- `.git/` — Metadados do Git.
- `_patch_ptr/` — Pasta reservada para patches de ponteiros.
- `config/` — Configurações globais (glossário, free space).
- `core/` — Núcleo de extração/tradução (módulos principais).
- `data/` — Dados auxiliares e reports.
- `docs/` — Documentação complementar.
- `dummy_pc_game/` — Jogo PC dummy para testes.
- `examples/` — Pasta do projeto.
- `export/` — Geradores de export/proof/report.
- `extraction/` — Analisadores/integrações de compressão.
- `fonts/` — Fontes usadas no projeto.
- `i18n/` — Traduções da interface (JSON).
- `interface/` — Aplicação PyQt6 (GUI) e módulos de UI.
- `internal/` — Materiais internos.
- `logs/` — Logs de execução.
- `orchestrator/` — Orquestrador do pipeline + políticas de qualidade.
- `plugins/` — Plugins por console/plataforma.
- `profiles/` — Perfis específicos (ex.: SMS).
- `ROMs/` — ROMs de trabalho do usuário.
- `rtce_core/` — Runtime Text Capture Engine (RTCE).
- `runtime/` — Captura runtime (emulador/harvester).
- `security/` — Módulos de licença/segurança.
- `tests/` — Testes automatizados.
- `tools/` — Scripts utilitários e manutenção.
- `unification/` — Unificação/deduplicação e validações de reinserção.
- `universal_kit/` — Toolkit de baixo nível (ponteiros, compressão, tiles).
- `utils/` — Utilitários gerais.

## Arquivos na raiz

- `.eula_accepted` — Flag de aceite da EULA/licença.
- `.gitignore` — Regras do Git para ignorar arquivos.
- `.pylintrc` — Configuração do linter pylint.
- `0.6` — Arquivo auxiliar.
- `ADVANCED_EXTRACTOR_REPORT.md` — 📊 RELATÓRIO: ADVANCED ROM EXTRACTOR v2.0
- `AGENTS.md` — Preferências de linguagem
- `ANTES_E_DEPOIS.md` — 🔄 ANTES E DEPOIS - Implementação do Manual de ROM Hacking
- `apply_neutral_patch.ps1` — Script PowerShell utilitário.
- `audit_mapping_items_sms.py` — (sem docstring/comentário de cabeçalho)
- `AUDITORIA_SMS.md` — Auditoria rapida - SMS (Master System)
- `config.json` — Configuração simples (tema/idioma da UI).
- `CONTRAST_THEME_SYSTEM.md` — 🎨 SISTEMA DE TEMAS COM CONTRASTE INTELIGENTE
- `CORREÇÃO_CASE_INSENSITIVE.md` — 🔧 CORREÇÃO TIER 1 ADVANCED - BUSCA CASE-INSENSITIVE
- `CORREÇÕES_UI_ANO_IMPLEMENTADAS.md` — ✅ CORREÇÕES IMPLEMENTADAS - UI SCROLL + ANO PRIORIZADO
- `DEEP_FINGERPRINTING_RAIO_X.md` — 🔬 DEEP FINGERPRINTING - RAIO-X FORENSE
- `DIFF_ATUAL.txt` — diff --git a/.claude/settings.local.json b/.claude/settings.local.json
- `ENGINE_RETRO_A_FINAL.md` — ✅ ENGINE RETRO-A - IMPLEMENTAÇÃO COMPLETA
- `ENTREGA_DEEP_FINGERPRINTING.txt` — ================================================================================
- `ENTREGA_FINAL_TIER1_ADVANCED.txt` — ================================================================================
- `estrutura.txt` — Listagem de caminhos de pasta
- `export_translate_diagnostics.py` — (sem docstring/comentário de cabeçalho)
- `FAQ_CLIENTES.md` — ❓ FAQ - Perguntas Frequentes dos Clientes
- `FAST_SCAN_MODE_IMPLEMENTATION.md` — ⚡ MODO SCAN RÁPIDO - Implementação Completa
- `fix_autofind_rom_from_txt.py` — !/usr/bin/env python3
- `fix_projectconfig_extraction_dir.py` — !/usr/bin/env python3
- `fonts_windows.txt` — Arial
- `gemini_quota.json` — Controle local de quota do Gemini.
- `GUIA_PC_GAMES_ATUALIZADO.md` — 🎯 GUIA: Tradução de Jogos de PC - ATUALIZADO 2026
- `GUIA_VISUAL_RAPIDO.md` — 🎨 GUIA VISUAL RÁPIDO - ROMs vs Jogos de PC
- `i18n_audit_report.txt` — Referência: pt (305 chaves)
- `i18n_missing_keys_in_code.txt` — (sem conteúdo)
- `IMPLEMENTACAO_MANUAL_COMPLETA.txt` — ╔══════════════════════════════════════════════════════════════════════════════╗
- `INDICE_DOCUMENTACAO.md` — 📚 ÍNDICE COMPLETO DA DOCUMENTAÇÃO
- `INICIAR_AQUI.bat` — Atalho/launcher principal no Windows.
- `INICIAR_OLLAMA.bat` — Atalho para iniciar o Ollama.
- `LICENSE` — Arquivo de licença do projeto.
- `license.key` — Chave/licença local do sistema.
- `LZ2_IMPLEMENTATION_REPORT.md` — 🎮 IMPLEMENTAÇÃO: LZ2 DECOMPRESSION + SNES 4BPP
- `main.py` — Entry point da aplicação (GUI).
- `make_needs_retranslate.py` — (sem docstring/comentário de cabeçalho)
- `MANUAL_COMPLETO_NEUROROM_AI.md` — 📘 MANUAL COMPLETO - NEUROROM AI v5.3
- `MANUAL_JOGOS_PC.md` — 💻 MANUAL: Como Traduzir Jogos de PC
- `MELHORIAS_DEEP_FINGERPRINTING.md` — 🔧 MELHORIAS DO DEEP FINGERPRINTING
- `MODERN_TEXTURE_SUPPORT.md` — 🎨 MODERN TEXTURE SUPPORT - Documentação Completa
- `MODERN_TEXTURES_IMPLEMENTATION_SUMMARY.md` — ✅ MODERN TEXTURE SUPPORT - Resumo da Implementação
- `patch_sms_extracao.diff` — Arquivo de patch/diff.
- `patch_translate_diagnostics.py` — (sem docstring/comentário de cabeçalho)
- `POPUP_GUIA_PC_2026.md` — 🎯 IMPORTANTE: Jogos de PC - ATUALIZAÇÃO 2026!
- `PRICING_ANALYSIS.md` — 💰 ANÁLISE DE PRECIFICAÇÃO - NEUROROM AI v5.3
- `README.md` — NEUROROM AI V6.0 PRO SUITE
- `REFACTORING_GRAPHICS_LAB.md` — 🔧 REFATORAÇÃO: GRAPHICS LAB MODULE
- `REFINAMENTO_FINAL_UI_ANO.md` — ✅ REFINAMENTO FINAL - UI MAIOR + BARRA PRETA + ANO CORRETO
- `RELATORIO_AUDITORIA.md` — RELATÓRIO DE AUDITORIA — ROM Translation Framework
- `REMIX_VISUAL_GUIDE.md` — 🎨 REMIX VISUAL - ENGINE RETRO-A v5.3
- `requirements-dev.txt` — Dependências de desenvolvimento.
- `requirements.txt` — Dependências de runtime (Python).
- `ROM_HACKING_MANUAL_IMPLEMENTATION.md` — ✅ ROM HACKING MANUAL - IMPLEMENTAÇÃO COMPLETA
- `rom_triage.py` — rom_triage.py
- `romtxt_pipeline_v1.py` — romtxt_pipeline_v1.py
- `RTCE_GUIA_RAPIDO.md` — 🔥 Guia Rápido - Runtime Text Capture (RTCE)
- `ARQUIVO_JOGO_OCULTO.md` — Relatório/arquivo relacionado a jogo (nome omitido).
- `ARQUIVO_JOGO_OCULTO.md` — Relatório/arquivo relacionado a jogo (nome omitido).
- `triage_min.py` — (sem docstring/comentário de cabeçalho)
- `UI_FIXES_SUMMARY.md` — ✅ CORREÇÕES DA UI - PyQt6
- `VISUAL_FIXES_APPLIED.md` — ✅ CORREÇÕES VISUAIS APLICADAS - NEUROROM AI v5.3

## Inventário por pasta

### `core/`

- `__init__.py` — ROM Translation Framework - Core Module
- `__pycache__/` — pasta
- `advanced_encoding_detector.py` — ADVANCED ENCODING DETECTOR - Detecção Avançada + Charsets Custom
- `advanced_extractor.py` — Advanced ROM Extractor - Sistema de Extração Inteligente
- `AUTO_LEARNING_ENGINE_NEUTRAL.py` — AUTO_LEARNING_ENGINE v1.0
- `AUTO_LEARNING_EXTRACTOR_NEUTRAL.py` — AUTO_LEARNING_EXTRACTOR.py - Sistema que APRENDE sozinho a extrair texto de QUALQUER jogo
- `auto_neural_graphics.py` — UPDATED FUNCTION FOR: interface_tradutor_final.py
- `batch_queue_manager.py` — Sistema de Fila Inteligente para Tradução em Lotes
- `charset_inference.py` — CHARSET INFERENCE - Descoberta Automática de Tabelas de Caracteres
- `compression_detector.py` — COMPRESSION DETECTOR - Detecção Heurística de Algoritmos de Compressão
- `deep_scavenger_engine.py` — DEEP SCAVENGER ENGINE - Varredura de Lacunas V7.0
- `encoding_detector.py` — ENCODING DETECTOR - Detecção e Preservação de Encoding de Arquivos
- `engine_detector.py` — Engine Detector - Detecta automaticamente o tipo de jogo/ROM
- `engine_fingerprinting.py` — ENGINE FINGERPRINTING - Detecção Automática de Game Engines
- `fast_clean_extractor.py` — FAST CLEAN EXTRACTOR - Extrator Rápido com Filtro Inteligente
- `file_format_detector.py` — FILE FORMAT DETECTOR - Detecção Automática de Estrutura de Arquivos
- `forensic_scanner.py` — SISTEMA FORENSE CORRIGIDO - ASSINATURAS REAIS
- `free_space_allocator.py` — FREE SPACE ALLOCATOR - Gerenciador de Alocacao Deterministico
- `gemini_translator.py` — Gemini Online Translator - Mixin Module
- `glossary_manager.py` — Glossary Manager - Sistema de Glossários Personalizados
- `graphics_worker.py` — Graphics Worker - Tile Viewer & Forensic Tool
- `hybrid_extractor.py` — HYBRID EXTRACTOR - Unificação V9 + Fast Clean
- `hybrid_translator.py` — Sistema Híbrido de Tradução com Fallback Automático
- `linguistic_qa.py` — LINGUISTIC QA - Auditoria Linguistica Automatica
- `MASTER_SYSTEM_UNIVERSAL_EXTRACTOR_FIXED_NEUTRAL.py` — BINARY DATA PROCESSOR - Universal SMS Extractor
- `nes_extractor_pro.py` — nes_extractor_pro.py
- `nes_injector_pro.py` — nes_injector_pro.py
- `parallel_translator.py` — TRADUTOR PARALELO ULTRA-OTIMIZADO v4.0 - DEPLOY CRÍTICO
- `pc_game_scanner.py` — PC GAME SCANNER - Varredura Automática de Pastas de Jogos
- `pc_pipeline.py` — PC PIPELINE - Pipeline Completo de Tradução para Jogos de PC
- `pc_safe_reinserter.py` — PC SAFE REINSERTER - Reinserção Segura de Traduções em Jogos de PC
- `pc_text_extractor.py` — PC TEXT EXTRACTOR - Extração Universal de Textos de Jogos de PC
- `pc_translation_cache.py` — PC TRANSLATION CACHE - Cache de Traduções para Economia de API
- `pointer_scanner.py` — POINTER SCANNER - Detecção Automática de Tabelas de Ponteiros
- `quota_manager.py` — Sistema Avançado de Gerenciamento de Quota para Google Gemini API
- `reinsertion_rules.py` — REINSERTION RULES - Regras de Reinserção V1
- `relative_pattern_engine.py` — RELATIVE PATTERN ENGINE - Quebrador de Tabela Matemático V7.0
- `retro8_bank_tools.py` — retro8_bank_tools.py
- `rom_analyzer.py` — ROM ANALYZER - Detecção Automática de Estrutura de ROM
- `rom_detector.py` — ROM Detector - Sistema Profissional de Detecção de ROMs
- `rom_text_validator.py` — ROM Text Validator - Detector de Texto Traduzível
- `rom_translation_prompts.py` — ROM Translation Prompts - Prompts Técnicos sem Alucinação
- `safe_reinserter.py` — SAFE REINSERTER - Reinserção Segura Universal
- `security_manager.py` — Security Manager - License Validation & Anti-Piracy
- `sega_extractor.py` — Sega Extractor - Master System & Mega Drive/Genesis
- `sega_extractor_PATCHED.py` — Sega Extractor - Master System & Mega Drive/Genesis
- `sega_reinserter.py` — NeuroROM AI - Sega Master System Reinserter
- `sms_injector_pro.py` — sms_injector_pro.py
- `sms_patcher.py` — !/usr/bin/env python3
- `sms_pointer_transform.py` — SMS POINTER TRANSFORM - Deterministic Pointer-to-Offset Conversion
- `sms_pro_extractor.py` — SMS PRO EXTRACTOR v1.0
- `sms_relocation_v1.py` — SMS RELOCATION V1 - Text Reinsertion with Pointer Relocation
- `string_classifier.py` — STRING CLASSIFIER - Classificação de Strings (Runtime vs Estáticas)
- `super_text_filter.py` — SUPER TEXT FILTER - Filtro Ultra-Agressivo de Lixo
- `tbl_loader.py` — TBL LOADER - Carregador de Tabelas Customizadas
- `technical_validator.py` — TECHNICAL VALIDATOR - Validacao Tecnica de Traducoes
- `text_scanner.py` — TEXT SCANNER - Localizador de Strings de Texto em ROMs
- `tilemap_extractor.py` — TILEMAP EXTRACTOR - Guided UI/HUD Label Extraction
- `translation_engine.py` — -*- coding: utf-8 -*-
- `translation_optimizer.py` — Translation Optimizer - Redução Agressiva de Workload
- `TRANSLATION_PREP_LAYER.py` — TRANSLATION PREP LAYER v2.1
- `translator_engine.py` — TRADUTOR UNIVERSAL v5.8 - TITAN EDITION (CLAUDE + GEMINI FIX)
- `ultimate_extractor_v7.py` — ULTIMATE EXTRACTOR V7.0 - ULTIMATE EXTRACTION SUITE
- `ultimate_extractor_v8.py` — ULTIMATE EXTRACTOR V8.0 - DTE/MTE COMPRESSION SOLVER
- `ultimate_extractor_v9.py` — ULTIMATE EXTRACTOR V 9.8 [FORENSIC KERNEL] - KERNEL CORE ENGINE
- `ultimate_text_extractor.py` — ULTIMATE TEXT EXTRACTOR - Extrator Definitivo com Tabela Customizada
- `universal_pipeline.py` — UNIVERSAL PIPELINE - Orquestrador do Processo Completo de Tradução

### `interface/`

- `__init__.py` — ROM Translation Framework - Interface Module
- `__pycache__/` — pasta
- `buscador_inteligente.py` — (sem docstring/comentário de cabeçalho)
- `config.json` — Configuração simples (tema/idioma da UI).
- `extraction_worker_elite.py` — -*- coding: utf-8 -*-
- `forensic_crc_db.json` — Base local de CRCs (forense).
- `forensic_engine_upgrade.py` — FORENSIC ENGINE UPGRADE - TIER 1 DETECTION SYSTEM
- `forensic_ui_integration.py` — FORENSIC UI INTEGRATION - MÉTODO ATUALIZADO
- `gemini_api.py` — GEMINI API TRANSLATOR - ROM Translation Framework v5.3
- `generic_pc_extractor.py` — Generic PC Game Text Extractor - Windows Platform
- `generic_snes_extractor.py` — Generic ROM Text Extractor - SNES Platform
- `graphics_worker.py` — Graphics Worker - Tile Viewer & Forensic Tool
- `gui_tabs/` — pasta
- `gui_translator.py` — TRADUTOR UNIVERSAL DE ROMs - INTERFACE GRÁFICA v4.2 - COMMERCIAL EDITION
- `interface_tradutor_final.py` — (sem docstring/comentário de cabeçalho)
- `interface_tradutor_final_NEUTRAL.py` — (sem docstring/comentário de cabeçalho)
- `make_translated_jsonl_from_txt.py` — (sem docstring/comentário de cabeçalho)
- `memory_mapper.py` — MEMORY MAPPER - Arquitetura Universal de Mapeamento de Memória
- `minimal_theme.py` — MINIMAL CSS - APENAS LAYOUT, SEM CORES FIXAS
- `pc_game_reinserter.py` — PC GAME REINSERTER - Módulo de Reinserção para Jogos PC (.exe)
- `pointer_scanner.py` — POINTER SCANNER - Sistema Avançado de Detecção de Ponteiros
- `premium_theme.py` — PREMIUM VISUAL THEME FOR NEUROROM AI
- `premium_theme_fixed.py` — PREMIUM THEME FIXED - Respeita escolha de tema do usuário
- `quota_monitor_widget.py` — Widget de Monitoramento de Quota para Google Gemini API
- `salvar_info_jogo.json` — Arquivo de dados/configuração em JSON.
- `smart_theme.py` — SMART THEME SYSTEM - Bordas com Contraste Dinâmico
- `translator_config.json` — Configuração salva da interface.

### `interface/gui_tabs/`

- `__init__.py` — GUI Tabs Package
- `__pycache__/` — pasta
- `extraction_tab.py` — Aba de extração e utilidades de análise para o módulo GUI.
- `graphic_lab.py` — -*- coding: utf-8 -*-
- `reinsertion_tab.py` — -*- coding: utf-8 -*-

### `plugins/`

- `__init__.py` — PLUGINS - Multi-Console ROM Translation Plugin System
- `base_plugin.py` — BASE PLUGIN - Abstract Base Class for Console Plugins
- `gba_plugin.py` — GBA PLUGIN - Game Boy Advance
- `md_plugin_NEUTRAL.py` — MD PLUGIN - Sega Mega Drive / Genesis
- `n64_plugin.py` — N64 PLUGIN - Nintendo 64
- `nes_plugin_NEUTRAL.py` — NES PLUGIN - Nintendo Entertainment System / Famicom
- `plugin_registry.py` — PLUGIN REGISTRY - Auto-Discovery and Management of Console Plugins
- `ps1_plugin.py` — PS1 PLUGIN - PlayStation 1
- `sms_plugin_NEUTRAL.py` — SMS PLUGIN - Sega Master System
- `snes_plugin.py` — SNES PLUGIN - Super Nintendo Entertainment System

### `orchestrator/`

- `__init__.py` — ORCHESTRATOR MODULE - Main Pipeline Controller
- `plugin_orchestrator.py` — PLUGIN ORCHESTRATOR - Main Pipeline Controller
- `policy_enforcer.py` — POLICY ENFORCER - Extraction Quality Policies

### `unification/`

- `__init__.py` — UNIFICATION - Merge Static and Runtime Text Extraction Results
- `reinsertion_validator.py` — REINSERTION VALIDATOR - Validates Safe Text Reinsertion
- `similarity_matcher.py` — SIMILARITY MATCHER - Fuzzy Text Matching
- `text_unifier.py` — TEXT UNIFIER - Merges Static and Runtime Text Items

### `universal_kit/`

- `__init__.py` — UNIVERSAL KIT - Shared Tools for All Console Plugins
- `auto_char_table_solver.py` — AUTO CHAR TABLE SOLVER - Automatic Character Table Discovery
- `compression_hunter.py` — COMPRESSION HUNTER - Detection and Tracking of Compressed Data
- `container_extractor.py` — CONTAINER EXTRACTOR - Archive and Filesystem Extraction
- `endian_pointer_hunter.py` — ENDIAN POINTER HUNTER - Universal Pointer Detection with Plugin Support
- `multi_decompress.py` — MULTI DECOMPRESS - Actual Decompression Engines for ROM Data
- `script_opcode_miner.py` — SCRIPT OPCODE MINER - Script Command Detection for ROM Text
- `tile_text_engine.py` — TILE TEXT ENGINE - Tile-to-Text Conversion for Retro Consoles

### `export/`

- `__init__.py` — EXPORT MODULE - Neutral Export System
- `neutral_exporter.py` — NEUTRAL EXPORTER - CRC32-Based Export System
- `proof_generator.py` — PROOF GENERATOR - SHA256 Verification Proof
- `report_generator.py` — REPORT GENERATOR - Human-Readable Extraction Report

### `tools/`

- `953F42E1_reinsertion_mapping.top1.safe.json` — Arquivo de dados/configuração em JSON.
- `__init__.py` — ROM Translation Framework - Tools Module
- `analyze_jsonl_reinsertion_safe.py` — (sem docstring/comentário de cabeçalho)
- `auto_tbl_sms_from_rom.py` — Inferência automática de TBL (Master System / tile text) sem emulador.
- `clean_binary_garbage.py` — Clean Binary Garbage - Remove lixo binário de arquivos extraídos
- `compression_table_extractor.py` — CompPointTable Extractor Tool
- `dev_scripts/` — pasta
- `diff_rom_ranges.py` — tools/diff_rom_ranges.py
- `entropy_analyzer.py` — ENTROPY ANALYZER - Raio-X de ROMs através de Análise de Entropia
- `filter_mapping_blocks.py` — tools/filter_mapping_blocks.py
- `filter_mapping_by_ranges.py` — filter_mapping_by_ranges.py
- `find_rom_by_crc32.py` — tools/find_rom_by_crc32.py
- `fix_translated_jsonl_for_reinsertion.py` — Corrige/normaliza JSONL traduzido para reinsercao:
- `generate_manuals.py` — NeuroROM AI - Professional Manual Generator (PDF)
- `make_preview_from_jsonl.ps1` — Script PowerShell utilitário.
- `make_translated_jsonl_from_txt.py` — (sem docstring/comentário de cabeçalho)
- `reinsert_sms_cli.py` — CLI para reinserção segura em ROMs SMS usando o SegaReinserter.
- `relative_searcher.py` — RELATIVE SEARCHER - Sistema de Busca Textual de Alta Performance
- `rom_triage.py` — rom_triage.py
- `romtxt_pipeline_v1.py` — romtxt_pipeline_v1.py
- `search_ascii_words.py` — Search ASCII Words in ROM (SMS V1)
- `sms_cleanup.py` — NeuroROM SMS cleanup helper.
- `test_jsonl_loader.py` — Mini-teste manual para validar loader JSONL do sega_reinserter.
- `test_sms_reinsert_one.py` — (sem docstring/comentário de cabeçalho)

### `tools/dev_scripts/`

- `cleanup_project.ps1` — Script PowerShell utilitário.
- `create_test_file.py` — Create a smaller test file from main.bin
- `exemplo_traducao_com_quota.py` — EXEMPLO COMPLETO - Sistema de Tradução com Gerenciamento de Quota
- `otimizar_arquivo_traducao.py` — Otimizador de Arquivo para Tradução
- `verificar_sistema.py` — 🔍 Verificador do Sistema - ROM Translation Framework v5.3

### `utils/`

- `__init__.py` — ROM Translation Framework - Utils Module
- `cuda_optimizer.py` — FIX CUDA ERRORS - Diagnóstico e Correção Definitiva
- `license_guard.py` — -*- coding: utf-8 -*-
- `rom_io.py` — Utilitários de I/O para ROM: backup incremental, escrita atômica e checksums.
- `system_diagnostics.py` — DIAGNÓSTICO COMPLETO - OLLAMA + CUDA + HARDWARE

### `runtime/`

- `__init__.py` — RUNTIME - Emulator-Based Text Capture Mode
- `auto_explorer.py` — AUTO EXPLORER - Deterministic Game Exploration Bot
- `emulator_runtime_host.py` — EMULATOR RUNTIME HOST - Libretro-Based Emulation Backend
- `origin_tracker.py` — ORIGIN TRACKER - Maps Runtime Text to Static ROM Origins
- `runtime_text_harvester.py` — RUNTIME TEXT HARVESTER - Extracts Text from Running Emulator
- `screen_change_detector.py` — SCREEN CHANGE DETECTOR - Detects Game Screen Transitions

### `rtce_core/`

- `__init__.py` — RUNTIME TEXT CAPTURE ENGINE (RTCE)
- `__pycache__/` — pasta
- `memory_scanner.py` — Memory Scanner - Leitura externa de memória de processos
- `orchestrator.py` — Text Capture Orchestrator - Orquestra OCR + RTCE
- `platform_profiles.py` — Platform Profiles - Perfis configuráveis para diferentes consoles/sistemas
- `README.md` — 🔥 Runtime Text Capture Engine (RTCE)
- `rtce_engine.py` — RTCE Engine - Motor principal de captura de texto runtime
- `runtime_v6_intelligent_pipeline.py` — ╔══════════════════════════════════════════════════════════════════════════════╗
- `text_heuristics.py` — -*- coding: utf-8 -*-

### `extraction/`

- `__init__.py` — ROM Translation Framework - Extraction Module
- `compression_analyzer.py` — Compression Analyzer V1.0
- `v8_compression_integration.py` — V8.0 + Compression Analyzer Integration

### `docs/`

- `archive/` — pasta
- `FORENSIC_SCANNER_GUIDE.md` — 🔬 Sistema Forense Corrigido - Guia Completo
- `GLOSSARY_INTEGRATION_GUIDE.md` — 📚 Guia de Integração de Glossários
- `INVENTARIO_COMPLETO.md` — Inventário Completo do Projeto
- `manuals/` — pasta

### `data/`

- `mapa_ponteiros.json` — Arquivo de dados/configuração em JSON.
- `reports/` — pasta

### `config/`

- `free_space_profiles.json` — Arquivo de dados/configuração em JSON.
- `translation_glossary.json` — Arquivo de dados/configuração em JSON.

### `i18n/`

- `ar.json` — Arquivo de dados/configuração em JSON.
- `de.json` — Arquivo de dados/configuração em JSON.
- `en.json` — Arquivo de dados/configuração em JSON.
- `es.json` — Arquivo de dados/configuração em JSON.
- `fr.json` — Arquivo de dados/configuração em JSON.
- `hi.json` — Arquivo de dados/configuração em JSON.
- `it.json` — Arquivo de dados/configuração em JSON.
- `ja.json` — Arquivo de dados/configuração em JSON.
- `ko.json` — Arquivo de dados/configuração em JSON.
- `nl.json` — Arquivo de dados/configuração em JSON.
- `pl.json` — Arquivo de dados/configuração em JSON.
- `pt.json` — Arquivo de dados/configuração em JSON.
- `ru.json` — Arquivo de dados/configuração em JSON.
- `summary.txt` — Arquivos JSON de tradução criados:
- `tr.json` — Arquivo de dados/configuração em JSON.
- `VALIDATION_CHECKLIST.md` — ✅ Checklist de Validação i18n - ROM Translation Framework
- `zh.json` — Arquivo de dados/configuração em JSON.

### `profiles/`

- `sms/` — pasta

### `profiles/sms/`

- `953F42E1.json` — Arquivo de dados/configuração em JSON.

### `tests/`

- `test_sega_reinserter_hardening.py` — (sem docstring/comentário de cabeçalho)
- `test_sms_e2e_one_item.py` — TEST SMS E2E ONE ITEM - End-to-End Single Item Reinsertion
- `test_sms_pointer_transform.py` — TEST SMS POINTER TRANSFORM - Automated Validation
- `test_sms_relocation_v2.py` — TEST SMS RELOCATION V1 - Automated Validation

### `fonts/`

- `NotoSans-Regular.ttf` — Arquivo de fonte.
- `NotoSansCJKjp-Regular.otf` — Arquivo de fonte.
- `NotoSansCJKjp-Regular.ttf` — Arquivo de fonte.
- `NotoSansCJKkr-Regular.otf` — Arquivo de fonte.
- `NotoSansCJKkr-Regular.ttf` — Arquivo de fonte.
- `NotoSansCJKsc-Regular.otf` — Arquivo de fonte.
- `NotoSansCJKsc-Regular.ttf` — Arquivo de fonte.

### `dummy_pc_game/`

- `config/` — pasta
- `extracted_texts_pc.json` — Arquivo de dados/configuração em JSON.
- `localization/` — pasta
- `scripts/` — pasta
- `test_translations.json` — Arquivo de dados/configuração em JSON.
- `translation_output/` — pasta

### `internal/`

- `MARKETING_STRATEGY.md` — 💰 Marketing Strategy - Gumroad Launch

### `ROMs/`

- `Master System/` — pasta
- `Playstation 1/` — pasta
- `Super Nintedo/` — pasta

### `security/`

- `__init__.py` — ROM Translation Framework - Security Module
- `license_guard.py` — -*- coding: utf-8 -*-

## Limpeza segura (higiene)

Você pode apagar sem afetar o funcionamento:

- `**/__pycache__/`, `**/*.pyc`
- `.pytest_cache/`, `.ruff_cache/`
- `interface/tempCodeRunnerFile.py`
- `tests/output/` (saída de testes)
- `*.bak` (backups antigos)

Arquivos que não devem ser removidos:

- `main.py`, `core/`, `interface/`, `plugins/`, `orchestrator/`, `universal_kit/`, `unification/`, `runtime/`, `rtce_core/`
- `requirements*.txt`, `LICENSE`, `license.key`, `config.json`, `i18n/`, `config/`
