#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrige/normaliza JSONL traduzido para reinsercao:
- Se houver mapping: gera JSONL a partir do reinsertion_mapping (fonte da verdade).
- Garante presença de offset (int) e offset_hex (string).
- Padroniza campo de traducao como "translated".
- (Opcional) Sanitiza para ASCII removendo acentos, preservando tokens/placeholder.
- Gera report e proof auditaveis no padrao {CRC32}_*.txt/.json.

Nao faz scan da ROM: usa a ROM apenas para calcular CRC32 e tamanho.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ---------------------------
# Utilitários de ROM
# ---------------------------

def compute_crc32_and_size(rom_path: Path) -> Tuple[str, int]:
    """Calcula CRC32 (hex uppercase, 8 chars) e tamanho em bytes."""
    data = rom_path.read_bytes()
    crc = zlib.crc32(data) & 0xFFFFFFFF
    return f"{crc:08X}", len(data)


# ---------------------------
# JSON / JSONL
# ---------------------------

def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Lê JSONL (1 objeto JSON por linha). Linhas vazias são ignoradas."""
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    obj["_line"] = i  # útil no report
                    out.append(obj)
                else:
                    out.append({"_line": i, "_raw": obj})
            except json.JSONDecodeError:
                out.append({"_line": i, "_json_error": True, "_raw_line": line})
    return out


def write_jsonl(path: Path, records: Iterable[Dict[str, Any]]) -> None:
    """Escreve JSONL com UTF-8."""
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_mapping_items(mapping_path: Optional[Path]) -> List[Dict[str, Any]]:
    """Carrega lista de itens do reinsertion_mapping.json (vários formatos)."""
    if mapping_path is None:
        return []

    obj = json.loads(mapping_path.read_text(encoding="utf-8"))
    items: List[Dict[str, Any]] = []

    if isinstance(obj, dict):
        if isinstance(obj.get("mappings"), list):
            items = [x for x in obj["mappings"] if isinstance(x, dict)]
        elif isinstance(obj.get("items"), list):
            items = [x for x in obj["items"] if isinstance(x, dict)]
        elif isinstance(obj.get("text_blocks"), list):
            items = [x for x in obj["text_blocks"] if isinstance(x, dict)]
        elif isinstance(obj.get("entries"), dict):
            items = [x for x in obj["entries"].values() if isinstance(x, dict)]
        else:
            # fallback: tenta valores dict
            for v in obj.values():
                if isinstance(v, dict):
                    items.append(v)
    elif isinstance(obj, list):
        items = [x for x in obj if isinstance(x, dict)]

    return items


def load_mapping_offsets(mapping_path: Optional[Path]) -> Dict[int, Dict[str, Any]]:
    """
    Carrega offsets de um reinsertion_mapping.json (vários formatos).
    Retorna dict: offset_int -> item.
    """
    items = load_mapping_items(mapping_path)
    out: Dict[int, Dict[str, Any]] = {}
    for it in items:
        off = best_effort_get_offset(it)
        if off is not None:
            out[off] = it
    return out


# ---------------------------
# Heurísticas de campos
# ---------------------------

OFFSET_KEYS = (
    "offset",
    "offset_int",
    "start_offset",
    "addr",
    "address",
    "pos",
    "at",
    "off",
    "target_offset",
    "origin_offset",
    "static_offset",
)
OFFSET_HEX_KEYS = ("offset_hex", "start_offset_hex", "addr_hex", "address_hex", "off_hex")

TRANSLATION_KEYS = (
    "text_dst",
    "translated",
    "translation",
    "text_translated",
    "translated_text",
    "pt",
    "pt_br",
    "target",
    "target_text",
    "out",
    "output",
)

SOURCE_KEYS = ("original", "source", "src", "text", "src_text", "original_text", "text_src")


def best_effort_get_offset(obj: Dict[str, Any]) -> Optional[int]:
    """
    Extrai offset como int.
    Aceita: int, "0x1A2B", "001A2B", "1A2B" (hex), ou decimal string.
    """
    # 1) se existir int direto
    for k in OFFSET_KEYS:
        if k in obj and isinstance(obj[k], int):
            return obj[k]

    # 2) se existir hex string
    for k in OFFSET_HEX_KEYS:
        v = obj.get(k)
        if isinstance(v, str):
            s = v.strip().lower()
            if s.startswith("0x"):
                s = s[2:]
            # se parece hex
            if re.fullmatch(r"[0-9a-f]{1,8}", s):
                return int(s, 16)

    # 3) strings em outras chaves
    for k in OFFSET_KEYS:
        v = obj.get(k)
        if isinstance(v, str):
            s = v.strip().lower()
            if s.startswith("0x"):
                s = s[2:]
            # hex puro
            if re.fullmatch(r"[0-9a-f]{1,8}", s):
                return int(s, 16)
            # decimal puro
            if re.fullmatch(r"\d{1,10}", s):
                return int(s, 10)

    return None


def best_effort_get_translation(obj: Dict[str, Any]) -> Optional[str]:
    """Pega texto traduzido com base em chaves comuns."""
    for k in TRANSLATION_KEYS:
        v = obj.get(k)
        if isinstance(v, str):
            return v
    return None


def best_effort_get_source(obj: Dict[str, Any]) -> Optional[str]:
    """Pega texto fonte/original (se existir)."""
    for k in SOURCE_KEYS:
        v = obj.get(k)
        if isinstance(v, str):
            return v
    return None


def _parse_hex_int(value: Any) -> Optional[int]:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        s = value.strip().lower()
        if s.startswith("0x"):
            s = s[2:]
        if re.fullmatch(r"[0-9a-f]{1,8}", s):
            return int(s, 16)
    return None


def normalize_mapping_items(items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Normaliza itens do mapping:
    Retorna (items_normalizados, items_com_erro).
    """
    normalized: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for it in items:
        off = best_effort_get_offset(it)
        if off is None:
            errors.append({"reason": "MISSING_OFFSET", "raw": it})
            continue

        src = best_effort_get_source(it)
        if src is None:
            src = ""

        max_len = it.get("max_len_bytes") or it.get("max_bytes") or it.get("max_length") or it.get("max_len")
        if isinstance(max_len, str) and max_len.strip().isdigit():
            max_len = int(max_len.strip())

        term = it.get("terminator")
        if term is None and it.get("terminator_hex") is not None:
            term = _parse_hex_int(it.get("terminator_hex"))

        normalized.append({
            "id": it.get("id") or it.get("uid"),
            "offset": int(off),
            "offset_hex": f"0x{int(off):06X}",
            "original": src,
            "translated": None,
            "encoding": it.get("encoding"),
            "max_len_bytes": max_len,
            "terminator": term,
        })

    return normalized, errors


def build_translated_from_mapping(
    mapping_items: List[Dict[str, Any]],
    translated_records: List[Dict[str, Any]],
    ascii_sanitize: bool = False,
    replace_unknown_with: str = "?",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    """
    Gera JSONL final a partir do mapping (fonte da verdade) e um JSONL de traducoes.
    Retorna: (records_saida, report, errors)
    """
    # Indexa traducoes por id e por offset
    translations_by_id: Dict[str, str] = {}
    translations_by_offset: Dict[int, str] = {}
    missing_translation_lines: List[Dict[str, Any]] = []
    offset_not_in_mapping_lines: List[Dict[str, Any]] = []

    mapping_offsets = {it["offset"] for it in mapping_items if isinstance(it.get("offset"), int)}

    for obj in translated_records:
        if not isinstance(obj, dict) or obj.get("_json_error"):
            continue
        line_no = obj.get("_line")
        tr = best_effort_get_translation(obj)
        if not isinstance(tr, str) or not tr.strip():
            missing_translation_lines.append({
                "line": line_no,
                "offset": best_effort_get_offset(obj),
                "id": obj.get("id") or obj.get("uid"),
            })
            continue

        off = best_effort_get_offset(obj)
        if off is not None and off not in mapping_offsets:
            offset_not_in_mapping_lines.append({
                "line": line_no,
                "offset": off,
            })

        key_id = obj.get("id") or obj.get("uid")
        if key_id is not None:
            translations_by_id[str(key_id)] = tr.strip()
        if off is not None:
            translations_by_offset[int(off)] = tr.strip()

    missing_translation_for_mapping: List[Dict[str, Any]] = []
    ascii_changed = 0
    out_records: List[Dict[str, Any]] = []

    for it in sorted(mapping_items, key=lambda x: x["offset"]):
        tr = None
        if it.get("id") is not None:
            tr = translations_by_id.get(str(it["id"]))
        if tr is None:
            tr = translations_by_offset.get(it["offset"])

        if tr is None or not tr.strip():
            missing_translation_for_mapping.append({
                "offset": it["offset"],
                "offset_hex": it["offset_hex"],
                "id": it.get("id"),
            })
            continue

        tr_final = tr.strip()
        if ascii_sanitize:
            sanitize_info = latinize_to_ascii_keep_tokens(tr_final, replace_unknown_with=replace_unknown_with)
            tr_final = sanitize_info.text
            if sanitize_info.changed:
                ascii_changed += 1

        rec = {
            "offset": it["offset"],
            "offset_hex": it["offset_hex"],
            "original": it.get("original", ""),
            "translated": tr_final,
        }

        if it.get("id") is not None:
            rec["id"] = it["id"]
        if it.get("encoding") is not None:
            rec["encoding"] = it["encoding"]
        if it.get("max_len_bytes") is not None:
            rec["max_len_bytes"] = it["max_len_bytes"]
        if it.get("terminator") is not None:
            rec["terminator"] = it["terminator"]

        out_records.append(rec)

    stats = {
        "mapping_total": len(mapping_items),
        "missing_translation_lines": len(missing_translation_lines),
        "offset_not_in_mapping": len(offset_not_in_mapping_lines),
        "missing_translation_for_mapping": len(missing_translation_for_mapping),
        "ascii_changed": ascii_changed,
        "output_lines": len(out_records),
    }

    report = {
        "stats": stats,
        "missing_translation_lines": missing_translation_lines,
        "offset_not_in_mapping_lines": offset_not_in_mapping_lines,
        "missing_translation_for_mapping": missing_translation_for_mapping,
    }

    errors = {
        "missing_translation_lines": missing_translation_lines,
        "offset_not_in_mapping_lines": offset_not_in_mapping_lines,
        "missing_translation_for_mapping": missing_translation_for_mapping,
    }

    return out_records, report, errors


# ---------------------------
# Sanitização (ASCII) preservando tokens
# ---------------------------

# Tokens preservados: {...} <...> [...]
TOKEN_RE = re.compile(r"(\{[^}]*\}|<[^>]*>|\[[^\]]*\])")

@dataclass
class SanitizeResult:
    text: str
    changed: bool
    removed_chars: List[str]


def latinize_to_ascii_keep_tokens(s: str, replace_unknown_with: str = "?") -> SanitizeResult:
    """
    Remove acentos e força ASCII, sem alterar tokens/placeholder.
    - Segmentos que NÃO são tokens passam por NFKD e filtragem ASCII.
    - Caracteres não-ASCII que sumiriam são substituídos por replace_unknown_with (por padrão "?")
      para evitar apagar conteúdo silenciosamente demais.
    """
    removed: List[str] = []

    def latinize_segment(seg: str) -> str:
        # Normaliza e separa diacríticos
        nfkd = unicodedata.normalize("NFKD", seg)
        out_chars: List[str] = []
        for ch in nfkd:
            o = ord(ch)
            if o < 128:
                out_chars.append(ch)
            else:
                removed.append(ch)
                out_chars.append(replace_unknown_with)
        return "".join(out_chars)

    parts = TOKEN_RE.split(s)
    rebuilt: List[str] = []
    for part in parts:
        if not part:
            continue
        if TOKEN_RE.fullmatch(part):
            # token intacto
            rebuilt.append(part)
        else:
            rebuilt.append(latinize_segment(part))

    out = "".join(rebuilt)
    return SanitizeResult(text=out, changed=(out != s), removed_chars=removed)


# ---------------------------
# Normalização + Report
# ---------------------------

def normalize_records(
    records: List[Dict[str, Any]],
    mapping_by_offset: Dict[int, Dict[str, Any]],
    ascii_sanitize: bool,
    replace_unknown_with: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Normaliza cada linha:
    - Garante offset/offset_hex se possível
    - Garante campos de tradução redundantes para compatibilidade
    - (Opcional) sanitiza tradução para ASCII preservando tokens
    - Produz estatísticas e provas (proof)
    """
    stats = {
        "total_lines": len(records),
        "json_errors": 0,
        "missing_translation": 0,
        "missing_offset": 0,
        "offset_not_in_mapping": 0,
        "ascii_changed": 0,
        "ok_candidates": 0,
    }

    proof_items: List[Dict[str, Any]] = []
    out_records: List[Dict[str, Any]] = []

    for obj in records:
        line_no = obj.get("_line")

        if obj.get("_json_error"):
            stats["json_errors"] += 1
            out_records.append(obj)
            proof_items.append({
                "line": line_no,
                "status": "JSON_ERROR",
            })
            continue

        if not isinstance(obj, dict):
            out_records.append(obj)
            continue

        off = best_effort_get_offset(obj)
        tr = best_effort_get_translation(obj)
        src = best_effort_get_source(obj)

        if tr is None:
            stats["missing_translation"] += 1

        if off is None:
            stats["missing_offset"] += 1

        # se tem mapping, checa se offset está lá
        in_mapping = True
        if mapping_by_offset and off is not None:
            in_mapping = (off in mapping_by_offset)
            if not in_mapping:
                stats["offset_not_in_mapping"] += 1

        # Sanitização ASCII
        tr_fixed = tr
        sanitize_info = None
        if tr is not None and ascii_sanitize:
            sanitize_info = latinize_to_ascii_keep_tokens(tr, replace_unknown_with=replace_unknown_with)
            tr_fixed = sanitize_info.text
            if sanitize_info.changed:
                stats["ascii_changed"] += 1

        # Cria um objeto "compat" (sem remover campos originais)
        new_obj = dict(obj)  # cópia
        if off is not None:
            new_obj["offset"] = int(off)
            new_obj["offset_hex"] = f"0x{off:06X}"

        if tr_fixed is not None:
            # redundância de campos para aumentar compatibilidade com reinserters diferentes
            new_obj["translated"] = tr_fixed
            new_obj["text_translated"] = tr_fixed
            new_obj["translated_text"] = tr_fixed
            new_obj["pt_br"] = tr_fixed

        # Ajuste: manter fonte/original se existir
        if src is not None:
            new_obj["original"] = src

        # status para report/proof
        status = "OK"
        if tr is None:
            status = "MISSING_TRANSLATION"
        elif off is None:
            status = "MISSING_OFFSET"
        elif mapping_by_offset and not in_mapping:
            status = "OFFSET_NOT_IN_MAPPING"

        out_records.append(new_obj)

        proof_items.append({
            "line": line_no,
            "status": status,
            "offset": off,
            "offset_hex": (f"0x{off:06X}" if isinstance(off, int) else None),
            "in_mapping": (None if not mapping_by_offset else in_mapping),
            "source": src,
            "translated_in": tr,
            "translated_out": tr_fixed,
            "ascii_sanitize": bool(ascii_sanitize),
            "removed_chars_sample": (sanitize_info.removed_chars[:20] if sanitize_info else []),
        })

        if status == "OK":
            stats["ok_candidates"] += 1

    report = {
        "stats": stats,
        "field_hints": {
            "offset_keys_seen": sorted(list({k for r in records if isinstance(r, dict) for k in r.keys() if k in OFFSET_KEYS or k in OFFSET_HEX_KEYS})),
            "translation_keys_seen": sorted(list({k for r in records if isinstance(r, dict) for k in r.keys() if k in TRANSLATION_KEYS})),
        },
        "proof_items": proof_items,
    }

    return out_records, report


def write_report_txt(path: Path, crc32: str, rom_size: int, report: Dict[str, Any]) -> None:
    """Escreve um report humano (txt) com contagens e dicas."""
    s = report["stats"]
    hints = report.get("field_hints", {})
    lines: List[str] = []
    lines.append(f"[ROM] CRC32={crc32} ROM_SIZE={rom_size}")
    lines.append("[JSONL] normalize_translated_jsonl_for_reinsertion")
    lines.append("")
    lines.append("[STATS]")
    lines.append(f"  total_lines={s.get('total_lines', 0)}")
    lines.append(f"  json_errors={s.get('json_errors', 0)}")
    lines.append(f"  missing_translation={s.get('missing_translation', s.get('missing_translation_lines', 0))}")
    lines.append(f"  missing_offset={s.get('missing_offset', 0)}")
    lines.append(f"  offset_not_in_mapping={s.get('offset_not_in_mapping', 0)}")
    lines.append(f"  ascii_changed={s.get('ascii_changed', 0)}")
    lines.append(f"  ok_candidates={s.get('ok_candidates', 0)}")
    if "mapping_total" in s:
        lines.append(f"  mapping_total={s.get('mapping_total', 0)}")
        lines.append(f"  missing_translation_for_mapping={s.get('missing_translation_for_mapping', 0)}")
        lines.append(f"  output_lines={s.get('output_lines', 0)}")
    lines.append("")
    lines.append("[HINTS]")
    lines.append(f"  offset_keys_seen={hints.get('offset_keys_seen', [])}")
    lines.append(f"  translation_keys_seen={hints.get('translation_keys_seen', [])}")
    lines.append("")
    lines.append("[NEXT]")
    lines.append("  - Se missing_offset>0 ou missing_translation>0, o reinserter vai ignorar itens.")
    lines.append("  - Se ascii_changed>0, havia caracteres fora do ASCII (acentos etc).")
    lines.append("  - Use o JSONL gerado por este script na reinserção.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------
# CLI
# ---------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Normaliza/gera JSONL traduzido para reinserção (fonte da verdade: mapping)."
    )
    ap.add_argument("--rom", required=True, help="Caminho da ROM usada (apenas para CRC32/tamanho).")
    ap.add_argument("--translated", required=True, help="JSONL traduzido de entrada.")
    ap.add_argument("--mapping", default=None, help="reinsertion_mapping.json (opcional, para checar offsets).")
    ap.add_argument("--out-jsonl", default=None, help="Saída JSONL normalizada (default: out/{CRC32}_translated.jsonl).")
    ap.add_argument("--ascii-sanitize", action="store_true", help="Remove acentos/força ASCII preservando tokens.")
    ap.add_argument("--replace-unknown-with", default="?", help="Substituto para chars não-ASCII (default: '?').")
    ap.add_argument("--out-dir", default="out", help="Diretório de saída (default: out).")

    args = ap.parse_args()

    rom_path = Path(args.rom)
    tr_path = Path(args.translated)
    mapping_path = Path(args.mapping) if args.mapping else None
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    crc32, rom_size = compute_crc32_and_size(rom_path)

    records = read_jsonl(tr_path)
    mapping_items_raw = load_mapping_items(mapping_path)

    if mapping_path is not None and mapping_items_raw:
        mapping_items, mapping_errors = normalize_mapping_items(mapping_items_raw)
        if mapping_errors:
            print("[ERROR] mapping sem offset válido em alguns itens. Corrija o mapping.")
            return 2

        fixed_records, report, errors = build_translated_from_mapping(
            mapping_items=mapping_items,
            translated_records=records,
            ascii_sanitize=bool(args.ascii_sanitize),
            replace_unknown_with=str(args.replace_unknown_with),
        )

        out_report_txt = out_dir / f"{crc32}_report.txt"
        out_proof_json = out_dir / f"{crc32}_proof.json"
        write_report_txt(out_report_txt, crc32, rom_size, report)
        out_proof_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        if errors["missing_translation_lines"]:
            print("[ERROR] Ha linhas sem traducao no JSONL de entrada.")
            for e in errors["missing_translation_lines"][:50]:
                off = e.get("offset")
                off_hex = f"0x{off:06X}" if isinstance(off, int) else "N/A"
                print(f"  line={e.get('line')} offset={off_hex}")
            print(f"[OUT] report={out_report_txt.name}")
            print(f"[OUT] proof={out_proof_json.name}")
            return 2

        if errors["offset_not_in_mapping_lines"]:
            print("[ERROR] Offsets do JSONL que nao existem no mapping.")
            for e in errors["offset_not_in_mapping_lines"][:50]:
                off = e.get("offset")
                off_hex = f"0x{off:06X}" if isinstance(off, int) else "N/A"
                print(f"  line={e.get('line')} offset={off_hex}")
            print(f"[OUT] report={out_report_txt.name}")
            print(f"[OUT] proof={out_proof_json.name}")
            return 2

        if errors["missing_translation_for_mapping"]:
            print("[ERROR] Faltam traducoes para itens do mapping.")
            for e in errors["missing_translation_for_mapping"][:50]:
                print(f"  offset={e.get('offset_hex')} id={e.get('id')}")
            print(f"[OUT] report={out_report_txt.name}")
            print(f"[OUT] proof={out_proof_json.name}")
            return 2

        fixed_records_sorted: List[Dict[str, Any]] = []
        for seq, rec in enumerate(sorted(fixed_records, key=lambda x: int(x.get("offset", 0) or 0))):
            out_rec = dict(rec)
            off = int(out_rec.get("offset", 0) or 0)
            out_rec["seq"] = int(seq)
            out_rec["offset"] = int(off)
            out_rec["offset_hex"] = f"0x{off:06X}"
            out_rec["rom_offset"] = f"0x{off:06X}"
            out_rec["rom_crc32"] = crc32
            out_rec["rom_size"] = int(rom_size)
            fixed_records_sorted.append(out_rec)

        out_jsonl = Path(args.out_jsonl) if args.out_jsonl else (out_dir / f"{crc32}_translated.jsonl")
        meta_header = {
            "type": "meta",
            "schema": "neurorom.translated_jsonl.v2",
            "rom_crc32": crc32,
            "rom_size": int(rom_size),
            "ordering": "seq/rom_offset",
        }
        write_jsonl(out_jsonl, [meta_header] + fixed_records_sorted)

        print(f"[OK] CRC32={crc32} ROM_SIZE={rom_size}")
        print(f"[OUT] translated_jsonl={out_jsonl.name}")
        print(f"[OUT] report={out_report_txt.name}")
        print(f"[OUT] proof={out_proof_json.name}")
        return 0

    # Fallback: modo legado de normalizacao
    mapping_by_offset = load_mapping_offsets(mapping_path)
    fixed_records, report = normalize_records(
        records=records,
        mapping_by_offset=mapping_by_offset,
        ascii_sanitize=bool(args.ascii_sanitize),
        replace_unknown_with=str(args.replace_unknown_with),
    )

    fixed_records_sorted: List[Dict[str, Any]] = []
    for seq, rec in enumerate(
        sorted(
            fixed_records,
            key=lambda x: best_effort_get_offset(x)
            if isinstance(x, dict) and best_effort_get_offset(x) is not None
            else (1 << 30),
        )
    ):
        if not isinstance(rec, dict):
            continue
        out_rec = dict(rec)
        off = best_effort_get_offset(out_rec)
        if off is None:
            off = 0
        out_rec["seq"] = int(seq)
        out_rec["offset"] = int(off)
        out_rec["offset_hex"] = f"0x{int(off):06X}"
        out_rec["rom_offset"] = f"0x{int(off):06X}"
        out_rec["rom_crc32"] = crc32
        out_rec["rom_size"] = int(rom_size)
        fixed_records_sorted.append(out_rec)

    out_jsonl = Path(args.out_jsonl) if args.out_jsonl else (out_dir / f"{crc32}_translated_fixed.jsonl")
    out_report_txt = out_dir / f"{crc32}_report.txt"
    out_proof_json = out_dir / f"{crc32}_proof.json"

    meta_header = {
        "type": "meta",
        "schema": "neurorom.translated_jsonl.v2",
        "rom_crc32": crc32,
        "rom_size": int(rom_size),
        "ordering": "seq/rom_offset",
    }
    write_jsonl(out_jsonl, [meta_header] + fixed_records_sorted)
    write_report_txt(out_report_txt, crc32, rom_size, report)
    out_proof_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] CRC32={crc32} ROM_SIZE={rom_size}")
    print(f"[OUT] fixed_jsonl={out_jsonl.name}")
    print(f"[OUT] report={out_report_txt.name}")
    print(f"[OUT] proof={out_proof_json.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
