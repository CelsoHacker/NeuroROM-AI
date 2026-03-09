# -*- coding: utf-8 -*-
"""
Search ASCII Words in ROM (SMS V1)
=================================
Procura bytes literais de palavras ASCII em uma ROM e imprime offsets.

Uso:
    python tools/search_ascii_words.py <ROM_PATH>
    python tools/search_ascii_words.py <ROM_PATH> --words POWER TRIES SCORE TIME WELCOME
"""

from __future__ import annotations

import argparse
import os
import zlib
from typing import List


DEFAULT_WORDS = ["POWER", "TRIES", "SCORE", "TIME", "WELCOME"]


def _crc32(data: bytes) -> str:
    return f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"


def _find_all(data: bytes, pattern: bytes) -> List[int]:
    offsets: List[int] = []
    start = 0
    while True:
        idx = data.find(pattern, start)
        if idx == -1:
            break
        offsets.append(idx)
        start = idx + 1
    return offsets


def main() -> int:
    ap = argparse.ArgumentParser(description="Procura palavras ASCII na ROM.")
    ap.add_argument("rom_path", help="Caminho da ROM (.sms/.gg/.sg)")
    ap.add_argument(
        "--words",
        nargs="+",
        default=DEFAULT_WORDS,
        help="Lista de palavras ASCII para buscar",
    )
    args = ap.parse_args()

    rom_path = args.rom_path
    if not os.path.exists(rom_path):
        print("[ERRO] ROM não encontrada.")
        return 1

    data = open(rom_path, "rb").read()
    crc32 = _crc32(data)
    rom_size = len(data)

    print(f"CRC32={crc32}")
    print(f"ROM_SIZE={rom_size}")
    print("")

    total_hits = 0
    for word in args.words:
        try:
            pattern = word.encode("ascii")
        except UnicodeEncodeError:
            print(f"[WARN] Palavra inválida (não ASCII): {word}")
            continue

        offsets = _find_all(data, pattern)
        total_hits += len(offsets)

        if offsets:
            offsets_hex = ", ".join(f"0x{off:06X}" for off in offsets)
            print(f"WORD={word} HITS={len(offsets)} OFFSETS={offsets_hex}")
        else:
            print(f"WORD={word} HITS=0")

    print("")
    print(f"TOTAL_HITS={total_hits}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
