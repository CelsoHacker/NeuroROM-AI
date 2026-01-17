# -*- coding: utf-8 -*-
"""
================================================================================
PC TRANSLATION CACHE - Cache de Traduções para Economia de API
================================================================================
Evita traduzir textos já traduzidos anteriormente:
- Cache baseado em hash MD5 do texto original
- Armazena traduções em JSON
- Economia massiva em traduções repetidas
- Útil para múltiplas versões do mesmo jogo

NÃO requer modificação de código existente - módulo opcional
================================================================================
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime


class TranslationCache:
    """
    Cache de traduções para economizar chamadas de API.
    Armazena traduções por hash MD5 do texto original.
    """

    def __init__(self, cache_file: str = "translation_cache.json"):
        """
        Args:
            cache_file: Caminho do arquivo de cache
        """
        self.cache_file = Path(cache_file)
        self.cache: Dict[str, Dict] = {}

        # Carrega cache existente
        if self.cache_file.exists():
            self._load_cache()
        else:
            self.cache = {
                'metadata': {
                    'created': datetime.now().isoformat(),
                    'version': '1.0',
                    'total_entries': 0
                },
                'translations': {}
            }

    def _load_cache(self):
        """Carrega cache do arquivo JSON."""
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                self.cache = json.load(f)

            # Migração de versões antigas (se necessário)
            if 'metadata' not in self.cache:
                self.cache = {
                    'metadata': {
                        'created': datetime.now().isoformat(),
                        'version': '1.0',
                        'total_entries': len(self.cache)
                    },
                    'translations': self.cache  # Cache antigo vira translations
                }

        except Exception as e:
            print(f"⚠️  Warning: Failed to load cache: {e}")
            self.cache = {
                'metadata': {
                    'created': datetime.now().isoformat(),
                    'version': '1.0',
                    'total_entries': 0
                },
                'translations': {}
            }

    def save_cache(self):
        """Salva cache em arquivo JSON."""
        try:
            # Atualiza metadata
            self.cache['metadata']['total_entries'] = len(self.cache['translations'])
            self.cache['metadata']['last_updated'] = datetime.now().isoformat()

            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"❌ Error saving cache: {e}")

    def _hash_text(self, text: str, target_language: str = "Portuguese (Brazil)") -> str:
        """
        Gera hash MD5 do texto + idioma alvo.

        Args:
            text: Texto original
            target_language: Idioma alvo

        Returns:
            Hash MD5
        """
        combined = f"{text}|{target_language}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest()

    def get(self, text: str, target_language: str = "Portuguese (Brazil)") -> Optional[str]:
        """
        Busca tradução no cache.

        Args:
            text: Texto original
            target_language: Idioma alvo

        Returns:
            Tradução em cache ou None
        """
        text_hash = self._hash_text(text, target_language)

        if text_hash in self.cache['translations']:
            entry = self.cache['translations'][text_hash]
            # Atualiza contador de hits
            entry['hits'] = entry.get('hits', 0) + 1
            entry['last_used'] = datetime.now().isoformat()
            return entry['translated']

        return None

    def set(self, text: str, translation: str, target_language: str = "Portuguese (Brazil)"):
        """
        Armazena tradução no cache.

        Args:
            text: Texto original
            translation: Tradução
            target_language: Idioma alvo
        """
        text_hash = self._hash_text(text, target_language)

        self.cache['translations'][text_hash] = {
            'original': text,
            'translated': translation,
            'target_language': target_language,
            'created': datetime.now().isoformat(),
            'last_used': datetime.now().isoformat(),
            'hits': 1
        }

    def get_batch(self, texts: list, target_language: str = "Portuguese (Brazil)") -> Tuple[Dict[int, str], list]:
        """
        Busca múltiplas traduções no cache.

        Args:
            texts: Lista de textos originais
            target_language: Idioma alvo

        Returns:
            (cached_translations, uncached_texts)
            - cached_translations: {index: translation}
            - uncached_texts: [(index, text)]
        """
        cached = {}
        uncached = []

        for i, text in enumerate(texts):
            translation = self.get(text, target_language)

            if translation:
                cached[i] = translation
            else:
                uncached.append((i, text))

        return cached, uncached

    def set_batch(self, texts: list, translations: list, target_language: str = "Portuguese (Brazil)"):
        """
        Armazena múltiplas traduções no cache.

        Args:
            texts: Lista de textos originais
            translations: Lista de traduções
            target_language: Idioma alvo
        """
        for text, translation in zip(texts, translations):
            self.set(text, translation, target_language)

    def get_stats(self) -> Dict:
        """Retorna estatísticas do cache."""
        total = len(self.cache['translations'])
        total_hits = sum(entry.get('hits', 0) for entry in self.cache['translations'].values())

        # Top 10 traduções mais usadas
        sorted_entries = sorted(
            self.cache['translations'].items(),
            key=lambda x: x[1].get('hits', 0),
            reverse=True
        )

        top_10 = [
            {
                'original': entry['original'][:50],
                'translated': entry['translated'][:50],
                'hits': entry.get('hits', 0)
            }
            for _, entry in sorted_entries[:10]
        ]

        return {
            'total_entries': total,
            'total_hits': total_hits,
            'cache_file': str(self.cache_file),
            'file_size_kb': self.cache_file.stat().st_size / 1024 if self.cache_file.exists() else 0,
            'top_10': top_10
        }

    def clear(self):
        """Limpa todo o cache."""
        self.cache['translations'] = {}
        self.save_cache()

    def remove_old_entries(self, days: int = 90):
        """
        Remove entradas não usadas por X dias.

        Args:
            days: Dias de inatividade para remoção
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days)
        removed = 0

        for text_hash, entry in list(self.cache['translations'].items()):
            last_used = datetime.fromisoformat(entry.get('last_used', entry['created']))

            if last_used < cutoff:
                del self.cache['translations'][text_hash]
                removed += 1

        if removed > 0:
            self.save_cache()
            print(f"🗑️  Removed {removed} old cache entries (unused for {days}+ days)")

        return removed


def translate_with_cache(
    texts: list,
    api_key: str,
    target_language: str = "Portuguese (Brazil)",
    cache_file: str = "translation_cache.json"
) -> Tuple[list, Dict]:
    """
    Traduz textos usando cache quando possível.

    Args:
        texts: Lista de textos
        api_key: API key Gemini
        target_language: Idioma alvo
        cache_file: Arquivo de cache

    Returns:
        (translations, stats)
        - translations: Lista de traduções
        - stats: {'cached': int, 'api_calls': int, 'saved_calls': int}
    """
    from interface.gemini_api import translate_batch

    cache = TranslationCache(cache_file)

    # Busca no cache
    cached_translations, uncached = cache.get_batch(texts, target_language)

    stats = {
        'total_texts': len(texts),
        'cached': len(cached_translations),
        'api_calls': len(uncached)
    }

    # Se todos estão no cache, retorna direto
    if not uncached:
        print(f"✅ All {len(texts)} texts found in cache (0 API calls)")
        translations = [cached_translations[i] for i in range(len(texts))]
        cache.save_cache()
        return translations, stats

    # Traduz apenas textos não cacheados
    print(f"📊 Cache stats: {len(cached_translations)} cached, {len(uncached)} need translation")

    uncached_texts = [text for _, text in uncached]
    new_translations, success, error = translate_batch(uncached_texts, api_key, target_language)

    if not success:
        raise Exception(f"Translation failed: {error}")

    # Armazena novas traduções no cache
    cache.set_batch(uncached_texts, new_translations, target_language)
    cache.save_cache()

    # Combina traduções cacheadas + novas
    all_translations = [''] * len(texts)

    for i, translation in cached_translations.items():
        all_translations[i] = translation

    for (original_index, _), translation in zip(uncached, new_translations):
        all_translations[original_index] = translation

    stats['saved_calls'] = stats['cached']
    stats['cache_hit_rate'] = (stats['cached'] / stats['total_texts'] * 100) if stats['total_texts'] > 0 else 0

    print(f"✅ Translation completed: {stats['cached']} from cache, {stats['api_calls']} API calls")
    print(f"   Cache hit rate: {stats['cache_hit_rate']:.1f}%")

    return all_translations, stats


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  View cache stats:")
        print("    python pc_translation_cache.py stats <cache_file>")
        print("\n  Clear cache:")
        print("    python pc_translation_cache.py clear <cache_file>")
        print("\n  Clean old entries:")
        print("    python pc_translation_cache.py clean <cache_file> <days>")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "stats":
        cache_file = sys.argv[2] if len(sys.argv) > 2 else "translation_cache.json"
        cache = TranslationCache(cache_file)

        stats = cache.get_stats()

        print(f"\n📊 CACHE STATISTICS")
        print(f"{'='*70}")
        print(f"Cache file: {stats['cache_file']}")
        print(f"Total entries: {stats['total_entries']}")
        print(f"Total hits: {stats['total_hits']}")
        print(f"File size: {stats['file_size_kb']:.2f} KB")

        if stats['top_10']:
            print(f"\n🔥 TOP 10 MOST USED TRANSLATIONS:")
            for i, entry in enumerate(stats['top_10'], 1):
                print(f"  {i:2d}. [{entry['hits']:3d} hits] {entry['original']}...")

        print(f"{'='*70}\n")

    elif command == "clear":
        cache_file = sys.argv[2] if len(sys.argv) > 2 else "translation_cache.json"
        cache = TranslationCache(cache_file)

        confirm = input(f"⚠️  Clear all {len(cache.cache['translations'])} entries? (yes/no): ")
        if confirm.lower() == "yes":
            cache.clear()
            print("✅ Cache cleared")
        else:
            print("❌ Cancelled")

    elif command == "clean":
        cache_file = sys.argv[2] if len(sys.argv) > 2 else "translation_cache.json"
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 90

        cache = TranslationCache(cache_file)
        removed = cache.remove_old_entries(days)

        print(f"✅ Removed {removed} entries unused for {days}+ days")

    else:
        print(f"❌ Unknown command: {command}")
        print("Valid commands: stats, clear, clean")
        sys.exit(1)
