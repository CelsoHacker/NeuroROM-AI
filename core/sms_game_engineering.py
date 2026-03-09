# -*- coding: utf-8 -*-
"""
SMS Game Engineering Profiles
=============================
Regras de engenharia específica por jogo (CRC) para:
- overrides de extração;
- normalização/regras de script;
- política de compressão/reinserção.
"""

from __future__ import annotations

import json
import re
import unicodedata
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _parse_int(value: Any, default: int = 0) -> int:
    """Converte inteiro aceitando decimal/hex string."""
    if value is None:
        return int(default)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        raw = value.strip().lower()
        if not raw:
            return int(default)
        if raw.startswith("0x-"):
            raw = "-0x" + raw[3:]
        try:
            if raw.startswith(("-0x", "+0x")):
                sign = -1 if raw.startswith("-") else 1
                return sign * int(raw[3:], 16)
            if raw.startswith("0x"):
                return int(raw, 16)
            return int(raw, 10)
        except ValueError:
            return int(default)
    return int(default)


def _parse_bool(value: Any, default: bool = False) -> bool:
    """Converte bool aceitando valores string comuns."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw in ("1", "true", "sim", "yes", "on"):
            return True
        if raw in ("0", "false", "nao", "não", "no", "off"):
            return False
    return bool(default)


class SMSGameEngineeringManager:
    """Carrega e aplica perfis por CRC para ROMs SMS."""

    def __init__(self, profiles_path: Optional[str] = None):
        base_dir = Path(__file__).resolve().parent
        default_path = base_dir / "profiles" / "sms" / "game_engineering_profiles.json"
        self.profiles_path = Path(profiles_path) if profiles_path else default_path
        self._db_cache: Optional[Dict[str, Any]] = None

    def _load_db(self) -> Dict[str, Any]:
        if self._db_cache is not None:
            return deepcopy(self._db_cache)
        if not self.profiles_path.exists():
            self._db_cache = {}
            return {}
        try:
            raw = json.loads(self.profiles_path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        self._db_cache = raw
        return deepcopy(raw)

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(out.get(key), dict):
                out[key] = self._deep_merge(out[key], value)
            elif isinstance(value, list) and isinstance(out.get(key), list):
                out[key] = deepcopy(out.get(key, [])) + deepcopy(value)
            else:
                out[key] = deepcopy(value)
        return out

    def get_profile(self, crc32: Optional[str]) -> Dict[str, Any]:
        """Retorna perfil efetivo (default + CRC)."""
        db = self._load_db()
        default_profile = db.get("default_profile", {})
        if not isinstance(default_profile, dict):
            default_profile = {}

        crc = str(crc32 or "").upper().strip()
        profile = {}
        profiles_by_crc = db.get("profiles_by_crc", {})
        if isinstance(profiles_by_crc, dict) and crc:
            profile = profiles_by_crc.get(crc, {})
        if not isinstance(profile, dict):
            profile = {}

        effective = self._deep_merge(default_profile, profile)
        effective["rom_crc32"] = crc
        effective["_profile_file"] = str(self.profiles_path)
        effective["_has_crc_profile"] = bool(profile)
        return effective

    def profile_summary(self, profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        p = profile if isinstance(profile, dict) else {}
        compression = p.get("compression", {}) if isinstance(p.get("compression"), dict) else {}
        return {
            "rom_crc32": p.get("rom_crc32"),
            "profile_id": p.get("id"),
            "profile_name": p.get("name"),
            "profile_version": p.get("version"),
            "profile_file": p.get("_profile_file"),
            "has_crc_profile": bool(p.get("_has_crc_profile", False)),
            "compression_mode": compression.get("mode"),
            "compression_block_reinsertion": bool(compression.get("block_reinsertion", False)),
        }

    def apply_extractor_overrides(
        self, config_obj: Any, profile: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Aplica overrides de extração no config já existente."""
        p = profile if isinstance(profile, dict) else {}
        overrides = p.get("extractor_overrides", {})
        if not isinstance(overrides, dict):
            return {}

        applied: Dict[str, Any] = {}
        scalar_map = {
            "min_safe_ratio": float,
            "min_pointer_confidence": float,
            "min_text_length": int,
            "max_text_length": int,
            "min_pointers_for_table": int,
            "tbl_min_confidence": float,
            "bank_size": int,
        }
        for key, caster in scalar_map.items():
            if key not in overrides or not hasattr(config_obj, key):
                continue
            try:
                val = caster(overrides.get(key))
                setattr(config_obj, key, val)
                applied[key] = val
            except Exception:
                continue

        if "candidate_terminators" in overrides and hasattr(config_obj, "candidate_terminators"):
            raw_terms = overrides.get("candidate_terminators")
            terms: List[int] = []
            if isinstance(raw_terms, (list, tuple)):
                for val in raw_terms:
                    parsed = _parse_int(val, default=-1)
                    if 0 <= parsed <= 0xFF:
                        terms.append(int(parsed))
            if terms:
                unique_terms = tuple(dict.fromkeys(terms))
                setattr(config_obj, "candidate_terminators", unique_terms)
                applied["candidate_terminators"] = list(unique_terms)

        if "profiles_dir" in overrides and hasattr(config_obj, "profiles_dir"):
            raw_dir = overrides.get("profiles_dir")
            if isinstance(raw_dir, str) and raw_dir.strip():
                setattr(config_obj, "profiles_dir", raw_dir.strip())
                applied["profiles_dir"] = raw_dir.strip()

        return applied

    def get_compression_policy(self, profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        p = profile if isinstance(profile, dict) else {}
        compression = p.get("compression", {})
        if not isinstance(compression, dict):
            return {}
        return {
            "mode": str(compression.get("mode", "unknown")).strip().lower(),
            "block_reinsertion": _parse_bool(compression.get("block_reinsertion"), default=False),
            "notes": str(compression.get("notes", "")).strip(),
            "extractor_hint": str(compression.get("extractor_hint", "")).strip(),
            "requires_codec": str(compression.get("requires_codec", "")).strip(),
        }

    def _resolve_stage_rules(self, profile: Dict[str, Any], stage: str) -> List[Dict[str, Any]]:
        rules: List[Dict[str, Any]] = []
        script_rules = profile.get("script_rules", {})
        if not isinstance(script_rules, dict):
            return rules
        for key in ("common", stage):
            chunk = script_rules.get(key, [])
            if isinstance(chunk, list):
                for item in chunk:
                    if isinstance(item, dict):
                        rules.append(item)
        return rules

    def _apply_rule(self, text: str, rule: Dict[str, Any]) -> str:
        op = str(rule.get("op", "")).strip().lower()
        if not op:
            return text

        if op == "replace":
            src = str(rule.get("src", ""))
            dst = str(rule.get("dst", ""))
            return text.replace(src, dst)

        if op == "regex_sub":
            pattern = str(rule.get("pattern", ""))
            repl = str(rule.get("repl", ""))
            flags_raw = str(rule.get("flags", "")).lower()
            flags = 0
            if "i" in flags_raw:
                flags |= re.IGNORECASE
            if "m" in flags_raw:
                flags |= re.MULTILINE
            if "s" in flags_raw:
                flags |= re.DOTALL
            if not pattern:
                return text
            return re.sub(pattern, repl, text, flags=flags)

        if op == "strip":
            return text.strip()

        if op == "collapse_spaces":
            return re.sub(r"\s+", " ", text).strip()

        if op == "upper":
            return text.upper()

        if op == "lower":
            return text.lower()

        return text

    def _apply_charset_policy(self, text: str, profile: Dict[str, Any]) -> str:
        charset = profile.get("charset", {})
        if not isinstance(charset, dict):
            return text

        out = text
        if _parse_bool(charset.get("strip_accents"), default=False):
            out = "".join(
                ch
                for ch in unicodedata.normalize("NFD", out)
                if unicodedata.category(ch) != "Mn"
            )

        allowed = charset.get("allowed_chars_regex")
        if isinstance(allowed, str) and allowed.strip():
            try:
                out = "".join(ch for ch in out if re.match(allowed, ch))
            except re.error:
                pass

        normalize_ws = _parse_bool(charset.get("normalize_whitespace"), default=True)
        preserve_nl = _parse_bool(charset.get("preserve_newlines"), default=False)
        if normalize_ws:
            if preserve_nl:
                out = "\n".join(
                    re.sub(r"\s+", " ", line).strip()
                    for line in out.splitlines()
                )
                out = "\n".join(line for line in out.splitlines() if line)
            else:
                out = re.sub(r"\s+", " ", out).strip()

        max_chars = _parse_int(charset.get("max_chars"), default=0)
        if max_chars > 0 and len(out) > max_chars:
            out = out[:max_chars]
        return out

    def apply_text_pipeline(
        self, text: str, profile: Optional[Dict[str, Any]], stage: str
    ) -> Tuple[str, int]:
        """Aplica regras de script + charset e retorna (texto, mudanças)."""
        if not isinstance(text, str):
            return "", 0
        p = profile if isinstance(profile, dict) else {}
        out = text
        changes = 0

        for rule in self._resolve_stage_rules(p, stage=stage):
            new_out = self._apply_rule(out, rule)
            if new_out != out:
                changes += 1
                out = new_out

        final_out = self._apply_charset_policy(out, p)
        if final_out != out:
            changes += 1
        return final_out, changes
