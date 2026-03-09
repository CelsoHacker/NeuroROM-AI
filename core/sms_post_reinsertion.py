# -*- coding: utf-8 -*-
"""
Patches pos-reinsercao por CRC (SMS).

Objetivo:
- aplicar hotfix binario deterministico por CRC32 + rom_size;
- validar readback dos offsets patchados;
- gerar prova auditavel em _historico;
- falhar de forma explicita quando um perfil esperado nao passar na validacao.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.rom_io import atomic_write_bytes, compute_checksums, ensure_parent_dir

_TOKEN_BYTE_RE = re.compile(r"\{([0-9A-Fa-f]{2})\}")


class PostPatchError(RuntimeError):
    """Erro controlado de patch pos-reinsercao."""


def _parse_int(value: Any, default: int = 0) -> int:
    if value is None:
        return int(default)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        raw = value.strip().lower()
        if not raw:
            return int(default)
        if raw.startswith("0x-"):
            raw = "-0x" + raw[3:]
        try:
            if raw.startswith(("-0x", "+0x")):
                sign = -1 if raw.startswith("-") else 1
                return sign * int(raw[3:], 16)
            if raw.startswith("0x"):
                return int(raw, 16)
            return int(raw, 10)
        except ValueError:
            return int(default)
    return int(default)


def _restore_common_ptbr_diacritics(text: str) -> str:
    """Restaura acentos comuns de PT-BR sem alterar tamanho textual."""
    if not isinstance(text, str) or not text:
        return ""

    replacements = {
        "nao": "não",
        "sao": "são",
        "estao": "estão",
        "entao": "então",
        "voce": "você",
        "voces": "vocês",
        "maos": "mãos",
        "tremulas": "trêmulas",
        "direcao": "direção",
        "direcoes": "direções",
        "opcao": "opção",
        "opcoes": "opções",
        "avanco": "avanço",
        "dificil": "difícil",
        "possivel": "possível",
        "musica": "música",
        "vitoria": "vitória",
        "justica": "justiça",
        "sacrificio": "sacrifício",
        "compaixao": "compaixão",
        "alem": "além",
        "ate": "até",
        "tambem": "também",
        "ja": "já",
        "ha": "há",
        "teras": "terás",
    }

    def _repl(match: re.Match) -> str:
        word = match.group(0)
        fixed = replacements.get(word.lower())
        if not fixed:
            return word
        if word.isupper():
            return fixed.upper()
        if word[:1].isupper():
            return fixed.capitalize()
        return fixed

    return re.sub(r"\b[A-Za-zÀ-ÿ]+\b", _repl, text)


def _encode_text_with_tokens(
    text: str,
    char_byte_map: Optional[Dict[str, int]] = None,
) -> bytes:
    def _fold_non_ascii_char(ch: str) -> str:
        if not ch:
            return " "
        normalized = unicodedata.normalize("NFD", ch)
        normalized = "".join(
            c for c in normalized if unicodedata.category(c) != "Mn"
        )
        normalized = (
            normalized.replace("“", "\"")
            .replace("”", "\"")
            .replace("‘", "'")
            .replace("’", "'")
            .replace("—", "-")
            .replace("–", "-")
            .replace("…", "...")
        )
        ascii_chars = [c for c in normalized if 32 <= ord(c) <= 126]
        return "".join(ascii_chars) if ascii_chars else " "

    if not isinstance(text, str):
        text = str(text)
    out = bytearray()
    cursor = 0
    for m in _TOKEN_BYTE_RE.finditer(text):
        if m.start() > cursor:
            chunk = text[cursor : m.start()]
            for ch in chunk:
                code = ord(ch)
                if 32 <= code <= 126:
                    out.append(code)
                    continue
                if char_byte_map and ch in char_byte_map:
                    out.append(int(char_byte_map[ch]) & 0xFF)
                    continue
                out.extend(_fold_non_ascii_char(ch).encode("ascii", errors="ignore"))
        out.append(int(m.group(1), 16))
        cursor = m.end()
    if cursor < len(text):
        tail = text[cursor:]
        for ch in tail:
            code = ord(ch)
            if 32 <= code <= 126:
                out.append(code)
                continue
            if char_byte_map and ch in char_byte_map:
                out.append(int(char_byte_map[ch]) & 0xFF)
                continue
            out.extend(_fold_non_ascii_char(ch).encode("ascii", errors="ignore"))
    return bytes(out)


def _load_profiles(profile_path: Path) -> List[Dict[str, Any]]:
    if not profile_path.exists():
        return []
    try:
        raw = json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, dict):
        return []
    rows = raw.get("profiles", [])
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _load_single_byte_tbl_map(tbl_path: Path) -> Dict[str, int]:
    """Carrega mapa de char->byte (1 byte) de uma .tbl."""
    mapping: Dict[str, int] = {}
    if not tbl_path.exists():
        return mapping
    try:
        lines = tbl_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return mapping

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        left, right = line.split("=", 1)
        key = left.strip().upper()
        value = right.strip()
        if len(key) != 2 or not re.fullmatch(r"[0-9A-F]{2}", key):
            continue
        if not value or len(value) != 1:
            continue
        try:
            mapping[value] = int(key, 16)
        except ValueError:
            continue
    return mapping


def _candidate_ptbr_tbl_paths(output_rom_path: Path, source_crc32: str) -> List[Path]:
    crc = str(source_crc32 or "").upper().strip()
    out = Path(output_rom_path)
    cands: List[Path] = []

    # Estrutura padrão: .../<CRC>/3_reinsercao/<rom>.sms
    crc_dir = out.parent.parent if out.parent.name.lower() == "3_reinsercao" else out.parent
    cands.append(crc_dir / "1_extracao" / f"{crc}_ptbr.tbl")
    cands.append(crc_dir / f"{crc}_ptbr.tbl")
    cands.append(crc_dir / "out" / crc / f"{crc}_ptbr.tbl")

    # Fallback por busca local no diretório do CRC
    try:
        cands.extend(sorted(crc_dir.glob("**/*_ptbr.tbl")))
    except Exception:
        pass

    # Remove duplicatas preservando ordem
    unique: List[Path] = []
    seen: set = set()
    for cand in cands:
        key = str(cand.resolve()) if cand.exists() else str(cand)
        if key in seen:
            continue
        seen.add(key)
        unique.append(cand)
    return unique


def _resolve_ptbr_tbl_single_byte_map(
    output_rom_path: Path,
    source_crc32: str,
) -> Tuple[Dict[str, int], Optional[str]]:
    for cand in _candidate_ptbr_tbl_paths(output_rom_path, source_crc32):
        if not cand.exists():
            continue
        mapping = _load_single_byte_tbl_map(cand)
        if mapping:
            return mapping, str(cand)
    return {}, None


def _select_profile(
    profiles: List[Dict[str, Any]],
    source_crc32: str,
    source_rom_size: int,
) -> Optional[Dict[str, Any]]:
    want_crc = str(source_crc32 or "").upper().strip()
    want_size = int(source_rom_size)
    for row in profiles:
        crc = str(row.get("source_crc32", "")).upper().strip()
        size = _parse_int(row.get("source_rom_size"), default=-1)
        if crc == want_crc and size == want_size:
            return row
    return None


def _op_expected_bytes(
    op: Dict[str, Any],
    char_byte_map: Optional[Dict[str, int]] = None,
    default_auto_accents: bool = False,
) -> Tuple[int, bytes]:
    kind = str(op.get("kind", "")).strip().lower()
    offset = _parse_int(op.get("offset"), default=-1)
    if offset < 0:
        raise PostPatchError(f"Operacao com offset invalido: {op.get('offset')}")

    if kind == "write_text":
        max_len = _parse_int(op.get("max_len"), default=0)
        if max_len <= 0:
            raise PostPatchError(f"write_text sem max_len valido em offset 0x{offset:X}")
        text_raw = str(op.get("text", ""))
        auto_accents = op.get("ptbr_auto_accents")
        if auto_accents is None:
            auto_accents = bool(default_auto_accents)
        if bool(auto_accents):
            text_raw = _restore_common_ptbr_diacritics(text_raw)
        payload = _encode_text_with_tokens(
            text_raw,
            char_byte_map=char_byte_map,
        )
        if len(payload) > max_len:
            raise PostPatchError(
                f"write_text excede max_len em 0x{offset:X}: payload={len(payload)} max_len={max_len}"
            )
        pad_byte = _parse_int(op.get("pad_byte"), default=0x20)
        if not (0 <= pad_byte <= 0xFF):
            raise PostPatchError(f"pad_byte invalido em 0x{offset:X}: {pad_byte}")
        expected = payload + bytes([pad_byte]) * (max_len - len(payload))
        return offset, expected

    if kind == "fill":
        length = _parse_int(op.get("length"), default=0)
        if length <= 0:
            raise PostPatchError(f"fill sem length valido em offset 0x{offset:X}")
        value = _parse_int(op.get("value"), default=0x20)
        if not (0 <= value <= 0xFF):
            raise PostPatchError(f"fill value invalido em 0x{offset:X}: {value}")
        return offset, bytes([value]) * length

    raise PostPatchError(f"Tipo de operacao nao suportado: {kind}")


def _slice_bytes(data: bytearray, offset: int, size: int) -> bytes:
    end = offset + size
    if offset < 0 or end > len(data):
        raise PostPatchError(
            f"Offset fora da ROM: off=0x{offset:X} size={size} rom_size={len(data)}"
        )
    return bytes(data[offset:end])


def _offset_in_ranges(offset: int, ranges: List[Tuple[int, int]]) -> bool:
    for start, end in ranges:
        if start <= offset < end:
            return True
    return False


def _run_validations(
    rom: bytearray,
    profile: Dict[str, Any],
    char_byte_map: Optional[Dict[str, int]] = None,
) -> List[str]:
    failures: List[str] = []
    validations = profile.get("validations", {})
    if not isinstance(validations, dict):
        return failures

    required_ascii = validations.get("required_ascii", [])
    if isinstance(required_ascii, list):
        for rule in required_ascii:
            if not isinstance(rule, dict):
                continue
            offset = _parse_int(rule.get("offset"), default=-1)
            text = str(rule.get("text", ""))
            if offset < 0 or not text:
                continue
            # Usa o mesmo encoder das operações para validar textos com chars PT-BR.
            needle = _encode_text_with_tokens(text, char_byte_map=char_byte_map)
            got = _slice_bytes(rom, offset, len(needle))
            if got != needle:
                failures.append(
                    f"required_ascii falhou em 0x{offset:X}: esperado={text!r} obtido={got.decode('latin-1', errors='replace')!r}"
                )

    forbidden_ascii = validations.get("forbidden_ascii", [])
    if isinstance(forbidden_ascii, list):
        for rule in forbidden_ascii:
            if not isinstance(rule, dict):
                continue
            offset = _parse_int(rule.get("offset"), default=-1)
            length = _parse_int(rule.get("length"), default=0)
            needles = rule.get("needles", [])
            if offset < 0 or length <= 0 or not isinstance(needles, list):
                continue
            chunk = _slice_bytes(rom, offset, length)
            for term in needles:
                if not isinstance(term, str) or not term:
                    continue
                needle = term.encode("latin-1", errors="ignore")
                if needle and chunk.find(needle) >= 0:
                    failures.append(
                        f"forbidden_ascii encontrou {term!r} em [0x{offset:X}, 0x{offset + length:X})"
                    )
    return failures


def _iter_ascii_runs(
    data: bytearray,
    start: int,
    end: int,
    min_len: int,
) -> List[Tuple[int, bytes]]:
    runs: List[Tuple[int, bytes]] = []
    cursor = int(start)
    run_start: Optional[int] = None

    while cursor < end:
        byte = data[cursor]
        printable = (32 <= byte <= 126) or byte == 0x01
        if printable and run_start is None:
            run_start = cursor
        if (not printable) and run_start is not None:
            if (cursor - run_start) >= min_len:
                runs.append((run_start, bytes(data[run_start:cursor])))
            run_start = None
        cursor += 1

    if run_start is not None and (end - run_start) >= min_len:
        runs.append((run_start, bytes(data[run_start:end])))
    return runs


def _marker_in_text(text_lower: str, marker_lower: str) -> bool:
    """
    Verifica marcador com preferência por limite de palavra para reduzir falso
    positivo (ex.: 'east' dentro de 'beast', 'camp' dentro de 'campo').
    """
    txt = str(text_lower or "").strip()
    mk = str(marker_lower or "").strip()
    if not txt or not mk:
        return False

    # Marcadores com espaço/símbolo relevante seguem por substring.
    if re.search(r"[^a-z0-9']", mk):
        return mk in txt

    # Marcador "palavra": aplica fronteira léxica simples.
    pattern = rf"(?<![a-z0-9']){re.escape(mk)}(?![a-z0-9'])"
    return bool(re.search(pattern, txt))


def _resolve_crc_root_from_output(out_path: Path) -> Path:
    """
    Resolve raiz de trabalho por CRC, considerando estrutura:
    <...>/<CRC>/3_reinsercao/<arquivo.sms>
    """
    p = Path(out_path)
    if p.parent.name.lower() == "3_reinsercao":
        return p.parent.parent
    return p.parent


def _merge_ranges(ranges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not ranges:
        return []
    ordered = sorted((int(a), int(b)) for a, b in ranges if int(b) > int(a))
    merged: List[Tuple[int, int]] = []
    cur_a, cur_b = ordered[0]
    for a, b in ordered[1:]:
        if a <= cur_b:
            cur_b = max(cur_b, b)
            continue
        merged.append((cur_a, cur_b))
        cur_a, cur_b = a, b
    merged.append((cur_a, cur_b))
    return merged


def _load_safe_scan_ranges_from_jsonl(
    out_path: Path,
    source_crc32: str,
    rom_size: int,
) -> Tuple[List[Tuple[int, int]], Optional[str]]:
    """
    Carrega faixas de auditoria a partir de JSONL (somente entradas reinsertion_safe).
    """
    crc = str(source_crc32 or "").upper().strip()
    root = _resolve_crc_root_from_output(out_path)
    candidates: List[Path] = []
    if crc:
        candidates.append(root / "2_traducao" / f"{crc}_translated.jsonl")
        candidates.append(root / "1_extracao" / f"{crc}_pure_text.jsonl")
    # Fallbacks genéricos (caso nome não siga padrão CRC).
    candidates.extend(sorted((root / "2_traducao").glob("*_translated.jsonl")) if (root / "2_traducao").exists() else [])
    candidates.extend(sorted((root / "1_extracao").glob("*_pure_text.jsonl")) if (root / "1_extracao").exists() else [])

    seen: set[str] = set()
    unique_candidates: List[Path] = []
    for cand in candidates:
        key = str(cand)
        if key in seen:
            continue
        seen.add(key)
        unique_candidates.append(cand)

    for cand in unique_candidates:
        if not cand.exists():
            continue
        ranges: List[Tuple[int, int]] = []
        try:
            for raw in cand.read_text(encoding="utf-8", errors="replace").splitlines():
                line = str(raw).strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if not isinstance(obj, dict):
                    continue
                rec_type = str(obj.get("type", obj.get("record_type", ""))).strip().lower()
                if rec_type == "meta" or bool(obj.get("meta")):
                    continue
                if obj.get("reinsertion_safe") is False:
                    continue
                off = _parse_int(obj.get("rom_offset", obj.get("offset")), default=-1)
                ln = _parse_int(
                    obj.get("max_len_bytes", obj.get("max_len", obj.get("max_length", obj.get("raw_len")))),
                    default=0,
                )
                if off < 0 or ln <= 0:
                    continue
                if off >= int(rom_size):
                    continue
                end = min(int(rom_size), off + ln)
                if end > off:
                    ranges.append((off, end))
        except Exception:
            continue

        merged = _merge_ranges(ranges)
        if merged:
            return merged, str(cand)
    return [], None


def _scan_residual_english(
    rom: bytearray,
    profile: Dict[str, Any],
    out_path: Path,
    source_crc32: str,
) -> Dict[str, Any]:
    cfg = profile.get("residual_english_audit", {})
    if not isinstance(cfg, dict):
        return {"enabled": False, "hits_count": 0, "pass": True}

    enabled = bool(cfg.get("enabled", False))
    if not enabled:
        return {"enabled": False, "hits_count": 0, "pass": True}

    # Permite varredura de strings curtas (>=4) para não ignorar entradas úteis.
    min_len = max(4, _parse_int(cfg.get("min_len"), default=20))
    min_hits = max(1, _parse_int(cfg.get("min_marker_hits"), default=2))
    max_items = max(20, _parse_int(cfg.get("max_report_items"), default=400))
    fail_on_hits = bool(cfg.get("fail_on_hits", False))
    max_allowed_hits = max(0, _parse_int(cfg.get("max_allowed_hits"), default=0))
    # Modo global opcional: exige ZERO ingles residual para aprovar.
    # Pode ser desligado via NEUROROM_ZERO_EN_REQUIRED=0.
    # Override por perfil (quando presente) tem prioridade.
    if "zero_en_required" in cfg:
        val = cfg.get("zero_en_required")
        if isinstance(val, str):
            zero_en_required = val.strip().lower() in {"1", "true", "yes", "on"}
        else:
            zero_en_required = bool(val)
    else:
        zero_en_required = str(os.environ.get("NEUROROM_ZERO_EN_REQUIRED", "1")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
    if zero_en_required:
        fail_on_hits = True
        max_allowed_hits = 0

    english_markers = [
        str(m).strip().lower()
        for m in (cfg.get("english_markers") or [])
        if isinstance(m, str) and str(m).strip()
    ]
    portuguese_markers = [
        str(m).strip().lower()
        for m in (cfg.get("portuguese_markers") or [])
        if isinstance(m, str) and str(m).strip()
    ]
    if not english_markers:
        english_markers = [
            "thou ",
            "the ",
            "he says:",
            "he asks:",
            "seek ",
            "virtue",
            "avatar",
            "castle",
            "britanni",
            "lorde britan",
        ]

    scan_mode = str(cfg.get("scan_mode", "ranges") or "ranges").strip().lower()
    scan_ranges: List[Tuple[int, int]] = []
    scan_ranges_source: Optional[str] = None

    if scan_mode in {"safe_spans", "safe_jsonl_spans"}:
        safe_ranges, source_path = _load_safe_scan_ranges_from_jsonl(
            out_path=out_path,
            source_crc32=source_crc32,
            rom_size=len(rom),
        )
        if safe_ranges:
            scan_ranges = safe_ranges
            scan_ranges_source = source_path

    if not scan_ranges:
        raw_ranges = cfg.get("scan_ranges", [])
        if isinstance(raw_ranges, list):
            for row in raw_ranges:
                if not isinstance(row, dict):
                    continue
                off = _parse_int(row.get("offset"), default=-1)
                length = _parse_int(row.get("length"), default=0)
                if off < 0 or length <= 0:
                    continue
                end = min(len(rom), off + length)
                if end > off:
                    scan_ranges.append((off, end))
        if not scan_ranges:
            scan_ranges = [(0, len(rom))]

    ignore_ranges: List[Tuple[int, int]] = []
    raw_ignore = cfg.get("ignore_ranges", [])
    if isinstance(raw_ignore, list):
        for row in raw_ignore:
            if not isinstance(row, dict):
                continue
            off = _parse_int(row.get("offset"), default=-1)
            length = _parse_int(row.get("length"), default=0)
            if off < 0 or length <= 0:
                continue
            end = min(len(rom), off + length)
            if end > off:
                ignore_ranges.append((off, end))

    def _inside_ignored(offset: int) -> bool:
        for start, end in ignore_ranges:
            if start <= offset < end:
                return True
        return False

    hits: List[Dict[str, Any]] = []
    for start, end in scan_ranges:
        for off, raw in _iter_ascii_runs(rom, start=start, end=end, min_len=min_len):
            if _inside_ignored(off):
                continue
            text = raw.decode("latin-1", errors="ignore").replace("\x01", " ")
            normalized = " ".join(text.split())
            lower = normalized.lower()
            english_hits = [m for m in english_markers if _marker_in_text(lower, m)]
            if len(english_hits) < min_hits:
                continue
            pt_hits = [m for m in portuguese_markers if _marker_in_text(lower, m)]
            if pt_hits and len(english_hits) <= len(pt_hits):
                continue
            hits.append(
                {
                    "offset": int(off),
                    "length": int(len(raw)),
                    "english_hits": english_hits,
                    "portuguese_hits": pt_hits,
                    "preview": normalized[:220],
                }
            )

    hits_sorted = sorted(hits, key=lambda row: int(row.get("offset", 0)))
    hits_count = len(hits_sorted)
    kept = hits_sorted[:max_items]

    history_dir = out_path.parent / "_historico"
    report_path = history_dir / f"{str(source_crc32).upper()}_residual_english_report.txt"
    report_json_path = history_dir / f"{str(source_crc32).upper()}_residual_english_report.json"
    ensure_parent_dir(report_path)
    ensure_parent_dir(report_json_path)

    lines: List[str] = []
    lines.append("RELATORIO DE INGLES RESIDUAL POS-REINSERCAO")
    lines.append(f"rom={out_path}")
    lines.append(f"hits_total={hits_count}")
    lines.append(f"scan_ranges={len(scan_ranges)}")
    if scan_ranges_source:
        lines.append(f"scan_ranges_source={scan_ranges_source}")
    lines.append(f"min_len={min_len} min_marker_hits={min_hits}")
    lines.append("")
    for row in kept:
        off = int(row["offset"])
        lines.append(
            f"offset=0x{off:06X} len={row['length']} markers={','.join(row['english_hits'][:6])} :: {row['preview']}"
        )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    report_json_path.write_text(
        json.dumps(
            {
                "type": "sms_residual_english_audit",
                "schema": "neurorom.sms.residual_english_audit.v1",
                "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "rom_path": str(out_path),
                "hits_total": hits_count,
                "min_len": min_len,
                "min_marker_hits": min_hits,
                "max_items": max_items,
                "scan_mode": scan_mode,
                "scan_ranges_source": scan_ranges_source,
                "scan_ranges": [
                    {"offset": f"0x{start:X}", "length": int(end - start)}
                    for start, end in scan_ranges
                ],
                "ignore_ranges": [
                    {"offset": f"0x{start:X}", "length": int(end - start)}
                    for start, end in ignore_ranges
                ],
                "hits": kept,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    passed = True
    if fail_on_hits and hits_count > max_allowed_hits:
        passed = False
    return {
        "enabled": True,
        "pass": bool(passed),
        "hits_count": int(hits_count),
        "max_allowed_hits": int(max_allowed_hits),
        "fail_on_hits": bool(fail_on_hits),
        "zero_en_required": bool(zero_en_required),
        "report_path": str(report_path),
        "report_json_path": str(report_json_path),
    }


def apply_sms_post_reinsertion_patches(
    source_crc32: str,
    source_rom_size: int,
    output_rom_path: Path,
    profile_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Aplica patch pos-reinsercao por CRC de origem.

    Retorna resumo estruturado. Se perfil existir e validacao falhar, dispara PostPatchError.
    """
    if profile_path is None:
        profile_path = Path(__file__).resolve().parent / "profiles" / "sms" / "post_reinsertion_crc_profiles.json"

    out_path = Path(output_rom_path)
    if not out_path.exists():
        raise PostPatchError(f"ROM de saida nao encontrada para pos-patch: {out_path}")

    profiles = _load_profiles(profile_path)
    selected = _select_profile(
        profiles=profiles,
        source_crc32=str(source_crc32).upper().strip(),
        source_rom_size=int(source_rom_size),
    )
    if not selected:
        return {
            "matched_profile": False,
            "profile_id": None,
            "changed": False,
            "changed_bytes": 0,
            "proof_path": None,
        }

    rom = bytearray(out_path.read_bytes())
    if len(rom) != int(source_rom_size):
        raise PostPatchError(
            f"Tamanho de ROM divergente no pos-patch: esperado={source_rom_size} atual={len(rom)}"
        )

    tbl_single_byte_map, tbl_path_used = _resolve_ptbr_tbl_single_byte_map(
        output_rom_path=out_path,
        source_crc32=str(source_crc32).upper().strip(),
    )

    before_crc32, before_sha256 = compute_checksums(bytes(rom))
    op_results: List[Dict[str, Any]] = []
    changed_bytes = 0

    operations = selected.get("operations", [])
    if not isinstance(operations, list) or not operations:
        raise PostPatchError(f"Perfil {selected.get('id')} sem operacoes.")
    auto_accents_default = bool(selected.get("ptbr_auto_accents_default", False))
    auto_accents_exclude_ranges: List[Tuple[int, int]] = []
    raw_exclude = selected.get("ptbr_auto_accents_exclude_ranges", [])
    if isinstance(raw_exclude, list):
        for row in raw_exclude:
            if not isinstance(row, dict):
                continue
            ex_off = _parse_int(row.get("offset"), default=-1)
            ex_len = _parse_int(row.get("length"), default=0)
            if ex_off < 0 or ex_len <= 0:
                continue
            ex_end = min(len(rom), ex_off + ex_len)
            if ex_end > ex_off:
                auto_accents_exclude_ranges.append((ex_off, ex_end))

    for idx, op in enumerate(operations, start=1):
        if not isinstance(op, dict):
            continue
        op_effective = op
        if auto_accents_default and auto_accents_exclude_ranges and "ptbr_auto_accents" not in op:
            op_offset = _parse_int(op.get("offset"), default=-1)
            if op_offset >= 0 and _offset_in_ranges(op_offset, auto_accents_exclude_ranges):
                op_effective = dict(op)
                op_effective["ptbr_auto_accents"] = False
        offset, expected = _op_expected_bytes(
            op_effective,
            char_byte_map=tbl_single_byte_map,
            default_auto_accents=auto_accents_default,
        )
        before = _slice_bytes(rom, offset, len(expected))
        changed = before != expected
        if changed:
            rom[offset : offset + len(expected)] = expected
            changed_bytes += len(expected)
        readback = _slice_bytes(rom, offset, len(expected))
        if readback != expected:
            raise PostPatchError(f"Readback falhou em op#{idx} offset=0x{offset:X}")
        op_results.append(
            {
                "index": idx,
                "kind": str(op.get("kind", "")),
                "offset": f"0x{offset:X}",
                "size": len(expected),
                "changed": bool(changed),
            }
        )

    failures = _run_validations(rom, selected, char_byte_map=tbl_single_byte_map)
    if failures:
        raise PostPatchError(
            "Validacao do pos-patch falhou: " + " | ".join(failures[:6])
        )

    residual_audit = _scan_residual_english(
        rom=rom,
        profile=selected,
        out_path=out_path,
        source_crc32=str(source_crc32).upper(),
    )
    if residual_audit.get("enabled") and not residual_audit.get("pass", True):
        raise PostPatchError(
            "Auditoria residual detectou ingles acima do limite: "
            f"hits={residual_audit.get('hits_count')} "
            f"limite={residual_audit.get('max_allowed_hits')}. "
            f"Relatorio={residual_audit.get('report_path')}"
        )

    changed = bytes(rom) != out_path.read_bytes()
    if changed:
        ensure_parent_dir(out_path)
        atomic_write_bytes(out_path, bytes(rom))

    after_crc32, after_sha256 = compute_checksums(bytes(rom))
    history_dir = out_path.parent / "_historico"
    proof_path = history_dir / f"{str(source_crc32).upper()}_auto_postpatch_proof.json"
    ensure_parent_dir(proof_path)

    profile_bytes = profile_path.read_bytes() if profile_path.exists() else b""
    proof = {
        "type": "sms_post_reinsertion_patch_proof",
        "schema": "neurorom.sms.post_reinsertion_patch_proof.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_identity": {
            "rom_crc32": str(source_crc32).upper(),
            "rom_size": int(source_rom_size),
        },
        "output_rom_path": str(out_path),
        "profile": {
            "id": selected.get("id"),
            "description": selected.get("description"),
            "profile_path": str(profile_path),
            "profile_sha256": hashlib.sha256(profile_bytes).hexdigest() if profile_bytes else None,
            "operations_total": len(op_results),
            "ptbr_tbl_path": tbl_path_used,
            "ptbr_tbl_single_byte_chars": int(len(tbl_single_byte_map)),
        },
        "checksums": {
            "before": {
                "crc32": str(before_crc32).upper(),
                "sha256": before_sha256,
                "size": len(rom),
            },
            "after": {
                "crc32": str(after_crc32).upper(),
                "sha256": after_sha256,
                "size": len(rom),
            },
        },
        "changed": bool(changed),
        "changed_bytes": int(changed_bytes),
        "operations": op_results,
        "validation_failures": [],
        "residual_english_audit": residual_audit,
    }
    proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "matched_profile": True,
        "profile_id": selected.get("id"),
        "changed": bool(changed),
        "changed_bytes": int(changed_bytes),
        "proof_path": str(proof_path),
        "crc32_after": str(after_crc32).upper(),
        "sha256_after": after_sha256,
        "residual_english_audit": residual_audit,
    }
