import json
from pathlib import Path

from core.quality_profile_manager import (
    candidate_quality_profile_paths,
    normalize_console_hint,
    resolve_quality_profile,
)


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def test_normalize_console_hint_expande_consoles_alvo():
    assert normalize_console_hint("psx") == "PS1"
    assert normalize_console_hint("nintendo 64") == "N64"
    assert normalize_console_hint("gba") == "GBA"
    assert normalize_console_hint("sfc") == "SNES"


def test_resolve_quality_profile_respeita_precedencia_console_family_crc(tmp_path: Path):
    root = tmp_path / "profiles" / "quality"
    _write_json(
        root / "default.json",
        {
            "register_policy": "voce",
            "semantic": {"min_semantic_score_standard": 70.0, "min_semantic_score_strict": 82.0},
        },
    )
    _write_json(
        root / "consoles" / "gba.json",
        {
            "register_policy": "tu",
            "semantic": {"min_semantic_score_standard": 72.0},
        },
    )
    _write_json(
        root / "families" / "pokemon_like.json",
        {
            "semantic": {"autofix_max_rounds": 12},
        },
    )
    _write_json(
        root / "crc" / "611535DC.json",
        {
            "register_policy": "ce",
            "semantic": {"min_semantic_score_strict": 90.0},
        },
    )

    resolved = resolve_quality_profile(
        console="GBA",
        family="pokemon_like",
        rom_crc32="611535DC",
        profiles_root=root,
    )
    profile = resolved["profile"]
    assert profile["register_policy"] == "ce"
    assert float(profile["semantic"]["min_semantic_score_standard"]) == 72.0
    assert float(profile["semantic"]["min_semantic_score_strict"]) == 90.0
    assert int(profile["semantic"]["autofix_max_rounds"]) == 12


def test_candidate_quality_profile_paths_inclui_console_ps1_n64_gba_snes(tmp_path: Path):
    root = tmp_path / "profiles" / "quality"
    paths = candidate_quality_profile_paths(console="PS1", profiles_root=root)
    assert any(str(p).endswith("consoles\\ps1.json") or str(p).endswith("consoles/ps1.json") for _, p in paths)

    paths_n64 = candidate_quality_profile_paths(console="N64", profiles_root=root)
    assert any(
        str(p).endswith("consoles\\n64.json") or str(p).endswith("consoles/n64.json")
        for _, p in paths_n64
    )

    paths_gba = candidate_quality_profile_paths(console="GBA", profiles_root=root)
    assert any(
        str(p).endswith("consoles\\gba.json") or str(p).endswith("consoles/gba.json")
        for _, p in paths_gba
    )

    paths_snes = candidate_quality_profile_paths(console="SNES", profiles_root=root)
    assert any(
        str(p).endswith("consoles\\snes.json") or str(p).endswith("consoles/snes.json")
        for _, p in paths_snes
    )

