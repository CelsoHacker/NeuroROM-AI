import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.box_profile_manager import BoxProfileManager
from core.console_memory_model import ConsoleMemoryModel
from core.glyph_metrics import GlyphMetrics
from core.plausibility import (
    classify_human_candidate,
    normalize_human_text,
    passes_min_offset_with_allowlist,
)
from core.relocation_manager import RelocationManager
from core.safe_reinserter import SafeReinserter
from core.text_layout_engine import TextLayoutEngine


def test_encoding_ok_and_warning_collection_in_safe_reinserter(tmp_path: Path):
    rom_path = tmp_path / "game.sms"
    rom_path.write_bytes(b"\xFF" * 256)

    extraction_path = tmp_path / "extract.json"
    extraction_path.write_text(
        json.dumps(
            {
                "console": "SMS",
                "mappings": [
                    {
                        "uid": "U_00001",
                        "offset_dec": 32,
                        "length": 6,
                        "terminator": 0,
                        "pointer_refs": [],
                        "source": "HELLO",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    reinserter = SafeReinserter(str(rom_path), str(extraction_path))
    reinserter.reinsert_translations({1: "HELLO WORLD"}, create_backup=False)

    qa_entry = reinserter.runtime_qa_entries[1]
    assert qa_entry["fallback_legacy"] is False
    assert qa_entry["reason"] == "ok"
    assert qa_entry["truncated"] is True
    assert qa_entry["warnings"]


def test_glyph_metrics_consistente(tmp_path: Path):
    glyph_path = tmp_path / "glyph_widths.json"
    glyph_path.write_text(
        json.dumps(
            {
                "default_width": 4,
                "widths": {"A": 5, "B": 6, " ": 2},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    metrics = GlyphMetrics(glyph_path)
    assert metrics.measure("AB A") == (5 + 6 + 2 + 5)
    assert metrics.measure("<WAIT>AB") == (5 + 6)


def test_layout_respeita_box_e_sinaliza_overflow(tmp_path: Path):
    glyph_path = tmp_path / "glyph_widths.json"
    glyph_path.write_text(json.dumps({"default_width": 5}, ensure_ascii=False), encoding="utf-8")
    metrics = GlyphMetrics(glyph_path)

    engine = TextLayoutEngine(metrics, {"mode": "pixel", "max_width": 10, "max_lines": 2})
    result = engine.layout("AAAA BBBB CCCC DDDD")

    assert result["line_count"] > 2
    assert result["visual_overflow"] is True
    assert any(width > 0 for width in result["pixel_widths"])


def test_selecao_de_perfil_deterministica(tmp_path: Path):
    db_path = tmp_path / "game_profiles_db.json"
    db_path.write_text(
        json.dumps(
            {
                "schema": "game_profiles_db.v1",
                "games": [
                    {
                        "crc32": "AAAABBBB",
                        "console": "SNES",
                        "box_profiles": {
                            "dialog": {"mode": "mono", "max_width": 18, "max_lines": 3}
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    manager = BoxProfileManager(db_path)
    p1 = manager.get_profile("SNES", "dialog", game_crc="AAAABBBB")
    p2 = manager.get_profile("SNES", "dialog", game_crc="AAAABBBB")
    assert p1 == p2
    assert p1["max_width"] == 18


def test_relocation_nao_escreve_fora_de_free_space_e_retorna_estrutura():
    rom = bytearray(b"\xFF" * 0x200)
    old_offset = 0x40
    rom[old_offset : old_offset + 4] = b"OLD\x00"
    rom[0x10:0x14] = old_offset.to_bytes(4, "little")

    model = ConsoleMemoryModel("GBA")
    manager = RelocationManager(model)
    result = manager.relocate(rom, old_offset=old_offset, new_bytes=b"NOVA\x00")

    assert set(result.keys()) >= {
        "relocated",
        "reason",
        "old_offset",
        "new_offset",
        "bytes_written",
        "pointers_updated",
        "in_bounds",
        "within_free_space",
    }
    assert result["relocated"] is True
    assert result["in_bounds"] is True
    assert result["within_free_space"] is True
    assert result["new_offset"] + result["bytes_written"] <= len(rom)


def test_human_only_heuristica_entropia_e_estrutura():
    ok_1, reason_1 = classify_human_candidate(normalize_human_text("Nova Aventura"))
    ok_2, reason_2 = classify_human_candidate(
        normalize_human_text("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789...")
    )
    ok_3, reason_3 = classify_human_candidate(normalize_human_text("E}}}}}}}}}}"))
    ok_4, reason_4 = classify_human_candidate(normalize_human_text("Restaurar Aventura"))
    ok_5, reason_5 = classify_human_candidate(
        normalize_human_text("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~0123456789")
    )
    ok_6, reason_6 = classify_human_candidate(normalize_human_text("A B C D E"))
    ok_7, reason_7 = classify_human_candidate(normalize_human_text("F G H I J"))

    assert ok_1 is True
    assert reason_1 == "ok"
    assert ok_2 is False
    assert reason_2 == "charset_table"
    assert ok_3 is False
    assert reason_3 != "ok"
    assert ok_4 is True
    assert reason_4 == "ok"
    assert ok_5 is False
    assert reason_5 in {"charset_table", "low_linguistic_separators"}
    assert ok_6 is False
    assert reason_6 == "charset_table"
    assert ok_7 is False
    assert reason_7 == "charset_table"


def test_allowlist_fura_apenas_corte_min_offset():
    text = normalize_human_text("Restaurar Aventura")
    ok_human, reason_human = classify_human_candidate(text)
    assert ok_human is True
    assert reason_human == "ok"

    keep_without_allow, reason_without_allow = passes_min_offset_with_allowlist(
        offset=0x2000,
        text=text,
        min_offset=0x10000,
        allow_offsets=[],
        allow_regex=[],
    )
    assert keep_without_allow is False
    assert reason_without_allow == "min_offset"

    keep_with_allow, reason_with_allow = passes_min_offset_with_allowlist(
        offset=0x2000,
        text=text,
        min_offset=0x10000,
        allow_offsets=[0x2000],
        allow_regex=[],
    )
    assert keep_with_allow is True
    assert reason_with_allow == "allow_offset"


def test_allowlist_nao_ressuscita_charset():
    text = normalize_human_text("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789...")
    ok_human, reason_human = classify_human_candidate(text)
    assert ok_human is False
    assert reason_human == "charset_table"

    # Mesmo com allowlist para o offset, continua bloqueado na heurística humana.
    keep_with_allow, reason_with_allow = passes_min_offset_with_allowlist(
        offset=0x2000,
        text=text,
        min_offset=0x10000,
        allow_offsets=[0x2000],
        allow_regex=["[A-Z]{5,}"],
    )
    assert keep_with_allow is True
    assert reason_with_allow in {"allow_offset", "allow_regex"}
    final_keep = bool(ok_human and keep_with_allow)
    assert final_keep is False


def test_normalizacao_remove_prefixo_tecnico_e_controle():
    normalized = normalize_human_text("zTorches\x01")
    assert normalized == "Torches"
    ok, reason = classify_human_candidate(normalized)
    assert ok is True
    assert reason == "ok"

    escaped = normalize_human_text("{Awaken")
    assert escaped == "Awaken"

    pref = normalize_human_text("IH OI MOONGLOW")
    assert pref == "MOONGLOW"
    pref_num = normalize_human_text("6 MC GI HONOR")
    assert pref_num == "HONOR"

    suff = normalize_human_text("SLEEP B D")
    assert suff == "SLEEP"
    suff_code = normalize_human_text("MANDRAKE KFGE")
    assert suff_code == "MANDRAKE"

    # Não deve destruir frase humana curta válida.
    human = normalize_human_text("I AM DEAD")
    assert human == "I AM DEAD"

    bad_short, bad_reason = classify_human_candidate(normalize_human_text("AB E"))
    assert bad_short is False
    assert bad_reason == "tokenish"


def test_human_only_rejeita_fragmentos_tecnicos_residuais():
    samples = [
        ("I J", {"spaced_single_letters", "tokenish"}),
        ("! ? END", {"end_marker", "punct_prefix_fragment", "tokenish"}),
        ("HHx XX`", {"rare_symbol", "tokenish"}),
        ("'t own any.", {"leading_apostrophe_fragment", "tokenish"}),
        ("Ko&", {"short_symbol_fragment", "rare_symbol", "tokenish"}),
        ("Ho.", {"short_symbol_fragment", "tokenish"}),
        ("ABCDE H", {"alphabet_tail_fragment", "tokenish", "charset_table"}),
    ]
    for raw, expected_reasons in samples:
        normalized = normalize_human_text(raw)
        ok, reason = classify_human_candidate(normalized)
        assert ok is False
        assert reason in expected_reasons

    ok_phrase, reason_phrase = classify_human_candidate(normalize_human_text("Oh... please..."))
    assert ok_phrase is True
    assert reason_phrase == "ok"

    ok_dialog, reason_dialog = classify_human_candidate(
        normalize_human_text("he sayeth 'CAH'.")
    )
    assert ok_dialog is True
    assert reason_dialog == "ok"
