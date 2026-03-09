import json
from pathlib import Path

crc="953F42E1"
out=Path("out")
proof=json.load(open(out/f"{crc}_proof_translate.json","r",encoding="utf-8"))
mapping=json.load(open(out/f"{crc}_reinsertion_mapping.json","r",encoding="utf-8"))

bad_reasons={"placeholders_mismatch","fallback_to_source_due_to_encode_error"}
bad_ids={e["id"] for e in proof.get("errors",[]) if e.get("reason") in bad_reasons}

items=[it for it in mapping.get("items",[]) if isinstance(it,dict) and it.get("id") in bad_ids]
dst=out/f"{crc}_needs_retranslate.jsonl"

with dst.open("w",encoding="utf-8") as f:
    for it in items:
        f.write(json.dumps({
            "id": it.get("id"),
            "offset": it.get("offset"),
            "max_length": it.get("max_length") or it.get("max_bytes"),
            "terminator": it.get("terminator"),
            "encoding": it.get("encoding"),
            "source_preview": (it.get("source") or it.get("source_text") or "")[:200],
            "translated_preview": (it.get("translated_text") or "")[:200],
        }, ensure_ascii=False) + "\n")

print("WROTE", dst, "items=", len(items))
