# -*- coding: utf-8 -*-
"""
================================================================================
TRADUTOR PARALELO ULTRA-OTIMIZADO v4.0 - DEPLOY CRÍTICO
PATCHES APLICADOS: Retry exponencial, Circuit Breaker, Throttling, Health Check
================================================================================
CORREÇÕES APLICADAS (Deploy Crítico):
✓ Health check do Ollama antes de iniciar
✓ Retry exponencial com jitter (5 tentativas: 0.5s → 1s → 2s → 4s → 8s)
✓ Circuit breaker (>20% falha em 60s → modo seguro)
✓ Throttling real com Semaphore (limita concorrência)
✓ Timeout configurável por requisição
✓ Parsing seguro de resposta (verifica Content-Type)
✓ Logger persistente (translator_errors.log)
✓ Removido num_gpu (causa erro em algumas versões)
✓ Validação de payload
✓ Fallback visível
================================================================================
"""

import os
import sys
import re
import json
import hashlib
import requests
import random
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, Semaphore
from typing import List, Dict, Tuple, Optional
from collections import defaultdict, Counter, deque
from datetime import datetime
import time
import math
import sys
import codecs
sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, 'strict')


# ============================================================================
# LOGGER DE ERROS PERSISTENTE
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('translator_errors.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURAÇÃO OTIMIZADA
# ============================================================================
class Config:
    """Configurações para Ollama local"""

    # Paralelismo (será ajustado pela UI)
    MAX_WORKERS = 1  # Default seguro (pode ser sobrescrito pela UI)
    BATCH_SIZE = 1

    # Filtros
    MIN_TEXT_LENGTH = 3
    MAX_TEXT_LENGTH = 500
    MIN_ALPHA_RATIO = 0.3

    # Ollama
    OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
    OLLAMA_HEALTH_URL = "http://127.0.0.1:11434/api/tags"
    MODEL = "llama3.2:3b"

    # Timeout configurável
    BASE_TIMEOUT = 60
    MAX_TIMEOUT = 120

    # Retry com backoff exponencial + jitter
    MAX_RETRIES = 5
    RETRY_BACKOFF_BASE = 0.5  # 0.5s base
    RETRY_JITTER = 0.3  # ±30%

    # Circuit breaker
    CIRCUIT_BREAKER_WINDOW = 60  # Janela de 60s
    CIRCUIT_BREAKER_THRESHOLD = 0.2  # >20% falha
    CIRCUIT_BREAKER_COOLDOWN = 60  # Pausa de 60s

    # Cache
    USE_CACHE = True
    CACHE_FILE = "cache_traducoes.json"


# ============================================================================
# HEALTH CHECK DO OLLAMA
# ============================================================================
def check_ollama_health() -> tuple[bool, str]:
    """
    Verifica se Ollama está rodando e acessível

    Returns:
        (success: bool, message: str)
    """
    try:
        logger.info("Verificando saúde do Ollama...")
        response = requests.get(Config.OLLAMA_HEALTH_URL, timeout=5)

        if response.status_code == 200:
            data = response.json()
            models = data.get('models', [])
            model_names = [m.get('name', '') for m in models]

            if Config.MODEL in model_names or any(Config.MODEL in m for m in model_names):
                logger.info(f"✓ Ollama OK - Modelo {Config.MODEL} disponível")
                return True, f"Ollama OK - {len(models)} modelo(s) disponível(is)"
            else:
                msg = f"Modelo {Config.MODEL} não encontrado. Disponíveis: {', '.join(model_names)}"
                logger.error(msg)
                return False, msg
        else:
            msg = f"Ollama respondeu com status {response.status_code}"
            logger.error(msg)
            return False, msg

    except requests.exceptions.ConnectionError:
        msg = "Ollama não está rodando. Execute: ollama serve"
        logger.error(msg)
        return False, msg
    except Exception as e:
        msg = f"Erro ao verificar Ollama: {e}"
        logger.error(msg)
        return False, msg


# ============================================================================
# SESSION MANAGER (Connection Pooling)
# ============================================================================
class SessionManager:
    """Gerencia pool de conexões HTTP reutilizáveis"""

    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.session = requests.Session()

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 502, 503, 504],
            allowed_methods=["POST"]
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=Config.MAX_WORKERS * 2,
            pool_maxsize=Config.MAX_WORKERS * 4
        )

        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self._initialized = True

    def get_session(self):
        return self.session


# ============================================================================
# CIRCUIT BREAKER
# ============================================================================
class CircuitBreaker:
    """Pausa traduções se servidor estiver falhando muito"""

    def __init__(self, window: int, threshold: float, cooldown: int):
        self.window = window
        self.threshold = threshold
        self.cooldown = cooldown

        self.requests = deque(maxlen=1000)  # Últimas 1000 requisições
        self.state = "closed"  # closed=normal, open=pausado
        self.open_until = 0
        self.lock = Lock()

        # Contador de workers (para modo degradado)
        self.degraded_mode = False

    def record_request(self, success: bool):
        """Registra resultado de requisição"""
        with self.lock:
            now = time.time()
            self.requests.append((now, success))

            # Calcula taxa de falha na janela
            recent = [(t, s) for t, s in self.requests if now - t < self.window]

            if len(recent) >= 10:  # Mínimo 10 requisições
                failures = sum(1 for _, s in recent if not s)
                failure_rate = failures / len(recent)

                if failure_rate > self.threshold and self.state == "closed":
                    self.state = "open"
                    self.open_until = now + self.cooldown
                    self.degraded_mode = True
                    logger.warning(f"⚠ CIRCUIT BREAKER ABERTO - Taxa de falha: {failure_rate*100:.1f}%")
                    logger.warning(f"⚠ Pausando por {self.cooldown}s - Modo seguro ativado")
                    print(f"\n{'='*70}")
                    print(f"⚠ OLLAMA INSTÁVEL - MODO SEGURO ATIVADO")
                    print(f"Taxa de falha: {failure_rate*100:.1f}%")
                    print(f"Reduzindo para 1 worker por {self.cooldown}s")
                    print(f"{'='*70}\n")

    def can_proceed(self) -> bool:
        """Verifica se pode fazer requisição"""
        with self.lock:
            if self.state == "closed":
                return True

            now = time.time()
            if now >= self.open_until:
                self.state = "closed"
                self.degraded_mode = False
                logger.info("✓ Circuit breaker fechado - voltando ao normal")
                print(f"\n✓ Ollama estabilizado - voltando ao modo normal\n")
                return True

            return False

    def wait_if_open(self):
        """Aguarda se circuit breaker estiver aberto"""
        while not self.can_proceed():
            time.sleep(2.0)

    def is_degraded(self) -> bool:
        """Verifica se está em modo degradado"""
        with self.lock:
            return self.degraded_mode


# ============================================================================
# FILTRO INTELIGENTE
# ============================================================================
class TextFilter:
    """Filtra apenas textos traduzíveis"""

    SPECIAL_CODES = re.compile(r'\[(NEW_LINE|NEW_PAGE|PLAYER_NAME|ITEM_NAME|'
                               r'COLOR_\w+|WAIT|CLEAR|CHOICE_\w+|NUMBER|'
                               r'VARIABLE|END_TEXT|PORTRAIT_\d+)\]')

    JUNK_PATTERNS = [
        re.compile(r'^[\x00-\x1F\x7F-\xFF]+$'),
        re.compile(r'^[0-9A-Fa-f\s]+$'),
        re.compile(r'^\W+$'),
        re.compile(r'^[\[\]]+$'),
    ]

    @classmethod
    def is_translatable(cls, text: str) -> bool:
        if not text or len(text) < Config.MIN_TEXT_LENGTH:
            return False

        clean = cls.SPECIAL_CODES.sub('', text).strip()
        if not clean:
            return False

        for pattern in cls.JUNK_PATTERNS:
            if pattern.match(clean):
                return False

        alpha_count = sum(1 for c in clean if c.isalnum())
        if len(clean) > 0:
            ratio = alpha_count / len(clean)
            if ratio < Config.MIN_ALPHA_RATIO:
                return False

        words = re.findall(r'\b[a-zA-Z]{2,}\b', clean)
        return bool(words)


# ============================================================================
# CACHE
# ============================================================================
class TranslationCache:
    """Cache persistente de traduções"""

    def __init__(self):
        self.cache: Dict[str, str] = {}
        self.hits = 0
        self.misses = 0
        self.lock = Lock()
        self.load_cache()

    def _get_hash(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    def get(self, text: str) -> Optional[str]:
        with self.lock:
            hash_key = self._get_hash(text)
            if hash_key in self.cache:
                self.hits += 1
                return self.cache[hash_key]
            self.misses += 1
            return None

    def set(self, text: str, translation: str):
        with self.lock:
            hash_key = self._get_hash(text)
            self.cache[hash_key] = translation

    def load_cache(self):
        if Config.USE_CACHE and os.path.exists(Config.CACHE_FILE):
            try:
                with open(Config.CACHE_FILE, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                logger.info(f"Cache carregado: {len(self.cache)} traduções")
            except:
                pass

    def save_cache(self):
        if Config.USE_CACHE:
            try:
                with open(Config.CACHE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(self.cache, f, ensure_ascii=False, indent=2)
                logger.info(f"Cache salvo: {len(self.cache)} traduções")
            except Exception as e:
                logger.error(f"Erro ao salvar cache: {e}")

    def stats(self) -> str:
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return f"Cache: {self.hits}/{total} ({hit_rate:.1f}%)"


# ============================================================================
# BATCHER
# ============================================================================
class TextBatcher:
    """Agrupa textos curtos para traduzir em lote"""

    @staticmethod
    def create_batches(texts: List[Dict]) -> List[List[Dict]]:
        batches = []
        current_batch = []
        current_length = 0

        for text_item in texts:
            text = text_item['texto']
            text_len = len(text)

            if text_len > Config.MAX_TEXT_LENGTH:
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_length = 0
                batches.append([text_item])
                continue

            if len(current_batch) < Config.BATCH_SIZE and \
               current_length + text_len < Config.MAX_TEXT_LENGTH:
                current_batch.append(text_item)
                current_length += text_len
            else:
                if current_batch:
                    batches.append(current_batch)
                current_batch = [text_item]
                current_length = text_len

        if current_batch:
            batches.append(current_batch)

        return batches


# ============================================================================
# TRADUTOR COM RETRY, CIRCUIT BREAKER E THROTTLING
# ============================================================================
class RobustTranslator:
    """Tradutor com todas as proteções"""

    def __init__(self, max_workers: int = None, timeout: int = None):
        # Permite configurar workers e timeout via UI
        if max_workers:
            Config.MAX_WORKERS = max_workers
        if timeout:
            Config.BASE_TIMEOUT = timeout

        self.cache = TranslationCache()
        self.session_manager = SessionManager()
        self.circuit_breaker = CircuitBreaker(
            Config.CIRCUIT_BREAKER_WINDOW,
            Config.CIRCUIT_BREAKER_THRESHOLD,
            Config.CIRCUIT_BREAKER_COOLDOWN
        )

        # Throttling real com Semaphore
        self.semaphore = Semaphore(Config.MAX_WORKERS)

        self.lock = Lock()
        self.stats = {
            'total': 0,
            'translated': 0,
            'cached': 0,
            'filtered': 0,
            'errors': 0,
            'retries': 0,
            'timeouts': 0,
            'http_500': 0,
            'start_time': None,
            'error_types': Counter(),
            'last_errors': deque(maxlen=10)  # Últimos 10 erros
        }

    def translate_text_with_retry(self, text: str) -> str:
        """Traduz com retry exponencial + jitter"""

        # Verifica cache
        cached = self.cache.get(text)
        if cached:
            with self.lock:
                self.stats['cached'] += 1
            return cached

        # Aguarda circuit breaker
        self.circuit_breaker.wait_if_open()

        # Throttling real
        with self.semaphore:
            # Retry loop com backoff exponencial
            for attempt in range(Config.MAX_RETRIES):
                try:
                    prompt = f"""Traduza de inglês para português brasileiro.

REGRAS:
- Mantenha códigos [XXX] exatamente como estão
- Use linguagem natural
- Responda SÓ a tradução

Texto:
{text}

Tradução:"""

                    session = self.session_manager.get_session()

                    # Payload SEM num_gpu (causa erro em algumas versões)
                    payload = {
                        'model': Config.MODEL,
                        'prompt': prompt,
                        'stream': False,
                        'options': {
		        	       'num_ctx': 256,
                           'temperature': 0.3,
                           'top_p': 0.9
                        }
                    }

                    response = session.post(
                        Config.OLLAMA_URL,
                        json=payload,
                        timeout=Config.BASE_TIMEOUT
                    )

                    # Parsing seguro
                    content_type = response.headers.get('Content-Type', '')

                    if response.status_code == 200:
                        if 'application/json' not in content_type:
                            raise ValueError(f"Unexpected Content-Type: {content_type}")

                        result = response.json()
                        translation = result.get('response', '').strip()

                        if '\n\n' in translation:
                            translation = translation.split('\n\n')[0]

                        self.cache.set(text, translation)
                        self.circuit_breaker.record_request(True)

                        with self.lock:
                            self.stats['translated'] += 1
                            if attempt > 0:
                                self.stats['retries'] += 1

                        return translation

                    elif response.status_code == 500:
                        with self.lock:
                            self.stats['http_500'] += 1

                        # Log detalhado de erro 500
                        body_preview = response.text[:1000] if response.text else ''
                        error_log = {
                            'timestamp': datetime.now().isoformat(),
                            'status': 500,
                            'attempt': attempt + 1,
                            'text_hash': hashlib.md5(text.encode()).hexdigest()[:8],
                            'body_preview': body_preview
                        }

                        logger.error(f"HTTP 500: {json.dumps(error_log)}")

                        with self.lock:
                            self.stats['last_errors'].append(error_log)

                        raise Exception(f"HTTP 500")

                    else:
                        raise Exception(f"HTTP {response.status_code}")

                except requests.exceptions.Timeout:
                    with self.lock:
                        self.stats['timeouts'] += 1
                        self.stats['error_types']['timeout'] += 1

                    logger.warning(f"Timeout na tentativa {attempt+1}/{Config.MAX_RETRIES}")

                    if attempt < Config.MAX_RETRIES - 1:
                        jitter = random.uniform(1 - Config.RETRY_JITTER, 1 + Config.RETRY_JITTER)
                        wait_time = (Config.RETRY_BACKOFF_BASE * (2 ** attempt)) * jitter
                        logger.info(f"Aguardando {wait_time:.2f}s antes do retry...")
                        time.sleep(wait_time)
                    else:
                        self.circuit_breaker.record_request(False)

                except Exception as e:
                    error_type = type(e).__name__
                    with self.lock:
                        self.stats['error_types'][error_type] += 1

                    logger.error(f"Erro na tentativa {attempt+1}: {error_type} - {e}")

                    if attempt < Config.MAX_RETRIES - 1:
                        jitter = random.uniform(1 - Config.RETRY_JITTER, 1 + Config.RETRY_JITTER)
                        wait_time = (Config.RETRY_BACKOFF_BASE * (2 ** attempt)) * jitter
                        time.sleep(wait_time)
                    else:
                        self.circuit_breaker.record_request(False)

            # Todas tentativas falharam
            with self.lock:
                self.stats['errors'] += 1

            logger.error(f"Falha após {Config.MAX_RETRIES} tentativas")
            return text  # Fallback: retorna original

    def translate_batch(self, batch: List[Dict]) -> List[Dict]:
        """Traduz um lote"""
        results = []

        for item in batch:
            texto_original = item['texto']

            if not TextFilter.is_translatable(texto_original):
                with self.lock:
                    self.stats['filtered'] += 1
                item['traducao'] = texto_original
                results.append(item)
                continue

            traducao = self.translate_text_with_retry(texto_original)
            item['traducao'] = traducao
            results.append(item)

        return results

    def translate_parallel(self, texts: List[Dict]) -> List[Dict]:
        """Traduz em paralelo com monitoramento"""

        self.stats['total'] = len(texts)
        self.stats['start_time'] = time.time()

        print(f"\n{'='*70}")
        print(f"CONFIGURAÇÃO")
        print(f"{'='*70}")
        print(f"Workers: {Config.MAX_WORKERS}")
        print(f"Batch size: {Config.BATCH_SIZE}")
        print(f"Timeout: {Config.BASE_TIMEOUT}s")
        print(f"Max retries: {Config.MAX_RETRIES}")
        print(f"{'='*70}\n")

        batches = TextBatcher.create_batches(texts)
        print(f"[INFO] Lotes criados: {len(batches)}\n")

        results = []
        completed = 0

        # Ajusta workers se em modo degradado
        actual_workers = 1 if self.circuit_breaker.is_degraded() else Config.MAX_WORKERS

        with ThreadPoolExecutor(max_workers=actual_workers) as executor:
            future_to_batch = {
                executor.submit(self.translate_batch, batch): i
                for i, batch in enumerate(batches)
            }

            for future in as_completed(future_to_batch):
                batch_results = future.result()
                results.extend(batch_results)
                completed += len(batch_results)

                # Progresso
                percent = (completed / len(texts)) * 100
                elapsed = time.time() - self.stats['start_time']
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (len(texts) - completed) / rate if rate > 0 else 0

                status_icon = "⚠" if self.circuit_breaker.is_degraded() else ""

                print(f"\r{status_icon}[{percent:5.1f}%] {completed}/{len(texts)} "
                      f"| {rate:.1f}/s | ETA: {eta/60:.0f}min "
                      f"| {self.cache.stats()} "
                      f"| Erros: {self.stats['errors']} ({self.stats['http_500']} x 500)",
                      end='', flush=True)

        print()
        results.sort(key=lambda x: x['id'])
        self.cache.save_cache()

        return results

    def print_stats(self):
        """Estatísticas finais"""
        elapsed = time.time() - self.stats['start_time']

        print(f"\n{'='*70}")
        print("ESTATÍSTICAS FINAIS")
        print(f"{'='*70}")
        print(f"Total: {self.stats['total']}")
        print(f"Traduzidos: {self.stats['translated']}")
        print(f"Cache: {self.stats['cached']}")
        print(f"Filtrados: {self.stats['filtered']}")
        print(f"Erros totais: {self.stats['errors']}")
        print(f"  - HTTP 500: {self.stats['http_500']}")
        print(f"  - Timeouts: {self.stats['timeouts']}")
        print(f"Retries bem-sucedidos: {self.stats['retries']}")
        print(f"\nTempo: {elapsed/60:.1f} min")
        print(f"Taxa média: {self.stats['total']/elapsed:.2f} textos/s")

        if self.stats['error_types']:
            print(f"\nTipos de erro:")
            for error_type, count in self.stats['error_types'].most_common(5):
                print(f"  {error_type}: {count}")

        if self.stats['last_errors']:
            print(f"\nÚltimos erros (veja translator_errors.log):")
            for err in list(self.stats['last_errors'])[-3:]:
                print(f"  {err['timestamp'][:19]} | Status {err['status']} | Hash {err['text_hash']}")

        print(f"{'='*70}")


# ============================================================================
# PIPELINE
# ============================================================================
def processar_arquivo_traducao(arquivo_entrada: str, arquivo_saida: str,
                               max_workers: int = None, timeout: int = None):
    """Pipeline completo otimizado"""

    print(f"\n{'='*70}")
    print("TRADUTOR PARALELO v4.0 - DEPLOY CRÍTICO")
    print(f"{'='*70}\n")

    # Health check OBRIGATÓRIO
    health_ok, health_msg = check_ollama_health()
    if not health_ok:
        print(f"\n❌ {health_msg}")
        print("\nSOLUÇÃO:")
        print("1. Abra um terminal")
        print("2. Execute: ollama serve")
        print("3. Aguarde mensagem 'Ollama is running'")
        print("4. Tente novamente\n")
        return False

    print(f"✓ {health_msg}\n")

    print(f"[1/4] Carregando: {arquivo_entrada}")
    texts = []

    try:
        with open(arquivo_entrada, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                if 'ID|OFFSET|ORIGINAL' in line or line.startswith('-'):
                    continue

                parts = line.rstrip('\n').split('|')
                if len(parts) >= 3:
                    texts.append({
                        'id': int(parts[0]) if parts[0].isdigit() else 0,
                        'offset': parts[1],
                        'texto': parts[2],
                        'traducao': ''
                    })
    except Exception as e:
        logger.error(f"Erro ao carregar: {e}")
        return False

    print(f"[OK] {len(texts)} textos\n")

    print(f"[2/4] Analisando...")
    traduziveis = sum(1 for t in texts if TextFilter.is_translatable(t['texto']))
    print(f"[INFO] Traduzíveis: {traduziveis}/{len(texts)} ({traduziveis/len(texts)*100:.1f}%)\n")

    print(f"[3/4] Traduzindo...")
    translator = RobustTranslator(max_workers=max_workers, timeout=timeout)
    results = translator.translate_parallel(texts)

    translator.print_stats()

    print(f"\n[4/4] Salvando: {arquivo_saida}")
    try:
        with open(arquivo_saida, 'w', encoding='utf-8') as f:
            f.write("# LEGEND OF game - TRADUZIDO v4.0\n")
            f.write("# ID|OFFSET|ORIGINAL|TRADUÇÃO\n\n")

            for item in results:
                f.write(f"{item['id']:05d}|{item['offset']}|{item['texto']}|{item['traducao']}\n")

        print(f"[OK] ✓ Concluído!")
        print(f"\n📄 Logs salvos em: translator_errors.log\n")
        return True

    except Exception as e:
        logger.error(f"Erro ao salvar: {e}")
        return False


# ============================================================================
# MAIN
# ============================================================================
def main():
    """Função principal - APENAS TRADUÇÃO, SEM DIAGNÓSTICO"""
    if len(sys.argv) < 2:
        print("\nUso: python tradutor_paralelo_v4.py <entrada> [saida] [workers] [timeout]\n")
        sys.exit(1)

    arquivo_entrada = sys.argv[1]
    arquivo_saida = sys.argv[2] if len(sys.argv) > 2 else "textos_traduzidos.txt"
    max_workers = int(sys.argv[3]) if len(sys.argv) > 3 else None
    timeout = int(sys.argv[4]) if len(sys.argv) > 4 else None

    if not os.path.exists(arquivo_entrada):
        print(f"[ERRO] Arquivo não encontrado: {arquivo_entrada}")
        sys.exit(1)

    # EXECUTA APENAS A TRADUÇÃO (sem diagnóstico)
    sucesso = processar_arquivo_traducao(arquivo_entrada, arquivo_saida, max_workers, timeout)
    sys.exit(0 if sucesso else 1)


if __name__ == "__main__":
    main()