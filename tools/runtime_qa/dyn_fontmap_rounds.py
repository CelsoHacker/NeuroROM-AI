# -*- coding: utf-8 -*-
"""
Acelera rodadas de mapeamento de glyphs do runtime-dyn.

Fluxo principal:
1) Lê `{CRC}_dyn_fontmap_bootstrap.json` e ordena glyphs por impacto (`hits`).
2) Exporta CSV (top N) para priorização manual.
3) Agrupa por similaridade de `pattern_hex` (duplicatas/variantes).
4) Gera template JSON de mapeamento manual.
5) Aplica mapeamento em preview de `*_dyn_text_unique.txt` (via `*_dyn_text_log.jsonl`).
6) Emite relatório com cobertura por hits e progresso de resolução.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from .common import infer_crc_from_name, iter_jsonl, parse_int, write_json
except ImportError:
    from common import infer_crc_from_name, iter_jsonl, parse_int, write_json  # type: ignore


HEX_HASH_RE = re.compile(r"^[0-9A-Fa-f]{8}$")
CONTROL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
WS_RE = re.compile(r"\s+")


def _log(message: str) -> None:
    print(f"[DYN_FMAP_ROUNDS] {message}")


def _sanitize_text(value: Any) -> str:
    txt = str(value or "")
    txt = CONTROL_RE.sub("", txt)
    txt = WS_RE.sub(" ", txt).strip()
    return txt


def _normalize_text_key(value: Any) -> str:
    return _sanitize_text(value).casefold()


def _normalize_hash(value: Any) -> Optional[str]:
    if value is None:
        return None
    txt = str(value).strip().upper()
    if not HEX_HASH_RE.match(txt):
        return None
    return txt


def _normalize_pattern_hex(value: Any) -> str:
    txt = str(value or "").strip().replace(" ", "").upper()
    if not txt:
        return ""
    if len(txt) % 2 != 0:
        return ""
    try:
        bytes.fromhex(txt)
    except Exception:
        return ""
    return txt


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _format_pct(value: float) -> float:
    return float(round(max(0.0, min(100.0, value)), 4))


def _load_json_dict(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        raise RuntimeError(f"Falha ao ler JSON {path}: {exc}") from exc
    if not isinstance(obj, dict):
        raise RuntimeError(f"JSON inválido (esperado objeto): {path}")
    return obj


def load_bootstrap_rows(bootstrap_path: Path) -> Dict[str, Any]:
    obj = _load_json_dict(bootstrap_path)
    rows_raw = obj.get("rows", [])
    if not isinstance(rows_raw, list):
        rows_raw = []

    rows_by_hash: Dict[str, Dict[str, Any]] = {}
    for raw in rows_raw:
        if not isinstance(raw, dict):
            continue
        glyph_hash = _normalize_hash(raw.get("glyph_hash"))
        if not glyph_hash:
            continue
        hits = int(parse_int(raw.get("hits"), default=0) or 0)
        already_mapped = bool(raw.get("already_mapped", False))
        pattern_hex = _normalize_pattern_hex(raw.get("pattern_hex"))
        sample_contexts_raw = raw.get("sample_contexts", [])
        sample_contexts: List[str] = []
        if isinstance(sample_contexts_raw, list):
            for item in sample_contexts_raw:
                txt = _sanitize_text(item)
                if txt:
                    sample_contexts.append(txt)
                if len(sample_contexts) >= 8:
                    break

        slot = rows_by_hash.get(glyph_hash)
        if slot is None:
            rows_by_hash[glyph_hash] = {
                "glyph_hash": glyph_hash,
                "hits": max(0, hits),
                "already_mapped": already_mapped,
                "sample_contexts": sample_contexts,
                "pattern_hex": pattern_hex,
            }
            continue

        slot["hits"] = int(slot.get("hits", 0) or 0) + max(0, hits)
        slot["already_mapped"] = bool(slot.get("already_mapped", False)) or already_mapped
        if not slot.get("pattern_hex") and pattern_hex:
            slot["pattern_hex"] = pattern_hex
        seen_ctx = set(slot.get("sample_contexts", []))
        merged = list(slot.get("sample_contexts", []))
        for txt in sample_contexts:
            if txt in seen_ctx:
                continue
            merged.append(txt)
            seen_ctx.add(txt)
            if len(merged) >= 8:
                break
        slot["sample_contexts"] = merged

    rows = list(rows_by_hash.values())
    rows.sort(key=lambda r: (-int(r.get("hits", 0) or 0), str(r.get("glyph_hash", ""))))

    inferred_crc = (
        str(obj.get("rom_crc32", "") or "").strip().upper()
        or infer_crc_from_name(bootstrap_path.name)
        or infer_crc_from_name(str(bootstrap_path.parent))
        or "UNKNOWN000"
    )
    total = int(parse_int(obj.get("unknown_glyphs_total"), default=len(rows)) or len(rows))
    if total < len(rows):
        total = len(rows)

    return {
        "schema": str(obj.get("schema", "") or ""),
        "rom_crc32": inferred_crc,
        "rom_size": int(parse_int(obj.get("rom_size"), default=0) or 0),
        "unknown_glyphs_total": total,
        "rows": rows,
    }


def _pattern_int(pattern_hex: str) -> Optional[int]:
    if not pattern_hex:
        return None
    try:
        return int(pattern_hex, 16)
    except Exception:
        return None


def _cluster_rows_by_pattern(
    rows_sorted: List[Dict[str, Any]],
    max_hamming_bits: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    clusters: List[Dict[str, Any]] = []
    top_rows: List[Dict[str, Any]] = []

    for rank, row in enumerate(rows_sorted, start=1):
        glyph_hash = str(row.get("glyph_hash", "") or "")
        pattern_hex = str(row.get("pattern_hex", "") or "")
        p_int = _pattern_int(pattern_hex)
        p_bits = len(pattern_hex) * 4 if pattern_hex else 0
        hits = int(parse_int(row.get("hits"), default=0) or 0)

        best_cluster_idx: Optional[int] = None
        best_distance: Optional[int] = None
        match_kind = "new"

        for idx, cluster in enumerate(clusters):
            rep_hex = str(cluster.get("rep_pattern_hex", "") or "")
            rep_int = cluster.get("rep_pattern_int")
            rep_bits = int(cluster.get("pattern_bits", 0) or 0)

            # Mesma assinatura visual exata.
            if pattern_hex and rep_hex and pattern_hex == rep_hex:
                best_cluster_idx = idx
                best_distance = 0
                match_kind = "exact"
                break

            # Aproximação por distância de Hamming (somente se tamanho bate).
            if (
                p_int is None
                or rep_int is None
                or p_bits <= 0
                or rep_bits <= 0
                or p_bits != rep_bits
            ):
                continue
            dist = int((int(p_int) ^ int(rep_int)).bit_count())
            if dist > int(max_hamming_bits):
                continue
            if best_distance is None or dist < best_distance:
                best_distance = dist
                best_cluster_idx = idx
                match_kind = "near"

        if best_cluster_idx is None:
            cluster_id = f"G{len(clusters) + 1:03d}"
            cluster = {
                "group_id": cluster_id,
                "rep_glyph_hash": glyph_hash,
                "rep_pattern_hex": pattern_hex,
                "rep_pattern_int": p_int,
                "pattern_bits": p_bits,
                "members": [glyph_hash],
                "member_rows": 1,
                "hits_total": hits,
                "near_members": 0,
                "exact_members": 1 if pattern_hex else 0,
            }
            clusters.append(cluster)
            best_cluster_idx = len(clusters) - 1
            best_distance = 0
            match_kind = "new"
        else:
            cluster = clusters[best_cluster_idx]
            cluster["members"] = list(cluster.get("members", [])) + [glyph_hash]
            cluster["member_rows"] = int(cluster.get("member_rows", 0) or 0) + 1
            cluster["hits_total"] = int(cluster.get("hits_total", 0) or 0) + hits
            if match_kind == "near":
                cluster["near_members"] = int(cluster.get("near_members", 0) or 0) + 1
            if match_kind == "exact":
                cluster["exact_members"] = int(cluster.get("exact_members", 0) or 0) + 1

        cluster = clusters[best_cluster_idx]
        group_size = int(cluster.get("member_rows", 1) or 1)
        similarity_pct = 100.0
        if p_bits > 0 and best_distance is not None:
            similarity_pct = (1.0 - (float(best_distance) / float(max(1, p_bits)))) * 100.0

        top_rows.append(
            {
                "rank": int(rank),
                "glyph_hash": glyph_hash,
                "hits": hits,
                "already_mapped": bool(row.get("already_mapped", False)),
                "sample_context_1": str((row.get("sample_contexts") or [""])[0] or ""),
                "pattern_hex": pattern_hex,
                "group_id": str(cluster.get("group_id", "")),
                "group_size": group_size,
                "group_match": match_kind,
                "group_distance_bits": int(best_distance or 0),
                "group_similarity_pct": _format_pct(similarity_pct),
                "group_representative": str(cluster.get("rep_glyph_hash", "") or ""),
            }
        )

    clusters_out: List[Dict[str, Any]] = []
    for cluster in clusters:
        members = list(cluster.get("members", []))
        clusters_out.append(
            {
                "group_id": str(cluster.get("group_id", "")),
                "rep_glyph_hash": str(cluster.get("rep_glyph_hash", "")),
                "member_rows": int(cluster.get("member_rows", 0) or 0),
                "hits_total": int(cluster.get("hits_total", 0) or 0),
                "near_members": int(cluster.get("near_members", 0) or 0),
                "exact_members": int(cluster.get("exact_members", 0) or 0),
                "members": members,
            }
        )
    clusters_out.sort(
        key=lambda c: (
            -int(c.get("member_rows", 0) or 0),
            -int(c.get("hits_total", 0) or 0),
            str(c.get("group_id", "")),
        )
    )
    return top_rows, clusters_out


def _write_csv(path: Path, rows: Iterable[Dict[str, Any]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _load_mapping_dict(mapping_path: Optional[Path]) -> Dict[str, str]:
    if mapping_path is None or not mapping_path.exists():
        return {}
    obj = _load_json_dict(mapping_path)
    raw_map = None
    if isinstance(obj.get("mappings"), dict):
        raw_map = obj.get("mappings")
    elif isinstance(obj.get("glyph_hash_to_char"), dict):
        raw_map = obj.get("glyph_hash_to_char")
    else:
        raw_map = obj

    resolved: Dict[str, str] = {}
    if not isinstance(raw_map, dict):
        return resolved
    for key, value in raw_map.items():
        glyph_hash = _normalize_hash(key)
        if not glyph_hash:
            continue
        if value is None:
            continue
        # Mantém whitespace válido (ex.: espaço), só descarta string vazia.
        ch = str(value)
        if len(ch) == 0:
            continue
        resolved[glyph_hash] = ch
    return resolved


def _parse_hash_list(raw: Any) -> List[str]:
    out: List[str] = []
    if isinstance(raw, list):
        for item in raw:
            h = _normalize_hash(item)
            if h:
                out.append(h)
    return out


def _build_seed_map_from_dyn_log(
    rows: List[Dict[str, Any]],
    *,
    min_samples: int = 3,
    min_confidence: float = 0.95,
    max_unmapped_ratio: float = 0.05,
    max_len_delta: int = 2,
) -> Tuple[Dict[str, str], Dict[str, Dict[str, int]]]:
    # Coleta só em linhas "confiáveis": pouca incerteza e alinhamento razoável.
    evidence: Dict[str, Counter[str]] = {}
    for row in rows:
        unmapped_ratio = _safe_float(row.get("unmapped_ratio"), default=1.0)
        if unmapped_ratio > float(max_unmapped_ratio):
            continue
        line = str(row.get("line", "") or "")
        glyph_hashes = _parse_hash_list(row.get("glyph_hashes", []))
        if not glyph_hashes:
            continue
        if abs(len(line) - len(glyph_hashes)) > int(max_len_delta):
            continue

        limit = min(len(line), len(glyph_hashes))
        for idx in range(limit):
            glyph_hash = glyph_hashes[idx]
            ch = line[idx]
            if ch == "?":
                continue
            bucket = evidence.setdefault(glyph_hash, Counter())
            bucket[ch] += 1

    seed_map: Dict[str, str] = {}
    conflicts: Dict[str, Dict[str, int]] = {}
    min_samples = max(1, int(min_samples))
    min_confidence = max(0.0, min(1.0, float(min_confidence)))

    for glyph_hash, counter in evidence.items():
        total = int(sum(counter.values()))
        if total < min_samples:
            continue
        best_char, best_hits = counter.most_common(1)[0]
        confidence = float(best_hits) / float(max(1, total))
        if confidence >= min_confidence:
            seed_map[glyph_hash] = best_char
            continue
        conflicts[glyph_hash] = dict(counter)

    return seed_map, conflicts


def _render_mapped_line(row: Dict[str, Any], glyph_map: Dict[str, str], seed_map: Dict[str, str]) -> str:
    line = str(row.get("line", "") or "")
    glyph_hashes = _parse_hash_list(row.get("glyph_hashes", []))
    if not glyph_hashes:
        return line

    target_len = min(len(line), len(glyph_hashes))
    if target_len <= 0:
        target_len = min(len(glyph_hashes), 32)

    chars: List[str] = []
    for idx in range(target_len):
        glyph_hash = glyph_hashes[idx]
        ch = glyph_map.get(glyph_hash)
        if ch is None:
            ch = seed_map.get(glyph_hash)
        if ch is None and idx < len(line):
            src_ch = line[idx]
            if src_ch != "?":
                ch = src_ch
        if ch is None:
            ch = "?"
        chars.append(ch)

    rendered = "".join(chars)
    return _sanitize_text(rendered)


def _aggregate_preview_unique_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    dedup: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        text = _sanitize_text(row.get("line_preview", ""))
        if not text:
            continue
        frame = int(parse_int(row.get("frame"), default=1 << 30) or (1 << 30))
        scene_hash = str(row.get("scene_hash", "") or "")
        hits = int(parse_int(row.get("hits"), default=1) or 1)
        unmapped_ratio = _safe_float(row.get("unmapped_ratio"), default=0.0)
        key = _normalize_text_key(text)

        slot = dedup.get(key)
        if slot is None:
            dedup[key] = {
                "text": text,
                "text_key": key,
                "first_frame": frame,
                "scene_hashes": [scene_hash] if scene_hash else [],
                "hits": max(1, hits),
                "unmapped_ratio_max": float(round(unmapped_ratio, 4)),
            }
            continue

        slot["hits"] = int(slot.get("hits", 0) or 0) + max(1, hits)
        if frame < int(slot.get("first_frame", frame) or frame):
            slot["first_frame"] = frame
        if scene_hash:
            hashes = list(slot.get("scene_hashes", []))
            if scene_hash not in hashes and len(hashes) < 12:
                hashes.append(scene_hash)
                slot["scene_hashes"] = hashes
        old_ratio = _safe_float(slot.get("unmapped_ratio_max"), default=0.0)
        if unmapped_ratio > old_ratio:
            slot["unmapped_ratio_max"] = float(round(unmapped_ratio, 4))

    unique_rows = list(dedup.values())
    unique_rows.sort(
        key=lambda r: (
            str(r.get("text_key", "")),
            int(parse_int(r.get("first_frame"), default=1 << 30) or (1 << 30)),
            str(",".join(r.get("scene_hashes", [])[:1])),
        )
    )
    return unique_rows


def _write_preview_text(path: Path, unique_rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    for row in unique_rows:
        scene_label = ",".join(str(s) for s in row.get("scene_hashes", [])[:3] if str(s))
        line = (
            f"{row.get('text', '')}\t"
            f"frame={int(parse_int(row.get('first_frame'), default=0) or 0)}\t"
            f"scene_hash={scene_label}\t"
            f"hits={int(parse_int(row.get('hits'), default=1) or 1)}\t"
            f"unmapped_ratio_max={float(_safe_float(row.get('unmapped_ratio_max'), 0.0)):.4f}"
        )
        lines.append(line)
    content = "\n".join(lines)
    if content and not content.endswith("\n"):
        content += "\n"
    path.write_text(content, encoding="utf-8")


def generate_round_artifacts(
    *,
    bootstrap_path: Path,
    dyn_unique_path: Optional[Path],
    dyn_log_path: Optional[Path],
    mapping_path: Optional[Path],
    out_dir: Optional[Path],
    top_n: int,
    template_top_n: int,
    max_hamming_bits: int,
) -> Dict[str, Any]:
    payload = load_bootstrap_rows(bootstrap_path)
    crc = str(payload.get("rom_crc32", "UNKNOWN000") or "UNKNOWN000").upper()
    rows = list(payload.get("rows", []))
    total_rows = len(rows)

    if out_dir is None:
        out_dir = bootstrap_path.parent
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if top_n <= 0:
        top_n = min(100, total_rows) if total_rows > 0 else 0
    top_n = min(max(0, int(top_n)), total_rows)
    if template_top_n <= 0:
        template_top_n = top_n if top_n > 0 else total_rows
    template_top_n = min(max(0, int(template_top_n)), total_rows)

    rows_top = rows[:top_n]
    rows_template = rows[:template_top_n]
    grouped_top_rows, grouped_summary = _cluster_rows_by_pattern(
        rows_top, max_hamming_bits=max(0, int(max_hamming_bits))
    )

    top_csv_path = out_dir / f"{crc}_dyn_fontmap_top{top_n}.csv"
    groups_csv_path = out_dir / f"{crc}_dyn_fontmap_groups_top{top_n}.csv"
    template_path = out_dir / f"{crc}_dyn_fontmap_round_template_top{template_top_n}.json"

    _write_csv(
        top_csv_path,
        grouped_top_rows,
        fieldnames=[
            "rank",
            "glyph_hash",
            "hits",
            "sample_context_1",
            "pattern_hex",
            "already_mapped",
            "group_id",
            "group_size",
            "group_match",
            "group_distance_bits",
            "group_similarity_pct",
            "group_representative",
        ],
    )
    _write_csv(
        groups_csv_path,
        grouped_summary,
        fieldnames=[
            "group_id",
            "rep_glyph_hash",
            "member_rows",
            "hits_total",
            "exact_members",
            "near_members",
            "members",
        ],
    )

    template_payload = {
        "rom_crc32": crc,
        "mappings": {str(r.get("glyph_hash", "")): "" for r in rows_template if r.get("glyph_hash")},
    }
    write_json(template_path, template_payload)

    manual_map = _load_mapping_dict(mapping_path)
    resolved_hashes = set(manual_map.keys())
    total_hits = int(sum(int(parse_int(r.get("hits"), default=0) or 0) for r in rows))
    unknown_total = int(payload.get("unknown_glyphs_total", total_rows) or total_rows)
    covered_hits = int(
        sum(
            int(parse_int(r.get("hits"), default=0) or 0)
            for r in rows
            if str(r.get("glyph_hash", "")) in resolved_hashes
        )
    )
    unresolved_count = max(0, unknown_total - len(resolved_hashes))
    covered_hits_pct = (
        (float(covered_hits) / float(max(1, total_hits))) * 100.0 if total_hits > 0 else 0.0
    )

    preview_path: Optional[Path] = None
    preview_rows_total = 0
    preview_unique_total = 0
    before_unknown_chars = 0
    after_unknown_chars = 0
    seed_map_count = 0
    seed_conflicts: Dict[str, Dict[str, int]] = {}

    effective_dyn_log: Optional[Path] = None
    if dyn_log_path is not None and dyn_log_path.exists():
        effective_dyn_log = dyn_log_path
    elif dyn_unique_path is not None:
        candidate = dyn_unique_path.parent / f"{crc}_dyn_text_log.jsonl"
        if candidate.exists():
            effective_dyn_log = candidate

    if effective_dyn_log is not None:
        dyn_rows: List[Dict[str, Any]] = []
        for obj in iter_jsonl(effective_dyn_log):
            if str(obj.get("type", "")).lower() == "meta":
                continue
            if str(obj.get("type", "")).lower() != "dyn_text":
                continue
            dyn_rows.append(dict(obj))

        seed_map, seed_conflicts = _build_seed_map_from_dyn_log(dyn_rows)
        seed_map_count = len(seed_map)

        rendered_rows: List[Dict[str, Any]] = []
        for row in dyn_rows:
            base_line = str(row.get("line", "") or "")
            before_unknown_chars += base_line.count("?")
            mapped_line = _render_mapped_line(row, glyph_map=manual_map, seed_map=seed_map)
            after_unknown_chars += mapped_line.count("?")
            row_new = dict(row)
            row_new["line_preview"] = mapped_line
            row_new["hits"] = int(parse_int(row.get("hits"), default=1) or 1)
            rendered_rows.append(row_new)

        preview_unique = _aggregate_preview_unique_rows(rendered_rows)
        preview_rows_total = len(rendered_rows)
        preview_unique_total = len(preview_unique)
        preview_path = out_dir / f"{crc}_dyn_text_unique_preview.txt"
        _write_preview_text(preview_path, preview_unique)

    improvement_pct = 0.0
    if before_unknown_chars > 0:
        improvement_pct = (
            (float(before_unknown_chars - after_unknown_chars) / float(before_unknown_chars)) * 100.0
        )
    improvement_pct = _format_pct(improvement_pct)

    report = {
        "schema": "runtime_dyn_fontmap_rounds.v1",
        "rom_crc32": crc,
        "rom_size": int(parse_int(payload.get("rom_size"), default=0) or 0),
        "bootstrap_path": str(bootstrap_path),
        "dyn_unique_input_path": str(dyn_unique_path) if dyn_unique_path else None,
        "dyn_log_input_path": str(effective_dyn_log) if effective_dyn_log else None,
        "mapping_input_path": str(mapping_path) if mapping_path else None,
        "top_n": int(top_n),
        "template_top_n": int(template_top_n),
        "max_hamming_bits": int(max_hamming_bits),
        "unknown_glyphs_total": int(unknown_total),
        "rows_in_bootstrap": int(total_rows),
        "resolved_glyphs_by_mapping": int(len(resolved_hashes)),
        "unresolved_glyphs": int(unresolved_count),
        "coverage_hits_total": int(total_hits),
        "coverage_hits_mapped": int(covered_hits),
        "coverage_hits_percent": _format_pct(covered_hits_pct),
        "coverage_hits_scope": "bootstrap_rows_only",
        "seed_map_count_from_dyn_log": int(seed_map_count),
        "seed_map_conflicts": seed_conflicts,
        "preview_rows_total": int(preview_rows_total),
        "preview_unique_rows_total": int(preview_unique_total),
        "preview_unknown_chars_before": int(before_unknown_chars),
        "preview_unknown_chars_after": int(after_unknown_chars),
        "preview_unknown_reduction_percent": float(improvement_pct),
        "top_csv_path": str(top_csv_path),
        "groups_csv_path": str(groups_csv_path),
        "template_mapping_path": str(template_path),
        "preview_output_path": str(preview_path) if preview_path else None,
    }
    report_path = out_dir / f"{crc}_dyn_fontmap_round_report.json"
    write_json(report_path, report)
    report["report_path"] = str(report_path)

    _log(f"CSV top glyphs: {top_csv_path}")
    _log(f"CSV grupos: {groups_csv_path}")
    _log(f"Template mapeamento: {template_path}")
    if preview_path:
        _log(f"Preview gerado: {preview_path}")
    else:
        _log("Preview não gerado (dyn_text_log indisponível).")
    _log(
        "Cobertura por hits dos glyphs mapeados: "
        f"{covered_hits}/{total_hits} ({_format_pct(covered_hits_pct):.2f}%)"
    )
    _log(
        "Progresso glyphs: "
        f"resolvidos={len(resolved_hashes)} | faltando={unresolved_count} | total={unknown_total}"
    )
    if before_unknown_chars > 0:
        _log(
            "Redução estimada de '?' no preview: "
            f"{before_unknown_chars}->{after_unknown_chars} ({improvement_pct:.2f}%)"
        )

    return report


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gera artefatos para acelerar mapeamento manual de glyphs runtime-dyn."
    )
    parser.add_argument(
        "--bootstrap",
        required=True,
        help="Caminho para {CRC}_dyn_fontmap_bootstrap.json",
    )
    parser.add_argument(
        "--dyn-unique",
        default="",
        help="Caminho para {CRC}_dyn_text_unique.txt (opcional; usado para inferir dyn_log).",
    )
    parser.add_argument(
        "--dyn-log",
        default="",
        help="Caminho para {CRC}_dyn_text_log.jsonl (opcional, recomendado para preview).",
    )
    parser.add_argument(
        "--mapping-json",
        default="",
        help=(
            "Arquivo de mapeamento preenchido manualmente. "
            "Aceita {'mappings': {...}}, {'glyph_hash_to_char': {...}} ou mapa direto."
        ),
    )
    parser.add_argument(
        "--out-dir",
        default="",
        help="Pasta de saída dos artefatos (padrão: pasta do bootstrap).",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=100,
        help="Quantidade de glyphs de maior impacto para CSV/grupos.",
    )
    parser.add_argument(
        "--template-top-n",
        type=int,
        default=100,
        help="Quantidade de glyphs incluídos no template JSON.",
    )
    parser.add_argument(
        "--max-hamming-bits",
        type=int,
        default=24,
        help="Distância máxima de Hamming (bits) para considerar patterns como variantes.",
    )
    return parser


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()

    bootstrap_path = Path(args.bootstrap).expanduser().resolve()
    dyn_unique_path = Path(args.dyn_unique).expanduser().resolve() if args.dyn_unique else None
    dyn_log_path = Path(args.dyn_log).expanduser().resolve() if args.dyn_log else None
    mapping_path = Path(args.mapping_json).expanduser().resolve() if args.mapping_json else None
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else None

    report = generate_round_artifacts(
        bootstrap_path=bootstrap_path,
        dyn_unique_path=dyn_unique_path,
        dyn_log_path=dyn_log_path,
        mapping_path=mapping_path,
        out_dir=out_dir,
        top_n=int(args.top_n),
        template_top_n=int(args.template_top_n),
        max_hamming_bits=int(args.max_hamming_bits),
    )
    _log(f"Relatório final: {report.get('report_path')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
