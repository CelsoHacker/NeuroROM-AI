# -*- coding: utf-8 -*-
"""
================================================================================
TRADUTOR UNIVERSAL DE ROMs v5.3 - STABLE & THREAD-SAFE
Desenvolvido por: Celso (Programador Solo)
Arquitetura: Multi-plataforma + Multi-idioma + Auto-detecção
================================================================================
v5.3 FIXED:
✓ FIXED: QWidget::repaint and QBackingStore::endPaint recursion errors
✓ FIXED: UI updates from background threads (ReinsertionWorker)
✓ IMPLEMENTED: Full QThread + pyqtSignal architecture for all tasks
✓ IMPROVED: Stability and signal/slot connections
✓ REFACTOR: Clear variable separation for ROM, Extracted, Optimized, Translated
✓ FIXED: Gemini API updated to gemini-2.5-flash with safety settings
✓ FIXED: Optimization moved to separate thread (no UI freezing)
✓ FIXED: API Key obfuscation with base64 encoding
✓ FIXED: Removed duplicate Gemini code, now uses gemini_api.py exclusively
================================================================================
"""

import sys
import os
import json
import subprocess
import re
import shutil
import traceback
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QFileDialog, QComboBox,
    QProgressBar, QGroupBox, QGridLayout, QTabWidget,
    QMessageBox, QLineEdit, QSpinBox, QCheckBox, QFormLayout, QDialog,
    QScrollArea, QFrame, QGraphicsView, QGraphicsScene, QStyle
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor, QPalette, QColor

# Importa o módulo centralizado de tradução Gemini
import gemini_api

# COMMERCIAL: Import Security Manager
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from core.security_manager import SecurityManager

# --- WORKERS (THREADS SEGURAS) ---

class ProcessThread(QThread):
    """Worker para executar scripts externos em subprocesso, seguro para a GUI."""
    progress = pyqtSignal(str)
    progress_percent = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, command: list):
        super().__init__()
        self.command = command
        self.process = None

    def run(self):
        try:
            creation_flags = 0
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NO_WINDOW

            self.process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=creation_flags
            )

            percent_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*%')

            for line in self.process.stdout:
                line = line.strip()
                if line:
                    self.progress.emit(line)
                    match = percent_pattern.search(line)
                    if match:
                        try:
                            self.progress_percent.emit(int(float(match.group(1))))
                        except:
                            pass

            self.process.wait()

            success = self.process.returncode == 0
            if success:
                self.finished.emit(True, "Operation completed successfully")
            else:
                stderr = self.process.stderr.read().strip()
                self.finished.emit(False, f"Error code {self.process.returncode}: {stderr}")
        except Exception as e:
            self.finished.emit(False, f"Exception: {str(e)}")

    def terminate(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                try:
                    self.process.kill()
                except:
                    pass
        super().terminate()


class OptimizationWorker(QThread):
    """Worker dedicado para otimização de dados em thread separada."""
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)  # Retorna caminho do arquivo otimizado
    error_signal = pyqtSignal(str)

    def __init__(self, input_file: str):
        super().__init__()
        self.input_file = input_file
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            self.status_signal.emit("Analisando arquivo...")
            self.progress_signal.emit(10)

            with open(self.input_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            total_original = len(lines)
            self.log_signal.emit(f"📊 Linhas originais: {total_original:,}")
            self.progress_signal.emit(20)

            # FASE 1: LIMPEZA COM PARSING DO FORMATO [0xENDERECO] TextoReal
            self.status_signal.emit("Parsing formato [0xENDERECO]...")
            cleaned_texts = []
            seen_texts = set()  # Para remover duplicatas

            stats = {
                'comments': 0,
                'no_bracket': 0,
                'too_short': 0,
                'no_vowels': 0,
                'has_code_chars': 0,
                'duplicates': 0,
                'kept': 0
            }

            for i, line in enumerate(lines):
                if not self._is_running:
                    self.error_signal.emit("Operação cancelada pelo usuário")
                    return

                original_line = line.strip()

                # FILTRO 1: IGNORAR COMENTÁRIOS
                if original_line.startswith('#'):
                    stats['comments'] += 1
                    continue

                # FILTRO 2: SEPARAR O LIXO - Pegar só o texto depois do ']'
                if ']' not in original_line:
                    stats['no_bracket'] += 1
                    continue

                # Divide no primeiro ']' e pega a parte depois
                parts = original_line.split(']', 1)
                if len(parts) < 2:
                    stats['no_bracket'] += 1
                    continue

                # Texto limpo (sem o prefixo [0x...])
                clean_text = parts[1].strip()

                # FILTRO 3: TAMANHO MÍNIMO (4 caracteres)
                if len(clean_text) < 4:
                    stats['too_short'] += 1
                    continue

                # FILTRO 4: VERIFICAR VOGAIS (se não tiver vogal, não é texto real)
                if not re.search(r'[aeiouAEIOU]', clean_text):
                    stats['no_vowels'] += 1
                    continue

                # FILTRO 5: REJEITAR CÓDIGOS (linhas com {, }, \, /)
                if any(char in clean_text for char in ['{', '}', '\\', '/']):
                    stats['has_code_chars'] += 1
                    continue

                # FILTRO 6: DUPLICATAS
                clean_text_lower = clean_text.lower()
                if clean_text_lower in seen_texts:
                    stats['duplicates'] += 1
                    continue

                # APROVADO! Adiciona apenas o texto limpo
                seen_texts.add(clean_text_lower)
                cleaned_texts.append(clean_text)
                stats['kept'] += 1

                # Atualização de progresso
                if i % 1000 == 0:
                    progress = 20 + int((i / total_original) * 60)
                    self.progress_signal.emit(progress)

            self.progress_signal.emit(80)
            self.status_signal.emit("Salvando arquivo otimizado...")

            # Salvar arquivo otimizado (SEM os prefixos [0x...])
            output_file = self.input_file.replace("_extracted_texts.txt", "_optimized.txt")
            if output_file == self.input_file:
                output_file = str(Path(self.input_file).with_suffix('')) + "_optimized.txt"

            with open(output_file, 'w', encoding='utf-8', newline='\n') as f:
                f.write('\n'.join(cleaned_texts))

            total_removed = total_original - stats['kept']

            self.progress_signal.emit(100)
            self.status_signal.emit("Concluído!")

            # Relatório detalhado
            self.log_signal.emit("=" * 60)
            self.log_signal.emit("🔥 OTIMIZAÇÃO COM PARSING [0xENDERECO] CONCLUÍDA")
            self.log_signal.emit("=" * 60)
            self.log_signal.emit(f"📊 Linhas originais: {total_original:,}")
            self.log_signal.emit(f"✅ Textos mantidos: {stats['kept']:,}")
            self.log_signal.emit(f"🗑️  Linhas removidas: {total_removed:,}")
            self.log_signal.emit("")
            self.log_signal.emit("Detalhamento das remoções:")
            self.log_signal.emit(f"  • Comentários (#): {stats['comments']:,}")
            self.log_signal.emit(f"  • Sem colchete ']': {stats['no_bracket']:,}")
            self.log_signal.emit(f"  • Muito curto (< 4 chars): {stats['too_short']:,}")
            self.log_signal.emit(f"  • Sem vogais: {stats['no_vowels']:,}")
            self.log_signal.emit(f"  • Caracteres de código ({{}}\\/) : {stats['has_code_chars']:,}")
            self.log_signal.emit(f"  • Duplicatas: {stats['duplicates']:,}")
            self.log_signal.emit("")
            self.log_signal.emit(f"💾 Arquivo salvo (SOMENTE TEXTOS LIMPOS): {os.path.basename(output_file)}")
            self.log_signal.emit("=" * 60)

            self.finished_signal.emit(output_file)

        except Exception as e:
            error_details = traceback.format_exc()
            self.log_signal.emit(f"Detalhes do Erro: {error_details}")
            self.error_signal.emit(str(e))


class GeminiWorker(QThread):
    """Worker dedicado para tradução com Gemini (usa gemini_api.py)."""
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)  # Retorna o caminho do arquivo final
    error_signal = pyqtSignal(str)

    def __init__(self, api_key: str, input_file: str, target_language: str = "Portuguese (Brazil)"):
        super().__init__()
        self.api_key = api_key
        self.input_file = input_file
        self.target_language = target_language
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            # Verifica disponibilidade da biblioteca
            if not gemini_api.GENAI_AVAILABLE:
                self.error_signal.emit(
                    "Biblioteca 'google-generativeai' não instalada.\n"
                    "Execute: pip install google-generativeai"
                )
                return

            with open(self.input_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            total_lines = len(lines)
            translated_lines = []
            output_file = self.input_file.replace("_optimized.txt", "_translated.txt")
            if output_file == self.input_file:
                output_file = str(Path(self.input_file).with_suffix('')) + "_translated.txt"

            self.log_signal.emit(f"Iniciando tradução de {total_lines} linhas...")

            # Processamento em lotes
            batch_size = 15
            current_batch = []
            batch_original_lines = []

            for i, line in enumerate(lines):
                if not self._is_running:
                    self.log_signal.emit("⚠️ Tradução interrompida pelo usuário.")
                    break

                # Verificação de None/Null para evitar crashes
                if line is None:
                    translated_lines.append("\n")
                    continue

                line = line.strip()
                if not line:
                    translated_lines.append("\n")
                    continue

                current_batch.append(line)
                batch_original_lines.append(line)

                # Processa o lote quando atingir o tamanho ou for a última linha
                if len(current_batch) >= batch_size or i == total_lines - 1:
                    if not current_batch:
                        continue

                    try:
                        # Chama a função centralizada do gemini_api
                        translations, success, error_msg = gemini_api.translate_batch(
                            current_batch,
                            self.api_key,
                            self.target_language,
                            120.0
                        )

                        if success and translations:
                            # Verifica se há traduções None no resultado
                            for trans in translations:
                                if trans is None or trans == "":
                                    translated_lines.append("\n")
                                else:
                                    translated_lines.append(trans)
                        else:
                            self.log_signal.emit(f"⚠️ {error_msg if error_msg else 'Erro desconhecido'}")
                            # Em caso de erro, usa as linhas originais
                            translated_lines.extend([l + "\n" for l in current_batch])

                        # Atualiza progresso
                        percent = int(((i + 1) / total_lines) * 100)
                        self.progress_signal.emit(percent)
                        self.status_signal.emit(f"Traduzindo... {percent}%")

                        current_batch = []
                        batch_original_lines = []

                    except Exception as e:
                        error_detail = str(e)
                        self.log_signal.emit(f"❌ Erro no lote: {error_detail}")
                        translated_lines.extend([l + "\n" for l in current_batch])
                        current_batch = []
                        batch_original_lines = []

            # Salva o arquivo traduzido
            with open(output_file, 'w', encoding='utf-8') as f:
                f.writelines(translated_lines)

            self.finished_signal.emit(output_file)

        except Exception as e:
            error_details = traceback.format_exc()
            self.log_signal.emit(f"Detalhes do Erro: {error_details}")
            self.error_signal.emit(str(e))


class HybridWorker(QThread):
    """Worker com fallback automático: Gemini → Ollama"""
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, api_key: str, input_file: str, target_language: str = "Portuguese (Brazil)"):
        super().__init__()
        self.api_key = api_key
        self.input_file = input_file
        self.target_language = target_language
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            # Importa HybridTranslator
            try:
                from core.hybrid_translator import HybridTranslator
            except ImportError:
                self.error_signal.emit("Módulo hybrid_translator não encontrado")
                return

            with open(self.input_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            total_lines = len(lines)
            translated_lines = []
            output_file = self.input_file.replace("_optimized.txt", "_translated.txt")
            if output_file == self.input_file:
                output_file = str(Path(self.input_file).with_suffix('')) + "_translated.txt"

            self.log_signal.emit(f"🤖 AUTO Mode: {total_lines} linhas (Gemini primeiro, Ollama se quota esgotar)")

            # Cria tradutor híbrido
            translator = HybridTranslator(api_key=self.api_key, prefer_gemini=True)

            self.log_signal.emit(f"✅ Gemini: {'Disponível' if translator.gemini_available else 'Indisponível'}")
            self.log_signal.emit(f"✅ Ollama: {'Disponível' if translator.ollama_available else 'Indisponível'}")

            # Processamento em lotes - OTIMIZADO PARA VELOCIDADE MÁXIMA
            batch_size = 100  # AUMENTADO 6.6x para velocidade!
            current_batch = []

            for i, line in enumerate(lines):
                if not self._is_running:
                    self.log_signal.emit("⚠️ Tradução interrompida pelo usuário.")
                    break

                line = line.strip()
                if not line:
                    translated_lines.append("\n")
                    continue

                current_batch.append(line)

                # Processa lote
                if len(current_batch) >= batch_size or i == total_lines - 1:
                    if not current_batch:
                        continue

                    try:
                        from core.hybrid_translator import TranslationMode

                        # Traduz com fallback automático
                        translations, success, error_msg = translator.translate_batch(
                            current_batch,
                            self.target_language,
                            TranslationMode.AUTO
                        )

                        if success:
                            translated_lines.extend(translations)
                        else:
                            self.log_signal.emit(f"⚠️ {error_msg}")
                            translated_lines.extend([l + "\n" for l in current_batch])

                        # Mostra status atual
                        stats = translator.get_stats()
                        if stats['fallback_switches'] > 0:
                            self.log_signal.emit(f"🔄 Mudou para Ollama (quota Gemini esgotada)")

                        # Atualiza progresso
                        percent = int(((i + 1) / total_lines) * 100)
                        self.progress_signal.emit(percent)
                        self.status_signal.emit(f"{translator.get_status_message()} - {percent}%")

                        current_batch = []

                    except Exception as e:
                        self.log_signal.emit(f"❌ Erro no lote: {str(e)}")
                        translated_lines.extend([l + "\n" for l in current_batch])
                        current_batch = []

            # Salva arquivo
            with open(output_file, 'w', encoding='utf-8') as f:
                f.writelines(translated_lines)

            # Mostra estatísticas finais
            final_stats = translator.get_stats()
            self.log_signal.emit("\n" + "="*50)
            self.log_signal.emit("📊 ESTATÍSTICAS FINAIS:")
            self.log_signal.emit(f"   Gemini: {final_stats['gemini_requests']} requisições")
            self.log_signal.emit(f"   Ollama: {final_stats['ollama_requests']} requisições")
            self.log_signal.emit(f"   Fallbacks: {final_stats['fallback_switches']}")
            self.log_signal.emit(f"   Total traduzido: {final_stats['total_texts_translated']} textos")
            self.log_signal.emit("="*50)

            self.finished_signal.emit(output_file)

        except Exception as e:
            error_details = traceback.format_exc()
            self.log_signal.emit(f"Detalhes do Erro: {error_details}")
            self.error_signal.emit(str(e))


class OllamaWorker(QThread):
    """
    Worker ULTRA-RESPONSIVO para Ollama
    FOCO: UI FLUIDA e botão Parar instantâneo
    """
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, input_file: str, target_language: str = "Portuguese (Brazil)", model: str = "llama3.2:3b"):
        super().__init__()
        self.input_file = input_file
        self.target_language = target_language
        self.model = model
        self._is_running = True
        self.executor = None  # Para forçar shutdown

    def stop(self):
        """Parada INSTANTÂNEA sem esperar requests"""
        self._is_running = False
        if self.executor:
            try:
                self.executor.shutdown(wait=False, cancel_futures=True)  # Python 3.9+
            except TypeError:
                self.executor.shutdown(wait=False)  # Python 3.8 e anteriores
        self.log_signal.emit("🛑 Parada solicitada - interrompendo...")

    def _detect_optimal_workers(self):
        """
        🌡️ PROTEÇÃO TÉRMICA: Força 1 worker para evitar superaquecimento da GPU
        GTX 1060 e GPUs similares: 2+ workers = 80°C+ (crítico)
        1 worker = ~60-70°C (seguro)
        """
        return 1  # TRAVA DE SEGURANÇA: Single-thread obrigatório

    def run(self):
        try:
            import requests
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import time
            import sys
            import os

            # Importa módulos de otimização e validação ROM
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from core.translation_optimizer import TranslationOptimizer
            from core.rom_text_validator import ROMTextValidator
            from core.rom_translation_prompts import ROMTranslationPrompts

            # Verifica se Ollama está rodando
            try:
                response = requests.get('http://127.0.0.1:11434/api/tags', timeout=2)
                if response.status_code != 200:
                    error_msg = (
                        "❌ ERRO: Ollama não está respondendo corretamente.\n\n"
                        "SOLUÇÃO:\n"
                        "1. Abra um terminal/CMD\n"
                        "2. Execute: ollama serve\n"
                        "3. Aguarde \"Ollama is running\"\n"
                        "4. Tente traduzir novamente"
                    )
                    self.error_signal.emit(error_msg)
                    return
            except requests.exceptions.ConnectionError:
                error_msg = (
                    "❌ ERRO: Ollama não está rodando.\n\n"
                    "SOLUÇÃO RÁPIDA:\n"
                    "1. Abra um novo terminal/CMD\n"
                    "2. Execute: ollama serve\n"
                    "3. Aguarde a mensagem \"Ollama is running\"\n"
                    "4. Volte aqui e clique em 'Traduzir com IA'\n\n"
                    "💡 DICA: Mantenha o terminal do Ollama aberto enquanto traduz"
                )
                self.error_signal.emit(error_msg)
                return
            except Exception as e:
                error_msg = (
                    f"❌ ERRO ao conectar ao Ollama: {str(e)}\n\n"
                    "SOLUÇÃO:\n"
                    "1. Verifique se o Ollama está instalado: ollama --version\n"
                    "2. Inicie o serviço: ollama serve\n"
                    "3. Tente novamente"
                )
                self.error_signal.emit(error_msg)
                return

            # ✅ NOVA VALIDAÇÃO: Verifica se modelo específico está instalado
            try:
                models_response = requests.get('http://127.0.0.1:11434/api/tags', timeout=5)
                if models_response.status_code == 200:
                    installed_models = models_response.json().get('models', [])
                    model_names = [m.get('name', '') for m in installed_models]

                    # Verifica se modelo existe (exato ou com variações de tag)
                    model_base = self.model.split(':')[0]  # Ex: "llama3.2" de "llama3.2:3b"
                    model_found = any(model_base in name for name in model_names)

                    if not model_found:
                        available_models = ', '.join(model_names[:5]) if model_names else 'Nenhum'
                        error_msg = (
                            f"❌ ERRO: Modelo '{self.model}' NÃO está instalado.\n\n"
                            f"📋 Modelos disponíveis: {available_models}\n\n"
                            "SOLUÇÃO RÁPIDA:\n"
                            f"1. Abra um terminal/CMD\n"
                            f"2. Execute: ollama pull {self.model}\n"
                            f"3. Aguarde o download completar\n"
                            f"4. Tente traduzir novamente\n\n"
                            f"💡 ALTERNATIVA: Instale modelo menor e mais rápido:\n"
                            f"   ollama pull llama3.2:1b"
                        )
                        self.error_signal.emit(error_msg)
                        return
                    else:
                        self.log_signal.emit(f"✅ Modelo '{self.model}' encontrado e pronto para uso")
            except Exception as e:
                self.log_signal.emit(f"⚠️ Não foi possível verificar modelos instalados: {str(e)}")
                # Continua mesmo assim (pode ser versão antiga do Ollama)

            with open(self.input_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines()]

            total_lines = len(lines)
            output_file = self.input_file.replace("_optimized.txt", "_translated.txt")
            if output_file == self.input_file:
                output_file = str(Path(self.input_file).with_suffix('')) + "_translated.txt"

            # === FASE 1: OTIMIZAÇÃO AGRESSIVA PRÉ-TRADUÇÃO ===
            self.log_signal.emit("="*60)
            self.log_signal.emit("🔧 FASE 1: OTIMIZAÇÃO AGRESSIVA")
            self.log_signal.emit("="*60)

            cache_file = os.path.join(os.path.dirname(self.input_file), "translation_cache.json")
            optimizer = TranslationOptimizer(cache_file=cache_file)

            self.log_signal.emit(f"📊 Textos originais: {total_lines:,}")
            self.log_signal.emit("🔍 Aplicando filtros: deduplicação, cache, heurísticas...")

            unique_texts, index_mapping = optimizer.optimize_text_list(
                lines,
                skip_technical=True,
                skip_proper_nouns=False,  # Mantenha False para não perder nomes de personagens
                min_entropy=0.30,
                use_cache=True
            )

            self.log_signal.emit(optimizer.get_stats_report())

            # Se não há nada para traduzir, reconstrói e salva
            if len(unique_texts) == 0:
                self.log_signal.emit("✅ Todos os textos já em cache ou filtrados!")
                reconstructed = optimizer.reconstruct_translations([], lines, index_mapping)
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(reconstructed))
                self.finished_signal.emit(output_file)
                return

            # === FASE 2: TRADUÇÃO OTIMIZADA ===
            self.log_signal.emit("="*60)
            self.log_signal.emit("🚀 FASE 2: TRADUÇÃO (SOMENTE TEXTOS ÚNICOS)")
            self.log_signal.emit("="*60)

            # DETECÇÃO AUTOMÁTICA DE WORKERS (hardware-aware)
            MAX_WORKERS = self._detect_optimal_workers()  # 1 worker = UI fluida

            # BATCH SIZE otimizado: 8-16 linhas (prompts curtos = mais estável)
            if len(unique_texts) < 1000:
                BATCH_SIZE = 12
            elif len(unique_texts) < 10000:
                BATCH_SIZE = 16
            else:
                BATCH_SIZE = 16

            self.log_signal.emit(f"⚡ Batch: {BATCH_SIZE} | Workers: {MAX_WORKERS} (otimizado para UI fluida)")
            self.log_signal.emit("🌡️ Modo de Proteção Térmica Ativo: Adicionando intervalos para resfriamento da GPU")
            estimated_time = (len(unique_texts) / BATCH_SIZE / MAX_WORKERS) * 2.0  # Estimativa realista
            self.log_signal.emit(f"⏱️  Tempo estimado: ~{estimated_time:.1f} minutos (com respiros térmicos)")

            translated_unique = [None] * len(unique_texts)  # Pré-aloca lista

            # Inicializa validador e gerador de prompts
            validator = ROMTextValidator()
            prompt_gen = ROMTranslationPrompts()

            def is_binary_garbage(text):
                """
                FILTRO DE ENTRADA: Detecta lixo binário/código ANTES de enviar para IA
                Retorna (is_garbage: bool, reason: str)
                """
                import re

                if not text or not isinstance(text, str):
                    return True, "Texto vazio ou inválido"

                text_clean = text.strip()
                if len(text_clean) < 1:
                    return True, "Texto muito curto (< 1 char)"

                # ✅ EXCEÇÃO: Game UI palavras curtas em MAIÚSCULAS (SCORE, TIME, LEVEL, 1UP)
                # Comum em jogos retro - sempre permitir
                game_ui_pattern = r'^[A-Z0-9\s\-]{1,12}$'  # Ex: SCORE, 1UP, P1, LEVEL 1
                if re.match(game_ui_pattern, text_clean):
                    return False, ""  # Válido - é UI de jogo

                # ✅ EXCEÇÃO: Textos com números que parecem HUD (Player 1, Stage 1-1)
                hud_pattern = r'(player|stage|level|world|area)\s*[\d\-]+'
                if re.search(hud_pattern, text_clean, re.IGNORECASE):
                    return False, ""  # Válido - é HUD

                # 1. Tem vogais? (palavras reais têm vogais)
                vowels = set('aeiouAEIOUàáâãéêíóôõúÀÁÂÃÉÊÍÓÔÕÚ')
                if not any(char in vowels for char in text_clean):
                    return True, f"Sem vogais (lixo binário)"

                # 2. Proporção de caracteres especiais
                special_chars = set('!@#$%^&*()_+-=[]{}|;:,.<>?/~`')
                special_count = sum(1 for char in text_clean if char in special_chars)
                if len(text_clean) > 0 and special_count / len(text_clean) > 0.7:  # 70% (era 50%)
                    return True, f">70% caracteres especiais"

                # 3. Padrões de lixo binário ESTRITO (só lixo real)
                garbage_patterns = [
                    (r'^[A-Z]{8,}$', "8+ letras maiúsculas"),     # AAAAAAAA (8+, não 6)
                    (r'^[!@#$%^&*]{4,}', "4+ símbolos"),          # !!!!
                    (r'^[0-9]{10,}$', "10+ dígitos"),             # 1234567890 (10+, não 8)
                    (r'^[dD][A-F0-9]{5,}', "Padrão hexadecimal"), # dAdBdCdE
                ]
                for pattern, desc in garbage_patterns:
                    if re.search(pattern, text_clean):
                        return True, desc

                # 4. Repetição excessiva (mais permissivo)
                if len(set(text_clean)) < len(text_clean) / 5 and len(text_clean) > 8:  # 20% (era 25%), >8 chars (era 5)
                    return True, "Repetição excessiva"

                return False, ""  # Válido

            def is_refusal_or_garbage(raw_text, original_text):
                """
                REFUSAL FILTER: Detecta se IA recusou traduzir ou retornou lixo
                Retorna True se devemos DESCARTAR a tradução
                """
                import re
                from difflib import SequenceMatcher

                if not raw_text or not isinstance(raw_text, str):
                    return True

                text_lower = raw_text.lower().strip()

                # Padrões de recusa (IA se recusando a traduzir)
                refusal_patterns = [
                    r'não posso',
                    r'i cannot',
                    r'i can\'t',
                    r'sorry',
                    r'desculpe',
                    r'i apologize',
                    r'peço desculpas',
                    r'i\'m unable',
                    r'não consigo',
                    r'i don\'t',
                    r'eu não',
                ]

                for pattern in refusal_patterns:
                    if re.search(pattern, text_lower):
                        return True  # É recusa, descartar

                # Detecta se IA repetiu instruções do prompt
                instruction_keywords = ['1.', '2.', '3.', 'se o texto', 'if the text', 'instructions']
                if any(keyword in text_lower for keyword in instruction_keywords):
                    return True  # Repetiu instruções, descartar

                # Validação de similaridade: >80% igual ao original = não traduziu
                similarity = SequenceMatcher(None, original_text.lower(), text_lower).ratio()
                if similarity > 0.8:
                    return True  # Muito similar, não traduziu de verdade

                return False  # Tradução válida

            def clean_translation(raw_text, original_text):
                """Remove prefixos indesejados preservando variáveis e tags"""
                import re

                if not raw_text or not isinstance(raw_text, str):
                    return original_text

                cleaned = raw_text.strip()

                # Remove prefixos comuns de modelos (case-insensitive)
                prefixes_to_remove = [
                    r'^sure[,:]?\s*',
                    r'^claro[,:]?\s*',
                    r'^here\s+(is|are)\s+(the\s+)?translation[s]?[:\s]*',
                    r'^aqui\s+está?\s+(a\s+)?tradução[:\s]*',
                    r'^translation[:\s]+',
                    r'^tradução[:\s]+',
                ]

                for prefix_pattern in prefixes_to_remove:
                    cleaned = re.sub(prefix_pattern, '', cleaned, flags=re.IGNORECASE)

                # Remove dois-pontos inicial isolado
                cleaned = re.sub(r'^:\s*', '', cleaned)

                # Remove aspas desnecessárias no início e fim
                if cleaned.startswith('"') and cleaned.endswith('"'):
                    cleaned = cleaned[1:-1]
                if cleaned.startswith("'") and cleaned.endswith("'"):
                    cleaned = cleaned[1:-1]

                cleaned = cleaned.strip()

                # Se limpeza removeu tudo, retorna original
                if not cleaned or len(cleaned) < 2:
                    return original_text

                return cleaned

            def translate_single(index, text):
                """Traduz um único texto - ULTRA RESPONSIVO"""
                # Check rápido de interrupção
                if not self._is_running:
                    return index, text

                original_text = text.strip()
                if not original_text:
                    return index, original_text

                # 🛡️ FILTRO DE ENTRADA: Detecta lixo binário ANTES de enviar para IA
                is_garbage, reason = is_binary_garbage(original_text)
                if is_garbage:
                    # LOG DETALHADO: Especifica motivo da rejeição
                    self.log_signal.emit(f"⚠️ Texto '{original_text[:30]}' ignorado. Motivo: {reason} (Filtro Entrada)")
                    return index, original_text

                # === TRADUÇÃO COM RETRY AUTOMÁTICO ===
                MAX_RETRIES = 3
                last_error = None

                for attempt in range(MAX_RETRIES):
                    try:
                        # Check antes de traduzir
                        if not self._is_running:
                            return index, text

                        # Prompt otimizado por modelo
                        if "llama" in self.model.lower():
                            # Llama 3.2: Prompt direto + instruções de formatação
                            prompt = (
                                f"Translate this retro video game text to {self.target_language}. "
                                f"Rules:\n"
                                f"- Output ONLY the translation\n"
                                f"- Keep punctuation (? ! . , etc)\n"
                                f"- Short text is normal (1-3 words)\n"
                                f"- Game UI words stay uppercase if originally uppercase\n"
                                f"- If garbage/code, return original exactly\n\n"
                                f"Text: {original_text}"
                            )
                        else:
                            # Mistral ou outros: usa prompt complexo
                            prompt = prompt_gen.get_translation_prompt(original_text, self.target_language)

                        payload = {
                            "model": self.model,
                            "prompt": prompt,
                            "stream": False,
                            "options": {
                                "temperature": 0.1,      # 🎯 MISTRAL: Baixo mas não zero (melhor qualidade)
                                "num_predict": 150,      # 🎯 MISTRAL: Aumentado (gera traduções melhores)
                                "top_p": 0.85,           # 🎯 MISTRAL: Reduzido = mais focado
                                "repeat_penalty": 1.2,   # 🎯 MISTRAL: Maior = evita repetições
                                "num_ctx": 512           # ⚡ ULTRA-RÁPIDO: Otimizado para GTX 1060 (3x mais rápido!)
                            }
                        }

                        response = requests.post(
                            'http://127.0.0.1:11434/api/generate',
                            json=payload,
                            timeout=180  # 🎯 MISTRAL: 180s (estabilidade máxima)
                        )

                        if response.status_code == 200:
                            raw_translation = response.json().get('response', '')

                            # REFUSAL FILTER: Detecta recusa ou lixo
                            if is_refusal_or_garbage(raw_translation, original_text):
                                # LOG DETALHADO: Mostra texto e resposta da IA
                                self.log_signal.emit(
                                    f"⚠️ Texto '{original_text[:30]}' ignorado. "
                                    f"Motivo: IA Recusou/Alucinou (Filtro Saída). "
                                    f"Resposta: '{raw_translation[:40]}'"
                                )
                                return index, original_text

                            # Extrai tradução com fallback robusto (NUNCA None)
                            translation = prompt_gen.extract_translation(raw_translation, original_text)

                            # Valida e corrige tradução
                            translation = prompt_gen.validate_and_fix_translation(original_text, translation)

                            # Pós-processamento: remove prefixos indesejados
                            translation = clean_translation(translation, original_text)

                            return index, translation
                        else:
                            # Erro HTTP: tenta novamente
                            last_error = f"HTTP {response.status_code}"
                            if attempt < MAX_RETRIES - 1:
                                time.sleep(2 ** attempt)  # Backoff: 1s, 2s, 4s
                                continue
                            else:
                                self.log_signal.emit(f"⚠️ Texto {index} falhou após {MAX_RETRIES} tentativas: {last_error}")
                                return index, original_text

                    except requests.exceptions.ConnectionError as e:
                        last_error = "Conexão perdida com Ollama"
                        if attempt < MAX_RETRIES - 1:
                            self.log_signal.emit(f"🔄 Texto {index}: Tentativa {attempt + 1}/{MAX_RETRIES} - Reconectando...")
                            time.sleep(2 ** attempt)  # Backoff exponencial
                            continue
                        else:
                            self.log_signal.emit(
                                f"❌ Texto {index}: Ollama desconectou após {MAX_RETRIES} tentativas.\n"
                                f"   Verifique se 'ollama serve' ainda está rodando."
                            )
                            return index, original_text

                    except requests.exceptions.Timeout as e:
                        last_error = f"Timeout após 180s"
                        if attempt < MAX_RETRIES - 1:
                            self.log_signal.emit(f"⏱️ Texto {index}: Timeout - Tentativa {attempt + 1}/{MAX_RETRIES}")
                            time.sleep(2 ** attempt)
                            continue
                        else:
                            # Fallback: tenta tradução simplificada linha por linha
                            self.log_signal.emit(f"🔄 Texto {index}: Tentando fallback linha por linha...")
                            try:
                                lines = original_text.split('\n')
                                if len(lines) > 1:
                                    # Texto multi-linha: traduz linha por linha
                                    translated_lines = []
                                    for line in lines:
                                        if not line.strip():
                                            translated_lines.append(line)
                                            continue
                                        simple_prompt = f"Translate to {self.target_language}: {line.strip()}"
                                        simple_payload = {
                                            "model": self.model,
                                            "prompt": simple_prompt,
                                            "stream": False,
                                            "options": {"temperature": 0.1, "num_predict": 100, "num_ctx": 256}
                                        }
                                        resp = requests.post('http://127.0.0.1:11434/api/generate', json=simple_payload, timeout=60)
                                        if resp.status_code == 200:
                                            line_trans = clean_translation(resp.json().get('response', ''), line)
                                            translated_lines.append(line_trans)
                                        else:
                                            translated_lines.append(line)
                                    fallback_result = '\n'.join(translated_lines)
                                    self.log_signal.emit(f"✅ Texto {index}: Fallback linha por linha bem-sucedido")
                                    return index, fallback_result
                            except:
                                pass

                            # Se fallback falhar: marca como não traduzido
                            self.log_signal.emit(f"⚠️ Texto {index}: Fallback falhou. Marcando como [UNTRANSLATED]")
                            return index, f"[UNTRANSLATED] {original_text}"

                    except requests.exceptions.HTTPError as e:
                        last_error = f"HTTPError: {str(e)}"
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(2 ** attempt)
                            continue
                        else:
                            self.log_signal.emit(f"⚠️ Texto {index}: Erro HTTP - {str(e)[:80]}")
                            return index, original_text

                    except Exception as e:
                        # Erro inesperado: mostra COMPLETO (não apenas 50 chars)
                        error_type = type(e).__name__
                        error_msg = str(e)
                        last_error = f"{error_type}: {error_msg}"

                        if attempt < MAX_RETRIES - 1:
                            self.log_signal.emit(f"⚠️ Texto {index}: {error_type} - Tentativa {attempt + 1}/{MAX_RETRIES}")
                            time.sleep(2 ** attempt)
                            continue
                        else:
                            self.log_signal.emit(
                                f"❌ Texto {index}: ERRO CRÍTICO após {MAX_RETRIES} tentativas:\n"
                                f"   Tipo: {error_type}\n"
                                f"   Detalhe: {error_msg[:200]}"
                            )
                            return index, original_text

                # Fallback final (não deveria chegar aqui)
                return index, original_text

            # Processa textos com UI FLUIDA
            completed = 0
            start_time = time.time()

            self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
            try:
                for batch_start in range(0, len(unique_texts), BATCH_SIZE):
                    # ✅ CHECK FREQUENTE de interrupção
                    if not self._is_running:
                        self.log_signal.emit("⚠️ Tradução interrompida pelo usuário.")
                        break

                    batch_end = min(batch_start + BATCH_SIZE, len(unique_texts))
                    batch = [(i, unique_texts[i]) for i in range(batch_start, batch_end)]

                    # Submete batch
                    futures = {self.executor.submit(translate_single, idx, text): idx for idx, text in batch}

                    # Aguarda resultados COM CHECKS de interrupção
                    for future in as_completed(futures):
                        # ✅ CHECK antes de processar resultado
                        if not self._is_running:
                            break

                        idx, translation = future.result()
                        translated_unique[idx] = translation
                        completed += 1

                        # Atualiza progresso
                        percent = int((completed / len(unique_texts)) * 100)
                        self.progress_signal.emit(percent)

                        elapsed = time.time() - start_time
                        rate = completed / elapsed if elapsed > 0 else 0
                        eta_seconds = (len(unique_texts) - completed) / rate if rate > 0 else 0
                        eta_minutes = eta_seconds / 60

                        self.status_signal.emit(f"🚀 {completed}/{len(unique_texts)} ({percent}%) | ETA: {eta_minutes:.1f}min")

                        # 🌡️ GPU BREATH: Respiro térmico obrigatório
                        # 200ms permite cooler dissipar calor antes da próxima requisição
                        # GTX 1060: 80°C com 0ms → 60-70°C com 200ms
                        time.sleep(0.2)  # PROTEÇÃO TÉRMICA: 200ms entre traduções

                    # Log a cada batch
                    self.log_signal.emit(f"✅ Batch {batch_start//BATCH_SIZE + 1}/{(len(unique_texts)+BATCH_SIZE-1)//BATCH_SIZE} completo")

                    # 🌡️ RESPIRO TÉRMICO entre batches (resfriamento intensivo)
                    time.sleep(0.5)  # 500ms: GPU + GUI respiram antes do próximo batch

            finally:
                # Garante shutdown do executor
                self.executor.shutdown(wait=False)
                self.executor = None

            # === FASE 3: RECONSTRUÇÃO ===
            self.log_signal.emit("="*60)
            self.log_signal.emit("🔧 FASE 3: RECONSTRUÇÃO DAS TRADUÇÕES")
            self.log_signal.emit("="*60)

            # Trata None em translated_unique
            for i in range(len(translated_unique)):
                if translated_unique[i] is None:
                    translated_unique[i] = unique_texts[i]  # Fallback para original

            # Reconstrói lista completa aplicando as traduções
            final_translations = optimizer.reconstruct_translations(
                translated_unique,
                lines,
                index_mapping
            )

            # Salva cache
            optimizer.save_cache()
            self.log_signal.emit(f"💾 Cache salvo: {len(optimizer.cache):,} entradas")

            # === DEBUG: CONTADORES ===
            translated_count = 0
            written_count = 0

            for i, (original, translated) in enumerate(zip(lines, final_translations)):
                if original.strip() != translated.strip():
                    translated_count += 1

            # Salva arquivo - PROTEÇÃO ANTI-CRASH
            with open(output_file, 'w', encoding='utf-8') as f:
                for line in final_translations:
                    f.write(line + '\n')
                    written_count += 1

            # DEBUG OBRIGATÓRIO
            print(f"[DEBUG] Escritas reais: {written_count}")
            print(f"[DEBUG] Linhas traduzidas: {translated_count}")
            print(f"[DEBUG] Arquivo de saída: {output_file}")
            print(f"[DEBUG] Tamanho do arquivo: {os.path.getsize(output_file)} bytes")

            self.log_signal.emit(f"[DEBUG] Escritas reais: {written_count}")
            self.log_signal.emit(f"[DEBUG] Linhas traduzidas: {translated_count}")
            self.log_signal.emit(f"[DEBUG] Arquivo: {output_file}")

            total_time = time.time() - start_time
            self.log_signal.emit(f"🎉 Completo em {total_time/60:.1f} minutos!")
            self.finished_signal.emit(output_file)

        except Exception as e:
            error_details = traceback.format_exc()
            self.log_signal.emit(f"Detalhes do Erro: {error_details}")
            self.error_signal.emit(str(e))


class ReinsertionWorker(QThread):
    """Worker dedicado para Reinserção. Thread-safe."""
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, rom_path: str, translated_path: str, output_rom_path: str):
        super().__init__()
        self.rom_path = rom_path
        self.translated_path = translated_path
        self.output_rom_path = output_rom_path

    def run(self):
        try:
            self.status_signal.emit("Preparando arquivos...")
            self.progress_signal.emit(0)

            with open(self.translated_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            shutil.copyfile(self.rom_path, self.output_rom_path)

            rom_size = os.path.getsize(self.output_rom_path)

            with open(self.output_rom_path, 'r+b') as rom_file:
                total_lines = len(lines)

                for i, line in enumerate(lines):
                    if self.isInterruptionRequested():
                        self.log_signal.emit("Reinserção interrompida pelo usuário.")
                        break

                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith('['):
                        try:
                            match = re.match(r'^\[(0x[0-9a-fA-F]+)\]\s*(.*)$', line)
                            if match:
                                offset_str = match.group(1)
                                offset = int(offset_str, 16)
                                new_text_with_codes = match.group(2)

                                # Validação de offset
                                if offset < 0 or offset >= rom_size:
                                    self.log_signal.emit(
                                        f"⚠️ Offset inválido {offset_str} na linha {i+1}. "
                                        f"ROM tem {rom_size} bytes. Pulando."
                                    )
                                    continue

                                rom_file.seek(offset)

                                # AVISO CRÍTICO: Encoding
                                # Latin-1 é usado aqui, mas ROMs geralmente usam tabelas
                                # customizadas. Acentos podem ser corrompidos.
                                # Idealmente, use um mapeamento de caracteres específico da ROM.
                                encoded_text = new_text_with_codes.encode('latin-1', errors='ignore')

                                # Validação de tamanho (básica)
                                if len(encoded_text) > 100:
                                    self.log_signal.emit(
                                        f"⚠️ Texto muito longo na linha {i+1} "
                                        f"({len(encoded_text)} bytes). "
                                        f"Pode sobrescrever dados importantes."
                                    )

                                rom_file.write(encoded_text)

                        except ValueError as e:
                            self.log_signal.emit(
                                f"⚠️ Erro de offset hexadecimal na linha {i+1}: {e}. Pulando."
                            )
                            continue
                        except Exception as e:
                            self.log_signal.emit(
                                f"⚠️ Erro de escrita na linha {i+1} "
                                f"({line[:50]}...): {e}. Pulando."
                            )
                            continue

                    # Atualização de progresso mais frequente
                    if total_lines > 0 and (i % 20 == 0 or i == total_lines - 1):
                        percent = int((i / total_lines) * 100)
                        self.status_signal.emit(f"Reinserindo... {percent}%")
                        self.progress_signal.emit(percent)

            self.progress_signal.emit(100)
            self.status_signal.emit("Concluído!")
            self.log_signal.emit(
                f"✅ ROM salva com sucesso: {os.path.basename(self.output_rom_path)}"
            )
            self.finished_signal.emit()

        except Exception as e:
            error_details = traceback.format_exc()
            self.log_signal.emit(f"Detalhes do Erro: {error_details}")
            self.error_signal.emit(str(e))


# --- CONFIG E UTILITÁRIOS ---

class ProjectConfig:
    BASE_DIR = Path(__file__).parent
    ROMS_DIR = BASE_DIR.parent / "ROMs"
    SCRIPTS_DIR = BASE_DIR.parent / "Scripts principais"
    CONFIG_FILE = BASE_DIR / "translator_config.json"
    I18N_DIR = BASE_DIR.parent / "i18n"
    # --- COLE AQUI (Mantenha o recuo/indentação igual ao de cima) ---

    PLATFORMS = {
        # --- PRONTOS PARA USO (Validados e Testados) ---
        "Super Nintendo (SNES)": {"code": "snes", "ready": True, "label": "platform_snes"},
        "PC Games (Windows)": {"code": "pc", "ready": True, "label": "platform_pc"},

        # --- EM FASE DE TESTES (Bloqueados até validação) ---
        "PlayStation 1 (PS1)": {"code": "ps1", "ready": False, "label": "platform_ps1"},
        "MS-DOS (PC Antigo)": {"code": "dos", "ready": False, "label": "platform_dos"},
        "PlayStation 2 (PS2)": {"code": "ps2", "ready": False, "label": "platform_ps2"},
        "PlayStation 3 (PS3)": {"code": "ps3", "ready": False, "label": "platform_ps3"},
        "PlayStation 4 (PS4)": {"code": "ps4", "ready": False, "label": "platform_ps4"},
        "PlayStation 5 (PS5)": {"code": "ps5", "ready": False, "label": "platform_ps5"},
        "Nintendo (NES)": {"code": "nes", "ready": False, "label": "platform_nes"},
        "Nintendo 64 (N64)": {"code": "n64", "ready": False, "label": "platform_n64"},
        "Nintendo GameCube": {"code": "gc", "ready": False, "label": "platform_gc"},
        "Nintendo Wii": {"code": "wii", "ready": False, "label": "platform_wii"},
        "Nintendo Wii U": {"code": "wiiu", "ready": False, "label": "platform_wiiu"},
        "Nintendo Switch": {"code": "switch", "ready": False, "label": "platform_switch"},
        "Game Boy (Classic)": {"code": "gb", "ready": False, "label": "platform_gb"},
        "Game Boy Color (GBC)": {"code": "gbc", "ready": False, "label": "platform_gbc"},
        "Game Boy Advance (GBA)": {"code": "gba", "ready": False, "label": "platform_gba"},
        "Nintendo DS (NDS)": {"code": "nds", "ready": False, "label": "platform_nds"},
        "Nintendo 3DS": {"code": "3ds", "ready": False, "label": "platform_3ds"},
        "Sega Master System": {"code": "sms", "ready": False, "label": "platform_sms"},
        "Sega Mega Drive": {"code": "md", "ready": False, "label": "platform_md"},
        "Sega CD": {"code": "scd", "ready": False, "label": "platform_scd"},
        "Sega Saturn": {"code": "sat", "ready": False, "label": "platform_sat"},
        "Sega Dreamcast": {"code": "dc", "ready": False, "label": "platform_dc"},
        "Neo Geo": {"code": "neo", "ready": False, "label": "platform_neo"},
        "Atari 2600": {"code": "atari", "ready": False, "label": "platform_atari"},
        "Xbox Clássico": {"code": "xbox", "ready": False, "label": "platform_xbox"},
        "Xbox 360": {"code": "x360", "ready": False, "label": "platform_x360"},
        "PC Games (Linux)": {"code": "linux", "ready": False, "label": "platform_linux"},
        "PC Games (Mac)": {"code": "mac", "ready": False, "label": "platform_mac"}
    }

    UI_LANGUAGES = {
            "🇧🇷 Português (Brasil)": "pt",
            "🇺🇸 English (US)": "en",
            "🇪🇸 Español (España)": "es",
            "🇫🇷 Français (France)": "fr",
            "🇩🇪 Deutsch (Deutschland)": "de",
            "🇮🇹 Italiano (Italia)": "it",
            "🇯🇵 日本語 (Japanese)": "ja",
            "🇰🇷 한국어 (Korean)": "ko",
            "🇨🇳 中文 (Chinese)": "zh",
            "🇷🇺 Русский (Russian)": "ru",
            "🇸🇦 العربية (Arabic)": "ar",
            "🇮🇳 हिन्दी (Hindi)": "hi",
            "🇹🇷 Türkçe (Turkish)": "tr",
            "🇵🇱 Polski (Polish)": "pl",
            "🇳🇱 Nederlands (Dutch)": "nl"
        }

    FONT_FAMILIES = {
            "Padrão (Segoe UI + CJK Fallback)": "Segoe UI, Malgun Gothic, Yu Gothic UI, Microsoft JhengHei UI, sans-serif",
            "Segoe UI Semilight": "Segoe UI Semilight, Segoe UI, sans-serif",
            "Malgun Gothic (Korean)": "Malgun Gothic, sans-serif",
            "Yu Gothic UI (Japanese)": "Yu Gothic UI, Yu Gothic, sans-serif",
            "Microsoft JhengHei UI (Chinese)": "Microsoft JhengHei UI, Microsoft JhengHei, sans-serif",
            "Arial": "Arial, sans-serif"
        }

    SOURCE_LANGUAGES = {
            "AUTO-DETECTAR": "auto",
            "Japonês (日本語)": "ja",
            "Inglês (English)": "en",
            "Espanhol (Español)": "es",
            "Russo (Русский)": "ru",
            "Chinês Simplificado (简体)": "zh-cn",
            "Chinês Tradicional (繁體)": "zh-tw",
            "Coreano (한국어)": "ko",
            "Francês (Français)": "fr",
            "Alemão (Deutsch)": "de",
            "Italiano (Italiano)": "it",
            "Árabe (العربية)": "ar",
            "Hindi (हिन्दी)": "hi",
            "Turco (Türkçe)": "tr",
            "Polonês (Polski)": "pl"
        }

    TARGET_LANGUAGES = {
            "Português (PT-BR)": "pt",
            "English (US)": "en",
            "Español (ES)": "es",
            "Français (FR)": "fr",
            "Deutsch (DE)": "de",
            "Italiano (IT)": "it",
            "日本語 (Japanese)": "ja",
            "한국어 (Korean)": "ko",
            "中文 (Chinese)": "zh",
            "Русский (Russian)": "ru"
        }
    THEMES = {
            "Preto (Black)": {"window": "#0d0d0d", "text": "#ffffff", "button": "#1a1a1a", "accent": "#4a9eff"},
            "Cinza (Gray)": {"window": "#2d2d2d", "text": "#ffffff", "button": "#3d3d3d", "accent": "#5c9eff"},
            "Branco (White)": {"window": "#f0f0f0", "text": "#000000", "button": "#e1e1e1", "accent": "#308cc6"}
        }

    # Mapping between internal theme keys and translation keys
    THEME_TRANSLATION_KEYS = {
            "Preto (Black)": "theme_black",
            "Cinza (Gray)": "theme_gray",
            "Branco (White)": "theme_white"
        }

    @classmethod
    def ensure_directories(cls):
        cls.ROMS_DIR.mkdir(exist_ok=True, parents=True)
        cls.SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    # i18n: JSON Loader with fallback
    _translations_cache = {}

    @classmethod
    def load_translations(cls, lang_code: str) -> Dict:
        """
        Load translations from JSON file with caching.
        Fallback hierarchy: requested lang → en → empty dict
        """
        if lang_code in cls._translations_cache:
            return cls._translations_cache[lang_code]

        json_file = cls.I18N_DIR / f"{lang_code}.json"

        if json_file.exists():
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    translations = json.load(f)
                    cls._translations_cache[lang_code] = translations
                    return translations
            except Exception as e:
                print(f"⚠️ Failed to load {lang_code}.json: {e}")

        # Fallback to English if not 'en' itself
        if lang_code != "en":
            return cls.load_translations("en")

        return {}

    # ROADMAP: Future platforms (not shown in main dropdown)
    PLATFORMS_ROADMAP = {
        "PlayStation": ["PS2", "PS3", "PS4", "PS5"],
        "Nintendo Classic": ["NES", "N64", "GameCube", "Wii", "Wii U", "Switch"],
        "Nintendo Portable": ["Game Boy", "Game Boy Color", "Game Boy Advance", "Nintendo DS", "3DS"],
        "Sega": ["Master System", "Mega Drive/Genesis", "Saturn", "Dreamcast"],
        "Xbox": ["Xbox", "Xbox 360", "Xbox One", "Xbox Series X/S"],
        "Other": ["Atari 2600", "Neo Geo", "PC Linux", "PC macOS"]
    }

    # ROADMAP TEXTS: Translations for roadmap popup
    ROADMAP_TEXTS = {
        "pt": {
            "header": "Plataformas em Desenvolvimento",
            "desc": "Estas plataformas serão adicionadas em futuras atualizações:",
            "note": "Nota: As atualizações são gratuitas para compradores do framework.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Outros"
            }
        },
        "en": {
            "header": "Platforms in Development",
            "desc": "These platforms will be added in future updates:",
            "note": "Note: Updates are free for framework purchasers.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Other"
            }
        },
        "es": {
            "header": "Plataformas en Desarrollo",
            "desc": "Estas plataformas se agregarán en futuras actualizaciones:",
            "note": "Nota: Las actualizaciones son gratuitas para los compradores del framework.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Otros"
            }
        },
        "fr": {
            "header": "Plateformes en Développement",
            "desc": "Ces plateformes seront ajoutées dans les futures mises à jour:",
            "note": "Note: Les mises à jour sont gratuites pour les acheteurs du framework.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Autres"
            }
        },
        "de": {
            "header": "Plattformen in Entwicklung",
            "desc": "Diese Plattformen werden in zukünftigen Updates hinzugefügt:",
            "note": "Hinweis: Updates sind kostenlos für Framework-Käufer.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Andere"
            }
        },
        "it": {
            "header": "Piattaforme in Sviluppo",
            "desc": "Queste piattaforme verranno aggiunte nei futuri aggiornamenti:",
            "note": "Nota: Gli aggiornamenti sono gratuiti per gli acquirenti del framework.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Altro"
            }
        },
        "ja": {
            "header": "開発中のプラットフォーム",
            "desc": "これらのプラットフォームは今後のアップデートで追加されます:",
            "note": "注: フレームワーク購入者はアップデートを無料で受け取れます。",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "任天堂クラシック",
                "Nintendo Portable": "任天堂ポータブル",
                "Sega": "セガ",
                "Xbox": "Xbox",
                "Other": "その他"
            }
        },
        "ko": {
            "header": "개발 중인 플랫폼",
            "desc": "이러한 플랫폼은 향후 업데이트에서 추가됩니다:",
            "note": "참고: 프레임워크 구매자는 무료로 업데이트를 받습니다.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "닌텐도 클래식",
                "Nintendo Portable": "닌텐도 휴대용",
                "Sega": "세가",
                "Xbox": "Xbox",
                "Other": "기타"
            }
        },
        "zh": {
            "header": "开发中的平台",
            "desc": "这些平台将在未来更新中添加:",
            "note": "注意: 框架购买者可免费获得更新。",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "任天堂经典",
                "Nintendo Portable": "任天堂掌机",
                "Sega": "世嘉",
                "Xbox": "Xbox",
                "Other": "其他"
            }
        },
        "ru": {
            "header": "Платформы в Разработке",
            "desc": "Эти платформы будут добавлены в будущих обновлениях:",
            "note": "Примечание: Обновления бесплатны для покупателей фреймворка.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Другое"
            }
        },
        "ar": {
            "header": "المنصات قيد التطوير",
            "desc": "ستتم إضافة هذه المنصات في التحديثات المستقبلية:",
            "note": "ملاحظة: التحديثات مجانية لمشتري الإطار.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "أخرى"
            }
        },
        "hi": {
            "header": "विकास में प्लेटफ़ॉर्म",
            "desc": "ये प्लेटफ़ॉर्म भविष्य के अपडेट में जोड़े जाएंगे:",
            "note": "नोट: फ्रेमवर्क खरीदारों के लिए अपडेट मुफ्त हैं।",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "अन्य"
            }
        },
        "tr": {
            "header": "Geliştirme Aşamasındaki Platformlar",
            "desc": "Bu platformlar gelecek güncellemelerde eklenecektir:",
            "note": "Not: Güncellemeler framework alıcıları için ücretsizdir.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Diğer"
            }
        },
        "pl": {
            "header": "Platformy w Rozwoju",
            "desc": "Te platformy zostaną dodane w przyszłych aktualizacjach:",
            "note": "Uwaga: Aktualizacje są bezpłatne dla nabywców frameworka.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Inne"
            }
        },
        "nl": {
            "header": "Platforms in Ontwikkeling",
            "desc": "Deze platforms worden toegevoegd in toekomstige updates:",
            "note": "Opmerking: Updates zijn gratis voor framework-kopers.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Andere"
            }
        }
    }

    FONT_FAMILIES = {
        "Padrão (Segoe UI + CJK Fallback)": "Segoe UI, Malgun Gothic, Yu Gothic UI, Microsoft JhengHei UI, sans-serif",
        "Segoe UI Semilight": "Segoe UI Semilight, Segoe UI, sans-serif",
        "Malgun Gothic (Korean)": "Malgun Gothic, sans-serif",
        "Yu Gothic UI (Japanese)": "Yu Gothic UI, Yu Gothic, sans-serif",
        "Microsoft JhengHei UI (Chinese)": "Microsoft JhengHei UI, Microsoft JhengHei, sans-serif",
        "Arial": "Arial, sans-serif"
    }

    SOURCE_LANGUAGES = {
        "AUTO-DETECTAR": "auto",
        "Japonês (日本語)": "ja",
        "Inglês (English)": "en",
        "Espanhol (Español)": "es",
        "Russo (Русский)": "ru",
        "Chinês Simplificado (简体)": "zh-cn",
        "Chinês Tradicional (繁體)": "zh-tw",
        "Coreano (한국어)": "ko",
        "Francês (Français)": "fr",
        "Alemão (Deutsch)": "de",
        "Italiano (Italiano)": "it",
        "Árabe (العربية)": "ar",
        "Hindi (हिन्दी)": "hi",
        "Turco (Türkçe)": "tr",
        "Polonês (Polski)": "pl"
    }

    TARGET_LANGUAGES = {
        "Português (PT-BR)": "pt",
        "English (US)": "en",
        "Español (ES)": "es",
        "Français (FR)": "fr",
        "Deutsch (DE)": "de",
        "Italiano (IT)": "it",
        "日本語 (Japanese)": "ja",
        "한국어 (Korean)": "ko",
        "中文 (Chinese)": "zh",
        "Русский (Russian)": "ru"
    }

    THEMES = {
        "Preto (Black)": {"window": "#0d0d0d", "text": "#ffffff", "button": "#1a1a1a", "accent": "#4a9eff"},
        "Cinza (Gray)": {"window": "#2d2d2d", "text": "#ffffff", "button": "#3d3d3d", "accent": "#5c9eff"},
        "Branco (White)": {"window": "#f0f0f0", "text": "#000000", "button": "#e1e1e1", "accent": "#308cc6"}
    }

    TRANSLATIONS = {
        "pt": {
            "title": "Extração - Otimização - Tradução IA - Reinserção",
            "tab1": "🔍 1. Extração", "tab2": "🧠 2. Tradução", "tab3": "📥 3. Reinserção", "tab4": "⚙️ 4. Configurações", "tab5": "🎨 5. Laboratório Gráfico",
            "platform": "Plataforma:", "rom_file": "Arquivo ROM", "no_rom": "⚠️ Nenhuma ROM selecionada",
            "select_rom": "Selecionar ROM", "extract_texts": "📄 Extrair Textos", "optimize_data": "🧹 Otimizar Dados",
            "extraction_progress": "Progresso da Extração", "optimization_progress": "Progresso da Otimização",
            "waiting": "Aguardando início...", "language_config": "🌍 Configuração de Idiomas",
            "source_language": "📖 Idioma de Origem (ROM)", "target_language": "🎯 Idioma de Destino",
            "translation_mode": "Modo de Tradução", "api_config": "Configuração de API", "api_key": "API Key:",
            "workers": "Workers:", "timeout": "Timeout (s):", "use_cache": "Usar cache de traduções",
            "translation_progress": "Progresso da Tradução", "translate_ai": "🤖 Traduzir com IA",
            "stop_translation": "🛑 Parar Tradução",
            "original_rom": "ROM Original", "translated_file": "Arquivo Traduzido", "select_file": "Selecionar Arquivo",
            "output_rom": "💾 ROM Traduzida (Saída)", "reinsertion_progress": "Progresso da Reinserção",
            "reinsert": "Reinserir Tradução", "theme": "🎨 Tema Visual", "ui_language": "🌐 Idioma da Interface",
            "font_family": "🔤 Fonte da Interface",
            "log": "Log de Operações", "restart": "Reiniciar", "exit": "Sair",
            "developer": "Desenvolvido por: Celso (Programador Solo)", "in_dev": "EM DESENVOLVIMENTO",
            "file_to_translate": "📄 Arquivo para Traduzir (Otimizado)", "no_file": "Nenhum arquivo selecionado",
            "help_support": "🆘 Ajuda e Suporte", "manual_guide": "📘 Guia de Uso Profissional:",
            "contact_support": "📧 Dúvidas? Entre em contato:",
            "btn_stop": "Parar Tradução", "btn_close": "Fechar",
            "roadmap_item": "Próximos Consoles (Roadmap)...", "roadmap_title": "Roadmap",
            "roadmap_desc": "Plataformas em desenvolvimento:",
            "theme_black": "Preto", "theme_gray": "Cinza", "theme_white": "Branco",

            "gfx_toolbar": "Controles de Visualização", "gfx_format": "Formato:", "gfx_zoom": "Zoom:",
            "gfx_palette": "Paleta:", "gfx_offset": "Endereço (Hex):", "gfx_tiles_per_row": "Largura:",
            "gfx_num_tiles": "Núm. Tiles:", "gfx_canvas": "Visualizador de Tiles",
            "gfx_load_rom": "📂 Carregue uma ROM na Aba 1 para visualizar aqui",
            "gfx_navigation_hint": "Dica: Use as setas do teclado para navegar. Scroll para Zoom.",
            "gfx_analysis": "Ferramentas de Análise", "gfx_editing": "Ferramentas de Edição",
            "gfx_btn_sniffer": "🔍 Detectar Fontes", "gfx_btn_entropy": "📊 Scanner de Compressão",
            "gfx_btn_export": "📥 Exportar PNG", "gfx_btn_import": "📤 Importar e Reinserir",
            "gfx_entropy_group": "Análise de Entropia de Shannon",
            "gfx_entropy_click": "Clique em 'Scanner de Entropia' para analisar...",
            "gfx_btn_prev": "◀ Página Anterior", "gfx_btn_next": "Próxima Página ▶",

            "manual_gfx_title": "🎨 Guia: Edição Gráfica Avançada",
            "manual_gfx_body": "FORMATOS DE TILES POR CONSOLE:\n\n"
                            "• SNES: 4bpp (16 cores por tile)\n"
                            "• Game Boy: 2bpp (4 cores por tile)\n"
                            "• Game Boy Color: 2bpp (4 cores)\n"
                            "• NES: 2bpp (4 cores)\n"
                            "• GBA: 4bpp ou 8bpp\n"
                            "• PS1: 4bpp ou 8bpp\n\n"
                            "WORKFLOW RECOMENDADO:\n\n"
                            "1. Exporte os tiles para PNG\n"
                            "2. Edite no Paint/Photoshop SEM mudar a paleta de cores\n"
                            "3. Importe de volta - o sistema reconverte automaticamente\n\n"
                            "IMPORTANTE: Não adicione cores novas! Use apenas as cores existentes no PNG exportado."
        },
        "en": {
            "title": "Extraction - Optimization - AI Translation - Reinsertion",
            "tab1": "🔍 1. Extraction", "tab2": "🧠 2. Translation", "tab3": "📥 3. Reinsertion", "tab4": "⚙️ 4. Settings", "tab5": "🎨 5. Graphics Lab",
            "platform": "Platform:", "rom_file": "ROM File", "no_rom": "⚠️ No ROM selected",
            "select_rom": "Select ROM", "extract_texts": "📄 Extract Texts", "optimize_data": "🧹 Optimize Data",
            "extraction_progress": "Extraction Progress", "optimization_progress": "Optimization Progress",
            "waiting": "Waiting...", "language_config": "🌍 Language Configuration",
            "source_language": "📖 Source Language (ROM)", "target_language": "🎯 Target Language",
            "translation_mode": "Translation Mode", "api_config": "API Configuration", "api_key": "API Key:",
            "workers": "Workers:", "timeout": "Timeout (s):", "use_cache": "Use translation cache",
            "translation_progress": "Translation Progress", "translate_ai": "🤖 Translate with AI",
            "stop_translation": "🛑 Stop Translation",
            "original_rom": "Original ROM", "translated_file": "Translated File", "select_file": "Select File",
            "output_rom": "💾 Translated ROM (Output)", "reinsertion_progress": "Reinsertion Progress",
            "reinsert": "Reinsert Translation", "theme": "🎨 Visual Theme", "ui_language": "🌐 Interface Language",
            "font_family": "🔤 Font Family",
            "log": "Operations Log", "restart": "Restart", "exit": "Exit",
            "developer": "Developed by: Celso (Solo Programmer)", "in_dev": "IN DEVELOPMENT",
            "file_to_translate": "📄 File to Translate (Optimized)", "no_file": "No file selected",
            "help_support": "🆘 Help & Support", "manual_guide": "📘 Professional User Guide:",
            "contact_support": "📧 Questions? Contact us:",
            "btn_stop": "Stop Translation", "btn_close": "Close",
            "roadmap_item": "Upcoming Consoles (Roadmap)...", "roadmap_title": "Roadmap",
            "roadmap_desc": "Platforms in development:","roadmap_cat_playstation": "PlayStation",
            "roadmap_cat_nintendo_classic": "Nintendo Classic",
            "roadmap_cat_nintendo_portable": "Nintendo Portable",
            "roadmap_cat_sega": "Sega",
            "roadmap_cat_xbox": "Xbox",
            "roadmap_cat_other": "Other",
            "theme_black": "Black", "theme_gray": "Gray", "theme_white": "White",

            "gfx_toolbar": "Visualization Controls", "gfx_format": "Format:", "gfx_zoom": "Zoom:",
            "gfx_palette": "Palette:", "gfx_offset": "Address (Hex):", "gfx_tiles_per_row": "Width:",
            "gfx_num_tiles": "Num. Tiles:", "gfx_canvas": "Tile Viewer",
            "gfx_load_rom": "📂 Load a ROM in Tab 1 to view here",
            "gfx_navigation_hint": "Tip: Use keyboard arrows to navigate. Scroll to Zoom.",
            "gfx_analysis": "Analysis Tools", "gfx_editing": "Editing Tools",
            "gfx_btn_sniffer": "🔍 Detect Fonts", "gfx_btn_entropy": "📊 Compression Scanner",
            "gfx_btn_export": "📥 Export PNG", "gfx_btn_import": "📤 Import and Reinsert",
            "gfx_entropy_group": "Shannon Entropy Analysis",
            "gfx_entropy_click": "Click 'Entropy Scanner' to analyze...",
            "gfx_btn_prev": "◀ Previous Page", "gfx_btn_next": "Next Page ▶",

            "manual_gfx_title": "🎨 Guide: Advanced Graphics Editing",
            "manual_gfx_body": "TILE FORMATS BY CONSOLE:\n\n"
                            "• SNES: 4bpp (16 colors per tile)\n"
                            "• Game Boy: 2bpp (4 colors per tile)\n"
                            "• Game Boy Color: 2bpp (4 colors)\n"
                            "• NES: 2bpp (4 colors)\n"
                            "• GBA: 4bpp or 8bpp\n"
                            "• PS1: 4bpp or 8bpp\n\n"
                            "RECOMMENDED WORKFLOW:\n\n"
                            "1. Export tiles to PNG\n"
                            "2. Edit in Paint/Photoshop WITHOUT changing color palette\n"
                            "3. Import back - system auto-converts to tile format\n\n"
                            "IMPORTANT: Don't add new colors! Use only existing colors from exported PNG."

        },
        "es": {
            "title": "Extracción - Optimización - Traducción IA - Reinserción",
            "tab1": "🔍 1. Extracción", "tab2": "🧠 2. Traducción", "tab3": "📥 3. Reinserción", "tab4": "⚙️ Configuración",
            "platform": "Plataforma:", "rom_file": "Archivo ROM", "no_rom": "⚠️ Ninguna ROM seleccionada",
            "select_rom": "Seleccionar ROM", "extract_texts": "📄 Extraer Textos", "optimize_data": "🧹 Optimizar Datos",
            "extraction_progress": "Progreso de Extracción", "optimization_progress": "Progreso de Optimización",
            "waiting": "Esperando inicio...", "language_config": "🌍 Configuración de Idiomas",
            "source_language": "📖 Idioma de Origen (ROM)", "target_language": "🎯 Idioma de Destino",
            "translation_mode": "Modo de Traducción", "api_config": "Configuración de API", "api_key": "Clave API:",
            "workers": "Workers:", "timeout": "Timeout (s):", "use_cache": "Usar caché de traducciones",
            "translation_progress": "Progreso de Traducción", "translate_ai": "🤖 Traducir con IA",
            "stop_translation": "🛑 Detener Traducción",
            "original_rom": "ROM Original", "translated_file": "Archivo Traducido", "select_file": "Seleccionar Archivo",
            "output_rom": "💾 ROM Traducida (Salida)", "reinsertion_progress": "Progreso de Reinserción",
            "reinsert": "Reinsertar Traducción", "theme": "🎨 Tema Visual", "ui_language": "🌐 Idioma de la Interfaz",
            "font_family": "🔤 Familia de Fuente",
            "log": "Registro de Operaciones", "restart": "Reiniciar", "exit": "Salir",
            "developer": "Desarrollado por: Celso (Programador Solo)", "in_dev": "EN DESARROLLO",
            "file_to_translate": "📄 Archivo para Traducir (Optimizado)", "no_file": "Ningún archivo seleccionado",
            "help_support": "🆘 Ayuda y Soporte", "manual_guide": "📘 Guía de Uso Profesional:",
            "contact_support": "📧 ¿Preguntas? Contáctenos:",
            "btn_stop": "Detener Traducción", "btn_close": "Cerrar",
            "roadmap_item": "Próximas Consolas (Roadmap)...", "roadmap_title": "Roadmap",
            "roadmap_desc": "Plataformas en desarrollo:",
            "roadmap_cat_playstation": "PlayStation",
            "roadmap_cat_nintendo_classic": "Nintendo Classic",
            "roadmap_cat_nintendo_portable": "Nintendo Portable",
            "roadmap_cat_sega": "Sega",
            "roadmap_cat_xbox": "Xbox",
            "roadmap_cat_other": "Otro",
            "theme_black": "Negro", "theme_gray": "Gris", "theme_white": "Blanco"
        },
        "fr": {
            "title": "Extraction - Optimisation - Traduction IA - Réinsertion",
            "tab1": "🔍 1. Extraction", "tab2": "🧠 2. Traduction", "tab3": "📥 3. Réinsertion", "tab4": "⚙️ Paramètres",
            "platform": "Plateforme:", "rom_file": "Fichier ROM", "no_rom": "⚠️ Aucune ROM sélectionnée",
            "select_rom": "Sélectionner ROM", "extract_texts": "📄 Extraire Textes", "optimize_data": "🧹 Optimiser Données",
            "extraction_progress": "Progression de l'Extraction", "optimization_progress": "Progression de l'Optimisation",
            "waiting": "En attente...", "language_config": "🌍 Configuration des Langues",
            "source_language": "📖 Langue Source (ROM)", "target_language": "🎯 Langue Cible",
            "translation_mode": "Mode de Traduction", "api_config": "Configuration API", "api_key": "Clé API:",
            "workers": "Workers:", "timeout": "Timeout (s):", "use_cache": "Utiliser le cache de traduction",
            "translation_progress": "Progression de la Traduction", "translate_ai": "🤖 Traduire avec IA",
            "stop_translation": "🛑 Arrêter Traduction",
            "original_rom": "ROM Originale", "translated_file": "Fichier Traduit", "select_file": "Sélectionner Fichier",
            "output_rom": "💾 ROM Traduite (Sortie)", "reinsertion_progress": "Progression de Réinsertion",
            "reinsert": "Réinsérer Traduction", "theme": "🎨 Thème Visuel", "ui_language": "🌐 Langue de l'Interface",
            "font_family": "🔤 Famille de Police",
            "log": "Journal des Opérations", "restart": "Redémarrer", "exit": "Quitter",
            "developer": "Développé par: Celso (Programmeur Solo)", "in_dev": "EN DÉVELOPPEMENT",
            "file_to_translate": "📄 Fichier à Traduire (Optimisé)", "no_file": "Aucun fichier sélectionné",
            "help_support": "🆘 Aide et Support", "manual_guide": "📘 Guide d'Utilisation Professionnel:",
            "contact_support": "📧 Questions? Contactez-nous:",
            "btn_stop": "Arrêter la Traduction", "btn_close": "Fermer",
            "roadmap_item": "Consoles à Venir (Roadmap)...", "roadmap_title": "Roadmap",
            "roadmap_desc": "Plateformes en développement:",
            "roadmap_cat_nintendo_classic": "Nintendo Classic",
            "roadmap_cat_nintendo_portable": "Nintendo Portable",
            "roadmap_cat_sega": "Sega",
            "roadmap_cat_xbox": "Xbox",
            "roadmap_cat_other": "Autres",
            "theme_black": "Noir", "theme_gray": "Gris", "theme_white": "Blanc"
        },
        "de": {
            "title": "Extraktion - Optimierung - KI-Übersetzung - Wiedereinfügung",
            "tab1": "🔍 1. Extraktion", "tab2": "🧠 2. Übersetzung", "tab3": "📥 3. Wiedereinfügung", "tab4": "⚙️ Einstellungen",
            "platform": "Plattform:", "rom_file": "ROM-Datei", "no_rom": "⚠️ Keine ROM ausgewählt",
            "select_rom": "ROM auswählen", "extract_texts": "📄 Texte Extrahieren", "optimize_data": "🧹 Daten Optimieren",
            "extraction_progress": "Extraktionsfortschritt", "optimization_progress": "Optimierungsfortschritt",
            "waiting": "Warten...", "language_config": "🌍 Sprachkonfiguration",
            "source_language": "📖 Quellsprache (ROM)", "target_language": "🎯 Zielsprache",
            "translation_mode": "Übersetzungsmodus", "api_config": "API-Konfiguration", "api_key": "API-Schlüssel:",
            "workers": "Workers:", "timeout": "Timeout (s):", "use_cache": "Übersetzungscache verwenden",
            "translation_progress": "Übersetzungsfortschritt", "translate_ai": "🤖 Mit KI Übersetzen",
            "stop_translation": "🛑 Übersetzung Stoppen",
            "original_rom": "Original-ROM", "translated_file": "Übersetzte Datei", "select_file": "Datei auswählen",
            "output_rom": "💾 Übersetzte ROM (Ausgabe)", "reinsertion_progress": "Wiedereinfügungsfortschritt",
            "reinsert": "Übersetzung Einfügen", "theme": "🎨 Visuelles Thema", "ui_language": "🌐 Oberflächensprache",
            "font_family": "🔤 Schriftfamilie",
            "log": "Operationsprotokoll", "restart": "Neustart", "exit": "Beenden",
            "developer": "Entwickelt von: Celso (Solo-Programmierer)", "in_dev": "IN ENTWICKLUNG",
            "file_to_translate": "📄 Zu übersetzende Datei (Optimiert)", "no_file": "Keine Datei ausgewählt",
            "help_support": "🆘 Hilfe und Support", "manual_guide": "📘 Professionelle Benutzeranleitung:",
            "contact_support": "📧 Fragen? Kontaktieren Sie uns:",
            "btn_stop": "Übersetzung Stoppen", "btn_close": "Schließen",
            "roadmap_item": "Kommende Konsolen (Roadmap)...", "roadmap_title": "Roadmap",
            "roadmap_desc": "Plattformen in Entwicklung:",
            "roadmap_cat_playstation": "PlayStation",
            "roadmap_cat_nintendo_classic": "Nintendo Classic",
            "roadmap_cat_nintendo_portable": "Nintendo Portable",
            "roadmap_cat_sega": "Sega",
            "roadmap_cat_xbox": "Xbox",
            "roadmap_cat_other": "Andet",
            "theme_black": "Schwarz", "theme_gray": "Grau", "theme_white": "Weiß"
        },
        "it": {
            "title": "Estrazione - Ottimizzazione - Traduzione IA - Reinserimento",
            "tab1": "🔍 1. Estrazione", "tab2": "🧠 2. Traduzione", "tab3": "📥 3. Reinserimento", "tab4": "⚙️ Impostazioni",
            "platform": "Piattaforma:", "rom_file": "File ROM", "no_rom": "⚠️ Nessuna ROM selezionata",
            "select_rom": "Seleziona ROM", "extract_texts": "📄 Estrai Testi", "optimize_data": "🧹 Ottimizza Dati",
            "extraction_progress": "Progresso Estrazione", "optimization_progress": "Progresso Ottimizzazione",
            "waiting": "In attesa...", "language_config": "🌍 Configurazione Lingue",
            "source_language": "📖 Lingua Sorgente (ROM)", "target_language": "🎯 Lingua Destinazione",
            "translation_mode": "Modalità Traduzione", "api_config": "Configurazione API", "api_key": "Chiave API:",
            "workers": "Workers:", "timeout": "Timeout (s):", "use_cache": "Usa cache traduzioni",
            "translation_progress": "Progresso Traduzione", "translate_ai": "🤖 Traduci con IA",
            "stop_translation": "🛑 Ferma Traduzione",
            "original_rom": "ROM Originale", "translated_file": "File Tradotto", "select_file": "Seleziona File",
            "output_rom": "💾 ROM Tradotta (Output)", "reinsertion_progress": "Progresso Reinserimento",
            "reinsert": "Reinserisci Traduzione", "theme": "🎨 Tema Visivo", "ui_language": "🌐 Lingua Interfaccia",
            "font_family": "🔤 Famiglia di Caratteri",
            "log": "Registro Operazioni", "restart": "Riavvia", "exit": "Esci",
            "developer": "Sviluppato da: Celso (Programmatore Solo)", "in_dev": "IN SVILUPPO",
            "file_to_translate": "📄 File da Tradurre (Ottimizzato)", "no_file": "Nessun file selezionato",
            "help_support": "🆘 Aiuto e Supporto", "manual_guide": "📘 Guida Utente Professionale:",
            "contact_support": "📧 Domande? Contattaci:",
            "btn_stop": "Ferma Traduzione", "btn_close": "Chiudi",
            "roadmap_item": "Prossime Console (Roadmap)...", "roadmap_title": "Roadmap",
            "roadmap_desc": "Piattaforme in sviluppo:",
            "roadmap_cat_playstation": "PlayStation",
            "roadmap_cat_nintendo_classic": "Nintendo Classic",
            "roadmap_cat_nintendo_portable": "Nintendo Portable",
            "roadmap_cat_sega": "Sega",
            "roadmap_cat_xbox": "Xbox",
            "roadmap_cat_other": "Altro",
            "theme_black": "Nero", "theme_gray": "Grigio", "theme_white": "Bianco"
        },
        "ja": {
                "title": "抽出 - 最適化 - AI翻訳 - 再挿入",
                "tab1": "🔍 1. 抽出", "tab2": "🧠 2. 翻訳", "tab3": "📥 3. 再挿入", "tab4": "⚙️ 設定",
                "platform": "プラットフォーム:", "rom_file": "📂 ROMファイル", "no_rom": "⚠️ ROM未選択",
                "select_rom": "📂 ROM選択", "extract_texts": "📄 テキスト抽出", "optimize_data": "🧹 データ最適化",
                "extraction_progress": "抽出進行状況", "optimization_progress": "最適化進行状況",
                "waiting": "待機中...", "language_config": "🌍 言語設定",
                "source_language": "📖 ソース言語 (ROM)", "target_language": "🎯 ターゲット言語",
                "translation_mode": "翻訳モード", "api_config": "API設定", "api_key": "APIキー:",
                "workers": "ワーカー:", "timeout": "タイムアウト (秒):", "use_cache": "翻訳キャッシュを使用",
                "translation_progress": "翻訳進行状況", "translate_ai": "🤖 AIで翻訳",
                "stop_translation": "🛑 翻訳を停止",
                "original_rom": "📂 オリジナルROM", "translated_file": "📄 翻訳済みファイル", "select_file": "📄 ファイル選択",
                "output_rom": "💾 翻訳済みROM (出力)", "reinsertion_progress": "再挿入進行状況",
                "reinsert": "翻訳を再挿入", "theme": "🎨 ビジュアルテーマ", "ui_language": "🌐 インターフェース言語",
                "font_family": "🔤 フォントファミリー",
                "log": "操作ログ", "restart": "再起動", "exit": "終了",
                "developer": "開発者: Celso (ソロプログラマー)", "in_dev": "開発中",
                "file_to_translate": "📄 翻訳するファイル (最適化済み)", "no_file": "📄 ファイル未選択",
                "help_support": "🆘 ヘルプとサポート", "manual_guide": "📘 プロフェッショナルユーザーガイド:",
            "contact_support": "📧 ご質問？お問い合わせ:",
            "btn_stop": "翻訳を停止", "btn_close": "閉じる",
                "roadmap_item": "今後のコンソール (ロードマップ)...", "roadmap_title": "ロードマップ",
                "roadmap_desc": "開発中のプラットフォーム:",
                "roadmap_cat_playstation": "PlayStation",
                "roadmap_cat_nintendo_classic": "Nintendo Classic",
                "roadmap_cat_nintendo_portable": "Nintendo Portable",
                "roadmap_cat_sega": "Sega",
                "roadmap_cat_xbox": "Xbox",
                "roadmap_cat_other": "その他",
                "theme_black": "黒", "theme_gray": "灰色", "theme_white": "白"
            },
        "ko": {
            "title": "추출 - 최적화 - AI 번역 - 재삽입",
            "tab1": "🔍 1. 추출", "tab2": "🧠 2. 번역", "tab3": "📥 3. 재삽입", "tab4": "⚙️ 설정",
            "platform": "플랫폼:", "rom_file": "ROM 파일", "no_rom": "⚠️ ROM 선택 안 됨",
            "select_rom": "ROM 선택", "extract_texts": "📄 텍스트 추출", "optimize_data": "🧹 데이터 최적화",
            "extraction_progress": "추출 진행률", "optimization_progress": "최적화 진행률",
            "waiting": "대기 중...", "language_config": "🌍 언어 설정",
            "source_language": "📖 소스 언어 (ROM)", "target_language": "🎯 대상 언어",
            "translation_mode": "번역 모드", "api_config": "API 구성", "api_key": "API 키:",
            "workers": "작업자:", "timeout": "타임아웃 (초):", "use_cache": "번역 캐시 사용",
            "translation_progress": "번역 진행률", "translate_ai": "🤖 AI로 번역",
            "stop_translation": "🛑 번역 중지",
            "original_rom": "원본 ROM", "translated_file": "번역된 파일", "select_file": "파일 선택",
            "output_rom": "💾 번역된 ROM (출력)", "reinsertion_progress": "재삽입 진행률",
            "reinsert": "번역 재삽입", "theme": "🎨 비주얼 테마", "ui_language": "🌐 인터페이스 언어",
            "font_family": "🔤 글꼴 패밀리",
            "log": "작업 로그", "restart": "재시작", "exit": "종료",
            "developer": "개발자: Celso (솔로 프로그래머)", "in_dev": "개발 중",
            "file_to_translate": "📄 번역할 파일 (최적화됨)", "no_file": "파일 선택 안 됨",
            "help_support": "🆘 도움말 및 지원", "manual_guide": "📘 전문 사용자 가이드:",
            "contact_support": "📧 질문이 있으신가요? 문의하기:",
            "btn_stop": "번역 중지", "btn_close": "닫기",
            "roadmap_item": "향후 콘솔 (로드맵)...", "roadmap_title": "로드맵",
            "roadmap_desc": "개발 중인 플랫폼:",
            "roadmap_cat_playstation": "플레이스테이션",
            "roadmap_cat_nintendo_classic": "닌텐도 클래식",
            "roadmap_cat_nintendo_portable": "닌텐도 포터블",
            "roadmap_cat_sega": "세가",
            "roadmap_cat_xbox": "엑스박스",
            "roadmap_cat_other": "기타",
            "roadmap_cat_playstation": "peulleiseuteisyeon",
            "roadmap_cat_nintendo_classic": "nintendo keullaesig",
            "roadmap_cat_nintendo_portable": "nintendo poteobeul",
            "roadmap_cat_sega": "sega",
            "roadmap_cat_xbox": "egseubagseu",
            "roadmap_cat_other": "gita",
            "theme_black": "검정", "theme_gray": "회색", "theme_white": "흰색"

        },
        "zh": {
            "title": "提取 - 优化 - AI翻译 - 重新插入",
            "tab1": "🔍 1. 提取", "tab2": "🧠 2. 翻译", "tab3": "📥 3. 重新插入", "tab4": "⚙️ 设置",
            "platform": "平台:", "rom_file": "ROM文件", "no_rom": "⚠️ 未选择ROM",
            "select_rom": "选择ROM", "extract_texts": "📄 提取文本", "optimize_data": "🧹 优化数据",
            "extraction_progress": "提取进度", "optimization_progress": "优化进度",
            "waiting": "等待中...", "language_config": "🌍 语言配置",
            "source_language": "📖 源语言 (ROM)", "target_language": "🎯 目标语言",
            "translation_mode": "翻译模式", "api_config": "API配置", "api_key": "API密钥:",
            "workers": "工作线程:", "timeout": "超时 (秒):", "use_cache": "使用翻译缓存",
            "translation_progress": "翻译进度", "translate_ai": "🤖 使用AI翻译",
            "stop_translation": "🛑 停止翻译",
            "original_rom": "原始ROM", "translated_file": "翻译文件", "select_file": "选择文件",
            "output_rom": "💾 翻译ROM (输出)", "reinsertion_progress": "重新插入进度",
            "reinsert": "重新插入翻译", "theme": "🎨 视觉主题", "ui_language": "🌐 界面语言",
            "font_family": "🔤 字体系列",
            "log": "操作日志", "restart": "重启", "exit": "退出",
            "developer": "开发者: Celso (独立程序员)", "in_dev": "开发中",
            "file_to_translate": "📄 要翻译的文件 (已优化)", "no_file": "未选择文件",
            "help_support": "🆘 帮助和支持", "manual_guide": "📘 专业用户指南:",
            "contact_support": "📧 有疑问？联系我们:",
            "btn_stop": "停止翻译", "btn_close": "关闭",
            "roadmap_item": "即将推出的游戏机 (路线图)...", "roadmap_title": "路线图",
            "roadmap_desc": "开发中的平台:",
            "theme_black": "黑色", "theme_gray": "灰色", "theme_white": "白色"
        },
        "ru": {
            "title": "Извлечение - Оптимизация - ИИ Перевод - Реинсерция",
            "tab1": "🔍 1. Извлечение", "tab2": "🧠 2. Перевод", "tab3": "📥 3. Реинсерция", "tab4": "⚙️ Настройки",
            "platform": "Платформа:", "rom_file": "ROM Файл", "no_rom": "⚠️ ROM не выбран",
            "select_rom": "Выбрать ROM", "extract_texts": "📄 Извлечь Тексты", "optimize_data": "🧹 Оптимизировать Данные",
            "extraction_progress": "Прогресс Извлечения", "optimization_progress": "Прогресс Оптимизации",
            "waiting": "Ожидание...", "language_config": "🌍 Настройка Языков",
            "source_language": "📖 Исходный Язык (ROM)", "target_language": "🎯 Целевой Язык",
            "translation_mode": "Режим Перевода", "api_config": "Настройка API", "api_key": "API Ключ:",
            "workers": "Воркеры:", "timeout": "Таймаут (сек):", "use_cache": "Использовать кэш переводов",
            "translation_progress": "Прогресс Перевода", "translate_ai": "🤖 Перевести с ИИ",
            "stop_translation": "🛑 Остановить Перевод",
            "original_rom": "Оригинальный ROM", "translated_file": "Переведенный Файл", "select_file": "Выбрать Файл",
            "output_rom": "💾 Переведенный ROM (Вывод)", "reinsertion_progress": "Прогресс Реинсерции",
            "reinsert": "Реинсертировать Перевод", "theme": "🎨 Визуальная Тема", "ui_language": "🌐 Язык Интерфейса",
            "font_family": "🔤 Семейство Шрифтов",
            "log": "Журнал Операций", "restart": "Перезапустить", "exit": "Выход",
            "developer": "Разработчик: Celso (Соло Программист)", "in_dev": "В РАЗРАБОТКЕ",
            "file_to_translate": "📄 Файл для Перевода (Оптимизирован)", "no_file": "Файл не выбран",
            "help_support": "🆘 Помощь и Поддержка", "manual_guide": "📘 Профессиональное Руководство:",
            "contact_support": "📧 Вопросы? Свяжитесь с нами:",
            "btn_stop": "Остановить Перевод", "btn_close": "Закрыть",
            "roadmap_item": "Предстоящие Консоли (Дорожная карта)...", "roadmap_title": "Дорожная карта",
            "roadmap_desc": "Платформы в разработке:",
            "theme_black": "Чёрный", "theme_gray": "Серый", "theme_white": "Белый"
        },
        "ar": {
            "title": "استخراج - تحسين - ترجمة الذكاء الاصطناعي - إعادة إدراج",
            "tab1": "🔍 1. استخراج", "tab2": "🧠 2. ترجمة", "tab3": "📥 3. إعادة إدراج", "tab4": "⚙️ إعدادات",
            "platform": "منصة:", "rom_file": "ملف ROM", "no_rom": "لم يتم تحديد ROM",
            "select_rom": "اختر ROM", "extract_texts": "استخراج النصوص", "optimize_data": "🧹 تحسين البيانات",
            "extraction_progress": "تقدم الاستخراج", "optimization_progress": "تقدم التحسين",
            "waiting": "في الانتظار...", "language_config": "🌍 تكوين اللغة",
            "source_language": "📖 اللغة المصدر (ROM)", "target_language": "🎯 اللغة المستهدفة",
            "translation_mode": "وضع الترجمة", "api_config": "تكوين API", "api_key": "مفتاح API:",
            "workers": "العمال:", "timeout": "المهلة (ثانية):", "use_cache": "استخدام ذاكرة التخزين المؤقت للترجمة",
            "translation_progress": "تقدم الترجمة", "translate_ai": "🤖 ترجمة بالذكاء الاصطناعي",
            "original_rom": "ROM الأصلي", "translated_file": "الملف المترجم", "select_file": "اختر ملف",
            "output_rom": "💾 ROM المترجم (الإخراج)", "reinsertion_progress": "تقدم إعادة الإدراج",
            "reinsert": "إعادة إدراج الترجمة", "theme": "🎨 السمة البصرية", "ui_language": "🌐 لغة الواجهة",
            "font_family": "🔤 عائلة الخط",
            "log": "سجل العمليات", "restart": "إعادة التشغيل", "exit": "خروج",
            "developer": "تطوير: Celso (مبرمج منفرد)", "in_dev": "قيد التطوير",
            "file_to_translate": "📄 ملف للترجمة (محسّن)", "no_file": "لم يتم تحديد ملف",
            "help_support": "🆘 المساعدة والدعم", "manual_guide": "📘 دليل المستخدم المحترف:",
            "contact_support": "📧 أسئلة؟ اتصل بنا:",
            "btn_stop": "إيقاف الترجمة", "btn_close": "إغلاق",
            "roadmap_item": "وحدات التحكم القادمة (خارطة الطريق)...", "roadmap_title": "خارطة الطريق",
            "roadmap_desc": "المنصات قيد التطوير:",
            "theme_black": "أسود", "theme_gray": "رمادي", "theme_white": "أبيض"
        },
        "hi": {
            "title": "निष्कर्षण - अनुकूलन - एआई अनुवाद - पुनः सम्मिलन",
            "tab1": "🔍 1. निष्कर्षण", "tab2": "🧠 2. अनुवाद", "tab3": "📥 3. पुनः सम्मिलन", "tab4": "⚙️ सेटिंग्स",
            "platform": "मंच:", "rom_file": "ROM फ़ाइल", "no_rom": "कोई ROM चयनित नहीं",
            "select_rom": "ROM चुनें", "extract_texts": "पाठ निकालें", "optimize_data": "🧹 डेटा अनुकूलित करें",
            "extraction_progress": "निष्कर्षण प्रगति", "optimization_progress": "अनुकूलन प्रगति",
            "waiting": "प्रतीक्षा में...", "language_config": "🌍 भाषा कॉन्फ़िगरेशन",
            "source_language": "📖 स्रोत भाषा (ROM)", "target_language": "🎯 लक्ष्य भाषा",
            "translation_mode": "अनुवाद मोड", "api_config": "API कॉन्फ़िगरेशन", "api_key": "API कुंजी:",
            "workers": "वर्कर्स:", "timeout": "टाइमआउट (सेकंड):", "use_cache": "अनुवाद कैश का उपयोग करें",
            "translation_progress": "अनुवाद प्रगति", "translate_ai": "🤖 एआई से अनुवाद करें",
            "original_rom": "मूल ROM", "translated_file": "अनुवादित फ़ाइल", "select_file": "फ़ाइल चुनें",
            "output_rom": "💾 अनुवादित ROM (आउटपुट)", "reinsertion_progress": "पुनः सम्मिलन प्रगति",
            "reinsert": "अनुवाद पुनः सम्मिलित करें", "theme": "🎨 दृश्य थीम", "ui_language": "🌐 इंटरफ़ेस भाषा",
            "font_family": "🔤 फ़ॉन्ट परिवार",
            "log": "ऑपरेशन लॉग", "restart": "पुनः आरंभ करें", "exit": "बाहर निकलें",
            "developer": "विकसित: Celso (एकल प्रोग्रामर)", "in_dev": "विकास में",
            "file_to_translate": "📄 अनुवाद करने के लिए फ़ाइल (अनुकूलित)", "no_file": "कोई फ़ाइल चयनित नहीं",
            "help_support": "🆘 सहायता और समर्थन", "manual_guide": "📘 पेशेवर उपयोगकर्ता गाइड:",
            "contact_support": "📧 सवाल? हमसे संपर्क करें:",
            "btn_stop": "अनुवाद रोकें", "btn_close": "बंद करें",
            "roadmap_item": "आगामी कंसोल (रोडमैप)...", "roadmap_title": "रोडमैप",
            "roadmap_desc": "विकास में प्लेटफ़ॉर्म:",
            "theme_black": "काला", "theme_gray": "स्लेटी", "theme_white": "सफेद"
        },
        "tr": {
            "title": "Çıkarma - Optimizasyon - Yapay Zeka Çevirisi - Yeniden Ekleme",
            "tab1": "🔍 1. Çıkarma", "tab2": "🧠 2. Çeviri", "tab3": "📥 3. Yeniden Ekleme", "tab4": "⚙️ Ayarlar",
            "platform": "Platform:", "rom_file": "ROM Dosyası", "no_rom": "ROM seçilmedi",
            "select_rom": "ROM Seç", "extract_texts": "METİNLERİ ÇIKAR", "optimize_data": "🧹 VERİLERİ OPTİMİZE ET",
            "extraction_progress": "Çıkarma İlerlemesi", "optimization_progress": "Optimizasyon İlerlemesi",
            "waiting": "Bekleniyor...", "language_config": "🌍 Dil Yapılandırması",
            "source_language": "📖 Kaynak Dil (ROM)", "target_language": "🎯 Hedef Dil",
            "translation_mode": "Çeviri Modu", "api_config": "API Yapılandırması", "api_key": "API Anahtarı:",
            "workers": "İşçiler:", "timeout": "Zaman Aşımı (sn):", "use_cache": "Çeviri önbelleğini kullan",
            "translation_progress": "Çeviri İlerlemesi", "translate_ai": "🤖 YAPAY ZEKA İLE ÇEVİR",
            "original_rom": "Orijinal ROM", "translated_file": "Çevrilmiş Dosya", "select_file": "Dosya Seç",
            "output_rom": "💾 Çevrilmiş ROM (Çıktı)", "reinsertion_progress": "Yeniden Ekleme İlerlemesi",
            "reinsert": "ÇEVİRİYİ YENİDEN EKLE", "theme": "🎨 Görsel Tema", "ui_language": "🌐 Arayüz Dili",
            "font_family": "🔤 Yazı Tipi Ailesi",
            "log": "İşlem Günlüğü", "restart": "YENİDEN BAŞLAT", "exit": "ÇIKIŞ",
            "developer": "Geliştirici: Celso (Solo Programcı)", "in_dev": "GELİŞTİRMEDE",
            "file_to_translate": "📄 Çevrilecek Dosya (Optimize Edilmiş)", "no_file": "Dosya seçilmedi",
            "help_support": "🆘 Yardım ve Destek", "manual_guide": "📘 Profesyonel Kullanıcı Kılavuzu:",
            "contact_support": "📧 Sorularınız mı var? Bize ulaşın:",
            "btn_stop": "ÇEVİRİYİ DURDUR", "btn_close": "KAPAT",
            "roadmap_item": "Yaklaşan Konsollar (Yol Haritası)...", "roadmap_title": "Yol Haritası",
            "roadmap_desc": "Geliştirme aşamasındaki platformlar:",
            "theme_black": "Siyah", "theme_gray": "Gri", "theme_white": "Beyaz"
        },
        "pl": {
            "title": "Ekstrakcja - Optymalizacja - Tłumaczenie AI - Reinsercja",
            "tab1": "🔍 1. Ekstrakcja", "tab2": "🧠 2. Tłumaczenie", "tab3": "📥 3. Reinsercja", "tab4": "⚙️ Ustawienia",
            "platform": "Platforma:", "rom_file": "Plik ROM", "no_rom": "Nie wybrano ROM",
            "select_rom": "Wybierz ROM", "extract_texts": "WYODRĘBNIJ TEKSTY", "optimize_data": "🧹 OPTYMALIZUJ DANE",
            "extraction_progress": "Postęp Ekstrakcji", "optimization_progress": "Postęp Optymalizacji",
            "waiting": "Oczekiwanie...", "language_config": "🌍 Konfiguracja Języka",
            "source_language": "📖 Język Źródłowy (ROM)", "target_language": "🎯 Język Docelowy",
            "translation_mode": "Tryb Tłumaczenia", "api_config": "Konfiguracja API", "api_key": "Klucz API:",
            "workers": "Pracownicy:", "timeout": "Limit czasu (s):", "use_cache": "Użyj pamięci podręcznej tłumaczeń",
            "translation_progress": "Postęp Tłumaczenia", "translate_ai": "🤖 TŁUMACZ Z AI",
            "original_rom": "Oryginalny ROM", "translated_file": "Przetłumaczony Plik", "select_file": "Wybierz Plik",
            "output_rom": "💾 Przetłumaczony ROM (Wyjście)", "reinsertion_progress": "Postęp Reinsercji",
            "reinsert": "WSTAW TŁUMACZENIE", "theme": "🎨 Motyw Wizualny", "ui_language": "🌐 Język Interfejsu",
            "font_family": "🔤 Rodzina Czcionek",
            "log": "Dziennik Operacji", "restart": "RESTART", "exit": "WYJŚCIE",
            "developer": "Opracowane przez: Celso (Programista Solo)", "in_dev": "W ROZWOJU",
            "file_to_translate": "📄 Plik do Tłumaczenia (Zoptymalizowany)", "no_file": "Nie wybrano pliku",
            "help_support": "🆘 Pomoc i Wsparcie", "manual_guide": "📘 Profesjonalny Przewodnik:",
            "contact_support": "📧 Pytania? Skontaktuj się z nami:",
            "btn_stop": "ZATRZYMAJ TŁUMACZENIE", "btn_close": "ZAMKNIJ",
            "roadmap_item": "Nadchodzące Konsole (Mapa drogowa)...", "roadmap_title": "Mapa drogowa",
            "roadmap_desc": "Platformy w rozwoju:",
            "theme_black": "Czarny", "theme_gray": "Szary", "theme_white": "Biały"
        },
        "nl": {
            "title": "Extractie - Optimalisatie - AI Vertaling - Herinvoer",
            "tab1": "🔍 1. Extractie", "tab2": "🧠 2. Vertaling", "tab3": "📥 3. Herinvoer", "tab4": "⚙️ Instellingen",
            "platform": "Platform:", "rom_file": "ROM Bestand", "no_rom": "Geen ROM geselecteerd",
            "select_rom": "Selecteer ROM", "extract_texts": "TEKSTEN EXTRAHEREN", "optimize_data": "🧹 DATA OPTIMALISEREN",
            "extraction_progress": "Extractie Voortgang", "optimization_progress": "Optimalisatie Voortgang",
            "waiting": "Wachten...", "language_config": "🌍 Taalconfiguratie",
            "source_language": "📖 Brontaal (ROM)", "target_language": "🎯 Doeltaal",
            "translation_mode": "Vertaalmodus", "api_config": "API Configuratie", "api_key": "API Sleutel:",
            "workers": "Workers:", "timeout": "Time-out (s):", "use_cache": "Gebruik vertaalcache",
            "translation_progress": "Vertaalvoortgang", "translate_ai": "🤖 VERTALEN MET AI",
            "original_rom": "Originele ROM", "translated_file": "Vertaald Bestand", "select_file": "Selecteer Bestand",
            "output_rom": "💾 Vertaalde ROM (Uitvoer)", "reinsertion_progress": "Herinvoer Voortgang",
            "reinsert": "VERTALING HERINVOEREN", "theme": "🎨 Visueel Thema", "ui_language": "🌐 Interface Taal",
            "font_family": "🔤 Lettertypefamilie",
            "log": "Operatielogboek", "restart": "HERSTARTEN", "exit": "AFSLUITEN",
            "developer": "Ontwikkeld door: Celso (Solo Programmeur)", "in_dev": "IN ONTWIKKELING",
            "file_to_translate": "📄 Te vertalen bestand (Geoptimaliseerd)", "no_file": "Geen bestand geselecteerd",
            "help_support": "🆘 Hulp en Ondersteuning", "manual_guide": "📘 Professionele Gebruikersgids:",
            "contact_support": "📧 Vragen? Neem contact op:",
            "btn_stop": "VERTALING STOPPEN", "btn_close": "SLUITEN",
            "roadmap_item": "Komende Consoles (Roadmap)...", "roadmap_title": "Roadmap",
            "roadmap_desc": "Platforms in ontwikkeling:",
            "theme_black": "Zwart", "theme_gray": "Grijs", "theme_white": "Wit"
        }
    }
@classmethod
def ensure_directories(cls):
        cls.ROMS_DIR.mkdir(exist_ok=True, parents=True)
        cls.SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


class ThemeManager:
    @staticmethod
    def apply(app: QApplication, theme_name: str):
        if theme_name not in ProjectConfig.THEMES:
            theme_name = "Preto (Black)"
        theme = ProjectConfig.THEMES[theme_name]
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(theme["window"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(theme["text"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(theme["window"]))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(theme["button"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(theme["text"]))
        palette.setColor(QPalette.ColorRole.Button, QColor(theme["button"]))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme["text"]))
        palette.setColor(QPalette.ColorRole.BrightText, QColor("#ff0000"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(theme["accent"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#000000"))
        app.setPalette(palette)


def _obfuscate_key(key: str) -> str:
    """Ofusca a API key usando base64 (não é criptografia real)."""
    if not key:
        return ""
    return base64.b64encode(key.encode()).decode()


def _deobfuscate_key(obfuscated: str) -> str:
    """Decodifica a API key ofuscada."""
    if not obfuscated:
        return ""
    try:
        return base64.b64decode(obfuscated.encode()).decode()
    except:
        return ""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.original_rom_path: Optional[str] = None
        self.extracted_file: Optional[str] = None
        self.optimized_file: Optional[str] = None
        self.translated_file: Optional[str] = None

        self.current_theme = "Preto (Black)"
        self.current_ui_lang = "en"
        self.current_font_family = "Padrão (Segoe UI + CJK Fallback)"

        # Referências para workers
        self.extract_thread: Optional[ProcessThread] = None
        self.optimize_thread: Optional[OptimizationWorker] = None
        self.translate_thread: Optional[GeminiWorker] = None
        self.reinsert_thread: Optional[ReinsertionWorker] = None

        # COMMERCIAL: Anti-Piracy Check
        self.check_eula_and_license()

        self.init_ui()
        self.load_config()
        self.refresh_ui_labels()  # Atualiza labels com o idioma carregado
        ProjectConfig.ensure_directories()
        self.on_mode_changed(self.mode_combo.currentIndex())

    def tr(self, key: str) -> str:
        """
        i18n translation with triple fallback:
        1. Current UI language (self.current_ui_lang)
        2. English (en) - universal fallback
        3. [KEY_NAME] - debug mode (makes missing keys visible)
        """
        # Level 1: Current language
        current_translations = ProjectConfig.load_translations(self.current_ui_lang)
        translation = current_translations.get(key)

        # Level 2: Fallback to English
        if translation is None:
            en_translations = ProjectConfig.load_translations("en")
            translation = en_translations.get(key)

        # Level 3: Visual debug fallback
        if translation is None:
            return f"[{key}]"

        return translation

    def get_translated_theme_name(self, internal_key: str) -> str:
        """Convert internal theme key to translated theme name."""
        translation_key = ProjectConfig.THEME_TRANSLATION_KEYS.get(internal_key)
        if translation_key:
            return self.tr(translation_key)
        return internal_key  # Fallback to internal key if not found

    def get_internal_theme_key(self, translated_name: str) -> str:
        """Convert translated theme name back to internal theme key."""
        # Check all internal keys to find which one translates to this name
        for internal_key, translation_key in ProjectConfig.THEME_TRANSLATION_KEYS.items():
            if self.tr(translation_key) == translated_name:
                return internal_key
        return translated_name  # Fallback if not found

    def get_all_translated_theme_names(self) -> list:
        """Get all theme names in translated form, maintaining order."""
        translated_names = []
        for internal_key in ProjectConfig.THEMES.keys():
            translated_names.append(self.get_translated_theme_name(internal_key))
        return translated_names

    def get_translated_source_language_name(self, internal_key: str) -> str:
        """Convert internal source language key to translated name."""
        if internal_key == "AUTO-DETECTAR":
            return self.tr("auto_detect")
        return internal_key  # Return as-is for other languages (they have native names)

    def get_internal_source_language_key(self, translated_name: str) -> str:
        """Convert translated source language name back to internal key."""
        if translated_name == self.tr("auto_detect"):
            return "AUTO-DETECTAR"
        return translated_name  # Return as-is for other languages

    def get_all_translated_source_languages(self) -> list:
        """Get all source language names with AUTO-DETECTAR translated."""
        translated_names = []
        for internal_key in ProjectConfig.SOURCE_LANGUAGES.keys():
            translated_names.append(self.get_translated_source_language_name(internal_key))
        return translated_names

    def check_eula_and_license(self):
        """COMMERCIAL: Check EULA acceptance and license activation."""
        # Check EULA
        if not SecurityManager.is_eula_accepted():
            eula_dialog = QDialog(self)
            eula_dialog.setWindowTitle("NeuroROM AI - EULA & Disclaimer")
            eula_dialog.setMinimumSize(700, 600)
            eula_dialog.setModal(True)

            layout = QVBoxLayout(eula_dialog)

            # EULA Text
            eula_text = QTextEdit()
            eula_text.setReadOnly(True)
            eula_text.setPlainText(SecurityManager.EULA_TEXT)
            layout.addWidget(eula_text)

            # Buttons
            button_layout = QHBoxLayout()
            accept_btn = QPushButton("Accept")
            reject_btn = QPushButton("Reject")

            def on_accept():
                SecurityManager.accept_eula()
                eula_dialog.accept()

            def on_reject():
                QMessageBox.critical(
                    eula_dialog,
                    "EULA Required",
                    "You must accept the EULA to use NeuroROM AI."
                )
                sys.exit(0)

            accept_btn.clicked.connect(on_accept)
            reject_btn.clicked.connect(on_reject)

            button_layout.addWidget(reject_btn)
            button_layout.addWidget(accept_btn)
            layout.addLayout(button_layout)

            eula_dialog.exec()

        # Check License
        if not SecurityManager.is_licensed():
            license_dialog = QDialog(self)
            license_dialog.setWindowTitle("NeuroROM AI - License Activation")
            license_dialog.setMinimumSize(500, 300)
            license_dialog.setModal(True)

            layout = QVBoxLayout(license_dialog)

            info_label = QLabel(
                "<h2>License Activation Required</h2>"
                "<p>Enter your Gumroad license key to activate NeuroROM AI.</p>"
                "<p><b>For development:</b> Use <code>DEV-LICENSE</code></p>"
            )
            info_label.setWordWrap(True)
            info_label.setTextFormat(Qt.TextFormat.RichText)
            layout.addWidget(info_label)

            key_label = QLabel("License Key:")
            layout.addWidget(key_label)

            key_input = QLineEdit()
            key_input.setPlaceholderText("NEUROROM-GUMROAD-XXXXXXXXXXXX")
            layout.addWidget(key_input)

            status_label = QLabel("")
            status_label.setStyleSheet("color: red;")
            layout.addWidget(status_label)

            button_layout = QHBoxLayout()
            activate_btn = QPushButton("Activate")
            skip_btn = QPushButton("Exit")

            def on_activate():
                key = key_input.text().strip()
                valid, msg = SecurityManager.validate_license(key)
                if valid:
                    status_label.setStyleSheet("color: green;")
                    status_label.setText("✅ " + msg)
                    QMessageBox.information(
                        license_dialog,
                        "Success",
                        "License activated successfully!\nWelcome to NeuroROM AI."
                    )
                    license_dialog.accept()
                else:
                    status_label.setStyleSheet("color: red;")
                    status_label.setText("❌ " + msg)

            def on_skip():
                QMessageBox.warning(
                    license_dialog,
                    "License Required",
                    "A valid license is required to use NeuroROM AI."
                )
                sys.exit(0)

            activate_btn.clicked.connect(on_activate)
            skip_btn.clicked.connect(on_skip)

            button_layout.addWidget(skip_btn)
            button_layout.addWidget(activate_btn)
            layout.addLayout(button_layout)

            license_dialog.exec()

    def update_window_title(self):
        self.setWindowTitle("NeuroROM AI - Universal Localization Suite v5.3")

    def init_ui(self):
        self.setWindowTitle("NeuroROM AI - Universal Localization Suite v5.3")
        self.setMinimumSize(1200, 800)  # Tamanho mínimo
        self.resize(1400, 900)  # Tamanho inicial (responsivo)
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_extraction_tab(), self.tr("tab1"))
        self.tabs.addTab(self.create_translation_tab(), self.tr("tab2"))
        self.tabs.addTab(self.create_reinsertion_tab(), self.tr("tab3"))
        self.tabs.addTab(self.create_graphics_lab_tab(), self.tr("tab5"))
        self.tabs.addTab(self.create_settings_tab(), self.tr("tab4"))
        left_layout.addWidget(self.tabs)
        main_layout.addWidget(left_panel, 3)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        log_group = QGroupBox(self.tr("log"))
        log_group.setObjectName("log_group")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(400)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group)

        restart_btn = QPushButton(self.tr("restart"))
        restart_btn.setObjectName("restart_btn")
        restart_btn.setMinimumHeight(40)
        restart_btn.setStyleSheet(
            "QPushButton{background-color:#4CAF50;color:white;font-size:12pt;"
            "font-weight:bold;border-radius:5px;}"
            "QPushButton:hover{background-color:#45a049;}"
        )
        restart_btn.clicked.connect(self.restart_application)
        right_layout.addWidget(restart_btn)

        exit_btn = QPushButton(self.tr("exit"))
        exit_btn.setObjectName("exit_btn")
        exit_btn.setMinimumHeight(40)
        exit_btn.setStyleSheet(
            "QPushButton{background-color:#000000;color:#FFFFFF;font-size:12pt;"
            "font-weight:bold;border-radius:5px;}"
            "QPushButton:hover{background-color:#222222;}"
        )
        exit_btn.clicked.connect(self.close)
        right_layout.addWidget(exit_btn)

        # COMMERCIAL: Copyright Footer
        copyright_label = QLabel("Developed by Celso - Programador Solo | © 2025 All Rights Reserved")
        copyright_label.setObjectName("copyright_label")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_label.setStyleSheet("color:#888;font-size:9pt;font-weight:bold;")
        right_layout.addWidget(copyright_label)

        main_layout.addWidget(right_panel, 2)
        self.statusBar().showMessage("NeuroROM AI Ready")
        self.log("Sistema v5.3 iniciado - Correções Aplicadas")

    def create_extraction_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        platform_group = QGroupBox(self.tr("platform"))
        platform_group.setObjectName("platform_group")
        platform_layout = QHBoxLayout()
        self.platform_combo = QComboBox()

        for platform_name, data in ProjectConfig.PLATFORMS.items():
            platform_code = data.get("code", "")

            if platform_code == "separator":
                self.platform_combo.addItem(platform_name)
                index = self.platform_combo.count() - 1
                item = self.platform_combo.model().item(index)
                item.setEnabled(False)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            else:
                # Usa o nome da plataforma diretamente (ex: "Super Nintendo (SNES)")
                self.platform_combo.addItem(platform_name, platform_code)

        self.platform_combo.currentIndexChanged.connect(lambda: self.on_platform_selected())
        platform_layout.addWidget(self.platform_combo)
        platform_group.setLayout(platform_layout)
        layout.addWidget(platform_group)

        rom_group = QGroupBox(self.tr("rom_file"))
        rom_group.setObjectName("rom_file_group")
        rom_layout = QVBoxLayout()
        rom_select_layout = QHBoxLayout()
        self.rom_path_label = QLabel(self.tr("no_rom"))
        self.rom_path_label.setObjectName("rom_path_label")
        rom_select_layout.addWidget(self.rom_path_label)
        self.select_rom_btn = QPushButton(self.tr("select_rom"))
        self.select_rom_btn.setObjectName("select_rom_btn")
        self.select_rom_btn.clicked.connect(self.select_rom)
        rom_select_layout.addWidget(self.select_rom_btn)
        rom_layout.addLayout(rom_select_layout)
        rom_group.setLayout(rom_layout)
        layout.addWidget(rom_group)

        self.extract_btn = QPushButton(self.tr("extract_texts"))
        self.extract_btn.setObjectName("extract_btn")
        self.extract_btn.setMinimumHeight(50)
        self.extract_btn.setStyleSheet(
            "QPushButton{background-color:#4CAF50;color:white;font-size:14pt;"
            "font-weight:bold;border-radius:5px;}"
            "QPushButton:hover{background-color:#45a049;}"
            "QPushButton:disabled{background-color:#cccccc;color:#666666;}"
        )
        self.extract_btn.clicked.connect(self.extract_texts)
        layout.addWidget(self.extract_btn)

        self.optimize_btn = QPushButton(self.tr("optimize_data"))
        self.optimize_btn.setObjectName("optimize_btn")
        self.optimize_btn.setMinimumHeight(50)
        self.optimize_btn.setEnabled(False)
        self.optimize_btn.clicked.connect(self.optimize_data)
        self.optimize_btn.setStyleSheet(
            "QPushButton{background-color:#FF9800;color:white;font-size:14pt;"
            "font-weight:bold;border-radius:5px;}"
            "QPushButton:hover{background-color:#e68900;}"
            "QPushButton:disabled{background-color:#cccccc;}"
        )
        layout.addWidget(self.optimize_btn)

        extract_progress_group = QGroupBox(self.tr("extraction_progress"))
        extract_progress_group.setObjectName("extract_progress_group")
        extract_progress_layout = QVBoxLayout()
        self.extract_progress_bar = QProgressBar()
        self.extract_progress_bar.setFormat("%p%")  # Mostra porcentagem
        extract_progress_layout.addWidget(self.extract_progress_bar)
        self.extract_status_label = QLabel(self.tr("waiting"))
        self.extract_status_label.setObjectName("extract_status_label")
        self.extract_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        extract_progress_layout.addWidget(self.extract_status_label)
        extract_progress_group.setLayout(extract_progress_layout)
        layout.addWidget(extract_progress_group)

        optimize_progress_group = QGroupBox(self.tr("optimization_progress"))
        optimize_progress_group.setObjectName("optimize_progress_group")
        optimize_progress_layout = QVBoxLayout()
        self.optimize_progress_bar = QProgressBar()
        self.optimize_progress_bar.setFormat("%p%")  # Mostra porcentagem
        optimize_progress_layout.addWidget(self.optimize_progress_bar)
        self.optimize_status_label = QLabel(self.tr("waiting"))
        self.optimize_status_label.setObjectName("optimize_status_label")
        self.optimize_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        optimize_progress_layout.addWidget(self.optimize_status_label)
        optimize_progress_group.setLayout(optimize_progress_layout)
        layout.addWidget(optimize_progress_group)

        layout.addStretch()
        return widget

    def create_translation_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        file_group = QGroupBox(self.tr("file_to_translate"))
        file_group.setObjectName("file_to_translate_group")
        file_layout = QHBoxLayout()

        self.trans_file_label = QLabel(self.tr("no_file"))
        self.trans_file_label.setObjectName("trans_file_label")
        self.trans_file_label.setStyleSheet("color: #888;")
        file_layout.addWidget(self.trans_file_label)

        self.sel_file_btn = QPushButton(self.tr("select_file"))
        self.sel_file_btn.setObjectName("sel_file_btn")
        self.sel_file_btn.clicked.connect(self.select_translation_input_file)
        file_layout.addWidget(self.sel_file_btn)

        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        lang_config_group = QGroupBox(self.tr("language_config"))
        lang_config_group.setObjectName("lang_config_group")
        lang_config_layout = QGridLayout()
        source_lang_label = QLabel(self.tr("source_language"))
        source_lang_label.setObjectName("source_lang_label")
        lang_config_layout.addWidget(source_lang_label, 0, 0)
        self.source_lang_combo = QComboBox()
        # Populate with translated source language names
        self.source_lang_combo.addItems(self.get_all_translated_source_languages())
        lang_config_layout.addWidget(self.source_lang_combo, 0, 1)
        target_lang_label = QLabel(self.tr("target_language"))
        target_lang_label.setObjectName("target_lang_label")
        lang_config_layout.addWidget(target_lang_label, 1, 0)
        self.target_lang_combo = QComboBox()
        self.target_lang_combo.addItems(ProjectConfig.TARGET_LANGUAGES.keys())
        lang_config_layout.addWidget(self.target_lang_combo, 1, 1)
        lang_config_group.setLayout(lang_config_layout)
        layout.addWidget(lang_config_group)

        mode_group = QGroupBox(self.tr("translation_mode"))
        mode_group.setObjectName("mode_group")
        mode_layout = QVBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "🤖 Auto (Gemini → Ollama)",
            "⚡ Online Gemini (Google API)",
            "🚀 Offline Rápido (Llama 3.2) [RECOMENDADO]",
            "🔥 Offline Alta Qualidade (Mistral 7B) [Requer 8GB+ VRAM]",
            "🌐 Online DeepL (API)"
        ])
        self.mode_combo.setCurrentText("🚀 Offline Rápido (Llama 3.2) [RECOMENDADO]")
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        self.api_group = QGroupBox(self.tr("api_config"))
        self.api_group.setObjectName("api_group")
        self.api_group.setVisible(True)
        api_layout = QGridLayout()
        api_key_label = QLabel(self.tr("api_key"))
        api_key_label.setObjectName("api_key_label")
        api_layout.addWidget(api_key_label, 0, 0)

        api_container = QWidget()
        api_container_layout = QHBoxLayout(api_container)
        api_container_layout.setContentsMargins(0, 0, 0, 0)
        api_container_layout.setSpacing(5)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self.eye_btn = QPushButton("👁️")
        self.eye_btn.setFixedWidth(40)
        self.eye_btn.setCheckable(True)
        self.eye_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.eye_btn.clicked.connect(self.toggle_api_visibility)
        self.eye_btn.setStyleSheet(
            "QPushButton { font-size: 16px; border: 1px solid #555; "
            "border-radius: 4px; background-color: #333; }"
            "QPushButton:checked { background-color: #555; }"
        )

        api_container_layout.addWidget(self.api_key_edit)
        api_container_layout.addWidget(self.eye_btn)

        api_layout.addWidget(api_container, 0, 1)
        workers_label = QLabel(self.tr("workers"))
        workers_label.setObjectName("workers_label")
        api_layout.addWidget(workers_label, 1, 0)
        self.workers_spin = QSpinBox()
        self.workers_spin.setMinimum(1)
        self.workers_spin.setMaximum(10)
        self.workers_spin.setValue(3)
        api_layout.addWidget(self.workers_spin, 1, 1)
        timeout_label = QLabel(self.tr("timeout"))
        timeout_label.setObjectName("timeout_label")
        api_layout.addWidget(timeout_label, 2, 0)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setMinimum(30)
        self.timeout_spin.setMaximum(300)
        self.timeout_spin.setValue(120)
        api_layout.addWidget(self.timeout_spin, 2, 1)
        cache_check = QCheckBox(self.tr("use_cache"))
        cache_check.setObjectName("cache_check")
        cache_check.setChecked(True)
        api_layout.addWidget(cache_check, 3, 0, 1, 2)
        self.api_group.setLayout(api_layout)
        layout.addWidget(self.api_group)

        translation_progress_group = QGroupBox(self.tr("translation_progress"))
        translation_progress_group.setObjectName("translation_progress_group")
        translation_progress_layout = QVBoxLayout()
        self.translation_progress_bar = QProgressBar()
        self.translation_progress_bar.setFormat("%p%")  # Mostra porcentagem
        translation_progress_layout.addWidget(self.translation_progress_bar)
        self.translation_status_label = QLabel(self.tr("waiting"))
        self.translation_status_label.setObjectName("translation_status_label")
        self.translation_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        translation_progress_layout.addWidget(self.translation_status_label)
        translation_progress_group.setLayout(translation_progress_layout)
        layout.addWidget(translation_progress_group)

        # Botão TRADUZIR
        self.translate_btn = QPushButton(self.tr("translate_ai"))
        self.translate_btn.setObjectName("translate_btn")
        self.translate_btn.setMinimumHeight(50)
        self.translate_btn.setStyleSheet(
            "QPushButton{background-color:#2196F3;color:white;font-size:14pt;"
            "font-weight:bold;border-radius:5px;}"
            "QPushButton:hover{background-color:#0b7dda;}"
        )
        self.translate_btn.clicked.connect(self.translate_texts)
        layout.addWidget(self.translate_btn)

        # Botão PARAR (NOVO!)
        self.stop_translation_btn = QPushButton(self.tr("stop_translation"))
        self.stop_translation_btn.setObjectName("stop_translation_btn")
        self.stop_translation_btn.setMinimumHeight(50)
        self.stop_translation_btn.setStyleSheet(
            "QPushButton{background-color:#000000;color:#FFFFFF;font-size:14pt;"
            "font-weight:bold;border-radius:5px;}"
            "QPushButton:hover{background-color:#222222;}"
        )
        self.stop_translation_btn.clicked.connect(self.stop_translation)
        self.stop_translation_btn.setEnabled(False)  # Desabilitado até iniciar tradução
        layout.addWidget(self.stop_translation_btn)

        layout.addStretch()
        return widget

    def create_reinsertion_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        rom_group = QGroupBox(self.tr("original_rom"))
        rom_group.setObjectName("reinsert_rom_group")
        rom_layout = QVBoxLayout()
        rom_select_layout = QHBoxLayout()
        self.reinsert_rom_label = QLabel(self.tr("no_rom"))
        self.reinsert_rom_label.setObjectName("reinsert_rom_label")
        rom_select_layout.addWidget(self.reinsert_rom_label)
        select_reinsert_rom_btn = QPushButton(self.tr("select_rom"))
        select_reinsert_rom_btn.setObjectName("select_reinsert_rom_btn")
        select_reinsert_rom_btn.clicked.connect(self.select_rom_for_reinsertion)
        rom_select_layout.addWidget(select_reinsert_rom_btn)
        rom_layout.addLayout(rom_select_layout)
        rom_group.setLayout(rom_layout)
        layout.addWidget(rom_group)

        trans_group = QGroupBox(self.tr("translated_file"))
        trans_group.setObjectName("translated_file_group")
        trans_layout = QVBoxLayout()
        trans_select_layout = QHBoxLayout()
        self.translated_file_label = QLabel(self.tr("no_rom"))
        self.translated_file_label.setObjectName("translated_file_label")
        trans_select_layout.addWidget(self.translated_file_label)
        select_translated_btn = QPushButton(self.tr("select_file"))
        select_translated_btn.setObjectName("select_translated_btn")
        select_translated_btn.clicked.connect(self.select_translated_file)
        trans_select_layout.addWidget(select_translated_btn)
        trans_layout.addLayout(trans_select_layout)
        trans_group.setLayout(trans_layout)
        layout.addWidget(trans_group)

        output_group = QGroupBox(self.tr("output_rom"))
        output_group.setObjectName("output_rom_group")
        output_layout = QVBoxLayout()
        self.output_rom_edit = QLineEdit()
        self.output_rom_edit.setPlaceholderText(self.tr("example_filename"))
        output_layout.addWidget(self.output_rom_edit)
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        reinsertion_progress_group = QGroupBox(self.tr("reinsertion_progress"))
        reinsertion_progress_group.setObjectName("reinsertion_progress_group")
        reinsertion_progress_layout = QVBoxLayout()
        self.reinsertion_progress_bar = QProgressBar()
        self.reinsertion_progress_bar.setFormat("%p%")  # Mostra porcentagem
        reinsertion_progress_layout.addWidget(self.reinsertion_progress_bar)
        self.reinsertion_status_label = QLabel(self.tr("waiting"))
        self.reinsertion_status_label.setObjectName("reinsertion_status_label")
        self.reinsertion_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        reinsertion_progress_layout.addWidget(self.reinsertion_status_label)
        reinsertion_progress_group.setLayout(reinsertion_progress_layout)
        layout.addWidget(reinsertion_progress_group)

        self.reinsert_btn = QPushButton(self.tr("reinsert"))
        self.reinsert_btn.setObjectName("reinsert_btn")
        self.reinsert_btn.setMinimumHeight(50)
        self.reinsert_btn.setStyleSheet(
            "QPushButton{background-color:#FF9800;color:white;font-size:14pt;"
            "font-weight:bold;border-radius:5px;}"
            "QPushButton:hover{background-color:#e68900;}"
        )
        self.reinsert_btn.clicked.connect(self.reinsert)
        layout.addWidget(self.reinsert_btn)

        layout.addStretch()
        return widget

    def create_settings_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        ui_lang_group = QGroupBox(self.tr("ui_language"))
        ui_lang_group.setObjectName("ui_lang_group")
        ui_lang_layout = QHBoxLayout()
        self.ui_lang_combo = QComboBox()
        self.ui_lang_combo.setMaxVisibleItems(15)
        self.ui_lang_combo.addItems(ProjectConfig.UI_LANGUAGES.keys())
        self.ui_lang_combo.currentTextChanged.connect(self.change_ui_language)
        ui_lang_layout.addWidget(self.ui_lang_combo)
        ui_lang_group.setLayout(ui_lang_layout)
        layout.addWidget(ui_lang_group)

        theme_group = QGroupBox(self.tr("theme"))
        theme_group.setObjectName("theme_group")
        theme_layout = QHBoxLayout()
        self.theme_combo = QComboBox()
        # Populate with translated theme names
        self.theme_combo.addItems(self.get_all_translated_theme_names())
        # Set current theme using translated name
        current_translated = self.get_translated_theme_name(self.current_theme)
        self.theme_combo.setCurrentText(current_translated)
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        theme_layout.addWidget(self.theme_combo)
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)

        font_group = QGroupBox(self.tr("font_family"))
        font_group.setObjectName("font_group")
        font_layout = QHBoxLayout()
        self.font_combo = QComboBox()
        self.font_combo.addItems(ProjectConfig.FONT_FAMILIES.keys())
        self.font_combo.setCurrentText(self.current_font_family)
        self.font_combo.currentTextChanged.connect(self.change_font_family)
        font_layout.addWidget(self.font_combo)
        font_group.setLayout(font_layout)
        layout.addWidget(font_group)

        # COMMERCIAL GRADE: Ajuda e Suporte Section
        self.help_group = QGroupBox(self.tr("help_support"))
        self.help_group.setObjectName("help_group")
        help_layout = QFormLayout()

        # Guia de Uso Profissional Dropdown
        self.manual_label = QLabel(self.tr("manual_guide"))
        self.manual_combo = QComboBox()
        self.populate_manual_combo()  # ✅ Use logical IDs
        self.manual_combo.currentIndexChanged.connect(self.show_manual_step)

        help_layout.addRow(self.manual_label, self.manual_combo)

        # Contato para dúvidas
        self.contact_label = QLabel(
            f"<br><b>{self.tr('contact_support')}</b><br>"
            "<a href='mailto:celsoexpert@gmail.com' style='color: #4CAF50; text-decoration: none;'>"
            "celsoexpert@gmail.com</a>"
        )
        self.contact_label.setOpenExternalLinks(True)
        self.contact_label.setWordWrap(True)
        self.contact_label.setTextFormat(Qt.TextFormat.RichText)
        self.contact_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        help_layout.addRow("", self.contact_label)

        self.help_group.setLayout(help_layout)
        layout.addWidget(self.help_group)

        # PROFESSIONAL: Version label for buyer confidence
        layout.addStretch()
        version_label = QLabel("Versão do Sistema: v5.3 Stable")
        version_label.setStyleSheet("color: #888; font-size: 9pt; font-style: italic;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        return widget

    def create_graphics_lab_tab(self):
        """Aba 4: Laboratório Gráfico & Forense (Experimental)"""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        # ===== BARRA DE CONTROLES SUPERIOR (HORIZONTAL) =====
        controls_container = QWidget()
        controls_layout = QHBoxLayout(controls_container)
        controls_layout.setContentsMargins(10, 10, 10, 10)
        controls_layout.setSpacing(20)  # Aumentado de 15 para 20 para melhor separação

        # 1. Formato Gráfico
        format_group = QHBoxLayout()
        self.gfx_format_label = QLabel(self.tr("Formato:"))
        format_group.addWidget(self.gfx_format_label)
        self.gfx_format_combo = QComboBox()
        self.gfx_format_combo.addItems([
            self.tr("1bpp (GB/NES)"),
            self.tr("2bpp (SNES/GBC)"),
            self.tr("4bpp (SNES/GBA)"),
            self.tr("8bpp (PS1)")
        ])
        self.gfx_format_combo.setCurrentIndex(1)
        self.gfx_format_combo.setMinimumWidth(140)  # Aumentado de 120 para 140
        format_group.addWidget(self.gfx_format_combo)
        controls_layout.addLayout(format_group)

        # ESPAÇAMENTO FORÇADO ENTRE FORMATO E ZOOM (30 pixels)
        controls_layout.addSpacing(30)

        # 2. Zoom
        zoom_group = QHBoxLayout()
        self.gfx_zoom_label = QLabel(self.tr("Zoom:"))
        zoom_group.addWidget(self.gfx_zoom_label)
        self.gfx_zoom_combo = QComboBox()
        self.gfx_zoom_combo.addItems(["1x", "2x", "4x", "8x"])
        self.gfx_zoom_combo.setCurrentIndex(2)
        self.gfx_zoom_combo.setFixedWidth(70)  # Tamanho fixo para evitar expansão
        zoom_group.addWidget(self.gfx_zoom_combo)
        controls_layout.addLayout(zoom_group)

        # 3. Paleta
        palette_group = QHBoxLayout()
        self.gfx_palette_label = QLabel(self.tr("Paleta:"))
        palette_group.addWidget(self.gfx_palette_label)
        self.gfx_palette_combo = QComboBox()
        self.gfx_palette_combo.addItems([
            self.tr("Grayscale"),
            self.tr("Cores SNES"),
            self.tr("Cores GBA"),
            self.tr("Personalizada")
        ])
        self.gfx_palette_combo.setMinimumWidth(120)
        palette_group.addWidget(self.gfx_palette_combo)
        controls_layout.addLayout(palette_group)

        # 4. Offset
        offset_group = QHBoxLayout()
        self.gfx_offset_label = QLabel(self.tr("Offset:"))
        offset_group.addWidget(self.gfx_offset_label)
        self.gfx_offset_edit = QLineEdit("0x0")
        self.gfx_offset_edit.setFixedWidth(70)
        self.gfx_offset_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        offset_group.addWidget(self.gfx_offset_edit)
        controls_layout.addLayout(offset_group)

        # 5. Tiles por Linha
        tiles_row_group = QHBoxLayout()
        self.gfx_tiles_row_label = QLabel(self.tr("Tiles/linha:"))
        tiles_row_group.addWidget(self.gfx_tiles_row_label)
        self.gfx_tiles_row_spin = QSpinBox()
        self.gfx_tiles_row_spin.setRange(1, 64)
        self.gfx_tiles_row_spin.setValue(16)
        self.gfx_tiles_row_spin.setFixedWidth(60)
        tiles_row_group.addWidget(self.gfx_tiles_row_spin)
        controls_layout.addLayout(tiles_row_group)

        # 6. Total de Tiles
        tiles_total_group = QHBoxLayout()
        self.gfx_tiles_total_label = QLabel(self.tr("Tiles total:"))
        tiles_total_group.addWidget(self.gfx_tiles_total_label)
        self.gfx_tiles_total_spin = QSpinBox()
        self.gfx_tiles_total_spin.setRange(1, 1024)
        self.gfx_tiles_total_spin.setValue(256)
        self.gfx_tiles_total_spin.setFixedWidth(70)
        tiles_total_group.addWidget(self.gfx_tiles_total_spin)
        controls_layout.addLayout(tiles_total_group)

        controls_layout.addStretch(1)
        main_layout.addWidget(controls_container)

        # ===== CANVAS DE VISUALIZAÇÃO =====
        self.gfx_canvas_container = QWidget()
        canvas_layout = QVBoxLayout(self.gfx_canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)

        self.gfx_graphics_view = QGraphicsView()
        self.gfx_scene = QGraphicsScene()
        self.gfx_graphics_view.setScene(self.gfx_scene)
        self.gfx_graphics_view.setMinimumHeight(350)
        self.gfx_graphics_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        canvas_layout.addWidget(self.gfx_graphics_view)

        # Placeholder central traduzível
        self.gfx_placeholder_label = QLabel(
            self.tr("Selecione uma ROM primeiro na Aba 1 (Extração)")
        )
        self.gfx_placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gfx_placeholder_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #666;
                font-style: italic;
                padding: 20px;
                background-color: #f8f8f8;
                border: 1px dashed #ccc;
                border-radius: 5px;
                margin: 40px;
            }
        """)

        # Container overlay para centralizar
        overlay_container = QWidget(self.gfx_canvas_container)
        overlay_layout = QVBoxLayout(overlay_container)
        overlay_layout.addStretch()
        overlay_layout.addWidget(self.gfx_placeholder_label)
        overlay_layout.addStretch()
        overlay_container.setGeometry(0, 0, 100, 100)

        main_layout.addWidget(self.gfx_canvas_container, 1)

        # ===== BARRA DE FERRAMENTAS =====
        tools_container = QWidget()
        tools_layout = QHBoxLayout(tools_container)
        tools_layout.setContentsMargins(0, 0, 0, 0)

        self.gfx_btn_sniffer = QPushButton(self.tr("Tile Sniffer"))
        self.gfx_btn_sniffer.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        tools_layout.addWidget(self.gfx_btn_sniffer)

        self.gfx_btn_entropy = QPushButton(self.tr("Analisar Entropia"))
        self.gfx_btn_entropy.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
        tools_layout.addWidget(self.gfx_btn_entropy)

        self.gfx_btn_export = QPushButton(self.tr("Exportar PNG"))
        self.gfx_btn_export.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        tools_layout.addWidget(self.gfx_btn_export)

        self.gfx_btn_import = QPushButton(self.tr("Importar PNG"))
        self.gfx_btn_import.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        tools_layout.addWidget(self.gfx_btn_import)

        self.gfx_btn_new = QPushButton(self.tr("Novo Scan"))
        self.gfx_btn_new.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        tools_layout.addWidget(self.gfx_btn_new)

        tools_layout.addStretch(1)
        main_layout.addWidget(tools_container)

        # ===== LOG DE OPERAÇÕES =====
        log_label = QLabel(self.tr("Log de Operações:"))
        main_layout.addWidget(log_label)

        self.gfx_log_text = QTextEdit()
        self.gfx_log_text.setMaximumHeight(100)
        self.gfx_log_text.setReadOnly(True)
        self.gfx_log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #e0e0e0;
                border: 1px solid #3e3e3e;
                border-radius: 4px;
                font-family: 'Consolas', 'Monospace';
                font-size: 10pt;
                selection-background-color: #3d3d3d;
            }
        """)
        main_layout.addWidget(self.gfx_log_text)

        # ===== COMPONENTES ADICIONAIS (usados por métodos existentes) =====
        # Barra de progresso de entropia (inicialmente invisível)
        self.gfx_entropy_progress = QProgressBar()
        self.gfx_entropy_progress.setVisible(False)
        self.gfx_entropy_progress.setTextVisible(True)
        self.gfx_entropy_progress.setMaximumHeight(20)

        # Label de entropia (inicialmente invisível)
        self.gfx_entropy_label = QLabel("")
        self.gfx_entropy_label.setVisible(False)
        self.gfx_entropy_label.setWordWrap(True)
        self.gfx_entropy_label.setStyleSheet("color: #666; font-size: 10pt; padding: 10px;")

        # ===== CONEXÕES =====
        self.gfx_format_combo.currentIndexChanged.connect(self.on_gfx_format_changed)
        self.gfx_zoom_combo.currentIndexChanged.connect(self.on_gfx_zoom_changed)
        self.gfx_palette_combo.currentIndexChanged.connect(self.on_gfx_palette_changed)
        self.gfx_offset_edit.editingFinished.connect(self.on_gfx_offset_changed)
        self.gfx_tiles_row_spin.valueChanged.connect(self.on_gfx_tiles_row_changed)
        self.gfx_tiles_total_spin.valueChanged.connect(self.on_gfx_tiles_total_changed)

        self.gfx_btn_sniffer.clicked.connect(self.on_gfx_sniffer_clicked)
        self.gfx_btn_entropy.clicked.connect(self.on_gfx_entropy_clicked)
        self.gfx_btn_export.clicked.connect(self.on_gfx_export_clicked)
        self.gfx_btn_import.clicked.connect(self.on_gfx_import_clicked)
        self.gfx_btn_new.clicked.connect(self.on_gfx_new_clicked)

        return tab

    def on_mode_changed(self, index: int):
        self.api_group.setVisible(index > 0)

    # ═══════════════════════════════════════════════════════════════════════
    # CALLBACKS DO LABORATÓRIO GRÁFICO
    # ═══════════════════════════════════════════════════════════════════════

    def on_gfx_bpp_changed(self):
        """Callback quando muda o formato BPP."""
        self.on_gfx_render()

    def on_gfx_offset_changed(self):
        """Callback quando muda o offset."""
        try:
            offset_text = self.gfx_offset_edit.text()
            self.gfx_current_offset = int(offset_text, 16) if offset_text.startswith('0x') else int(offset_text)
            self.on_gfx_render()
        except ValueError:
            self.log_message("⚠️ Offset inválido! Use formato hexadecimal (ex: 0x1000)")

    def on_gfx_prev_page(self):
        """Navega para página anterior."""
        bpp_mode = self.gfx_bpp_combo.currentText().split()[0]  # '1bpp', '2bpp', etc
        num_tiles = self.gfx_num_tiles_spin.value()

        bytes_per_tile = {'1bpp': 8, '2bpp': 16, '4bpp': 32, '8bpp': 64}
        tile_bytes = bytes_per_tile.get(bpp_mode, 16)

        page_bytes = num_tiles * tile_bytes
        self.gfx_current_offset = max(0, self.gfx_current_offset - page_bytes)

        self.gfx_offset_edit.setText(hex(self.gfx_current_offset))
        self.on_gfx_render()

    def on_gfx_next_page(self):
        """Navega para próxima página."""
        if not self.original_rom_path:
            return

        bpp_mode = self.gfx_bpp_combo.currentText().split()[0]
        num_tiles = self.gfx_num_tiles_spin.value()

        bytes_per_tile = {'1bpp': 8, '2bpp': 16, '4bpp': 32, '8bpp': 64}
        tile_bytes = bytes_per_tile.get(bpp_mode, 16)

        page_bytes = num_tiles * tile_bytes

        # Carrega ROM para verificar tamanho
        try:
            with open(self.original_rom_path, 'rb') as f:
                rom_size = len(f.read())
        except:
            rom_size = 1024 * 1024  # 1MB default

        self.gfx_current_offset = min(rom_size - page_bytes, self.gfx_current_offset + page_bytes)

        self.gfx_offset_edit.setText(hex(self.gfx_current_offset))
        self.on_gfx_render()

    def on_gfx_render(self):
        """Renderiza tiles no canvas."""
        if not self.original_rom_path:
            self.gfx_canvas_label.setText("📂 Selecione uma ROM primeiro na Aba 1 (Extração)")
            return

        try:
            # Carrega ROM
            with open(self.original_rom_path, 'rb') as f:
                rom_data = f.read()

            # Importa GraphicsWorker
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / 'core'))
            from graphics_worker import GraphicsWorker

            # Cria worker
            self.gfx_worker = GraphicsWorker(rom_data)

            # Parâmetros
            bpp_mode = self.gfx_bpp_combo.currentText().split()[0]  # '1bpp', '2bpp', etc
            scale_text = self.gfx_scale_combo.currentText()  # '4x'
            scale = int(scale_text.replace('x', ''))
            tiles_per_row = self.gfx_tiles_per_row_spin.value()
            num_tiles = self.gfx_num_tiles_spin.value()
            offset = self.gfx_current_offset

            # Export temporário para PNG
            import tempfile
            temp_png = tempfile.NamedTemporaryFile(suffix='.png', delete=False).name

            success = self.gfx_worker.export_tiles_to_png(
                start_offset=offset,
                num_tiles=num_tiles,
                bpp_mode=bpp_mode,
                tile_size=8,
                tiles_per_row=tiles_per_row,
                output_path=temp_png
            )

            if success:
                # Carrega PNG e aplica scale
                from PyQt5.QtGui import QPixmap
                pixmap = QPixmap(temp_png)

                if scale > 1:
                    pixmap = pixmap.scaled(
                        pixmap.width() * scale,
                        pixmap.height() * scale,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.FastTransformation
                    )

                self.gfx_canvas_label.setPixmap(pixmap)

                # Atualiza info
                self.gfx_info_label.setText(
                    f"Offset: {hex(offset)} | {bpp_mode} | {num_tiles} tiles | "
                    f"Zoom: {scale}x | Use ← → para navegar"
                )

                # Remove temp file
                import os
                os.unlink(temp_png)

                self.log_message(f"✅ Tiles renderizados: {num_tiles} tiles em {bpp_mode} @ {hex(offset)}")
            else:
                self.gfx_canvas_label.setText("❌ Erro ao renderizar tiles")

        except Exception as e:
            self.gfx_canvas_label.setText(f"❌ Erro: {str(e)}")
            self.log_message(f"⚠️ Erro ao renderizar tiles: {e}")

    def on_gfx_tile_sniffer(self):
        """Executa Tile Sniffer para detectar padrões de fonte."""
        if not self.original_rom_path:
            QMessageBox.warning(self, "Aviso", "Selecione uma ROM primeiro na Aba 1 (Extração)")
            return

        try:
            # Carrega ROM
            with open(self.original_rom_path, 'rb') as f:
                rom_data = f.read()

            # Importa GraphicsWorker
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / 'core'))
            from graphics_worker import GraphicsWorker

            self.gfx_worker = GraphicsWorker(rom_data)

            # Parâmetros
            bpp_mode = self.gfx_bpp_combo.currentText().split()[0]
            offset = self.gfx_current_offset

            self.log_message(f"🔍 Tile Sniffer iniciado @ {hex(offset)} ({bpp_mode})...")

            # Escaneia
            results = self.gfx_worker.scan_for_fonts(
                bpp_mode=bpp_mode,
                tile_size=8,
                start_offset=offset,
                max_tiles=512
            )

            if results:
                self.log_message(f"✅ Tile Sniffer encontrou {len(results)} tiles com padrão de fonte!")

                # Mostra resultados em diálogo
                msg = f"🔍 Tile Sniffer detectou {len(results)} possíveis tiles de fonte:\n\n"
                for result in results[:10]:  # Mostra primeiros 10
                    msg += f"• {result['offset_hex']} (confiança: {result['confidence']:.1%})\n"

                if len(results) > 10:
                    msg += f"\n... e mais {len(results) - 10} tiles.\n"

                msg += "\nNavegue até o primeiro offset detectado?"

                reply = QMessageBox.question(
                    self,
                    "Tile Sniffer - Resultados",
                    msg,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.Yes and results:
                    first_offset = results[0]['offset']
                    self.gfx_current_offset = first_offset
                    self.gfx_offset_edit.setText(hex(first_offset))
                    self.on_gfx_render()
            else:
                self.log_message("⚠️ Tile Sniffer não encontrou padrões de fonte nesta região")
                QMessageBox.information(
                    self,
                    "Tile Sniffer",
                    "Nenhum padrão de fonte detectado nesta região.\n\n"
                    "Tente navegar para outras áreas da ROM ou alterar o formato BPP."
                )

        except Exception as e:
            self.log_message(f"❌ Erro no Tile Sniffer: {e}")
            QMessageBox.critical(self, "Erro", f"Erro ao executar Tile Sniffer:\n{str(e)}")

    def on_gfx_export_png(self):
        """Exporta tiles atuais para PNG."""
        if not self.original_rom_path:
            QMessageBox.warning(self, "Aviso", "Selecione uma ROM primeiro")
            return

        # Diálogo de save
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Tiles para PNG",
            "exported_tiles.png",
            "PNG Images (*.png)"
        )

        if not output_path:
            return

        try:
            # Carrega ROM
            with open(self.original_rom_path, 'rb') as f:
                rom_data = f.read()

            # Importa GraphicsWorker
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / 'core'))
            from graphics_worker import GraphicsWorker

            self.gfx_worker = GraphicsWorker(rom_data)

            # Parâmetros
            bpp_mode = self.gfx_bpp_combo.currentText().split()[0]
            tiles_per_row = self.gfx_tiles_per_row_spin.value()
            num_tiles = self.gfx_num_tiles_spin.value()
            offset = self.gfx_current_offset

            # Exporta
            success = self.gfx_worker.export_tiles_to_png(
                start_offset=offset,
                num_tiles=num_tiles,
                bpp_mode=bpp_mode,
                tile_size=8,
                tiles_per_row=tiles_per_row,
                output_path=output_path
            )

            if success:
                self.log_message(f"✅ Tiles exportados para: {output_path}")
                QMessageBox.information(
                    self,
                    "Exportação Concluída",
                    f"Tiles exportados com sucesso!\n\n"
                    f"Arquivo: {Path(output_path).name}\n"
                    f"Tiles: {num_tiles}\n"
                    f"Formato: {bpp_mode}\n\n"
                    f"Edite o PNG no Paint/Photoshop e use 'Importar PNG' para reinserir."
                )
            else:
                self.log_message("❌ Erro ao exportar tiles")

        except Exception as e:
            self.log_message(f"❌ Erro na exportação: {e}")
            QMessageBox.critical(self, "Erro", f"Erro ao exportar:\n{str(e)}")

    def on_gfx_import_png(self):
        """Importa PNG editado e reinsere na ROM."""
        if not self.original_rom_path:
            QMessageBox.warning(self, "Aviso", "Selecione uma ROM primeiro")
            return

        # Diálogo de seleção
        png_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar PNG Editado",
            "",
            "PNG Images (*.png)"
        )

        if not png_path:
            return

        # Confirmação
        reply = QMessageBox.question(
            self,
            "Confirmação",
            "⚠️ ATENÇÃO: Esta operação irá MODIFICAR a ROM!\n\n"
            "O PNG será convertido de volta para tiles e inserido no offset atual.\n\n"
            "Deseja continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # Carrega ROM
            with open(self.original_rom_path, 'rb') as f:
                rom_data = f.read()

            # Importa GraphicsWorker
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / 'core'))
            from graphics_worker import GraphicsWorker

            self.gfx_worker = GraphicsWorker(rom_data)

            # Parâmetros
            bpp_mode = self.gfx_bpp_combo.currentText().split()[0]
            offset = self.gfx_current_offset

            # Importa e reinsere
            success = self.gfx_worker.import_png_to_tiles(
                png_path=png_path,
                target_offset=offset,
                bpp_mode=bpp_mode,
                tile_size=8
            )

            if success:
                # Salva ROM modificada
                output_rom = str(Path(self.original_rom_path).with_suffix('.modified.smc'))
                self.gfx_worker.save_rom(output_rom)

                self.log_message(f"✅ PNG importado e ROM salva: {output_rom}")
                QMessageBox.information(
                    self,
                    "Importação Concluída",
                    f"✅ PNG importado com sucesso!\n\n"
                    f"ROM modificada salva em:\n{Path(output_rom).name}\n\n"
                    f"Teste a ROM modificada em um emulador."
                )

                # Re-renderiza para ver mudanças
                self.on_gfx_render()
            else:
                self.log_message("❌ Erro ao importar PNG")

        except Exception as e:
            self.log_message(f"❌ Erro na importação: {e}")
            QMessageBox.critical(self, "Erro", f"Erro ao importar:\n{str(e)}")

    def on_gfx_entropy_scan(self):
        """Escaneia ROM com análise de entropia de Shannon."""
        if not self.original_rom_path:
            QMessageBox.warning(self, "Aviso", "Selecione uma ROM primeiro")
            return

        try:
            # Carrega ROM
            with open(self.original_rom_path, 'rb') as f:
                rom_data = f.read()

            # Importa GraphicsWorker
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / 'core'))
            from graphics_worker import GraphicsWorker

            self.gfx_worker = GraphicsWorker(rom_data)

            self.log_message("📊 Scanner de Entropia iniciado...")
            self.gfx_entropy_progress.setVisible(True)
            self.gfx_entropy_progress.setValue(0)

            # Escaneia
            results = self.gfx_worker.scan_entropy(chunk_size=256)

            # Analisa resultados
            total_chunks = len(results)
            compressed_chunks = sum(1 for r in results if r['is_compressed'])
            compression_ratio = compressed_chunks / total_chunks if total_chunks > 0 else 0

            avg_entropy = sum(r['entropy'] for r in results) / total_chunks if total_chunks > 0 else 0

            # Atualiza UI
            self.gfx_entropy_progress.setValue(100)

            report = (
                f"📊 Análise de Entropia Concluída:\n\n"
                f"• Total de blocos: {total_chunks:,}\n"
                f"• Entropia média: {avg_entropy:.2f}/8.0\n"
                f"• Blocos comprimidos/criptografados: {compressed_chunks:,} ({compression_ratio:.1%})\n"
                f"• Blocos normais: {total_chunks - compressed_chunks:,}\n\n"
            )

            if compression_ratio > 0.3:
                report += "🔴 ALTA ENTROPIA: >30% do ROM parece estar comprimido/criptografado!"
            elif compression_ratio > 0.1:
                report += "🟡 MÉDIA ENTROPIA: Alguns blocos podem estar comprimidos."
            else:
                report += "🟢 BAIXA ENTROPIA: ROM parece estar descomprimida."

            self.gfx_entropy_label.setText(report)
            self.log_message(f"✅ Scanner de Entropia concluído: {compression_ratio:.1%} comprimido")

            # Mostra detalhes em diálogo
            QMessageBox.information(
                self,
                "Scanner de Entropia - Resultados",
                report
            )

        except Exception as e:
            self.log_message(f"❌ Erro no scanner de entropia: {e}")
            QMessageBox.critical(self, "Erro", f"Erro ao escanear:\n{str(e)}")
        finally:
            self.gfx_entropy_progress.setVisible(False)

    # ===== NOVOS HANDLERS PARA ABA GRÁFICA SIMPLIFICADA =====

    def on_gfx_format_changed(self, index):
        """Handler para mudança de formato gráfico"""
        if hasattr(self, 'gfx_log_text'):
            format_name = self.gfx_format_combo.currentText()
            self.gfx_log_text.append(f"Formato alterado: {format_name}")

    def on_gfx_zoom_changed(self, index):
        """Handler para mudança de zoom"""
        if hasattr(self, 'gfx_log_text'):
            zoom_level = self.gfx_zoom_combo.currentText()
            self.gfx_log_text.append(f"Zoom alterado: {zoom_level}")

    def on_gfx_palette_changed(self, index):
        """Handler para mudança de paleta"""
        if hasattr(self, 'gfx_log_text'):
            palette_name = self.gfx_palette_combo.currentText()
            self.gfx_log_text.append(f"Paleta alterada: {palette_name}")

    def on_gfx_tiles_row_changed(self, value):
        """Handler para mudança de tiles por linha"""
        if hasattr(self, 'gfx_log_text'):
            self.gfx_log_text.append(f"Tiles por linha: {value}")

    def on_gfx_tiles_total_changed(self, value):
        """Handler para mudança de total de tiles"""
        if hasattr(self, 'gfx_log_text'):
            self.gfx_log_text.append(f"Total de tiles: {value}")

    def on_gfx_sniffer_clicked(self):
        """Handler para botão Tile Sniffer - mapeia para método existente"""
        self.on_gfx_tile_sniffer()

    def on_gfx_entropy_clicked(self):
        """Handler para botão Analisar Entropia - mapeia para método existente"""
        self.on_gfx_entropy_scan()

    def on_gfx_export_clicked(self):
        """Handler para botão Exportar PNG - mapeia para método existente"""
        self.on_gfx_export_png()

    def on_gfx_import_clicked(self):
        """Handler para botão Importar PNG - mapeia para método existente"""
        self.on_gfx_import_png()

    def on_gfx_new_clicked(self):
        """Handler para botão Novo Scan - limpa a visualização"""
        if hasattr(self, 'gfx_log_text'):
            self.gfx_log_text.append("Nova varredura iniciada")
            self.gfx_scene.clear()
            self.gfx_offset_edit.setText("0x0")

    def keyPressEvent(self, event):
        """
        Intercepta eventos de teclado para navegação no Laboratório Gráfico.

        Atalhos:
        - Seta Esquerda (←): Retrocede 1 tile
        - Seta Direita (→): Avança 1 tile
        - Page Up: Página anterior
        - Page Down: Próxima página
        """
        from PyQt5.QtCore import Qt

        # Só processa se estiver na aba do Laboratório Gráfico (aba index 3)
        if hasattr(self, 'tabs') and self.tabs.currentIndex() == 3:
            if event.key() == Qt.Key.Key_Left:
                # Seta esquerda: retrocede 1 tile
                bpp_mode = self.gfx_bpp_combo.currentText().split()[0]
                bytes_per_tile = {'1bpp': 8, '2bpp': 16, '4bpp': 32, '8bpp': 64}
                tile_bytes = bytes_per_tile.get(bpp_mode, 16)

                self.gfx_current_offset = max(0, self.gfx_current_offset - tile_bytes)
                self.gfx_offset_edit.setText(hex(self.gfx_current_offset))
                self.on_gfx_render()
                return

            elif event.key() == Qt.Key.Key_Right:
                # Seta direita: avança 1 tile
                bpp_mode = self.gfx_bpp_combo.currentText().split()[0]
                bytes_per_tile = {'1bpp': 8, '2bpp': 16, '4bpp': 32, '8bpp': 64}
                tile_bytes = bytes_per_tile.get(bpp_mode, 16)

                self.gfx_current_offset += tile_bytes
                self.gfx_offset_edit.setText(hex(self.gfx_current_offset))
                self.on_gfx_render()
                return

            elif event.key() == Qt.Key.Key_PageUp:
                # Page Up: página anterior
                self.on_gfx_prev_page()
                return

            elif event.key() == Qt.Key.Key_PageDown:
                # Page Down: próxima página
                self.on_gfx_next_page()
                return

        # Chama implementação padrão para outras teclas
        super().keyPressEvent(event)

    def populate_manual_combo(self):
        """Populate manual dropdown with translated items using logical IDs."""
        # Temporarily disconnect signal to prevent accidental auto-opening
        try:
            self.manual_combo.currentIndexChanged.disconnect(self.show_manual_step)
            signal_was_connected = True
        except:
            signal_was_connected = False

        # Repopulate combo
        self.manual_combo.clear()
        self.manual_combo.addItems([
            self.tr("manual_guide_title"),
            self.tr("manual_step_1"),
            self.tr("manual_step_2"),
            self.tr("manual_step_3"),
            self.tr("manual_step_4"),
            self.tr("manual_gfx_title")
        ])

        # Ensure index is 0 (closed state)
        self.manual_combo.setCurrentIndex(0)

        # Reconnect signal if it was connected before
        if signal_was_connected:
            self.manual_combo.currentIndexChanged.connect(self.show_manual_step)

    def on_platform_selected(self, index=None):
        selected_text = self.platform_combo.currentText()
        data = ProjectConfig.PLATFORMS.get(selected_text)

        # Fallback para busca por conteúdo se necessário
        if not data:
            for k, v in ProjectConfig.PLATFORMS.items():
                if k in selected_text: data = v; break

        # Se for separador ou inválido, desativa
        if not data or data.get("code") == "separator":
            if hasattr(self, 'extract_btn'):
                self.extract_btn.setEnabled(False)
                self.extract_btn.setText(self.tr("extract_texts"))
                self.extract_btn.setToolTip("")
            return

        is_ready = data.get("ready", False)

        if hasattr(self, 'extract_btn'):
            if is_ready:
                # PLATAFORMA PRONTA
                self.extract_btn.setEnabled(True)
                self.extract_btn.setText(self.tr("extract_texts"))
                self.extract_btn.setToolTip("")
                if hasattr(self, 'optimize_btn'): self.optimize_btn.setEnabled(True)
                self.log(f"Plataforma selecionada: {selected_text}")
            else:
                # PLATAFORMA EM FASE DE TESTES
                self.extract_btn.setEnabled(False)
                # Texto do Botão (Usa tradução)
                self.extract_btn.setText("🚧 " + self.tr("in_development"))
                # Tooltip ao passar o mouse (Usa tradução)
                self.extract_btn.setToolTip(self.tr("platform_tooltip"))

                if hasattr(self, 'optimize_btn'):
                    self.optimize_btn.setEnabled(False)
                    self.optimize_btn.setToolTip(self.tr("platform_tooltip"))

                self.log(f"ℹ️ {selected_text}: {self.tr('in_development')}")

    def change_ui_language(self, lang_name: str):
        self.current_ui_lang = ProjectConfig.UI_LANGUAGES[lang_name]
        self.refresh_ui_labels()
        self.save_config()
        self.log(f"Idioma alterado para: {lang_name}")

    def refresh_ui_labels(self):
        """Atualiza a interface gráfica quando o idioma é alterado."""
        self.update_window_title()

        # Tabs
        self.tabs.setTabText(0, self.tr("tab1"))
        self.tabs.setTabText(1, self.tr("tab2"))
        self.tabs.setTabText(2, self.tr("tab3"))
        self.tabs.setTabText(3, self.tr("tab5"))  # Graphics Lab agora no índice 3
        self.tabs.setTabText(4, self.tr("tab4"))  # Settings agora no índice 4

        # ═══════════════════════════════════════════════════════════
        # GRAPHICS LAB UI UPDATES (Tab 4 - i18n Support)
        # ═══════════════════════════════════════════════════════════

        # Atualizar a aba gráfica
        if hasattr(self, 'gfx_format_label'):
            self.retranslate_graphics_lab()

        # Update theme combo with translated names
        if hasattr(self, 'theme_combo'):
            # Temporarily disconnect to avoid triggering change event
            self.theme_combo.currentTextChanged.disconnect(self.change_theme)
            # Clear and repopulate with translated names
            self.theme_combo.clear()
            self.theme_combo.addItems(self.get_all_translated_theme_names())
            # Restore current selection with translated name
            current_translated = self.get_translated_theme_name(self.current_theme)
            self.theme_combo.setCurrentText(current_translated)
            # Reconnect the signal
            self.theme_combo.currentTextChanged.connect(self.change_theme)

        # Update output ROM placeholder with translated example filename
        if hasattr(self, 'output_rom_edit'):
            self.output_rom_edit.setPlaceholderText(self.tr("example_filename"))

        # Update source language combo with translated AUTO-DETECT
        if hasattr(self, 'source_lang_combo'):
            current_index = self.source_lang_combo.currentIndex()
            self.source_lang_combo.clear()
            self.source_lang_combo.addItems(self.get_all_translated_source_languages())
            self.source_lang_combo.setCurrentIndex(current_index)

        # Atualiza o título do grupo de Ajuda
        if hasattr(self, 'help_group'):
            self.help_group.setTitle(self.tr("help_support"))

        # Atualiza o texto do Guia
        if hasattr(self, 'manual_label'):
            self.manual_label.setText(self.tr("manual_guide"))

        def safe_update(object_name, widget_type, update_func):
            widget = self.findChild(widget_type, object_name)
            if widget:
                update_func(widget)

        # Manual dropdown
        if hasattr(self, 'populate_manual_combo'):
            self.populate_manual_combo()

        # Platform roadmap - REMOVED (not important for users)
        # if self.platform_combo and self.platform_combo.count() > 0:
        #     last_index = self.platform_combo.count() - 1
        #     self.platform_combo.setItemText(last_index, "📋 " + self.tr("roadmap_item"))

        # Buttons
        safe_update("btn_extract", QPushButton, lambda w: w.setText(self.tr("btn_extract")))
        safe_update("btn_optimize", QPushButton, lambda w: w.setText(self.tr("btn_optimize")))
        safe_update("stop_translation_btn", QPushButton, lambda w: w.setText(self.tr("stop_translation")))
        safe_update("reinsert_btn", QPushButton, lambda w: w.setText(self.tr("reinsert")))
        safe_update("extract_btn", QPushButton, lambda w: w.setText(self.tr("extract_texts")))
        safe_update("optimize_btn", QPushButton, lambda w: w.setText(self.tr("optimize_data")))
        safe_update("translate_btn", QPushButton, lambda w: w.setText(self.tr("translate_ai")))

        # Groups
        safe_update("platform_group", QGroupBox, lambda w: w.setTitle(self.tr("platform")))
        safe_update("rom_file_group", QGroupBox, lambda w: w.setTitle(self.tr("rom_file")))
        safe_update("extract_progress_group", QGroupBox, lambda w: w.setTitle(self.tr("extraction_progress")))
        safe_update("optimize_progress_group", QGroupBox, lambda w: w.setTitle(self.tr("optimization_progress")))
        safe_update("file_to_translate_group", QGroupBox, lambda w: w.setTitle(self.tr("file_to_translate")))
        safe_update("lang_config_group", QGroupBox, lambda w: w.setTitle(self.tr("language_config")))
        safe_update("mode_group", QGroupBox, lambda w: w.setTitle(self.tr("translation_mode")))
        safe_update("api_group", QGroupBox, lambda w: w.setTitle(self.tr("api_config")))
        safe_update("translation_progress_group", QGroupBox, lambda w: w.setTitle(self.tr("translation_progress")))
        safe_update("reinsert_rom_group", QGroupBox, lambda w: w.setTitle(self.tr("original_rom")))

        # Labels
        safe_update("rom_path_label", QLabel, lambda w: w.setText(self.tr("no_rom")) if self.original_rom_path is None else None)
        safe_update("extract_status_label", QLabel, lambda w: w.setText(self.tr("waiting")))
        safe_update("optimize_status_label", QLabel, lambda w: w.setText(self.tr("waiting")))
        safe_update("trans_file_label", QLabel, lambda w: w.setText(self.tr("no_file")) if self.optimized_file is None else None)
        safe_update("source_lang_label", QLabel, lambda w: w.setText(self.tr("source_language")))
        safe_update("target_lang_label", QLabel, lambda w: w.setText(self.tr("target_language")))
        safe_update("api_key_label", QLabel, lambda w: w.setText(self.tr("api_key")))
        safe_update("workers_label", QLabel, lambda w: w.setText(self.tr("workers")))
        safe_update("timeout_label", QLabel, lambda w: w.setText(self.tr("timeout")))
        safe_update("translation_status_label", QLabel, lambda w: w.setText(self.tr("waiting")))

        # Checkboxes
        safe_update("cache_check", QCheckBox, lambda w: w.setText(self.tr("use_cache")))

        # Button icons
        if self.select_rom_btn:
            self.select_rom_btn.setText(self.tr("select_rom"))
        if self.sel_file_btn:
            self.sel_file_btn.setText(self.tr("select_file"))

        # Update select reinsert ROM button with folder icon
        safe_update("select_reinsert_rom_btn", QPushButton, lambda w: w.setText(self.tr("select_rom")))

        safe_update("reinsert_rom_label", QLabel, lambda w: w.setText(self.tr("no_rom")) if self.original_rom_path is None else None)
        safe_update("translated_file_group", QGroupBox, lambda w: w.setTitle(self.tr("translated_file")))
        safe_update("translated_file_label", QLabel, lambda w: w.setText(self.tr("no_rom")) if self.translated_file is None else None)

        # Update select translated file button with folder icon
        safe_update("select_translated_btn", QPushButton, lambda w: w.setText(self.tr("select_file")))
        safe_update("output_rom_group", QGroupBox, lambda w: w.setTitle(self.tr("output_rom")))
        safe_update("reinsertion_progress_group", QGroupBox, lambda w: w.setTitle(self.tr("reinsertion_progress")))
        safe_update("reinsertion_status_label", QLabel, lambda w: w.setText(self.tr("waiting")))

        # Update reinsert button with syringe icon
        safe_update("reinsert_btn", QPushButton, lambda w: w.setText("💉 " + self.tr("reinsert")))

        # Update tooltips for disabled platform buttons
        if hasattr(self, 'extract_btn'):
            current_tooltip = self.extract_btn.toolTip()
            # If button is disabled and has a tooltip, update it
            if not self.extract_btn.isEnabled() and current_tooltip:
                self.extract_btn.setToolTip(self.tr("platform_tooltip"))
        if hasattr(self, 'optimize_btn'):
            current_tooltip = self.optimize_btn.toolTip()
            if not self.optimize_btn.isEnabled() and current_tooltip:
                self.optimize_btn.setToolTip(self.tr("platform_tooltip"))

        safe_update("ui_lang_group", QGroupBox, lambda w: w.setTitle(self.tr("ui_language")))
        safe_update("theme_group", QGroupBox, lambda w: w.setTitle(self.tr("theme")))
        safe_update("font_group", QGroupBox, lambda w: w.setTitle(self.tr("font_family")))
        safe_update("help_group", QGroupBox, lambda w: w.setTitle(self.tr("help_support")))

        # Update manual label
        if self.manual_label:
            self.manual_label.setText(self.tr("manual_guide"))

        # Update contact label
        if hasattr(self, 'contact_label'):
            self.contact_label.setText(
                f"<br><b>{self.tr('contact_support')}</b><br>"
                "<a href='mailto:celsoexpert@gmail.com' style='color: #4CAF50; text-decoration: none;'>"
                "celsoexpert@gmail.com</a>"
            )

        safe_update("log_group", QGroupBox, lambda w: w.setTitle(self.tr("log")))

        # Update restart button with recycle icon
        safe_update("restart_btn", QPushButton, lambda w: w.setText("🔄 " + self.tr("restart")))

        # Update exit button with door icon
        safe_update("exit_btn", QPushButton, lambda w: w.setText("🚪 " + self.tr("exit")))
        safe_update("developer_label", QLabel, lambda w: w.setText(self.tr("developer")))

    def retranslate_graphics_lab(self):
        """Atualiza todos os textos da aba gráfica quando idioma muda"""
        # Labels
        self.gfx_format_label.setText(self.tr("Formato:"))
        self.gfx_zoom_label.setText(self.tr("Zoom:"))
        self.gfx_palette_label.setText(self.tr("Paleta:"))
        self.gfx_offset_label.setText(self.tr("Offset:"))
        self.gfx_tiles_row_label.setText(self.tr("Tiles/linha:"))
        self.gfx_tiles_total_label.setText(self.tr("Tiles total:"))

        # Placeholder
        if hasattr(self, 'gfx_placeholder_label'):
            self.gfx_placeholder_label.setText(
                self.tr("Selecione uma ROM primeiro na Aba 1 (Extração)")
            )

        # Botões
        self.gfx_btn_sniffer.setText(self.tr("Tile Sniffer"))
        self.gfx_btn_entropy.setText(self.tr("Analisar Entropia"))
        self.gfx_btn_export.setText(self.tr("Exportar PNG"))
        self.gfx_btn_import.setText(self.tr("Importar PNG"))
        self.gfx_btn_new.setText(self.tr("Novo Scan"))

        # Atualizar itens dos comboboxes (preservando seleção)
        current_format = self.gfx_format_combo.currentIndex()
        current_palette = self.gfx_palette_combo.currentIndex()

        self.gfx_format_combo.clear()
        self.gfx_format_combo.addItems([
            self.tr("1bpp (GB/NES)"),
            self.tr("2bpp (SNES/GBC)"),
            self.tr("4bpp (SNES/GBA)"),
            self.tr("8bpp (PS1)")
        ])

        self.gfx_palette_combo.clear()
        self.gfx_palette_combo.addItems([
            self.tr("Grayscale"),
            self.tr("Cores SNES"),
            self.tr("Cores GBA"),
            self.tr("Personalizada")
        ])

        # Restaurar seleções
        if 0 <= current_format < self.gfx_format_combo.count():
            self.gfx_format_combo.setCurrentIndex(current_format)
        if 0 <= current_palette < self.gfx_palette_combo.count():
            self.gfx_palette_combo.setCurrentIndex(current_palette)

    def change_theme(self, theme_name: str):
        # Convert translated theme name to internal key
        internal_key = self.get_internal_theme_key(theme_name)
        self.current_theme = internal_key
        ThemeManager.apply(QApplication.instance(), internal_key)
        self.save_config()
        self.log(f"Tema alterado para: {internal_key}")

    def change_font_family(self, font_name: str):
        self.current_font_family = font_name
        font_family_string = ProjectConfig.FONT_FAMILIES[font_name]
        primary_font = font_family_string.split(',')[0].strip()
        font = QFont()
        font.setFamily(primary_font)
        font.setPointSize(10)
        QApplication.instance().setFont(font)
        self.save_config()
        self.log(f"Fonte alterada para: {font_name}")

    def toggle_api_visibility(self, checked):
        if checked:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.eye_btn.setText("🔒")
        else:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.eye_btn.setText("👁️")

    def select_rom(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, self.tr("select_rom"), str(ProjectConfig.ROMS_DIR),
            "ROMs (*.bin *.iso *.smc *.sfc *.z64 *.n64 *.gba *.gb *.gbc *.nds);;All (*.*)"
        )
        if file_path:
            self.original_rom_path = file_path
            self.rom_path_label.setText(Path(file_path).name)
            self.rom_path_label.setStyleSheet("color:#4CAF50;font-weight:bold;")
            self.reinsert_rom_label.setText(Path(file_path).name)
            self.reinsert_rom_label.setStyleSheet("color:#4CAF50;font-weight:bold;")
            self.log(f"ROM selected: {Path(file_path).name}")

    def select_translation_input_file(self):
        initial_dir = str(ProjectConfig.ROMS_DIR)
        if self.original_rom_path and os.path.exists(os.path.dirname(self.original_rom_path)):
            initial_dir = os.path.dirname(self.original_rom_path)

        file_path, _ = QFileDialog.getOpenFileName(
            self, self.tr("select_file"), initial_dir,
            "Text Files (*.txt *.optimized.txt *.translated.txt);;All Files (*.*)"
        )

        if file_path:
            self.optimized_file = file_path
            self.trans_file_label.setText(os.path.basename(file_path))
            self.trans_file_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.log(f"Arquivo carregado para tradução: {os.path.basename(file_path)}")

            rom_name = os.path.basename(file_path).replace(
                "_optimized.txt", ""
            ).replace(
                "_extracted_texts.txt", ""
            ).replace(
                "_translated.txt", ""
            ).rsplit('.', 1)[0]
            rom_directory = os.path.dirname(file_path)
            possible_roms = [
                os.path.join(rom_directory, f"{rom_name}{ext}")
                for ext in ['.smc', '.sfc', '.bin', '.nes', '.iso', '.z64', '.n64', '.gba']
            ]

            for possible_rom in possible_roms:
                if os.path.exists(possible_rom):
                    self.original_rom_path = possible_rom
                    self.reinsert_rom_label.setText(os.path.basename(possible_rom))
                    self.reinsert_rom_label.setStyleSheet("color:#4CAF50;font-weight:bold;")
                    self.log(f"Original ROM inferred: {os.path.basename(possible_rom)}")
                    break

    def select_rom_for_reinsertion(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, self.tr("select_rom"), str(ProjectConfig.ROMS_DIR),
            "ROMs (*.bin *.iso *.smc *.sfc *.z64 *.n64 *.gba *.gb *.gbc *.nds);;All (*.*)"
        )
        if file_path:
            self.original_rom_path = file_path
            self.reinsert_rom_label.setText(Path(file_path).name)
            self.reinsert_rom_label.setStyleSheet("color:#4CAF50;font-weight:bold;")
            self.rom_path_label.setText(Path(file_path).name)
            self.rom_path_label.setStyleSheet("color:#4CAF50;font-weight:bold;")

    def select_translated_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, self.tr("select_file"), str(ProjectConfig.ROMS_DIR),
            "Text Files (*.txt *.optimized.txt *.translated.txt);;All Files (*.*)"
        )
        if file_path:
            self.translated_file = file_path
            self.translated_file_label.setText(Path(file_path).name)
            self.translated_file_label.setStyleSheet("color:#4CAF50;font-weight:bold;")
            self.log(f"Translated file selected: {Path(file_path).name}")

    def reinsert(self):
        output_name = self.output_rom_edit.text().strip()
        if not self.original_rom_path or not os.path.exists(self.original_rom_path):
            QMessageBox.warning(self, "Aviso", "Selecione a ROM Original primeiro!")
            return
        if not self.translated_file or not os.path.exists(self.translated_file):
            QMessageBox.warning(self, "Aviso", "Arquivo Traduzido não encontrado!")
            return

        rom_path = self.original_rom_path
        translated_path = self.translated_file

        rom_directory = os.path.dirname(rom_path)
        if output_name:
            output_rom_path = os.path.join(rom_directory, output_name)
        else:
            rom_ext = Path(rom_path).suffix
            output_rom_path = os.path.join(rom_directory, f"translated_rom{rom_ext}")

        valid_extensions = ('.smc', '.sfc', '.bin', '.nes', '.z64', '.n64', '.gba', '.gb', '.gbc', '.nds', '.iso')
        if output_name and not output_name.lower().endswith(valid_extensions):
            QMessageBox.warning(self, "Erro", f"Extensão inválida. Use uma das: {', '.join(valid_extensions)}")
            return

        self.log(f"Starting reinsertion: {os.path.basename(rom_path)} -> {os.path.basename(output_rom_path)}")
        self.reinsertion_status_label.setText("Preparando arquivos...")
        self.reinsertion_progress_bar.setValue(0)
        self.reinsert_btn.setEnabled(False)

        self.reinsert_thread = ReinsertionWorker(rom_path, translated_path, output_rom_path)
        self.reinsert_thread.progress_signal.connect(self.reinsertion_progress_bar.setValue)
        self.reinsert_thread.status_signal.connect(self.reinsertion_status_label.setText)
        self.reinsert_thread.log_signal.connect(self.log)
        self.reinsert_thread.finished_signal.connect(self.on_reinsertion_finished)
        self.reinsert_thread.error_signal.connect(self.on_reinsertion_error)
        self.reinsert_thread.start()

    def on_reinsertion_finished(self):
        self.reinsertion_progress_bar.setValue(100)
        self.reinsert_btn.setEnabled(True)
        QMessageBox.information(self, self.tr("congratulations_title"), self.tr("congratulations_message"))

    def on_reinsertion_error(self, error_msg):
        self.reinsertion_status_label.setText("Erro!")
        self.reinsert_btn.setEnabled(True)
        self.log(f"❌ Erro fatal na reinserção: {error_msg}")
        QMessageBox.critical(self, "Erro", f"Ocorreu um erro na reinserção:\n{error_msg}")

    def extract_texts(self):
        if not self.original_rom_path:
            QMessageBox.warning(self, "Aviso", "Selecione uma ROM primeiro!")
            return

        self.log(f"Starting extraction: {os.path.basename(self.original_rom_path)}")
        self.extract_status_label.setText("Extraindo...")
        self.extract_progress_bar.setValue(0)
        self.optimize_btn.setEnabled(False)

        base_path = os.path.dirname(os.path.abspath(__file__))
        script_extractor = os.path.join(base_path, "generic_snes_extractor.py")

        if not os.path.exists(script_extractor):
            QMessageBox.critical(self, "Erro", f"Extraction script not found:\n{script_extractor}")
            self.extract_status_label.setText("Error: Script missing")
            return

        command = [sys.executable, script_extractor, self.original_rom_path]

        self.extract_thread = ProcessThread(command)
        self.extract_thread.progress.connect(self.log)
        self.extract_thread.progress_percent.connect(self.extract_progress_bar.setValue)
        self.extract_thread.finished.connect(self.on_extract_finished)
        self.extract_thread.start()

    def optimize_data(self):
        if not self.original_rom_path:
            QMessageBox.warning(self, "Aviso", "Nenhuma ROM selecionada!")
            return

        input_file = self.extracted_file
        if not input_file or not os.path.exists(input_file):
            rom_directory = os.path.dirname(self.original_rom_path)
            rom_filename = os.path.basename(self.original_rom_path).rsplit('.', 1)[0]
            input_file = os.path.join(rom_directory, f"{rom_filename}_extracted_texts.txt")
            if not os.path.exists(input_file):
                QMessageBox.warning(self, "Erro", f"Extracted file not found:\n{input_file}")
                return

        self.log("Starting intelligent data cleaning...")
        self.optimize_status_label.setText("Analyzing...")
        self.optimize_progress_bar.setValue(0)
        self.optimize_btn.setEnabled(False)

        self.optimize_thread = OptimizationWorker(input_file)
        self.optimize_thread.progress_signal.connect(self.optimize_progress_bar.setValue)
        self.optimize_thread.status_signal.connect(self.optimize_status_label.setText)
        self.optimize_thread.log_signal.connect(self.log)
        self.optimize_thread.finished_signal.connect(self.on_optimization_finished)
        self.optimize_thread.error_signal.connect(self.on_optimization_error)
        self.optimize_thread.start()

    def on_optimization_finished(self, output_file: str):
        self.optimized_file = output_file
        self.trans_file_label.setText(os.path.basename(output_file))
        self.trans_file_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        self.optimize_btn.setEnabled(True)
        self.tabs.setTabEnabled(1, True)

        # Recarrega o arquivo otimizado e atualiza o contador de linhas
        try:
            with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
                optimized_lines = f.readlines()

            line_count = len(optimized_lines)
            self.log(f"📊 Arquivo otimizado carregado: {line_count:,} linhas")

            # Atualiza interface para mostrar o novo arquivo
            self.optimize_status_label.setText(f"Concluído! ({line_count:,} linhas)")

        except Exception as e:
            self.log(f"⚠️ Erro ao contar linhas: {str(e)}")

        QMessageBox.information(self, "Sucesso", f"Optimization completed!\nFile: {os.path.basename(output_file)}\nLines: {line_count:,}")

    def on_optimization_error(self, error_msg: str):
        self.optimize_status_label.setText("Erro!")
        self.optimize_btn.setEnabled(True)
        self.log(f"❌ Erro na otimização: {error_msg}")
        QMessageBox.critical(self, "Erro", f"Optimization error:\n{error_msg}")

    def on_extract_finished(self, success: bool, message: str):
        if success:
            self.extract_status_label.setText("Concluído!")
            self.extract_progress_bar.setValue(100)

            try:
                rom_name = os.path.basename(self.original_rom_path).rsplit('.', 1)[0]
                rom_dir = os.path.dirname(self.original_rom_path)
                extracted_file_path = os.path.join(rom_dir, f"{rom_name}_extracted_texts.txt")

                if os.path.exists(extracted_file_path):
                    self.extracted_file = extracted_file_path
                    self.trans_file_label.setText(os.path.basename(extracted_file_path))
                    self.trans_file_label.setStyleSheet("color: #FF9800; font-weight: bold;")
                    self.log("✅ Extraction completed successfully. Ready for Optimization.")
                    self.optimize_btn.setEnabled(True)
                else:
                    self.log(f"❌ File not found: {extracted_file_path}")
                    self.optimize_btn.setEnabled(False)

            except Exception as e:
                self.log(f"❌ Error loading file: {e}")
                self.optimize_btn.setEnabled(False)
        else:
            self.extract_status_label.setText("Erro!")
            self.log(f"❌ Extraction failed: {message}")
            self.optimize_btn.setEnabled(False)
            QMessageBox.critical(self, "Erro", f"Extraction failed:\n\n{message}")

    def translate_texts(self):
        input_file = self.optimized_file

        if not input_file or not os.path.exists(input_file):
            QMessageBox.warning(self, "Aviso", "Select an optimized file first!")
            return

        mode_index = self.mode_combo.currentIndex()
        mode_text = self.mode_combo.currentText()

        # Verifica se modo requer API key
        needs_api_key = mode_index in [0, 1]  # Auto ou Gemini

        if needs_api_key:
            api_key = self.api_key_edit.text().strip()
            if not api_key:
                QMessageBox.warning(self, "Aviso", "API Key is required for this mode!")
                return
        else:
            api_key = ""

        self.translate_btn.setEnabled(False)
        self.stop_translation_btn.setEnabled(True)  # Habilita botão PARAR
        self.translation_progress_bar.setValue(0)
        self.translation_status_label.setText("Starting Worker...")

        target_lang_name = self.target_lang_combo.currentText()

        # Escolhe Worker baseado no modo
        if mode_index == 0:  # Auto (Gemini → Ollama)
            self.log(f"🤖 Starting AUTO mode (Gemini with Ollama fallback): {os.path.basename(input_file)}...")
            self.translate_thread = HybridWorker(api_key, input_file, target_lang_name)
        elif mode_index == 1:  # Gemini
            self.log(f"⚡ Starting Gemini translation: {os.path.basename(input_file)}...")
            self.translate_thread = GeminiWorker(api_key, input_file, target_lang_name)
        elif mode_index == 2:  # Llama 3.2 (Rápido)
            self.log(f"🚀 Starting Llama 3.2 translation (fast, offline): {os.path.basename(input_file)}...")
            self.translate_thread = OllamaWorker(input_file, target_lang_name, model="llama3.2:3b")
        elif mode_index == 3:  # Mistral 7B (Alta Qualidade)
            self.log(f"🔥 Starting Mistral 7B translation (high quality, offline): {os.path.basename(input_file)}...")
            self.translate_thread = OllamaWorker(input_file, target_lang_name, model="mistral:latest")
        else:
            QMessageBox.information(self, "Info", f"Mode '{mode_text}' not yet implemented!")
            self.translate_btn.setEnabled(True)
            self.stop_translation_btn.setEnabled(False)
            return

        self.translate_thread.progress_signal.connect(self.translation_progress_bar.setValue)
        self.translate_thread.status_signal.connect(self.translation_status_label.setText)
        self.translate_thread.log_signal.connect(self.log)
        self.translate_thread.finished_signal.connect(self.on_gemini_finished)
        self.translate_thread.error_signal.connect(self.on_gemini_error)
        self.translate_thread.start()

    def stop_translation(self):
        """Para a tradução em andamento"""
        if hasattr(self, 'translate_thread') and self.translate_thread and self.translate_thread.isRunning():
            reply = QMessageBox.question(
                self,
                'Confirmar',
                '⚠️ Tem certeza que deseja PARAR a tradução?\n\nO progresso até agora será salvo.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.log("🛑 Parando tradução...")
                self.translate_thread.stop()  # Chama método stop() do worker
                self.translate_thread.wait()  # Aguarda thread terminar
                self.translation_status_label.setText("❌ Parado pelo usuário")
                self.translate_btn.setEnabled(True)
                self.stop_translation_btn.setEnabled(False)
                self.log("✅ Tradução parada. Progresso parcial foi salvo.")

    def on_gemini_finished(self, output_file: str):
        self.translation_progress_bar.setValue(100)
        self.translation_status_label.setText("Concluído!")
        self.log(f"Translation saved: {os.path.basename(output_file)}")

        self.translated_file = output_file
        self.translated_file_label.setText(Path(output_file).name)
        self.translated_file_label.setStyleSheet("color:#2196F3;font-weight:bold;")

        self.translate_btn.setEnabled(True)
        self.stop_translation_btn.setEnabled(False)  # Desabilita botão PARAR
        self.tabs.setTabEnabled(2, True)
        QMessageBox.information(self, self.tr("congratulations_title"), self.tr("congratulations_message"))

    def on_gemini_error(self, error_msg: str):
        self.translation_status_label.setText("Erro Fatal")
        self.log(f"Translation error: {error_msg}")
        self.translate_btn.setEnabled(True)
        self.stop_translation_btn.setEnabled(False)  # Desabilita botão PARAR
        QMessageBox.critical(self, "Erro", f"Translation error:\n{error_msg}")

    def restart_application(self):
        self.log("Reiniciando aplicação...")
        self.save_config()
        self.cleanup_threads()

        python = sys.executable
        script = sys.argv[0]
        if sys.platform == 'win32':
            subprocess.Popen([python, script], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([python, script])
        QApplication.quit()

    def cleanup_threads(self):
        """Encerra threads com segurança antes de sair."""
        if self.extract_thread and self.extract_thread.isRunning():
            self.extract_thread.terminate()
            self.extract_thread.wait()

        if self.optimize_thread and self.optimize_thread.isRunning():
            self.optimize_thread.stop()
            self.optimize_thread.quit()
            self.optimize_thread.wait(1000)
            if self.optimize_thread.isRunning():
                self.optimize_thread.terminate()

        if self.translate_thread and self.translate_thread.isRunning():
            self.translate_thread.stop()
            self.translate_thread.quit()
            self.translate_thread.wait(1000)
            if self.translate_thread.isRunning():
                self.translate_thread.terminate()

        if self.reinsert_thread and self.reinsert_thread.isRunning():
            self.reinsert_thread.requestInterruption()
            self.reinsert_thread.quit()
            self.reinsert_thread.wait(1000)
            if self.reinsert_thread.isRunning():
                self.reinsert_thread.terminate()

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        self.log_text.moveCursor(QTextCursor.MoveOperation.End)

    def log_message(self, message: str):
        """Função centralizada para enviar mensagens para o log de operações da aba gráfica."""
        timestamp = datetime.now().strftime("[%H:%M:%S]")

        # Se estamos na aba gráfica, usa o log específico dela
        if hasattr(self, 'gfx_log_text'):
            self.gfx_log_text.append(f"{timestamp} {message}")
            scrollbar = self.gfx_log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        # Senão, usa o log principal
        elif hasattr(self, 'log_text'):
            self.log_text.append(f"{timestamp} {message}")
            self.log_text.moveCursor(QTextCursor.MoveOperation.End)
        else:
            print(f"DEBUG (Sem Log UI): {message}")

    def load_config(self):
        if ProjectConfig.CONFIG_FILE.exists():
            try:
                with open(ProjectConfig.CONFIG_FILE, 'r') as f:
                    config = json.load(f)

                    if 'theme' in config:
                        self.current_theme = config['theme']
                        # Set combo with translated theme name
                        translated_name = self.get_translated_theme_name(self.current_theme)
                        self.theme_combo.setCurrentText(translated_name)
                        ThemeManager.apply(QApplication.instance(), self.current_theme)

                    if 'ui_lang' in config:
                        self.current_ui_lang = config['ui_lang']
                        for name, code in ProjectConfig.UI_LANGUAGES.items():
                            if code == self.current_ui_lang:
                                self.ui_lang_combo.setCurrentText(name)
                                break
                        self.refresh_ui_labels()

                    if 'font_family' in config:
                        self.current_font_family = config['font_family']
                        self.font_combo.setCurrentText(self.current_font_family)
                        self.change_font_family(self.current_font_family)

                    if 'api_key_obfuscated' in config:
                        self.api_key_edit.setText(_deobfuscate_key(config['api_key_obfuscated']))

                    if 'workers' in config:
                        self.workers_spin.setValue(config['workers'])

                    if 'timeout' in config:
                        self.timeout_spin.setValue(config['timeout'])

                    self.log("Configuração carregada")
            except Exception as e:
                self.log(f"Falha ao carregar configuração: {e}")

    def save_config(self):
        config = {
            'theme': self.current_theme,
            'ui_lang': self.current_ui_lang,
            'font_family': self.current_font_family,
            'api_key_obfuscated': _obfuscate_key(self.api_key_edit.text()),
            'workers': self.workers_spin.value(),
            'timeout': self.timeout_spin.value(),
            'last_saved': datetime.now().isoformat()
        }
        try:
            with open(ProjectConfig.CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            self.log(f"Falha ao salvar configuração: {e}")

    def show_manual_step(self, index: int):
        """COMMERCIAL GRADE: Display manual instructions in professional popup."""
        if index == 0:
            return

        self.manual_combo.setCurrentIndex(0)

        if index == 3:
            self.show_step3_help()
            return

        # Handle Graphics Guide (index 5)
        if index == 5:
            self.show_graphics_guide()
            return

        step_title_keys = [
            "manual_step_1_title",
            "manual_step_2_title",
            "manual_step_3_title",
            "manual_step_4_title"
        ]

        step_content_keys = [
            "manual_step_1_content",
            "manual_step_2_content",
            "manual_step_3_content",
            "manual_step_4_content"
        ]

        step_title = self.tr(step_title_keys[index - 1])
        step_content = self.tr(step_content_keys[index - 1])

        dialog = QDialog(self)
        dialog.setWindowTitle(step_title)
        dialog.setMinimumSize(700, 600)

        layout = QVBoxLayout(dialog)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        content_label = QLabel(step_content)
        content_label.setWordWrap(True)
        content_label.setTextFormat(Qt.TextFormat.RichText)
        # COMMERCIAL GRADE: Set consistent font size for all content
        dialog_font = QFont("Segoe UI", 11)  # Unified 11pt font
        content_label.setFont(dialog_font)
        content_layout.addWidget(content_label)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        close_btn = QPushButton(self.tr("btn_close"))
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def show_graphics_guide(self):
        """Exibe o manual com texto fixo em PT-BR e tema escuro forçado."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Manual do Laboratório Gráfico")
        dialog.setMinimumSize(700, 600)

        # FORÇA O TEMA ESCURO (Corrige a tela branca)
        dialog.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #ffffff; }
            QTextEdit {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: 1px solid #3e3e3e;
                padding: 15px;
                font-size: 14px;
            }
            h2 { color: #4da6ff; }
            h3 { color: #ffcc00; margin-top: 20px; }
            li { margin-bottom: 5px; }
            QPushButton {
                background-color: #007acc; color: white; border: none;
                padding: 10px; border-radius: 4px; font-weight: bold;
            }
            QPushButton:hover { background-color: #0098ff; }
        """)

        layout = QVBoxLayout(dialog)

        # TEXTO DO MANUAL (HTML)
        html_content = """
        <h2>🎨 Guia do Laboratório Gráfico</h2>
        <hr>
        <p>Use esta ferramenta para visualizar e editar gráficos dentro da ROM.</p>

        <h3>1. Visualização (Barra Superior)</h3>
        <ul>
            <li><b>Formato:</b> Define como os pixels são lidos.
                <ul>
                    <li><i>1bpp:</i> Textos simples, fontes.</li>
                    <li><i>2bpp:</i> GameBoy, NES, Master System.</li>
                    <li><i>4bpp:</i> SNES, GBA, Mega Drive (Mais comum).</li>
                </ul>
            </li>
            <li><b>Offset:</b> É o endereço na memória. Use as setas para navegar ou digite um valor Hex (ex: 0x1000).</li>
            <li><b>Paleta:</b> Se as cores estiverem estranhas, mude para "Grayscale" (Cinza).</li>
        </ul>

        <h3>2. Exportar Gráficos (Extrair)</h3>
        <ol>
            <li>Encontre o desenho que quer editar na tela preta.</li>
            <li>Clique em <b>"💾 Export PNG"</b>.</li>
            <li>Salve o arquivo no seu PC.</li>
        </ol>

        <h3>3. Importar Gráficos (Inserir)</h3>
        <ol>
            <li>Edite o PNG no Paint/Photoshop. <b>NÃO mude as cores da paleta!</b></li>
            <li>Clique em <b>"📥 Import PNG"</b>.</li>
            <li>Selecione o arquivo editado. O programa salvará na ROM automaticamente.</li>
        </ol>
        """

        text_area = QTextEdit()
        text_area.setHtml(html_content)
        text_area.setReadOnly(True)
        layout.addWidget(text_area)

        btn_close = QPushButton("Fechar Manual")
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close)

        dialog.exec()

    def _create_emoji_text_widget(self, emoji: str, text: str, bold: bool = False) -> QWidget:
        """COMMERCIAL GRADE: Create widget with separated emoji and text for consistent sizing."""
        container = QWidget()
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)

        # Emoji label with fixed large size
        emoji_label = QLabel(emoji)
        emoji_font = QFont("Segoe UI Emoji", 20)  # Fixed large size for emojis
        emoji_label.setFont(emoji_font)
        h_layout.addWidget(emoji_label)

        # Text label with normal size
        text_label = QLabel(f"<b>{text}</b>" if bold else text)
        text_label.setTextFormat(Qt.TextFormat.RichText if bold else Qt.TextFormat.PlainText)
        text_font = QFont("Segoe UI", 11)  # Normal text size
        text_label.setFont(text_font)
        text_label.setWordWrap(True)
        h_layout.addWidget(text_label, 1)  # Stretch text label

        return container

    def show_step3_help(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("help_step3_title"))
        dialog.setMinimumSize(700, 600)

        layout = QVBoxLayout(dialog)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # COMMERCIAL GRADE: Separated emoji/text for consistent sizing
        text_font = QFont("Segoe UI", 11)

        # Objective - Extract emoji from translation
        obj_title_text = self.tr('help_step3_objective_title')
        obj_title = self._create_emoji_text_widget("🎯", obj_title_text.replace("🎯", "").strip(), bold=True)
        content_layout.addWidget(obj_title)

        obj_text = QLabel(self.tr("help_step3_objective_text"))
        obj_text.setWordWrap(True)
        obj_text.setFont(text_font)
        content_layout.addWidget(obj_text)
        content_layout.addSpacing(10)

        # Instructions
        inst_title_text = self.tr('help_step3_instructions_title')
        inst_title = self._create_emoji_text_widget("📝", inst_title_text.replace("📝", "").strip(), bold=True)
        content_layout.addWidget(inst_title)

        inst_text = QLabel(self.tr("help_step3_instructions_text"))
        inst_text.setWordWrap(True)
        inst_text.setFont(text_font)
        content_layout.addWidget(inst_text)
        content_layout.addSpacing(10)

        # Expectations
        expect_title_text = self.tr('help_step3_expect_title')
        expect_title = self._create_emoji_text_widget("✅", expect_title_text.replace("✅", "").strip(), bold=True)
        content_layout.addWidget(expect_title)

        expect_text = QLabel(self.tr("help_step3_expect_text"))
        expect_text.setWordWrap(True)
        expect_text.setFont(text_font)
        content_layout.addWidget(expect_text)
        content_layout.addSpacing(10)

        # Auto Mode
        auto_title_text = self.tr('help_step3_automode_title')
        auto_title = self._create_emoji_text_widget("🚀", auto_title_text.replace("🚀", "").strip(), bold=True)
        content_layout.addWidget(auto_title)

        auto_text = QLabel(self.tr("help_step3_automode_text"))
        auto_text.setWordWrap(True)
        auto_text.setFont(text_font)
        content_layout.addWidget(auto_text)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        close_btn = QPushButton(self.tr("btn_close"))
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def load_config(self):
        """Load saved configuration from JSON file."""
        if not ProjectConfig.CONFIG_FILE.exists():
            return

        try:
            with open(ProjectConfig.CONFIG_FILE, 'r') as f:
                config = json.load(f)

            # Restore theme
            theme_name = config.get('theme', 'Preto (Black)')
            if theme_name in ProjectConfig.THEMES:
                self.current_theme = theme_name
                if hasattr(self, 'theme_combo'):
                    # Set combo with translated theme name
                    translated_name = self.get_translated_theme_name(theme_name)
                    self.theme_combo.setCurrentText(translated_name)
                self.change_theme(translated_name)

            # Restore UI language
            ui_lang_code = config.get('ui_lang', 'en')
            self.current_ui_lang = ui_lang_code
            for lang_name, code in ProjectConfig.UI_LANGUAGES.items():
                if code == ui_lang_code:
                    if hasattr(self, 'ui_lang_combo'):
                        self.ui_lang_combo.setCurrentText(lang_name)
                    break

            # Restore font family
            font_name = config.get('font_family', 'Padrão (Segoe UI + CJK Fallback)')
            if font_name in ProjectConfig.FONT_FAMILIES:
                self.current_font_family = font_name
                if hasattr(self, 'font_combo'):
                    self.font_combo.setCurrentText(font_name)
                self.change_font_family(font_name)

            # Restore API key (deobfuscate)
            api_key_obfuscated = config.get('api_key_obfuscated', '')
            if api_key_obfuscated and hasattr(self, 'api_key_edit'):
                try:
                    decoded_key = base64.b64decode(api_key_obfuscated).decode('utf-8')
                    self.api_key_edit.setText(decoded_key)
                except:
                    pass

            # Restore workers and timeout
            if hasattr(self, 'workers_spin'):
                self.workers_spin.setValue(config.get('workers', 4))
            if hasattr(self, 'timeout_spin'):
                self.timeout_spin.setValue(config.get('timeout', 30))

            # CRITICAL FIX: Refresh UI labels after restoring language
            self.refresh_ui_labels()

            self.log("Configuração carregada com sucesso.")

        except Exception as e:
            self.log(f"Falha ao carregar configuração: {e}")

    def save_config(self):
        """Save current configuration to JSON file."""
        def _obfuscate_key(key: str) -> str:
            if not key:
                return ""
            return base64.b64encode(key.encode('utf-8')).decode('utf-8')

        config = {
            'theme': self.current_theme,
            'ui_lang': self.current_ui_lang,
            'font_family': self.current_font_family,
            'api_key_obfuscated': _obfuscate_key(self.api_key_edit.text()),
            'workers': self.workers_spin.value(),
            'timeout': self.timeout_spin.value(),
            'last_saved': datetime.now().isoformat()
        }
        try:
            with open(ProjectConfig.CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            self.log(f"Falha ao salvar configuração: {e}")

    def closeEvent(self, event):
        self.cleanup_threads()
        self.save_config()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    font = QFont()
    font.setFamily("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)

    ThemeManager.apply(app, "Preto (Black)")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
