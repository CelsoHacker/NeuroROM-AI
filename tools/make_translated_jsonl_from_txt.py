import argparse
import json
import re
from pathlib import Path
from difflib import SequenceMatcher

TOKEN_PATTERNS = [
    r"\{[^}]+\}",   # {TOKEN}
    r"\[[^\]]+\]",  # [TOKEN]
    r"<[^>]+>",     # <TOKEN>
]

def extract_tokens(s: str) -> list[str]:
    tokens = []
    for pat in TOKEN_PATTERNS:
        tokens.extend(re.findall(pat, s))
    return tokens

def _strip_prefixes(s: str) -> str:
    s = s.strip()
    for p in ("Original:", "ORIGINAL:", "Tradução:", "TRADUÇÃO:", "Traducao:", "TRADUCAO:"):
        if s.startswith(p):
            return s[len(p):].strip()
    return s

def fits_max_bytes(text: str, max_len_bytes: int, encoding: str) -> bool:
    try:
        enc = "utf-8" if encoding.lower() == "utf-8" else "ascii"
        b = text.encode(enc, errors="strict")
    except Exception:
        return False
    return len(b) <= int(max_len_bytes)

def pick_best_translation(a: str, b: str, src: str) -> str:
    a = _strip_prefixes(a)
    b = _strip_prefixes(b)
    src = src.strip()

    # Se uma das linhas for igual ao original, pega a outra
    if a == src and b != src:
        return b
    if b == src and a != src:
        return a

    # Se as duas diferem, escolhe a menos parecida com o original (heurística)
    ra = SequenceMatcher(None, a, src).ratio()
    rb = SequenceMatcher(None, b, src).ratio()
    return a if ra < rb else b

def normalize_translations(lines: list[str], items: list[dict]) -> list[str]:
    # Remove linhas vazias
    lines = [_strip_prefixes(x) for x in lines]
    lines = [x for x in lines if x.strip() != ""]

    n = len(items)

    # Caso perfeito: 22 linhas
    if len(lines) == n:
        return lines

    # Caso comum: 44 linhas (2 por item)
    if len(lines) == 2 * n:
        out = []
        for i, item in enumerate(items):
            a = lines[2*i]
            b = lines[2*i + 1]
            out.append(pick_best_translation(a, b, item.get("text_src", "")))
        return out

    raise SystemExit(f"ERRO: contagem diferente. jsonl={n} txt={len(lines)} (após limpar vazias)")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_jsonl", required=True)
    ap.add_argument("--in_txt", required=True)
    ap.add_argument("--out_jsonl", required=True)
    args = ap.parse_args()

    in_jsonl = Path(args.in_jsonl)
    in_txt = Path(args.in_txt)
    out_jsonl = Path(args.out_jsonl)

    items = []
    with in_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))

    raw_lines = in_txt.read_text(encoding="utf-8", errors="replace").splitlines()
    translations = normalize_translations(raw_lines, items)

    blocked = 0
    with out_jsonl.open("w", encoding="utf-8", newline="\n") as f:
        for item, t in zip(items, translations):
            src = item.get("text_src", "")
            max_len = item.get("max_len_bytes", 0)
            enc = item.get("encoding", "ascii")

            src_tokens = extract_tokens(src)
            tok_ok = all(tok in t for tok in src_tokens)
            len_ok = fits_max_bytes(t, max_len, enc)

            status = "OK"
            reason = None
            text_dst = t

            if not tok_ok:
                status = "BLOCKED"
                reason = "TOKENS_CHANGED"
                text_dst = src
                blocked += 1
            elif not len_ok:
                status = "BLOCKED"
                reason = "TOO_LONG_FOR_MAX_LEN_BYTES"
                text_dst = src
                blocked += 1

            item["text_dst"] = text_dst
            item["translation_status"] = status
            if reason:
                item["translation_block_reason"] = reason

            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"OK: gerado {out_jsonl.name} com {len(items)} itens. blocked={blocked}")

if __name__ == "__main__":
    main()
