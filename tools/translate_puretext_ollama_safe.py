#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera {CRC32}_translated_fixed_ptbr.jsonl a partir de {CRC32}_pure_text.jsonl.

Objetivo:
- Traducao segura por lotes (Ollama)
- Preserva ordem (seq/rom_offset)
- Preserva placeholders/tokens
- Nao excede max_len_bytes (fallback para texto original)
- Gera report/proof com metricas reais
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


HEX_TOKEN_RE = re.compile(r"\[[0-9A-Fa-f]{2}\]")
GENERIC_TOKEN_RE = re.compile(
    r"(\[[^\]]+\]|\{[^}]+\}|<[^>]+>|__PROTECTED__|@[A-Z0-9_]+)"
)
ICON_RE = re.compile(r"[🎮🔍🇯🇵]")
BRACKET_TAG_RE = re.compile(
    r"\[(CMD:[^\]]+|SPEED|WAIT_[^\]]+|NEWLINE|SCROLL|CHOOSE\d*|END|ADDR:[^\]]+|PTR:[^\]]+|Block[^\]]+|[A-Z_]{2,})\]"
)
WORD_RE = re.compile(r"[A-Za-z']+")
REPEAT_RE = re.compile(r"(.)\1{3,}")

STOPWORDS_EN = set(
    """
the and you to of in is for with your this that from are can be not all one more into over then them if
her their was were will no yes my our out up down just back attack enemy enemies item use name male female
world time day warm breeze personal crisis another options option save load continue start
""".split()
)

STOPWORDS_EN_STRONG = set(
    """
the and your this that from with attack enemy enemies item world time name options option
save load continue start another personal crisis warm breeze male female
""".split()
)

PT_HINTS = set(
    """
de da do das dos em no na nos nas para por com sem que e ou se mas nao sim
voce voces seu sua seus suas meu minha meus minhas um uma uns umas
ataque inimigo inimigos mundo tempo nome item opcao opcoes salvar carregar continuar
""".split()
)

LONG_CODE_RE = re.compile(r"[A-Z0-9]{6,}")
UNMAPPED_GLYPH_RATIO_LIMIT = 0.10
LEXICON_FALLBACK = {
    "the": "o",
    "and": "e",
    "in": "em",
    "of": "de",
    "to": "para",
    "you": "voce",
    "your": "seu",
    "this": "isto",
    "that": "isso",
    "world": "mundo",
    "time": "tempo",
    "day": "dia",
    "warm": "quente",
    "breeze": "brisa",
    "another": "outro",
    "options": "opcoes",
    "option": "opcao",
    "male": "masculino",
    "female": "feminino",
    "name": "nome",
    "attack": "ataque",
    "enemy": "inimigo",
    "enemies": "inimigos",
    "save": "salvar",
    "load": "carregar",
    "continue": "continuar",
    "critical": "critico",
    "wounded": "ferido",
    "truth": "verdade",
    "courage": "coragem",
    "compassionate": "compassivo",
    "valiant": "valoroso",
    "humble": "humilde",
    "lightning": "raio",
    "rocks": "pedras",
    "bridge": "ponte",
    "chest": "bau",
    "holds": "contem",
    "invaded": "invadido",
    "weapon": "arma",
    "armour": "armadura",
    "armor": "armadura",
    "magic": "magia",
    "spirit": "espirito",
    "void": "vazio",
    "hear": "ouve",
    "motion": "movimento",
    "says": "diz",
    "here": "aqui",
    "white": "branco",
}

# Regras ortograficas automaticas (ASCII, sem acentos).
PT_ORTHO_WORD_REPLACEMENTS = [
    (r"(?<![A-Za-z0-9])vc(?![A-Za-z0-9])", "voce"),
    (r"(?<![A-Za-z0-9])vcs(?![A-Za-z0-9])", "voces"),
    (r"(?<![A-Za-z0-9])p/(?![A-Za-z0-9])", "para"),
    (r"(?<![A-Za-z0-9])c/(?![A-Za-z0-9])", "com"),
    (r"(?<![A-Za-z0-9])q(?![A-Za-z0-9])", "que"),
    (r"(?<![A-Za-z0-9])atq(?![A-Za-z0-9])", "ataque"),
    (r"(?<![A-Za-z0-9])atk(?![A-Za-z0-9])", "ataque"),
    (r"(?<![A-Za-z0-9])tds(?![A-Za-z0-9])", "todos"),
    (r"(?<![A-Za-z0-9])inims(?![A-Za-z0-9])", "inimigos"),
    (r"(?<![A-Za-z0-9])mnstrs(?![A-Za-z0-9])", "monstros"),
    (r"(?<![A-Za-z0-9])pssvl(?![A-Za-z0-9])", "possivel"),
    (r"(?<![A-Za-z0-9])dscnsr(?![A-Za-z0-9])", "descansar"),
    (r"(?<![A-Za-z0-9])cmd(?![A-Za-z0-9])", "comida"),
    (r"(?<![A-Za-z0-9])prxms(?![A-Za-z0-9])", "proximos"),
    (r"(?<![A-Za-z0-9])cnglnt(?![A-Za-z0-9])", "gelo"),
    (r"(?<![A-Za-z0-9])mostros(?![A-Za-z0-9])", "monstros"),
    (r"(?<![A-Za-z0-9])acentudado(?![A-Za-z0-9])", "acentuado"),
    (r"(?<![A-Za-z0-9])acentudada(?![A-Za-z0-9])", "acentuada"),
]

PT_ORTHO_PHRASE_REPLACEMENTS = [
    (r"\bseus\s+pessoas\b", "suas pessoas"),
    (r"\bseu\s+pessoas\b", "suas pessoas"),
    (r"\bnossos\s+pessoas\b", "nossas pessoas"),
    (r"\bnosso\s+pessoas\b", "nossas pessoas"),
    (r"\bseus\s+moedas\b", "suas moedas"),
    (r"\bseu\s+moeda\b", "sua moeda"),
    (r"\bseus\s+moeda\b", "sua moeda"),
    (r"\balgum\s+pessoas\b", "algumas pessoas"),
    (r"\bum\s+pessoas\b", "umas pessoas"),
    (r"\besta\s+pessoas\b", "estas pessoas"),
]

PT_SRC_OVERRIDE_VARIANTS = {
    "Sorry, I can't help you with that.": ["Desculpe, nao posso ajudar com isso."],
    "Maybe you can TRADE it for something more useful.": ["Talvez voce possa negociar por algo mais util."],
    "You may only eat food!": ["Voce pode comer apenas comida!", "Voce so pode comer comida!"],
    "You can't rest here, monsters are near.": [
        "Voce nao pode descansar aqui, monstros estao perto.",
        "Nao descanse aqui, monstros estao perto.",
    ],
    "@Bomb attack": ["@Bomb ataque", "@Bomb ataque de bomba"],
    "feels the effects of poison!": ["sente os efeitos do veneno!"],
    "`Ice attack": ["`Ataque de gelo", "`Golpe gelo", "`Gelo atq"],
    "Ice attack": ["Ataque de gelo", "Golpe gelo"],
    "Blaze attack": ["Ataque de fogo", "Golpe fogo"],
    "`Light attack": ["`Ataque de raio", "`Ataque de luz"],
    "Light attack": ["Ataque de raio", "Ataque de luz"],
    "LOST WORLD": ["MUNDO PERDIDO", "MUNDO PERD"],
    ">LOST WORLD": [">MUNDO PERDIDO", ">MUNDO PERD"],
    "for this unnecessary sequel.": ["por essa sequencia desnecessaria", "por essa sequencia inutil."],
    "with@melody": ["com@melodia"],
    "breaks@the@seal": ["quebra@o@selo", "quebra@selo"],
    "Letter@from": ["Carta@de"],
    "with@tears": ["com@lagrimas", "com@lagrima", "com@pranto"],
    "Prize@from": ["Premio@de"],
    "Protects@from": ["Protege@de"],
    "Lola@and@Bill": ["Lola@e@Bill"],
    "Apple@from": ["Maca@de"],
    "🇯🇵 nnon|Attack all enemies.": ["nnon|Ataque todos inimigos."],
    "Spell name:": ["Nome magia:"],
    "Somewhat shaken by this": ["Meio abalado com isso"],
    "in the grass.": ["na grama."],
    "rebirth. But this could not": ["renascer. Mas isso nao"],
    "Closing the book, you again": ["Fechando livro, de novo"],
    "tent tops blow briskly in the": ["topos de tenda no vento"],
    ". Sit here and I": [". Sente aqui e eu"],
    "Chain Mail is the armour used by more warriors than all others. Ours costs 600gp.": [
        "Cota de malha e a armadura mais usada. A nossa custa 600gp."
    ],
    "says: Peace and Joy be with you friend.": ["diz: Paz e alegria com voce."],
    "Oh, and don't mind the strange noises, it's only rats!": [
        "Ah, ignore os barulhos estranhos, sao so ratos!"
    ],
    "The last person I knew that had any Mandrake was an old alchemist named Calumny.": [
        "A ultima pessoa com Mandrake que conheci foi o velho alquimista Calumny."
    ],
    "That subject is a bit foggy, perhaps more gold will refresh my memory.": [
        "Esse assunto esta meio nublado; mais ouro refresca minha memoria."
    ],
    "Notice the fine workmanship on this axe, you'll agree 225gp is a good price.": [
        "Veja o bom trabalho neste machado; 225gp e um preco justo."
    ],
    "This magical axe can be thrown at thy enemy and will then return all for 1500gp.": [
        "Este machado magico pode ser lancado no inimigo e volta por 1500gp."
    ],
    "Thy mind is still weary from thy last Meditation!": [
        "Sua mente ainda esta cansada da ultima meditacao!"
    ],
    "says: I rule all Britannia, and shall do my best to help thee!": [
        "diz: Eu governo Britannia e farei o melhor para ajuda-lo!"
    ],
    "to reward the good!": ["para premiar o bem!"],
}


def iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def parse_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        s = value.strip().lower()
        if not s:
            return None
        try:
            if s.startswith(("-0x", "+0x")):
                sign = -1 if s.startswith("-") else 1
                return sign * int(s[3:], 16)
            if s.startswith("0x"):
                return int(s, 16)
            return int(s, 10)
        except Exception:
            return None
    return None


def normalize_ascii(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = (
        text.replace("“", "\"")
        .replace("”", "\"")
        .replace("‘", "'")
        .replace("’", "'")
        .replace("—", "-")
        .replace("–", "-")
        .replace("…", "...")
    )
    return text


def clean_for_candidate(src: str) -> str:
    t = ICON_RE.sub(" ", src or "")
    t = BRACKET_TAG_RE.sub(" ", t)
    t = HEX_TOKEN_RE.sub(" ", t)
    t = t.replace("|", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def is_candidate(src: str) -> Tuple[bool, str]:
    cleaned = clean_for_candidate(src)
    if not cleaned or len(cleaned) < 2 or len(cleaned) > 220:
        return False, cleaned

    # Repetição extrema tende a indicar lixo/artefato.
    if REPEAT_RE.search(cleaned) and len(set(cleaned.lower())) <= 3:
        return False, cleaned

    printable = sum(32 <= ord(ch) < 127 for ch in cleaned)
    if printable / max(1, len(cleaned)) < 0.85:
        return False, cleaned

    letters = sum(ch.isalpha() for ch in cleaned)
    if letters < 1:
        return False, cleaned

    nonalnum = sum(
        1
        for ch in cleaned
        if not (ch.isalnum() or ch.isspace() or ch in "'.,!?-:")
    )
    if nonalnum / max(1, len(cleaned)) > 0.40:
        return False, cleaned

    digit_ratio = sum(ch.isdigit() for ch in cleaned) / max(1, len(cleaned))
    if digit_ratio > 0.60:
        return False, cleaned

    # Evita blobs de codigos longos em caps.
    if len(LONG_CODE_RE.findall(cleaned)) >= 4:
        return False, cleaned

    return True, cleaned


def _normalized_review_flags(obj: Dict[str, Any]) -> List[str]:
    raw = obj.get("review_flags")
    if isinstance(raw, list):
        return [str(x).strip().upper() for x in raw if str(x).strip()]
    if isinstance(raw, str) and raw.strip():
        return [part.strip().upper() for part in raw.split(",") if part.strip()]
    return []


def _parse_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        out = float(value)
    except Exception:
        return None
    if out < 0:
        out = 0.0
    if out > 1:
        out = 1.0
    return out


def _calc_unmapped_ratio(obj: Dict[str, Any], text_src: str) -> Tuple[float, int, int]:
    ratio = _parse_optional_float(obj.get("unmapped_ratio"))

    glyph_count = parse_optional_int(obj.get("glyph_count"))
    if glyph_count is None or glyph_count <= 0:
        glyph_hashes = obj.get("glyph_hashes")
        if isinstance(glyph_hashes, list):
            glyph_count = len(glyph_hashes)
    if glyph_count is None or glyph_count <= 0:
        glyph_count = max(1, len(str(text_src or "")))

    unmapped_count = parse_optional_int(obj.get("unmapped_glyph_count"))
    if unmapped_count is None or unmapped_count < 0:
        raw_hashes = obj.get("unmapped_glyph_hashes")
        if isinstance(raw_hashes, list):
            unmapped_count = len(raw_hashes)
        else:
            raw_tiles = obj.get("unmapped_tiles")
            if isinstance(raw_tiles, list):
                unmapped_count = len(raw_tiles)
            else:
                unmapped_count = 0
    unmapped_count = max(0, int(unmapped_count))

    if ratio is None:
        ratio = float(unmapped_count) / float(max(1, int(glyph_count)))

    ratio = max(0.0, min(1.0, float(ratio)))
    return ratio, int(unmapped_count), int(max(1, glyph_count))


def _is_unmapped_glyph_blocked(obj: Dict[str, Any], text_src: str) -> Tuple[bool, float, int, int]:
    ratio, unmapped_count, glyph_count = _calc_unmapped_ratio(obj, text_src)
    blocked = bool(ratio > UNMAPPED_GLYPH_RATIO_LIMIT)
    return blocked, ratio, unmapped_count, glyph_count


def _allow_review_fragment_candidate(obj: Dict[str, Any]) -> bool:
    """
    Permite traduzir fragmentos revisáveis (PREFIX/OVERLAP) com guardas estritas.
    Mantém bloqueio para casos realmente inseguros.
    """
    if not isinstance(obj, dict):
        return False
    if not bool(obj.get("needs_review", False)):
        return False

    flags = set(_normalized_review_flags(obj))
    if not flags:
        return False

    allowed = {"PREFIX_FRAGMENT", "OVERLAP_FRAGMENT", "TOO_SHORT_TEXT"}
    blocked = {
        "ROUNDTRIP_FAIL",
        "HAS_BYTE_PLACEHOLDER",
        "HAS_UNKNOWN_BYTES",
        "TOO_SHORT_FRAGMENT",
        "NOT_PLAUSIBLE_TEXT_SMS",
        "UNMAPPED_GLYPHS",
    }
    if flags & blocked:
        return False
    if not flags.issubset(allowed):
        return False

    if obj.get("audit_roundtrip_ok") is False:
        return False

    unknown = parse_optional_int(obj.get("unknown_bytes_count"))
    if isinstance(unknown, int) and unknown > 0:
        return False

    src = str(obj.get("text_src", "") or "")
    ok, _ = is_candidate(src)
    return bool(ok)


def looks_like_pt_translation(text: str) -> bool:
    words = [w.lower() for w in WORD_RE.findall(text or "")]
    if len(words) < 2:
        return False
    hits = sum(1 for w in words if w in PT_HINTS)
    return hits >= 1


def lexical_fallback_pt(text: str) -> str:
    def _repl(match: re.Match) -> str:
        w = match.group(0)
        lw = w.lower()
        mapped = LEXICON_FALLBACK.get(lw)
        if not mapped and len(lw) >= 4:
            # Fragmento por sufixo (ex.: "ightning" -> "raio").
            suffix_hits = [
                (len(k) - len(lw), k, v)
                for k, v in LEXICON_FALLBACK.items()
                if len(k) > len(lw) and k.endswith(lw)
            ]
            if suffix_hits:
                suffix_hits.sort(key=lambda it: (it[0], len(it[1])))
                mapped = suffix_hits[0][2]
        if not mapped:
            return w
        if w.isupper():
            return mapped.upper()
        if w[:1].isupper():
            return mapped[:1].upper() + mapped[1:]
        return mapped

    out = re.sub(r"[A-Za-z']+", _repl, text or "")
    out = normalize_ascii(out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def protect_tokens(text: str) -> Tuple[str, Dict[str, str]]:
    mapping: Dict[str, str] = {}
    idx = 0

    def _repl(match: re.Match) -> str:
        nonlocal idx
        key = f"__TOK{idx}__"
        mapping[key] = match.group(0)
        idx += 1
        return key

    protected = GENERIC_TOKEN_RE.sub(_repl, text)
    return protected, mapping


def restore_tokens(text: str, mapping: Dict[str, str]) -> str:
    out = text
    for key, val in mapping.items():
        out = out.replace(key, val)
    return out


def placeholders_preserved(src: str, dst: str) -> bool:
    src_tokens = GENERIC_TOKEN_RE.findall(src or "")
    return all(tok in (dst or "") for tok in src_tokens)


def can_fit_ascii(text: str, max_len_bytes: Optional[int]) -> bool:
    if max_len_bytes is None:
        return True
    try:
        size = len((text or "").encode("ascii", errors="strict"))
    except UnicodeEncodeError:
        return False
    return size <= int(max_len_bytes)


def choose_first_fitting_variant(
    variants: List[str],
    max_len_bytes: Optional[int],
) -> Optional[str]:
    if not variants:
        return None
    normalized = [re.sub(r"\s+", " ", normalize_ascii(v)).strip() for v in variants if v]
    if not normalized:
        return None
    if max_len_bytes is None:
        return normalized[0]
    for cand in normalized:
        if can_fit_ascii(cand, max_len_bytes):
            return cand
    return None


def looks_readable_text(text: str) -> bool:
    t = re.sub(r"\s+", " ", normalize_ascii(text or "")).strip()
    if len(t) < 4:
        return False
    words = WORD_RE.findall(t)
    if len(words) < 2:
        return False
    letters = sum(ch.isalpha() for ch in t)
    if letters < 4:
        return False
    if letters / max(1, len(t)) < 0.45:
        return False
    return True


def has_excessive_consonant_clipping(text: str) -> bool:
    """
    Detecta saidas mutiladas (ex.: "Fchnd", "nvmnt"), comuns em compactacao agressiva.
    Se detectar, bloqueia para evitar reinserir traducao ruim.
    """
    words = [w.lower() for w in WORD_RE.findall(normalize_ascii(text or ""))]
    if not words:
        return False

    heavy = 0
    for w in words:
        if len(w) < 4:
            continue
        if w in {"gp", "gps", "rpg", "sms"}:
            continue

        vowels = sum(1 for ch in w if ch in "aeiou")
        consonants = sum(1 for ch in w if ch in "bcdfghjklmnpqrstvwxyz")

        # Palavra sem vogal (ou quase sem vogal) em tamanho util.
        if vowels == 0 and consonants >= 4:
            heavy += 1
            continue
        if len(w) >= 6 and vowels <= 1 and consonants >= 4:
            heavy += 1

    return heavy >= 2


def apply_orthographic_cleanup(
    src: str,
    dst: str,
    max_len_bytes: Optional[int],
) -> str:
    src_norm = re.sub(r"\s+", " ", normalize_ascii(src or "")).strip()
    out = re.sub(r"\s+", " ", normalize_ascii(dst or "")).strip()
    if not out:
        return out
    if not looks_readable_text(src_norm) or not looks_readable_text(out):
        return out

    variants = PT_SRC_OVERRIDE_VARIANTS.get(src_norm)
    if variants:
        chosen = choose_first_fitting_variant(variants, max_len_bytes)
        if chosen:
            out = chosen

    for pattern, repl in PT_ORTHO_WORD_REPLACEMENTS:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
    for pattern, repl in PT_ORTHO_PHRASE_REPLACEMENTS:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)

    if "poison" in src_norm.lower():
        out = re.sub(r"\bpocao\b", "veneno", out, flags=re.IGNORECASE)
        out = re.sub(r"\bvenenosa\b", "envenenada", out, flags=re.IGNORECASE)
        out = re.sub(r"\bveneno foi removida\b", "veneno foi removido", out, flags=re.IGNORECASE)
    if "ice attack" in src_norm.lower():
        out = re.sub(r"\bataque\s+cnglnt\b", "ataque de gelo", out, flags=re.IGNORECASE)
        out = re.sub(r"\bataque\s+de\s+chama\b", "ataque de gelo", out, flags=re.IGNORECASE)
    if "blaze attack" in src_norm.lower():
        out = re.sub(r"\bataque\s+de\s+raio\b", "ataque de fogo", out, flags=re.IGNORECASE)

    out = re.sub(r"\s+", " ", out).strip()
    return out


def compact_translation_to_fit(text: str, max_len_bytes: Optional[int]) -> Tuple[str, bool]:
    """
    Tenta compactar traducao para caber em max_len_bytes.
    Retorna (texto_final, used_last_resort_truncate).
    """
    if max_len_bytes is None:
        return text, False

    out = (text or "").strip()
    if can_fit_ascii(out, max_len_bytes):
        return out, False

    # 1) Compactacao suave com foco em legibilidade.
    mild_replacements = [
        (r"\besta\b", "ta"),
        (r"\bestao\b", "tao"),
        (r"\bpara\b", "pra"),
    ]
    for pat, rep in mild_replacements:
        out2 = re.sub(pat, rep, out, flags=re.IGNORECASE)
        out2 = re.sub(r"\s+", " ", out2).strip()
        if out2 != out:
            out = out2
            if can_fit_ascii(out, max_len_bytes):
                return out, False

    # 2) Remove palavras de ligacao como ultimo ajuste sem quebrar semantica.
    filler_words = r"\b(o|a|os|as|um|uma|de|do|da|dos|das|e|ou)\b"
    tries = 0
    while not can_fit_ascii(out, max_len_bytes) and tries < 20:
        tries += 1
        out2 = re.sub(filler_words, " ", out, count=1, flags=re.IGNORECASE)
        out2 = re.sub(r"\s+", " ", out2).strip()
        if out2 == out:
            break
        out = out2
        if can_fit_ascii(out, max_len_bytes):
            return out, False

    # 3) Nao mutila palavras e nao trunca: deixa o bloqueio de tamanho agir.
    # Isso evita saidas ruins como "Fchnd"/"nvmnt".
    return out, False


def _ollama_generate(
    prompt: str,
    model: str,
    timeout: int,
    temperature: float = 0.0,
) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": float(temperature),
        },
    }
    r = requests.post(
        "http://127.0.0.1:11434/api/generate",
        json=payload,
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    return str(data.get("response", "") or "")


def translate_batch_ollama(
    pairs: List[Tuple[int, str]],
    model: str,
    timeout: int,
) -> Dict[int, str]:
    """
    Entrada: [(id, protected_text)]
    Saida: {id: translated_text}
    """
    lines = [f"{idx}|||{txt}" for idx, txt in pairs]
    block = "\n".join(lines)
    prompt = (
        "Traduza do ingles para portugues brasileiro.\n"
        "Mantenha placeholders (ex: __TOK0__) exatamente.\n"
        "Se a linha parecer fragmentada/truncada, entregue PT-BR natural (sem copiar lixo).\n"
        "Nao adicione comentarios.\n"
        "Retorne SOMENTE linhas no formato id|||traducao.\n\n"
        f"{block}\n"
    )
    raw = _ollama_generate(prompt=prompt, model=model, timeout=timeout)

    out: Dict[int, str] = {}
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln or "|||" not in ln:
            continue
        left, right = ln.split("|||", 1)
        left = left.strip()
        right = right.strip()
        if not left.isdigit():
            continue
        out[int(left)] = right
    return out


def _is_chainable_text(cleaned: str) -> bool:
    if not cleaned:
        return False
    if len(cleaned) < 2 or len(cleaned) > 120:
        return False
    if not any(ch.isalpha() for ch in cleaned):
        return False
    if GENERIC_TOKEN_RE.search(cleaned):
        return False
    if len(LONG_CODE_RE.findall(cleaned)) >= 2 and len(cleaned) <= 10:
        return False
    return True


def _parse_chain_segments(text: str, expected_segments: int) -> Optional[Dict[int, str]]:
    marker_re = re.compile(r"__SEG(\d+)__")
    matches = list(marker_re.finditer(text or ""))
    if not matches:
        return None
    out: Dict[int, str] = {}
    for i, m in enumerate(matches):
        seg_idx = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text or "")
        chunk = (text or "")[start:end]
        chunk = re.sub(r"^[\s|:;-]+", "", chunk)
        chunk = re.sub(r"[\s|]+$", "", chunk)
        out[seg_idx] = chunk.strip()
    if any(i not in out for i in range(expected_segments)):
        return None
    return out


def _build_chain_fallback_segments(grp: List[Dict[str, Any]]) -> Dict[int, str]:
    """
    Fallback deterministico para chain: traduz segmento a segmento via glossario local.
    Usado quando o parse do bloco falha ou quando o bloco retornou sem ganho real.
    """
    out: Dict[int, str] = {}
    for i, row in enumerate(grp):
        src = str(row.get("text_src", "") or "")
        max_len = row.get("max_len_bytes")
        if not isinstance(max_len, int):
            max_len = parse_optional_int(max_len)
        if not isinstance(max_len, int):
            max_len = None

        cand = lexical_fallback_pt(src)
        cand = normalize_ascii(cand)
        cand = re.sub(r"\s+", " ", cand).strip()
        if not cand:
            continue
        cand = apply_orthographic_cleanup(src, cand, max_len)
        if not placeholders_preserved(src, cand):
            continue
        cand, _ = compact_translation_to_fit(cand, max_len)
        if has_excessive_consonant_clipping(cand):
            continue
        if not can_fit_ascii(cand, max_len):
            continue
        try:
            cand.encode("ascii", errors="strict")
        except UnicodeEncodeError:
            continue

        src_norm = re.sub(r"\s+", " ", normalize_ascii(src)).strip().lower()
        cand_norm = re.sub(r"\s+", " ", normalize_ascii(cand)).strip().lower()
        if src_norm == cand_norm:
            continue
        out[i] = cand
    return out


def build_chain_translations(
    candidate_rows: List[Dict[str, Any]],
    translated_by_src: Dict[str, str],
    model: str,
    timeout: int,
    max_segments: int = 6,
    max_chars: int = 320,
) -> Tuple[Dict[int, str], Dict[str, Any]]:
    """
    CHAIN TRANSLATION:
    concatena segmentos adjacentes -> traduz de uma vez -> divide por segmento.
    """
    chain_by_id: Dict[int, str] = {}
    metrics = {
        "enabled": True,
        "groups_total": 0,
        "groups_ok": 0,
        "groups_fail": 0,
        "items_input": 0,
        "items_translated": 0,
    }
    if not candidate_rows:
        return chain_by_id, metrics

    pending: List[Dict[str, Any]] = []
    for row in candidate_rows:
        src = str(row.get("text_src", "") or "")
        base = translated_by_src.get(src, src)
        src_norm = re.sub(r"\s+", " ", normalize_ascii(src)).strip().lower()
        base_norm = re.sub(r"\s+", " ", normalize_ascii(base)).strip().lower()
        if base_norm == src_norm and _is_chainable_text(str(row.get("cleaned", "") or "")):
            pending.append(row)
    if not pending:
        return chain_by_id, metrics

    pending.sort(key=lambda r: (int(r.get("seq", 0) or 0), int(r.get("offset_int", 0) or 0)))
    metrics["items_input"] = int(len(pending))

    groups: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = []
    cur_chars = 0
    prev_seq = None
    for row in pending:
        seq = int(row.get("seq", 0) or 0)
        cleaned = str(row.get("cleaned", "") or "")
        seg_cost = len(cleaned) + 16
        seq_gap = 1 if prev_seq is None else max(0, int(seq - prev_seq))
        breaks_chain = (
            (prev_seq is not None and seq_gap > 2)
            or (len(cur) >= max_segments)
            or (cur_chars + seg_cost > max_chars)
        )
        if cur and breaks_chain:
            if len(cur) >= 2:
                groups.append(cur)
            cur = []
            cur_chars = 0
        cur.append(row)
        cur_chars += seg_cost
        prev_seq = seq
    if len(cur) >= 2:
        groups.append(cur)

    metrics["groups_total"] = int(len(groups))
    if not groups:
        return chain_by_id, metrics

    for grp in groups:
        seg_texts: List[str] = []
        seg_maps: List[Dict[str, str]] = []
        for row in grp:
            protected, mapping = protect_tokens(str(row.get("cleaned", "") or ""))
            seg_texts.append(protected)
            seg_maps.append(mapping)
        concat = " ".join(f"__SEG{i}__{txt}" for i, txt in enumerate(seg_texts))
        prompt = (
            "Traduza do ingles para portugues brasileiro.\n"
            "Regras obrigatorias:\n"
            "1) Preserve EXATAMENTE todos os marcadores __SEG0__, __SEG1__ etc.\n"
            "2) Nao remova, nao renomeie e nao reordene os marcadores.\n"
            "3) Se um segmento parecer truncado, traduza para PT-BR natural sem manter lixo.\n"
            "4) Retorne somente a sequencia com marcadores e traducao.\n\n"
            f"{concat}\n"
        )
        try:
            raw = _ollama_generate(prompt=prompt, model=model, timeout=timeout, temperature=0.0)
        except Exception:
            parsed = _build_chain_fallback_segments(grp)
            if not parsed:
                metrics["groups_fail"] += 1
                continue
        else:
            parsed = _parse_chain_segments(raw, len(grp))
            if not parsed:
                parsed = _build_chain_fallback_segments(grp)
                if not parsed:
                    metrics["groups_fail"] += 1
                    continue

        applied = 0
        for i, row in enumerate(grp):
            src = str(row.get("text_src", "") or "")
            dst = restore_tokens(str(parsed.get(i, "") or ""), seg_maps[i])
            dst = normalize_ascii(dst)
            dst = re.sub(r"\s+", " ", dst).strip()
            if not dst:
                continue
            max_len = row.get("max_len_bytes")
            if not isinstance(max_len, int):
                max_len = parse_optional_int(max_len)
            if not isinstance(max_len, int):
                max_len = None
            dst = apply_orthographic_cleanup(src, dst, max_len)
            if not placeholders_preserved(src, dst):
                continue
            dst, _ = compact_translation_to_fit(dst, max_len)
            if has_excessive_consonant_clipping(dst):
                continue
            if not can_fit_ascii(dst, max_len):
                continue
            try:
                dst.encode("ascii", errors="strict")
            except UnicodeEncodeError:
                continue
            src_norm = re.sub(r"\s+", " ", normalize_ascii(src)).strip().lower()
            dst_norm = re.sub(r"\s+", " ", normalize_ascii(dst)).strip().lower()
            if src_norm == dst_norm:
                continue

            item_id = parse_optional_int(row.get("id"))
            if item_id is None:
                continue
            chain_by_id[int(item_id)] = dst
            applied += 1

        if applied > 0:
            metrics["groups_ok"] += 1
            metrics["items_translated"] += int(applied)
        else:
            metrics["groups_fail"] += 1

    return chain_by_id, metrics


def collect_candidates(
    pure_jsonl: Path,
    max_unique: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, str], Dict[str, Any], Dict[str, Any]]:
    unique_candidates: Dict[str, str] = {}
    candidate_rows: List[Dict[str, Any]] = []
    stats = {
        "items_total": 0,
        "safe_items": 0,
        "review_fragment_items": 0,
        "blocked_unmapped_glyphs": 0,
        "candidate_items": 0,
        "candidate_unique": 0,
        "candidate_truncated_by_cap": 0,
    }
    meta: Dict[str, Any] = {}

    for obj in iter_jsonl(pure_jsonl):
        if obj.get("type") == "meta":
            meta = obj
            continue

        stats["items_total"] += 1
        src = str(obj.get("text_src", ""))
        blocked_unmapped, _ratio, _unmapped_count, _glyph_count = _is_unmapped_glyph_blocked(obj, src)
        if blocked_unmapped:
            stats["blocked_unmapped_glyphs"] += 1
            continue

        safe_mode = bool(obj.get("reinsertion_safe", False))
        allow_review_fragment = False
        if safe_mode:
            stats["safe_items"] += 1
            if bool(obj.get("needs_review", False)):
                continue
            rv = obj.get("review_flags")
            if isinstance(rv, list) and len(rv) > 0:
                continue
        else:
            allow_review_fragment = _allow_review_fragment_candidate(obj)
            if not allow_review_fragment:
                continue
            stats["review_fragment_items"] += 1

        ok, cleaned = is_candidate(src)
        if not ok:
            continue
        stats["candidate_items"] += 1
        item_id = parse_optional_int(obj.get("id"))
        if item_id is None:
            item_id = int(stats["items_total"])
        seq_val = parse_optional_int(obj.get("seq"))
        if seq_val is None:
            seq_val = int(stats["candidate_items"] - 1)
        off_val = parse_optional_int(obj.get("rom_offset", obj.get("offset")))
        if off_val is None:
            off_val = 0
        max_len = parse_optional_int(obj.get("max_len_bytes"))
        if max_len is None:
            max_len = parse_optional_int(obj.get("max_len"))
        candidate_rows.append(
            {
                "id": int(item_id),
                "seq": int(seq_val),
                "offset_int": int(off_val),
                "text_src": src,
                "cleaned": cleaned,
                "max_len_bytes": int(max_len) if max_len is not None else None,
                "allow_review_fragment": bool(allow_review_fragment),
            }
        )
        if src not in unique_candidates:
            if len(unique_candidates) >= max_unique:
                stats["candidate_truncated_by_cap"] += 1
                continue
            unique_candidates[src] = cleaned

    stats["candidate_unique"] = len(unique_candidates)
    return candidate_rows, unique_candidates, stats, meta


def build_translations(
    unique_candidates: Dict[str, str],
    model: str,
    timeout: int,
    batch_size: int,
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    items = list(unique_candidates.items())  # [(src, cleaned)]

    translated: Dict[str, str] = {}
    metrics = {
        "candidate_unique": len(items),
        "translated_ok": 0,
        "translated_fail": 0,
        "translated_lexical_fallback": 0,
        "batches_total": 0,
        "batches_fail": 0,
    }

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        metrics["batches_total"] += 1

        protected_rows: List[Tuple[int, str]] = []
        row_meta: Dict[int, Tuple[str, Dict[str, str]]] = {}
        for j, (src, cleaned) in enumerate(batch):
            protected, mapping = protect_tokens(cleaned)
            row_id = i + j
            protected_rows.append((row_id, protected))
            row_meta[row_id] = (src, mapping)

        try:
            raw_out = translate_batch_ollama(
                pairs=protected_rows,
                model=model,
                timeout=timeout,
            )
        except Exception:
            metrics["batches_fail"] += 1
            for src, _ in batch:
                fallback = lexical_fallback_pt(src)
                if fallback and normalize_ascii(fallback).strip().lower() != normalize_ascii(src).strip().lower():
                    translated[src] = fallback
                    metrics["translated_ok"] += 1
                    metrics["translated_lexical_fallback"] += 1
                else:
                    metrics["translated_fail"] += 1
                    translated[src] = src
            continue

        for row_id, (src, mapping) in row_meta.items():
            got = raw_out.get(row_id)
            if not got:
                fallback = lexical_fallback_pt(src)
                if fallback and normalize_ascii(fallback).strip().lower() != normalize_ascii(src).strip().lower():
                    translated[src] = fallback
                    metrics["translated_ok"] += 1
                    metrics["translated_lexical_fallback"] += 1
                else:
                    metrics["translated_fail"] += 1
                    translated[src] = src
                continue
            restored = restore_tokens(got, mapping)
            restored = normalize_ascii(restored)
            restored = re.sub(r"\s+", " ", restored).strip()
            if not restored:
                fallback = lexical_fallback_pt(src)
                if fallback and normalize_ascii(fallback).strip().lower() != normalize_ascii(src).strip().lower():
                    translated[src] = fallback
                    metrics["translated_ok"] += 1
                    metrics["translated_lexical_fallback"] += 1
                else:
                    metrics["translated_fail"] += 1
                    translated[src] = src
                continue
            # Gate de plausibilidade: evita "traduzir" blobs codificados.
            if not looks_like_pt_translation(restored):
                fallback = lexical_fallback_pt(restored)
                if (
                    fallback
                    and fallback != src
                    and placeholders_preserved(src, fallback)
                    and looks_like_pt_translation(fallback)
                ):
                    restored = fallback
                    metrics["translated_lexical_fallback"] += 1
                else:
                    fallback_src = lexical_fallback_pt(src)
                    if (
                        fallback_src
                        and fallback_src != src
                        and placeholders_preserved(src, fallback_src)
                        and looks_like_pt_translation(fallback_src)
                    ):
                        restored = fallback_src
                        metrics["translated_lexical_fallback"] += 1
                    else:
                        metrics["translated_fail"] += 1
                        translated[src] = src
                        continue
            translated[src] = restored
            metrics["translated_ok"] += 1

    return translated, metrics


def apply_translations(
    pure_jsonl: Path,
    out_jsonl: Path,
    translated_by_src: Dict[str, str],
    translated_by_id: Optional[Dict[int, str]] = None,
    fallback_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)

    m = {
        "items_total": 0,
        "meta_written": False,
        "text_changed": 0,
        "text_unchanged": 0,
        "blocked_unmapped_glyphs": 0,
        "blocked_too_long": 0,
        "blocked_placeholder": 0,
        "blocked_non_ascii": 0,
        "blocked_quality": 0,
        "truncated_last_resort": 0,
        "chain_overrides_used": 0,
    }

    source_meta: Optional[Dict[str, Any]] = None
    for meta_obj in iter_jsonl(pure_jsonl):
        if meta_obj.get("type") == "meta":
            source_meta = dict(meta_obj)
            break

    fb = fallback_meta if isinstance(fallback_meta, dict) else {}

    with pure_jsonl.open("r", encoding="utf-8", errors="replace") as fin, out_jsonl.open(
        "w", encoding="utf-8", newline="\n"
    ) as fout:
        def _cmp_norm(s: str) -> str:
            t = ICON_RE.sub(" ", s or "")
            t = re.sub(r"\s+", " ", t).strip().lower()
            return t

        # Sempre garante um header/meta para trava CRC/SIZE na reinsercao.
        if source_meta is None:
            synth = {
                "type": "meta",
                "schema": "neurorom.translated_jsonl.v1",
                "rom_crc32": str(fb.get("rom_crc32") or "").upper() or None,
                "rom_size": fb.get("rom_size"),
                "stage": "translated_fixed_ptbr",
                "ordering": "seq/rom_offset",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "source_pure_jsonl": str(pure_jsonl),
                "generated_from_missing_meta": True,
            }
            fout.write(json.dumps(synth, ensure_ascii=False) + "\n")
            m["meta_written"] = True

        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue

            if obj.get("type") == "meta":
                meta = dict(obj)
                if not meta.get("rom_crc32"):
                    meta["rom_crc32"] = str(fb.get("rom_crc32") or "").upper() or None
                if meta.get("rom_size") in (None, "", 0):
                    meta["rom_size"] = fb.get("rom_size")
                meta["stage"] = "translated_fixed_ptbr"
                meta["ordering"] = "seq/rom_offset"
                meta["generated_at"] = datetime.now().isoformat(timespec="seconds")
                fout.write(json.dumps(meta, ensure_ascii=False) + "\n")
                m["meta_written"] = True
                continue

            m["items_total"] += 1
            src = str(obj.get("text_src", ""))
            item_id = parse_optional_int(obj.get("id"))
            blocked_unmapped, unmapped_ratio, unmapped_count, glyph_count = _is_unmapped_glyph_blocked(
                obj, src
            )
            has_candidate_translation = False
            dst_candidate = src
            if not blocked_unmapped:
                if (
                    isinstance(translated_by_id, dict)
                    and item_id is not None
                    and int(item_id) in translated_by_id
                ):
                    dst_candidate = translated_by_id[int(item_id)]
                    has_candidate_translation = True
                    m["chain_overrides_used"] += 1
                elif src in translated_by_src:
                    has_candidate_translation = True
                    dst_candidate = translated_by_src.get(src, src)
            dst_candidate = normalize_ascii(dst_candidate)
            dst_candidate = re.sub(r"\s+", " ", dst_candidate).strip()
            max_len = obj.get("max_len_bytes")
            if isinstance(max_len, str) and max_len.isdigit():
                max_len = int(max_len)
            if not isinstance(max_len, int):
                max_len = None

            status = "UNCHANGED"
            block_reason = None
            final_dst = src

            if blocked_unmapped:
                status = "BLOCKED"
                block_reason = "UNMAPPED_GLYPHS"
                final_dst = src
                m["blocked_unmapped_glyphs"] += 1
            elif has_candidate_translation:
                status = "OK"
                final_dst = dst_candidate
                final_dst = apply_orthographic_cleanup(src, final_dst, max_len)

                if not placeholders_preserved(src, final_dst):
                    status = "BLOCKED"
                    block_reason = "PLACEHOLDER_FAIL"
                    final_dst = src
                    m["blocked_placeholder"] += 1
                else:
                    final_dst, used_truncate = compact_translation_to_fit(final_dst, max_len)
                    if used_truncate:
                        m["truncated_last_resort"] += 1
                    if has_excessive_consonant_clipping(final_dst):
                        status = "BLOCKED"
                        block_reason = "QUALITY_CLIPPED_TEXT"
                        final_dst = src
                        m["blocked_quality"] += 1
                    elif not can_fit_ascii(final_dst, max_len):
                        status = "BLOCKED"
                        block_reason = "TOO_LONG_FOR_MAX_LEN_BYTES"
                        final_dst = src
                        m["blocked_too_long"] += 1
                    else:
                        try:
                            final_dst.encode("ascii", errors="strict")
                        except UnicodeEncodeError:
                            status = "BLOCKED"
                            block_reason = "NON_ASCII_AFTER_NORMALIZATION"
                            final_dst = src
                            m["blocked_non_ascii"] += 1
                        else:
                            if _cmp_norm(final_dst) == _cmp_norm(src):
                                final_dst = src
                                status = "UNCHANGED"
                            elif final_dst == src:
                                status = "UNCHANGED"
                            else:
                                status = "OK"

            obj["text_dst"] = final_dst
            obj["translation_status"] = status
            if blocked_unmapped:
                obj["needs_review"] = True
                review_flags = _normalized_review_flags(obj)
                if "UNMAPPED_GLYPHS" not in review_flags:
                    review_flags.append("UNMAPPED_GLYPHS")
                obj["review_flags"] = review_flags
            if blocked_unmapped or unmapped_count > 0:
                obj["unmapped_ratio"] = float(round(unmapped_ratio, 4))
                obj["unmapped_glyph_count"] = int(unmapped_count)
                obj["glyph_count"] = int(glyph_count)
            if block_reason:
                obj["translation_block_reason"] = block_reason
            else:
                obj.pop("translation_block_reason", None)

            if final_dst != src:
                m["text_changed"] += 1
            else:
                m["text_unchanged"] += 1

            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")

    return m


def write_report_and_proof(
    report_path: Path,
    proof_path: Path,
    payload: Dict[str, Any],
) -> None:
    lines = [
        "TRANSLATION STAGE 2 (OLLAMA SAFE)",
        f"generated_at={payload['generated_at']}",
        f"rom_crc32={payload.get('rom_crc32')}",
        f"rom_size={payload.get('rom_size')}",
        f"translation_input={payload.get('translation_input')}",
        f"translation_output={payload.get('translation_output')}",
        "",
        "CANDIDATE_SCAN:",
        f"  items_total={payload['candidate_scan']['items_total']}",
        f"  safe_items={payload['candidate_scan'].get('safe_items', 0)}",
        f"  blocked_unmapped_glyphs={payload['candidate_scan'].get('blocked_unmapped_glyphs', 0)}",
        f"  candidate_items={payload['candidate_scan']['candidate_items']}",
        f"  candidate_unique={payload['candidate_scan']['candidate_unique']}",
        f"  candidate_truncated_by_cap={payload['candidate_scan']['candidate_truncated_by_cap']}",
        "",
        "OLLAMA_METRICS:",
        f"  model={payload['ollama']['model']}",
        f"  batches_total={payload['ollama']['batches_total']}",
        f"  batches_fail={payload['ollama']['batches_fail']}",
        f"  translated_ok={payload['ollama']['translated_ok']}",
        f"  translated_fail={payload['ollama']['translated_fail']}",
        "",
        "CHAIN_METRICS:",
        f"  enabled={str(bool(payload.get('chain', {}).get('enabled', False))).lower()}",
        f"  groups_total={payload.get('chain', {}).get('groups_total', 0)}",
        f"  groups_ok={payload.get('chain', {}).get('groups_ok', 0)}",
        f"  groups_fail={payload.get('chain', {}).get('groups_fail', 0)}",
        f"  items_input={payload.get('chain', {}).get('items_input', 0)}",
        f"  items_translated={payload.get('chain', {}).get('items_translated', 0)}",
        "",
        "OUTPUT_METRICS:",
        f"  items_total={payload['output']['items_total']}",
        f"  text_changed={payload['output']['text_changed']}",
        f"  text_unchanged={payload['output']['text_unchanged']}",
        f"  truncated_last_resort={payload['output']['truncated_last_resort']}",
        f"  blocked_too_long={payload['output']['blocked_too_long']}",
        f"  blocked_unmapped_glyphs={payload['output'].get('blocked_unmapped_glyphs', 0)}",
        f"  blocked_placeholder={payload['output']['blocked_placeholder']}",
        f"  blocked_non_ascii={payload['output']['blocked_non_ascii']}",
        f"  blocked_quality={payload['output'].get('blocked_quality', 0)}",
        f"  chain_overrides_used={payload['output'].get('chain_overrides_used', 0)}",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    proof_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Traduz pure_text.jsonl para translated_fixed_ptbr.jsonl com Ollama."
    )
    parser.add_argument("--pure-jsonl", required=True, help="Arquivo {CRC32}_pure_text.jsonl")
    parser.add_argument("--out-dir", required=True, help="Pasta de saida (normalmente 2_traducao)")
    parser.add_argument("--model", default="llama3.2:latest", help="Modelo Ollama")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout por requisicao")
    parser.add_argument("--batch-size", type=int, default=10, help="Itens por lote")
    parser.add_argument("--rom-crc32", default=None, help="Forca rom_crc32 no meta (opcional)")
    parser.add_argument("--rom-size", type=int, default=None, help="Forca rom_size no meta (opcional)")
    parser.add_argument(
        "--max-unique-candidates",
        type=int,
        default=1500,
        help="Limite de textos unicos candidatos para traduzir",
    )
    args = parser.parse_args()

    pure_jsonl = Path(args.pure_jsonl).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not pure_jsonl.exists():
        raise SystemExit(f"[ERRO] pure_jsonl nao encontrado: {pure_jsonl}")

    candidate_rows, unique_candidates, scan_stats, meta = collect_candidates(
        pure_jsonl=pure_jsonl,
        max_unique=int(args.max_unique_candidates),
    )
    translations, ollama_metrics = build_translations(
        unique_candidates=unique_candidates,
        model=args.model,
        timeout=int(args.timeout),
        batch_size=max(1, int(args.batch_size)),
    )
    chain_by_id, chain_metrics = build_chain_translations(
        candidate_rows=candidate_rows,
        translated_by_src=translations,
        model=args.model,
        timeout=int(args.timeout),
    )

    effective_crc = str(args.rom_crc32 or meta.get("rom_crc32") or pure_jsonl.stem.split("_")[0]).upper()
    effective_rom_size = args.rom_size if args.rom_size is not None else meta.get("rom_size")
    translated_path = out_dir / f"{effective_crc}_translated_fixed_ptbr.jsonl"

    output_metrics = apply_translations(
        pure_jsonl=pure_jsonl,
        out_jsonl=translated_path,
        translated_by_src=translations,
        translated_by_id=chain_by_id,
        fallback_meta={
            "rom_crc32": effective_crc,
            "rom_size": effective_rom_size,
        },
    )

    report_path = out_dir / f"{effective_crc}_translation_stage2_report.txt"
    proof_path = out_dir / f"{effective_crc}_translation_stage2_proof.json"
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rom_crc32": effective_crc,
        "rom_size": effective_rom_size,
        "translation_input": str(pure_jsonl),
        "translation_output": str(translated_path),
        "candidate_scan": scan_stats,
        "ollama": {
            "model": args.model,
            **ollama_metrics,
        },
        "chain": chain_metrics,
        "output": output_metrics,
    }
    write_report_and_proof(report_path=report_path, proof_path=proof_path, payload=payload)

    print(f"[OK] Output: {translated_path}")
    print(
        f"[OK] Changed={output_metrics['text_changed']} "
        f"Unchanged={output_metrics['text_unchanged']} "
        f"BlockedUnmapped={output_metrics.get('blocked_unmapped_glyphs', 0)} "
        f"BlockedTooLong={output_metrics['blocked_too_long']} "
        f"BlockedPlaceholder={output_metrics['blocked_placeholder']}"
    )
    print(f"[OK] Report: {report_path}")
    print(f"[OK] Proof: {proof_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
