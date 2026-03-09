#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prova estrutural em lote para 7 consoles (escopo por ROM/CRC).

Gera 3 artefatos auditaveis:
1) <prefix>_report.json
2) <prefix>_report.txt
3) <prefix>_proof.json

Fluxo:
- Lista ROMs por pasta de console
- Resolve identidade da ROM por CRC32/rom_size
- Garante estrutura CRC/<1_extracao,2_traducao,3_reinsercao>
- Opcionalmente roda extracao universal quando faltar *_pure_text.jsonl
- Consolida metricas de texto bruto/safe/clean por ROM e por console
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROMS_ROOT = PROJECT_ROOT / "ROMs"
DEFAULT_OUT_DIR = DEFAULT_ROMS_ROOT / "out"

DEFAULT_CONSOLES = [
    "Master System",
    "Nintedinho",
    "Super Nintedo",
    "GBA",
    "Nintedo 64",
    "Mega",
    "Playstation 1",
]

ROM_EXTS_BY_FOLDER = {
    "Master System": {".sms", ".sg", ".gg"},
    "Nintedinho": {".nes"},
    "Super Nintedo": {".sfc", ".smc"},
    "GBA": {".gba"},
    "Nintedo 64": {".z64", ".n64", ".v64"},
    "Mega": {".bin", ".gen", ".md", ".smd"},
    "Playstation 1": {".cue", ".chd", ".iso", ".pbp", ".ccd", ".img", ".mds", ".bin", ".psx"},
}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def crc32_of_file(path: Path, chunk_size: int = 1 << 20) -> str:
    crc = 0
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            crc = zlib.crc32(chunk, crc)
    return f"{crc & 0xFFFFFFFF:08X}"


def is_crc_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    name = path.name
    return len(name) == 8 and all(ch in "0123456789ABCDEFabcdef" for ch in name)


def rel_to_project(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except Exception:
        return str(path.resolve())


def ensure_crc_layout(console_dir: Path, crc: str, rom_path: Path) -> Path:
    crc_dir = console_dir / crc.upper()
    (crc_dir / "1_extracao").mkdir(parents=True, exist_ok=True)
    (crc_dir / "2_traducao").mkdir(parents=True, exist_ok=True)
    (crc_dir / "3_reinsercao").mkdir(parents=True, exist_ok=True)

    manifest_path = crc_dir / "crc_bootstrap_manifest.json"
    if not manifest_path.exists():
        manifest = {
            "generated_at": now_utc_iso(),
            "console": console_dir.name,
            "rom_file": str(rom_path.resolve()),
            "rom_file_name": rom_path.name,
            "rom_size": int(rom_path.stat().st_size),
            "rom_crc32": crc.upper(),
            "status": "BOOTSTRAPPED_BY_STRUCTURAL_PROOF",
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return crc_dir


def run_universal_extract(rom_path: Path, extract_dir: Path, timeout_s: int) -> Dict[str, Any]:
    cmd = [
        sys.executable,
        str((PROJECT_ROOT / "core" / "universal_translator.py").resolve()),
        str(rom_path.resolve()),
        str(extract_dir.resolve()),
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(60, int(timeout_s)),
        )
        duration_s = round(time.time() - t0, 3)
        return {
            "ok": int(proc.returncode) == 0,
            "returncode": int(proc.returncode),
            "duration_s": duration_s,
            "stdout_tail": "\n".join(proc.stdout.splitlines()[-25:]),
            "stderr_tail": "\n".join(proc.stderr.splitlines()[-25:]),
            "cmd": cmd,
        }
    except subprocess.TimeoutExpired:
        duration_s = round(time.time() - t0, 3)
        return {
            "ok": False,
            "returncode": -999,
            "duration_s": duration_s,
            "stdout_tail": "",
            "stderr_tail": f"TIMEOUT after {timeout_s}s",
            "cmd": cmd,
        }


def find_pure_jsonl(extract_dir: Path, crc: str) -> Optional[Path]:
    expected = extract_dir / f"{crc.upper()}_pure_text.jsonl"
    if expected.exists():
        return expected.resolve()
    cands = sorted(extract_dir.glob("*_pure_text.jsonl"), key=lambda p: p.name.lower())
    if not cands:
        return None
    preferred = [p for p in cands if p.name.upper().startswith(f"{crc.upper()}_")]
    return (preferred[0] if preferred else cands[0]).resolve()


def _safe_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        t = v.strip().lower()
        return t in {"1", "true", "yes", "y"}
    return False


def count_pure_jsonl(pure_path: Path) -> Dict[str, int]:
    rows_total = 0
    safe_items = 0
    offsets_total = set()
    offsets_safe = set()
    with pure_path.open("r", encoding="utf-8", errors="replace") as f:
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
            rows_total += 1
            off = str(obj.get("offset") or obj.get("rom_offset") or "").strip().upper()
            if off:
                offsets_total.add(off)
            if _safe_bool(obj.get("reinsertion_safe", False)):
                safe_items += 1
                if off:
                    offsets_safe.add(off)
    return {
        "textlike_items_total": int(rows_total),
        "reinsertion_safe_items_total": int(safe_items),
        "textlike_unique_offsets_total": int(len(offsets_total)),
        "reinsertion_safe_unique_offsets_total": int(len(offsets_safe)),
    }


def count_nonempty_lines(path: Optional[Path]) -> int:
    if path is None or not path.exists():
        return 0
    total = 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.strip():
                total += 1
    return int(total)


def load_audit_summary(audit_json: Optional[Path]) -> Dict[str, Any]:
    if audit_json is None or not audit_json.exists():
        return {}
    try:
        obj = json.loads(audit_json.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    if not isinstance(obj, dict):
        return {}
    summary = obj.get("summary", {})
    if isinstance(summary, dict):
        return summary
    return {}


def collect_console(
    *,
    roms_root: Path,
    console_name: str,
    extract_missing: bool,
    timeout_s: int,
    hash_rom_files: bool,
) -> Dict[str, Any]:
    console_dir = roms_root / console_name
    if not console_dir.exists():
        return {
            "console": console_name,
            "status": "MISSING_CONSOLE_DIR",
            "rom_items": [],
            "summary": {
                "rom_files_total": 0,
                "crc_dirs_total": 0,
                "extracted_total": 0,
                "missing_extraction_total": 0,
                "textlike_items_total": 0,
                "reinsertion_safe_unique_offsets_total": 0,
                "safe_clean_rows_total": 0,
            },
        }

    exts = ROM_EXTS_BY_FOLDER.get(console_name, set())
    rom_files = sorted(
        [
            p
            for p in console_dir.iterdir()
            if p.is_file() and (not exts or p.suffix.lower() in exts)
        ],
        key=lambda p: p.name.lower(),
    )

    rom_items: List[Dict[str, Any]] = []
    sum_textlike = 0
    sum_safe_offsets = 0
    sum_safe_clean_rows = 0
    extracted_total = 0
    missing_total = 0

    for rom_path in rom_files:
        crc = crc32_of_file(rom_path)
        rom_size = int(rom_path.stat().st_size)
        crc_dir = ensure_crc_layout(console_dir, crc, rom_path)
        extract_dir = crc_dir / "1_extracao"
        pure_path = find_pure_jsonl(extract_dir, crc)

        extract_result: Optional[Dict[str, Any]] = None
        if pure_path is None and extract_missing:
            extract_result = run_universal_extract(
                rom_path=rom_path,
                extract_dir=extract_dir,
                timeout_s=timeout_s,
            )
            pure_path = find_pure_jsonl(extract_dir, crc)

        only_safe = extract_dir / f"{crc}_only_safe_text_by_offset.txt"
        safe_clean = extract_dir / f"{crc}_only_safe_text_by_offset_clean.txt"
        safe_clean_jsonl = extract_dir / f"{crc}_only_safe_text_clean.jsonl"
        audit_json = extract_dir / f"{crc}_auto_audit_report.json"

        pure_stats = count_pure_jsonl(pure_path) if pure_path is not None else {}
        safe_clean_rows = count_nonempty_lines(safe_clean_jsonl)
        if safe_clean_rows <= 0:
            safe_clean_rows = count_nonempty_lines(safe_clean)

        audit_summary = load_audit_summary(audit_json if audit_json.exists() else None)
        extracted_ok = pure_path is not None and pure_path.exists()
        if extracted_ok:
            extracted_total += 1
            sum_textlike += int(pure_stats.get("textlike_items_total", 0))
            sum_safe_offsets += int(pure_stats.get("reinsertion_safe_unique_offsets_total", 0))
            sum_safe_clean_rows += int(safe_clean_rows)
        else:
            missing_total += 1

        item = {
            "console": console_name,
            "rom_file": rel_to_project(rom_path),
            "rom_name": rom_path.name,
            "rom_crc32": crc,
            "rom_size": rom_size,
            "crc_dir": rel_to_project(crc_dir),
            "pure_jsonl": rel_to_project(pure_path) if pure_path is not None else None,
            "only_safe_text_by_offset": rel_to_project(only_safe) if only_safe.exists() else None,
            "safe_clean_jsonl": rel_to_project(safe_clean_jsonl) if safe_clean_jsonl.exists() else None,
            "safe_clean_by_offset": rel_to_project(safe_clean) if safe_clean.exists() else None,
            "audit_report_json": rel_to_project(audit_json) if audit_json.exists() else None,
            "extracted_ok": bool(extracted_ok),
            "extract_attempted": bool(extract_result is not None),
            "extract_result": extract_result,
            "metrics": {
                **pure_stats,
                "safe_clean_rows_total": int(safe_clean_rows),
            },
            "audit_summary": audit_summary,
        }
        if hash_rom_files:
            item["rom_sha256"] = sha256_file(rom_path)
        rom_items.append(item)

    crc_dirs_total = len([p for p in console_dir.iterdir() if is_crc_dir(p)])
    return {
        "console": console_name,
        "status": "OK",
        "rom_items": rom_items,
        "summary": {
            "rom_files_total": int(len(rom_files)),
            "crc_dirs_total": int(crc_dirs_total),
            "extracted_total": int(extracted_total),
            "missing_extraction_total": int(missing_total),
            "textlike_items_total": int(sum_textlike),
            "reinsertion_safe_unique_offsets_total": int(sum_safe_offsets),
            "safe_clean_rows_total": int(sum_safe_clean_rows),
        },
    }


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_report_txt(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("STRUCTURAL PROOF - 7 CONSOLES")
    lines.append(f"generated_at_utc: {report.get('generated_at_utc')}")
    lines.append(f"roms_root: {report.get('roms_root')}")
    lines.append("")
    g = report.get("global_summary", {})
    lines.append("GLOBAL SUMMARY")
    lines.append(f"- consoles_requested: {g.get('consoles_requested', 0)}")
    lines.append(f"- consoles_found: {g.get('consoles_found', 0)}")
    lines.append(f"- rom_files_total: {g.get('rom_files_total', 0)}")
    lines.append(f"- extracted_total: {g.get('extracted_total', 0)}")
    lines.append(f"- missing_extraction_total: {g.get('missing_extraction_total', 0)}")
    lines.append(f"- textlike_items_total: {g.get('textlike_items_total', 0)}")
    lines.append(
        f"- reinsertion_safe_unique_offsets_total: {g.get('reinsertion_safe_unique_offsets_total', 0)}"
    )
    lines.append(f"- safe_clean_rows_total: {g.get('safe_clean_rows_total', 0)}")
    lines.append("")

    lines.append("BY CONSOLE")
    for c in report.get("consoles", []):
        name = c.get("console", "")
        st = c.get("status", "UNKNOWN")
        s = c.get("summary", {})
        lines.append(f"- {name}: status={st}")
        lines.append(
            "  "
            + (
                f"rom_files={s.get('rom_files_total', 0)} | "
                f"extracted={s.get('extracted_total', 0)} | "
                f"missing={s.get('missing_extraction_total', 0)} | "
                f"textlike={s.get('textlike_items_total', 0)} | "
                f"safe_offsets={s.get('reinsertion_safe_unique_offsets_total', 0)} | "
                f"safe_clean_rows={s.get('safe_clean_rows_total', 0)}"
            )
        )
    lines.append("")
    lines.append("NOTA")
    lines.append(
        "- textlike_items_total inclui candidatos brutos (pode conter ruido/duplicatas). "
        "safe_clean_rows_total e o escopo recomendado de traducao limpa."
    )
    return "\n".join(lines) + "\n"


def iter_files_for_proof(report: Dict[str, Any], report_json_path: Path, report_txt_path: Path) -> Iterable[Tuple[str, Path]]:
    yield ("report_json", report_json_path)
    yield ("report_txt", report_txt_path)
    for console in report.get("consoles", []):
        for item in console.get("rom_items", []):
            for role in [
                "pure_jsonl",
                "only_safe_text_by_offset",
                "safe_clean_jsonl",
                "safe_clean_by_offset",
                "audit_report_json",
            ]:
                rel = item.get(role)
                if not rel:
                    continue
                p = PROJECT_ROOT / str(rel)
                if p.exists():
                    yield (role, p)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Gera prova estrutural consolidada para 7 consoles."
    )
    ap.add_argument("--roms-root", default=str(DEFAULT_ROMS_ROOT), help="Raiz ROMs.")
    ap.add_argument("--output-dir", default=str(DEFAULT_OUT_DIR), help="Diretorio de saida dos artefatos.")
    ap.add_argument(
        "--consoles",
        nargs="*",
        default=list(DEFAULT_CONSOLES),
        help="Lista de pastas de consoles (default = 7 consoles padrao).",
    )
    ap.add_argument(
        "--extract-missing",
        action="store_true",
        help="Quando faltar *_pure_text.jsonl, roda universal_translator automaticamente.",
    )
    ap.add_argument("--timeout-s", type=int, default=1200, help="Timeout por extração automatica.")
    ap.add_argument(
        "--hash-rom-files",
        action="store_true",
        help="Inclui sha256 das ROMs no report (mais lento).",
    )
    ap.add_argument(
        "--report-prefix",
        default="STRUCTURAL_PROOF_7CONSOLES",
        help="Prefixo dos 3 artefatos.",
    )
    ap.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Retorna erro se houver ROM sem extração.",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    roms_root = Path(args.roms_root).expanduser().resolve()
    out_dir = Path(args.output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    consoles = [str(c).strip() for c in (args.consoles or []) if str(c).strip()]
    if not consoles:
        consoles = list(DEFAULT_CONSOLES)

    report: Dict[str, Any] = {
        "schema": "structural_proof_7consoles.v1",
        "generated_at_utc": now_utc_iso(),
        "roms_root": str(roms_root),
        "settings": {
            "consoles": consoles,
            "extract_missing": bool(args.extract_missing),
            "timeout_s": int(args.timeout_s),
            "hash_rom_files": bool(args.hash_rom_files),
        },
        "consoles": [],
    }

    g_roms = 0
    g_consoles_found = 0
    g_extracted = 0
    g_missing = 0
    g_textlike = 0
    g_safe_offsets = 0
    g_safe_clean = 0

    for console_name in consoles:
        data = collect_console(
            roms_root=roms_root,
            console_name=console_name,
            extract_missing=bool(args.extract_missing),
            timeout_s=int(args.timeout_s),
            hash_rom_files=bool(args.hash_rom_files),
        )
        report["consoles"].append(data)
        summary = data.get("summary", {})
        g_roms += int(summary.get("rom_files_total", 0) or 0)
        if data.get("status") != "MISSING_CONSOLE_DIR":
            g_consoles_found += 1
        g_extracted += int(summary.get("extracted_total", 0) or 0)
        g_missing += int(summary.get("missing_extraction_total", 0) or 0)
        g_textlike += int(summary.get("textlike_items_total", 0) or 0)
        g_safe_offsets += int(summary.get("reinsertion_safe_unique_offsets_total", 0) or 0)
        g_safe_clean += int(summary.get("safe_clean_rows_total", 0) or 0)

    report["global_summary"] = {
        "consoles_requested": int(len(consoles)),
        "consoles_found": int(g_consoles_found),
        "rom_files_total": int(g_roms),
        "extracted_total": int(g_extracted),
        "missing_extraction_total": int(g_missing),
        "textlike_items_total": int(g_textlike),
        "reinsertion_safe_unique_offsets_total": int(g_safe_offsets),
        "safe_clean_rows_total": int(g_safe_clean),
    }

    prefix = str(args.report_prefix).strip() or "STRUCTURAL_PROOF_7CONSOLES"
    report_json_path = out_dir / f"{prefix}_report.json"
    report_txt_path = out_dir / f"{prefix}_report.txt"
    proof_json_path = out_dir / f"{prefix}_proof.json"

    write_json(report_json_path, report)
    report_txt_path.write_text(build_report_txt(report), encoding="utf-8")

    proof_files: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for role, path in iter_files_for_proof(report, report_json_path, report_txt_path):
        key = str(path.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        proof_files.append(
            {
                "role": role,
                "path": rel_to_project(path),
                "sha256": sha256_file(path),
                "size": int(path.stat().st_size),
            }
        )

    proof = {
        "schema": "structural_proof_7consoles_files.v1",
        "generated_at_utc": now_utc_iso(),
        "report_json_path": rel_to_project(report_json_path),
        "report_txt_path": rel_to_project(report_txt_path),
        "report_json_sha256": sha256_file(report_json_path),
        "report_txt_sha256": sha256_file(report_txt_path),
        "files": proof_files,
    }
    write_json(proof_json_path, proof)

    print(f"[STRUCT_PROOF] report_json={report_json_path}")
    print(f"[STRUCT_PROOF] report_txt={report_txt_path}")
    print(f"[STRUCT_PROOF] proof_json={proof_json_path}")
    print(
        "[STRUCT_PROOF] summary: "
        f"roms={report['global_summary']['rom_files_total']} | "
        f"extracted={report['global_summary']['extracted_total']} | "
        f"missing={report['global_summary']['missing_extraction_total']}"
    )

    if bool(args.fail_on_missing) and int(report["global_summary"]["missing_extraction_total"]) > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
