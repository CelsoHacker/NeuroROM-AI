#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Executa run_codec_mastery_pipeline em lote e gera ranking final por ROM.

Objetivo:
- Rodar engenharia de codec em escala para todos os consoles/pastas disponíveis
- Produzir ranking consolidado com:
  GAIN, PATCH_OK, READY_FOR_REINSERT
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROM_EXTS = {".nes", ".sms", ".gg", ".md", ".gen", ".smd", ".smc", ".sfc", ".gba", ".bin", ".z64", ".n64", ".v64"}


@dataclass
class WorkItem:
    console: str
    crc32: str
    pure_jsonl: Path
    translation_jsonl: Optional[Path]
    patch_out_jsonl: Optional[Path]
    out_dir: Path


def detect_consoles(roms_root: Path) -> List[Path]:
    return sorted([p for p in roms_root.iterdir() if p.is_dir()], key=lambda p: p.name.lower())


def crc32_of_file(path: Path, chunk_size: int = 1 << 20) -> str:
    crc = 0
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            crc = zlib.crc32(chunk, crc)
    return f"{crc & 0xFFFFFFFF:08X}"


def find_crc_workdirs(console_dir: Path) -> List[Path]:
    out: List[Path] = []
    for p in sorted(console_dir.iterdir(), key=lambda x: x.name.lower()):
        if not p.is_dir():
            continue
        if len(p.name) == 8 and all(ch in "0123456789ABCDEFabcdef" for ch in p.name):
            out.append(p)
    return out


def read_bootstrap_manifest(crc_dir: Path) -> Dict[str, Any]:
    manifest_path = crc_dir / "crc_bootstrap_manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    if isinstance(data, dict):
        return data
    return {}


def find_rom_for_crc(console_dir: Path, crc_dir: Path, crc: str) -> Optional[Path]:
    """Encontra ROM original correspondente ao CRC da pasta."""
    manifest = read_bootstrap_manifest(crc_dir)
    rom_from_manifest = manifest.get("rom_file")
    if isinstance(rom_from_manifest, str) and rom_from_manifest:
        p = Path(rom_from_manifest)
        if p.exists() and p.is_file():
            try:
                if crc32_of_file(p) == crc.upper():
                    return p
            except Exception:
                pass

    for p in sorted(console_dir.iterdir(), key=lambda x: x.name.lower()):
        if not f_is_rom(p):
            continue
        try:
            if crc32_of_file(p) == crc.upper():
                return p
        except Exception:
            continue
    return None


def auto_extract_missing_pure_jsonl(rom_file: Path, out_dir: Path, crc: str) -> Dict[str, Any]:
    """Executa universal_translator para preencher {CRC}_pure_text.jsonl ausente."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str((Path(__file__).resolve().parents[1] / "core" / "universal_translator.py").resolve()),
        str(rom_file),
        str(out_dir),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    pure_jsonl = out_dir / f"{crc.upper()}_pure_text.jsonl"
    ok = bool(proc.returncode == 0 and pure_jsonl.exists())
    return {
        "ok": ok,
        "returncode": int(proc.returncode),
        "pure_jsonl": str(pure_jsonl) if pure_jsonl.exists() else None,
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-20:]),
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-20:]),
    }


def bootstrap_crc_workdirs_from_roms(console_dir: Path) -> List[Dict[str, Any]]:
    """Cria estrutura CRC a partir das ROMs brutas da pasta do console."""
    created: List[Dict[str, Any]] = []
    rom_files = [p for p in sorted(console_dir.iterdir(), key=lambda x: x.name.lower()) if f_is_rom(p)]
    for rom_file in rom_files:
        try:
            crc = crc32_of_file(rom_file)
        except Exception as e:
            created.append(
                {
                    "console": console_dir.name,
                    "rom_file": str(rom_file),
                    "status": "CRC_ERROR",
                    "error": str(e),
                }
            )
            continue
        crc_dir = console_dir / crc
        (crc_dir / "1_extracao").mkdir(parents=True, exist_ok=True)
        (crc_dir / "2_traducao").mkdir(parents=True, exist_ok=True)
        (crc_dir / "3_reinsercao").mkdir(parents=True, exist_ok=True)
        manifest_path = crc_dir / "crc_bootstrap_manifest.json"
        manifest = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "console": console_dir.name,
            "rom_file": str(rom_file),
            "rom_file_name": rom_file.name,
            "rom_size": int(rom_file.stat().st_size),
            "rom_crc32": crc,
            "status": "BOOTSTRAPPED_NO_PURE_JSONL",
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        created.append(
            {
                "console": console_dir.name,
                "rom_file": str(rom_file),
                "crc32": crc,
                "crc_dir": str(crc_dir),
                "manifest": str(manifest_path),
                "status": "BOOTSTRAPPED",
            }
        )
    return created


def f_is_rom(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in ROM_EXTS


def find_translation_jsonl(crc_dir: Path, crc: str) -> Optional[Path]:
    trad_dir = crc_dir / "2_traducao"
    if not trad_dir.exists():
        return None
    preferred = [
        trad_dir / f"{crc}_translated_fixed_ptbr.jsonl",
        trad_dir / f"{crc}_translated_fixed_ptbr_patched.jsonl",
        trad_dir / f"{crc}_translated_fixed.jsonl",
        trad_dir / f"{crc}_translated.jsonl",
    ]
    for p in preferred:
        if p.exists():
            return p
    candidates = sorted(trad_dir.glob("*translated*.jsonl"))
    return candidates[0] if candidates else None


def discover_work_items(
    roms_root: Path,
    bootstrap_crc_from_roms: bool = False,
    auto_extract_missing: bool = False,
) -> Tuple[List[WorkItem], List[Dict[str, Any]], List[Dict[str, Any]]]:
    items: List[WorkItem] = []
    skipped: List[Dict[str, Any]] = []
    bootstrapped: List[Dict[str, Any]] = []

    for console_dir in detect_consoles(roms_root):
        console_name = console_dir.name
        crc_dirs = find_crc_workdirs(console_dir)
        if (not crc_dirs) and bootstrap_crc_from_roms:
            created = bootstrap_crc_workdirs_from_roms(console_dir)
            bootstrapped.extend(created)
            crc_dirs = find_crc_workdirs(console_dir)
        if not crc_dirs:
            # Console sem estrutura CRC ainda.
            rom_files = [f for f in console_dir.iterdir() if f_is_rom(f)]
            skipped.append(
                {
                    "console": console_name,
                    "reason": "NO_CRC_WORKDIR",
                    "rom_files": [str(f) for f in rom_files[:50]],
                    "rom_files_count": len(rom_files),
                }
            )
            continue

        for crc_dir in crc_dirs:
            crc = crc_dir.name.upper()
            pure_jsonl = crc_dir / "1_extracao" / f"{crc}_pure_text.jsonl"
            if not pure_jsonl.exists():
                if auto_extract_missing:
                    rom_file = find_rom_for_crc(console_dir, crc_dir, crc)
                    if rom_file is not None:
                        auto = auto_extract_missing_pure_jsonl(
                            rom_file=rom_file,
                            out_dir=crc_dir / "1_extracao",
                            crc=crc,
                        )
                        if auto.get("ok"):
                            pure_jsonl = crc_dir / "1_extracao" / f"{crc}_pure_text.jsonl"
                        else:
                            skipped.append(
                                {
                                    "console": console_name,
                                    "crc32": crc,
                                    "crc_dir": str(crc_dir),
                                    "reason": "AUTO_EXTRACT_FAILED",
                                    "rom_file": str(rom_file),
                                    "auto_extract_returncode": auto.get("returncode"),
                                    "auto_extract_stdout_tail": auto.get("stdout_tail"),
                                    "auto_extract_stderr_tail": auto.get("stderr_tail"),
                                }
                            )
                            continue
                    else:
                        skipped.append(
                            {
                                "console": console_name,
                                "crc32": crc,
                                "crc_dir": str(crc_dir),
                                "reason": "NO_PURE_JSONL_NO_ROM_MATCH",
                            }
                        )
                        continue

            if not pure_jsonl.exists():
                skipped.append(
                    {
                        "console": console_name,
                        "crc32": crc,
                        "crc_dir": str(crc_dir),
                        "reason": "NO_PURE_JSONL",
                    }
                )
                continue
            translation_jsonl = find_translation_jsonl(crc_dir, crc)
            patch_out_jsonl = (
                translation_jsonl.with_name(f"{crc}_translated_fixed_ptbr_patched.jsonl")
                if translation_jsonl is not None
                else None
            )
            items.append(
                WorkItem(
                    console=console_name,
                    crc32=crc,
                    pure_jsonl=pure_jsonl,
                    translation_jsonl=translation_jsonl,
                    patch_out_jsonl=patch_out_jsonl,
                    out_dir=crc_dir / "1_extracao",
                )
            )
    return items, skipped, bootstrapped


def run_one(item: WorkItem, model: str, timeout: int, batch_size: int) -> Dict[str, Any]:
    cmd = [
        sys.executable,
        str((Path(__file__).resolve().parent / "run_codec_mastery_pipeline.py").resolve()),
        "--pure-jsonl",
        str(item.pure_jsonl),
        "--out-dir",
        str(item.out_dir),
        "--install-profile",
        "--model",
        str(model),
        "--timeout",
        str(int(timeout)),
        "--batch-size",
        str(int(batch_size)),
    ]
    if item.translation_jsonl is not None:
        cmd.extend(["--translation-jsonl", str(item.translation_jsonl)])
    if item.patch_out_jsonl is not None:
        cmd.extend(["--patch-out-jsonl", str(item.patch_out_jsonl)])

    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    summary_json = item.out_dir / f"{item.crc32}_codec_mastery_summary.json"
    summary = {}
    if summary_json.exists():
        try:
            summary = json.loads(summary_json.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            summary = {}
    return {
        "console": item.console,
        "crc32": item.crc32,
        "pure_jsonl": str(item.pure_jsonl),
        "translation_jsonl": str(item.translation_jsonl) if item.translation_jsonl else None,
        "returncode": int(proc.returncode),
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-25:]),
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-25:]),
        "summary_json": str(summary_json) if summary_json.exists() else None,
        "summary": summary,
        "ok": bool(proc.returncode == 0 and bool(summary)),
    }


def parse_patch_report(path: Path) -> Dict[str, Any]:
    out = {"patched_changed": None, "patched_blocked": None, "patch_ok": None}
    if not path.exists():
        return out
    kv: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        kv[k.strip()] = v.strip()
    try:
        out["patched_changed"] = int(kv.get("patched_changed", "0"))
        out["patched_blocked"] = int(kv.get("patched_blocked", "0"))
        out["patch_ok"] = bool(out["patched_blocked"] == 0)
    except Exception:
        pass
    return out


def build_ranking(results: List[Dict[str, Any]], skipped: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for r in results:
        s = r.get("summary", {}) if isinstance(r.get("summary"), dict) else {}
        patch_result = s.get("patch_result", {}) if isinstance(s, dict) else {}
        pure_jsonl = Path(r.get("pure_jsonl"))
        crc = str(r.get("crc32"))
        patch_report = pure_jsonl.parent.parent / "2_traducao" / f"{crc}_translated_fixed_ptbr_patched_patch_report.txt"
        patch_stats = parse_patch_report(patch_report)

        gain = int(s.get("probe_candidates_gain", 0) or 0)
        patch_ok = patch_result.get("ok")
        if patch_ok is None:
            patch_ok = patch_stats.get("patch_ok")
        patched_changed = patch_stats.get("patched_changed")
        patched_blocked = patch_stats.get("patched_blocked")

        ready = bool(
            r.get("ok")
            and bool(s.get("probe_profile_loaded", False))
            and bool(s.get("probe_profile_applied", False))
            and (patch_ok is True if patch_result.get("requested", False) else True)
            and (patched_blocked in (None, 0))
        )

        rows.append(
            {
                "console": r.get("console"),
                "crc32": crc,
                "gain": gain,
                "patch_ok": patch_ok,
                "patched_changed": patched_changed,
                "patched_blocked": patched_blocked,
                "ready_for_reinsert": ready,
                "summary_json": r.get("summary_json"),
                "status": "OK" if r.get("ok") else "FAILED",
            }
        )

    # Inclui pendências dos consoles/ROMs sem pure_jsonl.
    for sk in skipped:
        rows.append(
            {
                "console": sk.get("console"),
                "crc32": sk.get("crc32"),
                "gain": None,
                "patch_ok": None,
                "patched_changed": None,
                "patched_blocked": None,
                "ready_for_reinsert": False,
                "summary_json": None,
                "status": sk.get("reason", "SKIPPED"),
            }
        )

    def _sort_key(row: Dict[str, Any]) -> Tuple[int, int, int, str, str]:
        st = str(row.get("status", ""))
        ready = 1 if row.get("ready_for_reinsert") else 0
        gain = int(row.get("gain") or 0)
        ok = 1 if st == "OK" else 0
        return (-ready, -ok, -gain, str(row.get("console") or ""), str(row.get("crc32") or ""))

    rows.sort(key=_sort_key)
    return rows


def write_reports(
    out_json: Path,
    out_txt: Path,
    results: List[Dict[str, Any]],
    skipped: List[Dict[str, Any]],
    bootstrapped: List[Dict[str, Any]],
    ranking: List[Dict[str, Any]],
) -> None:
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "processed_total": len(results),
        "skipped_total": len(skipped),
        "bootstrapped_total": len(bootstrapped),
        "results": results,
        "skipped": skipped,
        "bootstrapped": bootstrapped,
        "ranking": ranking,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "CODEC MASTERY BATCH",
        f"generated_at={payload['generated_at']}",
        f"processed_total={len(results)}",
        f"skipped_total={len(skipped)}",
        f"bootstrapped_total={len(bootstrapped)}",
        "",
        "RANKING:",
        "console | crc32 | status | gain | patch_ok | patched_changed | patched_blocked | ready_for_reinsert",
    ]
    for row in ranking:
        lines.append(
            " | ".join(
                [
                    str(row.get("console") or "-"),
                    str(row.get("crc32") or "-"),
                    str(row.get("status") or "-"),
                    str(row.get("gain")),
                    str(row.get("patch_ok")),
                    str(row.get("patched_changed")),
                    str(row.get("patched_blocked")),
                    str(row.get("ready_for_reinsert")),
                ]
            )
        )
    out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Batch de codec mastery + ranking por ROM.")
    ap.add_argument("--roms-root", default=None, help="Raiz ROMs (padrao: ../ROMs)")
    ap.add_argument("--model", default="llama3.2:latest")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--out-json", default=None, help="Saida JSON consolidada")
    ap.add_argument("--out-txt", default=None, help="Saida TXT consolidada")
    ap.add_argument(
        "--bootstrap-crc-from-roms",
        action="store_true",
        help="Cria estrutura CRC automaticamente para consoles sem pasta CRC",
    )
    ap.add_argument(
        "--auto-extract-missing",
        action="store_true",
        help="Quando faltar {CRC}_pure_text.jsonl, tenta gerar automaticamente via universal_translator",
    )
    args = ap.parse_args()

    roms_root = Path(args.roms_root).expanduser().resolve() if args.roms_root else (Path(__file__).resolve().parents[1] / "ROMs")
    if not roms_root.exists():
        raise SystemExit(f"[ERRO] ROMs root nao encontrado: {roms_root}")

    out_json = Path(args.out_json).expanduser().resolve() if args.out_json else roms_root / "codec_mastery_batch_report.json"
    out_txt = Path(args.out_txt).expanduser().resolve() if args.out_txt else roms_root / "codec_mastery_batch_report.txt"

    items, skipped, bootstrapped = discover_work_items(
        roms_root=roms_root,
        bootstrap_crc_from_roms=bool(args.bootstrap_crc_from_roms),
        auto_extract_missing=bool(args.auto_extract_missing),
    )
    results: List[Dict[str, Any]] = []
    for i, item in enumerate(items, start=1):
        print(f"[{i}/{len(items)}] {item.console} {item.crc32} -> running mastery pipeline")
        res = run_one(
            item=item,
            model=args.model,
            timeout=int(args.timeout),
            batch_size=int(args.batch_size),
        )
        results.append(res)
        tag = "OK" if res.get("ok") else "FAIL"
        gain = (res.get("summary", {}) or {}).get("probe_candidates_gain")
        print(f"    [{tag}] gain={gain} summary={res.get('summary_json')}")

    ranking = build_ranking(results=results, skipped=skipped)
    write_reports(
        out_json=out_json,
        out_txt=out_txt,
        results=results,
        skipped=skipped,
        bootstrapped=bootstrapped,
        ranking=ranking,
    )
    print(f"[OK] batch_json={out_json}")
    print(f"[OK] batch_txt={out_txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
