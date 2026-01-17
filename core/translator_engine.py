# -*- coding: utf-8 -*-
"""
================================================================================
TRADUTOR UNIVERSAL v5.8 - TITAN EDITION (CLAUDE + GEMINI FIX)
================================================================================
Funcionalidades Completas:
1. Multi-Engine: Gemini (Online), DeepL (Online), Ollama (Offline).
2. Robustez: Cache, Rate Limiting, Retry, Logging em Arquivo.
3. Compatibilidade Híbrida (A FIX DO CELSO):
   - Lê arquivos simples (3 colunas)
   - Lê arquivos LZSS/System (5 colunas)
4. Engenharia de Prompt: Regras de Ouro embutidas.
================================================================================
"""

import os
import sys
import json
import requests
import time
import logging
import re
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Configuração de UTF-8 para Windows
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
except: pass

# Configuração de Log
logging.basicConfig(
    filename='translator_debug.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

def safe_print(*args, **kwargs):
    try: print(*args, **kwargs)
    except: pass

# ============================================================================
# 1. CONFIGURAÇÃO GLOBAL
# ============================================================================
class Config:
    MODE = "offline"
    GEMINI_API_KEY = ""
    DEEPL_API_KEY = ""

    # URLs
    OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
    GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    DEEPL_URL = "https://api-free.deepl.com/v2/translate"

    WORKERS = 1
    TIMEOUT = 60
    CACHE_FILE = "cache_traducoes.json"
    MIN_LENGTH = 2

# ============================================================================
# 2. FILTROS DE SEGURANÇA
# ============================================================================
class TextFilter:
    IGNORE_PATTERNS = [
        re.compile(r'^[\x00-\x1F]+$'),
        re.compile(r'^[0-9A-F]{2,}(\s[0-9A-F]{2,})*$'),
        re.compile(r'^[0-9\W]+$'), # Só números ou simbolos
        re.compile(r'^[A-Z0-9_]{3,}$') # Códigos de sistema (ex: PAD_INIT)
    ]

    @classmethod
    def should_translate(cls, text: str) -> bool:
        if not text or len(text.strip()) < Config.MIN_LENGTH: return False
        for pattern in cls.IGNORE_PATTERNS:
            if pattern.match(text): return False
        if not any(c.isalpha() for c in text): return False
        return True

# ============================================================================
# 3. SISTEMA DE CACHE
# ============================================================================
class TranslationCache:
    def __init__(self):
        self.cache = {}
        self.lock = Lock()
        self.hits = 0
        self.misses = 0
        self.load()

    def load(self):
        if os.path.exists(Config.CACHE_FILE):
            try:
                with open(Config.CACHE_FILE, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
            except: pass

    def save(self):
        try:
            with open(Config.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except: pass

    def get(self, text):
        with self.lock:
            if text in self.cache:
                self.hits += 1
                return self.cache[text]
            self.misses += 1
            return None

    def set(self, text, trans):
        with self.lock:
            self.cache[text] = trans

    def stats(self):
        total = self.hits + self.misses
        perc = (self.hits / total * 100) if total > 0 else 0
        return f"Cache: {self.hits}/{total} ({perc:.1f}%)"

# ============================================================================
# 4. ENGINES DE TRADUÇÃO (COM AS REGRAS DE OURO)
# ============================================================================

class GeminiTranslator:
    def translate(self, text):
        if not Config.GEMINI_API_KEY: return "ERRO_NO_KEY"

        # --- PROMPT DE ENGENHARIA (AQUI ESTÁ O SEGREDO) ---
        sys_prompt = (
            "You are a Retro Game Localization AI.\n"
            "Task: Translate from English to Brazilian Portuguese (PT-BR).\n"
            "RULES:\n"
            "1. Keep formatting codes like {name}, %d, <br> EXACTLY as is.\n"
            "2. Do NOT add explanations. Output ONLY the translation.\n"
            "3. Keep it concise.\n"
            f"Original: {text}"
        )

        payload = {
            "contents": [{"parts": [{"text": sys_prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 200}
        }

        try:
            url = f"{Config.GEMINI_URL}?key={Config.GEMINI_API_KEY}"
            response = requests.post(url, json=payload, timeout=Config.TIMEOUT)

            if response.status_code == 429: return "RATE_LIMIT"
            if response.status_code == 200:
                try:
                    return response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                except: return text
            return text
        except: return text

class DeepLTranslator:
    def translate(self, text):
        if not Config.DEEPL_API_KEY: return "ERRO_NO_KEY"
        data = {'auth_key': Config.DEEPL_API_KEY, 'text': text, 'target_lang': 'PT-BR', 'source_lang': 'EN'}
        try:
            r = requests.post(Config.DEEPL_URL, data=data, timeout=Config.TIMEOUT)
            if r.status_code == 429: return "RATE_LIMIT"
            if r.status_code == 200: return r.json()['translations'][0]['text']
            return text
        except: return text

class OfflineTranslator:
    def translate(self, text):
        data = {'model': 'gemma:2b', 'prompt': f"Translate to PT-BR: {text}", 'stream': False}
        try:
            r = requests.post(Config.OLLAMA_URL, json=data, timeout=Config.TIMEOUT)
            if r.status_code == 200: return r.json()['response'].strip()
            return text
        except: return text

# ============================================================================
# 5. PROCESSADOR PRINCIPAL (LÓGICA HÍBRIDA DE COLUNAS)
# ============================================================================
def processar_traducao(arquivo_entrada, arquivo_saida):
    safe_print(f"\n{'='*70}")
    safe_print(f"TRADUTOR UNIVERSAL v5.8 TITAN (INTEGRADO)")
    safe_print(f"{'='*70}\n")

    cache = TranslationCache()

    if Config.MODE == "gemini": translator = GeminiTranslator()
    elif Config.MODE == "deepl": translator = DeepLTranslator()
    else: translator = OfflineTranslator()

    safe_print(f"Modo: {Config.MODE.upper()} | Workers: {Config.WORKERS}")

    # --- ETAPA 1: LEITURA INTELIGENTE (FIX DO CELSO) ---
    safe_print(f"[1/3] Carregando e analisando estrutura...")
    lines_to_process = []
    header_line = ""

    try:
        with open(arquivo_entrada, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('#'):
                    header_line = line.strip()
                    continue
                if not line.strip(): continue

                parts = line.strip().split('|')

                # LÓGICA DE DETECÇÃO DE FORMATO
                # Formato LZSS Novo: ID|OFFSET|TYPE|SIZE|TEXTO (5 colunas ou mais)
                # Formato Antigo: ID|OFFSET|TEXTO (3 colunas)

                entry = {'full_parts': parts, 'trans': ''}

                if len(parts) >= 5:
                    # Assume formato LZSS/System
                    entry['text_col_index'] = 4 # O texto começa no índice 4
                    entry['orig_text'] = "|".join(parts[4:]) # Junta caso tenha pipes no texto
                elif len(parts) >= 3:
                    # Assume formato simples
                    entry['text_col_index'] = 2
                    entry['orig_text'] = "|".join(parts[2:])
                else:
                    continue # Linha inválida

                lines_to_process.append(entry)

    except Exception as e:
        safe_print(f"ERRO CRÍTICO: {e}")
        return False

    total = len(lines_to_process)
    safe_print(f"[OK] {total} linhas válidas carregadas.")
    safe_print(f"[2/3] Iniciando tradução...\n")

    # --- ETAPA 2: TRADUÇÃO PARALELA ---
    completed = 0
    start_time = time.time()

    def worker(item):
        text = item['orig_text']

        cached = cache.get(text)
        if cached: return cached

        if not TextFilter.should_translate(text): return text

        attempts = 0
        while attempts < 3:
            res = translator.translate(text)
            if res == "RATE_LIMIT":
                time.sleep(5 * (attempts + 1))
                attempts += 1
                continue
            if res == "ERRO_NO_KEY": return text

            if res and res != text:
                cache.set(text, res)
                return res
            break
        return text

    with ThreadPoolExecutor(max_workers=Config.WORKERS) as pool:
        futures = {pool.submit(worker, item): item for item in lines_to_process}

        for future in as_completed(futures):
            item = futures[future]
            try:
                item['trans'] = future.result()
            except:
                item['trans'] = item['orig_text']

            completed += 1
            if completed % 5 == 0 or completed == total:
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (total - completed) / rate if rate > 0 else 0
                print(f"[{completed/total*100:5.1f}%] {completed}/{total} | {rate:.1f}/s | ETA: {int(eta)}s | {cache.stats()}")
                sys.stdout.flush()

    cache.save()

    # --- ETAPA 3: RECONSTRUÇÃO DO ARQUIVO (FIX DO CELSO) ---
    safe_print(f"\n[3/3] Salvando arquivo final...")
    try:
        with open(arquivo_saida, 'w', encoding='utf-8') as f:
            # Escreve cabeçalho original ou padrão
            if header_line:
                f.write(header_line + "\n")
            else:
                f.write("# ID|OFFSET|TYPE|SIZE|TEXT\n")

            for item in lines_to_process:
                parts = item['full_parts']
                idx = item['text_col_index']

                # Reconstrói a linha: Metadados Originais + Tradução Limpa
                prefix = "|".join(parts[:idx])
                clean_trans = item['trans'].replace('\n', ' ').replace('\r', '')

                f.write(f"{prefix}|{clean_trans}\n")

        safe_print("[SUCESSO] Arquivo gerado perfeitamente.")
        return True
    except Exception as e:
        safe_print(f"ERRO ao salvar: {e}")
        return False

# ============================================================================
# 6. ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('input')
    parser.add_argument('output')
    parser.add_argument('--mode', default='offline')
    parser.add_argument('--gemini-key', default='')
    parser.add_argument('--deepl-key', default='')
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--timeout', type=int, default=60)

    args = parser.parse_args()
    Config.MODE = args.mode
    Config.GEMINI_API_KEY = args.gemini_key
    Config.DEEPL_API_KEY = args.deepl_key
    Config.WORKERS = args.workers
    Config.TIMEOUT = args.timeout

    processar_traducao(args.input, args.output)