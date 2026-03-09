#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Execucao em lote do Universal Translator (extracao) para um console.
"""

from __future__ import annotations

import argparse
import json
import sys
import zlib
from datetime import datetime
from pathlib import Path
import subprocess
from typing import Dict

ROM_EXTS_BY_CONSOLE = {
    "master system": {".sms", ".sg", ".gg"},
    "nintendinho": {".nes"},
    "super nintendo": {".sfc", ".smc"},
    "gba": {".gba"},
    "nintendo 64": {".z64", ".n64", ".v64"},
    "mega drive": {".bin", ".gen", ".md", ".smd"},
    "ps1": {".cue", ".chd", ".iso", ".pbp", ".ccd", ".img", ".mds", ".bin", ".psx"},
}


def _safe_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in " ._-()" else "_" for ch in name).strip()


def _load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _match_console(console: str, source_name: str) -> bool:
    c = console.lower().strip()
    s = source_name.lower().strip()
    if c in s:
        return True
    if c == "ps1" and s.startswith("ps1"):
        return True
    return False


def _fallback_console_dir(console: str) -> Path:
    """Fallback para estrutura local ROMs/<console> quando config não cobre o console."""
    normalized = console.lower().strip()
    name_map = {
        "master system": "Master System",
        "nintendinho": "Nintedinho",
        "super nintendo": "Super Nintedo",
        "gba": "GBA",
        "nintendo 64": "Nintedo 64",
        "mega drive": "Mega",
        "ps1": "Playstation 1",
    }
    folder = name_map.get(normalized, "")
    if not folder:
        return Path("")
    return Path("ROMs") / folder


def _collect_roms(paths: list[Path], exts: set[str]) -> list[Path]:
    roms = []
    seen = set()
    for root in paths:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() in exts:
                key = str(p.resolve()).lower()
                if key not in seen:
                    seen.add(key)
                    roms.append(p)
    return sorted(roms, key=lambda x: x.name.lower())


def _crc32(path: Path) -> str:
    data = path.read_bytes()
    return f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"


def _run_universal(rom_path: Path, out_dir: Path) -> dict:
    cmd = [
        sys.executable,
        str(Path("core") / "universal_translator.py"),
        str(rom_path),
        str(out_dir),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _classify_run(run: Dict[str, str | int], out_dir: Path) -> tuple[str, str]:
    """Classifica resultado com base em retorno, logs e artefatos gerados."""
    stdout = str(run.get("stdout", "") or "")
    stderr = str(run.get("stderr", "") or "")
    text = (stdout + "\n" + stderr).lower()

    pure_jsonl_found = any(out_dir.glob("*_pure_text.jsonl"))
    report_found = any(out_dir.glob("*_report.txt"))

    if int(run.get("returncode", 1)) != 0:
        return "erro", "returncode_nonzero"

    if "not yet implemented" in text or "coming soon" in text:
        return "nao_implementado", "driver_not_implemented"

    if "error:" in text or "[erro]" in text:
        if pure_jsonl_found:
            return "parcial", "error_logged_with_partial_output"
        return "erro", "error_logged_no_output"

    if pure_jsonl_found:
        return "ok", "pure_jsonl_generated"

    if report_found:
        return "parcial", "report_without_pure_jsonl"

    return "erro", "no_output_generated"


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch Universal Translator.")
    parser.add_argument(
        "--config",
        default=str(Path("config") / "rom_sources.json"),
        help="Caminho do JSON de fontes.",
    )
    parser.add_argument(
        "--console",
        required=True,
        help="Console alvo (ex: Master System, Nintendinho, Super Nintendo, GBA, Nintendo 64, PS1).",
    )
    parser.add_argument(
        "--output-root",
        default=str(Path("export") / "universal_batch"),
        help="Diretorio base de saida.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Pular ROMs ja processadas (report existente).",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=0,
        help="Limitar numero de ROMs (0 = sem limite).",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"[ERRO] Config nao encontrado: {config_path}")
        return 1

    console_key = args.console.lower().strip()
    exts = ROM_EXTS_BY_CONSOLE.get(console_key)
    if not exts:
        print(f"[ERRO] Console nao suportado: {args.console}")
        print(f"Suportados: {', '.join(sorted(ROM_EXTS_BY_CONSOLE.keys()))}")
        return 1

    cfg = _load_config(config_path)
    extraction_root = Path(cfg.get("extraction_root", ""))
    sources = cfg.get("sources", [])

    source_paths = []
    for src in sources:
        name = src.get("name", "")
        if _match_console(args.console, name):
            source_paths.append(Path(src.get("path", "")))
            if extraction_root:
                source_paths.append(extraction_root / _safe_name(name))

    source_paths = [p for p in source_paths if p and p.exists()]
    if not source_paths:
        fallback = _fallback_console_dir(args.console)
        if fallback and fallback.exists():
            source_paths = [fallback]
            print(f"[INFO] Fonte da config ausente para {args.console}. Usando fallback local: {fallback}")
        else:
            print(f"[ERRO] Nenhuma fonte encontrada para: {args.console}")
            return 1

    roms = _collect_roms(source_paths, exts)
    if args.max and args.max > 0:
        roms = roms[: args.max]

    out_root = Path(args.output_root) / _safe_name(args.console)
    out_root.mkdir(parents=True, exist_ok=True)
    batch_log = out_root / f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    results = {
        "console": args.console,
        "generated_at": datetime.now().isoformat(),
        "rom_count": len(roms),
        "items": [],
    }

    for idx, rom in enumerate(roms, 1):
        crc = _crc32(rom)
        safe_stem = _safe_name(rom.stem)
        out_dir = out_root / f"{safe_stem}_{crc}"
        report_exists = any(out_dir.glob("*_report.txt"))
        if args.resume and report_exists:
            results["items"].append(
                {
                    "rom": str(rom),
                    "crc32": crc,
                    "output_dir": str(out_dir),
                    "status": "skipped",
                    "reason": "report_existente",
                }
            )
            continue

        out_dir.mkdir(parents=True, exist_ok=True)
        run = _run_universal(rom, out_dir)
        status, reason = _classify_run(run, out_dir)
        pure_jsonl_count = len(list(out_dir.glob("*_pure_text.jsonl")))
        report_count = len(list(out_dir.glob("*_report.txt")))
        results["items"].append(
            {
                "rom": str(rom),
                "crc32": crc,
                "output_dir": str(out_dir),
                "status": status,
                "reason": reason,
                "returncode": run["returncode"],
                "pure_jsonl_count": pure_jsonl_count,
                "report_count": report_count,
            }
        )
        log_path = out_dir / "run.log"
        log_path.write_text(
            run["stdout"] + ("\n" + run["stderr"] if run["stderr"] else ""),
            encoding="utf-8",
        )

        print(
            f"[{idx}/{len(roms)}] {rom.name} -> {status} "
            f"(reason={reason}, pure_jsonl={pure_jsonl_count}, report={report_count})"
        )

    with batch_log.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=True)

    print(f"[OK] Batch report: {batch_log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
