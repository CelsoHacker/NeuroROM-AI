"""Utilitários de I/O para ROM: backup incremental, escrita atômica e checksums."""

from __future__ import annotations

import hashlib
import os
import zlib
from pathlib import Path
from typing import Tuple


def compute_crc32(data: bytes) -> str:
    """Calcula CRC32 em hexadecimal (8 chars, uppercase)."""
    return f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"


def compute_sha256(data: bytes) -> str:
    """Calcula SHA256 em hexadecimal."""
    return hashlib.sha256(data).hexdigest()


def make_backup(path: Path) -> Path:
    """Cria backup incremental .bak, .bak2, .bak3... e retorna o caminho."""
    base = path.with_suffix(path.suffix + ".bak")
    if not base.exists():
        base.write_bytes(path.read_bytes())
        return base

    idx = 2
    while True:
        cand = path.with_suffix(path.suffix + f".bak{idx}")
        if not cand.exists():
            cand.write_bytes(path.read_bytes())
            return cand
        idx += 1


def atomic_write_bytes(target: Path, data: bytes) -> Path:
    """Escrita atômica: grava em arquivo temporário e substitui."""
    tmp = target.with_suffix(target.suffix + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, target)
    return target


def ensure_parent_dir(path: Path) -> None:
    """Garante que o diretório pai exista."""
    path.parent.mkdir(parents=True, exist_ok=True)


def compute_checksums(data: bytes) -> Tuple[str, str]:
    """Retorna (crc32, sha256)."""
    return compute_crc32(data), compute_sha256(data)
