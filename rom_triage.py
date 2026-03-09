#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rom_triage.py
Diagnóstico de ROM quebrando após reinserção.

Uso típico:
  python rom_triage.py --clean ROM_LIMPA.bin --patched ROM_PRETA.bin --mapping CRC_reinsertion_mapping.json

Também pode gerar ROM com subset do mapping (para achar a entrada que quebra o boot):
  python rom_triage.py --clean ROM_LIMPA.bin --mapping mapping.json --subset percent:0.5 --out_subset TESTE_50.bin
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

def read_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()

def write_file(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)

def crc32_hex(data: bytes) -> str:
    return f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"

def parse_int_maybe_hex(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        s = v.strip()
        if s.lower().startswith("0x"):
            try:
                return int(s, 16)
            except ValueError:
                return None
        if re.fullmatch(r"[0-9a-fA-F]+", s):
            try:
                return int(s, 16)
            except ValueError:
                return None
        if re.fullmatch(r"\d+", s):
            try:
                return int(s, 10)
            except ValueError:
                return None
    return None

def parse_hex_bytes(s: str) -> bytes:
    s = s.strip().replace("0x", "").replace("0X", "")
    s = re.sub(r"[^0-9a-fA-F]", "", s)
    if len(s) % 2 != 0:
        raise ValueError("Hex inválido: número ímpar de dígitos.")
    return bytes.fromhex(s)

def diff_ranges(a: bytes, b: bytes) -> List[Tuple[int, int]]:
    n = min(len(a), len(b))
    ranges: List[Tuple[int, int]] = []
    i = 0
    while i < n:
        if a[i] != b[i]:
            start = i
            i += 1
            while i < n and a[i] != b[i]:
                i += 1
            ranges.append((start, i))
        else:
            i += 1
    if len(a) != len(b):
        ranges.append((n, max(len(a), len(b))))
    return ranges

OFFSET_KEYS = ["offset", "ofs", "start", "addr", "address"]
ALLOC_KEYS = ["allocated_len", "reserved_len", "max_len", "slot_len", "orig_len", "original_len", "length"]
NEWHEX_KEYS = ["new_bytes_hex", "patched_bytes_hex", "new_hex", "bytes_hex", "newBytesHex"]
NEWBYTES_KEYS = ["new_bytes", "patched_bytes", "bytes", "newBytes"]
ORIGHEX_KEYS = ["orig_bytes_hex", "original_bytes_hex", "old_bytes_hex", "origHex"]
TERM_KEYS = ["terminator", "term", "end_byte", "endByte"]

@dataclass
class MapEntry:
    idx: int
    offset: int
    allocated_len: int
    new_bytes: bytes
    terminator: Optional[int] = None
    raw: Optional[Dict[str, Any]] = None

def _get_first_key(d: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in d:
            return d[k]
    return None

def load_mapping(path: str) -> List[MapEntry]:
    obj = json.loads(open(path, "r", encoding="utf-8").read())
    if isinstance(obj, dict):
        for k in ["entries", "items", "mapping", "data"]:
            if k in obj and isinstance(obj[k], list):
                obj = obj[k]
                break
    if not isinstance(obj, list):
        raise ValueError("Mapping JSON precisa ser uma lista (ou dict contendo lista em entries/items/mapping/data).")

    out: List[MapEntry] = []
    for i, raw in enumerate(obj, start=1):
        if not isinstance(raw, dict):
            continue

        offset = parse_int_maybe_hex(_get_first_key(raw, OFFSET_KEYS))
        if offset is None:
            continue

        terminator = parse_int_maybe_hex(_get_first_key(raw, TERM_KEYS))

        new_bytes: Optional[bytes] = None
        newhex = _get_first_key(raw, NEWHEX_KEYS)
        if isinstance(newhex, str) and newhex.strip():
            new_bytes = parse_hex_bytes(newhex)

        if new_bytes is None:
            newlist = _get_first_key(raw, NEWBYTES_KEYS)
            if isinstance(newlist, list) and all(isinstance(x, int) for x in newlist):
                new_bytes = bytes([x & 0xFF for x in newlist])

        if new_bytes is None:
            continue

        allocated_len = parse_int_maybe_hex(_get_first_key(raw, ALLOC_KEYS))

        if allocated_len is None:
            orighex = _get_first_key(raw, ORIGHEX_KEYS)
            if isinstance(orighex, str) and orighex.strip():
                try:
                    allocated_len = len(parse_hex_bytes(orighex))
                except Exception:
                    allocated_len = None

        if allocated_len is None:
            allocated_len = len(new_bytes)

        out.append(MapEntry(idx=i, offset=offset, allocated_len=allocated_len, new_bytes=new_bytes, terminator=terminator, raw=raw))
    return out

def validate_entries(entries: List[MapEntry]) -> List[str]:
    errors: List[str] = []
    for e in entries:
        if len(e.new_bytes) > e.allocated_len:
            errors.append(f"[ENTRY {e.idx:04d}] len(new_bytes)={len(e.new_bytes)} > allocated_len={e.allocated_len} @0x{e.offset:06X}")
        if e.terminator is not None and len(e.new_bytes) > 0 and e.new_bytes[-1] != (e.terminator & 0xFF):
            errors.append(f"[ENTRY {e.idx:04d}] terminator esperado 0x{e.terminator & 0xFF:02X} mas último byte é 0x{e.new_bytes[-1]:02X} @0x{e.offset:06X}")
    return errors

def apply_entries(clean_rom: bytes, entries: List[MapEntry]) -> bytes:
    rom = bytearray(clean_rom)
    for e in entries:
        start = e.offset
        end = e.offset + e.allocated_len
        if start < 0 or end > len(rom):
            raise ValueError(f"[ENTRY {e.idx:04d}] Offset fora do arquivo: 0x{start:06X}..0x{end:06X} ROM_SIZE=0x{len(rom):X}")
        if len(e.new_bytes) > e.allocated_len:
            raise ValueError(f"[ENTRY {e.idx:04d}] new_bytes maior que slot em 0x{start:06X}")
        rom[start:start + len(e.new_bytes)] = e.new_bytes
    return bytes(rom)

def select_subset(entries: List[MapEntry], subset: str) -> List[MapEntry]:
    subset = subset.strip()
    if subset.startswith("first:"):
        n = int(subset.split(":", 1)[1])
        return entries[: max(0, n)]
    if subset.startswith("ids:"):
        ids_s = subset.split(":", 1)[1].strip()
        ids = set(int(x.strip()) for x in ids_s.split(",") if x.strip())
        return [e for e in entries if e.idx in ids]
    if subset.startswith("range:"):
        r = subset.split(":", 1)[1].strip()
        a_s, b_s = r.split("-", 1)
        a = int(a_s); b = int(b_s)
        if a > b: a, b = b, a
        return [e for e in entries if a <= e.idx <= b]
    if subset.startswith("percent:"):
        p = float(subset.split(":", 1)[1])
        p = max(0.0, min(1.0, p))
        n = int(round(len(entries) * p))
        return entries[:n]
    raise ValueError("subset inválido. Use first:N | ids:... | range:A-B | percent:P")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", required=True)
    ap.add_argument("--patched")
    ap.add_argument("--mapping")
    ap.add_argument("--boot_limit", default="0x0400")
    ap.add_argument("--out_subset")
    ap.add_argument("--subset")
    args = ap.parse_args()

    clean = read_file(args.clean)
    print(f"[CLEAN]  CRC32={crc32_hex(clean)}  SIZE={len(clean)} (0x{len(clean):X})")

    boot_limit = parse_int_maybe_hex(args.boot_limit)
    if boot_limit is None:
        print("boot_limit inválido", file=sys.stderr)
        return 1

    patched = None
    if args.patched:
        patched = read_file(args.patched)
        print(f"[PATCH]  CRC32={crc32_hex(patched)}  SIZE={len(patched)} (0x{len(patched):X})")
        ranges = diff_ranges(clean, patched)
        total = sum(e - s for s, e in ranges)
        print(f"[DIFF]   RANGES={len(ranges)}  BYTES_CHANGED~={total}")
        for j, (s, e) in enumerate(ranges[:20], start=1):
            print(f"  #{j:02d}  0x{s:06X}..0x{e:06X}  ({e - s} bytes)")
        if any(s < boot_limit for s, _ in ranges):
            print(f"[ALERTA] Mudou abaixo de 0x{boot_limit:06X} (região crítica) -> causa comum de tela preta.")
        else:
            print(f"[OK]     Nenhuma mudança abaixo de 0x{boot_limit:06X}.")

    entries: List[MapEntry] = []
    if args.mapping:
        entries = load_mapping(args.mapping)
        errs = validate_entries(entries)
        print(f"[MAP]    ENTRIES={len(entries)}  VALIDATION_ERRORS={len(errs)}")
        for line in errs[:20]:
            print(" ", line)

        if patched is not None:
            n = min(len(clean), len(patched))
            changed = bytearray(0 for _ in range(n))
            for s, e in diff_ranges(clean[:n], patched[:n]):
                changed[s:e] = b"\x01" * (e - s)

            risky = []
            for e in entries:
                slot_s = e.offset
                slot_e = e.offset + e.allocated_len
                if slot_s < boot_limit:
                    risky.append((e.idx, e.offset, e.allocated_len, "BOOT_REGION"))
                    continue
                if slot_s < n and any(changed[slot_s:min(slot_e, n)]):
                    risky.append((e.idx, e.offset, e.allocated_len, "CHANGED"))

            if risky:
                print("[MAP↔DIFF] Entradas potencialmente perigosas (primeiras 25):")
                for (idx, off, alen, tag) in risky[:25]:
                    print(f"  [ENTRY {idx:04d}] {tag}  @0x{off:06X}  slot={alen}")

    if args.out_subset:
        if not args.mapping or not args.subset:
            print("Para gerar subset você precisa de --mapping e --subset.", file=sys.stderr)
            return 1
        chosen = select_subset(entries, args.subset)
        errs2 = validate_entries(chosen)
        if errs2:
            print("[SUBSET] ERROS de validação (corrija antes de testar):", file=sys.stderr)
            for line in errs2[:50]:
                print(" ", line, file=sys.stderr)
            return 2
        out = apply_entries(clean, chosen)
        write_file(args.out_subset, out)
        print(f"[WRITE]  {args.out_subset}  CRC32={crc32_hex(out)}  SIZE={len(out)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
