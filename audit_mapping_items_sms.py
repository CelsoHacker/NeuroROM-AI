@'
import argparse, json, re, zlib
from pathlib import Path
from collections import Counter

# ============================================================
# audit_mapping_items_sms.py
# - NÃO faz scan cego: só lê os ranges (offset,max_length) do mapping
# - Filtra itens com alta probabilidade de serem TEXTO real (SMS)
# - Escreve mapping filtrado e um report
# ============================================================

PRINTABLE = set(range(0x20, 0x7F))  # ASCII visível
ALLOW_CTRL = {0x0A, 0x0D, 0x09}     # \n \r \t

def _crc32_bytes(b: bytes) -> str:
    return f"{(zlib.crc32(b) & 0xFFFFFFFF):08X}"

def _parse_int(v):
    if v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        s = v.strip()
        if s.lower().startswith("0x"):
            return int(s, 16)
        if re.fullmatch(r"[0-9A-Fa-f]+", s) and len(s) > 6:
            # hex sem 0x (comum em dumps)
            return int(s, 16)
        return int(s)
    raise TypeError(f"Valor numérico inválido: {type(v)}")

def _parse_terminator(v):
    if v is None:
        return None
    if isinstance(v, int):
        return v & 0xFF
    if isinstance(v, str):
        s = v.strip()
        if s == "":
            return None
        if s.lower().startswith("0x"):
            return int(s, 16) & 0xFF
        if re.fullmatch(r"[0-9A-Fa-f]{2}", s):
            return int(s, 16) & 0xFF
        return int(s) & 0xFF
    return None

def _get_items(mapping_obj: dict):
    # Preferência: raiz "items" (formato do expand-pointer-tables)
    if isinstance(mapping_obj.get("items"), list):
        return mapping_obj["items"]
    # Fallback: schema com text_blocks -> items
    items = []
    tb = mapping_obj.get("text_blocks")
    if isinstance(tb, list):
        for block in tb:
            if isinstance(block, dict) and isinstance(block.get("items"), list):
                items.extend(block["items"])
    return items

def _slice_item_bytes(rom: bytes, offset: int, max_len: int, terminator: int | None) -> bytes:
    if offset < 0 or offset >= len(rom):
        return b""
    end = min(offset + max_len, len(rom))
    chunk = rom[offset:end]
    if terminator is not None:
        idx = chunk.find(bytes([terminator]))
        if idx != -1:
            chunk = chunk[:idx]
    return chunk

def _longest_run_ratio(b: bytes) -> float:
    if not b:
        return 0.0
    best = 1
    cur = 1
    for i in range(1, len(b)):
        if b[i] == b[i-1]:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 1
    return best / max(1, len(b))

def _preview(b: bytes, limit=160) -> str:
    # latin-1 preserva bytes 0x80-0xFF sem explodir
    s = b.decode("latin-1", errors="replace")
    # normaliza controles pra facilitar leitura no report
    s = s.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    return s[:limit]

def _score_text_like(b: bytes):
    # Retorna: (score 0..1, reason_str, features_dict)
    n = len(b)
    if n == 0:
        return 0.0, "empty", {}
    if n < 2:
        return 0.0, "too_short", {"len": n}

    printable = 0
    letters = 0
    spaces = 0
    ctrls = 0
    high = 0

    for x in b:
        if x >= 0x80:
            high += 1
        if x < 0x20 and x not in ALLOW_CTRL:
            ctrls += 1
        if x in PRINTABLE or x in ALLOW_CTRL:
            printable += 1
        if (0x41 <= x <= 0x5A) or (0x61 <= x <= 0x7A):
            letters += 1
        if x == 0x20:
            spaces += 1

    pr = printable / n
    lr = letters / n
    sr = spaces / n
    cr = ctrls / n
    hr = high / n
    rr = _longest_run_ratio(b)

    txt = b.decode("latin-1", errors="replace")
    has_word = bool(re.search(r"[A-Za-z]{3,}", txt))
    has_punct = any(ch in txt for ch in ".!,?:;-'")

    # Score base (quanto parece texto)
    score = 0.55 * pr
    score += 0.20 * min(1.0, lr / 0.35)         # letras suficientes
    score += 0.10 * (1.0 if (sr >= 0.02) else 0.0)  # espaço ajuda (frases)
    score += 0.10 * (1.0 if has_word else 0.0)
    score += 0.05 * (1.0 if has_punct else 0.0)

    # Penalidades (quanto parece dado/binário/tile)
    score -= 0.70 * hr
    score -= 0.60 * cr
    if rr > 0.35:
        score -= 0.25

    # Pequenas strings UI ainda podem ser texto
    if n <= 6 and lr >= 0.5 and pr >= 0.9:
        score = max(score, 0.75)

    score = max(0.0, min(1.0, score))

    # Reason “principal” (pra relatório)
    if n < 4:
        reason = "too_short"
    elif pr < 0.80:
        reason = "low_printable"
    elif hr > 0.05:
        reason = "high_bytes"
    elif cr > 0.08:
        reason = "control_bytes"
    elif (not has_word) and n >= 8:
        reason = "no_word"
    elif rr > 0.45:
        reason = "repetitive"
    else:
        reason = "low_score_or_ok"

    feats = {"len": n, "printable_r": pr, "letters_r": lr, "spaces_r": sr, "high_r": hr, "ctrl_r": cr, "run_r": rr, "has_word": has_word}
    return score, reason, feats

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True, help="Caminho da ROM (binário).")
    ap.add_argument("--mapping", required=True, help="Mapping JSON (expand-pointer-tables).")
    ap.add_argument("--out-dir", default="out", help="Diretório de saída.")
    ap.add_argument("--crc32", default=None, help="Força CRC32 8HEX (opcional).")
    ap.add_argument("--min-score", type=float, default=0.80, help="Threshold 0..1 (padrão: 0.80).")
    ap.add_argument("--write-filtered-mapping", action="store_true", help="Escreve {CRC32}_reinsertion_mapping.filtered.json.")
    ap.add_argument("--max-items", type=int, default=None, help="(debug) limita itens processados.")
    args = ap.parse_args()

    rom_path = Path(args.rom)
    map_path = Path(args.mapping)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rom = rom_path.read_bytes()
    mapping = json.loads(map_path.read_text(encoding="utf-8"))

    items = _get_items(mapping)
    if args.max_items:
        items = items[:args.max_items]

    crc = args.crc32 or mapping.get("file_crc32") or _crc32_bytes(rom)

    kept = []
    removed = []
    reasons = Counter()
    seen = set()  # dedup por (offset,max,term)

    for it in items:
        if not isinstance(it, dict):
            continue
        off = _parse_int(it.get("offset"))
        max_len = _parse_int(it.get("max_length") or it.get("max_bytes") or it.get("max_len"))
        term = _parse_terminator(it.get("terminator"))
        if off is None or max_len is None or max_len <= 0:
            reasons["missing_fields"] += 1
            removed.append((0.0, "missing_fields", it, b""))
            continue

        key = (off, max_len, term)
        if key in seen:
            reasons["duplicate"] += 1
            continue
        seen.add(key)

        chunk = _slice_item_bytes(rom, off, max_len, term)
        score, why, feats = _score_text_like(chunk)

        if score >= args.min_score:
            kept.append(it)
        else:
            reasons[why] += 1
            removed.append((score, why, it, chunk))

    # Escreve report
    rep = out_dir / f"{crc}_audit_sms_report.txt"
    lines = []
    lines.append(f"[ROM] CRC32={crc} ROM_SIZE={len(rom)}\n")
    lines.append(f"[AUDIT] items_in={len(items)} dedup={len(seen)} kept={len(kept)} removed={len(removed)} min_score={args.min_score}\n")
    lines.append("[REMOVED_TOP_REASONS]\n")
    for k, v in reasons.most_common(25):
        lines.append(f"- {k}: {v}\n")

    # amostras removidas mais “perto” do threshold (úteis pra calibrar)
    removed_sorted = sorted(removed, key=lambda x: x[0], reverse=True)
    lines.append("\n[REMOVED_SAMPLES_NEAR_THRESHOLD]\n")
    for score, why, it, chunk in removed_sorted[:25]:
        off = it.get("offset")
        mx = it.get("max_length") or it.get("max_bytes") or it.get("max_len")
        lines.append(f"- score={score:.3f} why={why} id={it.get('id')} off={off} max={mx} prev={_preview(chunk)}\n")

    rep.write_text("".join(lines), encoding="utf-8")

    # mapping filtrado
    if args.write_filtered_mapping:
        new_map = dict(mapping)
        new_map["items"] = kept
        out_map = out_dir / f"{crc}_reinsertion_mapping.filtered.json"
        out_map.write_text(json.dumps(new_map, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] AUDIT_SMS | CRC32={crc} | kept={len(kept)} removed={len(removed)} | report={rep.name}")

if __name__ == "__main__":
    main()
'@ | Set-Content -Encoding UTF8 .\audit_mapping_items_sms.py'
