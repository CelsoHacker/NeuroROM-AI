# -*- coding: utf-8 -*-
"""
================================================================================
PC PIPELINE - Pipeline Completo de Tradução para Jogos de PC
================================================================================
Orquestra todo o fluxo de tradução automaticamente:
1. Scan → Encontra arquivos traduzíveis (pc_game_scanner.py)
2. Detect → Identifica formatos e encodings (file_format_detector.py, encoding_detector.py)
3. Extract → Extrai textos preservando estrutura (pc_text_extractor.py)
4. Translate → Traduz via API (interface/gemini_api.py)
5. Reinsert → Reinsere com segurança (pc_safe_reinserter.py)

Totalmente automático, sem hardcoding de jogos específicos
================================================================================
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Importa módulos do pipeline
from .pc_game_scanner import PCGameScanner
from .pc_text_extractor import PCTextExtractor, ExtractedText
from .pc_safe_reinserter import PCSafeReinserter


class PCTranslationPipeline:
    """
    Pipeline completo de tradução para jogos de PC.
    Automatiza todo o processo de scan → extract → translate → reinsert.
    """

    def __init__(self, game_path: str, output_dir: Optional[str] = None):
        """
        Args:
            game_path: Caminho raiz do jogo
            output_dir: Diretório de saída (default: game_path/translation_output)
        """
        self.game_path = Path(game_path)

        if not self.game_path.exists():
            raise FileNotFoundError(f"Game path not found: {game_path}")

        # Output dir
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = self.game_path / "translation_output"

        self.output_dir.mkdir(exist_ok=True)

        # Componentes do pipeline
        self.scanner: Optional[PCGameScanner] = None
        self.extractor: Optional[PCTextExtractor] = None
        self.reinserter: Optional[PCSafeReinserter] = None

        # Resultados
        self.extraction_json: Optional[Path] = None
        self.translatable_texts: List[ExtractedText] = []

    def run_full_pipeline(
        self,
        api_key: str,
        target_language: str = "Portuguese (Brazil)",
        min_priority: int = 30,
        create_backup: bool = True,
        batch_size: int = 50,
        use_cache: bool = True
    ) -> Dict:
        """
        Executa pipeline completo de tradução.

        Args:
            api_key: Chave API Gemini
            target_language: Idioma alvo
            min_priority: Prioridade mínima de arquivo
            create_backup: Criar backups antes de modificar
            batch_size: Tamanho do lote para tradução
            use_cache: Usar cache de traduções (padrão: True)

        Returns:
            Dict com resultados do pipeline
        """
        print(f"\n{'='*70}")
        print(f"🚀 PC TRANSLATION PIPELINE - Full Automatic Translation")
        print(f"{'='*70}")
        print(f"Game: {self.game_path}")
        print(f"Target Language: {target_language}")
        print(f"Output: {self.output_dir}")
        print(f"{'='*70}\n")

        results = {
            'game_path': str(self.game_path),
            'target_language': target_language,
            'timestamp': datetime.now().isoformat(),
            'steps': {}
        }

        try:
            # ETAPA 1: EXTRACTION
            print(f"[STEP 1/3] 📄 EXTRACTION")
            print(f"{'='*70}\n")

            extraction_result = self.extract_texts(min_priority=min_priority)
            results['steps']['extraction'] = extraction_result

            if extraction_result['translatable_count'] == 0:
                print(f"\n⚠️  WARNING: No translatable texts found!")
                results['success'] = False
                results['error'] = "No translatable texts found"
                return results

            print(f"\n✅ Extraction completed: {extraction_result['translatable_count']} texts\n")

            # ETAPA 2: TRANSLATION
            print(f"[STEP 2/3] 🌐 TRANSLATION")
            print(f"{'='*70}\n")

            translation_result = self.translate_texts(
                api_key=api_key,
                target_language=target_language,
                batch_size=batch_size,
                use_cache=use_cache
            )

            results['steps']['translation'] = translation_result

            if not translation_result['success']:
                print(f"\n❌ Translation failed: {translation_result.get('error', 'Unknown error')}")
                results['success'] = False
                results['error'] = f"Translation failed: {translation_result.get('error')}"
                return results

            print(f"\n✅ Translation completed: {translation_result['translated_count']} texts\n")

            # ETAPA 3: REINSERTION
            print(f"[STEP 3/3] 💾 REINSERTION")
            print(f"{'='*70}\n")

            reinsertion_result = self.reinsert_translations(
                translations=translation_result['translations'],
                create_backup=create_backup
            )

            results['steps']['reinsertion'] = reinsertion_result

            if not reinsertion_result['success']:
                print(f"\n❌ Reinsertion failed: {reinsertion_result.get('error', 'Unknown error')}")
                results['success'] = False
                results['error'] = f"Reinsertion failed: {reinsertion_result.get('error')}"
                return results

            print(f"\n✅ Reinsertion completed: {reinsertion_result['reinserted_count']} texts\n")

            # SUCESSO TOTAL
            results['success'] = True

            print(f"\n{'='*70}")
            print(f"✅ PIPELINE COMPLETED SUCCESSFULLY")
            print(f"{'='*70}")
            print(f"Total texts translated: {translation_result['translated_count']}")
            print(f"Total texts reinserted: {reinsertion_result['reinserted_count']}")
            print(f"Output directory: {self.output_dir}")
            print(f"{'='*70}\n")

            return results

        except Exception as e:
            print(f"\n❌ PIPELINE ERROR: {e}\n")
            results['success'] = False
            results['error'] = str(e)
            return results

    def extract_texts(self, min_priority: int = 30) -> Dict:
        """
        Etapa 1: Extração de textos.

        Args:
            min_priority: Prioridade mínima

        Returns:
            Dict com resultados da extração
        """
        self.extractor = PCTextExtractor(str(self.game_path))
        self.extractor.extract_all(min_priority=min_priority)

        # Exporta JSON
        self.extraction_json = self.output_dir / "extracted_texts_pc.json"
        self.extractor.export_to_json(str(self.extraction_json))

        self.translatable_texts = self.extractor.get_translatable_texts()

        return {
            'total_extracted': len(self.extractor.extracted_texts),
            'translatable_count': len(self.translatable_texts),
            'extraction_json': str(self.extraction_json)
        }

    def translate_texts(
        self,
        api_key: str,
        target_language: str = "Portuguese (Brazil)",
        batch_size: int = 50,
        use_cache: bool = True
    ) -> Dict:
        """
        Etapa 2: Tradução via Gemini API.

        Args:
            api_key: Chave API
            target_language: Idioma alvo
            batch_size: Tamanho do lote
            use_cache: Usar cache de traduções

        Returns:
            Dict com resultados da tradução
        """
        if not self.translatable_texts:
            return {
                'success': False,
                'error': 'No texts to translate (run extract_texts first)'
            }

        # Importa módulos necessários
        try:
            # Tenta importar do módulo interface
            sys.path.insert(0, str(self.game_path.parent))
            from interface.gemini_api import translate_batch

            # Importa cache se habilitado
            if use_cache:
                try:
                    from .pc_translation_cache import TranslationCache
                    cache_available = True
                except ImportError:
                    cache_available = False
                    print("⚠️  Warning: Translation cache not available, using direct API")
            else:
                cache_available = False

        except ImportError:
            return {
                'success': False,
                'error': 'Gemini API module not found (interface/gemini_api.py)'
            }

        # Prepara textos para tradução
        texts_to_translate = [t.original_text for t in self.translatable_texts]

        print(f"Translating {len(texts_to_translate)} texts to {target_language}...")
        print(f"Using batch size: {batch_size}")

        if use_cache and cache_available:
            print(f"Cache: ENABLED")
        else:
            print(f"Cache: DISABLED")
        print()

        # Inicializa cache se disponível
        cache = None
        cache_stats = {'cached': 0, 'api_calls': 0}

        if use_cache and cache_available:
            cache_file = self.output_dir / "translation_cache.json"
            cache = TranslationCache(str(cache_file))

        # Traduz em lotes
        all_translations = []
        total_batches = (len(texts_to_translate) + batch_size - 1) // batch_size

        for i in range(0, len(texts_to_translate), batch_size):
            batch = texts_to_translate[i:i + batch_size]
            batch_num = (i // batch_size) + 1

            # Verifica cache primeiro
            batch_translations = []
            api_needed = []
            api_indices = []

            if cache:
                for idx, text in enumerate(batch):
                    cached_translation = cache.get(text, target_language)
                    if cached_translation:
                        batch_translations.append(cached_translation)
                        cache_stats['cached'] += 1
                    else:
                        batch_translations.append(None)
                        api_needed.append(text)
                        api_indices.append(idx)
            else:
                api_needed = batch
                api_indices = list(range(len(batch)))

            # Traduz textos não cacheados
            if api_needed:
                print(f"  Batch {batch_num}/{total_batches}: {len(api_needed)} texts via API" +
                      (f" ({len(batch) - len(api_needed)} from cache)" if cache and len(batch) > len(api_needed) else ""))

                translations, success, error = translate_batch(
                    texts=api_needed,
                    api_key=api_key,
                    target_language=target_language,
                    timeout=120.0
                )

                if not success:
                    return {
                        'success': False,
                        'error': f"Batch {batch_num} failed: {error}"
                    }

                # Armazena no cache
                if cache:
                    cache.set_batch(api_needed, translations, target_language)

                # Combina traduções cacheadas + novas
                for api_idx, translation in zip(api_indices, translations):
                    batch_translations[api_idx] = translation

                cache_stats['api_calls'] += len(api_needed)
                print(f"    ✓ Batch {batch_num} completed")
            else:
                print(f"  Batch {batch_num}/{total_batches}: All {len(batch)} texts from cache (0 API calls)")

            all_translations.extend(batch_translations)

        # Salva cache
        if cache:
            cache.save_cache()
            hit_rate = (cache_stats['cached'] / len(texts_to_translate) * 100) if texts_to_translate else 0
            print(f"\n📊 Cache stats: {cache_stats['cached']} cached, {cache_stats['api_calls']} API calls (hit rate: {hit_rate:.1f}%)")

        # Mapeia traduções por ID
        translations_dict = {
            self.translatable_texts[i].id: all_translations[i]
            for i in range(len(all_translations))
        }

        # Salva traduções
        translations_json = self.output_dir / "translations.json"
        with open(translations_json, 'w', encoding='utf-8') as f:
            json.dump(translations_dict, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Translations saved to: {translations_json}")

        return {
            'success': True,
            'translated_count': len(all_translations),
            'translations': translations_dict,
            'translations_json': str(translations_json)
        }

    def reinsert_translations(self, translations: Dict[int, str], create_backup: bool = True) -> Dict:
        """
        Etapa 3: Reinserção de traduções.

        Args:
            translations: Dict {text_id: translated_text}
            create_backup: Criar backups

        Returns:
            Dict com resultados da reinserção
        """
        if not self.extraction_json or not self.extraction_json.exists():
            return {
                'success': False,
                'error': 'Extraction JSON not found (run extract_texts first)'
            }

        self.reinserter = PCSafeReinserter(str(self.extraction_json))

        success, message = self.reinserter.reinsert_translations(
            translations=translations,
            create_backup=create_backup
        )

        # Conta textos reinseridos
        reinserted = sum(r.texts_reinserted for r in self.reinserter.results if r.success)

        return {
            'success': success,
            'message': message,
            'reinserted_count': reinserted,
            'files_processed': len(self.reinserter.results),
            'files_succeeded': sum(1 for r in self.reinserter.results if r.success),
            'files_failed': sum(1 for r in self.reinserter.results if not r.success)
        }

    def extract_only(self, min_priority: int = 30, export_json: bool = True) -> Dict:
        """
        Executa apenas extração (sem tradução).

        Args:
            min_priority: Prioridade mínima
            export_json: Exportar JSON

        Returns:
            Dict com resultados
        """
        print(f"\n🔍 EXTRACTION ONLY MODE")
        print(f"{'='*70}\n")

        result = self.extract_texts(min_priority=min_priority)

        print(f"\n✅ Extraction completed")
        print(f"  Total extracted: {result['total_extracted']}")
        print(f"  Translatable: {result['translatable_count']}")
        print(f"  Output: {result['extraction_json']}\n")

        return result

    def get_summary(self) -> Dict:
        """Retorna resumo do pipeline."""
        summary = {
            'game_path': str(self.game_path),
            'output_dir': str(self.output_dir),
        }

        if self.extractor:
            summary['extraction'] = {
                'total': len(self.extractor.extracted_texts),
                'translatable': len(self.translatable_texts)
            }

        if self.reinserter:
            summary['reinsertion'] = {
                'files_processed': len(self.reinserter.results),
                'success_count': sum(1 for r in self.reinserter.results if r.success)
            }

        return summary


def extract_game(game_path: str, min_priority: int = 30) -> Dict:
    """
    Função de conveniência: Apenas extração.

    Args:
        game_path: Caminho do jogo
        min_priority: Prioridade mínima

    Returns:
        Dict com resultados
    """
    pipeline = PCTranslationPipeline(game_path)
    return pipeline.extract_only(min_priority=min_priority)


def translate_game(
    game_path: str,
    api_key: str,
    target_language: str = "Portuguese (Brazil)",
    min_priority: int = 30,
    create_backup: bool = True
) -> Dict:
    """
    Função de conveniência: Pipeline completo.

    Args:
        game_path: Caminho do jogo
        api_key: Chave API Gemini
        target_language: Idioma alvo
        min_priority: Prioridade mínima
        create_backup: Criar backups

    Returns:
        Dict com resultados do pipeline
    """
    pipeline = PCTranslationPipeline(game_path)
    return pipeline.run_full_pipeline(
        api_key=api_key,
        target_language=target_language,
        min_priority=min_priority,
        create_backup=create_backup
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Extract only:")
        print('    python pc_pipeline.py extract "C:\\Games\\MyGame"')
        print("\n  Full translation:")
        print('    python pc_pipeline.py translate "C:\\Games\\MyGame" <gemini_api_key> [target_language]')
        print("\nExample:")
        print('  python pc_pipeline.py extract "C:\\Games\\MyGame"')
        print('  python pc_pipeline.py translate "C:\\Games\\MyGame" "AIza..." "Portuguese (Brazil)"')
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "extract":
        # Modo extração apenas
        if len(sys.argv) < 3:
            print("❌ Missing game path")
            sys.exit(1)

        game_dir = sys.argv[2]
        result = extract_game(game_dir, min_priority=30)

        if result['translatable_count'] > 0:
            sys.exit(0)
        else:
            sys.exit(1)

    elif mode == "translate":
        # Modo tradução completa
        if len(sys.argv) < 4:
            print("❌ Missing arguments: game_path and api_key required")
            sys.exit(1)

        game_dir = sys.argv[2]
        api_key = sys.argv[3]
        target_lang = sys.argv[4] if len(sys.argv) >= 5 else "Portuguese (Brazil)"

        result = translate_game(
            game_path=game_dir,
            api_key=api_key,
            target_language=target_lang,
            min_priority=30,
            create_backup=True
        )

        if result.get('success', False):
            print(f"\n✅ Translation completed successfully!")
            sys.exit(0)
        else:
            print(f"\n❌ Translation failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)

    else:
        print(f"❌ Unknown mode: {mode}")
        print("Valid modes: extract, translate")
        sys.exit(1)
