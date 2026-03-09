from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict

_GLOSSARY_PATH = Path(__file__).resolve().with_name("compact_glossary.json")
_CACHE_MTIME: float | None = None
_CACHE_DATA: Dict[str, Dict[str, str]] | None = None
_WORD_CLASS = "0-9A-Za-zÀ-ÖØ-öø-ÿ_"


def _normalize_section(section: object) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not isinstance(section, dict):
        return out
    for raw_src, raw_dst in section.items():
        src = str(raw_src or "").strip()
        if not src or src.lower() == "comment":
            continue
        if not isinstance(raw_dst, str):
            continue
        out[src] = raw_dst
    return out


def _load_compact_glossary() -> Dict[str, Dict[str, str]]:
    global _CACHE_DATA, _CACHE_MTIME
    try:
        mtime = float(_GLOSSARY_PATH.stat().st_mtime)
    except Exception:
        _CACHE_DATA = {}
        _CACHE_MTIME = None
        return {}

    if _CACHE_DATA is not None and _CACHE_MTIME == mtime:
        return _CACHE_DATA

    loaded: Dict[str, Dict[str, str]] = {}
    try:
        raw_obj = json.loads(_GLOSSARY_PATH.read_text(encoding="utf-8"))
    except Exception:
        raw_obj = {}

    if isinstance(raw_obj, dict):
        for section_name, section_map in raw_obj.items():
            sec = str(section_name or "").strip()
            if not sec:
                continue
            if sec == "_global":
                loaded["_global"] = _normalize_section(section_map)
            else:
                loaded[sec.upper()] = _normalize_section(section_map)

    _CACHE_DATA = loaded
    _CACHE_MTIME = mtime
    return loaded


def _preserve_case(original: str, replacement: str) -> str:
    if not original or not replacement:
        return replacement
    # Mantém siglas como PV/PM sem deformar o formato.
    if replacement.isupper() and len(replacement) <= 4:
        return replacement
    if original.isupper():
        return replacement.upper()
    if original.islower():
        return replacement.lower()
    if original.istitle():
        return replacement.title()
    return replacement


def _replace_glossary_entries(text: str, entries: Dict[str, str]) -> str:
    if not text or not entries:
        return text

    out = text
    ordered_entries = sorted(
        entries.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for src, dst in ordered_entries:
        if not src:
            continue
        pattern = re.compile(
            rf"(?<![{_WORD_CLASS}]){re.escape(src)}(?![{_WORD_CLASS}])",
            re.IGNORECASE,
        )
        out = pattern.sub(lambda m: _preserve_case(m.group(0), dst), out)
    return out


def apply_compact_glossary(text: str, crc32: str = None) -> str:
    """Aplica glossário compacto; usar antes de strip_accents e fit/truncamento."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    if not text:
        return text

    glossary_data = _load_compact_glossary()
    if not glossary_data:
        return text

    out = _replace_glossary_entries(text, glossary_data.get("_global", {}))
    crc_key = str(crc32 or "").strip().upper()
    if crc_key:
        out = _replace_glossary_entries(out, glossary_data.get(crc_key, {}))
    return out
