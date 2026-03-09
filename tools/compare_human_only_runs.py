#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compara dois arquivos human-only por offset.

Uso:
  python tools/compare_human_only_runs.py \
    --run-a RUN_A_only_safe_text_by_offset.txt \
    --run-b RUN_B_only_safe_text_by_offset.txt \
    --duplicate-policy first \
    --sample 30 \
    --out-lost lost_by_cut.txt \
    --out-dup-a dup_a.txt \
    --out-dup-b dup_b.txt

Observação:
  Os arquivos precisam estar no formato:
    [0xOFFSET] texto
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Literal

LINE_RE = re.compile(r"^\[(0x[0-9A-Fa-f]+)\]\s*(.*)$")


def load_map(
    path: Path,
    duplicate_policy: Literal["first", "last"] = "first",
) -> tuple[dict[str, str], list[dict]]:
    """
    Carrega arquivo [0xOFFSET] texto em mapa offset->texto.

    duplicate_policy:
      - first: mantém a 1ª ocorrência do offset.
      - last: mantém a última ocorrência do offset.
    """
    result: dict[str, str] = {}
    duplicates: list[dict] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.rstrip("\n")
            match = LINE_RE.match(line)
            if not match:
                continue
            offset = match.group(1).upper()
            text = match.group(2).strip()
            if offset not in result:
                result[offset] = text
                continue
            previous_text = result[offset]
            duplicates.append(
                {
                    "line": int(line_no),
                    "offset": offset,
                    "kept_before": previous_text,
                    "incoming": text,
                    "policy": duplicate_policy,
                }
            )
            if duplicate_policy == "last":
                result[offset] = text
    return result, duplicates


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compara dois arquivos only_safe_text por offset.",
    )
    parser.add_argument(
        "--run-a",
        required=True,
        help="Arquivo Run A (ex.: min_offset=null), formato [0xOFFSET] texto.",
    )
    parser.add_argument(
        "--run-b",
        required=True,
        help="Arquivo Run B (ex.: min_offset=65536), formato [0xOFFSET] texto.",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=30,
        help="Quantidade de exemplos perdidos para imprimir (padrão: 30).",
    )
    parser.add_argument(
        "--out-lost",
        default="",
        help="Arquivo de saída com offsets perdidos no corte.",
    )
    parser.add_argument(
        "--duplicate-policy",
        choices=["first", "last"],
        default="first",
        help="Policy para offsets duplicados nos arquivos de entrada.",
    )
    parser.add_argument(
        "--out-dup-a",
        default="",
        help="Arquivo de saída com duplicatas detectadas no Run A.",
    )
    parser.add_argument(
        "--out-dup-b",
        default="",
        help="Arquivo de saída com duplicatas detectadas no Run B.",
    )
    args = parser.parse_args()

    path_a = Path(args.run_a)
    path_b = Path(args.run_b)
    if not path_a.exists():
        raise SystemExit(f"Arquivo Run A não encontrado: {path_a}")
    if not path_b.exists():
        raise SystemExit(f"Arquivo Run B não encontrado: {path_b}")

    run_a, dup_a = load_map(path_a, duplicate_policy=args.duplicate_policy)
    run_b, dup_b = load_map(path_b, duplicate_policy=args.duplicate_policy)

    lost_offsets = sorted(set(run_a.keys()) - set(run_b.keys()))
    gained_offsets = sorted(set(run_b.keys()) - set(run_a.keys()))

    print(f"kept_A: {len(run_a)}")
    print(f"kept_B: {len(run_b)}")
    print(f"lost_by_cut: {len(lost_offsets)}")
    print(f"gained_vs_A: {len(gained_offsets)}")
    print(f"duplicate_policy: {args.duplicate_policy}")
    print(f"duplicate_offsets_A: {len(dup_a)}")
    print(f"duplicate_offsets_B: {len(dup_b)}")
    print("")

    sample_n = max(0, int(args.sample))
    if sample_n > 0 and lost_offsets:
        print(f"Amostra de perdidos ({min(sample_n, len(lost_offsets))}):")
        for off in lost_offsets[:sample_n]:
            print(f"{off}\t{run_a.get(off, '')}")

    if args.out_lost:
        out_path = Path(args.out_lost)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8", newline="\n") as f:
            for off in lost_offsets:
                f.write(f"[{off}] {run_a.get(off, '')}\n")
        print("")
        print(f"Arquivo de perdidos salvo em: {out_path}")

    if args.out_dup_a:
        out_dup_a = Path(args.out_dup_a)
        out_dup_a.parent.mkdir(parents=True, exist_ok=True)
        with out_dup_a.open("w", encoding="utf-8", newline="\n") as f:
            f.write(f"# duplicate_policy={args.duplicate_policy}\n")
            for item in dup_a:
                f.write(
                    f"[{item['offset']}] line={item['line']} "
                    f"kept_before={item['kept_before']} "
                    f"incoming={item['incoming']}\n"
                )
        print(f"Duplicatas do Run A salvas em: {out_dup_a}")

    if args.out_dup_b:
        out_dup_b = Path(args.out_dup_b)
        out_dup_b.parent.mkdir(parents=True, exist_ok=True)
        with out_dup_b.open("w", encoding="utf-8", newline="\n") as f:
            f.write(f"# duplicate_policy={args.duplicate_policy}\n")
            for item in dup_b:
                f.write(
                    f"[{item['offset']}] line={item['line']} "
                    f"kept_before={item['kept_before']} "
                    f"incoming={item['incoming']}\n"
                )
        print(f"Duplicatas do Run B salvas em: {out_dup_b}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
