import argparse
import json
import re
from pathlib import Path

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

def fits_max_bytes(text: str, max_len_bytes: int, encoding: str) -> bool:
    try:
        b = text.encode("utf-8" if encoding.lower() == "utf-8" else "ascii", errors="strict")
    except Exception:
        return False
    return len(b) <= int(max_len_bytes)

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
            if not line:
                continue
            items.append(json.loads(line))

    translations = [ln.rstrip("\n") for ln in in_txt.read_text(encoding="utf-8", errors="replace").splitlines()]

    if len(translations) != len(items):
        raise SystemExit(f"ERRO: contagem diferente. jsonl={len(items)} txt={len(translations)}")

    blocked = 0
    with out_jsonl.open("w", encoding="utf-8", newline="\n") as f:
        for item, t in zip(items, translations):
            src = item.get("text_src", "")
            max_len = item.get("max_len_bytes", 0)
            enc = item.get("encoding", "ascii")

            # valida placeholders simples
            src_tokens = extract_tokens(src)
            tok_ok = all(tok in t for tok in src_tokens)

            # valida tamanho em bytes
            len_ok = fits_max_bytes(t, max_len, enc)

            # decisão: se falhar, NÃO força reinserção; mantém texto_src como fallback
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
