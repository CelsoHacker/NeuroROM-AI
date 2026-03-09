# -*- coding: utf-8 -*-
"""
Sincroniza perfis de engenharia SMS por CRC (sem nome de jogo).

Uso:
    python sync_sms_engineering_profiles.py
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


HEX8_RE = re.compile(r"^[0-9A-F]{8}$")


def _is_hex8(value: Any) -> bool:
    return isinstance(value, str) and bool(HEX8_RE.match(value.strip().upper()))


def _to_hex_terminators(values: Any) -> List[str]:
    out: List[str] = []
    if not isinstance(values, list):
        return out
    for value in values:
        try:
            iv = int(value)
        except Exception:
            continue
        if 0 <= iv <= 0xFF:
            out.append(f"0x{iv:02X}")
    # remove duplicados preservando ordem
    return list(dict.fromkeys(out))


def _default_overrides_by_encoding(encoding: str) -> Dict[str, Any]:
    enc = str(encoding or "").strip().lower()
    if enc == "tilemap":
        return {
            "min_safe_ratio": 0.35,
            "min_pointer_confidence": 0.45,
            "min_text_length": 2,
            "max_text_length": 240,
            "min_pointers_for_table": 4,
        }
    if enc == "ascii":
        return {
            "min_safe_ratio": 0.80,
            "min_pointer_confidence": 0.60,
            "min_text_length": 3,
            "max_text_length": 256,
            "min_pointers_for_table": 6,
        }
    return {
        "min_safe_ratio": 0.55,
        "min_pointer_confidence": 0.50,
        "min_text_length": 2,
        "max_text_length": 256,
        "min_pointers_for_table": 5,
    }


def _build_base_profile(crc: str, game_entry: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    entry = game_entry if isinstance(game_entry, dict) else {}
    encoding = str(entry.get("encoding", "auto")).strip().lower()
    terminators = _to_hex_terminators(entry.get("terminators", []))

    profile: Dict[str, Any] = {
        "id": f"sms_crc_{crc.lower()}",
        "name": f"SMS CRC {crc}",
        "version": "1.0",
        "extractor_overrides": _default_overrides_by_encoding(encoding),
    }
    if terminators:
        profile["extractor_overrides"]["candidate_terminators"] = terminators

    profile["compression"] = {
        "mode": "unknown",
        "block_reinsertion": False,
        "notes": "",
    }
    return profile


def _merge_missing(target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(target)
    for key, value in source.items():
        if key not in out:
            out[key] = deepcopy(value)
            continue
        if isinstance(out.get(key), dict) and isinstance(value, dict):
            out[key] = _merge_missing(out[key], value)
    return out


def main() -> int:
    core_dir = Path(__file__).resolve().parent
    profiles_dir = core_dir / "profiles" / "sms"
    target_path = profiles_dir / "game_engineering_profiles.json"
    db_path = core_dir / "game_profiles_db.json"

    if not target_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {target_path}")

    raw_target = json.loads(target_path.read_text(encoding="utf-8"))
    if not isinstance(raw_target, dict):
        raise ValueError("Formato inválido em game_engineering_profiles.json")

    profiles_by_crc = raw_target.get("profiles_by_crc")
    if not isinstance(profiles_by_crc, dict):
        profiles_by_crc = {}
        raw_target["profiles_by_crc"] = profiles_by_crc

    game_by_crc: Dict[str, Dict[str, Any]] = {}
    crc_set: Set[str] = set()

    if db_path.exists():
        raw_db = json.loads(db_path.read_text(encoding="utf-8"))
        games = raw_db.get("games", []) if isinstance(raw_db, dict) else []
        if isinstance(games, list):
            for game in games:
                if not isinstance(game, dict):
                    continue
                if str(game.get("console", "")).strip().upper() != "SMS":
                    continue
                crc = str(game.get("crc32", "")).strip().upper()
                if not _is_hex8(crc):
                    continue
                crc_set.add(crc)
                game_by_crc[crc] = game

    for file_path in profiles_dir.glob("*.json"):
        name = file_path.name
        if name.lower() == "game_engineering_profiles.json":
            continue
        crc = file_path.stem.strip().upper()
        if _is_hex8(crc):
            crc_set.add(crc)

    for crc in sorted(crc_set):
        base_profile = _build_base_profile(crc, game_by_crc.get(crc))
        existing = profiles_by_crc.get(crc)
        if isinstance(existing, dict):
            merged = _merge_missing(existing, base_profile)
            merged["id"] = f"sms_crc_{crc.lower()}"
            merged["name"] = f"SMS CRC {crc}"
            profiles_by_crc[crc] = merged
        else:
            profiles_by_crc[crc] = base_profile

    raw_target["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    raw_target["profiles_by_crc"] = {
        crc: profiles_by_crc[crc]
        for crc in sorted(profiles_by_crc.keys())
        if _is_hex8(crc)
    }

    target_path.write_text(
        json.dumps(raw_target, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Perfis CRC sincronizados: {len(raw_target['profiles_by_crc'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
