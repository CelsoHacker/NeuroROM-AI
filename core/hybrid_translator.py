"""
Sistema Híbrido de Tradução com Fallback Automático
====================================================

Usa Gemini (rápido) quando quota disponível,
automaticamente muda para Ollama (lento mas ilimitado) quando quota esgotar.

Autor: ROM Translation Framework v5.3
"""

import logging
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class TranslationMode(Enum):
    """Modos de tradução disponíveis"""
    GEMINI = "gemini"
    OLLAMA = "ollama"
    AUTO = "auto"  # Fallback automático
    SMART = "smart"  # NOVO: Gemini para longos, Ollama para curtos (economiza quota)


class HybridTranslator:
    """
    Tradutor híbrido que alterna automaticamente entre Gemini e Ollama

    Estratégia:
    1. Tenta Gemini (rápido, 1-2s por batch)
    2. Se quota esgotada → Ollama (lento, 30s por batch, mas ilimitado)
    3. Salva estatísticas de uso
    """

    def __init__(self, api_key: str = None, prefer_gemini: bool = True):
        """
        Inicializa tradutor híbrido

        Args:
            api_key: Google Gemini API key (opcional)
            prefer_gemini: Se True, usa Gemini primeiro (mais rápido)
        """
        self.api_key = api_key
        self.prefer_gemini = prefer_gemini
        self.current_mode = TranslationMode.GEMINI if prefer_gemini else TranslationMode.OLLAMA

        # Estatísticas
        self.stats = {
            'gemini_requests': 0,
            'ollama_requests': 0,
            'gemini_failures': 0,
            'ollama_failures': 0,
            'fallback_switches': 0,
            'total_texts_translated': 0,
            'gemini_quota_saved': 0  # Textos que usaram Ollama para economizar Gemini
        }

        # Configuração do modo SMART (economiza quota)
        self.smart_config = {
            'short_text_threshold': 50,  # Textos <= 50 chars vão para Ollama
            'dialog_keywords': ['?', '!', '...', '"', "'"],  # Diálogos vão para Gemini
            'menu_keywords': ['START', 'CONTINUE', 'OPTIONS', 'EXIT', 'SAVE', 'LOAD'],
        }

        # Importa módulos conforme disponível
        self.gemini_available = False
        self.ollama_available = False

        self._check_availability()

    def _check_availability(self):
        """Verifica quais serviços estão disponíveis"""
        # Testa Gemini
        try:
            from interface import gemini_api
            if gemini_api.GENAI_AVAILABLE:
                self.gemini_available = True
                logger.info("✅ Gemini API disponível")
            else:
                logger.warning("⚠️ Biblioteca google-generativeai não instalada")
        except ImportError:
            logger.warning("⚠️ Módulo gemini_api não encontrado")

        # Testa Ollama
        try:
            import requests
            response = requests.get('http://127.0.0.1:11434/api/tags', timeout=2)
            if response.status_code == 200:
                self.ollama_available = True
                models = response.json().get('models', [])
                logger.info(f"✅ Ollama disponível ({len(models)} modelos)")
            else:
                logger.warning("⚠️ Ollama respondeu mas com erro")
        except Exception as e:
            logger.warning(f"⚠️ Ollama não disponível: {e}")

    def translate_batch(
        self,
        texts: List[str],
        target_language: str = "Portuguese (Brazil)",
        mode: TranslationMode = TranslationMode.AUTO
    ) -> Tuple[List[str], bool, Optional[str]]:
        """
        Traduz batch de textos com fallback automático

        Args:
            texts: Lista de textos para traduzir
            target_language: Idioma de destino
            mode: AUTO = fallback automático, GEMINI/OLLAMA = força um específico

        Returns:
            (traduções, sucesso, erro)
        """
        if not texts:
            return [], True, None

        # Modo forçado
        if mode == TranslationMode.GEMINI:
            return self._translate_with_gemini(texts, target_language)
        elif mode == TranslationMode.OLLAMA:
            return self._translate_with_ollama(texts, target_language)
        elif mode == TranslationMode.SMART:
            return self._translate_smart(texts, target_language)

        # Modo AUTO: tenta Gemini primeiro se preferido
        if self.prefer_gemini and self.gemini_available:
            translations, success, error = self._translate_with_gemini(texts, target_language)

            # Se funcionou, retorna
            if success:
                return translations, success, error

            # Se falhou por quota esgotada, tenta Ollama
            if error and ("quota" in error.lower() or "429" in error):
                logger.warning(f"⚠️ Gemini quota esgotada - mudando para Ollama")
                self.stats['fallback_switches'] += 1
                self.current_mode = TranslationMode.OLLAMA

                if self.ollama_available:
                    return self._translate_with_ollama(texts, target_language)
                else:
                    return translations, False, "❌ Gemini sem quota e Ollama indisponível"

            # Outro erro, retorna erro
            return translations, success, error

        # Se não preferir Gemini ou Gemini indisponível, usa Ollama
        if self.ollama_available:
            return self._translate_with_ollama(texts, target_language)

        # Nenhum disponível
        return texts, False, "❌ Nenhum serviço de tradução disponível"

    def _classify_text(self, text: str) -> str:
        """
        Classifica texto para decidir qual tradutor usar.

        Returns:
            'gemini' = texto complexo (diálogo longo, precisa qualidade)
            'ollama' = texto simples (menu curto, Ollama resolve)
        """
        text_upper = text.upper()
        text_len = len(text)

        # Regra 1: Textos muito curtos (menus) → Ollama
        if text_len <= self.smart_config['short_text_threshold']:
            # Mas se tem pontuação de diálogo, pode ser importante
            has_dialog = any(kw in text for kw in self.smart_config['dialog_keywords'])
            if not has_dialog:
                return 'ollama'

        # Regra 2: Keywords de menu → Ollama (são simples)
        for kw in self.smart_config['menu_keywords']:
            if kw in text_upper:
                return 'ollama'

        # Regra 3: Texto longo com pontuação de diálogo → Gemini (precisa qualidade)
        if text_len > 80:
            return 'gemini'

        # Regra 4: Múltiplas frases → Gemini
        if text.count('.') >= 2 or text.count('!') >= 2 or text.count('?') >= 1:
            return 'gemini'

        # Default: textos médios vão para Ollama (economiza quota)
        return 'ollama'

    def _translate_smart(
        self,
        texts: List[str],
        target_language: str
    ) -> Tuple[List[str], bool, Optional[str]]:
        """
        Modo SMART: Economiza quota do Gemini.

        - Textos curtos/simples → Ollama (grátis, ilimitado)
        - Textos longos/diálogos → Gemini (qualidade, mas usa quota)
        """
        if not texts:
            return [], True, None

        # Classifica cada texto
        gemini_texts = []
        gemini_indices = []
        ollama_texts = []
        ollama_indices = []

        for i, text in enumerate(texts):
            classification = self._classify_text(text)
            if classification == 'gemini' and self.gemini_available and self.api_key:
                gemini_texts.append(text)
                gemini_indices.append(i)
            else:
                ollama_texts.append(text)
                ollama_indices.append(i)

        logger.info(f"📊 SMART: {len(gemini_texts)} para Gemini, {len(ollama_texts)} para Ollama")

        # Prepara resultado final
        translations = [''] * len(texts)
        all_success = True
        errors = []

        # Traduz com Ollama (textos simples)
        if ollama_texts and self.ollama_available:
            ollama_result, ollama_success, ollama_error = self._translate_with_ollama(
                ollama_texts, target_language
            )
            if ollama_success:
                for idx, trans in zip(ollama_indices, ollama_result):
                    translations[idx] = trans
                self.stats['gemini_quota_saved'] += len(ollama_texts)
            else:
                all_success = False
                if ollama_error:
                    errors.append(f"Ollama: {ollama_error}")
                # Fallback: mantém originais
                for idx, orig in zip(ollama_indices, ollama_texts):
                    translations[idx] = orig

        # Traduz com Gemini (textos complexos)
        if gemini_texts and self.gemini_available:
            gemini_result, gemini_success, gemini_error = self._translate_with_gemini(
                gemini_texts, target_language
            )
            if gemini_success:
                for idx, trans in zip(gemini_indices, gemini_result):
                    translations[idx] = trans
            else:
                # Gemini falhou - tenta Ollama como fallback
                if "quota" in str(gemini_error).lower() or "429" in str(gemini_error):
                    logger.warning("⚠️ Gemini quota esgotada - usando Ollama para textos complexos")
                    self.stats['fallback_switches'] += 1
                    if self.ollama_available:
                        fallback_result, fb_success, fb_error = self._translate_with_ollama(
                            gemini_texts, target_language
                        )
                        if fb_success:
                            for idx, trans in zip(gemini_indices, fallback_result):
                                translations[idx] = trans
                        else:
                            all_success = False
                            for idx, orig in zip(gemini_indices, gemini_texts):
                                translations[idx] = orig
                else:
                    all_success = False
                    if gemini_error:
                        errors.append(f"Gemini: {gemini_error}")
                    for idx, orig in zip(gemini_indices, gemini_texts):
                        translations[idx] = orig

        error_msg = "; ".join(errors) if errors else None
        return translations, all_success, error_msg

    def _translate_with_gemini(
        self,
        texts: List[str],
        target_language: str
    ) -> Tuple[List[str], bool, Optional[str]]:
        """Traduz usando Google Gemini"""
        if not self.gemini_available:
            return texts, False, "Gemini não disponível"

        if not self.api_key:
            return texts, False, "API Key do Gemini não configurada"

        try:
            from interface import gemini_api

            logger.info(f"🚀 Traduzindo {len(texts)} textos com Gemini...")

            translations, success, error = gemini_api.translate_batch(
                texts,
                self.api_key,
                target_language
            )

            if success:
                self.stats['gemini_requests'] += 1
                self.stats['total_texts_translated'] += len(texts)
                logger.info(f"✅ Gemini: {len(texts)} textos traduzidos")
            else:
                self.stats['gemini_failures'] += 1
                logger.error(f"❌ Gemini falhou: {error}")

            return translations, success, error

        except Exception as e:
            self.stats['gemini_failures'] += 1
            error_msg = f"Erro ao usar Gemini: {str(e)}"
            logger.exception(error_msg)
            return texts, False, error_msg

    def _translate_with_ollama(
        self,
        texts: List[str],
        target_language: str,
        model: str = "llama3.2:3b"
    ) -> Tuple[List[str], bool, Optional[str]]:
        """Traduz usando Ollama local"""
        if not self.ollama_available:
            return texts, False, "Ollama não disponível"

        try:
            import requests
            from concurrent.futures import ThreadPoolExecutor, as_completed

            logger.info(f"⚡ Traduzindo {len(texts)} textos com Ollama ({model}) - MODO PARALELO...")

            translations = [None] * len(texts)  # Pré-aloca lista

            def translate_single(index, text):
                """Traduz um único texto (função interna para paralelismo)"""
                # Prompt em INGLÊS (Llama responde melhor) pedindo tradução para PT-BR
                # CRÍTICO: Instrução direta e clara para forçar tradução completa
                prompt = f"""You are a professional game translator. Translate the following text to Brazilian Portuguese.

RULES:
- Translate EVERYTHING to Portuguese. Do NOT leave any English words.
- Keep the character's personality and tone (sarcastic, grumpy, angry, etc.)
- Preserve ONLY technical codes like {{VAR}}, [NAME], <0A>
- Output ONLY the translation. No explanations, no comments.

English: {text}
Portuguese:"""

                payload = {
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,  # Mais determinístico
                        "num_predict": 256,  # AUMENTADO: permite respostas longas
                        "num_ctx": 1024,  # Contexto maior para textos longos
                        "top_p": 0.9,
                        "repeat_penalty": 1.1  # Evita repetições
                    }
                }

                try:
                    response = requests.post(
                        'http://127.0.0.1:11434/api/generate',
                        json=payload,
                        timeout=90
                    )

                    if response.status_code == 200:
                        result = response.json()
                        translation = result['response'].strip()
                        if '\n\n' in translation:
                            translation = translation.split('\n\n')[0]
                        return index, translation + '\n'
                    else:
                        return index, text + '\n'

                except Exception:
                    return index, text + '\n'

            # PROCESSAMENTO PARALELO com 8 workers
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = {executor.submit(translate_single, i, text): i for i, text in enumerate(texts)}

                for future in as_completed(futures):
                    index, translation = future.result()
                    translations[index] = translation

            # Verifica se traduziu tudo
            success = all(t is not None for t in translations)

            if success:
                self.stats['ollama_requests'] += 1
                self.stats['total_texts_translated'] += len(texts)
                logger.info(f"✅ Ollama: {len(texts)} textos traduzidos")
            else:
                self.stats['ollama_failures'] += 1
                logger.error(f"❌ Ollama: tradução incompleta")

            return translations, success, None

        except Exception as e:
            self.stats['ollama_failures'] += 1
            error_msg = f"Erro ao usar Ollama: {str(e)}"
            logger.exception(error_msg)
            return [t + '\n' for t in texts], False, error_msg

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de uso"""
        total_requests = self.stats['gemini_requests'] + self.stats['ollama_requests']

        gemini_percent = (self.stats['gemini_requests'] / total_requests * 100) if total_requests > 0 else 0
        ollama_percent = (self.stats['ollama_requests'] / total_requests * 100) if total_requests > 0 else 0

        return {
            **self.stats,
            'total_requests': total_requests,
            'gemini_percent': gemini_percent,
            'ollama_percent': ollama_percent,
            'current_mode': self.current_mode.value,
            'gemini_available': self.gemini_available,
            'ollama_available': self.ollama_available
        }

    def get_status_message(self) -> str:
        """Retorna mensagem de status formatada"""
        stats = self.get_stats()

        if stats['current_mode'] == 'gemini':
            mode_icon = "⚡"
            mode_text = "Gemini (Rápido)"
        else:
            mode_icon = "🐌"
            mode_text = "Ollama (Lento)"

        return (
            f"{mode_icon} Modo: {mode_text} | "
            f"Textos traduzidos: {stats['total_texts_translated']} | "
            f"Gemini: {stats['gemini_requests']} | "
            f"Ollama: {stats['ollama_requests']} | "
            f"Fallbacks: {stats['fallback_switches']}"
        )

    def force_mode(self, mode: TranslationMode):
        """Força um modo específico"""
        self.current_mode = mode
        logger.info(f"🔧 Modo forçado: {mode.value}")

    def reset_stats(self):
        """Reseta estatísticas"""
        for key in self.stats:
            self.stats[key] = 0
        logger.info("📊 Estatísticas resetadas")


# ============================================================================
# FUNÇÕES HELPER
# ============================================================================

def translate_with_auto_fallback(
    texts: List[str],
    api_key: str,
    target_language: str = "Portuguese (Brazil)"
) -> Tuple[List[str], bool, Optional[str]]:
    """
    Traduz com fallback automático Gemini → Ollama

    Args:
        texts: Textos para traduzir
        api_key: Gemini API key
        target_language: Idioma de destino

    Returns:
        (traduções, sucesso, erro)
    """
    translator = HybridTranslator(api_key=api_key, prefer_gemini=True)
    return translator.translate_batch(texts, target_language, TranslationMode.AUTO)


# ============================================================================
# TESTE
# ============================================================================

if __name__ == "__main__":
    import os

    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    print("\n" + "="*70)
    print("🧪 TESTE DO TRADUTOR HÍBRIDO")
    print("="*70 + "\n")

    # API Key (você pode passar como argumento)
    api_key = os.getenv('GEMINI_API_KEY', '')

    if not api_key:
        print("⚠️ GEMINI_API_KEY não configurada - testando só Ollama")

    # Textos de teste
    test_texts = [
        "Welcome to the game!",
        "Press START to begin",
        "Game Over"
    ]

    # Cria tradutor
    translator = HybridTranslator(api_key=api_key, prefer_gemini=True)

    print(f"Disponibilidade:")
    print(f"  Gemini: {'✅' if translator.gemini_available else '❌'}")
    print(f"  Ollama: {'✅' if translator.ollama_available else '❌'}")
    print()

    # Traduz
    translations, success, error = translator.translate_batch(test_texts)

    print("\n" + "="*70)
    print("RESULTADOS:")
    print("="*70)

    for orig, trad in zip(test_texts, translations):
        print(f"  {orig:40} → {trad.strip()}")

    print("\n" + "="*70)
    print("ESTATÍSTICAS:")
    print("="*70)
    print(translator.get_status_message())
    print()

    stats = translator.get_stats()
    print(f"Requisições Gemini: {stats['gemini_requests']}")
    print(f"Requisições Ollama: {stats['ollama_requests']}")
    print(f"Fallbacks automáticos: {stats['fallback_switches']}")
    print(f"Taxa Gemini: {stats['gemini_percent']:.1f}%")
    print(f"Taxa Ollama: {stats['ollama_percent']:.1f}%")
    print("="*70 + "\n")
