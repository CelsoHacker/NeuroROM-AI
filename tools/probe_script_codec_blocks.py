#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Probe tecnico de script/codec sobre {CRC32}_pure_text.jsonl.

Saidas:
- {CRC32}_codec_probe_report.txt
- {CRC32}_codec_probe_proof.json
- {CRC32}_decoded_candidates.jsonl

Objetivo:
- medir cobertura de texto natural (traduzivel) vs script/codigo
- listar candidatos decodificaveis com evidencia
- orientar proxima etapa de engenharia por console/CRC
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from codec_family_decoders import (
    SegmentResult,
    build_decoder_for_input,
    get_decoder_for_console,
    infer_console_hint,
)

# Mantido em escapes unicode para preservar arquivo ASCII.
ICON_RE = re.compile(r"[\U0001F3AE\U0001F50D\U0001F1EF\U0001F1F5]")
HEX_TOKEN_RE = re.compile(r"\[[0-9A-Fa-f]{2}\]")
CTRL_TAG_RE = re.compile(
    r"\[(CMD:[^\]]+|SPEED|WAIT_[^\]]+|NEWLINE|SCROLL|CHOOSE\d*|END|ADDR:[^\]]+|PTR:[^\]]+|Block[^\]]+|[A-Z_]{2,})\]"
)
WORD_RE = re.compile(r"[A-Za-z']+")
SENT_RE = re.compile(r"[A-Za-z][A-Za-z' ,.!?-]{8,}")
CRC_RE = re.compile(r"([0-9A-Fa-f]{8})")

# Dicionario enxuto de ingles comum em textos de jogo.
EN_WORDS = set(
    """
the and you your to of in is for with this that from are can be not all one more into over then them if her their
was were will no yes my our out up down just back attack enemy enemies item use name male female world time day warm
breeze personal crisis another options option save load continue start strange lamp houses
""".split()
)

EN_STRONG = set(
    """
attack enemy enemies options option save load continue start world time name male female
strange lamp houses personal crisis warm breeze another
""".split()
)


def iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def infer_crc_from_jsonl_path(path: Path) -> Optional[str]:
    m = CRC_RE.search(path.name)
    if m:
        return str(m.group(1)).upper()
    return None


def infer_rom_size_from_manifest(pure_jsonl: Path) -> Optional[int]:
    try:
        crc_dir = pure_jsonl.parent.parent
        manifest = crc_dir / "crc_bootstrap_manifest.json"
        if manifest.exists():
            obj = json.loads(manifest.read_text(encoding="utf-8", errors="replace"))
            if isinstance(obj, dict):
                val = obj.get("rom_size")
                if isinstance(val, int):
                    return int(val)
                if isinstance(val, float):
                    return int(val)
                if isinstance(val, str) and val.strip().isdigit():
                    return int(val.strip())
    except Exception:
        return None
    return None


def _nearest_visible_char(s: str, start: int, step: int) -> str:
    i = start
    while 0 <= i < len(s):
        ch = s[i]
        if ch not in "[]":
            return ch
        i += step
    return ""


def derive_space_tokens(records: List[Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, float]], List[str]]:
    """
    Deriva tokens [XX] que se comportam como separador entre palavras.
    """
    stats: Dict[str, Dict[str, float]] = {}

    for obj in records:
        src = str(obj.get("text_src", ""))
        for m in HEX_TOKEN_RE.finditer(src):
            tok = m.group(0).upper()
            d = stats.setdefault(
                tok,
                {"total": 0.0, "between_alpha": 0.0, "around_space": 0.0},
            )
            d["total"] += 1.0
            left = _nearest_visible_char(src, m.start() - 1, -1)
            right = _nearest_visible_char(src, m.end(), +1)
            if left.isalpha() and right.isalpha():
                d["between_alpha"] += 1.0
            if left == " " or right == " ":
                d["around_space"] += 1.0

    selected: List[str] = []
    for tok, d in stats.items():
        total = d["total"]
        if total < 200:
            continue
        ba_ratio = d["between_alpha"] / total
        asp_ratio = d["around_space"] / total
        if ba_ratio >= 0.50 or (ba_ratio >= 0.35 and asp_ratio >= 0.20):
            selected.append(tok)

    selected.sort(
        key=lambda t: (
            -(stats[t]["between_alpha"] / max(1.0, stats[t]["total"])),
            -stats[t]["total"],
        )
    )

    # Limite para evitar overfit agressivo.
    selected = selected[:20]

    # Enriquecer stats com razoes.
    for tok, d in stats.items():
        total = max(1.0, d["total"])
        d["between_alpha_ratio"] = d["between_alpha"] / total
        d["around_space_ratio"] = d["around_space"] / total

    return stats, selected


def clean_for_probe(text: str) -> str:
    t = ICON_RE.sub(" ", text or "")
    t = CTRL_TAG_RE.sub(" ", t)
    t = HEX_TOKEN_RE.sub(" ", t)
    t = t.replace("_", " ")
    t = re.sub(r"[^\x20-\x7E|]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def segment_score(seg: str) -> Tuple[int, Dict[str, Any]]:
    words = [w.lower() for w in WORD_RE.findall(seg or "")]
    if len(words) < 2:
        return -1, {"words": words}

    recognized = sum(1 for w in words if w in EN_WORDS)
    strong = sum(1 for w in words if w in EN_STRONG)
    ratio = recognized / max(1, len(words))

    details = {
        "words_count": len(words),
        "recognized": recognized,
        "strong": strong,
        "recognized_ratio": ratio,
        "length": len(seg),
        "digit_ratio": sum(ch.isdigit() for ch in seg) / max(1, len(seg)),
        "upper_ratio": sum(ch.isupper() for ch in seg) / max(1, sum(ch.isalpha() for ch in seg)),
    }

    if len(seg) < 8 or len(seg) > 120:
        return -1, details
    if details["digit_ratio"] > 0.08:
        return -1, details
    if details["upper_ratio"] > 0.45:
        return -1, details
    if recognized < 2:
        return -1, details
    if ratio < 0.50:
        return -1, details
    if strong < 1:
        return -1, details

    score = recognized * 2 + strong * 3 - int((1.0 - ratio) * len(words))
    return score, details


def decode_candidates(
    base_records: List[Dict[str, Any]],
    decoder,
    space_tokens: List[str],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for obj in base_records:
        src = str(obj.get("text_src", ""))
        best: Optional[SegmentResult] = decoder.decode_best(src, list(space_tokens))
        if best is None:
            continue
        out.append(
            {
                "id": obj.get("id"),
                "seq": obj.get("seq"),
                "rom_offset": obj.get("rom_offset"),
                "text_src": src,
                "segment_en": best.segment_en,
                "score": best.score,
                "details": best.details,
                "cleaned": best.cleaned,
                "decoder_family": decoder.name,
            }
        )
    return out


def collect_unresolved_tokens(
    base_records: List[Dict[str, Any]],
    space_tokens: List[str],
    limit: int = 40,
) -> List[Dict[str, Any]]:
    """Lista tokens alfabéticos suspeitos para orientar engenharia de codec."""
    counter: Counter[str] = Counter()
    for obj in base_records:
        src = str(obj.get("text_src", ""))
        cleaned = src
        for tok in space_tokens:
            cleaned = cleaned.replace(tok, " ")
        cleaned = clean_for_probe(cleaned)
        if not cleaned:
            continue
        for tk in re.findall(r"\b[A-Za-z]{3,}\b", cleaned):
            low = tk.lower()
            if low in EN_WORDS:
                continue
            # Ignora sequências gritantes de ruído em caixa alta.
            if tk.isupper() and len(tk) >= 4:
                continue
            counter[low] += 1
    return [{"token": tok, "count": int(cnt)} for tok, cnt in counter.most_common(limit)]


def extract_best_segment(src: str) -> Optional[Dict[str, Any]]:
    return extract_best_segment_with_map(src, set())


def extract_best_segment_with_map(src: str, space_tokens: set[str]) -> Optional[Dict[str, Any]]:
    cleaned_src = src or ""
    for tok in space_tokens:
        cleaned_src = cleaned_src.replace(tok, " ")

    cleaned = clean_for_probe(cleaned_src)
    if not cleaned:
        return None

    candidates: List[str] = []
    candidates.extend([p.strip() for p in cleaned.split("|") if p.strip()])
    candidates.extend([m.group(0).strip() for m in SENT_RE.finditer(cleaned)])

    best: Optional[Dict[str, Any]] = None
    for seg in candidates:
        score, details = segment_score(seg)
        if score < 7:
            continue
        row = {
            "segment_en": seg,
            "score": int(score),
            "details": details,
            "cleaned": cleaned,
        }
        if best is None or row["score"] > best["score"]:
            best = row
    return best


def build_probe(pure_jsonl: Path) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    fallback_crc: Optional[str] = None
    fallback_size: Optional[int] = None
    ctrl_counter: Counter[str] = Counter()
    hex_counter: int = 0
    with_ctrl: int = 0
    with_non_ascii: int = 0
    items_total: int = 0
    candidates: List[Dict[str, Any]] = []
    base_records: List[Dict[str, Any]] = []
    console_hint = infer_console_hint(str(pure_jsonl))

    for obj in iter_jsonl(pure_jsonl):
        if obj.get("type") == "meta":
            meta = obj
            continue

        items_total += 1
        if fallback_crc is None and obj.get("rom_crc32"):
            fallback_crc = str(obj.get("rom_crc32")).upper()
        if fallback_size is None and obj.get("rom_size") is not None:
            try:
                fallback_size = int(obj.get("rom_size"))
            except Exception:
                fallback_size = None
        src = str(obj.get("text_src", ""))
        seq = obj.get("seq")
        off = obj.get("rom_offset")
        base_records.append({"seq": seq, "rom_offset": off, "text_src": src, "id": obj.get("id")})

        ctrl_hits = CTRL_TAG_RE.findall(src)
        if ctrl_hits:
            with_ctrl += 1
            for tag in ctrl_hits:
                ctrl_counter[str(tag)] += 1

        hx = HEX_TOKEN_RE.findall(src)
        if hx:
            hex_counter += len(hx)

        if any(ord(ch) > 127 for ch in src):
            with_non_ascii += 1

    token_stats, derived_space_tokens = derive_space_tokens(base_records)
    rom_crc32 = (
        str(meta.get("rom_crc32") or "").upper()
        or fallback_crc
        or infer_crc_from_jsonl_path(pure_jsonl)
        or None
    )
    rom_size = meta.get("rom_size")
    if rom_size is None:
        rom_size = fallback_size
    if rom_size is None:
        rom_size = infer_rom_size_from_manifest(pure_jsonl)

    baseline_decoder = get_decoder_for_console(console_hint, profile=None)
    baseline_candidates = decode_candidates(
        base_records=base_records,
        decoder=baseline_decoder,
        space_tokens=list(derived_space_tokens),
    )

    profile_decoder, profile_obj = build_decoder_for_input(
        pure_jsonl_path=str(pure_jsonl),
        console_hint=console_hint,
        rom_crc32=rom_crc32,
    )
    profile_candidates = decode_candidates(
        base_records=base_records,
        decoder=profile_decoder,
        space_tokens=list(derived_space_tokens),
    )

    profile_loaded = bool(profile_obj)
    profile_gain = int(len(profile_candidates) - len(baseline_candidates))
    profile_applied = bool(profile_loaded and profile_gain >= 0)

    if profile_applied:
        decoder = profile_decoder
        candidates = profile_candidates
    else:
        decoder = baseline_decoder
        candidates = baseline_candidates

    top_ctrl = [{"tag": k, "count": int(v)} for k, v in ctrl_counter.most_common(20)]
    candidate_ratio = (len(candidates) / items_total) if items_total else 0.0
    unresolved_tokens_top = collect_unresolved_tokens(
        base_records=base_records,
        space_tokens=list(derived_space_tokens),
        limit=40,
    )

    if candidate_ratio >= 0.20:
        recommendation = "Alta cobertura textual; foco em traducao/reinsercao."
    elif candidate_ratio >= 0.05:
        recommendation = "Cobertura parcial; combinar traducao com engenharia de tabela/script."
    else:
        recommendation = (
            "Baixa cobertura textual; forte indicio de codec/script proprietario. "
            "Priorizar engenharia de decodificacao antes da traducao massiva."
        )

    profile_rules_total = 0
    profile_drop_words_total = 0
    profile_extra_fragments_total = 0
    profile_path = None
    if isinstance(profile_obj, dict):
        profile_rules_total = (
            len(profile_obj.get("replace_rules", []))
            if isinstance(profile_obj.get("replace_rules"), list)
            else 0
        )
        profile_drop_words_total = (
            len(profile_obj.get("drop_words", []))
            if isinstance(profile_obj.get("drop_words"), list)
            else 0
        )
        profile_extra_fragments_total = (
            len(profile_obj.get("extra_fragments", []))
            if isinstance(profile_obj.get("extra_fragments"), list)
            else 0
        )
        profile_path = profile_obj.get("_path")

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "console_hint": console_hint,
        "decoder_family": decoder.name,
        "rom_crc32": rom_crc32,
        "rom_size": rom_size,
        "input_pure_jsonl": str(pure_jsonl),
        "items_total": int(items_total),
        "items_with_ctrl_tags": int(with_ctrl),
        "items_with_non_ascii": int(with_non_ascii),
        "hex_token_total": int(hex_counter),
        "decoded_candidates_total": int(len(candidates)),
        "decoded_candidate_ratio": float(candidate_ratio),
        "decoded_candidates_baseline_total": int(len(baseline_candidates)),
        "decoded_candidates_profile_total": int(len(profile_candidates)),
        "decoded_candidates_profile_gain": int(profile_gain),
        "profile_loaded": bool(profile_loaded),
        "profile_applied": bool(profile_applied),
        "profile_path": profile_path,
        "profile_rules_total": int(profile_rules_total),
        "profile_drop_words_total": int(profile_drop_words_total),
        "profile_extra_fragments_total": int(profile_extra_fragments_total),
        "derived_space_tokens": derived_space_tokens,
        "derived_space_tokens_count": int(len(derived_space_tokens)),
        "derived_space_token_stats": {
            tok: {
                "total": int(token_stats[tok]["total"]),
                "between_alpha_ratio": round(float(token_stats[tok]["between_alpha_ratio"]), 6),
                "around_space_ratio": round(float(token_stats[tok]["around_space_ratio"]), 6),
            }
            for tok in derived_space_tokens
        },
        "top_control_tags": top_ctrl,
        "unresolved_tokens_top": unresolved_tokens_top,
        "recommendation": recommendation,
        "decoded_candidates_preview": candidates[:30],
        "decoded_candidates": candidates,
    }


def write_outputs(payload: Dict[str, Any], out_dir: Path) -> None:
    crc = str(payload.get("rom_crc32") or "UNKNOWN").upper()
    report_path = out_dir / f"{crc}_codec_probe_report.txt"
    proof_path = out_dir / f"{crc}_codec_probe_proof.json"
    cand_path = out_dir / f"{crc}_decoded_candidates.jsonl"
    map_path = out_dir / f"{crc}_codec_token_map.json"

    out_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "CODEC/SCRIPT PROBE",
        f"generated_at={payload['generated_at']}",
        f"rom_crc32={payload.get('rom_crc32')}",
        f"rom_size={payload.get('rom_size')}",
        f"console_hint={payload.get('console_hint')}",
        f"decoder_family={payload.get('decoder_family')}",
        f"profile_loaded={payload.get('profile_loaded')}",
        f"profile_applied={payload.get('profile_applied')}",
        f"profile_path={payload.get('profile_path')}",
        f"profile_rules_total={payload.get('profile_rules_total')}",
        f"profile_drop_words_total={payload.get('profile_drop_words_total')}",
        f"profile_extra_fragments_total={payload.get('profile_extra_fragments_total')}",
        f"input_pure_jsonl={payload.get('input_pure_jsonl')}",
        "",
        "METRICS:",
        f"  items_total={payload['items_total']}",
        f"  items_with_ctrl_tags={payload['items_with_ctrl_tags']}",
        f"  items_with_non_ascii={payload['items_with_non_ascii']}",
        f"  hex_token_total={payload['hex_token_total']}",
        f"  decoded_candidates_baseline_total={payload['decoded_candidates_baseline_total']}",
        f"  decoded_candidates_profile_total={payload['decoded_candidates_profile_total']}",
        f"  decoded_candidates_profile_gain={payload['decoded_candidates_profile_gain']}",
        f"  decoded_candidates_total={payload['decoded_candidates_total']}",
        f"  decoded_candidate_ratio={payload['decoded_candidate_ratio']:.6f}",
        f"  derived_space_tokens_count={payload['derived_space_tokens_count']}",
        "",
        "TOP_CONTROL_TAGS:",
    ]
    for row in payload["top_control_tags"]:
        lines.append(f"  {row['tag']}={row['count']}")
    lines.extend(
        [
            "",
            "UNRESOLVED_TOKENS_TOP:",
        ]
    )
    for row in payload.get("unresolved_tokens_top", [])[:20]:
        lines.append(f"  {row.get('token')}={row.get('count')}")
    lines.extend(
        [
            "",
            "RECOMMENDATION:",
            f"  {payload['recommendation']}",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    proof_obj = dict(payload)
    proof_obj.pop("decoded_candidates", None)
    proof_path.write_text(json.dumps(proof_obj, ensure_ascii=False, indent=2), encoding="utf-8")

    with cand_path.open("w", encoding="utf-8", newline="\n") as f:
        for row in payload["decoded_candidates"]:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    token_map = {
        "generated_at": payload.get("generated_at"),
        "console_hint": payload.get("console_hint"),
        "decoder_family": payload.get("decoder_family"),
        "profile_loaded": payload.get("profile_loaded"),
        "profile_applied": payload.get("profile_applied"),
        "profile_path": payload.get("profile_path"),
        "rom_crc32": payload.get("rom_crc32"),
        "rom_size": payload.get("rom_size"),
        "space_tokens": payload.get("derived_space_tokens", []),
        "space_token_stats": payload.get("derived_space_token_stats", {}),
        "unresolved_tokens_top": payload.get("unresolved_tokens_top", []),
    }
    map_path.write_text(json.dumps(token_map, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] Report: {report_path}")
    print(f"[OK] Proof: {proof_path}")
    print(f"[OK] Candidates: {cand_path}")
    print(f"[OK] Token map: {map_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe de engenharia para detectar script/codec proprietario em pure_text.jsonl."
    )
    parser.add_argument("--pure-jsonl", required=True, help="Arquivo {CRC32}_pure_text.jsonl")
    parser.add_argument("--out-dir", required=True, help="Diretorio de saida")
    args = parser.parse_args()

    pure_jsonl = Path(args.pure_jsonl).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()

    if not pure_jsonl.exists():
        raise SystemExit(f"[ERRO] pure_jsonl nao encontrado: {pure_jsonl}")

    payload = build_probe(pure_jsonl)
    write_outputs(payload, out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
