# tools/filter_mapping_blocks.py
# Filtra reinsertion_mapping.json mantendo apenas o(s) bloco(s) de offsets mais densos.
# Ideia: reduzir risco de patchar dados/gráficos/código que parecem texto.

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional


OFFSET_KEYS = ("offset", "rom_offset", "off", "start", "addr")


def load_mapping(path: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Suporta:
      - JSON como lista de items
      - JSON como dict com chave 'items' (ou 'entries')
    Retorna (container, items_list). 'container' é o objeto raiz.
    """
    obj = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(obj, list):
        return {"__root_list__": True}, obj

    if isinstance(obj, dict):
        for k in ("items", "entries", "mapping", "data"):
            v = obj.get(k)
            if isinstance(v, list):
                return obj, v

        # fallback: procurar primeira lista de dicts
        for k, v in obj.items():
            if isinstance(v, list) and (len(v) == 0 or isinstance(v[0], dict)):
                return obj, v

    raise ValueError("Formato do mapping não reconhecido (esperado lista ou dict com lista).")


def get_offset(item: Dict[str, Any]) -> Optional[int]:
    """Extrai offset do item (várias chaves possíveis)."""
    for k in OFFSET_KEYS:
        if k in item:
            try:
                return int(item[k])
            except Exception:
                pass
    return None


def split_into_blocks(offsets: List[int], gap: int) -> List[Tuple[int, int, int]]:
    """
    offsets ordenados -> blocos.
    Retorna lista de (start, end, count) onde end é inclusivo.
    """
    if not offsets:
        return []

    blocks = []
    start = offsets[0]
    prev = offsets[0]
    count = 1

    for o in offsets[1:]:
        if o - prev <= gap:
            count += 1
            prev = o
        else:
            blocks.append((start, prev, count))
            start = o
            prev = o
            count = 1

    blocks.append((start, prev, count))
    return blocks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="reinsertion_mapping.json de entrada")
    ap.add_argument("--out", dest="out_path", required=True, help="arquivo de saída filtrado")
    ap.add_argument("--gap", type=int, default=0x400, help="gap máximo para considerar mesmo bloco (padrão 0x400)")
    ap.add_argument("--keep", default="top1", help="top1 | top2 | top3 (mantém N blocos com mais itens)")
    ap.add_argument("--dry-run", action="store_true", help="Só imprime blocos, não escreve arquivo")
    args = ap.parse_args()

    in_path = Path(args.in_path)
    out_path = Path(args.out_path)

    if not in_path.exists():
        print(f"[ERRO] mapping não existe: {in_path}")
        return 2

    container, items = load_mapping(in_path)

    pairs = []
    for idx, it in enumerate(items):
        if not isinstance(it, dict):
            continue
        off = get_offset(it)
        if off is None:
            continue
        pairs.append((off, idx))

    pairs.sort(key=lambda x: x[0])
    offsets = [p[0] for p in pairs]

    blocks = split_into_blocks(offsets, gap=args.gap)

    if not blocks:
        print("[ERRO] Nenhum offset encontrado no mapping.")
        return 2

    # rank por quantidade de itens
    ranked = sorted(blocks, key=lambda t: t[2], reverse=True)

    keep_n = 1
    if args.keep.lower() == "top2":
        keep_n = 2
    elif args.keep.lower() == "top3":
        keep_n = 3

    keep_blocks = ranked[:keep_n]
    keep_ranges = [(s, e) for (s, e, _) in keep_blocks]

    print("[BLOCKS] (ordenados por quantidade)")
    for i, (s, e, c) in enumerate(ranked[:10], 1):
        span = (e - s) + 1
        mark = " <KEEP>" if (s, e) in keep_ranges else ""
        print(f"  B{i:02d} @0x{s:06X}..0x{e:06X} span={span} items={c}{mark}")

    if args.dry_run:
        print("[DRY] Nenhum arquivo escrito.")
        return 0

    # Filtra items que caem dentro dos ranges mantidos
    def in_keep(off: int) -> bool:
        for s, e in keep_ranges:
            if s <= off <= e:
                return True
        return False

    kept = []
    for it in items:
        if not isinstance(it, dict):
            continue
        off = get_offset(it)
        if off is None:
            continue
        if in_keep(off):
            kept.append(it)

    # Reconstrói objeto raiz preservando formato original
    if container.get("__root_list__"):
        out_obj = kept
    else:
        # tenta recolocar na mesma chave onde estava a lista
        out_obj = container
        placed = False
        for k in ("items", "entries", "mapping", "data"):
            if isinstance(out_obj.get(k), list):
                out_obj[k] = kept
                placed = True
                break
        if not placed:
            # fallback: grava em 'items'
            out_obj["items"] = kept

    out_path.write_text(json.dumps(out_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] wrote={out_path} kept_items={len(kept)} total_items={len(items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
