#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fechamento de release em lote:
1) Gera translation_jsonl quando faltar
2) Reinsercao estrita in-place por JSONL
3) QA final padronizado por CRC/console
4) Checklist de smoke test no emulador
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import subprocess
import sys
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = PROJECT_ROOT / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

try:
    from final_qa import evaluate_reinsertion_qa, write_qa_artifacts
except Exception as exc:  # pragma: no cover
    raise RuntimeError(f"Falha ao importar final_qa.py: {exc}") from exc


ROM_EXTS = {".nes", ".sms", ".gg", ".md", ".gen", ".smd", ".smc", ".sfc", ".gba", ".bin", ".z64", ".n64", ".v64", ".iso", ".img", ".cue", ".chd", ".pbp", ".ccd", ".mds", ".psx"}


@dataclass
class CRCItem:
    console: str
    crc32: str
    crc_dir: Path
    pure_jsonl: Path
    trad_dir: Path
    rein_dir: Path
    rom_path: Optional[Path]
    rom_size: Optional[int]


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
    return path.is_dir() and len(path.name) == 8 and all(c in "0123456789ABCDEFabcdef" for c in path.name)


def list_crc_items(roms_root: Path) -> List[CRCItem]:
    items: List[CRCItem] = []
    for console_dir in sorted([p for p in roms_root.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
        for crc_dir in sorted([p for p in console_dir.iterdir() if is_crc_dir(p)], key=lambda p: p.name.lower()):
            crc = crc_dir.name.upper()
            pure_jsonl = crc_dir / "1_extracao" / f"{crc}_pure_text.jsonl"
            if not pure_jsonl.exists():
                continue
            rom_path = find_rom_for_crc(console_dir, crc_dir, crc)
            rom_size = int(rom_path.stat().st_size) if rom_path and rom_path.exists() else None
            items.append(
                CRCItem(
                    console=console_dir.name,
                    crc32=crc,
                    crc_dir=crc_dir,
                    pure_jsonl=pure_jsonl,
                    trad_dir=crc_dir / "2_traducao",
                    rein_dir=crc_dir / "3_reinsercao",
                    rom_path=rom_path,
                    rom_size=rom_size,
                )
            )
    return items


def read_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def find_rom_for_crc(console_dir: Path, crc_dir: Path, crc: str) -> Optional[Path]:
    manifest = crc_dir / "crc_bootstrap_manifest.json"
    if manifest.exists():
        obj = read_json(manifest)
        rom_file = obj.get("rom_file")
        if isinstance(rom_file, str) and rom_file:
            p = Path(rom_file)
            if p.exists() and p.is_file():
                try:
                    if crc32_of_file(p) == crc.upper():
                        return p
                except Exception:
                    pass
    for p in sorted(console_dir.iterdir(), key=lambda x: x.name.lower()):
        if not (p.is_file() and p.suffix.lower() in ROM_EXTS):
            continue
        try:
            if crc32_of_file(p) == crc.upper():
                return p
        except Exception:
            continue
    return None


def find_translation_jsonl(trad_dir: Path, crc: str) -> Optional[Path]:
    if not trad_dir.exists():
        return None
    preferred = [
        trad_dir / f"{crc}_translated_fixed_ptbr_patched_auto_delta.jsonl",
        trad_dir / f"{crc}_translated_fixed_ptbr_manual_delta.jsonl",
        trad_dir / f"{crc}_translated_fixed_ptbr_patched.jsonl",
        trad_dir / f"{crc}_translated_fixed_ptbr.jsonl",
    ]
    for p in preferred:
        if p.exists():
            return p
    cands = sorted(trad_dir.glob("*translated*.jsonl"))
    return cands[0] if cands else None


def run_cmd(cmd: List[str], timeout_s: int) -> Dict[str, Any]:
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=max(30, int(timeout_s)),
    )
    return {
        "returncode": int(proc.returncode),
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-25:]),
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-25:]),
    }


def run_codec_mastery(
    item: CRCItem,
    model: str,
    timeout_s: int,
    batch_size: int,
    translation_jsonl: Optional[Path] = None,
) -> Dict[str, Any]:
    """Roda engenharia de codec por CRC e retorna summary + patch opcional."""
    item.trad_dir.mkdir(parents=True, exist_ok=True)
    out_dir = item.crc_dir / "1_extracao"
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str((PROJECT_ROOT / "tools" / "run_codec_mastery_pipeline.py").resolve()),
        "--pure-jsonl",
        str(item.pure_jsonl),
        "--out-dir",
        str(out_dir),
        "--install-profile",
        "--model",
        str(model),
        "--timeout",
        str(int(timeout_s)),
        "--batch-size",
        str(int(batch_size)),
    ]

    patch_out = None
    if translation_jsonl is not None and Path(translation_jsonl).exists():
        patch_out = item.trad_dir / f"{item.crc32}_translated_fixed_ptbr_codec_patched.jsonl"
        cmd.extend(
            [
                "--translation-jsonl",
                str(Path(translation_jsonl)),
                "--patch-out-jsonl",
                str(patch_out),
            ]
        )

    result = run_cmd(cmd, timeout_s=max(120, int(timeout_s) * 20))
    summary_json = out_dir / f"{item.crc32}_codec_mastery_summary.json"
    summary = read_json(summary_json) if summary_json.exists() else {}
    patch_result = summary.get("patch_result", {}) if isinstance(summary, dict) else {}
    patched_jsonl = None
    if isinstance(patch_result, dict):
        out_jsonl = patch_result.get("out_jsonl")
        if isinstance(out_jsonl, str) and out_jsonl:
            out_path = Path(out_jsonl)
            if out_path.exists():
                patched_jsonl = out_path
    if patched_jsonl is None and patch_out and patch_out.exists():
        patched_jsonl = patch_out

    result.update(
        {
            "ok": bool(result["returncode"] == 0 and isinstance(summary, dict) and bool(summary)),
            "summary_json": str(summary_json) if summary_json.exists() else None,
            "summary": summary,
            "patched_jsonl": str(patched_jsonl) if patched_jsonl else None,
            "profile_loaded": bool(summary.get("probe_profile_loaded")) if isinstance(summary, dict) else False,
            "profile_applied": bool(summary.get("probe_profile_applied")) if isinstance(summary, dict) else False,
            "probe_gain": int(summary.get("probe_candidates_gain", 0) or 0)
            if isinstance(summary, dict)
            else 0,
        }
    )
    return result


def run_translation(
    item: CRCItem,
    model: str,
    timeout_s: int,
    batch_size: int,
    max_unique: int,
) -> Dict[str, Any]:
    item.trad_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str((PROJECT_ROOT / "tools" / "translate_puretext_ollama_safe.py").resolve()),
        "--pure-jsonl",
        str(item.pure_jsonl),
        "--out-dir",
        str(item.trad_dir),
        "--model",
        str(model),
        "--timeout",
        str(int(timeout_s)),
        "--batch-size",
        str(int(batch_size)),
        "--max-unique-candidates",
        str(int(max_unique)),
        "--rom-crc32",
        item.crc32,
    ]
    if item.rom_size is not None:
        cmd.extend(["--rom-size", str(int(item.rom_size))])

    result = run_cmd(cmd, timeout_s=timeout_s * 20)
    translated_path = item.trad_dir / f"{item.crc32}_translated_fixed_ptbr.jsonl"
    result["translated_path"] = str(translated_path) if translated_path.exists() else None
    result["ok"] = bool(result["returncode"] == 0 and translated_path.exists())
    return result


def parse_patch_report(path: Path) -> Dict[str, Any]:
    out = {"patched_changed": 0, "patched_blocked": 0, "skipped_non_ascii_source": 0}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k in out:
            try:
                out[k] = int(v)
            except Exception:
                pass
    return out


def run_decoded_candidates_patch(
    item: CRCItem,
    in_jsonl: Path,
    model: str,
    timeout_s: int,
    batch_size: int,
) -> Dict[str, Any]:
    candidates = item.crc_dir / "1_extracao" / f"{item.crc32}_decoded_candidates.jsonl"
    if not candidates.exists():
        fallback = list((item.crc_dir / "1_extracao").glob("*decoded_candidates.jsonl"))
        if fallback:
            candidates = fallback[0]
    if not candidates.exists():
        return {"ok": False, "skipped": True, "reason": "NO_DECODED_CANDIDATES"}

    out_jsonl = item.trad_dir / f"{item.crc32}_translated_fixed_ptbr_patched.jsonl"
    cmd = [
        sys.executable,
        str((PROJECT_ROOT / "tools" / "translate_decoded_candidates_patch.py").resolve()),
        "--in-jsonl",
        str(in_jsonl),
        "--candidates-jsonl",
        str(candidates),
        "--out-jsonl",
        str(out_jsonl),
        "--model",
        str(model),
        "--timeout",
        str(int(timeout_s)),
        "--batch-size",
        str(int(batch_size)),
    ]
    result = run_cmd(cmd, timeout_s=max(90, timeout_s * 10))
    report_path = out_jsonl.with_name(out_jsonl.stem + "_patch_report.txt")
    patch_stats = parse_patch_report(report_path)
    result.update(
        {
            "ok": bool(result["returncode"] == 0 and out_jsonl.exists()),
            "skipped": False,
            "candidates_jsonl": str(candidates),
            "patched_jsonl": str(out_jsonl) if out_jsonl.exists() else None,
            "patch_report_path": str(report_path) if report_path.exists() else None,
            **patch_stats,
        }
    )
    return result


def run_auto_delta_patch(
    item: CRCItem,
    in_jsonl: Path,
    model: str,
    timeout_s: int,
    batch_size: int,
) -> Dict[str, Any]:
    out_jsonl = item.trad_dir / f"{item.crc32}_translated_fixed_ptbr_patched_auto_delta.jsonl"
    cmd = [
        sys.executable,
        str((PROJECT_ROOT / "tools" / "auto_delta_retranslate_jsonl.py").resolve()),
        "--in-jsonl",
        str(in_jsonl),
        "--out-jsonl",
        str(out_jsonl),
        "--model",
        str(model),
        "--timeout",
        str(int(timeout_s)),
        "--batch-size",
        str(int(batch_size)),
        "--max-items",
        "3000",
    ]
    result = run_cmd(cmd, timeout_s=max(90, timeout_s * 15))
    report_path = out_jsonl.with_name(out_jsonl.stem + "_auto_delta_report.txt")
    proof_path = out_jsonl.with_name(out_jsonl.stem + "_auto_delta_proof.json")
    metrics = read_json(proof_path) if proof_path.exists() else {}
    result.update(
        {
            "ok": bool(result["returncode"] == 0 and out_jsonl.exists()),
            "out_jsonl": str(out_jsonl) if out_jsonl.exists() else None,
            "report_path": str(report_path) if report_path.exists() else None,
            "proof_path": str(proof_path) if proof_path.exists() else None,
            "metrics": metrics,
        }
    )
    return result


def run_strict_reinsert(
    item: CRCItem,
    translated_jsonl: Path,
    allow_truncate: bool,
) -> Dict[str, Any]:
    item.rein_dir.mkdir(parents=True, exist_ok=True)
    if item.rom_path is None:
        return {
            "ok": False,
            "returncode": -1,
            "stdout_tail": "",
            "stderr_tail": "ROM original nao localizada para o CRC.",
            "proof_path": None,
            "report_path": None,
            "output_rom": None,
        }

    cmd = [
        sys.executable,
        str((PROJECT_ROOT / "tools" / "reinsert_translated_jsonl_strict.py").resolve()),
        "--rom",
        str(item.rom_path),
        "--translated-jsonl",
        str(translated_jsonl),
        "--out-dir",
        str(item.rein_dir),
    ]
    if allow_truncate:
        cmd.append("--allow-last-resort-truncate")

    result = run_cmd(cmd, timeout_s=1800)
    proof_path = item.rein_dir / f"{item.crc32}_strict_reinsert_proof.json"
    report_path = item.rein_dir / f"{item.crc32}_strict_reinsert_report.txt"
    output_rom = item.rein_dir / f"{item.rom_path.stem}_STRICT_TRANSLATED{item.rom_path.suffix}"
    result["proof_path"] = str(proof_path) if proof_path.exists() else None
    result["report_path"] = str(report_path) if report_path.exists() else None
    result["output_rom"] = str(output_rom) if output_rom.exists() else None
    result["ok"] = bool(result["returncode"] == 0 and proof_path.exists() and output_rom.exists())
    return result


def read_emulator_results(path: Optional[Path]) -> Dict[str, bool]:
    if path is None or not path.exists():
        return {}
    data = read_json(path)
    out: Dict[str, bool] = {}
    for k, v in data.items():
        if not isinstance(k, str):
            continue
        if isinstance(v, bool):
            out[k.upper()] = v
    return out


def build_limitations(item: CRCItem, proof: Dict[str, Any], codec_summary: Dict[str, Any]) -> List[str]:
    limitations: List[str] = []
    cov = proof.get("coverage_check", {}) if isinstance(proof.get("coverage_check"), dict) else {}
    if int(cov.get("count_offsets_below_0x10000", 0) or 0) == 0:
        limitations.append("intro possivelmente nao extraido/mapeado (offsets baixos ausentes).")

    metrics = proof.get("metrics", {}) if isinstance(proof.get("metrics"), dict) else {}
    blocked_total = (
        int(metrics.get("blocked_too_long", 0) or 0)
        + int(metrics.get("blocked_non_ascii", 0) or 0)
        + int(metrics.get("blocked_oob", 0) or 0)
        + int(metrics.get("blocked_no_budget", 0) or 0)
        + int(metrics.get("placeholder_fail", 0) or 0)
        + int(metrics.get("terminator_missing", 0) or 0)
    )
    translatable = int(metrics.get("translatable_candidates_total", 0) or 0)
    untranslated = int(metrics.get("not_translated_count", 0) or 0)

    decoder_family = str(codec_summary.get("probe_decoder_family", "")).lower()
    profile_loaded = bool(codec_summary.get("probe_profile_loaded"))
    before_cands = int(codec_summary.get("probe_before_candidates_total", 0) or 0)
    has_translation_risk = bool(translatable > 0 and (untranslated > 0 or blocked_total > 0))
    has_profile_risk = bool((not profile_loaded) and before_cands > 0)
    rec = str(codec_summary.get("probe_recommendation", "")).strip()

    if rec and (has_translation_risk or has_profile_risk):
        limitations.append(rec)
    elif rec and translatable == 0 and blocked_total == 0:
        limitations.append("Cobertura textual baixa no extractor; faltam candidatos para validar traducao completa.")

    if decoder_family.startswith("generic") and has_profile_risk and has_translation_risk:
        limitations.append("Decoder generico sem profile especifico; pode haver script/codec proprietario nao mapeado.")
    elif decoder_family.startswith("generic") and before_cands == 0 and translatable == 0:
        limitations.append("Extractor sem candidatos antes do decode; revisar mapeamento estatico de blocos.")
    return limitations


def extract_proof_metrics(proof: Dict[str, Any]) -> Dict[str, Any]:
    metrics = proof.get("metrics", {}) if isinstance(proof.get("metrics"), dict) else {}
    ordering = proof.get("ordering_check", {}) if isinstance(proof.get("ordering_check"), dict) else {}
    coverage = proof.get("coverage_check", {}) if isinstance(proof.get("coverage_check"), dict) else {}
    input_match = proof.get("input_match_check", {}) if isinstance(proof.get("input_match_check"), dict) else {}

    blocked_total = (
        int(metrics.get("blocked_too_long", 0) or 0)
        + int(metrics.get("blocked_non_ascii", 0) or 0)
        + int(metrics.get("blocked_oob", 0) or 0)
        + int(metrics.get("blocked_no_budget", 0) or 0)
        + int(metrics.get("placeholder_fail", 0) or 0)
        + int(metrics.get("terminator_missing", 0) or 0)
    )
    critical_issues = (
        int(metrics.get("unchanged_equal_src", 0) or 0)
        + int(metrics.get("suspicious_non_pt", 0) or 0)
        + int(metrics.get("rom_vs_translated_mismatch", 0) or 0)
        + int(metrics.get("placeholder_fail", 0) or 0)
        + int(metrics.get("terminator_missing", 0) or 0)
        + int(metrics.get("not_translated_count", 0) or 0)
    )

    return {
        "items_total": int(metrics.get("items_total", 0) or 0),
        "items_considered": int(metrics.get("items_considered", 0) or 0),
        "translatable_candidates_total": int(metrics.get("translatable_candidates_total", 0) or 0),
        "non_translatable_skipped": int(metrics.get("non_translatable_skipped", 0) or 0),
        "applied": int(metrics.get("applied", 0) or 0),
        "unchanged_equal_src": int(metrics.get("unchanged_equal_src", 0) or 0),
        "not_translated_count": int(metrics.get("not_translated_count", 0) or 0),
        "suspicious_non_pt": int(metrics.get("suspicious_non_pt", 0) or 0),
        "rom_vs_translated_mismatch": int(metrics.get("rom_vs_translated_mismatch", 0) or 0),
        "placeholder_fail": int(metrics.get("placeholder_fail", 0) or 0),
        "terminator_missing": int(metrics.get("terminator_missing", 0) or 0),
        "truncated_count": int(metrics.get("truncated", 0) or 0),
        "blocked_too_long": int(metrics.get("blocked_too_long", 0) or 0),
        "blocked_non_ascii": int(metrics.get("blocked_non_ascii", 0) or 0),
        "blocked_oob": int(metrics.get("blocked_oob", 0) or 0),
        "blocked_no_budget": int(metrics.get("blocked_no_budget", 0) or 0),
        "blocked_items": int(blocked_total),
        "critical_issues_total": int(critical_issues),
        "ordering_sorted": bool(ordering.get("is_sorted_by_offset")),
        "input_match_ok": bool(input_match.get("rom_crc32_match") and input_match.get("rom_size_match")),
        "count_offsets_below_0x10000": int(coverage.get("count_offsets_below_0x10000", 0) or 0),
        "coverage_items_total": int(coverage.get("items_total", 0) or 0),
        "min_offset": int(coverage.get("min_offset", 0) or 0),
        "max_offset": int(coverage.get("max_offset", 0) or 0),
        "translation_input": str(proof.get("translation_input") or ""),
    }


def make_qa_for_item(
    item: CRCItem,
    translated_jsonl: Path,
    reinsert_result: Dict[str, Any],
    emulator_results: Dict[str, bool],
    require_manual_emulator: bool,
    codec_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    proof_path = Path(str(reinsert_result.get("proof_path", ""))) if reinsert_result.get("proof_path") else None
    proof = read_json(proof_path) if proof_path and proof_path.exists() else {}
    proof_metrics = extract_proof_metrics(proof)
    metrics = proof.get("metrics", {}) if isinstance(proof.get("metrics"), dict) else {}
    checks = {
        "input_match": bool(
            (proof.get("input_match_check", {}) or {}).get("rom_crc32_match")
            and (proof.get("input_match_check", {}) or {}).get("rom_size_match")
        ),
        "ordering": bool((proof.get("ordering_check", {}) or {}).get("is_sorted_by_offset")),
        "emulator_smoke": emulator_results.get(item.crc32.upper()),
    }

    evidence = {
        "unchanged_equal_src_count": int(metrics.get("unchanged_equal_src", 0) or 0),
        "suspicious_non_pt_count": int(metrics.get("suspicious_non_pt", 0) or 0),
        "rom_vs_translated_mismatch_count": int(metrics.get("rom_vs_translated_mismatch", 0) or 0),
        "placeholder_fail_count": int(metrics.get("placeholder_fail", 0) or 0),
        "terminator_missing_count": int(metrics.get("terminator_missing", 0) or 0),
        "not_translated_count": int(metrics.get("not_translated_count", 0) or 0),
        "truncated_count": int(metrics.get("truncated", 0) or 0),
    }

    blocked_total = (
        int(metrics.get("blocked_too_long", 0) or 0)
        + int(metrics.get("blocked_non_ascii", 0) or 0)
        + int(metrics.get("blocked_oob", 0) or 0)
        + int(metrics.get("blocked_no_budget", 0) or 0)
        + int(metrics.get("placeholder_fail", 0) or 0)
        + int(metrics.get("terminator_missing", 0) or 0)
    )
    qa_stats = {
        "truncated": int(metrics.get("truncated", 0) or 0),
        "blocked": blocked_total,
        "blocked_items": blocked_total,
    }

    if not isinstance(codec_summary, dict) or not codec_summary:
        codec_summary = read_json(item.crc_dir / "1_extracao" / f"{item.crc32}_codec_mastery_summary.json")
    limitations = build_limitations(item, proof, codec_summary)
    recommendation = str(codec_summary.get("probe_recommendation", "") or "").strip()
    rec_low = recommendation.lower()
    profile_loaded = bool(codec_summary.get("probe_profile_loaded"))
    profile_applied = bool(codec_summary.get("probe_profile_applied"))
    gain = int(codec_summary.get("probe_candidates_gain", 0) or 0)
    proprietary_signal = bool(
        recommendation
        and any(k in rec_low for k in ("codec", "propriet", "compress", "comprim", "script"))
    )
    if proprietary_signal and not profile_applied:
        compression_mode = "proprietary"
    elif profile_applied:
        compression_mode = "resolved"
    elif profile_loaded and gain >= 0:
        compression_mode = "generic"
    else:
        compression_mode = "generic"
    if compression_mode == "resolved":
        compression_notes = "profile aplicado por CRC (risco mitigado)"
    elif recommendation:
        compression_notes = recommendation
    else:
        compression_notes = "sem evidência forte de codec proprietário"
    compression_policy = {
        "mode": compression_mode,
        "requires_codec": "crc_profile" if proprietary_signal and not profile_applied else "",
        "notes": compression_notes,
    }

    qa = evaluate_reinsertion_qa(
        console=item.console,
        rom_crc32=item.crc32,
        rom_size=item.rom_size,
        stats=qa_stats,
        evidence=evidence,
        checks=checks,
        limitations=limitations,
        compression_policy=compression_policy,
        translation_input={"path": str(translated_jsonl)},
        require_manual_emulator=bool(require_manual_emulator),
    )
    qa_json_path, qa_txt_path = write_qa_artifacts(item.rein_dir, item.crc32, qa)
    qa_gate_status: Dict[str, str] = {}
    for gate in qa.get("gates", []) or []:
        name = str(gate.get("name") or "").strip()
        status = str(gate.get("status") or "").strip()
        if name:
            qa_gate_status[name] = status
    return {
        "qa": qa,
        "qa_json_path": str(qa_json_path),
        "qa_txt_path": str(qa_txt_path),
        "proof_metrics": proof_metrics,
        "limitations": limitations,
        "qa_gate_status": qa_gate_status,
        "qa_required_failed": list(qa.get("required_failed", []) or []),
        "qa_required_unknown": list(qa.get("required_unknown", []) or []),
        "proprietary_codec_risk": dict(qa.get("proprietary_codec_risk", {}) or {}),
    }


def write_checklist(path: Path, rows: List[Dict[str, Any]]) -> None:
    lines: List[str] = [
        "EMULATOR SMOKE CHECKLIST",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
        "",
        "Marcar PASS/FAIL por CRC em ROMs/emulator_smoke_results.json (ex.: {\"DE9F8517\": true}).",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"[ ] CRC={row.get('crc32')} console={row.get('console')}",
                f"    rom_output={row.get('output_rom')}",
                "    validar: boot inicial / menu principal / dialogo inicial / tela de escolha",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_emulator_template(path: Path, rows: List[Dict[str, Any]]) -> None:
    data: Dict[str, Any] = {
        "_how_to_use": "Troque PENDING por true (pass) ou false (fail) apos testar no emulador.",
    }
    for row in rows:
        crc = str(row.get("crc32") or "").upper()
        if not crc:
            continue
        data[crc] = "PENDING"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_summary(out_json: Path, out_txt: Path, payload: Dict[str, Any]) -> None:
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "RELEASE CLOSURE BATCH",
        f"generated_at={payload['generated_at']}",
        f"items_total={payload['items_total']}",
        f"translation_generated={payload['translation_generated']}",
        f"reinsert_ok={payload['reinsert_ok']}",
        f"qa_overall_pass={payload['qa_overall_pass']}",
        f"emulator_pass={payload['emulator_pass']}",
        f"pipeline_pass_percent={payload.get('pipeline_pass_percent')}",
        f"qa_pass_percent={payload.get('qa_pass_percent')}",
        f"reinsert_pass_percent={payload.get('reinsert_pass_percent')}",
        f"codec_runs={payload.get('codec_runs')}",
        f"codec_ok={payload.get('codec_ok')}",
        f"codec_profile_applied={payload.get('codec_profile_applied')}",
        f"codec_patch_ok={payload.get('codec_patch_ok')}",
        "",
        f"qa_fail_reason_counts={json.dumps(payload.get('qa_fail_reason_counts', {}), ensure_ascii=False)}",
        f"qa_unknown_gate_counts={json.dumps(payload.get('qa_unknown_gate_counts', {}), ensure_ascii=False)}",
        f"totals={json.dumps(payload.get('totals', {}), ensure_ascii=False)}",
        "",
        "ROWS:",
        "console | crc32 | translation_ok | reinsert_ok | qa_overall_pass | emulator_smoke | output_rom",
    ]
    for r in payload.get("rows", []):
        lines.append(
            " | ".join(
                [
                    str(r.get("console")),
                    str(r.get("crc32")),
                    str(r.get("translation_ok")),
                    str(r.get("reinsert_ok")),
                    str(r.get("qa_overall_pass")),
                    str(r.get("emulator_smoke")),
                    str(r.get("output_rom")),
                ]
            )
        )
    out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")


def aggregate_rows(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    fail_counts: Counter[str] = Counter()
    unknown_counts: Counter[str] = Counter()
    totals: Counter[str] = Counter()
    total_keys = [
        "items_total",
        "items_considered",
        "translatable_candidates_total",
        "non_translatable_skipped",
        "applied",
        "blocked_items",
        "truncated_count",
        "not_translated_count",
        "unchanged_equal_src",
        "suspicious_non_pt",
        "rom_vs_translated_mismatch",
        "placeholder_fail",
        "terminator_missing",
        "critical_issues_total",
    ]

    for row in rows:
        gate_status = row.get("qa_gate_status", {}) or {}
        if isinstance(gate_status, dict):
            for name, status in gate_status.items():
                gate = str(name or "").strip()
                st = str(status or "").strip().lower()
                if not gate:
                    continue
                if st == "fail":
                    fail_counts[gate] += 1
                elif st == "unknown":
                    unknown_counts[gate] += 1

        proof_metrics = row.get("proof_metrics", {}) or {}
        if not isinstance(proof_metrics, dict):
            continue
        for key in total_keys:
            value = proof_metrics.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                totals[key] += int(value)

    return {
        "qa_fail_reason_counts": dict(sorted(fail_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "qa_unknown_gate_counts": dict(sorted(unknown_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "totals": dict(sorted(totals.items(), key=lambda kv: kv[0])),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Fechamento de release: traducao + reinsercao + QA.")
    ap.add_argument("--roms-root", default=None, help="Raiz ROMs (default: ../ROMs)")
    ap.add_argument("--console", default=None, help="Filtra por console (nome da pasta, ex.: \"Master System\").")
    ap.add_argument("--crc", default=None, help="Filtra por CRC32 (8 hex).")
    ap.add_argument("--max-items", type=int, default=0, help="Processa no máximo N itens após filtros (0=todos).")
    ap.add_argument("--model", default="llama3.2:latest")
    ap.add_argument("--timeout", type=int, default=90, help="Timeout por requisicao de traducao")
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--max-unique-candidates", type=int, default=1200)
    ap.add_argument("--codec-model", default=None, help="Modelo para engenharia de codec (default: --model).")
    ap.add_argument("--codec-timeout", type=int, default=180, help="Timeout por requisicao no pipeline de codec.")
    ap.add_argument("--codec-batch-size", type=int, default=10, help="Batch no pipeline de codec.")
    ap.add_argument("--skip-codec-mastery", action="store_true", help="Nao executa engenharia de codec por CRC.")
    ap.add_argument("--allow-last-resort-truncate", action="store_true")
    ap.add_argument("--force-translate", action="store_true", help="Regera translated_jsonl mesmo se ja existir")
    ap.add_argument("--skip-auto-delta", action="store_true", help="Nao roda auto-delta patch no batch.")
    ap.add_argument(
        "--require-manual-emulator",
        action="store_true",
        help="Mantem gate de emulator_smoke_test como obrigatorio.",
    )
    ap.add_argument(
        "--emulator-results-json",
        default=None,
        help="JSON opcional com PASS/FAIL manual por CRC (ex.: ROMs/emulator_smoke_results.json)",
    )
    args = ap.parse_args()

    roms_root = Path(args.roms_root).expanduser().resolve() if args.roms_root else (PROJECT_ROOT / "ROMs")
    if not roms_root.exists():
        raise SystemExit(f"[ERRO] ROMs root nao encontrado: {roms_root}")

    items = list_crc_items(roms_root)
    if args.console:
        needle_console = str(args.console).strip().lower()
        items = [it for it in items if str(it.console).strip().lower() == needle_console]
    if args.crc:
        needle_crc = str(args.crc).strip().upper()
        items = [it for it in items if str(it.crc32).strip().upper() == needle_crc]
    if int(args.max_items or 0) > 0:
        items = items[: int(args.max_items)]
    emulator_results = read_emulator_results(
        Path(args.emulator_results_json).expanduser().resolve() if args.emulator_results_json else None
    )

    rows: List[Dict[str, Any]] = []
    translated_generated = 0
    reinsert_ok = 0
    qa_ok = 0
    emulator_pass = 0
    codec_runs = 0
    codec_ok = 0
    codec_profile_applied = 0
    codec_patch_ok = 0
    codec_model = str(args.codec_model or args.model)

    for idx, item in enumerate(items, start=1):
        print(f"[{idx}/{len(items)}] {item.console} {item.crc32}")
        row: Dict[str, Any] = {
            "console": item.console,
            "crc32": item.crc32,
            "crc_dir": str(item.crc_dir),
            "rom_path": str(item.rom_path) if item.rom_path else None,
            "pure_jsonl": str(item.pure_jsonl),
            "proof_metrics": {},
            "qa_gate_status": {},
            "qa_required_failed": [],
            "qa_required_unknown": [],
            "limitations": [],
            "qa_summary": {},
            "codec_mastery_before": {},
            "codec_mastery_after": {},
        }

        codec_before: Dict[str, Any] = {}
        codec_after: Dict[str, Any] = {}

        if not bool(args.skip_codec_mastery):
            codec_before = run_codec_mastery(
                item=item,
                model=codec_model,
                timeout_s=max(60, int(args.codec_timeout)),
                batch_size=max(1, int(args.codec_batch_size)),
                translation_jsonl=None,
            )
            row["codec_mastery_before"] = codec_before
            codec_runs += 1
            if codec_before.get("ok"):
                codec_ok += 1
            if codec_before.get("profile_applied"):
                codec_profile_applied += 1

        translated_path = find_translation_jsonl(item.trad_dir, item.crc32)
        translation_info: Dict[str, Any] = {"skipped_existing": bool(translated_path and not args.force_translate)}
        if translated_path is None or args.force_translate:
            if item.rom_path is None:
                translation_info = {
                    "ok": False,
                    "error": "ROM original nao encontrada para inferir rom_size.",
                }
            else:
                translation_info = run_translation(
                    item=item,
                    model=args.model,
                    timeout_s=int(args.timeout),
                    batch_size=int(args.batch_size),
                    max_unique=int(args.max_unique_candidates),
                )
                if translation_info.get("ok"):
                    translated_generated += 1
            translated_path = find_translation_jsonl(item.trad_dir, item.crc32)

        row["translation_ok"] = bool(translated_path and Path(translated_path).exists())
        row["translation_jsonl"] = str(translated_path) if translated_path else None
        row["translation_info"] = translation_info

        if not row["translation_ok"]:
            row["reinsert_ok"] = False
            row["qa_overall_pass"] = False
            rows.append(row)
            continue

        if not bool(args.skip_codec_mastery):
            codec_after = run_codec_mastery(
                item=item,
                model=codec_model,
                timeout_s=max(60, int(args.codec_timeout)),
                batch_size=max(1, int(args.codec_batch_size)),
                translation_jsonl=Path(translated_path),
            )
            row["codec_mastery_after"] = codec_after
            codec_runs += 1
            if codec_after.get("ok"):
                codec_ok += 1
            if codec_after.get("profile_applied"):
                codec_profile_applied += 1
            patched_by_codec = codec_after.get("patched_jsonl")
            if isinstance(patched_by_codec, str) and patched_by_codec and Path(patched_by_codec).exists():
                translated_path = patched_by_codec
                row["translation_jsonl"] = translated_path
                codec_patch_ok += 1

        if codec_after.get("patched_jsonl"):
            row["decoded_patch_info"] = {
                "ok": True,
                "skipped": True,
                "reason": "PATCH_BY_CODEC_MASTERY",
                "patched_jsonl": codec_after.get("patched_jsonl"),
            }
        else:
            patch_info = run_decoded_candidates_patch(
                item=item,
                in_jsonl=Path(translated_path),
                model=args.model,
                timeout_s=max(60, int(args.timeout)),
                batch_size=max(1, int(args.batch_size)),
            )
            row["decoded_patch_info"] = patch_info
            if patch_info.get("ok") and patch_info.get("patched_jsonl"):
                patched_changed = int(patch_info.get("patched_changed", 0) or 0)
                if patched_changed > 0:
                    translated_path = str(patch_info.get("patched_jsonl"))
                    row["translation_jsonl"] = translated_path

        if bool(args.skip_auto_delta):
            auto_delta_info = {"ok": False, "skipped": True, "reason": "SKIP_BY_FLAG"}
        else:
            auto_delta_info = run_auto_delta_patch(
                item=item,
                in_jsonl=Path(translated_path),
                model=args.model,
                timeout_s=max(60, int(args.timeout)),
                batch_size=max(1, int(args.batch_size)),
            )
        row["auto_delta_patch_info"] = auto_delta_info
        if auto_delta_info.get("ok") and auto_delta_info.get("out_jsonl"):
            metrics = auto_delta_info.get("metrics", {}) if isinstance(auto_delta_info.get("metrics"), dict) else {}
            changed = int(metrics.get("applied_changed", 0) or 0)
            if changed > 0:
                translated_path = str(auto_delta_info.get("out_jsonl"))
                row["translation_jsonl"] = translated_path

        rein_info = run_strict_reinsert(
            item=item,
            translated_jsonl=Path(translated_path),
            allow_truncate=bool(args.allow_last_resort_truncate),
        )
        row["reinsert_ok"] = bool(rein_info.get("ok"))
        row["reinsert_info"] = rein_info
        row["output_rom"] = rein_info.get("output_rom")
        if row["reinsert_ok"]:
            reinsert_ok += 1

        if row["reinsert_ok"]:
            qa_bundle = make_qa_for_item(
                item=item,
                translated_jsonl=Path(translated_path),
                reinsert_result=rein_info,
                emulator_results=emulator_results,
                require_manual_emulator=bool(args.require_manual_emulator),
                codec_summary=codec_after.get("summary")
                if isinstance(codec_after, dict) and isinstance(codec_after.get("summary"), dict)
                else None,
            )
            qa = qa_bundle["qa"]
            row["qa_overall_pass"] = bool(qa.get("overall_pass"))
            row["qa_quality_score_percent"] = qa.get("quality_score_percent")
            row["qa_json_path"] = qa_bundle["qa_json_path"]
            row["qa_txt_path"] = qa_bundle["qa_txt_path"]
            row["proof_metrics"] = qa_bundle.get("proof_metrics", {})
            row["qa_gate_status"] = qa_bundle.get("qa_gate_status", {})
            row["qa_required_failed"] = qa_bundle.get("qa_required_failed", [])
            row["qa_required_unknown"] = qa_bundle.get("qa_required_unknown", [])
            row["limitations"] = qa_bundle.get("limitations", [])
            row["proprietary_codec_risk"] = qa_bundle.get("proprietary_codec_risk", {})
            pm = row["proof_metrics"] if isinstance(row["proof_metrics"], dict) else {}
            row["qa_summary"] = {
                "critical_issues": int(pm.get("critical_issues_total", 0) or 0),
                "blocked_items": int(pm.get("blocked_items", 0) or 0),
                "truncated_count": int(pm.get("truncated_count", 0) or 0),
                "applied": int(pm.get("applied", 0) or 0),
                "translatable_candidates_total": int(pm.get("translatable_candidates_total", 0) or 0),
                "non_translatable_skipped": int(pm.get("non_translatable_skipped", 0) or 0),
                "not_translated_count": int(pm.get("not_translated_count", 0) or 0),
            }
            # Campo resumido com status manual do emulador.
            emu = None
            for g in qa.get("gates", []) or []:
                if g.get("name") == "emulator_smoke_test":
                    emu = g.get("status")
                    break
            row["emulator_smoke"] = emu
            if row["qa_overall_pass"]:
                qa_ok += 1
            if emu == "pass":
                emulator_pass += 1
        else:
            row["qa_overall_pass"] = False
            row["qa_quality_score_percent"] = 0.0

        rows.append(row)

    checklist_path = roms_root / "emulator_smoke_checklist.txt"
    write_checklist(checklist_path, rows)
    emulator_template_path = roms_root / "emulator_smoke_results_template.json"
    write_emulator_template(emulator_template_path, rows)
    aggregates = aggregate_rows(rows)
    items_total = len(rows)
    qa_pass_percent = round((qa_ok / items_total) * 100.0, 2) if items_total > 0 else 0.0
    reinsert_pass_percent = (
        round((reinsert_ok / items_total) * 100.0, 2) if items_total > 0 else 0.0
    )
    pipeline_pass_percent = qa_pass_percent

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "items_total": items_total,
        "translation_generated": translated_generated,
        "reinsert_ok": reinsert_ok,
        "qa_overall_pass": qa_ok,
        "emulator_pass": emulator_pass,
        "qa_pass_percent": qa_pass_percent,
        "reinsert_pass_percent": reinsert_pass_percent,
        "pipeline_pass_percent": pipeline_pass_percent,
        "codec_runs": int(codec_runs),
        "codec_ok": int(codec_ok),
        "codec_profile_applied": int(codec_profile_applied),
        "codec_patch_ok": int(codec_patch_ok),
        "checklist_path": str(checklist_path),
        "emulator_template_path": str(emulator_template_path),
        "qa_fail_reason_counts": aggregates.get("qa_fail_reason_counts", {}),
        "qa_unknown_gate_counts": aggregates.get("qa_unknown_gate_counts", {}),
        "totals": aggregates.get("totals", {}),
        "rows": rows,
    }
    out_json = roms_root / "release_closure_report.json"
    out_txt = roms_root / "release_closure_report.txt"
    write_summary(out_json, out_txt, payload)

    print(f"[OK] summary_json={out_json}")
    print(f"[OK] summary_txt={out_txt}")
    print(f"[OK] checklist={checklist_path}")
    print(f"[OK] emulator_template={emulator_template_path}")
    print(
        "[STATS] "
        f"pipeline_pass_percent={payload.get('pipeline_pass_percent')} "
        f"qa={qa_ok}/{items_total} "
        f"reinsert={reinsert_ok}/{items_total} "
        f"codec_profile_applied={codec_profile_applied}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
