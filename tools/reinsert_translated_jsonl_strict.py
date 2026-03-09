#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reinsercao estrita a partir de {CRC32}_translated_fixed_ptbr.jsonl.

Objetivos:
- Validacao forte de rom_crc32/rom_size (hard-fail por padrao)
- Ordenacao deterministica por seq (fallback offset)
- Aplicacao somente in-place (sem realocacao) para manter ROM intocada fora dos blocos alvo
- Sem truncar por padrao; truncamento apenas opcional e como ultimo recurso
- Gera report/proof com evidencias claras
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


PLACEHOLDER_RE = re.compile(r"(\[[^\]]+\]|\{[^}]+\}|<[^>]+>|@[A-Z0-9_]+|__[^_]+__)")
PT_HINTS = {
    "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas",
    "para", "por", "com", "sem", "que", "e", "ou", "se", "mas", "nao",
    "sim", "voce", "voces", "seu", "sua", "meu", "minha", "um", "uma",
    "ataque", "inimigo", "inimigos", "mundo", "tempo", "nome", "item",
    "opcao", "opcoes", "salvar", "carregar", "continuar",
}
EN_HINTS = {
    "the", "and", "you", "your", "this", "that", "from", "with", "attack",
    "enemy", "enemies", "item", "world", "time", "name", "male", "female",
    "options", "option", "save", "load", "continue",
}
WORD_RE = re.compile(r"[A-Za-z']+")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def parse_int_maybe(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        if s.startswith("@"):
            s = s[1:]
        try:
            if s.lower().startswith("0x"):
                return int(s, 16)
            if re.fullmatch(r"[0-9A-Fa-f]+", s):
                return int(s, 16)
            return int(s, 10)
        except Exception:
            return None
    return None


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def crc32_hex(data: bytes) -> str:
    return f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"


def is_ascii_strict(s: str) -> bool:
    try:
        s.encode("ascii", errors="strict")
        return True
    except UnicodeEncodeError:
        return False


def normalize_ascii_loose(text: str) -> str:
    t = unicodedata.normalize("NFD", text or "")
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    t = (
        t.replace("“", "\"")
        .replace("”", "\"")
        .replace("‘", "'")
        .replace("’", "'")
        .replace("—", "-")
        .replace("–", "-")
        .replace("…", "...")
    )
    t = t.encode("ascii", errors="ignore").decode("ascii", errors="ignore")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def compact_to_budget_no_truncate(text: str, budget: int, src_for_tokens: str) -> str:
    """
    Tenta reduzir texto para caber no budget SEM truncar bytes.
    Se nao couber, retorna o texto original.
    """
    if budget <= 0:
        return text
    out = text or ""
    if len(out.encode("ascii", errors="ignore")) <= budget:
        return out

    repl = [
        (r"\bpara\b", "p/"),
        (r"\bcom\b", "c/"),
        (r"\bvoce\b", "vc"),
        (r"\bvoces\b", "vcs"),
        (r"\bque\b", "q"),
        (r"\bnao\b", "n"),
        (r"\btodos\b", "tds"),
        (r"\binimigos\b", "inims"),
    ]
    for pat, rep in repl:
        out2 = re.sub(pat, rep, out, flags=re.IGNORECASE)
        out2 = re.sub(r"\s+", " ", out2).strip()
        if out2 == out:
            continue
        if not placeholders_preserved(src_for_tokens, out2):
            continue
        out = out2
        if len(out.encode("ascii", errors="ignore")) <= budget:
            return out

    filler_words = r"\b(o|a|os|as|um|uma|de|do|da|dos|das)\b"
    attempts = 0
    while len(out.encode("ascii", errors="ignore")) > budget and attempts < 16:
        attempts += 1
        out2 = re.sub(filler_words, " ", out, count=1, flags=re.IGNORECASE)
        out2 = re.sub(r"\s+", " ", out2).strip()
        if out2 == out or not placeholders_preserved(src_for_tokens, out2):
            break
        out = out2
        if len(out.encode("ascii", errors="ignore")) <= budget:
            return out

    # Encurta palavras longas sem truncar string inteira.
    def _shrink_long_word(match: re.Match) -> str:
        word = match.group(0)
        low = word.lower()
        fixed = {
            "attack": "atk",
            "enemy": "inim",
            "enemies": "inims",
            "options": "opcs",
            "option": "opc",
            "continue": "cont",
            "personal": "pessoal",
            "crises": "crises",
            "warming": "quente",
        }
        if low in fixed:
            return fixed[low]
        base = word[0] + re.sub(r"[aeiouAEIOU]", "", word[1:])
        if len(base) < 3:
            return word[:3]
        return base

    out2 = re.sub(r"\b[A-Za-z]{6,}\b", _shrink_long_word, out)
    out2 = re.sub(r"\s+", " ", out2).strip()
    if out2 != out and placeholders_preserved(src_for_tokens, out2):
        out = out2
        if len(out.encode("ascii", errors="ignore")) <= budget:
            return out

    # Ajustes finos para casos 1-3 bytes acima do budget.
    out2 = re.sub(r"[.,;:!?]+$", "", out).strip()
    if out2 != out and placeholders_preserved(src_for_tokens, out2):
        out = out2
        if len(out.encode("ascii", errors="ignore")) <= budget:
            return out

    def _drop_one_char_non_token(text_in: str) -> str:
        matches = list(re.finditer(r"\b[A-Za-z]{4,}\b", text_in))
        matches.sort(key=lambda m: len(m.group(0)), reverse=True)
        for m in matches:
            word = m.group(0)
            for i in range(1, len(word)):
                if word[i].lower() in "aeiou":
                    nw = word[:i] + word[i + 1 :]
                    return text_in[: m.start()] + nw + text_in[m.end() :]
        # Fallback: remove um espaco interno.
        pos = text_in.rfind(" ")
        if pos > 0:
            return text_in[:pos] + text_in[pos + 1 :]
        return text_in

    tries = 0
    while len(out.encode("ascii", errors="ignore")) > budget and tries < 12:
        tries += 1
        out2 = _drop_one_char_non_token(out)
        out2 = re.sub(r"\s+", " ", out2).strip()
        if out2 == out or not placeholders_preserved(src_for_tokens, out2):
            break
        out = out2
        if len(out.encode("ascii", errors="ignore")) <= budget:
            return out

    return text


def placeholders_preserved(src: str, dst: str) -> bool:
    src_tokens = PLACEHOLDER_RE.findall(src or "")
    return all(tok in (dst or "") for tok in src_tokens)


def looks_suspicious_non_pt(text: str) -> bool:
    words = [w.lower() for w in WORD_RE.findall(text or "")]
    if len(words) < 2:
        return False
    pt_hits = sum(1 for w in words if w in PT_HINTS)
    en_hits = sum(1 for w in words if w in EN_HINTS)
    return pt_hits == 0 and en_hits >= 1


def clean_text_for_gate(text: str) -> str:
    t = PLACEHOLDER_RE.sub(" ", text or "")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def is_translatable_candidate(src: str) -> bool:
    """
    Heuristica conservadora: considera candidato apenas texto com sinais
    claros de linguagem natural (evita contar lixo codificado como "nao traduzido").
    """
    t = clean_text_for_gate(src)
    if len(t) < 4 or len(t) > 140:
        return False
    try:
        b = t.encode("ascii", errors="strict")
    except UnicodeEncodeError:
        return False
    printable = sum(32 <= x < 127 for x in b) / max(1, len(b))
    if printable < 0.95:
        return False

    nonalnum = sum(
        1
        for ch in t
        if not (ch.isalnum() or ch.isspace() or ch in "'.,!?-:")
    )
    if nonalnum / max(1, len(t)) > 0.20:
        return False
    digit_ratio = sum(ch.isdigit() for ch in t) / max(1, len(t))
    if digit_ratio > 0.20:
        return False

    words = [w.lower() for w in WORD_RE.findall(t)]
    if len(words) < 2:
        return False
    long_words = [w for w in words if len(w) >= 3]
    if len(long_words) < 2:
        return False
    letters = sum(ch.isalpha() for ch in t)
    if letters < 4:
        return False

    en_hits = sum(1 for w in words if w in EN_HINTS)
    if en_hits < 1:
        return False
    if (en_hits / max(1, len(words))) < 0.20 and not any(
        w in {"attack", "enemy", "enemies", "world", "time", "name", "male", "female", "options", "item", "you", "your"}
        for w in words
    ):
        return False
    return True


def normalize_entry(raw: Dict[str, Any], idx: int) -> Dict[str, Any]:
    seq = parse_int_maybe(raw.get("seq"))
    off = parse_int_maybe(raw.get("rom_offset"))
    if off is None:
        off = parse_int_maybe(raw.get("offset"))

    return {
        "raw": raw,
        "id": raw.get("id", idx),
        "seq": seq if seq is not None else idx,
        "offset": off,
        "max_len_bytes": parse_int_maybe(raw.get("max_len_bytes")),
        "terminator": parse_int_maybe(raw.get("terminator")),
        "encoding": str(raw.get("encoding", "")),
        "text_src": str(raw.get("text_src", "")),
        "text_dst": str(raw.get("text_dst", raw.get("text_src", ""))),
        "translation_status": str(raw.get("translation_status", "")),
        "rom_crc32": str(raw.get("rom_crc32", "")).upper() if raw.get("rom_crc32") else None,
        "rom_size": parse_int_maybe(raw.get("rom_size")),
    }


def sort_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(entries, key=lambda it: (int(it.get("seq", 0)), int(it.get("offset") or -1)))


def ensure_out_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_report(path: Path, lines: List[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Reinsercao estrita por JSONL traduzido.")
    ap.add_argument("--rom", required=True, help="ROM original")
    ap.add_argument("--translated-jsonl", required=True, help="{CRC32}_translated_fixed_ptbr.jsonl")
    ap.add_argument("--out-dir", required=True, help="Pasta de saida (ex.: 3_reinsercao)")
    ap.add_argument("--output-rom", default=None, help="Nome/caminho da ROM de saida (opcional)")
    ap.add_argument(
        "--allow-missing-meta",
        action="store_true",
        help="Permite JSONL sem header/meta (nao recomendado)",
    )
    ap.add_argument(
        "--allow-last-resort-truncate",
        action="store_true",
        help="Permite truncar apenas como ultimo recurso",
    )
    ap.add_argument(
        "--apply-unchanged",
        action="store_true",
        help="Aplica tambem itens sem alteracao text_dst==text_src",
    )
    args = ap.parse_args()

    rom_path = Path(args.rom).expanduser().resolve()
    trans_path = Path(args.translated_jsonl).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    ensure_out_dir(out_dir)

    if not rom_path.exists():
        raise SystemExit(f"[ERRO] ROM nao encontrada: {rom_path}")
    if not trans_path.exists():
        raise SystemExit(f"[ERRO] JSONL traduzido nao encontrado: {trans_path}")

    rom = bytearray(rom_path.read_bytes())
    runtime_crc = crc32_hex(bytes(rom))
    runtime_size = len(rom)

    meta: Dict[str, Any] = {}
    raw_entries: List[Dict[str, Any]] = []
    for obj in iter_jsonl(trans_path):
        if obj.get("type") == "meta":
            meta = dict(obj)
            continue
        raw_entries.append(obj)

    declared_crc = str(meta.get("rom_crc32", "")).upper() if meta.get("rom_crc32") else None
    declared_size = parse_int_maybe(meta.get("rom_size"))
    crc_match = (declared_crc == runtime_crc) if declared_crc else False
    size_match = (declared_size == runtime_size) if declared_size is not None else False
    has_meta = bool(meta)

    if not has_meta and not args.allow_missing_meta:
        raise SystemExit(
            "[FAIL] JSONL sem meta/header. Use arquivo traduzido com rom_crc32/rom_size."
        )
    if has_meta and (not crc_match or not size_match):
        raise SystemExit(
            "[FAIL] JSONL pertence a outra ROM "
            f"(declared_crc32={declared_crc}, declared_size={declared_size}, "
            f"runtime_crc32={runtime_crc}, runtime_size={runtime_size})."
        )

    entries = [normalize_entry(e, i) for i, e in enumerate(raw_entries)]
    entries = sort_entries(entries)

    offsets = [int(e["offset"]) for e in entries if isinstance(e.get("offset"), int)]
    is_sorted_by_offset = offsets == sorted(offsets)
    first_10 = [
        {"seq": int(e.get("seq", 0)), "offset": f"0x{int(e['offset']):06X}"}
        for e in entries[:10]
        if isinstance(e.get("offset"), int)
    ]
    last_10 = [
        {"seq": int(e.get("seq", 0)), "offset": f"0x{int(e['offset']):06X}"}
        for e in entries[-10:]
        if isinstance(e.get("offset"), int)
    ]

    metrics = {
        "items_total": len(entries),
        "items_considered": 0,
        "translatable_candidates_total": 0,
        "non_translatable_skipped": 0,
        "applied": 0,
        "unchanged_equal_src": 0,
        "not_translated_count": 0,
        "suspicious_non_pt": 0,
        "rom_vs_translated_mismatch": 0,
        "placeholder_fail": 0,
        "terminator_missing": 0,
        "truncated": 0,
        "blocked_too_long": 0,
        "blocked_non_ascii": 0,
        "blocked_oob": 0,
        "blocked_no_budget": 0,
        "skipped_non_ascii_encoding": 0,
        "skipped_missing_fields": 0,
        "auto_normalized_ascii": 0,
        "auto_compacted_to_fit": 0,
    }

    examples: Dict[str, List[Dict[str, Any]]] = {
        "applied": [],
        "blocked": [],
        "unchanged": [],
        "suspicious_non_pt": [],
    }
    proof_entries: List[Dict[str, Any]] = []

    for e in entries:
        enc = str(e.get("encoding", "")).lower()
        if "ascii" not in enc:
            metrics["skipped_non_ascii_encoding"] += 1
            continue

        off = e.get("offset")
        max_len = e.get("max_len_bytes")
        if not isinstance(off, int) or not isinstance(max_len, int) or max_len <= 0:
            metrics["skipped_missing_fields"] += 1
            continue

        src = str(e.get("text_src", ""))
        dst = str(e.get("text_dst", src))
        dst_norm = normalize_ascii_loose(dst)
        if dst_norm != dst:
            metrics["auto_normalized_ascii"] += 1
            dst = dst_norm
        is_candidate = is_translatable_candidate(src)
        if is_candidate:
            metrics["translatable_candidates_total"] += 1

        # Nao penaliza como "nao traduzido" itens sem sinais de texto natural,
        # mesmo quando houve normalizacao ASCII no text_dst.
        if (not is_candidate) and (not args.apply_unchanged):
            metrics["non_translatable_skipped"] += 1
            continue

        metrics["items_considered"] += 1

        # Item-level mismatch declarado no JSONL.
        item_crc = e.get("rom_crc32")
        item_size = e.get("rom_size")
        if item_crc and item_crc != runtime_crc:
            metrics["rom_vs_translated_mismatch"] += 1
            metrics["blocked_oob"] += 0
            if len(examples["blocked"]) < 20:
                examples["blocked"].append(
                    {"id": e["id"], "seq": e["seq"], "offset": f"0x{off:06X}", "reason": "ITEM_CRC_MISMATCH"}
                )
            continue
        if item_size is not None and item_size != runtime_size:
            metrics["rom_vs_translated_mismatch"] += 1
            if len(examples["blocked"]) < 20:
                examples["blocked"].append(
                    {"id": e["id"], "seq": e["seq"], "offset": f"0x{off:06X}", "reason": "ITEM_SIZE_MISMATCH"}
                )
            continue

        if dst == src:
            if is_candidate:
                metrics["unchanged_equal_src"] += 1
                metrics["not_translated_count"] += 1
            if not args.apply_unchanged:
                if len(examples["unchanged"]) < 20:
                    examples["unchanged"].append(
                        {"id": e["id"], "seq": e["seq"], "offset": f"0x{off:06X}", "text": src[:80]}
                    )
                continue

        if is_candidate and looks_suspicious_non_pt(dst):
            metrics["suspicious_non_pt"] += 1
            if len(examples["suspicious_non_pt"]) < 20:
                examples["suspicious_non_pt"].append(
                    {"id": e["id"], "seq": e["seq"], "offset": f"0x{off:06X}", "text_dst": dst[:80]}
                )

        if not placeholders_preserved(src, dst):
            metrics["placeholder_fail"] += 1
            if len(examples["blocked"]) < 20:
                examples["blocked"].append(
                    {"id": e["id"], "seq": e["seq"], "offset": f"0x{off:06X}", "reason": "PLACEHOLDER_FAIL"}
                )
            continue

        if not is_ascii_strict(dst):
            metrics["blocked_non_ascii"] += 1
            if len(examples["blocked"]) < 20:
                examples["blocked"].append(
                    {"id": e["id"], "seq": e["seq"], "offset": f"0x{off:06X}", "reason": "NON_ASCII"}
                )
            continue

        term = e.get("terminator")
        reserve = 1 if isinstance(term, int) else 0
        budget = max_len - reserve
        if budget < 0:
            metrics["blocked_no_budget"] += 1
            if len(examples["blocked"]) < 20:
                examples["blocked"].append(
                    {"id": e["id"], "seq": e["seq"], "offset": f"0x{off:06X}", "reason": "INVALID_BUDGET"}
                )
            continue

        payload = dst.encode("ascii", errors="strict")
        if len(payload) > budget:
            compacted = compact_to_budget_no_truncate(dst, budget, src_for_tokens=src)
            if compacted != dst:
                dst = compacted
                metrics["auto_compacted_to_fit"] += 1
                payload = dst.encode("ascii", errors="strict")
        if len(payload) > budget:
            if args.allow_last_resort_truncate and not PLACEHOLDER_RE.search(dst):
                payload = payload[:budget]
                metrics["truncated"] += 1
            else:
                metrics["blocked_too_long"] += 1
                if len(examples["blocked"]) < 20:
                    examples["blocked"].append(
                        {
                            "id": e["id"],
                            "seq": e["seq"],
                            "offset": f"0x{off:06X}",
                            "reason": "TOO_LONG",
                            "payload_len": len(payload),
                            "budget": budget,
                        }
                    )
                continue

        if off < 0 or (off + max_len) > runtime_size:
            metrics["blocked_oob"] += 1
            if len(examples["blocked"]) < 20:
                examples["blocked"].append(
                    {"id": e["id"], "seq": e["seq"], "offset": f"0x{off:06X}", "reason": "OOB"}
                )
            continue

        before = bytes(rom[off:off + max_len])
        pad = (term & 0xFF) if isinstance(term, int) else 0x00
        for i in range(max_len):
            rom[off + i] = pad
        rom[off:off + len(payload)] = payload

        if isinstance(term, int):
            if len(payload) >= max_len:
                metrics["terminator_missing"] += 1
                rom[off:off + max_len] = before
                if len(examples["blocked"]) < 20:
                    examples["blocked"].append(
                        {"id": e["id"], "seq": e["seq"], "offset": f"0x{off:06X}", "reason": "NO_TERM_SPACE"}
                    )
                continue
            rom[off + len(payload)] = term & 0xFF

        after = bytes(rom[off:off + max_len])
        metrics["applied"] += 1
        proof_entry = {
            "id": e["id"],
            "seq": e["seq"],
            "offset": f"0x{off:06X}",
            "max_len_bytes": max_len,
            "before_sha256": sha256_hex(before),
            "after_sha256": sha256_hex(after),
            "payload_len": len(payload),
        }
        proof_entries.append(proof_entry)
        if len(examples["applied"]) < 20:
            examples["applied"].append(proof_entry)

    # Saida ROM.
    out_rom = Path(args.output_rom).expanduser().resolve() if args.output_rom else (
        out_dir / f"{rom_path.stem}_STRICT_TRANSLATED{rom_path.suffix}"
    )
    out_rom.write_bytes(bytes(rom))
    out_crc = crc32_hex(bytes(rom))

    # Evidence coverage.
    coverage = {
        "min_offset": min(offsets) if offsets else None,
        "max_offset": max(offsets) if offsets else None,
        "items_total": len(entries),
        "count_offsets_below_0x10000": sum(1 for x in offsets if x < 0x10000),
        "first_20_items_summary": [
            {"seq": int(e.get("seq", 0)), "offset": f"0x{int(e['offset']):06X}", "src": str(e.get("text_src", ""))[:36]}
            for e in entries[:20]
            if isinstance(e.get("offset"), int)
        ],
    }

    proof = {
        "generated_at": utc_now(),
        "translation_input": str(trans_path),
        "rom_input": str(rom_path),
        "rom_output": str(out_rom),
        "input_crc32": runtime_crc,
        "output_crc32": out_crc,
        "rom_size": runtime_size,
        "input_match_check": {
            "meta_present": has_meta,
            "rom_crc32_match": bool(crc_match),
            "rom_size_match": bool(size_match),
            "jsonl_declared_crc32": declared_crc,
            "jsonl_declared_size": declared_size,
            "runtime_crc32": runtime_crc,
            "runtime_size": runtime_size,
        },
        "ordering_check": {
            "is_sorted_by_offset": bool(is_sorted_by_offset),
            "first_10_offsets": first_10,
            "last_10_offsets": last_10,
        },
        "coverage_check": coverage,
        "metrics": metrics,
        "examples": examples,
        "proof_entries": proof_entries[:1000],
    }

    base = runtime_crc
    proof_path = out_dir / f"{base}_strict_reinsert_proof.json"
    report_path = out_dir / f"{base}_strict_reinsert_report.txt"
    proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "STRICT REINSERT REPORT",
        f"generated_at={proof['generated_at']}",
        f"translation_input={trans_path}",
        f"rom_input={rom_path}",
        f"rom_output={out_rom}",
        f"input_crc32={runtime_crc}",
        f"output_crc32={out_crc}",
        f"rom_size={runtime_size}",
        "",
        "INPUT_MATCH_CHECK:",
        f"  meta_present={has_meta}",
        f"  rom_crc32_match={crc_match}",
        f"  rom_size_match={size_match}",
        f"  jsonl_declared_crc32={declared_crc}",
        f"  jsonl_declared_size={declared_size}",
        "",
        "ORDERING_CHECK:",
        f"  is_sorted_by_offset={is_sorted_by_offset}",
        "",
        "COVERAGE_CHECK:",
        f"  min_offset={coverage['min_offset']}",
        f"  max_offset={coverage['max_offset']}",
        f"  items_total={coverage['items_total']}",
        f"  count_offsets_below_0x10000={coverage['count_offsets_below_0x10000']}",
        "",
        "METRICS:",
    ]
    for k, v in metrics.items():
        lines.append(f"  {k}={v}")
    lines.append("")
    lines.append("OBS:")
    if coverage["count_offsets_below_0x10000"] == 0:
        lines.append("  intro possivelmente nao extraido/mapeado (evidencia: offsets baixos ausentes).")
    lines.append("  reinsercao in-place estrita; sem realocacao de ponteiros neste modo.")
    write_report(report_path, lines)

    print(f"[OK] output_rom={out_rom}")
    print(f"[OK] report={report_path}")
    print(f"[OK] proof={proof_path}")
    print(
        "[OK] applied={applied} blocked={blocked} unchanged={unchanged}".format(
            applied=metrics["applied"],
            blocked=(
                metrics["blocked_too_long"]
                + metrics["blocked_non_ascii"]
                + metrics["blocked_oob"]
                + metrics["blocked_no_budget"]
                + metrics["placeholder_fail"]
                + metrics["terminator_missing"]
            ),
            unchanged=metrics["unchanged_equal_src"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
