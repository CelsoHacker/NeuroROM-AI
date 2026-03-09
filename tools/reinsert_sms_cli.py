#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI para reinserção segura em ROMs SMS usando o SegaReinserter."""

import argparse
import sys
from pathlib import Path

# Garante imports do projeto
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.sega_reinserter import SegaReinserter


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reinserção segura de textos em ROMs Sega Master System."
    )
    parser.add_argument("rom", help="Caminho da ROM original (.sms)")
    parser.add_argument("translated", help="Arquivo traduzido (.txt ou .jsonl)")
    parser.add_argument(
        "--output",
        default=None,
        help="Caminho do ROM de saída (padrão: _PTBR.*)",
    )
    parser.add_argument(
        "--mapping",
        default=None,
        help="Caminho do *_reinsertion_mapping.json (opcional)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Abortar se algum texto exceder o limite",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula a reinserção sem escrever arquivos",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Não criar backup .bak/.bak2",
    )
    parser.add_argument(
        "--force-blocked",
        action="store_true",
        help="Tentar reinserir itens marcados como reinsertion_safe=false",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Caminho do relatório JSON (opcional)",
    )

    args = parser.parse_args()

    rom_path = Path(args.rom)
    translated_path = Path(args.translated)

    if not rom_path.exists():
        print("Erro: ROM não encontrada.")
        return 2
    if not translated_path.exists():
        print("Erro: arquivo traduzido não encontrado.")
        return 2

    output_path = (
        Path(args.output)
        if args.output
        else rom_path.with_name(rom_path.stem + "_PTBR" + rom_path.suffix)
    )

    reinserter = SegaReinserter(str(rom_path))
    translations = reinserter.load_translations(str(translated_path))

    success, message = reinserter.reinsert(
        translations=translations,
        output_rom_path=str(output_path),
        create_backup=not args.no_backup,
        force_blocked=args.force_blocked,
        strict=args.strict,
        dry_run=args.dry_run,
        report_path=args.report,
        mapping_path=args.mapping,
    )

    print(message)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
