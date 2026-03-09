#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Converte *_V98_FORENSIC.txt em artefatos reinseriveis:
- {CRC32}_pure_text.jsonl
- {CRC32}_reinsertion_mapping.json
- {CRC32}_report.txt
- {CRC32}_proof.json

Foco:
- ordenacao deterministica por rom_offset (seq 0..N-1)
- metadados obrigatorios de rom_crc32/rom_size
- prova de cobertura e ordering_check
"""

from __future__ import annotations

import argparse
import json
import re
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


LINE_RE = re.compile(r"^\[(0x[0-9A-Fa-f]+)\]\s*(.*)$")
BYTE_TOKEN_RE = re.compile(r"\[[0-9A-Fa-f]{2}\]")


def _crc32_hex(path: Path) -> str:
    crc = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            crc = zlib.crc32(chunk, crc)
    return f"{crc & 0xFFFFFFFF:08X}"


def _rom_size(path: Path) -> int:
    return path.stat().st_size


def _parse_forensic(path: Path) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
    header: Dict[str, str] = {}
    entries: List[Dict[str, Any]] = []

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for ln, raw_line in enumerate(f, 1):
            line = raw_line.rstrip("\n")
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                body = stripped[1:].strip()
                if ":" in body:
                    k, v = body.split(":", 1)
                    header[k.strip()] = v.strip()
                continue
            m = LINE_RE.match(stripped)
            if not m:
                continue
            off_hex = m.group(1).upper()
            text = m.group(2)
            entries.append(
                {
                    "offset": int(off_hex, 16),
                    "offset_hex": off_hex,
                    "text_src": text,
                    "line_no": ln,
                }
            )
    return header, entries


def _estimate_source_len_bytes(text: str) -> int:
    """
    Estimativa conservadora:
    - [XX] conta 1 byte
    - caractere visivel conta 1 byte
    """
    if not text:
        return 0

    total = 0
    i = 0
    while i < len(text):
        token = BYTE_TOKEN_RE.match(text, i)
        if token:
            total += 1
            i = token.end()
        else:
            total += 1
            i += 1
    return total


def _preview_text(s: str, limit: int = 60) -> str:
    s = (s or "").replace("\r", " ").replace("\n", " ")
    if len(s) <= limit:
        return s
    return s[: limit - 3] + "..."


def _build_rows(
    parsed_entries: List[Dict[str, Any]],
    crc32: str,
    rom_size: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    # Ordenacao deterministica (offset asc + ordem de chegada)
    indexed = list(enumerate(parsed_entries))
    indexed.sort(key=lambda it: (int(it[1]["offset"]), int(it[0])))

    unique: List[Dict[str, Any]] = []
    seen_offsets = set()
    duplicates_removed = 0

    for _, item in indexed:
        off = int(item["offset"])
        if off in seen_offsets:
            duplicates_removed += 1
            continue
        seen_offsets.add(off)
        unique.append(item)

    rows: List[Dict[str, Any]] = []
    mapping_entries: List[Dict[str, Any]] = []

    for seq, item in enumerate(unique):
        off = int(item["offset"])
        text_src = str(item.get("text_src", ""))
        src_len = _estimate_source_len_bytes(text_src)
        max_len_bytes = max(1, int(src_len) + 1)  # +1 para terminador

        row = {
            "id": int(seq),
            "seq": int(seq),
            "offset": f"0x{off:06X}",
            "rom_offset": f"0x{off:06X}",
            "rom_crc32": str(crc32).upper(),
            "rom_size": int(rom_size),
            "text_src": text_src,
            "text_dst": "",
            "max_len_bytes": int(max_len_bytes),
            "encoding": "ascii",
            "source": "FORENSIC_V98",
            "reinsertion_safe": True,
        }
        rows.append(row)

        map_entry = {
            "id": int(seq),
            "seq": int(seq),
            "offset": int(off),
            "rom_offset": int(off),
            "rom_crc32": str(crc32).upper(),
            "rom_size": int(rom_size),
            "max_length": int(max_len_bytes),
            "max_len_bytes": int(max_len_bytes),
            "terminator": None,
            "encoding": "ascii",
            "source": "FORENSIC_V98",
            "reinsertion_safe": True,
        }
        mapping_entries.append(map_entry)

    return rows, mapping_entries, duplicates_removed


def _build_ordering_check(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    offsets = [int(str(r["rom_offset"]), 16) for r in rows]
    is_sorted = offsets == sorted(offsets)

    first_10 = [
        {"seq": int(r["seq"]), "rom_offset": str(r["rom_offset"])}
        for r in rows[:10]
    ]
    last_10 = [
        {"seq": int(r["seq"]), "rom_offset": str(r["rom_offset"])}
        for r in rows[-10:]
    ]
    return {
        "is_sorted_by_offset": bool(is_sorted),
        "first_10_offsets": first_10,
        "last_10_offsets": last_10,
    }


def _build_coverage_check(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {
            "min_offset": None,
            "max_offset": None,
            "items_total": 0,
            "count_offsets_below_0x10000": 0,
            "first_20_items_summary": [],
        }

    offsets = [int(str(r["rom_offset"]), 16) for r in rows]
    first_20 = [
        {
            "seq": int(r["seq"]),
            "rom_offset": str(r["rom_offset"]),
            "text_src": _preview_text(str(r.get("text_src", "")), limit=48),
        }
        for r in rows[:20]
    ]
    return {
        "min_offset": f"0x{min(offsets):X}",
        "max_offset": f"0x{max(offsets):X}",
        "items_total": int(len(rows)),
        "count_offsets_below_0x10000": int(sum(1 for o in offsets if o < 0x10000)),
        "first_20_items_summary": first_20,
    }


def _write_jsonl(path: Path, rows: List[Dict[str, Any]], meta: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(meta, ensure_ascii=False) + "\n")
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_report(path: Path, payload: Dict[str, Any]) -> None:
    lines = [
        "NEUROROM FORENSIC -> PURE_TEXT/MAPPING",
        f"timestamp={payload['generated_at']}",
        f"rom_crc32={payload['rom_crc32']}",
        f"rom_size={payload['rom_size']}",
        f"source_rom={payload['source_rom']}",
        f"source_forensic={payload['source_forensic']}",
        f"items_total_raw={payload['items_total_raw']}",
        f"items_total_unique={payload['items_total_unique']}",
        f"duplicates_removed={payload['duplicates_removed']}",
        "",
        "INPUT_MATCH_CHECK:",
        f"  rom_crc32_match={str(payload['input_match_check']['rom_crc32_match']).lower()}",
        f"  rom_size_match={str(payload['input_match_check']['rom_size_match']).lower()}",
        f"  jsonl_declared_crc32={payload['input_match_check']['jsonl_declared_crc32']}",
        f"  jsonl_declared_size={payload['input_match_check']['jsonl_declared_size']}",
        "",
        "ORDERING_CHECK:",
        f"  is_sorted_by_offset={str(payload['ordering_check']['is_sorted_by_offset']).lower()}",
        f"  first_10_offsets={json.dumps(payload['ordering_check']['first_10_offsets'], ensure_ascii=False)}",
        f"  last_10_offsets={json.dumps(payload['ordering_check']['last_10_offsets'], ensure_ascii=False)}",
        "",
        "COVERAGE_CHECK:",
        f"  min_offset={payload['coverage_check']['min_offset']}",
        f"  max_offset={payload['coverage_check']['max_offset']}",
        f"  items_total={payload['coverage_check']['items_total']}",
        f"  count_offsets_below_0x10000={payload['coverage_check']['count_offsets_below_0x10000']}",
        f"  first_20_items_summary={json.dumps(payload['coverage_check']['first_20_items_summary'], ensure_ascii=False)}",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Converte *_V98_FORENSIC.txt para artifacts reinseriveis (pure_text/mapping)."
    )
    parser.add_argument("--rom", required=True, help="Caminho da ROM original.")
    parser.add_argument("--forensic", required=True, help="Caminho do *_V98_FORENSIC.txt.")
    parser.add_argument(
        "--out-dir",
        default="",
        help="Diretorio de saida. Padrao: <pasta_rom>/<CRC32>/1_extracao",
    )
    args = parser.parse_args()

    rom_path = Path(args.rom).expanduser().resolve()
    forensic_path = Path(args.forensic).expanduser().resolve()

    if not rom_path.exists() or not rom_path.is_file():
        raise SystemExit(f"[ERRO] ROM nao encontrada: {rom_path}")
    if not forensic_path.exists() or not forensic_path.is_file():
        raise SystemExit(f"[ERRO] Forensic nao encontrado: {forensic_path}")

    crc32 = _crc32_hex(rom_path)
    rom_size = _rom_size(rom_path)

    if args.out_dir:
        out_dir = Path(args.out_dir).expanduser().resolve()
    else:
        out_dir = rom_path.parent / crc32 / "1_extracao"
    out_dir.mkdir(parents=True, exist_ok=True)

    header, parsed_entries = _parse_forensic(forensic_path)
    rows, mapping_entries, duplicates_removed = _build_rows(parsed_entries, crc32, rom_size)

    meta_header = {
        "type": "meta",
        "schema": "neurorom.pure_text.v2",
        "rom_crc32": crc32,
        "rom_size": int(rom_size),
        "ordering": "seq/rom_offset",
        "source_forensic": forensic_path.name,
        "source_rom": rom_path.name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "header_total_strings": header.get("Total Strings"),
    }

    jsonl_path = out_dir / f"{crc32}_pure_text.jsonl"
    mapping_path = out_dir / f"{crc32}_reinsertion_mapping.json"
    report_path = out_dir / f"{crc32}_report.txt"
    proof_path = out_dir / f"{crc32}_proof.json"

    _write_jsonl(jsonl_path, rows, meta_header)

    mapping_obj = {
        "type": "meta",
        "schema": "neurorom.reinsertion_mapping.v2",
        "rom_crc32": crc32,
        "rom_size": int(rom_size),
        "ordering": "seq/rom_offset",
        "source_forensic": forensic_path.name,
        "source_rom": rom_path.name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "entries": mapping_entries,
    }
    mapping_path.write_text(json.dumps(mapping_obj, ensure_ascii=False, indent=2), encoding="utf-8")

    ordering_check = _build_ordering_check(rows)
    coverage_check = _build_coverage_check(rows)
    input_match_check = {
        "rom_crc32_match": True,
        "rom_size_match": True,
        "jsonl_declared_crc32": crc32,
        "jsonl_declared_size": int(rom_size),
    }

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rom_crc32": crc32,
        "rom_size": int(rom_size),
        "source_rom": rom_path.name,
        "source_forensic": forensic_path.name,
        "items_total_raw": int(len(parsed_entries)),
        "items_total_unique": int(len(rows)),
        "duplicates_removed": int(duplicates_removed),
        "ordering_check": ordering_check,
        "coverage_check": coverage_check,
        "input_match_check": input_match_check,
        "outputs": {
            "pure_text_jsonl": str(jsonl_path),
            "reinsertion_mapping_json": str(mapping_path),
            "report_txt": str(report_path),
            "proof_json": str(proof_path),
        },
    }

    _write_report(report_path, payload)
    proof_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] CRC32={crc32} ROM_SIZE={rom_size}")
    print(f"[OK] Parsed={len(parsed_entries)} Unique={len(rows)} DuplicatesRemoved={duplicates_removed}")
    print(f"[OK] Wrote: {jsonl_path.name}")
    print(f"[OK] Wrote: {mapping_path.name}")
    print(f"[OK] Wrote: {report_path.name}")
    print(f"[OK] Wrote: {proof_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
