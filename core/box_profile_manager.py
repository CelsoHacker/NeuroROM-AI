# -*- coding: utf-8 -*-
"""
Gerenciador de perfis de caixa de texto por console/jogo.

Suposicoes minimas:
1) O arquivo pode seguir schema livre ou game_profiles_db.v1 existente.
2) Se nao houver perfil explicito, usa defaults seguros por console.
3) Override manual e aplicado por console/box_type e opcionalmente por CRC.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _merge_dict(base: dict[str, Any], extra: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(extra, Mapping):
        return base
    for key, value in extra.items():
        base[str(key)] = value
    return base


class BoxProfileManager:
    def __init__(self, profile_file: str | Path):
        self.profile_file = Path(profile_file)
        self.profiles = _load_json(self.profile_file)
        self._manual_overrides: dict[tuple[str, str, str | None], dict[str, Any]] = {}

    def set_override(
        self,
        console: str,
        box_type: str,
        profile: Mapping[str, Any],
        game_crc: str | None = None,
    ) -> None:
        key = (str(console).upper(), str(box_type).lower(), str(game_crc).upper() if game_crc else None)
        self._manual_overrides[key] = dict(profile)

    def get_profile(self, console: str, box_type: str, game_crc: str | None = None) -> dict[str, Any]:
        console_u = str(console).upper()
        box_l = str(box_type).lower()
        crc_u = str(game_crc).upper() if game_crc else None

        resolved = self._default_profile(console_u, box_l)
        _merge_dict(resolved, self._from_console_profiles(console_u, box_l))
        _merge_dict(resolved, self._from_game_profiles(console_u, box_l, crc_u))
        _merge_dict(resolved, self._manual_overrides.get((console_u, box_l, None)))
        if crc_u:
            _merge_dict(resolved, self._manual_overrides.get((console_u, box_l, crc_u)))
        return resolved

    def _default_profile(self, console: str, box_type: str) -> dict[str, Any]:
        defaults = {
            "NES": {"mode": "mono", "max_width": 32, "max_lines": 4},
            "SNES": {"mode": "pixel", "max_width": 224, "max_lines": 4},
            "SMS": {"mode": "mono", "max_width": 32, "max_lines": 4},
            "MD": {"mode": "pixel", "max_width": 320, "max_lines": 4},
            "GENESIS": {"mode": "pixel", "max_width": 320, "max_lines": 4},
            "GBA": {"mode": "pixel", "max_width": 240, "max_lines": 4},
            "N64": {"mode": "pixel", "max_width": 320, "max_lines": 4},
            "PS1": {"mode": "pixel", "max_width": 320, "max_lines": 4},
            "PC": {"mode": "pixel", "max_width": 640, "max_lines": 8},
        }
        base = defaults.get(console, {"mode": "mono", "max_width": 32, "max_lines": 4}).copy()
        base["box_type"] = box_type
        base["console"] = console
        return base

    def _from_console_profiles(self, console: str, box_type: str) -> dict[str, Any]:
        data = self.profiles if isinstance(self.profiles, Mapping) else {}
        console_profiles = data.get("console_profiles")
        if isinstance(console_profiles, Mapping):
            c_data = console_profiles.get(console, {})
        else:
            c_data = data.get(console, {})
        if not isinstance(c_data, Mapping):
            return {}

        for key in ("box_profiles", "boxes", "box_types"):
            bmap = c_data.get(key)
            if isinstance(bmap, Mapping):
                candidate = bmap.get(box_type)
                if isinstance(candidate, Mapping):
                    return dict(candidate)

        direct = c_data.get(box_type)
        if isinstance(direct, Mapping):
            return dict(direct)
        default = c_data.get("default_box_profile")
        if isinstance(default, Mapping):
            return dict(default)
        return {}

    def _from_game_profiles(self, console: str, box_type: str, game_crc: str | None) -> dict[str, Any]:
        data = self.profiles if isinstance(self.profiles, Mapping) else {}

        # Formato game_profiles_db.v1 (existente no projeto)
        games = data.get("games")
        if isinstance(games, list):
            for game in games:
                if not isinstance(game, Mapping):
                    continue
                if game_crc and str(game.get("crc32", "")).upper() != game_crc:
                    continue
                if str(game.get("console", "")).upper() != console:
                    continue
                for key in ("box_profiles", "boxes", "box_types"):
                    box_map = game.get(key)
                    if isinstance(box_map, Mapping):
                        candidate = box_map.get(box_type)
                        if isinstance(candidate, Mapping):
                            return dict(candidate)
                # Fallback simples usando text_regions existentes
                regions = game.get("text_regions")
                if isinstance(regions, list):
                    for region in regions:
                        if not isinstance(region, Mapping):
                            continue
                        label = str(region.get("label", "")).strip().lower()
                        if label != box_type:
                            continue
                        return {"region_start": region.get("start"), "region_end": region.get("end")}

        # Formatos alternativos
        game_profiles = data.get("game_profiles")
        if isinstance(game_profiles, Mapping) and game_crc:
            raw = game_profiles.get(game_crc, {})
            if isinstance(raw, Mapping):
                box_map = raw.get("box_profiles", {})
                if isinstance(box_map, Mapping):
                    candidate = box_map.get(box_type)
                    if isinstance(candidate, Mapping):
                        return dict(candidate)
        return {}

