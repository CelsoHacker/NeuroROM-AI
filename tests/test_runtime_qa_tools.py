import json
from pathlib import Path

from tools.runtime_qa.analyze_probe_hits import build_profile
from tools.runtime_qa.generate_probe_bizhawk import build_probe_payload, write_probe_artifacts
from tools.runtime_qa.generate_trace_autoplay_bizhawk import (
    build_trace_payload,
    write_trace_artifacts,
)
from tools.runtime_qa.runtime_qa_step import run_runtime_qa


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def test_generate_probe_bizhawk_uses_safe_seeds_and_writes_artifacts(tmp_path: Path):
    pure = tmp_path / "DE9F8517_pure_text.jsonl"
    _write_jsonl(
        pure,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288},
            {
                "id": 1,
                "seq": 0,
                "rom_offset": "0x000088",
                "max_len_bytes": 8,
                "raw_len": 9,
                "terminator": 0,
                "raw_bytes_hex": "48656C6C6F00000000",
                "reinsertion_safe": True,
            },
            {
                "id": 2,
                "seq": 1,
                "rom_offset": "0x000120",
                "max_len_bytes": 6,
                "raw_len": 7,
                "terminator": 0,
                "raw_bytes_hex": "776F726C640000",
                "reinsertion_safe": False,
            },
        ],
    )

    payload = build_probe_payload(
        pure_jsonl=pure,
        platform_hint="master_system",
        seeds_limit=16,
        sample_every_frames=5,
        out_base=tmp_path / "out",
    )
    assert payload["rom_crc32"] == "DE9F8517"
    assert payload["platform"] == "master_system"
    assert len(payload["seeds"]) == 1
    assert payload["seeds"][0]["rom_offset_hex"] == "0x000088"

    artifacts = write_probe_artifacts(payload)
    script = Path(artifacts["probe_script_path"])
    config = Path(artifacts["probe_config_path"])
    assert script.exists()
    assert config.exists()
    lua = script.read_text(encoding="utf-8")
    assert "probe_hits.jsonl" in lua
    assert "event.onmemoryexecute" in lua
    assert "client.exit" in lua
    assert "max_frames" in lua


def test_generate_trace_bizhawk_has_auto_exit_and_deterministic_output(tmp_path: Path):
    pure = tmp_path / "DE9F8517_pure_text.jsonl"
    _write_jsonl(
        pure,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288},
            {
                "id": 1,
                "seq": 0,
                "rom_offset": "0x000088",
                "max_len_bytes": 8,
                "raw_len": 9,
                "terminator": 0,
                "raw_bytes_hex": "48656C6C6F00000000",
                "reinsertion_safe": True,
            },
        ],
    )
    hook = tmp_path / "DE9F8517_runtime_hook_profile.json"
    hook.write_text(
        json.dumps(
            {
                "rom_crc32": "DE9F8517",
                "rom_size": 524288,
                "platform": "master_system",
                "top_pcs": [{"pc": "0x8123", "hits": 5}],
                "pointer_candidates": [{"name": "HL", "hits": 5}],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = build_trace_payload(
        pure_jsonl=pure,
        hook_profile_path=hook,
        platform_hint="master_system",
        max_watch_pcs=16,
        seeds_fallback=8,
        sample_every_frames=8,
        max_frames=900,
        trace_suffix="s0",
        out_base=tmp_path / "out",
    )
    artifacts = write_trace_artifacts(payload)
    script = Path(artifacts["runtime_trace_script_path"])
    lua = script.read_text(encoding="utf-8")
    assert "runtime_trace_s0.jsonl" in lua
    assert "client.exit" in lua
    assert "max_frames = 900" in lua


def test_analyze_probe_hits_generates_runtime_hook_profile(tmp_path: Path):
    probe_hits = tmp_path / "DE9F8517_probe_hits.jsonl"
    _write_jsonl(
        probe_hits,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288, "platform": "master_system"},
            {
                "frame": 120,
                "pc": "0x8123",
                "ptr_or_buf": "REG:HL=0xC200",
                "ptr_register": "HL",
                "context_tag": "dialog",
                "seed_key": "1",
            },
            {
                "frame": 140,
                "pc": "0x8123",
                "ptr_or_buf": "REG:HL=0xC240",
                "ptr_register": "HL",
                "context_tag": "dialog",
                "seed_key": "2",
            },
            {
                "frame": 260,
                "pc": "0x9230",
                "ptr_or_buf": "REG:DE=0xC300",
                "ptr_register": "DE",
                "context_tag": "menu",
                "seed_key": "3",
            },
        ],
    )

    out = tmp_path / "DE9F8517_runtime_hook_profile.json"
    result = build_profile(probe_hits, out_path=out, platform_hint="master_system")
    assert result.exists()
    profile = json.loads(result.read_text(encoding="utf-8"))
    assert profile["probe_hits_total"] == 3
    assert profile["top_pcs"][0]["pc"] == "0x8123"
    assert profile["recommended_hook"]["ptr_register"] == "HL"


def test_runtime_qa_step_generates_runtime_artifacts_and_injects_report_proof(tmp_path: Path):
    runtime_trace = tmp_path / "DE9F8517_runtime_trace.jsonl"
    _write_jsonl(
        runtime_trace,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288, "platform": "master_system"},
            {
                "frame": 100,
                "pc": "0x8123",
                "ptr_or_buf": "RAM:0x2000",
                "raw_bytes_hex": "54484520574F524C4400",
                "raw_len": 10,
                "terminator": 0,
                "context_tag": "dialog",
                "rom_offset": "0x000088",
            },
            {
                "frame": 140,
                "pc": "0x8130",
                "ptr_or_buf": "RAM:0x2100",
                "raw_bytes_hex": "4F4B00",
                "raw_len": 3,
                "terminator": 0,
                "context_tag": "menu",
                "rom_offset": "0x000120",
            },
        ],
    )

    translated = tmp_path / "DE9F8517_translated_fixed_ptbr.jsonl"
    _write_jsonl(
        translated,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288},
            {
                "id": 1,
                "key": "1",
                "seq": 0,
                "rom_offset": "0x000088",
                "text_src": "THE WORLD",
                "text_dst": "THE WORLD",
                "reinsertion_safe": True,
                "needs_review": False,
            }
        ],
    )

    mapping = tmp_path / "DE9F8517_reinsertion_mapping.json"
    mapping.write_text(
        json.dumps(
            {
                "entries": {
                    "1": {
                        "id": 1,
                        "key": "1",
                        "offset": 0x88,
                        "max_len": 8,
                        "terminator": 0,
                        "reinsertion_safe": True,
                    }
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    proof = tmp_path / "DE9F8517_proof.json"
    proof.write_text(json.dumps({"evidence": {}}, ensure_ascii=False, indent=2), encoding="utf-8")
    report_txt = tmp_path / "DE9F8517_report.txt"
    report_txt.write_text("REPORT_BASE\n", encoding="utf-8")
    report_json = tmp_path / "DE9F8517_reinsertion_report.json"
    report_json.write_text(json.dumps({"evidence": {}}, ensure_ascii=False, indent=2), encoding="utf-8")

    result = run_runtime_qa(
        runtime_trace_path=runtime_trace,
        translated_jsonl=translated,
        mapping_json=mapping,
        out_dir=tmp_path,
        proof_json=proof,
        report_txt=report_txt,
        report_json=report_json,
        inject_artifacts=True,
    )

    assert Path(result["runtime_displayed_text_trace"]).exists()
    assert Path(result["runtime_missing_displayed_text"]).exists()
    assert Path(result["runtime_coverage_summary"]).exists()
    assert result["summary"]["missing_displayed_text_count"] >= 1

    proof_obj = json.loads(proof.read_text(encoding="utf-8"))
    assert "RUNTIME_TRACE" in proof_obj
    assert proof_obj["evidence"]["runtime_missing_displayed_text_count"] >= 1

    txt = report_txt.read_text(encoding="utf-8")
    assert "RUNTIME_TRACE:" in txt
    assert "runtime_trace_items_total=" in txt
