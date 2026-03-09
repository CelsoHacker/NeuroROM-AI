import argparse, json, re, zlib

OFFSET_KEYS=["offset","ofs","start","addr","address"]
LEN_KEYS=["allocated_len","reserved_len","max_len","slot_len","orig_len","original_len","length"]
NEWHEX_KEYS=["new_bytes_hex","patched_bytes_hex","new_hex","bytes_hex","newBytesHex"]
TERM_KEYS=["terminator","term","end_byte","endByte"]

def crc32_hex(b): return f"{zlib.crc32(b)&0xFFFFFFFF:08X}"

def read(path):
    with open(path,"rb") as f: return f.read()

def p_int(v):
    if v is None: return None
    if isinstance(v,int): return v
    if isinstance(v,str):
        s=v.strip()
        if s.lower().startswith("0x"):
            try: return int(s,16)
            except: return None
        if re.fullmatch(r"[0-9a-fA-F]+",s):
            try: return int(s,16)
            except: return None
        if re.fullmatch(r"\d+",s):
            try: return int(s,10)
            except: return None
    return None

def diff_ranges(a,b):
    n=min(len(a),len(b))
    out=[]
    i=0
    while i<n:
        if a[i]!=b[i]:
            s=i; i+=1
            while i<n and a[i]!=b[i]: i+=1
            out.append((s,i))
        else:
            i+=1
    if len(a)!=len(b):
        out.append((n, max(len(a),len(b))))
    return out

def get_first(d, keys):
    for k in keys:
        if k in d: return d[k]
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--clean", required=True)
    ap.add_argument("--patched", required=True)
    ap.add_argument("--boot_limit", default="0x0400")
    args=ap.parse_args()

    clean=read(args.clean); patched=read(args.patched)
    boot=p_int(args.boot_limit)
    if boot is None: raise SystemExit("boot_limit inválido")

    print(f"[CLEAN] CRC32={crc32_hex(clean)} SIZE={len(clean)} (0x{len(clean):X})")
    print(f"[PATCH] CRC32={crc32_hex(patched)} SIZE={len(patched)} (0x{len(patched):X})")

    ranges=diff_ranges(clean, patched)
    total=sum(e-s for s,e in ranges)
    print(f"[DIFF] RANGES={len(ranges)} BYTES_CHANGED~={total}")
    for j,(s,e) in enumerate(ranges[:20], start=1):
        print(f"  #{j:02d} 0x{s:06X}..0x{e:06X} ({e-s} bytes)")
    if any(s<boot for s,_ in ranges):
        print(f"[ALERTA] Mudou abaixo de 0x{boot:06X} (região crítica) -> causa comum de tela preta.")
    else:
        print(f"[OK] Nenhuma mudança abaixo de 0x{boot:06X}.")

if __name__=="__main__":
    main()
