# -*- coding: utf-8 -*-
"""nes_extractor_pro.py

Extrator NES (iNES) focado em texto ASCII / TBL.

- Lê header iNES (16 bytes)
- Separa PRG-ROM (onde tipicamente ficam textos)
- Extrai sequências ASCII imprimíveis (min_len configurável)
- Gera:
  1) <ROMNAME>_NES_EXTRACTED.txt  (formato compatível com o resto do projeto)
  2) <ROMNAME>_NES_EXTRACTED_META.json (offset, length, bank, addr_in_bank)

V6.0 PRO (NeuroROM AI)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional


ASCII_RE = re.compile(b"[\x20-\x7E]{4,240}")


def parse_ines_header(data: bytes) -> Dict:
    if len(data) < 16 or data[:4] != b"NES\x1A":
        raise ValueError("Arquivo nao parece ser NES iNES (magic NES\\x1A ausente)")

    prg_16k = data[4]
    chr_8k = data[5]
    flags6 = data[6]
    flags7 = data[7]

    mapper = (flags7 & 0xF0) | (flags6 >> 4)

    has_trainer = bool(flags6 & 0x04)
    header_size = 16
    trainer_size = 512 if has_trainer else 0

    prg_size = prg_16k * 0x4000
    chr_size = chr_8k * 0x2000

    return {
        "prg_16k": prg_16k,
        "chr_8k": chr_8k,
        "mapper": mapper,
        "has_trainer": has_trainer,
        "header_size": header_size,
        "trainer_size": trainer_size,
        "prg_size": prg_size,
        "chr_size": chr_size,
    }


def _extract_ascii(prg: bytes, base_file_offset: int, min_len: int = 4) -> List[Tuple[int, str, int]]:
    out: List[Tuple[int, str, int]] = []

    for m in ASCII_RE.finditer(prg):
        raw = m.group()
        try:
            s = raw.decode("ascii", errors="strict").strip()
        except Exception:
            continue

        if len(s) < min_len:
            continue

        off_in_prg = m.start()
        file_off = base_file_offset + off_in_prg
        out.append((file_off, s, len(raw)))

    return out


def extract_nes(rom_path: str, tbl_path: Optional[str] = None, min_len: int = 4) -> Dict:
    rom_path = str(rom_path)
    p = Path(rom_path)

    data = p.read_bytes()
    hdr = parse_ines_header(data)

    start = hdr["header_size"] + hdr["trainer_size"]
    prg = data[start : start + hdr["prg_size"]]

    if len(prg) != hdr["prg_size"]:
        raise ValueError("PRG-ROM incompleto: arquivo menor que o indicado pelo header")

    strings = _extract_ascii(prg, base_file_offset=start, min_len=min_len)

    # Remove duplicatas mantendo primeira ocorrencia (mesmo texto)
    seen = set()
    uniq: List[Tuple[int, str, int]] = []
    for off, s, raw_len in strings:
        if s in seen:
            continue
        seen.add(s)
        uniq.append((off, s, raw_len))

    out_txt = p.with_name(f"{p.stem}_NES_EXTRACTED.txt")
    out_meta = p.with_name(f"{p.stem}_NES_EXTRACTED_META.json")

    meta: List[Dict] = []
    for idx, (file_off, s, raw_len) in enumerate(uniq, 1):
        off_in_prg = file_off - start
        bank = off_in_prg // 0x4000
        addr_in_bank = 0x8000 + (off_in_prg % 0x4000)  # modelo mais comum
        meta.append({
            "id": idx,
            "file_offset": file_off,
            "offset_in_prg": off_in_prg,
            "bank": bank,
            "addr_in_bank": addr_in_bank,
            "raw_len": raw_len,
            "text": s,
        })

    # Salva TXT
    with out_txt.open("w", encoding="utf-8") as f:
        f.write("# NES EXTRACTOR PRO - ASCII (PRG-ROM)\n")
        f.write(f"# ROM: {p.name}\n")
        f.write(f"# PRG banks (16KB): {hdr['prg_16k']} | Mapper: {hdr['mapper']}\n")
        f.write("# Formato: [0xOFFSET_NO_ARQUIVO] texto\n\n")
        for file_off, s, _ in uniq:
            f.write(f"[0x{file_off:06X}] {s}\n")

    # Salva META
    out_meta.write_text(json.dumps({"header": hdr, "strings": meta}, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "txt": str(out_txt),
        "meta": str(out_meta),
        "count": len(uniq),
        "header": hdr,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python nes_extractor_pro.py <rom.nes>")
        raise SystemExit(1)

    res = extract_nes(sys.argv[1])
    print(f"✅ Extracted {res['count']} strings")
    print(f"TXT:  {res['txt']}")
    print(f"META: {res['meta']}")
