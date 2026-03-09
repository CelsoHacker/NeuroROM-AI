from pathlib import Path
import re

p = Path("romtxt_pipeline_v1.py")
s = p.read_text(encoding="utf-8", errors="replace").splitlines(True)

if any("TRANSLATE_DIAGNOSTICS_V1" in ln for ln in s):
    print("[OK] diagnostics já instalado")
    raise SystemExit(0)

txt = "".join(s)

m = re.search(r"^def cmd_translate\(args: argparse\.Namespace\) -> int:\s*\n", txt, re.M)
if not m:
    print("[ERRO] não achei cmd_translate")
    raise SystemExit(1)

start = m.start()
m2 = re.search(r"^def cmd_\w+\(args: argparse\.Namespace\) -> int:\s*\n", txt[m.end():], re.M)
end = (m.end() + m2.start()) if m2 else len(txt)

block = txt[start:end].splitlines(True)

# 1) garantir lista translate_diagnostics logo após init ok/erros
ins_idx = None
for i, ln in enumerate(block[:260]):
    if re.search(r"\bok\s*=\s*0\b", ln) or re.search(r"\b(erros|errors)\s*=\s*0\b", ln):
        ins_idx = i + 1
if ins_idx is None:
    ins_idx = 1

diag_init = "    # TRANSLATE_DIAGNOSTICS_V1\n    translate_diagnostics = []  # lista de dicts, 1 por erro contado\n\n"
block.insert(ins_idx, diag_init)

# 2) após cada incremento de erros, anexar diagnóstico
patched_err_increments = 0
out = []
for ln in block:
    out.append(ln)
    if re.search(r"\b(erros|errors)\s*\+=\s*1\b", ln):
        patched_err_increments += 1
        out.append("        try:\n")
        out.append('            _it = locals().get("it") or locals().get("item") or locals().get("rec")\n')
        out.append('            _reason = locals().get("reason") or locals().get("err_reason") or locals().get("why")\n')
        out.append('            _exc = locals().get("e")\n')
        out.append("            if isinstance(_it, dict):\n")
        out.append("                translate_diagnostics.append({\n")
        out.append('                    "id": _it.get("id"),\n')
        out.append('                    "offset": _it.get("offset"),\n')
        out.append('                    "max_length": _it.get("max_length") or _it.get("max_bytes") or _it.get("max_len"),\n')
        out.append('                    "reason": str(_reason) if _reason else "counted_as_error",\n')
        out.append('                    "exc": (type(_exc).__name__ + ":" + str(_exc)) if _exc else None,\n')
        out.append('                    "source_preview": (str(_it.get("source") or "")[:160]),\n')
        out.append('                    "translated_preview": (str(_it.get("translated_text") or "")[:160]),\n')
        out.append("                })\n")
        out.append("        except Exception:\n")
        out.append("            pass\n")

# 3) antes do print [OK] TRANSLATE..., salvar JSONL
saved = False
final = []
for ln in out:
    if (not saved) and ("[OK] TRANSLATE |" in ln):
        final.append("    # TRANSLATE_DIAGNOSTICS_V1: exporta diagnósticos (somente os itens contados como erro)\n")
        final.append('    diag_path = out_dir / f"{crc32}_translate_diagnostics.jsonl"\n')
        final.append('    with diag_path.open("w", encoding="utf-8") as f:\n')
        final.append("        for row in translate_diagnostics:\n")
        final.append('            f.write(json.dumps(row, ensure_ascii=False) + "\\n")\n')
        saved = True
    final.append(ln)

new_block = "".join(final)
new_txt = txt[:start] + new_block + txt[end:]
p.write_text(new_txt, encoding="utf-8")

print(f"[OK] diagnostics instalado | increments_patched={patched_err_increments} | export={{CRC32}}_translate_diagnostics.jsonl")
