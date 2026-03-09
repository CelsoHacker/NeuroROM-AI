#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline automatizado de engenharia de codec por ROM.

Etapas:
1) Gerar perfil de codec (build_codec_profile)
2) Executar probe com perfil (probe_script_codec_blocks)
3) Opcional: aplicar patch de traducao por decoded_candidates
4) Gerar summary com evidencias before/after
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from build_codec_profile import default_paths, derive_profile, install_profile, write_report
from codec_family_decoders import infer_console_hint
from probe_script_codec_blocks import build_probe, write_outputs


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def run_patch_if_requested(
    pure_jsonl: Path,
    translation_jsonl: Optional[Path],
    out_jsonl: Optional[Path],
    model: str,
    timeout: int,
    batch_size: int,
) -> Dict[str, Any]:
    if translation_jsonl is None:
        return {"requested": False}
    if not translation_jsonl.exists():
        return {"requested": True, "ran": False, "error": f"translation_jsonl nao existe: {translation_jsonl}"}

    crc = pure_jsonl.stem.split("_")[0].upper() if "_" in pure_jsonl.stem else "UNKNOWN"
    cand_jsonl = pure_jsonl.parent / f"{crc}_decoded_candidates.jsonl"
    if not cand_jsonl.exists():
        return {"requested": True, "ran": False, "error": f"decoded_candidates nao encontrado: {cand_jsonl}"}

    if out_jsonl is None:
        out_jsonl = translation_jsonl.with_name(translation_jsonl.stem + "_patched.jsonl")

    cmd = [
        sys.executable,
        str((Path(__file__).resolve().parent / "translate_decoded_candidates_patch.py").resolve()),
        "--in-jsonl",
        str(translation_jsonl),
        "--candidates-jsonl",
        str(cand_jsonl),
        "--out-jsonl",
        str(out_jsonl),
        "--model",
        str(model),
        "--timeout",
        str(int(timeout)),
        "--batch-size",
        str(int(batch_size)),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return {
        "requested": True,
        "ran": True,
        "returncode": int(proc.returncode),
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-20:]),
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-20:]),
        "out_jsonl": str(out_jsonl),
        "ok": bool(proc.returncode == 0),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Pipeline completo de engenharia de codec por ROM.")
    ap.add_argument("--pure-jsonl", required=True, help="Arquivo {CRC32}_pure_text.jsonl")
    ap.add_argument("--out-dir", default=None, help="Diretorio de saida para probe (padrao: pasta do pure_jsonl)")
    ap.add_argument("--console-hint", default=None, help="Forca console_hint")
    ap.add_argument("--install-profile", action="store_true", help="Instala perfil em profiles/codec")
    ap.add_argument("--min-hits", type=int, default=4)
    ap.add_argument("--max-rules", type=int, default=120)
    ap.add_argument("--translation-jsonl", default=None, help="JSONL traduzido para patch opcional")
    ap.add_argument("--patch-out-jsonl", default=None, help="Saida do patch opcional")
    ap.add_argument("--model", default="llama3.2:latest")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--batch-size", type=int, default=10)
    args = ap.parse_args()

    pure_jsonl = Path(args.pure_jsonl).expanduser().resolve()
    if not pure_jsonl.exists():
        raise SystemExit(f"[ERRO] pure-jsonl nao encontrado: {pure_jsonl}")
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else pure_jsonl.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    console_hint = str(args.console_hint or infer_console_hint(str(pure_jsonl)) or "generic").lower()
    crc = pure_jsonl.stem.split("_")[0].upper() if "_" in pure_jsonl.stem else "UNKNOWN"
    proof_path = out_dir / f"{crc}_codec_probe_proof.json"
    before = read_json(proof_path)

    profile = derive_profile(
        pure_jsonl=pure_jsonl,
        console_hint=console_hint,
        min_hits=max(1, int(args.min_hits)),
        max_rules=max(1, int(args.max_rules)),
    )
    profile_path, profile_report_path = default_paths(
        pure_jsonl=pure_jsonl,
        profile=profile,
        out_profile=None,
        out_report=None,
    )
    profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    installed = None
    if args.install_profile:
        installed = install_profile(profile_path, console_hint=console_hint, rom_crc32=profile.get("rom_crc32"))
    write_report(
        report_path=profile_report_path,
        profile_path=profile_path,
        profile=profile,
        install_path=installed,
    )

    payload = build_probe(pure_jsonl)
    write_outputs(payload, out_dir)
    after = read_json(proof_path)

    patch_result = run_patch_if_requested(
        pure_jsonl=pure_jsonl,
        translation_jsonl=Path(args.translation_jsonl).expanduser().resolve()
        if args.translation_jsonl
        else None,
        out_jsonl=Path(args.patch_out_jsonl).expanduser().resolve() if args.patch_out_jsonl else None,
        model=args.model,
        timeout=int(args.timeout),
        batch_size=int(args.batch_size),
    )

    before_cands = int(before.get("decoded_candidates_total", 0) or 0)
    after_cands = int(after.get("decoded_candidates_total", payload.get("decoded_candidates_total", 0)) or 0)
    gain = int(after_cands - before_cands)
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "pure_jsonl": str(pure_jsonl),
        "console_hint": console_hint,
        "rom_crc32": payload.get("rom_crc32"),
        "rom_size": payload.get("rom_size"),
        "profile_path": str(profile_path),
        "profile_report_path": str(profile_report_path),
        "profile_installed_path": str(installed) if installed else None,
        "probe_before_candidates_total": before_cands,
        "probe_after_candidates_total": after_cands,
        "probe_candidates_gain": gain,
        "probe_decoder_family": payload.get("decoder_family"),
        "probe_profile_loaded": payload.get("profile_loaded"),
        "probe_profile_applied": payload.get("profile_applied"),
        "probe_profile_path": payload.get("profile_path"),
        "probe_recommendation": payload.get("recommendation"),
        "patch_result": patch_result,
    }
    summary_json = out_dir / f"{crc}_codec_mastery_summary.json"
    summary_txt = out_dir / f"{crc}_codec_mastery_summary.txt"
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_lines = [
        "CODEC MASTERY PIPELINE",
        f"generated_at={summary['generated_at']}",
        f"pure_jsonl={summary['pure_jsonl']}",
        f"console_hint={summary['console_hint']}",
        f"rom_crc32={summary.get('rom_crc32')}",
        f"probe_before_candidates_total={before_cands}",
        f"probe_after_candidates_total={after_cands}",
        f"probe_candidates_gain={gain}",
        f"profile_path={summary.get('profile_path')}",
        f"profile_installed_path={summary.get('profile_installed_path')}",
        f"probe_profile_loaded={summary.get('probe_profile_loaded')}",
        f"probe_profile_applied={summary.get('probe_profile_applied')}",
        f"probe_recommendation={summary.get('probe_recommendation')}",
        f"patch_requested={patch_result.get('requested')}",
        f"patch_ok={patch_result.get('ok')}",
    ]
    summary_txt.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print(f"[OK] profile={profile_path}")
    print(f"[OK] probe_proof={proof_path}")
    print(f"[OK] summary_json={summary_json}")
    print(f"[OK] summary_txt={summary_txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
