import json
from pathlib import Path

out_dir = Path("out")
crc = "953F42E1"

proof_path = out_dir / f"{crc}_proof_translate.json"
mapping_path = out_dir / f"{crc}_reinsertion_mapping.json"
diag_path = out_dir / f"{crc}_translate_diagnostics.jsonl"

proof = json.load(open(proof_path, "r", encoding="utf-8"))
mapping = json.load(open(mapping_path, "r", encoding="utf-8"))

items = mapping.get("items", [])
by_id = {it.get("id"): it for it in items if isinstance(it, dict)}

errs = proof.get("errors", [])

with diag_path.open("w", encoding="utf-8") as f:
    for e in errs:
        _id = e.get("id")
        it = by_id.get(_id, {})
        row = {
            "id": _id,
            "offset": e.get("offset"),
            "reason": e.get("reason"),
            "max_length": it.get("max_length") or it.get("max_bytes") or it.get("max_len"),
            "terminator": it.get("terminator"),
            "encoding": it.get("encoding"),
            "source_preview": (it.get("source") or it.get("source_text") or "")[:160],
            "translated_preview": (it.get("translated_text") or "")[:160],
        }
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

print("WROTE", diag_path, "lines=", len(errs))
