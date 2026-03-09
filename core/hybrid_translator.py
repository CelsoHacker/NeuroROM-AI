"""
Sistema Híbrido de Tradução com Fallback Automático
====================================================

Usa Gemini (rápido) quando quota disponível,
automaticamente muda para Ollama (lento mas ilimitado) quando quota esgotar.

Autor: ROM Translation Framework v5.3
"""

import logging
import os
import re
import shutil
import subprocess
import time
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

        # Flag: quota diária esgotada, não tenta mais Gemini nesta sessão
        self._gemini_daily_exhausted = False

        # Configuração do modo SMART (economiza quota)
        self.smart_config = {
            'short_text_threshold': 50,  # Textos <= 50 chars vão para Ollama
            'dialog_keywords': ['?', '!', '...', '"', "'"],  # Diálogos vão para Gemini
            'menu_keywords': ['START', 'CONTINUE', 'OPTIONS', 'EXIT', 'SAVE', 'LOAD'],
        }

        # Importa módulos conforme disponível
        self.gemini_available = False
        self.ollama_available = False
        self.ollama_models: List[str] = []
        self.ollama_model: str = "phi3:mini"

        self._check_availability()

    def _query_ollama_tags(self, timeout: int = 2) -> Tuple[bool, List[str]]:
        """Consulta tags do Ollama local e retorna (ativo, modelos)."""
        try:
            import requests
            response = requests.get("http://127.0.0.1:11434/api/tags", timeout=timeout)
            if response.status_code != 200:
                return False, []
            data = response.json() or {}
            models: List[str] = []
            for item in data.get("models", []):
                name = str(item.get("name", "")).strip()
                if name:
                    models.append(name)
            return True, models
        except Exception:
            return False, []

    def _pick_best_ollama_model(self, installed_models: List[str]) -> Optional[str]:
        """Escolhe automaticamente o melhor modelo instalado para tradução."""
        if not installed_models:
            return None
        installed_lower = [m.lower() for m in installed_models]
        preferred = [
            "qwen2.5:14b-instruct",
            "qwen2.5:7b-instruct",
            "llama3.1:8b",
            "llama3.2:3b",
            "mistral:7b-instruct",
            "phi3:medium",
            "phi3:mini",
        ]

        def _match(candidate: str) -> Optional[str]:
            cand = candidate.lower().strip()
            cand_base = cand.split(":")[0]
            if cand in installed_lower:
                return installed_models[installed_lower.index(cand)]
            for idx, model_name in enumerate(installed_lower):
                if model_name == cand_base or model_name.startswith(cand_base + ":"):
                    return installed_models[idx]
            return None

        for cand in preferred:
            hit = _match(cand)
            if hit:
                return hit
        return installed_models[0]

    def _try_start_ollama_service(self, wait_seconds: int = 10) -> bool:
        """Tenta iniciar `ollama serve` automaticamente quando estiver desligado."""
        ollama_bin = shutil.which("ollama")
        if not ollama_bin:
            logger.warning("⚠️ Ollama não encontrado no PATH")
            return False
        try:
            popen_kwargs: Dict[str, Any] = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
            if os.name == "nt":
                detached = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
                popen_kwargs["creationflags"] = detached | new_group
            subprocess.Popen([ollama_bin, "serve"], **popen_kwargs)
        except Exception as e:
            logger.warning(f"⚠️ Falha ao iniciar Ollama automaticamente: {e}")
            return False

        deadline = time.time() + max(2, int(wait_seconds))
        while time.time() < deadline:
            alive, _models = self._query_ollama_tags(timeout=2)
            if alive:
                logger.info("✅ Ollama iniciado automaticamente")
                return True
            time.sleep(1)
        logger.warning("⚠️ Ollama não respondeu após tentativa de auto-start")
        return False

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
        alive, models = self._query_ollama_tags(timeout=2)
        if not alive:
            logger.warning("⚠️ Ollama offline. Tentando iniciar automaticamente...")
            alive = self._try_start_ollama_service(wait_seconds=10)
            if alive:
                alive, models = self._query_ollama_tags(timeout=3)

        if not alive:
            self.ollama_available = False
            self.ollama_models = []
            logger.warning("⚠️ Ollama não disponível")
            return

        self.ollama_models = list(models)
        selected = self._pick_best_ollama_model(self.ollama_models)
        if not selected:
            self.ollama_available = False
            logger.warning("⚠️ Ollama ativo, mas sem modelos instalados (use: ollama pull qwen2.5:7b-instruct)")
            return

        self.ollama_model = selected
        self.ollama_available = True
        logger.info(f"✅ Ollama disponível ({len(self.ollama_models)} modelos) | modelo={self.ollama_model}")

    def translate_batch(
        self,
        texts: List[str],
        target_language: str = "Portuguese (Brazil)",
        mode: TranslationMode = TranslationMode.AUTO,
        _log_callback=None
    ) -> Tuple[List[str], bool, Optional[str]]:
        """
        Traduz batch de textos com fallback automático

        Args:
            texts: Lista de textos para traduzir
            target_language: Idioma de destino
            mode: AUTO = fallback automático, GEMINI/OLLAMA = força um específico
            _log_callback: Função opcional para emitir logs para a UI

        Returns:
            (traduções, sucesso, erro)
        """
        if not texts:
            return [], True, None

        def _log(msg):
            if _log_callback:
                _log_callback(msg)
            logger.info(msg)

        # Modo forçado
        if mode == TranslationMode.GEMINI:
            return self._translate_with_gemini(texts, target_language)
        elif mode == TranslationMode.OLLAMA:
            return self._translate_with_ollama(texts, target_language)
        elif mode == TranslationMode.SMART:
            return self._translate_smart(texts, target_language)

        # Se quota diária já esgotou, vai direto para Ollama
        if self._gemini_daily_exhausted and self.ollama_available:
            return self._translate_with_ollama(texts, target_language)

        # Modo AUTO: tenta Gemini primeiro se preferido
        if self.prefer_gemini and self.gemini_available:
            translations, success, error = self._translate_with_gemini(texts, target_language)

            # Se funcionou, retorna
            if success:
                return translations, success, error

            # Se falhou por quota esgotada, espera e retenta
            err_lower = error.lower() if error else ""
            is_quota_error = error and (
                "quota" in err_lower or "429" in error
                or "limite" in err_lower or "limit" in err_lower
                or "resource_exhausted" in err_lower
            )

            if is_quota_error:
                import time
                self.stats['fallback_switches'] += 1
                error_str = str(error)

                # Detecta se é quota DIÁRIA (PerDay) vs por minuto (PerMinute)
                # Gemini API retorna "PerDay" no erro original, mas gemini_api.py
                # pode reformatar para "Limite diario" ou "diário"
                err_str_lower = error_str.lower()
                is_daily = (
                    "PerDay" in error_str
                    or "per_day" in err_str_lower
                    or "diario" in err_str_lower
                    or "diário" in err_str_lower
                    or "daily" in err_str_lower
                    or "limite di" in err_str_lower
                )

                if is_daily:
                    # Quota diária: retries são inúteis, vai direto para Ollama
                    self._gemini_daily_exhausted = True
                    _log("[WARN] Quota DIÁRIA do Gemini esgotada (20 req/dia no free tier).")
                    if self.ollama_available:
                        _log("[FALLBACK] Usando Ollama para traduzir. Qualidade boa para textos de jogos.")
                        return self._translate_with_ollama(texts, target_language)
                    else:
                        return translations, False, "Quota diária do Gemini esgotada e Ollama não disponível. Tente amanhã."

                # Quota por minuto: espera e retenta
                for retry in range(1, 3):
                    wait_secs = 65
                    _log(f"[WAIT] Quota por minuto esgotada. Aguardando {wait_secs}s para retry {retry}/2...")
                    for elapsed in range(0, wait_secs, 10):
                        remaining = wait_secs - elapsed
                        if remaining > 0:
                            _log(f"   ⏱️ {remaining}s restantes...")
                            time.sleep(min(10, remaining))

                    _log(f"[RETRY] Tentativa {retry}/2 com Gemini...")
                    translations, success, error = self._translate_with_gemini(texts, target_language)
                    if success:
                        _log(f"[OK] Gemini respondeu no retry {retry}!")
                        return translations, success, error

                    # Checa se virou quota diária (mesmos padrões da detecção principal)
                    _retry_err = str(error).lower()
                    _is_daily_retry = (
                        "PerDay" in str(error) or "per_day" in _retry_err
                        or "diario" in _retry_err or "diário" in _retry_err
                        or "daily" in _retry_err or "limite di" in _retry_err
                    )
                    if _is_daily_retry:
                        self._gemini_daily_exhausted = True
                        _log("[WARN] Quota diária atingida durante retries.")
                        break

                    err_lower2 = error.lower() if error else ""
                    still_quota = error and (
                        "quota" in err_lower2 or "429" in str(error)
                        or "resource_exhausted" in err_lower2
                    )
                    if not still_quota:
                        break

                # Gemini esgotou após retries - marca flag e tenta Ollama
                self._gemini_daily_exhausted = True
                if self.ollama_available:
                    _log("[FALLBACK] Gemini indisponível. Usando Ollama para os próximos batches.")
                    return self._translate_with_ollama(texts, target_language)
                else:
                    return translations, False, "Quota do Gemini esgotada e Ollama não disponível."

            # Outro erro (não quota), retorna
            return translations, success, error

        # Gemini indisponível, tenta Ollama
        if self.ollama_available:
            return self._translate_with_ollama(texts, target_language)

        return texts, False, "❌ Nenhum serviço de tradução disponível. Configure a API Key do Gemini."

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
                # Gemini falhou - redireciona para Ollama se disponível
                is_quota = "quota" in str(gemini_error).lower() or "429" in str(gemini_error)
                if is_quota and self.ollama_available:
                    logger.info("🔄 Gemini quota esgotada no SMART - enviando para Ollama...")
                    ollama_r, ollama_s, ollama_e = self._translate_with_ollama(
                        gemini_texts, target_language
                    )
                    if ollama_s:
                        for idx, trans in zip(gemini_indices, ollama_r):
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
        model: Optional[str] = None
    ) -> Tuple[List[str], bool, Optional[str]]:
        """Traduz usando Ollama local"""
        if not self.ollama_available:
            return texts, False, "Ollama não disponível"

        try:
            import requests
            from concurrent.futures import ThreadPoolExecutor, as_completed

            model_name = str(model or self.ollama_model or "phi3:mini").strip()
            logger.info(f"⚡ Traduzindo {len(texts)} textos com Ollama ({model_name}) - MODO PARALELO...")

            translations = [None] * len(texts)  # Pré-aloca lista

            def translate_single(index, text):
                """Traduz um único texto"""
                def _normalize_for_match(value: str) -> str:
                    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())

                def _clean_output(value: str) -> str:
                    cleaned = str(value or "").strip()
                    if "\n\n" in cleaned:
                        cleaned = cleaned.split("\n\n")[0].strip()
                    for prefix in [
                        "Translation:",
                        "Tradução:",
                        "Traducao:",
                        "Portuguese:",
                        "PT-BR:",
                        "Saída:",
                        "Saida:",
                    ]:
                        if cleaned.startswith(prefix):
                            cleaned = cleaned[len(prefix):].strip()
                    if cleaned.startswith(("\"", "“")) and cleaned.endswith(("\"", "”")):
                        cleaned = cleaned[1:-1].strip()
                    return cleaned

                def _request(prompt_text: str) -> str:
                    payload = {
                        "model": model_name,
                        "prompt": prompt_text,
                        "system": (
                            "Voce e tradutor profissional de jogos retro. "
                            "Responda apenas em portugues brasileiro, sem explicacoes."
                        ),
                        "stream": False,
                        "options": {
                            "temperature": 0.0,
                            "num_predict": 200,
                            "num_ctx": 1024,
                            "top_p": 0.9,
                            "repeat_penalty": 1.1,
                        },
                    }
                    response = requests.post(
                        "http://127.0.0.1:11434/api/generate",
                        json=payload,
                        timeout=90,
                    )
                    if response.status_code != 200:
                        return ""
                    result = response.json() or {}
                    return _clean_output(result.get("response", ""))

                try:
                    src = str(text or "").strip()
                    prompt = (
                        "Traduza para portugues brasileiro natural e curto.\n"
                        "- Retorne SOMENTE a traducao.\n"
                        "- Nao explique.\n"
                        "- Nunca mantenha a frase inteira em ingles.\n"
                        f"Texto: {src}\n"
                        "Tradução:"
                    )
                    translation = _request(prompt)

                    # Segunda tentativa quando vier igual ao original.
                    if (
                        translation
                        and _normalize_for_match(translation) == _normalize_for_match(src)
                        and any(ch.isalpha() for ch in src)
                    ):
                        retry_prompt = (
                            "Corrija e traduza para portugues brasileiro.\n"
                            "Exemplo: Who opens? -> Quem abre?\n"
                            "- Responda apenas com a traducao final.\n"
                            f"Texto: {src}\n"
                            "PT-BR:"
                        )
                        retry_translation = _request(retry_prompt)
                        if retry_translation:
                            translation = retry_translation

                    if not translation:
                        return index, src + "\n"

                    lower_trans = translation.lower()
                    if any(w in lower_trans for w in ["translate", "rules:", "output only"]):
                        return index, src + "\n"
                    return index, translation + "\n"
                except Exception:
                    return index, str(text or "").strip() + "\n"

            # 1 WORKER - proteção térmica para GTX 1060
            with ThreadPoolExecutor(max_workers=1) as executor:
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
