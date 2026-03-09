# -*- coding: utf-8 -*-
"""
QA Gate + Runtime Coverage para pipeline de ROMs.

Regras:
- Sem scan cego de ROM.
- Baseado apenas em pure/translated/mapping/report/proof/runtime evidence.
- Identidade neutra por CRC32/rom_size.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .semantic_quality_gate import SemanticQualityGate
except Exception:
    try:
        from semantic_quality_gate import SemanticQualityGate
    except Exception:
        SemanticQualityGate = None

try:
    from .quality_profile_manager import normalize_register_policy, resolve_quality_profile
except Exception:
    try:
        from quality_profile_manager import normalize_register_policy, resolve_quality_profile
    except Exception:
        normalize_register_policy = None
        resolve_quality_profile = None


POINTER_FIELDS = (
    "pointer_refs",
    "pointer_offsets",
    "pointer_tables",
    "pointer_table",
    "pointers",
    "pointer",
    "ptrs",
    "ptr",
)

TEXT_DST_FIELDS = ("text_dst", "translation", "translated_text", "translated", "text")
TEXT_SRC_FIELDS = ("text_src", "text", "source_text", "original_text")

PLACEHOLDER_TOKEN_RE = re.compile(
    r"(<TILE:[0-9A-Fa-f]{2}>|<[0-9A-Fa-f]{2}>|%\d*[dsxX]|\{[A-Za-z0-9_:-]+\}|\[[A-Za-z0-9_:-]+\]|@[A-Za-z0-9_]+)"
)
WORD_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ0-9_.-]+")
SEMANTIC_LEXICON_PTBR = {
    "a": "um",
    "an": "um",
    "again": "novamente",
    "aid": "ajuda",
    "all": "todos",
    "already": "já",
    "also": "também",
    "and": "e",
    "any": "qualquer",
    "are": "são",
    "art": "és",
    "as": "como",
    "at": "em",
    "avatar": "Avatar",
    "be": "ser",
    "before": "antes",
    "best": "melhor",
    "blood": "sangue",
    "book": "livro",
    "but": "mas",
    "by": "por",
    "can": "pode",
    "cannot": "não pode",
    "close": "fechar",
    "command": "comando",
    "compassion": "Compaixão",
    "continue": "continuar",
    "courage": "Coragem",
    "dark": "escuro",
    "day": "dia",
    "de": "de",
    "do": "fazer",
    "door": "porta",
    "east": "leste",
    "enough": "suficiente",
    "enemy": "inimigo",
    "enemies": "inimigos",
    "exit": "sair",
    "female": "feminino",
    "find": "encontre",
    "for": "para",
    "from": "de",
    "game": "jogo",
    "give": "dar",
    "gold": "ouro",
    "good": "bom",
    "have": "ter",
    "has": "tem",
    "had": "tinha",
    "he": "ele",
    "hello": "olá",
    "help": "ajudar",
    "here": "aqui",
    "honesty": "Honestidade",
    "honor": "Honra",
    "how": "como",
    "humility": "Humildade",
    "i": "eu",
    "in": "em",
    "interest": "interesse",
    "into": "em",
    "is": "é",
    "item": "item",
    "items": "itens",
    "justice": "Justiça",
    "key": "chave",
    "kill": "matar",
    "killed": "abatido",
    "lead": "liderar",
    "load": "carregar",
    "locate": "localizar",
    "love": "Amor",
    "magic": "magia",
    "male": "masculino",
    "map": "mapa",
    "menu": "menu",
    "must": "deve",
    "name": "nome",
    "new": "novo",
    "no": "não",
    "north": "norte",
    "not": "não",
    "nothing": "nada",
    "of": "de",
    "on": "em",
    "only": "somente",
    "open": "abrir",
    "option": "opção",
    "options": "opções",
    "or": "ou",
    "other": "outro",
    "our": "nosso",
    "part": "parte",
    "path": "caminho",
    "player": "jogador",
    "position": "posição",
    "press": "pressione",
    "quest": "jornada",
    "reagents": "reagentes",
    "sacrifice": "Sacrifício",
    "save": "salvar",
    "seek": "buscar",
    "seems": "parece",
    "shall": "irá",
    "ship": "nau",
    "sleep": "sono",
    "slow": "lento",
    "some": "alguns",
    "south": "sul",
    "spell": "magia",
    "spirit": "espírito",
    "start": "iniciar",
    "stone": "pedra",
    "stones": "pedras",
    "strength": "força",
    "sword": "espada",
    "that": "isso",
    "the": "o",
    "thee": "te",
    "there": "lá",
    "they": "eles",
    "this": "isto",
    "thou": "tu",
    "thy": "teu",
    "to": "para",
    "travel": "viajar",
    "tu": "tu",
    "use": "usar",
    "valor": "Valor",
    "version": "versão",
    "virtue": "virtude",
    "was": "era",
    "were": "eram",
    "west": "oeste",
    "what": "o que",
    "who": "quem",
    "with": "com",
    "wizard": "mago",
    "world": "mundo",
    "yes": "sim",
    "you": "você",
    "your": "seu",
    "welcome": "bem-vindo",
    "where": "onde",
    "the": "o",
    "and": "e",
    "or": "ou",
    "you": "você",
    "your": "seu",
    "with": "com",
    "for": "para",
    "from": "de",
    "to": "para",
    "of": "de",
    "in": "em",
    "on": "em",
    "at": "em",
    "is": "é",
    "are": "são",
    "was": "era",
    "were": "eram",
    "be": "ser",
    "have": "ter",
    "has": "tem",
    "had": "tinha",
    "open": "abrir",
    "close": "fechar",
    "door": "porta",
    "start": "iniciar",
    "continue": "continuar",
    "save": "salvar",
    "load": "carregar",
    "attack": "ataque",
    "magic": "magia",
    "item": "item",
    "items": "itens",
    "enemy": "inimigo",
    "enemies": "inimigos",
    "world": "mundo",
    "name": "nome",
    "male": "masculino",
    "female": "feminino",
    "press": "pressione",
    "menu": "menu",
    "game": "jogo",
    "options": "opções",
    "option": "opção",
    "yes": "sim",
    "no": "não",
    "hello": "olá",
    "bye": "tchau",
    "welcome": "bem-vindo",
}
COMMON_NON_PROPER_TITLE_WORDS = {
    "Aim",
    "All",
    "Any",
    "Armour",
    "Attack",
    "Attacked",
    "Book",
    "But",
    "Candle",
    "Command",
    "Combat",
    "Dead",
    "Direction",
    "Disabled",
    "Dungeon",
    "East",
    "Energy",
    "Exit",
    "Female",
    "Find",
    "Flame",
    "Good",
    "Green",
    "Here",
    "How",
    "Interest",
    "Item",
    "Items",
    "Key",
    "Killed",
    "Level",
    "Load",
    "Locate",
    "Magic",
    "Male",
    "Mandrake",
    "Map",
    "Menu",
    "Name",
    "New",
    "North",
    "Not",
    "Only",
    "Open",
    "Orange",
    "Options",
    "Phase",
    "Player",
    "Poisoned",
    "Press",
    "Purple",
    "Ready",
    "Reagents",
    "Room",
    "Runes",
    "Save",
    "See",
    "Sleep",
    "Slow",
    "South",
    "Spell",
    "Start",
    "Stone",
    "Stones",
    "Sword",
    "Thank",
    "Torch",
    "Torches",
    "Travel",
    "Use",
    "Weapon",
    "West",
    "Wheel",
    "Who",
    "Wrong",
}
REGISTER_ENFORCE_PATTERNS = {
    "voce": [
        (re.compile(r"\btu\b", flags=re.IGNORECASE), "você"),
        (re.compile(r"\bteu\b", flags=re.IGNORECASE), "seu"),
        (re.compile(r"\btua\b", flags=re.IGNORECASE), "sua"),
        (re.compile(r"\bte\b", flags=re.IGNORECASE), "você"),
        (re.compile(r"\bcontigo\b", flags=re.IGNORECASE), "com você"),
        (re.compile(r"\best[aá]s\b", flags=re.IGNORECASE), "está"),
        (re.compile(r"\btens\b", flags=re.IGNORECASE), "tem"),
        (re.compile(r"\bés\b", flags=re.IGNORECASE), "é"),
        (re.compile(r"\bpodes\b", flags=re.IGNORECASE), "pode"),
        (re.compile(r"\bfoste\b", flags=re.IGNORECASE), "foi"),
        (re.compile(r"\bvais\b", flags=re.IGNORECASE), "vai"),
        (re.compile(r"\bcê\b", flags=re.IGNORECASE), "você"),
        (re.compile(r"\bce\b", flags=re.IGNORECASE), "você"),
        (re.compile(r"\b([A-Za-zÀ-ÿ]+)-te\b", flags=re.IGNORECASE), r"\1 você"),
    ],
    "tu": [
        (re.compile(r"\bvocê\b", flags=re.IGNORECASE), "tu"),
        (re.compile(r"\bvoce\b", flags=re.IGNORECASE), "tu"),
        (re.compile(r"\bcê\b", flags=re.IGNORECASE), "tu"),
        (re.compile(r"\bce\b", flags=re.IGNORECASE), "tu"),
    ],
    "ce": [
        (re.compile(r"\bvocê\b", flags=re.IGNORECASE), "cê"),
        (re.compile(r"\bvoce\b", flags=re.IGNORECASE), "cê"),
        (re.compile(r"\btu\b", flags=re.IGNORECASE), "cê"),
    ],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, "") or "").strip().lower()
    if not raw:
        return bool(default)
    return raw not in {"0", "false", "off", "no", "n"}


def _env_int(name: str, default: int, minimum: int = 1, maximum: int = 99) -> int:
    raw = str(os.environ.get(name, "") or "").strip()
    if not raw:
        return int(default)
    try:
        value = int(raw)
    except ValueError:
        return int(default)
    return max(int(minimum), min(int(maximum), int(value)))


def _parse_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        raw = value.strip().lower()
        if not raw:
            return None
        try:
            if raw.startswith(("-0x", "+0x")):
                sign = -1 if raw.startswith("-") else 1
                return sign * int(raw[3:], 16)
            if raw.startswith("0x"):
                return int(raw, 16)
            return int(raw, 10)
        except ValueError:
            return None
    return None


def _format_offset(value: Any) -> Optional[str]:
    parsed = _parse_int(value)
    if parsed is None or parsed < 0:
        return None
    return f"0x{int(parsed):06X}"


def _is_meta_row(obj: Dict[str, Any]) -> bool:
    if not isinstance(obj, dict):
        return False
    rec_type = str(obj.get("type", obj.get("record_type", ""))).strip().lower()
    if rec_type == "meta" or bool(obj.get("meta")):
        return True
    has_identity = ("rom_crc32" in obj) or ("rom_size" in obj)
    has_text = any(k in obj for k in ("text_src", "text_dst", "translated", "translation", "text"))
    return bool(has_identity and not has_text)


def _row_key(row: Dict[str, Any], idx: int = 0) -> str:
    if row.get("id") is not None:
        return str(row.get("id"))
    if row.get("key") is not None:
        return str(row.get("key"))
    return f"idx_{int(idx):08d}"


def _row_offset_int(row: Dict[str, Any]) -> Optional[int]:
    return _parse_int(row.get("rom_offset", row.get("offset")))


def _uid(row: Dict[str, Any], idx: int = 0) -> str:
    key = _row_key(row, idx=idx)
    off = _format_offset(row.get("rom_offset", row.get("offset"))) or "None"
    return f"{key}|{off}"


def _text_value(row: Dict[str, Any], fields: Tuple[str, ...]) -> str:
    for fld in fields:
        val = row.get(fld)
        if isinstance(val, str):
            return val
    return ""


def _normalize_runtime_snippet(text: str) -> str:
    if not isinstance(text, str):
        return ""
    # Normaliza para comparação estável por evidência runtime.
    out = text.replace("\r", " ").replace("\n", " ").replace("\t", " ").strip().lower()
    out = re.sub(r"\s+", " ", out)
    return out


def _canon_text(text: str) -> str:
    raw = str(text or "")
    normalized = unicodedata.normalize("NFD", raw)
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    lowered = stripped.casefold()
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def _is_probable_proper_noun(word: str) -> bool:
    token = str(word or "").strip()
    if not token:
        return False
    if token in COMMON_NON_PROPER_TITLE_WORDS:
        return False
    if "." in token or "_" in token:
        return True
    if token.isupper():
        return False
    if any(ch.isdigit() for ch in token[1:]):
        return True
    if any(ch.isupper() for ch in token[1:]):
        return True
    if len(token) <= 2:
        return False
    return bool(token[0].isupper() and "-" in token)


def _preserve_placeholders(src: str, dst: str) -> str:
    src_tokens = PLACEHOLDER_TOKEN_RE.findall(str(src or ""))
    if not src_tokens:
        return str(dst or "")
    out = str(dst or "").strip()
    for tok in src_tokens:
        if tok not in out:
            out = (out + " " + tok).strip() if out else tok
    return out


def _translate_source_conservative(source: str, register_policy: str) -> str:
    src = str(source or "")
    if not src.strip():
        return ""

    chunks: List[str] = []
    last = 0
    for match in PLACEHOLDER_TOKEN_RE.finditer(src):
        if match.start() > last:
            chunks.append(src[last:match.start()])
        chunks.append(match.group(0))
        last = match.end()
    if last < len(src):
        chunks.append(src[last:])

    out_parts: List[str] = []
    for part in chunks:
        if PLACEHOLDER_TOKEN_RE.fullmatch(part):
            out_parts.append(part)
            continue

        text = part
        words = WORD_TOKEN_RE.findall(text)
        for word in words:
            prefix_match = re.match(r"^[^A-Za-zÀ-ÿ0-9]*", word)
            suffix_match = re.search(r"[^A-Za-zÀ-ÿ0-9]*$", word)
            prefix = prefix_match.group(0) if prefix_match else ""
            suffix = suffix_match.group(0) if suffix_match else ""
            core_start = len(prefix)
            core_end = len(word) - len(suffix)
            core = word[core_start:core_end] if core_end > core_start else word
            if not core:
                continue
            low = core.casefold()
            replacement = None
            if core.isdigit():
                replacement = core
            elif core.isupper() and len(core) <= 4:
                ui_map = {"HP": "PV", "MP": "PM", "LV": "NV", "ATK": "ATQ", "DEF": "DEF"}
                replacement = ui_map.get(core, core)
            elif _is_probable_proper_noun(core):
                replacement = core
            else:
                replacement = SEMANTIC_LEXICON_PTBR.get(low)
            if replacement:
                final_word = f"{prefix}{replacement}{suffix}"
                token_re = re.compile(
                    rf"(?<![A-Za-zÀ-ÿ0-9_]){re.escape(word)}(?![A-Za-zÀ-ÿ0-9_])"
                )
                text = token_re.sub(final_word, text, count=1)
        out_parts.append(text)

    out = "".join(out_parts)
    out = re.sub(r"\s+", " ", out).strip()
    if register_policy in REGISTER_ENFORCE_PATTERNS:
        for pattern, repl in REGISTER_ENFORCE_PATTERNS.get(register_policy, []):
            out = pattern.sub(repl, out)
    return out


def _apply_glossary_and_names(
    source: str,
    translated: str,
    gate: Optional[Any],
) -> str:
    out = str(translated or "")
    if gate is None:
        return out
    try:
        ev = gate.evaluate(source_text=source, translated_text=out, context={})
    except Exception:
        return out

    for violation in list(ev.get("glossary_violations", []) or []):
        token = str(violation)
        if "->" not in token:
            continue
        src_term, expected = token.split("->", 1)
        src_term = str(src_term).strip()
        expected = str(expected).strip()
        if not expected:
            continue
        if _canon_text(expected) in _canon_text(out):
            continue
        if src_term and src_term in out:
            out = out.replace(src_term, expected)
        else:
            out = (out + " " + expected).strip() if out else expected

    hits = [str(x) for x in list(ev.get("proper_noun_hits", []) or []) if str(x).strip()]
    preserved = set(str(x) for x in list(ev.get("proper_noun_preserved", []) or []) if str(x).strip())
    for name in hits:
        rule = {}
        try:
            rule = dict((getattr(gate, "glossary", {}) or {}).get(name, {}) or {})
        except Exception:
            rule = {}
        preserve = bool(rule.get("preserve", True))
        allow_translation = bool(rule.get("allow_translation", not preserve))
        target = str(rule.get("target", name) or name).strip() or name
        expected = name if preserve and not allow_translation else target

        if _canon_text(expected) in _canon_text(out):
            continue
        if name in preserved:
            continue

        if name in out:
            out = out.replace(name, expected)
            continue
        out = (expected + " " + out).strip() if out else expected

    return out


def _build_translation_memory(
    pure_uid_map: Dict[str, Dict[str, Any]],
    trans_rows: List[Dict[str, Any]],
    gate: Optional[Any],
) -> Tuple[Dict[str, str], List[Tuple[str, str]]]:
    exact: Dict[str, str] = {}

    for idx, row in enumerate(trans_rows):
        uid = _uid(row, idx=idx)
        p_row = pure_uid_map.get(uid, {})
        src = _text_value(p_row, TEXT_SRC_FIELDS) or _text_value(row, TEXT_SRC_FIELDS)
        dst = _text_value(row, TEXT_DST_FIELDS)
        if not src or not dst:
            continue
        src_key = _canon_text(src)
        if not src_key:
            continue
        if src_key == _canon_text(dst):
            continue
        if gate is not None:
            try:
                ev = gate.evaluate(source_text=src, translated_text=dst, context={})
                if bool(ev.get("blocked", False)) or bool(ev.get("english_residue", False)):
                    continue
            except Exception:
                continue
        candidate = str(dst).strip()
        if not candidate:
            continue
        prev = exact.get(src_key)
        if not prev or len(candidate) < len(prev):
            exact[src_key] = candidate

    ranked: List[Tuple[str, str]] = sorted(exact.items(), key=lambda kv: len(kv[0]), reverse=True)
    return exact, ranked


def _lookup_translation_memory(
    source: str,
    tm_exact: Dict[str, str],
    tm_ranked: List[Tuple[str, str]],
) -> str:
    src_key = _canon_text(source)
    if not src_key:
        return ""
    if src_key in tm_exact:
        return str(tm_exact.get(src_key, "") or "")

    # Heurística para fragmentos com 1-2 bytes perdidos no início/fim.
    for trim in (1, 2):
        if len(src_key) <= (4 + trim):
            continue
        left = src_key[trim:]
        right = src_key[:-trim]
        if left in tm_exact:
            return str(tm_exact.get(left, "") or "")
        if right in tm_exact:
            return str(tm_exact.get(right, "") or "")

    # Heurística conservadora por sobreposição textual.
    for key, value in tm_ranked:
        if not key or not value:
            continue
        if len(key) < 12 or len(src_key) < 8:
            continue
        if src_key in key and (len(key) - len(src_key)) <= 10:
            return value
        if key in src_key and (len(src_key) - len(key)) <= 10:
            return value
    return ""


def _semantic_autofix_candidate(
    source: str,
    translated: str,
    gate: Optional[Any],
    register_policy: str,
    tm_exact: Optional[Dict[str, str]] = None,
    tm_ranked: Optional[List[Tuple[str, str]]] = None,
) -> str:
    src = str(source or "")
    dst = str(translated or "").strip()
    if not src.strip():
        return dst

    src_canon = _canon_text(src)
    dst_canon = _canon_text(dst)
    needs_from_source = not dst or (src_canon and src_canon == dst_canon)

    if not needs_from_source and gate is not None:
        try:
            ev = gate.evaluate(source_text=src, translated_text=dst, context={})
            needs_from_source = bool(
                ev.get("english_residue", False)
                or ev.get("semantic_drift", False)
                or ev.get("semantic_hallucination_suspect", False)
                or ev.get("overtranslation_suspect", False)
                or ev.get("undertranslation_suspect", False)
            )
        except Exception:
            needs_from_source = False

    if needs_from_source:
        tm_value = _lookup_translation_memory(
            src,
            tm_exact if isinstance(tm_exact, dict) else {},
            tm_ranked if isinstance(tm_ranked, list) else [],
        )
        if tm_value:
            dst = tm_value
        else:
            dst = _translate_source_conservative(src, register_policy=register_policy)
    else:
        if register_policy in REGISTER_ENFORCE_PATTERNS:
            for pattern, repl in REGISTER_ENFORCE_PATTERNS.get(register_policy, []):
                dst = pattern.sub(repl, dst)

    dst = _preserve_placeholders(src, dst)
    dst = _apply_glossary_and_names(source=src, translated=dst, gate=gate)
    dst = re.sub(r"\s+", " ", dst).strip()

    # Último fallback conservador: tradução por fonte para remover resíduo EN.
    if gate is not None:
        try:
            ev2 = gate.evaluate(source_text=src, translated_text=dst, context={})
            if bool(ev2.get("english_residue", False)):
                tm_value = _lookup_translation_memory(
                    src,
                    tm_exact if isinstance(tm_exact, dict) else {},
                    tm_ranked if isinstance(tm_ranked, list) else [],
                )
                if tm_value:
                    dst = tm_value
                else:
                    dst = _translate_source_conservative(src, register_policy=register_policy)
                dst = _preserve_placeholders(src, dst)
                dst = _apply_glossary_and_names(source=src, translated=dst, gate=gate)
                dst = re.sub(r"\s+", " ", dst).strip()
        except Exception:
            pass
    return dst


def _write_jsonl(path: str, metas: List[Dict[str, Any]], rows: List[Dict[str, Any]]) -> bool:
    if not path:
        return False
    out = Path(path)
    lines: List[str] = []
    for meta in metas:
        if isinstance(meta, dict):
            lines.append(json.dumps(meta, ensure_ascii=False))
    for row in rows:
        if isinstance(row, dict):
            lines.append(json.dumps(row, ensure_ascii=False))
    try:
        out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    except Exception:
        return False
    return True


def _load_jsonl(path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    metas: List[Dict[str, Any]] = []
    rows: List[Dict[str, Any]] = []
    if not path or not os.path.isfile(path):
        return metas, rows
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                if _is_meta_row(obj):
                    metas.append(obj)
                else:
                    rows.append(obj)
    except Exception:
        return [], []
    return metas, rows


def _load_json(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {}
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}


def _extract_counters_from_artifacts(
    report_json_path: Optional[str],
    proof_json_path: Optional[str],
) -> Dict[str, int]:
    report = _load_json(report_json_path)
    proof = _load_json(proof_json_path)

    report_stats = report.get("stats", {}) if isinstance(report, dict) else {}
    proof_stats = proof.get("stats", {}) if isinstance(proof, dict) else {}
    report_ui = report.get("ui_metrics", {}) if isinstance(report, dict) else {}
    proof_evidence = proof.get("evidence", {}) if isinstance(proof, dict) else {}
    proof_issue = proof.get("issue_index", {}) if isinstance(proof, dict) else {}
    report_issue = report.get("issue_index", {}) if isinstance(report, dict) else {}

    blocked = max(
        int(report_stats.get("BLOCKED", 0) or 0),
        int(proof_stats.get("BLOCKED", 0) or 0),
    )
    ui_blocked = max(
        int(report_ui.get("UI_ITEMS_BLOCKED", 0) or 0),
        int(proof.get("UI_ITEMS_BLOCKED", 0) or 0),
    )
    terminator_missing = max(
        int(((report_issue.get("counts", {}) or {}).get("terminator_missing", 0) or 0)),
        int(((proof_issue.get("counts", {}) or {}).get("terminator_missing", 0) or 0)),
        int(proof_evidence.get("terminator_missing_count", 0) or 0),
    )
    return {
        "blocked": int(blocked),
        "ui_items_blocked": int(ui_blocked),
        "terminator_missing_count": int(terminator_missing),
    }


def _extract_coverage_from_artifacts(
    report_json_path: Optional[str],
    proof_json_path: Optional[str],
) -> Dict[str, Any]:
    report = _load_json(report_json_path)
    proof = _load_json(proof_json_path)

    coverage_incomplete: Optional[bool] = None
    global_coverage_percent: Optional[float] = None

    for payload in (proof, report):
        if not isinstance(payload, dict) or not payload:
            continue
        if coverage_incomplete is None and "coverage_incomplete" in payload:
            coverage_incomplete = bool(payload.get("coverage_incomplete", True))
        if global_coverage_percent is None and payload.get("global_coverage_percent") is not None:
            try:
                global_coverage_percent = float(payload.get("global_coverage_percent"))
            except (TypeError, ValueError):
                global_coverage_percent = None

    return {
        "found": bool(coverage_incomplete is not None),
        "coverage_incomplete": bool(coverage_incomplete) if coverage_incomplete is not None else None,
        "global_coverage_percent": float(global_coverage_percent)
        if global_coverage_percent is not None
        else None,
    }


def _terminator_byte(value: Any) -> Optional[int]:
    parsed = _parse_int(value)
    if parsed is None:
        return None
    if parsed < 0:
        return None
    return int(parsed) & 0xFF


def _looks_like_hex_token(token: str) -> bool:
    tok = token.strip().lower()
    if tok.startswith("0x"):
        tok = tok[2:]
    return bool(tok and re.fullmatch(r"[0-9a-f]+", tok))


def _load_tbl_charset(tbl_path: Optional[str]) -> set:
    allowed = set()
    if not tbl_path or not os.path.isfile(tbl_path):
        return allowed
    try:
        with open(tbl_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                if raw.startswith(("#", ";", "//")):
                    continue
                if "=" not in raw:
                    continue
                left, right = raw.split("=", 1)
                left = left.strip()
                right = right.strip()
                if not left or not right:
                    continue

                left_hex = _looks_like_hex_token(left)
                right_hex = _looks_like_hex_token(right)
                if left_hex and not right_hex:
                    text_side = right
                elif right_hex and not left_hex:
                    text_side = left
                else:
                    text_side = right if not right_hex else left
                if not text_side:
                    continue
                for ch in text_side:
                    allowed.add(ch)
    except Exception:
        return set()
    return allowed


def _normalize_with_charset(text: str, charset: set) -> Tuple[str, int]:
    if not text:
        return "", 0
    normalized = unicodedata.normalize("NFC", text)
    if not charset:
        return normalized, 0

    out_chars: List[str] = []
    changes = 0
    for ch in normalized:
        if ch in charset or ch in {"\n", "\r", "\t"} or ord(ch) < 128:
            out_chars.append(ch)
            continue
        base = "".join(
            c for c in unicodedata.normalize("NFD", ch) if unicodedata.category(c) != "Mn"
        )
        candidate = base[0] if base else "?"
        if candidate in charset or ord(candidate) < 128:
            out_chars.append(candidate)
        else:
            out_chars.append("?")
        changes += 1
    return "".join(out_chars), int(changes)


def _row_sort_key(row: Dict[str, Any], idx: int) -> Tuple[int, str, int]:
    off = _row_offset_int(row)
    off_key = int(off) if off is not None else 0x7FFFFFFF
    return (off_key, _row_key(row, idx=idx), int(idx))


def _extract_rom_identity(
    pure_meta: List[Dict[str, Any]],
    pure_rows: List[Dict[str, Any]],
    trans_meta: List[Dict[str, Any]],
    trans_rows: List[Dict[str, Any]],
) -> Tuple[Optional[str], Optional[int]]:
    crc = None
    size = None
    for pool in (trans_meta, pure_meta, trans_rows[:1], pure_rows[:1]):
        for obj in pool:
            if not isinstance(obj, dict):
                continue
            if not crc and obj.get("rom_crc32"):
                cand = str(obj.get("rom_crc32")).strip().upper()
                if re.fullmatch(r"[0-9A-F]{8}", cand):
                    crc = cand
            if size is None and obj.get("rom_size") is not None:
                size_val = _parse_int(obj.get("rom_size"))
                if size_val is not None and size_val > 0:
                    size = int(size_val)
            if crc and size is not None:
                return crc, size
    return crc, size


def _normalize_register_policy_local(value: Any, default: str = "voce") -> str:
    if callable(normalize_register_policy):
        try:
            return str(normalize_register_policy(value, default=default))
        except Exception:
            pass
    raw = str(value or "").strip().lower()
    if raw in {"você", "voce", "vc"}:
        return "voce"
    if raw in {"tu"}:
        return "tu"
    if raw in {"cê", "ce"}:
        return "ce"
    return str(default)


def _normalize_console_hint_local(value: Any) -> Optional[str]:
    raw = str(value or "").strip().upper()
    if not raw:
        return None
    normalized = raw.replace("-", "_")
    aliases = {
        "MASTER SYSTEM": "SMS",
        "MASTER_SYSTEM": "SMS",
        "GAME GEAR": "SMS",
        "GAME_GEAR": "SMS",
        "GG": "SMS",
        "PLAYSTATION": "PS1",
        "PSX": "PS1",
        "GENESIS": "MD",
        "MEGA DRIVE": "MD",
        "MEGA_DRIVE": "MD",
        "SFC": "SNES",
        "SUPER NES": "SNES",
        "SUPER_NES": "SNES",
        "NINTENDO 64": "N64",
        "NINTENDO_64": "N64",
        "GAME BOY ADVANCE": "GBA",
        "GAME_BOY_ADVANCE": "GBA",
    }
    if normalized in aliases:
        return aliases[normalized]
    return normalized if normalized in {"NES", "SMS", "MD", "SNES", "PS1", "N64", "GBA"} else None


def _detect_console_hint(
    pure_meta: List[Dict[str, Any]],
    pure_rows: List[Dict[str, Any]],
    trans_meta: List[Dict[str, Any]],
    trans_rows: List[Dict[str, Any]],
    hint_paths: Optional[List[str]] = None,
) -> Optional[str]:
    for pool in (trans_meta, pure_meta, trans_rows[:1], pure_rows[:1]):
        for obj in pool:
            if not isinstance(obj, dict):
                continue
            for key in ("console", "platform", "console_hint"):
                cand = _normalize_console_hint_local(obj.get(key))
                if cand:
                    return cand
    for hint in (hint_paths or []):
        low = str(hint or "").lower()
        if not low:
            continue
        if "master system" in low or "\\sms\\" in low or "/sms/" in low:
            return "SMS"
        if "\\nes\\" in low or "/nes/" in low:
            return "NES"
        if "\\snes\\" in low or "/snes/" in low:
            return "SNES"
        if "\\ps1\\" in low or "/ps1/" in low or "playstation" in low:
            return "PS1"
        if "\\n64\\" in low or "/n64/" in low or "nintendo 64" in low:
            return "N64"
        if "\\gba\\" in low or "/gba/" in low or "game boy advance" in low:
            return "GBA"
        if "mega drive" in low or "\\md\\" in low or "/md/" in low or "genesis" in low:
            return "MD"
    return None


def _resolve_semantic_quality_context(
    rom_crc32: Optional[str],
    pure_meta: Optional[List[Dict[str, Any]]] = None,
    pure_rows: Optional[List[Dict[str, Any]]] = None,
    trans_meta: Optional[List[Dict[str, Any]]] = None,
    trans_rows: Optional[List[Dict[str, Any]]] = None,
    hint_paths: Optional[List[str]] = None,
) -> Dict[str, Any]:
    pure_meta = pure_meta or []
    pure_rows = pure_rows or []
    trans_meta = trans_meta or []
    trans_rows = trans_rows or []
    paths = [str(p) for p in (hint_paths or []) if p]
    console_hint = _detect_console_hint(
        pure_meta=pure_meta,
        pure_rows=pure_rows,
        trans_meta=trans_meta,
        trans_rows=trans_rows,
        hint_paths=paths,
    )

    extraction_stub: Dict[str, Any] = {}
    for pool in (trans_meta, pure_meta):
        for obj in pool:
            if not isinstance(obj, dict):
                continue
            for key in ("quality_family", "game_family", "family", "series"):
                if obj.get(key):
                    extraction_stub[key] = obj.get(key)
            if isinstance(obj.get("quality_profile"), dict):
                extraction_stub["quality_profile"] = obj.get("quality_profile")
            if isinstance(obj.get("semantic_policy"), dict):
                extraction_stub["semantic_policy"] = obj.get("semantic_policy")

    bundle: Dict[str, Any] = {"profile": {}, "meta": {}}
    if callable(resolve_quality_profile):
        try:
            bundle = resolve_quality_profile(
                console=console_hint,
                rom_crc32=rom_crc32,
                extraction_data=extraction_stub if extraction_stub else None,
                search_hint_paths=paths,
            )
        except Exception:
            bundle = {"profile": {}, "meta": {}}

    profile = dict(bundle.get("profile", {}) or {})
    meta = dict(bundle.get("meta", {}) or {})
    semantic_cfg = profile.get("semantic", {}) if isinstance(profile.get("semantic"), dict) else {}

    env_register_raw = str(os.environ.get("NEUROROM_REGISTER_POLICY", "") or "").strip()
    if env_register_raw:
        register_policy = _normalize_register_policy_local(env_register_raw, default="voce")
    else:
        register_policy = _normalize_register_policy_local(
            profile.get("register_policy", "voce"),
            default="voce",
        )

    env_sem_strict_raw = str(os.environ.get("NEUROROM_SEMANTIC_GATE_STRICT", "") or "").strip()
    if env_sem_strict_raw:
        semantic_strict = _env_bool("NEUROROM_SEMANTIC_GATE_STRICT", True)
    else:
        strict_candidate = semantic_cfg.get("strict_mode")
        semantic_strict = bool(strict_candidate) if isinstance(strict_candidate, bool) else True

    glossary: Dict[str, Any] = {}
    if isinstance(profile.get("glossary"), dict):
        glossary.update(profile.get("glossary", {}))
    if isinstance(semantic_cfg.get("glossary"), dict):
        glossary.update(semantic_cfg.get("glossary", {}))

    env_autofix_raw = str(os.environ.get("NEUROROM_SEMANTIC_AUTOFIX_MAX", "") or "").strip()
    if env_autofix_raw:
        autofix_rounds = _env_int("NEUROROM_SEMANTIC_AUTOFIX_MAX", 8, minimum=1, maximum=50)
    else:
        autofix_rounds = int(_parse_int(semantic_cfg.get("autofix_max_rounds")) or 8)
        autofix_rounds = max(1, min(50, autofix_rounds))

    try:
        min_std = float(semantic_cfg.get("min_semantic_score_standard", 70.0) or 70.0)
    except Exception:
        min_std = 70.0
    try:
        min_strict = float(semantic_cfg.get("min_semantic_score_strict", 82.0) or 82.0)
    except Exception:
        min_strict = 82.0

    return {
        "profile": profile,
        "meta": meta,
        "console_hint": console_hint,
        "register_policy": register_policy,
        "semantic_strict": bool(semantic_strict),
        "semantic_glossary": glossary,
        "semantic_min_score_standard": float(min_std),
        "semantic_min_score_strict": float(min_strict),
        "semantic_autofix_max_rounds": int(autofix_rounds),
    }


def run_qa_gate(
    pure_jsonl_path: str,
    translated_jsonl_path: str,
    mapping_json_path: Optional[str] = None,
    report_json_path: Optional[str] = None,
    proof_json_path: Optional[str] = None,
    tbl_path: Optional[str] = None,
    stage: str = "post_translation",
    reported_counters: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """
    Executa QA_GATE sem scan cego.

    Critérios:
    - pure vs translated por UID=(key, offset)
    - offset obrigatório
    - preservação de metadados de ponteiro em itens UI
    - ordenação por offset/key
    - terminador preservado e proibido no corpo
    - counters críticos (BLOCKED/UI_ITEMS_BLOCKED/terminator_missing_count) em zero
    - opcional: charset por TBL
    """
    pure_meta, pure_rows = _load_jsonl(pure_jsonl_path)
    trans_meta, trans_rows = _load_jsonl(translated_jsonl_path)

    rom_crc32, rom_size = _extract_rom_identity(pure_meta, pure_rows, trans_meta, trans_rows)

    pure_map: Dict[str, Dict[str, Any]] = {}
    trans_map: Dict[str, Dict[str, Any]] = {}
    pure_order: List[str] = []
    trans_order: List[str] = []

    for idx, row in enumerate(pure_rows):
        uid = _uid(row, idx=idx)
        if uid not in pure_map:
            pure_map[uid] = row
            pure_order.append(uid)

    for idx, row in enumerate(trans_rows):
        uid = _uid(row, idx=idx)
        if uid not in trans_map:
            trans_map[uid] = row
            trans_order.append(uid)

    missing_uids = [uid for uid in pure_order if uid not in trans_map]
    extra_uids = [uid for uid in trans_order if uid not in pure_map]

    offset_none_examples: List[Dict[str, Any]] = []
    pointer_invalid_examples: List[Dict[str, Any]] = []
    terminator_missing_examples: List[Dict[str, Any]] = []
    terminator_body_examples: List[Dict[str, Any]] = []

    offset_none_total = 0
    pointer_invalid_total = 0
    terminator_missing_total = 0
    terminator_body_total = 0

    for idx, row in enumerate(trans_rows):
        off = _row_offset_int(row)
        if off is None:
            offset_none_total += 1
            if len(offset_none_examples) < 20:
                offset_none_examples.append(
                    {"uid": _uid(row, idx=idx), "key": _row_key(row, idx=idx), "offset": row.get("offset")}
                )

    for idx, uid in enumerate(pure_order):
        p_row = pure_map.get(uid, {})
        t_row = trans_map.get(uid)
        if not isinstance(t_row, dict):
            continue
        is_ui_pointer = bool(p_row.get("ui_item", False) or p_row.get("has_pointer", False))
        if is_ui_pointer:
            t_off = _row_offset_int(t_row)
            p_off = _row_offset_int(p_row)
            mismatch = False
            reason = []
            if t_off is None:
                mismatch = True
                reason.append("OFFSET_NONE")
            elif p_off is not None and int(t_off) != int(p_off):
                mismatch = True
                reason.append("OFFSET_CHANGED")

            p_has_pointer_data = any(bool(p_row.get(fld)) for fld in POINTER_FIELDS)
            t_has_pointer_data = any(bool(t_row.get(fld)) for fld in POINTER_FIELDS)
            if p_has_pointer_data and not t_has_pointer_data:
                mismatch = True
                reason.append("POINTER_META_DROPPED")

            if bool(p_row.get("ui_item", False)) and not bool(t_row.get("ui_item", False)):
                mismatch = True
                reason.append("UI_FLAG_DROPPED")
            if bool(p_row.get("has_pointer", False)) and not bool(t_row.get("has_pointer", False)):
                mismatch = True
                reason.append("HAS_POINTER_DROPPED")

            if mismatch:
                pointer_invalid_total += 1
                if len(pointer_invalid_examples) < 20:
                    pointer_invalid_examples.append(
                        {
                            "uid": uid,
                            "key": _row_key(p_row, idx=idx),
                            "offset": _format_offset(p_off),
                            "reason": ",".join(reason),
                        }
                    )

        p_term = p_row.get("terminator")
        if p_term is None:
            continue
        t_term = t_row.get("terminator")
        if t_term is None:
            terminator_missing_total += 1
            if len(terminator_missing_examples) < 20:
                terminator_missing_examples.append(
                    {"uid": uid, "key": _row_key(p_row, idx=idx), "reason": "TERMINATOR_MISSING"}
                )
        else:
            p_term_b = _terminator_byte(p_term)
            t_term_b = _terminator_byte(t_term)
            if p_term_b is not None and t_term_b is not None and p_term_b != t_term_b:
                terminator_missing_total += 1
                if len(terminator_missing_examples) < 20:
                    terminator_missing_examples.append(
                        {
                            "uid": uid,
                            "key": _row_key(p_row, idx=idx),
                            "reason": f"TERMINATOR_CHANGED:{p_term_b}->{t_term_b}",
                        }
                    )

        term_byte = _terminator_byte(p_term)
        if term_byte is None:
            continue
        body = _text_value(t_row, TEXT_DST_FIELDS)
        if not body:
            continue
        # Skip if original source already contained the terminator char
        src_body = _text_value(p_row, ("text_src", "text"))
        hit = False
        if term_byte == 0 and "\x00" in body:
            if not (src_body and "\x00" in src_body):
                hit = True
        elif 32 <= term_byte <= 126 and chr(term_byte) in body:
            if not (src_body and chr(term_byte) in src_body):
                hit = True
        if hit:
            terminator_body_total += 1
            if len(terminator_body_examples) < 20:
                terminator_body_examples.append(
                    {"uid": uid, "key": _row_key(p_row, idx=idx), "terminator": term_byte}
                )

    sorted_trans_uids = [
        _uid(row, idx=idx)
        for idx, row in sorted(
            enumerate(trans_rows),
            key=lambda pair: _row_sort_key(pair[1], pair[0]),
        )
    ]
    ordering_pass = bool(trans_order == sorted_trans_uids)

    counters = {}
    if isinstance(reported_counters, dict):
        counters = {
            "blocked": int(reported_counters.get("blocked", 0) or 0),
            "ui_items_blocked": int(reported_counters.get("ui_items_blocked", 0) or 0),
            "terminator_missing_count": int(
                reported_counters.get("terminator_missing_count", 0) or 0
            ),
        }
    else:
        counters = _extract_counters_from_artifacts(report_json_path, proof_json_path)

    untranslated_total = 0
    untranslated_examples: List[Dict[str, Any]] = []
    for idx, row in enumerate(trans_rows):
        dst = _text_value(row, TEXT_DST_FIELDS)
        if str(dst or "").strip():
            continue
        untranslated_total += 1
        if len(untranslated_examples) < 20:
            untranslated_examples.append(
                {
                    "uid": _uid(row, idx=idx),
                    "key": _row_key(row, idx=idx),
                    "offset": _format_offset(_row_offset_int(row)),
                }
            )

    coverage_info = _extract_coverage_from_artifacts(report_json_path, proof_json_path)
    coverage_signal_from_artifacts = bool(coverage_info.get("found", False))
    if coverage_signal_from_artifacts:
        coverage_incomplete = bool(coverage_info.get("coverage_incomplete", True))
    else:
        coverage_incomplete = bool(
            int(len(missing_uids)) > 0
            or int(len(extra_uids)) > 0
            or int(untranslated_total) > 0
        )
    raw_global_coverage = coverage_info.get("global_coverage_percent")
    if raw_global_coverage is None:
        total_base = max(1, int(len(pure_rows)))
        covered = max(0, int(len(pure_rows)) - int(len(missing_uids)) - int(untranslated_total))
        raw_global_coverage = (float(covered) / float(total_base)) * 100.0
    global_coverage_percent = float(round(float(raw_global_coverage), 4))

    charset_policy = str(os.environ.get("NEUROROM_CHARSET_POLICY", "strict") or "strict").strip().lower()
    if charset_policy not in {"normalize", "strict"}:
        charset_policy = "strict"

    allowed_chars = _load_tbl_charset(tbl_path)
    missing_charset_chars: List[str] = []
    if allowed_chars:
        missing = set()
        for row in trans_rows:
            dst = _text_value(row, TEXT_DST_FIELDS)
            for ch in dst:
                if ch in {"\n", "\r", "\t", " "}:
                    continue
                if ch in allowed_chars:
                    continue
                if ord(ch) < 128:
                    continue
                missing.add(ch)
        missing_charset_chars = sorted(missing)

    quality_ctx = _resolve_semantic_quality_context(
        rom_crc32=rom_crc32,
        pure_meta=pure_meta,
        pure_rows=pure_rows,
        trans_meta=trans_meta,
        trans_rows=trans_rows,
        hint_paths=[
            pure_jsonl_path,
            translated_jsonl_path,
            mapping_json_path,
            report_json_path,
            proof_json_path,
            tbl_path,
        ],
    )
    semantic_enabled = _env_bool("NEUROROM_SEMANTIC_GATE_ENABLE", True)
    semantic_register_policy = str(quality_ctx.get("register_policy", "voce") or "voce").strip().lower()
    semantic_strict = bool(quality_ctx.get("semantic_strict", True))
    semantic_glossary = dict(quality_ctx.get("semantic_glossary", {}) or {})
    semantic_min_score_standard = float(quality_ctx.get("semantic_min_score_standard", 70.0) or 70.0)
    semantic_min_score_strict = float(quality_ctx.get("semantic_min_score_strict", 82.0) or 82.0)
    semantic_gate_ready = bool(semantic_enabled and SemanticQualityGate is not None)
    semantic_blocked_total = 0
    semantic_english_residue_total = 0
    semantic_glossary_violations_total = 0
    semantic_proper_noun_corruption_total = 0
    semantic_register_inconsistency_total = 0
    semantic_drift_total = 0
    semantic_score_sum = 0.0
    semantic_score_count = 0
    semantic_blocked_examples: List[Dict[str, Any]] = []

    if semantic_gate_ready:
        sem_gate = SemanticQualityGate(
            glossary=semantic_glossary,
            register_policy=semantic_register_policy,
            strict_mode=bool(semantic_strict),
            min_semantic_score_standard=semantic_min_score_standard,
            min_semantic_score_strict=semantic_min_score_strict,
        )
        for idx, uid in enumerate(pure_order):
            p_row = pure_map.get(uid, {})
            t_row = trans_map.get(uid)
            if not isinstance(t_row, dict):
                continue
            src = _text_value(p_row, TEXT_SRC_FIELDS)
            dst = _text_value(t_row, TEXT_DST_FIELDS)
            if not src and not dst:
                continue
            sem_eval = sem_gate.evaluate(
                source_text=src,
                translated_text=dst,
                context={
                    "context_low_confidence": bool(p_row.get("context_low_confidence", False)),
                    "segment_integrity_score": int(_parse_int(p_row.get("segment_integrity_score")) or 100),
                },
            )
            semantic_score_sum += float(sem_eval.get("semantic_score", 0.0) or 0.0)
            semantic_score_count += 1
            if bool(sem_eval.get("english_residue", False)):
                semantic_english_residue_total += 1
            if bool(sem_eval.get("glossary_violation", False)):
                semantic_glossary_violations_total += 1
            if bool(sem_eval.get("proper_noun_corruption", False)):
                semantic_proper_noun_corruption_total += 1
            if bool(sem_eval.get("register_inconsistency", False)):
                semantic_register_inconsistency_total += 1
            if bool(sem_eval.get("semantic_drift", False)):
                semantic_drift_total += 1
            if bool(sem_eval.get("blocked", False)):
                semantic_blocked_total += 1
                if len(semantic_blocked_examples) < 20:
                    semantic_blocked_examples.append(
                        {
                            "uid": uid,
                            "key": _row_key(p_row, idx=idx),
                            "offset": _format_offset(_row_offset_int(p_row)),
                            "semantic_score": float(sem_eval.get("semantic_score", 0.0) or 0.0),
                            "semantic_threshold_used": float(sem_eval.get("semantic_threshold_used", 0.0) or 0.0),
                            "absolute_block_reasons": list(sem_eval.get("absolute_block_reasons", []) or []),
                            "glossary_violations": list(sem_eval.get("glossary_violations", []) or []),
                        }
                    )

    checks = {
        "count_match": int(len(trans_rows)) == int(len(pure_rows)),
        "missing_zero": int(len(missing_uids)) == 0,
        "extra_zero": int(len(extra_uids)) == 0,
        "offset_not_none": int(offset_none_total) == 0,
        "pointer_meta_preserved": int(pointer_invalid_total) == 0,
        "ordering_consistent": bool(ordering_pass),
        "terminator_valid": int(terminator_missing_total) == 0 and int(terminator_body_total) == 0,
        "blocked_zero": int(counters.get("blocked", 0)) == 0,
        "ui_items_blocked_zero": int(counters.get("ui_items_blocked", 0)) == 0,
        "report_terminator_zero": int(counters.get("terminator_missing_count", 0)) == 0,
        "coverage_incomplete_false": bool(not coverage_incomplete),
    }
    if semantic_enabled:
        checks["semantic_gate_available"] = bool(semantic_gate_ready)
        checks["semantic_gate_pass"] = bool(semantic_gate_ready and semantic_blocked_total == 0)
        checks["semantic_english_residue_zero"] = bool(
            semantic_gate_ready and semantic_english_residue_total == 0
        )
    if allowed_chars:
        if charset_policy == "strict":
            checks["charset_encodable"] = len(missing_charset_chars) == 0
        else:
            checks["charset_encodable"] = True

    failed_checks = [name for name, ok in checks.items() if not bool(ok)]
    qa_pass = len(failed_checks) == 0

    return {
        "schema": "neurorom.qa_gate.v1",
        "stage": str(stage),
        "timestamp_utc": _now_iso(),
        "pass": bool(qa_pass),
        "failed_checks": failed_checks,
        "rom_crc32": rom_crc32,
        "rom_size": rom_size,
        "inputs": {
            "pure_jsonl": str(pure_jsonl_path or ""),
            "translated_jsonl": str(translated_jsonl_path or ""),
            "mapping_json": str(mapping_json_path or ""),
            "report_json": str(report_json_path or ""),
            "proof_json": str(proof_json_path or ""),
            "tbl_path": str(tbl_path or ""),
            "charset_policy": charset_policy,
            "semantic_gate_enabled": bool(semantic_enabled),
            "semantic_gate_ready": bool(semantic_gate_ready),
            "semantic_register_policy": semantic_register_policy,
            "semantic_strict": bool(semantic_strict),
            "semantic_glossary_terms": int(len(semantic_glossary)),
            "quality_profile_console": quality_ctx.get("console_hint"),
            "quality_profile_sources": list(
                (quality_ctx.get("meta", {}) or {}).get("applied_sources", [])
            ),
            "coverage_signal_from_artifacts": bool(coverage_signal_from_artifacts),
        },
        "metrics": {
            "pure_count": int(len(pure_rows)),
            "translated_count": int(len(trans_rows)),
            "missing_count": int(len(missing_uids)),
            "extra_count": int(len(extra_uids)),
            "untranslated_count": int(untranslated_total),
            "offset_none_count": int(offset_none_total),
            "pointer_invalid_count": int(pointer_invalid_total),
            "terminator_missing_count": int(terminator_missing_total),
            "terminator_in_body_count": int(terminator_body_total),
            "blocked_count": int(counters.get("blocked", 0)),
            "ui_items_blocked": int(counters.get("ui_items_blocked", 0)),
            "report_terminator_missing_count": int(counters.get("terminator_missing_count", 0)),
            "coverage_incomplete": bool(coverage_incomplete),
            "global_coverage_percent": float(global_coverage_percent),
            "charset_missing_chars_count": int(len(missing_charset_chars)),
            "semantic_blocked_count": int(semantic_blocked_total),
            "semantic_english_residue_count": int(semantic_english_residue_total),
            "semantic_glossary_violations_count": int(semantic_glossary_violations_total),
            "semantic_proper_noun_corruption_count": int(semantic_proper_noun_corruption_total),
            "semantic_register_inconsistency_count": int(semantic_register_inconsistency_total),
            "semantic_drift_count": int(semantic_drift_total),
            "semantic_avg_score": float(
                round((semantic_score_sum / float(max(1, semantic_score_count))), 4)
                if semantic_score_count > 0
                else 0.0
            ),
        },
        "checks": checks,
        "examples": {
            "missing_uids": missing_uids[:20],
            "extra_uids": extra_uids[:20],
            "untranslated_uids": untranslated_examples[:20],
            "offset_none": offset_none_examples[:20],
            "pointer_invalid": pointer_invalid_examples[:20],
            "terminator_missing": terminator_missing_examples[:20],
            "terminator_in_body": terminator_body_examples[:20],
            "charset_missing_chars": missing_charset_chars[:120],
            "semantic_blocked": semantic_blocked_examples[:20],
        },
    }


def repair_translated_jsonl(
    pure_jsonl_path: str,
    translated_jsonl_path: str,
    tbl_path: Optional[str] = None,
    charset_policy: str = "normalize",
) -> Dict[str, Any]:
    """
    Regenera translated.jsonl 1:1 com base no pure, preservando metadados críticos.
    """
    pure_meta, pure_rows = _load_jsonl(pure_jsonl_path)
    trans_meta, trans_rows = _load_jsonl(translated_jsonl_path)
    if not pure_rows or not translated_jsonl_path:
        return {
            "pass": False,
            "written": False,
            "changed": False,
            "reason": "PURE_NOT_FOUND_OR_EMPTY",
        }

    policy = str(charset_policy or "normalize").strip().lower()
    if policy not in {"normalize", "strict"}:
        policy = "normalize"
    allowed_chars = _load_tbl_charset(tbl_path)

    trans_map: Dict[str, Dict[str, Any]] = {}
    for idx, row in enumerate(trans_rows):
        uid = _uid(row, idx=idx)
        if uid not in trans_map:
            trans_map[uid] = row

    merged_rows: List[Dict[str, Any]] = []
    changed_rows = 0
    normalized_chars = 0

    keep_from_trans = {
        "translation_status",
        "translation_block_reason",
        "needs_review",
        "review_flags",
        "review_status",
        "review_autounblock_candidate",
        "review_promotion_kind",
        "charset_fallback_chars",
        "layout_fingerprint",
        "alignment_mode",
        "engine",
        "source_engine",
        "ui_item",
        "has_pointer",
    }

    for idx, p_row in enumerate(pure_rows):
        uid = _uid(p_row, idx=idx)
        t_row = trans_map.get(uid, {})

        out = dict(p_row)
        if isinstance(t_row, dict):
            for fld in keep_from_trans:
                if fld in t_row:
                    out[fld] = t_row.get(fld)

        src = _text_value(p_row, TEXT_SRC_FIELDS)
        dst = ""
        if isinstance(t_row, dict):
            dst = _text_value(t_row, TEXT_DST_FIELDS)
        if not isinstance(dst, str) or not dst.strip():
            dst = src

        if policy == "normalize":
            dst_norm, changed = _normalize_with_charset(dst, allowed_chars)
            dst = dst_norm
            normalized_chars += int(changed)

        out["text_src"] = src
        out["text_dst"] = dst
        out["translated_text"] = dst

        off_int = _row_offset_int(p_row)
        if off_int is None and isinstance(t_row, dict):
            off_int = _row_offset_int(t_row)
        if off_int is not None:
            off_hex = f"0x{int(off_int):06X}"
            out["offset"] = off_hex
            out["rom_offset"] = off_hex

        if p_row.get("terminator") is not None:
            out["terminator"] = p_row.get("terminator")

        # Preserva metadados de ponteiro de UI
        if bool(p_row.get("ui_item", False)):
            out["ui_item"] = True
        if bool(p_row.get("has_pointer", False)):
            out["has_pointer"] = True
        for fld in POINTER_FIELDS:
            if p_row.get(fld) is not None and not out.get(fld):
                out[fld] = p_row.get(fld)

        if out != p_row:
            changed_rows += 1
        merged_rows.append(out)

    merged_rows = [
        row
        for idx, row in sorted(
            enumerate(merged_rows),
            key=lambda pair: _row_sort_key(pair[1], pair[0]),
        )
    ]
    for idx, row in enumerate(merged_rows):
        row["seq"] = int(idx)
        off = _row_offset_int(row)
        if off is not None:
            off_hex = f"0x{int(off):06X}"
            row["offset"] = off_hex
            row["rom_offset"] = off_hex

    meta_out: Dict[str, Any] = {}
    if trans_meta:
        meta_out = dict(trans_meta[0])
    elif pure_meta:
        meta_out = dict(pure_meta[0])
    meta_out["type"] = "meta"
    meta_out["schema"] = "neurorom.translated_jsonl.v2"
    meta_out["ordering"] = "rom_offset/key"
    meta_out["items_total"] = int(len(merged_rows))
    if not meta_out.get("rom_crc32"):
        meta_out["rom_crc32"] = (
            (pure_meta[0].get("rom_crc32") if pure_meta else None)
            or (trans_meta[0].get("rom_crc32") if trans_meta else None)
        )
    if not meta_out.get("rom_size"):
        meta_out["rom_size"] = (
            (pure_meta[0].get("rom_size") if pure_meta else None)
            or (trans_meta[0].get("rom_size") if trans_meta else None)
        )
    meta_out["qa_gate_autofix"] = True
    meta_out["qa_gate_autofix_at"] = _now_iso()

    out_path = Path(translated_jsonl_path)
    before = ""
    try:
        before = out_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        before = ""

    lines = [json.dumps(meta_out, ensure_ascii=False)]
    for row in merged_rows:
        lines.append(json.dumps(row, ensure_ascii=False))
    after = "\n".join(lines) + "\n"

    try:
        out_path.write_text(after, encoding="utf-8", newline="\n")
    except Exception as exc:
        return {
            "pass": False,
            "written": False,
            "changed": False,
            "reason": f"WRITE_ERROR: {exc}",
        }

    return {
        "pass": True,
        "written": True,
        "changed": bool(before != after),
        "rows_total": int(len(merged_rows)),
        "rows_changed": int(changed_rows),
        "charset_normalized_chars": int(normalized_chars),
        "output_path": str(out_path),
    }


def repair_translated_jsonl_semantic(
    pure_jsonl_path: str,
    translated_jsonl_path: str,
    qa_gate: Optional[Dict[str, Any]] = None,
    register_policy: Optional[str] = None,
    semantic_strict: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Repara semanticamente translated.jsonl usando fonte + regras conservadoras.
    """
    pure_meta, pure_rows = _load_jsonl(pure_jsonl_path)
    trans_meta, trans_rows = _load_jsonl(translated_jsonl_path)
    if not pure_rows or not trans_rows or not translated_jsonl_path:
        return {
            "pass": False,
            "written": False,
            "changed": False,
            "reason": "PURE_OR_TRANSLATED_EMPTY",
        }

    rom_crc32, _ = _extract_rom_identity(pure_meta, pure_rows, trans_meta, trans_rows)
    quality_ctx = _resolve_semantic_quality_context(
        rom_crc32=rom_crc32,
        pure_meta=pure_meta,
        pure_rows=pure_rows,
        trans_meta=trans_meta,
        trans_rows=trans_rows,
        hint_paths=[pure_jsonl_path, translated_jsonl_path],
    )
    policy = _normalize_register_policy_local(
        register_policy if register_policy is not None else quality_ctx.get("register_policy", "voce"),
        default="voce",
    )
    strict_flag = bool(
        semantic_strict if semantic_strict is not None else quality_ctx.get("semantic_strict", True)
    )
    semantic_glossary = dict(quality_ctx.get("semantic_glossary", {}) or {})
    semantic_min_score_standard = float(quality_ctx.get("semantic_min_score_standard", 70.0) or 70.0)
    semantic_min_score_strict = float(quality_ctx.get("semantic_min_score_strict", 82.0) or 82.0)
    gate = None
    if SemanticQualityGate is not None:
        try:
            gate = SemanticQualityGate(
                glossary=semantic_glossary,
                register_policy=policy,
                strict_mode=bool(strict_flag),
                min_semantic_score_standard=semantic_min_score_standard,
                min_semantic_score_strict=semantic_min_score_strict,
            )
        except Exception:
            gate = None

    pure_uid_map: Dict[str, Dict[str, Any]] = {}
    trans_uid_idx: Dict[str, int] = {}
    for idx, row in enumerate(pure_rows):
        pure_uid_map[_uid(row, idx=idx)] = row
    for idx, row in enumerate(trans_rows):
        trans_uid_idx[_uid(row, idx=idx)] = idx

    tm_exact: Dict[str, str] = {}
    tm_ranked: List[Tuple[str, str]] = []
    if gate is not None:
        tm_exact, tm_ranked = _build_translation_memory(pure_uid_map, trans_rows, gate)

    target_uids: List[str] = []
    target_uid_set = set()
    if isinstance(qa_gate, dict):
        for obj in list((qa_gate.get("examples", {}) or {}).get("semantic_blocked", []) or []):
            if not isinstance(obj, dict):
                continue
            uid = str(obj.get("uid", "") or "").strip()
            if uid and uid in trans_uid_idx and uid not in target_uid_set:
                target_uid_set.add(uid)
                target_uids.append(uid)

    # Varredura completa: o QA exibe amostra de exemplos, mas o reparo precisa
    # atuar em todos os segmentos bloqueados e/ou com resíduo em inglês.
    for idx, row in enumerate(trans_rows):
        uid = _uid(row, idx=idx)
        p_row = pure_uid_map.get(uid, {})
        src = _text_value(p_row, TEXT_SRC_FIELDS)
        dst = _text_value(row, TEXT_DST_FIELDS)
        if not src and not dst:
            continue
        needs_fix = False
        if gate is not None:
            try:
                ev = gate.evaluate(source_text=src, translated_text=dst, context={})
                needs_fix = bool(
                    ev.get("blocked", False)
                    or ev.get("english_residue", False)
                    or ev.get("register_inconsistency", False)
                    or ev.get("semantic_drift", False)
                )
            except Exception:
                needs_fix = False
        else:
            needs_fix = bool(not dst.strip() or _canon_text(src) == _canon_text(dst))

        if needs_fix and uid not in target_uid_set:
            target_uid_set.add(uid)
            target_uids.append(uid)

    changed_rows = 0
    touched_uids: List[str] = []
    for uid in target_uids:
        idx = trans_uid_idx.get(uid)
        p_row = pure_uid_map.get(uid, {})
        if idx is None or not isinstance(p_row, dict):
            continue

        row = dict(trans_rows[idx])
        src = _text_value(p_row, TEXT_SRC_FIELDS)
        if not src:
            src = _text_value(row, TEXT_SRC_FIELDS)
        dst_old = _text_value(row, TEXT_DST_FIELDS)
        ev_old = {}
        if gate is not None:
            try:
                ev_old = gate.evaluate(source_text=src, translated_text=dst_old, context={})
            except Exception:
                ev_old = {}
        dst_new = _semantic_autofix_candidate(
            source=src,
            translated=dst_old,
            gate=gate,
            register_policy=policy,
            tm_exact=tm_exact,
            tm_ranked=tm_ranked,
        )
        if not isinstance(dst_new, str) or not dst_new.strip():
            continue
        if str(dst_new).strip() == str(dst_old).strip():
            continue

        # Evita degradar o segmento: só aceita edição com melhoria semântica.
        if gate is not None:
            try:
                ev_new = gate.evaluate(source_text=src, translated_text=dst_new, context={})
            except Exception:
                ev_new = {}
            if ev_old and ev_new:
                old_score = float(ev_old.get("semantic_score", 0.0) or 0.0)
                new_score = float(ev_new.get("semantic_score", 0.0) or 0.0)
                improved = bool(
                    (not bool(ev_new.get("blocked", False)) and bool(ev_old.get("blocked", False)))
                    or (bool(ev_old.get("english_residue", False)) and not bool(ev_new.get("english_residue", False)))
                    or (new_score >= old_score + 0.5)
                )
                if not improved:
                    continue

        # Atualiza campos de tradução mantendo compatibilidade.
        if isinstance(row.get("text_dst"), str) or "text_dst" in row:
            row["text_dst"] = dst_new
        else:
            row["text_dst"] = dst_new
        if isinstance(row.get("translated_text"), str) or "translated_text" in row:
            row["translated_text"] = dst_new
        if isinstance(row.get("translation"), str) or "translation" in row:
            row["translation"] = dst_new
        if isinstance(row.get("translated"), str) or "translated" in row:
            row["translated"] = dst_new
        row["semantic_autofix_applied"] = True
        row["semantic_autofix_at"] = _now_iso()
        trans_rows[idx] = row
        changed_rows += 1
        touched_uids.append(uid)

    if changed_rows == 0:
        return {
            "pass": True,
            "written": False,
            "changed": False,
            "rows_total": int(len(trans_rows)),
            "rows_changed": 0,
            "touched_uids": [],
            "register_policy": policy,
        }

    meta_out: Dict[str, Any] = {}
    if trans_meta:
        meta_out = dict(trans_meta[0])
    elif pure_meta:
        meta_out = dict(pure_meta[0])
    meta_out["type"] = "meta"
    if not meta_out.get("schema"):
        meta_out["schema"] = "neurorom.translated_jsonl.v2"
    meta_out["semantic_autofix"] = True
    meta_out["semantic_autofix_at"] = _now_iso()
    meta_out["semantic_autofix_rows_changed"] = int(changed_rows)
    meta_out["semantic_autofix_register_policy"] = policy
    meta_out["semantic_autofix_quality_profile_sources"] = list(
        (quality_ctx.get("meta", {}) or {}).get("applied_sources", [])
    )

    written = _write_jsonl(translated_jsonl_path, [meta_out], trans_rows)
    return {
        "pass": bool(written),
        "written": bool(written),
        "changed": bool(written),
        "rows_total": int(len(trans_rows)),
        "rows_changed": int(changed_rows),
        "touched_uids": touched_uids[:200],
        "output_path": str(translated_jsonl_path),
        "register_policy": policy,
    }


def _qa_release_ready(qa: Dict[str, Any]) -> bool:
    checks = qa.get("checks", {}) if isinstance(qa, dict) else {}
    return bool(
        bool(qa.get("pass", False))
        and bool(checks.get("semantic_gate_pass", True))
        and bool(checks.get("semantic_english_residue_zero", True))
        and bool(checks.get("coverage_incomplete_false", True))
    )


def run_semantic_autoretry_for_translation(
    pure_jsonl_path: str,
    translated_jsonl_path: str,
    mapping_json_path: Optional[str] = None,
    report_json_path: Optional[str] = None,
    proof_json_path: Optional[str] = None,
    tbl_path: Optional[str] = None,
    max_rounds: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Loop automático de saneamento semântico até convergir ou atingir limite.
    """
    pure_meta, pure_rows = _load_jsonl(pure_jsonl_path)
    trans_meta, trans_rows = _load_jsonl(translated_jsonl_path)
    rom_crc32, _ = _extract_rom_identity(pure_meta, pure_rows, trans_meta, trans_rows)
    quality_ctx = _resolve_semantic_quality_context(
        rom_crc32=rom_crc32,
        pure_meta=pure_meta,
        pure_rows=pure_rows,
        trans_meta=trans_meta,
        trans_rows=trans_rows,
        hint_paths=[
            pure_jsonl_path,
            translated_jsonl_path,
            mapping_json_path,
            report_json_path,
            proof_json_path,
            tbl_path,
        ],
    )

    rounds = (
        int(max_rounds)
        if max_rounds is not None
        else int(quality_ctx.get("semantic_autofix_max_rounds", 8) or 8)
    )
    rounds = max(1, min(50, rounds))
    policy = _normalize_register_policy_local(
        quality_ctx.get("register_policy", "voce"),
        default="voce",
    )
    strict_from_ctx = bool(quality_ctx.get("semantic_strict", True))

    history: List[Dict[str, Any]] = []
    changed_any = False
    repairs = 0

    final_qa: Dict[str, Any] = {}
    for attempt in range(1, rounds + 1):
        qa = run_qa_gate(
            pure_jsonl_path=pure_jsonl_path,
            translated_jsonl_path=translated_jsonl_path,
            mapping_json_path=mapping_json_path,
            report_json_path=report_json_path,
            proof_json_path=proof_json_path,
            tbl_path=tbl_path,
            stage=f"semantic_autofix_round_{attempt}",
        )
        qa["attempt"] = int(attempt)
        history.append({"qa_gate": qa})
        final_qa = qa
        checks = qa.get("checks", {}) if isinstance(qa, dict) else {}
        if _qa_release_ready(qa):
            break
        if not bool(checks.get("semantic_gate_available", True)):
            break
        if attempt >= rounds:
            break

        repair = repair_translated_jsonl_semantic(
            pure_jsonl_path=pure_jsonl_path,
            translated_jsonl_path=translated_jsonl_path,
            qa_gate=qa,
            register_policy=policy,
            semantic_strict=strict_from_ctx,
        )
        repairs += 1
        changed_any = changed_any or bool(repair.get("changed", False))
        history.append({"semantic_repair": repair})
        if not bool(repair.get("written", False)):
            break

    return {
        "enabled": True,
        "pass": bool(_qa_release_ready(final_qa)),
        "attempts": int(sum(1 for h in history if "qa_gate" in h)),
        "repairs": int(repairs),
        "changed": bool(changed_any),
        "qa_gate": final_qa,
        "history": history,
        "register_policy": policy,
        "quality_profile_sources": list((quality_ctx.get("meta", {}) or {}).get("applied_sources", [])),
    }


def run_autoretry_for_translation(
    pure_jsonl_path: str,
    translated_jsonl_path: str,
    mapping_json_path: Optional[str] = None,
    report_json_path: Optional[str] = None,
    proof_json_path: Optional[str] = None,
    tbl_path: Optional[str] = None,
    max_retries: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Auto-retry de QA do translated.jsonl (máximo por env/config).
    """
    enabled = _env_bool("NEUROROM_AUTORETRY_ENABLE", True)
    retries = int(max_retries) if max_retries is not None else _env_int(
        "NEUROROM_AUTORETRY_MAX", 3, minimum=1, maximum=10
    )
    policy = str(os.environ.get("NEUROROM_CHARSET_POLICY", "strict") or "strict").strip().lower()
    if policy not in {"normalize", "strict"}:
        policy = "strict"

    history: List[Dict[str, Any]] = []
    changed_any = False
    repairs = 0

    if not enabled:
        qa_once = run_qa_gate(
            pure_jsonl_path=pure_jsonl_path,
            translated_jsonl_path=translated_jsonl_path,
            mapping_json_path=mapping_json_path,
            report_json_path=report_json_path,
            proof_json_path=proof_json_path,
            tbl_path=tbl_path,
            stage="post_translation",
        )
        return {
            "enabled": False,
            "pass": bool(qa_once.get("pass", False)),
            "attempts": 1,
            "repairs": 0,
            "changed": False,
            "qa_gate": qa_once,
            "history": [qa_once],
        }

    structural_attempts = 0
    final_qa: Dict[str, Any] = {}
    for attempt in range(1, retries + 1):
        structural_attempts += 1
        qa = run_qa_gate(
            pure_jsonl_path=pure_jsonl_path,
            translated_jsonl_path=translated_jsonl_path,
            mapping_json_path=mapping_json_path,
            report_json_path=report_json_path,
            proof_json_path=proof_json_path,
            tbl_path=tbl_path,
            stage="post_translation",
        )
        qa["attempt"] = int(attempt)
        history.append({"qa_gate": qa, "phase": "structural"})
        final_qa = qa
        if _qa_release_ready(qa):
            break

        checks = qa.get("checks", {}) if isinstance(qa, dict) else {}
        structural_fixable = any(
            not bool(checks.get(name, True))
            for name in (
                "count_match",
                "missing_zero",
                "extra_zero",
                "offset_not_none",
                "pointer_meta_preserved",
                "ordering_consistent",
                "terminator_valid",
                "charset_encodable",
            )
        )
        if not structural_fixable:
            break
        if attempt >= retries:
            break

        structural_repair = repair_translated_jsonl(
            pure_jsonl_path=pure_jsonl_path,
            translated_jsonl_path=translated_jsonl_path,
            tbl_path=tbl_path,
            charset_policy=policy,
        )
        repairs += 1
        changed_any = changed_any or bool(structural_repair.get("changed", False))
        history.append({"structural_repair": structural_repair, "attempt": int(attempt)})
        if not bool(structural_repair.get("written", False)):
            break

    semantic_result: Optional[Dict[str, Any]] = None
    checks = final_qa.get("checks", {}) if isinstance(final_qa, dict) else {}
    semantic_needed = bool(
        not bool(checks.get("semantic_gate_pass", True))
        or not bool(checks.get("semantic_english_residue_zero", True))
        or not bool(checks.get("coverage_incomplete_false", True))
    )
    semantic_available = bool(checks.get("semantic_gate_available", True))
    if final_qa and (not _qa_release_ready(final_qa)) and semantic_needed and semantic_available:
        semantic_result = run_semantic_autoretry_for_translation(
            pure_jsonl_path=pure_jsonl_path,
            translated_jsonl_path=translated_jsonl_path,
            mapping_json_path=mapping_json_path,
            report_json_path=report_json_path,
            proof_json_path=proof_json_path,
            tbl_path=tbl_path,
            max_rounds=None,
        )
        history.append({"semantic_autoretry": semantic_result})
        repairs += int(semantic_result.get("repairs", 0) or 0)
        changed_any = changed_any or bool(semantic_result.get("changed", False))
        qa_sem = semantic_result.get("qa_gate", {})
        if isinstance(qa_sem, dict) and qa_sem:
            final_qa = qa_sem

    if not final_qa:
        final_qa = run_qa_gate(
            pure_jsonl_path=pure_jsonl_path,
            translated_jsonl_path=translated_jsonl_path,
            mapping_json_path=mapping_json_path,
            report_json_path=report_json_path,
            proof_json_path=proof_json_path,
            tbl_path=tbl_path,
            stage="post_translation",
        )
        history.append({"qa_gate": final_qa, "phase": "final"})

    total_attempts = int(structural_attempts)
    if isinstance(semantic_result, dict):
        total_attempts += int(semantic_result.get("attempts", 0) or 0)

    return {
        "enabled": True,
        "pass": bool(_qa_release_ready(final_qa)),
        "attempts": int(total_attempts),
        "repairs": int(repairs),
        "changed": bool(changed_any),
        "qa_gate": final_qa,
        "history": history,
        "charset_policy": policy,
        "semantic_autoretry": semantic_result,
    }


def _load_mapping_offsets(mapping_json_path: Optional[str]) -> set:
    offsets = set()
    if not mapping_json_path or not os.path.isfile(mapping_json_path):
        return offsets
    data = _load_json(mapping_json_path)
    if not data:
        return offsets

    rows: List[Dict[str, Any]] = []
    if isinstance(data, list):
        rows = [x for x in data if isinstance(x, dict)]
    elif isinstance(data, dict):
        for fld in ("items", "entries", "mapping", "rows"):
            val = data.get(fld)
            if isinstance(val, list):
                rows.extend([x for x in val if isinstance(x, dict)])
    for row in rows:
        off = _parse_int(row.get("offset", row.get("rom_offset")))
        if off is not None and off >= 0:
            offsets.add(int(off))
    return offsets


def _load_runtime_evidence_rows(runtime_evidence_path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not runtime_evidence_path or not os.path.isfile(runtime_evidence_path):
        return rows
    try:
        with open(runtime_evidence_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                if str(obj.get("type", "") or "").strip().lower() == "meta":
                    continue

                block_reason = str(obj.get("translation_block_reason", "") or "").strip().upper()
                if block_reason == "UNMAPPED_GLYPHS":
                    continue

                off = (
                    _parse_int(obj.get("offset"))
                    or _parse_int(obj.get("rom_offset"))
                    or _parse_int(obj.get("addr"))
                    or _parse_int(obj.get("address"))
                )
                snippet = (
                    obj.get("snippet")
                    if isinstance(obj.get("snippet"), str)
                    else obj.get("line")
                    if isinstance(obj.get("line"), str)
                    else obj.get("text")
                    if isinstance(obj.get("text"), str)
                    else obj.get("line_key")
                    if isinstance(obj.get("line_key"), str)
                    else ""
                )
                source = (
                    obj.get("source")
                    if isinstance(obj.get("source"), str)
                    else obj.get("type")
                    if isinstance(obj.get("type"), str)
                    else ""
                )
                snippet_str = str(snippet) if isinstance(snippet, str) else ""
                snippet_norm = _normalize_runtime_snippet(snippet_str)
                if off is None and not snippet_norm:
                    continue
                row = {
                    "offset": int(off) if off is not None and off >= 0 else None,
                    "snippet": snippet_str,
                    "snippet_norm": snippet_norm,
                    "source": str(source) if isinstance(source, str) else "",
                }
                rows.append(row)
    except Exception:
        return []
    return rows


def _derive_runtime_search_dirs(
    rom_crc32: Optional[str],
    hint_paths: Optional[List[str]],
) -> List[Path]:
    dirs: List[Path] = []
    crc = str(rom_crc32 or "").strip().upper()
    hex8 = re.compile(r"^[0-9A-F]{8}$")

    for hint in (hint_paths or []):
        if not hint:
            continue
        p = Path(hint)
        if p.is_file():
            dirs.append(p.parent)
        elif p.is_dir():
            dirs.append(p)
        try:
            parents = [p] + list(p.parents)
        except Exception:
            parents = [p]
        for parent in parents:
            name = str(parent.name or "").strip().upper()
            if hex8.fullmatch(name):
                if not crc:
                    crc = name
                try:
                    console_dir = parent.parent
                    out_runtime = console_dir / "out" / name / "runtime"
                    dirs.append(out_runtime)
                except Exception:
                    pass
                break

    if crc:
        for hint in (hint_paths or []):
            if not hint:
                continue
            p = Path(hint)
            parents = [p] + list(p.parents)
            for parent in parents:
                if str(parent.name or "").strip().upper() == crc:
                    try:
                        console_dir = parent.parent
                        dirs.append(console_dir / "out" / crc / "runtime")
                    except Exception:
                        pass
                    break

    uniq: List[Path] = []
    seen = set()
    for d in dirs:
        try:
            rd = d.resolve()
        except Exception:
            rd = d
        if rd in seen:
            continue
        seen.add(rd)
        if d.exists() and d.is_dir():
            uniq.append(d)
    return uniq


def discover_runtime_evidence_path(
    rom_crc32: Optional[str] = None,
    hint_paths: Optional[List[str]] = None,
) -> Optional[str]:
    env_path = str(os.environ.get("NEUROROM_RUNTIME_EVIDENCE_PATH", "") or "").strip()
    if env_path and os.path.isfile(env_path):
        return env_path

    search_dirs = _derive_runtime_search_dirs(rom_crc32=rom_crc32, hint_paths=hint_paths or [])
    if not search_dirs:
        return None

    patterns = (
        "*_runtime_seen.jsonl",
        "*runtime_seen*.jsonl",
        "*_dyn_text_unique.jsonl",
        "*dyn_text_unique*.jsonl",
        "*_dyn_text_log.jsonl",
        "*dyn_text_log*.jsonl",
    )

    candidates: List[Path] = []
    for base in search_dirs:
        for pattern in patterns:
            try:
                for found in base.rglob(pattern):
                    if found.is_file():
                        candidates.append(found)
            except Exception:
                continue
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return str(candidates[0])


def run_runtime_coverage(
    pure_jsonl_path: str,
    translated_jsonl_path: str,
    mapping_json_path: Optional[str] = None,
    runtime_evidence_path: Optional[str] = None,
    rom_crc32: Optional[str] = None,
    rom_size: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Avalia cobertura por evidência runtime (sem scan de ROM).
    """
    provided = bool(runtime_evidence_path and os.path.isfile(runtime_evidence_path))
    if not provided:
        return {
            "schema": "neurorom.runtime_coverage.v1",
            "timestamp_utc": _now_iso(),
            "provided": False,
            "enabled": False,
            "pass": True,
            "reason": "RUNTIME_EVIDENCE_NOT_PROVIDED",
            "runtime_unmapped_total": 0,
            "runtime_untranslated_total": 0,
            "examples": {"unmapped": [], "untranslated": []},
            "inputs": {
                "runtime_evidence_path": str(runtime_evidence_path or ""),
                "pure_jsonl": str(pure_jsonl_path or ""),
                "translated_jsonl": str(translated_jsonl_path or ""),
                "mapping_json": str(mapping_json_path or ""),
                "rom_crc32": rom_crc32,
                "rom_size": rom_size,
            },
        }

    _, pure_rows = _load_jsonl(pure_jsonl_path)
    _, trans_rows = _load_jsonl(translated_jsonl_path)
    evidence_rows = _load_runtime_evidence_rows(runtime_evidence_path or "")

    mapping_offsets = _load_mapping_offsets(mapping_json_path)
    pure_offsets = set()
    known_source_snippets = set()
    for row in pure_rows:
        off = _row_offset_int(row)
        if off is not None and off >= 0:
            pure_offsets.add(int(off))
        src_norm = _normalize_runtime_snippet(_text_value(row, TEXT_SRC_FIELDS))
        if src_norm:
            known_source_snippets.add(src_norm)

    translated_offsets_with_dst = set()
    translated_source_snippets_with_dst = set()
    for row in trans_rows:
        off = _row_offset_int(row)
        dst = _text_value(row, TEXT_DST_FIELDS)
        if isinstance(dst, str) and dst.strip():
            if off is not None and off >= 0:
                translated_offsets_with_dst.add(int(off))
            src_norm = _normalize_runtime_snippet(_text_value(row, TEXT_SRC_FIELDS))
            if src_norm:
                translated_source_snippets_with_dst.add(src_norm)

    known_offsets = pure_offsets | mapping_offsets

    unmapped: List[Dict[str, Any]] = []
    untranslated: List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []
    with_offset = 0
    assessable_total = 0
    mapped_hits = 0
    runtime_unmapped_total = 0
    runtime_untranslated_total = 0
    runtime_unresolved_total = 0

    for row in evidence_rows:
        off = row.get("offset")
        snippet_norm = _normalize_runtime_snippet(str(row.get("snippet_norm", "") or ""))
        if off is None and not snippet_norm:
            runtime_unresolved_total += 1
            if len(unresolved) < 20:
                unresolved.append(
                    {
                        "offset": None,
                        "snippet": row.get("snippet", ""),
                        "source": row.get("source", ""),
                        "reason": "MISSING_OFFSET_AND_SNIPPET",
                    }
                )
            continue

        assessable_total += 1
        if off is not None:
            with_offset += 1
            off_int = int(off)
            if off_int not in known_offsets:
                runtime_unmapped_total += 1
                if len(unmapped) < 20:
                    unmapped.append(
                        {
                            "offset": f"0x{off_int:06X}",
                            "snippet": row.get("snippet", ""),
                            "source": row.get("source", ""),
                            "reason": "OFFSET_NOT_IN_PURE_OR_MAPPING",
                        }
                    )
                continue

            mapped_hits += 1
            if off_int not in translated_offsets_with_dst:
                runtime_untranslated_total += 1
                if len(untranslated) < 20:
                    untranslated.append(
                        {
                            "offset": f"0x{off_int:06X}",
                            "snippet": row.get("snippet", ""),
                            "source": row.get("source", ""),
                            "reason": "MAPPED_OFFSET_WITHOUT_DST",
                        }
                    )
            continue

        if snippet_norm not in known_source_snippets:
            runtime_unmapped_total += 1
            if len(unmapped) < 20:
                unmapped.append(
                    {
                        "offset": None,
                        "snippet": row.get("snippet", ""),
                        "source": row.get("source", ""),
                        "reason": "SNIPPET_NOT_IN_PURE",
                    }
                )
            continue

        mapped_hits += 1
        if snippet_norm not in translated_source_snippets_with_dst:
            runtime_untranslated_total += 1
            if len(untranslated) < 20:
                untranslated.append(
                    {
                        "offset": None,
                        "snippet": row.get("snippet", ""),
                        "source": row.get("source", ""),
                        "reason": "MAPPED_SNIPPET_WITHOUT_DST",
                    }
                )

    coverage_hits_percent = (mapped_hits / assessable_total * 100.0) if assessable_total > 0 else 0.0
    runtime_reason = ""
    runtime_pass = (
        int(runtime_unmapped_total) == 0
        and int(runtime_untranslated_total) == 0
        and int(assessable_total) > 0
    )
    if int(assessable_total) == 0:
        runtime_reason = "RUNTIME_EVIDENCE_NO_IDENTIFIERS"
        runtime_pass = False

    return {
        "schema": "neurorom.runtime_coverage.v1",
        "timestamp_utc": _now_iso(),
        "provided": True,
        "enabled": True,
        "pass": bool(runtime_pass),
        "reason": runtime_reason,
        "runtime_unmapped_total": int(runtime_unmapped_total),
        "runtime_untranslated_total": int(runtime_untranslated_total),
        "runtime_unresolved_total": int(runtime_unresolved_total),
        "coverage_hits_percent": float(round(coverage_hits_percent, 4)),
        "runtime_evidence_total": int(len(evidence_rows)),
        "runtime_evidence_assessable_total": int(assessable_total),
        "runtime_evidence_with_offset_total": int(with_offset),
        "examples": {
            "unmapped": unmapped,
            "untranslated": untranslated,
            "unresolved": unresolved,
        },
        "inputs": {
            "runtime_evidence_path": str(runtime_evidence_path or ""),
            "pure_jsonl": str(pure_jsonl_path or ""),
            "translated_jsonl": str(translated_jsonl_path or ""),
            "mapping_json": str(mapping_json_path or ""),
            "rom_crc32": rom_crc32,
            "rom_size": rom_size,
        },
    }


def upsert_qa_runtime_artifacts(
    report_txt_path: Optional[str],
    proof_json_path: Optional[str],
    report_json_path: Optional[str],
    qa_gate: Dict[str, Any],
    runtime_coverage: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Injeta QA_GATE + RUNTIME_COVERAGE nos artefatos existentes.
    """
    qa_ok = bool((qa_gate or {}).get("pass", False))
    rt_obj = runtime_coverage if isinstance(runtime_coverage, dict) else {}
    rt_provided = bool(rt_obj.get("provided", False))
    rt_ok = bool(rt_obj.get("pass", False))
    verified_100 = bool(qa_ok and ((not rt_provided) or rt_ok))

    updated = {
        "report_txt": False,
        "proof_json": False,
        "report_json": False,
        "verified_100": bool(verified_100),
    }

    def _write_json_payload(path_str: Optional[str]) -> bool:
        if not path_str:
            return False
        path = Path(path_str)
        if not path.exists() or not path.is_file():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}
        payload["qa_gate"] = qa_gate
        payload["runtime_coverage"] = runtime_coverage
        payload["verified_100"] = bool(verified_100)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return True

    updated["proof_json"] = _write_json_payload(proof_json_path)
    updated["report_json"] = _write_json_payload(report_json_path)

    if report_txt_path:
        txt_path = Path(report_txt_path)
        if txt_path.exists() and txt_path.is_file():
            try:
                old = txt_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                old = ""
            marker = "\n[NEUROROM_QA_RUNTIME]\n"
            if marker in old:
                old = old.split(marker, 1)[0].rstrip() + "\n"
            qa_metrics = qa_gate.get("metrics", {}) if isinstance(qa_gate, dict) else {}
            rt_metrics = runtime_coverage if isinstance(runtime_coverage, dict) else {}
            block = [
                "",
                "[NEUROROM_QA_RUNTIME]",
                "QA_GATE:",
                f"  pass={str(bool(qa_ok)).lower()}",
                f"  failed_checks={json.dumps((qa_gate or {}).get('failed_checks', []), ensure_ascii=False)}",
                f"  pure_count={qa_metrics.get('pure_count', 0)}",
                f"  translated_count={qa_metrics.get('translated_count', 0)}",
                f"  missing_count={qa_metrics.get('missing_count', 0)}",
                f"  extra_count={qa_metrics.get('extra_count', 0)}",
                f"  offset_none_count={qa_metrics.get('offset_none_count', 0)}",
                f"  pointer_invalid_count={qa_metrics.get('pointer_invalid_count', 0)}",
                f"  terminator_missing_count={qa_metrics.get('terminator_missing_count', 0)}",
                f"  blocked_count={qa_metrics.get('blocked_count', 0)}",
                f"  ui_items_blocked={qa_metrics.get('ui_items_blocked', 0)}",
                "RUNTIME_COVERAGE:",
                f"  provided={str(bool(rt_obj.get('provided', False))).lower()}",
                f"  pass={str(bool(rt_obj.get('pass', False))).lower()}",
                f"  reason={rt_metrics.get('reason', '')}",
                f"  runtime_unmapped_total={rt_metrics.get('runtime_unmapped_total', 0)}",
                f"  runtime_untranslated_total={rt_metrics.get('runtime_untranslated_total', 0)}",
                f"  runtime_unresolved_total={rt_metrics.get('runtime_unresolved_total', 0)}",
                f"  coverage_hits_percent={rt_metrics.get('coverage_hits_percent', 0.0)}",
                "VERIFICATION:",
                f"  verified_100={str(bool(verified_100)).lower()}",
                "",
            ]
            try:
                txt_path.write_text(old.rstrip() + "\n" + "\n".join(block), encoding="utf-8")
                updated["report_txt"] = True
            except Exception:
                updated["report_txt"] = False

    return updated
