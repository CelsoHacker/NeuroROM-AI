import argparse
import json
import os
import sys
from pathlib import Path


def _load_first_translation(jsonl_path: Path):
    total = 0
    usable = 0
    first = None

    with jsonl_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            text = (obj.get("text_dst") or obj.get("translation") or
                    obj.get("translated_text") or obj.get("translated") or
                    obj.get("text"))
            if not isinstance(text, str) or not text.strip():
                continue

            # Normaliza offset para int (pode vir como "0x000524")
            off = obj.get("offset", 0)
            if isinstance(off, str):
                s = off.strip()
                try:
                    off = int(s, 16) if s.lower().startswith("0x") else int(s)
                except ValueError:
                    off = 0

            # Chave preferencial: id > key > offset
            if obj.get("id") is not None:
                key = str(obj["id"])
            else:
                key = obj.get("key") or f"0x{off:X}"

            usable += 1
            first = {"key": key, "text": text.strip()}
            break

    return total, usable, first


def main():
    parser = argparse.ArgumentParser(
        description="Testa reinserção SMS com apenas o primeiro texto traduzido."
    )
    parser.add_argument("--rom", required=True, help="Caminho da ROM .sms")
    parser.add_argument("--jsonl", required=True, help="Caminho do JSONL traduzido")
    parser.add_argument("--out", help="Caminho da ROM de saída (opcional)")
    parser.add_argument("--mapping", help="Caminho do *_mapping.json (opcional)")
    parser.add_argument("--force-blocked", action="store_true", help="Ignora reinsertion_safe")
    parser.add_argument("--debug", action="store_true", help="Ativa logs detalhados no core")
    args = parser.parse_args()

    rom_path = Path(args.rom)
    jsonl_path = Path(args.jsonl)
    if not rom_path.exists():
        raise SystemExit(f"ROM não encontrada: {rom_path}")
    if not jsonl_path.exists():
        raise SystemExit(f"JSONL não encontrado: {jsonl_path}")

    if args.debug:
        os.environ["NEUROROM_DEBUG_REINSERT"] = "1"

    # Importa depois de setar o env DEBUG
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from core.sega_reinserter import SegaMasterSystemReinserter, ReinsertionError

    print("STEP 1: Lendo JSONL e pegando o primeiro texto traduzido")
    total, usable, first = _load_first_translation(jsonl_path)
    print(f"  Total linhas JSONL: {total}")
    print(f"  Linhas com texto válido: {usable}")
    if not first:
        raise SystemExit("Nenhum texto traduzido válido encontrado no JSONL.")

    print(f"  Usando key={first['key']} texto='{first['text'][:60]}'")

    engine = SegaMasterSystemReinserter()
    mapping_path = Path(args.mapping) if args.mapping else engine._guess_mapping_path(jsonl_path, rom_path)
    if mapping_path is None or not mapping_path.exists():
        raise SystemExit("mapping.json não encontrado. Passe --mapping ou coloque *_mapping.json na mesma pasta.")

    out_path = Path(args.out) if args.out else jsonl_path.with_name(f"{rom_path.stem}_ONE_TEST{rom_path.suffix}")

    print("STEP 2: Reinserindo 1 item")
    try:
        out_file, stats = engine.apply_translation(
            rom_path=rom_path,
            translated_path=jsonl_path,
            mapping_path=mapping_path,
            output_rom_path=out_path,
            force_blocked=args.force_blocked,
            translated={first["key"]: first["text"]},
        )
    except ReinsertionError as e:
        raise SystemExit(f"Erro: {e}")

    entry = engine.mapping.get(first["key"])
    if entry:
        print("STEP 3: Detalhes do item no mapping")
        print(f"  offset=0x{entry.offset:X} max_len={entry.max_len} reinsertion_safe={entry.reinsertion_safe}")
        print(f"  has_pointer={entry.has_pointer} pointer_offsets={entry.pointer_offsets}")
    else:
        print("STEP 3: Item não encontrado no mapping (key não bate)")

    print("STEP 4: Resultado")
    print(f"  ROM saída: {out_file}")
    print(f"  Stats: {stats}")


if __name__ == "__main__":
    main()
