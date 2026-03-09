import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Analisa quantos itens no JSONL possuem reinsertion_safe=false."
    )
    parser.add_argument("--jsonl", required=True, help="Caminho do JSONL")
    args = parser.parse_args()

    path = Path(args.jsonl)
    if not path.exists():
        raise SystemExit(f"JSONL não encontrado: {path}")

    total = 0
    with_flag = 0
    true_count = 0
    false_count = 0
    invalid = 0

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                invalid += 1
                continue

            total += 1
            if "reinsertion_safe" in obj:
                with_flag += 1
                if obj.get("reinsertion_safe") is False:
                    false_count += 1
                else:
                    true_count += 1

    print("JSONL reinsertion_safe stats:")
    print(f"  total_linhas_validas: {total}")
    print(f"  linhas_com_flag: {with_flag}")
    print(f"  reinsertion_safe=true: {true_count}")
    print(f"  reinsertion_safe=false: {false_count}")
    print(f"  invalid_json: {invalid}")


if __name__ == "__main__":
    main()
