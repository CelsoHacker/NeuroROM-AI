# -*- coding: utf-8 -*-
"""
================================================================================
GEMINI API TRANSLATOR - ROM Translation Framework v5.3
Módulo centralizado para tradução via Google Gemini API
COM GERENCIAMENTO AVANÇADO DE QUOTA
================================================================================
"""

import time
import logging
from typing import List, Optional, Tuple, Dict, Any

try:
    import google.generativeai as genai  # type: ignore
    from google.generativeai.types import HarmCategory, HarmBlockThreshold  # type: ignore
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# Importar sistema de quota
try:
    # Tenta importação relativa primeiro (quando rodado como módulo)
    from ..core.quota_manager import get_quota_manager, GeminiQuotaManager
    QUOTA_MANAGER_AVAILABLE = True
except (ImportError, ValueError):
    try:
        # Fallback: importação absoluta (quando rodado diretamente)
        import sys
        from pathlib import Path
        core_path = Path(__file__).parent.parent / 'core'
        if str(core_path) not in sys.path:
            sys.path.insert(0, str(core_path.parent))
        from core.quota_manager import get_quota_manager, GeminiQuotaManager
        QUOTA_MANAGER_AVAILABLE = True
    except ImportError:
        QUOTA_MANAGER_AVAILABLE = False
        GeminiQuotaManager = None  # Define como None se não disponível
        print("⚠️ QuotaManager não disponível - rodando sem controle de quota")

logger = logging.getLogger(__name__)

# --- CONFIGURAÇÕES GLOBAIS ---
MODEL_NAME = "gemini-2.5-flash"
RATE_LIMIT_DELAY = 0.8  # Segundos entre chamadas (fallback se quota manager não disponível)
MAX_BATCH_SIZE = 200  # Traduz até 200 textos por requisição

# Instância global do quota manager (singleton)
_quota_manager = None


def get_or_create_quota_manager():
    """Retorna instância do QuotaManager (singleton) ou None se não disponível"""
    global _quota_manager

    if not QUOTA_MANAGER_AVAILABLE:
        return None

    if _quota_manager is None:
        _quota_manager = get_quota_manager()

    return _quota_manager


def _build_system_prompt(target_language: str = "Portuguese (Brazil)") -> str:
    """Constrói o prompt de sistema especializado para ROM localization."""
    return (
        f"You are a professional game localizer specialized in ROM hacking "
        f"and low-level text injection.\n"
        f"Your primary goal is to translate the provided text into highly "
        f"fluent and natural {target_language}.\n"
        f"CRITICAL RULES:\n"
        f"1. Preserve ALL control codes, tags, hex sequences, and placeholders "
        f"EXACTLY as they appear.\n"
        f"   Examples: <0A>, $C2, [OFFSET], [NAME], \\n, {{VAR}}, etc.\n"
        f"2. Do NOT translate or modify control codes.\n"
        f"3. If you receive text lines separated by '\\n', return the SAME "
        f"NUMBER of lines.\n"
        f"4. ONLY return the translated text. Do not add explanations or "
        f"commentary.\n"
        f"5. If a line is untranslatable or too technical, return it unchanged."
    )


def _get_safety_settings() -> List[Dict[str, Any]]:
    """Retorna configurações de segurança para evitar bloqueios."""
    if not GENAI_AVAILABLE:
        return []

    return [
        {
            "category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            "threshold": HarmBlockThreshold.BLOCK_NONE,
        },
        {
            "category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            "threshold": HarmBlockThreshold.BLOCK_NONE,
        },
        {
            "category": HarmCategory.HARM_CATEGORY_HARASSMENT,
            "threshold": HarmBlockThreshold.BLOCK_NONE,
        },
        {
            "category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            "threshold": HarmBlockThreshold.BLOCK_NONE,
        },
    ]


def configure_api(api_key: str, timeout: float = 120.0) -> bool:
    """
    Configura a API do Gemini com a chave fornecida.

    Args:
        api_key: Chave de API do Google
        timeout: Timeout de rede em segundos

    Returns:
        True se configuração foi bem-sucedida, False caso contrário
    """
    if not GENAI_AVAILABLE:
        return False

    if not api_key or not api_key.strip():
        return False

    try:
        genai.configure(api_key=api_key.strip())
        return True
    except Exception as e:
        print(f"Erro ao configurar API: {e}")
        return False


def _translate_single_batch(
    lines: List[str],
    api_key: str,
    target_language: str = "Portuguese (Brazil)",
    timeout: float = 120.0
) -> Tuple[List[str], bool, Optional[str]]:
    """
    Traduz uma lista de linhas em um único bloco usando Gemini API.
    FUNÇÃO INTERNA - use translate_batch() para auto-batching.

    Args:
        lines: Lista de strings para traduzir (máx. MAX_BATCH_SIZE)
        api_key: Chave de API do Google
        target_language: Idioma de destino
        timeout: Timeout em segundos

    Returns:
        Tupla: (linhas_traduzidas, sucesso, mensagem_erro)
        - Se sucesso: retorna linhas traduzidas com \\n
        - Se falha: retorna linhas originais com \\n
    """
    if not GENAI_AVAILABLE:
        error_msg = "Biblioteca 'google-generativeai' não está instalada. Execute: pip install google-generativeai"
        return [l + "\n" for l in lines], False, error_msg

    if not lines:
        return [], True, None

    # Configurar API
    if not configure_api(api_key, timeout):
        error_msg = "Falha ao configurar API. Verifique sua API Key."
        return [l + "\n" for l in lines], False, error_msg

    # Preparar configuração de geração
    generation_config = {
        "temperature": 0.3,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
    }

    # Preparar texto em bloco
    text_block = "\n".join(lines)

    try:
        # ===== CONTROLE DE QUOTA INTELIGENTE =====
        quota_mgr = get_or_create_quota_manager()

        if quota_mgr:
            # Verifica se pode fazer requisição
            if not quota_mgr.wait_if_needed():
                error_msg = "⛔ Limite diário de requisições atingido. Aguarde o reset (00:00)"
                logger.error(error_msg)
                return [l + "\n" for l in lines], False, error_msg

            logger.info(f"📊 {quota_mgr.get_status_message()}")
        else:
            # Fallback: rate limiting simples
            time.sleep(RATE_LIMIT_DELAY)

        # Criar modelo com configurações
        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            generation_config=generation_config,
            safety_settings=_get_safety_settings(),
            system_instruction=_build_system_prompt(target_language)
        )

        # Gerar tradução
        response = model.generate_content(text_block)

        # ===== REGISTRA REQUISIÇÃO BEM-SUCEDIDA =====
        if quota_mgr:
            quota_mgr.record_request(success=True)

        # Processar resposta
        if not response or not response.text:
            error_msg = "API retornou resposta vazia"
            return [l + "\n" for l in lines], False, error_msg

        translated_text = response.text.strip()
        translations = translated_text.split('\n')

        # Validar número de linhas
        if len(translations) == len(lines):
            return [t + "\n" for t in translations], True, None

        warning_msg = (
            f"Aviso: API retornou {len(translations)} linhas mas "
            f"esperava {len(lines)}. Usando original."
        )
        print(warning_msg)
        return [l + "\n" for l in lines], False, warning_msg

    except Exception as e:
        # ===== REGISTRA REQUISIÇÃO FALHADA =====
        quota_mgr = get_or_create_quota_manager()
        if quota_mgr:
            quota_mgr.record_request(success=False)

        error_msg = f"Erro na tradução: {str(e)}"
        logger.error(error_msg)
        print(error_msg)
        return [l + "\n" for l in lines], False, error_msg


def translate_batch(
    lines: List[str],
    api_key: str,
    target_language: str = "Portuguese (Brazil)",
    timeout: float = 120.0
) -> Tuple[List[str], bool, Optional[str]]:
    """
    Traduz uma lista de linhas usando auto-batching otimizado.

    Divide automaticamente listas grandes em batches de MAX_BATCH_SIZE
    para reduzir o número de requisições à API e respeitar rate limits.

    Exemplo: 1000 textos com MAX_BATCH_SIZE=200 = 5 requisições

    Args:
        lines: Lista de strings para traduzir (qualquer tamanho)
        api_key: Chave de API do Google
        target_language: Idioma de destino
        timeout: Timeout em segundos

    Returns:
        Tupla: (linhas_traduzidas, sucesso, mensagem_erro)
        - Se sucesso: retorna linhas traduzidas com \\n
        - Se falha parcial: retorna o que conseguiu traduzir + originais
    """
    if not GENAI_AVAILABLE:
        error_msg = "Biblioteca 'google-generativeai' não está instalada. Execute: pip install google-generativeai"
        return [l + "\n" for l in lines], False, error_msg

    if not lines:
        return [], True, None

    # Se a lista couber em um único batch, usa função direta
    if len(lines) <= MAX_BATCH_SIZE:
        return _translate_single_batch(lines, api_key, target_language, timeout)

    # Dividir em batches e traduzir cada um
    print(f"📦 Dividindo {len(lines)} textos em batches de {MAX_BATCH_SIZE}...")

    all_translations = []
    batch_count = (len(lines) + MAX_BATCH_SIZE - 1) // MAX_BATCH_SIZE

    for i in range(0, len(lines), MAX_BATCH_SIZE):
        batch_num = (i // MAX_BATCH_SIZE) + 1
        batch = lines[i:i + MAX_BATCH_SIZE]

        print(f"   🔄 Traduzindo batch {batch_num}/{batch_count} ({len(batch)} textos)...")

        batch_translations, success, error = _translate_single_batch(
            batch, api_key, target_language, timeout
        )

        if not success:
            # Se um batch falhar, retornar o que conseguimos + originais restantes
            warning_msg = (
                f"Erro no batch {batch_num}/{batch_count}: {error}\n"
                f"Traduzidos: {len(all_translations)}/{len(lines)}"
            )
            print(f"   ⚠️  {warning_msg}")

            # Adicionar traduções já feitas + originais restantes
            all_translations.extend(batch_translations)
            all_translations.extend([l + "\n" for l in lines[i + len(batch):]])

            return all_translations, False, warning_msg

        all_translations.extend(batch_translations)
        print(f"   ✅ Batch {batch_num}/{batch_count} completo")

    print(f"✅ Tradução completa: {len(all_translations)} textos em {batch_count} requisições")
    return all_translations, True, None


def test_api_key(api_key: str) -> Tuple[bool, str]:
    """
    Testa se a API Key é válida fazendo uma chamada de teste.

    Args:
        api_key: Chave de API para testar

    Returns:
        Tupla: (sucesso, mensagem)
    """
    if not GENAI_AVAILABLE:
        return False, "Biblioteca google-generativeai não instalada"

    test_lines = ["Hello"]
    _, success, error = translate_batch(test_lines, api_key, "Portuguese (Brazil)", 30.0)

    if success:
        return True, "API Key válida e funcional"

    return False, error or "Erro desconhecido ao testar API"


# ============================================================================
# FUNÇÕES DE GERENCIAMENTO DE QUOTA
# ============================================================================

def get_quota_status() -> Dict[str, Any]:
    """
    Retorna status atual da quota da API

    Returns:
        Dicionário com estatísticas de uso
    """
    quota_mgr = get_or_create_quota_manager()

    if not quota_mgr:
        return {
            'available': False,
            'message': 'Sistema de quota não disponível'
        }

    stats = quota_mgr.get_stats()
    stats['available'] = True
    stats['status_message'] = quota_mgr.get_status_message()

    return stats


def estimate_translation_quota(total_texts: int, batch_size: int = 200) -> Dict[str, Any]:
    """
    Estima se a tradução pode ser completada com a quota disponível

    Args:
        total_texts: Total de textos para traduzir
        batch_size: Tamanho de cada batch

    Returns:
        Dicionário com estimativa detalhada
    """
    quota_mgr = get_or_create_quota_manager()

    if not quota_mgr:
        return {
            'available': False,
            'message': 'Sistema de quota não disponível',
            'can_translate': True  # Permite tradução sem controle
        }

    estimate = quota_mgr.estimate_batches(total_texts, batch_size)
    estimate['available'] = True

    return estimate


def print_quota_estimate(total_texts: int, batch_size: int = 200):
    """
    Imprime estimativa formatada da tradução

    Args:
        total_texts: Total de textos para traduzir
        batch_size: Tamanho de cada batch
    """
    quota_mgr = get_or_create_quota_manager()

    if not quota_mgr:
        print("\n⚠️ Sistema de quota não disponível - tradução sem limite\n")
        return

    quota_mgr.print_estimate(total_texts, batch_size)


def reset_quota_if_needed():
    """Força verificação de reset de quota (útil para testes)"""
    quota_mgr = get_or_create_quota_manager()

    if quota_mgr:
        # Simplesmente checa se precisa resetar
        quota_mgr.can_make_request()
        logger.info("✅ Verificação de quota completa")


def get_quota_stats_message() -> str:
    """
    Retorna mensagem de status da quota para exibir na UI

    Returns:
        String formatada com status
    """
    quota_mgr = get_or_create_quota_manager()

    if not quota_mgr:
        return "Sistema de quota não disponível"

    return quota_mgr.get_status_message()

