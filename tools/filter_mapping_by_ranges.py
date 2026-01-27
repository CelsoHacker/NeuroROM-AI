#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
filter_mapping_by_ranges.py

Filtra um reinsertion_mapping.json EXCLUINDO itens em faixas de offsets perigosos.
Util para isolar "offsets toxicos" que parecem texto mas corrompem a ROM.

Modos:
  --exclude-ranges "0x23806-0x23840,0x23887-0x23897"   (manual)
  --infer-from-diff --base-rom X --bad-rom Y          (automatico)

Compativel com formatos:
- Top-level list: [ {offset: ...}, ... ]
- Top-level dict com lista em: items / entries / records / mapping / data

Regras:
- NAO renomeia nada do projeto existente.
- Neutralidade: output sem nome do jogo, apenas CRC32 e SIZE.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional


def _parse_int(x: Any) -> Optional[int]:
    """Converte offset que pode vir como int, '0x1234', '1234', etc."""
    if x is None:
        return None
    if isinstance(x, int):
        return x
    if isinstance(x, str):
        s = x.strip()
        try:
            if s.lower().startswith("0x"):
                return int(s, 16)
            if re.fullmatch(r"[0-9a-fA-F]+", s) and not re.fullmatch(r"\d+", s):
                return int(s, 16)
            return int(s, 10)
        except ValueError:
            return None
    return None


def _find_items_container(data: Any) -> Tuple[Any, List[Dict[str, Any]], str]:
    """
    Retorna (container_original, items_list, key_name).
    O container_original e o objeto que deve ser preservado ao salvar.
    """
    if isinstance(data, list):
        items = [x for x in data if isinstance(x, dict)]
        return data, items, "__root__"

    if isinstance(data, dict):
        for k in ("items", "entries", "records", "mapping", "data"):
            v = data.get(k)
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return data, v, k

        for k, v in data.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                for cand_key in ("offset", "off", "pos", "address", "addr"):
                    if any(cand_key in it for it in v):
                        return data, v, k

    raise SystemExit("Nao consegui localizar a lista de itens dentro do mapping JSON.")


def _get_offset(item: Dict[str, Any]) -> Optional[int]:
    """Extrai offset de um item."""
    for key in ("offset", "off", "pos", "address", "addr"):
        if key in item:
            return _parse_int(item.get(key))
    return None


def _get_max_len(item: Dict[str, Any]) -> int:
    """Extrai max_length/max_len/length de um item, default 1."""
    for key in ("max_length", "max_len", "length", "size", "len"):
        v = item.get(key)
        if v is not None:
            parsed = _parse_int(v)
            if parsed and parsed > 0:
                return parsed
    return 1


def _parse_ranges(ranges_str: str) -> List[Tuple[int, int]]:
    """
    Formato aceito (end EXCLUSIVE como solicitado):
      "0x23806..0x23840"      (notation ..)
      "0x23806-0x23840"       (notation -)
      "0x23806..0x23840,0x23887..0x23897"  (multiplos)
    """
    out: List[Tuple[int, int]] = []
    if not ranges_str or not ranges_str.strip():
        return out
    parts = [p.strip() for p in ranges_str.split(",") if p.strip()]
    for p in parts:
        # aceita .. ou -
        m = re.fullmatch(r"(0x[0-9a-fA-F]+|\d+)\s*(?:\.\.|-)\s*(0x[0-9a-fA-F]+|\d+)", p)
        if not m:
            raise SystemExit(f"Range invalido: {p}")
        a = _parse_int(m.group(1))
        b = _parse_int(m.group(2))
        if a is None or b is None:
            raise SystemExit(f"Range invalido (parse falhou): {p}")
        if b < a:
            a, b = b, a
        out.append((a, b))
    return out


def _intervals_intersect(item_start: int, item_end: int, ranges: List[Tuple[int, int]]) -> bool:
    """
    True se intervalo [item_start, item_end) intersecta algum range [a, b).
    Todos os ranges sao end-exclusive.
    """
    for a, b in ranges:
        # Interseccao: NOT (item_end <= a OR item_start >= b)
        if not (item_end <= a or item_start >= b):
            return True
    return False


def _infer_ranges_from_diff(base_path: Path, bad_path: Path, min_gap: int = 16) -> List[Tuple[int, int]]:
    """
    Compara dois arquivos e retorna ranges de bytes que diferem.
    Agrupa diferencas proximas (min_gap) em ranges maiores.
    """
    base_data = base_path.read_bytes()
    bad_data = bad_path.read_bytes()

    if len(base_data) != len(bad_data):
        raise SystemExit(f"Tamanhos diferentes: base={len(base_data)}, bad={len(bad_data)}")

    diff_offsets: List[int] = []
    for i in range(len(base_data)):
        if base_data[i] != bad_data[i]:
            diff_offsets.append(i)

    if not diff_offsets:
        return []

    # Agrupa em ranges
    ranges: List[Tuple[int, int]] = []
    start = diff_offsets[0]
    end = diff_offsets[0] + 1

    for off in diff_offsets[1:]:
        if off <= end + min_gap:
            end = off + 1
        else:
            ranges.append((start, end))
            start = off
            end = off + 1

    ranges.append((start, end))
    return ranges


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Filtra mapping JSON excluindo itens em ranges perigosos."
    )
    ap.add_argument("--input", "-i", dest="inp", required=True,
                    help="Arquivo reinsertion_mapping.json de entrada")
    ap.add_argument("--output", "-o", dest="outp", required=True,
                    help="Arquivo de saida filtrado (mapping safe)")
    ap.add_argument("--exclude-ranges", dest="exclude_ranges", default="",
                    help='Ranges a EXCLUIR. Ex: "0x23806..0x23840,0x23887..0x23897"')
    ap.add_argument("--infer-from-diff", action="store_true",
                    help="Infere ranges automaticamente comparando ROMs")
    ap.add_argument("--base-rom", dest="base_rom",
                    help="ROM base (boa) para comparacao")
    ap.add_argument("--bad-rom", dest="bad_rom",
                    help="ROM corrompida para comparacao")
    ap.add_argument("--min-gap", type=int, default=16,
                    help="Gap minimo para agrupar diferencas (default: 16)")
    ap.add_argument("--report", dest="report",
                    help="Gera report .txt (default: <output>.report.txt)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Nao escreve arquivo, so mostra contagem")
    args = ap.parse_args()

    inp = Path(args.inp)
    outp = Path(args.outp)

    # Carrega mapping
    data = json.loads(inp.read_text(encoding="utf-8"))
    container, items, key_name = _find_items_container(data)

    # Determina ranges a excluir
    exclude_ranges: List[Tuple[int, int]] = []

    if args.exclude_ranges:
        exclude_ranges = _parse_ranges(args.exclude_ranges)

    if args.infer_from_diff:
        if not args.base_rom or not args.bad_rom:
            raise SystemExit("--infer-from-diff requer --base-rom e --bad-rom")
        inferred = _infer_ranges_from_diff(
            Path(args.base_rom), Path(args.bad_rom), args.min_gap
        )
        exclude_ranges.extend(inferred)

    if not exclude_ranges:
        raise SystemExit("Nenhum range de exclusao definido. Use --exclude-ranges ou --infer-from-diff.")

    # Filtra itens
    kept: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []
    missing_off = 0

    for it in items:
        off = _get_offset(it)
        if off is None:
            missing_off += 1
            kept.append(it)  # mantem itens sem offset (metadados)
            continue

        max_len = _get_max_len(it)
        item_start = off
        item_end = off + max_len  # end exclusive

        if _intervals_intersect(item_start, item_end, exclude_ranges):
            removed.append(it)
        else:
            kept.append(it)

    # Metadados para neutralidade
    file_crc32 = data.get("file_crc32", "UNKNOWN")
    file_size = data.get("file_size", 0)

    # Output
    print(f"[FILTER] CRC32={file_crc32} SIZE={file_size}")
    print(f"[IN ] {inp}")
    print(f"       items_total={len(items)} missing_offset={missing_off}")
    print(f"[OUT] {outp}")
    print(f"       kept={len(kept)} removed={len(removed)}")
    print(f"[EXCLUDE RANGES] ({len(exclude_ranges)} ranges)")
    for a, b in exclude_ranges:
        print(f"  - 0x{a:06X}..0x{b:06X} (len={b - a})")

    # Report
    report_path = Path(args.report) if args.report else outp.with_suffix(".report.txt")
    report_lines = [
        f"FILTER MAPPING BY RANGES REPORT",
        f"================================",
        f"Timestamp: {datetime.now().isoformat()}",
        f"",
        f"Source: {inp.name}",
        f"Output: {outp.name}",
        f"CRC32: {file_crc32}",
        f"SIZE: {file_size}",
        f"",
        f"STATISTICS:",
        f"  Total items: {len(items)}",
        f"  Kept: {len(kept)}",
        f"  Removed: {len(removed)}",
        f"  Missing offset: {missing_off}",
        f"",
        f"EXCLUDE RANGES ({len(exclude_ranges)}):",
    ]
    for a, b in exclude_ranges:
        report_lines.append(f"  0x{a:06X}..0x{b:06X} (len={b - a})")

    if removed:
        report_lines.append(f"")
        report_lines.append(f"REMOVED ITEMS ({len(removed)}):")
        for it in removed:
            off = _get_offset(it)
            max_len = _get_max_len(it)
            item_id = it.get("id", it.get("uid", "?"))
            src = it.get("source", "")[:30]
            report_lines.append(f"  id={item_id} offset=0x{off:06X} len={max_len} src=\"{src}...\"")

    report_text = "\n".join(report_lines)

    if args.dry_run:
        print(f"\n[DRY-RUN] Nenhum arquivo escrito.")
        print(f"\n--- REPORT PREVIEW ---")
        print(report_text)
        return 0

    # Salva mapping filtrado preservando formato
    if key_name == "__root__":
        out_data: Any = kept
    else:
        out_data = dict(container)
        out_data[key_name] = kept

    outp.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Mapping escrito: {outp}")

    # Salva report
    report_path.write_text(report_text, encoding="utf-8")
    print(f"[OK] Report escrito: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
