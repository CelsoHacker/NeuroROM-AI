import json
from pathlib import Path

from tools.runtime_qa.dyn_text_pipeline import process_dynamic_capture, sanitize_dynamic_text
from tools.runtime_qa.generate_dyn_capture_bizhawk import (
    build_dyn_capture_payload,
    write_dyn_capture_artifacts,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def test_sanitize_dynamic_text_remove_controles():
    assert sanitize_dynamic_text("Menu\x01\x02  Principal\n\tAgora") == "Menu Principal Agora"


def test_process_dynamic_capture_dedup_estavel(tmp_path: Path):
    rows_a = [
        {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288, "platform": "master_system"},
        {"type": "dyn_text", "frame": 20, "scene_hash": "BBBB", "line_idx": 2, "line": "Start Game"},
        {"type": "dyn_text", "frame": 10, "scene_hash": "AAAA", "line_idx": 1, "line": "Menu\x01"},
        {"type": "dyn_text", "frame": 11, "scene_hash": "AAAA", "line_idx": 1, "line": "Menu"},
    ]
    rows_b = [rows_a[0], rows_a[2], rows_a[1], rows_a[3]]
    raw_a = tmp_path / "run_a_raw.jsonl"
    raw_b = tmp_path / "run_b_raw.jsonl"
    _write_jsonl(raw_a, rows_a)
    _write_jsonl(raw_b, rows_b)

    out_a = tmp_path / "out_a"
    out_b = tmp_path / "out_b"
    ra = process_dynamic_capture(dyn_log_input_path=raw_a, out_dir=out_a, crc32="DE9F8517")
    rb = process_dynamic_capture(dyn_log_input_path=raw_b, out_dir=out_b, crc32="DE9F8517")

    lines_a = Path(ra["dyn_text_unique_path"]).read_text(encoding="utf-8").splitlines()
    lines_b = Path(rb["dyn_text_unique_path"]).read_text(encoding="utf-8").splitlines()
    assert lines_a == lines_b
    assert len(lines_a) == 2
    assert "scene_hash=" in lines_a[0]
    assert "hits=" in lines_a[0]


def test_process_dynamic_capture_bootstrap_fontmap(tmp_path: Path):
    raw = tmp_path / "dyn_raw.jsonl"
    _write_jsonl(
        raw,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288, "platform": "master_system"},
            {
                "type": "dyn_text",
                "frame": 100,
                "scene_hash": "ABCD1234",
                "line_idx": 4,
                "line": "A?B",
                "glyph_hashes": ["A1B2C3D4", "DEADBEEF", "9F00E112"],
                "unmapped_glyph_hashes": ["DEADBEEF", "DEADBEEF"],
                "unknown_glyph_samples": [
                    {
                        "hash": "DEADBEEF",
                        "tile_id": 66,
                        "pattern_hex": "0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF",
                    }
                ],
                "glyph_count": 3,
                "unmapped_glyph_count": 2,
            },
        ],
    )
    fontmap = tmp_path / "fontmap.json"
    fontmap.write_text(
        json.dumps(
            {"glyph_hash_to_char": {"A1B2C3D4": "A", "9F00E112": "B"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = process_dynamic_capture(
        dyn_log_input_path=raw,
        out_dir=tmp_path / "out",
        crc32="DE9F8517",
        fontmap_path=fontmap,
        bootstrap_enabled=True,
    )
    bootstrap = Path(result["fontmap_bootstrap_path"])
    assert bootstrap.exists()
    obj = json.loads(bootstrap.read_text(encoding="utf-8"))
    by_hash = {str(r["glyph_hash"]): int(r["hits"]) for r in obj["rows"]}
    assert "DEADBEEF" in by_hash
    assert by_hash["DEADBEEF"] >= 2
    assert Path(result["unknown_glyphs_jsonl_path"]).exists()
    png_path = result.get("unknown_glyphs_png_path")
    if png_path:
        assert Path(png_path).exists()


def test_process_dynamic_capture_coverage_diff(tmp_path: Path):
    raw = tmp_path / "dyn_raw.jsonl"
    _write_jsonl(
        raw,
        [
            {"type": "meta", "rom_crc32": "DE9F8517"},
            {"type": "dyn_text", "frame": 1, "scene_hash": "S1", "line": "Start"},
            {"type": "dyn_text", "frame": 2, "scene_hash": "S2", "line": "Load"},
        ],
    )
    static_path = tmp_path / "DE9F8517_only_safe_text_by_offset.txt"
    static_path.write_text("[0x000010] Start\n[0x000020] Save\n", encoding="utf-8")

    result = process_dynamic_capture(
        dyn_log_input_path=raw,
        out_dir=tmp_path / "out",
        crc32="DE9F8517",
        static_only_safe_by_offset=static_path,
    )
    cov = result["coverage"]
    assert cov["static_rows_total"] == 2
    assert cov["missing_from_runtime_count"] == 1
    assert Path(cov["coverage_diff_report_path"]).exists()
    assert Path(cov["missing_from_runtime_path"]).exists()


def test_generate_dyn_capture_script_contains_vram_nametable_scene_hash(tmp_path: Path):
    pure = tmp_path / "DE9F8517_pure_text.jsonl"
    _write_jsonl(
        pure,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288},
            {"id": 1, "seq": 0, "rom_offset": "0x000088", "max_len_bytes": 8, "reinsertion_safe": True},
        ],
    )
    payload = build_dyn_capture_payload(
        pure_jsonl=pure,
        platform_hint="master_system",
        trace_suffix="s0",
        max_frames=600,
        sample_every_frames=2,
        out_base=tmp_path / "out",
    )
    artifacts = write_dyn_capture_artifacts(payload)
    script = Path(artifacts["dyn_capture_script_path"])
    assert script.exists()
    lua = script.read_text(encoding="utf-8")
    assert "nametable_bases" in lua
    assert "pattern_bases" in lua
    assert "glyph_hash_to_char" in lua
    assert "tile_to_char" in lua
    assert "fnv1a_32_hex" in lua
    assert "decode_tile_row" in lua
    assert "scene_hash" in lua
    assert "memory.getmemorydomainlist" in lua
    assert "RAM_DOMAIN_CANDIDATES" in lua
    assert '"Z80 BUS"' in lua
    assert "VRAM_DOMAIN_CANDIDATES" in lua
    assert "pick_domain" in lua
    assert "RAM_DOMAIN=" in lua
    assert "VRAM_DOMAIN=" in lua
    assert "68K RAM" not in lua
    assert "bit." not in lua
    assert "bit32" not in lua
    assert " << " in lua
    assert " >> " in lua
    assert " & " in lua
    assert " | " in lua
    assert " ~ " in lua
    assert "frame_origin" in lua
    assert "local VRAM_SIZE = 16384" in lua
    assert "local function safe_read(domain, addr, len)" in lua
    assert "(addr_num + len_num) > VRAM_SIZE" in lua
    assert "safe_read(VRAM_DOMAIN, addr, 1)" in lua
    assert "safe_read(VRAM_DOMAIN, addr, size)" in lua
    assert "mask_vram_addr(" in lua
    assert "name_table_base = (((reg2 & 0x0E) * 0x400) & 0x3FFF)" in lua
    assert "pattern_base = (((reg4 & 0x07) * 0x800) & 0x3FFF)" in lua
    assert "xpcall(capture_main" in lua
    assert "frame_origin=%d end_frame=%d" in lua
    assert "READ_DOMAINS_RAM=" in lua
    assert "if (not allow_vram) and is_vram_domain(n) then return end" in lua
    assert "sample_every_n_frames" in lua
    assert "last_nametable_hash" in lua
    assert "compute_nametable_hash" in lua
    assert "if not input_explorer_enabled then" in lua
    assert "if (frame % sample_every_n_frames) == 0 then" in lua
    assert "step_ok, step_err = xpcall(function()" in lua
    assert "emu.frameadvance()" in lua


def test_build_dyn_capture_payload_nao_cria_pasta_antecipada(tmp_path: Path):
    pure = tmp_path / "DE9F8517_pure_text.jsonl"
    _write_jsonl(
        pure,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288},
            {"id": 1, "seq": 0, "rom_offset": "0x000088", "max_len_bytes": 8, "reinsertion_safe": True},
        ],
    )
    out_base = tmp_path / "out"
    payload = build_dyn_capture_payload(
        pure_jsonl=pure,
        platform_hint="master_system",
        trace_suffix="s1",
        max_frames=600,
        sample_every_frames=2,
        out_base=out_base,
    )
    out_dir = Path(payload["out_dir"])
    assert not out_dir.exists()

    artifacts = write_dyn_capture_artifacts(payload)
    assert Path(artifacts["dyn_capture_script_path"]).exists()
    assert out_dir.exists()


def test_build_dyn_capture_payload_default_sample_every_n_frames_3(tmp_path: Path):
    pure = tmp_path / "DE9F8517_pure_text.jsonl"
    _write_jsonl(
        pure,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288},
            {"id": 1, "seq": 0, "rom_offset": "0x000088", "max_len_bytes": 8, "reinsertion_safe": True},
        ],
    )
    payload = build_dyn_capture_payload(
        pure_jsonl=pure,
        platform_hint="master_system",
        trace_suffix="s2",
        max_frames=600,
        out_base=tmp_path / "out",
    )
    assert int(payload["sample_every_n_frames"]) == 3


def test_process_dynamic_capture_gera_segmento_canonico_e_artifacts(tmp_path: Path):
    raw = tmp_path / "dyn_raw.jsonl"
    _write_jsonl(
        raw,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288},
            {"type": "dyn_text", "frame": 1, "scene_hash": "S1", "line": "Ação rápida"},
        ],
    )

    required = (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz "
        "áàâãäéêíóôõúüçÁÀÂÃÄÉÊÍÓÔÕÚÜÇ.,;:!?-'/()% \""
    )
    fontmap_payload = {"glyph_hash_to_char": {f"{i+1:08X}": ch for i, ch in enumerate(required)}}
    fontmap = tmp_path / "fontmap.json"
    fontmap.write_text(json.dumps(fontmap_payload, ensure_ascii=False), encoding="utf-8")

    result = process_dynamic_capture(
        dyn_log_input_path=raw,
        out_dir=tmp_path / "out",
        crc32="DE9F8517",
        fontmap_path=fontmap,
        bootstrap_enabled=False,
    )
    assert result["ptbr_full_coverage"] is True
    assert result["missing_glyphs"] == []
    assert Path(result["pure_text_path"]).exists()
    assert Path(result["reinsertion_mapping_path"]).exists()
    assert Path(result["report_path"]).exists()
    assert Path(result["proof_path"]).exists()

    rows = Path(result["pure_text_path"]).read_text(encoding="utf-8").splitlines()
    segment = json.loads(rows[1])
    required_fields = {
        "segment_id",
        "rom_crc32",
        "rom_size",
        "start_offset",
        "end_offset",
        "original_bytes_hex",
        "decoded_text",
        "translated_text",
        "renderable_text",
        "control_tokens",
        "terminator_hex",
        "max_bytes",
        "pointer_refs",
        "script_source",
        "confidence",
        "encoding_ok",
        "glyphs_ok",
        "tokens_ok",
        "terminator_ok",
        "layout_ok",
        "byte_length_ok",
        "offsets_ok",
        "pointers_ok",
        "fallback_applied",
        "fallback_changes",
        "missing_glyphs",
        "failure_reason",
        "status",
    }
    assert required_fields.issubset(set(segment.keys()))


def test_process_dynamic_capture_ptbr_coverage_parcial(tmp_path: Path):
    raw = tmp_path / "dyn_raw.jsonl"
    _write_jsonl(
        raw,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288},
            {"type": "dyn_text", "frame": 1, "scene_hash": "S1", "line": "Ação"},
        ],
    )
    fontmap = tmp_path / "fontmap.json"
    fontmap.write_text(
        json.dumps({"glyph_hash_to_char": {"AAAABBBB": "A", "CCCCDDDD": "o"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    result = process_dynamic_capture(
        dyn_log_input_path=raw,
        out_dir=tmp_path / "out",
        crc32="DE9F8517",
        fontmap_path=fontmap,
        bootstrap_enabled=False,
    )
    assert result["ptbr_full_coverage"] is False
    assert "á" in result["missing_glyphs"] or "Á" in result["missing_glyphs"]
