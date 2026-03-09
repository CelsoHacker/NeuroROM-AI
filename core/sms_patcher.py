#!/usr/bin/env python3
import json
from pathlib import Path

def parse_clean_blocks_txt(p: Path):
    out = {}
    cur_id = None
    waiting = False
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and len(line) >= 6 and line[5] == "]":
            try:
                cur_id = int(line[1:5])
                waiting = True
            except:
                cur_id = None
                waiting = False
            continue
        if line.startswith(">") or line.startswith("-"):
            continue
        if waiting and cur_id is not None:
            out[cur_id] = line
            waiting = False
    return out

def main(rom_path, mapping_path, translated_blocks_path):
    rom_path = Path(rom_path)
    mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
    trans = parse_clean_blocks_txt(Path(translated_blocks_path))

    rom = bytearray(rom_path.read_bytes())
    patched, skipped_long, skipped_missing = 0, 0, 0

    for e in mapping["entries"]:
        i = int(e["id"])
        off = int(e["offset"])
        max_len = int(e.get("max_len", 0))
        enc = e.get("encoding", "ascii")

        if i not in trans:
            skipped_missing += 1
            continue
        if enc != "ascii":
            # modo mínimo: só ASCII
            continue

        payload = trans[i].encode("ascii", errors="replace")
        if max_len <= 0:
            max_len = len(payload)

        if len(payload) > max_len:
            skipped_long += 1
            continue

        rom[off:off+max_len] = payload.ljust(max_len, b"\x00")
        if off + max_len < len(rom):
            rom[off+max_len:off+max_len+1] = b"\x00"
        patched += 1

    out_rom = rom_path.with_name(rom_path.stem + "_patched" + rom_path.suffix)
    out_rom.write_bytes(bytes(rom))

    report = {
        "patched": patched,
        "skipped_too_long": skipped_long,
        "skipped_missing": skipped_missing
    }
    Path(rom_path.stem + "_patch_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("OK:", out_rom, report)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        print("Uso: python sms_patcher.py ROM.sms ROM_mapping.json traducao_clean_blocks.txt")
        raise SystemExit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
