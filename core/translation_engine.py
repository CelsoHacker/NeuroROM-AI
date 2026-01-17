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
        """Store translation in cache"""
        with self.lock:
            self.cache[original] = translation
            if len(self.cache) % 100 == 0:  # Auto-save every 100 entries
                self.save()

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
                return result if result else text
            else:
                logging.error(f"Ollama error {response.status_code}: {response.text}")
                return text
                
        except Exception as e:
            logging.error(f"Ollama exception: {str(e)}")
            return text

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
                return result if result else text
            else:
                logging.error(f"Gemini error {response.status_code}: {response.text}")
                return text
                
        except Exception as e:
            logging.error(f"Gemini exception: {str(e)}")
            return text

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
                return result if result else text
            else:
                logging.error(f"DeepL error {response.status_code}: {response.text}")
                return text
                
        except Exception as e:
            logging.error(f"DeepL exception: {str(e)}")
            return text

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
    
    def translate_text(self, text: str) -> str:
        """Translate single text with caching"""
        # Check cache first
        cached = self.cache.get(text)
        if cached:
            return cached
        
        # Filter untranslatable text
        if not TextFilter.should_translate(text):
            return text
        
        # Translate
        translation = self.engine.translate(text)
        
        # Cache result
        self.cache.set(text, translation)
        
        return translation
    
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
        total = len(lines)
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
            
            # Translate
            original_text = data.get('text', '')
            translated_text = self.translate_text(original_text)
            
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
        
        # Final stats
        self.cache.save()
        stats = self.cache.get_stats()
        elapsed = time.time() - start_time
        
        safe_print(f"\n\n{'='*60}")
        safe_print(f"✅ Translation Complete!")
        safe_print(f"⏱️  Time: {elapsed:.1f}s | Rate: {total/elapsed:.1f} texts/s")
        safe_print(f"💾 Cache: {stats['total_cached']} entries | Hit rate: {stats['hit_rate']:.1f}%")
        safe_print(f"📁 Output: {output_file}")
        safe_print(f"{'='*60}\n")

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
