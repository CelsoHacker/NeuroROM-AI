# -*- coding: utf-8 -*-
"""
================================================================================
GEMINI API TRANSLATOR - ROM Translation Framework v5.3
Módulo centralizado para tradução via Google Gemini API
COM GERENCIAMENTO AVANÇADO DE QUOTA
================================================================================
"""

import os
import re
import time
import logging
from typing import List, Optional, Tuple, Dict, Any, Union

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


def _sanitize_error(msg: str) -> str:
    """Remove possíveis API keys / tokens de mensagens de erro."""
    s = str(msg)
    s = re.sub(r'AIza[0-9A-Za-z\-_]{10,}', '[REDACTED]', s)
    s = re.sub(r'([?&]key=)[^&\s]+', r'\1[REDACTED]', s)
    s = re.sub(r'(Bearer\s+)[A-Za-z0-9\-_\.]{10,}', r'\1[REDACTED]', s)
    s = re.sub(r'sk-[A-Za-z0-9]{10,}', 'sk-[REDACTED]', s)
    return s


# --- CONFIGURAÇÕES GLOBAIS ---
MODEL_CANDIDATES = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]
MODEL_NAME = MODEL_CANDIDATES[0]
RATE_LIMIT_DELAY = 4.0  # Segundos entre chamadas (free tier: 10-15 RPM → 1 req a cada 4-6s)
MAX_BATCH_SIZE = 200  # Traduz até 200 textos por requisição
NEUROROM_BATCH_SIZE = 50  # Batch fixo solicitado para automação de strings

# Instância global do quota manager (singleton)
_quota_manager = None
_detected_model_name: Optional[str] = None


def get_or_create_quota_manager():
    """Retorna instância do QuotaManager (singleton) ou None se não disponível"""
    global _quota_manager

    if not QUOTA_MANAGER_AVAILABLE:
        return None

    if _quota_manager is None:
        _quota_manager = get_quota_manager()

    return _quota_manager


def _build_system_prompt(target_language: str = "Portuguese (Brazil)",
                         game_context: str = "") -> str:
    """Constrói o prompt de sistema especializado para ROM localization."""
    base = (
        f"You are a professional game localizer specialized in retro game "
        f"ROM translation with 20 years of experience.\n"
        f"Your goal is to produce publication-quality {target_language} "
        f"translations that read as if the game was originally made in that language.\n\n"
        f"TRANSLATION QUALITY RULES:\n"
        f"1. Use natural, fluent {target_language}. Avoid literal translations.\n"
        f"2. Adapt idioms and expressions to the target culture.\n"
        f"3. Keep proper names (characters, places, items) UNCHANGED unless "
        f"they have an established localized name.\n"
        f"4. Maintain the tone: RPG dialogue should feel epic/immersive, "
        f"action games should feel urgent/exciting.\n"
        f"5. Keep translated text SHORT - retro games have strict character limits. "
        f"Prefer concise translations over verbose ones.\n\n"
        f"TECHNICAL RULES:\n"
        f"6. Preserve ALL control codes, tags, hex sequences EXACTLY: "
        f"<0A>, $C2, [OFFSET], [NAME], \\n, {{VAR}}, etc.\n"
        f"7. Each input line is numbered [N]. Return EACH line with the SAME [N] prefix.\n"
        f"8. Do NOT skip, merge, reorder, or add lines.\n"
        f"9. ONLY return translated lines. No explanations or commentary.\n"
        f"10. If a line is a menu item or single word, translate it as a single "
        f"word/short phrase (not a sentence).\n"
        f"11. If input looks like garbage/binary data, return it UNCHANGED.\n"
    )
    if game_context:
        base += f"\nGAME CONTEXT:\n{game_context}\n"
    return base


# Contexto de jogo detectado automaticamente
_game_context_cache: str = ""


def set_game_context(context: str):
    """Define contexto do jogo para melhorar qualidade da tradução."""
    global _game_context_cache
    _game_context_cache = context


def detect_game_context_from_texts(texts: list) -> str:
    """Detecta gênero/contexto do jogo a partir dos textos extraídos."""
    if not texts:
        return ""
    sample = " ".join(texts[:100]).lower()

    # Detecta RPG
    rpg_keywords = ["quest", "sword", "magic", "spell", "armor", "potion",
                    "dragon", "king", "castle", "village", "gold", "level",
                    "attack", "defense", "hp", "mp", "inn", "shop", "weapon",
                    "thou", "thy", "avatar", "virtue", "dungeon"]
    rpg_score = sum(1 for k in rpg_keywords if k in sample)

    # Detecta Action/Platform
    action_keywords = ["score", "time", "lives", "bonus", "stage", "boss",
                       "jump", "power", "speed", "zone", "act", "ring",
                       "continue", "game over", "1up", "start"]
    action_score = sum(1 for k in action_keywords if k in sample)

    # Detecta Adventure
    adv_keywords = ["look", "take", "open", "talk", "use", "inventory",
                    "door", "key", "examine", "go", "north", "south"]
    adv_score = sum(1 for k in adv_keywords if k in sample)

    if rpg_score >= 4:
        return (
            "This is an RPG (Role-Playing Game). Use epic, immersive language. "
            "Maintain medieval/fantasy tone for dialogue. "
            "Translate menu items concisely: 'Attack'→'Atacar', 'Magic'→'Magia', "
            "'Inn'→'Estalagem', 'Shop'→'Loja', 'Weapon'→'Arma', 'Armor'→'Armadura'. "
            "Keep character/place names unchanged."
        )
    elif action_score >= 4:
        return (
            "This is an Action/Platform game. Use energetic, concise language. "
            "Translate: 'Game Over'→'Fim de Jogo', 'Continue'→'Continuar', "
            "'Stage'→'Fase', 'Score'→'Pontos', 'Lives'→'Vidas'. "
            "Keep short and impactful."
        )
    elif adv_score >= 3:
        return (
            "This is an Adventure game. Use descriptive, atmospheric language. "
            "Translate commands naturally: 'Look'→'Examinar', 'Take'→'Pegar', "
            "'Use'→'Usar', 'Talk'→'Falar'. Maintain mystery/exploration tone."
        )
    return ""


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


def _is_model_not_found_error(error_str: str) -> bool:
    """Detecta se o erro é de modelo não encontrado/indisponível (HTTP 404)."""
    err_lower = error_str.lower()
    return (
        ('404' in err_lower or 'not found' in err_lower) and
        ('model' in err_lower or 'generatecontent' in err_lower)
    )


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
        print(f"Erro ao configurar API: {_sanitize_error(e)}")
        return False


def _get_next_model_candidate(current_model: str) -> Optional[str]:
    """Retorna o próximo candidato após o modelo atual."""
    try:
        idx = MODEL_CANDIDATES.index(current_model)
    except ValueError:
        return MODEL_CANDIDATES[0] if MODEL_CANDIDATES else None

    next_idx = idx + 1
    if next_idx < len(MODEL_CANDIDATES):
        return MODEL_CANDIDATES[next_idx]
    return None


def _detect_gemini_model(target_language: str = "Portuguese (Brazil)") -> str:
    """
    Detecta automaticamente o primeiro modelo Gemini funcional.
    Ordem: gemini-2.0-flash -> gemini-1.5-flash -> gemini-1.5-pro
    """
    global _detected_model_name

    if _detected_model_name:
        return _detected_model_name

    generation_config = {
        "temperature": 0.0,
        "top_p": 1.0,
        "top_k": 1,
        "max_output_tokens": 16,
    }

    for candidate in MODEL_CANDIDATES:
        try:
            model = genai.GenerativeModel(
                model_name=candidate,
                generation_config=generation_config,
                safety_settings=_get_safety_settings(),
                system_instruction=_build_system_prompt(target_language, _game_context_cache),
            )
            response = model.generate_content("Responda apenas com: OK")
            if response and getattr(response, "text", None):
                _detected_model_name = candidate
                logger.info(f"[INFO] Gemini model detectado: {candidate}")
                print(f"[INFO] Gemini model detectado: {candidate}")
                return candidate
        except Exception as e:
            logger.warning(
                f"[MODEL_DETECT] Falha ao testar '{candidate}': {_sanitize_error(e)}"
            )

    # Se nada funcionar, mantém fallback para o primeiro candidato.
    _detected_model_name = MODEL_CANDIDATES[0]
    return _detected_model_name


def _translate_single_batch(
    lines: List[str],
    api_key: str,
    target_language: str = "Portuguese (Brazil)",
    timeout: float = 120.0,
    max_retries: int = 3,
    model_name: Optional[str] = None,
    _fallback_attempted: bool = False,
    _mismatch_retried: bool = False
) -> Tuple[List[str], bool, Optional[str]]:
    """
    Traduz uma lista de linhas em um único bloco usando Gemini API.
    FUNÇÃO INTERNA - use translate_batch() para auto-batching.
    INCLUI RETRY COM BACKOFF EXPONENCIAL para erros 429/503/504.

    Args:
        lines: Lista de strings para traduzir (máx. MAX_BATCH_SIZE)
        api_key: Chave de API do Google
        target_language: Idioma de destino
        timeout: Timeout em segundos
        max_retries: Número máximo de tentativas (default: 3)

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

    # Preparar texto em bloco com IDs numéricos
    numbered_lines = [f"[{i+1}] {line}" for i, line in enumerate(lines)]
    text_block = "\n".join(numbered_lines)

    # Regex para extrair respostas numeradas: [N] texto
    _ID_RE = re.compile(r"^\[(\d+)\]\s?(.*)", re.MULTILINE)

    def _parse_numbered_response(response_text: str, expected: int) -> list | None:
        """Mapeia resposta da API por [N] IDs. Retorna lista ordenada ou None."""
        matches = _ID_RE.findall(response_text)
        if not matches:
            return None
        result_map = {}
        for num_str, text in matches:
            idx = int(num_str) - 1  # [1]-based -> 0-based
            if 0 <= idx < expected:
                result_map[idx] = text
        if len(result_map) < expected * 0.15:
            return None  # Menos de 15% mapeada: falha
        # Monta lista completa; itens não mapeados ficam com original
        output = []
        for i in range(expected):
            if i in result_map:
                output.append(result_map[i])
            else:
                output.append(lines[i])  # Mantém original para itens faltantes
        return output

    # RETRY COM BACKOFF EXPONENCIAL
    last_error = None
    # _mismatch_retried: parametro ja define valor inicial
    for attempt in range(max_retries):
        try:
            # ===== CONTROLE DE QUOTA INTELIGENTE =====
            quota_mgr = get_or_create_quota_manager()

            if quota_mgr:
                # Verifica se pode fazer requisição
                if not quota_mgr.wait_if_needed():
                    error_msg = "Limite diario de requisicoes atingido (quota). Aguarde o reset (00:00)"
                    logger.error(error_msg)
                    return [l + "\n" for l in lines], False, error_msg

                logger.info(f"{quota_mgr.get_status_message()}")
            else:
                # Fallback: rate limiting simples
                time.sleep(RATE_LIMIT_DELAY)

            # Criar modelo com configurações
            current_model = model_name or _detect_gemini_model(target_language)
            model = genai.GenerativeModel(
                model_name=current_model,
                generation_config=generation_config,
                safety_settings=_get_safety_settings(),
                system_instruction=_build_system_prompt(target_language, _game_context_cache)
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

            # Tentativa 1: Parse por IDs numerados [N]
            parsed = _parse_numbered_response(translated_text, len(lines))
            if parsed is not None:
                # Conta itens efetivamente traduzidos vs mantidos como original
                mapped_count = sum(
                    1 for i, p in enumerate(parsed) if p != lines[i]
                )
                if mapped_count < len(lines):
                    logger.info(
                        f"[BATCH] {mapped_count}/{len(lines)} itens mapeados por ID"
                    )
                return [t + "\n" for t in parsed], True, None

            # Tentativa 2: Fallback para split por \n (sem linhas vazias)
            raw_lines = [
                ln for ln in translated_text.split('\n') if ln.strip()
            ]
            if len(raw_lines) == len(lines):
                return [t + "\n" for t in raw_lines], True, None

            # Mismatch: re-tenta 1x com instrução explícita
            if not _mismatch_retried:
                _mismatch_retried = True
                logger.warning(
                    f"[MISMATCH] API retornou {len(raw_lines)} linhas, "
                    f"esperava {len(lines)}. Re-tentando com instrucao explicita."
                )
                text_block = (
                    f"IMPORTANT: Return EXACTLY {len(lines)} numbered lines.\n"
                    + "\n".join(numbered_lines)
                )
                continue

            # Recuperação: sub-batch das linhas faltantes
            # Se a API retornou menos linhas, tenta traduzir as restantes
            # em batches menores (50 linhas)
            logger.warning(
                f"[MISMATCH] API retornou {len(raw_lines)}/{len(lines)}. "
                f"Tentando recuperar linhas faltantes via sub-batches."
            )
            print(
                f"[RECOVERY] Recuperando {len(lines) - len(raw_lines)} linhas "
                f"faltantes via sub-batches..."
            )

            # Monta resultado parcial
            result = []
            missing_indices = []
            for i in range(len(lines)):
                if i < len(raw_lines) and raw_lines[i].strip():
                    result.append(raw_lines[i] + "\n")
                else:
                    result.append(lines[i] + "\n")  # placeholder
                    missing_indices.append(i)

            # Tenta traduzir as linhas faltantes em sub-batches de 50
            SUB_BATCH = 50
            recovered = 0
            for sb_start in range(0, len(missing_indices), SUB_BATCH):
                sb_indices = missing_indices[sb_start:sb_start + SUB_BATCH]
                sb_lines = [lines[idx] for idx in sb_indices]
                try:
                    sb_result, sb_ok, _ = _translate_single_batch(
                        sb_lines, api_key, target_language, timeout,
                        max_retries=2, _fallback_attempted=_fallback_attempted,
                        _mismatch_retried=True  # evita recursão infinita
                    )
                    if sb_ok or (sb_result and len(sb_result) == len(sb_lines)):
                        for j, idx in enumerate(sb_indices):
                            if j < len(sb_result):
                                t = sb_result[j].strip()
                                if t and t != lines[idx]:
                                    result[idx] = sb_result[j]
                                    recovered += 1
                except Exception as sub_err:
                    logger.warning(f"[RECOVERY] Sub-batch falhou: {sub_err}")

            total_ok = len(lines) - len(missing_indices) + recovered
            warning_msg = (
                f"Batch parcial: {total_ok}/{len(lines)} traduzidos "
                f"({recovered} recuperados via sub-batch)"
            )
            logger.info(warning_msg)
            print(f"[RECOVERY] {warning_msg}")
            # Retorna True se conseguiu >=80% do batch
            return result, total_ok >= len(lines) * 0.8, warning_msg

        except Exception as e:
            last_error = _sanitize_error(e)
            error_str = last_error.lower()

            # === DETECTA ERRO DE MODELO NÃO ENCONTRADO (404) ===
            if _is_model_not_found_error(last_error):
                current_model = model_name or _detected_model_name or MODEL_NAME
                logger.error(f"[MODEL_NOT_FOUND] Modelo '{current_model}' indisponível: {last_error}")
                print(f"[MODEL_NOT_FOUND] Modelo '{current_model}' não encontrado ou não suporta generateContent.")

                # Tenta próximo modelo candidato (1 vez)
                next_model = _get_next_model_candidate(current_model)
                if not _fallback_attempted and next_model:
                    logger.info(f"[FALLBACK] Tentando modelo alternativo: {next_model}")
                    print(f"[FALLBACK] Tentando modelo alternativo: {next_model}...")
                    return _translate_single_batch(
                        lines, api_key, target_language, timeout, max_retries,
                        model_name=next_model, _fallback_attempted=True
                    )

                error_msg = (
                    f"Modelo inválido/indisponível: '{current_model}'. "
                    f"Verifique modelos disponíveis com: genai.list_models()"
                )
                return [l + "\n" for l in lines], False, error_msg

            # Detecta erros retriáveis (429, 503, 504, RESOURCE_EXHAUSTED)
            is_retriable = any(x in error_str for x in ['429', '503', '504', 'resource_exhausted', 'quota', 'rate'])

            if is_retriable and attempt < max_retries - 1:
                backoff_time = (2 ** attempt) * 2  # 2s, 4s, 8s
                logger.warning(f"[RETRY {attempt+1}/{max_retries}] Erro retriável: {last_error}. Aguardando {backoff_time}s...")
                print(f"[RETRY {attempt+1}/{max_retries}] Aguardando {backoff_time}s antes de tentar novamente...")
                time.sleep(backoff_time)
                continue

            # Erro não retriável ou última tentativa
            quota_mgr = get_or_create_quota_manager()
            if quota_mgr:
                quota_mgr.record_request(success=False)

            error_msg = f"Erro na tradução (tentativa {attempt+1}/{max_retries}): {last_error}"
            logger.error(error_msg)
            print(error_msg)
            return [l + "\n" for l in lines], False, error_msg

    # Se saiu do loop sem retornar, retorna erro
    return [l + "\n" for l in lines], False, f"Falha após {max_retries} tentativas: {last_error}"


def _translate_batch_legacy(
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


def _parse_neurorom_numbered_response(
    response_text: str,
    source_batch: List[str]
) -> List[str]:
    """
    Faz parse de resposta numerada (1. texto) e mantém ordem original.
    Se a tradução vier vazia ou faltar item, mantém a string original.
    """
    numbered_re = re.compile(r"^\s*(\d+)\s*[\.\)\-:]\s*(.*)$")
    translated_map: Dict[int, str] = {}

    for raw_line in response_text.splitlines():
        match = numbered_re.match(raw_line.strip())
        if not match:
            continue
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(source_batch):
            translated_map[idx] = match.group(2).strip()

    parsed: List[str] = []
    for i, original in enumerate(source_batch):
        candidate = translated_map.get(i, "").strip()
        parsed.append(candidate if candidate else original)
    return parsed


def _translate_neurorom_single_request(
    batch: List[str],
    src_lang: str,
    tgt_lang: str,
    api_key: str,
    timeout: float = 120.0,
    max_retries: int = 3,
) -> List[str]:
    """
    Traduz um único lote no formato numerado solicitado.
    Retry automático para erros de quota: espera 60s, máximo 3 tentativas.
    """
    if not batch:
        return []

    if not GENAI_AVAILABLE:
        return list(batch)

    if not configure_api(api_key, timeout):
        return list(batch)

    generation_config = {
        "temperature": 0.2,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
    }

    numbered_lines = [f"{i + 1}. {text}" for i, text in enumerate(batch)]
    prompt = (
        f"Traduza as seguintes frases de {src_lang} para {tgt_lang}.\n"
        f"Responda APENAS com as traduções numeradas, uma por linha, mantendo a ordem:\n"
        + "\n".join(numbered_lines)
    )

    for attempt in range(max_retries):
        quota_mgr = get_or_create_quota_manager()
        if quota_mgr:
            if not quota_mgr.wait_if_needed():
                logger.error("Limite diário de requisições atingido (quota).")
                return list(batch)
        else:
            time.sleep(RATE_LIMIT_DELAY)

        try:
            model = genai.GenerativeModel(
                model_name=_detected_model_name or _detect_gemini_model(tgt_lang),
                generation_config=generation_config,
                safety_settings=_get_safety_settings(),
            )
            response = model.generate_content(prompt)

            if quota_mgr:
                quota_mgr.record_request(success=True)

            if not response or not getattr(response, "text", None):
                return list(batch)

            parsed = _parse_neurorom_numbered_response(response.text, batch)
            return parsed

        except Exception as e:
            err = _sanitize_error(e)
            err_lower = err.lower()
            is_quota_error = any(
                token in err_lower
                for token in ("quota", "resource_exhausted", "429", "rate limit", "too many requests")
            )

            if quota_mgr:
                quota_mgr.record_request(success=False)

            if is_quota_error and attempt < max_retries - 1:
                logger.warning(
                    f"[GEMINI_BATCH_RETRY] Erro de quota ({attempt + 1}/{max_retries}): {err}. "
                    f"Aguardando 60s..."
                )
                time.sleep(60)
                continue

            logger.error(f"[GEMINI_BATCH] Falha no lote: {err}")
            return list(batch)

    return list(batch)


def _translate_batch_neurorom(
    strings: List[str],
    src_lang: str,
    tgt_lang: str,
    api_key: str,
    timeout: float = 120.0,
) -> List[str]:
    """
    Novo fluxo NEUROROM:
    - Agrupa em lotes de 50 strings por request.
    - Prompt numerado.
    - Parse numerado mantendo ordem.
    - Se tradução vier vazia, mantém original.
    """
    if not strings:
        return []

    if not api_key or not api_key.strip():
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            return list(strings)

    output: List[str] = []
    for i in range(0, len(strings), NEUROROM_BATCH_SIZE):
        batch = strings[i:i + NEUROROM_BATCH_SIZE]
        output.extend(
            _translate_neurorom_single_request(
                batch=batch,
                src_lang=src_lang,
                tgt_lang=tgt_lang,
                api_key=api_key,
                timeout=timeout,
                max_retries=3,
            )
        )

    return output


def translate_batch(
    strings: List[str],
    src_lang_or_api_key: str,
    tgt_lang: str = "Portuguese (Brazil)",
    timeout: float = 120.0,
    *,
    api_key: Optional[str] = None,
) -> Union[Tuple[List[str], bool, Optional[str]], List[str]]:
    """
    API dual para compatibilidade:

    1) Modo legado (retorna tupla):
       translate_batch(lines, api_key, target_language, timeout)

    2) Modo NEUROROM batch (retorna lista):
       translate_batch(strings, src_lang, tgt_lang, api_key="<SUA_KEY>")
    """
    if api_key is None:
        return _translate_batch_legacy(strings, src_lang_or_api_key, tgt_lang, timeout)

    return _translate_batch_neurorom(
        strings=strings,
        src_lang=src_lang_or_api_key,
        tgt_lang=tgt_lang,
        api_key=api_key,
        timeout=timeout,
    )


def ai_review_translations(
    originals: List[str],
    translations: List[str],
    api_key: str,
    target_language: str = "Portuguese (Brazil)",
    timeout: float = 120.0
) -> Tuple[List[str], bool, Optional[str]]:
    """
    Segundo passo de qualidade: IA revisa suas próprias traduções.
    Corrige frases estranhas, mantém nomes próprios, ajusta naturalidade.

    Returns:
        (traduções_revisadas, sucesso, erro)
    """
    if not GENAI_AVAILABLE or not originals or not translations:
        return translations, True, None

    # Só revisa se houver textos substanciais (não desperdiça API com menus curtos)
    substantial = [t for t in translations if len(t.strip()) > 15]
    if len(substantial) < 3:
        return translations, True, None

    if not configure_api(api_key, timeout):
        return translations, True, None  # Se falhar, retorna sem revisão

    # Prepara pares original/tradução para revisão
    review_lines = []
    for i, (orig, trans) in enumerate(zip(originals, translations)):
        o = orig.strip()
        t = trans.strip()
        if len(t) > 10:  # Só revisa textos substanciais
            review_lines.append(f"[{i+1}] ORIG: {o}")
            review_lines.append(f"[{i+1}] TRAD: {t}")

    if not review_lines:
        return translations, True, None

    review_prompt = (
        f"You are a translation quality reviewer for {target_language} game localization.\n"
        f"Below are original English texts and their translations.\n"
        f"Review ONLY for:\n"
        f"1. Unnatural/awkward phrasing - fix to sound native\n"
        f"2. Proper names that were incorrectly translated - restore original\n"
        f"3. Hallucinated content (translation much longer than original) - fix\n"
        f"4. Technical terms mistranslated\n\n"
        f"For each line that needs correction, return: [N] corrected_text\n"
        f"For lines that are OK, do NOT return anything.\n"
        f"ONLY return corrections, nothing else.\n\n"
    )
    review_text = review_prompt + "\n".join(review_lines)

    try:
        time.sleep(RATE_LIMIT_DELAY)
        model = genai.GenerativeModel(
            model_name=_detected_model_name or _detect_gemini_model(target_language),
            generation_config={"temperature": 0.2, "max_output_tokens": 8192},
            safety_settings=_get_safety_settings()
        )
        response = model.generate_content(review_text)

        if response and response.text:
            # Parse correções
            _ID_RE = re.compile(r"^\[(\d+)\]\s?(.*)", re.MULTILINE)
            corrections = _ID_RE.findall(response.text)
            fixed_count = 0
            result = list(translations)
            for num_str, corrected in corrections:
                idx = int(num_str) - 1
                if 0 <= idx < len(result) and corrected.strip():
                    # Só aplica se a correção não for absurdamente maior
                    if len(corrected) <= len(result[idx]) * 2:
                        result[idx] = corrected.strip() + "\n"
                        fixed_count += 1
            return result, True, f"Revisão: {fixed_count} correções aplicadas"

    except Exception as e:
        logger.warning(f"Revisão IA falhou (não crítico): {_sanitize_error(e)}")

    return translations, True, None


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
