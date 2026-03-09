#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Passo opcional de RuntimeQA:
- compara runtime_trace real com translated + mapping
- gera runtime_displayed_text_trace / runtime_missing_displayed_text / runtime_coverage_summary
- injeta bloco RUNTIME_TRACE em proof/report sem quebrar compatibilidade.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from .common import (
        english_stopword_hit_count,
        infer_crc_from_name,
        infer_platform_from_path,
        iter_jsonl,
        parse_int,
        write_json,
        write_jsonl,
    )
except ImportError:  # pragma: no cover
    from common import (  # type: ignore
        english_stopword_hit_count,
        infer_crc_from_name,
        infer_platform_from_path,
        iter_jsonl,
        parse_int,
        write_json,
        write_jsonl,
    )


def _norm_hex(raw: str) -> str:
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", str(raw or ""))
    if len(cleaned) % 2 != 0:
        cleaned = cleaned[:-1]
    return cleaned.upper()


def _decode_ascii(raw_hex: str, terminator: Optional[int]) -> str:
    if not raw_hex:
        return ""
    try:
        data = bytes.fromhex(raw_hex)
    except Exception:
        return ""
    out: List[str] = []
    term = int(terminator) if terminator is not None else None
    for b in data:
        if term is not None and int(b) == term:
            break
        if 32 <= int(b) <= 126:
            out.append(chr(int(b)))
        else:
            out.append(f"{{B:{int(b):02X}}}")
    return "".join(out).strip()


def _is_phrase(value: str) -> bool:
    txt = str(value or "").strip()
    if len(txt) < 5:
        return False
    return bool(re.search(r"[A-Za-z]", txt) and (" " in txt))


def _is_english_residual(value: str) -> bool:
    txt = str(value or "").strip()
    if not txt:
        return False
    return english_stopword_hit_count(txt) > 0


def _load_mapping(mapping_path: Optional[Path]) -> Tuple[Dict[str, Dict[str, Any]], Dict[int, str]]:
    if mapping_path is None or not mapping_path.exists():
        return {}, {}
    try:
        obj = json.loads(mapping_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}, {}

    entries_obj = obj.get("entries", obj if isinstance(obj, dict) else {})
    by_key: Dict[str, Dict[str, Any]] = {}
    by_offset: Dict[int, str] = {}
    if isinstance(entries_obj, dict):
        iterator = entries_obj.items()
    elif isinstance(entries_obj, list):
        iterator = ((str(i), row) for i, row in enumerate(entries_obj))
    else:
        iterator = []

    for key, row in iterator:
        if not isinstance(row, dict):
            continue
        k = str(row.get("id", row.get("key", key)))
        off = parse_int(row.get("offset", row.get("rom_offset", row.get("origin_offset"))), default=None)
        if off is None:
            continue
        mapped = {
            "key": k,
            "id": parse_int(row.get("id"), default=None),
            "seq": parse_int(row.get("seq"), default=None),
            "rom_offset": int(off),
            "max_len_bytes": int(parse_int(row.get("max_len", row.get("max_len_bytes")), default=0) or 0),
            "terminator": parse_int(row.get("terminator"), default=None),
            "reinsertion_safe": bool(row.get("reinsertion_safe", False)),
            "source": row.get("category", row.get("source")),
        }
        by_key[k] = mapped
        by_offset.setdefault(int(off), k)
    return by_key, by_offset


def _load_translated(translated_jsonl: Optional[Path]) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]], Dict[int, str]]:
    if translated_jsonl is None or not translated_jsonl.exists():
        return {}, {}, {}
    meta: Dict[str, Any] = {}
    by_key: Dict[str, Dict[str, Any]] = {}
    by_offset: Dict[int, str] = {}
    for obj in iter_jsonl(translated_jsonl):
        if obj.get("type") == "meta":
            meta = dict(obj)
            continue
        key = str(obj.get("key", obj.get("id", ""))).strip()
        if not key:
            off_key = parse_int(
                obj.get("rom_offset", obj.get("offset", obj.get("origin_offset"))),
                default=None,
            )
            if off_key is not None:
                key = f"off_{int(off_key):X}"
            else:
                continue
        row = {
            "key": key,
            "id": parse_int(obj.get("id"), default=None),
            "seq": parse_int(obj.get("seq"), default=None),
            "rom_offset": parse_int(
                obj.get("rom_offset", obj.get("offset", obj.get("origin_offset"))),
                default=None,
            ),
            "text_src": str(obj.get("text_src", "") or ""),
            "text_dst": str(obj.get("text_dst", obj.get("translated", "")) or ""),
            "terminator": parse_int(obj.get("terminator"), default=None),
            "reinsertion_safe": bool(obj.get("reinsertion_safe", False)),
            "needs_review": bool(obj.get("needs_review", False)),
            "review_flags": obj.get("review_flags", []),
        }
        by_key[key] = row
        if row["rom_offset"] is not None:
            by_offset.setdefault(int(row["rom_offset"]), key)
    return meta, by_key, by_offset


def _load_runtime_trace(runtime_trace_path: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    meta: Dict[str, Any] = {}
    rows: List[Dict[str, Any]] = []
    for obj in iter_jsonl(runtime_trace_path):
        if obj.get("type") == "meta":
            meta = dict(obj)
            continue
        rows.append(dict(obj))
    rows.sort(
        key=lambda r: (
            parse_int(r.get("frame"), default=1 << 30) or (1 << 30),
            parse_int(r.get("seq"), default=1 << 30) or (1 << 30),
        )
    )
    return meta, rows


def _detect_crc_size_platform(
    runtime_meta: Dict[str, Any],
    translated_meta: Dict[str, Any],
    runtime_trace_path: Path,
    force_crc: Optional[str],
    force_size: Optional[int],
    force_platform: Optional[str],
) -> Tuple[str, int, str]:
    crc = str(force_crc or runtime_meta.get("rom_crc32") or translated_meta.get("rom_crc32") or "").upper().strip()
    if not crc:
        crc = infer_crc_from_name(runtime_trace_path.name) or infer_crc_from_name(str(runtime_trace_path.parent)) or "UNKNOWN000"
    size = (
        parse_int(force_size, default=None)
        or parse_int(runtime_meta.get("rom_size"), default=None)
        or parse_int(translated_meta.get("rom_size"), default=0)
        or 0
    )
    platform = str(force_platform or runtime_meta.get("platform") or "").strip().lower()
    if not platform:
        platform = infer_platform_from_path(str(runtime_trace_path))
    return crc, int(size), platform


def _resolve_output_paths(out_dir: Path, crc: str) -> Dict[str, Path]:
    return {
        "trace": out_dir / f"{crc}_runtime_displayed_text_trace.jsonl",
        "missing": out_dir / f"{crc}_runtime_missing_displayed_text.jsonl",
        "summary": out_dir / f"{crc}_runtime_coverage_summary.json",
    }


def _infer_aux_artifact(path: Optional[Path], out_dir: Path, crc: str, suffix: str) -> Optional[Path]:
    if path is not None:
        return path
    cand = out_dir.parent / f"{crc}_{suffix}"
    if cand.exists():
        return cand
    cand2 = out_dir / f"{crc}_{suffix}"
    if cand2.exists():
        return cand2
    return None


def _append_runtime_block_to_report(report_path: Path, summary: Dict[str, Any], artifacts: Dict[str, str]) -> None:
    if not report_path.exists():
        return
    original = report_path.read_text(encoding="utf-8", errors="replace")
    block = [
        "",
        "RUNTIME_TRACE:",
        f"  trace_path={artifacts.get('trace_path')}",
        f"  missing_path={artifacts.get('missing_path')}",
        f"  coverage_summary_path={artifacts.get('coverage_summary_path')}",
        f"  runtime_trace_items_total={summary.get('runtime_trace_items_total', 0)}",
        f"  runtime_displayed_mapped_items={summary.get('runtime_displayed_mapped_items', 0)}",
        f"  runtime_displayed_unmapped_items={summary.get('runtime_displayed_unmapped_items', 0)}",
        f"  runtime_displayed_skip_displayed_count={summary.get('runtime_displayed_skip_displayed_count', 0)}",
        f"  runtime_displayed_english_residual_count={summary.get('runtime_displayed_english_residual_count', 0)}",
        f"  runtime_displayed_same_as_source_phrase_count={summary.get('runtime_displayed_same_as_source_phrase_count', 0)}",
        f"  missing_displayed_text_count={summary.get('missing_displayed_text_count', 0)}",
    ]
    report_path.write_text(original.rstrip() + "\n" + "\n".join(block) + "\n", encoding="utf-8")


def _inject_runtime_block_json(path: Optional[Path], runtime_block: Dict[str, Any], summary: Dict[str, Any]) -> None:
    if path is None or not path.exists():
        return
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return
    if not isinstance(obj, dict):
        return
    obj["RUNTIME_TRACE"] = dict(runtime_block)
    obj["runtime_trace"] = dict(runtime_block)
    obj["runtime_coverage_summary"] = dict(summary)
    evidence = obj.get("evidence", {})
    if not isinstance(evidence, dict):
        evidence = {}
    evidence["runtime_missing_displayed_text_count"] = int(summary.get("missing_displayed_text_count", 0))
    evidence["runtime_displayed_skip_displayed_count"] = int(
        summary.get("runtime_displayed_skip_displayed_count", 0)
    )
    evidence["runtime_displayed_english_residual_count"] = int(
        summary.get("runtime_displayed_english_residual_count", 0)
    )
    evidence["runtime_displayed_same_as_source_phrase_count"] = int(
        summary.get("runtime_displayed_same_as_source_phrase_count", 0)
    )
    obj["evidence"] = evidence
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def run_runtime_qa(
    runtime_trace_path: Path,
    translated_jsonl: Optional[Path] = None,
    mapping_json: Optional[Path] = None,
    out_dir: Optional[Path] = None,
    proof_json: Optional[Path] = None,
    report_txt: Optional[Path] = None,
    report_json: Optional[Path] = None,
    force_crc: Optional[str] = None,
    force_size: Optional[int] = None,
    force_platform: Optional[str] = None,
    inject_artifacts: bool = True,
) -> Dict[str, Any]:
    runtime_meta, runtime_rows = _load_runtime_trace(runtime_trace_path)
    translated_meta, translated_by_key, translated_by_offset = _load_translated(translated_jsonl)
    mapping_by_key, mapping_by_offset = _load_mapping(mapping_json)

    crc, rom_size, platform = _detect_crc_size_platform(
        runtime_meta=runtime_meta,
        translated_meta=translated_meta,
        runtime_trace_path=runtime_trace_path,
        force_crc=force_crc,
        force_size=force_size,
        force_platform=force_platform,
    )
    runtime_out_dir = (out_dir or runtime_trace_path.parent).expanduser().resolve()
    runtime_out_dir.mkdir(parents=True, exist_ok=True)
    paths = _resolve_output_paths(runtime_out_dir, crc)

    trace_rows: List[Dict[str, Any]] = []
    missing_rows: List[Dict[str, Any]] = []

    mapped_count = 0
    unmapped_count = 0
    skip_count = 0
    english_count = 0
    same_src_count = 0
    needs_review_count = 0

    for idx, row in enumerate(runtime_rows):
        frame = int(parse_int(row.get("frame"), default=idx) or idx)
        pc = row.get("pc")
        ptr_or_buf = str(row.get("ptr_or_buf", "") or "")
        raw_hex = _norm_hex(str(row.get("raw_bytes_hex", "") or ""))
        raw_len = int(parse_int(row.get("raw_len"), default=(len(raw_hex) // 2)) or 0)
        terminator = parse_int(row.get("terminator"), default=None)
        context_tag = str(row.get("context_tag", "") or "")
        runtime_text = str(row.get("text", row.get("decoded_text", "")) or "").strip()
        if not runtime_text:
            runtime_text = _decode_ascii(raw_hex, terminator)

        key = str(row.get("key", row.get("id", "")) or "").strip()
        rom_offset = parse_int(row.get("rom_offset", row.get("offset", None)), default=None)
        if not key and rom_offset is not None:
            key = translated_by_offset.get(int(rom_offset), mapping_by_offset.get(int(rom_offset), ""))

        translated = translated_by_key.get(key, {}) if key else {}
        if not translated and rom_offset is not None:
            key_from_off = translated_by_offset.get(int(rom_offset))
            if key_from_off:
                key = str(key_from_off)
                translated = translated_by_key.get(str(key_from_off), {})

        mapping = mapping_by_key.get(key, {}) if key else {}
        if not mapping and rom_offset is not None:
            mk = mapping_by_offset.get(int(rom_offset))
            if mk:
                mapping = mapping_by_key.get(str(mk), {})
                if not key:
                    key = str(mk)

        mapping_found = bool(translated or mapping)
        if mapping_found:
            mapped_count += 1
        else:
            unmapped_count += 1

        text_src = str(translated.get("text_src", "") or "")
        text_dst = str(translated.get("text_dst", "") or "")
        if rom_offset is None:
            rom_offset = parse_int(mapping.get("rom_offset"), default=None)
        if rom_offset is None:
            rom_offset = parse_int(translated.get("rom_offset"), default=None)

        reinsertion_safe = bool(
            translated.get("reinsertion_safe", mapping.get("reinsertion_safe", False))
        )
        needs_review = bool(translated.get("needs_review", False))
        review_flags = translated.get("review_flags", [])
        if not isinstance(review_flags, list):
            review_flags = [str(review_flags)]

        skip_displayed = bool(mapping_found and (needs_review or not reinsertion_safe or not text_dst.strip()))
        english_residual = bool(text_dst.strip() and _is_english_residual(text_dst))
        same_as_source_phrase = bool(text_dst.strip() and text_dst.strip() == text_src.strip() and _is_phrase(text_src))

        if skip_displayed:
            skip_count += 1
        if english_residual:
            english_count += 1
        if same_as_source_phrase:
            same_src_count += 1
        if needs_review:
            needs_review_count += 1

        trace_row = {
            "frame": int(frame),
            "pc": pc,
            "ptr_or_buf": ptr_or_buf,
            "raw_bytes_hex": raw_hex,
            "raw_len": int(raw_len),
            "terminator": int(terminator) if terminator is not None else None,
            "context_tag": context_tag,
            "runtime_text": runtime_text,
            "key": key or None,
            "id": translated.get("id", mapping.get("id")),
            "seq": translated.get("seq", mapping.get("seq")),
            "rom_offset": f"0x{int(rom_offset):06X}" if rom_offset is not None and int(rom_offset) >= 0 else None,
            "text_src": text_src,
            "text_dst": text_dst,
            "mapping_found": bool(mapping_found),
            "mapping_status": "MAPPED" if mapping_found else "FALTANDO",
            "reinsertion_safe": bool(reinsertion_safe),
            "needs_review": bool(needs_review),
            "review_flags": review_flags,
            "skip_displayed": bool(skip_displayed),
            "english_residual": bool(english_residual),
            "same_as_source_phrase": bool(same_as_source_phrase),
        }
        trace_rows.append(trace_row)

        reasons: List[str] = []
        if not mapping_found:
            reasons.append("FALTANDO_MAPPING")
        if skip_displayed:
            reasons.append("SKIP_DISPLAYED")
        if english_residual:
            reasons.append("ENGLISH_RESIDUAL_DISPLAYED")
        if same_as_source_phrase:
            reasons.append("SAME_AS_SOURCE_PHRASE_DISPLAYED")
        if reasons:
            missing_rows.append(
                {
                    "frame": trace_row["frame"],
                    "pc": trace_row["pc"],
                    "ptr_or_buf": trace_row["ptr_or_buf"],
                    "key": trace_row["key"],
                    "id": trace_row["id"],
                    "seq": trace_row["seq"],
                    "rom_offset": trace_row["rom_offset"],
                    "context_tag": trace_row["context_tag"],
                    "missing_reason_codes": sorted(set(reasons)),
                    "text_src": trace_row["text_src"],
                    "text_dst": trace_row["text_dst"],
                    "runtime_text": trace_row["runtime_text"],
                    "raw_bytes_hex": trace_row["raw_bytes_hex"],
                    "raw_len": trace_row["raw_len"],
                    "terminator": trace_row["terminator"],
                }
            )

    summary = {
        "schema": "runtime_coverage_summary.v1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "rom_crc32": str(crc).upper(),
        "rom_size": int(rom_size),
        "platform": str(platform),
        "runtime_trace_items_total": int(len(runtime_rows)),
        "runtime_displayed_trace_items_total": int(len(trace_rows)),
        "runtime_displayed_mapped_items": int(mapped_count),
        "runtime_displayed_unmapped_items": int(unmapped_count),
        "runtime_displayed_needs_review_items": int(needs_review_count),
        "runtime_displayed_skip_displayed_count": int(skip_count),
        "runtime_displayed_english_residual_count": int(english_count),
        "runtime_displayed_same_as_source_phrase_count": int(same_src_count),
        "missing_displayed_text_count": int(len(missing_rows)),
        # Aliases mantidos para compatibilidade com gates antigos/novos.
        "runtime_missing_displayed_text_count": int(len(missing_rows)),
        "runtime_skip_displayed_count": int(skip_count),
        "runtime_english_residual_count": int(english_count),
        "runtime_same_as_source_phrase_count": int(same_src_count),
        "overall_pass": bool(len(missing_rows) == 0 and english_count == 0 and skip_count == 0),
        "first_20_missing": missing_rows[:20],
    }

    trace_meta = {
        "type": "meta",
        "schema": "runtime_displayed_text_trace.v1",
        "rom_crc32": str(crc).upper(),
        "rom_size": int(rom_size),
        "platform": str(platform),
        "items_total": int(len(trace_rows)),
    }
    missing_meta = {
        "type": "meta",
        "schema": "runtime_missing_displayed_text.v1",
        "rom_crc32": str(crc).upper(),
        "rom_size": int(rom_size),
        "platform": str(platform),
        "items_total": int(len(missing_rows)),
    }
    write_jsonl(paths["trace"], trace_rows, meta=trace_meta)
    write_jsonl(paths["missing"], missing_rows, meta=missing_meta)
    write_json(paths["summary"], summary)

    proof_path = _infer_aux_artifact(proof_json, runtime_out_dir, crc, "proof.json")
    report_txt_path = _infer_aux_artifact(report_txt, runtime_out_dir, crc, "report.txt")
    report_json_path = _infer_aux_artifact(report_json, runtime_out_dir, crc, "reinsertion_report.json")

    runtime_block = {
        "enabled": True,
        "trace_path": str(runtime_trace_path),
        "runtime_displayed_text_trace_path": str(paths["trace"]),
        "runtime_missing_displayed_text_path": str(paths["missing"]),
        "runtime_coverage_summary_path": str(paths["summary"]),
        "summary": summary,
    }
    if inject_artifacts:
        _inject_runtime_block_json(proof_path, runtime_block=runtime_block, summary=summary)
        _inject_runtime_block_json(report_json_path, runtime_block=runtime_block, summary=summary)
        if report_txt_path is not None:
            _append_runtime_block_to_report(
                report_path=report_txt_path,
                summary=summary,
                artifacts={
                    "trace_path": str(paths["trace"]),
                    "missing_path": str(paths["missing"]),
                    "coverage_summary_path": str(paths["summary"]),
                },
            )

    return {
        "crc32": str(crc).upper(),
        "runtime_displayed_text_trace": str(paths["trace"]),
        "runtime_missing_displayed_text": str(paths["missing"]),
        "runtime_coverage_summary": str(paths["summary"]),
        "proof_injected": str(proof_path) if proof_path and proof_path.exists() else None,
        "report_injected": str(report_txt_path) if report_txt_path and report_txt_path.exists() else None,
        "report_json_injected": str(report_json_path) if report_json_path and report_json_path.exists() else None,
        "summary": summary,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Executa RuntimeQA opcional e integra report/proof.")
    ap.add_argument("--runtime-trace", required=True, help="Arquivo {CRC32}_runtime_trace.jsonl")
    ap.add_argument("--translated-jsonl", default=None, help="Arquivo {CRC32}_translated*.jsonl")
    ap.add_argument("--mapping-json", default=None, help="Arquivo {CRC32}_reinsertion_mapping.json")
    ap.add_argument("--out-dir", default=None, help="Diretorio de saida (default: pasta do runtime trace)")
    ap.add_argument("--proof-json", default=None, help="Arquivo {CRC32}_proof.json (opcional)")
    ap.add_argument("--report-txt", default=None, help="Arquivo {CRC32}_report.txt (opcional)")
    ap.add_argument("--report-json", default=None, help="Arquivo {CRC32}_reinsertion_report.json (opcional)")
    ap.add_argument("--rom-crc32", default=None, help="Forca CRC32")
    ap.add_argument("--rom-size", type=int, default=None, help="Forca tamanho da ROM")
    ap.add_argument("--platform", default=None, help="Forca plataforma")
    ap.add_argument(
        "--no-inject",
        action="store_true",
        help="Nao injeta bloco RUNTIME_TRACE no proof/report (somente gera artefatos runtime_*).",
    )
    args = ap.parse_args()

    runtime_trace = Path(args.runtime_trace).expanduser().resolve()
    if not runtime_trace.exists():
        raise SystemExit(f"[ERRO] runtime-trace nao encontrado: {runtime_trace}")

    result = run_runtime_qa(
        runtime_trace_path=runtime_trace,
        translated_jsonl=Path(args.translated_jsonl).expanduser().resolve() if args.translated_jsonl else None,
        mapping_json=Path(args.mapping_json).expanduser().resolve() if args.mapping_json else None,
        out_dir=Path(args.out_dir).expanduser().resolve() if args.out_dir else None,
        proof_json=Path(args.proof_json).expanduser().resolve() if args.proof_json else None,
        report_txt=Path(args.report_txt).expanduser().resolve() if args.report_txt else None,
        report_json=Path(args.report_json).expanduser().resolve() if args.report_json else None,
        force_crc=args.rom_crc32,
        force_size=args.rom_size,
        force_platform=args.platform,
        inject_artifacts=not bool(args.no_inject),
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
