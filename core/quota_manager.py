"""
Sistema Avançado de Gerenciamento de Quota para Google Gemini API
=================================================================

Recursos:
- Controle automático de limites diários (20 requisições/dia no free tier)
- Rate limiting adaptativo com retry automático
- Persistência de contador de uso
- Pausa automática quando atingir limite
- Reset automático às 00:00 (fuso horário local)
- Monitoramento em tempo real
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple
from threading import Lock
import logging

logger = logging.getLogger(__name__)


class GeminiQuotaManager:
    """Gerenciador de quota para Google Gemini API Free Tier"""

    # Limites do Free Tier (gemini-2.5-flash)
    FREE_TIER_DAILY_LIMIT = 20  # requisições por dia
    FREE_TIER_RPM = 15  # requisições por minuto (estimado)
    MIN_DELAY_BETWEEN_REQUESTS = 4.0  # segundos (60s / 15 RPM)
    SAFETY_MARGIN = 0.2  # 20% de margem de segurança

    def __init__(self, quota_file: str = "gemini_quota.json"):
        """
        Inicializa gerenciador de quota

        Args:
            quota_file: Arquivo para persistir dados de uso
        """
        self.quota_file = Path(quota_file)
        self.lock = Lock()

        # Estado do quota
        self.daily_requests = 0
        self.last_request_time = None
        self.current_date = datetime.now().date()
        self.quota_reset_time = None

        # Histórico de requisições (última hora)
        self.request_history = []

        # Carrega estado salvo
        self._load_quota_state()

        logger.info(f"✅ QuotaManager inicializado - Uso hoje: {self.daily_requests}/{self.FREE_TIER_DAILY_LIMIT}")

    def _load_quota_state(self):
        """Carrega estado de quota do arquivo"""
        if not self.quota_file.exists():
            self._reset_quota()
            return

        try:
            with open(self.quota_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Verifica se é do mesmo dia
            saved_date = datetime.fromisoformat(data['date']).date()
            today = datetime.now().date()

            if saved_date != today:
                logger.info("🔄 Novo dia detectado - resetando quota")
                self._reset_quota()
            else:
                self.daily_requests = data['daily_requests']
                self.last_request_time = datetime.fromisoformat(data['last_request_time']) if data.get('last_request_time') else None
                self.current_date = saved_date
                self.quota_reset_time = datetime.fromisoformat(data['quota_reset_time'])

                logger.info(f"📊 Estado carregado - {self.daily_requests} requisições usadas hoje")

        except Exception as e:
            logger.warning(f"⚠️ Erro ao carregar quota state: {e}")
            self._reset_quota()

    def _save_quota_state(self):
        """Salva estado de quota no arquivo"""
        try:
            data = {
                'date': self.current_date.isoformat(),
                'daily_requests': self.daily_requests,
                'last_request_time': self.last_request_time.isoformat() if self.last_request_time else None,
                'quota_reset_time': self.quota_reset_time.isoformat(),
                'updated_at': datetime.now().isoformat()
            }

            with open(self.quota_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"❌ Erro ao salvar quota state: {e}")

    def _reset_quota(self):
        """Reseta contador de quota (novo dia)"""
        self.daily_requests = 0
        self.current_date = datetime.now().date()
        self.last_request_time = None

        # Próximo reset: amanhã às 00:00
        tomorrow = datetime.now() + timedelta(days=1)
        self.quota_reset_time = datetime.combine(tomorrow.date(), datetime.min.time())

        self._save_quota_state()
        logger.info(f"🔄 Quota resetado - Próximo reset: {self.quota_reset_time}")

    def can_make_request(self) -> Tuple[bool, Optional[str]]:
        """
        Verifica se pode fazer uma requisição agora

        Returns:
            (pode_fazer, mensagem_erro)
        """
        with self.lock:
            # Verifica se precisa resetar (novo dia)
            if datetime.now().date() != self.current_date:
                self._reset_quota()

            # Verifica limite diário
            if self.daily_requests >= self.FREE_TIER_DAILY_LIMIT:
                time_until_reset = (self.quota_reset_time - datetime.now()).total_seconds()
                hours = int(time_until_reset // 3600)
                minutes = int((time_until_reset % 3600) // 60)

                return False, f"⛔ Limite diário atingido ({self.FREE_TIER_DAILY_LIMIT} requisições). Reset em {hours}h {minutes}min"

            # Verifica rate limiting (delay mínimo)
            if self.last_request_time:
                time_since_last = (datetime.now() - self.last_request_time).total_seconds()
                required_delay = self.MIN_DELAY_BETWEEN_REQUESTS * (1 + self.SAFETY_MARGIN)

                if time_since_last < required_delay:
                    wait_time = required_delay - time_since_last
                    return False, f"⏳ Aguarde {wait_time:.1f}s antes da próxima requisição (rate limit)"

            return True, None

    def wait_if_needed(self) -> bool:
        """
        Aguarda se necessário antes de fazer requisição

        Returns:
            True se pode continuar, False se atingiu limite diário
        """
        can_request, error_msg = self.can_make_request()

        if not can_request:
            if "Limite diário atingido" in error_msg:
                logger.error(error_msg)
                return False

            # Se é rate limit, aguarda
            if "rate limit" in error_msg:
                # Extrai tempo de espera
                wait_time = self.MIN_DELAY_BETWEEN_REQUESTS * (1 + self.SAFETY_MARGIN)
                if self.last_request_time:
                    elapsed = (datetime.now() - self.last_request_time).total_seconds()
                    wait_time = max(0, wait_time - elapsed)

                if wait_time > 0:
                    logger.info(f"⏳ Aguardando {wait_time:.1f}s (rate limiting)...")
                    time.sleep(wait_time)

        return True

    def record_request(self, success: bool = True):
        """
        Registra uma requisição feita

        Args:
            success: Se a requisição foi bem-sucedida
        """
        with self.lock:
            now = datetime.now()

            # Incrementa contador
            self.daily_requests += 1
            self.last_request_time = now

            # Adiciona ao histórico
            self.request_history.append({
                'timestamp': now.isoformat(),
                'success': success
            })

            # Mantém apenas última hora
            one_hour_ago = now - timedelta(hours=1)
            self.request_history = [
                r for r in self.request_history
                if datetime.fromisoformat(r['timestamp']) > one_hour_ago
            ]

            # Salva estado
            self._save_quota_state()

            # Log
            remaining = self.FREE_TIER_DAILY_LIMIT - self.daily_requests
            logger.info(f"📊 Requisição registrada - Restam {remaining}/{self.FREE_TIER_DAILY_LIMIT} hoje")

    def get_stats(self) -> Dict:
        """Retorna estatísticas de uso"""
        with self.lock:
            remaining = self.FREE_TIER_DAILY_LIMIT - self.daily_requests
            usage_percent = (self.daily_requests / self.FREE_TIER_DAILY_LIMIT) * 100

            # Tempo até reset
            time_until_reset = (self.quota_reset_time - datetime.now()).total_seconds()
            hours_until_reset = time_until_reset / 3600

            # Taxa de sucesso (última hora)
            recent_requests = self.request_history
            success_count = sum(1 for r in recent_requests if r['success'])
            success_rate = (success_count / len(recent_requests) * 100) if recent_requests else 100

            return {
                'daily_used': self.daily_requests,
                'daily_limit': self.FREE_TIER_DAILY_LIMIT,
                'daily_remaining': remaining,
                'usage_percent': usage_percent,
                'hours_until_reset': hours_until_reset,
                'last_request': self.last_request_time.isoformat() if self.last_request_time else None,
                'requests_last_hour': len(recent_requests),
                'success_rate_last_hour': success_rate
            }

    def get_status_message(self) -> str:
        """Retorna mensagem de status para UI"""
        stats = self.get_stats()

        # Emoji baseado em uso
        if stats['usage_percent'] < 50:
            emoji = "🟢"
        elif stats['usage_percent'] < 80:
            emoji = "🟡"
        else:
            emoji = "🔴"

        return (
            f"{emoji} API Gemini: {stats['daily_used']}/{stats['daily_limit']} requisições "
            f"({stats['usage_percent']:.0f}%) | "
            f"Reset em {stats['hours_until_reset']:.1f}h"
        )

    def estimate_batches(self, total_texts: int, batch_size: int = 200) -> Dict:
        """
        Estima quantas requisições serão necessárias

        Args:
            total_texts: Total de textos para traduzir
            batch_size: Tamanho do batch (textos por requisição)

        Returns:
            Dicionário com estimativa
        """
        with self.lock:
            # Calcula batches necessários
            batches_needed = (total_texts + batch_size - 1) // batch_size

            # Quota disponível
            remaining = self.FREE_TIER_DAILY_LIMIT - self.daily_requests

            # Pode completar?
            can_complete = batches_needed <= remaining

            # Tempo estimado
            total_time = batches_needed * self.MIN_DELAY_BETWEEN_REQUESTS * (1 + self.SAFETY_MARGIN)

            # Textos que podem ser traduzidos hoje
            texts_today = min(total_texts, remaining * batch_size)
            texts_tomorrow = max(0, total_texts - texts_today)

            return {
                'total_texts': total_texts,
                'batches_needed': batches_needed,
                'quota_remaining': remaining,
                'can_complete_today': can_complete,
                'estimated_time_seconds': total_time,
                'estimated_time_minutes': total_time / 60,
                'texts_today': texts_today,
                'texts_tomorrow': texts_tomorrow,
                'completion_date': 'Hoje' if can_complete else 'Amanhã'
            }

    def print_estimate(self, total_texts: int, batch_size: int = 200):
        """Imprime estimativa formatada"""
        est = self.estimate_batches(total_texts, batch_size)

        print("\n" + "="*60)
        print("📊 ESTIMATIVA DE TRADUÇÃO COM GEMINI API")
        print("="*60)
        print(f"Total de textos: {est['total_texts']:,}")
        print(f"Batches necessários: {est['batches_needed']} (até {batch_size} textos/batch)")
        print(f"Quota disponível hoje: {est['quota_remaining']} requisições")
        print(f"Tempo estimado: {est['estimated_time_minutes']:.1f} minutos")
        print("-"*60)

        if est['can_complete_today']:
            print(f"✅ PODE COMPLETAR HOJE!")
            print(f"   {est['texts_today']:,} textos serão traduzidos")
        else:
            print(f"⚠️ NÃO PODE COMPLETAR HOJE")
            print(f"   Hoje: {est['texts_today']:,} textos")
            print(f"   Amanhã: {est['texts_tomorrow']:,} textos")

        print("="*60 + "\n")


# Singleton global
_quota_manager_instance = None

def get_quota_manager(quota_file: str = "gemini_quota.json") -> GeminiQuotaManager:
    """Retorna instância singleton do QuotaManager"""
    global _quota_manager_instance

    if _quota_manager_instance is None:
        _quota_manager_instance = GeminiQuotaManager(quota_file)

    return _quota_manager_instance
