"""NeuroROM SMS cleanup helper.

Use este script quando o Windows/patches acabam criando arquivos duplicados
(como ...py.py) e o Python passa a importar a versao errada do extrator.

Ele:
- remove __pycache__ do core
- remove arquivos duplicados de MASTER_SYSTEM_UNIVERSAL_EXTRACTOR* com extensao dupla
- remove versoes OLD/API_COMPAT duplicadas (se existirem)

Como rodar (na raiz do rom-translation-framework):
  python tools/sms_cleanup.py
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    core = root / "core"

    if not core.exists():
        print("[ERRO] Pasta core nao encontrada:", core)
        return 1

    deleted = []

    pycache = core / "__pycache__"
    if pycache.exists() and pycache.is_dir():
        shutil.rmtree(pycache, ignore_errors=True)
        deleted.append(str(pycache))

    patterns = [
        "MASTER_SYSTEM_UNIVERSAL_EXTRACTOR*.py.py",
        "MASTER_SYSTEM_UNIVERSAL_EXTRACTOR*_OLD*.py*",
        "MASTER_SYSTEM_UNIVERSAL_EXTRACTOR*_API_COMPAT*.py*",
    ]

    for pat in patterns:
        for p in core.glob(pat):
            if p.name == "MASTER_SYSTEM_UNIVERSAL_EXTRACTOR.py":
                continue
            try:
                p.unlink()
                deleted.append(str(p))
            except Exception as e:
                print("[WARN] Nao consegui apagar", p, "->", e)

    print("\n=== SMS cleanup ===")
    if deleted:
        print("Apagado:")
        for p in deleted:
            print(" -", p)
    else:
        print("Nada para apagar.")

    print("\nAgora garanta que exista APENAS:")
    print(" - core/MASTER_SYSTEM_UNIVERSAL_EXTRACTOR.py")
    print(" - core/MASTER_SYSTEM_COMPLETE_DATABASE.py")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
