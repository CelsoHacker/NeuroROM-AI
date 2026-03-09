import json
from pathlib import Path

from core.qa_gate_runtime import (
    run_autoretry_for_translation,
    run_qa_gate,
    run_semantic_autoretry_for_translation,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_qa_gate_semantico_bloqueia_alucinacao(tmp_path: Path):
    pure = tmp_path / "pure.jsonl"
    translated = tmp_path / "translated.jsonl"
    _write_jsonl(
        pure,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288},
            {
                "id": 1,
                "offset": "0x000200",
                "rom_offset": "0x000200",
                "text_src": "Ealing",
                "terminator": 0,
            },
        ],
    )
    _write_jsonl(
        translated,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288},
            {
                "id": 1,
                "offset": "0x000200",
                "rom_offset": "0x000200",
                "text_src": "Ealing",
                "text_dst": "Ealing e um bairro de Londres",
                "terminator": 0,
            },
        ],
    )

    qa = run_qa_gate(str(pure), str(translated))
    assert qa["pass"] is False
    assert "semantic_gate_pass" in qa["failed_checks"]
    assert int((qa.get("metrics", {}) or {}).get("semantic_blocked_count", 0)) >= 1
    assert (qa.get("examples", {}) or {}).get("semantic_blocked")


def test_qa_gate_semantico_bloqueia_ingles_residual(tmp_path: Path):
    pure = tmp_path / "pure.jsonl"
    translated = tmp_path / "translated.jsonl"
    _write_jsonl(
        pure,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288},
            {
                "id": 1,
                "offset": "0x000200",
                "rom_offset": "0x000200",
                "text_src": "Open the door",
                "terminator": 0,
            },
        ],
    )
    _write_jsonl(
        translated,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288},
            {
                "id": 1,
                "offset": "0x000200",
                "rom_offset": "0x000200",
                "text_src": "Open the door",
                "text_dst": "Open the door",
                "terminator": 0,
            },
        ],
    )

    qa = run_qa_gate(str(pure), str(translated))
    assert qa["pass"] is False
    assert "semantic_english_residue_zero" in qa["failed_checks"]
    assert int((qa.get("metrics", {}) or {}).get("semantic_english_residue_count", 0)) >= 1


def test_qa_gate_semantico_aprova_segmento_fiel(tmp_path: Path):
    pure = tmp_path / "pure.jsonl"
    translated = tmp_path / "translated.jsonl"
    _write_jsonl(
        pure,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288},
            {
                "id": 1,
                "offset": "0x000200",
                "rom_offset": "0x000200",
                "text_src": "Mys.Robe seeks Honesty",
                "terminator": 0,
            },
        ],
    )
    _write_jsonl(
        translated,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288},
            {
                "id": 1,
                "offset": "0x000200",
                "rom_offset": "0x000200",
                "text_src": "Mys.Robe seeks Honesty",
                "text_dst": "Mys.Robe busca Honestidade",
                "terminator": 0,
            },
        ],
    )

    qa = run_qa_gate(str(pure), str(translated))
    assert qa["pass"] is True
    assert "semantic_gate_pass" not in qa["failed_checks"]
    assert int((qa.get("metrics", {}) or {}).get("semantic_blocked_count", 0)) == 0


def test_qa_gate_falha_quando_artifact_indica_cobertura_incompleta(tmp_path: Path):
    pure = tmp_path / "pure.jsonl"
    translated = tmp_path / "translated.jsonl"
    proof = tmp_path / "proof.json"
    _write_jsonl(
        pure,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288},
            {
                "id": 1,
                "offset": "0x000200",
                "rom_offset": "0x000200",
                "text_src": "Mys.Robe seeks Honesty",
                "terminator": 0,
            },
        ],
    )
    _write_jsonl(
        translated,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288},
            {
                "id": 1,
                "offset": "0x000200",
                "rom_offset": "0x000200",
                "text_src": "Mys.Robe seeks Honesty",
                "text_dst": "Mys.Robe busca Honestidade",
                "terminator": 0,
            },
        ],
    )
    proof.write_text(
        json.dumps(
            {
                "schema": "reinsertion_proof.v2",
                "coverage_incomplete": True,
                "global_coverage_percent": 80.0,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    qa = run_qa_gate(str(pure), str(translated), proof_json_path=str(proof))
    assert qa["pass"] is False
    assert "coverage_incomplete_false" in qa["failed_checks"]
    assert bool((qa.get("metrics", {}) or {}).get("coverage_incomplete", False)) is True


def test_autoretry_semantico_remove_residuo_ingles_automaticamente(tmp_path: Path):
    pure = tmp_path / "pure.jsonl"
    translated = tmp_path / "translated.jsonl"
    _write_jsonl(
        pure,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288},
            {
                "id": 1,
                "offset": "0x000200",
                "rom_offset": "0x000200",
                "text_src": "Open the door",
                "terminator": 0,
            },
        ],
    )
    _write_jsonl(
        translated,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288},
            {
                "id": 1,
                "offset": "0x000200",
                "rom_offset": "0x000200",
                "text_src": "Open the door",
                "text_dst": "Open the door",
                "terminator": 0,
            },
        ],
    )

    res = run_autoretry_for_translation(
        pure_jsonl_path=str(pure),
        translated_jsonl_path=str(translated),
        max_retries=1,
    )
    qa = res.get("qa_gate", {})
    assert res["pass"] is True
    assert qa.get("checks", {}).get("semantic_gate_pass", False) is True
    assert qa.get("checks", {}).get("semantic_english_residue_zero", False) is True
    assert qa.get("checks", {}).get("coverage_incomplete_false", False) is True


def test_semantic_autoretry_varre_todos_bloqueados_nao_so_amostra(tmp_path: Path):
    pure = tmp_path / "pure.jsonl"
    translated = tmp_path / "translated.jsonl"
    pure_rows = [{"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288}]
    trans_rows = [{"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288}]
    for idx in range(1, 31):
        row = {
            "id": idx,
            "offset": f"0x{0x200 + idx * 8:06X}",
            "rom_offset": f"0x{0x200 + idx * 8:06X}",
            "text_src": "Open the door",
            "terminator": 0,
        }
        pure_rows.append(dict(row))
        trans_row = dict(row)
        trans_row["text_dst"] = "Open the door"
        trans_rows.append(trans_row)
    _write_jsonl(pure, pure_rows)
    _write_jsonl(translated, trans_rows)

    res = run_semantic_autoretry_for_translation(
        pure_jsonl_path=str(pure),
        translated_jsonl_path=str(translated),
        max_rounds=2,
    )
    qa = res.get("qa_gate", {})
    assert res["pass"] is True
    assert int((qa.get("metrics", {}) or {}).get("semantic_english_residue_count", 99)) == 0
    assert int((qa.get("metrics", {}) or {}).get("semantic_blocked_count", 99)) == 0


def test_qa_gate_aplica_register_policy_via_quality_profile(monkeypatch, tmp_path: Path):
    pure = tmp_path / "pure.jsonl"
    translated = tmp_path / "translated.jsonl"
    profile = tmp_path / "quality_profile.json"
    _write_jsonl(
        pure,
        [
            {"type": "meta", "rom_crc32": "A31BEAD4", "rom_size": 2097152, "console": "SNES"},
            {
                "id": 1,
                "offset": "0x001000",
                "rom_offset": "0x001000",
                "text_src": "Can you help me?",
                "terminator": 0,
            },
        ],
    )
    _write_jsonl(
        translated,
        [
            {"type": "meta", "rom_crc32": "A31BEAD4", "rom_size": 2097152, "console": "SNES"},
            {
                "id": 1,
                "offset": "0x001000",
                "rom_offset": "0x001000",
                "text_src": "Can you help me?",
                "text_dst": "Tu podes me ajudar?",
                "terminator": 0,
            },
        ],
    )
    profile.write_text(
        json.dumps(
            {
                "schema": "neurorom.quality_profile.v1",
                "register_policy": "tu",
                "semantic": {
                    "strict_mode": True,
                    "min_semantic_score_standard": 70.0,
                    "min_semantic_score_strict": 82.0,
                    "autofix_max_rounds": 4,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("NEUROROM_QUALITY_PROFILE_PATH", str(profile))
    monkeypatch.delenv("NEUROROM_REGISTER_POLICY", raising=False)
    qa = run_qa_gate(str(pure), str(translated))
    assert qa["pass"] is True
    assert qa.get("inputs", {}).get("semantic_register_policy") == "tu"
