#!/usr/bin/env python3
# Fix ROM auto-find when loading extracted TXT files in interface_tradutor_final*.py
# - Adds support for *_extracted.txt, *_clean_blocks*.txt naming
# - Expands file dialog filter to show those files
# Creates a .bak backup next to each patched file.

import os
import re
import shutil
import sys
from pathlib import Path

REPLACEMENTS_CHAIN = (
    '.replace("_clean_blocks_optimized_translated.txt", "")'
    '.replace("_clean_blocks_optimized.txt", "")'
    '.replace("_clean_blocks.txt", "")'
    '.replace("_extracted_texts.txt", "")'
    '.replace("_extracted.txt", "")'
)

FILTER_NEEDLES = [
    '*_clean_blocks.txt',
    '*_clean_blocks_optimized.txt',
    '*_clean_blocks_optimized_translated.txt',
    '*_extracted.txt',
]


def patch_text(content: str) -> tuple[str, int]:
    changes = 0

    # 1) Extend rom_name sanitization chain in load_extracted_txt_directly (and similar blocks)
    # We anchor on the known start of the chain.
    pat = re.compile(r'(rom_name\s*=\s*os\.path\.basename\(file_path\)\.'
                     r'replace\("_CLEAN_EXTRACTED\.txt",\s*""\))')

    def _chain_inserter(m: re.Match) -> str:
        nonlocal changes
        chunk = m.group(1)
        if '_extracted.txt' in content or '_clean_blocks.txt' in content:
            # still ensure chain exists in THIS occurrence
            # If chain already inserted, skip.
            # We'll check locally around match span (next 300 chars).
            start = m.start(1)
            local = content[start:start+400]
            if '_extracted.txt' in local or '_clean_blocks.txt' in local:
                return chunk
        changes += 1
        return chunk + REPLACEMENTS_CHAIN

    new_content, n = pat.subn(_chain_inserter, content)
    if n:
        # subn counts matches; changes counts actual modifications
        content = new_content

    # 2) Expand file dialog filter for Carregar TXT Extraído
    # Look for the filter string that starts with "Text Files (" and includes *_CLEAN_EXTRACTED.txt
    filter_pat = re.compile(r'(Text Files \(\*\_CLEAN_EXTRACTED\.txt[^\)]*\))')

    def _filter_expand(m: re.Match) -> str:
        nonlocal changes
        s = m.group(1)
        if all(x in s for x in FILTER_NEEDLES):
            return s
        # insert missing needles before closing parenthesis
        before = s[:-1]  # drop ')'
        for needle in FILTER_NEEDLES:
            if needle not in before:
                before += f' {needle}'
        changes += 1
        return before + ')'

    content2, n2 = filter_pat.subn(_filter_expand, content)
    if n2:
        content = content2

    return content, changes


def find_targets(project_root: Path) -> list[Path]:
    candidates = [
        project_root / 'rom-translation-framework' / 'interface' / 'interface_tradutor_final (1).py',
        project_root / 'rom-translation-framework' / 'interface' / 'interface_tradutor_final.original.py',
        project_root / 'rom-translation-framework' / 'interface' / 'interface_tradutor_final.py',
    ]
    return [p for p in candidates if p.exists()]


def main() -> int:
    project_root = Path.cwd()
    if len(sys.argv) > 1:
        project_root = Path(sys.argv[1]).expanduser().resolve()

    targets = find_targets(project_root)
    if not targets:
        print('[ERRO] Não achei interface_tradutor_final*.py dentro de rom-translation-framework/interface')
        print('Dica: rode este script dentro da pasta PROJETO_V5_OFICIAL (onde existe a pasta rom-translation-framework).')
        return 2

    total_changes = 0
    for path in targets:
        raw = path.read_text(encoding='utf-8', errors='ignore')
        patched, changes = patch_text(raw)
        if changes:
            bak = path.with_suffix(path.suffix + '.bak')
            shutil.copy2(path, bak)
            path.write_text(patched, encoding='utf-8', errors='ignore')
            print(f'[OK] Patcheado: {path} (backup: {bak.name})')
            total_changes += changes
        else:
            print(f'[OK] Já estava atualizado: {path}')

    if total_changes == 0:
        print('[INFO] Nenhuma alteração necessária.')
    else:
        print(f'[INFO] Alterações aplicadas: {total_changes}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
