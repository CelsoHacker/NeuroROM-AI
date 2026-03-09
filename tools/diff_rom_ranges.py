# tools/diff_rom_ranges.py
# Compara ROM base vs ROM patchada e lista ranges alterados.
# Isso NÃO faz scan de strings; é só diff binário para diagnosticar corrupção.

import argparse
import zlib
from pathlib import Path


def crc32_file(path: Path, chunk_size: int = 1024 * 1024) -> int:
    """Calcula CRC32 lendo em chunks (estável e rápido)."""
    crc = 0
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            crc = zlib.crc32(chunk, crc)
    return crc & 0xFFFFFFFF


def load_bytes(path: Path) -> bytes:
    """Lê o arquivo inteiro em memória (256KB é tranquilo)."""
    return path.read_bytes()


def compute_diff_ranges(a: bytes, b: bytes):
    """
    Retorna uma lista de ranges [ (start, end_exclusive) ] onde a != b.
    """
    if len(a) != len(b):
        raise ValueError(f"Tamanhos diferentes: base={len(a)} patched={len(b)}")

    ranges = []
    in_range = False
    start = 0

    for i in range(len(a)):
        if a[i] != b[i]:
            if not in_range:
                in_range = True
                start = i
        else:
            if in_range:
                in_range = False
                ranges.append((start, i))

    if in_range:
        ranges.append((start, len(a)))

    return ranges


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="Caminho da ROM base")
    ap.add_argument("--patched", required=True, help="Caminho da ROM patchada")
    ap.add_argument("--max", type=int, default=40, help="Quantos ranges imprimir")
    args = ap.parse_args()

    base_path = Path(args.base)
    patched_path = Path(args.patched)

    if not base_path.exists():
        print(f"[ERRO] base não existe: {base_path}")
        return 2
    if not patched_path.exists():
        print(f"[ERRO] patched não existe: {patched_path}")
        return 2

    base_crc = crc32_file(base_path)
    patched_crc = crc32_file(patched_path)

    base = load_bytes(base_path)
    patched = load_bytes(patched_path)

    print(f"[INFO] BASE   CRC32={base_crc:08X} SIZE={len(base)} PATH={base_path}")
    print(f"[INFO] PATCH  CRC32={patched_crc:08X} SIZE={len(patched)} PATH={patched_path}")

    ranges = compute_diff_ranges(base, patched)
    total_changed = sum(end - start for start, end in ranges)

    print(f"[DIFF] ranges={len(ranges)} changed_bytes={total_changed}")

    for idx, (start, end) in enumerate(ranges[: args.max], 1):
        span = end - start
        print(f"[R{idx:02d}] @0x{start:06X}..0x{end:06X} len={span}")

    if len(ranges) > args.max:
        print(f"[INFO] +{len(ranges) - args.max} ranges não mostrados (use --max)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
