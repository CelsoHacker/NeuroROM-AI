# -*- coding: utf-8 -*-
"""
Verificador de convergencia de cobertura para runtime dyn.

Objetivo:
- Agregar multiplos runs dyn do mesmo ROM (CRC32 + rom_size).
- Medir estabilizacao de captura (delta de unicos).
- Medir legibilidade (taxa de glyph desconhecido no preview).
- Medir cobertura por hits com a mesma regra do dyn_fontmap_rounds.
- Gerar relatorio final auditavel (JSON/TXT + prova com sha256).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

try:
    from .common import infer_crc_from_name, iter_jsonl, parse_int, write_json
    from .dyn_fontmap_rounds import load_bootstrap_rows
except ImportError:  # pragma: no cover
    from common import infer_crc_from_name, iter_jsonl, parse_int, write_json  # type: ignore
    from dyn_fontmap_rounds import load_bootstrap_rows  # type: ignore


HEX_HASH_RE = re.compile(r"^[0-9A-F]{8}$")
HEX_PATTERN_RE = re.compile(r"^[0-9A-F]+$")
CONTROL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
WS_RE = re.compile(r"\s+")
RUN_PREFIX_RE = re.compile(r"^(\d+)_")
UNKNOWN_MARKERS = {"?", "�"}


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _log(message: str) -> None:
    print(f"[DYN_CONVERGE] {message}")


def _sanitize_text(value: Any) -> str:
    txt = str(value or "")
    txt = CONTROL_RE.sub("", txt)
    txt = WS_RE.sub(" ", txt).strip()
    return txt


def _normalize_hash(value: Any) -> Optional[str]:
    if value is None:
        return None
    txt = str(value).strip().upper()
    if txt.startswith("0X"):
        txt = txt[2:]
    if HEX_HASH_RE.fullmatch(txt):
        return txt
    return None


def _normalize_pattern_hex(value: Any) -> Optional[str]:
    txt = str(value or "").strip().upper().replace(" ", "")
    if not txt:
        return None
    if not HEX_PATTERN_RE.fullmatch(txt):
        return None
    if len(txt) % 2 != 0:
        return None
    return txt


def _safe_ratio(value: Any) -> float:
    try:
        out = float(value)
    except Exception:
        return 0.0
    if out < 0.0:
        return 0.0
    if out > 1.0:
        return 1.0
    return out


def _format_pct(value: float) -> float:
    return float(round(max(0.0, min(100.0, value)), 4))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _safe_relative(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except Exception:
        return str(path.resolve())


def _run_sort_key(run_dir: Path) -> Tuple[int, str]:
    m = RUN_PREFIX_RE.match(run_dir.name)
    if m:
        return (int(m.group(1)), run_dir.name.lower())
    return (10**9, run_dir.name.lower())


def _has_dyn_files(run_dir: Path) -> bool:
    if not run_dir.is_dir():
        return False
    has_log = any(run_dir.glob("*_dyn_text_log.jsonl"))
    has_unique = any(run_dir.glob("*_dyn_text_unique.txt"))
    return bool(has_log and has_unique)


def _discover_run_dirs(runs_dir: Path) -> List[Path]:
    if not runs_dir.exists() or not runs_dir.is_dir():
        raise FileNotFoundError(f"--runs-dir invalido: {runs_dir}")
    runs_dir = runs_dir.resolve()
    if _has_dyn_files(runs_dir):
        return [runs_dir]
    candidates = [p.resolve() for p in runs_dir.iterdir() if p.is_dir() and _has_dyn_files(p)]
    if not candidates:
        raise RuntimeError(
            "Nenhum run dyn encontrado em --runs-dir (esperado *_dyn_text_log.jsonl e *_dyn_text_unique.txt)."
        )
    candidates.sort(key=_run_sort_key)
    return candidates


def _resolve_file_override(
    *,
    run_dir: Path,
    override: str,
    default_glob: str,
    required: bool,
) -> Optional[Path]:
    run_dir = run_dir.resolve()
    override = str(override or "").strip()
    if override:
        raw = Path(override).expanduser()
        if raw.is_absolute():
            if raw.exists():
                return raw.resolve()
            if required:
                raise FileNotFoundError(f"Arquivo nao encontrado: {raw}")
            return None
        if any(ch in override for ch in ("*", "?", "[")):
            cands = sorted(run_dir.glob(override))
            if cands:
                return cands[0].resolve()
            if required:
                raise FileNotFoundError(f"Nenhum arquivo para override '{override}' em {run_dir}")
            return None
        rel = (run_dir / override).resolve()
        if rel.exists():
            return rel
        if required:
            raise FileNotFoundError(f"Arquivo override nao encontrado em run {run_dir}: {override}")
        return None

    cands = sorted(run_dir.glob(default_glob))
    if cands:
        return cands[0].resolve()
    if required:
        raise FileNotFoundError(f"Nenhum arquivo '{default_glob}' em {run_dir}")
    return None


def _read_dyn_log(dyn_log_path: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    meta: Dict[str, Any] = {}
    rows: List[Dict[str, Any]] = []
    for obj in iter_jsonl(dyn_log_path):
        typ = str(obj.get("type", "")).strip().lower()
        if typ == "meta" and not meta:
            meta = dict(obj)
            continue
        if typ != "dyn_text":
            continue
        if isinstance(obj, dict):
            rows.append(dict(obj))
    return meta, rows


def _read_dyn_log_meta_only(path: Path) -> Dict[str, Any]:
    for obj in iter_jsonl(path):
        if str(obj.get("type", "")).lower() == "meta":
            return dict(obj)
    return {}


def _discover_aux_raw_meta(run_dir: Path, crc_hint: str) -> Dict[str, Any]:
    patterns: List[str] = []
    crc_hint = str(crc_hint or "").upper().strip()
    if crc_hint:
        patterns.append(f"{crc_hint}_dyn_text_log_raw*.jsonl")
    patterns.append("*_dyn_text_log_raw*.jsonl")
    for pattern in patterns:
        for cand in sorted(run_dir.glob(pattern)):
            meta = _read_dyn_log_meta_only(cand)
            if meta:
                meta["_source_path"] = str(cand.resolve())
                return meta
    return {}


def _parse_hash_list(raw: Any) -> List[str]:
    out: List[str] = []
    if isinstance(raw, list):
        for item in raw:
            h = _normalize_hash(item)
            if h:
                out.append(h)
        return out
    if isinstance(raw, str):
        for token in re.split(r"[,\s;]+", raw):
            h = _normalize_hash(token)
            if h:
                out.append(h)
    return out


def _load_mapping_dict(mapping_path: Optional[Path]) -> Dict[str, str]:
    if mapping_path is None or not mapping_path.exists():
        return {}
    try:
        obj = json.loads(mapping_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    if not isinstance(obj, dict):
        return {}

    raw_map: Any
    if isinstance(obj.get("mappings"), dict):
        raw_map = obj.get("mappings")
    elif isinstance(obj.get("glyph_hash_to_char"), dict):
        raw_map = obj.get("glyph_hash_to_char")
    else:
        raw_map = obj

    if not isinstance(raw_map, dict):
        return {}

    mapping: Dict[str, str] = {}
    for key, value in raw_map.items():
        glyph_hash = _normalize_hash(key)
        if not glyph_hash:
            continue
        if value is None:
            continue
        mapped = str(value)
        if mapped == "":
            continue
        mapping[glyph_hash] = mapped
    return mapping


def _load_unique_texts(dyn_unique_path: Path) -> List[str]:
    dedup: Dict[str, str] = {}
    lines = dyn_unique_path.read_text(encoding="utf-8", errors="replace").splitlines()
    for raw in lines:
        raw = str(raw or "").strip()
        if not raw:
            continue
        text = _sanitize_text(raw.split("\t", 1)[0])
        if not text:
            continue
        key = text.casefold()
        if key not in dedup:
            dedup[key] = text
    out = list(dedup.values())
    out.sort(key=lambda s: s.casefold())
    return out


def _render_mapped_line(row: Dict[str, Any], glyph_map: Dict[str, str]) -> str:
    base_line = _sanitize_text(row.get("line", ""))
    glyph_hashes = _parse_hash_list(row.get("glyph_hashes", []))
    if not glyph_hashes:
        return base_line

    target_len = min(len(base_line), len(glyph_hashes))
    if target_len <= 0:
        target_len = min(len(glyph_hashes), 32)

    chars: List[str] = []
    for idx in range(target_len):
        glyph_hash = glyph_hashes[idx]
        ch = glyph_map.get(glyph_hash)
        if ch is None and idx < len(base_line):
            src = base_line[idx]
            if src != "?":
                ch = src
        if ch is None:
            ch = "?"
        chars.append(ch)
    return _sanitize_text("".join(chars))


def _build_preview_unique_rows(
    dyn_rows: List[Dict[str, Any]],
    glyph_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    dedup: Dict[str, Dict[str, Any]] = {}
    for row in dyn_rows:
        mapped_line = _render_mapped_line(row, glyph_map)
        if not mapped_line:
            continue
        key = mapped_line.casefold()
        frame = int(parse_int(row.get("frame"), default=1 << 30) or (1 << 30))
        scene_hash = str(row.get("scene_hash", "") or "")
        hits = int(parse_int(row.get("hits"), default=1) or 1)
        unmapped_ratio = _safe_ratio(row.get("unmapped_ratio"))

        slot = dedup.get(key)
        if slot is None:
            dedup[key] = {
                "text": mapped_line,
                "text_key": key,
                "first_frame": frame,
                "scene_hashes": [scene_hash] if scene_hash else [],
                "hits": max(1, hits),
                "unmapped_ratio_max": float(round(unmapped_ratio, 4)),
            }
            continue

        slot["hits"] = int(parse_int(slot.get("hits"), default=0) or 0) + max(1, hits)
        if frame < int(parse_int(slot.get("first_frame"), default=frame) or frame):
            slot["first_frame"] = frame
        if scene_hash:
            scene_list = list(slot.get("scene_hashes", []))
            if scene_hash not in scene_list and len(scene_list) < 12:
                scene_list.append(scene_hash)
                slot["scene_hashes"] = scene_list
        if unmapped_ratio > _safe_ratio(slot.get("unmapped_ratio_max")):
            slot["unmapped_ratio_max"] = float(round(unmapped_ratio, 4))

    rows = list(dedup.values())
    rows.sort(
        key=lambda r: (
            str(r.get("text_key", "")),
            int(parse_int(r.get("first_frame"), default=1 << 30) or (1 << 30)),
            str(",".join(r.get("scene_hashes", [])[:1])),
        )
    )
    return rows


def _unique_rows_from_texts(texts: List[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for idx, text in enumerate(texts):
        rows.append(
            {
                "text": _sanitize_text(text),
                "text_key": _sanitize_text(text).casefold(),
                "first_frame": idx,
                "scene_hashes": [],
                "hits": 1,
                "unmapped_ratio_max": 0.0,
            }
        )
    rows.sort(key=lambda r: str(r.get("text_key", "")))
    return rows


def _merge_preview_unique_rows(
    base_rows: List[Dict[str, Any]],
    extra_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for row in base_rows + extra_rows:
        text = _sanitize_text(row.get("text", ""))
        if not text:
            continue
        key = text.casefold()
        frame = int(parse_int(row.get("first_frame"), default=1 << 30) or (1 << 30))
        scene_hashes = row.get("scene_hashes", [])
        if not isinstance(scene_hashes, list):
            scene_hashes = []
        hits = int(parse_int(row.get("hits"), default=1) or 1)
        ratio = _safe_ratio(row.get("unmapped_ratio_max"))

        slot = merged.get(key)
        if slot is None:
            merged[key] = {
                "text": text,
                "text_key": key,
                "first_frame": frame,
                "scene_hashes": [str(x) for x in scene_hashes if str(x)],
                "hits": max(1, hits),
                "unmapped_ratio_max": float(round(ratio, 4)),
            }
            continue

        slot["hits"] = int(parse_int(slot.get("hits"), default=0) or 0) + max(1, hits)
        if frame < int(parse_int(slot.get("first_frame"), default=frame) or frame):
            slot["first_frame"] = frame
        known_hashes = list(slot.get("scene_hashes", []))
        for sh in scene_hashes:
            sh_txt = str(sh or "")
            if not sh_txt:
                continue
            if sh_txt in known_hashes:
                continue
            if len(known_hashes) >= 12:
                break
            known_hashes.append(sh_txt)
        slot["scene_hashes"] = known_hashes
        if ratio > _safe_ratio(slot.get("unmapped_ratio_max")):
            slot["unmapped_ratio_max"] = float(round(ratio, 4))

    out = list(merged.values())
    out.sort(
        key=lambda r: (
            str(r.get("text_key", "")),
            int(parse_int(r.get("first_frame"), default=1 << 30) or (1 << 30)),
            str(",".join(r.get("scene_hashes", [])[:1])),
        )
    )
    return out


def _write_preview_text(path: Path, rows: List[Dict[str, Any]]) -> None:
    lines: List[str] = []
    for row in rows:
        scene_label = ",".join(str(s) for s in row.get("scene_hashes", [])[:3] if str(s))
        line = (
            f"{row.get('text', '')}\t"
            f"frame={int(parse_int(row.get('first_frame'), default=0) or 0)}\t"
            f"scene_hash={scene_label}\t"
            f"hits={int(parse_int(row.get('hits'), default=1) or 1)}\t"
            f"unmapped_ratio_max={float(_safe_ratio(row.get('unmapped_ratio_max'))):.4f}"
        )
        lines.append(line)
    content = "\n".join(lines)
    if content and not content.endswith("\n"):
        content += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _unknown_stats(unique_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    unknown_count = 0
    chars_total = 0
    for row in unique_rows:
        text = str(row.get("text", "") or "")
        if not text:
            continue
        chars_total += len(text)
        for ch in text:
            if ch in UNKNOWN_MARKERS:
                unknown_count += 1
    unknown_pct = (float(unknown_count) / float(max(1, chars_total))) * 100.0 if chars_total > 0 else 0.0
    return {
        "unknown_count": int(unknown_count),
        "chars_total": int(chars_total),
        "unknown_pct": _format_pct(unknown_pct),
    }


def _pattern_set_from_bootstrap_rows(rows: Iterable[Dict[str, Any]]) -> Set[str]:
    patterns: Set[str] = set()
    for row in rows:
        pattern = _normalize_pattern_hex(row.get("pattern_hex"))
        if pattern:
            patterns.add(pattern)
    return patterns


def _pattern_set_from_dyn_rows(rows: Iterable[Dict[str, Any]]) -> Set[str]:
    patterns: Set[str] = set()
    for row in rows:
        samples = row.get("unknown_glyph_samples", [])
        if not isinstance(samples, list):
            continue
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            pattern = _normalize_pattern_hex(sample.get("pattern_hex"))
            if pattern:
                patterns.add(pattern)
    return patterns


def _resolve_output_crc_dir(runs_dir: Path, run_dirs: List[Path], crc: str) -> Path:
    first_run = run_dirs[0]
    out_base: Path
    if first_run.parent.name.lower() == "runtime":
        out_base = first_run.parent.parent
    elif runs_dir.name.lower() == "runtime":
        out_base = runs_dir.parent
    else:
        out_base = runs_dir

    crc = str(crc or "").upper().strip()
    if crc and crc != "UNKNOWN000" and out_base.name.upper() != crc:
        out_base = out_base / crc
    out_base.mkdir(parents=True, exist_ok=True)
    return out_base.resolve()


def _choose_identity(run_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    crc_values: List[str] = []
    size_values: List[int] = []
    missing_crc_runs: List[str] = []
    missing_size_runs: List[str] = []
    for item in run_metrics:
        run_name = str(item.get("run_name", ""))
        crc = str(item.get("rom_crc32", "") or "").upper().strip()
        size = int(parse_int(item.get("rom_size"), default=0) or 0)
        if crc and crc != "UNKNOWN000":
            crc_values.append(crc)
        else:
            missing_crc_runs.append(run_name)
        if size > 0:
            size_values.append(size)
        else:
            missing_size_runs.append(run_name)

    unique_crc = sorted(set(crc_values))
    unique_sizes = sorted(set(size_values))
    crc_mismatch = len(unique_crc) > 1
    size_mismatch = len(unique_sizes) > 1

    canonical_crc = unique_crc[0] if unique_crc else "UNKNOWN000"
    canonical_size = unique_sizes[0] if unique_sizes else 0

    return {
        "rom_crc32": canonical_crc,
        "rom_size": int(canonical_size),
        "crc_values_detected": unique_crc,
        "rom_size_values_detected": unique_sizes,
        "crc_mismatch": bool(crc_mismatch),
        "rom_size_mismatch": bool(size_mismatch),
        "missing_crc_runs": missing_crc_runs,
        "missing_rom_size_runs": missing_size_runs,
        "identity_ok": bool(
            canonical_crc != "UNKNOWN000"
            and canonical_size > 0
            and not crc_mismatch
            and not size_mismatch
            and not missing_crc_runs
            and not missing_size_runs
        ),
    }


def _calc_delta_pct(delta_count: int, prev_count: int) -> float:
    if prev_count <= 0:
        return 0.0 if delta_count == 0 else 100.0
    return (abs(float(delta_count)) / float(prev_count)) * 100.0


def _write_report_txt(path: Path, report: Dict[str, Any]) -> None:
    lines: List[str] = []
    lines.append("RUNTIME DYN CONVERGENCE REPORT")
    lines.append(f"ROM_CRC32: {report.get('rom_crc32')}")
    lines.append(f"ROM_SIZE: {report.get('rom_size')}")
    lines.append(f"RUNS_TOTAL: {report.get('runs_total')}")
    lines.append(f"CONVERGED: {str(report.get('converged', False)).upper()}")
    lines.append(f"DECISION: {report.get('decision')}")
    lines.append("MOTIVOS:")
    reasons = report.get("decision_reasons", [])
    if isinstance(reasons, list) and reasons:
        for reason in reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("- ALL_THRESHOLDS_OK")

    criteria = report.get("criteria", {})
    lines.append("CRITERIA:")
    lines.append(f"- identity_ok={criteria.get('identity_ok')}")
    lines.append(f"- capture_convergence_ok={criteria.get('capture_convergence_ok')}")
    lines.append(f"- legibility_ok={criteria.get('legibility_ok')}")
    lines.append(f"- coverage_ok={criteria.get('coverage_ok')}")

    thresholds = report.get("thresholds", {})
    lines.append("THRESHOLDS:")
    lines.append(f"- k={thresholds.get('k')}")
    lines.append(f"- delta_unique_pct_max={thresholds.get('delta_unique_pct_max')}")
    lines.append(f"- delta_glyph_pct_max={thresholds.get('delta_glyph_pct_max')}")
    lines.append(f"- max_unknown_pct={thresholds.get('max_unknown_pct')}")
    lines.append(f"- min_coverage_hits={thresholds.get('min_coverage_hits')}")

    consolidated = report.get("consolidated", {})
    lines.append("CONSOLIDATED:")
    lines.append(f"- unique_preview_rows={consolidated.get('preview_unique_rows_total')}")
    lines.append(f"- unknown_count={consolidated.get('unknown_count')}")
    lines.append(f"- unknown_pct={consolidated.get('unknown_pct')}")
    lines.append(f"- coverage_hits_total={consolidated.get('coverage_hits_total')}")
    lines.append(f"- coverage_hits_mapped={consolidated.get('coverage_hits_mapped')}")
    lines.append(f"- coverage_hits_percent={consolidated.get('coverage_hits_percent')}")
    lines.append(f"- preview_path={consolidated.get('preview_output_path')}")

    lines.append("RUNS:")
    runs = report.get("runs", [])
    if isinstance(runs, list):
        for run in runs:
            lines.append(
                (
                    f"- {run.get('run_name')}: unique_text={run.get('unique_text_count')} | "
                    f"unique_glyphs={run.get('unique_glyphs_count')} | total_hits={run.get('total_hits')} | "
                    f"unknown_count={run.get('unknown_count')} | unknown_pct={run.get('unknown_pct')} | "
                    f"coverage_hits_percent={run.get('coverage_hits_percent')}"
                )
            )

    lines.append("DELTAS:")
    deltas = report.get("deltas", [])
    if isinstance(deltas, list) and deltas:
        for delta in deltas:
            lines.append(
                (
                    f"- {delta.get('prev_run_name')} -> {delta.get('run_name')}: "
                    f"delta_unique_text_count={delta.get('delta_unique_text_count')} "
                    f"({delta.get('delta_unique_text_pct')}%), "
                    f"delta_unique_glyphs_count={delta.get('delta_unique_glyphs_count')} "
                    f"({delta.get('delta_unique_glyphs_pct')}%)"
                )
            )
    else:
        lines.append("- sem deltas (runs insuficientes)")

    content = "\n".join(lines)
    if content and not content.endswith("\n"):
        content += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def analyze_convergence(
    *,
    runs_dir: Path,
    bootstrap_override: str,
    dyn_log_override: str,
    dyn_unique_override: str,
    mapping_json: Optional[Path],
    k: int,
    delta_unique_pct_max: float,
    delta_glyph_pct_max: float,
    max_unknown_pct: float,
    min_coverage_hits: float,
    strict: bool,
) -> Dict[str, Any]:
    run_dirs = _discover_run_dirs(runs_dir)
    mapping = _load_mapping_dict(mapping_json)

    consumed_files: List[Dict[str, Any]] = []
    run_metrics: List[Dict[str, Any]] = []
    consolidated_preview_rows: List[Dict[str, Any]] = []
    aggregated_bootstrap_hits: Dict[str, int] = {}

    for idx, run_dir in enumerate(run_dirs, start=1):
        dyn_log_path = _resolve_file_override(
            run_dir=run_dir,
            override=dyn_log_override,
            default_glob="*_dyn_text_log.jsonl",
            required=True,
        )
        dyn_unique_path = _resolve_file_override(
            run_dir=run_dir,
            override=dyn_unique_override,
            default_glob="*_dyn_text_unique.txt",
            required=True,
        )
        if dyn_log_path is None or dyn_unique_path is None:
            raise RuntimeError(f"Run invalido: {run_dir}")

        meta, dyn_rows = _read_dyn_log(dyn_log_path)
        inferred_crc = (
            str(meta.get("rom_crc32", "") or "").upper().strip()
            or infer_crc_from_name(dyn_log_path.name)
            or infer_crc_from_name(str(run_dir))
            or "UNKNOWN000"
        )
        inferred_size = int(parse_int(meta.get("rom_size"), default=0) or 0)

        aux_meta = {}
        if inferred_size <= 0:
            aux_meta = _discover_aux_raw_meta(run_dir, inferred_crc)
            if aux_meta:
                inferred_size = int(parse_int(aux_meta.get("rom_size"), default=0) or 0)
                aux_crc = str(aux_meta.get("rom_crc32", "") or "").upper().strip()
                if aux_crc and inferred_crc == "UNKNOWN000":
                    inferred_crc = aux_crc
                aux_src = aux_meta.get("_source_path")
                if aux_src:
                    consumed_files.append(
                        {
                            "role": "dyn_log_aux",
                            "run_name": run_dir.name,
                            "path": str(Path(str(aux_src)).resolve()),
                        }
                    )

        bootstrap_path: Optional[Path] = None
        if bootstrap_override:
            bootstrap_path = _resolve_file_override(
                run_dir=run_dir,
                override=bootstrap_override,
                default_glob="*_dyn_fontmap_bootstrap.json",
                required=False,
            )
        else:
            preferred = run_dir / f"{inferred_crc}_dyn_fontmap_bootstrap.json"
            if preferred.exists():
                bootstrap_path = preferred.resolve()
            else:
                cands = sorted(run_dir.glob("*_dyn_fontmap_bootstrap.json"))
                if cands:
                    bootstrap_path = cands[0].resolve()

        bootstrap_payload: Dict[str, Any] = {}
        bootstrap_rows: List[Dict[str, Any]] = []
        if bootstrap_path is not None and bootstrap_path.exists():
            bootstrap_payload = load_bootstrap_rows(bootstrap_path)
            bootstrap_rows = list(bootstrap_payload.get("rows", []))
            if inferred_crc == "UNKNOWN000":
                inferred_crc = str(bootstrap_payload.get("rom_crc32", "UNKNOWN000") or "UNKNOWN000").upper()
            if inferred_size <= 0:
                inferred_size = int(parse_int(bootstrap_payload.get("rom_size"), default=0) or 0)

        unique_texts = _load_unique_texts(dyn_unique_path)
        unique_text_count = len(unique_texts)

        if mapping:
            preview_rows = _build_preview_unique_rows(dyn_rows, mapping)
        else:
            preview_rows = _unique_rows_from_texts(unique_texts)

        unknown = _unknown_stats(preview_rows)

        if bootstrap_rows:
            pattern_set = _pattern_set_from_bootstrap_rows(bootstrap_rows)
            total_hits = int(sum(int(parse_int(r.get("hits"), default=0) or 0) for r in bootstrap_rows))
            coverage_hits_mapped = int(
                sum(
                    int(parse_int(r.get("hits"), default=0) or 0)
                    for r in bootstrap_rows
                    if str(r.get("glyph_hash", "")).upper() in mapping
                )
            )
            for row in bootstrap_rows:
                glyph_hash = str(row.get("glyph_hash", "")).upper()
                if not glyph_hash:
                    continue
                aggregated_bootstrap_hits[glyph_hash] = (
                    int(aggregated_bootstrap_hits.get(glyph_hash, 0))
                    + int(parse_int(row.get("hits"), default=0) or 0)
                )
        else:
            pattern_set = _pattern_set_from_dyn_rows(dyn_rows)
            total_hits = 0
            coverage_hits_mapped = 0

        coverage_hits_percent = (
            (float(coverage_hits_mapped) / float(max(1, total_hits))) * 100.0 if total_hits > 0 else 0.0
        )

        run_item = {
            "run_index": int(idx),
            "run_name": str(run_dir.name),
            "run_dir": str(run_dir.resolve()),
            "rom_crc32": str(inferred_crc).upper(),
            "rom_size": int(max(0, inferred_size)),
            "dyn_log_path": str(dyn_log_path),
            "dyn_unique_path": str(dyn_unique_path),
            "bootstrap_path": str(bootstrap_path) if bootstrap_path else None,
            "unique_text": int(unique_text_count),
            "unique_text_count": int(unique_text_count),
            "unique_glyphs": int(len(pattern_set)),
            "unique_glyphs_count": int(len(pattern_set)),
            "total_hits": int(total_hits),
            "coverage_hits_percent": _format_pct(coverage_hits_percent),
            "unknown_count": int(unknown["unknown_count"]),
            "unknown_pct": _format_pct(float(unknown["unknown_pct"])),
        }
        run_metrics.append(run_item)
        consolidated_preview_rows = _merge_preview_unique_rows(consolidated_preview_rows, preview_rows)

        consumed_files.append({"role": "dyn_log", "run_name": run_dir.name, "path": str(dyn_log_path)})
        consumed_files.append({"role": "dyn_unique", "run_name": run_dir.name, "path": str(dyn_unique_path)})
        if bootstrap_path is not None and bootstrap_path.exists():
            consumed_files.append({"role": "bootstrap", "run_name": run_dir.name, "path": str(bootstrap_path)})

    if mapping_json is not None and mapping_json.exists():
        consumed_files.append({"role": "mapping_json", "run_name": "", "path": str(mapping_json.resolve())})

    identity = _choose_identity(run_metrics)
    if strict:
        if not bool(identity.get("identity_ok", False)):
            raise RuntimeError(
                "Falha em --strict: mismatch/ausencia de identidade CRC32+rom_size entre runs."
            )

    if bool(identity.get("crc_mismatch")) or bool(identity.get("rom_size_mismatch")):
        _log("Aviso: mismatch de CRC32/rom_size detectado entre runs.")

    canonical_crc = str(identity.get("rom_crc32", "UNKNOWN000") or "UNKNOWN000").upper()
    canonical_size = int(parse_int(identity.get("rom_size"), default=0) or 0)
    out_crc_dir = _resolve_output_crc_dir(runs_dir.resolve(), run_dirs, canonical_crc)

    preview_out_path: Optional[Path] = None
    if mapping:
        preview_out_path = out_crc_dir / f"{canonical_crc}_dyn_text_unique_preview.txt"
        _write_preview_text(preview_out_path, consolidated_preview_rows)

    consolidated_unknown = _unknown_stats(consolidated_preview_rows)
    coverage_hits_total = int(sum(int(v) for v in aggregated_bootstrap_hits.values()))
    coverage_hits_mapped = int(
        sum(int(hits) for glyph_hash, hits in aggregated_bootstrap_hits.items() if glyph_hash in mapping)
    )
    coverage_hits_percent = (
        (float(coverage_hits_mapped) / float(max(1, coverage_hits_total))) * 100.0
        if coverage_hits_total > 0
        else 0.0
    )

    deltas: List[Dict[str, Any]] = []
    for i in range(1, len(run_metrics)):
        prev_run = run_metrics[i - 1]
        curr_run = run_metrics[i]
        delta_unique = int(curr_run["unique_text_count"]) - int(prev_run["unique_text_count"])
        delta_glyph = int(curr_run["unique_glyphs_count"]) - int(prev_run["unique_glyphs_count"])
        delta_item = {
            "run_index": int(curr_run["run_index"]),
            "run_name": str(curr_run["run_name"]),
            "prev_run_index": int(prev_run["run_index"]),
            "prev_run_name": str(prev_run["run_name"]),
            "delta_unique_text_count": int(delta_unique),
            "delta_unique_text_pct": _format_pct(
                _calc_delta_pct(delta_unique, int(prev_run["unique_text_count"]))
            ),
            "delta_unique_glyphs_count": int(delta_glyph),
            "delta_unique_glyphs_pct": _format_pct(
                _calc_delta_pct(delta_glyph, int(prev_run["unique_glyphs_count"]))
            ),
        }
        deltas.append(delta_item)

    k = max(1, int(k))
    capture_ok = True
    capture_reasons: List[str] = []
    if len(run_metrics) < k:
        capture_ok = False
        capture_reasons.append(f"RUNS_INSUFICIENTES: total={len(run_metrics)} < k={k}")
    else:
        window_deltas = deltas[-(k - 1) :] if k > 1 else []
        for delta in window_deltas:
            if float(delta["delta_unique_text_pct"]) > float(delta_unique_pct_max):
                capture_ok = False
                capture_reasons.append(
                    f"DELTA_UNIQUE_TEXT_ACIMA_LIMIAR em {delta['prev_run_name']}->{delta['run_name']}: "
                    f"{delta['delta_unique_text_pct']} > {delta_unique_pct_max}"
                )
            if float(delta["delta_unique_glyphs_pct"]) > float(delta_glyph_pct_max):
                capture_ok = False
                capture_reasons.append(
                    f"DELTA_UNIQUE_GLYPHS_ACIMA_LIMIAR em {delta['prev_run_name']}->{delta['run_name']}: "
                    f"{delta['delta_unique_glyphs_pct']} > {delta_glyph_pct_max}"
                )

    legibility_ok = float(consolidated_unknown["unknown_pct"]) <= float(max_unknown_pct)
    coverage_ok = _format_pct(coverage_hits_percent) >= float(min_coverage_hits)
    identity_ok = bool(identity.get("identity_ok", False))

    reasons: List[str] = []
    if not identity_ok:
        reasons.append("IDENTIDADE_ROM_INVALIDA_OU_INCOMPLETA")
    reasons.extend(capture_reasons)
    if not legibility_ok:
        reasons.append(
            f"UNKNOWN_PCT_ACIMA_LIMIAR: {consolidated_unknown['unknown_pct']} > {float(max_unknown_pct)}"
        )
    if not coverage_ok:
        reasons.append(f"COVERAGE_HITS_ABAIXO_MINIMO: {_format_pct(coverage_hits_percent)} < {float(min_coverage_hits)}")
    if not reasons:
        reasons.append("ALL_THRESHOLDS_OK")

    converged = bool(identity_ok and capture_ok and legibility_ok and coverage_ok)

    report: Dict[str, Any] = {
        "schema": "runtime_dyn_convergence.v1",
        "generated_at": _now_utc_iso(),
        "rom_crc32": canonical_crc,
        "rom_size": int(canonical_size),
        "runs_dir": str(runs_dir.resolve()),
        "runs_total": int(len(run_metrics)),
        "strict": bool(strict),
        "thresholds": {
            "k": int(k),
            "delta_unique_pct_max": float(delta_unique_pct_max),
            "delta_glyph_pct_max": float(delta_glyph_pct_max),
            "max_unknown_pct": float(max_unknown_pct),
            "min_coverage_hits": float(min_coverage_hits),
        },
        "identity": identity,
        "runs": run_metrics,
        "deltas": deltas,
        "consolidated": {
            "preview_output_path": str(preview_out_path) if preview_out_path else None,
            "preview_unique_rows_total": int(len(consolidated_preview_rows)),
            "unknown_count": int(consolidated_unknown["unknown_count"]),
            "unknown_chars_total": int(consolidated_unknown["chars_total"]),
            "unknown_pct": _format_pct(float(consolidated_unknown["unknown_pct"])),
            "coverage_hits_total": int(coverage_hits_total),
            "coverage_hits_mapped": int(coverage_hits_mapped),
            "coverage_hits_percent": _format_pct(coverage_hits_percent),
            "coverage_hits_scope": "bootstrap_rows_only",
        },
        "criteria": {
            "identity_ok": bool(identity_ok),
            "capture_convergence_ok": bool(capture_ok),
            "legibility_ok": bool(legibility_ok),
            "coverage_ok": bool(coverage_ok),
        },
        "decision": "CONVERGED" if converged else "NOT_CONVERGED",
        "converged": bool(converged),
        "decision_reasons": reasons,
    }

    report_json_path = out_crc_dir / f"{canonical_crc}_dyn_convergence_report.json"
    report_txt_path = out_crc_dir / f"{canonical_crc}_dyn_convergence_report.txt"
    proof_path = out_crc_dir / f"{canonical_crc}_dyn_convergence_proof.json"

    write_json(report_json_path, report)
    _write_report_txt(report_txt_path, report)

    unique_path_roles: Dict[str, Set[str]] = {}
    unique_path_runs: Dict[str, Set[str]] = {}
    resolved_paths: Dict[str, Path] = {}
    for item in consumed_files:
        role = str(item.get("role", "") or "")
        run_name = str(item.get("run_name", "") or "")
        path = Path(str(item.get("path", ""))).expanduser().resolve()
        key = str(path)
        resolved_paths[key] = path
        unique_path_roles.setdefault(key, set()).add(role)
        if run_name:
            unique_path_runs.setdefault(key, set()).add(run_name)

    all_paths = [resolved_paths[k] for k in sorted(resolved_paths.keys())]
    base_candidates = [str(p) for p in all_paths] + [str(out_crc_dir.resolve())]
    common_base = Path(os.path.commonpath(base_candidates)).resolve() if base_candidates else out_crc_dir.resolve()

    proof_files: List[Dict[str, Any]] = []
    for key in sorted(resolved_paths.keys()):
        file_path = resolved_paths[key]
        if not file_path.exists():
            continue
        proof_files.append(
            {
                "path": _safe_relative(file_path, common_base),
                "sha256": _sha256_file(file_path),
                "roles": sorted(unique_path_roles.get(key, set())),
                "runs": sorted(unique_path_runs.get(key, set())),
            }
        )

    proof = {
        "schema": "runtime_dyn_convergence_proof.v1",
        "generated_at": _now_utc_iso(),
        "rom_crc32": canonical_crc,
        "rom_size": int(canonical_size),
        "strict": bool(strict),
        "proof_base_dir": str(common_base),
        "consumed_files": proof_files,
        "consumed_relative_paths": [item["path"] for item in proof_files],
        "report_json_path": str(report_json_path),
        "report_txt_path": str(report_txt_path),
    }
    write_json(proof_path, proof)

    report["report_json_path"] = str(report_json_path)
    report["report_txt_path"] = str(report_txt_path)
    report["proof_path"] = str(proof_path)
    return report


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verifica convergencia de runtime dyn (captura, legibilidade e cobertura por hits)."
    )
    parser.add_argument(
        "--runs-dir",
        required=True,
        help="Diretorio com varios runs dyn (ex.: .../runtime contendo 2_runtime_dyn, 3_runtime_dyn...).",
    )
    parser.add_argument(
        "--bootstrap",
        default="",
        help=(
            "Override para bootstrap por run. Aceita caminho absoluto, caminho relativo por run "
            "ou glob (default: auto por CRC)."
        ),
    )
    parser.add_argument(
        "--dyn-log",
        default="",
        help=(
            "Override para dyn_log por run. Aceita caminho absoluto, caminho relativo por run "
            "ou glob (default: *_dyn_text_log.jsonl)."
        ),
    )
    parser.add_argument(
        "--dyn-unique",
        default="",
        help=(
            "Override para dyn_unique por run. Aceita caminho absoluto, caminho relativo por run "
            "ou glob (default: *_dyn_text_unique.txt)."
        ),
    )
    parser.add_argument(
        "--mapping-json",
        default="",
        help="Opcional: mapping atual para gerar preview consolidado e calcular coverage_hits_percent.",
    )
    parser.add_argument("--k", type=int, default=3, help="Quantidade de runs consecutivos para criterio de captura.")
    parser.add_argument(
        "--delta-unique-pct",
        type=float,
        default=0.5,
        help="Limiar maximo (%%) do delta de unique_text entre runs consecutivos.",
    )
    parser.add_argument(
        "--delta-glyph-pct",
        type=float,
        default=0.5,
        help="Limiar maximo (%%) do delta de unique_glyphs(pattern_hex) entre runs consecutivos.",
    )
    parser.add_argument(
        "--max-unknown-pct",
        type=float,
        default=1.0,
        help="Limiar maximo (%%) de '?' (ou glyph desconhecido) no preview consolidado.",
    )
    parser.add_argument(
        "--min-coverage-hits",
        type=float,
        default=95.0,
        help="Cobertura minima (%%) por hits para considerar convergido.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Falha imediatamente se houver mismatch/ausencia de CRC32+rom_size entre runs.",
    )
    return parser


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir).expanduser().resolve()
    mapping_json = Path(args.mapping_json).expanduser().resolve() if args.mapping_json else None

    try:
        report = analyze_convergence(
            runs_dir=runs_dir,
            bootstrap_override=str(args.bootstrap or ""),
            dyn_log_override=str(args.dyn_log or ""),
            dyn_unique_override=str(args.dyn_unique or ""),
            mapping_json=mapping_json,
            k=int(args.k),
            delta_unique_pct_max=float(args.delta_unique_pct),
            delta_glyph_pct_max=float(args.delta_glyph_pct),
            max_unknown_pct=float(args.max_unknown_pct),
            min_coverage_hits=float(args.min_coverage_hits),
            strict=bool(args.strict),
        )
    except Exception as exc:
        print(f"[ERRO] {exc}", file=sys.stderr)
        return 2

    _log(
        "Resultado final: "
        f"CONVERGED={bool(report.get('converged', False))} | "
        f"report={report.get('report_json_path')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
