# -*- coding: utf-8 -*-
"""
Pós-processamento de captura dinâmica de texto (Runtime QA / BizHawk).

Suposições mínimas:
- O log de entrada é JSONL com linhas `type=meta` + linhas com `line`/`text`.
- O arquivo estático de comparação pode ser:
  1) TXT no formato `[0xOFFSET] texto`, ou
  2) JSONL com campos `rom_offset/offset` e `text/text_src`.
- O objetivo aqui é "texto humano para cobertura": controles são removidos e
  linhas vazias são descartadas.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None  # type: ignore[assignment]

try:
    from .common import (
        infer_crc_from_name,
        iter_jsonl,
        parse_int,
        write_json,
        write_jsonl,
    )
except ImportError:  # pragma: no cover
    from common import (  # type: ignore
        infer_crc_from_name,
        iter_jsonl,
        parse_int,
        write_json,
        write_jsonl,
    )


CONTROL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
WS_RE = re.compile(r"\s+")
OFFSET_LINE_RE = re.compile(r"^\[(0x[0-9A-Fa-f]+)\]\s*(.*)$")
HEX_HASH_RE = re.compile(r"^[0-9A-Fa-f]{8}$")
TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ]{2,}")

UNMAPPED_GLYPH_THRESHOLD = 0.10
PURE_UNMAPPED_GLYPH_THRESHOLD = 0.08
PURE_MIN_ALPHA_RATIO = 0.58
PURE_MAX_UNKNOWN_RATIO = 0.18
PURE_MIN_TOKEN_LEN = 3
PURE_MAX_REPEAT_RATIO = 0.45
PURE_MAX_QMARK_RATIO = 0.25

COMMON_PUNCT = set(".,:;!?\"'()[]{}+-*/%&@#_=<>|\\`~")
TOKEN_ORDER_RE = re.compile(
    r"(<TILE:[0-9A-Fa-f]{2}>|<[0-9A-Fa-f]{2}>|%\d*[ds]|"
    r"\{[A-Za-z0-9_]+\}|\[[A-Za-z0-9_]+\]|@[A-Za-z0-9_]+)"
)
CONTROL_TOKEN_RE = re.compile(r"<TILE:[0-9A-Fa-f]{2}>|<[0-9A-Fa-f]{2}>")
PLACEHOLDER_RE = re.compile(r"%\d*[ds]|\{[A-Za-z0-9_]+\}|\[[A-Za-z0-9_]+\]|@[A-Za-z0-9_]+")

PTBR_REQUIRED_GLYPHS = [
    "á",
    "à",
    "â",
    "ã",
    "ä",
    "é",
    "ê",
    "í",
    "ó",
    "ô",
    "õ",
    "ú",
    "ü",
    "ç",
]
PTBR_PUNCT = [".", ",", ";", ":", "!", "?", "-", "'", "\"", "(", ")", "%", "/"]
CANONICAL_SEGMENT_FIELDS = (
    "segment_id",
    "rom_crc32",
    "rom_size",
    "start_offset",
    "end_offset",
    "original_bytes_hex",
    "decoded_text",
    "translated_text",
    "renderable_text",
    "control_tokens",
    "terminator_hex",
    "max_bytes",
    "pointer_refs",
    "script_source",
    "confidence",
    "encoding_ok",
    "glyphs_ok",
    "tokens_ok",
    "terminator_ok",
    "layout_ok",
    "byte_length_ok",
    "offsets_ok",
    "pointers_ok",
    "fallback_applied",
    "fallback_changes",
    "missing_glyphs",
    "failure_reason",
    "status",
)


def sanitize_dynamic_text(value: str) -> str:
    """Remove controles e normaliza espaços para uso humano."""
    txt = str(value or "")
    txt = CONTROL_RE.sub("", txt)
    txt = WS_RE.sub(" ", txt).strip()
    return txt


def normalize_text_key(value: str) -> str:
    """Chave estável de deduplicação/comparação."""
    return sanitize_dynamic_text(value).casefold()


def _fontmap_supported_chars(fontmap: Dict[str, Dict[Any, str]]) -> List[str]:
    supported: List[str] = []
    seen: set[str] = set()
    for ch in list(fontmap.get("glyph_hash_to_char", {}).values()) + list(fontmap.get("tile_to_char", {}).values()):
        txt = str(ch or "")[:1]
        if not txt:
            continue
        if txt in seen:
            continue
        seen.add(txt)
        supported.append(txt)
    return supported


def _ptbr_coverage_from_fontmap(fontmap: Dict[str, Dict[Any, str]]) -> Dict[str, Any]:
    supported_chars = set(_fontmap_supported_chars(fontmap))
    required: List[str] = []
    for ch in PTBR_REQUIRED_GLYPHS:
        required.append(ch)
        required.append(ch.upper())
    required.extend(PTBR_PUNCT)
    required.append(" ")
    ordered_required = sorted({str(ch) for ch in required if str(ch)}, key=lambda c: (ord(c[0]), c))
    missing = [ch for ch in ordered_required if ch not in supported_chars]
    supported = [ch for ch in ordered_required if ch in supported_chars]
    return {
        "supported_glyphs": supported,
        "missing_glyphs": missing,
        "ptbr_full_coverage": bool(len(missing) == 0),
    }


def _iter_renderable_chars(text: str) -> List[str]:
    txt = str(text or "")
    out: List[str] = []
    last = 0
    for match in TOKEN_ORDER_RE.finditer(txt):
        chunk = txt[last : match.start()]
        for ch in chunk:
            if ch in ("\r", "\n", "\t"):
                continue
            out.append(ch)
        last = match.end()
    tail = txt[last:]
    for ch in tail:
        if ch in ("\r", "\n", "\t"):
            continue
        out.append(ch)
    return out


def _missing_glyphs_for_text(text: str, supported_chars: set[str]) -> List[str]:
    missing: List[str] = []
    seen: set[str] = set()
    for ch in _iter_renderable_chars(text):
        if not supported_chars:
            # Sem fontmap: não mascara problema; marca todos como ausentes.
            if ch not in seen:
                seen.add(ch)
                missing.append(ch)
            continue
        if ch in supported_chars:
            continue
        if ch in seen:
            continue
        seen.add(ch)
        missing.append(ch)
    return missing


def _canonical_segment_gate_failures(segment: Dict[str, Any]) -> List[str]:
    failed: List[str] = []
    for key in (
        "encoding_ok",
        "glyphs_ok",
        "tokens_ok",
        "terminator_ok",
        "layout_ok",
        "byte_length_ok",
        "offsets_ok",
        "pointers_ok",
    ):
        if bool(segment.get(key, False)):
            continue
        failed.append(key)
    return failed


def _segment_structural_ok(segment: Dict[str, Any], src_row: Dict[str, Any]) -> bool:
    ptr_valid = bool(src_row.get("pointer_valid", False) or src_row.get("pointer_table_valid", False))
    terminator_known = bool(segment.get("terminator_ok", False))
    script_known = bool(str(segment.get("script_source", "") or "").strip())
    strong_text = bool(src_row.get("is_human_text", False)) and float(src_row.get("unmapped_ratio", 1.0) or 1.0) <= PURE_UNMAPPED_GLYPH_THRESHOLD
    if ptr_valid:
        return True
    if terminator_known and script_known:
        return True
    if strong_text and terminator_known:
        return True
    return False


def _build_canonical_segment(
    *,
    idx: int,
    row: Dict[str, Any],
    crc: str,
    rom_size: int,
    supported_chars: set[str],
    ptbr_full_coverage: bool,
) -> Dict[str, Any]:
    decoded_text = str(row.get("line", "") or "")
    translated_text = str(row.get("translated_text", decoded_text) or decoded_text)
    renderable_text = str(row.get("renderable_text", translated_text) or translated_text)
    start_offset = parse_int(row.get("rom_offset", row.get("offset", row.get("start_offset"))), default=None)
    max_bytes = parse_int(
        row.get("max_bytes", row.get("max_len", row.get("max_len_bytes"))),
        default=None,
    )
    payload_len = len(renderable_text.encode("utf-8", errors="replace"))
    end_offset = None
    if start_offset is not None and max_bytes is not None and int(max_bytes) > 0:
        end_offset = int(start_offset) + int(max_bytes) - 1

    pointer_refs = row.get("pointer_refs", [])
    if not isinstance(pointer_refs, list):
        pointer_refs = []

    missing_original = _missing_glyphs_for_text(decoded_text, supported_chars)
    missing_translated = _missing_glyphs_for_text(translated_text, supported_chars)
    missing_renderable = _missing_glyphs_for_text(renderable_text, supported_chars)
    missing_glyphs: List[str] = []
    for ch in missing_original + missing_translated + missing_renderable:
        if ch not in missing_glyphs:
            missing_glyphs.append(ch)

    tokens_ok = TOKEN_ORDER_RE.findall(decoded_text) == TOKEN_ORDER_RE.findall(renderable_text)
    placeholders_ok = PLACEHOLDER_RE.findall(decoded_text) == PLACEHOLDER_RE.findall(renderable_text)
    controls_ok = CONTROL_TOKEN_RE.findall(decoded_text) == CONTROL_TOKEN_RE.findall(renderable_text)
    tokens_ok = bool(tokens_ok and placeholders_ok and controls_ok)

    terminator = parse_int(row.get("terminator", row.get("end_byte")), default=0)
    terminator_ok = bool(terminator is not None and 0 <= int(terminator) <= 0xFF)
    terminator_hex = f"{int(terminator) & 0xFF:02X}" if terminator_ok else ""

    line_count = max(1, len(renderable_text.split("\n")))
    max_line_width = max((len(x) for x in renderable_text.split("\n")), default=len(renderable_text))
    overflow_detected = bool(max_line_width > 64 or line_count > 6)
    layout_ok = not overflow_detected

    offsets_ok = bool(
        start_offset is not None
        and max_bytes is not None
        and int(start_offset) >= 0
        and int(max_bytes) > 0
        and int(start_offset) + int(max_bytes) <= int(rom_size)
    )
    pointers_ok = True
    for pref in pointer_refs:
        if not isinstance(pref, dict):
            pointers_ok = False
            break
        ptr_off = parse_int(pref.get("ptr_offset"), default=None)
        ptr_size = parse_int(pref.get("ptr_size"), default=2)
        if ptr_off is None or ptr_size is None or ptr_size not in {2, 3, 4}:
            pointers_ok = False
            break
        if ptr_off < 0 or (ptr_off + ptr_size) > int(rom_size):
            pointers_ok = False
            break

    max_bytes_int = int(max_bytes) if max_bytes is not None else payload_len
    byte_length_ok = bool(max_bytes_int <= 0 or payload_len <= max_bytes_int)

    segment = {
        "segment_id": f"DYN_{int(idx):06d}",
        "rom_crc32": str(crc).upper(),
        "rom_size": int(rom_size),
        "start_offset": int(start_offset) if start_offset is not None else None,
        "end_offset": int(end_offset) if end_offset is not None else None,
        "original_bytes_hex": str(row.get("raw_bytes_hex", row.get("tile_row_hex", "")) or "").replace(" ", "").upper(),
        "decoded_text": decoded_text,
        "translated_text": translated_text,
        "renderable_text": renderable_text,
        "control_tokens": CONTROL_TOKEN_RE.findall(decoded_text),
        "terminator_hex": terminator_hex,
        "max_bytes": int(max_bytes_int),
        "pointer_refs": pointer_refs,
        "script_source": str(row.get("source", "tilemap_vram") or "tilemap_vram"),
        "confidence": float(max(0.0, min(1.0, float(row.get("human_score", 0.0) or 0.0)))),
        "encoding_ok": True,
        "glyphs_ok": bool(len(missing_glyphs) == 0),
        "tokens_ok": bool(tokens_ok),
        "terminator_ok": bool(terminator_ok),
        "layout_ok": bool(layout_ok),
        "byte_length_ok": bool(byte_length_ok),
        "offsets_ok": bool(offsets_ok or start_offset is None),
        "pointers_ok": bool(pointers_ok),
        "fallback_applied": False,
        "fallback_changes": [],
        "missing_glyphs": missing_glyphs,
        "failure_reason": "",
        "status": "PENDING",
        "line_count": int(line_count),
        "max_line_width": int(max_line_width),
        "overflow_detected": bool(overflow_detected),
        "supported_glyphs": sorted(supported_chars),
        "ptbr_full_coverage": bool(ptbr_full_coverage),
    }
    failed = _canonical_segment_gate_failures(segment)
    if failed:
        segment["status"] = "ABORTED_VALIDATION"
        segment["failure_reason"] = "gate_failed:" + ",".join(failed)
    else:
        segment["status"] = "VALIDATED"
    return segment


def _build_static_word_lexicon(rows: List[Dict[str, Any]]) -> set[str]:
    lex: set[str] = set()
    for row in rows:
        text = sanitize_dynamic_text(str(row.get("text", "") or ""))
        if not text:
            continue
        for token in TOKEN_RE.findall(text):
            tok = token.casefold().strip()
            if len(tok) < PURE_MIN_TOKEN_LEN:
                continue
            lex.add(tok)
    return lex


def _max_repeat_ratio(text: str) -> float:
    visible = [ch for ch in str(text or "") if ch != " "]
    if not visible:
        return 0.0
    freq: Dict[str, int] = {}
    max_rep = 0
    for ch in visible:
        cnt = int(freq.get(ch, 0)) + 1
        freq[ch] = cnt
        if cnt > max_rep:
            max_rep = cnt
    return float(max_rep) / float(len(visible))


def _longest_sequential_alpha_run(token: str) -> int:
    txt = str(token or "")
    if not txt:
        return 0
    best = 1
    cur = 1
    prev = None
    for ch in txt:
        c = ch.casefold()
        if not c.isalpha():
            cur = 1
            prev = None
            continue
        code = ord(c)
        if prev is not None and code == (prev + 1):
            cur += 1
        else:
            cur = 1
        if cur > best:
            best = cur
        prev = code
    return int(best)


def _human_text_score(
    *,
    line: str,
    unmapped_ratio: float,
    static_lexicon: Optional[set[str]],
) -> Tuple[bool, float]:
    """
    Heurística de pureza para separar texto humano de ruído visual de tilemap.
    Retorna (is_human, score 0..1).
    """
    text = sanitize_dynamic_text(line)
    if not text or len(text) < 2:
        return False, 0.0

    visible_chars = [ch for ch in text if ch != " "]
    if not visible_chars:
        return False, 0.0

    visible = float(len(visible_chars))
    alpha = sum(1 for ch in visible_chars if ch.isalpha())
    digits = sum(1 for ch in visible_chars if ch.isdigit())
    qmarks = sum(1 for ch in visible_chars if ch == "?")
    punct = sum(1 for ch in visible_chars if ch in COMMON_PUNCT)
    weird = max(0.0, visible - float(alpha + digits + punct))

    alpha_ratio = float(alpha) / visible
    qmark_ratio = float(qmarks) / visible
    weird_ratio = float(weird) / visible
    rep_ratio = _max_repeat_ratio(text)

    if float(unmapped_ratio) > PURE_UNMAPPED_GLYPH_THRESHOLD:
        return False, 0.0
    if alpha_ratio < PURE_MIN_ALPHA_RATIO:
        return False, 0.0
    if qmark_ratio > PURE_MAX_QMARK_RATIO:
        return False, 0.0
    if weird_ratio > PURE_MAX_UNKNOWN_RATIO:
        return False, 0.0
    if rep_ratio > PURE_MAX_REPEAT_RATIO:
        return False, 0.0

    tokens = [tok.casefold() for tok in TOKEN_RE.findall(text) if len(tok) >= PURE_MIN_TOKEN_LEN]
    token_count = len(tokens)
    if token_count <= 0:
        return False, 0.0

    # Corta padrões artificiais comuns em tabelas/fontes (abc... / sequências lineares).
    longest_seq = max((_longest_sequential_alpha_run(tok) for tok in tokens), default=0)
    if longest_seq >= 8:
        return False, 0.0
    if token_count == 1:
        tok0 = tokens[0]
        if len(tok0) >= 12:
            if not static_lexicon or tok0 not in static_lexicon:
                return False, 0.0
    if len(text) >= 16 and (" " not in text) and token_count <= 1:
        tok0 = tokens[0] if tokens else ""
        if not static_lexicon or tok0 not in static_lexicon:
            return False, 0.0

    lex_hit_ratio = 0.0
    if static_lexicon:
        hits = sum(1 for tok in tokens if tok in static_lexicon)
        lex_hit_ratio = float(hits) / float(max(1, token_count))
        # Quando há léxico estático disponível, exigimos algum acerto mínimo.
        if token_count >= 2 and lex_hit_ratio <= 0.0:
            return False, 0.0

    # Score simples para auditoria/ordenação.
    score = (
        (alpha_ratio * 0.45)
        + ((1.0 - qmark_ratio) * 0.15)
        + ((1.0 - weird_ratio) * 0.15)
        + ((1.0 - min(1.0, rep_ratio)) * 0.15)
        + (lex_hit_ratio * 0.10)
    )
    return True, float(max(0.0, min(1.0, score)))


def build_scene_hash(*parts: str) -> str:
    """Hash estável curto para agrupar cenas."""
    raw = "|".join(str(p or "") for p in parts)
    digest = hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest().upper()
    return digest[:12]


def _parse_tile_key(raw: Any) -> Optional[int]:
    if raw is None:
        return None
    if isinstance(raw, int):
        return int(raw)
    if isinstance(raw, str):
        txt = raw.strip()
        if not txt:
            return None
        if txt.lower().startswith("0x"):
            try:
                return int(txt, 16)
            except Exception:
                return None
        try:
            return int(txt)
        except Exception:
            return None
    return None


def _parse_unmapped_tiles(raw: Any) -> List[int]:
    out: List[int] = []
    if isinstance(raw, list):
        for item in raw:
            val = _parse_tile_key(item)
            if val is not None:
                out.append(int(val))
    elif isinstance(raw, str):
        for token in re.split(r"[,\s;]+", raw):
            val = _parse_tile_key(token)
            if val is not None:
                out.append(int(val))
    return out


def _parse_char_value(value: Any) -> str:
    if isinstance(value, str):
        return value[:1]
    if isinstance(value, int):
        return chr(value) if 32 <= int(value) <= 126 else ""
    return ""


def _normalize_glyph_hash(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    txt = str(raw).strip().upper()
    if txt.startswith("0X"):
        txt = txt[2:]
    if HEX_HASH_RE.fullmatch(txt):
        return txt
    return None


def _parse_hash_list(raw: Any) -> List[str]:
    out: List[str] = []
    if isinstance(raw, list):
        for item in raw:
            h = _normalize_glyph_hash(item)
            if h:
                out.append(h)
    elif isinstance(raw, str):
        for token in re.split(r"[,\s;]+", raw):
            h = _normalize_glyph_hash(token)
            if h:
                out.append(h)
    return out


def _normalize_pattern_hex(raw: Any) -> Optional[str]:
    txt = str(raw or "").strip().upper()
    if not txt:
        return None
    txt = re.sub(r"[^0-9A-F]", "", txt)
    if len(txt) < 32:
        return None
    if len(txt) >= 64:
        return txt[:64]
    return txt[:32]


def _parse_unknown_samples(raw: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        glyph_hash = _normalize_glyph_hash(
            item.get("hash", item.get("glyph_hash", item.get("pattern_hash")))
        )
        pattern_hex = _normalize_pattern_hex(item.get("pattern_hex"))
        tile_id = _parse_tile_key(item.get("tile_id", item.get("tile_index")))
        if not glyph_hash and not pattern_hex:
            continue
        out.append(
            {
                "glyph_hash": glyph_hash or "",
                "pattern_hex": pattern_hex or "",
                "tile_id": int(tile_id) if tile_id is not None else None,
            }
        )
    return out


def _parse_ratio(raw: Any) -> Optional[float]:
    try:
        if raw is None:
            return None
        value = float(raw)
    except Exception:
        return None
    if value < 0:
        value = 0.0
    if value > 1:
        value = 1.0
    return value


def _parse_review_flags(raw: Any) -> List[str]:
    flags: List[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item.strip():
                flags.append(item.strip().upper())
    elif isinstance(raw, str) and raw.strip():
        flags = [part.strip().upper() for part in raw.split(",") if part.strip()]
    seen = set()
    out: List[str] = []
    for flag in flags:
        if flag not in seen:
            seen.add(flag)
            out.append(flag)
    return out


def load_fontmap(path: Optional[Path]) -> Dict[str, Dict[Any, str]]:
    """
    Carrega fontmap em dois modos:
    - glyph_hash_to_char: hash(FNV-1a 32 dos 32 bytes do tile) -> char
    - tile_to_char: legado tile_id -> char (fallback)
    """
    empty = {"glyph_hash_to_char": {}, "tile_to_char": {}}
    if path is None or not path.exists():
        return empty
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return empty
    if not isinstance(obj, dict):
        return empty

    glyph_map: Dict[str, str] = {}
    tile_map: Dict[int, str] = {}

    containers: List[Dict[str, Any]] = []
    glyph_part = obj.get("glyph_hash_to_char")
    tile_part = obj.get("tile_to_char")
    mappings_part = obj.get("mappings")
    if isinstance(glyph_part, dict):
        containers.append({"kind": "hash", "map": glyph_part})
    if isinstance(mappings_part, dict):
        # Compatibilidade com template manual: {"rom_crc32": "...", "mappings": {...}}
        containers.append({"kind": "hash", "map": mappings_part})
    if isinstance(tile_part, dict):
        containers.append({"kind": "tile", "map": tile_part})
    if not containers:
        containers.append({"kind": "mixed", "map": obj})

    for chunk in containers:
        kind = str(chunk.get("kind", "mixed"))
        raw_map = chunk.get("map")
        if not isinstance(raw_map, dict):
            continue
        for key, value in raw_map.items():
            ch = _parse_char_value(value)
            if not ch:
                continue
            h = _normalize_glyph_hash(key)
            if h and kind in {"hash", "mixed"}:
                glyph_map[h] = ch
                continue
            tile = _parse_tile_key(key)
            if tile is not None and kind in {"tile", "mixed"}:
                tile_map[int(tile)] = ch

    return {"glyph_hash_to_char": glyph_map, "tile_to_char": tile_map}


def discover_static_only_safe_by_offset(
    *,
    crc32: str,
    pure_jsonl: Optional[Path],
    runtime_dir: Path,
) -> Optional[Path]:
    """Tenta localizar o arquivo estático `{CRC}_*_by_offset.txt`."""
    crc = str(crc32 or "").upper().strip()
    candidates: List[Path] = []
    if pure_jsonl is not None:
        base = pure_jsonl.parent
        candidates.extend(
            [
                base / f"{crc}_only_safe_text_by_offset.txt",
                base / f"{crc}_only_safe_text_human_by_offset.txt",
                base / f"{crc}_pure_text_optimized_by_offset.txt",
            ]
        )
    runtime_parent = runtime_dir.parent
    candidates.extend(
        [
            runtime_parent / f"{crc}_only_safe_text_by_offset.txt",
            runtime_parent / f"{crc}_only_safe_text_human_by_offset.txt",
            runtime_dir / f"{crc}_only_safe_text_by_offset.txt",
        ]
    )
    for cand in candidates:
        if cand.exists():
            return cand

    # Fallback: quando a ROM runtime usa CRC diferente (ex.: ROM com fonte),
    # reaproveita o único *_by_offset disponível ao lado do pure_jsonl.
    if pure_jsonl is not None:
        base = pure_jsonl.parent
        broad_candidates: List[Path] = []
        broad_candidates.extend(sorted(base.glob("*_only_safe_text_by_offset.txt")))
        broad_candidates.extend(sorted(base.glob("*_only_safe_text_human_by_offset.txt")))
        broad_candidates.extend(sorted(base.glob("*_pure_text_optimized_by_offset.txt")))
        broad_candidates = [p for p in broad_candidates if p.exists() and p.is_file()]
        if len(broad_candidates) == 1:
            return broad_candidates[0]

        pure_crc = infer_crc_from_name(pure_jsonl.name)
        if pure_crc:
            pure_crc = str(pure_crc).upper()
            for cand in broad_candidates:
                if str(cand.name).upper().startswith(pure_crc):
                    return cand
    return None


def _parse_static_txt(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for idx, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        m = OFFSET_LINE_RE.match(raw.strip())
        if m:
            offset = parse_int(m.group(1), default=None)
            text = sanitize_dynamic_text(m.group(2))
        else:
            offset = None
            text = sanitize_dynamic_text(raw)
        if not text:
            continue
        rows.append(
            {
                "idx": int(idx),
                "offset": int(offset) if offset is not None else None,
                "offset_hex": f"0x{int(offset):06X}" if offset is not None else "",
                "text": text,
                "text_key": normalize_text_key(text),
            }
        )
    return rows


def _parse_static_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    idx = 0
    for obj in iter_jsonl(path):
        if obj.get("type") == "meta":
            continue
        text = sanitize_dynamic_text(
            str(
                obj.get("text")
                or obj.get("text_src")
                or obj.get("raw_text")
                or obj.get("value")
                or ""
            )
        )
        if not text:
            continue
        off = parse_int(obj.get("rom_offset", obj.get("offset", obj.get("origin_offset"))), default=None)
        rows.append(
            {
                "idx": int(idx),
                "offset": int(off) if off is not None else None,
                "offset_hex": f"0x{int(off):06X}" if off is not None else "",
                "text": text,
                "text_key": normalize_text_key(text),
            }
        )
        idx += 1
    return rows


def parse_static_only_safe_rows(path: Path) -> List[Dict[str, Any]]:
    """Carrega arquivo estático para diff de cobertura."""
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return _parse_static_jsonl(path)
    return _parse_static_txt(path)


def _decode_pattern_32bytes_to_pixels(pattern_hex: str) -> Optional[List[int]]:
    pattern = _normalize_pattern_hex(pattern_hex)
    if not pattern:
        return None
    raw = bytes.fromhex(pattern)
    if len(raw) not in {16, 32}:
        return None
    pixels: List[int] = []
    if len(raw) == 32:
        for row in range(8):
            b0, b1, b2, b3 = raw[row * 4 : row * 4 + 4]
            for col in range(8):
                bit = 7 - col
                value = (
                    ((b0 >> bit) & 1)
                    | (((b1 >> bit) & 1) << 1)
                    | (((b2 >> bit) & 1) << 2)
                    | (((b3 >> bit) & 1) << 3)
                )
                pixels.append(int(value))
    else:
        for row in range(8):
            b0, b1 = raw[row * 2 : row * 2 + 2]
            for col in range(8):
                bit = 7 - col
                value = ((b0 >> bit) & 1) | (((b1 >> bit) & 1) << 1)
                pixels.append(int(value) * 5)
    return pixels


def _write_unknown_glyphs_png(
    *,
    crc32: str,
    out_dir: Path,
    rows: List[Dict[str, Any]],
    max_items: int = 256,
) -> Optional[Path]:
    if Image is None:
        return None
    draw_rows = [row for row in rows if row.get("pattern_hex")]
    if not draw_rows:
        return None

    draw_rows = draw_rows[: max(1, int(max_items))]
    cols = 16
    tile_px = 8
    scale = 4
    cell = tile_px * scale
    rows_count = (len(draw_rows) + cols - 1) // cols
    width = cols * cell
    height = rows_count * cell
    img = Image.new("RGB", (width, height), color=(22, 22, 22))

    for idx, row in enumerate(draw_rows):
        pixels = _decode_pattern_32bytes_to_pixels(str(row.get("pattern_hex", "") or ""))
        if pixels is None:
            continue
        x0 = (idx % cols) * cell
        y0 = (idx // cols) * cell
        for py in range(8):
            for px in range(8):
                val = int(pixels[py * 8 + px])
                gray = int((val / 15.0) * 255)
                color = (gray, gray, gray)
                for sy in range(scale):
                    for sx in range(scale):
                        img.putpixel((x0 + px * scale + sx, y0 + py * scale + sy), color)

    out_path = out_dir / f"{str(crc32).upper()}_unknown_glyphs.png"
    img.save(out_path)
    return out_path


def _make_bootstrap(
    *,
    crc32: str,
    rom_size: int,
    out_dir: Path,
    unknown_hash_counter: Counter[str],
    hash_context: Dict[str, List[str]],
    hash_pattern: Dict[str, str],
    current_fontmap_hash: Dict[str, str],
    max_items: int = 512,
) -> Dict[str, Optional[Path]]:
    if not unknown_hash_counter:
        return {
            "fontmap_bootstrap_path": None,
            "unknown_glyphs_jsonl_path": None,
            "unknown_glyphs_png_path": None,
        }

    rows: List[Dict[str, Any]] = []
    for glyph_hash, hits in unknown_hash_counter.most_common(max_items):
        row = {
            "glyph_hash": str(glyph_hash),
            "hits": int(hits),
            "already_mapped": str(glyph_hash) in current_fontmap_hash,
            "sample_contexts": list(hash_context.get(str(glyph_hash), [])[:6]),
            "pattern_hex": str(hash_pattern.get(str(glyph_hash), "") or ""),
        }
        rows.append(row)

    payload = {
        "schema": "runtime_dyn_fontmap_bootstrap.v2",
        "rom_crc32": str(crc32).upper(),
        "rom_size": int(max(0, int(rom_size))),
        "unknown_glyphs_total": int(len(unknown_hash_counter)),
        "rows": rows,
    }
    bootstrap_path = out_dir / f"{str(crc32).upper()}_dyn_fontmap_bootstrap.json"
    write_json(bootstrap_path, payload)

    unknown_jsonl = out_dir / f"{str(crc32).upper()}_unknown_glyphs.jsonl"
    write_jsonl(
        unknown_jsonl,
        rows,
        meta={
            "type": "meta",
            "schema": "runtime_unknown_glyphs.v1",
            "rom_crc32": str(crc32).upper(),
            "rows_total": int(len(rows)),
        },
    )

    unknown_png = _write_unknown_glyphs_png(
        crc32=str(crc32).upper(),
        out_dir=out_dir,
        rows=rows,
    )

    return {
        "fontmap_bootstrap_path": bootstrap_path,
        "unknown_glyphs_jsonl_path": unknown_jsonl,
        "unknown_glyphs_png_path": unknown_png,
    }


def _render_unique_lines(rows: Iterable[Dict[str, Any]]) -> List[str]:
    lines: List[str] = []
    for row in rows:
        text = str(row.get("text", "") or "")
        frame = int(parse_int(row.get("first_frame"), default=0) or 0)
        scenes = row.get("scene_hashes", [])
        if not isinstance(scenes, list):
            scenes = []
        hits = int(parse_int(row.get("hits"), default=1) or 1)
        unmapped_ratio_max = _parse_ratio(row.get("unmapped_ratio_max"))
        scene_label = ",".join(str(s) for s in scenes[:3] if str(s))
        ratio_label = (
            f"\tunmapped_ratio_max={float(unmapped_ratio_max):.4f}"
            if unmapped_ratio_max is not None
            else ""
        )
        lines.append(f"{text}\tframe={frame}\tscene_hash={scene_label}\thits={hits}{ratio_label}")
    return lines


def _write_text(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(str(x) for x in lines)
    if content and not content.endswith("\n"):
        content += "\n"
    path.write_text(content, encoding="utf-8")


def _build_coverage_diff(
    *,
    crc32: str,
    out_dir: Path,
    runtime_unique_rows: List[Dict[str, Any]],
    static_rows: List[Dict[str, Any]],
    tag: str = "",
) -> Dict[str, Any]:
    runtime_map = {str(r["text_key"]): r for r in runtime_unique_rows if r.get("text_key")}
    static_map = {str(r["text_key"]): r for r in static_rows if r.get("text_key")}

    static_total = int(len(static_rows))
    static_unique = int(len(static_map))
    runtime_unique = int(len(runtime_map))
    matched_keys = sorted(set(static_map.keys()) & set(runtime_map.keys()))
    missing_static_keys = sorted(set(static_map.keys()) - set(runtime_map.keys()))
    missing_runtime_keys = sorted(set(runtime_map.keys()) - set(static_map.keys()))

    missing_static_rows = [static_map[k] for k in missing_static_keys]
    missing_runtime_rows = [runtime_map[k] for k in missing_runtime_keys]

    coverage_pct = (len(matched_keys) / static_unique * 100.0) if static_unique > 0 else 100.0
    capture_progress_pct_raw = (runtime_unique / static_unique * 100.0) if static_unique > 0 else 100.0
    # Progresso de captura é um KPI de completude; mantém limite visual em 100%.
    capture_progress_pct = min(100.0, float(capture_progress_pct_raw))
    suffix = f"_{str(tag).strip()}" if str(tag or "").strip() else ""
    report_path = out_dir / f"{str(crc32).upper()}_coverage_diff_report{suffix}.txt"
    miss_static_path = out_dir / f"{str(crc32).upper()}_coverage_missing_from_runtime{suffix}.txt"
    miss_runtime_path = out_dir / f"{str(crc32).upper()}_coverage_missing_from_static{suffix}.txt"

    _write_text(
        miss_static_path,
        [
            f"[{row.get('offset_hex') or 'NO_OFFSET'}] {row.get('text', '')}"
            for row in missing_static_rows
        ],
    )
    _write_text(
        miss_runtime_path,
        [
            f"[scene={','.join(row.get('scene_hashes', [])[:1])}] {row.get('text', '')}"
            for row in missing_runtime_rows
        ],
    )

    report_lines = [
        "RUNTIME COVERAGE DIFF",
        f"ROM_CRC32: {str(crc32).upper()}",
        f"STATIC_ROWS_TOTAL: {static_total}",
        f"STATIC_UNIQUE_TEXTS: {static_unique}",
        f"RUNTIME_UNIQUE_TEXTS: {runtime_unique}",
        f"MATCHED_UNIQUE_TEXTS: {len(matched_keys)}",
        f"MISSING_FROM_RUNTIME: {len(missing_static_rows)}",
        f"MISSING_FROM_STATIC: {len(missing_runtime_rows)}",
        f"COVERAGE_PERCENT: {coverage_pct:.2f}",
        f"CAPTURE_PROGRESS_PERCENT: {capture_progress_pct:.2f}",
        f"PROGRESS_PRIMARY_PERCENT: {capture_progress_pct:.2f}",
        f"MISSING_FROM_RUNTIME_PATH: {miss_static_path}",
        f"MISSING_FROM_STATIC_PATH: {miss_runtime_path}",
    ]
    _write_text(report_path, report_lines)

    return {
        "coverage_diff_report_path": str(report_path),
        "missing_from_runtime_path": str(miss_static_path),
        "missing_from_static_path": str(miss_runtime_path),
        "static_rows_total": static_total,
        "static_unique_texts": static_unique,
        "runtime_unique_texts": runtime_unique,
        "matched_unique_texts": int(len(matched_keys)),
        "missing_from_runtime_count": int(len(missing_static_rows)),
        "missing_from_static_count": int(len(missing_runtime_rows)),
        "coverage_percent": float(round(coverage_pct, 4)),
        "capture_progress_percent": float(round(capture_progress_pct, 4)),
        "progress_primary_percent": float(round(capture_progress_pct, 4)),
    }


def process_dynamic_capture(
    *,
    dyn_log_input_path: Path,
    out_dir: Path,
    crc32: Optional[str] = None,
    static_only_safe_by_offset: Optional[Path] = None,
    fontmap_path: Optional[Path] = None,
    bootstrap_enabled: bool = True,
) -> Dict[str, Any]:
    """
    Gera artefatos dinâmicos finais:
    - `{CRC}_dyn_text_log.jsonl` (sanitizado)
    - `{CRC}_dyn_text_unique.txt` (dedup + contexto)
    - `coverage_diff_report` + missing lists (quando há arquivo estático)
    - bootstrap de fontmap (opcional)
    """
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    dyn_log_input_path = dyn_log_input_path.expanduser().resolve()
    if not dyn_log_input_path.exists():
        raise FileNotFoundError(f"dyn_log_input não encontrado: {dyn_log_input_path}")

    meta: Dict[str, Any] = {}
    rows_clean: List[Dict[str, Any]] = []
    rows_clean_pure: List[Dict[str, Any]] = []
    dedup_by_text: Dict[str, Dict[str, Any]] = {}
    dedup_pure_by_text: Dict[str, Dict[str, Any]] = {}
    dropped_controls = 0
    dropped_empty = 0
    blocked_unmapped_glyphs_count = 0
    unknown_hash_counter: Counter[str] = Counter()
    hash_context: Dict[str, List[str]] = {}
    hash_pattern: Dict[str, str] = {}

    mapped_font = load_fontmap(fontmap_path)
    mapped_hash_font = {
        str(k).upper(): str(v)
        for k, v in dict(mapped_font.get("glyph_hash_to_char", {})).items()
        if _normalize_glyph_hash(k)
    }
    mapped_tile_font = {
        int(k): str(v)
        for k, v in dict(mapped_font.get("tile_to_char", {})).items()
        if _parse_tile_key(k) is not None
    }
    supported_chars = set(_fontmap_supported_chars(mapped_font))
    coverage_proof = _ptbr_coverage_from_fontmap(mapped_font)

    static_rows_for_diff: List[Dict[str, Any]] = []
    static_lexicon: set[str] = set()
    if static_only_safe_by_offset is not None and static_only_safe_by_offset.exists():
        static_rows_for_diff = parse_static_only_safe_rows(static_only_safe_by_offset)
        static_lexicon = _build_static_word_lexicon(static_rows_for_diff)

    for idx, obj in enumerate(iter_jsonl(dyn_log_input_path)):
        if obj.get("type") == "meta":
            meta = dict(obj)
            continue

        raw_text = str(obj.get("line", obj.get("text", "")) or "")
        line = sanitize_dynamic_text(raw_text)
        had_control = bool(CONTROL_RE.search(raw_text))
        if had_control:
            dropped_controls += 1
        if not line:
            dropped_empty += 1
            continue

        frame = int(parse_int(obj.get("frame"), default=idx) or idx)
        line_idx = int(parse_int(obj.get("line_idx"), default=0) or 0)
        scene_hash = str(obj.get("scene_hash", "") or "").strip().upper()
        if not scene_hash:
            scene_hash = build_scene_hash(
                str(obj.get("tile_row_hex", "") or ""),
                str(obj.get("scene_hex", "") or ""),
                str(frame),
                str(line_idx),
            )

        unmapped_tiles = _parse_unmapped_tiles(obj.get("unmapped_tiles", []))
        glyph_hashes = _parse_hash_list(obj.get("glyph_hashes", []))
        unmapped_hashes = _parse_hash_list(
            obj.get("unmapped_glyph_hashes", obj.get("unmapped_hashes", []))
        )
        unknown_samples = _parse_unknown_samples(obj.get("unknown_glyph_samples", []))

        glyph_count = parse_int(obj.get("glyph_count"), default=None)
        if glyph_count is None or int(glyph_count) <= 0:
            glyph_count = len(glyph_hashes)
        if glyph_count is None or int(glyph_count) <= 0:
            glyph_count = max(len(line), len(unmapped_hashes), len(unmapped_tiles), 1)
        glyph_count = max(1, int(glyph_count))

        unmapped_count = parse_int(obj.get("unmapped_glyph_count"), default=None)
        if unmapped_count is None or int(unmapped_count) < 0:
            unmapped_count = len(unmapped_hashes) if unmapped_hashes else len(unmapped_tiles)
        unmapped_count = max(0, int(unmapped_count))

        unmapped_ratio = _parse_ratio(obj.get("unmapped_ratio"))
        if unmapped_ratio is None:
            unmapped_ratio = min(1.0, float(unmapped_count) / float(max(1, glyph_count)))
        unmapped_ratio = float(min(1.0, max(0.0, unmapped_ratio)))

        # Coleta hashes desconhecidos para bootstrap.
        row_unknown_hashes: List[str] = []
        if unmapped_hashes:
            for i, glyph_hash in enumerate(unmapped_hashes):
                if glyph_hash in mapped_hash_font:
                    continue
                tile_id = None
                if i < len(unmapped_tiles):
                    try:
                        tile_id = int(unmapped_tiles[i])
                    except Exception:
                        tile_id = None
                if tile_id is not None:
                    if tile_id in mapped_tile_font:
                        continue
                    if (tile_id & 0x1FF) in mapped_tile_font:
                        continue
                    if (tile_id & 0xFF) in mapped_tile_font:
                        continue
                row_unknown_hashes.append(glyph_hash)
        else:
            # Compatibilidade com logs antigos (sem hash): gera hash sintético por tile.
            for tile in unmapped_tiles:
                tile_id = int(tile)
                if tile_id in mapped_tile_font:
                    continue
                if (tile_id & 0x1FF) in mapped_tile_font:
                    continue
                if (tile_id & 0xFF) in mapped_tile_font:
                    continue
                row_unknown_hashes.append(f"{(0xFF000000 | (tile_id & 0xFFFF)):08X}")

        unmapped_count = int(len(row_unknown_hashes))
        unmapped_ratio = min(1.0, float(unmapped_count) / float(max(1, glyph_count)))

        for sample in unknown_samples:
            glyph_hash = _normalize_glyph_hash(sample.get("glyph_hash"))
            pattern_hex = _normalize_pattern_hex(sample.get("pattern_hex"))
            if glyph_hash and pattern_hex and glyph_hash not in hash_pattern:
                hash_pattern[glyph_hash] = pattern_hex

        for glyph_hash in row_unknown_hashes:
            unknown_hash_counter[glyph_hash] += 1
            if glyph_hash not in hash_context:
                hash_context[glyph_hash] = []
            if len(hash_context[glyph_hash]) < 8:
                hash_context[glyph_hash].append(line)

        review_flags = _parse_review_flags(obj.get("review_flags"))
        needs_review = bool(obj.get("needs_review", False)) or bool(review_flags)
        if float(unmapped_ratio) > float(UNMAPPED_GLYPH_THRESHOLD):
            if "UNMAPPED_GLYPHS" not in review_flags:
                review_flags.append("UNMAPPED_GLYPHS")
            needs_review = True
            blocked_unmapped_glyphs_count += 1

        is_human_text, human_score = _human_text_score(
            line=line,
            unmapped_ratio=float(unmapped_ratio),
            static_lexicon=static_lexicon if static_lexicon else None,
        )
        if not is_human_text:
            if "NON_HUMAN_TEXT" not in review_flags:
                review_flags.append("NON_HUMAN_TEXT")
            needs_review = True

        row = {
            "type": "dyn_text",
            "frame": frame,
            "scene_hash": scene_hash,
            "line_idx": line_idx,
            "line": line,
            "line_key": normalize_text_key(line),
            "source": str(obj.get("source", "tilemap_vram") or "tilemap_vram"),
            "tile_row_hex": str(obj.get("tile_row_hex", "") or "").upper(),
            "nametable_base": str(obj.get("nametable_base", "") or ""),
            "pattern_base": str(obj.get("pattern_base", "") or ""),
            "glyph_hashes": glyph_hashes,
            "unmapped_tiles": unmapped_tiles,
            "unmapped_glyph_hashes": row_unknown_hashes,
            "unknown_glyph_samples": unknown_samples,
            "glyph_count": int(glyph_count),
            "unmapped_glyph_count": int(unmapped_count),
            "unmapped_ratio": float(round(unmapped_ratio, 4)),
            "needs_review": bool(needs_review),
            "review_flags": review_flags,
            "is_human_text": bool(is_human_text),
            "human_score": float(round(human_score, 4)),
        }
        if "UNMAPPED_GLYPHS" in review_flags:
            row["translation_status"] = "BLOCKED"
            row["translation_block_reason"] = "UNMAPPED_GLYPHS"
        elif "NON_HUMAN_TEXT" in review_flags:
            row["translation_status"] = "REVIEW"
            row["translation_block_reason"] = "NON_HUMAN_TEXT"
        rows_clean.append(row)
        if bool(is_human_text):
            rows_clean_pure.append(row)

        k = str(row["line_key"])
        agg = dedup_by_text.get(k)
        if agg is None:
            dedup_by_text[k] = {
                "text": line,
                "text_key": k,
                "first_frame": frame,
                "scene_hashes": [scene_hash] if scene_hash else [],
                "hits": 1,
                "unmapped_ratio_max": float(round(unmapped_ratio, 4)),
                "blocked_unmapped_hits": 1 if "UNMAPPED_GLYPHS" in review_flags else 0,
            }
        else:
            agg["hits"] = int(parse_int(agg.get("hits"), default=0) or 0) + 1
            if frame < int(parse_int(agg.get("first_frame"), default=frame) or frame):
                agg["first_frame"] = frame
            hashes = agg.get("scene_hashes", [])
            if isinstance(hashes, list) and scene_hash and scene_hash not in hashes and len(hashes) < 12:
                hashes.append(scene_hash)
            old_ratio = _parse_ratio(agg.get("unmapped_ratio_max")) or 0.0
            if float(unmapped_ratio) > old_ratio:
                agg["unmapped_ratio_max"] = float(round(unmapped_ratio, 4))
            if "UNMAPPED_GLYPHS" in review_flags:
                agg["blocked_unmapped_hits"] = int(parse_int(agg.get("blocked_unmapped_hits"), default=0) or 0) + 1

        if bool(is_human_text):
            agg_pure = dedup_pure_by_text.get(k)
            if agg_pure is None:
                dedup_pure_by_text[k] = {
                    "text": line,
                    "text_key": k,
                    "first_frame": frame,
                    "scene_hashes": [scene_hash] if scene_hash else [],
                    "hits": 1,
                    "unmapped_ratio_max": float(round(unmapped_ratio, 4)),
                    "blocked_unmapped_hits": 1 if "UNMAPPED_GLYPHS" in review_flags else 0,
                    "human_score_max": float(round(human_score, 4)),
                }
            else:
                agg_pure["hits"] = int(parse_int(agg_pure.get("hits"), default=0) or 0) + 1
                if frame < int(parse_int(agg_pure.get("first_frame"), default=frame) or frame):
                    agg_pure["first_frame"] = frame
                hashes = agg_pure.get("scene_hashes", [])
                if isinstance(hashes, list) and scene_hash and scene_hash not in hashes and len(hashes) < 12:
                    hashes.append(scene_hash)
                old_ratio_pure = _parse_ratio(agg_pure.get("unmapped_ratio_max")) or 0.0
                if float(unmapped_ratio) > old_ratio_pure:
                    agg_pure["unmapped_ratio_max"] = float(round(unmapped_ratio, 4))
                old_hscore = _parse_ratio(agg_pure.get("human_score_max")) or 0.0
                if float(human_score) > old_hscore:
                    agg_pure["human_score_max"] = float(round(human_score, 4))
                if "UNMAPPED_GLYPHS" in review_flags:
                    agg_pure["blocked_unmapped_hits"] = int(
                        parse_int(agg_pure.get("blocked_unmapped_hits"), default=0) or 0
                    ) + 1

    crc = str(
        crc32
        or meta.get("rom_crc32")
        or infer_crc_from_name(dyn_log_input_path.name)
        or infer_crc_from_name(str(dyn_log_input_path.parent))
        or "UNKNOWN000"
    ).upper()

    rows_clean.sort(
        key=lambda r: (
            int(parse_int(r.get("frame"), default=1 << 30) or (1 << 30)),
            str(r.get("scene_hash", "")),
            int(parse_int(r.get("line_idx"), default=0) or 0),
            str(r.get("line_key", "")),
        )
    )
    unique_rows = sorted(
        dedup_by_text.values(),
        key=lambda r: (
            str(r.get("text_key", "")),
            int(parse_int(r.get("first_frame"), default=1 << 30) or (1 << 30)),
            str(",".join(r.get("scene_hashes", [])[:1])),
        ),
    )
    unique_rows_pure = sorted(
        dedup_pure_by_text.values(),
        key=lambda r: (
            str(r.get("text_key", "")),
            int(parse_int(r.get("first_frame"), default=1 << 30) or (1 << 30)),
            str(",".join(r.get("scene_hashes", [])[:1])),
        ),
    )
    pure_fallback_applied = False
    if not unique_rows_pure and static_rows_for_diff:
        pure_fallback_applied = True
        unique_rows_pure = [
            {
                "text": str(r.get("text", "") or ""),
                "text_key": str(r.get("text_key", "") or ""),
                "first_frame": 0,
                "scene_hashes": ["STATIC_FALLBACK"],
                "hits": 1,
                "unmapped_ratio_max": 0.0,
                "blocked_unmapped_hits": 0,
                "human_score_max": 1.0,
            }
            for r in static_rows_for_diff
            if str(r.get("text", "") or "").strip()
        ]
        rows_clean_pure = [
            {
                "type": "dyn_text",
                "frame": 0,
                "scene_hash": "STATIC_FALLBACK",
                "line_idx": int(parse_int(r.get("idx"), default=0) or 0),
                "line": str(r.get("text", "") or ""),
                "line_key": str(r.get("text_key", "") or ""),
                "source": "static_fallback",
                "tile_row_hex": "",
                "nametable_base": "",
                "pattern_base": "",
                "glyph_hashes": [],
                "unmapped_tiles": [],
                "unmapped_glyph_hashes": [],
                "unknown_glyph_samples": [],
                "glyph_count": max(1, len(str(r.get("text", "") or ""))),
                "unmapped_glyph_count": 0,
                "unmapped_ratio": 0.0,
                "needs_review": False,
                "review_flags": [],
                "is_human_text": True,
                "human_score": 1.0,
            }
            for r in static_rows_for_diff
            if str(r.get("text", "") or "").strip()
        ]

    rom_size_int = int(max(0, int(parse_int(meta.get("rom_size"), default=0) or 0)))
    canonical_segments: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows_clean_pure):
        seg = _build_canonical_segment(
            idx=idx,
            row=row,
            crc=crc,
            rom_size=rom_size_int,
            supported_chars=set(supported_chars),
            ptbr_full_coverage=bool(coverage_proof.get("ptbr_full_coverage", False)),
        )
        structural_ok = _segment_structural_ok(seg, row)
        seg["structural_ok"] = bool(structural_ok)
        if not structural_ok:
            seg["status"] = "ABORTED_STRUCTURAL"
            if not seg.get("failure_reason"):
                seg["failure_reason"] = "structural_validation_failed"
        canonical_segments.append(seg)
    canonical_segments_valid = [seg for seg in canonical_segments if str(seg.get("status")) == "VALIDATED"]

    log_meta = {
        "type": "meta",
        "schema": "runtime_dyn_text_log.v2",
        "rom_crc32": crc,
        "rom_size": rom_size_int,
        "rows_total": int(len(rows_clean)),
        "rows_unique_text": int(len(unique_rows)),
        "rows_pure_total": int(len(rows_clean_pure)),
        "rows_unique_text_pure": int(len(unique_rows_pure)),
        "dropped_controls_count": int(dropped_controls),
        "dropped_empty_count": int(dropped_empty),
        "blocked_unmapped_glyphs_count": int(blocked_unmapped_glyphs_count),
        "unknown_glyph_hashes_total": int(len(unknown_hash_counter)),
        "unmapped_ratio_threshold": float(UNMAPPED_GLYPH_THRESHOLD),
        "pure_unmapped_ratio_threshold": float(PURE_UNMAPPED_GLYPH_THRESHOLD),
        "pure_fallback_applied": bool(pure_fallback_applied),
        "supported_glyphs": list(coverage_proof.get("supported_glyphs", [])),
        "missing_glyphs": list(coverage_proof.get("missing_glyphs", [])),
        "ptbr_full_coverage": bool(coverage_proof.get("ptbr_full_coverage", False)),
        "segments_total": int(len(canonical_segments)),
        "segments_validated": int(len(canonical_segments_valid)),
    }

    dyn_log_out = out_dir / f"{crc}_dyn_text_log.jsonl"
    dyn_log_pure_out = out_dir / f"{crc}_dyn_text_log_pure.jsonl"
    dyn_unique_out = out_dir / f"{crc}_dyn_text_unique.txt"
    dyn_unique_all_out = out_dir / f"{crc}_dyn_text_unique_all.txt"
    dyn_unique_pure_out = out_dir / f"{crc}_dyn_text_unique_pure.txt"
    pure_text_out = out_dir / f"{crc}_pure_text.jsonl"
    mapping_out = out_dir / f"{crc}_reinsertion_mapping.json"
    report_out = out_dir / f"{crc}_report.txt"
    proof_out = out_dir / f"{crc}_proof.json"
    write_jsonl(dyn_log_out, rows_clean, meta=log_meta)
    write_jsonl(
        dyn_log_pure_out,
        rows_clean_pure,
        meta={
            **log_meta,
            "schema": "runtime_dyn_text_log_pure.v1",
            "rows_total": int(len(rows_clean_pure)),
            "rows_unique_text": int(len(unique_rows_pure)),
        },
    )
    # Compatibilidade: dyn_text_unique.txt agora aponta para linhas puras.
    _write_text(dyn_unique_out, _render_unique_lines(unique_rows_pure))
    _write_text(dyn_unique_pure_out, _render_unique_lines(unique_rows_pure))
    # Auditoria: mantém visão completa separada.
    _write_text(dyn_unique_all_out, _render_unique_lines(unique_rows))

    bootstrap_paths = {
        "fontmap_bootstrap_path": None,
        "unknown_glyphs_jsonl_path": None,
        "unknown_glyphs_png_path": None,
    }
    if bootstrap_enabled:
        bootstrap_paths = _make_bootstrap(
            crc32=crc,
            rom_size=int(max(0, int(parse_int(meta.get("rom_size"), default=0) or 0))),
            out_dir=out_dir,
            unknown_hash_counter=unknown_hash_counter,
            hash_context=hash_context,
            hash_pattern=hash_pattern,
            current_fontmap_hash=mapped_hash_font,
        )

    coverage_result: Dict[str, Any] = {}
    coverage_pure_result: Dict[str, Any] = {}
    if static_rows_for_diff:
        coverage_result = _build_coverage_diff(
            crc32=crc,
            out_dir=out_dir,
            runtime_unique_rows=unique_rows,
            static_rows=static_rows_for_diff,
        )
        coverage_pure_result = _build_coverage_diff(
            crc32=crc,
            out_dir=out_dir,
            runtime_unique_rows=unique_rows_pure,
            static_rows=static_rows_for_diff,
            tag="pure",
        )

    accepted_segments = [seg for seg in canonical_segments if str(seg.get("status", "")) == "VALIDATED"]
    write_jsonl(
        pure_text_out,
        accepted_segments,
        meta={
            "type": "meta",
            "schema": "segment_canonical.v1",
            "rom_crc32": crc,
            "rom_size": rom_size_int,
            "segments_total": int(len(accepted_segments)),
            "validations": [
                "encoding_ok",
                "glyphs_ok",
                "tokens_ok",
                "terminator_ok",
                "layout_ok",
                "byte_length_ok",
                "offsets_ok",
                "pointers_ok",
            ],
        },
    )

    mapping_rows: List[Dict[str, Any]] = []
    for seg in canonical_segments:
        start = parse_int(seg.get("start_offset"), default=None)
        max_bytes = int(parse_int(seg.get("max_bytes"), default=0) or 0)
        payload_len = len(str(seg.get("renderable_text", "")).encode("utf-8", errors="replace"))
        final_offset = parse_int(seg.get("final_offset"), default=start)
        relocated = bool(
            final_offset is not None and start is not None and int(final_offset) != int(start)
        )
        mapping_rows.append(
            {
                "segment_id": seg.get("segment_id"),
                "original_offset": start,
                "final_offset": final_offset,
                "original_size": max_bytes,
                "final_size": payload_len,
                "relocated": relocated,
                "updated_pointers": int(parse_int(seg.get("updated_pointers"), default=0) or 0),
                "terminator_preserved": bool(seg.get("terminator_ok", False)),
                "tokens_preserved": bool(seg.get("tokens_ok", False)),
                "fallback_applied": bool(seg.get("fallback_applied", False)),
                "layout_ok": bool(seg.get("layout_ok", False)),
                "status": seg.get("status", "PENDING"),
                "failure_reason": seg.get("failure_reason", ""),
            }
        )
    write_json(mapping_out, mapping_rows)

    report_lines = [
        f"CRC32: {crc}",
        f"ROM_SIZE: {rom_size_int}",
        f"SEGMENTS_TOTAL: {len(canonical_segments)}",
        f"REINSERTED: {sum(1 for seg in canonical_segments if str(seg.get('status', '')).startswith('REINSERTED'))}",
        f"RELOCATED: {sum(1 for seg in canonical_segments if seg.get('final_offset') is not None and seg.get('start_offset') != seg.get('final_offset'))}",
        f"LAYOUT_OK: {sum(1 for seg in canonical_segments if bool(seg.get('layout_ok', False)))}",
        f"PTBR_FULL_COVERAGE: {1 if coverage_proof.get('ptbr_full_coverage', False) else 0}",
        f"FALLBACK_APPLIED: {sum(1 for seg in canonical_segments if bool(seg.get('fallback_applied', False)))}",
        f"ABORTED: {sum(1 for seg in canonical_segments if str(seg.get('status', '')).startswith('ABORTED'))}",
        "FAILURE_REASONS:",
    ]
    fail_counter: Counter[str] = Counter(
        str(seg.get("failure_reason", "") or "ok")
        for seg in canonical_segments
        if str(seg.get("failure_reason", "")).strip()
    )
    if fail_counter:
        for reason, hits in fail_counter.most_common():
            report_lines.append(f"- {reason}: {hits}")
    else:
        report_lines.append("- none")
    _write_text(report_out, report_lines)

    proof_payload = {
        "schema": "runtime_dyn_proof.v2",
        "rom_crc32": crc,
        "rom_size": rom_size_int,
        "charset_effective": "fontmap_runtime",
        "supported_glyphs": list(coverage_proof.get("supported_glyphs", [])),
        "missing_glyphs": list(coverage_proof.get("missing_glyphs", [])),
        "ptbr_full_coverage": bool(coverage_proof.get("ptbr_full_coverage", False)),
        "validations_executed": [
            "encoding_ok",
            "glyphs_ok",
            "tokens_ok",
            "terminator_ok",
            "layout_ok",
            "byte_length_ok",
            "offsets_ok",
            "pointers_ok",
            "structural_validation",
        ],
        "segments_processed": int(len(canonical_segments)),
        "failures": [
            {
                "segment_id": seg.get("segment_id"),
                "status": seg.get("status"),
                "failure_reason": seg.get("failure_reason", ""),
            }
            for seg in canonical_segments
            if str(seg.get("status", "")).startswith("ABORTED")
        ],
        "fallback_applied": int(sum(1 for seg in canonical_segments if bool(seg.get("fallback_applied", False)))),
        "artifacts": {
            "pure_text": str(pure_text_out),
            "reinsertion_mapping": str(mapping_out),
            "report": str(report_out),
        },
    }
    write_json(proof_out, proof_payload)
    proof_payload["artifacts"]["hashes"] = {
        "pure_text_sha256": hashlib.sha256(pure_text_out.read_bytes()).hexdigest(),
        "reinsertion_mapping_sha256": hashlib.sha256(mapping_out.read_bytes()).hexdigest(),
        "report_sha256": hashlib.sha256(report_out.read_bytes()).hexdigest(),
        "proof_sha256": hashlib.sha256(proof_out.read_bytes()).hexdigest(),
    }
    write_json(proof_out, proof_payload)

    result = {
        "rom_crc32": crc,
        "rom_size": int(max(0, int(parse_int(meta.get("rom_size"), default=0) or 0))),
        "dyn_text_log_path": str(dyn_log_out),
        "dyn_text_log_pure_path": str(dyn_log_pure_out),
        "dyn_text_unique_path": str(dyn_unique_out),
        "dyn_text_unique_pure_path": str(dyn_unique_pure_out),
        "dyn_text_unique_all_path": str(dyn_unique_all_out),
        "rows_total": int(len(rows_clean)),
        "rows_unique_text": int(len(unique_rows)),
        "rows_total_pure": int(len(rows_clean_pure)),
        "rows_unique_text_pure": int(len(unique_rows_pure)),
        "pure_fallback_applied": bool(pure_fallback_applied),
        "dropped_controls_count": int(dropped_controls),
        "dropped_empty_count": int(dropped_empty),
        "blocked_unmapped_glyphs_count": int(blocked_unmapped_glyphs_count),
        "unknown_glyph_hashes_total": int(len(unknown_hash_counter)),
        "supported_glyphs": list(coverage_proof.get("supported_glyphs", [])),
        "missing_glyphs": list(coverage_proof.get("missing_glyphs", [])),
        "ptbr_full_coverage": bool(coverage_proof.get("ptbr_full_coverage", False)),
        "pure_text_path": str(pure_text_out),
        "reinsertion_mapping_path": str(mapping_out),
        "report_path": str(report_out),
        "proof_path": str(proof_out),
        "segments_total": int(len(canonical_segments)),
        "segments_validated": int(len(accepted_segments)),
        "fontmap_bootstrap_path": str(bootstrap_paths.get("fontmap_bootstrap_path"))
        if bootstrap_paths.get("fontmap_bootstrap_path")
        else None,
        "unknown_glyphs_jsonl_path": str(bootstrap_paths.get("unknown_glyphs_jsonl_path"))
        if bootstrap_paths.get("unknown_glyphs_jsonl_path")
        else None,
        "unknown_glyphs_png_path": str(bootstrap_paths.get("unknown_glyphs_png_path"))
        if bootstrap_paths.get("unknown_glyphs_png_path")
        else None,
        "static_only_safe_by_offset_path": str(static_only_safe_by_offset) if static_only_safe_by_offset else None,
        "coverage": coverage_result,
        "coverage_pure": coverage_pure_result,
    }
    return result
