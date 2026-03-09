# -*- coding: utf-8 -*-
"""
Heurísticas de plausibilidade para texto ASCII.
Uso principal: filtrar tabelas de ponteiros falsas.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable, List

_CTRL_RE = re.compile(r"[\x00-\x1F\x7F-\x9F]")
_WHITESPACE_RE = re.compile(r"\s+")
_TOKENISH_RE = re.compile(r"^[A-Z0-9_]{3,}$")
_COMMON_SHORT_WORDS = {
    "A",
    "I",
    "AM",
    "AN",
    "AS",
    "AT",
    "BE",
    "BY",
    "DO",
    "GO",
    "HE",
    "IN",
    "IS",
    "IT",
    "ME",
    "MY",
    "NO",
    "OF",
    "ON",
    "OR",
    "TO",
    "UP",
    "US",
    "WE",
    "II",
    "III",
    "IV",
    "VI",
    "VII",
    "VIII",
    "IX",
    "X",
}


def score_ascii_plausibility(text: str) -> float:
    """
    Retorna score 0.0-1.0 para plausibilidade ASCII.
    Valores baixos indicam lixo/binário disfarçado de texto.
    """
    if not text or len(text) < 3:
        return 0.0

    printable = sum(1 for c in text if _is_printable_ascii_char(c))
    ratio = printable / len(text)
    if ratio < 0.80:
        return 0.0

    if _has_repetitive_pattern(text):
        return 0.0

    if _looks_like_alphabet_sequence(text):
        return 0.0

    if _has_rare_symbols(text):
        return 0.0

    if _has_low_diversity(text):
        return 0.0

    if _has_low_alpha_ratio(text):
        return 0.0

    if _missing_vowel(text):
        return 0.0

    if _has_consonant_dominance(text):
        return 0.0

    if _has_repeated_consonant(text):
        return 0.0

    if _has_high_symbol_digit_ratio(text):
        return 0.0

    if _has_anomalous_case_mixing(text):
        return 0.0

    if _has_garbage_short_pattern(text):
        return 0.0

    if _short_no_vowel(text):
        return 0.0

    return ratio


def is_plausible_ascii(text: str, min_len: int = 3, min_printable_ratio: float = 0.80) -> bool:
    """Decide se uma string ASCII parece texto real."""
    if not text or len(text) < min_len:
        return False

    printable = sum(1 for c in text if _is_printable_ascii_char(c))
    ratio = printable / len(text)
    if ratio < min_printable_ratio:
        return False

    if _has_repetitive_pattern(text):
        return False

    if _looks_like_alphabet_sequence(text):
        return False

    if _has_rare_symbols(text):
        return False

    if _has_low_diversity(text):
        return False

    if _has_low_alpha_ratio(text):
        return False

    if _missing_vowel(text):
        return False

    if _has_consonant_dominance(text):
        return False

    if _has_repeated_consonant(text):
        return False

    if _has_high_symbol_digit_ratio(text):
        return False

    if _has_anomalous_case_mixing(text):
        return False

    if _has_garbage_short_pattern(text):
        return False

    if _short_no_vowel(text):
        return False

    return True


def should_accept_pointer_table(
    decoded_samples: Iterable[str],
    accept_ratio: float = 0.35,
    min_good: int = 4,
) -> bool:
    """
    Aceita tabela de ponteiros se houver texto plausível suficiente.
    """
    samples = [s for s in decoded_samples if s]
    if not samples:
        return False

    good = sum(1 for s in samples if is_plausible_ascii(s))
    if good < min_good:
        return False

    return (good / len(samples)) >= accept_ratio


def shannon_entropy(text: str) -> float:
    """Calcula entropia de Shannon para uma string."""
    if not text:
        return 0.0
    freq = Counter(text)
    n = len(text)
    return -sum((count / n) * math.log2(count / n) for count in freq.values())


def _has_long_ascii_run(text: str, min_run: int = 10) -> bool:
    """Detecta sequência ASCII crescente longa (assinatura típica de tabela)."""
    if not text or len(text) < min_run:
        return False
    run = 1
    prev = ord(text[0])
    for ch in text[1:]:
        cur = ord(ch)
        if cur == prev + 1:
            run += 1
            if run >= min_run:
                return True
        else:
            run = 1
        prev = cur
    return False


def looks_like_charset_table(text: str) -> bool:
    """
    Detecta linha com padrão típico de tabela de charset/fonte.
    Heurística focada em strings longas sem espaços e alta diversidade.
    """
    t = str(text or "").strip()
    # Casos curtos de "parede" alfabética fragmentada:
    # ex.: "A B C D E", "F G H I J", "L M N O".
    if _looks_like_spaced_alphabet_chunks(t):
        return True

    if len(t) < 28:
        return False
    # Tabela de charset costuma vir quase sem espaços.
    if t.count(" ") > 2:
        return False
    t_compact = t.replace(" ", "")
    if len(t_compact) < 28:
        return False

    uniq = len(set(t_compact))
    uniq_ratio = uniq / max(len(t_compact), 1)
    alnum_ratio = sum(1 for ch in t_compact if ch.isalnum()) / max(len(t_compact), 1)
    punct_ratio = sum(1 for ch in t_compact if not ch.isalnum()) / max(len(t_compact), 1)
    letters = sum(1 for ch in t_compact if ch.isalpha())
    vowels = sum(1 for ch in t_compact.lower() if ch in "aeiou")
    vowel_ratio = (vowels / max(letters, 1)) if letters else 0.0
    ent = shannon_entropy(t_compact)

    has_many_types = (
        any("A" <= ch <= "Z" for ch in t_compact)
        and any("a" <= ch <= "z" for ch in t_compact)
        and any(ch.isdigit() for ch in t_compact)
    )

    if uniq >= 18 and uniq_ratio >= 0.55 and alnum_ratio >= 0.70 and ent >= 3.8:
        return True

    if has_many_types and len(t_compact) >= 40 and uniq >= 22:
        return True

    # Parede ASCII (ordens crescentes) costuma ser dump de charset/fonte.
    if _has_long_ascii_run(t_compact, min_run=10) and len(t_compact) >= 28 and uniq >= 14:
        return True

    # Sequência explícita de alfabetos + números.
    if (
        len(t_compact) >= 30
        and "ABCDEFGHIJKLMNOPQRSTUVWXYZ" in t_compact
        and any(ch.isdigit() for ch in t_compact)
    ):
        return True

    if (
        len(t_compact) >= 30
        and "abcdefghijklmnopqrstuvwxyz" in t_compact
        and any(ch.isdigit() for ch in t_compact)
    ):
        return True

    # Muro de pontuação/símbolos longos (ex.: !"#$%&...).
    if punct_ratio >= 0.55 and uniq >= 14 and ent >= 3.4 and len(t_compact) >= 28:
        return True

    # Linha longa com quase nenhum separador linguístico e baixa vogal.
    if (
        len(t_compact) >= 36
        and t.count(" ") <= 1
        and uniq_ratio >= 0.50
        and ent >= 3.6
        and vowel_ratio <= 0.22
    ):
        return True

    return False


def normalize_human_text(text: str) -> str:
    """Normaliza texto para preview/tradução, removendo ruído técnico básico."""
    if not isinstance(text, str):
        return ""
    cleaned = _CTRL_RE.sub("", text)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    if not cleaned:
        return ""

    # Remove prefixos técnicos comuns (somente no artefato human-only).
    opcode_prefixes = {"T", "Z", "z", "h", "H", "i", "v", "V", "&", "4", "=", "{"}
    for _ in range(3):
        if len(cleaned) < 3:
            break
        first = cleaned[0]
        second = cleaned[1]
        if first not in opcode_prefixes:
            break
        if second.isupper() or second in (" ", ":"):
            candidate = cleaned[1:].lstrip()
            if candidate and re.search(r"[A-Za-z]", candidate):
                cleaned = candidate
                continue
        break

    # Remove blocos técnicos curtos no começo/fim quando há núcleo lexical forte.
    cleaned = _strip_leading_technical_chunks(cleaned)
    cleaned = _strip_trailing_technical_chunks(cleaned)

    return cleaned


def classify_human_candidate(text: str, source: str = "") -> tuple[bool, str]:
    """
    Classifica se uma linha é candidata a tradução humana.
    Retorna (aceita, motivo).
    """
    t = str(text or "")
    if not t:
        return False, "empty"

    n = len(t)
    if n < 2:
        return False, "too_short"

    # Prioridade máxima: tabela de charset/fonte deve ser cortada primeiro.
    if looks_like_charset_table(t):
        return False, "charset_table"

    n_space = t.count(" ")
    n_alpha = sum(1 for c in t if c.isalpha())
    if n_alpha < 2:
        return False, "not_enough_letters"
    if _has_rare_symbols(t):
        return False, "rare_symbol"

    tokens = [tok for tok in t.split() if tok]
    if tokens:
        tech_short = sum(1 for tok in tokens if _is_short_technical_token(tok))
        lexical = sum(1 for tok in tokens if len(tok) >= 3 and any(ch.isalpha() for ch in tok))
        if tech_short >= 2 and lexical == 0:
            return False, "tokenish"
        if len(tokens) <= 3 and tech_short >= 2 and lexical <= 1 and n <= 8:
            return False, "tokenish"

    alpha_tokens = re.findall(r"[A-Za-z]+", t)
    if len(alpha_tokens) >= 2 and all(len(tok) == 1 for tok in alpha_tokens):
        # Ex.: "I J" costuma ser fragmento/tabela, nao frase humana.
        if any(tok.upper() not in {"A", "I"} for tok in alpha_tokens):
            return False, "spaced_single_letters"
    if re.fullmatch(r"[!\?\s]*END", t.upper()):
        return False, "end_marker"
    if re.match(r"^[^A-Za-z0-9\s][A-Za-z]{4,}$", t):
        return False, "leading_symbol_fragment"
    if re.search(r"[A-Za-z][!?:;][A-Za-z]", t):
        return False, "internal_symbol_fragment"
    if re.match(r"^[A-Za-z]\s", t):
        alpha_words = re.findall(r"[A-Za-z]+", t)
        if len(alpha_words) >= 3 and len(alpha_words[0]) == 1:
            head = alpha_words[0].lower()
            if head not in {"a", "i", "o", "e"}:
                return False, "single_letter_prefix_fragment"
    if re.match(r"^'[a-z]\s", t):
        # Ex.: "'t own any." (fragmento truncado no inicio).
        return False, "leading_apostrophe_fragment"
    if len(tokens) >= 3 and tokens[0] in {"!", "?", "."} and tokens[1] in {"!", "?", "."}:
        return False, "punct_prefix_fragment"
    if n_space == 0 and n <= 3 and any(not ch.isalnum() for ch in t):
        short_exceptions = {"NO.", "YES.", "OK.", "MR.", "DR.", "ST.", "GO!", "GO."}
        if t.upper() not in short_exceptions:
            return False, "short_symbol_fragment"
    if re.fullmatch(r"[A-Z]{4,}\s+[A-Z]{1,2}", t):
        compact_alpha = "".join(ch for ch in t if ch.isalpha()).upper()
        if _has_long_ascii_run(compact_alpha, min_run=5):
            return False, "alphabet_tail_fragment"

    frac_alpha = n_alpha / max(n, 1)
    vowels = sum(1 for c in t.lower() if c in "aeiou")
    src = str(source or "").upper()
    uniq_chars = len(set(t))

    allowed_punct = set(".,!?:;'\"-()/")
    symbol_count = sum(
        1
        for c in t
        if (not c.isalnum()) and (not c.isspace()) and (c not in allowed_punct)
    )
    symbol_ratio = symbol_count / max(n, 1)

    # Linhas longas sem separação linguística tendem a ser pseudo-texto técnico.
    if n >= 28 and n_space <= 1 and uniq_chars / max(n, 1) >= 0.55 and vowels <= 2:
        return False, "low_linguistic_separators"

    if n_space == 0 and uniq_chars <= 3 and n >= 8:
        return False, "repetitive_noise"

    if (n >= 4) and (n_space == 0) and (frac_alpha < 0.70):
        return False, "gibberish_compact"

    if "POINTER_TABLE" in src:
        return False, "pointer_table_source"

    if symbol_ratio > 0.35:
        return False, "symbol_ratio"

    if n_space == 0 and len(t) <= 12:
        if _TOKENISH_RE.match(t):
            vowel_count = sum(1 for c in t.upper() if c in "AEIOU")
            if any(c.isdigit() for c in t) or "_" in t:
                return False, "tokenish"
            if vowel_count == 0:
                return False, "tokenish"
            if len(t) <= 5 and vowel_count <= 1:
                return False, "tokenish"
        if sum(ch in "{}\\/|" for ch in t) >= 2:
            return False, "tokenish"

    if n_space == 0 and 3 <= n <= 8:
        if re.fullmatch(r"[A-Z0-9_]+", t):
            if vowels == 0 or any(c.isdigit() for c in t):
                return False, "tokenish"
        if t.isupper() and vowels == 0:
            return False, "tokenish"

    if n <= 4 and vowels == 0:
        return False, "short_no_vowel"

    if re.match(r"^[A-Z]{2,}[A-Z][a-z]{2,}$", t):
        return False, "camel_fragment"

    if (
        n_space == 0
        and 4 <= n <= 10
        and any(c.islower() for c in t)
        and any(c.isupper() for c in t)
        and vowels <= 1
    ):
        return False, "mixed_fragment"

    if "SCRIPT_OPCODE_AUTO" in src:
        if n_space == 0 and n <= 18:
            return False, "script_opcode_compact"
        if symbol_ratio > 0.15:
            return False, "script_opcode_symbols"

    # Fallback: marcador técnico escapou da normalização.
    if len(t) >= 2 and t[0] in {"4", "z", "{", "&", "="} and t[1].isupper():
        return False, "technical_prefix_unstripped"
    if len(t) >= 2 and t[0] == "T" and t[1].isupper() and " " not in t[:16]:
        return False, "technical_prefix_unstripped"

    return True, "ok"


def is_human_candidate(text: str, source: str = "") -> bool:
    """Atalho booleano para `classify_human_candidate`."""
    ok, _reason = classify_human_candidate(text, source)
    return ok


def passes_min_offset_with_allowlist(
    offset: int,
    text: str,
    min_offset: int | None = None,
    allow_offsets: Iterable[int] | None = None,
    allow_regex: Iterable[str | re.Pattern] | None = None,
) -> tuple[bool, str]:
    """
    Decide corte por min_offset com exceções cirúrgicas.

    Importante:
    - Esta função só trata a etapa de offset.
    - Heurística de humanidade/lixo deve ser aplicada antes.
    """
    off = int(offset)
    if min_offset is None:
        return True, "no_min_offset"
    min_off = int(min_offset)
    if off >= min_off:
        return True, "within_min_offset"

    allow_set = {int(v) for v in (allow_offsets or [])}
    if off in allow_set:
        return True, "allow_offset"

    candidate_text = str(text or "")
    for pattern in (allow_regex or []):
        compiled = pattern
        if not isinstance(compiled, re.Pattern):
            try:
                compiled = re.compile(str(pattern), re.IGNORECASE)
            except re.error:
                continue
        try:
            if compiled.search(candidate_text):
                return True, "allow_regex"
        except Exception:
            continue

    return False, "min_offset"


def _is_printable_ascii_char(ch: str) -> bool:
    if not ch:
        return False
    code = ord(ch)
    return 0x20 <= code <= 0x7E


def _has_repetitive_pattern(text: str) -> bool:
    """Detecta padrões repetitivos simples (AAAA, ABABAB, 010101)."""
    if len(text) >= 4 and len(set(text)) == 1:
        return True

    lowered = text.lower()
    for unit_len in (1, 2, 3, 4):
        if len(lowered) < unit_len * 2:
            continue

        remainder = len(lowered) % unit_len
        base_len = len(lowered) - remainder
        if base_len >= unit_len * 2:
            unit = lowered[:unit_len]
            base = lowered[:base_len]
            if unit * (base_len // unit_len) == base:
                if (base_len / len(lowered)) >= 0.80:
                    return True

        # Permite 1 caractere “ruim” no fim, mas exige alto matching
        matches = 0
        for i, ch in enumerate(lowered):
            if ch == lowered[i % unit_len]:
                matches += 1
        if (matches / len(lowered)) >= 0.85:
            return True

    return False


def _looks_like_alphabet_sequence(text: str, min_run: int = 6) -> bool:
    """Rejeita sequências tipo alfabeto/quase-alfabeto contínuo."""
    cleaned = "".join(ch.lower() for ch in text if ch.isalpha())
    if len(cleaned) < min_run:
        return False

    run = 1
    for i in range(1, len(cleaned)):
        if ord(cleaned[i]) == ord(cleaned[i - 1]) + 1:
            run += 1
            if run >= min_run:
                return True
        else:
            run = 1
    return False


def _looks_like_spaced_alphabet_chunks(text: str) -> bool:
    """
    Detecta linhas com letras unitárias separadas por espaço em ordem alfabética.
    Exemplos típicos de lixo/charset:
    - "A B C D E"
    - "F G H I J"
    """
    t = str(text or "").strip()
    if len(t) < 7:
        return False

    alpha_only = re.sub(r"[^A-Za-z\s]", " ", t)
    tokens = [tok for tok in alpha_only.split() if tok]
    if len(tokens) < 4:
        return False
    if not all(len(tok) == 1 and tok.isalpha() for tok in tokens):
        return False

    vals = [ord(tok.upper()) for tok in tokens]
    # Sequência quase contínua: aceita 1 quebra para ruído residual.
    sequential_steps = sum(1 for i in range(1, len(vals)) if vals[i] == vals[i - 1] + 1)
    if sequential_steps >= (len(vals) - 2):
        return True

    # Faixa estreita com muitas letras unitárias também tende a ser tabela.
    uniq = len(set(vals))
    if uniq >= 4 and (max(vals) - min(vals)) <= 25 and len(tokens) >= 5:
        return True

    return False


def _has_low_diversity(text: str, min_len: int = 6, max_unique_ratio: float = 0.35, max_unique: int = 3) -> bool:
    """Rejeita textos longos com diversidade muito baixa."""
    if len(text) < min_len:
        return False
    unique = len(set(text))
    if unique <= max_unique:
        return True
    return (unique / len(text)) < max_unique_ratio


def _has_low_alpha_ratio(text: str, min_ratio: float = 0.35, min_letters: int = 2) -> bool:
    """Exige uma fração mínima de letras para strings maiores."""
    letters = sum(1 for c in text if c.isalpha())
    if len(text) >= 3 and letters == 0:
        return True
    if len(text) >= 4:
        if letters < min_letters:
            return True
        return (letters / len(text)) < min_ratio
    return False


def _missing_vowel(text: str, min_len: int = 3) -> bool:
    """Rejeita textos sem vogais a partir de certo tamanho."""
    if len(text) < min_len:
        return False
    vowels = set("aeiouAEIOU")
    return not any(c in vowels for c in text)


def _has_rare_symbols(text: str) -> bool:
    """Rejeita símbolos muito improváveis em texto natural."""
    rare = set("`~^@|")
    return any(ch in rare for ch in text)


_CONSONANTS = set("bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ")
_VOWELS = set("aeiouAEIOU")
_KNOWN_TOKENS = {"OK", "HP", "LV", "MP", "SP", "XP", "PT", "GP", "LP",
                 "1UP", "2UP", "ATK", "DEF", "STR", "DMG", "NPC", "VS",
                 "HQ", "KO", "DX", "NY", "TV", "FM", "CD", "DR", "MR",
                 "MS", "ST", "NG", "LR", "HR", "QTY", "LVL", "EXP",
                 "START", "WORLD", "EXTRA", "SWORD", "STAFF", "SPELL",
                 "CRAFT", "QUEST", "NORTH", "SOUTH", "FIRST", "FRONT",
                 "BLAST", "GHOST", "PLANT", "STMP", "CTRL", "SCRN"}


def _has_consonant_dominance(text: str) -> bool:
    """Regra 10: muitas consoantes e poucas vogais em strings curtas."""
    if len(text) > 6:
        return False
    cons = sum(1 for c in text if c in _CONSONANTS)
    vow = sum(1 for c in text if c in _VOWELS)
    if cons >= 4 and vow <= 1:
        return text.upper().strip() not in _KNOWN_TOKENS
    return False


def _has_repeated_consonant(text: str) -> bool:
    """Regra 11: consoante unica repetida demais em string curta."""
    if len(text) > 8:
        return False
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return False
    freq = Counter(c.upper() for c in alpha)
    for ch, cnt in freq.items():
        if ch in _CONSONANTS and cnt >= 3 and cnt / len(text) > 0.35:
            return True
    return False


def _has_high_symbol_digit_ratio(text: str) -> bool:
    """Regra 12: ratio alto de simbolos+digitos em strings curtas."""
    if len(text) > 5 or len(text) == 0:
        return False
    sym_digit = sum(1 for c in text if not c.isalpha() and not c.isspace())
    if sym_digit / len(text) >= 0.50:
        return text.upper().strip() not in _KNOWN_TOKENS
    return False


def _has_anomalous_case_mixing(text: str) -> bool:
    """Regra 13: case mixing anomalo em strings curtas (3-5 chars).
    Permite: ALL UPPER, all lower, Title Case. Rejeita: 'cpA', 'gXf'."""
    if not (3 <= len(text) <= 5):
        return False
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 2:
        return False
    uppers = [c for c in letters if c.isupper()]
    lowers = [c for c in letters if c.islower()]
    if uppers and lowers:
        first_alpha_idx = next(i for i, c in enumerate(text) if c.isalpha())
        if text[first_alpha_idx].isupper() and all(c.islower() for c in letters[1:]):
            return False  # Title Case ok
        return text.upper().strip() not in _KNOWN_TOKENS
    return False


def _has_garbage_short_pattern(text: str) -> bool:
    """Regra 14: strings de 3 chars com mistura digito+letra+simbolo."""
    if len(text) != 3:
        return False
    has_digit = any(c.isdigit() for c in text)
    has_letter = any(c.isalpha() for c in text)
    has_symbol = any(not c.isalnum() and not c.isspace() for c in text)
    if has_digit and has_letter and has_symbol:
        return text.upper().strip() not in _KNOWN_TOKENS
    # 3 chars all-lowercase sem vogal
    alpha = [c for c in text if c.isalpha()]
    if alpha and all(c.islower() for c in alpha) and not any(c in _VOWELS for c in text):
        return text.upper().strip() not in _KNOWN_TOKENS
    return False


def _short_no_vowel(text: str) -> bool:
    """Regra 15: strings curtas (<=4) sem vogal e com 2+ letras."""
    if len(text) > 4:
        return False
    if text.upper().strip() in _KNOWN_TOKENS:
        return False
    alpha = [c for c in text if c.isalpha()]
    if len(alpha) >= 2 and not any(c in _VOWELS for c in alpha):
        return True
    return False


def _is_short_technical_token(token: str) -> bool:
    t = str(token or "").strip().upper()
    if not t:
        return False
    if t in _COMMON_SHORT_WORDS:
        return False
    if re.fullmatch(r"\d{1,2}", t):
        return True
    if re.fullmatch(r"[A-Z]{1,2}", t):
        return True
    return bool(re.fullmatch(r"[A-Z0-9]{1,2}", t))


def _is_code_like_token(token: str) -> bool:
    t = str(token or "").strip().upper()
    if len(t) < 3 or len(t) > 4:
        return False
    if not re.fullmatch(r"[A-Z0-9]{3,4}", t):
        return False
    if t in _COMMON_SHORT_WORDS:
        return False
    vowels = sum(1 for ch in t if ch in "AEIOU")
    return vowels <= 1


def _strip_leading_technical_chunks(text: str) -> str:
    tokens = [tok for tok in str(text or "").split() if tok]
    if len(tokens) < 3:
        return str(text or "").strip()
    idx = 0
    while idx < min(4, len(tokens) - 1) and _is_short_technical_token(tokens[idx]):
        idx += 1
    removed = idx
    if removed < 2:
        return " ".join(tokens)
    remaining = tokens[idx:]
    has_long_lexical = any(len(tok) >= 4 and any(ch.isalpha() for ch in tok) for tok in remaining)
    if not has_long_lexical:
        return " ".join(tokens)
    return " ".join(remaining)


def _strip_trailing_technical_chunks(text: str) -> str:
    tokens = [tok for tok in str(text or "").split() if tok]
    if len(tokens) < 2:
        return str(text or "").strip()
    end = len(tokens)
    removed = 0
    while end > 1 and removed < 4 and _is_short_technical_token(tokens[end - 1]):
        end -= 1
        removed += 1
    if removed >= 2:
        remaining = tokens[:end]
        has_long_lexical = any(len(tok) >= 4 and any(ch.isalpha() for ch in tok) for tok in remaining)
        if has_long_lexical:
            return " ".join(remaining)
    if _is_code_like_token(tokens[-1]):
        remaining = tokens[:-1]
        has_long_lexical = any(len(tok) >= 5 and any(ch.isalpha() for ch in tok) for tok in remaining)
        if has_long_lexical:
            return " ".join(remaining)
    return " ".join(tokens)
