import json
import zlib
from pathlib import Path

import pytest

from core.sega_reinserter import SegaMasterSystemReinserter, ReinsertionError, SegaReinserter


def _write_mapping(path: Path, entry: dict) -> Path:
    data = {"entries": {"1": entry}}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _write_translated(path: Path, text: str) -> Path:
    content = "[1]\n" + text + "\n-----\n"
    path.write_text(content, encoding="utf-8")
    return path


def _write_rom(path: Path, size: int = 64) -> Path:
    path.write_bytes(b"\xFF" * size)
    return path


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return path


def test_reinsert_in_place_creates_backup_and_report(tmp_path: Path):
    rom_path = _write_rom(tmp_path / "game.sms", 64)
    mapping_path = _write_mapping(
        tmp_path / "map.json",
        {
            "offset": 16,
            "max_len": 5,
            "category": "DIALOG",
            "has_pointer": False,
            "pointer_offsets": [],
            "terminator": 0,
            "encoding": "ascii",
            "reinsertion_safe": True,
        },
    )
    translated_path = _write_translated(tmp_path / "translated.txt", "HELLO")

    reinserter = SegaMasterSystemReinserter()
    out_path, stats = reinserter.apply_translation(
        rom_path=rom_path,
        translated_path=translated_path,
        mapping_path=mapping_path,
        output_rom_path=tmp_path / "out.sms",
        create_backup=True,
    )

    assert out_path.exists()
    assert (tmp_path / "game.sms.bak").exists()
    assert stats["OK"] == 1

    data = out_path.read_bytes()
    assert data[16:19] == b"OLA"

    out_dir = tmp_path / "out"
    report_candidates = list(out_dir.glob("*_reinsertion_report.json"))
    assert report_candidates
    report = json.loads(report_candidates[0].read_text(encoding="utf-8"))
    assert report["stats"]["OK"] == 1
    assert list(out_dir.glob("*_report.txt"))
    assert list(out_dir.glob("*_proof.json"))


def test_reinsert_truncates_by_default(tmp_path: Path):
    rom_path = _write_rom(tmp_path / "game.sms", 64)
    mapping_path = _write_mapping(
        tmp_path / "map.json",
        {
            "offset": 8,
            "max_len": 4,
            "category": "DIALOG",
            "has_pointer": False,
            "pointer_offsets": [],
            "terminator": 0,
            "encoding": "ascii",
            "reinsertion_safe": True,
        },
    )
    translated_path = _write_translated(tmp_path / "translated.txt", "TOOLONG")

    reinserter = SegaMasterSystemReinserter()
    out_path, stats = reinserter.apply_translation(
        rom_path=rom_path,
        translated_path=translated_path,
        mapping_path=mapping_path,
        output_rom_path=tmp_path / "out.sms",
        create_backup=False,
    )

    # Nova estratégia: reformula/abrevia antes de truncar.
    assert stats["TRUNC"] == 0
    assert stats["REFORM"] >= 1
    data = out_path.read_bytes()
    inserted = data[8:12]
    assert inserted.strip(b"\x00")
    assert len(inserted) == 4


def test_reinsert_strict_aborts(tmp_path: Path):
    rom_path = _write_rom(tmp_path / "game.sms", 64)
    mapping_path = _write_mapping(
        tmp_path / "map.json",
        {
            "offset": 8,
            "max_len": 4,
            "category": "DIALOG",
                "has_pointer": False,
                "pointer_offsets": [],
                "terminator": 0,
                "encoding": "ascii",
                "reinsertion_safe": False,
            },
        )
    translated_path = _write_translated(tmp_path / "translated.txt", "TOOLONG")

    reinserter = SegaMasterSystemReinserter()
    with pytest.raises(ReinsertionError):
        reinserter.apply_translation(
            rom_path=rom_path,
            translated_path=translated_path,
            mapping_path=mapping_path,
            output_rom_path=tmp_path / "out.sms",
            strict=True,
        )


def test_reinsert_dry_run_does_not_write(tmp_path: Path):
    rom_path = _write_rom(tmp_path / "game.sms", 64)
    mapping_path = _write_mapping(
        tmp_path / "map.json",
        {
            "offset": 10,
            "max_len": 3,
            "category": "DIALOG",
            "has_pointer": False,
            "pointer_offsets": [],
            "terminator": 0,
            "encoding": "ascii",
            "reinsertion_safe": True,
        },
    )
    translated_path = _write_translated(tmp_path / "translated.txt", "ABC")

    reinserter = SegaMasterSystemReinserter()
    out_path, _ = reinserter.apply_translation(
        rom_path=rom_path,
        translated_path=translated_path,
        mapping_path=mapping_path,
        output_rom_path=tmp_path / "out.sms",
        dry_run=True,
    )

    assert not out_path.exists()
    assert not (tmp_path / "game.sms.bak").exists()
    out_dir = tmp_path / "out"
    assert list(out_dir.glob("*_reinsertion_report.json"))


def test_reinsert_jsonl_without_meta_hard_fails(tmp_path: Path):
    rom_path = _write_rom(tmp_path / "game.sms", 96)
    mapping_path = _write_mapping(
        tmp_path / "map.json",
        {
            "offset": 12,
            "max_len": 5,
            "category": "DIALOG",
            "has_pointer": False,
            "pointer_offsets": [],
            "terminator": 0,
            "encoding": "ascii",
            "reinsertion_safe": True,
        },
    )
    translated_path = _write_jsonl(
        tmp_path / "translated_fixed_ptbr.jsonl",
        [
            {
                "id": 1,
                "seq": 0,
                "offset": "0x00000C",
                "text_dst": "HELLO",
            }
        ],
    )

    wrapper = SegaReinserter(str(rom_path))
    translations = wrapper.load_translations(str(translated_path))
    ok, msg = wrapper.reinsert(translations, str(tmp_path / "out.sms"), mapping_path=str(mapping_path))

    assert not ok
    assert "metadados obrigatórios" in msg


def test_reinsert_jsonl_with_meta_generates_checks(tmp_path: Path):
    rom_path = _write_rom(tmp_path / "game.sms", 128)
    rom_data = rom_path.read_bytes()
    rom_crc32 = f"{zlib.crc32(rom_data) & 0xFFFFFFFF:08X}"
    rom_size = len(rom_data)

    map_data = {
        "entries": {
            "1": {
                "offset": 10,
                "max_len": 5,
                "category": "DIALOG",
                "has_pointer": False,
                "pointer_offsets": [],
                "terminator": 0,
                "encoding": "ascii",
                "reinsertion_safe": True,
            },
            "2": {
                "offset": 20,
                "max_len": 5,
                "category": "DIALOG",
                "has_pointer": False,
                "pointer_offsets": [],
                "terminator": 0,
                "encoding": "ascii",
                "reinsertion_safe": True,
            },
        }
    }
    mapping_path = tmp_path / "map.json"
    mapping_path.write_text(json.dumps(map_data, indent=2), encoding="utf-8")

    translated_path = _write_jsonl(
        tmp_path / "translated_fixed_ptbr.jsonl",
        [
            {
                "type": "meta",
                "rom_crc32": rom_crc32,
                "rom_size": rom_size,
                "ordering": "seq/rom_offset",
            },
            {
                "id": 2,
                "seq": 1,
                "offset": "0x000014",
                "text_dst": "WORLD",
                "rom_crc32": rom_crc32,
                "rom_size": rom_size,
            },
            {
                "id": 1,
                "seq": 0,
                "offset": "0x00000A",
                "text_dst": "HELLO",
                "rom_crc32": rom_crc32,
                "rom_size": rom_size,
            },
        ],
    )

    wrapper = SegaReinserter(str(rom_path))
    translations = wrapper.load_translations(str(translated_path))
    ok, msg = wrapper.reinsert(translations, str(tmp_path / "patched.sms"), mapping_path=str(mapping_path))
    assert ok, msg

    out_dir = tmp_path / "out"
    proof_files = list(out_dir.glob("*_proof.json"))
    assert proof_files
    proof = json.loads(proof_files[0].read_text(encoding="utf-8"))
    assert "ordering_check" in proof
    assert "coverage_check" in proof
    assert "input_match_check" in proof
    assert proof["input_match_check"]["rom_crc32_match"] is True
    assert proof["input_match_check"]["rom_size_match"] is True
    assert proof["ordering_check"]["is_sorted_by_offset"] is True


def test_incremental_delta_generates_delta_jsonl_and_before_after_metrics(tmp_path: Path):
    rom_path = _write_rom(tmp_path / "game.sms", 128)
    rom_data = rom_path.read_bytes()
    rom_crc32 = f"{zlib.crc32(rom_data) & 0xFFFFFFFF:08X}"
    rom_size = len(rom_data)

    mapping_path = _write_mapping(
        tmp_path / "map.json",
        {
            "offset": 12,
            "max_len": 5,
            "category": "DIALOG",
            "has_pointer": False,
            "pointer_offsets": [],
            "terminator": 0,
            "encoding": "ascii",
            "reinsertion_safe": True,
        },
    )

    translated_path = _write_jsonl(
        tmp_path / "translated_fixed_ptbr.jsonl",
        [
            {
                "type": "meta",
                "rom_crc32": rom_crc32,
                "rom_size": rom_size,
                "ordering": "seq/rom_offset",
            },
            {
                "id": 1,
                "seq": 0,
                "offset": "0x00000C",
                "rom_offset": "0x00000C",
                "text_src": "HELLO",
                "text_dst": "HELLO",
                "max_len_bytes": 5,
                "terminator": 0,
                "encoding": "ascii",
                "rom_crc32": rom_crc32,
                "rom_size": rom_size,
            },
        ],
    )

    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{rom_crc32}_proof.json").write_text("{}", encoding="utf-8")

    wrapper = SegaReinserter(str(rom_path))
    translations = wrapper.load_translations(str(translated_path))
    ok, msg = wrapper.reinsert(
        translations,
        str(tmp_path / "patched.sms"),
        mapping_path=str(mapping_path),
    )
    assert ok, msg

    delta_path = tmp_path / "translated_fixed_ptbr_delta.jsonl"
    assert delta_path.exists()
    delta_rows = []
    for ln in delta_path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln:
            delta_rows.append(json.loads(ln))
    assert len(delta_rows) >= 2
    assert delta_rows[1]["id"] == 1
    assert delta_rows[1]["seq"] == 0
    assert delta_rows[1]["rom_offset"] == "0x00000C"

    proof_path = out_dir / f"{rom_crc32}_proof.json"
    report_txt_path = out_dir / f"{rom_crc32}_report.txt"
    report_json_path = out_dir / f"{rom_crc32}_reinsertion_report.json"
    assert proof_path.exists()
    assert report_txt_path.exists()
    assert report_json_path.exists()

    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    assert proof.get("delta_incremental", {}).get("enabled") is True
    assert "before" in proof.get("delta_incremental", {})
    assert "after" in proof.get("delta_incremental", {})
    assert "issue_index" in proof

    report_txt = report_txt_path.read_text(encoding="utf-8")
    assert "DELTA_INCREMENTAL:" in report_txt
    assert "before_counts=" in report_txt
    assert "after_counts=" in report_txt

    report_json = json.loads(report_json_path.read_text(encoding="utf-8"))
    assert report_json.get("stats", {}).get("TRUNC", 0) == 0
    assert report_json.get("stats", {}).get("BLOCKED", 0) == 0


def test_repoint_rejects_pointer_inside_text_and_preserves_source_bytes(tmp_path: Path):
    rom_path = _write_rom(tmp_path / "game.sms", 256)
    rom = bytearray(rom_path.read_bytes())
    # key=316 (offset=0x20): texto sensível usado na regressão
    rom[0x20:0x29] = b"Mys.Robe\x00"
    # key=319 (offset=0x30): texto curto que precisará de REPOINT
    rom[0x30:0x35] = b"Keys\x00"
    # ponteiro seguro fora da área de texto (2 bytes LE -> 0x0030)
    rom[0x40:0x42] = (0x30).to_bytes(2, "little")
    rom_path.write_bytes(bytes(rom))

    mapping_path = tmp_path / "map.json"
    map_data = {
        "entries": {
            "316": {
                "offset": 0x20,
                "max_len": 8,
                "category": "DIALOG",
                "has_pointer": True,
                "pointer_offsets": [],
                "pointer_refs": [
                    {
                        "ptr_offset": 0x50,
                        "ptr_size": 2,
                        "endianness": "little",
                        "addressing_mode": "ABSOLUTE",
                        "bank_addend": 0,
                    }
                ],
                "terminator": 0,
                "encoding": "ascii",
                "reinsertion_safe": True,
            },
            "319": {
                "offset": 0x30,
                "max_len": 4,
                "category": "DIALOG",
                "has_pointer": True,
                "pointer_offsets": [0x23, 0x40],
                "pointer_refs": [
                    {
                        # ponteiro INVÁLIDO: cai dentro da string de key=316
                        "ptr_offset": 0x23,
                        "ptr_size": 2,
                        "endianness": "little",
                        "addressing_mode": "ABSOLUTE",
                        "bank_addend": 0,
                    },
                    {
                        # ponteiro VÁLIDO: fora de área de texto
                        "ptr_offset": 0x40,
                        "ptr_size": 2,
                        "endianness": "little",
                        "addressing_mode": "ABSOLUTE",
                        "bank_addend": 0,
                    },
                ],
                "terminator": 0,
                "encoding": "ascii",
                "reinsertion_safe": True,
            },
        }
    }
    mapping_path.write_text(json.dumps(map_data, indent=2), encoding="utf-8")

    translated_path = tmp_path / "translated.txt"
    translated_path.write_text(
        "[316]\nMys.Robe\n-----\n[319]\nCHAVEZZ\n-----\n",
        encoding="utf-8",
    )

    reinserter = SegaMasterSystemReinserter()
    out_path, stats = reinserter.apply_translation(
        rom_path=rom_path,
        translated_path=translated_path,
        mapping_path=mapping_path,
        output_rom_path=tmp_path / "out.sms",
        create_backup=False,
    )

    patched = out_path.read_bytes()
    # Regressão: bytes da string em 0x20 NÃO podem ser corrompidos por escrita de ponteiro.
    assert patched[0x20:0x29] == b"Mys.Robe\x00"
    assert patched[0x23:0x25] == b".R"
    # Ponteiro seguro deve ser atualizado no REPOINT.
    assert patched[0x40:0x42] != (0x30).to_bytes(2, "little")
    assert stats.get("REPOINT", 0) >= 1
    assert stats.get("PTR_REF_REJECTED_TEXT_OVERLAP", 0) >= 1


def test_snes_platform_overrides_enable_archaic_english_cleanup(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("NEUROROM_SNES_BOX_COLS", raising=False)
    monkeypatch.delenv("NEUROROM_DIALOG_BOX_COLS", raising=False)
    monkeypatch.delenv("NEUROROM_SMS_BOX_COLS", raising=False)

    reinserter = SegaMasterSystemReinserter()
    reinserter.set_target_rom("sample.smc")

    assert reinserter._target_platform == "SNES"
    assert reinserter._contains_english_stopwords("Art thou male or female ?") is True

    rewritten = reinserter._fragment_autotranslate_pt("Art thou male or female ?")
    lowered = rewritten.lower()
    assert "masc" in lowered
    assert "femin" in lowered


def test_wrap_width_respects_platform_defaults(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("NEUROROM_SNES_BOX_COLS", raising=False)
    monkeypatch.delenv("NEUROROM_DIALOG_BOX_COLS", raising=False)
    monkeypatch.delenv("NEUROROM_SMS_BOX_COLS", raising=False)

    text = "A" * 80
    reinserter = SegaMasterSystemReinserter()
    reinserter.set_target_rom("sample.smc")
    assert reinserter._infer_wrap_width(text, 120) == 30

    reinserter.set_target_rom("sample.sms")
    assert reinserter._infer_wrap_width(text, 120) == 28


def test_postpatch_profile_path_uses_snes_base():
    wrapper = SegaReinserter("sample.smc")
    profile_path = wrapper._resolve_postpatch_profile_path()
    assert profile_path is not None
    assert str(profile_path).replace("\\", "/").endswith(
        "core/profiles/snes/post_reinsertion_crc_profiles.json"
    )


def test_postpatch_profile_path_uses_sms_base():
    wrapper = SegaReinserter("sample.sms")
    profile_path = wrapper._resolve_postpatch_profile_path()
    assert profile_path is not None
    assert str(profile_path).replace("\\", "/").endswith(
        "core/profiles/sms/post_reinsertion_crc_profiles.json"
    )
