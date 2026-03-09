#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
romtxt_pipeline_v1.py

Pipeline V1 (NES/SMS/MD/SNES) — modo seguro e auditável:
1) audit     -> lê ROM + {CRC32}_pure_text.jsonl e gera:
               {CRC32}_report.txt, {CRC32}_proof.json, {CRC32}_reinsertion_mapping.json
2) translate -> traduz itens do mapping (japonês->pt) com NLLB/M2M100 (opcional)
3) reinsert  -> reinserção estrita (byte-length/terminador/placeholders) usando mapping

REGRAS:
- NÃO faz scan cego: só processa offsets vindos do JSONL/mapping.
- Neutralidade: logs e outputs referenciam apenas CRC32 e ROM_SIZE.
- V1 seguro: reinserção automática limitada a ASCII estrito (sem tabelas .tbl).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sys
import unicodedata
import zlib
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ---------------------------
# Utilidades base
# ---------------------------

def read_file_bytes(path: str) -> bytes:
    """Lê arquivo binário inteiro."""
    with open(path, "rb") as f:
        return f.read()

def crc32_hex(data: bytes) -> str:
    """CRC32 em HEX (8 chars) em uppercase."""
    return f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"

def sha256_hex(data: bytes) -> str:
    """SHA256 em HEX."""
    return hashlib.sha256(data).hexdigest()

def safe_mkdir(path: str) -> None:
    """Cria diretório se não existir."""
    os.makedirs(path, exist_ok=True)

def iter_jsonl(path: str) -> Iterable[Dict[str, Any]]:
    """Itera linhas JSON de um JSONL."""
    with open(path, "r", encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
                if isinstance(obj, dict):
                    yield obj
                else:
                    raise ValueError("linha não é objeto dict")
            except Exception as e:
                raise ValueError(f"JSONL inválido em {path}:{ln}: {e}") from e

def write_text(path: str, text: str) -> None:
    """Escreve texto UTF-8."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

def write_json(path: str, obj: Any) -> None:
    """Escreve JSON formatado."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def parse_int_maybe(x: Any) -> Optional[int]:
    """Aceita int, '0x..', '@000524', '524' etc."""
    if x is None:
        return None
    if isinstance(x, int):
        return x
    if isinstance(x, str):
        s = x.strip()
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


# ---------------------------
# Normalização do seu JSONL
# ---------------------------

def normalize_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normaliza um item do JSONL para o formato interno do mapping.

    Ajuste SOMENTE AQUI se seu JSONL usar chaves diferentes.
    """
    offset = (
        parse_int_maybe(raw.get("offset")) or
        parse_int_maybe(raw.get("ofs")) or
        parse_int_maybe(raw.get("start")) or
        parse_int_maybe(raw.get("addr"))
    )

    max_bytes = (
        parse_int_maybe(raw.get("max_bytes")) or
        parse_int_maybe(raw.get("max_len")) or
        parse_int_maybe(raw.get("length")) or
        parse_int_maybe(raw.get("size")) or
        parse_int_maybe(raw.get("byte_len"))
    )

    terminator = (
        parse_int_maybe(raw.get("terminator")) or
        parse_int_maybe(raw.get("term")) or
        parse_int_maybe(raw.get("end_byte"))
    )

    encoding = raw.get("encoding") or raw.get("enc") or raw.get("type") or "UNKNOWN"
    if isinstance(encoding, str):
        encoding = encoding.strip()

    text = raw.get("text")
    if text is None:
        text = raw.get("string")
    if text is None:
        text = raw.get("value")
    if text is None:
        text = ""

    if not isinstance(text, str):
        text = str(text)

    return {
        "offset": offset,
        "max_bytes": max_bytes,
        "terminator": terminator,
        "encoding": encoding,
        "orig_text": text,
    }


# ---------------------------
# Validações estritas
# ---------------------------

_PLACEHOLDER_RE = re.compile(
    r"(\{[^}]+\}|\[[^\]]+\]|<[^>]+>|@[A-Z0-9_]+|\\x[0-9A-Fa-f]{2})"
)

def protect_placeholders(s: str) -> Tuple[str, Dict[str, str]]:
    """Protege placeholders para não serem alterados na tradução."""
    mapping: Dict[str, str] = {}
    parts: List[str] = []
    idx = 0
    last = 0
    for m in _PLACEHOLDER_RE.finditer(s):
        parts.append(s[last:m.start()])
        key = f"__PH{idx}__"
        mapping[key] = m.group(0)
        parts.append(key)
        idx += 1
        last = m.end()
    parts.append(s[last:])
    return "".join(parts), mapping

def restore_placeholders(s: str, mapping: Dict[str, str]) -> str:
    """Restaura placeholders protegidos."""
    for k, v in mapping.items():
        s = s.replace(k, v)
    return s

def _normalize_whitespace(s: str) -> str:
    """Normaliza espaços e quebras de linha."""
    s = s.replace("\r", " ").replace("\n", " ")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)
    return s.strip()

def _sanitize_ascii(s: str) -> str:
    """Remove acentos e normaliza pontuação para ASCII estrito."""
    if not s:
        return s
    norm = unicodedata.normalize("NFD", s)
    norm = "".join(ch for ch in norm if unicodedata.category(ch) != "Mn")
    norm = (
        norm.replace("“", "\"")
        .replace("”", "\"")
        .replace("‘", "'")
        .replace("’", "'")
        .replace("—", "-")
        .replace("–", "-")
        .replace("…", "...")
    )
    return norm

def _split_by_placeholders(s: str) -> List[Tuple[bool, str]]:
    """Divide string em segmentos (token, texto)."""
    parts: List[Tuple[bool, str]] = []
    last = 0
    for m in _PLACEHOLDER_RE.finditer(s):
        if m.start() > last:
            parts.append((False, s[last:m.start()]))
        parts.append((True, m.group(0)))
        last = m.end()
    if last < len(s):
        parts.append((False, s[last:]))
    return parts

def _replace_ci(text: str, pattern: str, repl: str) -> str:
    """Replace case-insensitive preservando capitalização básica."""
    def _sub(m):
        src = m.group(0)
        if src.isupper():
            return repl.upper()
        if src[:1].isupper():
            return repl.capitalize()
        return repl
    return re.sub(pattern, _sub, text, flags=re.IGNORECASE)

def _apply_ptbr_shortening(s: str) -> str:
    """Encurtamento determinístico PT-BR (não mexe em tokens)."""
    if not s:
        return s
    rules = [
        (r"\bpor favor\b", "pf"),
        (r"\bporque\b", "pq"),
        (r"\bpor que\b", "pq"),
        (r"\bpara\b", "pra"),
        (r"\bvoce\b", "vc"),
        (r"\btambem\b", "tb"),
        (r"\bnumero\b", "num"),
        (r"\bquantidade\b", "qtde"),
    ]
    out: List[str] = []
    for is_token, seg in _split_by_placeholders(s):
        if is_token:
            out.append(seg)
            continue
        tmp = seg
        for pat, rep in rules:
            tmp = _replace_ci(tmp, pat, rep)
        out.append(tmp)
    return "".join(out)

def is_ascii_strict(s: str) -> bool:
    """True se todos os chars são ASCII (0..127)."""
    try:
        s.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False

def enforce_byte_limit_ascii(text: str, max_bytes: int, terminator: Optional[int]) -> Tuple[str, str]:
    """
    Garante que a string em ASCII caiba no campo (reservando 1 byte se houver terminador).
    Retorna (texto_final, status).
    """
    if max_bytes is None or max_bytes <= 0:
        return text, "SKIP_NO_MAXBYTES"

    reserve = 1 if terminator is not None else 0
    limit = max_bytes - reserve
    if limit < 0:
        return text, "FAIL_INVALID_MAXBYTES"

    if not is_ascii_strict(text):
        return text, "SKIP_NON_ASCII"

    b = text.encode("ascii")
    if len(b) <= limit:
        return text, "OK"

    t = re.sub(r"\s+", " ", text).strip()
    if len(t.encode("ascii")) <= limit:
        return t, "OK_TRIMMED"

    cut = t[:limit]
    cut = re.sub(r"__PH\d+_$", "", cut)
    if len(cut.encode("ascii")) <= limit:
        return cut, "OK_TRUNCATED"

    return text, "FAIL_TOO_LONG"

def _encoding_kind(enc: str) -> str:
    e = (enc or "").lower()
    if "tile" in e or "tbl" in e:
        return "tbl"
    return "ascii"

def _encode_for_length(text: str, enc_kind: str, tbl) -> Optional[bytes]:
    if enc_kind == "tbl":
        if tbl is not None:
            try:
                return tbl.encode_text(text)
            except Exception:
                return None
        # fallback ASCII se não houver TBL
    try:
        return text.encode("ascii")
    except UnicodeEncodeError:
        return None

def _encoded_len(text: str, enc_kind: str, tbl) -> Optional[int]:
    data = _encode_for_length(text, enc_kind, tbl)
    if data is None:
        return None
    return len(data)

def _fits_budget(text: str, limit: int, enc_kind: str, tbl) -> Tuple[bool, str, Optional[int]]:
    byte_len = _encoded_len(text, enc_kind, tbl)
    if byte_len is None:
        return False, "FAIL_ENCODING", None
    if byte_len <= limit:
        return True, "OK", byte_len
    return False, "FAIL_BUDGET", byte_len

def _trim_words_to_fit(text: str, limit: int, enc_kind: str, tbl) -> Optional[str]:
    parts = _split_by_placeholders(text)
    def build(p: List[Tuple[bool, str]]) -> str:
        return _normalize_whitespace("".join(seg for _, seg in p))
    for idx in range(len(parts) - 1, -1, -1):
        is_token, seg = parts[idx]
        if is_token:
            continue
        words = [w for w in seg.split(" ") if w != ""]
        while words:
            words.pop()
            parts[idx] = (False, " ".join(words))
            cand = build(parts)
            ok, _, _ = _fits_budget(cand, limit, enc_kind, tbl)
            if ok:
                return cand
        parts[idx] = (False, "")
        cand = build(parts)
        ok, _, _ = _fits_budget(cand, limit, enc_kind, tbl)
        if ok:
            return cand
    return None

def _shorten_to_budget(text: str, limit: int, enc_kind: str, tbl) -> Tuple[Optional[str], str]:
    base = _normalize_whitespace(text)
    ok, reason, _ = _fits_budget(base, limit, enc_kind, tbl)
    if ok:
        return base, "OK"
    if reason == "FAIL_ENCODING":
        return None, "FAIL_ENCODING"

    short1 = _normalize_whitespace(_apply_ptbr_shortening(base))
    ok, reason, _ = _fits_budget(short1, limit, enc_kind, tbl)
    if ok:
        return short1, "OK_SHORTENED"
    if reason == "FAIL_ENCODING":
        return None, "FAIL_ENCODING"

    short2 = re.sub(r"[\\s\\.!?]+$", "", short1).strip()
    if short2:
        ok, reason, _ = _fits_budget(short2, limit, enc_kind, tbl)
        if ok:
            return short2, "OK_SHORTENED"
        if reason == "FAIL_ENCODING":
            return None, "FAIL_ENCODING"

    trimmed = _trim_words_to_fit(short1, limit, enc_kind, tbl)
    if trimmed is not None:
        return trimmed, "OK_TRIMMED"

    return None, "FAIL_BUDGET"


# ---------------------------
# Auditoria / Exports
# ---------------------------

def cmd_audit(args: argparse.Namespace) -> int:
    rom = read_file_bytes(args.rom)
    rom_crc = crc32_hex(rom)
    rom_size = len(rom)

    print(f"[AUDIT] CRC32={rom_crc} ROM_SIZE={rom_size}")

    items_raw = list(iter_jsonl(args.jsonl))
    norm: List[Dict[str, Any]] = []
    issues: List[str] = []

    for i, raw in enumerate(items_raw, 1):
        it = normalize_item(raw)
        it["id"] = i

        if it["offset"] is None:
            it["status"] = "FAIL_NO_OFFSET"
            issues.append(f"id={i} sem offset")
        if it["max_bytes"] is None:
            it["status"] = it.get("status") or "WARN_NO_MAXBYTES"
            issues.append(f"id={i} sem max_bytes/length")
        if it["offset"] is not None and it["max_bytes"] is not None:
            if it["offset"] < 0 or it["offset"] + it["max_bytes"] > rom_size:
                it["status"] = "FAIL_OOB"
                issues.append(f"id={i} fora da ROM (offset+len)")
        norm.append(it)

    out_dir = args.out_dir or os.path.dirname(os.path.abspath(args.jsonl)) or "."
    safe_mkdir(out_dir)

    base = rom_crc
    report_path = os.path.join(out_dir, f"{base}_report.txt")
    proof_path = os.path.join(out_dir, f"{base}_proof.json")
    mapping_path = os.path.join(out_dir, f"{base}_reinsertion_mapping.json")

    lines = []
    lines.append("NEUROROM_AI V1 AUDIT REPORT")
    lines.append(f"CRC32={rom_crc}")
    lines.append(f"ROM_SIZE={rom_size}")
    lines.append(f"TOTAL_ITEMS={len(norm)}")
    lines.append("")
    lines.append("ISSUES:")
    if issues:
        lines.extend([f"- {x}" for x in issues[:200]])
        if len(issues) > 200:
            lines.append(f"- ... (mais {len(issues)-200})")
    else:
        lines.append("- (nenhum)")
    write_text(report_path, "\n".join(lines) + "\n")

    proof = {
        "created_at": _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "crc32": rom_crc,
        "rom_size": rom_size,
        "rom_sha256": sha256_hex(rom),
        "total_items": len(norm),
        "issues_count": len(issues),
        "items": [
            {
                "id": it["id"],
                "offset": it["offset"],
                "max_bytes": it["max_bytes"],
                "terminator": it["terminator"],
                "encoding": it["encoding"],
                "orig_preview": it["orig_text"][:120],
                "status": it.get("status", "OK_OR_UNCHECKED"),
            }
            for it in norm
        ],
    }
    write_json(proof_path, proof)

    mapping = {
        "crc32": rom_crc,
        "rom_size": rom_size,
        "created_at": proof["created_at"],
        "items": []
    }
    for it in norm:
        mapping["items"].append({
            "id": it["id"],
            "offset": it["offset"],
            "max_bytes": it["max_bytes"],
            "terminator": it["terminator"],
            "encoding": it["encoding"],
            "orig_text": it["orig_text"],
            "translated_text": "",
            "status": it.get("status", "PENDING"),
            "notes": "",
        })
    write_json(mapping_path, mapping)

    print(f"[OK] report: {report_path}")
    print(f"[OK] proof:  {proof_path}")
    print(f"[OK] map:    {mapping_path}")
    return 0


# ---------------------------
# Tradução (opcional)
# ---------------------------

def _resolve_tbl_path_for_crc(crc32: str, mapping: Dict[str, Any]) -> Optional[str]:
    """Tenta resolver caminho da TBL via mapping ou game_profiles_db.json."""
    tbl_path = mapping.get("tbl_path") or mapping.get("tbl")
    if isinstance(tbl_path, str) and tbl_path.strip():
        return tbl_path

    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "core", "game_profiles_db.json"))
    if not os.path.exists(db_path):
        return None
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data.get("games", []):
            if str(entry.get("crc32", "")).upper() == str(crc32).upper():
                tbl_path = entry.get("tbl_path")
                if not tbl_path:
                    return None
                return str(tbl_path)
    except Exception:
        return None
    return None

def _resolve_tbl_candidate(path_str: str) -> Optional[str]:
    """Resolve caminho relativo da TBL para path absoluto existente."""
    if not path_str:
        return None
    if os.path.isabs(path_str):
        return path_str if os.path.exists(path_str) else None
    project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cand = os.path.join(project_dir, path_str)
    if os.path.exists(cand):
        return cand
    return None

def _try_load_tbl_loader(tbl_path: Optional[str]):
    if not tbl_path:
        return None
    tbl_abs = _resolve_tbl_candidate(tbl_path)
    if not tbl_abs:
        return None
    try:
        from core.tbl_loader import TBLLoader  # type: ignore
    except Exception:
        try:
            sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
            from core.tbl_loader import TBLLoader  # type: ignore
        except Exception:
            return None
    try:
        return TBLLoader(str(tbl_abs))
    except Exception:
        return None

def _lazy_load_translator(model_name: str):
    """
    Carrega modelo de tradução via transformers.
    Modelos sugeridos:
      - facebook/nllb-200-distilled-600M
      - facebook/m2m100_418M
    """
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM  # type: ignore
    tok = AutoTokenizer.from_pretrained(model_name)
    mdl = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    return tok, mdl

def _translate_one(tok, mdl, text: str, model_name: str, gen_kwargs: Optional[Dict[str, Any]] = None) -> str:
    """Tradução JA->PT com configuração mínima e placeholders preservados."""
    protected, ph_map = protect_placeholders(text)
    gen_kwargs = dict(gen_kwargs or {})
    if "max_new_tokens" not in gen_kwargs:
        gen_kwargs["max_new_tokens"] = 256

    if "nllb" in model_name.lower():
        src = "jpn_Jpan"
        tgt = "por_Latn"
        if hasattr(tok, "src_lang"):
            tok.src_lang = src
        forced_id = None
        if hasattr(tok, "lang_code_to_id") and isinstance(tok.lang_code_to_id, dict):
            forced_id = tok.lang_code_to_id.get(tgt)
        inputs = tok(protected, return_tensors="pt", truncation=True)
        if forced_id is not None and "forced_bos_token_id" not in gen_kwargs:
            gen_kwargs["forced_bos_token_id"] = forced_id
        out = mdl.generate(**inputs, **gen_kwargs)
        decoded = tok.batch_decode(out, skip_special_tokens=True)[0]
        return restore_placeholders(decoded, ph_map).strip()

    if "m2m100" in model_name.lower():
        if hasattr(tok, "src_lang"):
            tok.src_lang = "ja"
        forced_id = None
        if hasattr(tok, "get_lang_id"):
            try:
                forced_id = tok.get_lang_id("pt")
            except Exception:
                forced_id = None
        inputs = tok(protected, return_tensors="pt", truncation=True)
        if forced_id is not None and "forced_bos_token_id" not in gen_kwargs:
            gen_kwargs["forced_bos_token_id"] = forced_id
        out = mdl.generate(**inputs, **gen_kwargs)
        decoded = tok.batch_decode(out, skip_special_tokens=True)[0]
        return restore_placeholders(decoded, ph_map).strip()

    inputs = tok(protected, return_tensors="pt", truncation=True)
    out = mdl.generate(**inputs, **gen_kwargs)
    decoded = tok.batch_decode(out, skip_special_tokens=True)[0]
    return restore_placeholders(decoded, ph_map).strip()

def cmd_translate(args: argparse.Namespace) -> int:
    mapping = json.loads(open(args.mapping, "r", encoding="utf-8").read())
    rom_crc = mapping.get("crc32", "UNKNOWN")
    rom_size = mapping.get("rom_size", "UNKNOWN")
    print(f"[TRANSLATE] CRC32={rom_crc} ROM_SIZE={rom_size}")

    model_name = args.model
    dry_run = bool(getattr(args, "dry_run", False))
    tok = mdl = None
    if not dry_run:
        tok, mdl = _lazy_load_translator(model_name)

    tbl_loader = _try_load_tbl_loader(_resolve_tbl_path_for_crc(str(rom_crc), mapping))
    max_tries = max(1, int(os.environ.get("NEUROROM_BUDGET_TRIES", "4") or 4))
    base_max_tokens = max(32, int(os.environ.get("NEUROROM_TRANSLATE_MAX_NEW_TOKENS", "256") or 256))

    def _gen_kwargs_for_attempt(attempt: int) -> Dict[str, Any]:
        max_new = max(32, int(base_max_tokens * (0.75 ** attempt)))
        length_penalty = max(0.5, 0.9 - (0.1 * attempt))
        return {"max_new_tokens": max_new, "length_penalty": length_penalty}

    translated_count = 0
    for it in mapping.get("items", []):
        if str(it.get("status", "")).startswith("FAIL"):
            continue
        if it.get("translated_text"):
            continue

        src = it.get("orig_text", "")
        if not str(src).strip():
            it["status"] = "SKIP_EMPTY"
            continue

        max_bytes = it.get("max_bytes")
        if not isinstance(max_bytes, int) or max_bytes <= 0:
            it["status"] = "SKIP_NO_MAXBYTES"
            continue

        term = parse_int_maybe(it.get("terminator"))
        if term is not None and not (0 <= term <= 255):
            it["status"] = "FAIL_INVALID_TERMINATOR"
            continue

        limit = max_bytes - (1 if term is not None else 0)
        if limit < 0:
            it["status"] = "FAIL_INVALID_MAXBYTES"
            continue

        enc = str(it.get("encoding", "")).upper()
        enc_kind = _encoding_kind(enc)
        use_tbl = (enc_kind == "tbl" and tbl_loader is not None)
        eff_kind = "tbl" if use_tbl else "ascii"

        orig_text = str(src)
        orig_tokens = Counter(_PLACEHOLDER_RE.findall(orig_text))

        last_candidate = ""
        final_text: Optional[str] = None
        final_status = ""

        for attempt in range(max_tries):
            if dry_run:
                out = orig_text
            else:
                out = _translate_one(tok, mdl, orig_text, model_name, gen_kwargs=_gen_kwargs_for_attempt(attempt))
            out = _normalize_whitespace(out)

            if Counter(_PLACEHOLDER_RE.findall(out)) != orig_tokens:
                final_status = "FAIL_PLACEHOLDER_MISMATCH"
                last_candidate = ""
                break

            candidate = out
            if eff_kind == "ascii":
                candidate = _sanitize_ascii(candidate)
            candidate = _normalize_whitespace(candidate)
            last_candidate = candidate

            final_text, final_status = _shorten_to_budget(candidate, limit, eff_kind, tbl_loader)
            if final_text is not None:
                break

        if final_text is None:
            it["translated_text"] = last_candidate
            it["status"] = final_status or "FAIL_BUDGET"
        else:
            it["translated_text"] = final_text
            it["status"] = final_status

        translated_count += 1

    out_path = args.out or args.mapping
    write_json(out_path, mapping)
    print(f"[OK] mapping atualizado: {out_path} | itens processados={translated_count}")
    return 0


# ---------------------------
# Reinserção estrita
# ---------------------------

def cmd_reinsert(args: argparse.Namespace) -> int:
    rom = bytearray(read_file_bytes(args.rom))
    in_crc = crc32_hex(rom)
    rom_size = len(rom)
    dry_run = bool(getattr(args, "dry_run", False))

    mapping = json.loads(open(args.mapping, "r", encoding="utf-8").read())
    map_crc = mapping.get("crc32")
    map_size = mapping.get("rom_size")

    print(f"[REINSERT] ROM_CRC32={in_crc} ROM_SIZE={rom_size}")
    if map_crc and map_crc != in_crc:
        print(f"[FAIL] mapping CRC32 != ROM CRC32 ({map_crc} != {in_crc})")
        return 2
    if map_size and int(map_size) != rom_size:
        print(f"[FAIL] mapping ROM_SIZE != ROM_SIZE ({map_size} != {rom_size})")
        return 2

    applied = 0
    proof_entries: List[Dict[str, Any]] = []

    for it in mapping.get("items", []):
        offset = it.get("offset")
        max_bytes = it.get("max_bytes")
        terminator = it.get("terminator")
        enc = str(it.get("encoding", "")).upper()
        txt = it.get("translated_text") or ""

        if "ASCII" not in enc:
            continue
        if not isinstance(offset, int) or not isinstance(max_bytes, int):
            continue

        orig = it.get("orig_text", "")
        orig_ph = set(_PLACEHOLDER_RE.findall(str(orig)))
        new_ph = set(_PLACEHOLDER_RE.findall(str(txt)))
        if orig_ph != new_ph:
            it["status"] = "FAIL_PLACEHOLDER_MISMATCH"
            continue

        term = terminator if isinstance(terminator, int) else None

        final, st = enforce_byte_limit_ascii(str(txt), max_bytes, term)
        if not st.startswith("OK"):
            it["status"] = st
            continue

        if offset < 0 or offset + max_bytes > rom_size:
            it["status"] = "FAIL_OOB"
            continue

        before = bytes(rom[offset:offset + max_bytes])
        pad = 0x00 if term in (None, 0x00) else int(term) & 0xFF

        for j in range(max_bytes):
            rom[offset + j] = pad

        payload = final.encode("ascii")
        rom[offset:offset + len(payload)] = payload

        if term is not None:
            if len(payload) >= max_bytes:
                it["status"] = "FAIL_NO_SPACE_FOR_TERMINATOR"
                rom[offset:offset + max_bytes] = before
                continue
            rom[offset + len(payload)] = term & 0xFF

        after = bytes(rom[offset:offset + max_bytes])

        it["status"] = "APPLIED"
        applied += 1
        proof_entries.append({
            "id": it.get("id"),
            "offset": offset,
            "max_bytes": max_bytes,
            "terminator": term,
            "orig_sha256": sha256_hex(before),
            "new_sha256": sha256_hex(after),
        })

    out_dir = args.out_dir or os.path.dirname(os.path.abspath(args.mapping)) or "."
    safe_mkdir(out_dir)

    out_path = os.path.join(out_dir, f"{in_crc}_translated.bin")
    if not dry_run:
        with open(out_path, "wb") as f:
            f.write(bytes(rom))

    out_crc = crc32_hex(bytes(rom))

    proof_path = os.path.join(out_dir, f"{in_crc}_proof.json")
    proof = {
        "created_at": _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "input_crc32": in_crc,
        "output_crc32": out_crc,
        "rom_size": rom_size,
        "applied": applied,
        "entries": proof_entries,
    }
    write_json(proof_path, proof)

    report_path = os.path.join(out_dir, f"{in_crc}_report.txt")
    write_text(report_path, "\n".join([
        "NEUROROM_AI V1 REINSERT REPORT",
        f"CRC32_IN={in_crc}",
        f"CRC32_OUT={out_crc}",
        f"ROM_SIZE={rom_size}",
        f"APPLIED={applied}",
        "",
        "OBS: reinserção automática limitada a ASCII estrito (V1 seguro).",
        ""
    ]) + "\n")

    if dry_run:
        print("[OK] out:   (dry-run: ROM não escrita)")
    else:
        print(f"[OK] out:   {out_path}")
    print(f"[OK] proof: {proof_path}")
    print(f"[OK] report:{report_path}")
    return 0


# ---------------------------
# CLI
# ---------------------------

def main(argv: List[str]) -> int:
    p = argparse.ArgumentParser(prog="romtxt_pipeline_v1.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("audit", help="gera report/proof/mapping a partir do pure_text.jsonl")
    pa.add_argument("--rom", required=True, help="caminho da ROM")
    pa.add_argument("--jsonl", required=True, help="caminho do {CRC32}_pure_text.jsonl")
    pa.add_argument("--out-dir", default=None, help="pasta de saída (default: pasta do jsonl)")
    pa.set_defaults(fn=cmd_audit)

    pt = sub.add_parser("translate", help="traduz e atualiza reinsertion_mapping.json")
    pt.add_argument("--mapping", required=True, help="caminho do {CRC32}_reinsertion_mapping.json")
    pt.add_argument("--model", default="facebook/nllb-200-distilled-600M", help="modelo transformers")
    pt.add_argument("--out", default=None, help="salvar mapping atualizado em outro path (opcional)")
    pt.add_argument("--dry-run", action="store_true", help="não carrega modelo; aplica budget no texto original")
    pt.set_defaults(fn=cmd_translate)

    pr = sub.add_parser("reinsert", help="reinserção estrita usando mapping")
    pr.add_argument("--rom", required=True, help="caminho da ROM")
    pr.add_argument("--mapping", required=True, help="caminho do {CRC32}_reinsertion_mapping.json")
    pr.add_argument("--out-dir", default=None, help="pasta de saída")
    pr.add_argument("--dry-run", action="store_true", help="não escreve ROM; gera apenas proof/report")
    pr.set_defaults(fn=cmd_reinsert)

    args = p.parse_args(argv)
    return int(args.fn(args))

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
