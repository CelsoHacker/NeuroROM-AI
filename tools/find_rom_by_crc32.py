# tools/find_rom_by_crc32.py
# Busca arquivos de ROM por CRC32 e tamanho (sem scan de strings; só checksum).

import argparse
import os
import zlib
from pathlib import Path


def crc32_of_file(path: Path, chunk_size: int = 1024 * 1024) -> int:
    """
    Calcula CRC32 do arquivo lendo em chunks (eficiente e seguro).
    Retorna inteiro (0..0xFFFFFFFF).
    """
    crc = 0
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            crc = zlib.crc32(chunk, crc)
    return crc & 0xFFFFFFFF


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="Diretório raiz para procurar (ex: PROJETO_V5_OFICIAL)")
    ap.add_argument("--crc", required=True, help="CRC32 alvo em HEX (ex: 953F42E1)")
    ap.add_argument("--size", type=int, default=0, help="Tamanho exato em bytes (0 = ignorar)")
    ap.add_argument("--ext", default=".sms,.rom,.bin,.md,.nes,.sfc,.smc",
                    help="Extensões aceitas separadas por vírgula")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"[ERRO] root não existe: {root}")
        return 2

    target_crc = int(args.crc, 16) & 0xFFFFFFFF
    exts = {e.strip().lower() for e in args.ext.split(",") if e.strip()}

    hits = 0
    scanned = 0

    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.suffix.lower() not in exts:
                continue

            try:
                st = p.stat()
            except OSError:
                continue

            if args.size and st.st_size != args.size:
                continue

            scanned += 1
            try:
                crc = crc32_of_file(p)
            except OSError:
                continue

            if crc == target_crc:
                hits += 1
                print(f"[FOUND] CRC32={crc:08X} SIZE={st.st_size} PATH={p}")

    print(f"[DONE] scanned={scanned} hits={hits}")
    return 0 if hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
