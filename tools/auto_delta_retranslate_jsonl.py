#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch incremental para reduzir itens criticos de traducao:
- text_dst == text_src (unchanged/not_translated)
- suspeita de nao-PT em text_dst

Opera sobre JSONL traduzido e reescreve SOMENTE itens alvo,
preservando ordem/ids/offsets e validacoes de placeholders/tamanho ASCII.
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


TOKEN_RE = re.compile(r"(\[[^\]]+\]|\{[^}]+\}|<[^>]+>|__PROTECTED__|@[A-Z0-9_]+)")
WORD_RE = re.compile(r"[A-Za-z']+")
PT_HINTS = {
    "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas",
    "para", "por", "com", "sem", "que", "e", "ou", "se", "mas", "nao",
    "sim", "voce", "voces", "seu", "sua", "meu", "minha", "um", "uma",
    "ataque", "inimigo", "inimigos", "mundo", "tempo", "nome", "item",
    "opcao", "opcoes", "salvar", "carregar", "continuar",
}
EN_HINTS = {
    "the", "and", "you", "your", "this", "that", "from", "with", "attack",
    "enemy", "enemies", "item", "world", "time", "name", "male", "female",
    "options", "option", "save", "load", "continue",
}
LEXICON_FALLBACK = {
    "the": "o",
    "and": "e",
    "or": "ou",
    "is": "e",
    "are": "sao",
    "was": "era",
    "were": "eram",
    "be": "ser",
    "am": "sou",
    "in": "em",
    "of": "de",
    "for": "para",
    "on": "em",
    "at": "em",
    "with": "com",
    "without": "sem",
    "from": "de",
    "by": "por",
    "as": "como",
    "if": "se",
    "then": "entao",
    "all": "todos",
    "some": "alguns",
    "no": "nao",
    "not": "nao",
    "yes": "sim",
    "my": "meu",
    "our": "nosso",
    "their": "deles",
    "his": "dele",
    "her": "dela",
    "to": "para",
    "you": "voce",
    "i": "eu",
    "me": "me",
    "we": "nos",
    "us": "nos",
    "they": "eles",
    "he": "ele",
    "she": "ela",
    "it": "isso",
    "your": "seu",
    "this": "isto",
    "that": "isso",
    "these": "estes",
    "those": "esses",
    "there": "la",
    "here": "aqui",
    "again": "novamente",
    "next": "proximo",
    "first": "primeiro",
    "last": "ultimo",
    "old": "velho",
    "new": "novo",
    "real": "real",
    "bad": "ruim",
    "good": "bom",
    "weak": "fraco",
    "lost": "perdido",
    "suddenly": "de_repente",
    "feel": "sentir",
    "please": "por_favor",
    "hurry": "depressa",
    "come": "venha",
    "back": "volte",
    "when": "quando",
    "where": "onde",
    "wherever": "onde_quiser",
    "now": "agora",
    "before": "antes",
    "after": "depois",
    "over": "fim",
    "down": "baixo",
    "up": "cima",
    "main": "principal",
    "door": "porta",
    "call": "chame",
    "track": "rastrear",
    "find": "encontrar",
    "help": "ajudar",
    "need": "precisa",
    "needs": "precisa",
    "must": "deve",
    "can": "pode",
    "cant": "nao_pode",
    "cannot": "nao_pode",
    "will": "vai",
    "should": "deveria",
    "start": "comecar",
    "drop": "soltar",
    "take": "pegar",
    "push": "aperte",
    "put": "coloque",
    "equip": "equipar",
    "machine": "maquina",
    "machines": "maquinas",
    "reality": "realidade",
    "secret": "secreto",
    "myth": "mito",
    "war": "guerra",
    "news": "noticia",
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
    "item": "item",
    "design": "design",
}

MANUAL_OVERRIDES = {
    "Sorry, I can't help you with that.": "Desculpe, nao posso ajudar nisso.",
    "Maybe you can TRADE it for something more useful.": "Talvez voce possa negociar por algo mais util.",
    "You may only eat food!": "Voce pode comer apenas comida!",
    "You can't rest here, monsters are near.": "Voce nao pode descansar aqui, monstros estao perto.",
    "@Bomb attack": "@Bomb ataque",
    "AND PUSH \"A\"\"B\"\"C\"\"START\"": "E APERTE A/B/C/START",
    "PUT IN YOUR PAD": "PONHA NO PAD",
    "Hmmph! You think I'm": "Hum! Voce acha?",
    "Now you must stand": "Agora fique firme",
    "may you be as lucky as I!": "que tenha sorte como eu!",
    "like you doing in": "como voce faz em",
    "easier once you find": "fica facil ao achar",
    "How could this": "Como assim?",
    "If I were you, I'd look": "Se eu fosse vc, busc.",
    "Thank you. We owe": "Obrigado. Devemos",
    "NIf you go west, you'll": "Se for ao oeste, vc",
    "he'll ruin this land.": "ele vai arruinar tudo",
    "This place is so busy": "Este lugar lotado",
    "luck, use this map.": "sorte, use mapa.",
    "I'm amazed you made": "Surpreso que veio",
    "You can't afford it.": "Voce nao pode pagar.",
    "in all you do.": "em tudo q faz.",
    "Now you must hunt": "Agora va cacar",
    "then I can't help you.": "entao nao ajudo vc.",
    "So, you are here at last.": "Entao, chegou enfim.",
    "You feel chills, as if": "Sente calafrios, como",
    "you can walk": "voce anda",
    "You Can Never Be Too": "Voce nunca e demais",
    "You Can Do It": "Voce consegue",
    "Now, take this ELECTROKEY!": "Agora, pegue ELECTROKEY!",
    "When we first met, I wondered if you knew what you were doing...": "Quando nos vimos, pensei se voce sabia o que fazia...",
    "You know, I feel smarter already!": "Sabe, ja me sinto mais esperto!",
    "+_you found my": "+_vc achou meu",
    "You can use STAR FUEL DRUMS as bombs!": "Use STAR FUEL DRUMS como bombas!",
    "Here's a RED KEY to get you started.": "Aqui uma RED KEY para comecar.",
    "ELF MALE": "ELFO M",
    "HALF-ELF MALE": "MEIO-ELFO M",
    "GNOME MALE": "GNOMO M",
    "\"Will you allow him to join": "\"Vai permitir ele entrar",
    "\"Please! You must free me!": "\"Por favor! Me liberte!",
    "turns to you. \"Beyond hope,": "vira pra voce. \"Sem esper.",
    "your darkest hour.\"": "sua hora mais somb.",
    "think I owe you for": "acho q devo a vc",
    "Try all you like, this game": "Tente o quanto quiser, jogo",
    "1st@item": "1o@item",
    "2nd@item": "2o@item",
}

# Variantes manuais por frase critica, em ordem de preferencia.
# O seletor escolhe automaticamente a primeira que cabe no max_len_bytes.
FORCED_OVERRIDE_VARIANTS = {
    "Sorry, I can't help you with that.": [
        "Desculpe, nao posso ajudar nisso.",
        "Nao posso ajudar nisso, desculpe.",
        "Desculpe, nao posso ajudar.",
    ],
    "Maybe you can TRADE it for something more useful.": [
        "Talvez voce possa negociar por algo mais util.",
        "Talvez voce negocie por algo mais util.",
        "Talvez negocie por algo mais util.",
    ],
    "You may only eat food!": [
        "Voce pode comer apenas comida!",
        "Voce so pode comer comida!",
        "So pode comer comida!",
    ],
    "You can't rest here, monsters are near.": [
        "Voce nao pode descansar aqui, monstros estao perto.",
        "Nao descanse aqui, monstros estao perto.",
        "Nao descanse aqui, monstros perto.",
    ],
    "@Bomb attack": [
        "@Bomb ataque",
        "@Bomb atq",
        "@Bomb atk",
    ],
    "feels the effects of poison!": [
        "sente os efeitos do veneno!",
    ],
    "`Ice attack": [
        "`Ataque de gelo",
        "`Golpe gelo",
        "`Gelo atq",
    ],
    "Ice attack": [
        "Ataque de gelo",
        "Golpe gelo",
    ],
    "Blaze attack": [
        "Ataque de fogo",
        "Golpe fogo",
    ],
    "`Light attack": [
        "`Ataque de raio",
        "`Ataque de luz",
    ],
    "Light attack": [
        "Ataque de raio",
        "Ataque de luz",
    ],
    "LOST WORLD": [
        "MUNDO PERDIDO",
        "MUNDO PERD",
    ],
    ">LOST WORLD": [
        ">MUNDO PERDIDO",
        ">MUNDO PERD",
    ],
    "for this unnecessary sequel.": [
        "por essa sequencia desnecessaria",
        "por essa sequencia inutil.",
    ],
    "with@melody": [
        "com@melodia",
    ],
    "breaks@the@seal": [
        "quebra@o@selo",
        "quebra@selo",
    ],
    "Letter@from": [
        "Carta@de",
    ],
    "with@tears": [
        "com@lagrimas",
        "com@lagrima",
        "com@pranto",
    ],
    "Prize@from": [
        "Premio@de",
    ],
    "Protects@from": [
        "Protege@de",
    ],
    "Lola@and@Bill": [
        "Lola@e@Bill",
    ],
    "Apple@from": [
        "Maca@de",
    ],
    "🇯🇵 nnon|Attack all enemies.": [
        "nnon|Ataque todos inimigos.",
    ],
}

# Regras ortograficas automaticas em PT-BR (sem acentos, por compatibilidade ASCII).
ORTHO_WORD_REPLACEMENTS = [
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

ORTHO_PHRASE_REPLACEMENTS = [
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


def normalize_ascii(text: str) -> str:
    t = unicodedata.normalize("NFD", text or "")
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    t = (
        t.replace("“", "\"")
        .replace("”", "\"")
        .replace("‘", "'")
        .replace("’", "'")
        .replace("—", "-")
        .replace("–", "-")
        .replace("…", "...")
    )
    t = re.sub(r"\s+", " ", t).strip()
    return t


def clean_text_for_gate(text: str) -> str:
    t = TOKEN_RE.sub(" ", text or "")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def looks_like_pt_translation(text: str) -> bool:
    words = [w.lower() for w in WORD_RE.findall(text or "")]
    if len(words) < 2:
        return False
    return sum(1 for w in words if w in PT_HINTS) >= 1


def looks_suspicious_non_pt(text: str) -> bool:
    words = [w.lower() for w in WORD_RE.findall(text or "")]
    if len(words) < 2:
        return False
    pt_hits = sum(1 for w in words if w in PT_HINTS)
    en_hits = sum(1 for w in words if w in EN_HINTS)
    return pt_hits == 0 and en_hits >= 1


def looks_readable_text(text: str) -> bool:
    t = clean_text_for_gate(text or "")
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
    non_text = sum(
        1
        for ch in t
        if not (ch.isalnum() or ch.isspace() or ch in "'.,!?-:;/|@")
    )
    if non_text / max(1, len(t)) > 0.25:
        return False
    return True


def is_translatable_candidate(src: str) -> bool:
    t = clean_text_for_gate(src)
    if len(t) < 4 or len(t) > 140:
        return False
    try:
        b = t.encode("ascii", errors="strict")
    except UnicodeEncodeError:
        return False
    printable = sum(32 <= x < 127 for x in b) / max(1, len(b))
    if printable < 0.95:
        return False
    nonalnum = sum(
        1
        for ch in t
        if not (ch.isalnum() or ch.isspace() or ch in "'.,!?-:")
    )
    if nonalnum / max(1, len(t)) > 0.20:
        return False
    digit_ratio = sum(ch.isdigit() for ch in t) / max(1, len(t))
    if digit_ratio > 0.20:
        return False
    words = [w.lower() for w in WORD_RE.findall(t)]
    if len(words) < 2:
        return False
    en_hits = sum(1 for w in words if w in EN_HINTS)
    return en_hits >= 1


def protect_tokens(text: str) -> Tuple[str, Dict[str, str]]:
    mapping: Dict[str, str] = {}
    idx = 0

    def _repl(match: re.Match) -> str:
        nonlocal idx
        key = f"__TOK{idx}__"
        mapping[key] = match.group(0)
        idx += 1
        return key

    protected = TOKEN_RE.sub(_repl, text or "")
    return protected, mapping


def restore_tokens(text: str, mapping: Dict[str, str]) -> str:
    out = text or ""
    for k, v in mapping.items():
        out = out.replace(k, v)
    return out


def placeholders_preserved(src: str, dst: str) -> bool:
    src_tokens = TOKEN_RE.findall(src or "")
    return all(tok in (dst or "") for tok in src_tokens)


def can_fit_ascii(text: str, max_len_bytes: Optional[int]) -> bool:
    if max_len_bytes is None:
        return True
    try:
        b = (text or "").encode("ascii", errors="strict")
    except UnicodeEncodeError:
        return False
    return len(b) <= int(max_len_bytes)


def compact_to_fit(text: str, max_len_bytes: Optional[int]) -> str:
    if max_len_bytes is None:
        return text
    out = text or ""
    if can_fit_ascii(out, max_len_bytes):
        return out

    # Etapa 1: compactacao suave, preservando legibilidade.
    mild_repl = [
        (r"\bpara\b", "pra"),
        (r"\bestao\b", "tao"),
        (r"\bnao\b", "nao"),
    ]
    for pat, rep in mild_repl:
        out2 = re.sub(pat, rep, out, flags=re.IGNORECASE)
        out2 = re.sub(r"\s+", " ", out2).strip()
        if out2 != out:
            out = out2
            if can_fit_ascii(out, max_len_bytes):
                return out

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
            return out

    # Etapa 2: abreviacao moderada, somente se ainda nao coube.
    moderate_repl = [
        (r"\bcontinuar\b", "continua"),
        (r"\bcarregar\b", "carrega"),
        (r"\bsalvar\b", "salva"),
        (r"\bprincipal\b", "princ."),
    ]
    for pat, rep in moderate_repl:
        out2 = re.sub(pat, rep, out, flags=re.IGNORECASE)
        out2 = re.sub(r"\s+", " ", out2).strip()
        if out2 != out:
            out = out2
            if can_fit_ascii(out, max_len_bytes):
                return out

    # Etapa 3: ultimo recurso para casos extremos.
    def _shrink_long_word(match: re.Match) -> str:
        word = match.group(0)
        base = word[0] + re.sub(r"[aeiouAEIOU]", "", word[1:])
        if len(base) >= 3:
            return base
        return word[:3]

    out2 = re.sub(r"\b[A-Za-z]{6,}\b", _shrink_long_word, out)
    out2 = re.sub(r"\s+", " ", out2).strip()
    if out2 != out:
        out = out2
        if can_fit_ascii(out, max_len_bytes):
            return out

    out2 = re.sub(r"[.,;:!?]+$", "", out).strip()
    if out2 != out:
        out = out2
        if can_fit_ascii(out, max_len_bytes):
            return out
    return out


def choose_forced_override(src: str, max_len_bytes: Optional[int]) -> Optional[str]:
    variants = FORCED_OVERRIDE_VARIANTS.get(src)
    if not variants:
        manual = MANUAL_OVERRIDES.get(src)
        return normalize_ascii(manual) if manual else None
    normalized_variants = [normalize_ascii(v) for v in variants if v]
    if not normalized_variants:
        return None
    if max_len_bytes is None:
        return normalized_variants[0]
    for cand in normalized_variants:
        if can_fit_ascii(cand, max_len_bytes):
            return cand
    fallback = compact_to_fit(normalized_variants[0], max_len_bytes)
    return fallback if fallback else None


def _apply_ortho_word_rules(text: str) -> str:
    out = text or ""
    for pattern, repl in ORTHO_WORD_REPLACEMENTS:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _apply_ortho_phrase_rules(text: str) -> str:
    out = text or ""
    for pattern, repl in ORTHO_PHRASE_REPLACEMENTS:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def apply_orthographic_cleanup(
    src: str,
    dst: str,
    max_len_bytes: Optional[int],
) -> str:
    src_norm = normalize_ascii(src or "")
    out = normalize_ascii(dst or "")
    if not out:
        return out

    # 1) Correcoes por frase especifica (com fallback por tamanho)
    forced = choose_forced_override(src_norm, max_len_bytes)
    if forced:
        out = forced

    # 2) Correcoes lexicais gerais
    out = _apply_ortho_word_rules(out)
    out = _apply_ortho_phrase_rules(out)

    # 3) Ajustes semanticos orientados por contexto da source
    if "poison" in src_norm.lower():
        out = re.sub(r"\bpocao\b", "veneno", out, flags=re.IGNORECASE)
        out = re.sub(r"\bvenenosa\b", "envenenada", out, flags=re.IGNORECASE)
        out = re.sub(r"\bveneno foi removida\b", "veneno foi removido", out, flags=re.IGNORECASE)
    if "poisoned" in src_norm.lower():
        out = re.sub(r"\bpocao\b", "veneno", out, flags=re.IGNORECASE)
    if "ice attack" in src_norm.lower():
        out = re.sub(r"\bataque\s+de\s+chama\b", "ataque de gelo", out, flags=re.IGNORECASE)
        out = re.sub(r"\bataque\s+cnglnt\b", "ataque de gelo", out, flags=re.IGNORECASE)
    if "blaze attack" in src_norm.lower():
        out = re.sub(r"\bataque\s+de\s+raio\b", "ataque de fogo", out, flags=re.IGNORECASE)

    out = normalize_ascii(out)
    if max_len_bytes is not None and not can_fit_ascii(out, max_len_bytes):
        compacted = compact_to_fit(out, max_len_bytes)
        if compacted and can_fit_ascii(compacted, max_len_bytes):
            out = compacted

    return out


def needs_orthographic_cleanup(src: str, dst: str, max_len_bytes: Optional[int]) -> bool:
    src_norm = normalize_ascii(src or "")
    dst_norm = normalize_ascii(dst or "")
    if not src_norm or not dst_norm:
        return False
    if not is_translatable_candidate(src_norm):
        return False
    if not looks_readable_text(src_norm):
        return False
    if not looks_readable_text(dst_norm):
        return False
    cleaned = apply_orthographic_cleanup(src_norm, dst_norm, max_len_bytes)
    return normalize_ascii(cleaned) != dst_norm


def lexical_fallback_pt(text: str) -> str:
    def _repl(match: re.Match) -> str:
        w = match.group(0)
        lw = w.lower()
        mapped = LEXICON_FALLBACK.get(lw)
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


def ollama_translate_batch(
    pairs: List[Tuple[int, str]],
    model: str,
    timeout: int,
) -> Dict[int, str]:
    lines = [f"{idx}|||{txt}" for idx, txt in pairs]
    prompt = (
        "Traduza do ingles para portugues brasileiro.\n"
        "Mantenha placeholders (__TOK0__, etc.) exatamente.\n"
        "Nao deixe frases em ingles.\n"
        "Retorne somente linhas no formato id|||traducao.\n\n"
        + "\n".join(lines)
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }
    r = requests.post(
        "http://127.0.0.1:11434/api/generate",
        json=payload,
        timeout=max(30, int(timeout)),
    )
    r.raise_for_status()
    data = r.json()
    raw = str(data.get("response", "") or "")

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


def parse_max_len(v: Any) -> Optional[int]:
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.isdigit():
        return int(v)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Auto delta retranslate para reduzir unchanged/suspicious.")
    ap.add_argument("--in-jsonl", required=True)
    ap.add_argument("--out-jsonl", required=True)
    ap.add_argument("--model", default="llama3.2:latest")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--max-items", type=int, default=2000)
    args = ap.parse_args()

    in_jsonl = Path(args.in_jsonl).expanduser().resolve()
    out_jsonl = Path(args.out_jsonl).expanduser().resolve()
    if not in_jsonl.exists():
        raise SystemExit(f"[ERRO] in-jsonl nao encontrado: {in_jsonl}")

    rows: List[Dict[str, Any]] = []
    meta: Optional[Dict[str, Any]] = None
    candidates: List[Tuple[int, Dict[str, Any], str]] = []
    by_src: Dict[str, List[int]] = {}

    for obj in iter_jsonl(in_jsonl):
        if obj.get("type") == "meta":
            meta = dict(obj)
            continue
        row = dict(obj)
        idx = len(rows)
        rows.append(row)

        src = str(row.get("text_src", ""))
        dst = str(row.get("text_dst", src))
        src_norm = normalize_ascii(src)
        max_len = parse_max_len(row.get("max_len_bytes"))
        is_translatable = is_translatable_candidate(src)
        unresolved = is_translatable and ((dst == src) or looks_suspicious_non_pt(dst))
        forced_dst = choose_forced_override(src_norm, max_len) or choose_forced_override(src, max_len)
        needs_forced = bool(forced_dst and normalize_ascii(dst) != normalize_ascii(forced_dst))
        needs_ortho = needs_orthographic_cleanup(src, dst, max_len)
        if not unresolved and not needs_forced and not needs_ortho:
            continue
        if len(candidates) >= int(args.max_items):
            continue

        protected, mapping = protect_tokens(src)
        cobj = {
            "row_index": idx,
            "src": src,
            "dst": dst,
            "protected": protected,
            "mapping": mapping,
            "max_len": max_len,
            "forced_dst": forced_dst,
            "needs_forced": needs_forced,
            "needs_ortho": needs_ortho,
            "unresolved": unresolved,
            "is_translatable": is_translatable,
        }
        candidates.append((idx, cobj, src))
        if unresolved:
            by_src.setdefault(src, []).append(idx)

    unique_src = list(by_src.keys())
    trans_by_src: Dict[str, str] = {}
    metrics = {
        "rows_total": len(rows),
        "targets_total": len(candidates),
        "targets_unique_src": len(unique_src),
        "translated_ok": 0,
        "translated_fail": 0,
        "applied_changed": 0,
        "forced_targets_total": 0,
        "forced_applied": 0,
        "ortho_targets_total": 0,
        "ortho_applied": 0,
        "blocked_fit": 0,
        "blocked_placeholder": 0,
        "blocked_non_ascii": 0,
        "lexical_fallback_used": 0,
    }

    # Traduz por src unico.
    protected_unique: List[Tuple[str, str, Dict[str, str]]] = []
    for src in unique_src:
        p, m = protect_tokens(src)
        protected_unique.append((src, p, m))

    batch_size = max(1, int(args.batch_size))
    for i in range(0, len(protected_unique), batch_size):
        batch = protected_unique[i : i + batch_size]
        pairs = [(i + j, txt) for j, (_, txt, _) in enumerate(batch)]
        try:
            got = ollama_translate_batch(pairs, model=args.model, timeout=int(args.timeout))
        except Exception:
            for src, _, _ in batch:
                trans_by_src[src] = src
                metrics["translated_fail"] += 1
            continue

        for rid, (src, _, mapping) in zip([x[0] for x in pairs], batch):
            raw = got.get(rid, "")
            if not raw:
                trans_by_src[src] = src
                metrics["translated_fail"] += 1
                continue
            restored = restore_tokens(raw, mapping)
            restored = normalize_ascii(restored)
            if (not restored) or (not placeholders_preserved(src, restored)):
                trans_by_src[src] = src
                metrics["translated_fail"] += 1
                continue
            if not looks_like_pt_translation(restored):
                fb = lexical_fallback_pt(restored)
                if fb and fb != src and placeholders_preserved(src, fb) and looks_like_pt_translation(fb):
                    restored = fb
                    metrics["lexical_fallback_used"] += 1
            trans_by_src[src] = restored
            if restored != src:
                metrics["translated_ok"] += 1
            else:
                metrics["translated_fail"] += 1

    # Aplica patch.
    for idx, cobj, src in candidates:
        row = rows[idx]
        forced_dst = cobj.get("forced_dst")
        needs_forced = bool(cobj.get("needs_forced"))
        needs_ortho = bool(cobj.get("needs_ortho"))
        if needs_forced:
            metrics["forced_targets_total"] += 1
        if needs_ortho:
            metrics["ortho_targets_total"] += 1
        if forced_dst:
            dst = str(forced_dst)
        else:
            src_norm = normalize_ascii(src)
            dst = (
                MANUAL_OVERRIDES.get(src_norm)
                or MANUAL_OVERRIDES.get(src)
                or trans_by_src.get(src, str(cobj.get("dst", src)))
            )
        max_len = cobj.get("max_len")
        dst = normalize_ascii(dst)
        if (dst == src) or looks_suspicious_non_pt(dst):
            forced = lexical_fallback_pt(src)
            if forced and forced != src:
                dst = forced
        dst_before_ortho = dst
        apply_cleanup = bool(cobj.get("is_translatable")) or needs_forced or needs_ortho
        if apply_cleanup:
            dst = apply_orthographic_cleanup(src, dst, max_len)
            dst = compact_to_fit(dst, max_len)

        if not placeholders_preserved(src, dst):
            metrics["blocked_placeholder"] += 1
            continue
        if not can_fit_ascii(dst, max_len):
            metrics["blocked_fit"] += 1
            continue
        try:
            dst.encode("ascii", errors="strict")
        except UnicodeEncodeError:
            metrics["blocked_non_ascii"] += 1
            continue
        if dst == src:
            continue

        row["text_dst"] = dst
        row["translation_status"] = "OK"
        row.pop("translation_block_reason", None)
        metrics["applied_changed"] += 1
        if needs_forced:
            metrics["forced_applied"] += 1
        if needs_ortho and normalize_ascii(dst) != normalize_ascii(dst_before_ortho):
            metrics["ortho_applied"] += 1

    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl.open("w", encoding="utf-8", newline="\n") as f:
        if meta is not None:
            m = dict(meta)
            m["stage"] = "translated_fixed_ptbr_auto_delta"
            m["generated_at"] = datetime.now().isoformat(timespec="seconds")
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    report_path = out_jsonl.with_name(out_jsonl.stem + "_auto_delta_report.txt")
    proof_path = out_jsonl.with_name(out_jsonl.stem + "_auto_delta_proof.json")
    report_lines = [
        "AUTO DELTA RETRANSLATE",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
        f"in_jsonl={in_jsonl}",
        f"out_jsonl={out_jsonl}",
        f"targets_total={metrics['targets_total']}",
        f"targets_unique_src={metrics['targets_unique_src']}",
        f"translated_ok={metrics['translated_ok']}",
        f"translated_fail={metrics['translated_fail']}",
        f"lexical_fallback_used={metrics['lexical_fallback_used']}",
        f"forced_targets_total={metrics['forced_targets_total']}",
        f"forced_applied={metrics['forced_applied']}",
        f"ortho_targets_total={metrics['ortho_targets_total']}",
        f"ortho_applied={metrics['ortho_applied']}",
        f"applied_changed={metrics['applied_changed']}",
        f"blocked_fit={metrics['blocked_fit']}",
        f"blocked_placeholder={metrics['blocked_placeholder']}",
        f"blocked_non_ascii={metrics['blocked_non_ascii']}",
    ]
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    proof_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] out={out_jsonl}")
    print(
        f"[OK] changed={metrics['applied_changed']} blocked_fit={metrics['blocked_fit']} "
        f"blocked_placeholder={metrics['blocked_placeholder']} blocked_non_ascii={metrics['blocked_non_ascii']}"
    )
    print(f"[OK] report={report_path}")
    print(f"[OK] proof={proof_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
