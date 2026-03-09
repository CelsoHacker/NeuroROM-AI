#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rom_triage.py
Diagnóstico rápido de ROM quebrando no boot após reinserção.

- Calcula CRC32 e tamanho.
- Faz diff e lista ranges alterados.
- (Opcional) cruza com reinsertion_mapping.json para apontar entradas perigosas.
- (Opcional) gera ROM com subset do mapping para você fazer "binary search" manual.

Compatível com Python 3.10+ (usa apenas stdlib).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zlib
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ----------------------------- Utilidades básicas -----------------------------

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
    """
    Aceita int, string decimal, string hex ("0x1A2B" ou "1A2B").
    """
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
        # hex puro?
        if re.fullmatch(r"[0-9a-fA-F]+", s):
            try:
                return int(s, 16)
            except ValueError:
                return None
        # decimal?
        if re.fullmatch(r"\d+", s):
            try:
                return int(s, 10)
            except ValueError:
                return None
    return None

def parse_hex_bytes(s: str) -> bytes:
    """
    Aceita:
      - "AA BB CC"
      - "AABBCC"
      - com "0x" perdido misturado
    """
    s = s.strip().replace("0x", "").replace("0X", "")
    s = re.sub(r"[^0-9a-fA-F]", "", s)
    if len(s) % 2 != 0:
        raise ValueError("Hex inválido: número ímpar de dígitos.")
    return bytes.fromhex(s)

def diff_ranges(a: bytes, b: bytes) -> List[Tuple[int, int]]:
    """
    Retorna lista de ranges [start, end) onde a != b.
    """
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

    # Se tamanhos diferentes, considera como range extra no final
    if len(a) != len(b):
        start = n
        end = max(len(a), len(b))
        ranges.append((start, end))

    return ranges


# ----------------------------- Mapping (robusto) ------------------------------

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
    """
    Espera JSON ser:
      - lista de entradas
      - ou dict com "entries" / "items" / "mapping"
    Cada entrada precisa ter offset e bytes novos (hex string ou lista de ints).
    allocated_len é inferido de:
      - allocated_len/reserved_len/max_len...
      - senão len(orig_bytes_hex) se existir
      - senão len(new_bytes) (último recurso; ainda valida tamanho no apply)
    """
    obj = json.loads(open(path, "r", encoding="utf-8").read())

    if isinstance(obj, dict):
        for k in ["entries", "items", "mapping", "data"]:
            if k in obj and isinstance(obj[k], list):
                obj = obj[k]
                break

    if not isinstance(obj, list):
        raise ValueError("Mapping JSON precisa ser uma lista (ou dict contendo lista em entries/items/mapping/data).")

    entries: List[MapEntry] = []
    for i, raw in enumerate(obj, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"Entrada #{i} do mapping não é objeto JSON.")

        off_v = _get_first_key(raw, OFFSET_KEYS)
        offset = parse_int_maybe_hex(off_v)
        if offset is None:
            raise ValueError(f"Entrada #{i}: não encontrei offset válido (chaves: {OFFSET_KEYS}).")

        term_v = _get_first_key(raw, TERM_KEYS)
        terminator = parse_int_maybe_hex(term_v)

        # new bytes: prefer hex, senão lista de ints
        new_bytes: Optional[bytes] = None
        newhex_v = _get_first_key(raw, NEWHEX_KEYS)
        if isinstance(newhex_v, str) and newhex_v.strip():
            new_bytes = parse_hex_bytes(newhex_v)

        if new_bytes is None:
            newlist_v = _get_first_key(raw, NEWBYTES_KEYS)
            if isinstance(newlist_v, list) and all(isinstance(x, int) for x in newlist_v):
                new_bytes = bytes([x & 0xFF for x in newlist_v])

        if new_bytes is None:
            raise ValueError(
                f"Entrada #{i}: não encontrei bytes novos (hex string em {NEWHEX_KEYS} ou lista ints em {NEWBYTES_KEYS})."
            )

        alloc_v = _get_first_key(raw, ALLOC_KEYS)
        allocated_len = parse_int_maybe_hex(alloc_v)

        if allocated_len is None:
            orighex_v = _get_first_key(raw, ORIGHEX_KEYS)
            if isinstance(orighex_v, str) and orighex_v.strip():
                try:
                    allocated_len = len(parse_hex_bytes(orighex_v))
                except Exception:
                    allocated_len = None

        if allocated_len is None:
            # último recurso: assume slot = len(new_bytes)
            allocated_len = len(new_bytes)

        entries.append(MapEntry(idx=i, offset=offset, allocated_len=allocated_len, new_bytes=new_bytes, terminator=terminator, raw=raw))

    return entries

def validate_entries(entries: List[MapEntry]) -> List[str]:
    """
    Validações estritas para evitar boot-kill:
      - len(new_bytes) <= allocated_len
      - se terminator definido, último byte deve ser terminator
    Retorna lista de erros (vazia se ok).
    """
    errors: List[str] = []
    for e in entries:
        if len(e.new_bytes) > e.allocated_len:
            errors.append(f"[ENTRY {e.idx:04d}] len(new_bytes)={len(e.new_bytes)} > allocated_len={e.allocated_len} @0x{e.offset:06X}")

        if e.terminator is not None:
            if len(e.new_bytes) == 0:
                errors.append(f"[ENTRY {e.idx:04d}] new_bytes vazio mas terminator definido @0x{e.offset:06X}")
            else:
                if e.new_bytes[-1] != (e.terminator & 0xFF):
                    errors.append(
                        f"[ENTRY {e.idx:04d}] terminator esperado 0x{e.terminator & 0xFF:02X} mas último byte é 0x{e.new_bytes[-1]:02X} @0x{e.offset:06X}"
                    )
    return errors

def apply_entries(clean_rom: bytes, entries: List[MapEntry]) -> bytes:
    """
    Aplica patch em uma cópia do clean_rom, respeitando allocated_len:
      - escreve new_bytes
      - completa o resto do slot com bytes originais (não zera nada)
    """
    rom = bytearray(clean_rom)
    for e in entries:
        start = e.offset
        end = e.offset + e.allocated_len
        if start < 0 or end > len(rom):
            raise ValueError(f"[ENTRY {e.idx:04d}] Offset fora do arquivo: 0x{start:06X}..0x{end:06X} ROM_SIZE=0x{len(rom):X}")

        if len(e.new_bytes) > e.allocated_len:
            raise ValueError(f"[ENTRY {e.idx:04d}] new_bytes maior que slot em 0x{start:06X}")

        # escreve apenas os bytes novos; mantém o restante como era
        rom[start:start + len(e.new_bytes)] = e.new_bytes
    return bytes(rom)

def select_subset(entries: List[MapEntry], subset: str) -> List[MapEntry]:
    """
    subset formats:
      - "first:N"     (primeiras N entradas)
      - "ids:1,2,3"   (IDs 1-based do mapping)
      - "range:A-B"   (inclusive, 1-based)
      - "percent:P"   (P em 0..1, ex: 0.5)
    """
    subset = subset.strip()
    if subset.startswith("first:"):
        n = int(subset.split(":", 1)[1])
        return entries[: max(0, n)]

    if subset.startswith("ids:"):
        ids_s = subset.split(":", 1)[1].strip()
        ids = []
        for part in ids_s.split(","):
            part = part.strip()
            if part:
                ids.append(int(part))
        chosen = [e for e in entries if e.idx in set(ids)]
        return chosen

    if subset.startswith("range:"):
        r = subset.split(":", 1)[1].strip()
        a_s, b_s = r.split("-", 1)
        a = int(a_s); b = int(b_s)
        if a > b:
            a, b = b, a
        return [e for e in entries if a <= e.idx <= b]

    if subset.startswith("percent:"):
        p = float(subset.split(":", 1)[1])
        if p < 0:
            p = 0.0
        if p > 1:
            p = 1.0
        n = int(round(len(entries) * p))
        return entries[:n]

    raise ValueError("subset inválido. Use first:N | ids:... | range:A-B | percent:P")


# ----------------------------- Main ------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Diagnóstico de ROM quebrando após reinserção (CRC32/size/diff + subset patch).")
    ap.add_argument("--clean", required=True, help="ROM original limpa (bin).")
    ap.add_argument("--patched", help="ROM patch quebrada (opcional, para diff).")
    ap.add_argument("--mapping", help="reinsertion_mapping.json (opcional).")
    ap.add_argument("--boot_limit", default="0x0400", help="Região crítica inicial (default 0x0400).")
    ap.add_argument("--out_subset", help="Se definido, gera ROM a partir de --clean + subset do mapping.")
    ap.add_argument("--subset", help="Subset do mapping: first:N | ids:1,2 | range:A-B | percent:0.5")
    args = ap.parse_args()

    clean = read_file(args.clean)
    clean_crc = crc32_hex(clean)
    print(f"[CLEAN]  CRC32={clean_crc}  SIZE={len(clean)} (0x{len(clean):X})")

    boot_limit = parse_int_maybe_hex(args.boot_limit)
    if boot_limit is None:
        print("boot_limit inválido.", file=sys.stderr)
        return 1

    patched = None
    if args.patched:
        patched = read_file(args.patched)
        patched_crc = crc32_hex(patched)
        print(f"[PATCH]  CRC32={patched_crc}  SIZE={len(patched)} (0x{len(patched):X})")

        ranges = diff_ranges(clean, patched)
        total_changed = sum((end - start) for start, end in ranges)
        print(f"[DIFF]   RANGES={len(ranges)}  BYTES_CHANGED~={total_changed}")

        # mostra os primeiros 20 ranges
        for j, (s, e) in enumerate(ranges[:20], start=1):
            print(f"  #{j:02d}  0x{s:06X}..0x{e:06X}  ({e - s} bytes)")

        touched_boot = any(s < boot_limit for s, _ in ranges)
        if touched_boot:
            print(f"[ALERTA] Diferenças dentro da região crítica 0x000000..0x{boot_limit-1:06X} (isso costuma dar tela preta).")
        else:
            print(f"[OK]     Nenhuma diferença abaixo de 0x{boot_limit:06X}.")

    entries: List[MapEntry] = []
    if args.mapping:
        entries = load_mapping(args.mapping)
        errs = validate_entries(entries)
        print(f"[MAP]    ENTRIES={len(entries)}  VALIDATION_ERRORS={len(errs)}")
        for line in errs[:20]:
            print(" ", line)
        if len(errs) > 20:
            print(f"  ... (+{len(errs)-20} erros)")

        # Se há diff e mapping, tenta apontar entradas na região crítica
        if patched is not None:
            # mapeia bytes alterados para lookup rápido (somente até len menor)
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
            else:
                print("[MAP↔DIFF] Nenhuma entrada do mapping caiu na região crítica nem bateu com bytes alterados (bom sinal).")

    # Gera subset ROM
    if args.out_subset:
        if not args.mapping or not args.subset:
            print("Para gerar subset você precisa de --mapping e --subset.", file=sys.stderr)
            return 1
        chosen = select_subset(entries, args.subset)
        # valida de novo só o subset
        errs2 = validate_entries(chosen)
        if errs2:
            print("[SUBSET] ERROS de validação (corrija antes de testar):", file=sys.stderr)
            for line in errs2[:50]:
                print(" ", line, file=sys.stderr)
            return 2

        out = apply_entries(clean, chosen)
        out_crc = crc32_hex(out)
        write_file(args.out_subset, out)
        print(f"[WRITE]  {args.out_subset}  CRC32={out_crc}  SIZE={len(out)}")
        print(f"[INFO]   Subset aplicado: {len(chosen)}/{len(entries)} entradas ({args.subset})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
