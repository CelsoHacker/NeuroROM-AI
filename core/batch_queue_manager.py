"""
Sistema de Fila Inteligente para Tradução em Lotes
===================================================

Recursos:
- Fila de prioridades com agendamento inteligente
- Processamento em background com pausas automáticas
- Salvamento de progresso incremental
- Resumo de traduções interrompidas
- Estatísticas em tempo real
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Callable
from queue import PriorityQueue
from threading import Thread, Event, Lock
from dataclasses import dataclass, field, asdict
from enum import IntEnum
import logging

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """Prioridades de tradução"""
    CRITICAL = 1  # Textos críticos (menus, diálogos principais)
    HIGH = 2      # Textos importantes (missões, NPCs)
    NORMAL = 3    # Textos comuns (descrições)
    LOW = 4       # Textos opcionais (easter eggs, flavor text)


@dataclass(order=True)
class TranslationBatch:
    """Representa um batch de textos para traduzir"""
    priority: Priority = field(compare=True)
    batch_id: int = field(compare=True)
    texts: List[str] = field(default_factory=list, compare=False)
    metadata: Dict = field(default_factory=dict, compare=False)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(), compare=False)
    status: str = field(default='pending', compare=False)
    translations: List[str] = field(default_factory=list, compare=False)
    error: Optional[str] = field(default=None, compare=False)
    attempts: int = field(default=0, compare=False)


class BatchQueueManager:
    """Gerenciador de fila de traduções com priorização"""

    def __init__(self,
                 progress_file: str = "translation_queue.json",
                 auto_save_interval: int = 10):
        """
        Inicializa gerenciador de fila

        Args:
            progress_file: Arquivo para salvar progresso
            auto_save_interval: Intervalo de auto-save (em batches processados)
        """
        self.progress_file = Path(progress_file)
        self.auto_save_interval = auto_save_interval

        # Fila de prioridades
        self.queue = PriorityQueue()
        self.lock = Lock()

        # Estado
        self.batches_processed = 0
        self.batches_failed = 0
        self.batches_pending = 0
        self.total_batches = 0
        self.current_batch: Optional[TranslationBatch] = None

        # Histórico completo (para salvar/carregar)
        self.all_batches: Dict[int, TranslationBatch] = {}

        # Controle de execução
        self.is_running = False
        self.is_paused = False
        self.stop_event = Event()
        self.pause_event = Event()
        self.worker_thread: Optional[Thread] = None

        # Callbacks
        self.on_batch_complete: Optional[Callable] = None
        self.on_batch_error: Optional[Callable] = None
        self.on_queue_complete: Optional[Callable] = None
        self.on_quota_exceeded: Optional[Callable] = None

        # Carregar progresso anterior
        self._load_progress()

        logger.info(f"✅ BatchQueueManager inicializado - {self.batches_pending} batches pendentes")

    def add_batch(self,
                  texts: List[str],
                  priority: Priority = Priority.NORMAL,
                  metadata: Optional[Dict] = None) -> int:
        """
        Adiciona batch à fila

        Args:
            texts: Lista de textos para traduzir
            priority: Prioridade do batch
            metadata: Metadados adicionais (ex: tipo de texto, contexto)

        Returns:
            batch_id
        """
        with self.lock:
            batch_id = self.total_batches
            self.total_batches += 1

            batch = TranslationBatch(
                priority=priority,
                batch_id=batch_id,
                texts=texts,
                metadata=metadata or {},
                status='pending'
            )

            self.queue.put(batch)
            self.all_batches[batch_id] = batch
            self.batches_pending += 1

            logger.info(f"📦 Batch #{batch_id} adicionado à fila (prioridade: {priority.name}, {len(texts)} textos)")

            return batch_id

    def add_batches_auto(self,
                         all_texts: List[str],
                         batch_size: int = 200,
                         priority: Priority = Priority.NORMAL,
                         detect_priority: bool = False) -> List[int]:
        """
        Divide textos em batches automaticamente

        Args:
            all_texts: Todos os textos para traduzir
            batch_size: Tamanho de cada batch
            priority: Prioridade padrão
            detect_priority: Se deve tentar detectar prioridade automaticamente

        Returns:
            Lista de batch_ids criados
        """
        batch_ids = []

        # Divide em chunks
        for i in range(0, len(all_texts), batch_size):
            chunk = all_texts[i:i+batch_size]

            # Detecta prioridade se solicitado
            chunk_priority = priority
            if detect_priority:
                chunk_priority = self._detect_priority(chunk)

            batch_id = self.add_batch(
                texts=chunk,
                priority=chunk_priority,
                metadata={
                    'batch_index': i // batch_size,
                    'total_batches': (len(all_texts) + batch_size - 1) // batch_size,
                    'text_range': f"{i}-{i+len(chunk)}"
                }
            )
            batch_ids.append(batch_id)

        logger.info(f"📊 {len(batch_ids)} batches criados automaticamente de {len(all_texts)} textos")

        return batch_ids

    def _detect_priority(self, texts: List[str]) -> Priority:
        """Detecta prioridade baseado em palavras-chave"""
        text_combined = ' '.join(texts).lower()

        # Palavras-chave críticas (UI, menus, erros)
        critical_keywords = ['menu', 'error', 'warning', 'button', 'confirm', 'cancel', 'yes', 'no']
        if any(kw in text_combined for kw in critical_keywords):
            return Priority.CRITICAL

        # Palavras-chave importantes (diálogos, missões)
        high_keywords = ['quest', 'mission', 'dialogue', 'npc', 'boss', 'level']
        if any(kw in text_combined for kw in high_keywords):
            return Priority.HIGH

        # Palavras-chave baixas (flavor text)
        low_keywords = ['flavor', 'description', 'lore', 'easter egg']
        if any(kw in text_combined for kw in low_keywords):
            return Priority.LOW

        return Priority.NORMAL

    def start_processing(self,
                        translate_function: Callable,
                        quota_manager=None):
        """
        Inicia processamento da fila em background

        Args:
            translate_function: Função que traduz um batch
                Assinatura: (texts: List[str]) -> (translations: List[str], success: bool, error: str)
            quota_manager: Instância de GeminiQuotaManager (opcional)
        """
        if self.is_running:
            logger.warning("⚠️ Processamento já está rodando")
            return

        self.is_running = True
        self.stop_event.clear()
        self.pause_event.clear()

        def worker():
            logger.info("🚀 Iniciando processamento de fila")

            while self.is_running and not self.stop_event.is_set():
                # Verifica pausa
                if self.is_paused:
                    logger.info("⏸️ Processamento pausado")
                    self.pause_event.wait()
                    logger.info("▶️ Processamento retomado")

                # Pega próximo batch
                try:
                    if self.queue.empty():
                        logger.info("✅ Fila vazia - processamento completo")
                        self.is_running = False
                        if self.on_queue_complete:
                            self.on_queue_complete()
                        break

                    batch = self.queue.get(timeout=1)
                    self.current_batch = batch

                    logger.info(f"🔄 Processando batch #{batch.batch_id} ({len(batch.texts)} textos)")

                    # Verifica quota se disponível
                    if quota_manager:
                        if not quota_manager.wait_if_needed():
                            logger.error("⛔ Quota diária excedida - pausando processamento")
                            self.pause()
                            if self.on_quota_exceeded:
                                self.on_quota_exceeded(batch)
                            # Recoloca batch na fila
                            self.queue.put(batch)
                            continue

                    # Traduz
                    batch.status = 'processing'
                    batch.attempts += 1

                    try:
                        translations, success, error = translate_function(batch.texts)

                        if success:
                            batch.translations = translations
                            batch.status = 'completed'
                            batch.error = None

                            with self.lock:
                                self.batches_processed += 1
                                self.batches_pending -= 1

                            logger.info(f"✅ Batch #{batch.batch_id} completo")

                            if self.on_batch_complete:
                                self.on_batch_complete(batch)

                            # Registra no quota manager
                            if quota_manager:
                                quota_manager.record_request(success=True)

                        else:
                            batch.status = 'failed'
                            batch.error = error

                            with self.lock:
                                self.batches_failed += 1
                                self.batches_pending -= 1

                            logger.error(f"❌ Batch #{batch.batch_id} falhou: {error}")

                            if self.on_batch_error:
                                self.on_batch_error(batch)

                            # Registra falha no quota manager
                            if quota_manager:
                                quota_manager.record_request(success=False)

                    except Exception as e:
                        batch.status = 'failed'
                        batch.error = str(e)

                        with self.lock:
                            self.batches_failed += 1
                            self.batches_pending -= 1

                        logger.exception(f"❌ Exceção ao processar batch #{batch.batch_id}")

                        if self.on_batch_error:
                            self.on_batch_error(batch)

                    # Auto-save
                    if self.batches_processed % self.auto_save_interval == 0:
                        self._save_progress()

                    self.current_batch = None

                except Exception as e:
                    logger.error(f"❌ Erro no worker: {e}")
                    time.sleep(1)

            # Save final
            self._save_progress()
            logger.info("🏁 Processamento finalizado")

        self.worker_thread = Thread(target=worker, daemon=True)
        self.worker_thread.start()

        logger.info("✅ Worker thread iniciada")

    def pause(self):
        """Pausa processamento"""
        if not self.is_running:
            return

        self.is_paused = True
        logger.info("⏸️ Pausando processamento...")

    def resume(self):
        """Resume processamento"""
        if not self.is_paused:
            return

        self.is_paused = False
        self.pause_event.set()
        logger.info("▶️ Retomando processamento...")

    def stop(self):
        """Para processamento completamente"""
        if not self.is_running:
            return

        logger.info("🛑 Parando processamento...")
        self.is_running = False
        self.stop_event.set()
        self.pause_event.set()  # Desbloqueia se pausado

        if self.worker_thread:
            self.worker_thread.join(timeout=5)

        self._save_progress()
        logger.info("✅ Processamento parado")

    def get_stats(self) -> Dict:
        """Retorna estatísticas da fila"""
        with self.lock:
            total_texts_processed = sum(
                len(b.translations) for b in self.all_batches.values()
                if b.status == 'completed'
            )

            total_texts = sum(len(b.texts) for b in self.all_batches.values())

            success_rate = (self.batches_processed / max(1, self.batches_processed + self.batches_failed)) * 100

            return {
                'total_batches': self.total_batches,
                'batches_pending': self.batches_pending,
                'batches_processed': self.batches_processed,
                'batches_failed': self.batches_failed,
                'total_texts': total_texts,
                'texts_translated': total_texts_processed,
                'success_rate': success_rate,
                'is_running': self.is_running,
                'is_paused': self.is_paused,
                'current_batch_id': self.current_batch.batch_id if self.current_batch else None
            }

    def get_status_message(self) -> str:
        """Retorna mensagem de status formatada"""
        stats = self.get_stats()

        if stats['is_paused']:
            status_emoji = "⏸️"
            status_text = "PAUSADO"
        elif stats['is_running']:
            status_emoji = "🔄"
            status_text = "PROCESSANDO"
        else:
            status_emoji = "⏹️"
            status_text = "PARADO"

        return (
            f"{status_emoji} {status_text} | "
            f"Batches: {stats['batches_processed']}/{stats['total_batches']} "
            f"({stats['batches_pending']} pendentes, {stats['batches_failed']} falhas) | "
            f"Textos: {stats['texts_translated']:,}/{stats['total_texts']:,} | "
            f"Taxa de sucesso: {stats['success_rate']:.1f}%"
        )

    def get_all_translations(self) -> List[str]:
        """
        Retorna todas as traduções na ordem correta dos batches

        Returns:
            Lista ordenada de traduções
        """
        all_translations = []

        # Ordena batches por batch_id
        sorted_batches = sorted(self.all_batches.values(), key=lambda b: b.batch_id)

        for batch in sorted_batches:
            if batch.status == 'completed':
                all_translations.extend(batch.translations)
            else:
                # Se batch falhou/pendente, adiciona textos originais
                all_translations.extend(batch.texts)

        return all_translations

    def _save_progress(self):
        """Salva progresso em arquivo JSON"""
        try:
            data = {
                'metadata': {
                    'last_saved': datetime.now().isoformat(),
                    'total_batches': self.total_batches,
                    'batches_processed': self.batches_processed,
                    'batches_failed': self.batches_failed,
                    'batches_pending': self.batches_pending
                },
                'batches': {
                    str(batch_id): {
                        'priority': batch.priority.value,
                        'batch_id': batch.batch_id,
                        'texts': batch.texts,
                        'translations': batch.translations,
                        'metadata': batch.metadata,
                        'status': batch.status,
                        'error': batch.error,
                        'attempts': batch.attempts,
                        'created_at': batch.created_at
                    }
                    for batch_id, batch in self.all_batches.items()
                }
            }

            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.debug(f"💾 Progresso salvo em {self.progress_file}")

        except Exception as e:
            logger.error(f"❌ Erro ao salvar progresso: {e}")

    def _load_progress(self):
        """Carrega progresso de arquivo JSON"""
        if not self.progress_file.exists():
            logger.info("ℹ️ Nenhum progresso anterior encontrado")
            return

        try:
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Restaura metadata
            meta = data.get('metadata', {})
            self.total_batches = meta.get('total_batches', 0)
            self.batches_processed = meta.get('batches_processed', 0)
            self.batches_failed = meta.get('batches_failed', 0)

            # Restaura batches
            batches_data = data.get('batches', {})
            pending_count = 0

            for batch_id_str, batch_dict in batches_data.items():
                batch = TranslationBatch(
                    priority=Priority(batch_dict['priority']),
                    batch_id=batch_dict['batch_id'],
                    texts=batch_dict['texts'],
                    translations=batch_dict['translations'],
                    metadata=batch_dict['metadata'],
                    status=batch_dict['status'],
                    error=batch_dict.get('error'),
                    attempts=batch_dict.get('attempts', 0),
                    created_at=batch_dict['created_at']
                )

                batch_id = int(batch_id_str)
                self.all_batches[batch_id] = batch

                # Recoloca pendentes/failed na fila
                if batch.status in ['pending', 'failed']:
                    self.queue.put(batch)
                    pending_count += 1

            self.batches_pending = pending_count

            logger.info(
                f"✅ Progresso carregado - "
                f"{self.batches_processed} completos, "
                f"{self.batches_failed} falhas, "
                f"{pending_count} recolocados na fila"
            )

        except Exception as e:
            logger.error(f"❌ Erro ao carregar progresso: {e}")

    def clear_completed(self):
        """Remove batches completados da memória (mantém apenas pendentes/failed)"""
        with self.lock:
            completed_ids = [
                batch_id for batch_id, batch in self.all_batches.items()
                if batch.status == 'completed'
            ]

            for batch_id in completed_ids:
                del self.all_batches[batch_id]

            logger.info(f"🧹 {len(completed_ids)} batches completados removidos da memória")

    def retry_failed(self):
        """Recoloca batches falhados na fila"""
        with self.lock:
            failed_batches = [
                batch for batch in self.all_batches.values()
                if batch.status == 'failed'
            ]

            for batch in failed_batches:
                batch.status = 'pending'
                batch.error = None
                self.queue.put(batch)
                self.batches_pending += 1
                self.batches_failed -= 1

            logger.info(f"🔄 {len(failed_batches)} batches falhados recolocados na fila")
