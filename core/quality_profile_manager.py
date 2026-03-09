# -*- coding: utf-8 -*-
"""
Resolvedor de perfis de qualidade (gates + semântica) por escopo.

Ordem de merge (mais genérico -> mais específico):
1) defaults embutidos
2) profiles/quality/default.json
3) profiles/quality/consoles/{console}.json
4) profiles/quality/families/{family}.json
5) profiles/quality/crc/{CRC32}.json
6) profile explícito por path (env/extraction parâmetro)
7) profile inline em extraction_data["quality_profile"]
"""

from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple


REGISTER_POLICY_ALIASES = {
    "voce": "voce",
    "você": "voce",
    "vc": "voce",
    "tu": "tu",
    "ce": "ce",
    "cê": "ce",
}

CONSOLE_ALIASES = {
    "SMS": "SMS",
    "MASTER_SYSTEM": "SMS",
    "MASTER SYSTEM": "SMS",
    "GG": "SMS",
    "GAME_GEAR": "SMS",
    "GAME GEAR": "SMS",
    "NES": "NES",
    "FAMICOM": "NES",
    "SNES": "SNES",
    "SFC": "SNES",
    "SUPER_NINTENDO": "SNES",
    "SUPER NINTENDO": "SNES",
    "SUPER_NES": "SNES",
    "SUPER NES": "SNES",
    "PSX": "PS1",
    "PS1": "PS1",
    "PLAYSTATION": "PS1",
    "N64": "N64",
    "NINTENDO_64": "N64",
    "NINTENDO 64": "N64",
    "GBA": "GBA",
    "GAME_BOY_ADVANCE": "GBA",
    "GAME BOY ADVANCE": "GBA",
    "MD": "MD",
    "GENESIS": "MD",
    "MEGA_DRIVE": "MD",
    "MEGA DRIVE": "MD",
}

DEFAULT_QUALITY_PROFILE: Dict[str, Any] = {
    "schema": "neurorom.quality_profile.v1",
    "quality_mode": "standard",
    "register_policy": "voce",
    "semantic": {
        "strict_mode": True,
        "min_semantic_score_standard": 70.0,
        "min_semantic_score_strict": 82.0,
        "autofix_max_rounds": 8,
        "glossary": {},
    },
    "audit": {
        "require_coverage_complete": True,
        "require_semantic_gate_pass": True,
        "require_semantic_english_residue_zero": True,
    },
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _safe_int(value: Any, default: int, minimum: int = 1, maximum: int = 50) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = int(default)
    parsed = max(int(minimum), parsed)
    parsed = min(int(maximum), parsed)
    return int(parsed)


def _deep_merge(base: Dict[str, Any], extra: Mapping[str, Any]) -> Dict[str, Any]:
    for key, value in extra.items():
        k = str(key)
        if isinstance(value, Mapping) and isinstance(base.get(k), dict):
            base[k] = _deep_merge(dict(base.get(k) or {}), value)
        else:
            base[k] = copy.deepcopy(value)
    return base


def _normalize_crc32(value: Any) -> Optional[str]:
    raw = str(value or "").strip().upper()
    if not raw:
        return None
    return raw if re.fullmatch(r"[0-9A-F]{8}", raw) else None


def normalize_register_policy(value: Any, default: str = "voce") -> str:
    raw = str(value or "").strip().casefold()
    if not raw:
        return str(default)
    return REGISTER_POLICY_ALIASES.get(raw, str(default))


def normalize_console_hint(value: Any) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    key = raw.upper().replace("-", "_")
    return CONSOLE_ALIASES.get(
        key,
        key if key in {"NES", "SMS", "MD", "SNES", "PS1", "N64", "GBA"} else None,
    )


def _normalize_family(value: Any) -> Optional[str]:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    cleaned = re.sub(r"[^a-z0-9_.-]+", "_", raw).strip("_")
    return cleaned or None


def _derive_family_hint(
    family: Optional[str],
    extraction_data: Optional[Mapping[str, Any]] = None,
) -> Optional[str]:
    normalized = _normalize_family(family)
    if normalized:
        return normalized
    if not isinstance(extraction_data, Mapping):
        return None
    for key in ("quality_family", "game_family", "family", "series"):
        cand = _normalize_family(extraction_data.get(key))
        if cand:
            return cand
    semantic_policy = extraction_data.get("semantic_policy")
    if isinstance(semantic_policy, Mapping):
        cand = _normalize_family(semantic_policy.get("family"))
        if cand:
            return cand
    return None


def _extract_profile_payload(raw: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    # Permite wrapper sem quebrar compatibilidade de formatos legados.
    for key in ("quality_profile", "profile", "semantic_profile"):
        sub = raw.get(key)
        if isinstance(sub, Mapping):
            return dict(sub)
    return dict(raw)


def candidate_quality_profile_paths(
    console: Optional[str] = None,
    family: Optional[str] = None,
    rom_crc32: Optional[str] = None,
    extraction_data: Optional[Mapping[str, Any]] = None,
    explicit_profile_path: Optional[str] = None,
    search_hint_paths: Optional[List[str]] = None,
    profiles_root: Optional[str | Path] = None,
) -> List[Tuple[str, Path]]:
    root = (
        Path(profiles_root).expanduser().resolve()
        if profiles_root
        else (_project_root() / "profiles" / "quality").resolve()
    )
    console_u = normalize_console_hint(console)
    family_l = _derive_family_hint(family=family, extraction_data=extraction_data)
    crc_u = _normalize_crc32(rom_crc32)

    candidates: List[Tuple[str, Path]] = [("default", root / "default.json")]
    if console_u:
        candidates.append(("console", root / "consoles" / f"{console_u.lower()}.json"))
    if family_l:
        candidates.append(("family", root / "families" / f"{family_l}.json"))
    if crc_u:
        candidates.append(("crc", root / "crc" / f"{crc_u}.json"))

    hint_dirs: List[Path] = []
    for hint in (search_hint_paths or []):
        if not hint:
            continue
        p = Path(hint).expanduser()
        hint_dirs.append(p.parent if p.suffix else p)

    def _resolve_maybe_relative(raw_path: str) -> Path:
        p = Path(str(raw_path)).expanduser()
        if p.is_absolute():
            return p
        for d in hint_dirs:
            try:
                cand = (d / p).resolve()
            except Exception:
                cand = d / p
            if cand.exists():
                return cand
        return p

    env_path = str(os.environ.get("NEUROROM_QUALITY_PROFILE_PATH", "") or "").strip()
    if env_path:
        candidates.append(("env", _resolve_maybe_relative(env_path)))

    if explicit_profile_path:
        candidates.append(("explicit", _resolve_maybe_relative(explicit_profile_path)))

    if isinstance(extraction_data, Mapping):
        for key in ("quality_profile_path", "semantic_quality_profile_path"):
            raw = extraction_data.get(key)
            if not raw:
                continue
            candidates.append(("extraction_path", _resolve_maybe_relative(str(raw))))
        sem = extraction_data.get("semantic_policy")
        if isinstance(sem, Mapping):
            raw = sem.get("quality_profile_path")
            if raw:
                candidates.append(("semantic_policy_path", _resolve_maybe_relative(str(raw))))

    if search_hint_paths:
        for hint in search_hint_paths:
            if not hint:
                continue
            p = Path(hint).expanduser()
            dirs = [p.parent] if p.suffix else [p]
            for d in dirs:
                if not d:
                    continue
                candidates.append(("hint_dir", d / "quality_profile.json"))
                if crc_u:
                    candidates.append(("hint_crc", d / f"{crc_u}_quality_profile.json"))

    uniq: List[Tuple[str, Path]] = []
    seen = set()
    for scope, path in candidates:
        try:
            rp = path.resolve()
        except Exception:
            rp = path
        key = str(rp).lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append((scope, rp))
    return uniq


def resolve_quality_profile(
    console: Optional[str] = None,
    family: Optional[str] = None,
    rom_crc32: Optional[str] = None,
    extraction_data: Optional[Mapping[str, Any]] = None,
    explicit_profile_path: Optional[str] = None,
    search_hint_paths: Optional[List[str]] = None,
    profiles_root: Optional[str | Path] = None,
) -> Dict[str, Any]:
    resolved = copy.deepcopy(DEFAULT_QUALITY_PROFILE)
    applied_sources: List[Dict[str, Any]] = []

    candidates = candidate_quality_profile_paths(
        console=console,
        family=family,
        rom_crc32=rom_crc32,
        extraction_data=extraction_data,
        explicit_profile_path=explicit_profile_path,
        search_hint_paths=search_hint_paths,
        profiles_root=profiles_root,
    )

    for scope, path in candidates:
        obj = _load_json(path)
        if not obj:
            continue
        payload = _extract_profile_payload(obj)
        if not payload or payload.get("enabled", True) is False:
            continue
        _deep_merge(resolved, payload)
        applied_sources.append({"scope": scope, "path": str(path)})

    if isinstance(extraction_data, Mapping):
        for key in ("quality_profile", "semantic_quality_profile"):
            raw = extraction_data.get(key)
            if isinstance(raw, Mapping):
                _deep_merge(resolved, dict(raw))
                applied_sources.append({"scope": f"inline:{key}", "path": "inline"})
        sem = extraction_data.get("semantic_policy")
        if isinstance(sem, Mapping):
            inline = sem.get("quality_profile")
            if isinstance(inline, Mapping):
                _deep_merge(resolved, dict(inline))
                applied_sources.append({"scope": "inline:semantic_policy", "path": "inline"})

    quality_mode = str(resolved.get("quality_mode", "standard") or "standard").strip().lower()
    resolved["quality_mode"] = "strict" if quality_mode == "strict" else "standard"
    resolved["register_policy"] = normalize_register_policy(
        resolved.get("register_policy"),
        default="voce",
    )

    semantic = resolved.get("semantic")
    if not isinstance(semantic, dict):
        semantic = {}
    strict_mode = semantic.get("strict_mode")
    if not isinstance(strict_mode, bool):
        strict_mode = True
    semantic["strict_mode"] = bool(strict_mode)
    semantic["min_semantic_score_standard"] = float(
        _safe_float(semantic.get("min_semantic_score_standard", 70.0), default=70.0)
    )
    semantic["min_semantic_score_strict"] = float(
        _safe_float(semantic.get("min_semantic_score_strict", 82.0), default=82.0)
    )
    semantic["autofix_max_rounds"] = int(
        _safe_int(semantic.get("autofix_max_rounds", 8), default=8, minimum=1, maximum=50)
    )
    glossary = semantic.get("glossary")
    semantic["glossary"] = dict(glossary) if isinstance(glossary, Mapping) else {}
    resolved["semantic"] = semantic
    resolved.setdefault("schema", "neurorom.quality_profile.v1")

    meta = {
        "console": normalize_console_hint(console),
        "family": _derive_family_hint(family=family, extraction_data=extraction_data),
        "rom_crc32": _normalize_crc32(rom_crc32),
        "profiles_root": str(
            Path(profiles_root).expanduser().resolve()
            if profiles_root
            else (_project_root() / "profiles" / "quality").resolve()
        ),
        "applied_sources": applied_sources,
    }
    return {"profile": resolved, "meta": meta}
