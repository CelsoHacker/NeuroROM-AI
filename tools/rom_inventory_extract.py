#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inventario e extracao de ROMs a partir de fontes configuradas.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import zipfile

ROM_EXTS = {
    ".sms",
    ".sg",
    ".gg",
    ".nes",
    ".sfc",
    ".smc",
    ".bin",
    ".gen",
    ".md",
    ".gba",
    ".z64",
    ".n64",
    ".v64",
    ".iso",
    ".cue",
    ".chd",
    ".pbp",
    ".ccd",
    ".img",
    ".mds",
    ".psx",
    ".raw",
    ".str",
    ".xa",
}

ARCHIVE_EXTS = {".zip", ".7z", ".rar"}
ZIP_EXTS = {".zip"}


def _load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _safe_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in " ._-()" else "_" for ch in name).strip()


def _collect_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


def _extract_zip(zip_path: Path, dest_dir: Path) -> tuple[bool, str]:
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        marker = dest_dir / ".extracted.ok"
        if marker.exists():
            return False, "ja_extraido"
        if any(dest_dir.iterdir()):
            return False, "destino_nao_vazio"
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest_dir)
        marker.write_text(datetime.now().isoformat(), encoding="utf-8")
        return True, "extraido"
    except Exception as e:
        return False, f"erro: {e}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventario e extracao de ROMs.")
    parser.add_argument(
        "--config",
        default=str(Path("config") / "rom_sources.json"),
        help="Caminho do JSON de fontes.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Arquivo de saida do inventario (JSON).",
    )
    parser.add_argument(
        "--extract-zip",
        action="store_true",
        help="Extrair arquivos .zip para a pasta configurada.",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"[ERRO] Config nao encontrado: {config_path}")
        return 1

    cfg = _load_config(config_path)
    extraction_root = Path(cfg.get("extraction_root", ""))
    sources = cfg.get("sources", [])

    inventory = {
        "generated_at": datetime.now().isoformat(),
        "config": str(config_path),
        "extraction_root": str(extraction_root),
        "sources": [],
        "pending_archives": [],
        "errors": [],
    }

    for src in sources:
        name = src.get("name", "Fonte")
        path_str = src.get("path", "")
        src_path = Path(path_str)
        entry = {
            "name": name,
            "path": path_str,
            "exists": src_path.exists(),
            "total_files": 0,
            "total_size_bytes": 0,
            "rom_files": 0,
            "archive_files": 0,
            "ext_counts": {},
            "rom_list": [],
            "archive_list": [],
            "extract_results": [],
        }

        if not src_path.exists():
            inventory["errors"].append(f"PATH_NOT_FOUND: {path_str}")
            inventory["sources"].append(entry)
            continue

        files = _collect_files(src_path)
        entry["total_files"] = len(files)
        entry["total_size_bytes"] = sum(p.stat().st_size for p in files)

        for p in files:
            ext = p.suffix.lower()
            entry["ext_counts"][ext] = entry["ext_counts"].get(ext, 0) + 1
            if ext in ROM_EXTS:
                entry["rom_files"] += 1
                entry["rom_list"].append(str(p))
            elif ext in ARCHIVE_EXTS:
                entry["archive_files"] += 1
                entry["archive_list"].append(str(p))

        if args.extract_zip and extraction_root:
            dest_base = extraction_root / _safe_name(name)
            for archive in entry["archive_list"]:
                ap = Path(archive)
                if ap.suffix.lower() in ZIP_EXTS:
                    dest_dir = dest_base / _safe_name(ap.stem)
                    ok, status = _extract_zip(ap, dest_dir)
                    entry["extract_results"].append(
                        {"archive": str(ap), "dest": str(dest_dir), "status": status}
                    )
                else:
                    inventory["pending_archives"].append(str(ap))

        inventory["sources"].append(entry)

    output_path = Path(args.output) if args.output else Path("export") / (
        "rom_inventory_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2, ensure_ascii=True)

    print(f"[OK] Inventario salvo em: {output_path}")
    if inventory["pending_archives"]:
        pending_path = output_path.with_suffix(".pending_archives.txt")
        with pending_path.open("w", encoding="utf-8") as f:
            f.write("\n".join(inventory["pending_archives"]))
        print(f"[WARN] Arquivos pendentes (rar/7z): {pending_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
