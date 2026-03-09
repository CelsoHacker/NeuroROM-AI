#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analisa probe_hits.jsonl e gera runtime_hook_profile por CRC.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from .common import (
        infer_crc_from_name,
        infer_platform_from_path,
        iter_jsonl,
        load_platform_profile,
        parse_int,
        write_json,
    )
except ImportError:  # pragma: no cover
    from common import (  # type: ignore
        infer_crc_from_name,
        infer_platform_from_path,
        iter_jsonl,
        load_platform_profile,
        parse_int,
        write_json,
    )


def _norm_pc(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, int):
        return f"0x{int(value):X}"
    raw = str(value).strip()
    if not raw:
        return None
    iv = parse_int(raw, default=None)
    if iv is not None:
        return f"0x{int(iv):X}"
    return raw.upper()


def _norm_ptr_buf(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return raw


def _extract_crc_size_platform(meta: Dict[str, Any], hits_path: Path) -> Tuple[str, int, str]:
    crc = str(meta.get("rom_crc32", "") or "").upper().strip()
    if not crc:
        crc = infer_crc_from_name(hits_path.name) or infer_crc_from_name(str(hits_path.parent)) or "UNKNOWN000"
    size = parse_int(meta.get("rom_size"), default=0) or 0
    platform = str(meta.get("platform", "") or "").strip().lower()
    if not platform:
        platform = infer_platform_from_path(str(hits_path), fallback="master_system")
    return crc, int(size), str(platform)


def analyze_hits(hits_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    pc_counter: Counter[str] = Counter()
    frame_minmax: Dict[str, List[int]] = {}
    pc_seed_set: Dict[str, Set[str]] = defaultdict(set)
    ptr_counter: Counter[str] = Counter()
    ptr_reg_counter: Counter[str] = Counter()
    context_counter: Counter[str] = Counter()
    unique_frames: Set[int] = set()

    for row in hits_rows:
        frame = parse_int(row.get("frame"), default=None)
        if frame is not None:
            unique_frames.add(int(frame))

        pc = _norm_pc(row.get("pc"))
        if pc:
            pc_counter[pc] += 1
            seed = str(row.get("seed_key", row.get("seed_id", "")) or "").strip()
            if seed:
                pc_seed_set[pc].add(seed)
            if pc not in frame_minmax:
                frame_minmax[pc] = [int(frame or 0), int(frame or 0)]
            else:
                frame_minmax[pc][0] = min(frame_minmax[pc][0], int(frame or 0))
                frame_minmax[pc][1] = max(frame_minmax[pc][1], int(frame or 0))

        ptr = _norm_ptr_buf(row.get("ptr_or_buf"))
        if ptr:
            ptr_counter[ptr] += 1
            if ptr.upper().startswith("REG:"):
                ptr_reg_counter[ptr[4:]] += 1

        ptr_reg = str(row.get("ptr_register", "") or "").strip()
        if ptr_reg:
            ptr_reg_counter[ptr_reg] += 1

        ctx = str(row.get("context_tag", "") or "").strip().lower()
        if ctx:
            context_counter[ctx] += 1

    top_pcs: List[Dict[str, Any]] = []
    for pc, hits in sorted(pc_counter.items(), key=lambda kv: (-kv[1], kv[0])):
        mm = frame_minmax.get(pc, [0, 0])
        top_pcs.append(
            {
                "pc": pc,
                "hits": int(hits),
                "first_frame": int(mm[0]),
                "last_frame": int(mm[1]),
                "unique_seed_hits": int(len(pc_seed_set.get(pc, set()))),
            }
        )

    pointer_candidates = [
        {"name": name, "hits": int(hits)}
        for name, hits in sorted(ptr_reg_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    buffer_candidates = [
        {"ptr_or_buf": ptr, "hits": int(hits)}
        for ptr, hits in sorted(ptr_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    contexts = [
        {"context_tag": tag, "hits": int(hits)}
        for tag, hits in sorted(context_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    recommended = {
        "pc": top_pcs[0]["pc"] if top_pcs else None,
        "ptr_register": pointer_candidates[0]["name"] if pointer_candidates else None,
        "ptr_or_buf": buffer_candidates[0]["ptr_or_buf"] if buffer_candidates else None,
        "context_tag": contexts[0]["context_tag"] if contexts else None,
        "capture_strategy": "pc_hook_with_pointer" if top_pcs else "buffer_watch_only",
    }

    return {
        "probe_hits_total": int(len(hits_rows)),
        "probe_hits_unique_frames": int(len(unique_frames)),
        "probe_hits_unique_pcs": int(len(pc_counter)),
        "top_pcs": top_pcs[:64],
        "pointer_candidates": pointer_candidates[:32],
        "buffer_candidates": buffer_candidates[:64],
        "context_candidates": contexts[:16],
        "recommended_hook": recommended,
    }


def build_profile(
    hits_path: Path,
    out_path: Optional[Path] = None,
    platform_hint: Optional[str] = None,
) -> Path:
    meta: Dict[str, Any] = {}
    rows: List[Dict[str, Any]] = []
    for obj in iter_jsonl(hits_path):
        if obj.get("type") == "meta":
            meta = dict(obj)
            continue
        rows.append(dict(obj))

    crc, size, platform = _extract_crc_size_platform(meta, hits_path)
    if platform_hint:
        platform = str(platform_hint).strip().lower()
    profile_base = load_platform_profile(platform)
    analysis = analyze_hits(rows)

    payload = {
        "schema": "runtime_hook_profile.v1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "rom_crc32": crc,
        "rom_size": int(size),
        "platform": str(platform),
        "source_probe_hits": str(hits_path),
        "profile_base": {
            "cpu": profile_base.get("cpu"),
            "pc_register": profile_base.get("pc_register"),
            "pointer_registers": profile_base.get("pointer_registers", []),
            "buffer_registers": profile_base.get("buffer_registers", []),
            "default_terminators": profile_base.get("default_terminators", [0]),
            "memory_domains": profile_base.get("memory_domains", []),
            "max_bytes_per_capture": profile_base.get("max_bytes_per_capture", 192),
        },
        **analysis,
    }

    if out_path is None:
        out_path = hits_path.parent / f"{crc}_runtime_hook_profile.json"
    write_json(Path(out_path), payload)
    return Path(out_path)


def main() -> int:
    ap = argparse.ArgumentParser(description="Analisa probe_hits e gera runtime_hook_profile.")
    ap.add_argument("--probe-hits", required=True, help="Arquivo {CRC32}_probe_hits.jsonl")
    ap.add_argument("--out", default=None, help="Saida do profile JSON (opcional)")
    ap.add_argument("--platform", default=None, help="Forca plataforma (opcional)")
    args = ap.parse_args()

    hits_path = Path(args.probe_hits).expanduser().resolve()
    if not hits_path.exists():
        raise SystemExit(f"[ERRO] arquivo nao encontrado: {hits_path}")

    out = Path(args.out).expanduser().resolve() if args.out else None
    profile_path = build_profile(
        hits_path=hits_path,
        out_path=out,
        platform_hint=args.platform,
    )
    print(f"[OK] runtime_hook_profile={profile_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

