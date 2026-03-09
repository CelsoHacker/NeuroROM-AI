#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera corpus limpo por CRC em lote a partir do report estrutural.

Fluxo por ROM:
1) Garante {CRC}_only_safe_text_by_offset.txt (se faltar, deriva do pure_text.jsonl)
2) Roda AutoTextAuditor (mesma heurística do projeto)
3) Gera {CRC}_only_safe_text_by_offset_clean.txt removendo offsets suspeitos
4) Gera {CRC}_only_safe_text_clean.jsonl (entrada limpa para tradução)
5) Consolida relatório batch com contagens por CRC/console
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = PROJECT_ROOT / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from auto_text_auditor import AutoTextAuditor  # type: ignore


_OFF_RE = re.compile(r"^\[(0x[0-9A-Fa-f]+)\]\s*(.*)$")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_offset(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return int(v)
    if isinstance(v, float):
        return int(v)
    s = str(v).strip()
    if not s:
        return None
    try:
        if s.lower().startswith("0x"):
            return int(s, 16)
        return int(s, 10)
    except ValueError:
        return None


def _normalize_line_text(text: str) -> str:
    t = str(text or "").replace("\r", " ").replace("\n", " ").replace("\t", " ")
    t = " ".join(t.split())
    return t.strip()


def _score_text(text: str) -> int:
    t = str(text or "")
    letters = sum(1 for c in t if c.isalpha())
    spaces = sum(1 for c in t if c.isspace())
    punct = sum(1 for c in t if c in ".,!?:;'\"-()/")
    return int((len(t) * 2) + (letters * 3) + spaces + punct)


def _count_nonempty_lines(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.strip():
                total += 1
    return int(total)


def _read_jsonl_records(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            if str(obj.get("type", "")).strip().lower() == "meta":
                continue
            yield obj


def build_only_safe_by_offset_from_pure(*, pure_path: Path, by_offset_path: Path) -> Dict[str, Any]:
    by_offset_path.parent.mkdir(parents=True, exist_ok=True)
    best: Dict[int, Tuple[int, str]] = {}
    for obj in _read_jsonl_records(pure_path):
        if not bool(obj.get("reinsertion_safe", False)):
            continue
        off = _parse_offset(obj.get("offset") or obj.get("rom_offset"))
        if off is None or off < 0:
            continue
        text = (
            obj.get("text_src")
            or obj.get("text")
            or obj.get("text_dst")
            or obj.get("translated_text")
            or ""
        )
        text = _normalize_line_text(str(text))
        if not text:
            continue
        score = _score_text(text)
        prev = best.get(off)
        if prev is None or score > prev[0]:
            best[off] = (score, text)

    rows = sorted(best.items(), key=lambda kv: int(kv[0]))
    with by_offset_path.open("w", encoding="utf-8", newline="\n") as f:
        for off, (_score, text) in rows:
            f.write(f"[0x{int(off):06X}] {text}\n")

    return {
        "rows_total": int(len(rows)),
        "generated": True,
    }


def read_suspect_offsets(suspects_path: Path) -> set[int]:
    out: set[int] = set()
    if not suspects_path.exists():
        return out
    with suspects_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _OFF_RE.match(line.strip())
            if not m:
                continue
            off = _parse_offset(m.group(1))
            if off is not None:
                out.add(int(off))
    return out


def write_clean_outputs(
    *,
    by_offset_path: Path,
    by_offset_clean_path: Path,
    clean_jsonl_path: Path,
    suspect_offsets: set[int],
) -> Dict[str, int]:
    kept: List[Tuple[int, str]] = []
    with by_offset_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            m = _OFF_RE.match(line.strip())
            if not m:
                continue
            off = _parse_offset(m.group(1))
            if off is None:
                continue
            if int(off) in suspect_offsets:
                continue
            text = _normalize_line_text(m.group(2))
            if not text:
                continue
            kept.append((int(off), text))

    kept.sort(key=lambda x: x[0])
    by_offset_clean_path.parent.mkdir(parents=True, exist_ok=True)
    with by_offset_clean_path.open("w", encoding="utf-8", newline="\n") as f:
        for off, text in kept:
            f.write(f"[0x{int(off):06X}] {text}\n")

    with clean_jsonl_path.open("w", encoding="utf-8", newline="\n") as f:
        for off, text in kept:
            row = {
                "offset": f"0x{int(off):06X}",
                "text_src": text,
                "source": "ONLY_SAFE_CLEAN",
                "reinsertion_safe": True,
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {
        "clean_rows": int(len(kept)),
        "suspects_removed": int(len(suspect_offsets)),
    }


def rel_to_project(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except Exception:
        return str(path.resolve())


def run_batch(
    *,
    source_report: Path,
    purity_min_score: int,
    keep_suspects: bool,
    fail_on_suspect: bool,
) -> Dict[str, Any]:
    src_obj = json.loads(source_report.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(src_obj, dict):
        raise RuntimeError(f"report inválido: {source_report}")

    auditor = AutoTextAuditor(
        purity_min_score=int(purity_min_score),
        keep_suspects=bool(keep_suspects),
        fail_on_suspect=bool(fail_on_suspect),
    )

    out_rows: List[Dict[str, Any]] = []
    total_processed = 0

    for console in src_obj.get("consoles", []):
        console_name = str(console.get("console", "") or "")
        for item in console.get("rom_items", []):
            crc = str(item.get("rom_crc32", "") or "").upper()
            if len(crc) != 8:
                continue
            crc_dir_rel = str(item.get("crc_dir", "") or "")
            if not crc_dir_rel:
                continue
            crc_dir = PROJECT_ROOT / crc_dir_rel
            stage_dir = crc_dir / "1_extracao"
            pure_rel = item.get("pure_jsonl")
            if not pure_rel:
                continue
            pure_path = PROJECT_ROOT / str(pure_rel)
            if not pure_path.exists():
                continue

            rom_rel = str(item.get("rom_file", "") or "")
            rom_path = (PROJECT_ROOT / rom_rel) if rom_rel else None
            if rom_path is not None and not rom_path.exists():
                rom_path = None

            by_offset_path = stage_dir / f"{crc}_only_safe_text_by_offset.txt"
            created_safe = False
            created_meta: Dict[str, Any] = {}
            if not by_offset_path.exists():
                created_meta = build_only_safe_by_offset_from_pure(
                    pure_path=pure_path,
                    by_offset_path=by_offset_path,
                )
                created_safe = True

            safe_rows = _count_nonempty_lines(by_offset_path)
            audit_result = auditor.audit(
                by_offset_path=str(by_offset_path),
                stage_dir=str(stage_dir),
                crc32=crc,
                output_path=str(stage_dir / f"{crc}_only_safe_text.txt"),
                rom_path=str(rom_path) if rom_path is not None else None,
            )
            suspects_path = Path(str(audit_result.get("suspects_path", "") or ""))
            if not suspects_path.exists():
                suspects_path = stage_dir / f"{crc}_auto_audit_suspects.txt"
            suspect_offsets = read_suspect_offsets(suspects_path)

            by_offset_clean_path = stage_dir / f"{crc}_only_safe_text_by_offset_clean.txt"
            clean_jsonl_path = stage_dir / f"{crc}_only_safe_text_clean.jsonl"
            clean_meta = write_clean_outputs(
                by_offset_path=by_offset_path,
                by_offset_clean_path=by_offset_clean_path,
                clean_jsonl_path=clean_jsonl_path,
                suspect_offsets=suspect_offsets,
            )

            out_rows.append(
                {
                    "console": console_name,
                    "crc32": crc,
                    "crc_dir": rel_to_project(crc_dir),
                    "rom_file": rom_rel,
                    "pure_jsonl": rel_to_project(pure_path),
                    "only_safe_text_by_offset": rel_to_project(by_offset_path),
                    "only_safe_text_by_offset_clean": rel_to_project(by_offset_clean_path),
                    "only_safe_text_clean_jsonl": rel_to_project(clean_jsonl_path),
                    "safe_rows_total": int(safe_rows),
                    "clean_rows_total": int(clean_meta["clean_rows"]),
                    "suspects_removed": int(clean_meta["suspects_removed"]),
                    "audit_passed": bool(audit_result.get("passed", False)),
                    "audit_fail_reason": str(audit_result.get("fail_reason", "") or ""),
                    "audit_summary": {
                        "total": int(audit_result.get("total", 0) or 0),
                        "ok": int(audit_result.get("ok", 0) or 0),
                        "suspect": int(audit_result.get("suspect", 0) or 0),
                        "error": int(audit_result.get("error", 0) or 0),
                        "purity_score": int(audit_result.get("purity_score", 0) or 0),
                    },
                    "created_only_safe_by_offset": bool(created_safe),
                    "created_only_safe_meta": created_meta,
                }
            )
            total_processed += 1

    out_rows.sort(key=lambda r: (str(r["console"]).lower(), str(r["crc32"])))

    return {
        "schema": "batch_safe_clean_audit.v1",
        "generated_at_utc": now_utc_iso(),
        "source_report": rel_to_project(source_report),
        "settings": {
            "purity_min_score": int(purity_min_score),
            "keep_suspects": bool(keep_suspects),
            "fail_on_suspect": bool(fail_on_suspect),
        },
        "summary": {
            "processed_crc_total": int(total_processed),
            "safe_rows_total": int(sum(int(r["safe_rows_total"]) for r in out_rows)),
            "clean_rows_total": int(sum(int(r["clean_rows_total"]) for r in out_rows)),
            "suspects_removed_total": int(sum(int(r["suspects_removed"]) for r in out_rows)),
        },
        "items": out_rows,
    }


def write_report_txt(path: Path, obj: Dict[str, Any]) -> None:
    lines: List[str] = []
    lines.append("BATCH SAFE CLEAN AUDIT")
    lines.append(f"generated_at_utc: {obj.get('generated_at_utc')}")
    s = obj.get("summary", {})
    lines.append("SUMMARY")
    lines.append(f"- processed_crc_total: {s.get('processed_crc_total', 0)}")
    lines.append(f"- safe_rows_total: {s.get('safe_rows_total', 0)}")
    lines.append(f"- clean_rows_total: {s.get('clean_rows_total', 0)}")
    lines.append(f"- suspects_removed_total: {s.get('suspects_removed_total', 0)}")
    lines.append("")
    lines.append("BY CRC")
    for it in obj.get("items", []):
        lines.append(
            f"[{it.get('console')}] CRC={it.get('crc32')} | "
            f"safe={it.get('safe_rows_total')} | clean={it.get('clean_rows_total')} | "
            f"suspects_removed={it.get('suspects_removed')} | "
            f"audit_passed={str(it.get('audit_passed'))}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Audita e gera safe_clean em lote por CRC.")
    ap.add_argument(
        "--source-report",
        default=str(PROJECT_ROOT / "ROMs" / "out" / "STRUCTURAL_PROOF_7CONSOLES_report.json"),
        help="Report estrutural de entrada.",
    )
    ap.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "ROMs" / "out"),
        help="Diretorio de saida dos artefatos do batch.",
    )
    ap.add_argument("--prefix", default="STRUCTURAL_PROOF_7CONSOLES_SAFE_CLEAN", help="Prefixo dos artefatos.")
    ap.add_argument("--purity-min-score", type=int, default=98)
    ap.add_argument("--keep-suspects", action="store_true")
    ap.add_argument("--fail-on-suspect", action="store_true")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    source_report = Path(args.source_report).expanduser().resolve()
    if not source_report.exists():
        raise FileNotFoundError(f"source report não encontrado: {source_report}")
    out_dir = Path(args.output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    result = run_batch(
        source_report=source_report,
        purity_min_score=int(args.purity_min_score),
        keep_suspects=bool(args.keep_suspects),
        fail_on_suspect=bool(args.fail_on_suspect),
    )

    prefix = str(args.prefix).strip() or "STRUCTURAL_PROOF_7CONSOLES_SAFE_CLEAN"
    json_path = out_dir / f"{prefix}_report.json"
    txt_path = out_dir / f"{prefix}_report.txt"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report_txt(txt_path, result)

    print(f"[SAFE_CLEAN_BATCH] report_json={json_path}")
    print(f"[SAFE_CLEAN_BATCH] report_txt={txt_path}")
    print(
        "[SAFE_CLEAN_BATCH] summary: "
        f"processed={result['summary']['processed_crc_total']} | "
        f"safe={result['summary']['safe_rows_total']} | "
        f"clean={result['summary']['clean_rows_total']} | "
        f"suspects_removed={result['summary']['suspects_removed_total']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
