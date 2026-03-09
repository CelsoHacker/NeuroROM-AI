#!/usr/bin/env python3
# Fix: ProjectConfig.EXTRACTION_DIR missing in interface_tradutor_final (1).py
# - Finds the interface file
# - Creates a .bak copy
# - Ensures `os` is imported
# - Injects a safe fallback that defines ProjectConfig.EXTRACTION_DIR when missing

import os
import re
from pathlib import Path

PATCH_MARKER_START = "# --- NeuroROM patch: ensure ProjectConfig.EXTRACTION_DIR exists ---"
PATCH_MARKER_END   = "# --- end patch ---"

PATCH_BLOCK = f'''{PATCH_MARKER_START}
try:
    if 'ProjectConfig' in globals() and not hasattr(ProjectConfig, 'EXTRACTION_DIR'):
        _base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        ProjectConfig.EXTRACTION_DIR = os.path.join(_base_dir, 'extraction')
except Exception:
    pass
{PATCH_MARKER_END}
'''

TARGET_NAMES = [
    "interface_tradutor_final (1).py",
    "interface_tradutor_final.py",
]

def _looks_like_docstring_start(s: str) -> bool:
    s = s.lstrip()
    return s.startswith('\"\"\"') or s.startswith(\"'''\")
def _docstring_delim(s: str) -> str | None:
    s = s.lstrip()
    if s.startswith('\"\"\"'):
        return '\"\"\"'
    if s.startswith(\"'''\"):
        return \"'''\"
    return None

def find_interface_file(root: Path) -> Path | None:
    # common expected path
    for name in TARGET_NAMES:
        p = root / "rom-translation-framework" / "interface" / name
        if p.exists():
            return p
        p = root / "interface" / name
        if p.exists():
            return p
    # recursive fallback (avoid venv/cache)
    for p in root.rglob("interface_tradutor_final*.py"):
        if any(part.lower() in ("venv", ".venv", "__pycache__", "site-packages") for part in p.parts):
            continue
        if p.name in TARGET_NAMES or "interface_tradutor_final" in p.name:
            return p
    return None

def ensure_import_os(lines: list[str]) -> list[str]:
    has_os = any(re.match(r"^\\s*import\\s+os(\\s|$)", ln) for ln in lines) or any(re.match(r"^\\s*from\\s+os\\s+import\\s+", ln) for ln in lines)
    if has_os:
        return lines

    insert_at = 0

    # skip shebang and encoding
    while insert_at < len(lines) and (lines[insert_at].startswith("#!") or re.match(r"^#\\s*-\\*-\\s*coding", lines[insert_at])):
        insert_at += 1

    # skip leading empty lines
    while insert_at < len(lines) and lines[insert_at].strip() == "":
        insert_at += 1

    # skip leading module docstring if present
    if insert_at < len(lines) and _looks_like_docstring_start(lines[insert_at]):
        q = _docstring_delim(lines[insert_at])
        insert_at += 1
        while insert_at < len(lines) and (q not in lines[insert_at]):
            insert_at += 1
        if insert_at < len(lines):
            insert_at += 1
        while insert_at < len(lines) and lines[insert_at].strip() == "":
            insert_at += 1

    # insert before first import/from if exists; else insert here
    for i in range(insert_at, min(insert_at + 400, len(lines))):
        if re.match(r"^\\s*(import|from)\\s+", lines[i]):
            insert_at = i
            break

    lines.insert(insert_at, "import os\\n")
    return lines

def inject_patch(lines: list[str]) -> list[str]:
    txt = "".join(lines)
    if PATCH_MARKER_START in txt:
        return lines  # already patched

    i = 0
    # skip shebang/encoding
    while i < len(lines) and (lines[i].startswith("#!") or re.match(r"^#\\s*-\\*-\\s*coding", lines[i])):
        i += 1
    while i < len(lines) and lines[i].strip() == "":
        i += 1

    # skip leading docstring
    if i < len(lines) and _looks_like_docstring_start(lines[i]):
        q = _docstring_delim(lines[i])
        i += 1
        while i < len(lines) and (q not in lines[i]):
            i += 1
        if i < len(lines):
            i += 1

    # move past import/from block
    while i < len(lines):
        ln = lines[i]
        if re.match(r"^\\s*(import|from)\\s+", ln) or ln.strip() == "" or ln.strip().startswith("#"):
            i += 1
            continue
        break

    lines.insert(i, "\\n" + PATCH_BLOCK + "\\n")
    return lines

def main() -> int:
    root = Path.cwd()
    target = find_interface_file(root)
    if not target:
        print("[ERRO] Não encontrei o arquivo da interface.")
        print("       Rode este script dentro da pasta do projeto (a que tem 'rom-translation-framework').")
        return 2

    original = target.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

    updated = ensure_import_os(original.copy())
    updated = inject_patch(updated)

    bak = target.with_suffix(target.suffix + ".bak")
    if not bak.exists():
        bak.write_text("".join(original), encoding="utf-8")

    target.write_text("".join(updated), encoding="utf-8")
    print("[OK] Patch aplicado em:", target)
    print("[OK] Backup criado em:", bak)
    print("[DICA] Agora rode a interface de novo.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
