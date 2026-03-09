#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Traduz e aplica somente candidatos de {CRC32}_decoded_candidates.jsonl
sobre {CRC32}_translated_fixed_ptbr.jsonl (ou pure_text como fallback).

Foco:
- patch incremental e seguro
- validacao estrita de tamanho/tokens
- sem alterar linhas fora da lista de candidatos
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


TOKEN_RE = re.compile(r"(\[[^\]]+\]|\{[^}]+\}|<[^>]+>|__PROTECTED__|@[A-Z0-9_]+)")

# Corretor ortografico (saida ASCII para reinsercao).
ORTHO_WORD_REPLACEMENTS = [
    (r"(?<![A-Za-z0-9])vc(?![A-Za-z0-9])", "voce"),
    (r"(?<![A-Za-z0-9])vcs(?![A-Za-z0-9])", "voces"),
    (r"(?<![A-Za-z0-9])p/(?![A-Za-z0-9])", "para"),
    (r"(?<![A-Za-z0-9])c/(?![A-Za-z0-9])", "com"),
    (r"(?<![A-Za-z0-9])q(?![A-Za-z0-9])", "que"),
    (r"(?<![A-Za-z0-9])atq(?![A-Za-z0-9])", "ataque"),
    (r"(?<![A-Za-z0-9])atk(?![A-Za-z0-9])", "ataque"),
    (r"(?<![A-Za-z0-9])tds(?![A-Za-z0-9])", "todos"),
    (r"(?<![A-Za-z0-9])inims(?![A-Za-z0-9])", "inimigos"),
    (r"(?<![A-Za-z0-9])mnstrs(?![A-Za-z0-9])", "monstros"),
    (r"(?<![A-Za-z0-9])pssvl(?![A-Za-z0-9])", "possivel"),
    (r"(?<![A-Za-z0-9])dscnsr(?![A-Za-z0-9])", "descansar"),
    (r"(?<![A-Za-z0-9])cmd(?![A-Za-z0-9])", "comida"),
    (r"(?<![A-Za-z0-9])prxms(?![A-Za-z0-9])", "proximos"),
    (r"(?<![A-Za-z0-9])mostros(?![A-Za-z0-9])", "monstros"),
    (r"(?<![A-Za-z0-9])acentudado(?![A-Za-z0-9])", "acentuado"),
    (r"(?<![A-Za-z0-9])acentudada(?![A-Za-z0-9])", "acentuada"),
]

ORTHO_PHRASE_REPLACEMENTS = [
    (r"\bseus\s+pessoas\b", "suas pessoas"),
    (r"\bseu\s+pessoas\b", "suas pessoas"),
    (r"\bnossos\s+pessoas\b", "nossas pessoas"),
    (r"\bnosso\s+pessoas\b", "nossas pessoas"),
    (r"\bseus\s+moedas\b", "suas moedas"),
    (r"\bseu\s+moeda\b", "sua moeda"),
    (r"\bseus\s+moeda\b", "sua moeda"),
    (r"\balgum\s+pessoas\b", "algumas pessoas"),
    (r"\bum\s+pessoas\b", "umas pessoas"),
    (r"\besta\s+pessoas\b", "estas pessoas"),
]

# Regras de acentuacao apenas para PREVIEW humano (nao reinserido na ROM).
PREVIEW_ACCENT_WORD_REPLACEMENTS = [
    ("voce", "você"),
    ("voces", "vocês"),
    ("nao", "não"),
    ("tambem", "também"),
    ("sera", "será"),
    ("serao", "serão"),
    ("esta", "está"),
    ("estao", "estão"),
    ("sao", "são"),
    ("ate", "até"),
    ("ja", "já"),
    ("so", "só"),
    ("possivel", "possível"),
    ("lingua", "língua"),
    ("acentuacao", "acentuação"),
    ("maca", "maçã"),
    ("lagrima", "lágrima"),
    ("lagrimas", "lágrimas"),
    ("premio", "prêmio"),
    ("sequencia", "sequência"),
    ("desnecessaria", "desnecessária"),
]


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


def normalize_ascii(text: str) -> str:
    t = unicodedata.normalize("NFD", text or "")
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    t = (
        t.replace("\u201c", "\"")
        .replace("\u201d", "\"")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2026", "...")
    )
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _apply_ortho_word_rules_ascii(text: str) -> str:
    out = normalize_ascii(text or "")
    for pattern, repl in ORTHO_WORD_REPLACEMENTS:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _apply_ortho_phrase_rules_ascii(text: str) -> str:
    out = text or ""
    for pattern, repl in ORTHO_PHRASE_REPLACEMENTS:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def apply_orthographic_cleanup_ascii(text: str) -> str:
    out = _apply_ortho_word_rules_ascii(text or "")
    out = _apply_ortho_phrase_rules_ascii(out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _replace_word_keep_case(text: str, src_word: str, dst_word: str) -> str:
    pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(src_word)}(?![A-Za-z0-9])", re.IGNORECASE)

    def _repl(match: re.Match) -> str:
        cur = match.group(0)
        if cur.isupper():
            return dst_word.upper()
        if cur[:1].isupper():
            return dst_word[:1].upper() + dst_word[1:]
        return dst_word

    return pattern.sub(_repl, text)


def to_preview_ptbr(text_ascii: str) -> str:
    """
    Gera versao com acentos para leitura humana em preview.
    A saida para reinsercao continua ASCII.
    """
    out = apply_orthographic_cleanup_ascii(text_ascii or "")
    for src_word, dst_word in PREVIEW_ACCENT_WORD_REPLACEMENTS:
        out = _replace_word_keep_case(out, src_word, dst_word)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def can_fit(text: str, max_len_bytes: Optional[int]) -> bool:
    if max_len_bytes is None:
        return True
    try:
        b = (text or "").encode("ascii", errors="strict")
    except UnicodeEncodeError:
        return False
    return len(b) <= int(max_len_bytes)


def compact_to_fit(text: str, max_len_bytes: Optional[int]) -> str:
    if max_len_bytes is None:
        return text
    t = text
    if can_fit(t, max_len_bytes):
        return t
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
        t2 = re.sub(pat, rep, t, flags=re.IGNORECASE)
        t2 = re.sub(r"\s+", " ", t2).strip()
        if t2 != t:
            t = t2
            if can_fit(t, max_len_bytes):
                return t
    if not TOKEN_RE.search(t):
        raw = t.encode("ascii", errors="ignore")
        if len(raw) > int(max_len_bytes):
            raw = raw[: int(max_len_bytes)]
        t = raw.decode("ascii", errors="ignore").strip()
    return t


def ollama_translate_batch(
    pairs: List[Tuple[int, str]],
    model: str,
    timeout: int,
) -> Dict[int, str]:
    prompt_lines = [f"{i}|||{txt}" for i, txt in pairs]
    prompt = (
        "Traduza fragmentos de texto de jogo do ingles para portugues brasileiro (ASCII, sem acentos).\n"
        "Regras obrigatorias:\n"
        "- Nao invente contexto.\n"
        "- Nao acrescente palavras que nao existem no trecho fonte.\n"
        "- Mantenha a ordem aproximada dos termos.\n"
        "- Se o trecho for ruido/codigo e nao der para traduzir com seguranca, retorne exatamente o texto original.\n"
        "- Retorne somente linhas no formato id|||traducao.\n"
        "- Nao adicione explicacoes.\n\n"
        + "\n".join(prompt_lines)
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }
    r = requests.post(
        "http://127.0.0.1:11434/api/generate",
        json=payload,
        timeout=timeout,
    )
    r.raise_for_status()
    out = str(r.json().get("response", "") or "")

    results: Dict[int, str] = {}
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln or "|||" not in ln:
            continue
        a, b = ln.split("|||", 1)
        a = a.strip()
        b = b.strip()
        if not a.isdigit():
            continue
        results[int(a)] = b
    return results


def load_candidates(path: Path) -> List[Dict[str, Any]]:
    rows = [r for r in iter_jsonl(path)]
    rows.sort(
        key=lambda r: (
            int(r.get("score", 0)),
            int(r.get("seq", 0) or 0),
        ),
        reverse=True,
    )
    return rows


def build_preview_rows(
    candidates: List[Dict[str, Any]],
    seg_to_pt: Dict[str, str],
    max_rows: int = 300,
) -> List[Dict[str, Any]]:
    """
    Gera prévia legível de traduções por segmento decodificado.
    Não altera reinserção; serve como evidência/QA humano.
    """
    out: List[Dict[str, Any]] = []
    seen = set()
    for c in candidates:
        seg = str(c.get("segment_en", "")).strip()
        if not seg:
            continue
        pt_ascii = apply_orthographic_cleanup_ascii(seg_to_pt.get(seg, seg))
        pt_preview = to_preview_ptbr(pt_ascii)
        key = (seg.lower(), pt_ascii.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "seq": c.get("seq"),
                "rom_offset": c.get("rom_offset"),
                "score": c.get("score"),
                "segment_en": seg,
                "segment_pt_ascii": pt_ascii,
                "segment_pt": pt_preview,
            }
        )
        if len(out) >= max_rows:
            break
    return out


def write_preview_files(
    out_jsonl: Path,
    preview_rows: List[Dict[str, Any]],
) -> Tuple[Path, Path]:
    preview_json = out_jsonl.with_name(out_jsonl.stem + "_decoded_preview.json")
    preview_txt = out_jsonl.with_name(out_jsonl.stem + "_decoded_preview.txt")

    preview_json.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "items_total": len(preview_rows),
                "items": preview_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        "DECODED CANDIDATES PREVIEW (PT-BR)",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
        f"items_total={len(preview_rows)}",
        "",
    ]
    for row in preview_rows:
        seq = row.get("seq")
        off = row.get("rom_offset")
        score = row.get("score")
        lines.append(f"[seq={seq} off={off} score={score}]")
        lines.append(f"EN: {row.get('segment_en', '')}")
        lines.append(f"PT: {row.get('segment_pt', '')}")
        lines.append(f"PT_ASCII: {row.get('segment_pt_ascii', '')}")
        lines.append("")
    preview_txt.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return preview_json, preview_txt


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch traduzido por decoded_candidates.")
    parser.add_argument("--in-jsonl", required=True, help="Base JSONL (translated_fixed ou pure_text)")
    parser.add_argument("--candidates-jsonl", required=True, help="Arquivo decoded_candidates")
    parser.add_argument("--out-jsonl", required=True, help="Saida patched")
    parser.add_argument("--model", default="llama3.2:latest")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()

    in_jsonl = Path(args.in_jsonl).expanduser().resolve()
    cand_jsonl = Path(args.candidates_jsonl).expanduser().resolve()
    out_jsonl = Path(args.out_jsonl).expanduser().resolve()

    if not in_jsonl.exists():
        raise SystemExit(f"[ERRO] in-jsonl nao encontrado: {in_jsonl}")
    if not cand_jsonl.exists():
        raise SystemExit(f"[ERRO] candidates-jsonl nao encontrado: {cand_jsonl}")

    # Carrega base em memoria (preserva ordem).
    base_rows: List[Dict[str, Any]] = []
    meta_row: Optional[Dict[str, Any]] = None
    by_seq: Dict[int, Dict[str, Any]] = {}
    for obj in iter_jsonl(in_jsonl):
        if obj.get("type") == "meta":
            meta_row = dict(obj)
            continue
        row = dict(obj)
        base_rows.append(row)
        seq = row.get("seq")
        if isinstance(seq, int):
            by_seq[seq] = row

    cands = load_candidates(cand_jsonl)
    if not cands:
        # Sem candidatos, apenas reescreve.
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with out_jsonl.open("w", encoding="utf-8", newline="\n") as f:
            if meta_row:
                f.write(json.dumps(meta_row, ensure_ascii=False) + "\n")
            for r in base_rows:
                if "text_dst" not in r:
                    r["text_dst"] = r.get("text_src", "")
                    r["translation_status"] = "UNCHANGED"
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"[OK] no-candidates -> {out_jsonl}")
        return 0

    # Traducoes unicas por segmento.
    unique_segments: List[str] = []
    seen = set()
    for c in cands:
        seg = str(c.get("segment_en", "")).strip()
        if not seg:
            continue
        if seg not in seen:
            seen.add(seg)
            unique_segments.append(seg)

    seg_to_pt: Dict[str, str] = {}
    for i in range(0, len(unique_segments), max(1, args.batch_size)):
        batch = unique_segments[i : i + max(1, args.batch_size)]
        pairs = [(i + j, txt) for j, txt in enumerate(batch)]
        try:
            got = ollama_translate_batch(pairs, model=args.model, timeout=int(args.timeout))
        except Exception:
            for _, txt in pairs:
                seg_to_pt[txt] = txt
            continue
        for rid, txt in pairs:
            tr = normalize_ascii(got.get(rid, txt))
            tr = apply_orthographic_cleanup_ascii(tr)
            if not tr:
                tr = txt
            seg_to_pt[txt] = tr

    preview_rows = build_preview_rows(cands, seg_to_pt)
    preview_json_path, preview_txt_path = write_preview_files(
        out_jsonl=out_jsonl,
        preview_rows=preview_rows,
    )
    translated_segments_total = sum(
        1
        for seg in unique_segments
        if normalize_ascii(seg_to_pt.get(seg, seg)).strip().lower()
        != normalize_ascii(seg).strip().lower()
    )

    changed = 0
    blocked = 0
    skipped_non_ascii_source = 0
    patched_seq = set()

    for c in cands:
        seq = c.get("seq")
        if not isinstance(seq, int):
            continue
        row = by_seq.get(seq)
        if not row:
            continue
        if seq in patched_seq:
            continue

        src = str(row.get("text_src", ""))
        seg = str(c.get("segment_en", "")).strip()
        if not seg or seg not in src:
            continue

        # Seguranca: nao toca linhas que tenham bytes/simbolos nao-ASCII fora do trecho.
        # Evita corromper representacoes proprietarias.
        src_ascii_probe = src.replace("🇯🇵", "").strip()
        if any(ord(ch) > 127 for ch in src_ascii_probe):
            skipped_non_ascii_source += 1
            continue

        tr_seg = seg_to_pt.get(seg, seg)
        tr_seg = apply_orthographic_cleanup_ascii(tr_seg)
        trial = src.replace(seg, tr_seg, 1)

        max_len = row.get("max_len_bytes")
        if isinstance(max_len, str) and max_len.isdigit():
            max_len = int(max_len)
        if not isinstance(max_len, int):
            max_len = None

        trial = compact_to_fit(trial, max_len)
        if not can_fit(trial, max_len):
            blocked += 1
            continue

        # Preserva placeholders.
        src_tokens = TOKEN_RE.findall(src)
        if not all(tok in trial for tok in src_tokens):
            blocked += 1
            continue

        if trial != src:
            row["text_dst"] = trial
            row["translation_status"] = "OK"
            row.pop("translation_block_reason", None)
            changed += 1
            patched_seq.add(seq)

    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl.open("w", encoding="utf-8", newline="\n") as f:
        if meta_row:
            meta = dict(meta_row)
            meta["stage"] = "decoded_candidates_patch"
            meta["generated_at"] = datetime.now().isoformat(timespec="seconds")
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")
        for r in base_rows:
            if "text_dst" not in r:
                r["text_dst"] = r.get("text_src", "")
                r["translation_status"] = "UNCHANGED"
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    report_path = out_jsonl.with_name(out_jsonl.stem + "_patch_report.txt")
    report = [
        "DECODED CANDIDATES PATCH",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
        f"in_jsonl={in_jsonl}",
        f"candidates_jsonl={cand_jsonl}",
        f"out_jsonl={out_jsonl}",
        f"candidates_total={len(cands)}",
        f"unique_segments={len(unique_segments)}",
        f"translated_segments_total={translated_segments_total}",
        f"preview_items_total={len(preview_rows)}",
        f"patched_changed={changed}",
        f"patched_blocked={blocked}",
        f"skipped_non_ascii_source={skipped_non_ascii_source}",
        f"preview_json={preview_json_path}",
        f"preview_txt={preview_txt_path}",
    ]
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"[OK] out={out_jsonl}")
    print(f"[OK] changed={changed} blocked={blocked}")
    print(f"[OK] report={report_path}")
    print(f"[OK] preview_json={preview_json_path}")
    print(f"[OK] preview_txt={preview_txt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
