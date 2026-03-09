#!/usr/bin/env python3
"""
promote_ascii_dialog.py

Promove entradas ASCII_BRUTE do all_text.jsonl para o pure_text.jsonl.

Essas entradas são textos de diálogo NPC em bloco sequencial no ROM.
O extrator as encontrou mas as marcou como reinsertion_safe=False por
não terem referência de ponteiro confirmada.

Critérios de promoção:
  - Zona de dialogo (offset >= DIALOG_ZONE_START)
  - reinsertion_safe = False (ainda não promovido)
  - review_flags vazio (sem problemas detectados)
  - ASCII limpo, >=55% letras, pelo menos uma palavra com 3+ chars
  - Sem conflito de offset com entradas existentes em pure_text.jsonl

Palavras-chave de menu (todas maiúsculas, <=12 chars) são marcadas como
needs_review=True para revisão opcional antes de tradução.

Uso:
  python promote_ascii_dialog.py <all_text.jsonl> <pure_text.jsonl> [--dry-run] [--min-offset HEX]
"""

import json
import sys
import re
from pathlib import Path

# Offset inicial do bloco de dialogo (ajustável via --min-offset)
DEFAULT_DIALOG_ZONE = 0x06E000

# Flags que bloqueiam promoção
BAD_FLAGS = {
    "PREFIX_FRAGMENT",
    "ROUNDTRIP_FAIL",
    "HAS_UNKNOWN_BYTES",
    "NOT_PLAUSIBLE_TEXT_SMS",
    "HAS_BYTE_PLACEHOLDER",
    "TOO_SHORT_FRAGMENT",
}

WORD_RE = re.compile(r"[A-Za-z]{3,}")
KEYWORD_RE = re.compile(r"^[A-Z][A-Z0-9 '\-]{1,11}$")  # palavras-chave de menu


def is_promotable(entry: dict, min_offset: int) -> tuple[bool, str]:
    """Retorna (pode_promover, motivo)."""
    if entry.get("type") == "meta":
        return False, "meta"
    try:
        off = int(entry.get("offset", "0x0"), 16)
    except ValueError:
        return False, "offset_inválido"

    if off < min_offset:
        return False, "fora_da_zona"
    if entry.get("reinsertion_safe"):
        return False, "já_seguro"
    if entry.get("source") not in ("ASCII_BRUTE", "ASCII_PROFILE", None, ""):
        if not str(entry.get("source", "")).startswith("ASCII"):
            return False, "fonte_não_ascii"

    flags = set(entry.get("review_flags", []))
    bad = flags & BAD_FLAGS
    if bad:
        return False, f"flag_ruim:{','.join(bad)}"

    txt = entry.get("text_src", "")
    if len(txt) < 4:
        return False, "muito_curto"

    letters = sum(1 for c in txt if c.isalpha())
    ratio = letters / max(1, len(txt))
    if ratio < 0.55:
        return False, "poucas_letras"

    words = WORD_RE.findall(txt)
    if not words:
        return False, "sem_palavra_real"

    # Rejeita padrões de dados binários (char+símbolo alternado)
    if len(txt) >= 6 and txt.count(" ") == 0:
        alt = sum(1 for i in range(min(8, len(txt) - 1)) if txt[i].isalpha() != txt[i + 1].isalpha())
        if alt >= 5:
            return False, "padrão_binário"

    return True, "ok"


def is_menu_keyword(txt: str) -> bool:
    """Detecta palavras-chave de menu (todas maiúsculas, curtas)."""
    return bool(KEYWORD_RE.match(txt.strip()))


def promote_ascii_dialog(
    all_jsonl_path: str,
    pure_jsonl_path: str,
    dry_run: bool = False,
    min_offset: int = DEFAULT_DIALOG_ZONE,
) -> None:
    # Carrega entradas existentes no pure_text.jsonl
    pure_entries: list[dict] = []
    existing_offsets: set[str] = set()

    with open(pure_jsonl_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                e = json.loads(line)
                pure_entries.append(e)
                off = e.get("offset")
                if off:
                    existing_offsets.add(str(off).upper())

    # Lê candidatos do all_text.jsonl
    candidates: list[dict] = []
    with open(all_jsonl_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            ok, reason = is_promotable(e, min_offset)
            if ok:
                candidates.append(e)

    print(f"all_text.jsonl candidatos encontrados: {len(candidates)}")
    print(f"pure_text.jsonl entradas atuais: {len([e for e in pure_entries if e.get('type') != 'meta'])}")
    print()

    promoted = 0
    skipped_conflict = 0
    skipped_keyword = 0

    new_entries: list[dict] = []

    for entry in candidates:
        off_str = str(entry.get("offset", "")).upper()

        # Verifica conflito de offset
        if off_str in existing_offsets:
            skipped_conflict += 1
            continue

        txt = entry.get("text_src", "")
        keyword = is_menu_keyword(txt)

        if dry_run:
            tag = "[KEYWORD]" if keyword else "[PROMOVER]"
            print(f"  {tag} {entry.get('offset')}  \"{txt[:70]}\"")
            promoted += 1
            continue

        # Prepara entrada promovida
        promoted_entry = dict(entry)
        promoted_entry["reinsertion_safe"] = True
        promoted_entry["needs_review"] = keyword  # keywords ficam para revisão
        if keyword:
            flags = list(promoted_entry.get("review_flags", []))
            if "KEYWORD_MENU" not in flags:
                flags.append("KEYWORD_MENU")
            promoted_entry["review_flags"] = flags
        promoted_entry["reason_code"] = "PROMOTED_DIALOG"

        # max_len_bytes = comprimento original (restrição de reinserção in-place)
        raw_len = entry.get("raw_len") or len(txt)
        promoted_entry["max_len_bytes"] = raw_len

        new_entries.append(promoted_entry)
        existing_offsets.add(off_str)
        promoted += 1

    if not dry_run:
        # Adiciona novas entradas ao final do pure_text.jsonl
        all_entries = pure_entries + new_entries

        with open(pure_jsonl_path, "w", encoding="utf-8") as fh:
            for e in all_entries:
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")

    total_after = len([e for e in pure_entries if e.get("type") != "meta"]) + (promoted if not dry_run else 0)
    print()
    print(f"Resultado:")
    print(f"  Promovidos     : {promoted}")
    print(f"  Conflitos      : {skipped_conflict}")
    print(f"  Total pure_text: {total_after if not dry_run else '?'}")

    if dry_run:
        print()
        print("(dry-run: nenhum arquivo alterado)")
    else:
        print()
        print(f"Gravado: {pure_jsonl_path}")


def main() -> None:
    args = sys.argv[1:]
    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    flags = {a for a in args if a.startswith("--")}
    positional = [a for a in args if not a.startswith("--") and not a.startswith("0x")]

    if len(positional) < 2:
        print("Uso: promote_ascii_dialog.py <all_text.jsonl> <pure_text.jsonl> [--dry-run] [--min-offset 0xHEX]")
        sys.exit(1)

    dry_run = "--dry-run" in flags

    min_offset = DEFAULT_DIALOG_ZONE
    if "--min-offset" in args:
        idx = args.index("--min-offset")
        if idx + 1 < len(args):
            try:
                min_offset = int(args[idx + 1], 16)
            except ValueError:
                pass

    promote_ascii_dialog(
        all_jsonl_path=positional[0],
        pure_jsonl_path=positional[1],
        dry_run=dry_run,
        min_offset=min_offset,
    )


if __name__ == "__main__":
    main()
