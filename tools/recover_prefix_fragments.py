#!/usr/bin/env python3
"""
recover_prefix_fragments.py

Recupera bytes cortados no início de entradas PREFIX_FRAGMENT no JSONL.

Para cada entrada PREFIX_FRAGMENT:
  - Varre o ROM para trás a partir do offset registrado
  - Encontra o início real da string (para antes de byte nulo ou não-printável)
  - Atualiza text_src, offset, pointer_refs e marca reinsertion_safe=True

Modos:
  --dry-run   apenas mostra o que seria recuperado, sem gravar
  --medium    inclui entradas com stop=0x01 (byte de controle simples) além de null [recomendado]
  --all       inclui qualquer stop byte (mais agressivo, pode incluir falsos positivos)
              padrão: só recupera quando o stop foi byte nulo (\x00) [conservador]

Uso:
  python recover_prefix_fragments.py <jsonl_path> <rom_path> [out_path] [--dry-run] [--medium] [--all]
"""

import json
import sys
import re
from pathlib import Path

PRINTABLE_MIN = 0x20
PRINTABLE_MAX = 0x7E
MAX_LOOKBACK = 32


def is_printable(b: int) -> bool:
    return PRINTABLE_MIN <= b <= PRINTABLE_MAX


def parse_bank_addend(v) -> int:
    """Converte bank_addend (string hex possivelmente negativa) para int."""
    if v is None:
        return 0
    s = str(v).strip().lower().replace(" ", "")
    neg = s.startswith("-")
    s = s.lstrip("+-")
    try:
        val = int(s, 16) if "0x" in s else int(s)
    except ValueError:
        return 0
    return -val if neg else val


def calc_pointer_value(new_rom_offset: int, ref: dict) -> str:
    """
    Recalcula pointer_value para novo rom_offset.
    Fórmula inversa de: rom_offset = ptr_value + bank_addend
    → ptr_value = rom_offset - bank_addend
    """
    bank_addend = parse_bank_addend(ref.get("bank_addend", "0"))
    new_val = new_rom_offset - bank_addend
    ptr_size = int(ref.get("ptr_size", 2) or 2)
    mask = (1 << (ptr_size * 8)) - 1
    return f"0x{(new_val & mask):04X}"


def scan_backward(rom_data: bytes, offset: int) -> tuple[int, int | None]:
    """
    Varre para trás a partir de offset.
    Retorna (lookback_bytes, stop_byte).
    stop_byte == 0x00  → parou em terminador nulo  (recuperação segura)
    stop_byte != 0x00  → parou em byte de controle (recuperação arriscada)
    stop_byte == None  → chegou no início do arquivo
    """
    lb = 0
    stop = None
    while lb < MAX_LOOKBACK:
        prev = offset - lb - 1
        if prev < 0:
            break
        b = rom_data[prev]
        if b == 0x00 or not is_printable(b):
            stop = b
            break
        lb += 1
    return lb, stop


def recover_prefix_fragments(
    jsonl_path: str,
    rom_path: str,
    out_path: str | None = None,
    dry_run: bool = False,
    aggressive: bool = False,
    medium: bool = False,
) -> None:
    rom_data = Path(rom_path).read_bytes()

    entries: list[dict] = []
    with open(jsonl_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    # Coleta offsets existentes para detectar conflitos
    existing_offsets: set[str] = set()
    for entry in entries:
        if entry.get("type") == "meta":
            continue
        off = entry.get("offset")
        if off:
            existing_offsets.add(off.upper())

    fixed = 0
    skipped_no_prefix = 0
    skipped_conflict = 0
    skipped_risky = 0
    skipped_bad_text = 0

    print(f"Processando: {jsonl_path}")
    print(f"ROM: {rom_path}")
    if aggressive:
        modo_str = "AGRESSIVO (qualquer stop byte)"
    elif medium:
        modo_str = "MÉDIO (null-stop + stop=0x01)"
    else:
        modo_str = "SEGURO (apenas null-stop)"
    print(f"Modo: {'DRY-RUN ' if dry_run else ''}{modo_str}")
    print()

    for entry in entries:
        if entry.get("type") == "meta":
            continue
        if "PREFIX_FRAGMENT" not in entry.get("review_flags", []):
            continue

        try:
            offset = int(entry["offset"], 16)
        except (ValueError, KeyError):
            continue

        lb, stop_byte = scan_backward(rom_data, offset)

        if lb == 0:
            skipped_no_prefix += 1
            continue

        # Modo seguro: só recupera quando parou em byte nulo (ou 0x01 no modo médio)
        safe_stops = {0x00}
        if medium or aggressive:
            safe_stops.add(0x01)
        if aggressive:
            safe_stops = None  # aceita qualquer stop
        if safe_stops is not None and stop_byte not in safe_stops:
            skipped_risky += 1
            if dry_run:
                try:
                    prefix_bytes = rom_data[offset - lb : offset]
                    prefix_str = prefix_bytes.decode("ascii", errors="replace")
                    full_preview = prefix_str + entry.get("text_src", "")
                    print(
                        f"  [IGNORADO/arriscado] {entry['offset']}  stop={hex(stop_byte) if stop_byte is not None else 'EOF'}"
                        f'  prefix="{prefix_str}"  completo="{full_preview}"'
                    )
                except Exception:
                    pass
            continue

        real_start = offset - lb
        new_offset_str = f"0x{real_start:08X}"

        # Verifica conflito: outro entry já usa esse offset
        if new_offset_str.upper() in existing_offsets and new_offset_str.upper() != entry["offset"].upper():
            skipped_conflict += 1
            if dry_run:
                print(f"  [IGNORADO/conflito] {entry['offset']} → {new_offset_str}  (offset já em uso)")
            continue

        # Lê bytes completos
        orig_end = offset + entry.get("raw_len", 0)
        if orig_end <= real_start:
            skipped_bad_text += 1
            continue

        full_bytes = rom_data[real_start:orig_end]
        try:
            full_text = full_bytes.decode("ascii")
        except UnicodeDecodeError:
            skipped_bad_text += 1
            continue

        # Validação básica: texto completo deve começar com letra
        if not full_text or not full_text[0].isalpha():
            skipped_bad_text += 1
            if dry_run:
                print(f"  [IGNORADO/inválido] {entry['offset']} → full=\"{full_text}\"")
            continue

        if dry_run:
            prefix_str = rom_data[offset - lb : offset].decode("ascii", errors="replace")
            print(
                f"  [RECUPERAR] {entry['offset']} → {new_offset_str}"
                f'  +"{prefix_str}" + "{entry.get("text_src","")}" = "{full_text}"'
            )
            fixed += 1
            continue

        # --- Aplica correção ---
        old_offset_upper = entry["offset"].upper()
        entry["offset"] = new_offset_str
        entry["rom_offset"] = new_offset_str
        entry["text_src"] = full_text
        entry["raw_bytes_hex"] = full_bytes.hex().upper()
        entry["raw_len"] = len(full_bytes)
        entry["max_len_bytes"] = len(full_bytes)
        entry["review_flags"] = [f for f in entry.get("review_flags", []) if f != "PREFIX_FRAGMENT"]
        entry["needs_review"] = len(entry["review_flags"]) > 0
        entry["reinsertion_safe"] = True
        entry["reason_code"] = "RECOVERED"

        # Atualiza pointer_refs com novo pointer_value
        for ref in entry.get("pointer_refs", []):
            ref["pointer_value"] = calc_pointer_value(real_start, ref)

        # Atualiza conjunto de offsets conhecidos
        existing_offsets.discard(old_offset_upper)
        existing_offsets.add(new_offset_str.upper())

        fixed += 1

    print()
    print(f"Resultado:")
    print(f"  Recuperados : {fixed}")
    print(f"  Sem prefixo : {skipped_no_prefix}")
    print(f"  Conflito    : {skipped_conflict}")
    print(f"  Arriscado   : {skipped_risky}  (use --all para incluir)")
    print(f"  Inválido    : {skipped_bad_text}")

    if dry_run:
        print()
        print("(dry-run: nenhum arquivo foi alterado)")
        return

    dest = out_path or jsonl_path
    with open(dest, "w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print()
    print(f"Gravado: {dest}")


def main() -> None:
    args = sys.argv[1:]
    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    flags = {a for a in args if a.startswith("--")}
    positional = [a for a in args if not a.startswith("--")]

    if len(positional) < 2:
        print("Uso: recover_prefix_fragments.py <jsonl> <rom> [saida.jsonl] [--dry-run] [--medium] [--all]")
        sys.exit(1)

    jsonl_path = positional[0]
    rom_path = positional[1]
    out_path = positional[2] if len(positional) > 2 else None
    dry_run = "--dry-run" in flags
    aggressive = "--all" in flags
    medium = "--medium" in flags and not aggressive

    recover_prefix_fragments(
        jsonl_path=jsonl_path,
        rom_path=rom_path,
        out_path=out_path,
        dry_run=dry_run,
        aggressive=aggressive,
        medium=medium,
    )


if __name__ == "__main__":
    main()
