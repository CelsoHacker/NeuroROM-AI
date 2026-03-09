# -*- coding: utf-8 -*-
"""
================================================================================
ROM TRANSLATION FRAMEWORK - CORE ENGINE v5.8
================================================================================
Universal translation system for retro game ROMs using AI engines.

Features:
1. Multi-Engine Support: Gemini (Online), DeepL (Online), Ollama (Offline)
2. Robust Architecture: Caching, Rate Limiting, Retry Logic, File Logging
3. Hybrid Compatibility: Supports both simple (3-column) and advanced (5-column) formats
4. Smart Prompt Engineering: Built-in translation rules for gaming context

© 2025 - Open Source ROM Translation Framework
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

# UTF-8 Configuration for cross-platform compatibility
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
except: 
    pass

# Logging Configuration
logging.basicConfig(
    filename='translator_debug.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

def safe_print(*args, **kwargs):
    """Safe print function that handles encoding errors"""
    try: 
        print(*args, **kwargs)
    except: 
        pass

# ============================================================================
# 1. GLOBAL CONFIGURATION
# ============================================================================
class Config:
    """Central configuration for translation engines"""
    MODE = "offline"  # Options: offline, gemini, deepl
    GEMINI_API_KEY = ""
    DEEPL_API_KEY = ""

    # API Endpoints
    OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
    GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    DEEPL_URL = "https://api-free.deepl.com/v2/translate"

    # Performance Settings
    WORKERS = 1
    TIMEOUT = 60
    CACHE_FILE = "cache_translations.json"
    MIN_LENGTH = 2

# ============================================================================
# 2. TEXT FILTERING SYSTEM
# ============================================================================
class TextFilter:
    """Smart filters to identify non-translatable content"""
    IGNORE_PATTERNS = [
        re.compile(r'^[\x00-\x1F]+$'),  # Control characters
        re.compile(r'^[0-9A-F]{2,}(\s[0-9A-F]{2,})*$'),  # Hex codes
        re.compile(r'^[0-9\W]+$'),  # Numbers and symbols only
        re.compile(r'^[A-Z0-9_]{3,}$')  # System codes (e.g., PAD_INIT)
    ]

    @classmethod
    def should_translate(cls, text: str) -> bool:
        """Determine if text should be translated"""
        if not text or len(text.strip()) < Config.MIN_LENGTH: 
            return False
        for pattern in cls.IGNORE_PATTERNS:
            if pattern.match(text): 
                return False
        if not any(c.isalpha() for c in text): 
            return False
        return True

# ============================================================================
# 2.5. ENCODING FIX SYSTEM (MOJIBAKE CORRECTION)
# ============================================================================
class EncodingFixer:
    """
    Corrige problemas de encoding (mojibake) onde UTF-8 foi lido como Latin-1/CP1252.
    Exemplos: "Ã£" → "ã", "Ã©" → "é", "Ã§" → "ç"
    """

    # Mapeamento de sequências mojibake comuns para caracteres corretos
    MOJIBAKE_MAP = {
        # Vogais com acentos (português)
        'Ã¡': 'á', 'Ã ': 'à', 'Ã¢': 'â', 'Ã£': 'ã', 'Ã¤': 'ä',
        'Ã©': 'é', 'Ã¨': 'è', 'Ãª': 'ê', 'Ã«': 'ë',
        'Ã­': 'í', 'Ã¬': 'ì', 'Ã®': 'î', 'Ã¯': 'ï',
        'Ã³': 'ó', 'Ã²': 'ò', 'Ã´': 'ô', 'Ãµ': 'õ', 'Ã¶': 'ö',
        'Ãº': 'ú', 'Ã¹': 'ù', 'Ã»': 'û', 'Ã¼': 'ü',
        # Maiúsculas
        'Ã': 'Á', 'Ã€': 'À', 'Ã‚': 'Â', 'Ãƒ': 'Ã', 'Ã„': 'Ä',
        'Ã‰': 'É', 'Ãˆ': 'È', 'ÃŠ': 'Ê', 'Ã‹': 'Ë',
        'Ã': 'Í', 'ÃŒ': 'Ì', 'ÃŽ': 'Î', 'Ã': 'Ï',
        "Ã“": "Ó", "Ã’": "Ò", "Ã”": "Ô", "Ã•": "Õ", "Ã–": "Ö",
        'Ãš': 'Ú', 'Ã™': 'Ù', 'Ã›': 'Û', 'Ãœ': 'Ü',
        # Consoantes especiais
        'Ã§': 'ç', 'Ã‡': 'Ç',
        'Ã±': 'ñ', "Ã‘": "Ñ",
        # Símbolos
        'â€œ': '"', 'â€': '"', 'â€™': "'", 'â€˜': "'",
        'â€"': '—', 'â€"': '–', 'â€¦': '…',
        'Â°': '°', 'Â©': '©', 'Â®': '®', 'â„¢': '™',
        'Â«': '«', 'Â»': '»',
        'Â¡': '¡', 'Â¿': '¿',
        # Outros caracteres comuns
        'Ã½': 'ý', 'Ã¿': 'ÿ',
        'Ã°': 'ð', 'Ã': 'Ð',
        'Ã¦': 'æ', 'Ã†': 'Æ',
        'Ã¸': 'ø', 'Ã˜': 'Ø',
        'ÃŸ': 'ß',
    }

    @classmethod
    def fix_encoding(cls, text: str) -> str:
        """
        Corrige mojibake no texto traduzido.
        Usa duas estratégias:
        1. Mapeamento direto de sequências conhecidas
        2. Tentativa de decode/encode para casos não mapeados
        """
        if not text:
            return text

        result = text

        # Estratégia 1: Substituição direta de sequências conhecidas
        for bad, good in cls.MOJIBAKE_MAP.items():
            if bad in result:
                result = result.replace(bad, good)

        # Estratégia 2: Tenta corrigir via encode/decode se ainda houver problemas
        # Detecta se ainda há caracteres suspeitos (sequências Ã + outro char)
        if 'Ã' in result or 'â€' in result:
            try:
                # Tenta converter de volta: Latin-1 → bytes → UTF-8
                fixed = result.encode('latin-1').decode('utf-8')
                # Verifica se o resultado é válido (não tem caracteres de controle)
                if not any(ord(c) < 32 and c not in '\n\r\t' for c in fixed):
                    result = fixed
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass  # Mantém o resultado do mapeamento

        return result

    @classmethod
    def fix_file(cls, file_path: str, output_path: str = None) -> int:
        """
        Corrige encoding de um arquivo inteiro.
        Retorna o número de correções feitas.
        """
        if not output_path:
            output_path = file_path  # Sobrescreve o original

        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        original = content
        fixed = cls.fix_encoding(content)

        if fixed != original:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(fixed)

            # Conta aproximadamente quantas correções foram feitas
            corrections = sum(1 for bad in cls.MOJIBAKE_MAP if bad in original)
            safe_print(f"✅ Encoding corrigido: {corrections} substituições em {output_path}")
            return corrections

        return 0

# ============================================================================
# 3. CACHING SYSTEM
# ============================================================================
class TranslationCache:
    """Persistent cache to avoid re-translating identical strings"""
    def __init__(self):
        self.cache = {}
        self.lock = Lock()
        self.hits = 0
        self.misses = 0
        self.load()

    def load(self):
        """Load cache from disk"""
        if os.path.exists(Config.CACHE_FILE):
            try:
                with open(Config.CACHE_FILE, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                safe_print(f"✅ Loaded {len(self.cache)} cached translations")
            except Exception as e:
                logging.error(f"Cache load error: {e}")

    def save(self):
        """Save cache to disk"""
        try:
            with open(Config.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Cache save error: {e}")

    def get(self, text: str) -> str:
        """Get translation from cache"""
        with self.lock:
            if text in self.cache:
                self.hits += 1
                return self.cache[text]
            self.misses += 1
            return None

    def set(self, original: str, translation: str):
        """Store translation in cache - only if actually translated"""
        with self.lock:
            # ANTI-CACHE FALSO: não salva se tradução == original
            original_clean = original.strip().lower()
            translation_clean = translation.strip().lower()

            if original_clean == translation_clean:
                logging.warning(f"Cache REJECTED (same as original): {original[:50]}")
                return False  # Indica que não foi cacheado

            # Não salva se tradução está vazia ou é muito curta
            if not translation.strip() or len(translation.strip()) < 2:
                logging.warning(f"Cache REJECTED (empty/short): {original[:50]}")
                return False

            self.cache[original] = translation
            if len(self.cache) % 100 == 0:  # Auto-save every 100 entries
                self.save()
            return True

    def get_stats(self):
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': hit_rate,
            'total_cached': len(self.cache)
        }

# ============================================================================
# 4. TRANSLATION ENGINES
# ============================================================================
class TranslationEngine:
    """Base class for translation engines"""
    
    @staticmethod
    def build_prompt(text: str) -> str:
        """Build optimized prompt for gaming translation"""
        return f"""Translate this game text from English to Brazilian Portuguese.

CRITICAL RULES:
1. Keep proper nouns (character/place names) in ENGLISH
2. Preserve ALL formatting: {{brackets}}, [codes], symbols
3. Maintain line breaks and spacing exactly
4. Keep technical terms (HP, MP, EXP) as-is
5. Return ONLY the translation, no explanations

TEXT: {text}

TRANSLATION:"""

class OllamaEngine(TranslationEngine):
    """Offline translation using Ollama"""
    
    @staticmethod
    def translate(text: str) -> str:
        """Translate using local Ollama model"""
        try:
            payload = {
                "model": "gemma:2b",
                "prompt": TranslationEngine.build_prompt(text),
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9
                }
            }
            
            response = requests.post(
                Config.OLLAMA_URL,
                json=payload,
                timeout=Config.TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json().get("response", "").strip()
                # Clean up common AI artifacts
                result = re.sub(r'^(TRANSLATION:|Translation:)\s*', '', result, flags=re.IGNORECASE)

                # VALIDAÇÃO: se resultado == original, retorna None (falhou)
                if not result or result.strip().lower() == text.strip().lower():
                    logging.warning(f"Ollama returned same text: {text[:50]}")
                    return None

                return result
            else:
                logging.error(f"Ollama error {response.status_code}: {response.text}")
                return None

        except Exception as e:
            logging.error(f"Ollama exception: {str(e)}")
            return None

class GeminiEngine(TranslationEngine):
    """Online translation using Google Gemini API"""
    
    @staticmethod
    def translate(text: str) -> str:
        """Translate using Gemini Pro"""
        if not Config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not configured")
        
        try:
            url = f"{Config.GEMINI_URL}?key={Config.GEMINI_API_KEY}"
            payload = {
                "contents": [{
                    "parts": [{"text": TranslationEngine.build_prompt(text)}]
                }],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 200
                }
            }
            
            response = requests.post(url, json=payload, timeout=Config.TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                result = data['candidates'][0]['content']['parts'][0]['text'].strip()

                # VALIDAÇÃO: se resultado == original, retorna None
                if not result or result.strip().lower() == text.strip().lower():
                    logging.warning(f"Gemini returned same text: {text[:50]}")
                    return None

                return result
            else:
                logging.error(f"Gemini error {response.status_code}: {response.text}")
                return None

        except Exception as e:
            logging.error(f"Gemini exception: {str(e)}")
            return None

class DeepLEngine(TranslationEngine):
    """Professional translation using DeepL API"""
    
    @staticmethod
    def translate(text: str) -> str:
        """Translate using DeepL"""
        if not Config.DEEPL_API_KEY:
            raise ValueError("DEEPL_API_KEY not configured")
        
        try:
            payload = {
                "auth_key": Config.DEEPL_API_KEY,
                "text": text,
                "source_lang": "EN",
                "target_lang": "PT-BR",
                "preserve_formatting": True
            }
            
            response = requests.post(
                Config.DEEPL_URL,
                data=payload,
                timeout=Config.TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()['translations'][0]['text']

                # VALIDAÇÃO: se resultado == original, retorna None
                if not result or result.strip().lower() == text.strip().lower():
                    logging.warning(f"DeepL returned same text: {text[:50]}")
                    return None

                return result
            else:
                logging.error(f"DeepL error {response.status_code}: {response.text}")
                return None

        except Exception as e:
            logging.error(f"DeepL exception: {str(e)}")
            return None

# ============================================================================
# 5. FILE FORMAT HANDLERS
# ============================================================================
class FileFormatHandler:
    """Handle different ROM text dump formats"""
    
    @staticmethod
    def detect_format(line: str) -> str:
        """Detect file format type"""
        parts = line.split('|')
        if len(parts) == 5:
            return "advanced"  # Advanced format with compression info
        elif len(parts) == 3:
            return "simple"  # Simple format
        else:
            return "unknown"
    
    @staticmethod
    def parse_line(line: str, format_type: str):
        """Parse line according to format"""
        if format_type == "advanced":
            parts = line.split('|')
            if len(parts) == 5:
                return {
                    'address': parts[0],
                    'compression': parts[1],
                    'text': parts[2],
                    'extra1': parts[3],
                    'extra2': parts[4]
                }
        elif format_type == "simple":
            parts = line.split('|')
            if len(parts) == 3:
                return {
                    'address': parts[0],
                    'text': parts[1],
                    'extra': parts[2]
                }
        return None
    
    @staticmethod
    def rebuild_line(data: dict, translation: str, format_type: str) -> str:
        """Rebuild line with translation"""
        if format_type == "advanced":
            return f"{data['address']}|{data['compression']}|{translation}|{data['extra1']}|{data['extra2']}"
        elif format_type == "simple":
            return f"{data['address']}|{translation}|{data['extra']}"
        return translation

# ============================================================================
# 6. MAIN TRANSLATOR CLASS
# ============================================================================
class ROMTranslator:
    """Main translation orchestrator"""
    
    def __init__(self, mode: str = "offline"):
        self.cache = TranslationCache()
        self.mode = mode
        self.engine = self._get_engine()
        
    def _get_engine(self):
        """Select translation engine based on mode"""
        engines = {
            'offline': OllamaEngine,
            'gemini': GeminiEngine,
            'deepl': DeepLEngine
        }
        return engines.get(self.mode, OllamaEngine)
    
    def translate_text(self, text: str, max_retries: int = 2) -> tuple:
        """
        Translate single text with caching.
        Returns: (translation, success_flag)
        """
        # Check cache first
        cached = self.cache.get(text)
        if cached:
            return (cached, True)

        # Filter untranslatable text
        if not TextFilter.should_translate(text):
            return (text, True)  # Não precisa traduzir, mas não é falha

        # Tenta traduzir com retries
        translation = None
        for attempt in range(max_retries):
            translation = self.engine.translate(text)

            if translation is not None:
                # Aplica correção de encoding (mojibake)
                translation = EncodingFixer.fix_encoding(translation)

                # Tradução bem-sucedida - salva no cache
                if self.cache.set(text, translation):
                    return (translation, True)
                else:
                    # Cache rejeitou (igual ao original) - tenta novamente
                    logging.warning(f"Retry {attempt+1}: translation same as original")
                    continue

        # Todas tentativas falharam
        logging.error(f"FAILED after {max_retries} attempts: {text[:50]}")
        return (text, False)  # Retorna original + flag de falha
    
    def translate_file(self, input_file: str, output_file: str = None):
        """Translate entire file"""
        if not output_file:
            output_file = input_file.replace('.txt', '_translated.txt')
        
        safe_print(f"\n🚀 ROM Translation Framework")
        safe_print(f"📂 Input: {input_file}")
        safe_print(f"📝 Output: {output_file}")
        safe_print(f"🔧 Mode: {self.mode.upper()}")
        safe_print(f"{'='*60}\n")
        
        # Read file
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Detect format
        format_type = FileFormatHandler.detect_format(lines[0]) if lines else "unknown"
        safe_print(f"📋 Detected format: {format_type}")
        
        translated_lines = []
        failed_lines = []  # Rastreia linhas que falharam
        total = len(lines)
        success_count = 0
        fail_count = 0
        start_time = time.time()

        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                translated_lines.append('')
                continue

            # Parse line
            data = FileFormatHandler.parse_line(line, format_type)
            if not data:
                translated_lines.append(line)
                continue

            # Translate - agora retorna (texto, sucesso)
            original_text = data.get('text', '')
            translated_text, success = self.translate_text(original_text)

            if success:
                success_count += 1
            else:
                fail_count += 1
                failed_lines.append({'line': i, 'text': original_text})

            # Rebuild line
            new_line = FileFormatHandler.rebuild_line(data, translated_text, format_type)
            translated_lines.append(new_line)

            # Progress
            if i % 100 == 0 or i == total:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                safe_print(f"Progress: {i}/{total} ({i/total*100:.1f}%) | {rate:.1f} texts/s", end='\r')

        # Save result
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(translated_lines))

        # Save failed lines report (se houver falhas)
        if failed_lines:
            fail_report = output_file.replace('.txt', '_FAILED.txt')
            with open(fail_report, 'w', encoding='utf-8') as f:
                f.write(f"# Translation Failures Report\n")
                f.write(f"# Total: {len(failed_lines)} lines failed\n")
                f.write(f"# These lines were NOT translated and need manual review\n")
                f.write("=" * 60 + "\n\n")
                for item in failed_lines:
                    f.write(f"Line {item['line']}: {item['text']}\n")
            safe_print(f"\n⚠️  {len(failed_lines)} lines failed - see {fail_report}")

        # Final stats
        self.cache.save()
        stats = self.cache.get_stats()
        elapsed = time.time() - start_time

        safe_print(f"\n\n{'='*60}")
        safe_print(f"✅ Translation Complete!")
        safe_print(f"📊 Success: {success_count} | Failed: {fail_count}")
        safe_print(f"⏱️  Time: {elapsed:.1f}s | Rate: {total/elapsed:.1f} texts/s")
        safe_print(f"💾 Cache: {stats['total_cached']} entries | Hit rate: {stats['hit_rate']:.1f}%")
        safe_print(f"📁 Output: {output_file}")
        safe_print(f"{'='*60}\n")


def strip_accents_for_rom(text: str) -> str:
    """Remove acentos para ROMs/fontes sem suporte PT-BR."""
    if not isinstance(text, str) or not text:
        return ""
    replacements = {
        "ã": "a",
        "ê": "e",
        "ç": "c",
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "â": "a",
        "õ": "o",
        "à": "a",
        "Ã": "A",
        "Ê": "E",
        "Ç": "C",
        "Á": "A",
        "É": "E",
        "Í": "I",
        "Ó": "O",
        "Ú": "U",
        "Â": "A",
        "Õ": "O",
        "À": "A",
    }
    out = text
    for src, dst in replacements.items():
        out = out.replace(src, dst)
    return out


def _safe_json_load(path: str) -> dict:
    try:
        if not path or not os.path.isfile(path):
            return {}
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _extract_font_has_pt_br(payload: dict) -> bool | None:
    if not isinstance(payload, dict):
        return None
    candidates = [
        payload.get("font_has_pt_br"),
        (payload.get("font_profile") or {}).get("font_has_pt_br") if isinstance(payload.get("font_profile"), dict) else None,
        (payload.get("font_profile") or {}).get("has_pt_br") if isinstance(payload.get("font_profile"), dict) else None,
        (payload.get("profile") or {}).get("font_has_pt_br") if isinstance(payload.get("profile"), dict) else None,
        (payload.get("profile") or {}).get("has_pt_br") if isinstance(payload.get("profile"), dict) else None,
    ]
    for val in candidates:
        if isinstance(val, bool):
            return bool(val)
    return None


def _should_strip_accents_for_context(input_path: str | None = None) -> bool:
    """
    Retorna True quando o perfil não declara font_has_pt_br=true.
    Regras:
    - env NEUROROM_FONT_HAS_PT_BR tem prioridade;
    - depois tenta JSON via env NEUROROM_PROFILE_JSON;
    - depois tenta sidecars perto do arquivo de entrada;
    - ausente => assume sem suporte PT-BR (strip ativo).
    """
    env_flag = str(os.environ.get("NEUROROM_FONT_HAS_PT_BR", "") or "").strip().lower()
    if env_flag in {"1", "true", "yes", "on"}:
        return False
    if env_flag in {"0", "false", "no", "off"}:
        return True

    profile_env = str(os.environ.get("NEUROROM_PROFILE_JSON", "") or "").strip()
    if profile_env:
        flag = _extract_font_has_pt_br(_safe_json_load(profile_env))
        if isinstance(flag, bool):
            return not flag

    candidates = []
    if isinstance(input_path, str) and input_path.strip():
        p = os.path.abspath(input_path)
        root, _ = os.path.splitext(p)
        candidates.extend(
            [
                f"{root}.profile.json",
                f"{root}_profile.json",
                f"{root}.meta.json",
                f"{root}_meta.json",
            ]
        )
    for c in candidates:
        flag = _extract_font_has_pt_br(_safe_json_load(c))
        if isinstance(flag, bool):
            return not flag

    # Sem flag explícita => aplica strip por segurança.
    return True


def _install_romtranslator_font_policy_wrapper() -> None:
    """Instala wrapper em runtime sem editar os métodos originais."""
    if getattr(ROMTranslator, "_neurorom_font_policy_installed", False):
        return

    original_translate_text = ROMTranslator.translate_text
    original_translate_file = ROMTranslator.translate_file

    def _patched_translate_file(self, input_file: str, output_file: str = None):
        self._neurorom_input_file = input_file
        return original_translate_file(self, input_file, output_file)

    def _patched_translate_text(self, text: str, max_retries: int = 2) -> tuple:
        translated, success = original_translate_text(self, text, max_retries=max_retries)
        if not success:
            return translated, success
        context_path = getattr(self, "_neurorom_input_file", None)
        if _should_strip_accents_for_context(context_path):
            translated = strip_accents_for_rom(str(translated or ""))
        return translated, success

    ROMTranslator.translate_file = _patched_translate_file
    ROMTranslator.translate_text = _patched_translate_text
    ROMTranslator._neurorom_font_policy_installed = True


_install_romtranslator_font_policy_wrapper()

# ============================================================================
# 7. COMMAND LINE INTERFACE
# ============================================================================
def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='ROM Translation Framework - Universal game text translator'
    )
    parser.add_argument('input', help='Input text file to translate')
    parser.add_argument('output', nargs='?', help='Output file (optional)')
    parser.add_argument('--mode', choices=['offline', 'gemini', 'deepl'], 
                       default='offline', help='Translation engine')
    parser.add_argument('--gemini-key', help='Gemini API key')
    parser.add_argument('--deepl-key', help='DeepL API key')
    parser.add_argument('--workers', type=int, default=1, help='Parallel workers')
    
    args = parser.parse_args()
    
    # Configure
    Config.MODE = args.mode
    Config.WORKERS = args.workers
    
    if args.gemini_key:
        Config.GEMINI_API_KEY = args.gemini_key
    if args.deepl_key:
        Config.DEEPL_API_KEY = args.deepl_key
    
    # Translate
    translator = ROMTranslator(mode=args.mode)
    translator.translate_file(args.input, args.output)

if __name__ == "__main__":
    main()
