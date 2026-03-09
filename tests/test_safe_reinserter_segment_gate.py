import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.safe_reinserter import SafeReinserter


def _make_charset(tmp_path: Path, chars: str) -> None:
    out = tmp_path / "inferred_charsets"
    out.mkdir(parents=True, exist_ok=True)
    char_to_byte = {}
    used = set()
    value = 1
    for ch in chars:
        if ch in used:
            continue
        used.add(ch)
        char_to_byte[ch] = f"{value & 0xFF:02X}"
        value += 1
    payload = {
        "name": "test_charset",
        "confidence": 1.0,
        "char_to_byte": char_to_byte,
    }
    (out / "charset_candidate_test.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _build_reinserter(
    tmp_path: Path,
    *,
    decoded_text: str = "HELLO",
    translated_text: str = "HELLO",
    length: int = 24,
    terminator: int = 0x00,
    accent_fallback: bool = False,
    quality_mode: str = "standard",
    register_policy: str = "voce",
    semantic_glossary: dict | None = None,
    charset_chars: str | None = None,
    pointer_refs: list[dict] | None = None,
    entry_patch: dict | None = None,
    mappings: list[dict] | None = None,
    translations: dict[int, str] | None = None,
) -> tuple[SafeReinserter, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    rom_path = tmp_path / "game.sms"
    rom_path.write_bytes(b"\xFF" * 0x8000)

    if mappings is None:
        entry = {
            "uid": "U_00001",
            "offset_dec": 0x0200,
            "length": int(length),
            "terminator": int(terminator) & 0xFF,
            "pointer_refs": list(pointer_refs or []),
            "source": decoded_text,
            "box_width": 40,
            "max_lines": 3,
        }
        if entry_patch:
            entry.update(entry_patch)
        mappings = [entry]

    extraction = {
        "console": "SMS",
        "quality_mode": str(quality_mode),
        "register_policy": str(register_policy),
        "accent_policy": {
            "allow_fallback": bool(accent_fallback),
            "explicit_map": {},
        },
        "mappings": mappings,
    }
    if semantic_glossary:
        extraction["glossary"] = semantic_glossary
    extraction_path = tmp_path / "extract.json"
    extraction_path.write_text(
        json.dumps(extraction, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if charset_chars is not None:
        _make_charset(tmp_path, charset_chars)

    reinserter = SafeReinserter(str(rom_path), str(extraction_path))
    out_rom = tmp_path / "out.sms"
    payload = translations if translations is not None else {1: translated_text}
    reinserter.reinsert_translations(
        payload,
        output_path=str(out_rom),
        create_backup=False,
    )
    return reinserter, out_rom


def test_glyph_coverage_ptbr_completo(tmp_path: Path):
    chars = (
        " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        "áàâãäéêíóôõúüçÁÀÂÃÄÉÊÍÓÔÕÚÜÇ.,;:!?-'/()%[]{}<>\""
    )
    reinserter, _ = _build_reinserter(
        tmp_path,
        decoded_text="AÇÃO",
        translated_text="AÇÃO ÚNICA",
        length=40,
        charset_chars=chars,
    )
    seg = reinserter.segment_audit_rows[0]
    assert seg["ptbr_full_coverage"] is True
    assert seg["glyphs_ok"] is True
    assert seg["fallback_applied"] is False
    assert seg["status"] == "REINSERTED_IN_PLACE"


def test_glyph_coverage_parcial_sem_fallback_aborta(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,;:!?-'/()%[]{}<>\""
    reinserter, _ = _build_reinserter(
        tmp_path,
        translated_text="ação",
        length=40,
        accent_fallback=False,
        charset_chars=chars,
    )
    seg = reinserter.segment_audit_rows[0]
    assert seg["glyphs_ok"] is False
    assert seg["fallback_applied"] is False
    assert seg["status"].startswith("ABORTED")


def test_fallback_de_acento_ligado(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,;:!?-'/()%[]{}<>\""
    reinserter, _ = _build_reinserter(
        tmp_path,
        translated_text="ação",
        length=40,
        accent_fallback=True,
        charset_chars=chars,
    )
    seg = reinserter.segment_audit_rows[0]
    assert seg["status"] == "REINSERTED_IN_PLACE"
    assert seg["fallback_applied"] is True
    assert seg["renderable_text"] == "acao"
    assert seg["fallback_changes"]


def test_preservacao_tokens_placeholders_e_terminador(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789{}<>%"
    reinserter, out_rom = _build_reinserter(
        tmp_path,
        decoded_text="HP {NUM} <1F>",
        translated_text="HP {NUM} <1F>",
        length=32,
        terminator=0x7F,
        charset_chars=chars,
    )
    seg = reinserter.segment_audit_rows[0]
    assert seg["tokens_ok"] is True
    assert seg["terminator_ok"] is True
    assert seg["status"] == "REINSERTED_IN_PLACE"
    mapping = json.loads((tmp_path / f"{reinserter.original_crc32}_reinsertion_mapping.json").read_text(encoding="utf-8"))
    assert mapping[0]["terminator_preserved"] is True
    assert Path(out_rom).exists()


def test_preservacao_tokens_falha_quando_placeholder_some(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789{}<>%"
    reinserter, _ = _build_reinserter(
        tmp_path,
        decoded_text="HP {NUM} <1F>",
        translated_text="HP 10",
        length=32,
        charset_chars=chars,
    )
    seg = reinserter.segment_audit_rows[0]
    assert seg["tokens_ok"] is False
    assert seg["status"].startswith("ABORTED")


def test_layout_que_cabe_e_layout_que_nao_cabe(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    ok_reinserter, _ = _build_reinserter(
        tmp_path / "ok",
        translated_text="LINHA CURTA",
        length=32,
        charset_chars=chars,
        entry_patch={"box_width": 32, "max_lines": 2},
    )
    ok_seg = ok_reinserter.segment_audit_rows[0]
    assert ok_seg["layout_ok"] is True
    assert ok_seg["status"] == "REINSERTED_IN_PLACE"

    bad_reinserter, _ = _build_reinserter(
        tmp_path / "bad",
        translated_text="TEXTO MUITO GRANDE PARA CAIXA",
        length=64,
        charset_chars=chars,
        entry_patch={"box_width": 8, "max_lines": 1},
    )
    bad_seg = bad_reinserter.segment_audit_rows[0]
    assert bad_seg["layout_ok"] is False
    assert bad_seg["status"].startswith("ABORTED")


def test_layout_tenta_variante_curta_existente(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    reinserter, _ = _build_reinserter(
        tmp_path,
        translated_text="TEXTO MUITO GRANDE PARA CAIXA",
        length=64,
        charset_chars=chars,
        entry_patch={"box_width": 8, "max_lines": 1, "short_variants": ["CURTO"]},
    )
    seg = reinserter.segment_audit_rows[0]
    assert seg["layout_ok"] is True
    assert seg["renderable_text"] == "CURTO"
    assert seg["status"] == "REINSERTED_IN_PLACE"


def test_byte_length_valido(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    reinserter, _ = _build_reinserter(
        tmp_path,
        translated_text="ABC",
        length=8,
        charset_chars=chars,
    )
    seg = reinserter.segment_audit_rows[0]
    assert seg["byte_length_ok"] is True
    assert seg["status"] == "REINSERTED_IN_PLACE"


def test_byte_length_excedido_com_realocacao_e_update_de_ponteiro(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    pointer_refs = [
        {
            "ptr_offset": "0x000010",
            "ptr_size": 2,
            "endianness": "little",
            "addressing_mode": "ABSOLUTE",
            "base": "0x0000",
            "addend": 0,
        }
    ]
    reinserter, _ = _build_reinserter(
        tmp_path,
        translated_text="TEXTO GRANDE DEMAIS",
        length=6,
        charset_chars=chars,
        pointer_refs=pointer_refs,
    )
    seg = reinserter.segment_audit_rows[0]
    assert seg["status"] == "REINSERTED_RELOCATED"
    assert int(seg["updated_pointers"]) >= 1
    assert int(seg["final_offset"]) != int(seg["start_offset"])
    ptr_value = int.from_bytes(reinserter.rom_data[0x10:0x12], "little")
    assert ptr_value == (int(seg["final_offset"]) & 0xFFFF)


def test_segmento_abortado_quando_qualquer_validacao_falha(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    reinserter, _ = _build_reinserter(
        tmp_path,
        translated_text="texto com emoji 😃",
        length=64,
        accent_fallback=False,
        charset_chars=chars,
    )
    seg = reinserter.segment_audit_rows[0]
    assert seg["status"].startswith("ABORTED")
    assert any(not bool(seg.get(flag, False)) for flag in SafeReinserter.REQUIRED_GATE_FLAGS)


def test_quality_gate_bloqueia_score_baixo_mesmo_sem_overflow(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?-'/()%[]{}<>\""
    reinserter, _ = _build_reinserter(
        tmp_path,
        decoded_text="Press start to continue",
        translated_text="???? ? ? ?",
        length=32,
        charset_chars=chars,
    )
    seg = reinserter.segment_audit_rows[0]
    assert seg["final_audit_pass"] is False
    assert seg["blocked_by_quality_gate"] is True
    assert seg["quality_score"] < 75
    assert seg["status"].startswith("ABORTED")


def test_quality_mode_strict_bloqueia_faixa_suspeita(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?-'/()%[]{}<>\""
    reinserter, _ = _build_reinserter(
        tmp_path,
        decoded_text="Press start",
        translated_text="Press 1234 start 99",
        length=64,
        quality_mode="strict",
        charset_chars=chars,
    )
    seg = reinserter.segment_audit_rows[0]
    assert seg["quality_mode"] == "strict"
    assert 75 <= float(seg["quality_score"]) < 90
    assert seg["final_audit_pass"] is False
    assert seg["blocked_by_quality_gate"] is True
    assert seg["status"].startswith("ABORTED")


def test_failure_reason_score_coerente_com_threshold_real_no_strict(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?-'/()%[]{}<>\""
    reinserter, _ = _build_reinserter(
        tmp_path,
        decoded_text="Press start to continue",
        translated_text="Press  start to continue!!!",
        length=64,
        quality_mode="strict",
        charset_chars=chars,
    )
    seg = reinserter.segment_audit_rows[0]
    assert seg["blocked_by_quality_gate"] is True
    assert seg["quality_block_kind"] == "score"
    assert seg["absolute_block_reasons"] == []
    assert float(seg["quality_threshold_used"]) == 90.0
    assert float(seg["quality_score"]) < float(seg["quality_threshold_used"])
    reason = str(seg["failure_reason"])
    assert reason.startswith("quality_gate_failed:score:")
    assert "<90.00" in reason
    assert "mode=strict" in reason


def test_failure_reason_por_flag_absoluta_nao_reporta_como_score(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?-'/()%[]{}<>\""
    reinserter, _ = _build_reinserter(
        tmp_path,
        decoded_text="Fleeing!",
        translated_text=":Fugindo!",
        length=40,
        quality_mode="standard",
        charset_chars=chars,
    )
    seg = reinserter.segment_audit_rows[0]
    assert seg["blocked_by_quality_gate"] is True
    assert seg["quality_block_kind"] == "absolute"
    assert "fragment_suspect" in list(seg.get("absolute_block_reasons", []))
    reason = str(seg["failure_reason"])
    assert reason.startswith("quality_gate_failed:absolute:")
    assert "score:" not in reason
    assert "<" not in reason


def test_quality_scores_exportados_no_mapping_report_proof(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?-'/()%[]{}<>\""
    reinserter, _ = _build_reinserter(
        tmp_path,
        decoded_text="FALAR",
        translated_text="FALAR",
        length=24,
        charset_chars=chars,
    )
    crc = reinserter.original_crc32
    mapping = json.loads((tmp_path / f"{crc}_reinsertion_mapping.json").read_text(encoding="utf-8"))
    row = mapping[0]
    assert "technical_score" in row
    assert "visual_score" in row
    assert "linguistic_score" in row
    assert "quality_score" in row
    assert "quality_mode" in row
    assert "quality_threshold_used" in row
    assert "absolute_block_reasons" in row
    assert "final_audit_pass" in row
    assert "blocked_by_quality_gate" in row
    assert "failure_reason" in row

    report = (tmp_path / f"{crc}_report.txt").read_text(encoding="utf-8")
    assert "QUALITY_MODE:" in report
    assert "QUALITY_THRESHOLD_USED:" in report
    assert "QUALITY_PASS:" in report
    assert "QUALITY_BLOCKED:" in report
    assert "TECHNICAL_SCORE_AVG:" in report
    assert "VISUAL_SCORE_AVG:" in report
    assert "LINGUISTIC_SCORE_AVG:" in report
    assert "ABSOLUTE_BLOCK_REASONS:" in report

    proof = json.loads((tmp_path / f"{crc}_proof.json").read_text(encoding="utf-8"))
    assert "quality_mode" in proof
    assert "quality_threshold_used" in proof
    assert "quality_pass" in proof
    assert "quality_blocked" in proof
    assert any("quality_score" in s for s in proof.get("segments", []))
    assert any("quality_threshold_used" in s for s in proof.get("segments", []))
    assert any("absolute_block_reasons" in s for s in proof.get("segments", []))


def test_coerencia_score_threshold_mode_e_failure_reason_nos_failures(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?-'/()%[]{}<>\""
    reinserter, _ = _build_reinserter(
        tmp_path,
        decoded_text="Press start to continue",
        translated_text="Press  start to continue!!!",
        length=64,
        quality_mode="strict",
        charset_chars=chars,
    )
    crc = reinserter.original_crc32
    proof = json.loads((tmp_path / f"{crc}_proof.json").read_text(encoding="utf-8"))
    failures = proof.get("failures", [])
    assert failures
    seg = failures[0]
    assert bool(seg.get("blocked_by_quality_gate", False)) is True
    reason = str(seg.get("failure_reason", ""))
    threshold = float(seg.get("quality_threshold_used", 0.0))
    mode = str(seg.get("quality_mode", ""))
    score = float(seg.get("quality_score", 0.0))
    abs_reasons = list(seg.get("absolute_block_reasons", []) or [])
    if reason.startswith("quality_gate_failed:absolute:"):
        assert abs_reasons
    elif reason.startswith("quality_gate_failed:score:"):
        assert not abs_reasons
        m = re.search(r"score:([0-9]+(?:\.[0-9]+)?)<([0-9]+(?:\.[0-9]+)?)", reason)
        assert m is not None
        score_from_reason = float(m.group(1))
        threshold_from_reason = float(m.group(2))
        assert abs(score_from_reason - score) < 0.01
        assert abs(threshold_from_reason - threshold) < 0.01
        assert score < threshold
        assert f"mode={mode}" in reason
    else:
        raise AssertionError(f"failure_reason inesperado: {reason}")


def test_semantic_gate_bloqueia_nome_proprio_corrompido(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?-'/()%[]{}<>\""
    reinserter, _ = _build_reinserter(
        tmp_path,
        decoded_text="Mys.Robe",
        translated_text="Meus Robos",
        length=48,
        quality_mode="strict",
        charset_chars=chars,
    )
    seg = reinserter.segment_audit_rows[0]
    assert seg["blocked_by_quality_gate"] is True
    assert seg["proper_noun_corruption"] is True
    assert seg["status"].startswith("ABORTED")


def test_semantic_gate_bloqueia_alucinacao_semantica(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?-'/()%[]{}<>\""
    reinserter, _ = _build_reinserter(
        tmp_path,
        decoded_text="Ealing",
        translated_text="Ealing e um bairro de Londres",
        length=64,
        quality_mode="strict",
        charset_chars=chars,
    )
    seg = reinserter.segment_audit_rows[0]
    assert seg["blocked_by_quality_gate"] is True
    assert seg["semantic_hallucination_suspect"] is True
    assert seg["status"].startswith("ABORTED")


def test_semantic_gate_bloqueia_violacao_de_glossario(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?-'/()%[]{}<>\""
    glossary = {
        "Honesty": {
            "target": "Honestidade",
            "category": "virtue",
            "preserve": False,
            "allow_translation": True,
            "enforce": True,
        }
    }
    reinserter, _ = _build_reinserter(
        tmp_path,
        decoded_text="Honesty",
        translated_text="Sinceridade",
        length=48,
        quality_mode="strict",
        charset_chars=chars,
        semantic_glossary=glossary,
    )
    seg = reinserter.segment_audit_rows[0]
    assert seg["blocked_by_quality_gate"] is True
    assert seg["glossary_violation"] is True
    assert "glossary_violation" in list(seg.get("absolute_block_reasons", []))


def test_semantic_gate_bloqueia_inconsistencia_de_registro(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?-'/()%[]{}<>\""
    reinserter, _ = _build_reinserter(
        tmp_path,
        decoded_text="Can you help me?",
        translated_text="Tu podes ajudar?",
        length=64,
        quality_mode="strict",
        register_policy="voce",
        charset_chars=chars,
    )
    seg = reinserter.segment_audit_rows[0]
    assert seg["blocked_by_quality_gate"] is True
    assert seg["register_inconsistency"] is True


def test_semantic_gate_bloqueia_ingles_residual(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?-'/()%[]{}<>\""
    reinserter, _ = _build_reinserter(
        tmp_path,
        decoded_text="Open the door",
        translated_text="Open the door",
        length=64,
        quality_mode="standard",
        charset_chars=chars,
    )
    seg = reinserter.segment_audit_rows[0]
    assert seg["blocked_by_quality_gate"] is True
    assert seg["english_residue"] is True
    assert seg["status"].startswith("ABORTED")


def test_semantic_gate_aceita_segmento_fiel_com_glossario(tmp_path: Path):
    chars = (
        " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        "áàâãäéêíóôõúüçÁÀÂÃÄÉÊÍÓÔÕÚÜÇ0123456789.,;:!?-'/()%[]{}<>\""
    )
    glossary = {
        "Honesty": {
            "target": "Honestidade",
            "category": "virtue",
            "preserve": False,
            "allow_translation": True,
            "enforce": True,
        },
        "Mys.Robe": {
            "target": "Mys.Robe",
            "category": "npc",
            "preserve": True,
            "allow_translation": False,
            "enforce": True,
        },
    }
    reinserter, _ = _build_reinserter(
        tmp_path,
        decoded_text="Mys.Robe seeks Honesty",
        translated_text="Mys.Robe busca Honestidade",
        length=96,
        quality_mode="strict",
        charset_chars=chars,
        semantic_glossary=glossary,
    )
    seg = reinserter.segment_audit_rows[0]
    assert seg["status"].startswith("REINSERTED")
    assert seg["semantic_quality_gate_pass"] is True
    assert seg["glossary_violation"] is False
    assert seg["proper_noun_corruption"] is False


def test_text_inventory_marca_cobertura_incompleta_quando_falta_traducao(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?-'/()%[]{}<>\""
    mappings = [
        {
            "uid": "U_00001",
            "id": 1,
            "offset_dec": 0x0200,
            "length": 32,
            "terminator": 0x00,
            "pointer_refs": [],
            "source": "HELLO",
            "box_width": 40,
            "max_lines": 3,
        },
        {
            "uid": "U_00002",
            "id": 2,
            "offset_dec": 0x0240,
            "length": 32,
            "terminator": 0x00,
            "pointer_refs": [],
            "source": "BYE",
            "box_width": 40,
            "max_lines": 3,
        },
    ]
    reinserter, _ = _build_reinserter(
        tmp_path,
        mappings=mappings,
        translations={1: "OLA"},
        translated_text="OLA",
        charset_chars=chars,
    )
    crc = reinserter.original_crc32
    inv_json = tmp_path / f"{crc}_text_inventory.json"
    inv_txt = tmp_path / f"{crc}_text_inventory.txt"
    inv_proof = tmp_path / f"{crc}_text_inventory_proof.json"
    assert inv_json.exists()
    assert inv_txt.exists()
    assert inv_proof.exists()

    inv = json.loads(inv_json.read_text(encoding="utf-8"))
    assert inv["coverage_incomplete"] is True
    assert int(inv["total_untranslated"]) == 1
    assert int((inv.get("counts_by_status", {}) or {}).get("untranslated", 0)) == 1
    assert any(s.get("status") == "untranslated" for s in inv.get("segments", []))

    report = (tmp_path / f"{crc}_report.txt").read_text(encoding="utf-8")
    assert "COVERAGE_INCOMPLETE: true" in report


def test_text_inventory_cobertura_completa_quando_tudo_reinserido(tmp_path: Path):
    chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?-'/()%[]{}<>\""
    mappings = [
        {
            "uid": "U_00001",
            "id": 1,
            "offset_dec": 0x0200,
            "length": 32,
            "terminator": 0x00,
            "pointer_refs": [],
            "source": "HELLO",
            "box_width": 40,
            "max_lines": 3,
        },
        {
            "uid": "U_00002",
            "id": 2,
            "offset_dec": 0x0240,
            "length": 32,
            "terminator": 0x00,
            "pointer_refs": [],
            "source": "BYE",
            "box_width": 40,
            "max_lines": 3,
        },
    ]
    reinserter, _ = _build_reinserter(
        tmp_path,
        mappings=mappings,
        translations={1: "OLA", 2: "TCHAU"},
        translated_text="OLA",
        charset_chars=chars,
    )
    crc = reinserter.original_crc32
    inv = json.loads((tmp_path / f"{crc}_text_inventory.json").read_text(encoding="utf-8"))
    assert inv["coverage_incomplete"] is False
    assert int(inv["total_untranslated"]) == 0
    assert int((inv.get("counts_by_status", {}) or {}).get("inserted", 0)) == 2
