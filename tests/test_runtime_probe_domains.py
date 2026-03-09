import json
from pathlib import Path

from tools.runtime_qa.generate_probe_bizhawk import (
    build_probe_payload,
    write_probe_artifacts,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )


def test_generate_probe_script_uses_domain_picker_master_system(tmp_path: Path):
    pure = tmp_path / "DE9F8517_pure_text.jsonl"
    _write_jsonl(
        pure,
        [
            {"type": "meta", "rom_crc32": "DE9F8517", "rom_size": 524288},
            {
                "id": 1,
                "seq": 0,
                "rom_offset": "0x000120",
                "max_len_bytes": 12,
                "reinsertion_safe": True,
            },
        ],
    )
    payload = build_probe_payload(
        pure_jsonl=pure,
        platform_hint="master_system",
        out_base=tmp_path / "out",
    )
    artifacts = write_probe_artifacts(payload)
    script = Path(artifacts["probe_script_path"])
    assert script.exists()
    lua = script.read_text(encoding="utf-8")
    assert "memory.getmemorydomainlist" in lua
    assert "RAM_DOMAIN_CANDIDATES" in lua
    assert '"Z80 BUS"' in lua
    assert "VRAM_DOMAIN_CANDIDATES" in lua
    assert "pick_domain" in lua
    assert "[NR_QA][PROBE] RAM_DOMAIN=" in lua
    assert "READ_DOMAINS_RAM" in lua
    assert "if (not allow_vram) and is_vram_domain(n) then return nil end" in lua
    assert "68K RAM" not in lua
